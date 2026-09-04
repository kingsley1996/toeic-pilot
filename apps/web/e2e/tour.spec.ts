import { type Page, expect, test } from "@playwright/test";

/*
 * Tour chào người mới ở trang chủ.
 *
 * Chỗ đáng kiểm không phải là bong bóng trông thế nào, mà là hai câu trả lời
 * NGƯỢC NHAU mà cùng một trang phải đưa ra: hiện với người chưa xem, và im lặng
 * với người đã xem. Cả hai hỏng im lặng và hỏng theo hướng không ai báo — không
 * hiện thì người mới mất lời chào mà chẳng có lỗi nào in ra, còn hiện lại thì
 * lớp phủ chặn trang chủ của người đã dùng lâu, mỗi lần vào lại một lần nữa.
 *
 * Mốc nằm ở MÁY CHỦ (`user_profile.toured_at`), không ở `localStorage`, nên bài
 * "đã xem thì thôi" phải đi qua một lần tải lại thật — đó chính là thứ một mốc
 * lưu trong trình duyệt sẽ vượt qua được mà vẫn sai ở thiết bị thứ hai.
 */

function freshEmail(): string {
  return `tour-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

async function signUp(page: Page): Promise<void> {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

/* Lớp phủ tự nhận mình bằng vai trò, không bằng tên lớp — cùng thứ mà trình đọc
   màn hình thấy, nên bài kiểm và người dùng khiếm thị nhìn vào một chỗ. */
const overlay = (page: Page) => page.locator('[role="dialog"][aria-modal="true"]');

test("người mới được chào, và đi hết bốn bước", async ({ page }) => {
  await signUp(page);

  await expect(overlay(page)).toBeVisible();
  await expect(page.getByText("Ba việc mỗi ngày")).toBeVisible();
  await expect(page.getByText("1/4")).toBeVisible();

  await page.getByRole("button", { name: "Tiếp" }).click();
  await expect(page.getByText("2/4")).toBeVisible();
  await page.getByRole("button", { name: "Tiếp" }).click();
  await expect(page.getByText("3/4")).toBeVisible();
  await page.getByRole("button", { name: "Tiếp" }).click();
  await expect(page.getByText("4/4")).toBeVisible();

  /* Bước cuối đổi nút thành "Xong": nếu nó vẫn là "Tiếp" thì người dùng bấm mãi
     mà không thoát được, và lớp phủ thì chặn hết mọi thứ phía sau. */
  await page.getByRole("button", { name: "Xong" }).click();
  await expect(overlay(page)).toHaveCount(0);
});

test("đã xem rồi thì lần vào sau không bị chào lại", async ({ page }) => {
  await signUp(page);
  await expect(overlay(page)).toBeVisible();
  await page.getByRole("button", { name: "Bỏ qua" }).click();
  await expect(overlay(page)).toHaveCount(0);

  await page.reload();

  /* Neo trước, rồi mới khẳng định sự vắng mặt: `toHaveCount(0)` đúng ngay lập
     tức trên một trang chưa tải gì, nên không có cái neo này thì bài vẫn xanh
     kể cả khi mốc "đã xem" không hề được ghi. */
  await expect(page.getByRole("region", { name: "Việc hôm nay" })).toBeVisible();
  await expect(overlay(page)).toHaveCount(0);
});
