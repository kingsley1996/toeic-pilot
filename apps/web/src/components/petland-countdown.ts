/**
 * Đồng hồ đếm ngược tới lúc một cuộc chạm mặt hết hạn.
 *
 * Hai hàm thuần trong một tệp `.ts` riêng chứ không nằm trong component dùng
 * chúng: ở đây chúng chạy được thẳng bằng `node --experimental-strip-types`, còn
 * chôn trong một `.tsx` thì cách duy nhất để kiểm là dựng cả React lên.
 */

/** Còn bao nhiêu giây. Âm thì kẹp về 0 — quá hạn rồi thì không đếm lùi nữa. */
export function secondsLeft(iso: string, now: number): number {
  return Math.max(0, Math.floor((new Date(iso).getTime() - now) / 1000));
}

/** `m:ss`. Phút không đệm 0, giây thì có — "0:09" đọc ra ngay là chín giây. */
export function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}
