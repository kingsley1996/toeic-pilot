"use client";

import { API_ROUTES, type LlmStats } from "@toeic-pilot/shared";
import { Activity, Coins, Gauge, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";

import { FacetAccuracyTable } from "@/components/facet-accuracy-table";
import { Page, PageHeader, Panel, SectionHeader, SkeletonList, ValueTile } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

function money(value: string | number): string {
  const n = typeof value === "string" ? Number(value) : value;
  // Bốn chữ số thập phân, không phải hai: một lượt gọi rẻ là 0,0004 USD, và làm
  // tròn về 0,00 thì cả bảng toàn số không — đúng con số người mở trang này để tìm.
  return `$${n.toFixed(4)}`;
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Bảng điều khiển tầng AI: mọi con số của các lượt gọi mô hình.
 *
 * Gắn nhãn KHÔNG ở đây — nó là một trong nhiều việc của tầng này, và nằm ở
 * `/admin/ai/skill-tags`. Trang này trả lời những câu không gắn với một việc cụ
 * thể nào: đã tiêu bao nhiêu, hỏng bao nhiêu, chậm bao nhiêu, ai chạm trần.
 */
export default function AdminAiPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [stats, setStats] = useState<LlmStats | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function load(bearer: string) {
      const next = await apiFetch<LlmStats>(API_ROUTES.adminAiStats, { token: bearer });
      if (!cancelled) setStats(next);
    }
    load(token).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (status === "loading") {
    return (
      <Page>
        <SkeletonList rows={6} />
      </Page>
    );
  }

  const errorRate = stats && stats.total_calls > 0 ? stats.error_calls / stats.total_calls : 0;

  return (
    <Page>
      <PageHeader
        title="AI layer"
        description="Cost, reliability and latency of every model call. The ledger is the source of truth — no summary table is written alongside it."
      />

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <ValueTile
          Icon={Coins}
          label="Spent"
          value={stats ? money(stats.cost_usd) : null}
          hint={`${stats?.total_calls ?? 0} calls recorded`}
          empty="no calls yet"
        />
        <ValueTile
          Icon={ShieldAlert}
          label="Failure rate"
          value={stats ? pct(errorRate) : null}
          hint={`${stats?.error_calls ?? 0} failed · ${stats?.refused_calls ?? 0} refused by the budget`}
          empty="no calls yet"
        />
        <ValueTile
          Icon={Gauge}
          label="Latency (p95)"
          value={stats ? (stats.latency_p95_ms / 1000).toFixed(1) : null}
          unit="s"
          hint={stats ? `median ${(stats.latency_p50_ms / 1000).toFixed(1)}s` : undefined}
          empty="no data yet"
        />
        <ValueTile
          Icon={Activity}
          label="Tokens in / out"
          value={stats ? `${stats.prompt_tokens} / ${stats.completion_tokens}` : null}
          hint={`${stats?.cached_tokens ?? 0} tokens read from cache`}
          empty="no data yet"
          numeric={false}
        />
      </section>

      <section className="mt-10 grid gap-3 lg:grid-cols-2">
        <div>
          <SectionHeader title="By feature" />
          <UsageTable rows={stats?.by_feature ?? []} />
        </div>
        <div>
          {/*
           * Tách `provider` khỏi `model` ở sổ cái chính là để bảng này trả lời
           * được câu hỏi mà định tuyến sinh ra: đổi việc X sang model rẻ hơn
           * thì tiết kiệm bao nhiêu.
           */}
          <SectionHeader title="By model" />
          <UsageTable rows={stats?.by_model ?? []} />
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader
          title="Accuracy by facet"
          aside={
            <span className="text-small text-ink-muted">
              {stats?.questions_labelled ?? 0} / {stats?.questions_total ?? 0} questions labelled
            </span>
          }
        />
        <FacetAccuracyTable facets={stats?.facets ?? []} />
      </section>

      {(stats?.budget_hit_users ?? 0) > 0 && (
        <Panel className="mt-10 border-warn p-4">
          <p className="text-small">
            <strong>{stats?.budget_hit_users}</strong> accounts hit the spending cap in the last 30
            days. The budget deliberately fails closed when Redis is down — here Redis is the only
            thing standing between an account and your bill.
          </p>
        </Panel>
      )}
    </Page>
  );
}

function UsageTable({
  rows,
}: {
  rows: { key: string; calls: number; cost_usd: string; prompt_tokens: number }[];
}) {
  if (rows.length === 0) {
    return <Panel className="p-4 text-small text-ink-muted">No calls yet.</Panel>;
  }
  return (
    <Panel className="overflow-x-auto p-0">
      <table className="w-full min-w-[360px] text-small">
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-rule last:border-0">
              <td className="px-4 py-2.5 font-data text-label">{row.key}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-ink-muted">
                {row.calls} calls
              </td>
              <td className="px-4 py-2.5 text-right font-data tabular-nums">
                {money(row.cost_usd)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
