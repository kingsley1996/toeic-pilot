import type { Metadata } from "next";
import type { ReactNode } from "react";

/* Trang xếp hạng là client component — metadata nằm ở layout server bọc ngoài. */
export const metadata: Metadata = {
  title: "Bảng Xếp Hạng Học TOEIC",
  description:
    "Vinh danh người học TOEIC chăm chỉ nhất: streak, điểm số và huy hiệu cập nhật mỗi ngày.",
  alternates: { canonical: "/hall-of-fame" },
};

export default function HallOfFameLayout({ children }: { children: ReactNode }) {
  return children;
}
