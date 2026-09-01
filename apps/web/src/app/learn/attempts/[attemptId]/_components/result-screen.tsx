"use client";

import { type AttemptResult, type AttemptState } from "@toeic-pilot/shared";

import { Button, ButtonLink, cx } from "@/components/ui";
import { formatClock, Tally } from "./shared";

/** Màn kết quả sau khi nộp: điểm quy đổi và số câu đúng theo part. */

/**
 * Bảng kết quả sau khi nộp.
 *
 * Thay cho danh sách câu chứ không nằm đè lên nó: câu hỏi đầu tiên sau khi nộp
 * là "tôi được bao nhiêu", còn xem lại từng câu là việc thứ hai và có nút riêng.
 *
 * Điểm quy đổi chỉ hiện khi máy chủ THẬT SỰ gửi. `scoring.py` từ chối quy đổi
 * một đề rút gọn — bảng điểm dựng cho 200 câu, nên đề 40 câu tra vào đó sẽ chạm
 * sàn và in ra "Nghe 5 · Đọc 5" cho một người làm đúng 60%. Chỗ trống đó được
 * lấp bằng `scale_note` nói lý do, không phải bằng số 0.
 */
export function ResultScreen({
  result,
  state,
  onReview,
}: {
  result: AttemptResult;
  state: AttemptState;
  onReview: () => void;
}) {
  const answered = state.questions.filter((q) => q.selected_option_id).length;
  const flagged = state.questions.filter((q) => q.flagged).length;
  const percent = result.question_count
    ? Math.round((result.correct_count / result.question_count) * 100)
    : 0;

  // Đúng/tổng theo từng part, tính từ chính danh sách câu — sau khi nộp mỗi câu
  // đã mang `correct_option_id`, nên không cần endpoint thống kê riêng.
  const byPart = state.parts.map((part) => {
    const questions = state.questions.filter((q) => q.part === part.part);
    const correct = questions.filter(
      (q) => q.selected_option_id !== null && q.selected_option_id === q.correct_option_id,
    ).length;
    return { ...part, correct, count: questions.length };
  });

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <p className="text-label uppercase text-ink-muted">Kết quả</p>
      <h1 className="mt-1 text-title">{state.test_title}</h1>

      <div className="mt-6 rounded border border-rule-strong bg-panel p-5">
        <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
          <div>
            <p className="text-label uppercase text-ink-muted">Số câu đúng</p>
            <p className="font-data text-3xl font-semibold tabular-nums">
              {result.correct_count}
              <span className="text-ink-faint">/{result.question_count}</span>
            </p>
          </div>
          <div>
            <p className="text-label uppercase text-ink-muted">Độ chính xác</p>
            <p className="font-data text-3xl tabular-nums">{percent}%</p>
          </div>
          {result.total_scaled !== null && (
            <div>
              <p className="text-label uppercase text-ink-muted">Tổng quy đổi</p>
              <p className="font-data text-3xl font-semibold tabular-nums text-action-ink">
                {result.total_scaled}
              </p>
            </div>
          )}
          {result.listening_scaled !== null && (
            <div>
              <p className="text-label uppercase text-ink-muted">Nghe</p>
              <p className="font-data text-2xl tabular-nums">{result.listening_scaled}</p>
            </div>
          )}
          {result.reading_scaled !== null && (
            <div>
              <p className="text-label uppercase text-ink-muted">Đọc</p>
              <p className="font-data text-2xl tabular-nums">{result.reading_scaled}</p>
            </div>
          )}
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-rule pt-4 sm:grid-cols-4">
          <Tally label="Đã trả lời" value={`${answered}/${result.question_count}`} />
          <Tally
            label="Bỏ trống"
            value={result.question_count - answered}
            tone={answered < result.question_count ? "warn" : undefined}
          />
          <Tally label="Đã đánh dấu" value={flagged} />
          <Tally label="Thời gian đã dùng" value={formatClock(result.elapsed_seconds)} />
        </dl>

        {result.scale_note && (
          <p className="mt-4 rounded border border-rule bg-recess p-3 text-small text-ink-muted">
            {result.scale_note}
          </p>
        )}
      </div>

      <section className="mt-8">
        <h2 className="text-label font-semibold uppercase text-ink-muted">Theo từng phần</h2>
        <div className="mt-3 space-y-2">
          {byPart
            .filter((part) => part.count > 0)
            .map((part) => {
              const share = part.count ? Math.round((part.correct / part.count) * 100) : 0;
              return (
                <div
                  key={part.part}
                  className="flex items-center gap-3 rounded border border-rule bg-panel px-3 py-2.5"
                >
                  <span className="w-28 shrink-0 text-small font-semibold">
                    Part {part.part}
                    <span className="ml-1.5 font-normal text-ink-faint">{part.section}</span>
                  </span>
                  <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-pill bg-recess">
                    <div
                      className={cx("h-full", share >= 50 ? "bg-ok" : "bg-warn")}
                      style={{ width: `${share}%` }}
                    />
                  </div>
                  <span className="w-20 shrink-0 text-right font-data text-small tabular-nums">
                    {part.correct}/{part.count}
                  </span>
                  <span className="w-12 shrink-0 text-right font-data text-small tabular-nums text-ink-muted">
                    {share}%
                  </span>
                </div>
              );
            })}
        </div>
      </section>

      <div className="mt-8 flex flex-wrap gap-2">
        <Button onClick={onReview}>Xem chi tiết từng câu</Button>
        <ButtonLink href="/learn/tests" variant="secondary">
          Về danh sách đề
        </ButtonLink>
      </div>
    </div>
  );
}
