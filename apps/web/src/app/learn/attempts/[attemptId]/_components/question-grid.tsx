"use client";

import { type AttemptState, type QuestionPublic } from "@toeic-pilot/shared";

import { cx } from "@/components/ui";

/** Lưới số câu: đã trả lời, đã đánh dấu, đang xem — và chú giải của nó. */

export function QuestionGrid({
  state,
  answered,
  current,
  onJump,
}: {
  state: AttemptState;
  answered: number;
  current: number | null;
  onJump: (question: QuestionPublic) => void;
}) {
  const percent = state.question_count ? Math.round((answered / state.question_count) * 100) : 0;

  return (
    <aside className="hidden w-64 shrink-0 xl:block">
      <div className="sticky top-32 rounded border border-rule-strong bg-panel p-4">
        <div className="flex items-baseline justify-between gap-2">
          <p className="font-semibold">Tiến độ</p>
          <p className="font-data text-small tabular-nums text-ink-muted">
            {answered}/{state.question_count} ({percent}%)
          </p>
        </div>
        <div className="mt-2 h-1.5 rounded bg-recess">
          <div className="h-full rounded bg-action" style={{ width: `${percent}%` }} />
        </div>

        {/* Đệm trong vùng cuộn để vòng "đang xem" có chỗ: nó vẽ NGOÀI hộp, mà
            `overflow-y-auto` cắt cả hai chiều — không có đệm thì ô ở rìa hiện
            một vòng đứt đoạn, đọc như lỗi vẽ chứ không như một trạng thái. */}
        <div className="mt-4 max-h-[calc(100dvh-16rem)] space-y-4 overflow-y-auto p-1.5">
          {state.parts.map((part) => (
            <div key={part.part}>
              <p className="text-label font-semibold uppercase text-ink-muted">
                Part {part.part} ({part.first_number}–{part.last_number})
              </p>
              <div className="mt-1.5 grid grid-cols-5 gap-1.5">
                {state.questions
                  .filter((question) => question.part === part.part)
                  .map((question) => (
                    <button
                      key={question.id}
                      type="button"
                      onClick={() => onJump(question)}
                      aria-current={current === question.number ? "true" : undefined}
                      title={gridTitle(question, current === question.number)}
                      className={gridClass(question, current === question.number)}
                    >
                      {question.number}
                      {/* Đánh dấu là một chấm ở góc, không phải một màu nền
                          khác: câu vừa được đánh dấu vừa đã trả lời là chuyện
                          bình thường, và hai trạng thái đó phải cùng đọc được. */}
                      {question.flagged && (
                        // Viền cùng màu nền để chấm tách khỏi ô kể cả khi ô đã
                        // được tô — trên nền `action-tint` nó nhoè vào, và
                        // trạng thái đánh dấu biến mất đúng ở những câu hay
                        // được đánh dấu nhất.
                        <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-pill border border-panel bg-warn" />
                      )}
                    </button>
                  ))}
              </div>
            </div>
          ))}
        </div>

        <Legend />
      </div>
    </aside>
  );
}

/* Bốn trạng thái dùng ba KÊNH thị giác khác nhau, nên chúng chồng lên nhau
 * được mà vẫn đọc riêng ra được:
 *
 *   nền + viền   chưa trả lời  <->  đã trả lời   (loại trừ nhau)
 *   vòng ngoài   đang xem                        (chồng lên cả hai)
 *   chấm góc     đánh dấu                        (chồng lên cả hai)
 *
 * Dùng cùng một kênh cho hai trạng thái độc lập là cách chắc chắn nhất để một
 * trong hai biến mất khi cả hai cùng đúng.
 */
function gridClass(question: QuestionPublic, isCurrent: boolean): string {
  return cx(
    "relative h-8 rounded border font-data text-small tabular-nums",
    question.selected_option_id
      ? "border-action bg-action-tint font-semibold text-action-ink"
      : "border-rule bg-panel text-ink-muted hover:border-rule-strong",
    /*
     * Vòng vẽ bằng PSEUDO-ELEMENT, không phải `outline` và cũng không `ring`.
     * Cả hai lối kia đều đã có chủ:
     *
     *   `ring` của Tailwind biên dịch ra box-shadow — §6.3 chỉ chừa box-shadow
     *   cho vòng focus, header dính và lớp phủ thật.
     *
     *   `outline` thuộc về hệ thống focus. `globals.css` có
     *   `:focus:not(:focus-visible) { outline: none }`, và selector đó nặng
     *   (0,2,0) hơn utility `.outline-2` (0,1,0) nên nó THẮNG. Bấm chuột vào
     *   một `<button>` cho `:focus` mà không cho `:focus-visible`, tức vòng bị
     *   xoá đúng trên ô vừa bấm — nhìn từ phía người dùng là vòng không bao giờ
     *   nằm ở ô mình bấm mà nhấp nháy sang ô bên cạnh.
     */
    isCurrent &&
      "after:pointer-events-none after:absolute after:-inset-[3px] after:rounded after:border-2 after:border-action-ink",
  );
}

function gridTitle(question: QuestionPublic, isCurrent: boolean): string {
  const states = [
    question.selected_option_id ? "đã trả lời" : "chưa trả lời",
    ...(isCurrent ? ["đang xem"] : []),
    ...(question.flagged ? ["đã đánh dấu"] : []),
  ];
  return `Câu ${question.number} — ${states.join(", ")}`;
}

function Legend() {
  return (
    // Chú giải chứ không để người dùng tự đoán: bốn trạng thái mà chỉ có màu
    // sắc phân biệt thì người mới nhìn không biết cái nào nghĩa là gì, và họ
    // đang giữa một bài thi tính giờ.
    <ul className="mt-4 space-y-1.5 border-t border-rule pt-3 text-small text-ink-muted">
      {[
        { label: "Chưa trả lời", box: "border-rule bg-panel", dot: false },
        { label: "Đã trả lời", box: "border-action bg-action-tint", dot: false },
        {
          label: "Đang xem",
          box: "border-rule bg-panel after:pointer-events-none after:absolute after:-inset-[3px] after:rounded after:border-2 after:border-action-ink",
          dot: false,
        },
        { label: "Đã đánh dấu", box: "border-rule bg-panel", dot: true },
      ].map((item) => (
        <li key={item.label} className="flex items-center gap-2.5">
          <span className={cx("relative h-4 w-4 shrink-0 rounded border", item.box)}>
            {item.dot && (
              <span className="absolute -right-1 -top-1 h-2 w-2 rounded-pill border border-panel bg-warn" />
            )}
          </span>
          {item.label}
        </li>
      ))}
    </ul>
  );
}
