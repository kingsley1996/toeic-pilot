"use client";

import { cx } from "@/components/ui";

/*
 * Lời giải thích được viết theo định dạng có khoá nhãn:
 *
 *   <dẫn chứng> | (A) … | (B) … | (C) … | (D) …
 *
 * Định dạng ấy sinh ra cho khâu sinh đề — phép cân đáp án đổi chỗ mệnh đề cùng
 * với lựa chọn — nhưng nó cũng đọc dễ hơn hẳn một khối văn xuôi: mắt tìm được
 * ngay mệnh đề của phương án mình vừa chọn sai.
 *
 * Hàng trăm câu Part 5 đã nạp viết theo lối cũ và không có dấu phân cách nào,
 * nên khi tách không ra hình dạng ấy thì in nguyên một đoạn.
 */
const CLAUSE = /^\(([A-D])\)\s*(.+)$/;

function segments(text: string): { evidence: string; clauses: [string, string][] } | null {
  // Tách tại `|` đứng ngay TRƯỚC một nhãn, không tại mọi `|`: bảng biểu Part 7
  // dùng dấu ống ngăn cột và lời giải thích trích chúng nguyên văn, nên tách
  // theo mọi dấu sẽ cắt `"Sales | 12"` thành hai đoạn rác.
  const parts = text
    .split(/\s*\|\s*(?=\([A-D]\))/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.length < 2) return null;

  const clauses: [string, string][] = [];
  for (const part of parts.slice(1)) {
    const matched = CLAUSE.exec(part);
    if (!matched) return null;
    clauses.push([matched[1], matched[2]]);
  }
  return { evidence: parts[0], clauses };
}

export function ExplanationNote({
  text,
  correctLabel,
}: {
  text: string;
  correctLabel: string | null;
}) {
  const parsed = segments(text);

  return (
    <div className="mt-3 rounded border border-rule bg-recess p-3 text-small leading-relaxed">
      {parsed === null ? (
        <p>{text}</p>
      ) : (
        <>
          <p>{parsed.evidence}</p>
          <ul className="mt-2 space-y-1">
            {parsed.clauses.map(([label, body]) => (
              <li key={label} className="flex gap-2">
                <span
                  className={cx(
                    "font-semibold",
                    label === correctLabel ? "text-ok" : "text-ink-muted",
                  )}
                >
                  ({label})
                </span>
                <span className="min-w-0">{body}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
