"use client";

import { API_ROUTES, type ServiceUptime, type UptimeReport } from "@toeic-pilot/shared";
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Page, PageHeader, Panel, Tag, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Uptime of the services this project runs on.
 *
 * The history comes from `/ready`, which already checks Postgres and Redis every
 * time it is called and is called every five minutes by the uptime monitor. No
 * scheduler was added, because nothing schedules anything in this architecture.
 *
 * The limit is stated on the page rather than hidden: a Postgres outage cannot
 * be written to Postgres, so it appears as a **gap**, never as a red bar. Gaps
 * are drawn in their own colour and excluded from the percentage — a number that
 * quietly counts unrecorded minutes as healthy is worse than no number.
 */

const WINDOWS = [
  { hours: 6, label: "6h" },
  { hours: 24, label: "24h" },
  { hours: 72, label: "3d" },
  { hours: 168, label: "7d" },
] as const;

const BAR_TONE: Record<string, string> = {
  ok: "var(--ok)",
  degraded: "var(--warn)",
  down: "var(--alert)",
};

function Strip({ service }: { service: ServiceUptime }) {
  return (
    <div className="mt-3 flex h-9 items-stretch gap-[2px] overflow-hidden rounded">
      {service.buckets.map((bucket, i) => {
        const tone = bucket.state ? BAR_TONE[bucket.state] : null;
        const at = new Date(bucket.start).toLocaleString();
        return (
          <span
            key={i}
            className={cx("upbar min-w-0 flex-1", tone ? "" : "is-gap")}
            style={{
              background: tone ? `rgb(${tone})` : undefined,
              animationDelay: `${Math.min(i * 8, 600)}ms`,
            }}
            title={
              bucket.state
                ? `${at} · ${bucket.state}${bucket.latency_ms != null ? ` · ${bucket.latency_ms} ms` : ""}`
                : `${at} · no sample recorded`
            }
          />
        );
      })}
    </div>
  );
}

function ServiceCard({ service, retention }: { service: ServiceUptime; retention: number }) {
  const gaps = service.buckets.filter((b) => b.state === null).length;
  const latencies = service.buckets
    .map((b) => b.latency_ms)
    .filter((v): v is number => v != null)
    .sort((a, b) => a - b);
  const median = latencies.length ? latencies[Math.floor(latencies.length / 2)] : null;

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-subtitle">{service.label}</h2>
        <div className="flex items-center gap-2">
          {service.worst && (
            <Tag tone={service.worst === "ok" ? "ok" : service.worst === "down" ? "alert" : "warn"}>
              {service.worst === "ok" ? "no incident" : service.worst}
            </Tag>
          )}
          <span className="font-mono text-title font-semibold tabular-nums">
            {service.ok_ratio == null ? "—" : `${(service.ok_ratio * 100).toFixed(2)}%`}
          </span>
        </div>
      </div>

      <Strip service={service} />

      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 border-t border-rule pt-3 text-small">
        <div className="flex gap-2">
          <dt className="text-ink-faint">Samples</dt>
          <dd className="font-mono tabular-nums text-ink-muted">{service.samples}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-ink-faint">Median</dt>
          <dd className="font-mono tabular-nums text-ink-muted">
            {median == null ? "—" : `${median} ms`}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-ink-faint">Gaps</dt>
          <dd className="font-mono tabular-nums text-ink-muted">
            {gaps} / {service.buckets.length}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-ink-faint">Kept</dt>
          <dd className="font-mono tabular-nums text-ink-muted">{retention} days</dd>
        </div>
      </dl>
    </Panel>
  );
}

export default function HealthPage() {
  const { status: session, token } = useRequireSession({ canEdit: true });
  const [hours, setHours] = useState<number>(24);
  const [report, setReport] = useState<UptimeReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  const fetchReport = useCallback((auth: string, window: number) => {
    return apiFetch<UptimeReport>(`${API_ROUTES.adminSystemUptime}?hours=${window}&slots=72`, {
      token: auth,
    })
      .then(setReport)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not read the uptime history."),
      )
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => {
    if (!token) return;
    void fetchReport(token, hours);
  }, [token, hours, fetchReport]);

  const recheck = () => {
    if (!token) return;
    setBusy(true);
    setError(null);
    void fetchReport(token, hours);
  };

  if (session !== "authenticated") return null;

  const empty = report?.services.every((s) => s.samples === 0) ?? false;

  return (
    <Page>
      <PageHeader
        eyebrow="Operations"
        title="Service uptime"
        description="Recorded every time /ready runs — which is every five minutes, because that is what keeps the free tiers from sleeping."
        actions={
          <Button onClick={recheck} disabled={busy}>
            <RefreshCw
              size={15}
              strokeWidth={1.75}
              className={cx(busy && "animate-spin")}
              aria-hidden
            />
            {busy ? "Loading" : "Refresh"}
          </Button>
        }
      />

      {error && <Alert tone="alert">{error}</Alert>}

      <div className="flex flex-wrap items-center gap-2">
        {WINDOWS.map((w) => (
          <Button
            key={w.hours}
            size="sm"
            variant={hours === w.hours ? "primary" : "secondary"}
            onClick={() => setHours(w.hours)}
          >
            {w.label}
          </Button>
        ))}
        {report && (
          <span className="ml-1 font-mono text-small text-ink-faint">
            since {new Date(report.since).toLocaleString()}
          </span>
        )}
      </div>

      {empty && (
        <div className="mt-4">
          <Alert tone="info">
            No samples yet. History starts building the first time <code>/ready</code> is called
            after this deploy — the uptime monitor does that within five minutes.
          </Alert>
        </div>
      )}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {report?.services.map((s) => (
          <ServiceCard key={s.service} service={s} retention={report.retention_days} />
        ))}
      </div>

      <Panel className="mt-4 p-4">
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {(
            [
              ["Healthy", "var(--ok)"],
              ["Degraded", "var(--warn)"],
              ["Down", "var(--alert)"],
            ] as const
          ).map(([label, colour]) => (
            <span key={label} className="flex items-center gap-1.5 text-small text-ink-muted">
              <span className="h-3 w-3 rounded" style={{ background: `rgb(${colour})` }} />
              {label}
            </span>
          ))}
          <span className="flex items-center gap-1.5 text-small text-ink-muted">
            <span className="upbar is-gap h-3 w-3 rounded" />
            No sample recorded
          </span>
        </div>

        <p className="mt-3 border-t border-rule pt-3 text-small text-ink-muted">
          <strong>A gap is not the same as green, and not the same as red.</strong> These samples
          are written to Postgres by the very request that checks it, so a Postgres outage cannot
          record itself — it leaves a hole. The same is true of the API: if it is asleep or down,
          nothing runs to write anything. Gaps are excluded from the percentage rather than counted
          as healthy.
        </p>
        <p className="mt-2 text-small text-ink-muted">
          Only two services appear here, and that is the honest boundary: the API can record what it
          calls. The audio and image stores are fetched by the browser directly, so they are
          measured on <strong>Production topology</strong> instead, in the viewer&rsquo;s own
          browser.
        </p>
      </Panel>
    </Page>
  );
}
