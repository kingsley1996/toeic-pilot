"use client";

import { type AttemptState } from "@toeic-pilot/shared";
import { BookOpen, Headphones } from "lucide-react";

import { cx } from "@/components/ui";

/** Chuyển part, kèm số câu đã trả lời của từng part. */

export function PartTabs({
  state,
  active,
  onSelect,
}: {
  state: AttemptState;
  active: number | null;
  onSelect: (part: number) => void;
}) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto border-t border-rule px-4 py-1.5">
      {state.parts.map((part, index) => {
        const previous = state.parts[index - 1];
        const boundary = index === 0 || previous.section !== part.section;
        // Đếm tại chỗ chứ KHÔNG dùng `part.answered`: con số đó là ảnh chụp lúc
        // nạp trang, còn đáp án thì được lưu từng câu mà không nạp lại. Bản đầu
        // dùng nó, và kết quả là thanh bên hiện 1/17 trong khi tab vẫn hiện 0/1
        // — hai con số cùng nói về một việc mà không khớp nhau.
        const answered = state.questions.filter(
          (question) => question.part === part.part && question.selected_option_id,
        ).length;
        return (
          <div key={part.part} className="flex items-center gap-1">
            {boundary && (
              <span className="px-1.5 text-ink-faint" title={part.section}>
                {part.section === "listening" ? (
                  <Headphones size={15} strokeWidth={1.75} aria-hidden />
                ) : (
                  <BookOpen size={15} strokeWidth={1.75} aria-hidden />
                )}
              </span>
            )}
            <button
              type="button"
              onClick={() => onSelect(part.part)}
              aria-current={active === part.part}
              className={cx(
                "inline-flex shrink-0 items-center gap-1.5 rounded px-2.5 py-1 text-small font-semibold",
                active === part.part
                  ? "bg-action text-on-action"
                  : "text-ink-muted hover:bg-recess hover:text-ink",
              )}
            >
              P{part.part}
              <span
                className={cx(
                  "font-data tabular-nums text-label",
                  active === part.part ? "opacity-80" : "text-ink-faint",
                )}
              >
                {answered}/{part.total}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
