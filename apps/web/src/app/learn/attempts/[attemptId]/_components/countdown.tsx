"use client";

import { Clock } from "lucide-react";

import { cx } from "@/components/ui";
import { clock } from "@/lib/attempt";

/**
 * Đồng hồ đếm lùi.
 *
 * Chỉ VẼ, không tính: `remaining_seconds` của máy chủ là nguồn sự thật, vì đồng
 * hồ máy khách chỉnh được và một bài thi tin vào `Date.now()` là một bài thi
 * không có giới hạn thời gian.
 */

export function Countdown({ seconds, done }: { seconds: number | null; done: boolean }) {
  if (done) {
    return <span className="shrink-0 text-small font-semibold text-ok">Đã nộp</span>;
  }
  if (seconds === null) {
    return <span className="shrink-0 text-small text-ink-muted">Không giới hạn giờ</span>;
  }
  // Dưới năm phút thì đổi màu. Không nhấp nháy: một thứ nhấp nháy trong tầm mắt
  // suốt năm phút cuối là thứ lấy đi sự tập trung đúng lúc cần nhất.
  const low = seconds <= 300;
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1.5 rounded border px-2.5 py-1 font-data tabular-nums",
        low ? "border-alert text-alert" : "border-rule-strong text-ink",
      )}
      aria-live={low ? "polite" : "off"}
    >
      <Clock size={14} strokeWidth={2} aria-hidden />
      {clock(seconds)}
    </span>
  );
}
