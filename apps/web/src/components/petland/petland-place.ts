/**
 * Chỗ đứng của bảng thú cưng trên màn hình.
 *
 * **Lưu ở `localStorage`, không lưu ở máy chủ**, và ranh giới đó đã được vẽ sẵn
 * trong dự án: chủ đề sáng/tối nằm ở `localStorage` vì nó là sở thích theo
 * THIẾT BỊ, còn `user_profile.pet` nằm ở máy chủ vì "con thú của tôi" phải đi
 * theo tài khoản. Kéo bảng sang góc nào là chuyện của cái màn hình đang dùng —
 * màn 13 inch và màn ngoài 27 inch muốn hai chỗ khác nhau, và đồng bộ chúng qua
 * tài khoản là làm phiền chứ không phải giúp.
 *
 * Không React, không DOM. Kẹp toạ độ là số học thuần nên kiểm được ngoài trình
 * duyệt, và đó là chỗ dễ sai nhất: một bảng bị kéo ra ngoài mép rồi lưu lại sẽ
 * KHÔNG BAO GIỜ quay về được, vì nó nằm ngoài chỗ chuột với tới.
 */

const KEY = "petland:place";

export type Place = { x: number; y: number };

/** Chừa mép, để bảng không dính sát cạnh màn hình. */
export const MARGIN = 16;

/**
 * Ép một vị trí vào trong màn hình.
 *
 * Gọi ở CẢ HAI đầu — lúc thả chuột và lúc đọc lại từ `localStorage`. Chỉ kẹp lúc
 * thả là chưa đủ: người dùng kéo bảng sang mép phải trên màn rộng, đóng máy, mở
 * lại bằng màn hẹp hơn, và bảng nằm ngoài vùng nhìn thấy được. Không có gì báo,
 * và cách duy nhất để lấy lại là xoá `localStorage`.
 */
export function clamp(
  place: Place,
  panel: { w: number; h: number },
  screen: { w: number; h: number },
): Place {
  const maxX = Math.max(MARGIN, screen.w - panel.w - MARGIN);
  const maxY = Math.max(MARGIN, screen.h - panel.h - MARGIN);
  return {
    x: Math.min(Math.max(MARGIN, place.x), maxX),
    y: Math.min(Math.max(MARGIN, place.y), maxY),
  };
}

/**
 * Chỗ mặc định: góc dưới bên PHẢI.
 *
 * Trước đây là góc dưới bên trái, ngay sát mép sidebar — tức là nằm TRONG cột
 * nội dung, đúng chỗ ô gõ của bài nghe chép chính tả. Cột nội dung căn giữa và
 * có bề rộng tối đa, nên lề phải là dải trống rộng nhất trên màn; còn toast toàn
 * trang thì ở góc trên phải, nên hai lớp không đụng nhau.
 *
 * Không cần biết sidebar rộng bao nhiêu nữa: sidebar nằm bên trái.
 */
export function defaultPlace(
  panel: { w: number; h: number },
  screen: { w: number; h: number },
): Place {
  return clamp({ x: screen.w - panel.w - MARGIN, y: screen.h - panel.h - MARGIN }, panel, screen);
}

export function readPlace(): Place | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const { x, y } = parsed as Partial<Place>;
    return typeof x === "number" && typeof y === "number" ? { x, y } : null;
  } catch {
    // Safari riêng tư ném khi đọc localStorage, và JSON hỏng thì cũng vậy.
    return null;
  }
}

export function writePlace(place: Place): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(place));
  } catch {
    /* không lưu được thì vẫn kéo được trong phiên này */
  }
}
