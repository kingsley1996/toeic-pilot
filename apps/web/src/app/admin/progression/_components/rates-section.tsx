"use client";

import { API_ROUTES } from "@toeic-pilot/shared";

import { Button, Panel, SectionHeader } from "@/components/ui";
import { type SectionProps, NumberField } from "./shared";

/** Mục ĐIỂM XP: mức thưởng mỗi hoạt động và trần mỗi ngày. */

export function RatesSection({ config, setConfig, busy, send }: SectionProps) {
  const form = config.setting;
  const patch = (next: Partial<typeof form>) =>
    setConfig({ ...config, setting: { ...form, ...next } });

  return (
    <section className="mt-8">
      <SectionHeader title="XP rates and daily cap" />
      <Panel className="p-5 sm:p-6">
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
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
            label="Per grammar question"
            hint="Correct only, once per question ever."
            value={form.xp_grammar_attempt}
            onChange={(xp_grammar_attempt) => patch({ xp_grammar_attempt })}
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
                xp_grammar_attempt: form.xp_grammar_attempt,
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
