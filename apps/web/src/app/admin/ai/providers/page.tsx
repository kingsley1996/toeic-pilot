"use client";

import { API_ROUTES, type ProviderDetail, type TestConnectionResult } from "@toeic-pilot/shared";
import { Check, CircleSlash, FlaskConical, Globe, KeyRound } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, Page, PageHeader, Panel, SkeletonList, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Quản lý provider & model tầng AI: kết nối còn chạy không, khoá đặt chưa.
 *
 * Chọn model cho từng tính năng nằm ở `/admin/ai/features`; trang này chỉ nói
 * về provider: có những provider nào, base_url, giá model, khoá đặt chưa, và
 * test kết nối thật từng model.
 *
 * Khoá KHÔNG bao giờ nằm ở đây — chỉ trạng thái "đã đặt / chưa" mới hiển thị.
 */
export default function AiProvidersPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [providers, setProviders] = useState<ProviderDetail[] | null>(null);
  const [results, setResults] = useState<TestConnectionResult[] | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function load(bearer: string) {
      const next = await apiFetch<ProviderDetail[]>(API_ROUTES.adminAiProviders, { token: bearer });
      if (!cancelled) setProviders(next);
    }
    load(token).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function testAll() {
    if (!token || testing) return;
    setTesting(true);
    setError(null);
    setNotice(null);
    try {
      const rows = await apiFetch<TestConnectionResult[]>(API_ROUTES.adminAiTestConnection, {
        method: "POST",
        token,
      });
      setResults(rows);
      setNotice(`${rows.filter((r) => r.ok).length}/${rows.length} models reachable.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không test được kết nối");
    } finally {
      setTesting(false);
    }
  }

  if (status === "loading" || providers === null) {
    return (
      <Page>
        <SkeletonList rows={5} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="AI providers"
        description="Providers available, per-model prices, key status, and live connection test."
        actions={
          <button
            type="button"
            onClick={() => void testAll()}
            disabled={testing}
            className="inline-flex h-9 items-center gap-2 rounded border border-rule-strong bg-panel px-3.5 text-body font-semibold transition-colors hover:bg-recess disabled:opacity-45"
          >
            <FlaskConical size={15} strokeWidth={2} aria-hidden />
            {testing ? "Đang test…" : "Test all connections"}
          </button>
        }
      />

      {notice && (
        <div className="mb-6">
          <Alert tone="ok">{notice}</Alert>
        </div>
      )}
      {error && (
        <div className="mb-6">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      <Panel className="flex items-start gap-2.5 p-4">
        <KeyRound size={16} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
        <p className="text-small">
          <strong>API keys are never shown here, and never will be.</strong> A key field is a key
          that ends up in logs, screenshots and backups. Keys live in{" "}
          <code className="font-data">.env</code>; this screen only reports whether one is set.
        </p>
      </Panel>

      <section className="mt-10">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="text-h4">Providers</h2>
          <span className="font-data text-label text-ink-faint">{providers.length} configured</span>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {providers.map((provider) => (
            <ProviderCard key={provider.provider} provider={provider} testResults={results} />
          ))}
        </div>
      </section>
    </Page>
  );
}

function ProviderCard({
  provider,
  testResults,
}: {
  provider: ProviderDetail;
  testResults: TestConnectionResult[] | null;
}) {
  const matching = testResults?.filter((r) => r.provider === provider.provider) ?? [];
  const anyOk = matching.some((r) => r.ok);
  const anyFail = matching.some((r) => !r.ok);

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold">{provider.provider}</span>
          <Tag tone={provider.key_configured ? "ok" : "alert"}>
            {provider.key_configured ? "key set" : "missing key"}
          </Tag>
          {matching.length > 0 && (
            <Tag tone={anyFail ? "alert" : "ok"}>
              {anyOk ? `${matching.filter((r) => r.ok).length} ok` : "all fail"}
            </Tag>
          )}
        </div>
        {provider.base_url && (
          <span className="flex items-center gap-1.5 text-label text-ink-faint">
            <Globe size={13} strokeWidth={2} aria-hidden />
            {provider.base_url}
          </span>
        )}
      </div>

      <div className="mt-3 space-y-1.5 border-t border-rule pt-3">
        {(provider.models ?? []).map((model) => {
          const test = matching.find((r) => r.model === model.model);
          return (
            <div key={model.model} className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="font-data text-small">{model.model}</p>
                {model.comment && (
                  <p className="truncate text-label text-ink-faint">{model.comment}</p>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="font-data text-label tabular-nums text-ink-faint">
                  {formatUsd(model.rate_in)} / {formatUsd(model.rate_out)} per 1M
                </span>
                {test &&
                  (test.ok ? (
                    <span className="flex items-center gap-1 text-small text-ok">
                      <Check size={14} strokeWidth={2} aria-hidden />
                      {test.latency_ms}ms
                    </span>
                  ) : (
                    <span
                      className="flex items-center gap-1 text-small text-alert"
                      title={test.error ?? ""}
                    >
                      <CircleSlash size={14} strokeWidth={2} aria-hidden />
                      fail
                    </span>
                  ))}
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function formatUsd(value: number | string | null | undefined): string {
  const amount = Number(value ?? 0);
  if (Number.isNaN(amount)) return "—";
  if (amount === 0) return "free";
  if (amount >= 1) return `$${amount}`;
  return `$${amount.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}`;
}
