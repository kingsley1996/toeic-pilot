import { API_ROUTES, type ImageAssetPublic } from "@toeic-pilot/shared";

import { apiFetch } from "@/lib/api";
import { uploadViaTicket } from "@/lib/upload";

/**
 * Xuất xứ của một bức ảnh. Ba trường đầu là NOT NULL trong `image_asset`.
 *
 * Không có mặc định ở bất kỳ tầng nào, đúng luật của `question.source`: phần lớn
 * ảnh mở là CC-BY — dùng được *với điều kiện* ghi công — và ghi công chỉ có tác
 * dụng nếu nó được lưu lại. Đoán hộ ở đây là ghi một lời khai sai vào đúng cột
 * tồn tại để trả lời "ảnh này ở đâu ra".
 */
export type ImageProvenance = {
  source_url: string;
  license: string;
  attribution: string;
  alt_text: string | null;
};

/** Xin vé → POST thẳng lên Cloudinary → xác nhận → trả về asset đã tạo. */
export async function uploadImage(
  file: File,
  provenance: ImageProvenance,
  token: string,
): Promise<ImageAssetPublic> {
  const { storageKey } = await uploadViaTicket(API_ROUTES.adminImageTicket, file, token);
  return apiFetch<ImageAssetPublic>(API_ROUTES.adminImageConfirm, {
    method: "POST",
    token,
    body: JSON.stringify({ storage_key: storageKey, ...provenance }),
  });
}
