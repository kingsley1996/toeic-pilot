"use client";

import { API_ROUTES, type RubyRulePublic } from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import { Alert, Button, Input, Page, PageHeader, Panel, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Ruby earning rates (ADR-011 §6).
 *
 * Every number in the ruby economy is a row, same shape as `/admin/progression`
 * and `/admin/pet`. What makes handing this over safe is the ledger: each
 * `ruby_event` stores the amount granted at the time, so lowering a rate today
 * never claws back what anyone already earned.
 *
 * There is no "add a source" button, and that is the boundary between data and
 * code: every source type is a real query in the backend (a story finished, a
 * topic mastered, a test submitted), so a made-up code would be a row that can
 * never be granted. Disable instead of deleting — an empty table means "never
 * configured", and the defaults seed themselves back on the next read.
 */
export default function RubyRulesAdminPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [rows, setRows] = useState<RubyRulePublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<RubyRulePublic[]>(API_ROUTES.adminRubyRules, { token })
      .then(setRows)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load the ruby rules."),
      );
  }, [token]);

  const patch = (sourceType: string, changes: Partial<RubyRulePublic>) => {
    if (!token) return;
    setError(null);
    // Send only the field that changed. `PATCH` tells an absent key from a null
    // one, so posting the whole row turns a label edit into an overwrite — and a
    // stale row in state would quietly restore old values.
    void apiFetch<RubyRulePublic>(API_ROUTES.adminRubyRule(sourceType), {
      method: "PATCH",
      token,
      body: JSON.stringify(changes),
    })
      .then((updated) =>
        setRows((current) =>
          (current ?? []).map((row) => (row.source_type === sourceType ? updated : row)),
        ),
      )
      .catch((err) => setError(err instanceof ApiError ? err.message : "Save failed."));
  };

  if (status !== "authenticated") {
    return (
      <Page>
        <PageHeader eyebrow="Ruby" title="Earning rates" />
      </Page>
    );
  }

  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Ruby"
        title="Earning rates"
        description="Ruby pays for finishing something, never per review. Changing a rate takes effect on the next grant and never touches what was already earned."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <div className="grid gap-2">
        {rows?.map((row) => (
          <Panel
            key={row.source_type}
            className={cx("flex flex-wrap items-center gap-3 p-3", !row.enabled && "opacity-60")}
          >
            <span className="w-40 shrink-0 font-data text-small text-ink-faint">
              {row.source_type}
            </span>

            <Input
              defaultValue={row.label}
              aria-label={`Label for ${row.source_type}`}
              className="w-56"
              onBlur={(event) => {
                const next = event.target.value.trim();
                if (next && next !== row.label) patch(row.source_type, { label: next });
              }}
            />

            <label className="flex items-center gap-1.5 text-small text-ink-muted">
              Ruby
              <Input
                type="number"
                min={1}
                max={1000}
                defaultValue={row.amount}
                aria-label={`Amount for ${row.source_type}`}
                className="w-24"
                onBlur={(event) => {
                  const next = Number(event.target.value);
                  if (Number.isInteger(next) && next > 0 && next !== row.amount) {
                    patch(row.source_type, { amount: next });
                  }
                }}
              />
            </label>

            <Button
              size="sm"
              variant={row.enabled ? "secondary" : "primary"}
              className="ml-auto"
              onClick={() => patch(row.source_type, { enabled: !row.enabled })}
            >
              {row.enabled ? "Disable" : "Enable"}
            </Button>
          </Panel>
        ))}
      </div>

      <p className="mt-4 text-small text-ink-muted">
        The label is what a learner reads in their ruby history, so it is written in Vietnamese.
        Deleting every row is not a way to empty this table — the defaults seed themselves on the
        next read, so disable a source instead.
      </p>
    </Page>
  );
}
