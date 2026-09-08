/**
 * Trạng thái thú cưng vừa đổi, phát cho những chỗ khác đang hiển thị nó.
 *
 * Bảng thú cưng và thẻ ở sidebar cùng vẽ MỘT con thú nhưng nằm ở hai nhánh cây
 * component khác hẳn nhau — bảng do `app-shell` dựng, thẻ do `shell` dựng. Không
 * có kênh này thì thẻ chỉ biết những gì nó tự đọc lúc dựng: cho ăn xong, đổi
 * sang con khác, lên level — bảng đổi ngay còn thẻ vẫn in con số của mười phút
 * trước, và không có gì báo là nó đã cũ.
 *
 * Phát nguyên khối máy chủ trả về chứ không phát tín hiệu "đi đọc lại đi": mỗi
 * hành động đã trả sẵn `PetPublic` mới rồi, nên một lần đọc nữa vừa thừa một
 * vòng mạng vừa mở ra cửa sổ để hai bên nói hai con số khác nhau.
 *
 * Cùng khuôn `pet-notice.ts` và `pet-open.ts`.
 */

import { type PetPublic } from "@toeic-pilot/shared";

const listeners = new Set<(pet: PetPublic) => void>();

// Bản PetPublic MỚI NHẤT đã đi qua kênh này. Chỉ bộ đệm một giá trị: thứ duy
// nhất người tiêu thụ cần khi vào giữa phiên là "con thú đang là gì", và giá
// trị cũ hơn giá trị mới không có vai trò nào — còn lịch sử đầy đủ là việc của
// máy chủ, không của client.
let latest: PetPublic | null = null;

export function lastPet(): PetPublic | null {
  return latest;
}

export function subscribeToPetState(onPet: (pet: PetPublic) => void): () => void {
  listeners.add(onPet);
  return () => {
    listeners.delete(onPet);
  };
}

export function publishPet(pet: PetPublic): void {
  latest = pet;
  for (const listener of listeners) listener(pet);
}
