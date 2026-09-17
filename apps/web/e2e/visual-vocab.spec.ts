import { type APIRequestContext, type Page, expect, test } from "@playwright/test";

import { SCENES } from "../src/content/scenes";
import { skipTour } from "./support";

/*
 * Cảnh từ vựng 3D (`SPEC-VISUAL-VOCAB-3D.md`).
 *
 * Hai chỗ nối mà chỉ e2e chạm tới được, và cả hai hỏng IM LẶNG:
 *
 *   · Scene file ràng buộc từ bằng (headword, part_of_speech), resolve qua
 *     `?topic=`. Nếu resolve hỏng thì canvas vẫn đẹp — chỉ là thiếu hotspot —
 *     nên bài này đòi thấy TỪNG object bằng tên, chứ không đếm số lượng.
 *   · Mọi cú bấm Recall phải đổ vào ĐÚNG `/vocabulary/{id}/review` của từ
 *     được hỏi (không phải từ vừa bấm nhầm). grade 4/0 không nhìn thấy trên
 *     màn hình; chỉ request nói thật.
 *
 * Theo khuôn `vocabulary-learn.spec.ts`: điều kiện (kho `logistics` đủ từ)
 * được HỎI LÚC CHẠY — stack dev trắng thì skip kèm lý do, không tắt cứng.
 */

const API_BASE = "http://localhost:8000";

// Scene kho hiện tại có 14 object — ít nhất từng đó từ published trong topic.
const MIN_ENTRIES = 14;

async function signUp(page: Page): Promise<void> {
  await page.goto("/register");
  await page
    .getByLabel("Email")
    .fill(`visual-vocab-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`);
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);
}

async function topicEntryCount(request: APIRequestContext, slug: string): Promise<number> {
  const res = await request.get(`${API_BASE}/api/v1/vocabulary?topic=${slug}&limit=1`);
  if (!res.ok()) return 0;
  return (await res.json()).total ?? 0;
}

async function topicHasEnoughEntries(request: APIRequestContext): Promise<boolean> {
  // `request` chứ không phải `page.evaluate(fetch)`: điều kiện được hỏi TRƯỚC
  // khi trang nào mở, và fetch từ `about:blank` là CORS chết ngay tại chỗ.
  const res = await request.get(`${API_BASE}/api/v1/vocabulary?topic=logistics&limit=1`);
  if (!res.ok()) return false;
  return ((await res.json()).total ?? 0) >= MIN_ENTRIES;
}

async function openWarehouseScene(page: Page): Promise<void> {
  await page.goto("/learn/scenes");
  await page.getByRole("link", { name: /Trong nhà kho/ }).click();
  await expect(page).toHaveURL(/\/learn\/scenes\/warehouse-01$/);
}

/** Chờ resolve xong: chấm của một từ cụ thể phải xuất hiện. */
function hotspot(page: Page, word: string) {
  return page.getByRole("button", { name: word, exact: true });
}

test("khám phá: chạm hotspot mở thẻ từ, 'Đã thuộc' ghi grade 6", async ({ page, request }) => {
  test.skip(
    !(await topicHasEnoughEntries(request)),
    `kho logistics cần ≥${MIN_ENTRIES} từ published`,
  );
  test.setTimeout(90_000);

  await signUp(page);
  await openWarehouseScene(page);

  const reviews: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && /\/api\/v1\/vocabulary\/[0-9a-f-]+\/review$/.test(req.url())) {
      reviews.push(req.postData() ?? "");
    }
  });

  await expect(hotspot(page, "forklift")).toBeVisible({ timeout: 30_000 });
  await hotspot(page, "forklift").click();

  const sheet = page.getByRole("heading", { name: "forklift", exact: true });
  await expect(sheet).toBeVisible();
  // Thẻ từ nằm TRONG khung cảnh (góc dưới trái), không ở dưới canvas — thẻ ở
  // ngoài thì người học phải rời mắt khỏi vật vừa chạm để đọc.
  const frame = await page.locator("canvas").evaluate((c) => {
    const r = (c.parentElement?.parentElement as HTMLElement).getBoundingClientRect();
    return { top: r.top, left: r.left, bottom: r.bottom, right: r.right };
  });
  const card = await sheet.boundingBox();
  expect(card).not.toBeNull();
  expect(card!.x).toBeGreaterThan(frame.left);
  expect(card!.y + card!.height).toBeLessThan(frame.bottom);

  await page.getByRole("button", { name: "Đã thuộc" }).click();

  await expect.poll(() => reviews.length).toBe(1);
  expect(reviews[0]).toContain('"grade":6');
});

test("recall: bấm đúng vật chấm grade 4 vào ĐÚNG từ được hỏi", async ({ page, request }) => {
  test.skip(
    !(await topicHasEnoughEntries(request)),
    `kho logistics cần ≥${MIN_ENTRIES} từ published`,
  );
  test.setTimeout(90_000);

  await signUp(page);
  await openWarehouseScene(page);
  await expect(hotspot(page, "forklift")).toBeVisible({ timeout: 30_000 });

  const graded: { url: string; body: string }[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && /\/api\/v1\/vocabulary\/[0-9a-f-]+\/review$/.test(req.url())) {
      graded.push({ url: req.url(), body: req.postData() ?? "" });
    }
  });

  await page.getByRole("button", { name: "Recall" }).click();
  const banner = page.getByText(/^Tìm:/);
  await expect(banner).toBeVisible();

  // Đọc từ được hỏi từ chính banner — bài test không giả định thứ tự queue
  // (queue được xáo ở client).
  const asked = /Tìm:\s*(.+?)\s*\(\d+\/\d+\)/.exec((await banner.innerText()) ?? "");
  expect(asked).not.toBeNull();
  const word = asked![1]!;

  // Trong recall hotspot là chấm tròn KHÔNG hiện chữ — nhưng `aria-label` vẫn
  // mang tên từ, nên bấm theo label là chạm đúng object 3D đó.
  await page.getByRole("button", { name: word, exact: true }).click();

  await expect.poll(() => graded.length).toBe(1);
  expect(graded[0]!.body).toContain('"grade":4');
  expect(graded[0]!.url).toContain("/vocabulary/");
});

/**
 * Nhịp `patrol` của xe — thứ duy nhất trong cảnh đổi vị trí mà không có gì
 * đảm nhận: hỏng thì canvas vẫn đẹp, chỉ là xe đứng chết hoặc (tệ hơn) xe chạy
 * trong lúc đang chấm điểm. Đo bằng toạ độ hotspot trên màn hình vì đó là tất
 * cả những gì e2e chạm tới được.
 */
test("xe chỉ chạy ở explore: courier di chuyển, rồi đứng hẳn khi vào recall", async ({
  page,
  request,
}) => {
  test.skip(
    !(await topicHasEnoughEntries(request)),
    `kho logistics cần ≥${MIN_ENTRIES} từ published`,
  );
  test.setTimeout(90_000);

  await signUp(page);
  await openWarehouseScene(page);
  const dot = page.locator('[data-object-id="obj-courier"]');
  await expect(dot).toBeVisible({ timeout: 30_000 });

  const x = async () => (await dot.boundingBox())?.x ?? 0;
  await page.waitForTimeout(1200);
  const start = await x();
  await page.waitForTimeout(2500);
  expect(Math.abs((await x()) - start)).toBeGreaterThan(30);

  await page.getByRole("button", { name: "Recall" }).click();
  // Chờ nốt nhịp trôi về neo: `home` giảm theo e^(-4t) nên 2.5s là đã hết trôi.
  await page.waitForTimeout(2500);
  const before = await x();
  await page.waitForTimeout(2500);
  expect(Math.abs(before - (await x()))).toBeLessThan(2);
});

/*
 * Nhãn ĐỨNG YÊN không bao giờ được nhãn khác che. Hộp `Html` của drei phủ một
 * vùng rộng hơn cái pill bên trong, nên khi camera lùi xa và nhiều nhãn xích lại
 * gần nhau, một từ có thể bấm không được trong khi canvas vẫn đẹp — hỏng im lặng
 * mà cả ba bài ở trên đều bỏ sót. `pointerEvents="none"` trên `Html` là bất biến,
 * không phải trang trí.
 *
 * Vật CÓ `patrol` nằm ngoài luật này một cách chủ ý: pill của nó
 * `pointer-events-none` để không nuốt con trỏ của hàng xóm khi quét ngang cảnh;
 * bấm vào thân xe/thân người vẫn ăn vì mesh có `onClick`.
 */
for (const scene of SCENES) {
  test(`mọi hotspot của ${scene.id} đều bấm được`, async ({ page, request }) => {
    const count = await topicEntryCount(request, scene.topicSlug);
    test.skip(
      count < scene.objects.length,
      `${scene.topicSlug} cần ${scene.objects.length} từ, có ${count}`,
    );
    test.setTimeout(120_000);

    await signUp(page);
    await page.goto(`/learn/scenes/${scene.id}`);
    await expect(page.locator("[data-object-id]").first()).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(2500);

    const stillIds = scene.objects.filter((o) => !o.patrol).map((o) => o.id);
    const blocked = await page.evaluate((ids: string[]) => {
      return [...document.querySelectorAll("[data-object-id]")]
        .filter((el) => ids.includes(el.getAttribute("data-object-id") ?? ""))
        .map((el) => {
          const r = el.getBoundingClientRect();
          const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return [el.getAttribute("data-object-id"), !!top && el.contains(top)] as const;
        })
        .filter(([, hit]) => !hit)
        .map(([id]) => id);
    }, stillIds);
    expect(blocked).toEqual([]);
  });
}
