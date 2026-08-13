"use client";

import type { VocabularyParseResponse } from "@toeic-pilot/shared";
import { CircleAlert, Terminal } from "lucide-react";

import { Alert, Panel, Tag, cx } from "@/components/ui";

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
