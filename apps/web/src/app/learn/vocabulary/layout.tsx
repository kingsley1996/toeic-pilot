import type { Metadata } from "next";
import type { ReactNode } from "react";

/* Metadata dùng chung cả cây từ vựng — trang hub là client component nên
 * title/description nằm ở layout server này. ISR 10 phút cùng lý do với layout
 * trang cảnh: API free-tier ngủ lúc build thì bản tĩnh đầu thiếu section, 10
 * phút sau tự có. Khối SSR chủ điểm nằm ở `(hub)/layout.tsx` vì chỉ thuộc
 * trang hub. */
export const revalidate = 600;

export const metadata: Metadata = {
  title: "Tuyển Tập Từ Vựng TOEIC Theo Chủ Điểm",
  description:
    "Từ vựng TOEIC sắp theo chủ điểm công việc, du lịch, mua sắm: mỗi từ có phát âm, ví dụ và lịch ôn SM-2 đúng lúc sắp quên.",
  alternates: { canonical: "/learn/vocabulary" },
};

export default function VocabularyLayout({ children }: { children: ReactNode }) {
  return children;
}
