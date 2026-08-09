"use client";

import type { VocabularyParseResponse } from "@toeic-pilot/shared";

import { Alert, Badge, Card } from "@/components/ui";

/**
 * How ready a piece of content's audio is.
 *
 * `stale` is the one worth understanding: the clip exists but was made from an
 * older version of the text, so it says the wrong words. For a dictation that
 * matters twice over, because the transcript is also the answer key — the
 * learner would be marked against a sentence they were never played.
 */
export function AudioBadge({ state }: { state: string }) {
  if (state === "current") return <Badge tone="success">audio sẵn sàng</Badge>;
  if (state === "stale") return <Badge tone="warning">audio đã cũ</Badge>;
  return <Badge tone="neutral">chưa có audio</Badge>;
}

/** The command that fills in whatever is missing. */
export function BackfillHint() {
  return (
    <Alert tone="brand">
      Audio không sinh từ giao diện này. Nội dung mới lưu ở dạng nháp; chạy trong{" "}
      <code className="font-mono">apps/api</code>:{" "}
      <code className="font-mono">uv run python -m app.content.backfill_audio</code>. Chỉ publish
      được khi audio khớp đúng với text hiện tại.
    </Alert>
  );
}

type ParsedRow = { line: number; problems?: string[] | null };

/** Shared review grid: the parse result before anything is written. */
export function ParsePreview<T extends ParsedRow>({
  parsed,
  render,
}: {
  parsed: { ok_count: number; error_count: number; rows: T[] } | VocabularyParseResponse;
  render: (row: T) => React.ReactNode;
}) {
  const rows = parsed.rows as T[];
  return (
    <Card className="mt-4 overflow-hidden">
      <div className="flex items-center gap-3 border-b border-border px-5 py-3">
        <Badge tone="success">{parsed.ok_count} hợp lệ</Badge>
        {parsed.error_count > 0 && <Badge tone="danger">{parsed.error_count} lỗi</Badge>}
        <span className="text-xs text-text-subtle">Chưa có gì được ghi vào cơ sở dữ liệu</span>
      </div>
      <ul className="divide-y divide-border">
        {rows.map((row) => (
          <li
            key={row.line}
            className={row.problems?.length ? "bg-danger-soft/40 px-5 py-3" : "px-5 py-3"}
          >
            <div className="flex items-start gap-3">
              <span className="w-6 shrink-0 text-right text-xs text-text-subtle tabular-nums">
                {row.line}
              </span>
              <div className="min-w-0 flex-1 text-sm">{render(row)}</div>
            </div>
            {row.problems?.map((problem) => (
              <p key={problem} className="ml-9 mt-1 text-xs text-danger">
                ⚠ {problem}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </Card>
  );
}
