"use client";

import { CircleCheck, Info, OctagonAlert, TriangleAlert, X, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { cx } from "@/components/ui";
import type { Toast, ToastTone } from "@/lib/toast";

/**
 * Chỗ đứng của hàng thông báo tạm, và hình dạng của từng thẻ.
 *
 * Chỉ biết vẽ. Quyết định "khi nào nói" nằm ở `lib/toast.tsx`.
 *
 * Ba ràng buộc của hệ thiết kế gặp nhau ở đây:
 *
 *   §6.3  Toast là **lớp phủ thật**, nên nó là một trong ba ngoại lệ được dùng
 *         `box-shadow` — qua utility `.shadow-overlay`, giống modal và menu thả
 *         xuống. Không có nó, một tấm thẻ nổi trên nội dung chỉ có viền sẽ trông
 *         như bị dán vào giữa trang.
 *   §7    Mọi chuyển động ngoài bảng chấm dictation là **fade 120ms**. Không
 *         trượt vào từ bên phải, không nảy. Khối `prefers-reduced-motion` chung
 *         ở `globals.css` rút mọi animation về 0.01ms nên chỗ này không cần khai
 *         báo lại.
 *   §11.3 Không thông tin nào chỉ nằm ở màu: mỗi giọng có icon riêng, y như
 *         `Alert`.
 */

const TONES: Record<ToastTone, { className: string; iconClass: string; Icon: LucideIcon }> = {
  ok: { className: "border-ok/50", iconClass: "bg-ok-tint text-ok", Icon: CircleCheck },
  info: {
    className: "border-rule-strong",
    iconClass: "bg-action-tint text-action-ink",
    Icon: Info,
  },
  warn: { className: "border-warn/50", iconClass: "bg-warn-tint text-warn", Icon: TriangleAlert },
  alert: {
    className: "border-alert/50",
    iconClass: "bg-alert-tint text-alert",
    Icon: OctagonAlert,
  },
};

function ToastCard({
  toast,
  paused,
  onDismiss,
}: {
  toast: Toast;
  paused: boolean;
  onDismiss: (id: string) => void;
}) {
  const tone = TONES[toast.tone];
  /*
   * Thời gian CÒN LẠI, không phải thời điểm hết hạn.
   *
   * Đồng hồ bị tạm dừng khi con trỏ nằm trên hàng thông báo hoặc khi focus rơi
   * vào trong nó, và cái thứ hai mới là cái bắt buộc: một thẻ có đường dẫn mà
   * biến mất giữa lúc người ta đang Tab tới nó thì đường dẫn ấy coi như không
   * tồn tại với người không dùng chuột.
   */
  const remaining = useRef(toast.durationMs ?? 0);
  const startedAt = useRef(0);

  useEffect(() => {
    if (toast.durationMs === null || paused || toast.leaving) return;
    startedAt.current = Date.now();
    const timer = window.setTimeout(() => onDismiss(toast.id), remaining.current);
    return () => {
      window.clearTimeout(timer);
      remaining.current = Math.max(0, remaining.current - (Date.now() - startedAt.current));
    };
  }, [paused, toast.durationMs, toast.leaving, toast.id, onDismiss]);

  const body = (
    <>
      {toast.imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={toast.imageUrl}
          alt=""
          aria-hidden
          className="h-9 w-9 shrink-0 rounded object-contain"
        />
      ) : (
        <span
          aria-hidden
          className={cx("grid h-9 w-9 shrink-0 place-items-center rounded", tone.iconClass)}
        >
          <tone.Icon size={18} strokeWidth={1.75} />
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block font-semibold text-ink">{toast.title}</span>
        {toast.description && (
          <span className="mt-0.5 block text-small text-ink-muted">{toast.description}</span>
        )}
        {toast.href && toast.linkLabel && (
          <span className="mt-1.5 block text-small font-semibold text-action-ink">
            {toast.linkLabel}
          </span>
        )}
      </span>
    </>
  );

  return (
    <div
      className={cx(
        "pointer-events-auto w-full rounded border bg-panel p-3.5",
        "shadow-overlay flex items-start gap-3",
        toast.leaving ? "toast-leave" : "toast-enter",
        tone.className,
      )}
    >
      {toast.href ? (
        <Link href={toast.href} className="flex min-w-0 flex-1 items-start gap-3">
          {body}
        </Link>
      ) : (
        <div className="flex min-w-0 flex-1 items-start gap-3">{body}</div>
      )}
      {/* Luôn đóng được bằng tay. Một thông báo chỉ tự tắt sau vài giây là thứ
          người dùng bàn phím không có cách nào gạt đi khi nó che mất chỗ họ đang
          làm việc. */}
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label={`Đóng thông báo: ${toast.title}`}
        className="-mr-1 -mt-1 grid h-7 w-7 shrink-0 place-items-center rounded text-ink-faint transition-colors hover:bg-recess hover:text-ink"
      >
        <X size={15} strokeWidth={2} aria-hidden />
      </button>
    </div>
  );
}

/**
 * Hộp chứa. **Luôn được dựng, kể cả khi rỗng**, và đó không phải chuyện thẩm mỹ:
 * `aria-live` chỉ đọc những gì được chèn vào một vùng ĐÃ CÓ SẴN trong DOM. Dựng
 * vùng ấy cùng lúc với thẻ đầu tiên thì trình đọc màn hình không đọc gì cả, và
 * cách duy nhất phát hiện là bật trình đọc lên nghe.
 *
 * Hai vùng chứ không phải một, theo đúng cách chuẩn: tin vui đợi người dùng ngắt
 * lời xong (`polite`), còn lỗi thì chen ngang (`assertive`). Nhét cả hai vào một
 * vùng buộc phải chọn một mức cho mọi thứ — `assertive` cho một cái huy hiệu là
 * cắt ngang câu người ta đang nghe để khoe.
 *
 * Góc trên bên phải vì hai góc dưới đã có chủ: thú cưng ở dưới trái, nút trợ lý
 * ở dưới phải (cả hai `z-40`). Chừa `top-[4.5rem]` để không chui xuống dưới
 * header dính.
 */
export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}) {
  const [paused, setPaused] = useState(false);
  const polite = toasts.filter((t) => t.tone !== "alert");
  const loud = toasts.filter((t) => t.tone === "alert");

  const render = (list: Toast[]) =>
    list.map((toast) => (
      <ToastCard key={toast.id} toast={toast} paused={paused} onDismiss={onDismiss} />
    ));

  return (
    <div
      /* `pointer-events-none` ở hộp ngoài, `pointer-events-auto` ở từng thẻ: hộp
         phủ một dải rộng ở góc trên, và nếu nó ăn chuột thì lúc rỗng nó vẫn chặn
         mọi cú bấm vào phần nội dung nằm dưới. */
      className="pointer-events-none fixed inset-x-4 top-[4.5rem] z-50 flex flex-col items-end gap-2 sm:inset-x-auto sm:right-4 sm:w-[22rem]"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
    >
      {/* Hai vùng là hộp flex thật, KHÔNG phải `display: contents`. Cái sau dựng
          đúng y hệt và là cách hiển nhiên để hai vùng dùng chung một cột — nhưng
          `display: contents` gỡ phần tử khỏi cây bố cục, và cây trợ năng của
          trình duyệt đã có tiền sử gỡ luôn cả `role` theo. Một vùng `aria-live`
          không còn là vùng `aria-live` thì hỏng theo kiểu chỉ nghe thấy chứ
          không nhìn thấy. */}
      <div
        className="flex w-full flex-col items-end gap-2"
        role="status"
        aria-live="polite"
        aria-atomic="false"
      >
        {render(polite)}
      </div>
      <div
        className="flex w-full flex-col items-end gap-2"
        role="alert"
        aria-live="assertive"
        aria-atomic="false"
      >
        {render(loud)}
      </div>
    </div>
  );
}
