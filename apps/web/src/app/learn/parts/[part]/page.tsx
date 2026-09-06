import { ArrowRight, Dumbbell } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { MarkdownLite } from "@/components/markdown-lite";
import { Page, PageHeader, Panel } from "@/components/ui";
import { getPart } from "@/lib/parts";

/**
 * Trang chiến thuật của MỘT part — SERVER component đọc tệp markdown từ đĩa.
 *
 * Nội dung sống ở `content/parts/part-N.md`, cùng triết lý viết-offline như
 * `apps/api/content/grammar/` nhưng KHÔNG qua database: lý thuyết part là trang
 * chiến thuật tĩnh cạnh chỗ luyện (SPEC-GRAMMAR §3) — không lesson, không
 * progress, không XP. h1 đầu tệp bị cắt vì PageHeader đã mang tiêu đề, đúng
 * như bài ngữ pháp.
 */
export default async function PartTacticsPage({ params }: { params: Promise<{ part: string }> }) {
  const { part } = await params;
  const info = getPart(part);
  if (!info) notFound();

  const raw = await readFile(
    path.join(process.cwd(), "content", "parts", `part-${info.part}.md`),
    "utf8",
  );
  const tactics = raw.replace(/^# .+\n\n/, "");

  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={[{ href: "/learn/parts", label: "Luyện theo phần" }]} />
      <PageHeader eyebrow={`Part ${info.part}`} title={info.title} description={info.short} />

      {/* Nền trắng như trang lesson: tài liệu đọc dài cần bề mặt đọc, không
          phải nền xám của khung trang. */}
      <Panel className="mt-6 p-6 sm:p-8">
        <MarkdownLite text={tactics} className="text-lesson" />
      </Panel>

      <div className="mt-6">
        <h2 className="text-label font-semibold uppercase text-ink-faint">Luyện theo nhãn</h2>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {info.labels.map((l) => (
            <Link
              key={l.code}
              href={`/learn/parts/${info.part}/drill?label=${l.code}`}
              className="rounded border border-rule-strong bg-panel px-2.5 py-1 font-data text-small tabular-nums hover:bg-recess"
            >
              {l.title} · {l.count}
              {l.grammarSlug && <span className="ml-1 text-action">→ Ngữ pháp</span>}
            </Link>
          ))}
        </div>
      </div>

      <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-rule pt-5">
        <Link
          href={`/learn/parts/${info.part}/drill`}
          className="inline-flex items-center gap-1.5 rounded border border-action bg-action px-4 py-2 text-small font-semibold text-on-action hover:bg-action-hover"
        >
          <Dumbbell size={14} strokeWidth={2} aria-hidden />
          Luyện Part {info.part}
          <ArrowRight size={13} strokeWidth={2} aria-hidden />
        </Link>
        <span className="font-data text-small tabular-nums text-ink-faint">
          {info.questionCount} câu trong kho · {info.minutes}
        </span>
      </div>
    </Page>
  );
}
