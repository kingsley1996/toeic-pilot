"use client";

import {
  API_ROUTES,
  type BadgeRuleAdmin,
  type DailyTaskSlotAdmin,
  type FrameTierAdmin,
  type ProgressionConfigAdmin,
} from "@toeic-pilot/shared";
import { Image as ImageIcon, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  Alert,
  Button,
  Field,
  Input,
  Page,
  PageHeader,
  Panel,
  SectionHeader,
  Select,
  Skeleton,
  Tag,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { messageFor, uploadProgressionArt } from "@/lib/upload";
import { useRequireSession } from "@/lib/session";

/**
 * Progression controls: XP rates, the daily cap, the level curve, avatar frames
 * and badge rules.
 *
 * Everything on this page used to be a constant in the API. Three properties of
 * the underlying design are what make it safe to hand over, and each one fails
 * silently if a later change gives it up:
 *
 *   · **XP is a ledger.** Every `xp_event` row stores the amount granted at the
 *     time, so lowering a rate today never claws back points somebody already
 *     earned. That is the whole reason the rates are editable at all.
 *   · **Level never drops.** `user_profile.level_reached` is a high-water mark,
 *     so raising the curve slows down new learners without taking a level away
 *     from anyone who already reached it.
 *   · **A daily task slot is a row with a stable uuid**, and that uuid is what
 *     the anti-double-award constraint keys on. Rename a slot, move its target,
 *     change its reward — the days already paid stay paid. Deleting a slot and
 *     recreating "the same" one does not: the new row is a new uuid, and every
 *     past day becomes unpaid again. Disable rather than delete.
 *
 * Every write here returns the whole configuration, so the screen replaces its
 * state with what the server actually stored instead of guessing.
 */

const KINDS: { value: DailyTaskSlotAdmin["kind"]; label: string }[] = [
  { value: "vocabulary_review", label: "Vocabulary reviews" },
  { value: "dictation_complete", label: "Dictation sentences completed" },
  { value: "attempt_answer", label: "Questions answered in a test" },
];

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

const TONES: FrameTierAdmin["tone"][] = ["ok", "action", "warn", "alert"];

/**
 * Upload art for one frame or badge, then hand the key to the row's PATCH.
 *
 * The upload and the attach are two steps on purpose: the file has to exist on
 * the provider before its key can be written, because the PATCH verifies it.
 * Doing both from one button is fine — what is not fine is writing the key
 * first and hoping, which is how a broken image ends up in the database and
 * stays there until somebody happens to look at a frame.
 */
function ArtControl({
  url,
  busy,
  onPick,
  onClear,
}: {
  url: string | null;
  busy: boolean;
  onPick: (file: File) => void;
  onClear: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center gap-2">
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt=""
          className="h-9 w-9 shrink-0 rounded border border-rule object-contain"
        />
      ) : (
        <span
          aria-hidden
          className="grid h-9 w-9 shrink-0 place-items-center rounded border border-dashed border-rule-strong text-ink-faint"
        >
          <ImageIcon size={14} strokeWidth={1.75} />
        </span>
      )}
      <input
        ref={input}
        type="file"
        accept="image/png,image/webp,image/jpeg"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onPick(file);
          // Cho phép chọn LẠI cùng một file: không xoá giá trị thì `change`
          // không bắn lần thứ hai, và nút trông như hỏng.
          event.target.value = "";
        }}
      />
      <Button size="sm" variant="secondary" disabled={busy} onClick={() => input.current?.click()}>
        {url ? "Replace" : "Upload"}
      </Button>
      {url && (
        <Button size="sm" variant="quiet" disabled={busy} onClick={onClear}>
          Clear
        </Button>
      )}
    </div>
  );
}

/** A row of small labelled number inputs. */
function NumberField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <Field label={label} hint={hint}>
      <Input
        type="number"
        value={String(value)}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </Field>
  );
}

export default function ProgressionAdminPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  /*
   * MỘT bản nháp cho cả trang, không phải một bản sao trong mỗi hàng.
   *
   * Mỗi hàng giữ state riêng thì phải đồng bộ lại mỗi khi máy chủ trả về cấu
   * hình mới, và cách duy nhất để làm điều đó là `setState` trong một effect —
   * thứ mà `react-hooks/set-state-in-effect` cấm, vì nó xếp tầng render và trôi
   * khỏi dữ liệu nó mô tả. Ở đây các hàng là component có kiểm soát: chúng chỉ
   * nhận `value` và `onChange`, còn sự thật thì nằm một chỗ.
   */
  const [config, setConfig] = useState<ProgressionConfigAdmin | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    apiFetch<ProgressionConfigAdmin>(API_ROUTES.adminProgression, { token })
      .then(setConfig)
      .catch(() => setError("Could not load the configuration."));
  }, [token]);

  /**
   * Every mutation goes through here.
   *
   * `await` is on its own line on purpose: `done?.(await work())` short-circuits
   * the *whole* call expression when `done` is nullish, so the work never runs
   * and the caller is told it succeeded. That cost this project a long hunt once
   * already (CLAUDE.md).
   */
  async function send(path: string, method: string, body?: unknown) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const next = await apiFetch<ProgressionConfigAdmin>(path, {
        method,
        token,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      setConfig(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  /** Tải một file lên, trả về khoá — hoặc `null` nếu hỏng (lỗi đã hiện ra). */
  async function upload(file: File): Promise<string | null> {
    if (!token) return null;
    setBusy(true);
    setError(null);
    try {
      // `await` trên dòng riêng, không nhét vào tham số của một lời gọi tuỳ chọn.
      const key = await uploadProgressionArt(file, token);
      return key;
    } catch (caught) {
      setError(messageFor(caught, "Could not upload the image."));
      return null;
    } finally {
      setBusy(false);
    }
  }

  if (status !== "authenticated" || !config) {
    return (
      <Page>
        <Skeleton className="h-9 w-64" />
        <Skeleton className="mt-6 h-64" />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Progression"
        title="XP, levels and badges"
        description="Applies to every learner from now on. Points already awarded are never recalculated, and nobody loses a level they have reached."
        actions={
          <>
            {/* Khung là thứ DUY NHẤT ở trang này không kiểm được bằng số liệu:
                tranh tràn ra ngoài ô 25% mỗi phía, nên phải nhìn. */}
            <Link
              href="/admin/progression/preview"
              className="text-small font-semibold text-ink-muted hover:text-ink"
            >
              Frame preview
            </Link>
            <Tag tone="warn">Admin only</Tag>
          </>
        }
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <RatesSection config={config} setConfig={setConfig} busy={busy} send={send} upload={upload} />
      <CurveSection config={config} setConfig={setConfig} busy={busy} send={send} upload={upload} />
      <SlotsSection config={config} setConfig={setConfig} busy={busy} send={send} upload={upload} />
      <FramesSection
        config={config}
        setConfig={setConfig}
        busy={busy}
        send={send}
        upload={upload}
      />
      <BadgesSection
        config={config}
        setConfig={setConfig}
        busy={busy}
        send={send}
        upload={upload}
      />
    </Page>
  );
}

type SendFn = (path: string, method: string, body?: unknown) => Promise<void>;
type UploadFn = (file: File) => Promise<string | null>;
type SectionProps = {
  config: ProgressionConfigAdmin;
  setConfig: (next: ProgressionConfigAdmin) => void;
  busy: boolean;
  send: SendFn;
  upload: UploadFn;
};

function RatesSection({ config, setConfig, busy, send }: SectionProps) {
  const form = config.setting;
  const patch = (next: Partial<typeof form>) =>
    setConfig({ ...config, setting: { ...form, ...next } });

  return (
    <section className="mt-8">
      <SectionHeader title="XP rates and daily cap" />
      <Panel className="p-5 sm:p-6">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <NumberField
            label="Per review"
            hint="Every SM-2 review, any grade."
            value={form.xp_vocabulary_review}
            onChange={(xp_vocabulary_review) => patch({ xp_vocabulary_review })}
          />
          <NumberField
            label="Per dictation sentence"
            hint="Only when the sentence is fully correct."
            value={form.xp_dictation_complete}
            onChange={(xp_dictation_complete) => patch({ xp_dictation_complete })}
          />
          <NumberField
            label="Per test submitted"
            hint="Abandoned attempts pay nothing."
            value={form.xp_attempt_submit}
            onChange={(xp_attempt_submit) => patch({ xp_attempt_submit })}
          />
          <NumberField
            label="Daily cap"
            hint="Trims the last award instead of dropping it. Learning itself is never blocked."
            value={form.daily_xp_cap}
            onChange={(daily_xp_cap) => patch({ daily_xp_cap })}
          />
        </div>
        <div className="mt-5 flex items-center gap-3 border-t border-rule pt-4">
          <Button
            disabled={busy}
            onClick={() =>
              send(API_ROUTES.adminProgressionSetting, "PATCH", {
                xp_vocabulary_review: form.xp_vocabulary_review,
                xp_dictation_complete: form.xp_dictation_complete,
                xp_attempt_submit: form.xp_attempt_submit,
                daily_xp_cap: form.daily_xp_cap,
              })
            }
          >
            Save rates
          </Button>
          <p className="text-small text-ink-muted">
            Past awards keep the amount they were granted with — the ledger is never recalculated.
          </p>
        </div>
      </Panel>
    </section>
  );
}

function CurveSection({ config, setConfig, busy, send }: SectionProps) {
  const form = config.setting;
  const levels = config.levels;
  const setForm = (next: typeof form) => setConfig({ ...config, setting: next });
  const setLevels = (next: typeof levels) => setConfig({ ...config, levels: next });

  return (
    <section className="mt-8">
      <SectionHeader
        title="Level curve"
        aside={<span className="text-small text-ink-muted">{levels.length} levels</span>}
      />
      <Panel className="p-5 sm:p-6">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
          <NumberField
            label="Coefficient"
            value={form.curve_coefficient}
            onChange={(curve_coefficient) => setForm({ ...form, curve_coefficient })}
          />
          <NumberField
            label="Exponent"
            value={form.curve_exponent}
            onChange={(curve_exponent) => setForm({ ...form, curve_exponent })}
          />
          <NumberField
            label="Linear from level"
            value={form.curve_break}
            onChange={(curve_break) => setForm({ ...form, curve_break })}
          />
          <NumberField
            label="Linear step"
            value={form.curve_linear_step}
            onChange={(curve_linear_step) => setForm({ ...form, curve_linear_step })}
          />
          <NumberField
            label="Max level"
            value={form.max_level}
            onChange={(max_level) => setForm({ ...form, max_level })}
          />
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-rule pt-4">
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() =>
              send(API_ROUTES.adminProgressionSetting, "PATCH", {
                curve_coefficient: form.curve_coefficient,
                curve_exponent: form.curve_exponent,
                curve_break: form.curve_break,
                curve_linear_step: form.curve_linear_step,
                max_level: form.max_level,
              })
            }
          >
            Save parameters
          </Button>
          <Button
            disabled={busy}
            onClick={() => send(API_ROUTES.adminProgressionLevelsGenerate, "POST")}
          >
            Regenerate table
          </Button>
          {/* Said before the click, not discovered after it: the generator is the
              only control on this page that destroys work rather than adding to it. */}
          <p className="text-small text-warn">
            Regenerating overwrites every threshold below, including ones edited by hand.
          </p>
        </div>

        <div className="mt-5 max-h-80 overflow-y-auto border-t border-rule pt-4">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {levels.map((tier, index) => (
              <label key={tier.level} className="flex items-center gap-2">
                <span className="w-16 shrink-0 text-small text-ink-muted">Level {tier.level}</span>
                <Input
                  type="number"
                  value={String(tier.xp_required)}
                  disabled={tier.level === 1}
                  onChange={(event) => {
                    const next = [...levels];
                    next[index] = { ...tier, xp_required: Number(event.target.value) };
                    setLevels(next);
                  }}
                />
              </label>
            ))}
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3 border-t border-rule pt-4">
          <Button
            disabled={busy}
            onClick={() => send(API_ROUTES.adminProgressionLevels, "PUT", { tiers: levels })}
          >
            Save thresholds
          </Button>
          {/* The table is validated as a block — level 1 at 0 XP, no gaps, strictly
              climbing — because a table that dips makes the lookup stop at the wrong
              level, and `level_reached` would record that wrong level permanently. */}
          <p className="text-small text-ink-muted">
            Thresholds must climb with no gaps. Level 1 is always 0.
          </p>
        </div>
      </Panel>
    </section>
  );
}

function SlotsSection({ config, setConfig, busy, send }: SectionProps) {
  const [draft, setDraft] = useState<{
    kind: DailyTaskSlotAdmin["kind"];
    label: string;
    target: number;
    xp: number;
  }>({ kind: "vocabulary_review", label: "", target: 10, xp: 10 });

  return (
    <section className="mt-8">
      <SectionHeader title="Daily tasks" />
      <Panel className="p-5 sm:p-6">
        {/* The trap §6.2 of USER-ROAD names, stated where the number is typed:
            targets take effect immediately, so raising one at 2pm reopens a task
            somebody finished at 9am. The XP is not re-granted — the ledger's unique
            constraint sees to that — but their bar goes backwards. */}
        <p className="text-small text-ink-muted">
          Changes apply immediately, including mid-day. Raising a target reopens a task a learner
          already finished today; XP already granted is never taken back.
        </p>

        <ul className="mt-4 space-y-2">
          {config.slots.map((slot, index) => (
            <SlotRow
              key={slot.id}
              slot={slot}
              busy={busy}
              send={send}
              onChange={(next) => {
                const slots = [...config.slots];
                slots[index] = next;
                setConfig({ ...config, slots });
              }}
            />
          ))}
        </ul>

        <div className="mt-5 border-t border-rule pt-4">
          <p className="text-label font-semibold uppercase text-ink-faint">Add a task</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Field label="Measured by">
              <Select
                value={draft.kind}
                onChange={(event) =>
                  setDraft({ ...draft, kind: event.target.value as DailyTaskSlotAdmin["kind"] })
                }
              >
                {KINDS.map((kind) => (
                  <option key={kind.value} value={kind.value}>
                    {kind.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Label (shown to learners)">
              <Input
                value={draft.label}
                placeholder="Ôn từ vựng"
                onChange={(event) => setDraft({ ...draft, label: event.target.value })}
              />
            </Field>
            <NumberField
              label="Target"
              value={draft.target}
              onChange={(target) => setDraft({ ...draft, target })}
            />
            <NumberField
              label="XP"
              value={draft.xp}
              onChange={(xp) => setDraft({ ...draft, xp })}
            />
            <div className="flex items-end">
              <Button
                disabled={busy || draft.label.trim() === ""}
                onClick={async () => {
                  await send(API_ROUTES.adminProgressionSlots, "POST", {
                    ...draft,
                    position: config.slots.length + 1,
                  });
                  setDraft({ ...draft, label: "" });
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

function SlotRow({
  slot,
  busy,
  send,
  onChange,
}: {
  slot: DailyTaskSlotAdmin;
  busy: boolean;
  send: SendFn;
  onChange: (next: DailyTaskSlotAdmin) => void;
}) {
  // Hàng có KIỂM SOÁT: sự thật nằm ở bản nháp của trang, không phải ở đây.
  const form = slot;
  const setForm = onChange;

  return (
    <li className="grid items-end gap-3 rounded border border-rule-strong p-3 sm:grid-cols-2 lg:grid-cols-6">
      <Field label="Measured by">
        <Select
          value={form.kind}
          onChange={(event) =>
            setForm({ ...form, kind: event.target.value as DailyTaskSlotAdmin["kind"] })
          }
        >
          {KINDS.map((kind) => (
            <option key={kind.value} value={kind.value}>
              {kind.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Label">
        <Input
          value={form.label}
          onChange={(event) => setForm({ ...form, label: event.target.value })}
        />
      </Field>
      <NumberField
        label="Target"
        value={form.target}
        onChange={(target) => setForm({ ...form, target })}
      />
      <NumberField label="XP" value={form.xp} onChange={(xp) => setForm({ ...form, xp })} />
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
            send(API_ROUTES.adminProgressionSlot(slot.id), "PATCH", {
              kind: form.kind,
              label: form.label,
              target: form.target,
              xp: form.xp,
              enabled: form.enabled,
            })
          }
        >
          Save
        </Button>
        {/* Delete is last and quiet: disabling keeps the uuid, and the uuid is what
            stops a day being paid twice. */}
        <Button
          size="sm"
          variant="quiet"
          disabled={busy}
          onClick={() => send(API_ROUTES.adminProgressionSlot(slot.id), "DELETE")}
          title="Deleting loses the anti-double-award key. Prefer Hidden."
        >
          <Trash2 size={16} strokeWidth={2} aria-hidden />
        </Button>
      </div>
    </li>
  );
}

function FramesSection({ config, setConfig, busy, send, upload }: SectionProps) {
  const [draft, setDraft] = useState<FrameTierAdmin>({
    code: "",
    label: "",
    min_level: 40,
    tone: "action",
    ring: false,
    // Tranh gắn SAU khi tạo, không phải lúc tạo: file phải tồn tại trên kho
    // trước khi khoá được ghi, nên đính kèm ngay trong biểu mẫu tạo sẽ là hai
    // thao tác mạng cột vào một nút và một nửa thất bại không có đường lùi.
    image_storage_key: null,
    image_url: null,
  });

  return (
    <section className="mt-8">
      <SectionHeader title="Avatar frames" />
      <Panel className="p-5 sm:p-6">
        <p className="text-small text-ink-muted">
          Purely decorative. Colours are design-system tokens, never hex — every token ships a dark
          variant, so a frame cannot become invisible in one theme.
        </p>

        <ul className="mt-4 space-y-2">
          {config.frames.map((frame, index) => (
            <FrameRow
              key={frame.code}
              frame={frame}
              busy={busy}
              send={send}
              upload={upload}
              onChange={(next) => {
                const frames = [...config.frames];
                frames[index] = next;
                setConfig({ ...config, frames });
              }}
            />
          ))}
        </ul>

        <div className="mt-5 border-t border-rule pt-4">
          <p className="text-label font-semibold uppercase text-ink-faint">Add a tier</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Field label="Code" hint="Lowercase, permanent.">
              <Input
                value={draft.code}
                placeholder="diamond"
                onChange={(event) => setDraft({ ...draft, code: event.target.value })}
              />
            </Field>
            <Field label="Label">
              <Input
                value={draft.label}
                placeholder="Kim cương"
                onChange={(event) => setDraft({ ...draft, label: event.target.value })}
              />
            </Field>
            <NumberField
              label="From level"
              value={draft.min_level}
              onChange={(min_level) => setDraft({ ...draft, min_level })}
            />
            <Field label="Tone">
              <Select
                value={draft.tone}
                onChange={(event) =>
                  setDraft({ ...draft, tone: event.target.value as FrameTierAdmin["tone"] })
                }
              >
                {TONES.map((tone) => (
                  <option key={tone} value={tone}>
                    {tone}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex items-end">
              <Button
                disabled={busy || draft.code.trim() === "" || draft.label.trim() === ""}
                onClick={async () => {
                  await send(API_ROUTES.adminProgressionFrames, "POST", draft);
                  setDraft({ ...draft, code: "", label: "" });
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

function FrameRow({
  frame,
  busy,
  send,
  upload,
  onChange,
}: {
  frame: FrameTierAdmin;
  busy: boolean;
  send: SendFn;
  upload: UploadFn;
  onChange: (next: FrameTierAdmin) => void;
}) {
  const attachArt = async (file: File) => {
    const key = await upload(file);
    if (key)
      await send(API_ROUTES.adminProgressionFrame(frame.code), "PATCH", {
        image_storage_key: key,
      });
  };
  // Hàng có KIỂM SOÁT: sự thật nằm ở bản nháp của trang, không phải ở đây.
  const form = frame;
  const setForm = onChange;

  return (
    <li className="grid items-end gap-3 rounded border border-rule-strong p-3 sm:grid-cols-2 lg:grid-cols-7">
      <Field label="Code">
        <Input value={form.code} disabled />
      </Field>
      <Field label="Label">
        <Input
          value={form.label}
          onChange={(event) => setForm({ ...form, label: event.target.value })}
        />
      </Field>
      <NumberField
        label="From level"
        value={form.min_level}
        onChange={(min_level) => setForm({ ...form, min_level })}
      />
      <Field label="Tone">
        <Select
          value={form.tone}
          onChange={(event) =>
            setForm({ ...form, tone: event.target.value as FrameTierAdmin["tone"] })
          }
        >
          {TONES.map((tone) => (
            <option key={tone} value={tone}>
              {tone}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Art">
        <ArtControl
          url={frame.image_url}
          busy={busy}
          onPick={(file) => void attachArt(file)}
          onClear={() =>
            void send(API_ROUTES.adminProgressionFrame(frame.code), "PATCH", {
              image_storage_key: null,
            })
          }
        />
      </Field>
      <Field label="Outer ring">
        <Select
          value={form.ring ? "yes" : "no"}
          onChange={(event) => setForm({ ...form, ring: event.target.value === "yes" })}
        >
          <option value="no">No</option>
          <option value="yes">Yes</option>
        </Select>
      </Field>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          disabled={busy}
          onClick={() =>
            send(API_ROUTES.adminProgressionFrame(frame.code), "PATCH", {
              label: form.label,
              min_level: form.min_level,
              tone: form.tone,
              ring: form.ring,
            })
          }
        >
          Save
        </Button>
        <Button
          size="sm"
          variant="quiet"
          disabled={busy}
          onClick={() => send(API_ROUTES.adminProgressionFrame(frame.code), "DELETE")}
        >
          <Trash2 size={16} strokeWidth={2} aria-hidden />
        </Button>
      </div>
    </li>
  );
}

function BadgesSection({ config, setConfig, busy, send, upload }: SectionProps) {
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
