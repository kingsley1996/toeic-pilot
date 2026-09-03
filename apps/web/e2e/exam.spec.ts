import { expect, test } from "@playwright/test";

/*
 * Một vòng làm bài: mở đề → trả lời → nộp → xem kết quả → xem lại từng câu.
 *
 * Đây là bài test đáng giá nhất trong bộ, vì nó đi qua đúng những chỗ đã hỏng
 * trong sprint này và không chỗ nào bị `tsc` hay test backend bắt được:
 *
 *   · sáu endpoint đổi từ mảng trần sang `Page[T]` — `apiFetch<T>` nhận kiểu từ
 *     nơi gọi nên trình biên dịch im lặng, và danh sách chỉ rỗng đi lúc chạy
 *   · `_question_admin` thiếu bản đồ asset — media đã gắn hiện ra là "chưa có"
 *   · bảng kết quả và màn xem lại vốn không có test nào chạm tới
 *
 * Nó dùng đề demo đã xuất bản sẵn trong database dev. Không tự dựng nội dung:
 * tạo một đề qua API admin cần tài khoản admin, mà tài khoản đó không đăng ký
 * được — `register` cố ý không cho chọn vai trò. Dựng cái đó ở đây sẽ là nhiều
 * giàn giáo hơn cả thứ đang được kiểm.
 */

const TEST_PATH = "/learn/tests/demo-2026/demo-2026-test-1";

async function signUp(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/register");
  await page
    .getByLabel("Email")
    .fill(`e2e-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`);
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("làm một đề rồi nộp thì thấy kết quả và xem lại được từng câu", async ({ page }) => {
  await signUp(page);

  await page.goto(TEST_PATH);
  await page.getByRole("button", { name: /bắt đầu làm bài/i }).click();
  await expect(page).toHaveURL(/\/learn\/attempts\/[0-9a-f-]+$/);

  // Trả lời câu đầu tiên. Không có nút Lưu — mỗi lần chọn là một lần ghi lên
  // máy chủ, nên chỗ này cũng kiểm luôn đường PATCH.
  const firstQuestion = page.locator("text=/^Câu \\d+$/").first();
  await expect(firstQuestion).toBeVisible();
  await page
    .getByRole("button", { pressed: false })
    .filter({ hasText: /^\(?A\)?/ })
    .first()
    .click();

  await page.getByRole("button", { name: "Nộp bài" }).first().click();

  /*
   * Hộp thoại xác nhận phải mang BỐN con số, không phải một câu văn: đã trả
   * lời, chưa trả lời, đã đánh dấu, thời gian còn. Bản trước chỉ nói "còn N câu
   * chưa trả lời" và giấu mất chuyện người ta đã đánh dấu vài câu để quay lại.
   */
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Đã trả lời")).toBeVisible();
  await expect(dialog.getByText("Chưa trả lời")).toBeVisible();
  await expect(dialog.getByText("Đã đánh dấu")).toBeVisible();
  await expect(dialog.getByText("Thời gian còn")).toBeVisible();

  await dialog.getByRole("button", { name: "Nộp bài" }).click();

  // Bảng kết quả THAY danh sách câu, không nằm đè lên nó.
  await expect(page.getByText("Số câu đúng")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Theo từng phần" })).toBeVisible();

  /*
   * Bốn ô đếm, và ba trong số đó là lý do bảng này tồn tại: SAI và BỎ TRỐNG là
   * hai chuyện khác nhau. Trước đây thanh mỗi part chỉ có đúng/tổng, nên người
   * hết giờ ở Part 7 trông y hệt người đọc sai — một bên cần luyện tốc độ, bên
   * kia cần luyện đọc.
   */
  const tallies = page.locator("dl").first();
  for (const label of ["Đúng", "Sai", "Bỏ trống", "Thời gian"]) {
    await expect(tallies.getByText(label, { exact: true })).toBeVisible();
  }

  /*
   * KHÔNG có tab chọn part ở màn kết quả: ở đó không còn gì để điều hướng tới,
   * và một hàng tab bấm được nhưng không đưa đi đâu là một lời hứa sai. Khẳng
   * định phủ định này neo vào một thứ CÓ mặt ngay trên (`Theo từng phần`), nếu
   * không nó xanh trên một trang chưa nạp xong.
   */
  await expect(page.getByRole("button", { name: /^P1\b/ })).toHaveCount(0);

  await page.getByRole("button", { name: /xem chi tiết từng câu/i }).click();

  // Bộ lọc là thứ khiến màn xem lại dùng được với đề 200 câu.
  for (const label of ["Tất cả", "Câu sai", "Bỏ trống", "Đã đánh dấu"]) {
    await expect(page.getByRole("button", { name: label })).toBeVisible();
  }
  // Tab part quay lại ngay khi rời màn kết quả — chúng chỉ vắng mặt ở đó.
  await expect(page.getByRole("button", { name: /^P1\b/ })).toBeVisible();

  await page.getByRole("button", { name: "Kết quả" }).click();
  await expect(page.getByText("Số câu đúng")).toBeVisible();
});

test("lượt đang dở hiện ở trang chủ và ở lịch sử làm bài", async ({ page }) => {
  await signUp(page);

  await page.goto(TEST_PATH);
  await page.getByRole("button", { name: /bắt đầu làm bài/i }).click();
  await expect(page).toHaveURL(/\/learn\/attempts\/[0-9a-f-]+$/);

  /*
   * Bỏ dở giữa chừng là tình huống THẬT chứ không phải ngoại lệ: đồng hồ chạy ở
   * máy chủ, nên đóng tab không dừng bài — chỉ làm mất đường quay lại. Dev DB
   * từng có 26 lượt dở so với 17 lượt đã nộp, và không màn nào hiện chúng.
   */
  await page.goto("/dashboard");
  await expect(page.getByText(/đang làm dở/i)).toBeVisible();
  await expect(page.getByRole("link", { name: "Làm tiếp" }).first()).toBeVisible();

  await page.goto("/learn/attempts");
  await expect(page.getByRole("heading", { name: "Lịch sử làm bài" })).toBeVisible();
  await expect(page.getByText(/bài đang làm dở/i)).toBeVisible();
});
