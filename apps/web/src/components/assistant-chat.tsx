"use client";

import {
  API_ROUTES,
  type ChatHistoryPage,
  type ChatMessagePublic,
  type ChatTurn,
} from "@toeic-pilot/shared";
import { Send, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cx } from "@/components/ui";
import { MarkdownLite } from "@/components/markdown-lite";
import { apiFetch } from "@/lib/api";

// Hình dạng phản hồi đến TỪ HỢP ĐỒNG, không gõ tay lại. `apiFetch<T>` nhận
// kiểu từ nơi gọi, nên một shape tự khai làm mọi thay đổi ở API trở nên vô
// hình với `tsc` — đúng cái bẫy CLAUDE.md ghi cho sáu endpoint đổi sang Page.
type Message = ChatMessagePublic;

/*
 * Câu gợi ý lúc chưa có tin nhắn nào — bấm là điền vào ô nhập để sửa rồi gửi,
 * không gửi thẳng: một đề xuất lạc đề là thứ người dùng phải có quyền huỷ.
 */
const SUGGESTIONS = [
  "Trang web có những khu nào?",
  "Cách tính điểm luyện đề thế nào?",
  "Làm sao để ôn từ vựng hiệu quả?",
  "Tiến độ của tôi đang ra sao?",
];

/**
 * Màn hỏi đáp của Trợ lý trang web — khác hộp "Hỏi trợ giảng" ở NƠI SỐNG:
 *
 * - Trợ giảng neo vào một lượt làm bài, nên nó là hộp dính góc trên màn xem lại.
 *   Trợ lý nói về cả trang web và tiến độ người học, không neo vào đâu, nên nó
 *   có một màn riêng và nạp lịch sử NGAY khi mở — không có lý do gì để chờ một
 *   cú bấm mới hỏi máy chủ "có chuyện gì đang dở không".
 *
 * Hình dạng theo chuẩn chat frontier: cột tin nhắn hẹp, người học bên phải trong
 * bong bóng, trợ lý bên trái không bong bóng kèm dấu hiệu AI, và thanh nhập bo
 * tròn ở đáy. Các quyết định UI giữ nguyên từ `coach-chat.tsx`: tin nhắn hiện
 * lạc quan trước khi máy chủ trả lời, gỡ và TRẢ LẠI ô nhập khi gửi hỏng, chiều
 * cao ô nhập bám theo `draft` trong effect chứ không trong `onChange`, và
 * `isComposing` chặn Enter giữa chừng một từ tiếng Việt.
 */
export function AssistantChat({ token }: { token: string | null }) {
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Số tin nhắn cũ hơn còn nằm ngoài trang đầu — 0 nghĩa là đã thấy hết.
  const [older, setOlder] = useState(0);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!token || messages !== null) return;
    let cancelled = false;
    // Máy chủ trả trang MỚI NHẤT TRƯỚC (`position` giảm dần), nên đảo lại để
    // đọc theo mạch trò chuyện. Đây là lý do endpoint không sắp tăng dần: trang
    // đầu phải là thứ vừa nói, không phải cuộc trò chuyện của tháng trước.
    apiFetch<ChatHistoryPage>(`${API_ROUTES.assistantChat}?limit=50`, { token })
      .then((page) => {
        if (cancelled) return;
        setMessages([...page.items].reverse());
        setOlder(Math.max(0, page.total - page.items.length));
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [token, messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, busy]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 96)}px`;
  }, [draft]);

  async function send() {
    const text = draft.trim();
    if (!text || !token || busy) return;

    const optimisticId = `pending:${Date.now()}`;
    setMessages((rows) => [...(rows ?? []), { id: optimisticId, role: "user", content: text }]);
    setDraft("");
    setBusy(true);
    setError(null);

    try {
      const turn = await apiFetch<ChatTurn>(API_ROUTES.assistantChat, {
        method: "POST",
        token,
        body: JSON.stringify({ message: text }),
      });
      setMessages((rows) => [
        ...(rows ?? []).filter((row) => row.id !== optimisticId),
        turn.question,
        turn.answer,
      ]);
    } catch (caught) {
      setMessages((rows) => (rows ?? []).filter((row) => row.id !== optimisticId));
      setDraft(text);
      setError(caught instanceof Error ? caught.message : "Chưa gửi được câu hỏi");
    } finally {
      setBusy(false);
    }
  }

  const loadOlder = () => {
    if (!token || loadingOlder) return;
    setLoadingOlder(true);
    // `offset` tính theo số tin ĐÃ CÓ, và endpoint sắp giảm dần, nên trang kế
    // tiếp đúng là đoạn liền trước những gì đang hiện.
    apiFetch<ChatHistoryPage>(
      `${API_ROUTES.assistantChat}?limit=50&offset=${(messages ?? []).length}`,
      { token },
    )
      .then((page) => {
        setMessages((current) => [...[...page.items].reverse(), ...(current ?? [])]);
        setOlder(Math.max(0, page.total - (messages ?? []).length - page.items.length));
      })
      .catch(() => setError("Không tải được tin nhắn cũ."))
      .finally(() => setLoadingOlder(false));
  };

  const rows = messages ?? [];

  // Xoá lịch sử cần XÁC NHẬN trước khi gửi DELETE: gõ nhầm một cú bấm là mất
  // cả mạch trò chuyện. Hai bước — bấm lần một hiện "Xoá hẳn?", lần hai mới gửi.
  async function clearHistory() {
    if (!token || clearing) return;
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    setClearing(true);
    setError(null);
    try {
      await apiFetch<void>(API_ROUTES.assistantChat, { method: "DELETE", token });
      setMessages([]);
      setOlder(0);
      setConfirmClear(false);
      inputRef.current?.focus();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Chưa xoá được lịch sử");
    } finally {
      setClearing(false);
    }
  }

  const hasHistory = rows.length > 0;

  return (
    <div className="flex h-[min(78vh,46rem)] flex-col overflow-hidden rounded border border-rule bg-panel">
      <div className="flex-1 overflow-y-auto scroll-smooth">
        <div className="mx-auto w-full max-w-2xl space-y-4 px-4 py-5">
          {messages === null && <p className="text-small text-ink-faint">Đang tải…</p>}

          {hasHistory && (
            <div className="flex items-center justify-end">
              <button
                type="button"
                onClick={() => void clearHistory()}
                disabled={clearing || busy}
                className={cx(
                  "flex items-center gap-1.5 rounded px-2 py-1 text-small transition-colors",
                  confirmClear
                    ? "bg-alert-tint font-semibold text-alert hover:opacity-90"
                    : "text-ink-muted hover:bg-recess hover:text-ink",
                )}
              >
                <Trash2 size={14} strokeWidth={2} aria-hidden />
                {clearing ? "Đang xoá…" : confirmClear ? "Xoá hẳn?" : "Xoá lịch sử"}
              </button>
            </div>
          )}

          {messages !== null && rows.length === 0 && !busy && (
            <div className="space-y-5">
              <div>
                <h2 className="text-title font-semibold">Tôi có thể giúp gì?</h2>
                <p className="mt-2 max-w-md text-small text-ink-muted">
                  Hỏi về cách dùng TOEIC Pilot, một quy tắc hoạt động ra sao, hoặc tiến độ của chính
                  bạn. Trợ lý chỉ dựa trên trang này, nên câu ngoài phạm vi nó sẽ nói thẳng là không
                  biết.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => {
                      setDraft(suggestion);
                      inputRef.current?.focus();
                    }}
                    className="rounded border border-rule bg-panel px-3 py-2 text-small text-ink-muted transition-colors hover:border-rule-strong hover:bg-recess hover:text-ink"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {older > 0 && (
            <button
              type="button"
              onClick={loadOlder}
              disabled={loadingOlder}
              className="mx-auto block rounded px-3 py-1 text-small text-ink-muted underline underline-offset-4 hover:text-ink disabled:opacity-50"
            >
              {loadingOlder ? "Đang tải…" : `Xem ${older} tin nhắn cũ hơn`}
            </button>
          )}

          {rows.map((message) =>
            message.role === "user" ? (
              <div key={message.id} className="flex justify-end">
                <div className="max-w-[85%] rounded bg-recess px-3.5 py-2 text-body leading-relaxed">
                  <MarkdownLite text={message.content} />
                </div>
              </div>
            ) : (
              <div key={message.id} className="flex items-start gap-2.5">
                <span
                  className="grid h-7 w-7 shrink-0 place-items-center rounded bg-recess text-ink-muted"
                  aria-hidden
                >
                  <Sparkles size={15} strokeWidth={2} />
                </span>
                <div className="min-w-0 flex-1 pt-0.5 text-body leading-relaxed">
                  <MarkdownLite text={message.content} />
                </div>
              </div>
            ),
          )}

          {busy && (
            <div
              className="flex items-start gap-2.5"
              role="status"
              aria-label="Trợ lý đang soạn câu trả lời"
            >
              <span
                className="grid h-7 w-7 shrink-0 place-items-center rounded bg-recess text-ink-muted"
                aria-hidden
              >
                <Sparkles size={15} strokeWidth={2} />
              </span>
              <span className="mt-2 flex items-center gap-1" aria-hidden>
                <span className="chat-dot h-1.5 w-1.5 rounded-full bg-ink-muted" />
                <span className="chat-dot h-1.5 w-1.5 rounded-full bg-ink-muted" />
                <span className="chat-dot h-1.5 w-1.5 rounded-full bg-ink-muted" />
              </span>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {error && <p className="mx-auto w-full max-w-2xl px-4 pb-2 text-small text-alert">{error}</p>}

      <form
        className="border-t border-rule p-3"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <div className="mx-auto flex max-w-2xl items-end gap-2 rounded border border-rule-strong bg-panel p-2">
          <textarea
            value={draft}
            ref={inputRef}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.nativeEvent.isComposing) return;
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send();
              }
            }}
            rows={1}
            placeholder="Hỏi về TOEIC Pilot…"
            aria-label="Câu hỏi cho trợ lý"
            className="max-h-24 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-body text-ink placeholder:text-ink-faint"
          />
          <button
            type="submit"
            disabled={busy || draft.trim() === ""}
            aria-label="Gửi câu hỏi"
            className={cx(
              "grid h-9 w-9 shrink-0 place-items-center rounded transition-opacity",
              busy || draft.trim() === ""
                ? "cursor-not-allowed bg-recess text-ink-faint"
                : "ai-fill hover:opacity-90",
            )}
          >
            <Send size={15} strokeWidth={2} aria-hidden />
          </button>
        </div>
      </form>
    </div>
  );
}
