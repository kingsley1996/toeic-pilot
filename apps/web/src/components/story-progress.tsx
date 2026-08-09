"use client";

import type { StoryProgress } from "@toeic-pilot/shared";

import { Meter, cx } from "@/components/ui";

/**
 * Tiến độ một story: bao nhiêu câu đã gõ đúng.
 *
 * Không còn điểm trung bình. Dictation đo được đúng một chuyện một cách đáng
 * tin — nghe ra hay chưa — và "89%" không nói cho người học biết nên đi tiếp hay
 * nghe lại. "3/6 câu" thì nói được, và nó cũng là con số duy nhất họ cần để
 * biết mai vào học tiếp từ đâu.
 */
export function StoryProgressBar({
  progress,
  className,
}: {
  progress: StoryProgress;
  className?: string;
}) {
  const done = progress.completed_items;
  const total = progress.total_items;
  const finished = total > 0 && done >= total;

  return (
    <div className={cx("min-w-0", className)}>
      <Meter value={done} max={total} ticks={Math.min(Math.max(total, 1), 10)} />
      <p className={cx("mt-1.5 font-data text-small", finished ? "text-ok" : "text-ink-muted")}>
        {done}/{total} câu đã xong
      </p>
    </div>
  );
}
