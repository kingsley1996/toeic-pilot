"use client";

import { BookOpenText } from "lucide-react";
import Link from "next/link";

import { Page, PageHeader, Panel } from "@/components/ui";
import { PART_META } from "@/lib/parts";

/** Danh sách bảy part — cửa vào màn soạn chiến thuật của từng part. */
export default function AdminPartsPage() {
  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Nội dung"
        title="Chiến thuật theo part"
        description="Sửa trang chiến thuật và đính video giảng cho từng part — người học thấy ngay trên trang luyện."
      />
      <div className="space-y-2">
        {PART_META.map((meta) => (
          <Link key={meta.part} href={`/admin/parts/${meta.part}`} className="block">
            <Panel className="flex items-center gap-3 p-4 transition-colors hover:bg-recess">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded border border-rule-strong text-ink-muted">
                <BookOpenText size={16} strokeWidth={1.75} aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-small font-semibold">
                  Part {meta.part} · {meta.title}
                </span>
                <span className="block truncate text-small text-ink-muted">{meta.short}</span>
              </span>
            </Panel>
          </Link>
        ))}
      </div>
    </Page>
  );
}
