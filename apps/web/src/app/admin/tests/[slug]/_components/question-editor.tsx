"use client";

import { type QuestionAdmin } from "@toeic-pilot/shared";
import { useState } from "react";

import { Button, Field, Input, Textarea, cx } from "@/components/ui";

/**
 * Sửa một câu đã ghi.
 *
 * Part 1 và 2 KHÔNG in gì ra đề, nên ô đề bài để trống ở đó là đúng chứ không
 * phải thiếu dữ liệu — và lúc lưu phải BỎ HẲN khoá `prompt_text` thay vì gửi
 * chuỗi rỗng, vì `exclude_unset` là thứ duy nhất phân biệt "để nguyên" với
 * "xoá đi", và `""` bị cổng kiểm từ chối.
 */

export function QuestionEditor({
  question,
  busy,
  onSave,
}: {
  question: QuestionAdmin;
  busy: boolean;
  onSave: (changes: Record<string, unknown>) => void;
}) {
  const [prompt, setPrompt] = useState(question.prompt_text ?? "");
  const [explanation, setExplanation] = useState(question.explanation ?? "");
  const [correct, setCorrect] = useState(
    question.options.find((option) => option.is_correct)?.label ?? "A",
  );
  const [options, setOptions] = useState<Record<string, string>>(
    Object.fromEntries(question.options.map((option) => [option.label, option.content ?? ""])),
  );
  const [translations, setTranslations] = useState<Record<string, string>>(
    Object.fromEntries(question.options.map((option) => [option.label, option.content_vi ?? ""])),
  );

  // Part 1 và 2 KHÔNG in gì cả, nên ở đó không có đề bài và không có nội dung
  // đáp án để sửa — chữ của chúng nằm trong lời thoại, sửa ở khung Lời thoại.
  //
  // Không phải chuyện gọn mắt: hai ô đó gửi `""` lên server, mà `""` không phải
  // NULL, nên `validate_question` từ chối và câu Part 1/2 nào cũng không lưu
  // nổi. Ẩn ô đi mà vẫn gửi khoá thì vẫn hỏng y hệt — nên khoá cũng bị bỏ khỏi
  // payload bên dưới.
  const printed = question.part !== 1 && question.part !== 2;

  return (
    <div className="mt-3 border-t border-rule pt-3">
      {printed && (
        <Field label="Đề bài">
          <Textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={2} />
        </Field>
      )}

      <div className="mt-3 space-y-2">
        {question.options.map((option) => (
          <div key={option.label} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setCorrect(option.label)}
              aria-pressed={correct === option.label}
              title="Đặt làm đáp án đúng"
              className={cx(
                "grid h-8 w-8 shrink-0 place-items-center rounded border font-semibold",
                correct === option.label
                  ? "border-ok bg-ok-tint text-ok"
                  : "border-rule-strong text-ink-muted hover:border-ok",
              )}
            >
              {option.label}
            </button>
            {printed ? (
              <Input
                value={options[option.label] ?? ""}
                onChange={(event) => setOptions({ ...options, [option.label]: event.target.value })}
              />
            ) : (
              <span className="text-small text-ink-faint">
                {/* Part 1/2 không in đáp án, nhưng LỜI ĐỌC thì có — hiện nó ở
                    đây để người soạn biết mình đang dịch câu nào. */}
                {option.spoken_text ?? "đọc lên, không in — sửa ở khung Lời thoại"}
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="mt-3 space-y-2">
        {/*
         * Bản dịch tách thành một khối riêng, không xen giữa các đáp án.
         *
         * Xen vào thì hàng đáp án dài gấp đôi và việc hay làm nhất — soát xem
         * đáp án đúng đã chọn chưa — bị đẩy ra xa nhau. Ở đây người soạn dịch
         * cả bốn câu một lượt, đúng nhịp thật của việc dịch.
         *
         * Hiện ở MỌI part, khác ô nội dung: Part 1/2 không in đáp án nhưng vẫn
         * có lời đọc để dịch, và bản dịch đó hiện cho học viên ở chế độ Luyện tập.
         */}
        <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
          Dịch nghĩa từng đáp án
        </p>
        {question.options.map((option) => (
          <div key={option.label} className="flex items-center gap-2">
            <span className="w-8 shrink-0 text-center font-data text-small text-ink-faint">
              {option.label}
            </span>
            <Input
              value={translations[option.label] ?? ""}
              placeholder="để trống nếu chưa dịch"
              aria-label={`Dịch nghĩa đáp án ${option.label}`}
              onChange={(event) =>
                setTranslations({ ...translations, [option.label]: event.target.value })
              }
            />
          </div>
        ))}
      </div>

      <div className="mt-3">
        <Field label="Giải thích" hint="Viết tiếng Việt — người học sẽ đọc nó.">
          <Textarea
            value={explanation}
            onChange={(event) => setExplanation(event.target.value)}
            rows={2}
          />
        </Field>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button
          size="sm"
          onClick={() =>
            onSave(
              // `exclude_unset` ở server phân biệt "vắng mặt" với "null", nên
              // với Part 1/2 phải BỎ HẲN hai khoá này — gửi `""` là ghi một
              // chuỗi rỗng vào cột buộc phải NULL, và câu sẽ không lưu được.
              printed
                ? {
                    prompt_text: prompt,
                    explanation: explanation || null,
                    correct_label: correct,
                    options,
                    translations,
                  }
                : {
                    explanation: explanation || null,
                    correct_label: correct,
                    // `translations` đi kèm CẢ ở Part 1/2, khác `options`: chỗ
                    // này dịch lời đọc, và lời đọc thì hai part đó có.
                    translations,
                  },
            )
          }
          disabled={busy}
        >
          Lưu
        </Button>
        {/* Sửa một câu đã xuất bản sẽ đưa nó về nháp, và người soạn phải biết
            trước khi bấm — không phải phát hiện sau khi cái badge đổi màu. */}
        {question.status === "published" && (
          <span className="text-small text-warn">Lưu xong câu này quay về trạng thái nháp</span>
        )}
      </div>
    </div>
  );
}
