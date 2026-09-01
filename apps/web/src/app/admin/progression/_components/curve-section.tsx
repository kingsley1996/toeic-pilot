"use client";

import { API_ROUTES } from "@toeic-pilot/shared";

import { Button, Input, Panel, SectionHeader } from "@/components/ui";
import { type SectionProps, NumberField } from "./shared";

/**
 * Mục ĐƯỜNG CONG CẤP.
 *
 * Bảng cấp được kiểm theo KHỐI ở máy chủ — cấp 1 tại 0 XP, không hụt bậc, tăng
 * nghiêm ngặt — vì một bảng đi xuống làm phép tra dừng ở sai cấp, mà
 * `level_reached` chỉ tăng nên một dấu sai ghi trong khoảng đó là vĩnh viễn.
 */

export function CurveSection({ config, setConfig, busy, send }: SectionProps) {
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
