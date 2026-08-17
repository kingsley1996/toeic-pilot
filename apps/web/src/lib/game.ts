/** Tiện ích cho minigame từ vựng — những phép tính thuần, không đụng mạng. */

import { API_ROUTES, type ReviewResult } from "@toeic-pilot/shared";

import { apiFetch } from "@/lib/api";

/**
 * Ghi MỘT lượt ôn SM-2 từ một minigame, đi qua đúng endpoint thẻ lật dùng.
 *
 * Chơi game mà không ghi progress thì "đã thuộc" trên trang chủ không bao giờ
 * nhích lên từ những lượt chơi — con số đáng ra điều khiển hành vi mỗi ngày lại
 * đứng yên. Đúng = grade 4 (good), sai = grade 0 (forgot): cùng thang SM-2 mà
 * thẻ lật chấm, nên một từ ghép đúng ở đây cũng đến hạn ôn lại y như khi tự
 * chấm "good" trên thẻ. Lỗi ghi im lặng bỏ qua: game là tự luyện tập, và một
 * request hỏng thì không được phá cả màn chơi. Trả về promise để nơi nào cần
 * số liệu TIẾN ĐỘ ĐÃ GHI (progress meter) biết lúc nào đáng đọc lại.
 */
export function recordReview(token: string, entryId: string, grade: number): Promise<void> {
  return apiFetch<ReviewResult>(API_ROUTES.submitReview(entryId), {
    method: "POST",
    token,
    body: JSON.stringify({ grade }),
  })
    .then(() => {})
    .catch(() => {});
}

/** Xáo trộn bản sao của mảng (Fisher–Yates), không đụng mảng gốc. */
export function shuffle<T>(items: T[]): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j]!, copy[i]!];
  }
  return copy;
}
