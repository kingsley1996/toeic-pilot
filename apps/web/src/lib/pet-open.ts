/**
 * Yêu cầu mở bảng thú cưng, phát từ chỗ khác trong ứng dụng.
 *
 * Trạng thái đóng/mở nằm trong `PetLand`, còn thứ muốn mở nó — thẻ thú cưng ở
 * sidebar — nằm ở nhánh cây component hoàn toàn khác, do `shell.tsx` dựng. Nâng
 * trạng thái ấy lên một context bao cả hai nghĩa là mỗi lần bật/tắt bảng lại
 * dựng lại toàn bộ khung ứng dụng.
 *
 * Cùng khuôn với `pet-notice.ts` và `pet-cheer.ts`. Không mang dữ liệu: đây là
 * một cú bấm, không phải một sự kiện có nội dung.
 */

const listeners = new Set<() => void>();

export function subscribeToPetOpen(onOpen: () => void): () => void {
  listeners.add(onOpen);
  return () => {
    listeners.delete(onOpen);
  };
}

export function requestPetOpen(): void {
  for (const listener of listeners) listener();
}
