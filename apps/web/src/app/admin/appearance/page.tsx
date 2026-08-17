"use client";

import { API_ROUTES, type BackdropPublic } from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import {
  Alert,
  Button,
  Field,
  Page,
  PageHeader,
  Panel,
  Select,
  Skeleton,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Backdrop controls.
 *
 * The grid itself is not configurable and deliberately so: cell size, alpha and
 * mask are calibrated against the type and the panel spacing (DESIGN-SYSTEM
 * §9.7b), and a slider over them is a slider over the readability of every page
 * behind it. What an editor gets is the three things that are a matter of taste
 * — how many beams, how many twinkles, and which colour.
 *
 * Colour is a **token name**, never a hex. Every token here ships a light value
 * and a dark one, so changing the colour cannot break the contrast promise. A
 * free hex field fails exactly where nobody looks: someone picks a colour in
 * light mode, and the same colour is invisible or glaring in dark mode, with
 * nothing to report it.
 */

const COLORS = [
  { value: "action", label: "Action (brand)" },
  { value: "ok", label: "Ok (green)" },
  { value: "warn", label: "Warn (amber)" },
  { value: "alert", label: "Alert (red)" },
  { value: "accent-us", label: "Accent US (blue)" },
  { value: "accent-uk", label: "Accent UK (violet)" },
  { value: "accent-au", label: "Accent AU (teal)" },
  { value: "accent-ca", label: "Accent CA (gold)" },
];

const MAX_SPARKS = 6;
const MAX_TWINKLES = 12;

/*
 * Speed is a percentage multiplier, not a duration in seconds.
 *
 * Each meteor has its own base cycle, deliberately co-prime with the others so
 * they never fall into a visible rhythm. A "seconds" field would flatten that —
 * the one property the effect depends on to read as ambient rather than as a
 * loop. The multiplier scales all of them and keeps the ratios.
 *
 * The floor is not arbitrary: below it a streak advances less than a pixel per
 * frame, and a thin line moving sub-pixel shimmers instead of gliding
 * (DESIGN-SYSTEM §9.7b). Slower is not calmer, it is broken.
 */
const SPEEDS = [
  { value: 50, label: "0.5x — slow" },
  { value: 75, label: "0.75x" },
  { value: 100, label: "1x — default" },
  { value: 150, label: "1.5x" },
  { value: 200, label: "2x — fast" },
  { value: 300, label: "3x — very fast" },
];

function AppearanceAdmin() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [form, setForm] = useState<BackdropPublic | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    apiFetch<BackdropPublic>(API_ROUTES.backdrop)
      .then(setForm)
      .catch(() => setError("Could not load the current settings."));
  }, []);

  async function save() {
    if (!form || !token) return;
    setSaving(true);
    setError(null);
    try {
      const next = await apiFetch<BackdropPublic>(API_ROUTES.adminBackdrop, {
        method: "PUT",
        token,
        body: JSON.stringify(form),
      });
      setForm(next);
      setSaved(true);
    } catch {
      setError("Could not save. Nothing was changed.");
    } finally {
      setSaving(false);
    }
  }

  if (status !== "authenticated" || !form) {
    return (
      <Page>
        <Skeleton className="h-9 w-64" />
        <Skeleton className="mt-6 h-64" />
      </Page>
    );
  }

  /* Any edit clears the "saved" note. Leaving it up while the form has moved on
     tells the editor their newest change is live when it is not. */
  const patch = (next: Partial<BackdropPublic>) => {
    setForm({ ...form, ...next });
    setSaved(false);
  };

  return (
    <Page>
      <PageHeader
        eyebrow="Appearance"
        title="Backdrop"
        description="The meteor backdrop behind every page except the exam runner. Changes apply to everyone, signed in or not."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <Panel className="p-5 sm:p-6">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Beams" hint={`0–${MAX_SPARKS}. Each traces one rectangle of grid edges.`}>
              <Select
                value={String(form.spark_count)}
                onChange={(event) => patch({ spark_count: Number(event.target.value) })}
              >
                {Array.from({ length: MAX_SPARKS + 1 }, (_, n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Twinkles" hint={`0–${MAX_TWINKLES}. Dots at grid intersections.`}>
              <Select
                value={String(form.twinkle_count)}
                onChange={(event) => patch({ twinkle_count: Number(event.target.value) })}
              >
                {Array.from({ length: MAX_TWINKLES + 1 }, (_, n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Colour" hint="Design-system tokens only — each has a dark variant.">
              <Select value={form.color} onChange={(event) => patch({ color: event.target.value })}>
                {COLORS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Speed" hint="Scales every cycle. Higher is faster.">
              <Select
                value={String(form.speed_percent)}
                onChange={(event) => patch({ speed_percent: Number(event.target.value) })}
              >
                {SPEEDS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>

            <Field
              label="Motion"
              hint="Off keeps the static grid and stops the beams and twinkles."
            >
              <Select
                value={form.enabled ? "on" : "off"}
                onChange={(event) => patch({ enabled: event.target.value === "on" })}
              >
                <option value="on">On</option>
                <option value="off">Off</option>
              </Select>
            </Field>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-rule pt-5">
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
            {saved && <span className="text-small text-ok">Saved — live for everyone.</span>}
          </div>

          <p className="mt-4 text-small text-ink-faint">
            Visitors with <span className="font-data">prefers-reduced-motion</span> never see the
            meteors or twinkles regardless of this setting; the static grid stays.
          </p>
        </Panel>

        {/*
         * The real backdrop is fixed behind the whole page, so it cannot be
         * previewed inside a box. This swatch shows the one thing a box CAN
         * show honestly — the colour — and says plainly that the count is not
         * previewed here. A fake mini-grid would be a second implementation of
         * the effect, and the two would drift.
         */}
        <Panel className="p-5">
          <p className="text-label font-semibold uppercase text-ink-faint">Colour</p>
          <div
            className="mt-3 h-16 rounded border border-rule"
            style={{ background: `rgb(var(--${form.color}))` }}
          />
          <p className="mt-3 text-small text-ink-muted">
            Meteors and twinkles are drawn behind the page itself — save, then look at any page to
            see the counts. This panel previews the colour only.
          </p>
          <dl className="mt-4 space-y-1.5 border-t border-rule pt-4 text-small">
            {[
              ["Meteors", form.enabled ? form.spark_count : 0],
              ["Twinkles", form.enabled ? form.twinkle_count : 0],
              ["Speed", `${form.speed_percent}%`],
            ].map(([label, value]) => (
              <div key={String(label)} className="flex justify-between">
                <dt className="text-ink-muted">{label}</dt>
                <dd className={cx("font-data tabular-nums", value === 0 && "text-ink-faint")}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>
    </Page>
  );
}

export default function AppearanceAdminPage() {
  return <AppearanceAdmin />;
}
