"use client";

import {
  API_ROUTES,
  type CompareOut,
  type TestAnalytics,
  type TestAnalyticsRow,
} from "@toeic-pilot/shared";
import { ArrowLeft, ChartColumn, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  EmptyState,
  Page,
  PageHeader,
  Panel,
  PublishTag,
  SectionHeader,
  SkeletonList,
  Tag,
  ValueTile,
  cx,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

import { GroupedBars } from "./_components/charts";

/**
 * Chất lượng đề — đọc khóa phân tích của một hay nhiều đề đặt cạnh nhau.
 *
 * Ba nhóm tiêu chí, tất cả đều đã có sẵn trong DB + blueprint nên màn này chỉ
 * ĐỌC: (1) cơ cấu và cân bằng — số câu theo part, đáp án A/B/C/D, độ khó ghi
 * trong DB và ô `hard` trong blueprint; (2) taxonomy — phủ từng mặt phân loại,
 * nhãn máy gán đúng bao nhiêu, còn thiếu ở đâu; (3) thực tế làm bài — p-value
 * từ các lượt đã nộp so với độ khó dự kiến. Cờ đỏ gom mọi thứ vượt ngưỡng.
 */

const MAX_SELECT = 6;

function mean(dist: Record<string, number> | undefined): number | null {
  if (!dist) return null;
  let n = 0;
  let s = 0;
  for (const [k, v] of Object.entries(dist)) {
    n += v;
    s += Number(k) * v;
  }
  return n > 0 ? s / n : null;
}

function Bar({ value, max, tone }: { value: number; max: number; tone?: string }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className="h-2 w-full bg-ink-faint/20" role="img" aria-label={`${value}/${max}`}>
      <div className={cx("h-2", tone ?? "bg-accent")} style={{ width: `${pct}%` }} />
    </div>
  );
}

function TestCard({ test }: { test: TestAnalytics }) {
  const total = test.total ?? 0;
  const parts = test.parts ?? [];
  const listening = parts.filter((p) => p.part <= 4);
  const reading = parts.filter((p) => p.part >= 5);
  const sum = (pick: (p: NonNullable<TestAnalytics["parts"]>[number]) => number) =>
    parts.reduce((a, p) => a + pick(p), 0);
  const answers: Record<string, number> = {};
  for (const p of parts)
    for (const [k, v] of Object.entries(p.answers ?? {})) answers[k] = (answers[k] ?? 0) + v;
  const diffMean = mean(
    Object.fromEntries(
      ["1", "2", "3", "4", "5"].map((k) => [
        k,
        parts.reduce((a, p) => a + (p.difficulty?.[k] ?? 0), 0),
      ]),
    ),
  );
  const hard = sum((p) => p.hard_planned ?? 0);
  const hasHard = parts.some((p) => p.hard_planned != null);
  const review = test.review;
  const perf = test.performance;

  return (
    <Panel className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="text-h3 font-semibold">{test.title}</h3>
        <Tag>{test.slug}</Tag>
        <Tag>{test.kind}</Tag>
        <PublishTag status={test.status} />
      </div>
      {(test.flags ?? []).length > 0 && (
        <div className="mb-3 space-y-1.5">
          {(test.flags ?? []).map((f, i) => (
            <Alert key={i} tone="warn">
              {f.message}
            </Alert>
          ))}
        </div>
      )}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <ValueTile Icon={ChartColumn} label="Tổng câu" value={total} empty="Chưa có câu" />
        <ValueTile
          Icon={ChartColumn}
          label="Nghe / Đọc"
          value={`${sum((p) => (p.part <= 4 ? p.count : 0))} / ${sum((p) => (p.part >= 5 ? p.count : 0))}`}
          empty="—"
          numeric={false}
        />
        <ValueTile
          Icon={ChartColumn}
          label="Độ khó TB (DB)"
          value={diffMean == null ? null : diffMean.toFixed(2)}
          empty="Chưa ghi"
        />
        <ValueTile
          Icon={ChartColumn}
          label="Ô hard (ràng buộc sinh đề)"
          value={hasHard ? hard : null}
          empty="Không có blueprint"
        />
      </div>

      <SectionHeader title="Theo part" />
      <table className="mb-4 w-full text-small">
        <thead>
          <tr className="text-left text-ink-muted">
            <th className="py-1 pr-2">Part</th>
            <th className="py-1 pr-2">Câu</th>
            <th className="py-1 pr-2">Đáp án</th>
            <th className="py-1 pr-2">Khó TB</th>
            <th className="py-1 pr-2">Audio</th>
            <th className="py-1">Giải thích</th>
          </tr>
        </thead>
        <tbody>
          {parts.map((p) => {
            const m = mean(p.difficulty);
            return (
              <tr key={p.part} className="border-t border-ink-faint/20">
                <td className="py-1.5 pr-2 font-data">P{p.part}</td>
                <td className="py-1.5 pr-2 font-data">{p.count}</td>
                <td className="py-1.5 pr-2">
                  <span className="font-data">
                    {["A", "B", "C", "D"].map((l) => `${l}:${p.answers?.[l] ?? 0}`).join(" ")}
                  </span>
                  {(p.hard_planned ?? 0) > 0 && (
                    <span className="ml-2 text-ink-muted">hard {p.hard_planned} ô</span>
                  )}
                </td>
                <td className="py-1.5 pr-2 font-data">{m == null ? "—" : m.toFixed(2)}</td>
                <td className="py-1.5 pr-2 font-data">
                  {p.audio_covered}/{p.count}
                </td>
                <td className="py-1.5 font-data">
                  {p.explained}/{p.count}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {listening.length > 0 && reading.length > 0 && (
        <p className="mb-4 text-small text-ink-muted">
          Đáp án toàn đề —{" "}
          {["A", "B", "C", "D"]
            .map((l) => `${l} ${total > 0 ? Math.round(((answers[l] ?? 0) / total) * 100) : 0}%`)
            .join(" · ")}
        </p>
      )}

      <SectionHeader title="Taxonomy" />
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        {(test.facets ?? []).map((f) => {
          const top = (f.codes ?? []).slice(0, 6);
          const max = top[0]?.count ?? 0;
          const labeled = top.reduce((a, c) => a + c.count, 0);
          return (
            <div key={f.facet} className="border border-ink-faint/20 p-2.5">
              <div className="mb-2 flex items-baseline justify-between">
                <span className="font-medium">{f.label_vi}</span>
                <span className="text-small text-ink-muted">
                  {labeled} có nhãn{(f.missing ?? 0) > 0 && ` · thiếu ${f.missing}`}
                </span>
              </div>
              {top.length === 0 ? (
                <p className="text-small text-ink-muted">Chưa gán nhãn nào.</p>
              ) : (
                <div className="space-y-1.5">
                  {top.map((c) => (
                    <div key={c.code}>
                      <div className="mb-0.5 flex items-baseline justify-between gap-2 text-small">
                        <span className="truncate" title={c.code}>
                          {c.label_vi}
                        </span>
                        <span className="font-data">{c.count}</span>
                      </div>
                      <Bar value={c.count} max={Math.max(max, 1)} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <SectionHeader title="Máy gán nhãn & thực tế làm bài" />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <ValueTile
          Icon={ChartColumn}
          label="Nhãn đã duyệt"
          value={review ? `${review.reviewed ?? 0}/${review.labels_total ?? 0}` : null}
          empty="Chưa có nhãn"
          numeric={false}
        />
        <ValueTile
          Icon={ChartColumn}
          label="Máy gán đúng"
          value={
            review && (review.reviewed ?? 0) > 0
              ? `${Math.round(((review.agree ?? 0) / (review.reviewed ?? 1)) * 100)}%`
              : null
          }
          empty="Chưa duyệt nhãn nào"
          numeric={false}
        />
        <ValueTile
          Icon={ChartColumn}
          label="Lượt đã nộp"
          value={perf?.attempts ?? null}
          empty="Chưa ai làm"
        />
        <ValueTile
          Icon={ChartColumn}
          label="Tỉ lệ đúng TB"
          value={perf?.avg_p == null ? null : `${Math.round(perf.avg_p * 100)}%`}
          empty="Chưa có dữ liệu"
          numeric={false}
        />
      </div>
      {(perf?.attempts ?? 0) === 0 && (
        <p className="mt-2 text-small text-ink-muted">
          Đề chưa có lượt nộp nên chưa có p-value — các cột độ khó lúc này chỉ là dự kiến từ
          blueprint và nhãn.
        </p>
      )}
    </Panel>
  );
}

function TaxonomyCompare({ tests }: { tests: TestAnalytics[] }) {
  const facets = tests[0]?.facets ?? [];
  return (
    <Panel className="mb-3 p-4">
      <SectionHeader title="So sánh taxonomy" />
      <div className="grid gap-4 xl:grid-cols-2">
        {facets.map((f) => {
          const order = new Map<string, string>();
          for (const t of tests)
            for (const c of t.facets?.find((x) => x.facet === f.facet)?.codes ?? [])
              if (!order.has(c.code)) order.set(c.code, c.label_vi ?? c.code);
          const counts = (code: string) =>
            tests.map(
              (t) =>
                t.facets?.find((x) => x.facet === f.facet)?.codes?.find((c) => c.code === code)
                  ?.count ?? 0,
            );
          const rows = [...order.keys()]
            .map((code) => ({ code, vals: counts(code) }))
            .sort((a, b) => b.vals.reduce((s, v) => s + v, 0) - a.vals.reduce((s, v) => s + v, 0));
          const missing = tests.map(
            (t) => t.facets?.find((x) => x.facet === f.facet)?.missing ?? 0,
          );
          if (rows.length === 0 && missing.every((m) => m === 0)) return null;
          return (
            <div key={f.facet} className="overflow-x-auto">
              <p className="mb-1.5 font-medium">{f.label_vi}</p>
              <table className="w-full min-w-[320px] text-small">
                <thead>
                  <tr className="text-left text-ink-muted">
                    <th className="py-1 pr-3">Nhãn</th>
                    {tests.map((t) => (
                      <th key={t.slug} className="py-1 pr-3 font-medium text-ink">
                        {t.slug}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ code, vals }) => {
                    const max = Math.max(...vals);
                    return (
                      <tr key={code} className="border-t border-ink-faint/20">
                        <td className="py-1 pr-3" title={code}>
                          {order.get(code)}
                        </td>
                        {vals.map((v, i) => (
                          <td
                            key={tests[i].slug}
                            className={cx(
                              "py-1 pr-3 font-data",
                              v === 0 && "text-ink-faint",
                              max > 0 && v === max && vals.filter((x) => x === max).length === 1
                                ? "font-semibold text-warn"
                                : "text-ink-muted",
                            )}
                          >
                            {v}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                  {missing.some((m) => m > 0) && (
                    <tr className="border-t border-ink-faint/20">
                      <td className="py-1 pr-3 text-ink-muted">Thiếu nhãn</td>
                      {missing.map((m, i) => (
                        <td key={tests[i].slug} className="py-1 pr-3 font-data text-ink-muted">
                          {m}
                        </td>
                      ))}
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

export default function AdminAnalyticsPage() {
  const { token } = useRequireSession({ canEdit: true });
  const [tests, setTests] = useState<TestAnalyticsRow[] | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [data, setData] = useState<CompareOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<TestAnalyticsRow[]>(API_ROUTES.adminAnalyticsTests, { token })
      .then((rows) => {
        setTests(rows);
        setSelected((cur) =>
          cur.length > 0
            ? cur
            : rows
                .filter((r) => r.kind === "full")
                .slice(0, 3)
                .map((r) => r.slug),
        );
      })
      .catch((e: ApiError) => setError(e.message));
  }, [token]);

  const fetchCompare = useCallback((slugs: string[], tk: string | null) => {
    if (!tk || slugs.length === 0) {
      if (slugs.length === 0) setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    apiFetch<CompareOut>(API_ROUTES.adminAnalyticsCompare(slugs.join(",")), { token: tk })
      .then(setData)
      .catch((e: ApiError) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!token) return;
    apiFetch<TestAnalyticsRow[]>(API_ROUTES.adminAnalyticsTests, { token })
      .then((rows) => {
        setTests(rows);
        const initial = rows
          .filter((r) => r.kind === "full")
          .slice(0, 3)
          .map((r) => r.slug);
        setSelected(initial);
        fetchCompare(initial, token);
      })
      .catch((e: ApiError) => setError(e.message));
    // Chạy một lần khi có token: nạp danh sách rồi fetch luôn lượt so sánh
    // đầu tiên. Các lần đổi chọn đề về sau do `toggle` fetch trực tiếp.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const toggle = (slug: string) => {
    const next = selected.includes(slug)
      ? selected.filter((s) => s !== slug)
      : selected.length >= MAX_SELECT
        ? selected
        : [...selected, slug];
    setSelected(next);
    if (detail && !next.includes(detail)) setDetail(null);
    fetchCompare(next, token);
  };

  const compared = data?.tests ?? [];
  const detailTest = detail ? compared.find((t) => t.slug === detail) : undefined;

  const partNums = [...new Set(compared.flatMap((t) => (t.parts ?? []).map((p) => p.part)))].sort(
    (a, b) => a - b,
  );
  const answerPct = (t: TestAnalytics, label: string) => {
    const tot = t.total ?? 0;
    if (tot === 0) return 0;
    const n = (t.parts ?? []).reduce((s, p) => s + (p.answers?.[label] ?? 0), 0);
    return Math.round((n / tot) * 100);
  };
  const coveragePct = (
    t: TestAnalytics,
    pick: (p: NonNullable<TestAnalytics["parts"]>[number]) => [number, number],
  ) => {
    let got = 0;
    let n = 0;
    for (const p of t.parts ?? []) {
      const [g, c] = pick(p);
      got += g;
      n += c;
    }
    return n > 0 ? Math.round((got / n) * 100) : 0;
  };

  return (
    <Page>
      <PageHeader
        title="Chất lượng đề"
        description="Độ khó, taxonomy, media và thực tế làm bài — chọn nhiều đề để đặt cạnh nhau, bấm tên đề để xem chi tiết."
      />
      {error && (
        <div className="mb-3">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}
      {!tests ? (
        <SkeletonList />
      ) : (
        <Panel className="mb-3 p-4">
          <SectionHeader title={`Chọn đề (tối đa ${MAX_SELECT})`} />
          <div className="flex flex-wrap gap-2">
            {tests.map((t) => (
              <label
                key={t.slug}
                className={cx(
                  "flex cursor-pointer items-center gap-1.5 border px-2.5 py-1.5 text-small",
                  selected.includes(t.slug) ? "border-accent bg-accent/10" : "border-ink-faint/30",
                )}
              >
                <input
                  type="checkbox"
                  checked={selected.includes(t.slug)}
                  onChange={() => toggle(t.slug)}
                  className="accent-[var(--color-accent)]"
                />
                <span className="font-medium">{t.slug}</span>
                <span className="font-data text-ink-muted">{t.total}</span>
              </label>
            ))}
          </div>
        </Panel>
      )}
      {loading && <SkeletonList />}
      {!loading && selected.length === 0 && (
        <EmptyState
          icon={ChartColumn}
          title="Chưa chọn đề nào"
          description="Tick ít nhất một đề ở trên để xem khóa chất lượng."
        />
      )}
      {!loading && detailTest && (
        <>
          <div className="mb-3">
            <Button variant="quiet" onClick={() => setDetail(null)}>
              <ArrowLeft size={16} /> Quay lại so sánh
            </Button>
          </div>
          <div className="mb-3">
            <TestCard test={detailTest} />
          </div>
        </>
      )}
      {!loading && !detailTest && compared.length >= 1 && (
        <Panel className="mb-3 overflow-x-auto p-4">
          <SectionHeader title="So sánh nhanh" />
          <table className="w-full min-w-[560px] text-small">
            <thead>
              <tr className="text-left text-ink-muted">
                <th className="py-1 pr-3">Tiêu chí</th>
                {compared.map((t) => (
                  <th key={t.slug} className="py-1 pr-3">
                    <button
                      type="button"
                      onClick={() => setDetail(t.slug)}
                      className="font-medium text-accent underline-offset-2 hover:underline"
                      title={`Xem chi tiết ${t.slug}`}
                    >
                      {t.slug}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(
                [
                  {
                    label: "Tổng câu",
                    text: (t) => `${t.total ?? 0}`,
                    num: (t) => t.total ?? 0,
                  },
                  {
                    label: "Nghe / Đọc",
                    text: (t) =>
                      `${(t.parts ?? []).filter((p) => p.part <= 4).reduce((a, p) => a + p.count, 0)} / ${(t.parts ?? []).filter((p) => p.part >= 5).reduce((a, p) => a + p.count, 0)}`,
                    num: () => null,
                  },
                  {
                    label: "Đáp án A·B·C·D %",
                    text: (t) => {
                      const tot = t.total ?? 0;
                      const a: Record<string, number> = {};
                      for (const p of t.parts ?? [])
                        for (const [k, v] of Object.entries(p.answers ?? {}))
                          a[k] = (a[k] ?? 0) + v;
                      return ["A", "B", "C", "D"]
                        .map((l) => (tot > 0 ? Math.round(((a[l] ?? 0) / tot) * 100) : 0))
                        .join("·");
                    },
                    num: () => null,
                  },
                  {
                    label: "Ô hard",
                    text: (t) =>
                      (t.parts ?? []).some((p) => p.hard_planned != null)
                        ? `${(t.parts ?? []).reduce((s, p) => s + (p.hard_planned ?? 0), 0)}`
                        : "—",
                    num: (t) =>
                      (t.parts ?? []).some((p) => p.hard_planned != null)
                        ? (t.parts ?? []).reduce((s, p) => s + (p.hard_planned ?? 0), 0)
                        : null,
                  },
                  {
                    label: "Audio đủ",
                    text: (t) => {
                      const ps = (t.parts ?? []).filter((p) => p.part <= 4);
                      const n = ps.reduce((s, p) => s + p.count, 0);
                      const got = ps.reduce((s, p) => s + (p.audio_covered ?? 0), 0);
                      return n > 0 ? `${Math.round((got / n) * 100)}%` : "—";
                    },
                    num: (t) => {
                      const ps = (t.parts ?? []).filter((p) => p.part <= 4);
                      const n = ps.reduce((s, p) => s + p.count, 0);
                      const got = ps.reduce((s, p) => s + (p.audio_covered ?? 0), 0);
                      return n > 0 ? got / n : null;
                    },
                  },
                  {
                    label: "Có giải thích",
                    text: (t) => {
                      const n = (t.parts ?? []).reduce((s, p) => s + p.count, 0);
                      const got = (t.parts ?? []).reduce((s, p) => s + (p.explained ?? 0), 0);
                      return n > 0 ? `${Math.round((got / n) * 100)}%` : "—";
                    },
                    num: (t) => {
                      const n = (t.parts ?? []).reduce((s, p) => s + p.count, 0);
                      const got = (t.parts ?? []).reduce((s, p) => s + (p.explained ?? 0), 0);
                      return n > 0 ? got / n : null;
                    },
                  },
                  {
                    label: "Nhãn đã duyệt",
                    text: (t) =>
                      t.review && (t.review.labels_total ?? 0) > 0
                        ? `${t.review.reviewed}/${t.review.labels_total}`
                        : "—",
                    num: (t) =>
                      t.review && (t.review.labels_total ?? 0) > 0
                        ? (t.review.reviewed ?? 0) / (t.review.labels_total ?? 1)
                        : null,
                  },
                  {
                    label: "Lượt nộp",
                    text: (t) => `${t.performance?.attempts ?? 0}`,
                    num: (t) => t.performance?.attempts ?? 0,
                  },
                  {
                    label: "Tỉ lệ đúng TB",
                    text: (t) =>
                      t.performance?.avg_p == null
                        ? "—"
                        : `${Math.round(t.performance.avg_p * 100)}%`,
                    num: (t) => t.performance?.avg_p ?? null,
                  },
                ] as {
                  label: string;
                  text: (t: TestAnalytics) => string;
                  num: (t: TestAnalytics) => number | null;
                }[]
              ).map(({ label, text, num }) => {
                const vals = compared.map(num);
                const defined = vals.filter((v): v is number => v != null);
                const max = defined.length > 0 ? Math.max(...defined) : null;
                const unique = max != null && defined.filter((v) => v === max).length === 1;
                return (
                  <tr key={label} className="border-t border-ink-faint/20">
                    <td className="py-1.5 pr-3 text-ink-muted">{label}</td>
                    {compared.map((t, i) => (
                      <td
                        key={t.slug}
                        className={cx(
                          "py-1.5 pr-3 font-data",
                          unique && vals[i] === max ? "font-semibold text-warn" : "text-ink",
                        )}
                      >
                        {text(t)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Panel>
      )}
      {!loading && !detailTest && compared.length >= 1 && (
        <Panel className="mb-3 p-4">
          <SectionHeader title="Biểu đồ so sánh" />
          <div className="mb-5">
            <p className="mb-1 text-small font-medium">Số câu theo part</p>
            <GroupedBars
              series={compared.map((t) => t.slug)}
              groups={partNums.map((p) => ({
                label: `P${p}`,
                values: compared.map((t) => t.parts?.find((x) => x.part === p)?.count ?? 0),
              }))}
            />
          </div>
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <p className="mb-1 text-small font-medium">Đáp án đúng (%)</p>
              <GroupedBars
                series={compared.map((t) => t.slug)}
                groups={["A", "B", "C", "D"].map((l) => ({
                  label: l,
                  values: compared.map((t) => answerPct(t, l)),
                }))}
                format={(v) => `${v}%`}
              />
            </div>
            <div>
              <p className="mb-1 text-small font-medium">Độ phủ (%)</p>
              <GroupedBars
                series={compared.map((t) => t.slug)}
                groups={[
                  {
                    label: "Audio",
                    values: compared.map((t) =>
                      coveragePct(t, (p) =>
                        p.part <= 4 ? [p.audio_covered ?? 0, p.count] : [0, 0],
                      ),
                    ),
                  },
                  {
                    label: "Giải thích",
                    values: compared.map((t) => coveragePct(t, (p) => [p.explained ?? 0, p.count])),
                  },
                  {
                    label: "Duyệt nhãn",
                    values: compared.map((t) =>
                      t.review && (t.review.labels_total ?? 0) > 0
                        ? Math.round(
                            ((t.review.reviewed ?? 0) / (t.review.labels_total ?? 1)) * 100,
                          )
                        : 0,
                    ),
                  },
                ]}
                format={(v) => `${v}%`}
              />
            </div>
          </div>
        </Panel>
      )}
      {!loading && !detailTest && compared.length >= 2 && <TaxonomyCompare tests={compared} />}
      {!loading && !detailTest && compared.length > 0 && (
        <p className="flex items-center gap-1.5 text-small text-ink-muted">
          <TriangleAlert size={14} />
          Cột độ khó trong DB hiện mọi câu đều là 3 — pipeline load chưa truyền độ khó thật. Ô hard
          không phải độ khó: nó là ràng buộc sinh đề (mỗi ô phải có bấy nhiêu câu ghép chứng cứ từ
          hai chỗ tách rời), P3/P4 bị ép cứng mọi ô nên đề nào cùng đời cũng ra 34; đề đời cũ hiện
          &ldquo;—&rdquo; vì blueprint chưa có cờ này. Muốn đo khó thật thì đọc p-value khi đề đã có
          lượt làm.
        </p>
      )}
    </Page>
  );
}
