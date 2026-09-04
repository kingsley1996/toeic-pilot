import { type APIRequestContext, expect, test } from "@playwright/test";

import { skipTour } from "./support";

/*
 * Huy hiệu (USER-ROAD §4).
 *
 * Chỗ nối đáng kiểm là VÒNG ĐỜI của chấm đỏ, vì nó đi qua ba lớp và không lớp
 * nào tự thấy được cả vòng: điều kiện suy ra từ lịch sử học ở máy chủ → hàng
 * `user_badge` ghi lười trong chính lần đọc → `POST .../seen` tắt chấm khi
 * người dùng MỞ TRANG, chứ không khi họ lướt qua trang chủ.
 *
 * Hỏng thì hỏng im lặng theo hai hướng ngược nhau, và cả hai đều không phải lỗi
 * ai báo được: đánh dấu quá sớm thì thông báo dẫn người ta tới một trang không
 * còn gì mới, còn không đánh dấu thì chấm đỏ ở lại vĩnh viễn và mất hết ý nghĩa.
 */

const API_BASE = "http://localhost:8000";

function freshEmail(): string {
  return `badge-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

/** Chép đúng trọn một câu — đủ để mở `first_steps`? Không: đó là badge của lượt
 * ÔN TỪ. Dictation mở `dictation_10`, cần 10 câu. Nên bài này dùng lượt ôn. */
async function reviewOneWord(request: APIRequestContext, token: string): Promise<boolean> {
  const auth = { Authorization: `Bearer ${token}` };
  const session = await request.get(`${API_BASE}/api/v1/vocabulary-review/session`, {
    headers: auth,
  });
  if (!session.ok()) return false;
  const card = (await session.json()).cards?.[0];
  if (!card) return false;

  // Chấm điểm nằm trên chính từ đó (`/vocabulary/{id}/review`), không phải trên
  // phiên ôn: phiên chỉ phát thẻ, còn thứ được ghi là trạng thái SM-2 của từ.
  const result = await request.post(`${API_BASE}/api/v1/vocabulary/${card.id}/review`, {
    headers: auth,
    data: { grade: 4 },
  });
  return result.ok();
}

test("huy hiệu đầu tiên: báo ở trang chủ, mở trang thì tắt chấm đỏ", async ({ page, request }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  expect(token).toBeTruthy();

  const reviewed = await reviewOneWord(request, token as string);
  test.skip(!reviewed, "cần ít nhất một từ đã xuất bản để ôn");

  // Trang chủ báo, và báo bằng MỘT dòng chứ không phải một dòng mỗi huy hiệu.
  await page.reload();
  const notice = page.getByText(/Bạn vừa mở 1 huy hiệu/);
  await expect(notice).toBeVisible();

  /*
   * Cùng lúc đó, thông báo tạm gọi thẳng TÊN huy hiệu — thứ mà dòng cố định
   * không nói, vì nó phải gộp mọi huy hiệu vào một câu. Nó nằm trong vùng
   * `aria-live` lịch sự, nên trình đọc màn hình cũng nghe được mà không cần đi
   * tìm.
   */
  await expect(page.getByRole("status").getByText("Huy hiệu mới: Bước đầu tiên")).toBeVisible();

  // Bấm ĐÚNG dòng cố định, không phải con toast: cả hai cùng dẫn tới
  // `/profile/badges`, nên một locator chỉ theo tên sẽ khớp hai phần tử.
  await page.getByRole("link", { name: /Bạn vừa mở 1 huy hiệu/ }).click();
  await expect(page).toHaveURL(/\/profile\/badges$/);

  // Nhãn MỚI phải còn thấy được trong ĐÚNG lượt xem này — nếu đánh dấu đã xem
  // trước khi dựng thì người dùng mở ra và không thấy gì mới cả.
  // Bám vào Ô huy hiệu chứ không vào cả trang: con toast đi theo qua lần chuyển
  // trang phía client — đúng như nó phải thế — và nó cũng in tên huy hiệu, nên
  // một locator theo chữ trần khớp cả hai.
  const tile = page.getByRole("listitem").filter({ hasText: "Bước đầu tiên" });
  await expect(tile).toBeVisible();
  await expect(tile.getByText("Mới", { exact: true })).toBeVisible();
  // Huy hiệu chưa mở vẫn hiện, kèm tiến độ: đó là thứ nói "còn bao xa". Bám
  // theo mô tả chứ không theo con số — "0/50" xuất hiện ở cả huy hiệu 50 từ lẫn
  // 50 câu chép, và một locator khớp hai ô là một locator không nói được ô nào.
  await expect(page.getByRole("listitem").filter({ hasText: "Thuộc 50 từ" })).toContainText("0/50");

  // Và lần sau thì hết chấm đỏ.
  //
  // Thứ tự hai khẳng định dưới đây là bắt buộc, và đã đo: `toHaveCount(0)` đúng
  // ngay lập tức với một trang CHƯA tải xong, nên đặt nó trước sẽ xanh kể cả khi
  // `POST .../seen` không hề được gọi. Chờ một thứ CÓ mặt trước — cả hai đến từ
  // cùng một lần đọc, nên khi ô huy hiệu đã hiện thì nhãn MỚI cũng đã có cơ hội
  // hiện ra rồi.
  await page.goto("/profile/badges");
  await expect(page.getByRole("listitem").filter({ hasText: "Bước đầu tiên" })).toBeVisible();
  await expect(page.getByText("Mới", { exact: true })).toHaveCount(0);
});
