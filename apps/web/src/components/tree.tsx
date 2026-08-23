"use client";

import { Check, Pencil, Plus, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { Button, Input, cx } from "@/components/ui";

/**
 * Cây nội dung của khu quản trị — dùng chung cho cả ba cây: từ vựng
 * (tuyển tập → cuốn sách → chủ đề), dictation (chủ đề → phần → bài) và đề thi
 * (bộ đề → đề).
 *
 * Ba cây từng được dựng ba kiểu. Hai trong ba không phải là cây: chúng in ba
 * DANH SÁCH PHẲNG chồng lên nhau, mỗi hàng con mang theo tên cha ở đầu dòng như
 * một mẩu breadcrumb ("Short stories / Unit 1 /"). Cách đó đọc được khi có một
 * chủ đề, và hỏng ngay khi có ba: quan hệ cha–con phải tự ghép lại trong đầu
 * người đọc, thứ tự các nhóm không tồn tại, và một cuốn sách rỗng thì không xuất
 * hiện ở đâu cả — nó chỉ vắng mặt trong danh sách bên dưới, mà vắng mặt thì
 * không nhìn thấy được.
 *
 * Nên quan hệ ở đây do BỐ CỤC nói, không do chữ nói: con nằm trong hộp của cha,
 * thụt vào sau một đường kẻ dọc. Không cần in tên cha nữa, và một nhánh rỗng
 * vẫn là một nhánh nhìn thấy được.
 */

/**
 * Bề mặt theo tầng.
 *
 * Ba tầng phân biệt bằng NỀN và VIỀN chứ không bằng bóng đổ hay bo góc — hệ
 * thiết kế chỉ có một bán kính 4px và cấm `box-shadow` (§6.3). Tầng ngoài là
 * bề mặt nổi, tầng giữa là bậc lõm, tầng trong không có khung riêng và dựa hẳn
 * vào đường kẻ thụt đầu dòng của cha.
 */
const SURFACE: Record<number, string> = {
  0: "rounded border border-rule bg-panel px-4 py-3",
  1: "rounded border border-rule bg-recess px-3 py-2.5",
  2: "rounded px-3 py-2 transition-colors hover:bg-recess",
};

export function TreeNode({
  level = 0,
  icon: Icon,
  name,
  meta,
  actions,
  children,
  className,
}: {
  /** 0 = gốc. Chỉ quyết định bề mặt; quan hệ do lồng nhau nói. */
  level?: 0 | 1 | 2;
  icon?: LucideIcon;
  /** Tên nút — thường là `<InlineRename/>`. */
  name: ReactNode;
  /** Slug, số đếm, nhãn trạng thái. */
  meta?: ReactNode;
  /** Xuất bản, xoá, thêm con. Dồn về phải. */
  actions?: ReactNode;
  /** Các nút con, kể cả ô "thêm". */
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx(SURFACE[level], className)}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {Icon && (
          <Icon size={15} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
        )}
        {name}
        {meta}
        {actions && <span className="ml-auto flex flex-wrap items-center gap-1.5">{actions}</span>}
      </div>
      {/* Đường kẻ dọc là thứ DUY NHẤT nói "những hàng này thuộc hàng trên". Bỏ
          nó đi thì ở tầng 2 — tầng không có khung riêng — con và cháu trông
          như hai hàng ngang cấp. */}
      {children && <div className="mt-2.5 space-y-1.5 border-l-2 border-rule pl-3">{children}</div>}
    </div>
  );
}

/** Một nhánh rỗng vẫn phải nói ra là nó rỗng, nếu không nó chỉ đơn giản vắng mặt. */
export function TreeEmpty({ children }: { children: ReactNode }) {
  return <p className="px-3 py-1.5 text-small text-ink-faint">{children}</p>;
}

/**
 * Đổi tên tại chỗ.
 *
 * Bản nháp nằm ở ĐÂY chứ không ở trang: hai cây trước kia giữ `editing` trong
 * state của trang, mà `NameCell` lại được khai báo bên trong thân component
 * cha — nên mỗi phím gõ là một kiểu component mới, React tháo ô nhập ra rồi
 * dựng lại. Nó "chạy" nhờ `autoFocus` bắt lại con trỏ mỗi lần, nhưng bộ gõ
 * tiếng Việt thì mất chuỗi ghép chữ giữa chừng, và cái đó không có gì báo.
 */
export function InlineRename({
  value,
  onSave,
  disabled,
  editLabel = "Sửa tên",
  saveLabel = "Lưu tên",
  cancelLabel = "Huỷ sửa",
  className,
}: {
  value: string;
  onSave: (next: string) => void;
  disabled?: boolean;
  editLabel?: string;
  saveLabel?: string;
  cancelLabel?: string;
  className?: string;
}) {
  const [draft, setDraft] = useState<string | null>(null);

  if (draft === null) {
    return (
      <span className={cx("flex min-w-0 items-center gap-1", className)}>
        <span className="truncate font-semibold">{value}</span>
        <Button
          size="sm"
          variant="quiet"
          disabled={disabled}
          aria-label={`${editLabel}: ${value}`}
          title={editLabel}
          onClick={() => setDraft(value)}
        >
          <Pencil size={13} strokeWidth={2} aria-hidden />
        </Button>
      </span>
    );
  }

  return (
    <span className={cx("flex min-w-0 flex-1 items-center gap-1", className)}>
      <Input
        value={draft}
        autoFocus
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          // Bỏ qua Enter khi bộ gõ đang ghép chữ: với Telex/VNI, Enter giữa
          // chừng một từ là phím XÁC NHẬN của bộ gõ chứ không phải phím lưu.
          if (e.nativeEvent.isComposing) return;
          if (e.key === "Enter" && draft.trim()) {
            onSave(draft.trim());
            setDraft(null);
          }
          if (e.key === "Escape") setDraft(null);
        }}
        className="max-w-xs"
      />
      <Button
        size="sm"
        aria-label={saveLabel}
        disabled={!draft.trim()}
        onClick={() => {
          onSave(draft.trim());
          setDraft(null);
        }}
      >
        <Check size={13} strokeWidth={2} aria-hidden />
      </Button>
      <Button size="sm" variant="quiet" aria-label={cancelLabel} onClick={() => setDraft(null)}>
        <X size={13} strokeWidth={2} aria-hidden />
      </Button>
    </span>
  );
}

export type AddField = { name: string; placeholder: string; className?: string };

/**
 * Ô "thêm một nút con", đặt ngay trong nhánh mà nó thêm vào.
 *
 * Trước kia mỗi tầng có một form riêng ở đầu trang, kèm một `<select>` "thuộc
 * chủ đề nào". Cái `<select>` đó là hệ quả của việc form đứng tách khỏi cây:
 * nó bắt người dùng nhắc lại bằng lời một thứ mà chỗ đứng đã nói rồi. Ở trong
 * nhánh thì cha là chỗ đang bấm, nên không còn gì để chọn — và không còn cách
 * nào chọn nhầm.
 */
export function AddChild({
  label,
  fields,
  onSubmit,
  disabled,
  submitLabel = "Thêm",
  cancelLabel = "Huỷ",
}: {
  label: string;
  fields: AddField[];
  onSubmit: (values: Record<string, string>) => void;
  disabled?: boolean;
  submitLabel?: string;
  cancelLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});

  const ready = fields.every((field) => (values[field.name] ?? "").trim() !== "");

  function submit() {
    if (!ready) return;
    onSubmit(
      Object.fromEntries(fields.map((field) => [field.name, (values[field.name] ?? "").trim()])),
    );
    setValues({});
    setOpen(false);
  }

  if (!open) {
    return (
      <Button size="sm" variant="quiet" disabled={disabled} onClick={() => setOpen(true)}>
        <Plus size={13} strokeWidth={2} aria-hidden />
        {label}
      </Button>
    );
  }

  return (
    <span className="flex flex-1 flex-wrap items-center gap-1.5">
      {fields.map((field) => (
        <Input
          key={field.name}
          autoFocus={field === fields[0]}
          value={values[field.name] ?? ""}
          placeholder={field.placeholder}
          aria-label={field.placeholder}
          onChange={(e) => setValues({ ...values, [field.name]: e.target.value })}
          onKeyDown={(e) => {
            if (e.nativeEvent.isComposing) return;
            if (e.key === "Enter") submit();
            if (e.key === "Escape") setOpen(false);
          }}
          className={field.className ?? "max-w-xs"}
        />
      ))}
      <Button size="sm" disabled={!ready} onClick={submit}>
        {submitLabel}
      </Button>
      <Button
        size="sm"
        variant="quiet"
        onClick={() => {
          setValues({});
          setOpen(false);
        }}
      >
        {cancelLabel}
      </Button>
    </span>
  );
}
