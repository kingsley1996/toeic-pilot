import { type Page } from "@playwright/test";

/**
 * Việc chung của mọi bài e2e mở một tài khoản mới.
 *
 * Ở đây có đúng một hàm, và nó tồn tại vì một lý do rất cụ thể: người mới bây
 * giờ được chào bằng một tour có LỚP PHỦ TOÀN MÀN HÌNH ở trang chủ. Lớp phủ ấy
 * nuốt cú bấm — đó là chủ ý của nó — nên mọi bài đăng ký rồi bấm gì đó trên
 * trang chủ sẽ hỏng, và hỏng theo kiểu tệ nhất: tour chỉ hiện sau khi hồ sơ trả
 * lời VÀ các khối đã vẽ xong, nên bài nào nhanh hơn cuộc đua ấy thì vẫn xanh.
 * Một bộ kiểm nửa đỏ nửa xanh tuỳ lúc chạy còn khó lần hơn một bộ đỏ hẳn.
 */

const API_BASE = "http://localhost:8000";

/**
 * Tắt tour chào mừng cho tài khoản đang đăng nhập trên `page`.
 *
 * Gọi thẳng API chứ không bấm "Bỏ qua": đây là DỰNG BỐI CẢNH, không phải thứ
 * đang được đo — cùng lý lẽ với `hatch` ở `petland.spec.ts`. Bấm qua giao diện
 * sẽ biến mọi bài thành một bài kiểm gián tiếp cho cái tour.
 *
 * Gọi NGAY sau khi tới trang chủ, trước thao tác đầu tiên. Nó không đợi tour
 * hiện ra — nó đặt mốc ở máy chủ để tour không bao giờ hiện.
 */
export async function skipTour(page: Page): Promise<void> {
  await page.evaluate(async (base) => {
    const token = window.localStorage.getItem("toeic_pilot_access_token");
    if (!token) return;
    await fetch(`${base}/api/v1/profile/tour-seen`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  }, API_BASE);
  /* Tải lại vì `Tour` hỏi hồ sơ MỘT LẦN lúc gắn: đặt mốc sau đó thì bản đang
     chạy vẫn giữ câu trả lời cũ và lớp phủ vẫn bật lên. */
  await page.reload();
}
