"use client";

import { type GroupDraft, type TestPartParseResponse } from "@toeic-pilot/shared";
import { CircleAlert } from "lucide-react";

import { Panel, Tag, cx } from "@/components/ui";

/** Xem trước kết quả dán trước khi ghi: từng cụm, từng câu, kèm lỗi của nó. */

export function GroupPreview({ parsed }: { parsed: TestPartParseResponse }) {
  return (
    <Panel className="mt-4 overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-rule bg-recess px-4 py-2.5">
        <Tag tone="ok">{parsed.ok_count} cụm hợp lệ</Tag>
        {parsed.error_count > 0 && <Tag tone="alert">{parsed.error_count} cụm lỗi</Tag>}
        {/* Câu này phải nói ra, vì nó là toàn bộ lý do bước xem trước tồn tại. */}
        <span className="text-small text-ink-muted">Chưa có gì được ghi vào cơ sở dữ liệu</span>
      </div>
      <ul className="divide-y divide-rule">
        {parsed.groups.map((group) => (
          <GroupRow key={group.line} group={group} part={parsed.part} />
        ))}
      </ul>
    </Panel>
  );
}

function GroupRow({ group, part }: { group: GroupDraft; part: number }) {
  const broken = group.problems.length > 0 || group.questions.some((q) => q.problems.length > 0);
  // Part 1 và 2 không in gì; chữ của chúng nằm trong lời thoại bên dưới.
  const printed = part !== 1 && part !== 2;
  return (
    <li className={cx("px-4 py-3", broken && "bg-alert-tint/50")}>
      {group.title && <p className="text-small font-semibold">{group.title}</p>}

      {group.passages.map((passage, index) => (
        <p
          key={index}
          className="mt-1.5 line-clamp-3 whitespace-pre-wrap rounded border border-rule bg-recess p-2 text-small text-ink-muted"
        >
          {passage}
        </p>
      ))}

      {group.problems.map((problem) => (
        <p key={problem} className="mt-1.5 flex items-center gap-1.5 text-small text-alert">
          <CircleAlert size={14} strokeWidth={2} aria-hidden className="shrink-0" />
          {problem}
        </p>
      ))}

      {group.questions.map((question) => (
        <div key={question.line} className="mt-2.5 border-l-2 border-rule pl-3">
          <div className="flex items-start gap-2">
            <span className="w-6 shrink-0 text-right font-data text-small text-ink-faint">
              {question.line}
            </span>
            <div className="min-w-0 flex-1">
              {/* NULL là giá trị ĐÚNG ở Part 1/2, không phải dữ liệu thiếu — in
                  "thiếu đề bài" ở đó là báo lỗi cho một câu hoàn toàn ổn, ngay
                  tại bước người ta đang soát xem có gì sai không. */}
              {printed ? (
                <p className="text-small">{question.prompt_text || <em>thiếu đề bài</em>}</p>
              ) : (
                <p className="text-small text-ink-faint">Đọc lên, không in — xem Lời thoại</p>
              )}
              <p className="mt-0.5 text-small text-ink-muted">
                {question.options.map((option) => (
                  <span
                    key={option.label}
                    className={cx("mr-3", option.is_correct && "font-semibold text-ok")}
                  >
                    ({option.label}){option.content ? ` ${option.content}` : ""}
                  </span>
                ))}
              </p>
              {question.problems.map((problem) => (
                <p key={problem} className="mt-1 flex items-center gap-1.5 text-small text-alert">
                  <CircleAlert size={14} strokeWidth={2} aria-hidden className="shrink-0" />
                  {problem}
                </p>
              ))}
            </div>
          </div>
        </div>
      ))}
    </li>
  );
}
