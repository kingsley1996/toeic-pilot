"use client";

/**
 * Học từ vựng, hai hình thái:
 *
 * 1. LUỒNG TUẦN TỰ theo chủ đề (`TopicSession`, mode typing / flashcard / quiz):
 *    ĐI CHUNG MỘT cơ chế — đi qua TỪNG TỪ một; xong phần tương tác thì hiện
 *    MỘT bộ năm nút tự chấm (Học lại / Khó / Tốt / Dễ / Thành thạo) → ghi đúng
 *    MỘT grade đó qua endpoint thẻ lật `/review` → sang từ kế. Ba chế độ chỉ
 *    khác cách từ hiện ra: gõ từ, thẻ lật, hay trắc nghiệm. Progress vì thế
 *    chạy theo từng từ và đồng bộ giữa các tab.
 *
 * 2. BÀN CỜ NHIỀU TỪ (`MatchGame` + `QuizGame` ở trang minigame riêng):
 *    ghép/trắc nghiệm NHIỀU từ cùng lúc, không đi qua từng từ nên không nhét
 *    vào luồng tuần tự. TẠM KHÔNG bày bàn cờ ghép từ trên trang chủ đề — muốn
 *    thêm lại thì cho tab "match" dùng `MatchGame`, không nhét nó qua năm nút.
 *
 * Nút "Thành thạo" là điểm 6 của SM-2 (srs.py): đưa interval thẳng lên ngưỡng
 * đã-thuộc, nên bấm nó là từ lên "đã thuộc" ngay — không phải lời nói suông.
 * Riêng tab gõ từ nhờ MÁY chấm chính tả trước qua `/recall-check` (không ghi
 * điểm) rồi người học mới tự chọn mức độ nhớ; ghi điểm ở đó sẽ tính từ hai lần
 * trong cùng một lượt.
 */

import {
  API_ROUTES,
  type RecallCheck,
  type TopicSession as TopicSessionState,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import { RotateCcw, Trophy } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, ButtonLink, Kbd, Panel, Skeleton, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { recordReview, shuffle } from "@/lib/game";

export type LearnMode = "typing" | "flashcard" | "quiz";

// Số từ tối thiểu để từng chế độ hoạt động: quiz cần 1 đúng + 3 nhiễu từ chính
// hồ từ; match cần đủ cặp cho bàn cờ 4x4.
export const MATCH_PAIRS = 8;
export const MIN_WORDS = { typing: 1, flashcard: 1, quiz: 4, match: MATCH_PAIRS } as const;

// Năm nút tự chấm — thứ tự trái sang phải, giá trị là thang SM-2 engine hiểu:
// 0 quên · 3 khó · 4 tốt · 5 dễ · 6 thành thạo (điểm 6 là phần mở rộng có chủ
// đích: học viên khẳng định "thuộc rồi" và engine tôn trọng điều đó).
export const GRADE_OPTIONS = [
  { grade: 0, label: "Học lại", hint: "chưa nhớ", key: "1", bar: "bg-alert" },
  { grade: 3, label: "Khó", hint: "chật vật", key: "2", bar: "bg-warn" },
  { grade: 4, label: "Tốt", hint: "nhớ ra", key: "3", bar: "bg-ink-muted" },
  { grade: 5, label: "Dễ", hint: "nhớ ngay", key: "4", bar: "bg-action" },
  { grade: 6, label: "Thành thạo", hint: "thuộc luôn", key: "5", bar: "bg-ok" },
] as const;

/* --- luồng học tuần tự theo chủ đề ------------------------------------------ */

// Bàn cờ (thứ tự từ + đang học tới đâu) lưu TRÊN SERVER theo (user, topic) qua
// `/vocabulary-topic-sessions`: trạng thái học là dữ liệu người dùng — đi theo
// tài khoản, thấy được trong DB, không biến mất khi đổi trình duyệt hay xoá
// cache. Bàn cờ thuộc về CHỦ ĐỀ chứ không thuộc về tab, nên chuyển giữa gõ từ /
// thẻ lật / trắc nghiệm hay F5 vẫn nối tiếp đúng từ đang học.

// Khớp bàn cờ đã lưu với hồ từ hiện tại: hồ từ đổi đi một từ (thêm/bớt nội
// dung) thì bàn cờ cũ trỏ vào sai chỗ — trả `null` để xáo một bàn mới còn hơn
// nối tiếp một bàn cờ lệch.
function restoreBoard(
  saved: TopicSessionState,
  pool: VocabularySummary[],
): VocabularySummary[] | null {
  if (saved.entry_ids.length !== new Set(pool.map((entry) => entry.id)).size) return null;
  const byId = new Map(pool.map((entry) => [entry.id, entry]));
  const order: VocabularySummary[] = [];
  for (const id of saved.entry_ids) {
    const entry = byId.get(id);
    if (!entry) return null;
    order.push(entry);
  }
  return order;
}

export function TopicSession({
  pool,
  token,
  mode,
  topicId,
  backHref,
  onGraded,
}: {
  pool: VocabularySummary[];
  token: string;
  mode: LearnMode;
  /** Topic đang học — bàn cờ lưu theo đó, dùng chung cho cả ba module. */
  topicId: string;
  backHref?: string;
  /** Gọi sau mỗi lần chấm xong một từ — trang cha dùng để cập nhật progress. */
  onGraded?: (entryId: string, grade: number) => void;
}) {
  // `null` = chưa hỏi server; mảng = bàn cờ đã chốt (đã lưu hoặc mới xáo).
  const [order, setOrder] = useState<VocabularySummary[] | null>(null);
  const [index, setIndex] = useState(0);
  const [done, setDone] = useState(false);
  const [phase, setPhase] = useState<"interact" | "grade">("interact");

  // Ghi bàn cờ lên server — fire-and-forget với NGƯỜI GỌI: một lần lưu hỏng thì
  // mất chỗ ở lượt đó, nhưng điểm SM-2 vẫn được ghi qua /review và ván không
  // được phép đứng lại vì lỗi mạng.
  //
  // Nhưng các lượt ghi phải NỐI ĐUÔI NHAU, không bắn song song. Chấm nhanh bằng
  // phím 1–5 là hai PUT cách nhau vài chục mili-giây, và mỗi PUT ghi đè toàn bộ
  // `position`; nếu cái position=4 về tới máy chủ SAU cái position=5 thì bàn cờ
  // đã lưu lùi lại một từ, và người học mở lại phải học lại đúng từ vừa xong.
  // Không có gì báo — bản ghi cuối cùng vẫn hợp lệ, chỉ là sai.
  const writeQueue = useRef<Promise<void>>(Promise.resolve());
  const persistBoard = useCallback(
    (board: VocabularySummary[], position: number) => {
      const next = writeQueue.current.then(() =>
        apiFetch(API_ROUTES.vocabularyTopicSession(topicId), {
          method: "PUT",
          token,
          body: JSON.stringify({ entry_ids: board.map((entry) => entry.id), position }),
        })
          .then(() => {})
          .catch(() => {}),
      );
      writeQueue.current = next;
      return next;
    },
    [topicId, token],
  );

  // Đọc bàn cờ ĐÚNG MỘT LẦN khi mở: có thì nối tiếp, không (404) hay lệch hồ
  // từ thì xáo bàn mới và ghi lại ngay cho ván này có chỗ lưu.
  useEffect(() => {
    let stale = false;
    const startFresh = () => {
      const fresh = shuffle(pool);
      setOrder(fresh);
      setIndex(0);
      setDone(false);
      void persistBoard(fresh, 0);
    };
    apiFetch<TopicSessionState>(API_ROUTES.vocabularyTopicSession(topicId), { token })
      .then((saved) => {
        if (stale) return;
        const restored = restoreBoard(saved, pool);
        if (!restored) {
          startFresh();
          return;
        }
        setOrder(restored);
        setIndex(Math.min(saved.position, Math.max(0, restored.length - 1)));
        setDone(saved.done || saved.position >= restored.length);
      })
      .catch(() => {
        // 404 = chưa từng lưu; lỗi mạng khác thì cũng không đáng chặn học —
        // xáo bàn mới, ván vẫn ghi điểm qua /review như thường.
        if (!stale) startFresh();
      });
    return () => {
      stale = true;
    };
  }, [topicId, pool, token, persistBoard]);

  const word = order?.[index];

  const restart = useCallback(() => {
    if (!order) return;
    const fresh = shuffle(pool);
    setOrder(fresh);
    setIndex(0);
    setPhase("interact");
    setDone(false);
    void persistBoard(fresh, 0);
  }, [pool, order, persistBoard]);

  // Ghi ĐÚNG MỘT grade cho từ hiện tại rồi sang từ kế. Đây là thứ đảm bảo
  // progress không bị tính hai lần trong cùng một lượt học. onGraded báo về
  // trang cha SAU KHI server đã ghi điểm, để meter đọc lại con số thật. Bàn cờ
  // được ghi cùng lượt: `position` là số từ ĐÃ chấm, bằng `len` khi xong ván.
  const grade = useCallback(
    (g: number) => {
      if (!word || !order || done) return;
      void recordReview(token, word.id, g).then(() => onGraded?.(word.id, g));
      void persistBoard(order, Math.min(index + 1, order.length));
      if (index + 1 >= order.length) {
        setDone(true);
        return;
      }
      setPhase("interact");
      setIndex(index + 1);
    },
    [word, order, done, token, index, persistBoard, onGraded],
  );

  // Pha "chấm": phím 1–5 chọn mức, đúng nhịp bốn-nút của thẻ lật toàn cục.
  useEffect(() => {
    if (phase !== "grade") return;
    function onKey(event: KeyboardEvent) {
      const match = GRADE_OPTIONS.find((entry) => entry.key === event.key);
      if (match) grade(match.grade);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, grade]);

  if (!order || !word) return <Skeleton className="h-56" />;

  if (done) {
    return (
      <Panel className="px-6 py-10 text-center">
        <Trophy size={24} strokeWidth={1.75} aria-hidden className="mx-auto text-ok" />
        <p className="mt-3 text-subtitle font-semibold">Xong {order.length} từ</p>
        <p className="mt-1.5 text-small text-ink-muted">
          Mỗi lượt chấm đã được ghi lại, và lịch ôn kế tiếp đã được tính.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Button onClick={restart}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden />
            Học lại từ đầu
          </Button>
          {backHref && (
            <ButtonLink href={backHref} variant="secondary">
              Về danh sách từ
            </ButtonLink>
          )}
        </div>
      </Panel>
    );
  }

  const reveal = () => setPhase("grade");
  const revealed = phase === "grade";

  return (
    <Panel className="p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="font-data text-small tabular-nums text-ink-muted">
          Từ {index + 1}/{order.length}
        </p>
        <span className="text-small text-ink-faint">{revealed ? "Chấm mức độ nhớ" : "Xem từ"}</span>
      </div>

      {/* key = id của từ: đổi từ là remount, để state nội bộ (bài gõ, lựa chọn đã
          bấm) không chảy xuyên sang từ kế tiếp. min-h CỐ ĐỊNH + justify-center ở
          đây (chứ không phải ở từng step) để cả ba mode — cao thấp khác nhau —
          cùng đứng trong một khung không đổi, từ ngắn thì nằm giữa khung thay
          vì kéo khung co lại. Vùng chấm điểm bên dưới cũng giữ chỗ sẵn, nên
          hiện/mất dãy nút chấm không làm panel nhảy kích thước. */}
      <div className="flex min-h-80 flex-col justify-center">
        {mode === "typing" && (
          <TypingStep key={word.id} word={word} token={token} revealed={revealed} onDone={reveal} />
        )}
        {mode === "flashcard" && (
          <FlashcardStep key={word.id} word={word} revealed={revealed} onDone={reveal} />
        )}
        {mode === "quiz" && (
          <QuizStep key={word.id} word={word} pool={pool} revealed={revealed} onDone={reveal} />
        )}
      </div>

      {/* Vùng chấm GIỮ CHỖ SẴN (viền + khoảng trống) ngay cả khi chưa reveal:
          hiện dãy năm nút là lấp vào khung đã dành sẵn, panel không phình ra.
          Grid ba cột trên mobile giữ khung ở hai hàng thay vì ba. */}
      <div className="mt-5 min-h-[11rem] border-t border-rule pt-5 sm:min-h-[7rem]">
        {revealed && (
          <div className="animate-settle">
            <p className="mb-3 text-label font-semibold uppercase text-ink-faint">
              Bạn nhớ từ này thế nào?
            </p>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
              {GRADE_OPTIONS.map((entry) => (
                <button
                  key={entry.grade}
                  type="button"
                  onClick={() => grade(entry.grade)}
                  className={cx(
                    "flex items-center gap-2.5 rounded border border-rule-strong bg-panel px-2.5 py-2 text-left transition-colors",
                    "hover:bg-recess",
                  )}
                >
                  {/* Vạch màu mã hoá mức; chữ mới là thứ mang nghĩa. */}
                  <span aria-hidden className={cx("h-8 w-1 shrink-0", entry.bar)} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-small font-semibold">{entry.label}</span>
                    <span className="block text-label uppercase text-ink-faint">{entry.hint}</span>
                  </span>
                  <Kbd>{entry.key}</Kbd>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

function StepHeader({ word }: { word: VocabularySummary }) {
  return (
    <>
      <p className="text-label font-semibold uppercase text-ink-faint">{word.part_of_speech}</p>
      <p className="mt-2 text-title">{word.headword}</p>
      {word.phonetic && <p className="mt-1 font-data text-small text-ink-faint">{word.phonetic}</p>}
    </>
  );
}

/* --- thẻ lật: nhìn từ → lật ra nghĩa ---------------------------------------- */

function FlashcardStep({
  word,
  revealed,
  onDone,
}: {
  word: VocabularySummary;
  revealed: boolean;
  onDone: () => void;
}) {
  // Space để lật, đúng nhịp của thẻ lật toàn cục (/learn/review). Enter thì
  // KHÔNG: lỡ bật phím Enter sang màn chấm thì người học lật thẻ mà chưa kịp
  // nhìn.
  useEffect(() => {
    if (revealed) return;
    function onKey(event: KeyboardEvent) {
      if (event.code === "Space") {
        event.preventDefault();
        onDone();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [revealed, onDone]);

  // Cả tấm thẻ là một cái nút: bấm (hoặc Space) lật xoay quanh trục Y, nghĩa
  // hiện TRÊN MẶT SAU của thẻ tại chỗ chứ không mọc thêm nội dung bên dưới.
  // Hai mặt cùng mounted nên cú lật là animation thật; mặt sau che mặt trước
  // khi `is-flipped`. Chiều cao đặt CỐ ĐỊNH bằng khung của vùng game, để tấm
  // thẻ lấp đầy khung thay vì tự co giãn theo nội dung.
  //
  // Mặt đang quay ĐI được đánh `inert`, không phải `aria-hidden`. Cả hai mặt
  // luôn nằm trong DOM và `backface-visibility` chỉ giấu chúng khỏi MẮT — trình
  // đọc màn hình vẫn đọc cả hai, nên người dùng nó nghe thấy nghĩa của từ ngay
  // trước khi được hỏi có nhớ nghĩa không, tức là mất luôn bài tập. `inert` che
  // khỏi cây accessibility, khoá tương tác VÀ tự đẩy con trỏ ra khỏi phần tử
  // đang focus; `aria-hidden` không làm hai việc sau, và đặt nó lên chính cái
  // nút vừa được bấm là một vi phạm ARIA.
  return (
    <div className="flip-scene w-full">
      <div className={cx("flip-card h-80", revealed && "is-flipped")}>
        <button
          type="button"
          onClick={() => {
            if (!revealed) onDone();
          }}
          inert={revealed}
          aria-label="Lật thẻ để xem nghĩa"
          className="flip-face flex w-full flex-col justify-center rounded border border-rule-strong bg-panel p-6 text-left transition-colors hover:bg-recess"
        >
          <p className="text-label font-semibold uppercase text-ink-faint">Nhớ nghĩa của</p>
          <p className="mt-2 text-title">{word.headword}</p>
          {word.phonetic && (
            <p className="mt-1 font-data text-small text-ink-faint">{word.phonetic}</p>
          )}
          <p className="mt-6 flex items-center gap-2 text-small text-ink-muted">
            Bấm vào thẻ để lật
            <Kbd>Space</Kbd>
          </p>
        </button>
        <div
          className="flip-face flip-back flex flex-col justify-center rounded border border-rule-strong bg-panel p-6"
          inert={!revealed}
        >
          <p className="text-label font-semibold uppercase text-ink-faint">{word.headword}</p>
          <p className="mt-2 text-title">{word.meaning_vi}</p>
        </div>
      </div>
    </div>
  );
}

/* --- trắc nghiệm: chọn nghĩa đúng -------------------------------------------- */

/**
 * Bốn lựa chọn cho một từ: nghĩa đúng + ba nhiễu lấy từ chính hồ từ (cùng chủ đề
 * nên hợp lý, càng gần đúng càng khó).
 *
 * Lọc theo NGHĨA chứ không chỉ theo id, và đó là chỗ dễ bỏ sót: hai từ khác nhau
 * vẫn dịch ra cùng một tiếng Việt — trong kho hiện tại "quảng cáo" và "thường
 * xuyên" mỗi cái thuộc về hai từ. Một nhiễu trùng chữ với đáp án đúng làm hỏng
 * hai thứ cùng lúc: người học thấy hai ô y hệt nhau mà chỉ một ô được tô xanh,
 * và React nhận hai phần tử cùng `key` nên cảnh báo rồi render sai trạng thái.
 *
 * Khi hồ từ không đủ ba nghĩa khác nhau thì câu hỏi ít lựa chọn hơn, cố ý: một
 * câu ba lựa chọn vẫn trả lời được, còn bốn lựa chọn trong đó hai cái không phân
 * biệt được thì không.
 */
function buildOptions(word: VocabularySummary, pool: VocabularySummary[]): string[] {
  const seen = new Set([word.meaning_vi]);
  const distractors: string[] = [];
  for (const entry of shuffle(pool)) {
    if (distractors.length === 3) break;
    if (entry.id === word.id || seen.has(entry.meaning_vi)) continue;
    seen.add(entry.meaning_vi);
    distractors.push(entry.meaning_vi);
  }
  return shuffle([word.meaning_vi, ...distractors]);
}

function QuizStep({
  word,
  pool,
  revealed,
  onDone,
}: {
  word: VocabularySummary;
  pool: VocabularySummary[];
  revealed: boolean;
  onDone: () => void;
}) {
  // Đáp án xáo MỘT LẦN khi từ hiện ra (useState init + remount qua key ở cha) —
  // không tính lại trong render, nếu không lựa chọn nhảy chỗ mỗi lần bấm nút.
  const [options] = useState<string[]>(() => buildOptions(word, pool));
  const [picked, setPicked] = useState<string | null>(null);

  function pick(option: string) {
    if (picked !== null || revealed) return;
    setPicked(option);
    // Chờ một nhịp để người học kịp thấy đúng/sai rồi mới mở màn chấm.
    window.setTimeout(onDone, 550);
  }

  const correct = word.meaning_vi;

  return (
    <>
      <StepHeader word={word} />

      {/* Nhóm có nhãn: trình đọc màn hình gọi được tên cả dãy ("Các nghĩa để
          chọn") thay vì đọc bốn cái nút rời không rõ chúng thuộc về đâu. */}
      <div role="group" aria-label="Các nghĩa để chọn" className="mt-5 grid gap-2">
        {options.map((option) => {
          const isCorrect = option === correct;
          const isPicked = option === picked;
          return (
            <button
              key={option}
              type="button"
              onClick={() => pick(option)}
              disabled={picked !== null}
              className={[
                "rounded border px-4 py-3 text-left transition-colors",
                picked === null && "border-rule-strong hover:bg-recess",
                picked !== null && isCorrect && "border-ok bg-ok-tint text-ok",
                picked !== null &&
                  isPicked &&
                  !isCorrect &&
                  "border-alert bg-alert-tint text-alert",
                picked !== null && !isPicked && !isCorrect && "border-rule opacity-60",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {option}
            </button>
          );
        })}
      </div>
    </>
  );
}

/* --- gõ từ: máy chấm chính tả trước, người học tự chấm sau ------------------- */

const VERDICTS = {
  correct: { label: "Đúng rồi", tone: "text-ok", ring: "border-ok" },
  typo: { label: "Gần đúng — sai một ký tự", tone: "text-warn", ring: "border-warn" },
  wrong: { label: "Chưa đúng", tone: "text-alert", ring: "border-alert" },
  unknown: { label: "Chưa biết từ này", tone: "text-ink-muted", ring: "border-rule-strong" },
} as const;

type Verdict = keyof typeof VERDICTS;

function TypingStep({
  word,
  token,
  revealed,
  onDone,
}: {
  word: VocabularySummary;
  token: string;
  revealed: boolean;
  onDone: () => void;
}) {
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<RecallCheck | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Con trỏ nằm sẵn trong ô nhập — cả một phiên là hàng chục lượt gõ, phải với
  // tay ra chuột mỗi lần là khác biệt giữa một công cụ và một việc vặt.
  useEffect(() => {
    if (!revealed) inputRef.current?.focus();
  }, [revealed]);

  const check = useCallback(
    async ({ giveUp = false } = {}) => {
      // /recall-check chỉ CHẤM chính tả, không ghi điểm — điểm do năm nút tự
      // chấm phía sau ghi qua /review, đúng một lần.
      if (saving || result || revealed) return;
      if (!giveUp && !typed.trim()) return;
      setSaving(true);
      setError(null);
      try {
        const res = await apiFetch<RecallCheck>(API_ROUTES.recallCheck(word.id), {
          method: "POST",
          token,
          body: JSON.stringify({ typed, give_up: giveUp }),
        });
        setResult(res);
        window.setTimeout(onDone, 600);
      } catch {
        setError("Không chấm được câu trả lời.");
      } finally {
        setSaving(false);
      }
    },
    [word.id, token, typed, saving, result, revealed, onDone],
  );

  const verdict = result ? VERDICTS[result.verdict as Verdict] : null;

  return (
    <>
      <p className="text-label font-semibold uppercase text-ink-faint">
        {word.part_of_speech} — viết từ tiếng Anh cho nghĩa
      </p>
      <p className="mt-2 text-title">{word.meaning_vi}</p>

      <input
        ref={inputRef}
        value={typed}
        onChange={(event) => setTyped(event.target.value)}
        onKeyDown={(event) => {
          // Enter kiểm tra; chặn repeat để giữ phím không bắn nhiều request.
          if (event.key === "Enter" && !event.repeat) {
            event.preventDefault();
            void check();
          }
        }}
        // Đã sang màn chấm thì ô này đóng băng: kết quả là thứ cuối cùng nhìn vào.
        readOnly={result !== null || revealed}
        spellCheck={false}
        autoComplete="off"
        autoCapitalize="off"
        aria-label="Viết lại từ tiếng Anh"
        placeholder="viết từ tiếng Anh…"
        className={cx(
          "mt-5 w-full rounded border bg-recess px-4 py-3 font-data text-title outline-none",
          verdict ? verdict.ring : "border-rule-strong focus:border-action",
        )}
      />

      {error && <p className="mt-3 text-small text-alert">{error}</p>}

      {result ? (
        <div className="animate-settle mt-4">
          <p className={cx("font-semibold", verdict?.tone)}>{verdict?.label}</p>
          {/* Đáp án chỉ hiện khi chưa gõ đúng hẳn — in sau câu trả lời đúng chỉ
              làm nhiễu đúng lúc cần một tín hiệu "xong". */}
          {result.verdict !== "correct" && (
            <p className="mt-1 font-data text-title">{result.expected}</p>
          )}
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button disabled={saving || !typed.trim()} onClick={() => void check()}>
            Kiểm tra
            <Kbd>Enter</Kbd>
          </Button>
          <div className="flex-1" />
          {/* Lối ra trung thực: không có nó thì muốn đi tiếp phải bịa câu trả lời. */}
          <Button variant="quiet" disabled={saving} onClick={() => void check({ giveUp: true })}>
            Tôi chưa biết
          </Button>
        </div>
      )}
    </>
  );
}

/* --- ghép từ: bàn cờ 4x4, nhiều từ cùng lúc ---------------------------------- */

type Tile = { entryId: string; text: string; kind: "word" | "meaning" };

function buildTiles(pool: VocabularySummary[]): Tile[] {
  const cards = shuffle(pool).slice(0, MATCH_PAIRS);
  return shuffle(
    cards.flatMap((word) => [
      { entryId: word.id, text: word.headword, kind: "word" as const },
      { entryId: word.id, text: word.meaning_vi, kind: "meaning" as const },
    ]),
  );
}

export function MatchGame({
  pool,
  token,
  backHref,
  onFinish,
}: {
  pool: VocabularySummary[];
  token: string | null;
  backHref?: string;
  /** Bàn cờ kết thúc — dùng để trang cha cập nhật tiến độ chủ đề. */
  onFinish?: () => void;
}) {
  const [tiles, setTiles] = useState<Tile[]>(() => buildTiles(pool));
  // Ô đang chọn và các cặp đã xong — đều là CHỈ SỐ ô, vì cùng một từ hiện ở hai
  // ô khác nhau và phải ẩn được cả hai.
  const [picked, setPicked] = useState<number | null>(null);
  const [solvedTiles, setSolvedTiles] = useState<Set<number>>(new Set());
  // Hai ô báo đỏ trong giây lát sau một lần ghép sai. `locked` chặn bấm trong
  // lúc đó, để cái nháy đỏ kịp được nhìn thấy thay vì bị cú bấm kế tiếp nuốt mất.
  const [wrongTiles, setWrongTiles] = useState<Set<number>>(new Set());
  const [locked, setLocked] = useState(false);
  const [moves, setMoves] = useState(0);

  const done = solvedTiles.size === tiles.length;

  // Báo bàn cờ xong ĐÚNG MỘT LẦN — effect canh đúng thời điểm solvedTiles vừa đủ.
  // Chờ thêm một nhịp: grade của cặp cuối được ghi fire-and-forget, refetch ngay
  // sẽ đọc về con số thiếu đúng cặp đó.
  const finishedRef = useRef(false);
  useEffect(() => {
    if (!done || finishedRef.current) return;
    finishedRef.current = true;
    const timer = window.setTimeout(() => onFinish?.(), 500);
    return () => window.clearTimeout(timer);
  }, [done, onFinish]);

  const restart = useCallback(() => {
    setTiles(buildTiles(pool));
    setPicked(null);
    setSolvedTiles(new Set());
    setWrongTiles(new Set());
    setLocked(false);
    setMoves(0);
    finishedRef.current = false;
  }, [pool]);

  function pick(index: number) {
    if (locked || done || solvedTiles.has(index)) return;
    if (picked === null) {
      setPicked(index);
      return;
    }
    if (picked === index) {
      setPicked(null);
      return;
    }

    const first = tiles[picked]!;
    const second = tiles[index]!;
    setMoves((value) => value + 1);

    if (first.entryId === second.entryId) {
      // Ghép đúng một cặp = một lượt ôn được ghi (grade 4). Match không đi qua
      // năm nút vì nó diễn ra trên NHIỀU từ cùng lúc — năm nút chỉ dành cho
      // luồng đi qua từng từ.
      if (token) recordReview(token, first.entryId, 4);
      setSolvedTiles((prev) => new Set(prev).add(picked).add(index));
      setPicked(null);
      return;
    }

    // Sai: cả hai ô báo đỏ rồi mở khoá, KHÔNG giữ lại lựa chọn — flash ngắn đủ
    // nói "sai rồi", và giữ nguyên tay đang chọn chỉ làm người chơi rón rén.
    setWrongTiles(new Set([picked, index]));
    setPicked(null);
    setLocked(true);
    window.setTimeout(() => {
      setWrongTiles(new Set());
      setLocked(false);
    }, 650);
  }

  if (done) {
    return (
      <div className="rounded border border-rule bg-panel px-6 py-10 text-center">
        <Trophy size={24} strokeWidth={1.75} aria-hidden className="mx-auto text-ok" />
        <p className="mt-3 text-subtitle font-semibold">Xong trong {moves} lượt</p>
        <p className="mt-1.5 text-small text-ink-muted">
          {moves === MATCH_PAIRS
            ? "Không một lần nhầm — đỉnh luôn."
            : "Càng ít lượt nhầm càng chắc tay."}
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Button onClick={restart}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden />
            Chơi lại
          </Button>
          {backHref && (
            <ButtonLink href={backHref} variant="secondary">
              Về danh sách từ
            </ButtonLink>
          )}
        </div>
      </div>
    );
  }

  return (
    <Panel className="p-6">
      <p className="font-data text-small tabular-nums text-ink-muted">
        Ghép {(tiles.length - solvedTiles.size) / 2} cặp còn lại · {moves} lượt đã thử
      </p>

      {/* `invisible` thay vì unmount: ô đã ghép biến mất nhưng BÀN CỜ GIỮ HÌNH —
          một lưới 4x4 co lại theo từng cặp sẽ làm người chơi mất phương hướng. */}
      <div className="mx-auto mt-4 grid max-w-md grid-cols-4 gap-1.5 sm:gap-2">
        {tiles.map((tile, index) => {
          const isSolved = solvedTiles.has(index);
          const isPicked = picked === index;
          const isWrong = wrongTiles.has(index);
          return (
            <button
              key={`${tile.entryId}-${tile.kind}`}
              type="button"
              onClick={() => pick(index)}
              disabled={isSolved || locked}
              aria-label={isSolved ? "đã ghép" : undefined}
              className={cx(
                "grid aspect-square place-items-center rounded border p-1 text-center text-small leading-snug transition-colors",
                isSolved && "invisible",
                isWrong &&
                  cx("border-alert bg-alert-tint text-alert", tile.kind === "word" && "font-bold"),
                !isSolved &&
                  !isWrong &&
                  isPicked &&
                  cx(
                    "border-action bg-action-tint",
                    tile.kind === "word" ? "font-bold text-action-ink" : "text-ink",
                  ),
                !isSolved &&
                  !isWrong &&
                  !isPicked &&
                  cx(
                    "border-rule-strong bg-panel hover:bg-recess",
                    tile.kind === "word" ? "font-bold text-action-ink" : "text-ink",
                  ),
              )}
            >
              <span className="line-clamp-3 overflow-hidden break-words">{tile.text}</span>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}

/* --- trắc nghiệm dạng minigame riêng (vẫn là bảng điểm, không qua 5 nút) ------ */

const ROUND_SIZE = 10;
const GRADE_GOOD = 4;
const GRADE_FORGOT = 0;

interface Question {
  word: VocabularySummary;
  options: string[];
}

function buildRound(pool: VocabularySummary[]): Question[] {
  const cards = shuffle(pool).slice(0, ROUND_SIZE);
  return cards.map((word) => ({ word, options: buildOptions(word, pool) }));
}

export function QuizGame({
  pool,
  token,
  backHref,
}: {
  pool: VocabularySummary[];
  token: string | null;
  backHref?: string;
}) {
  const [round, setRound] = useState<Question[]>(() => buildRound(pool));
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);

  const start = useCallback(() => {
    setRound(buildRound(pool));
    setIndex(0);
    setPicked(null);
    setScore(0);
    setDone(false);
  }, [pool]);

  if (done) {
    return (
      <Panel className="px-6 py-10 text-center">
        <Trophy size={24} strokeWidth={1.75} aria-hidden className="mx-auto text-ok" />
        <p className="mt-3 text-subtitle font-semibold">
          Đúng {score}/{round.length}
        </p>
        <p className="mt-1.5 text-small text-ink-muted">
          {score === round.length
            ? "Trọn vẹn! Chủ đề này đã nằm lòng."
            : score >= round.length / 2
              ? "Khá lắm. Chơi thêm một ván để chắc hơn."
              : "Đừng nản — lặp lại vài lần là nhớ."}
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Button onClick={start}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden />
            Chơi lại
          </Button>
          {backHref && (
            <ButtonLink href={backHref} variant="secondary">
              Về danh sách từ
            </ButtonLink>
          )}
        </div>
      </Panel>
    );
  }

  const question = round[index];
  if (!question) return null;

  function pick(option: string) {
    if (picked !== null) return;
    setPicked(option);
    const correct = option === question!.word.meaning_vi;
    if (correct) setScore((value) => value + 1);
    if (token) recordReview(token, question!.word.id, correct ? GRADE_GOOD : GRADE_FORGOT);
  }

  function next() {
    if (index + 1 >= round.length) {
      setDone(true);
      return;
    }
    setIndex(index + 1);
    setPicked(null);
  }

  const correct = question.word.meaning_vi;

  return (
    <Panel className="p-6">
      <p className="font-data text-small tabular-nums text-ink-muted">
        Câu {index + 1}/{round.length} · đúng {score}
      </p>
      <p className="mt-3 text-label font-semibold uppercase text-ink-faint">Chọn nghĩa của</p>
      <p className="mt-2 text-[1.6rem] font-semibold leading-tight">{question.word.headword}</p>
      {question.word.phonetic && (
        <p className="mt-1 font-data text-small text-ink-faint">{question.word.phonetic}</p>
      )}

      <div className="mt-5 grid gap-2">
        {question.options.map((option) => {
          const isCorrect = option === correct;
          const isPicked = option === picked;
          return (
            <button
              key={option}
              type="button"
              onClick={() => pick(option)}
              disabled={picked !== null}
              className={[
                "rounded border px-4 py-3 text-left transition-colors",
                picked === null && "border-rule-strong hover:bg-recess",
                picked !== null && isCorrect && "border-ok bg-ok-tint text-ok",
                picked !== null &&
                  isPicked &&
                  !isCorrect &&
                  "border-alert bg-alert-tint text-alert",
                picked !== null && !isPicked && !isCorrect && "border-rule opacity-60",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {option}
            </button>
          );
        })}
      </div>

      {picked !== null && (
        <div className="mt-5 flex items-center justify-between gap-3">
          <p className="text-small text-ink-muted">
            {picked === correct ? "Đúng rồi!" : `Đáp án: ${correct}`}
          </p>
          <Button size="sm" onClick={next}>
            {index + 1 >= round.length ? "Xem kết quả" : "Câu tiếp"}
          </Button>
        </div>
      )}
    </Panel>
  );
}
