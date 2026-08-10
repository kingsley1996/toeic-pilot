"use client";

import { API_ROUTES, type ImageAssetPublic } from "@toeic-pilot/shared";
import { ImageIcon, Upload } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import {
  Alert,
  Button,
  EmptyState,
  Field,
  FieldError,
  Input,
  Page,
  PageHeader,
  Panel,
  SectionHeader,
  Skeleton,
  Spinner,
  Tag,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";
import { messageFor, uploadViaTicket } from "@/lib/upload";

/*
 * Thư viện ảnh dùng cho câu hỏi.
 *
 * Có trước trình nhập câu hỏi (Sprint 5) một cách có chủ ý: soạn nội dung là nút
 * thắt thật của dự án, và biên tập viên gom được ảnh từ bây giờ thì tới lúc có
 * trình nhập đã sẵn thư viện để chọn. Ngược lại thì họ phải làm hai việc cùng
 * lúc dưới áp lực thời gian.
 */

export default function AdminMediaPage() {
  const { status, token } = useRequireSession({ canEdit: true });

  const [images, setImages] = useState<ImageAssetPublic[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  // Bộ đếm chứ không phải cờ: hai lần thêm ảnh liên tiếp phải chạy hai lượt
  // đọc. Cùng khuôn với `session.refresh()` — và cùng lý do tránh gọi setState
  // thẳng trong thân effect, thứ mà `react-hooks/set-state-in-effect` chặn.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    apiFetch<ImageAssetPublic[]>(API_ROUTES.adminImages, { token })
      .then((rows) => {
        if (!cancelled) setImages(rows);
      })
      .catch(() => {
        /* danh sách hỏng không được chặn đường thêm ảnh mới */
      });
    return () => {
      cancelled = true;
    };
  }, [token, reloadKey]);

  const onSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!token || !pending) return;
      const data = new FormData(event.currentTarget);
      setError(null);
      setNote(null);
      setBusy(true);

      try {
        // (1)(3) xin vé rồi tải thẳng lên nhà cung cấp — file không qua API.
        const { storageKey } = await uploadViaTicket(API_ROUTES.adminImageTicket, pending, token);
        // (4) xác nhận: máy chủ hỏi lại nhà cung cấp rồi mới ghi hàng asset.
        await apiFetch(API_ROUTES.adminImageConfirm, {
          method: "POST",
          token,
          body: JSON.stringify({
            storage_key: storageKey,
            source_url: String(data.get("source_url")),
            license: String(data.get("license")),
            attribution: String(data.get("attribution")),
            alt_text: String(data.get("alt_text") || "") || null,
          }),
        });
        formRef.current?.reset();
        setPending(null);
        if (fileInput.current) fileInput.current.value = "";
        setNote("Đã thêm ảnh vào thư viện.");
        setReloadKey((key) => key + 1);
      } catch (err) {
        setError(messageFor(err, "Không thêm được ảnh."));
      } finally {
        setBusy(false);
      }
    },
    [token, pending],
  );

  if (status !== "authenticated") {
    return (
      <Page>
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-6 h-64 w-full" />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Nội dung"
        title="Thư viện ảnh"
        description="Ảnh dùng cho câu hỏi Part 1. Mỗi ảnh phải kèm nguồn và giấy phép."
      />

      <section>
        <SectionHeader title="Thêm ảnh" />
        <Panel className="p-5 sm:p-6">
          <form ref={formRef} onSubmit={onSubmit} className="space-y-5" noValidate>
            <Field
              label="Tệp ảnh"
              hint="JPG, PNG hoặc WebP, tối đa 8MB. Ảnh sẽ được thu nhỏ về tối đa 2000px và xoá sạch metadata."
            >
              <input
                ref={fileInput}
                type="file"
                required
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => setPending(event.target.files?.[0] ?? null)}
                className="w-full rounded border border-rule-strong bg-panel px-3 py-2 text-body file:mr-3 file:rounded file:border-0 file:bg-recess file:px-3 file:py-1 file:text-small file:font-semibold file:text-ink"
              />
            </Field>

            {/*
             * Ba trường bản quyền là bắt buộc, khớp ba cột NOT NULL trên
             * `image_asset`. ADR-004 §2: phần lớn ảnh mở là CC-BY — dùng được
             * *với điều kiện* ghi công — và điều đó chỉ ghi lại trung thực được
             * vào đúng lúc thêm ảnh, khi trang nguồn còn đang mở.
             */}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Nguồn" hint="Trang gốc của ảnh, hoặc nơi bạn lưu bản gốc.">
                <Input name="source_url" required placeholder="https://…" />
              </Field>
              <Field label="Giấy phép" hint="Ví dụ: CC-BY-4.0, CC0-1.0, hoặc 'Tự chụp'.">
                <Input name="license" required placeholder="CC-BY-4.0" />
              </Field>
            </div>
            <Field label="Ghi công" hint="Tên tác giả và cách họ muốn được ghi tên.">
              <Input name="attribution" required placeholder="Ảnh: Nguyễn Văn A" />
            </Field>
            <Field
              label="Mô tả cho trình đọc màn hình"
              hint="Mô tả cảnh, KHÔNG tiết lộ đáp án — một chú thích nói ra câu nào đúng sẽ làm câu hỏi mất giá trị với mọi người."
            >
              <Input name="alt_text" placeholder="Hai người đang xem tài liệu trong văn phòng" />
            </Field>

            {error && <FieldError>{error}</FieldError>}
            {note && !error && <Alert tone="ok">{note}</Alert>}

            <Button type="submit" disabled={busy || !pending}>
              {busy ? <Spinner /> : <Upload size={15} strokeWidth={2} aria-hidden />}
              {busy ? "Đang tải lên…" : "Thêm vào thư viện"}
            </Button>
          </form>
        </Panel>
      </section>

      <section className="mt-10">
        <SectionHeader
          title="Đã có"
          aside={
            images ? (
              <span className="font-data text-small text-ink-muted">{images.length} ảnh</span>
            ) : undefined
          }
        />
        {images === null ? (
          <Skeleton className="h-40 w-full" />
        ) : images.length === 0 ? (
          <EmptyState
            icon={ImageIcon}
            title="Chưa có ảnh nào"
            description="Thêm ảnh đầu tiên ở trên. Part 1 cần một ảnh cho mỗi câu hỏi."
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {images.map((image) => (
              <Panel key={image.id} className="overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={image.url}
                  alt={image.alt_text ?? ""}
                  className="h-40 w-full border-b border-rule object-cover"
                />
                <div className="p-3">
                  <div className="flex items-center justify-between gap-2">
                    <Tag tone={image.source === "uploaded" ? "action" : "neutral"}>
                      {image.source}
                    </Tag>
                    <span className="font-data text-label text-ink-faint">
                      {image.width}×{image.height}
                    </span>
                  </div>
                  {/* Ghi công phải HIỆN RA, không chỉ được lưu: lưu mà không
                      hiện vẫn là vi phạm giấy phép (ADR-004 §4.2). */}
                  <p className="mt-2 line-clamp-2 text-small text-ink-muted">{image.attribution}</p>
                  <p className="mt-0.5 font-data text-label text-ink-faint">{image.license}</p>
                </div>
              </Panel>
            ))}
          </div>
        )}
      </section>
    </Page>
  );
}
