import { expect, test } from "@playwright/test";

import { skipTour } from "./support";

/*
 * Blog (SPEC-BLOG P2+P3): soạn qua UI admin → publish → đọc được ở trang bài,
 * đúng định dạng, không HTTP 4xx.
 *
 * Cần tài khoản admin seeded của ngăn xếp dev (`admin@example.com`) — `register`
 * không cấp được role admin. CI chạy database trắng không có admin nên bài này
 * tự bỏ qua khi đăng nhập admin thất bại (cùng cách `vocabulary.spec.ts` làm).
 *
 * Hai điểm kiến trúc bài này tôn trọng:
 * - Hub `/blog` ISR 10 phút (SPEC-BLOG §4): bài vừa publish CHƯA CHẮC đã hiện ở
 *   hub ngay — nên bài này assert trang chi tiết (slug mới theo timestamp là
 *   cache lạnh, luôn tươi), còn hub chỉ assert cấu trúc + không 4xx.
 * - Bài tạo ra được XÓA HẲN cuối bài qua API (DELETE admin), nên chạy xong
 *   database sạch như trước.
 */

const ADMIN_EMAIL = "admin@example.com";
const ADMIN_PASSWORD = "dev-admin-123";
const API_BASE = "http://localhost:8000";

async function loginAdmin(page: import("@playwright/test").Page): Promise<boolean> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.locator('input[name="password"]').fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  try {
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 20000 });
    return true;
  } catch {
    return false;
  }
}

test("soạn blog qua UI, publish, đọc được ở trang bài", async ({ page }) => {
  test.skip(!(await loginAdmin(page)), "Không có admin seeded — bỏ qua trên CI database trắng.");
  await skipTour(page);

  const badResponses: string[] = [];
  page.on("response", (res) => {
    if (res.status() >= 400) badResponses.push(`${res.status()} ${res.url()}`);
  });

  const stamp = Date.now();
  const title = `Bai e2e ${stamp}`;

  // 1. Soạn bài mới qua UI (slug tự gợi ý từ tiêu đề).
  await page.goto("/admin/blog/new");
  await page.getByLabel("Tiêu đề", { exact: true }).fill(title);
  const slug = await page.getByLabel(/Slug/).inputValue();
  expect(slug).toContain(`bai-e2e-${stamp}`);
  await page.getByLabel(/Sapo/).fill("Sapo bai kiem thu end-to-end cho blog.");
  await page.getByLabel("Tags (phẩy ngăn cách)").fill("e2e");

  const area = page.locator(".blog-edit-area");
  await area.click();
  await page.getByRole("button", { name: "Tiêu đề 2" }).click();
  await page.keyboard.type("Muc mot");
  await page.keyboard.press("Enter");
  await page.keyboard.type("Day la than bai du 300 ky tu. ".repeat(12));

  await page.getByRole("button", { name: "Lưu", exact: true }).click();
  await expect(page).toHaveURL(/\/admin\/blog\/[0-9a-f-]+$/, { timeout: 10000 });
  const postId = page.url().split("/").pop()!;

  // 2. Nháp chưa đọc được ở URL public.
  expect(await page.request.get(`${API_BASE}/api/v1/blog/posts/${slug}`)).not.toBeOK();

  // 3. Publish qua UI rồi đọc ở trang bài (URL mới = cache lạnh, luôn tươi).
  await page.getByRole("button", { name: "Xuất bản" }).click();
  await expect(page.getByText("Đã xuất bản")).toBeVisible({ timeout: 10000 });

  await page.goto(`/blog/${slug}`);
  await expect(page.getByRole("heading", { name: title, level: 1 })).toBeVisible();
  const article = page.locator(".article-blog");
  await expect(article.getByRole("heading", { name: "Muc mot" })).toBeVisible();
  await expect(article).toContainText("Day la than bai");
  // Mục lục neo đúng heading đã gắn id.
  await expect(page.locator('nav a[href="#muc-mot"]')).toBeVisible();

  // 4. Hub render cấu trúc (bài mới có thể chưa vào cache ISR 10 phút).
  await page.goto("/blog");
  await expect(page.getByRole("heading", { name: "Blog TOEIC", level: 1 })).toBeVisible();

  // 5. Dọn: xóa hẳn để database sạch.
  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const deleted = await page.request.delete(`${API_BASE}/api/v1/admin/blog/posts/${postId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(deleted.status()).toBe(204);

  expect(badResponses).toEqual([]);
});
