import Link from "next/link";
import type { TopicPublic } from "@toeic-pilot/shared";

const PREVIEW_COUNT = 10;

function TopicCard({ topic }: { topic: TopicPublic }) {
  return (
    <li className="rounded border border-rule bg-panel p-3">
      <Link href={`/learn/vocabulary/${topic.slug}`} className="font-semibold">
        {topic.name}
      </Link>
      <p className="mt-1 text-small text-ink-muted">{topic.entry_count} từ</p>
    </li>
  );
}

/*
 * Khối SSR chủ điểm ở hub từ vựng (GĐ3): link chủ điểm thật, hiện 10 card đầu;
 * phần còn lại nằm trong <details> nên vẫn có trong HTML cho crawler. Nút "Xem
 * tất cả" tự ẩn khi mở (group-open:hidden) — mở một chiều, không cần JS. Cảnh
 * 3D đã có trong sitemap + PanelLink ngay giữa hub nên không lặp ở đây.
 */
export function SeoTopicList({ topics }: { topics: TopicPublic[] }) {
  const preview = topics.slice(0, PREVIEW_COUNT);
  const rest = topics.slice(PREVIEW_COUNT);
  return (
    <section
      aria-label="Chủ điểm từ vựng TOEIC"
      className="mx-auto mt-4 w-full max-w-5xl px-4 pb-12"
    >
      <h2 className="text-subtitle font-semibold">Chủ điểm từ vựng TOEIC ({topics.length})</h2>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2">
        {preview.map((t) => (
          <TopicCard key={t.slug} topic={t} />
        ))}
      </ul>
      {rest.length > 0 && (
        <details className="group mt-3">
          <summary className="group-open:hidden inline-flex cursor-pointer list-none items-center rounded border border-rule-strong bg-panel px-3.5 py-2 text-small font-semibold text-ink transition-colors hover:bg-recess [&::-webkit-details-marker]:hidden">
            Xem tất cả chủ điểm
          </summary>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {rest.map((t) => (
              <TopicCard key={t.slug} topic={t} />
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
