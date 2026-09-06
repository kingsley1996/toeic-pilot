"use client";

import { API_ROUTES, type PartSummary } from "@toeic-pilot/shared";
import { ArrowRight, Clock } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Page, PageHeader, Panel, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { PART_META } from "@/lib/parts";

/**
 * Tầng 1 của khu "Luyện theo part". Số câu là dữ liệu server đo từ kho thật;
 * nhãn KHÔNG hiện ở đây — phân loại theo nhãn là việc của màn drill, chỗ người
 * ta đang chọn sẽ luyện gì.
 */
export default function PartsHubPage() {
  const [parts, setParts] = useState<PartSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<PartSummary[]>(API_ROUTES.practiceParts)
      .then(setParts)
      .catch(() => setError("Không tải được danh sách phần."));
  }, []);

  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Luyện thi"
        title="Luyện theo phần"
        description="Thi thật có bảy phần, mỗi phần một kỹ năng riêng. Luyện rời từng phần, kèm chiến thuật làm phần đó."
      />

      {error && <p className="mb-4 text-small text-alert">{error}</p>}
      {!parts && !error && <SkeletonList rows={5} />}

      <div className="space-y-3">
        {parts &&
          PART_META.map((m) => {
            const summary = parts.find((p) => p.part === m.part);
            return (
              <Panel key={m.part} className="flex flex-wrap items-center gap-4 p-4">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded bg-recess text-ink-muted">
                  <m.Icon size={18} strokeWidth={1.75} aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className="font-semibold">
                      Part {m.part} · {m.title}
                    </span>
                    {summary && (
                      <span className="font-data text-small tabular-nums text-ink-faint">
                        {summary.question_count} câu
                      </span>
                    )}
                  </span>
                  <span className="block text-small text-ink-muted">{m.short}</span>
                  <span className="mt-0.5 flex items-center gap-1 text-small text-ink-faint">
                    <Clock size={11} strokeWidth={2} aria-hidden />
                    {m.minutes}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <Link
                    href={`/learn/parts/${m.part}`}
                    className="inline-flex items-center rounded border border-rule-strong px-3 py-1.5 text-small font-semibold hover:bg-recess"
                  >
                    Chiến thuật
                  </Link>
                  <Link
                    href={`/learn/parts/${m.part}/drill`}
                    className="inline-flex items-center gap-1.5 rounded border border-action bg-action px-3 py-1.5 text-small font-semibold text-on-action hover:bg-action-hover"
                  >
                    Luyện ngay
                    <ArrowRight size={13} strokeWidth={2} aria-hidden />
                  </Link>
                </span>
              </Panel>
            );
          })}
      </div>

      <p className="mt-6 flex flex-wrap gap-x-4 text-small text-ink-faint">
        <span>
          Ngữ pháp cho Part 5–6 có giáo trình riêng:{" "}
          <Link href="/learn/grammar" className="font-semibold text-ink underline">
            Mô-đun Ngữ pháp
          </Link>
        </span>
        <Link href="/learn/parts/sessions" className="font-semibold text-ink underline">
          Phiên đã luyện
        </Link>
      </p>
    </Page>
  );
}
