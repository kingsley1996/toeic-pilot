"use client";

import { API_ROUTES, type AiFeatureRow, type KnownModel } from "@toeic-pilot/shared";
import { KeyRound, Power } from "lucide-react";
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
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Chọn nhà cung cấp và model cho từng tính năng AI.
 *
 * Chia theo TÍNH NĂNG chứ không theo tầng rẻ/mạnh, vì hai việc khác hẳn nhau về
 * yêu cầu: gắn nhãn chạy một lần ngoài luồng và model chạy tại máy là đủ, còn
 * Coach thì học viên nhìn thấy trực tiếp. `ai_interaction.feature` đã tách sẵn
 * nên hiệu quả của từng lựa chọn đo được ngay trên sổ cái.
 */
export default function AiProvidersPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [features, setFeatures] = useState<AiFeatureRow[] | null>(null);
  const [models, setModels] = useState<KnownModel[]>([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    async function load(bearer: string) {
      const [rows, known] = await Promise.all([
        apiFetch<AiFeatureRow[]>(API_ROUTES.adminAiFeatures, { token: bearer }),
        apiFetch<KnownModel[]>(API_ROUTES.adminAiModels, { token: bearer }),
      ]);
      if (cancelled) return;
      setFeatures(rows);
      setModels(known);
    }
    load(token).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token, reloadKey]);

  async function save(feature: AiFeatureRow, provider: string, model: string, enabled: boolean) {
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
        title="AI providers"
        description="Each feature picks its own provider and model. A change here takes effect on the next call — no restart needed."
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
          {/*
           * Nói ra chỗ KHÔNG có ô nhập, vì sự vắng mặt của một ô không tự giải
           * thích: người dùng sẽ đi tìm chỗ nhập khoá và tưởng màn này chưa xong.
           */}
          <strong>API keys are never entered here, and never will be.</strong> A key field is a key
          that ends up in logs, screenshots and database backups. Keys live in{" "}
          <code className="font-data">.env</code>; this screen only picks what to use.
        </p>
      </Panel>

      <section className="mt-10">
        <SectionHeader title="Per feature" />
        <div className="space-y-3">
          {features.map((feature) => (
            <FeatureCard key={feature.key} feature={feature} models={models} onSave={save} />
          ))}
        </div>
      </section>
    </Page>
  );
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
            {/*
             * "Chưa cấu hình" KHÁC "chưa dùng được": tính năng vẫn chạy bằng
             * cấu hình từ biến môi trường. Một ô trống không nói được điều đó.
             */}
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
