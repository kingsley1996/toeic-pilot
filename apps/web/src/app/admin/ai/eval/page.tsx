"use client";

import {
  API_ROUTES,
  type EvalOverview,
  type EvalRunDetail,
  type EvalRunRow,
} from "@toeic-pilot/shared";
import { CheckCircle2, FlaskConical, Loader2, Play, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Button,
  Page,
  PageHeader,
  Panel,
  SectionHeader,
  SkeletonList,
  StatusTag,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

const SUITES = ["all", "coach", "shape", "retrieval", "planner", "exam", "judge"] as const;

/**
 * Chạy và xem eval AI từ giao diện.
 *
 * Nút bấm chỉ XẾP HÀNG (202) — worker eval mới là thứ chạy suite, vì API không
 * được import `app.content`. Danh sách tự làm mới trong khi còn lượt chạy dở.
 */
export default function AdminEvalPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [overview, setOverview] = useState<EvalOverview | null>(null);
  const [runs, setRuns] = useState<EvalRunRow[]>([]);
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);
  const [suite, setSuite] = useState<string>("all");
  const [retrievalMode, setRetrievalMode] = useState<string>("lexical");
  const [judgeModel, setJudgeModel] = useState("");
  const [genModel, setGenModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async (bearer: string) => {
    const next = await apiFetch<EvalRunRow[]>(API_ROUTES.adminAiEvalRuns, { token: bearer });
    return next;
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function load(bearer: string) {
      const nextOverview = await apiFetch<EvalOverview>(API_ROUTES.adminAiEvalOverview, {
        token: bearer,
      });
      const nextRuns = await loadRuns(bearer);
      if (!cancelled) {
        setOverview(nextOverview);
        setRuns(nextRuns);
      }
    }
    load(token).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token, loadRuns]);

  useEffect(() => {
    if (!token) return;
    if (!runs.some((row) => row.status === "queued" || row.status === "running")) return;
    const timer = setInterval(() => {
      loadRuns(token)
        .then((next) => setRuns(next))
        .catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, [token, runs, loadRuns]);

  if (status === "loading") {
    return (
      <Page>
        <SkeletonList rows={6} />
      </Page>
    );
  }

  async function startRun() {
    if (!token || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await apiFetch<EvalRunRow>(API_ROUTES.adminAiEvalRuns, {
        token,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          suite,
          judge_model: judgeModel || null,
          gen_model: genModel || null,
          retrieval_mode: retrievalMode,
        }),
      });
      setRuns((prev) => [created, ...prev]);
      setSuite("all");
      setJudgeModel("");
      setGenModel("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Queueing failed");
    } finally {
      setBusy(false);
    }
  }

  async function openRun(id: string) {
    if (!token) return;
    try {
      const next = await apiFetch<EvalRunDetail>(API_ROUTES.adminAiEvalRun(id), { token });
      setDetail(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Loading failed");
    }
  }

  return (
    <Page>
      <PageHeader
        title="Eval runs"
        description="Offline suites (free) and the LLM judge (costs real money) — queued here, executed by the eval worker, never inside a request."
      />

      <section className="mt-6 grid gap-3 lg:grid-cols-2">
        <div>
          <SectionHeader
            title="Suites"
            aside={
              overview && (
                <span className="text-small text-ink-muted">
                  manifest {overview.manifest_version}
                  {overview.manifest_match ? "" : " — datasets changed since pin"}
                </span>
              )
            }
          />
          <Panel className="overflow-x-auto p-0">
            <table className="w-full min-w-[320px] text-small">
              <tbody>
                {(overview?.suites ?? []).map((row) => (
                  <tr key={row.name} className="border-b border-rule last:border-0">
                    <td className="px-4 py-2.5 font-data text-label">{row.name}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-ink-muted">
                      {row.cases} cases
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-ink-muted">
                      ≥{(row.threshold * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        </div>

        <div>
          <SectionHeader title="Queue a run" />
          <Panel className="flex flex-col gap-3 p-4">
            <label className="flex flex-col gap-1 text-small">
              <span className="text-ink-muted">Suite</span>
              <select
                value={suite}
                onChange={(event) => setSuite(event.target.value)}
                className="rounded border border-rule bg-surface px-2 py-1.5"
              >
                {SUITES.map((name) => (
                  <option key={name} value={name}>
                    {name}
                    {name === "judge" ? " (costs money)" : ""}
                  </option>
                ))}
              </select>
            </label>
            {suite !== "judge" && (
              <label className="flex flex-col gap-1 text-small">
                <span className="text-ink-muted">Retrieval mode</span>
                <select
                  value={retrievalMode}
                  onChange={(event) => setRetrievalMode(event.target.value)}
                  className="rounded border border-rule bg-surface px-2 py-1.5"
                >
                  <option value="lexical">lexical (offline)</option>
                  <option value="vector">vector (live keys)</option>
                </select>
              </label>
            )}
            {suite === "judge" && (
              <>
                <label className="flex flex-col gap-1 text-small">
                  <span className="text-ink-muted">Judge model (provider/model)</span>
                  <input
                    value={judgeModel}
                    onChange={(event) => setJudgeModel(event.target.value)}
                    placeholder="groq/openai/gpt-oss-120b"
                    className="rounded border border-rule bg-surface px-2 py-1.5"
                  />
                </label>
                <label className="flex flex-col gap-1 text-small">
                  <span className="text-ink-muted">Generation model (must differ)</span>
                  <input
                    value={genModel}
                    onChange={(event) => setGenModel(event.target.value)}
                    placeholder="human/curated"
                    className="rounded border border-rule bg-surface px-2 py-1.5"
                  />
                </label>
              </>
            )}
            {error && <p className="text-small text-alert">{error}</p>}
            <div>
              <Button onClick={startRun} disabled={busy}>
                {busy ? (
                  <>
                    <Loader2 size={14} className="animate-spin" aria-hidden /> Queueing…
                  </>
                ) : (
                  <>
                    <Play size={14} aria-hidden /> Queue run
                  </>
                )}
              </Button>
            </div>
          </Panel>
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader title="Runs" />
        <Panel className="overflow-x-auto p-0">
          <table className="w-full min-w-[480px] text-small">
            <tbody>
              {runs.map((row) => (
                <tr key={row.id} className="border-b border-rule last:border-0">
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => openRun(row.id)}
                      className="font-data text-label underline decoration-rule underline-offset-2"
                    >
                      {row.suite}
                    </button>
                  </td>
                  <td className="px-4 py-2.5">
                    <RunStatus status={row.status} />
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-ink-muted">
                    {new Date(row.created_at).toLocaleString()}
                  </td>
                  <td className="max-w-[280px] truncate px-4 py-2.5 text-ink-muted">
                    {row.error ?? ""}
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td className="px-4 py-2.5 text-ink-muted">No runs yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </Panel>
      </section>

      {detail && (
        <section className="mt-10">
          <SectionHeader title={`Run ${detail.suite} — ${detail.status}`} />
          {detailSuites(detail).map((suite: EvalSuiteReport) => (
            <div key={suite.name} className="mb-3">
              <p className="mb-1 text-small">
                <strong className="font-data">{suite.name}</strong>{" "}
                <span className="tabular-nums text-ink-muted">
                  {suite.passed}/{suite.total} passed
                  {suite.summary ? ` · ${suite.summary}` : ""}
                </span>
              </p>
              {(suite.failures ?? []).map((failure: EvalSuiteFailure) => (
                <Panel key={failure.id} className="mb-1 border-warn p-3 text-small">
                  <span className="font-data">{failure.id}</span>{" "}
                  <span className="text-ink-muted">
                    [{failure.kind}
                    {failure.code ? `/${failure.code}` : ""}]
                  </span>{" "}
                  {failure.detail}
                </Panel>
              ))}
            </div>
          ))}
          {detailSuites(detail).length === 0 && (
            <Panel className="p-4 text-small text-ink-muted">
              {detail.status === "queued" || detail.status === "running"
                ? "Still running — this list refreshes automatically."
                : (detail.error ?? "No report.")}
            </Panel>
          )}
        </section>
      )}
    </Page>
  );
}

type EvalSuiteReport = {
  name: string;
  passed: number;
  total: number;
  summary?: string;
  failures?: EvalSuiteFailure[];
};

type EvalSuiteFailure = {
  id: string;
  kind: string;
  code?: string;
  detail: string;
};

/** Report là `dict` tự do từ backend — đọc có kiểm hình, không `as` mù. */
function detailSuites(detail: EvalRunDetail): EvalSuiteReport[] {
  const report = detail.report as { suites?: unknown } | null;
  const suites = report?.suites;
  if (!Array.isArray(suites)) return [];
  return suites.filter(
    (suite): suite is EvalSuiteReport =>
      typeof suite === "object" &&
      suite !== null &&
      typeof (suite as EvalSuiteReport).name === "string",
  );
}

function RunStatus({ status }: { status: string }) {
  if (status === "done") {
    return (
      <StatusTag tone="ok" icon={CheckCircle2}>
        done
      </StatusTag>
    );
  }
  if (status === "error") {
    return (
      <StatusTag tone="alert" icon={XCircle}>
        error
      </StatusTag>
    );
  }
  return (
    <StatusTag tone="neutral" icon={FlaskConical}>
      {status}
    </StatusTag>
  );
}
