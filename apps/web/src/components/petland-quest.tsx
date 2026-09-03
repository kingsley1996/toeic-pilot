"use client";

import {
  API_ROUTES,
  type EncounterHint,
  type EncounterPublic,
  type EncounterResult,
} from "@toeic-pilot/shared";
import { Lightbulb, Volume2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { clock, secondsLeft } from "@/components/petland-countdown";
import { Button, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { notifyPet } from "@/lib/pet-notice";

/**
 * Thẻ nhiệm vụ của một cuộc chạm mặt (ADR-012 §3).
 *
 * **Bài tập diễn ra NGAY TRONG bảng**, không đẩy sang màn học: một cú chuyển
 * trang cho một xung động kéo dài hai mươi giây thì xung động ấy chết giữa
 * đường. Nhưng "trong bảng" chỉ nói về chỗ hiển thị — câu trả lời vẫn đi ra
 * đúng endpoint có bộ chấm thật, và với từ vựng thì đó là SM-2.
 *
 * **Không có lật thẻ ở đây**, dù màn từ vựng vẫn có. Lật thẻ là *tự chấm*, và
 * tự chấm không dùng được ở chỗ có phần thưởng: một cái nút "tôi nhớ rồi" trả
 * ruby là một cái nút in tiền, và nó cũng không đo được gì vì người bấm chính
 * là người được thưởng. Ba dạng ở đây đều **máy chấm**: gõ lại từ, chọn nghĩa,
 * và chép chính tả.
 *
 * Nên thẻ này không có phép chấm nào. Nó gửi đúng thứ người học nhập vào; máy
 * chủ mới là chỗ biết thứ ấy đúng hay sai.
 */

export function QuestCard({
  token,
  encounter,
  autoFocusInput,
  onChange,
  onFight,
  onClose,
}: {
  token: string;
  encounter: EncounterPublic;
  /**
   * Có tự đặt con trỏ vào ô nhập không.
   *
   * `false` khi thẻ mở ra do con thú HÚC vào vị khách: lúc ấy người dùng đang
   * lái bằng bàn phím, và cướp focus nghĩa là phím W tiếp theo gõ chữ "w" vào ô
   * nhập thay vì đi lên — bàn phím trông như chết mà không có lý do nào hiện ra.
   */
  autoFocusInput: boolean;
  /** Cuộc chạm mặt sau khi trả lời, hoặc `null` khi nó đã xong hoặc đã hết. */
  onChange: (next: EncounterPublic | null) => void;
  /**
   * Một đòn vừa trúng kẻ xâm nhập. `win` là đòn kết liễu.
   *
   * Gọi TRƯỚC `onChange`, và thứ tự ấy là load-bearing: `onChange(null)` gỡ vị
   * khách khỏi bản đồ, nên báo trận đánh sau đó thì nó đánh vào chỗ trống.
   */
  onFight: (win: boolean) => void;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [diff, setDiff] = useState<Array<{ op: string; word: string }> | null>(null);
  const [tried, setTried] = useState<string[]>([]);
  /*
   * Gợi ý VÀ số lượt còn lại, cả hai đến từ máy chủ.
   *
   * Số lượt khởi tạo từ `task.hints_left` chứ không từ một hằng số ở đây: bộ đếm
   * sống ở `encounter.hints_used`, nên đếm lùi từ 2 trong trình duyệt sẽ mời
   * người dùng bấm một cái nút chắc chắn trả về 409 sau khi tải lại trang.
   */
  const [hint, setHint] = useState<string | null>(null);
  const [hintsLeft, setHintsLeft] = useState(encounter.task.hints_left);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  /*
   * Đồng hồ đếm ngược, nhịp một giây, sống trong chính thẻ này.
   *
   * Ở đây nó quan trọng hơn ở danh sách: người dùng đang GÕ DỞ một câu trả lời,
   * và cuộc chạm mặt vẫn có hạn. Không có con số này thì cái hạn ấy ập đến như
   * một lỗi — bấm "Kiểm tra" và nhận 409 mà không hiểu vì sao.
   */
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(tick);
  }, []);
  const left = secondsLeft(encounter.expires_at, now);

  const task = encounter.task;
  const danger = encounter.kind === "intruder";

  async function answer(payload: { text?: string; choice?: string }) {
    if (busy) return;
    setBusy(true);
    setFailed(null);
    try {
      const result = await apiFetch<EncounterResult>(API_ROUTES.petEncounterAnswer(encounter.id), {
        method: "POST",
        token,
        body: JSON.stringify(payload),
      });
      setDiff(result.word_diff ?? null);
      // Chỉ kẻ xâm nhập mới có trận đánh: một người đi đường nhờ ôn giúp một từ
      // mà bị con thú lao vào đấm thì lời thoại và hoạt cảnh kể hai câu chuyện
      // khác nhau.
      if (danger && result.correct) onFight(result.done);
      if (result.done) {
        notifyPet({
          tone: "ok",
          title: danger ? "Đã đẩy lui!" : "Xong nhiệm vụ",
          // Ruby vào `gains` chứ không viết vào câu chữ: ba con số phần thưởng
          // hiện cùng một kiểu ở mọi thông báo, nên mắt tìm chúng ở một chỗ.
          gains: { ruby: result.reward_ruby },
          sound: "complete",
          dedupeKey: `quest-${encounter.id}`,
        });
        onChange(null);
        onClose();
        return;
      }
      onChange(result.encounter);
      if (result.correct) {
        // Bước sau là một câu hỏi KHÁC (máy chủ bốc lại mục tiêu), nên câu vừa
        // gõ và những ô đã thử phải đi theo bước cũ. Dọn ở đây chứ không trong
        // một effect nghe ngóng `encounter`: `set-state-in-effect` cấm đúng cái
        // đó, và cũng không cần — chỉ nút này đổi được bước.
        setTyped("");
        setTried([]);
        setDiff(null);
        // Bước sau là một từ khác, và máy chủ đã đặt lại lượt gợi ý của nó. Giữ
        // lại gợi ý cũ ở đây là in một nửa từ CŨ lên trên đề bài mới.
        setHint(null);
        setHintsLeft(result.encounter?.task.hints_left ?? 0);
        return;
      }
      // Sai thì KHÔNG hiện đáp án. Cuộc chạm mặt vẫn đang chờ nên người học thử
      // lại được, và hiện đáp án ra lúc này biến lần thử sau thành một lần chép
      // — mà cuối lần thử sau thì có ruby.
      if (payload.choice) setTried((current) => [...current, payload.choice as string]);
      setFailed(
        task.mode === "dictation"
          ? "Chưa đúng trọn câu. Nghe lại và sửa những chữ được tô."
          : "Chưa đúng. Lượt ôn đã được ghi — thử lại nhé.",
      );
    } catch (err) {
      setFailed(err instanceof ApiError ? err.message : "Chưa gửi được câu trả lời.");
      if (err instanceof ApiError && err.status === 409) onChange(null);
    } finally {
      setBusy(false);
    }
  }

  async function takeHint() {
    if (busy || hintsLeft <= 0) return;
    setBusy(true);
    setFailed(null);
    try {
      const result = await apiFetch<EncounterHint>(API_ROUTES.petEncounterHint(encounter.id), {
        method: "POST",
        token,
      });
      setHint(result.hint);
      setHintsLeft(result.hints_left);
    } catch (err) {
      setFailed(err instanceof ApiError ? err.message : "Chưa lấy được gợi ý.");
      // 409 ở đây là "hết lượt" hoặc "cuộc đã kết thúc"; cả hai đều nghĩa là cái
      // nút không nên mời bấm nữa.
      if (err instanceof ApiError && err.status === 409) setHintsLeft(0);
    } finally {
      setBusy(false);
    }
  }

  const ready = typed.trim().length > 0;

  return (
    <div className="max-h-[35vh] w-full shrink-0 overflow-y-auto border-t border-rule p-3 sm:h-[var(--pet-map-h)] sm:max-h-none sm:w-[var(--pet-egg-w)] sm:border-l sm:border-t-0">
      <div className="flex items-center justify-between gap-3">
        <h3 className={cx("text-small font-semibold", danger ? "text-alert" : "text-warn")}>
          {danger ? "Kẻ xâm nhập" : "Có người cần giúp"}
          {encounter.steps_total > 1 && (
            <span className="ml-2 font-data font-normal tabular-nums text-ink-muted">
              {encounter.steps_done}/{encounter.steps_total}
            </span>
          )}
        </h3>
        {/* Dưới một phút thì đổi màu: đó là lúc con số thôi là thông tin và bắt
            đầu là một lời khuyên nên gõ nhanh lên. */}
        <span
          className={cx(
            "ml-auto font-data text-label tabular-nums",
            left <= 60 ? "text-alert" : "text-ink-faint",
          )}
        >
          {clock(left)}
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Đóng nhiệm vụ"
          className="grid h-6 w-6 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink"
        >
          <X size={14} strokeWidth={2} aria-hidden />
        </button>
      </div>

      <p className="mt-1 text-small text-ink-muted">
        {danger
          ? `Trả lời đúng ${encounter.steps_total} lần để đẩy lui.`
          : task.mode === "dictation"
            ? "Nghe và chép lại giúp một câu, nhận thưởng."
            : "Trả lời giúp một từ, nhận thưởng."}
      </p>

      {task.mode === "typing" && task.prompt ? (
        <div className="mt-3 rounded border border-rule-strong p-3">
          <p className="text-body text-ink">{task.prompt}</p>
          {task.part_of_speech && (
            <p className="font-data text-label text-ink-faint">{task.part_of_speech}</p>
          )}
          <input
            value={typed}
            autoFocus={autoFocusInput}
            onChange={(event) => setTyped(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && ready) void answer({ text: typed });
            }}
            placeholder="Gõ từ tiếng Anh"
            aria-label="Từ tiếng Anh"
            className="mt-2 w-full rounded border border-rule-strong bg-surface px-2 py-1 text-small text-ink outline-none focus-visible:border-accent"
          />
          {/* Gợi ý in RIÊNG một dòng, không đổ vào ô nhập.
              Đổ vào ô nhập thì người học mất luôn cái họ đang gõ dở, và tệ hơn:
              phần máy mở ra trông y hệt phần họ tự nhớ, nên lần sau nhìn lại
              không phân biệt được mình đã nhớ tới đâu. */}
          {hint && <p className="mt-2 font-data text-body tracking-widest text-warn">{hint}</p>}

          <div className="mt-2 flex items-center gap-2">
            <Button size="sm" disabled={busy || !ready} onClick={() => answer({ text: typed })}>
              Kiểm tra
            </Button>
            {/* Nút mờ đi phải NÓI vì sao nó mờ.
                Bản đầu chỉ mất con số và xám lại, và câu hỏi đầu tiên nhận được
                đúng là "sao nút gợi ý bị disable" — một lời từ chối không nêu lý
                do thì người dùng đoán, và họ thường đoán là hỏng. */}
            <Button
              size="sm"
              variant="secondary"
              disabled={busy || hintsLeft <= 0}
              title={
                hintsLeft > 0
                  ? `Còn ${hintsLeft} lượt gợi ý`
                  : "Đã dùng hết 2 lượt gợi ý cho câu này"
              }
              onClick={() => void takeHint()}
            >
              <Lightbulb size={14} strokeWidth={2} aria-hidden />
              {hintsLeft > 0 ? `Gợi ý (${hintsLeft})` : "Hết gợi ý"}
            </Button>
          </div>
        </div>
      ) : task.mode === "choice" && task.choices ? (
        <div className="mt-3 rounded border border-rule-strong p-3">
          <p className="text-title text-ink">{task.prompt}</p>
          {task.part_of_speech && (
            <p className="font-data text-label text-ink-faint">{task.part_of_speech}</p>
          )}
          {/* Đánh số để nói ra rằng đây là bốn lựa chọn ngang hàng, không phải
              một danh sách có thứ tự ưu tiên. Ô đã thử sai bị gạch và khoá lại —
              bấm lại đúng ô vừa sai chỉ tốn thêm một lượt ôn mức QUÊN. */}
          <div className="mt-2 grid gap-1.5">
            {task.choices.map((choice, index) => (
              <button
                key={choice.key}
                type="button"
                disabled={busy || tried.includes(choice.key)}
                onClick={() => answer({ choice: choice.key })}
                className={cx(
                  "flex items-center gap-2 rounded border border-rule-strong px-2 py-1 text-left text-small transition-colors",
                  tried.includes(choice.key)
                    ? "text-ink-faint opacity-45 line-through"
                    : "text-ink hover:bg-recess",
                )}
              >
                <span className="font-data text-label text-ink-faint">{index + 1}</span>
                {choice.text}
              </button>
            ))}
          </div>
        </div>
      ) : task.mode === "dictation" && task.audio_url ? (
        <div className="mt-3 rounded border border-rule-strong p-3">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                const el = audioRef.current;
                if (!el) return;
                el.currentTime = 0;
                void el.play();
              }}
            >
              <Volume2 size={14} strokeWidth={2} aria-hidden />
              Nghe
            </Button>
            <span className="font-data text-label text-ink-faint">{task.word_count} từ</span>
          </div>
          {/* Không có `<track>`: phụ đề của một bài nghe-chép chính là đáp án. */}
          <audio ref={audioRef} src={task.audio_url} preload="auto" />

          <textarea
            value={typed}
            autoFocus={autoFocusInput}
            onChange={(event) => setTyped(event.target.value)}
            onKeyDown={(event) => {
              // Enter gửi bài, Shift+Enter xuống dòng. Một câu chép chính tả là
              // MỘT câu, nên phím Enter dùng để xuống dòng gần như không bao giờ
              // là thứ người ta muốn ở đây.
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (ready) void answer({ text: typed });
              }
            }}
            rows={3}
            placeholder="Gõ lại câu vừa nghe"
            aria-label="Câu vừa nghe"
            className="mt-2 w-full rounded border border-rule-strong bg-surface p-2 text-small text-ink outline-none focus-visible:border-accent"
          />

          {/* Chữ THIẾU hiện thành chấm, không hiện chữ. Cùng lý do
              `maskUnreached` ở màn chép chính tả: một bước sai rồi thử lại mà
              được xem đáp án thì lần thử sau chỉ là chép lại — và ở đây lần thử
              sau còn có ruby ở cuối. Chữ THỪA thì hiện nguyên, vì đó là chữ của
              chính người gõ và không tiết lộ gì. */}
          {diff && (
            <p className="mt-2 text-small leading-relaxed">
              {diff.map((word, index) => (
                <span
                  key={`${index}-${word.word}`}
                  className={cx(
                    "mr-1 inline-block",
                    word.op === "match" && "text-ok",
                    word.op === "missing" && "text-alert",
                    word.op === "extra" && "text-warn line-through",
                  )}
                >
                  {word.op === "missing" ? "•".repeat(Math.min(word.word.length, 12)) : word.word}
                </span>
              ))}
            </p>
          )}

          <Button
            size="sm"
            className="mt-2"
            disabled={busy || !ready}
            onClick={() => answer({ text: typed })}
          >
            Kiểm tra
          </Button>
        </div>
      ) : (
        <p className="mt-3 text-small text-warn">
          Nội dung của nhiệm vụ này không còn nữa. Cứ để nó tự hết hạn.
        </p>
      )}

      {failed && <p className="mt-2 text-small text-warn">{failed}</p>}
    </div>
  );
}
