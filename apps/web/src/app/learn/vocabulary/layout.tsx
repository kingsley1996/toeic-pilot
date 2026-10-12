import type { Metadata } from "next";
import type { ReactNode } from "react";

/* Trang hub là client component — metadata nằm ở layout server bọc ngoài. */
export const metadata: Metadata = {
  title: "Tuyển Tập Từ Vựng TOEIC Theo Chủ Điểm",
  description:
    "Từ vựng TOEIC sắp theo chủ điểm công việc, du lịch, mua sắm: mỗi từ có phát âm, ví dụ và lịch ôn SM-2 đúng lúc sắp quên.",
  alternates: { canonical: "/learn/vocabulary" },
};

export default function VocabularyLayout({ children }: { children: ReactNode }) {
  return children;
}
