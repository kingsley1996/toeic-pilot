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

test("cho ăn làm chỉ số no tăng, và ăn tiếp khi đã no thì bị từ chối có lý do", async ({
  page,
  request,
}) => {
  /*
   * Bài này bắc qua chỗ nối mà cả hai phía đứng riêng đều xanh: máy chủ trừ dần
   * theo `needs_at` và trả về nhu cầu MỚI, còn trình duyệt phải vẽ đúng con số
   * đó chứ không phải con số nó tự cộng.
   *
   * Đọc chỉ số qua API chứ không qua thanh chỉ số: thanh cố ý KHÔNG in phần
   * trăm (`petland-ui.tsx` giải thích vì sao), nên nó không đọc được thành số.
   * Cái phải kiểm ở giao diện là nút có gọi đúng thứ không và lời từ chối có
   * hiện ra không.
   */
  await signUp(page);
  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const auth = { Authorization: `Bearer ${token}` };
  const read = async () =>
    (await (await request.get("http://localhost:8000/api/v1/pet", { headers: auth })).json()).needs
      .fullness as number;

  await launcher(page).click();
  const feed = page.getByRole("button", { name: /Cho ăn/i });
  await expect(feed).toBeVisible();

  const before = await read();
  await feed.click();
  await expect.poll(read).toBeGreaterThan(before);

  /*
   * Đã no thì nút TỰ MỜ, kèm lý do trong `title` — người dùng không bao giờ chạm
   * tới lỗi 409, và đó là chủ ý.
   *
   * Bản đầu của bài này chờ dòng chữ từ chối hiện ra, và nó sai: một con thú
   * bắt đầu ở 0,62 cộng 0,35 là 0,97, tức vượt ngưỡng ngay sau MỘT lần cho ăn,
   * nên cái nút đã tự khoá trước khi có gì để từ chối. Lỗi 409 vẫn phải đúng —
   * nó chặn đường gọi thẳng API — nhưng nó được `tests/test_pet_state.py` canh,
   * chứ không phải ở đây.
   */
  await expect(feed).toBeDisabled();
  await expect(feed).toHaveAttribute("title", /đang no/i);
});
