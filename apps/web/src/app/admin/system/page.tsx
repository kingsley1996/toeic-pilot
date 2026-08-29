"use client";

import { API_ROUTES, type SystemStatus } from "@toeic-pilot/shared";
import type { Edge, Node } from "@xyflow/react";
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Modal } from "@/components/modal";
import { NODE_FACTS } from "@/components/system-facts";
import { SystemFlow, type ProbeState, type ServiceData } from "@/components/system-flow";
import { Alert, Button, Page, PageHeader, Panel, Tag, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Live map of what production is made of (ADR-014).
 *
 * Two kinds of check, and the split is the point. Postgres and Redis are things
 * the API itself calls, so the API reports them. Audio and images are fetched by
 * the browser straight from the CDN and never pass through the API, so probing
 * them server-side would test a path nobody walks — this page probes them from
 * the browser instead, which is exactly what a learner's browser does.
 */

type MediaProbe = { state: ProbeState; latencyMs: number | null };

const LAYOUT = {
  browser: { x: 0, y: 250 },
  ci: { x: 320, y: 0 },
  ghcr: { x: 640, y: 0 },
  web: { x: 320, y: 130 },
  api: { x: 640, y: 250 },
  db: { x: 960, y: 175 },
  redis: { x: 960, y: 325 },
  audio: { x: 320, y: 375 },
  image: { x: 320, y: 490 },
} as const;

function edge(
  id: string,
  source: string,
  target: string,
  label: string,
  colour: string,
  opts: Partial<Edge> = {},
): Edge {
  return {
    id,
    source,
    target,
    label,
    animated: true,
    style: { stroke: `rgb(${colour})`, strokeWidth: 1.6 },
    labelBgPadding: [5, 2],
    labelBgBorderRadius: 4,
    ...opts,
  };
}

export default function SystemMonitorPage() {
  const { status: session, token } = useRequireSession({ canEdit: true });
  const [data, setData] = useState<SystemStatus | null>(null);
  const [probes, setProbes] = useState<Record<string, MediaProbe>>({});
  const [error, setError] = useState<string | null>(null);
  // Bắt đầu ở trạng thái đang tải: lượt đọc đầu chạy ngay khi có token.
  const [busy, setBusy] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  const fetchStatus = useCallback((auth: string) => {
    return apiFetch<SystemStatus>(API_ROUTES.adminSystemStatus, { token: auth })
      .then((next) => {
        setData(next);
        // Đo từ TRÌNH DUYỆT, vì đó là nơi media thật sự được tải về.
        for (const channel of next.media) {
          if (!channel.sample_url) {
            setProbes((p) => ({ ...p, [channel.id]: { state: "unknown", latencyMs: null } }));
            continue;
          }
          setProbes((p) => ({ ...p, [channel.id]: { state: "checking", latencyMs: null } }));
          const started = performance.now();
          fetch(channel.sample_url, { method: "HEAD", cache: "no-store" })
            .then((res) => ({
              state: (res.ok ? "ok" : "down") as ProbeState,
              latencyMs: performance.now() - started,
            }))
            // Lỗi mạng ở đây là "không kiểm được", không phải "đã chết": một CDN
            // chặn CORS trông giống hệt một CDN sập, và gọi nhầm là báo động giả.
            .catch(() => ({ state: "unknown" as ProbeState, latencyMs: null }))
            .then((probe) => setProbes((p) => ({ ...p, [channel.id]: probe })));
        }
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not read the system status."),
      )
      .finally(() => setBusy(false));
  }, []);

  // Effect KHÔNG đặt state đồng bộ — `react-hooks/set-state-in-effect` từ chối
  // đúng chỗ đó, và nó đúng: `busy` đã bắt đầu bằng true nên không cần đặt lại.
  useEffect(() => {
    if (!token) return;
    void fetchStatus(token);
  }, [token, fetchStatus]);

  const recheck = () => {
    if (!token) return;
    setBusy(true);
    setError(null);
    void fetchStatus(token);
  };

  const { nodes, edges } = useMemo(() => {
    const dep = (id: string) => data?.dependencies.find((d) => d.id === id);
    const media = (id: string) => data?.media.find((m) => m.id === id);
    const db = dep("database");
    const redis = dep("redis");
    const audio = media("audio");
    const image = media("image");

    const make = (
      id: keyof typeof LAYOUT,
      d: Omit<ServiceData, "index" | "selected">,
      index: number,
    ): Node<ServiceData> => ({
      id,
      type: "service",
      position: LAYOUT[id],
      data: { ...d, index, selected: id === selected },
      draggable: false,
    });

    const nodes: Node<ServiceData>[] = [
      make(
        "browser",
        { label: "Learner's browser", provider: "any device", tier: "client", state: "ok" },
        0,
      ),
      make(
        "web",
        {
          label: "Web · Next.js",
          provider: "toeic-pilot-web.vercel.app",
          tier: "edge",
          state: "ok",
        },
        1,
      ),
      make(
        "api",
        {
          label: "API · FastAPI",
          provider: "toeic-pilot-api-main.onrender.com",
          tier: "compute",
          state: data ? "ok" : "checking",
          detail: data?.environment,
        },
        2,
      ),
      make(
        "db",
        {
          label: "PostgreSQL",
          provider: db?.provider ?? "supabase",
          tier: "data",
          state: (db?.state as ProbeState) ?? "checking",
          latencyMs: db?.latency_ms,
          detail: db?.detail,
        },
        3,
      ),
      make(
        "redis",
        {
          label: "Redis",
          provider: redis?.provider ?? "upstash",
          tier: "data",
          state: (redis?.state as ProbeState) ?? "checking",
          latencyMs: redis?.latency_ms,
          detail: redis?.detail,
        },
        4,
      ),
      make(
        "audio",
        {
          label: "Audio store",
          provider: audio?.public_base_url ?? "—",
          tier: "media",
          state: probes.audio?.state ?? "checking",
          latencyMs: probes.audio?.latencyMs,
          detail: audio?.driver,
        },
        5,
      ),
      make(
        "image",
        {
          label: "Image store",
          provider: image?.public_base_url ?? "—",
          tier: "media",
          state: probes.image?.state ?? "checking",
          latencyMs: probes.image?.latencyMs,
          detail: image?.driver,
        },
        6,
      ),
      make(
        "ci",
        {
          label: "GitHub Actions",
          provider: "builds & boots the image",
          tier: "build",
          state: "ok",
        },
        7,
      ),
      make(
        "ghcr",
        { label: "GHCR", provider: "ghcr.io · toeic-pilot-api", tier: "build", state: "ok" },
        8,
      ),
    ];

    const edges: Edge[] = [
      edge("e-browser-web", "browser", "web", "page", "var(--accent-us)", {
        sourceHandle: "s-right",
        targetHandle: "t-left",
      }),
      edge("e-browser-api", "browser", "api", "data · CORS", "var(--action)", {
        sourceHandle: "s-right",
        targetHandle: "t-left",
      }),
      edge("e-browser-audio", "browser", "audio", "audio", "var(--accent-uk)", {
        sourceHandle: "s-right",
        targetHandle: "t-left",
      }),
      edge("e-browser-image", "browser", "image", "images", "var(--accent-uk)", {
        sourceHandle: "s-right",
        targetHandle: "t-left",
      }),
      edge("e-api-db", "api", "db", "SQL", "var(--accent-au)", {
        sourceHandle: "s-right",
        targetHandle: "t-left",
      }),
      edge("e-api-redis", "api", "redis", "tokens · limits", "var(--accent-au)", {
        sourceHandle: "s-right",
        targetHandle: "t-left",
      }),
      edge("e-ci-ghcr", "ci", "ghcr", "push image", "var(--ink-faint)", {
        sourceHandle: "s-right",
        targetHandle: "t-left",
        animated: false,
        style: { stroke: "rgb(var(--ink-faint))", strokeWidth: 1.4, strokeDasharray: "4 4" },
      }),
      edge("e-ghcr-api", "ghcr", "api", "deploy hook", "var(--ink-faint)", {
        sourceHandle: "s-bottom",
        targetHandle: "t-top",
        animated: false,
        style: { stroke: "rgb(var(--ink-faint))", strokeWidth: 1.4, strokeDasharray: "4 4" },
      }),
    ];
    return { nodes, edges };
  }, [data, probes, selected]);

  if (session !== "authenticated") return null;

  const unhealthy = data?.dependencies.filter((d) => d.state !== "ok") ?? [];

  return (
    <Page>
      <PageHeader
        title="Production topology"
        description="What the live system is made of, and which parts answered just now."
        actions={
          <Button onClick={recheck} disabled={busy}>
            <RefreshCw
              size={15}
              strokeWidth={1.75}
              className={cx(busy && "animate-spin")}
              aria-hidden
            />
            {busy ? "Checking" : "Re-check"}
          </Button>
        }
      />

      {error && <Alert tone="alert">{error}</Alert>}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Tag tone={data?.environment === "production" ? "ok" : "warn"}>
          {data?.environment ?? "…"}
        </Tag>
        {data?.schema_revision && <Tag tone="neutral">schema {data.schema_revision}</Tag>}
        {unhealthy.length === 0 && data ? (
          <Tag tone="ok">all dependencies healthy</Tag>
        ) : (
          unhealthy.map((d) => (
            <Tag key={d.id} tone={d.state === "down" ? "alert" : "warn"}>
              {d.label} {d.state}
            </Tag>
          ))
        )}
        {data && (
          <span className="font-mono text-small text-ink-faint">
            checked {new Date(data.checked_at).toLocaleTimeString()}
          </span>
        )}
      </div>

      <div className="mt-4">
        <SystemFlow nodes={nodes} edges={edges} onSelect={setSelected} />
      </div>

      <Panel className="mt-4 p-4">
        <p className="text-small text-ink-muted">
          Solid lines carry a request; dashed lines are the deploy path, which only moves when
          someone pushes to <code className="font-mono text-[12px]">main</code>.{" "}
          <strong>Click any box for what it is and what breaks without it.</strong>
        </p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-rule pt-3">
          {(
            [
              ["Request path", "var(--action)"],
              ["Data stores", "var(--accent-au)"],
              ["Media, direct to browser", "var(--accent-uk)"],
              ["Deploy path", "var(--ink-faint)"],
            ] as const
          ).map(([label, colour]) => (
            <span key={label} className="flex items-center gap-1.5 text-small text-ink-muted">
              <span className="h-0.5 w-5 rounded" style={{ background: `rgb(${colour})` }} />
              {label}
            </span>
          ))}
        </div>
      </Panel>

      <Modal
        open={selected !== null && selected in NODE_FACTS}
        onClose={() => setSelected(null)}
        title={selected ? (NODE_FACTS[selected]?.title ?? "") : ""}
      >
        {selected && NODE_FACTS[selected] && (
          <>
            <p className="text-small text-ink-muted">{NODE_FACTS[selected].role}</p>
            <dl className="mt-4 space-y-2 border-t border-rule pt-4">
              {NODE_FACTS[selected].facts.map(([key, value]) => (
                <div key={key} className="flex gap-4 text-small">
                  <dt className="w-[36%] shrink-0 text-ink-faint">{key}</dt>
                  <dd className="min-w-0 text-ink-muted">{value}</dd>
                </div>
              ))}
            </dl>
            {NODE_FACTS[selected].ifItFails && (
              <div className="mt-4 rounded border border-warn bg-warn-tint px-3 py-2.5">
                <p className="text-label font-semibold uppercase text-warn">If it fails</p>
                <p className="mt-1 text-small text-ink-muted">{NODE_FACTS[selected].ifItFails}</p>
              </div>
            )}
          </>
        )}
      </Modal>
    </Page>
  );
}
