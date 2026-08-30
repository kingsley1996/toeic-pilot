"use client";

import {
  API_ROUTES,
  type ChatHistoryPage,
  type ChatMessagePublic,
  type ChatTurn,
} from "@toeic-pilot/shared";
import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cx } from "@/components/ui";
import { MarkdownLite } from "@/components/markdown-lite";
import { apiFetch } from "@/lib/api";

// Hình dạng phản hồi đến TỪ HỢP ĐỒNG, không gõ tay lại. `apiFetch<T>` nhận
// kiểu từ nơi gọi, nên một shape tự khai làm mọi thay đổi ở API trở nên vô
// hình với `tsc` — đúng cái bẫy CLAUDE.md ghi cho sáu endpoint đổi sang Page.
type Message = ChatMessagePublic;

/**
 * Màn hỏi đáp của Trợ lý trang web — khác hộp "Hỏi trợ giảng" ở NƠI SỐNG:
 *
 * - Trợ giảng neo vào một lượt làm bài, nên nó là hộp dính góc trên màn xem lại.
 *   Trợ lý nói về cả trang web và tiến độ người học, không neo vào đâu, nên nó
 *   có một màn riêng và nạp lịch sử NGAY khi mở — không có lý do gì để chờ một
 *   cú bấm mới hỏi máy chủ "có chuyện gì đang dở không".
 *
 * Các quyết định UI giữ nguyên từ `coach-chat.tsx`: tin nhắn hiện lạc quan trước
 * khi máy chủ trả lời, gỡ và TRẢ LẠI ô nhập khi gửi hỏng, chiều cao ô nhập bám
 * theo `draft` trong effect chứ không trong `onChange`, và `isComposing` chặn
 * Enter giữa chừng một từ tiếng Việt.
 */
export function AssistantChat({ token }: { token: string | null }) {
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Số tin nhắn cũ hơn còn nằm ngoài trang đầu — 0 nghĩa là đã thấy hết.
  const [older, setOlder] = useState(0);
  const [loadingOlder, setLoadingOlder] = useState(false);
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

  return (
    <div className="flex h-[min(70vh,40rem)] flex-col rounded border border-rule-strong bg-panel">
      <div className="flex-1 space-y-3 overflow-y-auto scroll-smooth px-4 py-3">
        {messages === null && <p className="text-small text-ink-faint">Đang tải…</p>}
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
        {messages !== null && rows.length === 0 && !busy && (
          <p className="text-small text-ink-muted">
            Hỏi bất cứ điều gì về TOEIC Pilot: tính năng nào ở đâu, một quy tắc hoạt động ra sao,
            hoặc tiến độ của chính bạn. Trợ lý chỉ dựa trên trang này, nên câu ngoài phạm vi nó sẽ
            nói thẳng là không biết.
          </p>
        )}
        {rows.map((message) => (
          <div
            key={message.id}
            className={cx(
              "max-w-[85%] rounded px-3 py-2 text-small leading-relaxed",
              message.role === "user" ? "ml-auto bg-recess" : "border border-rule bg-panel",
            )}
          >
            <MarkdownLite text={message.content} />
          </div>
        ))}
        {busy && (
          <div
            className="w-fit rounded border border-rule bg-panel px-3 py-2.5"
            role="status"
            aria-label="Trợ lý đang soạn câu trả lời"
          >
            <span className="flex items-center gap-1" aria-hidden>
              <span className="chat-dot h-1.5 w-1.5 rounded-full bg-ink-muted" />
              <span className="chat-dot h-1.5 w-1.5 rounded-full bg-ink-muted" />
              <span className="chat-dot h-1.5 w-1.5 rounded-full bg-ink-muted" />
            </span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error && <p className="px-4 pb-2 text-small text-alert">{error}</p>}

      <form
        className="flex items-end gap-2 border-t border-rule px-3 py-2.5"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
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
          className="max-h-24 min-h-9 flex-1 resize-none rounded border border-rule-strong bg-panel px-3 py-2 text-small text-ink placeholder:text-ink-faint"
        />
        <button
          type="submit"
          disabled={busy || draft.trim() === ""}
          aria-label="Gửi câu hỏi"
          className="ai-fill grid h-9 w-9 shrink-0 place-items-center rounded transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45"
        >
          <Send size={15} strokeWidth={2} aria-hidden />
        </button>
      </form>
    </div>
  );
}
