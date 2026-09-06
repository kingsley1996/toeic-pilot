"use client";

import { ArrowRight, Dumbbell } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { MarkdownLite } from "@/components/markdown-lite";
import { EmptyState, Page, PageHeader } from "@/components/ui";
import { getPart } from "@/lib/parts";

/**
 * Trang chiến thuật của MỘT part — nội dung tĩnh, không progress, không XP
 * (SPEC-GRAMMAR §3: lý thuyết part là trang chiến thuật cạnh chỗ luyện, không
 * phải bài học trong cây). Client component vì toàn khu này dùng `useParams`
 * chứ không nhận `params` từ server.
 */
export default function PartTacticsPage() {
  const info = getPart(String(useParams().part));

  if (!info) {
    return (
      <Page className="max-w-3xl">
        <EmptyState
          icon={Dumbbell}
          title="Không có phần này"
          description="Bài thi TOEIC có bảy phần, từ 1 đến 7."
        />
      </Page>
    );
  }

  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={[{ href: "/learn/parts", label: "Luyện theo phần" }]} />
      <PageHeader eyebrow={`Part ${info.part}`} title={info.title} description={info.short} />

      <article className="mt-6">
        <MarkdownLite text={info.tactics} className="text-lesson" />
      </article>

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
