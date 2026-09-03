/**
 * Thông báo của góc thú cưng, hiện NGAY TRONG bảng chứ không dùng toast toàn trang.
 *
 * Toast toàn trang (`lib/toast.tsx`) nói những chuyện của cả ứng dụng: huy hiệu,
 * việc hôm nay, lên level. Chuyện của con thú thì thuộc về chỗ con thú đang
 * đứng — "+1 XP" bay ra ở góc trên phải màn hình, cách con thú nửa màn, bắt
 * người đọc tự nối hai thứ lại với nhau. Ở góc dưới phải của chính bảng thì
 * không cần nối gì cả.
 *
 * **Kênh phát chứ không phải context**, cùng khuôn `theme.ts` và `sidebar.ts`:
 * bên gửi là các màn học nằm ở cây component khác hẳn, và luồn một prop qua sáu
 * tầng để nói "vừa được 1 XP" là cách chắc chắn khiến lần thêm màn học sau quên
 * mất nó.
 *
 * Khác `pet-cheer.ts` ở chỗ đó là HIỆU ỨNG (con thú loé sáng) còn đây là CHỮ.
 * Hai thứ tách nhau vì chúng không luôn đi cùng: trả lời đúng lúc đã kịch trần
 * XP thì vẫn loé sáng, nhưng không có con số nào để khoe.
 */

import { type SoundName } from "@/lib/sound";

export type PetNoticeTone = "ok" | "warn" | "alert";

/** Ba con số đáng khoe. Bỏ trống nghĩa là lượt này không có phần ấy. */
export type PetGains = {
  xp?: number;
  /** Mức tinh thần tăng thêm, 0–1. Giao diện tự đổi ra phần trăm. */
  mood?: number;
  ruby?: number;
};

export type PetNotice = {
  title: string;
  detail?: string;
  tone?: PetNoticeTone;
  gains?: PetGains;
  /**
   * Tiếng báo, và chỉ xin ở thông báo đi NGAY SAU một cú bấm.
   *
   * Cùng luật với `lib/toast.tsx`: trình duyệt chặn phát tiếng cho tới khi người
   * dùng đã tương tác, nên xin ở một thông báo bắn ra từ `fetch` lúc mở trang là
   * xin một thứ chắc chắn không được cấp — và code nói dối về hành vi thật của
   * nó. Mở trứng thì hợp lệ: nó xảy ra đúng lúc người ta vừa bấm.
   */
  sound?: SoundName;
  /** Thẻ cùng khoá thì THAY tại chỗ thay vì xếp thêm một thẻ nữa. */
  dedupeKey?: string;
};

const listeners = new Set<(notice: PetNotice) => void>();

export function subscribeToPetNotices(onNotice: (notice: PetNotice) => void): () => void {
  listeners.add(onNotice);
  return () => {
    listeners.delete(onNotice);
  };
}

export function notifyPet(notice: PetNotice): void {
  for (const listener of listeners) listener(notice);
}

/**
 * Thông báo phần thưởng từ một lượt học, nếu máy chủ có cấp gì.
 *
 * Nhận nguyên khối `pet` mà API trả về, và **im lặng khi nó là `null`** — trần
 * XP ngày và mức trần 1.0 của tinh thần đều có thể đã cắt sạch, và một cái toast
 * "+0" là nhiễu. Con số đến từ máy chủ chứ không tính lại ở đây: bảng mức thưởng
 * chép sang client là hai nguồn sự thật, và chúng lệch nhau vào đúng ngày ai đó
 * chỉnh một con số.
 */
export function notifyStudyReward(
  pet: { xp: number; mood: string; ruby?: number } | null | undefined,
  title = "Thú cưng vui hơn",
): void {
  if (!pet) return;
  const mood = Number(pet.mood);
  const gains: PetGains = {
    xp: pet.xp > 0 ? pet.xp : undefined,
    mood: mood > 0 ? mood : undefined,
    ruby: pet.ruby && pet.ruby > 0 ? pet.ruby : undefined,
  };
  if (gains.xp === undefined && gains.mood === undefined && gains.ruby === undefined) return;
  notifyPet({ title, tone: "ok", gains });
}
