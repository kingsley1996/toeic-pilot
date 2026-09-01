"use client";

import { Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { Button, FieldError, Field, Input } from "@/components/ui";

/**
 * Tải ảnh lên ngay tại chỗ nó thuộc về.
 *
 * Không có thư viện ảnh để chọn: quá vài trăm ảnh thì thứ duy nhất phân biệt hai
 * mục là phần đuôi của `storage_key`, nên chọn nhầm sẽ THÀNH CÔNG, im lặng, và
 * đưa cho người học một bức ảnh không ai viết câu hỏi cho.
 */

/**
 * Tải một bức ảnh lên NGAY TẠI Ô nó thuộc về.
 *
 * Thay cho luồng cũ: tải lên một thư viện chung rồi quay lại chọn từ dropdown.
 * Dropdown đó hỏng theo số lượng — hai chục ảnh là còn tìm được, hai trăm thì
 * nhãn duy nhất phân biệt được chúng là mười hai ký tự cuối của `storage_key`,
 * và chọn nhầm ảnh **khớp thành công**, không có gì báo.
 *
 * Xuất xứ (nguồn, giấy phép, ghi công) khai một lần ở đầu trang cho cả lô, vì
 * một bộ đề thường lấy ảnh từ cùng một nguồn. `alt_text` thì ở đây, vì nó mô tả
 * riêng bức này.
 */
export function ImageUpload({
  busy,
  hasImage,
  needsAlt,
  blocked,
  onUpload,
  onRemove,
}: {
  busy: boolean;
  hasImage: boolean;
  needsAlt: boolean;
  /** Lý do chưa tải lên được, hoặc null. Xem `send`. */
  blocked: string | null;
  onUpload: (file: File, alt: string | null) => Promise<string | null>;
  onRemove: () => Promise<string | null>;
}) {
  const [alt, setAlt] = useState("");
  const [refusal, setRefusal] = useState<string | null>(null);

  async function send(file: File) {
    // Chặn TRƯỚC khi tải lên, không phải sau. Bước xác nhận từ chối thiếu xuất
    // xứ bằng 422, nhưng lúc đó file đã nằm trên Cloudinary rồi — và nó ở lại
    // đó, không ai trỏ tới, không ai biết để dọn.
    //
    // Luật này đã áp cho chữ thay ảnh ngay từ đầu; không áp cho xuất xứ là một
    // chỗ sót, và nó nổ ngay lần tải ảnh Part 1 đầu tiên.
    if (blocked) {
      setRefusal(blocked);
      return;
    }
    if (needsAlt && !alt.trim()) {
      setRefusal("Cần chữ thay ảnh trước khi tải lên.");
      return;
    }
    setRefusal(await onUpload(file, alt.trim() || null));
  }

  return (
    <div className="mt-2">
      {needsAlt && (
        <Field label="Chữ thay ảnh" hint="Mô tả nội dung hình. Bắt buộc.">
          <Input value={alt} onChange={(event) => setAlt(event.target.value)} />
        </Field>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-3">
        <label className="inline-flex cursor-pointer items-center gap-2 text-small font-semibold text-action-ink">
          <Upload size={14} strokeWidth={2} aria-hidden />
          {hasImage ? "Thay ảnh" : "Tải ảnh lên"}
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
            disabled={busy}
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              // Xoá giá trị để chọn LẠI cùng một file vẫn kích hoạt onChange —
              // thứ người ta làm ngay sau một lần tải lên thất bại.
              event.target.value = "";
              if (file) void send(file);
            }}
          />
        </label>

        {hasImage && (
          <Button
            size="sm"
            variant="quiet"
            onClick={async () => setRefusal(await onRemove())}
            disabled={busy}
          >
            <Trash2 size={14} strokeWidth={1.75} aria-hidden />
            Gỡ ảnh
          </Button>
        )}
      </div>

      {refusal && <FieldError>{refusal}</FieldError>}
    </div>
  );
}
