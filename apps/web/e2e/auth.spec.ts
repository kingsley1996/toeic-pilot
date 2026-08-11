import { expect, test } from "@playwright/test";

/*
 * Luồng đăng ký → vào khu học.
 *
 * Mỗi lần chạy tự tạo một email mới thay vì dùng lại tài khoản cố định: email
 * là UNIQUE ở database, nên một tài khoản dùng chung sẽ khiến lần chạy thứ hai
 * đỏ vì "email đã tồn tại" — một lỗi không nói gì về code.
 */
function freshEmail(): string {
  return `e2e-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

test("đăng ký xong thì vào thẳng khu học và đã đăng nhập", async ({ page }) => {
  const email = freshEmail();

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();

  await expect(page).toHaveURL(/\/learn$/);

  /*
   * Kiểm ĐÃ ĐĂNG NHẬP, không chỉ kiểm URL.
   *
   * `useRequireSession` có ba trạng thái chứ không phải hai, và `loading` khác
   * `anonymous` — một trang render xong với trạng thái loading trông hệt như
   * trang của người đã đăng nhập. Lời chào lấy từ `user` nên nó chỉ hiện khi
   * phiên đã thực sự phân giải.
   */
  await expect(page.getByRole("heading", { name: /chào/i })).toBeVisible();
});

test("đăng nhập sai mật khẩu thì báo lỗi và ở lại trang", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("khong-ton-tai@example.com");
  await page.locator('input[name="password"]').fill("sai-mat-khau-123");
  await page.getByRole("button", { name: "Đăng nhập" }).click();

  // Ở LẠI là một nửa của khẳng định: một lần chuyển hướng ngầm sau khi đăng
  // nhập hỏng là cách nhanh nhất làm người dùng tin họ đã vào được.
  await expect(page).toHaveURL(/\/login$/);
  // Bắt theo chữ máy chủ thật trả về, không đoán: `/auth/login` trả
  // `Incorrect email or password`, và giao diện in nguyên `ApiError.message`.
  await expect(page.getByText(/Incorrect email or password/i)).toBeVisible();
});
