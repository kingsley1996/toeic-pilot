import type { TopicPublic, VocabularyDetail, VocabularyPage } from "@toeic-pilot/shared";

import { API_ROUTES } from "@toeic-pilot/shared";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/*
 * Nguồn từ vựng cho khối SSR đọc bởi crawler (GĐ3 SEO). Chạy ở server component
 * nên dùng `fetch` thẳng, cache 1 giờ — trang cảnh ít đổi nội dung. API hỏng thì
 * trả null và layout bỏ qua khối SEO: trang vẫn chạy bằng fetch client như cũ,
 * chứ không 500 cả trang vì một khối phụ.
 */
export type SeoWord = Pick<
  VocabularyDetail,
  | "headword"
  | "part_of_speech"
  | "phonetic"
  | "meaning_vi"
  | "meaning_en"
  | "example"
  | "example_vi"
>;

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function getSeoWords(topicSlug: string): Promise<SeoWord[] | null> {
  const page = await getJson<VocabularyPage>(
    `${API_ROUTES.vocabulary}?topic=${topicSlug}&limit=200`,
  );
  const items = page?.items;
  if (!items?.length) return null;
  const details = await Promise.all(
    items.map((item) => getJson<VocabularyDetail>(API_ROUTES.vocabularyDetail(item.id))),
  );
  const words = details.filter((d): d is VocabularyDetail => d !== null);
  return words.length ? words : null;
}

export async function getSeoTopics(): Promise<TopicPublic[] | null> {
  const topics = await getJson<TopicPublic[]>(API_ROUTES.topics);
  return topics?.length ? topics : null;
}
