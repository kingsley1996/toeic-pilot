"use client";

import type { VocabularyParseResponse } from "@toeic-pilot/shared";
import { Check, CircleAlert, Pencil, Terminal, X } from "lucide-react";
import { useState } from "react";

import { Alert, IconButton, Input, Panel, Tag, cx } from "@/components/ui";

/** Lệnh sinh ra phần audio còn thiếu. */
export function BackfillHint() {
  return (
    <Alert tone="info">
      <span className="flex items-center gap-1.5 font-semibold text-ink">
        <Terminal size={14} strokeWidth={2} aria-hidden />
        Audio is not generated from this screen
      </span>
      <p className="mt-1">
        New content is saved as a draft. Run <code className="font-data text-ink">apps/api</code>:{" "}
        <code className="font-data text-ink">uv run python -m app.content.backfill_audio</code>.
        Publishing is refused until every clip matches its current text.
      </p>
    </Alert>
  );
}

type ParsedRow = { line: number; problems?: string[] | null };

/**
 * Lưới xem lại kết quả parse — trước khi bất cứ thứ gì được ghi.
 *
 * Dòng chữ "Nothing has been written to the database" không phải trấn an: parse và
 * commit là hai endpoint tách rời và parse KHÔNG BAO GIỜ ghi database
 * (ADR-005 §5.1). Xem trước rồi mới quyết định là toàn bộ lý do công cụ này
 * tồn tại.
 */
export function ParsePreview<T extends ParsedRow>({
  parsed,
  render,
}: {
  parsed: { ok_count: number; error_count: number; rows: T[] } | VocabularyParseResponse;
  render: (row: T) => React.ReactNode;
}) {
  const rows = parsed.rows as T[];
  return (
    <Panel className="mt-4 overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-rule bg-recess px-4 py-2.5">
        <Tag tone="ok">{parsed.ok_count} valid</Tag>
        {parsed.error_count > 0 && <Tag tone="alert">{parsed.error_count} lỗi</Tag>}
        <span className="text-small text-ink-muted">Nothing has been written to the database</span>
      </div>
      <ul className="divide-y divide-rule">
        {rows.map((row) => {
          const broken = Boolean(row.problems?.length);
          return (
            <li key={row.line} className={cx("px-4 py-2.5", broken && "bg-alert-tint/50")}>
              <div className="flex items-start gap-3">
                <span className="w-6 shrink-0 text-right font-data text-small text-ink-faint">
                  {row.line}
                </span>
                <div className="min-w-0 flex-1 text-body">{render(row)}</div>
              </div>
              {row.problems?.map((problem) => (
                <p
                  key={problem}
                  className="ml-9 mt-1 flex items-center gap-1.5 text-small text-alert"
                >
                  <CircleAlert size={14} strokeWidth={2} className="shrink-0" aria-hidden />
                  {problem}
                </p>
              ))}
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

/**
 * Rename in place: a pencil beside the name, an input where the name was.
 *
 * Not a modal. Renaming is the smallest edit the admin area has, and a dialog
 * costs an overlay, a focus trap and two extra clicks to change one word — the
 * kind of ceremony that makes people leave the typo instead.
 *
 * The name is the ONLY thing this touches. A slug looks like the same kind of
 * text and is not: it sits in every admin URL and is what the content scripts
 * look a collection up by, so editing it here would turn fixing a typo into
 * breaking every saved link at once, with nothing redirecting them. The API
 * refuses it too — `CollectionUpdate` does not declare `slug`.
 *
 * Escape cancels and Enter saves, because a one-field form where the only way
 * out is the mouse is a form people abandon halfway.
 */
export function InlineRename({
  value,
  label,
  onSave,
  disabled,
}: {
  value: string;
  /** Names the thing being renamed, for the screen reader and the tooltip. */
  label: string;
  onSave: (next: string) => void;
  disabled?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  if (!editing) {
    return (
      <IconButton
        icon={Pencil}
        aria-label={`Rename ${label}`}
        disabled={disabled}
        className="h-7 w-7"
        onClick={() => {
          // Seed the draft at the moment of opening, never from an effect: the
          // value may have changed since the last render, and an effect that
          // syncs it would also stomp on what the user has typed.
          setDraft(value);
          setEditing(true);
        }}
      />
    );
  }

  const commit = () => {
    const next = draft.trim();
    setEditing(false);
    // An empty name is a name nobody can find the row by, and every one of these
    // titles is NOT NULL. Treat blank as cancel rather than sending it and
    // letting the server answer with a 422.
    if (next && next !== value) onSave(next);
  };

  return (
    <span className="flex items-center gap-1.5">
      <Input
        autoFocus
        value={draft}
        aria-label={`Name of ${label}`}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commit();
          }
          if (event.key === "Escape") setEditing(false);
        }}
        className="w-64"
      />
      <IconButton icon={Check} aria-label="Save name" className="h-7 w-7" onClick={commit} />
      <IconButton
        icon={X}
        aria-label="Cancel rename"
        className="h-7 w-7"
        onClick={() => setEditing(false)}
      />
    </span>
  );
}
