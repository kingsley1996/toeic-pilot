"use client";

import { API_ROUTES, type DailyTaskSlotAdmin } from "@toeic-pilot/shared";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button, Field, Input, Panel, SectionHeader, Select } from "@/components/ui";
import { type SendFn, type SectionProps, NumberField } from "./shared";

/**
 * Mục VIỆC HÔM NAY.
 *
 * Nút có ở đây là *tắt*, không phải *xoá*: mỗi ô là một hàng có uuid bền, và
 * uuid ấy là thứ `xp_event.source_id` khoá vào. Xoá rồi tạo lại "cùng một ô"
 * là một uuid mới, và mọi ngày đã trả công thành chưa trả.
 */

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
  { value: "grammar_lesson_complete", label: "Grammar lessons completed" },
];

export function SlotsSection({ config, setConfig, busy, send }: SectionProps) {
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
