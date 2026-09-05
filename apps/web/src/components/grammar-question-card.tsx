"use client";

import {
  API_ROUTES,
  type GrammarPracticeQuestion,
  type GrammarPracticeResult,
} from "@toeic-pilot/shared";
import { Check, X } from "lucide-react";
import { useState } from "react";

import { MarkdownLite } from "@/components/markdown-lite";
import { Panel, Tag } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";

/**
 * Một câu trắc nghiệm, chấm ở MÁY CHỦ: `is_correct` chỉ rời máy chủ sau khi
 * nộp — cùng luật `QuestionPublic` của khu luyện thi, dù đây là tự học.
 *
 * Dùng chung cho hai chỗ: màn "Luyện tập" cuối chủ đề (G3) và lesson
 * `kind=practice` (G4). Hai bản sao của khối này sẽ trôi nhau đúng chỗ nguy
 * hiểm nhất: cách tô đáp án sau khi nộp.
 */
export function GrammarQuestionCard({
  question,
  token,
  onCorrect,
}: {
  question: GrammarPracticeQuestion;
  token: string | null;
  onCorrect?: (questionId: string) => void;
}) {
  const [answer, setAnswer] = useState<(GrammarPracticeResult & { chosenId: string }) | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  async function choose(optionId: string) {
    if (!token || answer) return;
    setFailure(null);
    try {
      const result = await apiFetch<GrammarPracticeResult>(API_ROUTES.grammarAttempts, {
        method: "POST",
        token,
        body: JSON.stringify({ question_id: question.id, option_id: optionId }),
      });
      setAnswer({ ...result, chosenId: optionId });
      if (result.is_correct) onCorrect?.(question.id);
    } catch (err) {
      setFailure(err instanceof ApiError ? err.message : "Không nộp được câu trả lời.");
    }
  }

  const done = question.completed || Boolean(answer?.is_correct);

  return (
    <Panel className="p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="font-data text-body">{question.prompt_text ?? `(Part ${question.part})`}</p>
        {done && (
          <Tag tone="ok">
            <Check size={12} strokeWidth={2} aria-hidden />
            Đã đúng
          </Tag>
        )}
      </div>
      {failure && <p className="mt-2 text-small text-alert">{failure}</p>}
      <div className="mt-3 grid gap-1.5">
        {question.options.map((option) => {
          const chosen = answer?.chosenId === option.id;
          const isKey = answer?.correct_option_id === option.id;
          const tone = !answer
            ? "border-rule hover:border-rule-strong"
            : isKey
              ? "border-ok bg-ok-tint"
              : chosen
                ? "border-alert bg-alert-tint"
                : "border-rule";
          return (
            <button
              key={option.id}
              type="button"
              disabled={Boolean(answer)}
              onClick={() => void choose(option.id)}
              className={`flex items-center gap-2 rounded border px-3 py-2 text-left text-body disabled:cursor-default ${tone}`}
            >
              <span className="font-data text-small text-ink-faint">{option.label}</span>
              <span className="min-w-0 flex-1">{option.content}</span>
              {answer && isKey && (
                <Check size={14} strokeWidth={2} className="text-ok" aria-hidden />
              )}
              {answer && chosen && !isKey && (
                <X size={14} strokeWidth={2} className="text-alert" aria-hidden />
              )}
            </button>
          );
        })}
      </div>
      {answer?.explanation && (
        <div className="mt-3 border-t border-rule pt-3">
          <MarkdownLite text={answer.explanation} className="text-small text-ink-muted" />
        </div>
      )}
    </Panel>
  );
}
