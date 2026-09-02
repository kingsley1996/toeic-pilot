"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { IconButton } from "@/components/ui";

/**
 * Hộp thoại, dựng trên `<dialog>` gốc của trình duyệt.
 *
 * Dùng phần tử thật chứ không phải một `div` có `position: fixed`, vì `<dialog>`
 * đã có sẵn ba thứ mà bản tự viết hầu như luôn thiếu: bẫy tiêu điểm (Tab không
 * chạy ra sau lớp phủ), Escape để đóng, và `inert` cho phần còn lại của trang
 * đối với trình đọc màn hình. Tự làm lại ba thứ đó là cách chắc chắn nhất để
 * làm hỏng chúng.
 *
 * Nằm ở file riêng chứ không nhét vào `ui.tsx`: file đó không khai `use client`
 * nên vẫn dùng được từ phía máy chủ, và thêm hook vào đó sẽ kéo cả bộ primitive
 * sang phía client.
 *
 * Đổ bóng là MỘT trong ba ngoại lệ của luật cấm `box-shadow` (§6.3) — lớp phủ
 * thật nằm đè lên nội dung, nên viền thôi không đủ tách nó ra.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    // `showModal()` là thứ bật bẫy tiêu điểm và lớp `::backdrop`; đặt thuộc tính
    // `open` bằng tay thì được một hộp thoại KHÔNG modal, trông giống hệt nhưng
    // Tab vẫn chạy ra sau nó.
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    /*
     * Gắn TRỰC TIẾP bằng `addEventListener`, không dùng prop `onCancel` của
     * React.
     *
     * `cancel` của `<dialog>` KHÔNG nổi bọt, mà React lại gắn phần lớn trình xử
     * lý ở gốc cây và dựa vào nổi bọt để phân phát. Viết `onCancel={...}` nên
     * trông đúng, biên dịch trót lọt, và im lặng không bao giờ chạy — Escape sẽ
     * đóng hộp thoại ở tầng trình duyệt trong khi state React vẫn tưởng nó đang
     * mở, và lần bấm sửa kế tiếp không mở ra được gì cả.
     *
     * `preventDefault` để việc đóng đi qua React chứ không đi vòng qua nó, giữ
     * cho phần tử DOM và state luôn nói cùng một điều.
     */
    function onCancel(event: Event) {
      event.preventDefault();
      onClose();
    }

    // Phần tử `<dialog>` phủ kín cả vùng backdrop, nên bấm ra nền sẽ báo target
    // chính là nó. Bấm vào bên trong báo target là phần tử con.
    function onClick(event: MouseEvent) {
      if (event.target === dialog) onClose();
    }

    dialog.addEventListener("cancel", onCancel);
    dialog.addEventListener("click", onClick);
    return () => {
      dialog.removeEventListener("cancel", onCancel);
      dialog.removeEventListener("click", onClick);
    };
    // Gắn lại khi `onClose` đổi danh tính. Rẻ, và tránh phải ghi vào ref trong
    // thân render — thứ mà `react-hooks/refs` chặn, vì một ref đọc lúc render
    // không kích hoạt lượt render mới và sẽ âm thầm lệch pha.
  }, [onClose]);

  return (
    <dialog
      ref={ref}
      className="shadow-overlay w-[min(34rem,calc(100vw-2rem))] rounded border border-rule-strong bg-panel p-0 text-ink backdrop:bg-black/50"
    >
      <div className="flex items-start justify-between gap-4 border-b border-rule px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-subtitle leading-tight">{title}</h2>
          {description && <p className="mt-1 text-small text-ink-muted">{description}</p>}
        </div>
        <IconButton icon={X} aria-label="Đóng" onClick={onClose} />
      </div>
      <div className="px-5 py-5">{children}</div>
    </dialog>
  );
}
