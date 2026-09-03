"use client";

import { type QuestionPublic } from "@toeic-pilot/shared";

import { cx } from "@/components/ui";

/** Mảnh dùng chung giữa màn làm bài và các khối của nó. */

export type ReviewFilter = "all" | "wrong" | "blank" | "flagged";

export const FILTERS: { value: ReviewFilter; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "wrong", label: "Câu sai" },
  { value: "blank", label: "Bỏ trống" },
  { value: "flagged", label: "Đã đánh dấu" },
];

/**
 * Câu này có lọt qua bộ lọc đang chọn không.
 *
 * "Sai" và "bỏ trống" là hai thứ KHÁC nhau ở đây, dù chấm điểm thì cả hai đều
 * không được điểm: bỏ trống là hết giờ hoặc bỏ qua, còn sai là đã cân nhắc rồi
 * chọn nhầm — và hai loại đó cần đọc lại theo hai kiểu khác nhau.
 */
export function matchesFilter(question: QuestionPublic, filter: ReviewFilter): boolean {
  if (filter === "all") return true;
  if (filter === "flagged") return question.flagged;
  if (filter === "blank") return question.selected_option_id === null;
  return (
    question.selected_option_id !== null &&
    question.correct_option_id !== null &&
    question.selected_option_id !== question.correct_option_id
  );
}

/** Giây -> "42 phút 15 giây", cho chỗ đọc chậm chứ không phải đồng hồ đếm ngược. */
export function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safe / 60);
  return minutes ? `${minutes} phút ${safe % 60} giây` : `${safe} giây`;
}

/**
 * Khoảng thời gian đã dùng, dạng đồng hồ: `1:47:41`, hoặc `47:41` khi dưới một giờ.
 *
 * Khác `formatClock` một cách CÓ CHỦ Ý. Đồng hồ đếm ngược đọc thành lời ("45
 * phút 12 giây") vì người đang làm bài liếc một cái là phải hiểu. Còn ở trang
 * kết quả nó đứng cạnh thời lượng đề, và "107 phút 41 giây / 120 phút 0 giây"
 * dài tới mức phải đọc cả dòng mới so được hai số.
 */
export function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const pad = (value: number) => String(value).padStart(2, "0");
  const hours = Math.floor(safe / 3600);
  const rest = `${pad(Math.floor((safe % 3600) / 60))}:${pad(safe % 60)}`;
  return hours ? `${hours}:${rest}` : rest;
}

export function Tally({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: "warn";
}) {
  return (
    <div>
      <dt className="text-label uppercase text-ink-faint">{label}</dt>
      <dd className={cx("font-data tabular-nums", tone === "warn" ? "text-warn" : "text-ink")}>
        {value}
      </dd>
    </div>
  );
}
