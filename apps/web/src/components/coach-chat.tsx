"use client";

import { API_ROUTES } from "@toeic-pilot/shared";
import { MessageCircle, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";

type Message = { id: string; role: string; content: string };
type Turn = { conversation_id: string; question: Message; answer: Message };

/**
 * Hộp hỏi đáp dính góc dưới, NEO vào lượt làm bài đang xem.
 *
 * Vì sao là hộp dính chứ không phải một màn riêng: máy chủ neo cuộc trò chuyện
 * vào một lượt làm bài, và ngữ cảnh đến từ chính lượt đó. Một màn độc lập sẽ
 * không có gì để neo — nó phải bỏ neo (thứ ta cố ý không làm khi chưa có ngữ
 * liệu cho RAG) hoặc thêm một bước chọn lượt, tức là màn xem lại với nhiều thao
 * tác hơn. Màn riêng là hình dạng đúng SAU khi có RAG.
 *
 * Khác với nút "AI Explain" trên từng câu: chỗ này trả lời câu hỏi về CẢ BÀI
 * ("tôi yếu phần nào"), thứ mà một lời giải cho một câu không trả lời được.
 */
export function CoachChat({ attemptId, token }: { attemptId: string; token: string | null }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Chỉ nạp lịch sử khi người dùng thật sự mở hộp. Nạp sẵn cho mọi lượt xem lại
  // là một lượt đi mạng cho một hộp phần lớn người không mở.
  useEffect(() => {
    if (!open || loaded || !token) return;
    let cancelled = false;
    async function load(bearer: string) {
      const rows = await apiFetch<Message[]>(`${API_ROUTES.coachChat(attemptId)}`, {
        token: bearer,
      });
      if (cancelled) return;
      setMessages(rows);
      setLoaded(true);
    }
    load(token).catch(() => setLoaded(true));
    return () => {
      cancelled = true;
    };
  }, [open, loaded, token, attemptId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, busy]);

  async function send() {
    const text = draft.trim();
    if (!text || !token || busy) return;

    /*
     * Hiện tin nhắn của người dùng NGAY, trước khi gọi máy chủ.
     *
     * Đây là khác biệt lớn nhất giữa một hộp chat thật và một biểu mẫu: chờ
     * round-trip rồi mới vẽ nghĩa là người ta gõ xong, bấm gửi, và màn hình
     * không đổi gì trong nhiều giây — cảm giác đầu tiên là "nó có nhận không".
     *
     * Id tạm mang tiền tố `pending:` để phân biệt với id thật của máy chủ, và
     * bị thay bằng bản thật khi phản hồi tới. Không có tiền tố thì một lần trùng
     * id sẽ khiến React tái dùng nhầm node.
     */
    const optimisticId = `pending:${Date.now()}`;
    setMessages((rows) => [...rows, { id: optimisticId, role: "user", content: text }]);
    setDraft("");
    setBusy(true);
    setError(null);

    try {
      const turn = await apiFetch<Turn>(API_ROUTES.coachChat(attemptId), {
        method: "POST",
        token,
        body: JSON.stringify({ message: text }),
      });
      setMessages((rows) => [
        ...rows.filter((row) => row.id !== optimisticId),
        turn.question,
        turn.answer,
      ]);
    } catch (caught) {
      // Gỡ tin nhắn lạc quan và TRẢ CHỮ LẠI ô nhập. Để nó nằm lại trong danh
      // sách sẽ là một lời nói dối: nó chưa bao giờ tới máy chủ.
      setMessages((rows) => rows.filter((row) => row.id !== optimisticId));
      setDraft(text);
      setError(caught instanceof Error ? caught.message : "Chưa gửi được câu hỏi");
    } finally {
      setBusy(false);
    }
  }

  if (!token) return null;

  if (!open) {
    return (
      <span className="ai-border fixed bottom-5 right-5 z-40 inline-flex">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="ai-fill inline-flex items-center gap-2 rounded px-3.5 py-2.5 text-small font-semibold transition-opacity hover:opacity-90"
        >
          <MessageCircle size={16} strokeWidth={2} aria-hidden />
          Hỏi trợ giảng
        </button>
      </span>
    );
  }

  return (
    /*
     * `shadow-overlay` là MỘT trong ba ngoại lệ của luật cấm đổ bóng (§6.3):
     * đây là lớp phủ thật, nằm đè lên nội dung chứ không nằm cạnh, nên chỉ một
     * đường viền là không đủ để tách nó ra.
     */
    <div className="ai-border fixed bottom-5 right-5 z-40 w-[min(24rem,calc(100vw-2.5rem))]">
      <div className="shadow-overlay flex max-h-[min(32rem,70vh)] flex-col rounded bg-panel">
        <div className="flex items-center justify-between gap-2 border-b border-rule px-4 py-2.5">
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
            Trợ giảng · hỏi về bài này
          </p>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Đóng hộp trò chuyện"
            className="rounded p-1 text-ink-muted transition-colors hover:bg-recess hover:text-ink"
          >
            <X size={15} strokeWidth={2} aria-hidden />
          </button>
        </div>

        {/* `scroll-smooth` là CSS, không phải tuỳ chọn của `scrollIntoView` —
            nên nó được khối `prefers-reduced-motion` sẵn có ở globals.css tắt
            giúp, thay vì phải thêm một phép kiểm `matchMedia` thứ hai mà ai đó
            sẽ quên đồng bộ. */}
        <div className="flex-1 space-y-3 overflow-y-auto scroll-smooth px-4 py-3">
          {messages.length === 0 && !busy && (
            <p className="text-small text-ink-muted">
              {/*
               * Nói rõ PHẠM VI ngay từ đầu. Trợ giảng chỉ dựa vào bài vừa làm,
               * và một người hỏi "thì hiện tại hoàn thành là gì" rồi nhận "tôi
               * chưa có thông tin đó" sẽ nghĩ là hỏng — trừ khi đã được báo trước.
               */}
              Hỏi về bài vừa làm: câu nào sai, sai vì sao, nên ôn phần nào. Trợ giảng chỉ dựa vào
              bài này nên chưa trả lời được câu hỏi ngoài phạm vi đó.
            </p>
          )}
          {messages.map((message) => (
            <div
              key={message.id}
              className={cx(
                "max-w-[85%] rounded px-3 py-2 text-small leading-relaxed",
                message.role === "user" ? "ml-auto bg-recess" : "border border-rule bg-panel",
              )}
            >
              {message.content}
            </div>
          ))}
          {busy && (
            <div
              className="w-fit rounded border border-rule bg-panel px-3 py-2.5"
              role="status"
              aria-label="Trợ giảng đang soạn câu trả lời"
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
            onChange={(event) => {
              setDraft(event.target.value);
              // Tự giãn theo nội dung: một ô một dòng buộc người ta cuộn trong
              // chính thứ họ đang gõ.
              const el = event.target;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 96)}px`;
            }}
            onKeyDown={(event) => {
              // Enter gửi, Shift+Enter xuống dòng — quy ước của mọi hộp chat.
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send();
              }
            }}
            rows={1}
            placeholder="Hỏi về bài vừa làm…"
            aria-label="Câu hỏi cho trợ giảng"
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
    </div>
  );
}
