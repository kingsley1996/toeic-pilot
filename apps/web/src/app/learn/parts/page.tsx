import { ArrowRight, Clock } from "lucide-react";
import Link from "next/link";

import { Page, PageHeader, Panel } from "@/components/ui";
import { PARTS } from "@/lib/parts";

/**
 * Tầng 1 của khu "Luyện theo part". Server component thuần: số liệu đang mock
 * trong `lib/parts.ts` (đo thật từ kho), chưa có API.
 */
export default function PartsHubPage() {
  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Luyện thi"
        title="Luyện theo phần"
        description="Thi thật có bảy phần, mỗi phần một kỹ năng riêng. Luyện rời từng phần, phân loại theo nhãn của đề thi."
      />

      <div className="space-y-3">
        {PARTS.map((p) => (
          <Panel key={p.part} className="p-4">
            <div className="flex flex-wrap items-center gap-4">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded bg-recess text-ink-muted">
                <p.Icon size={18} strokeWidth={1.75} aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className="font-semibold">
                    Part {p.part} · {p.title}
                  </span>
                  <span className="font-data text-small tabular-nums text-ink-faint">
                    {p.questionCount} câu
                  </span>
                </span>
                <span className="block text-small text-ink-muted">{p.short}</span>
                <span className="mt-0.5 flex items-center gap-1 text-small text-ink-faint">
                  <Clock size={11} strokeWidth={2} aria-hidden />
                  {p.minutes}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <Link
                  href={`/learn/parts/${p.part}`}
                  className="inline-flex items-center rounded border border-rule-strong px-3 py-1.5 text-small font-semibold hover:bg-recess"
                >
                  Chiến thuật
                </Link>
                <Link
                  href={`/learn/parts/${p.part}/drill`}
                  className="inline-flex items-center gap-1.5 rounded border border-action bg-action px-3 py-1.5 text-small font-semibold text-on-action hover:bg-action-hover"
                >
                  Luyện ngay
                  <ArrowRight size={13} strokeWidth={2} aria-hidden />
                </Link>
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5 border-t border-rule pt-3">
              {p.labels.slice(0, 5).map((l) => (
                <Link
                  key={l.code}
                  href={`/learn/parts/${p.part}/drill?label=${l.code}`}
                  className="rounded bg-recess px-2 py-0.5 font-data text-small tabular-nums text-ink-muted hover:text-ink"
                >
                  {l.title} · {l.count}
                </Link>
              ))}
              {p.labels.length > 5 && (
                <Link
                  href={`/learn/parts/${p.part}`}
                  className="px-1 py-0.5 text-small text-ink-faint hover:text-ink"
                >
                  +{p.labels.length - 5} nhãn
                </Link>
              )}
            </div>
          </Panel>
        ))}
      </div>

      <p className="mt-6 text-small text-ink-faint">
        Ngữ pháp cho Part 5–6 có giáo trình riêng:{" "}
        <Link href="/learn/grammar" className="font-semibold text-ink underline">
          Mô-đun Ngữ pháp
        </Link>
        .
      </p>
    </Page>
  );
}
