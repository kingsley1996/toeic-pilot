import { expect, test, type Page } from "@playwright/test";

/*
 * Góc thú cưng, bản bản-đồ-ô (ADR-010).
 *
 * Bài kiểm cũ đo bản cũ: phối cảnh dọc đường đi, lớp hạt lửa trại, chọc và cho
 * ăn trên một bức tranh. Cả ba thứ đó không còn tồn tại, nên giữ lại là giữ một
 * bức ảnh xanh về một tính năng đã bị thay.
 *
 * Ba bài dưới đây đo ba chỗ nối mà `tsc` và `eslint` đều không thấy: vị trí sau
 * khi NẠP LẠI trang, vị trí sau khi kéo, và kích thước khung khi mở toàn bản đồ.
 */

function freshEmail(): string {
  return `e2e-pet-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

async function signUp(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

const launcher = (page: Page) => page.getByRole("button", { name: "Thú cưng" });

test("sau khi nạp lại trang, góc thú cưng vẫn ở nửa dưới màn hình", async ({ page }) => {
  /*
   * Đây là một lỗi CÓ THẬT đã gặp, và nó là bẫy ba trạng thái của phiên.
   *
   * Lượt dựng đầu tiên `status` là `loading` nên component trả `null`; hiệu ứng
   * đặt chỗ chạy lúc đó, không thấy node nào, và không chạy lại khi phiên phân
   * giải xong — bảng nằm nguyên ở toạ độ inline khởi tạo, tức góc TRÊN TRÁI.
   *
   * Chỉ lộ ra khi NẠP LẠI trang: điều hướng bên trong app không dựng lại
   * `SidebarShell`, nên phiên đã sẵn sàng từ trước và mọi thứ trông bình thường.
   * Vì thế bài này phải `reload()`, không được chỉ `goto()`.
   */
  await signUp(page);
  await page.reload();

  const box = await launcher(page).boundingBox();
  expect(box).not.toBeNull();
  const view = page.viewportSize();
  expect(view).not.toBeNull();
  expect(box!.y).toBeGreaterThan(view!.height / 2);
});

test("kéo góc thú cưng sang chỗ khác thì chỗ đó được nhớ", async ({ page }) => {
  await signUp(page);

  const handle = page.getByTitle("Kéo để đổi chỗ");
  const before = await launcher(page).boundingBox();
  expect(before).not.toBeNull();

  const grip = await handle.boundingBox();
  await page.mouse.move(grip!.x + grip!.width / 2, grip!.y + grip!.height / 2);
  await page.mouse.down();
  await page.mouse.move(520, 260, { steps: 12 });
  await page.mouse.up();

  const after = await launcher(page).boundingBox();
  expect(after!.y).toBeLessThan(before!.y - 50);

  // Nạp lại: `localStorage` phải giữ chỗ. Đây là nửa còn lại của bài đầu — đặt
  // chỗ đúng lúc mount thì cũng phải đọc được chỗ ĐÃ LƯU chứ không phải mặc định.
  await page.reload();
  const reloaded = await launcher(page).boundingBox();
  expect(Math.abs(reloaded!.y - after!.y)).toBeLessThan(24);
});

test("mở toàn bản đồ thì khung nhìn rộng ra", async ({ page }) => {
  await signUp(page);
  await launcher(page).click();

  const canvas = page.locator("canvas");
  await expect(canvas).toBeVisible();
  const small = await canvas.boundingBox();

  await page.getByRole("button", { name: "Xem toàn bản đồ" }).click();
  const large = await canvas.boundingBox();

  expect(large!.width).toBeGreaterThan(small!.width);
  // Cùng MỘT canvas: `setView` đổi khung tại chỗ chứ không dựng lại sân khấu —
  // mỗi lần dựng lại là một WebGL context nữa, và trình duyệt chỉ cho vài cái.
  await expect(canvas).toHaveCount(1);
});
