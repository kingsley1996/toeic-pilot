import { expect, test, type Page } from "@playwright/test";

import { skipTour } from "./support";

/*
 * Listening Lab slice YouTube: dán link → tạo bài từ phụ đề → chép chính tả.
 *
 * Một test duy nhất, một lần đăng ký: Turnstile đôi khi từ chối lượt kiểm thứ
 * hai liên tiếp trong trình duyệt tự động, nên chia hai test là xin flake.
 *
 * Phát lại THẬT không khẳng định: CI không có loa/mạng ổn định cho iframe
 * YouTube, và tiếng đã có bài dictation.spec.ts giữ. Ở đây chỉ cần player dựng
 * lên không vỡ trang — phần nghe-chép (grade, lưu bài, tiến độ) mới là thứ slice
 * này phải giữ.
 *
 * oEmbed và lấy phụ đề được chặn (route stub): cả hai là mạng ngoài, để chúng
 * gọi thật là bắt bài kiểm chờ một thứ không thuộc về mình.
 */

const VIDEO_ID = "dQw4w9WgXcQ";
const YOUTUBE_URL = `https://www.youtube.com/watch?v=${VIDEO_ID}`;
// Kịch bản đúng dùng video khác kịch bản hỏng: cùng URL thì app giữ tên user
// đã gõ (đúng hành vi), còn test cần ô tên reset để kiểm oEmbed tự điền.
const YOUTUBE_URL_2 = "https://www.youtube.com/watch?v=AAAAAAAAAAA";

function freshEmail(): string {
  return `listening-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

async function register(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);
}

test("lab youtube: link hỏng báo ngay, phụ đề hỏng không tạo bài, bài đúng học được", async ({
  page,
}) => {
  // Lượt oEmbed đầu giả vờ hỏng (kịch bản phụ đề hỏng phải gõ tên tay), các
  // lượt sau trả tên stub.
  let oembedCalls = 0;
  await page.route("https://www.youtube.com/oembed**", async (route) => {
    oembedCalls += 1;
    if (oembedCalls === 1) await route.fulfill({ status: 404, body: "nope" });
    else await route.fulfill({ json: { title: "Stubbed Video Title" } });
  });
  await page.route("**/api/v1/listening/captions", async (route) => {
    await route.fulfill({
      status: 422,
      contentType: "application/json",
      json: { detail: { code: "CAPTIONS_UNAVAILABLE" } },
    });
  });
  await register(page);

  await page.goto("/learn/listening?create=1");
  const urlBox = page.getByPlaceholder("https://www.youtube.com/watch?v=…");

  await urlBox.fill("chữ này không phải link");
  await page.getByRole("button", { name: "Tiếp tục" }).click();
  await expect(page.getByText("Link chưa đúng — kiểm tra lại URL video YouTube.")).toBeVisible();

  await urlBox.fill("https://www.tiktok.com/@u/video/123");
  await page.getByRole("button", { name: "Tiếp tục" }).click();
  await expect(
    page.getByText("Mục này mới chỉ nhận link YouTube (bài TikTok có sẵn trong thư viện)."),
  ).toBeVisible();

  // Kịch bản phụ đề hỏng: oEmbed hỏng nên tên phải gõ tay; phụ đề rác thì
  // backend từ chối đúng dòng lỗi và không tạo bài (vẫn ở nguyên trang).
  await urlBox.fill(YOUTUBE_URL);
  await page.getByRole("button", { name: "Tiếp tục" }).click();
  await expect(page.getByText("Video này không có phụ đề công khai")).toBeVisible();
  await page.getByPlaceholder("VD: Business Meeting — New Schedule").fill("Bài hỏng");
  await page.getByPlaceholder(/Hello everyone/).fill("đây không phải srt");
  await page.getByRole("button", { name: "Tạo bài học" }).click();
  await expect(page.getByText("Transcript is empty")).toBeVisible();
  await expect(page).toHaveURL(/\/learn\/listening(\?create=1)?$/);

  // Kịch bản đúng: đổi link (oEmbed lần này trả tên), chép mẫu, tạo bài, học.
  await page.getByRole("button", { name: "Đổi link khác" }).click();
  await page.getByPlaceholder("https://www.youtube.com/watch?v=…").fill(YOUTUBE_URL_2);
  await page.getByRole("button", { name: "Tiếp tục" }).click();
  await expect(page.getByRole("link", { name: YOUTUBE_URL_2 })).toBeVisible();
  await expect(page.getByPlaceholder("VD: Business Meeting — New Schedule")).toHaveValue(
    "Stubbed Video Title",
  );

  await page.getByRole("button", { name: "Chép mẫu thử" }).click();
  await page.getByRole("button", { name: "Tạo bài học" }).click();
  await expect(page).toHaveURL(/\/learn\/listening\/[0-9a-f-]+$/);

  // Hai câu mẫu có mặt, ô chép hiện ra. Chưa câu nào lộ lời: tên nút chỉ có
  // sao che, chữ thật tìm trong list không thấy.
  await expect(page.getByTitle("Câu 1 · chưa đúng")).toBeVisible();
  await expect(page.getByPlaceholder("Gõ lại những gì bạn nghe được…")).toBeVisible();
  const answer = "Hello everyone, welcome back.";
  await expect(page.getByRole("button", { name: answer })).toHaveCount(0);

  // Gõ đúng nguyên văn câu 1 → đúng trọn, dòng transcript mở ra, nút sang câu
  // sau hiện ra.
  const box = page.getByPlaceholder("Gõ lại những gì bạn nghe được…");
  await box.fill(answer);
  await box.press("Enter");
  await expect(page.getByText("Đúng rồi — bạn đã nghe ra cả câu.")).toBeVisible();
  await expect(page.getByRole("button", { name: answer })).toHaveCount(1);

  await page.getByRole("button", { name: "Câu tiếp theo" }).click();
  const box2 = page.getByPlaceholder("Gõ lại những gì bạn nghe được…");
  await box2.fill("nonsense words here");
  await box2.press("Enter");
  await expect(page.getByText("Chưa đúng — đối chiếu")).toBeVisible();

  // Lịch sử được lưu: eyebrow trang học hiện 1/2 (hub đã ẩn mục "Bài đã tạo"
  // nên không đọc ở đó nữa).
  await expect(page.getByText("YouTube · 1/2 câu đã đúng")).toBeVisible();
});
