import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SeoTopicList } from "@/components/seo-topic-list";
import { getSeoTopics } from "@/lib/seo-content";

/* Trang hub là client component — metadata + khối SSR cho crawler nằm ở layout server này. */
export const metadata: Metadata = {
  title: "Tuyển Tập Từ Vựng TOEIC Theo Chủ Điểm",
  description:
    "Từ vựng TOEIC sắp theo chủ điểm công việc, du lịch, mua sắm: mỗi từ có phát âm, ví dụ và lịch ôn SM-2 đúng lúc sắp quên.",
  alternates: { canonical: "/learn/vocabulary" },
};

export default async function VocabularyLayout({ children }: { children: ReactNode }) {
  const topics = await getSeoTopics();
  return (
    <>
      {children}
      {topics ? <SeoTopicList topics={topics} /> : null}
    </>
  );
}
