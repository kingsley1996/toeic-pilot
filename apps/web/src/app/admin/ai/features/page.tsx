"use client";

import {
  API_ROUTES,
  type AiFeatureRow,
  type KnownModel,
  type ModelTaskRow,
} from "@toeic-pilot/shared";
import { Power } from "lucide-react";
import { useEffect, useState } from "react";

import {
  Alert,
  Button,
  Page,
  PageHeader,
  Panel,
  SectionHeader,
  Select,
  SkeletonList,
  Tag,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

const TASKS = ["exam_plan", "exam_write", "exam_verify", "exam_ambiguity", "coach_chat", "assistant_chat"];

/**
 * Chọn model cho từng tính năng AI, và so sánh model theo task.
 *
 * Provider là chuyện của `/admin/ai/providers` (khoá, kết nối, giá). Trang này
 * chỉ trả lời một câu: task nào dùng model nào — và model nào đang làm tốt nhất
 * mỗi task (từ sổ cái ai_interaction).
 */
export default function AiFeaturesPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [features, setFeatures] = useState<AiFeatureRow[] | null>(null);
  const [models, setModels] = useState<KnownModel[]>([]);
  const [stats, setStats] = useState<ModelTaskRow[] | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function load(bearer: string) {
      const [featRows, known, taskStats] = await Promise.all([
        apiFetch<AiFeatureRow[]>(API_ROUTES.adminAiFeatures, { token: bearer }),
        apiFetch<KnownModel[]>(API_ROUTES.adminAiModels, { token: bearer }),
        apiFetch<ModelTaskRow[]>(API_ROUTES.adminAiStatsModels, { token: bearer }),
      ]);
      if (cancelled) return;
      setFeatures(featRows);
      setModels(known);
      setStats(taskStats);
    }
    load(token).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token, reloadKey]);

  async function saveFeature(
    feature: AiFeatureRow,
    provider: string,
    model: string,
    enabled: boolean,
  ) {
    if (!token) return;
    setError(null);
    setNotice(null);
    try {
      await apiFetch<AiFeatureRow>(API_ROUTES.adminAiFeature(feature.key), {
        method: "PUT",
        token,
        body: JSON.stringify({ provider, model, enabled }),
      });
      setNotice(`Saved configuration for “${feature.label_vi}”. The next call uses it.`);
      setReloadKey((key) => key + 1);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save");
    }
  }

  if (status === "loading" || features === null) {
    return (
      <Page>
        <SkeletonList rows={5} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        title="AI model picker"
        description="Which model each AI task uses, and how each model has performed per task."
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

      <section>
        <SectionHeader
          title="Per feature"
          aside={
            <span className="font-data text-label text-ink-faint">
              choose which model each AI task uses
            </span>
          }
        />
        <div className="space-y-3">
          {features.map((feature) => (
            <FeatureCard key={feature.key} feature={feature} models={models} onSave={saveFeature} />
          ))}
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader
          title="Model comparison per task"
          aside={
            stats && stats.length > 0 ? (
              <span className="font-data text-label text-ink-faint">
                {stats.length} (provider, model, task) rows
              </span>
            ) : (
              <span className="font-data text-label text-ink-faint">
                no calls yet — run the pipeline to see numbers
              </span>
            )
          }
        />
        {stats && stats.length > 0 ? (
          <div className="overflow-x-auto rounded border border-rule">
            <table className="w-full text-small">
              <thead>
                <tr className="border-b border-rule bg-recess text-left text-label uppercase text-ink-muted">
                  <th className="px-3 py-2">provider / model</th>
                  {TASKS.map((task) => (
                    <th key={task} className="px-3 py-2 text-right">
                      {task}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {modelsWithData(stats).map((key) => (
                  <tr key={key} className="hover:bg-recess">
                    <td className="whitespace-nowrap px-3 py-2 font-data">{key}</td>
                    {TASKS.map((task) => {
                      const row = stats.find(
                        (r) => `${r.provider}/${r.model}` === key && r.feature === task,
                      );
                      return (
                        <td key={task} className="px-3 py-2 text-right align-top">
                          {row && row.calls > 0 ? (
                            <span className="flex flex-col items-end gap-0.5">
                              <span
                                className={cx(
                                  "font-data tabular-nums",
                                  row.success_rate === 0 && "text-alert",
                                )}
                              >
                                {Math.round(row.success_rate * 100)}%
                              </span>
                              <span className="text-label text-ink-faint">
                                {row.calls} calls · p50 {row.latency_p50_ms ?? "—"}ms
                              </span>
                            </span>
                          ) : (
                            <span className="text-label text-ink-faint">—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Panel className="p-6 text-small text-ink-muted">
            Chưa có lượt gọi nào trong sổ cái <code className="font-data">ai_interaction</code>.
            Chạy pipeline (plan / write / check) rồi quay lại — mỗi lượt gọi sẽ ghi một hàng so
            sánh được.
          </Panel>
        )}
      </section>
    </Page>
  );
}

function modelsWithData(stats: ModelTaskRow[]): string[] {
  return [...new Set(stats.map((r) => `${r.provider}/${r.model}`))].sort();
}

function FeatureCard({
  feature,
  models,
  onSave,
}: {
  feature: AiFeatureRow;
  models: KnownModel[];
  onSave: (f: AiFeatureRow, provider: string, model: string, enabled: boolean) => Promise<void>;
}) {
  const [picked, setPicked] = useState(
    feature.provider && feature.model ? `${feature.provider}|${feature.model}` : "",
  );
  const [provider, model] = picked.split("|");

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{feature.label_vi}</span>
            <span className="font-data text-label text-ink-faint">{feature.key}</span>
            {!feature.enabled && <Tag tone="alert">disabled</Tag>}
            {!feature.configured && <Tag>from environment</Tag>}
          </div>
          <p className="mt-1 max-w-2xl text-small text-ink-muted">{feature.description_vi}</p>
          {feature.updated_by && (
            <p className="mt-1 font-data text-label text-ink-faint">
              last changed by {feature.updated_by}
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-rule pt-3">
        <Select
          className="w-auto min-w-[18rem]"
          value={picked}
          onChange={(event) => setPicked(event.target.value)}
          aria-label={`Model for ${feature.label_vi}`}
        >
          <option value="" disabled>
            pick a model
          </option>
          {models.map((known) => (
            <option
              key={`${known.provider}|${known.model}`}
              value={`${known.provider}|${known.model}`}
            >
              {known.provider} / {known.model}
            </option>
          ))}
        </Select>
        <Button
          size="sm"
          disabled={!provider || !model}
          onClick={() => void onSave(feature, provider, model, feature.enabled)}
        >
          Save
        </Button>
        <Button
          size="sm"
          variant={feature.enabled ? "destructive" : "secondary"}
          disabled={!feature.provider || !feature.model}
          onClick={() =>
            void onSave(
              feature,
              feature.provider as string,
              feature.model as string,
              !feature.enabled,
            )
          }
        >
          <Power size={14} strokeWidth={1.75} aria-hidden />
          {feature.enabled ? "Disable" : "Enable"}
        </Button>
      </div>
    </Panel>
  );
}
