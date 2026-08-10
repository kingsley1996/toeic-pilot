import { API_ROUTES, type UploadTicket } from "@toeic-pilot/shared";

import { ApiError, apiFetch } from "@/lib/api";

/*
 * Ba bước phía trình duyệt của luồng upload (ADR-006 §2.3).
 *
 * Bước POST file đi THẲNG tới nhà cung cấp và cố ý KHÔNG dùng `apiFetch`: hàm
 * đó gắn `Content-Type: application/json` và token của ta vào mọi request, mà
 * cả hai đều sai ở đây — Cloudinary cần multipart do trình duyệt tự đặt kèm
 * boundary, và gửi token của mình sang máy chủ bên thứ ba là rò rỉ.
 */

export type UploadOutcome = { storageKey: string };

/** Lỗi ở bước tải lên nhà cung cấp, tách khỏi lỗi của API mình. */
export class UploadError extends Error {}

async function putToProvider(ticket: UploadTicket, file: File): Promise<void> {
  const form = new FormData();
  // Mọi trường trong vé đều đã nằm trong chữ ký. Sửa bất kỳ giá trị nào — kể cả
  // thêm một trường — cũng làm chữ ký hỏng, và đó là điều mong muốn.
  for (const [key, value] of Object.entries(ticket.fields)) form.append(key, value);
  form.append("file", file);

  const response = await fetch(ticket.upload_url, { method: "POST", body: form });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      if (body.error?.message) detail = body.error.message;
    } catch {
      /* nhà cung cấp không phải lúc nào cũng trả JSON */
    }
    throw new UploadError(detail);
  }
}

function checkBeforeSending(ticket: UploadTicket, file: File): void {
  /*
   * Kiểm ở client là để nói sớm, KHÔNG phải để bảo vệ: chữ ký đã ghim định dạng
   * và nhà cung cấp mới là bên thực thi. Nhưng một người chọn nhầm file 40MB
   * xứng đáng biết ngay, thay vì chờ hết một lượt tải rồi mới nhận lỗi.
   */
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!ticket.allowed_formats.includes(ext)) {
    throw new UploadError(`Chỉ nhận ${ticket.allowed_formats.join(", ")} — file này là .${ext}`);
  }
  if (file.size > ticket.max_bytes) {
    const limit = Math.round(ticket.max_bytes / (1024 * 1024));
    throw new UploadError(`File vượt quá ${limit}MB`);
  }
}

/** Xin vé → tải thẳng lên nhà cung cấp. Bước xác nhận do nơi gọi tự làm. */
export async function uploadViaTicket(
  ticketPath: string,
  file: File,
  token: string,
): Promise<UploadOutcome> {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "jpg";
  const ticket = await apiFetch<UploadTicket>(ticketPath, {
    method: "POST",
    token,
    body: JSON.stringify({ ext: ext === "jpeg" ? "jpg" : ext }),
  });
  checkBeforeSending(ticket, file);
  await putToProvider(ticket, file);
  return { storageKey: ticket.storage_key };
}

/** Avatar: xin vé, tải lên, rồi gắn vào hồ sơ. */
export async function uploadAvatar(file: File, token: string): Promise<void> {
  const { storageKey } = await uploadViaTicket(API_ROUTES.avatarTicket, file, token);
  await apiFetch(API_ROUTES.avatar, {
    method: "POST",
    token,
    body: JSON.stringify({ storage_key: storageKey }),
  });
}

export function messageFor(error: unknown, fallback: string): string {
  if (error instanceof UploadError) return error.message;
  if (error instanceof ApiError) return error.message;
  return fallback;
}
