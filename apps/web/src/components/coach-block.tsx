"use client";

import { API_ROUTES, type CoachExplanation } from "@toeic-pilot/shared";
import { ChevronDown, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { Spinner, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";

/** Năm mục, đúng thứ tự người đọc cần: chẩn đoán trước, mẹo tránh bẫy sau. */
const SECTIONS: { key: string; label: string }[] = [
  { key: "chan_doan", label: "Bạn nhầm ở đâu" },
  { key: "vi_sao_ban_chon_sai", label: "Vì sao phương án bạn chọn sai" },
  { key: "vi_sao_dap_an_dung", label: "Vì sao đáp án đúng" },
  { key: "quy_tac", label: "Quy tắc cần nhớ" },
  { key: "bay_tuong_tu", label: "Bẫy tương tự" },
];

/**
 * Trợ giảng giải thích một câu làm sai.
 *
 * Chỉ hiện sau khi đã nộp bài — máy chủ trả 409 nếu chưa, nhưng giao diện không
 * được dựa vào đó: một nút bấm được rồi báo lỗi là một nút hứa sai.
 *
 * Lời giải KHÔNG tự tải. Người học vừa xem xong bảng kết quả và đang lướt hàng
 * chục câu; tải sẵn cho mọi câu là hàng chục lượt gọi cho một hai câu người ta
 * thực sự muốn đọc — và mỗi lượt là tiền thật.
 */
export function CoachBlock({
  attemptId,
  questionId,
  token,
}: {
  attemptId: string;
  questionId: string;
  token: string | null;
}) {
  const [explanation, setExplanation] = useState<CoachExplanation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);

  async function ask() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      setExplanation(
        await apiFetch<CoachExplanation>(API_ROUTES.coachExplain(attemptId, questionId), {
          method: "POST",
          token,
        }),
      );
      setOpen(true);
    } catch (caught) {
      // In nguyên thông điệp máy chủ. Nó phân biệt năm tình huống rất khác nhau
      // — hết hạn mức, tính năng tắt, câu thiếu nội dung, chưa tạo được lời giải
      // đạt, nhà cung cấp hỏng — và gộp thành "có lỗi xảy ra" là bỏ đi thứ duy
      // nhất giúp người dùng biết nên chờ hay nên thôi.
      setError(caught instanceof Error ? caught.message : "Chưa lấy được lời giải");
    } finally {
      setBusy(false);
    }
  }

  async function rate(helpful: boolean) {
    if (!token || !explanation) return;
    try {
      setExplanation(
        await apiFetch<CoachExplanation>(API_ROUTES.coachFeedback(attemptId, questionId), {
          method: "POST",
          token,
          body: JSON.stringify({ explanation_id: explanation.id, helpful }),
        }),
      );
    } catch {
      /* phiếu đánh giá hỏng không đáng làm phiền người đang đọc */
    }
  }

  if (explanation === null) {
    return (
      <div className="mt-3">
        {/* Viền gradient là một LỚP BỌC, không phải `border` trên nút: một viền
            chuyển màu không dựng được bằng thuộc tính `border`. */}
        <span className="ai-border inline-flex">
          <button
            type="button"
            onClick={ask}
            disabled={busy || !token}
            className={cx(
              "ai-fill inline-flex items-center gap-1.5 rounded px-3 py-1.5",
              "text-small font-semibold transition-opacity",
              "hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60",
            )}
          >
            {busy ? <Spinner className="h-3.5 w-3.5" /> : <Sparkles size={14} strokeWidth={2} />}
            {busy ? "Đang soạn…" : "AI Explain"}
          </button>
        </span>
        {error && <p className="mt-2 text-small text-alert">{error}</p>}
      </div>
    );
  }

  return (
    <div className="ai-border mt-3">
      <div className="rounded bg-panel p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="flex items-center gap-1.5 text-label font-semibold uppercase tracking-wide text-ink-muted">
            <Sparkles size={13} strokeWidth={2} aria-hidden />
            AI Explain
          </p>
          {/*
           * Thu gọn, không phải đóng: lời giải đã tốn một lượt gọi model, nên
           * bỏ nó khỏi cây DOM sẽ khiến người mở lại phải trả tiền lần nữa —
           * hoặc tệ hơn, khiến ta phải nhớ cache ở tầng giao diện.
           */}
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-label={open ? "Thu gọn lời giải" : "Mở lời giải"}
            className="rounded p-1 text-ink-muted transition-colors hover:bg-recess hover:text-ink"
          >
            <ChevronDown
              size={16}
              strokeWidth={2}
              aria-hidden
              className={cx("transition-transform", open && "rotate-180")}
            />
          </button>
        </div>

        {open && (
          <>
            <dl className="mt-3 space-y-3">
              {SECTIONS.map((section) => {
                const text = explanation.body[section.key];
                if (!text) return null;
                return (
                  <div key={section.key}>
                    <dt className="text-label font-semibold uppercase tracking-wide text-ink-faint">
                      {section.label}
                    </dt>
                    <dd className="mt-0.5 text-small leading-relaxed">{text}</dd>
                  </div>
                );
              })}
            </dl>

            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-rule pt-3">
              <span className="text-small text-ink-muted">Lời giải này có giúp bạn không?</span>
              <RateButton
                icon={ThumbsUp}
                label="Có ích"
                active={explanation.helpful === true}
                onClick={() => void rate(true)}
              />
              <RateButton
                icon={ThumbsDown}
                label="Chưa rõ"
                active={explanation.helpful === false}
                onClick={() => void rate(false)}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function RateButton({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: typeof ThumbsUp;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cx(
        "inline-flex items-center gap-1.5 rounded px-2 py-1 text-small font-semibold",
        active ? "bg-action-tint text-action-ink" : "text-ink-muted hover:bg-recess hover:text-ink",
      )}
    >
      <Icon size={14} strokeWidth={2} aria-hidden />
      {label}
    </button>
  );
}
