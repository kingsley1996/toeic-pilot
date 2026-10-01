"use client";

import { cx } from "@/components/ui";

/**
 * Biểu đồ cột SVG vẽ tay — không thêm lib chart nào.
 *
 * Quy ước chung của admin là hình CSS/SVG tự vẽ (`contribution-graph`,
 * `Meter`), và ba biểu đồ ở đây chỉ cần cột + lưới + chú thích, nên một
 * component ~80 dòng là đủ, nhẹ hơn cả một dependency.
 */

export const CHART_COLORS = [
  "#4f9cf9",
  "#34d399",
  "#fbbf24",
  "#f87171",
  "#c084fc",
  "#22d3ee",
] as const;

export function Legend({ series }: { series: string[] }) {
  return (
    <div className="mb-2 flex flex-wrap gap-3 text-small">
      {series.map((name, i) => (
        <span key={name} className="flex items-center gap-1.5 text-ink-muted">
          <span
            className="inline-block h-2.5 w-2.5"
            style={{ background: CHART_COLORS[i % CHART_COLORS.length] }}
          />
          {name}
        </span>
      ))}
    </div>
  );
}

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const exp = Math.floor(Math.log10(v));
  const base = 10 ** exp;
  const n = v / base;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return step * base;
}

export function GroupedBars({
  groups,
  series,
  format = (v) => `${v}`,
}: {
  groups: { label: string; values: number[] }[];
  series: string[];
  format?: (v: number) => string;
}) {
  const W = 620;
  const H = 230;
  const padL = 40;
  const padB = 28;
  const padT = 12;
  const innerW = W - padL - 8;
  const innerH = H - padT - padB;
  const max = niceMax(Math.max(0, ...groups.flatMap((g) => g.values)));
  const n = Math.max(series.length, 1);
  const slot = groups.length > 0 ? innerW / groups.length : 0;
  const barW = Math.min(28, (slot * 0.7) / n);
  const y = (v: number) => padT + innerH - (v / max) * innerH;
  const ticks = [0, 0.5, 1].map((t) => t * max);

  return (
    <div>
      <Legend series={series} />
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={padL}
              x2={W - 8}
              y1={y(t)}
              y2={y(t)}
              className="stroke-ink-faint/30"
              strokeWidth={1}
            />
            <text
              x={padL - 6}
              y={y(t) + 4}
              textAnchor="end"
              fontSize={11}
              className="fill-ink-muted"
            >
              {format(t)}
            </text>
          </g>
        ))}
        {groups.map((g, gi) => (
          <g key={g.label}>
            {g.values.map((v, si) => {
              const x = padL + gi * slot + (slot - barW * n) / 2 + si * barW;
              return (
                <rect
                  key={si}
                  x={x}
                  y={y(v)}
                  width={Math.max(barW - 2, 1)}
                  height={Math.max(padT + innerH - y(v), 0)}
                  fill={CHART_COLORS[si % CHART_COLORS.length]}
                  rx={0}
                >
                  <title>{`${series[si]} · ${g.label}: ${format(v)}`}</title>
                </rect>
              );
            })}
            <text
              x={padL + gi * slot + slot / 2}
              y={H - 8}
              textAnchor="middle"
              fontSize={11}
              className="fill-ink-muted"
            >
              {g.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export function CoverageBars({
  rows,
}: {
  rows: { label: string; pct: number | null; color: string }[];
}) {
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="mb-0.5 flex items-baseline justify-between text-small">
            <span className="text-ink-muted">{r.label}</span>
            <span className="font-data text-ink">{r.pct == null ? "—" : `${r.pct}%`}</span>
          </div>
          <div className="h-2 w-full bg-ink-faint/20">
            <div className={cx("h-2")} style={{ width: `${r.pct ?? 0}%`, background: r.color }} />
          </div>
        </div>
      ))}
    </div>
  );
}
