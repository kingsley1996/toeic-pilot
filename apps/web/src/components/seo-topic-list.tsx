import Link from "next/link";
import type { TopicPublic } from "@toeic-pilot/shared";

/*
 * Khối SSR cho crawler ở hub từ vựng (GĐ3): 36 link chủ điểm thật. Cảnh 3D đã
 * có trong sitemap + PanelLink ngay giữa hub nên không lặp lại ở đây, mà 36 câu
 * mô tả cùng khuôn ("N từ vựng TOEIC chủ điểm ... có phát âm và ví dụ") cũng bỏ
 * — nội dung mẫu lặp 36 lần không giúp gì cho người đọc lẫn crawler, chỉ làm
 * trang dài thêm.
 */
export function SeoTopicList({ topics }: { topics: TopicPublic[] }) {
  return (
    <section
      aria-label="Chủ điểm từ vựng TOEIC"
      className="mx-auto mt-4 w-full max-w-5xl px-4 pb-12"
    >
      <h2 className="text-subtitle font-semibold">Chủ điểm từ vựng TOEIC ({topics.length})</h2>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2">
        {topics.map((t) => (
          <li key={t.slug} className="rounded border border-rule bg-panel p-3">
            <Link href={`/learn/vocabulary/${t.slug}`} className="font-semibold">
              {t.name}
            </Link>
            <p className="mt-1 text-small text-ink-muted">{t.entry_count} từ</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
