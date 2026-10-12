import Link from "next/link";
import type { TopicPublic } from "@toeic-pilot/shared";

import { SCENES } from "@/content/scenes";

/*
 * Khối SSR cho crawler ở hub từ vựng (GĐ3): 36 chủ điểm + 12 cảnh, toàn link
 * nội bộ thật. Người học cũng dùng được — cùng một danh sách, không hai bản.
 */
export function SeoTopicList({ topics }: { topics: TopicPublic[] }) {
  return (
    <>
      <section aria-label="Chủ điểm từ vựng TOEIC" className="mx-auto mt-4 w-full max-w-5xl px-4">
        <h2 className="text-subtitle font-semibold">Chủ điểm từ vựng TOEIC ({topics.length})</h2>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {topics.map((t) => (
            <li key={t.slug} className="rounded border border-rule p-3">
              <Link href={`/learn/vocabulary/${t.slug}`} className="font-semibold">
                {t.name}
              </Link>
              <p className="mt-1 text-small text-ink-muted">
                {t.entry_count} từ vựng TOEIC chủ điểm {t.name.toLowerCase()} có phát âm và ví dụ.
              </p>
            </li>
          ))}
        </ul>
      </section>
      <section
        aria-label="Cảnh 3D học từ vựng"
        className="mx-auto mt-8 w-full max-w-5xl px-4 pb-12"
      >
        <h2 className="text-subtitle font-semibold">Học từ vựng trong cảnh 3D ({SCENES.length})</h2>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {SCENES.map((s) => (
            <li key={s.id} className="rounded border border-rule p-3">
              <Link href={`/learn/scenes/${s.id}`} className="font-semibold">
                {s.title}
              </Link>
              <p className="mt-1 text-small text-ink-muted">{s.description}</p>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
