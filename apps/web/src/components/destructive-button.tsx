"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui";

/**
 * Nút xoá cần bấm hai lần.
 *
 * Không dùng `window.confirm`: hộp thoại của trình duyệt chặn toàn bộ trang,
 * không nhận được kiểu chữ của hệ thiết kế, và nói bằng giọng của trình duyệt
 * chứ không phải của sản phẩm. Bước xác nhận ngay tại chỗ nói rõ cái gì sắp mất
 * và cái gì thì không — thứ mà một hộp thoại "Bạn có chắc không?" không nói
 * được.
 *
 * Tự trở về trạng thái đầu khi rê chuột ra, nên một cú bấm nhầm không để lại
 * một nút xoá đang lên nòng ở đó.
 */
export function DestructiveButton({
  label,
  confirmLabel,
  onConfirm,
  disabled,
  title,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  disabled?: boolean;
  title?: string;
}) {
  const [armed, setArmed] = useState(false);

  if (!armed) {
    return (
      <Button
        size="sm"
        variant="quiet"
        disabled={disabled}
        title={title ?? label}
        onClick={() => setArmed(true)}
      >
        <Trash2 size={14} strokeWidth={2} aria-hidden />
        {label}
      </Button>
    );
  }

  return (
    <span className="inline-flex items-center gap-1" onMouseLeave={() => setArmed(false)}>
      <Button
        size="sm"
        variant="destructive"
        onClick={() => {
          setArmed(false);
          onConfirm();
        }}
      >
        {confirmLabel}
      </Button>
      <Button size="sm" variant="quiet" onClick={() => setArmed(false)}>
        Huỷ
      </Button>
    </span>
  );
}
