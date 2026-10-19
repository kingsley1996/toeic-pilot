import type { ReactNode } from "react";

import { SeoTopicList } from "@/components/seo-topic-list";
import { getSeoTopics } from "@/lib/seo-content";

/*
 * Khối SSR chủ điểm chỉ thuộc TRANG HUB từ vựng, không phải cả cây route.
 * Trước đây nó nằm ở layout chung nên lặp lại ở đáy mọi trang con (chi tiết
 * bộ sưu tập, danh sách từ, quiz...). API hỏng thì bỏ qua khối — trang vẫn
 * chạy bằng fetch client như cũ.
 */
export default async function VocabularyHubLayout({ children }: { children: ReactNode }) {
  const topics = await getSeoTopics();
  return (
    <>
      {children}
      {topics ? <SeoTopicList topics={topics} /> : null}
    </>
  );
}
