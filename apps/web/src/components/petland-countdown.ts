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

/** `m:ss`, và từ một giờ lên là `h:mm:ss` — "1439:50" đọc là phút của một giờ,
 * không phải một ngày. Nhiệm vụ hồi phục sống cả ngày nên cần vạch giờ. */
export function clock(seconds: number): string {
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  }
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}
