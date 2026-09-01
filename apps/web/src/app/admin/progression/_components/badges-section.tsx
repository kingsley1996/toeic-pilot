"use client";

import { API_ROUTES, type BadgeRuleAdmin } from "@toeic-pilot/shared";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button, Field, Input, Panel, SectionHeader, Select } from "@/components/ui";
import { type SendFn, type UploadFn, type SectionProps, ArtControl, NumberField } from "./shared";

/**
 * Mục HUY HIỆU.
 *
 * `metric` và `icon` là hai tập đóng, mỗi cái vì một lý do khác nhau: `metric`
 * ứng với một truy vấn có thật, còn `icon` thì frontend phải biết cách vẽ.
 * `code` thì là dữ liệu — đổi lại việc thêm một huy hiệu không cần triển khai.
 */

const METRICS: { value: BadgeRuleAdmin["metric"]; label: string }[] = [
  { value: "reviews", label: "Total reviews" },
  { value: "words_mastered", label: "Words mastered" },
  { value: "dictation_items", label: "Dictation sentences completed" },
  { value: "tests_submitted", label: "Tests finished" },
  { value: "best_score", label: "Best scaled score" },
  { value: "longest_streak", label: "Longest streak (days)" },
  { value: "level", label: "Level reached" },
];

const ICONS: BadgeRuleAdmin["icon"][] = [
  "footprints",
  "book",
  "library",
  "graduation",
  "headphones",
  "target",
  "medal",
  "trophy",
  "flame",
  "star",
  "sparkles",
  "award",
];

export function BadgesSection({ config, setConfig, busy, send, upload }: SectionProps) {
  const [draft, setDraft] = useState<BadgeRuleAdmin>({
    code: "",
    label: "",
    hint: "",
    icon: "star",
    image_storage_key: null,
    image_url: null,
    metric: "reviews",
    target: 10,
    position: 99,
    enabled: true,
  });

  return (
    <section className="mt-8">
      <SectionHeader
        title="Badges"
        aside={<span className="text-small text-ink-muted">{config.badges.length} rules</span>}
      />
      <Panel className="p-5 sm:p-6">
        {/* Two facts an operator needs before touching anything here, and neither is
            visible from the form itself. */}
        <p className="text-small text-ink-muted">
          Conditions are read straight from learning history, so a new badge is correct for existing
          accounts the first time it is read — no backfill. Disabling hides a badge without erasing
          who earned it; deleting keeps those rows too, so re-adding the same code does not announce
          it as new again.
        </p>

        <ul className="mt-4 space-y-2">
          {config.badges.map((badge, index) => (
            <BadgeRow
              key={badge.code}
              badge={badge}
              busy={busy}
              send={send}
              upload={upload}
              onChange={(next) => {
                const badges = [...config.badges];
                badges[index] = next;
                setConfig({ ...config, badges });
              }}
            />
          ))}
        </ul>

        <div className="mt-5 border-t border-rule pt-4">
          <p className="text-label font-semibold uppercase text-ink-faint">Add a badge</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Code" hint="Lowercase, permanent — it keys the award history.">
              <Input
                value={draft.code}
                placeholder="words_500"
                onChange={(event) => setDraft({ ...draft, code: event.target.value })}
              />
            </Field>
            <Field label="Label">
              <Input
                value={draft.label}
                placeholder="500 từ"
                onChange={(event) => setDraft({ ...draft, label: event.target.value })}
              />
            </Field>
            <Field label="Hint">
              <Input
                value={draft.hint}
                placeholder="Thuộc 500 từ"
                onChange={(event) => setDraft({ ...draft, hint: event.target.value })}
              />
            </Field>
            <Field label="Measured by">
              <Select
                value={draft.metric}
                onChange={(event) =>
                  setDraft({ ...draft, metric: event.target.value as BadgeRuleAdmin["metric"] })
                }
              >
                {METRICS.map((metric) => (
                  <option key={metric.value} value={metric.value}>
                    {metric.label}
                  </option>
                ))}
              </Select>
            </Field>
            <NumberField
              label="Threshold"
              value={draft.target}
              onChange={(target) => setDraft({ ...draft, target })}
            />
            <Field label="Icon">
              <Select
                value={draft.icon}
                onChange={(event) =>
                  setDraft({ ...draft, icon: event.target.value as BadgeRuleAdmin["icon"] })
                }
              >
                {ICONS.map((icon) => (
                  <option key={icon} value={icon}>
                    {icon}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex items-end">
              <Button
                disabled={
                  busy ||
                  draft.code.trim() === "" ||
                  draft.label.trim() === "" ||
                  draft.hint.trim() === ""
                }
                onClick={async () => {
                  await send(API_ROUTES.adminProgressionBadges, "POST", draft);
                  setDraft({ ...draft, code: "", label: "", hint: "" });
                }}
              >
                <Plus size={16} strokeWidth={2} aria-hidden />
                Add
              </Button>
            </div>
          </div>
        </div>
      </Panel>
    </section>
  );
}

function BadgeRow({
  badge,
  busy,
  send,
  upload,
  onChange,
}: {
  badge: BadgeRuleAdmin;
  busy: boolean;
  send: SendFn;
  upload: UploadFn;
  onChange: (next: BadgeRuleAdmin) => void;
}) {
  const attachArt = async (file: File) => {
    const key = await upload(file);
    if (key)
      await send(API_ROUTES.adminProgressionBadge(badge.code), "PATCH", {
        image_storage_key: key,
      });
  };
  // Hàng có KIỂM SOÁT: sự thật nằm ở bản nháp của trang, không phải ở đây.
  const form = badge;
  const setForm = onChange;

  return (
    <li className="grid items-end gap-3 rounded border border-rule-strong p-3 sm:grid-cols-2 lg:grid-cols-8">
      {/* The code is shown but never editable: it is what `user_badge.code` points
          at, so changing it strands the award history and makes the badge read as
          new again for everyone who already has it. */}
      <Field label="Code">
        <Input value={form.code} disabled />
      </Field>
      <Field label="Label">
        <Input
          value={form.label}
          onChange={(event) => setForm({ ...form, label: event.target.value })}
        />
      </Field>
      <Field label="Hint">
        <Input
          value={form.hint}
          onChange={(event) => setForm({ ...form, hint: event.target.value })}
        />
      </Field>
      <Field label="Measured by">
        <Select
          value={form.metric}
          onChange={(event) =>
            setForm({ ...form, metric: event.target.value as BadgeRuleAdmin["metric"] })
          }
        >
          {METRICS.map((metric) => (
            <option key={metric.value} value={metric.value}>
              {metric.label}
            </option>
          ))}
        </Select>
      </Field>
      <NumberField
        label="Threshold"
        value={form.target}
        onChange={(target) => setForm({ ...form, target })}
      />
      <Field label="Art">
        <ArtControl
          url={badge.image_url}
          busy={busy}
          onPick={(file) => void attachArt(file)}
          onClear={() =>
            void send(API_ROUTES.adminProgressionBadge(badge.code), "PATCH", {
              image_storage_key: null,
            })
          }
        />
      </Field>
      <Field label="Shown">
        <Select
          value={form.enabled ? "yes" : "no"}
          onChange={(event) => setForm({ ...form, enabled: event.target.value === "yes" })}
        >
          <option value="yes">Enabled</option>
          <option value="no">Hidden</option>
        </Select>
      </Field>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          disabled={busy}
          onClick={() =>
            send(API_ROUTES.adminProgressionBadge(badge.code), "PATCH", {
              label: form.label,
              hint: form.hint,
              icon: form.icon,
              metric: form.metric,
              target: form.target,
              enabled: form.enabled,
            })
          }
        >
          Save
        </Button>
        <Button
          size="sm"
          variant="quiet"
          disabled={busy}
          onClick={() => send(API_ROUTES.adminProgressionBadge(badge.code), "DELETE")}
        >
          <Trash2 size={16} strokeWidth={2} aria-hidden />
        </Button>
      </div>
    </li>
  );
}
