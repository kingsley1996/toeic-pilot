import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

import { skipTour } from "./support";
import { SCENES } from "../src/content/scenes";

// Ảnh 2× để nét trên card, và khung cao hơn mặc định để cảnh không bị cắt nóc.
test.use({ deviceScaleFactor: 2, viewport: { width: 1280, height: 860 } });

/*
 * KHÔNG phải test — là công cụ dựng ảnh xem trước cho section "Visual Word" ở
 * /learn/vocabulary. Chạy:
 *
 *   SCENE_PREVIEWS=1 pnpm exec playwright test e2e/scene-previews.spec.ts
 *
 * `locator("canvas").screenshot()` crop khung hình TẠI hộp canvas — mọi lớp phủ DOM
 * đè lên hộp đó (nhãn từ, panel) VẪN lọt vào ảnh. Thumbnail dựng bằng `?plain=1`
 * (tắt nhãn ngay từ đầu) nên hình là 3D thuần, không chữ.
 * Ở chế độ plain không còn `[data-object-id]` để chờ — chờ response từ vựng
 * (3D chỉ dựng sau khi resolve xong) rồi ngủ thêm cho three vẽ đủ khung hình.
 * `reducedMotion: reduce` dựng cảnh đứng yên tại neo: không có ảnh nào chụp
 * được lúc chiếc xe đang ở giữa tuyến, và hai lần chạy ra hai ảnh khác nhau thì
 * không ai biết bản nào là đúng.
 *
 * Ảnh là SẢN PHẨM PHẢI COMMIT và nó sẽ lệch nếu ta sửa vị trí trong scene file —
 * đó là lý do tệp này sống trong repo thay vì một lần chạy tay ở /tmp.
 */

const OUT = join(__dirname, "../public/scenes");

test("render ảnh xem trước cho từng cảnh", async ({ page, request }) => {
  test.skip(!process.env.SCENE_PREVIEWS, "chỉ chạy khi SCENE_PREVIEWS=1");
  test.setTimeout(180_000);
  const res = await request.get("http://localhost:8000/api/v1/vocabulary?topic=logistics&limit=1");
  test.skip(!res.ok(), "stack dev chưa chạy");

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/register");
  await page.getByLabel("Email").fill(`preview-${Date.now()}@example.com`);
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  for (const scene of SCENES) {
    await page.goto(`/learn/scenes/${scene.id}?plain=1`);
    await page.waitForResponse((r) => r.url().includes("/api/v1/vocabulary") && r.ok(), {
      timeout: 30_000,
    });
    await expect(page.locator("canvas")).toBeVisible({ timeout: 30_000 });
    // Nút góp ý fixed ở mép phải đè lên hộp canvas — ẩn nó sau mỗi `goto`
    // (`addStyleTag` không sống qua chuyển trang), production giữ nguyên.
    await page.addStyleTag({ content: '[aria-label="Gửi góp ý"]{display:none !important}' });
    await page.waitForTimeout(2500);
    const file = join(OUT, `${scene.id}.png`);
    mkdirSync(dirname(file), { recursive: true });
    await page.locator("canvas").screenshot({ path: file });
    console.log(`  ${scene.id} -> ${file}`);
  }
});
