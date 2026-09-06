import type { LucideIcon } from "lucide-react";
import { BookOpenText, FileText, Image, MessagesSquare, Mic, Pencil, Users } from "lucide-react";

/**
 * Siêu dữ liệu GIAO DIỆN của bảy part — chỉ những thứ code phải biết để vẽ.
 *
 * Số câu, nhãn, chiến thuật đều là dữ liệu server (`/practice/parts`,
 * `/practice/parts/{n}/tactics`); icon và nhãn đề mục là thứ frontend phải
 * biết cách vẽ nên nằm ở đây, cùng triết lý với `BADGE_ICONS`.
 */

export type PartMeta = {
  part: number;
  title: string;
  short: string;
  minutes: string;
  Icon: LucideIcon;
};

export const PART_META: PartMeta[] = [
  {
    part: 1,
    title: "Mô tả tranh",
    short: "Chọn câu mô tả đúng nhất bức tranh",
    minutes: "~6 phút · 6 câu",
    Icon: Image,
  },
  {
    part: 2,
    title: "Hỏi – đáp",
    short: "Chọn phản hồi đúng cho một câu hỏi hoặc lời chào",
    minutes: "~11 phút · 30 câu",
    Icon: MessagesSquare,
  },
  {
    part: 3,
    title: "Hội thoại ngắn",
    short: "Nghe hội thoại 2–4 người, trả lời 3 câu",
    minutes: "~13 phút · 30 câu",
    Icon: Users,
  },
  {
    part: 4,
    title: "Độc thoại",
    short: "Nghe thông báo / bài nói đơn độc, trả lời 3 câu",
    minutes: "~11 phút · 30 câu",
    Icon: Mic,
  },
  {
    part: 5,
    title: "Hoàn thành câu",
    short: "Chọn từ đúng để điền vào câu đơn",
    minutes: "~12 phút · 30 câu",
    Icon: FileText,
  },
  {
    part: 6,
    title: "Hoàn thành đoạn văn",
    short: "Điền từ và câu vào một bài viết ngắn",
    minutes: "~8 phút · 16 câu",
    Icon: Pencil,
  },
  {
    part: 7,
    title: "Đọc hiểu",
    short: "Email, quảng cáo, bài báo — đọc và trả lời",
    minutes: "~30 phút · 29 câu",
    Icon: BookOpenText,
  },
];

export function getPartMeta(part: string | number | undefined): PartMeta | undefined {
  return PART_META.find((p) => String(p.part) === String(part));
}
