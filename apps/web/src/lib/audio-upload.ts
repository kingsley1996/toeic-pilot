import { API_ROUTES, type AudioAssetPublic } from "@toeic-pilot/shared";

import { UploadError, uploadViaTicket } from "@/lib/upload";
import { apiFetch } from "@/lib/api";

/**
 * Đọc độ dài clip TRƯỚC khi tải lên.
 *
 * Máy chủ không đo được: đọc khung mp3 cần một thư viện nằm sau extra `content`,
 * mà đó đúng là thứ tiến trình HTTP không được import (A4.1). Trình duyệt thì đã
 * có sẵn file trong tay, nên nó khai — và đây là ngoại lệ có chủ ý với luật
 * "không tin lời trình duyệt": ba thứ quyết định tính đúng đắn (file có tồn tại,
 * định dạng gì, bao nhiêu byte) vẫn được hỏi lại kho lưu trữ ở bước xác nhận.
 */
export async function readDuration(file: File): Promise<number> {
  const url = URL.createObjectURL(file);
  try {
    return await new Promise<number>((resolve, reject) => {
      const probe = new Audio();
      probe.preload = "metadata";
      probe.onloadedmetadata = () => resolve(Math.round(probe.duration * 1000));
      probe.onerror = () => reject(new UploadError("Không đọc được file audio này."));
      probe.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Xin vé → PUT thẳng lên object store → xác nhận → trả về asset đã tạo. */
export async function uploadAudio(
  file: File,
  accent: string,
  token: string,
): Promise<AudioAssetPublic> {
  const duration = await readDuration(file);
  if (!Number.isFinite(duration) || duration <= 0) {
    throw new UploadError("Không đọc được độ dài clip.");
  }

  const { storageKey } = await uploadViaTicket(API_ROUTES.adminAudioTicket, file, token, "mp3");
  return apiFetch<AudioAssetPublic>(API_ROUTES.adminAudioConfirm, {
    method: "POST",
    token,
    body: JSON.stringify({ storage_key: storageKey, duration_ms: duration, accent }),
  });
}
