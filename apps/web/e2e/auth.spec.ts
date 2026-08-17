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

  await expect(page).toHaveURL(/\/dashboard$/);

  /*
   * Kiểm ĐÃ ĐĂNG NHẬP, không chỉ kiểm URL.
   *
   * `useRequireSession` có ba trạng thái chứ không phải hai, và `loading` khác
   * `anonymous` — một trang render xong với trạng thái loading trông hệt như
   * trang của người đã đăng nhập. Lời chào lấy từ `user` nên nó chỉ hiện khi
   * phiên đã thực sự phân giải.
   */
  await expect(page.getByRole("heading", { name: /chào/i })).toBeVisible();

  /*
   * Logo trỏ về trang giới thiệu KỂ CẢ khi đã đăng nhập — quy ước chung của web
   * là logo = gốc của site. Trước đây nó trỏ về khu học, và đổi lại là một quyết
   * định có chủ đích, không phải sơ suất; ghim ở đây để lần sau ai đó "sửa" nó
   * về trạng thái cũ thì có chỗ đọc được lý do.
   */
  await expect(page.getByRole("link", { name: "TOEIC Pilot" })).toHaveAttribute("href", "/");

  /*
   * Nav phải sáng đúng mục, và trang chủ giờ ở `/dashboard` trong khi các chế độ
   * ôn tập vẫn ở `/learn/*` — tức quy tắc "tiền tố của href" KHÔNG còn với tới
   * chúng. `NavItem.covers` là thứ bắc cầu; bỏ nó đi thì mở "Ôn tập" xong cả
   * thanh nav tắt đèn, người dùng mất dấu mình đang ở đâu, và trang thì vẫn
   * đúng nên không ai gọi đó là lỗi.
   */
  const today = page.getByRole("link", { name: "Hôm nay" }).first();
  await expect(today).toHaveAttribute("aria-current", "page");

  await page.goto("/learn/review");
  await expect(today).toHaveAttribute("aria-current", "page");
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

test("đăng xuất thì thoát hẳn, và token cũ không dùng lại được", async ({ page }) => {
  /*
   * Bài này tồn tại vì một lỗi đã lọt: `logout` gọi `API_ROUTES.auth.logout`
   * trong khi map đó PHẲNG, nên nó ném TypeError ngay dòng đầu — trước cả
   * `clearAccessToken()`. Bấm Đăng xuất không xảy ra gì cả. Không thứ nào bắt
   * được: eslint không kiểm kiểu, và không bài e2e nào chạm tới nút đó.
   *
   * Nó cũng canh nửa còn lại — token bị THU HỒI ở máy chủ chứ không chỉ bị xoá
   * khỏi trình duyệt. Xoá phía client thì `localStorage.clear()` cũng làm được;
   * thứ đáng kiểm là bản sao của token có còn dùng được hay không.
   */
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  expect(token).toBeTruthy();

  // Đăng xuất nằm ở ĐÁY SIDEBAR, không còn sau một menu xổ: các trang trong ứng
  // dụng dùng khung có cột trái, và khối tài khoản ở đáy cột đó. Menu xổ vẫn
  // còn, nhưng chỉ trên ba trang dùng thanh trên (`/`, `/login`, `/register`).
  await page.getByRole("button", { name: "Đăng xuất" }).first().click();

  // KHÔNG ghim URL đích. `logout` đẩy về "/", nhưng `/dashboard` cũng tự đá ra
  // /login ngay khi phiên thành ẩn danh, nên trang cuối cùng tuỳ vào cái nào
  // chạy trước — một chi tiết không phải trọng tâm của bài này.
  await expect(page).not.toHaveURL(/\/dashboard/);
  expect(
    await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token")),
  ).toBeNull();

  // Nửa quan trọng: bản sao của token phải bị máy chủ từ chối.
  const status = await page.evaluate(async (bearer) => {
    const response = await fetch("http://localhost:8000/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${bearer}` },
    });
    return response.status;
  }, token);
  expect(status).toBe(401);
});
