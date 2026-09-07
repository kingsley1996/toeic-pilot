"use client";

import { API_ROUTES, type ComparePayload, type EvalRow } from "@toeic-pilot/shared";
import { FlaskConical, Play } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  EmptyState,
  Page,
  PageHeader,
  Panel,
  Select,
  SkeletonList,
  cx,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * So sánh planner V1 (rule) / V2 (LLM) — SPEC-PLACEMENT §5.
 *
 * Nút chạy là một lượt gọi model THẬT (tiền + ~54 giây), nên nó là hành động
 * có xác nhận; trang đọc chỉ đọc. Câu hỏi màn này trả lời bằng số: "AI xếp
 * khác gì rule, và đáng tiền không?"
 */
export default function PlannerComparePage() {
  const { token } = useRequireSession({ canEdit: true });
  const [data, setData] = useState<ComparePayload | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    apiFetch<ComparePayload>(API_ROUTES.adminPlannerCompare, { token })
      .then((d) => {
        setData(d);
        if (!selected && d.attempts.length > 0) setSelected(d.attempts[0].attempt_id);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được dữ liệu."));
  }, [token, selected]);

  useEffect(() => {
    load();
    // `load` đổi khi `selected` đổi nhưng việc chọn lượt không cần nạp lại trang.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function run() {
    if (!token || !selected || running) return;
    setRunning(true);
    setError(null);
    try {
      await apiFetch<EvalRow>(API_ROUTES.adminPlannerRun, {
        method: "POST",
        token,
        body: JSON.stringify({ attempt_id: selected }),
      });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không chạy được so sánh.");
    } finally {
      setRunning(false);
    }
  }

  if (status === "loading") {
    return (
      <Page>
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="So sánh planner"
        description="Kế hoạch rule so với kế hoạch AI trên cùng một kết quả bài test đầu vào. Chạy là gọi model thật."
      />

      {error && (
        <div className="mb-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      {data && data.stats.ok + data.stats.error > 0 && (
        <div className="grid gap-3 sm:grid-cols-4">
          <SmallStat label="Lượt V2 thành công" value={String(data.stats.ok)} />
          <SmallStat label="Lượt V2 lỗi (→ rule)" value={String(data.stats.error)} />
          <SmallStat
            label="Chi phí / lượt"
            value={
              data.stats.avg_cost_usd !== null ? `$${data.stats.avg_cost_usd.toFixed(4)}` : "—"
            }
          />
          <SmallStat
            label="Độ trễ / lượt"
            value={
              data.stats.avg_latency_ms !== null
                ? `${(data.stats.avg_latency_ms / 1000).toFixed(1)}s`
                : "—"
            }
          />
        </div>
      )}

      <Panel className="mt-4 flex flex-wrap items-end gap-3 p-4">
        <label className="min-w-0 flex-1">
          <span className="block text-label font-semibold uppercase text-ink-faint">
            Lượt placement
          </span>
          <Select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="mt-1 w-full"
            aria-label="Chọn lượt placement để so sánh"
          >
            {(data?.attempts ?? []).map((a) => (
              <option key={a.attempt_id} value={a.attempt_id}>
                {a.email} · {a.cefr_overall ?? "?"} · {a.weak_count} điểm yếu
                {a.plan_source ? ` · kế hoạch: ${a.plan_source}` : ""}
              </option>
            ))}
          </Select>
        </label>
        <Button disabled={running || !selected} onClick={() => void run()}>
          <Play size={14} strokeWidth={2} className="mr-1.5" aria-hidden />
          {running ? "Đang chạy (gọi model thật)…" : "Chạy so sánh"}
        </Button>
      </Panel>

      {!data && <SkeletonList rows={3} />}

      {data && data.rows.length === 0 && (
        <div className="mt-6">
          <EmptyState
            icon={FlaskConical}
            title="Chưa có lượt so sánh nào"
            description="Chạy một lượt để lưu kết quả đầu tiên."
          />
        </div>
      )}

      <div className="mt-4 space-y-3">
        {data?.rows.map((row) => (
          <Panel key={row.id} className="p-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-small">
              <span className="font-semibold">{row.email}</span>
              <span className="text-ink-muted">
                {new Date(row.created_at).toLocaleString("vi-VN")}
              </span>
              {row.model && <span className="font-data text-ink-faint">{row.model}</span>}
              {row.cost_usd !== null && (
                <span className="font-data tabular-nums text-ink-faint">
                  ${row.cost_usd.toFixed(4)}
                </span>
              )}
              <span className="font-data tabular-nums text-ink-faint">
                {(row.latency_ms / 1000).toFixed(1)}s
              </span>
              <span
                className={cx(
                  "ml-auto rounded px-2 py-0.5 font-data text-small",
                  row.v2_items ? "bg-ok-tint text-ok" : "bg-warn-tint text-warn",
                )}
              >
                {row.v2_items
                  ? `phủ ${((row.coverage ?? 0) * 100).toFixed(0)}% V1`
                  : "V2 lỗi → rule"}
              </span>
            </div>

            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-label font-semibold uppercase text-ink-faint">
                  V1 rule · {row.v1_items.length} mục
                </p>
                <ol className="mt-1.5 space-y-1">
                  {row.v1_items.map((i, idx) => (
                    <li key={idx} className="text-small">
                      {idx + 1}. {i.label}
                    </li>
                  ))}
                </ol>
              </div>
              <div>
                <p className="text-label font-semibold uppercase text-ink-faint">
                  {row.v2_items
                    ? `V2 AI · ${row.v2_items.length} mục${row.dangling > 0 ? ` · ${row.dangling} ref treo` : ""}`
                    : "V2 AI · không dùng được"}
                </p>
                {row.v2_items ? (
                  <ol className="mt-1.5 space-y-1">
                    {row.v2_items.map((i, idx) => (
                      <li key={idx} className="text-small">
                        {idx + 1}. {i.label}
                        {i.reason && (
                          <span className="block pl-4 text-label text-ink-muted">{i.reason}</span>
                        )}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="mt-1.5 text-small text-ink-muted">
                    {row.error ?? "Model không trả được lựa chọn hợp lệ."}
                  </p>
                )}
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </Page>
  );
}

function SmallStat({ label, value }: { label: string; value: string }) {
  return (
    <Panel className="p-3">
      <p className="text-label font-semibold uppercase text-ink-faint">{label}</p>
      <p className="mt-1 font-data text-subtitle font-semibold tabular-nums">{value}</p>
    </Panel>
  );
}
