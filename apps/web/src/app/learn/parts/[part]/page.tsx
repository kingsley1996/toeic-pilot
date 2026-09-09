"use client";

import { API_ROUTES, type PartTacticsPublic } from "@toeic-pilot/shared";
import { ArrowRight, Dumbbell } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { MarkdownLite } from "@/components/markdown-lite";
import { Alert, Page, PageHeader, Panel, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { getPartMeta } from "@/lib/parts";

/**
 * Trang chiến thuật của MỘT part — đọc `part_tactics` từ API, không đọc từ đĩa
 * (production web không có thư mục content; nguồn soạn là markdown trong
 * `apps/web/content/parts/`, đường một chiều md → DB qua `scripts/sync-parts.sh`).
 *
 * Không progress, không XP: đây là trang chiến thuật cạnh chỗ luyện, không phải
 * bài học trong cây (SPEC-GRAMMAR §3).
 */
export default function PartTacticsPage() {
  const meta = getPartMeta(String(useParams().part));
  const [tactics, setTactics] = useState<PartTacticsPublic | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!meta) return;
    apiFetch<PartTacticsPublic>(API_ROUTES.partTactics(meta.part))
      .then(setTactics)
      .catch(() => setError("Không tải được trang chiến thuật này."));
  }, [meta]);

  if (!meta) {
    return (
      <Page className="max-w-3xl">
        <Alert>Không có phần này — bài thi TOEIC có bảy phần, từ 1 đến 7.</Alert>
      </Page>
    );
  }

  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={[{ href: "/learn/parts", label: "Luyện theo phần" }]} />
      <PageHeader eyebrow={`Part ${meta.part}`} title={meta.title} description={meta.short} />

      {error && <Alert>{error}</Alert>}
      {!tactics && !error && <SkeletonList rows={4} />}

      {/* Nền trắng như trang lesson: tài liệu đọc dài cần bề mặt đọc. */}
      {tactics && (
        <>
          {/* Video chiến thuật đứng RIÊNG ngoài Panel chữ — cùng hình dạng với
              trang lesson ngữ pháp. `preload="metadata"`: tải nguyên file trước
              khi bấm phát là băng thông bỏ đi. */}
          {tactics.video_url && (
            <video
              controls
              preload="metadata"
              src={tactics.video_url}
              className="mt-6 w-full rounded"
            />
          )}
          <Panel className="mt-4 p-6 sm:p-8">
            <MarkdownLite text={tactics.body} className="text-lesson" />
          </Panel>
        </>
      )}

      <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-rule pt-5">
        <Link
          href={`/learn/parts/${meta.part}/drill`}
          className="inline-flex items-center gap-1.5 rounded border border-action bg-action px-4 py-2 text-small font-semibold text-on-action hover:bg-action-hover"
        >
          <Dumbbell size={14} strokeWidth={2} aria-hidden />
          Luyện Part {meta.part}
          <ArrowRight size={13} strokeWidth={2} aria-hidden />
        </Link>
        <span className="text-small text-ink-faint">{meta.minutes}</span>
      </div>
    </Page>
  );
}
