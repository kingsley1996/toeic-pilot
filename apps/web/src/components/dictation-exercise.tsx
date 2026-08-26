"use client";

import { API_ROUTES } from "@toeic-pilot/shared";
import { Check, CircleCheck } from "lucide-react";
import { useRef, useState } from "react";

import { Alert, Button, Kbd, Panel, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useToast } from "@/lib/toast";
import {
  annotateTyped,
  grade,
  maskUnreached,
  wrongSubmittedIndices,
  type GradeResult,
} from "@/lib/dictation";

/*
 * Xanh = đúng, cam = chưa đúng. Nhưng "chưa đúng" có hai vai trò ngược nhau, và
 * gán nhầm dấu gạch bỏ cho vai nào là chuyện đã xảy ra một lần:
 *
 *   missing — từ CỦA ĐÁP ÁN mà người học chưa gõ ra. Đây là thứ họ cần gõ.
 *   extra   — từ HỌ ĐÃ GÕ nhưng không có trong đáp án. Đây là cái sai.
 *
 * Ban đầu `missing` mang gạch bỏ. Nghĩa là từ ĐÚNG bị gạch, và ở ngay vị trí
 * người học đang gõ dở thì nó đọc thành "từ này sai" — trong khi đó chính là từ
 * họ phải gõ. Gạch bỏ phải nằm trên cái mình muốn xoá đi, tức là trên `extra`.
 *
 * Giờ dòng đối chiếu đọc được thành câu: "… make ~~maek~~" = phải là *make*,
 * bạn gõ *maek*.
 */
const DIFF_STYLE: Record<string, string> = {
  match: "text-ok",
  // Từ cần gõ: nhấn mạnh, KHÔNG gạch bỏ — nó là đích, không phải lỗi.
  missing: "text-warn font-semibold",
  // Từ gõ sai: gạch bỏ, và mờ hơn vì nó là thứ sẽ bị bỏ đi.
  extra: "text-warn line-through decoration-2 opacity-70",
  // Chưa gõ tới: không phải đúng, cũng không phải sai. Xám và không trang trí.
  hidden: "font-data text-ink-faint",
};

const STAGGER_LIMIT_WORDS = 25;
const STAGGER_STEP_MS = 24;
const STAGGER_CAP_MS = 600;

export type ExerciseItem = {
  id: string;
  transcript: string;
  audio_url: string;
  word_count: number;
};

/**
 * Một câu dictation: nghe, gõ, chấm tại chỗ.
 *
 * Tách riêng vì luồng câu lẻ và luồng câu-trong-story phải chấm **giống hệt
 * nhau**. Hai bản sao của màn này sẽ trôi khỏi nhau, và chỗ trôi đầu tiên sẽ là
 * điểm số — thứ tệ nhất để có hai phiên bản.
 *
 * **Đổi câu phải truyền `key={item.id}`**, không phải một effect reset. Effect
 * là setState đồng bộ trong thân effect (lint `react-hooks/set-state-in-effect`
 * chặn đúng chỗ này), và nó còn dựng một khung hình mang câu mới cùng đáp án
 * câu cũ trước khi kịp dọn. `key` thay component mới hoàn toàn, không có khoảng
 * hở đó.
 */
export function DictationExercise({
  item,
  onGraded,
  onNext,
  nextLabel = "Câu tiếp theo",
  footer,
}: {
  item: ExerciseItem;
  /** Gọi sau mỗi lượt chấm, để trang cha làm mới tiến độ. */
  onGraded?: () => void;
  /** Có thì hiện nút đi tiếp, và Enter sẽ bấm nó khi câu đã đúng. */
  onNext?: () => void;
  nextLabel?: string;
  footer?: React.ReactNode;
}) {
  const [typed, setTyped] = useState("");
  // `checkedText` ghi lại văn bản đã được chấm, để khi người học sửa tiếp thì
  // bảng đối chiếu tự nhận là đã cũ thay vì nói dối về đoạn chữ hiện tại.
  const [result, setResult] = useState<GradeResult | null>(null);
  const [checkedText, setCheckedText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { token } = useSession();
  const { show } = useToast();
  const box = useRef<HTMLTextAreaElement | null>(null);
  const mirror = useRef<HTMLDivElement | null>(null);
  /*
   * Một lần bấm phím = một việc.
   *
   * Không có khoá này, lần bấm Enter làm câu trở thành đúng sẽ nhảy luôn sang
   * câu sau: giữ phím dù chỉ nửa giây là trình duyệt tự lặp `keydown`, lần đầu
   * chấm ra đúng, lần ngay sau đã thấy `is_complete` nên đi tiếp — người học
   * không kịp thấy câu mình vừa làm xong. Khoá được mở lại khi nhả phím, nên
   * muốn đi tiếp thì phải bấm một lần nữa thật sự.
   *
   * Là `ref` chứ không phải state: nó điều phối các sự kiện bàn phím trong cùng
   * một lần bấm, và không có gì trên màn hình phụ thuộc vào nó.
   */
  const canAdvance = useRef(true);

  /**
   * Chấm tại chỗ, rồi ghi lại lượt làm.
   *
   * Chấm chạy hoàn toàn trong trình duyệt (`lib/dictation.ts`, bản port từng
   * bước của bộ chấm phía server) nên phản hồi hiện tức thì.
   *
   * Ghi lại MỌI lượt, không còn luật "chỉ lần đầu tiên được tính". Luật đó sinh
   * ra khi tiến độ là điểm trung bình và cần chống việc chép lại đáp án để nâng
   * điểm. Giờ tiến độ chỉ đếm "đã gõ đúng chưa", nên không có gì để nâng — và
   * đổi lại, số lần thử trở thành dữ liệu học tập thật. Bỏ được luật đó cũng bỏ
   * luôn dòng chữ "Lần kiểm tra đầu tiên sẽ được ghi nhận", vốn bắt người học
   * phải cân nhắc trước khi bấm một nút lẽ ra bấm thoải mái.
   */
  function check(): GradeResult {
    const graded = grade(item.transcript, typed);
    setResult(graded);
    setCheckedText(typed);

    /*
     * Xong một câu thì báo, và đây là thông báo DUY NHẤT trong app có tiếng.
     *
     * Lý do không phải thẩm mỹ mà là kỹ thuật: trình duyệt chỉ cho phát tiếng
     * sau khi người dùng đã tương tác với trang, và chỗ này chạy ngay trong lần
     * bấm Enter hoặc lần bấm nút Kiểm tra. Ba thông báo còn lại (huy hiệu, việc
     * hôm nay, lên level) bắn ra từ một lần `fetch` lúc mở trang, nên xin tiếng
     * ở đó là xin một thứ chắc chắn không được cấp.
     *
     * Chấm bằng `graded` chứ không bằng `result`: `setResult` chưa có hiệu lực
     * trong chính lần chạy này, nên đọc `result` ở đây là đọc kết quả của LẦN
     * CHẤM TRƯỚC — câu vừa gõ đúng sẽ im, còn câu ngay sau đó sẽ kêu oan.
     *
     * Khoá theo id câu: gõ lại một câu đã xong là chuyện bình thường (mọi lượt
     * đều được ghi), và lúc đó thẻ cũ được thay tại chỗ thay vì xếp thêm một
     * thẻ nữa.
     */
    if (graded.is_complete) {
      show({
        tone: "ok",
        title: "Đúng rồi",
        description: "Xong một câu. Nghe lại vẫn được nếu bạn muốn.",
        sound: "complete",
        dedupeKey: `dictation-${item.id}`,
      });
    }
    // Bấm nút thì con trỏ nhảy sang nút, và Enter kế tiếp sẽ bấm lại chính nút
    // đó. Trả con trỏ về ô nhập để Enter luôn có nghĩa "việc tiếp theo".
    box.current?.focus();

    if (token) {
      // Server chấm lại từ `submitted_text`; kết quả của server mới là bản được
      // lưu, nên bản ghi không phụ thuộc vào bất cứ điều gì trình duyệt khai báo.
      apiFetch(API_ROUTES.submitDictation(item.id), {
        method: "POST",
        token,
        body: JSON.stringify({ submitted_text: typed }),
      })
        .then(() => onGraded?.())
        .catch(() => setError("Đã chấm xong, nhưng không lưu được lượt làm này."));
    }
    return graded;
  }

  /**
   * Enter làm việc tiếp theo, dù việc đó là gì.
   *
   * Chưa đúng thì Enter là "kiểm tra"; đúng rồi thì Enter là "câu tiếp theo".
   * Cả bài dictation chạy được bằng bàn phím mà không rời tay khỏi chỗ gõ — mà
   * gõ chính là việc duy nhất người học đang làm ở đây.
   *
   * Shift+Enter vẫn xuống dòng. Một câu dictation không cần xuống dòng, nhưng
   * cướp hẳn một phím quen thuộc mà không chừa đường lui là thứ chỉ đúng cho tới
   * lúc có người thật sự cần nó.
   */
  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    // Giữ phím không phải là bấm nhiều lần.
    if (event.repeat) return;

    if (result?.is_complete && onNext) {
      if (canAdvance.current) onNext();
      return;
    }
    if (!typed.trim()) return;

    // Nếu chính lần bấm này làm câu trở thành đúng, khoá việc đi tiếp lại cho
    // tới khi nhả phím: khoảnh khắc "xong một câu" phải được nhìn thấy.
    if (check().is_complete) canAdvance.current = false;
  }

  function onKeyUp(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter") canAdvance.current = true;
  }

  const stagger = result !== null && result.diff.length <= STAGGER_LIMIT_WORDS;

  return (
    <>
      {error && (
        <div className="mb-4">
          <Alert tone="warn">{error}</Alert>
        </div>
      )}

      <Panel className="p-5">
        {/* Controls gốc của trình duyệt cho sẵn tua và phát lại, và không đòi
            CORS trên nguồn media. */}
        <audio controls src={item.audio_url} className="w-full" />

        {/*
         * Ô nhập có một lớp phủ nằm dưới để gạch chân những từ gõ sai, ngay tại
         * chỗ người học đang gõ.
         *
         * `<textarea>` không tô màu được từng từ bên trong nó, nên cách duy nhất
         * là: một `<div>` chép lại đúng đoạn chữ đó nằm dưới, và textarea nằm
         * trên với chữ trong suốt — chỉ còn con trỏ và vùng chọn là thật.
         *
         * Hai lớp phải khớp đến từng pixel, nếu không chữ sẽ lệch khỏi gạch
         * chân: cùng cỡ chữ, cùng padding, cùng độ dày viền (lớp phủ dùng viền
         * trong suốt để chiếm đúng chỗ), và `whitespace-pre-wrap` để xuống dòng
         * y hệt nhau. Cuộn cũng phải đồng bộ, vì lớp phủ không tự cuộn theo.
         */}
        <div className="relative mt-5">
          <div
            ref={mirror}
            aria-hidden
            className={cx(
              "pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words",
              "rounded border border-transparent px-3 py-2 text-body",
            )}
          >
            {result ? (
              annotateTyped(typed, wrongSubmittedIndices(result.diff)).map((piece, index) => (
                <span
                  key={index}
                  className={
                    piece.wrong
                      ? "text-ink underline decoration-warn decoration-wavy decoration-2 underline-offset-4"
                      : "text-ink"
                  }
                >
                  {piece.text}
                </span>
              ))
            ) : (
              // Chưa chấm thì chưa biết từ nào sai — chép nguyên văn để chữ
              // vẫn hiện ra bình thường.
              <span className="text-ink">{typed}</span>
            )}
            {/* Ký tự vô hình giữ cho dòng cuối không bị co lại khi kết thúc bằng
                xuống dòng, để lớp phủ và textarea cùng cao. */}
            {"\u200b"}
          </div>

          {/* KHÔNG khoá sau khi chấm: sửa rồi kiểm lại là cách người ta thực sự
              dùng một bài dictation. */}
          <textarea
            ref={box}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            onKeyDown={onKeyDown}
            onKeyUp={onKeyUp}
            onScroll={(event) => {
              if (mirror.current) mirror.current.scrollTop = event.currentTarget.scrollTop;
            }}
            rows={4}
            placeholder="Gõ lại những gì bạn nghe được…"
            className={cx(
              "relative w-full resize-y rounded border border-rule-strong bg-transparent px-3 py-2",
              "text-body text-transparent caret-ink placeholder:text-ink-faint",
            )}
          />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button disabled={!typed.trim()} onClick={check}>
            <Check size={16} strokeWidth={2} aria-hidden />
            Kiểm tra
          </Button>
          <span className="flex items-center gap-1.5 text-small text-ink-faint">
            hoặc nhấn <Kbd>Enter</Kbd>
          </span>
        </div>

        {/* Kết quả nằm NGAY DƯỚI ô nhập, trong cùng một khối — mắt không phải
            rời khỏi chỗ vừa gõ để đọc kết quả của chính nó. */}
        {result && (
          <div className="animate-settle mt-5 border-t border-rule pt-4">
            {/*
             * Câu trả lời là "đúng chưa", không phải "được bao nhiêu phần trăm".
             * Không có con số nào ở đây: 89% không nói cho người học biết nên đi
             * tiếp hay nghe lại, còn hai trạng thái dưới đây thì nói được.
             */}
            {result.is_complete ? (
              <p className="flex items-center gap-2 font-semibold text-ok">
                <CircleCheck size={18} strokeWidth={2} aria-hidden />
                Đúng rồi — bạn đã nghe ra cả câu.
              </p>
            ) : (
              <>
                <p className="text-label font-semibold uppercase text-ink-faint">
                  Chưa đúng — đối chiếu
                </p>

                {/*
                 * Từng từ hiện ra, trái sang phải — vì đó chính là cách người ta
                 * nghe lại câu. Khoảnh khắc dàn dựng DUY NHẤT của cả app (§7).
                 */}
                <p className="mt-2 text-subtitle leading-9">
                  {maskUnreached(result.diff).map((word, position) => (
                    <span
                      key={`${word.op}-${position}`}
                      className={cx(stagger && "animate-settle", DIFF_STYLE[word.op])}
                      style={
                        stagger
                          ? {
                              animationDelay: `${Math.min(position * STAGGER_STEP_MS, STAGGER_CAP_MS)}ms`,
                            }
                          : undefined
                      }
                    >
                      {word.word}{" "}
                    </span>
                  ))}
                </p>

                {/* Chú giải in đúng KIỂU CHỮ của từng trạng thái, không chỉ ô
                    màu: mù màu lục-cam là kiểu phổ biến, nên màu không bao giờ
                    là kênh thông tin duy nhất. */}
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-small text-ink-muted">
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="h-2 w-2 bg-ok" /> đúng
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="h-2 w-2 bg-warn" />
                    <span className="font-semibold text-warn">cần gõ</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="h-2 w-2 bg-warn" />
                    <span className="text-warn line-through decoration-2 opacity-70">gõ sai</span>
                  </span>
                  {/* Không có dòng này, dấu sao trông như một lỗi thứ tư. */}
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="font-data text-ink-faint">
                      ***
                    </span>
                    chưa gõ tới
                  </span>
                </div>

                {/* Sửa xong mà chưa chấm lại thì bảng trên đang nói về đoạn chữ
                    cũ. Nói ra, thay vì để nó âm thầm sai. */}
                {checkedText !== null && typed !== checkedText && (
                  <p className="mt-3 text-small text-warn">
                    Bạn đã sửa lại bài. Bấm Kiểm tra để đối chiếu đoạn hiện tại.
                  </p>
                )}

                <details className="mt-4 rounded border border-rule bg-recess p-3">
                  <summary className="cursor-pointer text-label font-semibold uppercase text-ink-faint">
                    Xem đáp án
                  </summary>
                  <p className="mt-2">{item.transcript}</p>
                </details>
              </>
            )}

            {(onNext || footer) && (
              <div className="mt-4 flex flex-wrap items-center gap-3">
                {onNext && (
                  <>
                    <Button onClick={onNext}>{nextLabel}</Button>
                    {result.is_complete && (
                      <span className="flex items-center gap-1.5 text-small text-ink-faint">
                        hoặc nhấn <Kbd>Enter</Kbd>
                      </span>
                    )}
                  </>
                )}
                {footer}
              </div>
            )}
          </div>
        )}
      </Panel>
    </>
  );
}
