"use client";

import { ArrowLeft } from "lucide-react";

import { Button, cx } from "@/components/ui";
import { type ReviewFilter, FILTERS } from "./shared";

/** Thanh lọc lúc xem lại: tất cả / sai / bỏ trống / đã đánh dấu. */

/**
 * Thanh lọc khi xem lại bài đã chấm.
 *
 * Bộ lọc chạy TRONG part đang mở, không cắt ngang cả đề: người xem lại vẫn đi
 * theo cấu trúc đề, và "câu sai của Part 3" là câu hỏi thật, còn "câu sai thứ
 * mười bảy của cả bài" thì không.
 */
export function ReviewToolbar({
  filter,
  onFilter,
  shown,
  onBack,
}: {
  filter: ReviewFilter;
  onFilter: (value: ReviewFilter) => void;
  shown: number;
  onBack: (() => void) | null;
}) {
  return (
    <div className="border-b border-rule bg-recess px-4 py-2.5">
      <div className="mx-auto flex w-full max-w-[110rem] flex-wrap items-center gap-2">
        {onBack && (
          <Button size="sm" variant="secondary" onClick={onBack}>
            <ArrowLeft size={14} strokeWidth={2} aria-hidden />
            Kết quả
          </Button>
        )}
        <div className="flex flex-wrap items-center gap-1.5">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onFilter(option.value)}
              aria-pressed={filter === option.value}
              className={cx(
                "rounded border px-2.5 py-1 text-small font-semibold",
                filter === option.value
                  ? "border-rule-strong bg-panel text-ink"
                  : "border-transparent text-ink-muted hover:text-ink",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
        <span className="font-data text-small tabular-nums text-ink-faint">{shown} câu</span>
      </div>
    </div>
  );
}
