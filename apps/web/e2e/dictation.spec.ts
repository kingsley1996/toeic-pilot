import { type APIRequestContext, expect, test } from "@playwright/test";

/*
 * Gõ xong một câu chép chính tả thì có thông báo tạm, và thông báo đó có tiếng.
 *
 * Bài này bắc qua chỗ nối mà hai phía đứng riêng đều xanh: bộ chấm phía trình
 * duyệt (`lib/dictation.ts`) nói câu đã trọn, còn hàng thông báo phải nghe thấy
 * điều đó ngay trong chính lần bấm phím ấy. Nó đã được kiểm bằng cách làm hỏng
 * thật — bỏ lời gọi `show(...)` trong `check()` thì khẳng định về con toast đỏ
 * lên, và đổi `graded.is_complete` thành `result?.is_complete` (đọc state chưa
 * kịp cập nhật) cũng đỏ.
 *
 * TIẾNG được kiểm bằng REQUEST chứ không bằng tai: `playSound` dựng một
 * `new Audio(src)` rồi gọi `play()`, nên trình duyệt phải đi lấy
 * `/sounds/complete.mp3`. Đó là bằng chứng gần nhất với "đã phát" mà một bài
 * kiểm tự động chạm tới được, và nó đủ để bắt hai lỗi thật: quên gắn `sound`
 * vào thông báo, và đặt file sai chỗ nên 404.
 *
 * Nội dung được lấy qua API chứ không dựng sẵn: bản chép LÀ đáp án và máy chủ cố
 * ý gửi nó cho trình duyệt (xem `DictationDetail.transcript`), nên bài này không
 * cần một câu cố định nào và không hỏng khi nội dung đổi.
 */
const API_BASE = "http://localhost:8000";

function freshEmail(): string {
  return `dictation-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

/** Story đã xuất bản đầu tiên tìm được, đi từ topic xuống. Không có thì trả null. */
async function firstStory(
  request: APIRequestContext,
  token: string,
): Promise<{ storyId: string; transcripts: string[] } | null> {
  const headers = { Authorization: `Bearer ${token}` };

  const topics = await request.get(`${API_BASE}/api/v1/dictation-topics`, { headers });
  if (!topics.ok()) return null;

  for (const topic of await topics.json()) {
    const detail = await request.get(`${API_BASE}/api/v1/dictation-topics/${topic.id}`, {
      headers,
    });
    if (!detail.ok()) continue;
    for (const section of (await detail.json()).sections ?? []) {
      const inSection = await request.get(`${API_BASE}/api/v1/dictation-sections/${section.id}`, {
        headers,
      });
      if (!inSection.ok()) continue;
      for (const story of (await inSection.json()).stories ?? []) {
        const full = await request.get(`${API_BASE}/api/v1/dictation-stories/${story.id}`, {
          headers,
        });
        if (!full.ok()) continue;
        const items = (await full.json()).items ?? [];
        // Cần HAI câu: câu đầu để kiểm tiếng có kêu, câu sau để kiểm nút tắt
        // tiếng thật sự tắt được.
        const transcripts = items
          .map((item: { transcript?: string }) => item.transcript)
          .filter((t: string | undefined): t is string => Boolean(t));
        if (transcripts.length >= 2) return { storyId: story.id, transcripts };
      }
    }
  }
  return null;
}

test("gõ đúng một câu thì có thông báo tạm kèm tiếng báo", async ({ page, request }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  expect(token).toBeTruthy();

  const story = await firstStory(request, token as string);
  test.skip(story === null, "cần một story dictation đã xuất bản có từ hai câu trở lên");

  await page.goto(`/learn/dictation/stories/${story!.storyId}`);
  const box = page.getByPlaceholder("Gõ lại những gì bạn nghe được…");
  await expect(box).toBeVisible();

  // Rình sẵn TRƯỚC khi gõ: chờ sau khi tiếng đã phát xong là chờ một thứ đã đi qua.
  const soundRequest = page.waitForRequest((r) => r.url().includes("/sounds/complete.mp3"), {
    timeout: 10_000,
  });

  await box.fill(story!.transcripts[0]);
  await box.press("Enter");

  // Khối kết quả ngay dưới ô nhập vẫn nói câu của nó…
  await expect(page.getByText("Đúng rồi — bạn đã nghe ra cả câu.")).toBeVisible();
  // …còn đây là con toast, trong vùng `aria-live` lịch sự. Bám theo `role` chứ
  // không theo chữ trần: hai chỗ cùng mở đầu bằng "Đúng rồi".
  await expect(page.getByRole("status").getByText("Đúng rồi", { exact: true })).toBeVisible();

  await soundRequest;

  /*
   * Và nút tắt tiếng phải TẮT ĐƯỢC THẬT.
   *
   * Đây là thứ dễ hỏng lặng lẽ nhất trong cả tính năng: thông báo vẫn hiện,
   * chữ vẫn đúng, chỉ có cái công tắc là không còn tác dụng — và người duy nhất
   * phát hiện ra là người đã tắt nó vì đang ngồi chỗ đông người.
   *
   * Khẳng định phủ định ở cuối chỉ có nghĩa vì nó đứng SAU một khẳng định
   * dương từ cùng lần gõ: con toast phải hiện ra trước, rồi mới hỏi tới việc
   * KHÔNG có request nào cho file tiếng. Đếm từ lúc nạp lại trang, nên tiếng
   * của câu trước không tính vào đây.
   */
  await page.evaluate(() => window.localStorage.setItem("sound", "off"));
  await page.goto(`/learn/dictation/stories/${story!.storyId}`);

  let soundHits = 0;
  page.on("request", (r) => {
    if (r.url().includes("/sounds/complete.mp3")) soundHits += 1;
  });

  const nextBox = page.getByPlaceholder("Gõ lại những gì bạn nghe được…");
  await expect(nextBox).toBeVisible();
  await nextBox.fill(story!.transcripts[1]);
  await nextBox.press("Enter");

  await expect(page.getByRole("status").getByText("Đúng rồi", { exact: true })).toBeVisible();
  expect(soundHits).toBe(0);
});
