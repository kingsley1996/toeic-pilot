import type { SeoWord } from "@/lib/seo-content";

/*
 * Danh sách từ SSR dưới canvas 3D — cho crawler đọc (GĐ3) và cho người học
 * ôn lướt. Server component thuần, không tương tác: bấm vào từ để học vẫn là
 * việc của canvas phía trên. Nghĩa + ví dụ lấy từ API lúc render, cache 1 giờ.
 */
export function SeoWordList({ words, sceneTitle }: { words: SeoWord[]; sceneTitle: string }) {
  return (
    <section
      aria-label={`Từ vựng trong cảnh ${sceneTitle}`}
      className="mx-auto mt-4 w-full max-w-5xl px-4 pb-12"
    >
      <h2 className="text-subtitle font-semibold">Từ vựng trong cảnh này ({words.length} từ)</h2>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2">
        {words.map((w) => (
          <div key={`${w.headword}-${w.part_of_speech}`} className="rounded border border-rule p-3">
            <dt className="font-semibold">
              {w.headword}
              {w.phonetic ? (
                <span className="ml-2 font-normal text-ink-muted">{w.phonetic}</span>
              ) : null}
              <span className="ml-2 font-data text-small font-normal text-ink-faint">
                {w.part_of_speech}
              </span>
            </dt>
            <dd className="mt-1 text-body">{w.meaning_vi}</dd>
            {w.meaning_en ? <dd className="text-small text-ink-muted">{w.meaning_en}</dd> : null}
            {w.example ? (
              <dd className="mt-1 text-small italic text-ink-muted">
                {w.example}
                {w.example_vi ? <span className="not-italic"> — {w.example_vi}</span> : null}
              </dd>
            ) : null}
          </div>
        ))}
      </dl>
    </section>
  );
}
