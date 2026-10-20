import { type APIRequestContext, expect, test } from "@playwright/test";

import { skipTour } from "./support";

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
export async function firstStory(
  request: APIRequestContext,
  token: string,
): Promise<{
  storyId: string;
  items: Array<{ id: string; transcript: string; transcript_vi: string | null }>;
} | null> {
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
        const raw = (await full.json()).items ?? [];
        // Cần HAI câu: câu đầu để kiểm tiếng có kêu, câu sau để kiểm nút tắt
        // tiếng thật sự tắt được.
        const items = raw
          .filter((item: { transcript?: string }) => Boolean(item.transcript))
          .map((item: { id: string; transcript: string; transcript_vi?: string | null }) => ({
            id: item.id,
            transcript: item.transcript,
            transcript_vi: item.transcript_vi ?? null,
          }));
        if (items.length >= 2) return { storyId: story.id, items };
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
  await skipTour(page);

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

  await box.fill(story!.items[0].transcript);
  await box.press("Enter");

  // Khối kết quả ngay dưới ô nhập vẫn nói câu của nó…
  await expect(page.getByText("Đúng rồi — bạn đã nghe ra cả câu.")).toBeVisible();
  // …và mở nghĩa của câu, thứ chỉ có sau khi chấm đúng (hiện trước là lộ đáp án).
  const meaning = story!.items[0].transcript_vi;
  if (meaning) await expect(page.getByText(meaning, { exact: true })).toBeVisible();
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
  await nextBox.fill(story!.items[1].transcript);
  await nextBox.press("Enter");

  await expect(page.getByRole("status").getByText("Đúng rồi", { exact: true })).toBeVisible();
  expect(soundHits).toBe(0);
});

test("nghe ngẫu nhiên: bấm câu khác thì ra câu khác thật", async ({ page, request }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  /*
   * Bỏ qua khi kho rỗng, HỎI Ở THỜI ĐIỂM CHẠY — và đây là chỗ đã đỏ suốt bảy
   * lần chạy CI liên tiếp.
   *
   * Hai bài trên đã có cổng này qua `firstStory(...) === null`; bài này thì
   * không, nên trên CI — nơi database chỉ được seed thang điểm và một đề demo,
   * không có câu chép chính tả nào — trang không dựng nổi thẻ audio và khẳng
   * định đầu tiên hết giờ. Ở máy dev thì kho có gần bốn chục câu nên nó luôn
   * xanh: đúng loại lỗi chỉ CI mới thấy, và nó đã che mất mọi lần đỏ THẬT của
   * job này kể từ đó.
   *
   * Hỏi máy chủ chứ không `test.skip(true, …)`: một bài bị tắt cứng thì không
   * bao giờ chạy lại, kể cả khi CI đã seed được nội dung — cùng bài học mà
   * `vocabulary.spec.ts` và `vocabulary-learn.spec.ts` đã ghi.
   */
  const sample = await request.get(`${API_BASE}/api/v1/dictation-random`);
  test.skip(!sample.ok(), "cần ít nhất một câu chép chính tả đã xuất bản");

  await page.goto("/learn/dictation/random");

  /*
   * Bám theo `src` của thẻ audio, không theo chữ trên màn hình.
   *
   * Câu chưa gõ thì không in ra ở đâu cả — cả trang chỉ có số từ, mà hai câu
   * khác nhau hoàn toàn có thể cùng số từ. `src` là khoá nội dung của chính bản
   * thu, nên nó phân biệt được hai câu bất kỳ.
   *
   * ĐÃ ĐO và KHÔNG bắt được: bỏ hẳn `exclude` ở phía client thì bài này vẫn
   * xanh, bốn lần chạy liền. Kho đang có gần bốn chục câu nên xác suất bốc trúng
   * lại câu cũ chỉ cỡ 1/38 — quá thấp để một bài kiểm dựa vào. Thứ bài này thật
   * sự canh là cái nút CÓ bốc lại hay không; còn `exclude` thì
   * `test_random_skips_the_sentence_just_heard` phía API canh, với kho hai câu
   * và năm vòng lặp, nên ở đó nó là điều chắc chắn chứ không phải may rủi.
   */
  const audio = page.locator("audio");
  await expect(audio).toHaveAttribute("src", /.+/);
  const first = await audio.getAttribute("src");

  await page.getByRole("button", { name: "Câu khác" }).click();
  await expect(audio).not.toHaveAttribute("src", first as string);
});

test("xong hết một bài thì có lối đi tiếp", async ({ page, request }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const story = await firstStory(request, token as string);
  test.skip(story === null, "cần một story dictation đã xuất bản có từ hai câu trở lên");

  // Làm xong CẢ bài qua API: thứ đang kiểm là khối đi tiếp, không phải luồng gõ
  // — luồng đó đã có đường kiểm riêng ngay bài trên.
  for (const item of story!.items) {
    await request.post(`${API_BASE}/api/v1/dictation/${item.id}/attempts`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { submitted_text: item.transcript },
    });
  }

  await page.goto(`/learn/dictation/stories/${story!.storyId}`);
  await expect(page.getByText("Xong bài này")).toBeVisible();

  // Đi tiếp phải dẫn tới một chỗ CÓ THẬT trong cây, không phải một liên kết chết.
  const go = page.getByRole("link", { name: /Đi tiếp/ });
  await expect(go).toBeVisible();
  await go.click();
  await expect(page).toHaveURL(/\/learn\/dictation\/(stories|sections|topics)\/[0-9a-f-]+$/);
});

test("câu cuối đúng thì Enter đi tiếp sang bài kế", async ({ page, request }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const story = await firstStory(request, token as string);
  test.skip(story === null, "cần một story dictation đã xuất bản có từ hai câu trở lên");

  // Xong hết trừ câu cuối qua API: câu cuối là câu duy nhất còn mở, và cũng là
  // câu làm cả bài xong — đúng lúc Enter phải rời bài thay vì chấm lại.
  const headers = { Authorization: `Bearer ${token}` };
  for (const item of story!.items.slice(0, -1)) {
    await request.post(`${API_BASE}/api/v1/dictation/${item.id}/attempts`, {
      headers,
      data: { submitted_text: item.transcript },
    });
  }

  await page.goto(`/learn/dictation/stories/${story!.storyId}`);
  const box = page.getByPlaceholder("Gõ lại những gì bạn nghe được…");
  const last = story!.items[story!.items.length - 1];
  await box.fill(last.transcript);
  await box.press("Enter");
  await expect(page.getByText("Đúng rồi — bạn đã nghe ra cả câu.")).toBeVisible();
  await expect(page.getByText("Xong bài này")).toBeVisible();

  // Đích "Đi tiếp" do panel phía trên tìm qua API, nên chờ nút dưới ô nhập
  // xuất hiện — đó là dấu Enter đã có chỗ để đi.
  await expect(page.getByRole("button", { name: "Đi tiếp" })).toBeVisible();
  const before = page.url();
  await box.press("Enter");
  await expect(page).not.toHaveURL(before);
  await expect(page).toHaveURL(/\/learn\/dictation\/(stories|sections|topics)\/[0-9a-f-]+$/);
});

test("gợi ý có giá và chế độ điền từng từ vẫn chấm như gõ cả câu", async ({ page, request }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const story = await firstStory(request, token as string);
  test.skip(story === null, "cần một story dictation đã xuất bản có từ hai câu trở lên");

  await page.goto(`/learn/dictation/stories/${story!.storyId}`);

  /*
   * Bậc gợi ý đi một chiều, và bậc cuối có giá.
   *
   * Mở đáp án rồi chép lại vẫn ra bài đúng từng từ — đó là chuyện bộ chấm phải
   * làm — nhưng câu đó không được tính là đã nghe ra. Hai vế cùng khẳng định
   * dưới đây mới phân biệt được "chấm đúng" với "được tính".
   */
  await page.getByRole("button", { name: "Gợi ý chữ đầu" }).click();
  // Chữ đầu của từng từ còn lại là dấu sao; đáp án đầy đủ thì chưa được in ra.
  await expect(page.getByText(/[A-Za-z]\*{2,}/).first()).toBeVisible();
  await expect(page.getByText(story!.items[0].transcript)).toHaveCount(0);

  await page.getByRole("button", { name: "Xem đáp án" }).click();
  await expect(page.getByText(story!.items[0].transcript)).toBeVisible();
  await expect(
    page.getByText("Đã xem đáp án — lượt gõ tiếp theo không tính vào tiến độ."),
  ).toBeVisible();

  await page.getByRole("checkbox", { name: "Gõ từng từ" }).check();
  const boxes = page.getByRole("textbox", { name: /^Từ thứ/ });
  const words = story!.items[0].transcript
    .toLowerCase()
    .replace(/[^a-z0-9'\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  await expect(boxes).toHaveCount(words.length);

  // Bộ gõ commit cả từ kèm dấu cách trong MỘT sự kiện input (không có keydown
  // để chặn): ô cũ phải sạch dấu cách, focus sang ô sau, và không dồn chữ sang.
  await boxes.nth(0).fill(`${words[0]} `);
  await expect(boxes.nth(0)).toHaveValue(words[0]);
  await expect(boxes.nth(1)).toBeFocused();
  await expect(boxes.nth(1)).toHaveValue("");
  await boxes.nth(0).fill("");

  for (const [index, word] of words.entries()) {
    await boxes.nth(index).fill(word);
    if (index < words.length - 1) {
      await boxes.nth(index).press(" ");
      // Dấu cách là đường đi sang ô sau, không phải ký tự trong từ.
      await expect(boxes.nth(index + 1)).toBeFocused();
      await expect(boxes.nth(index + 1)).toHaveValue("");
    }
  }
  // Nút Kiểm tra phải sống khi chữ nằm trong các ô, không chỉ khi ở textarea.
  await expect(page.getByRole("button", { name: "Kiểm tra" })).toBeEnabled();
  await boxes.nth(words.length - 1).press("Enter");

  // Chấm xong không được kéo con trỏ về ô đầu: mắt và tay đang ở ô vừa gõ.
  await expect(boxes.nth(words.length - 1)).toBeFocused();
  await expect(
    page.getByText("Đã chép đúng — nhưng đáp án đã xem nên câu này không tính vào tiến độ."),
  ).toBeVisible();

  /*
   * Chấm bằng NÚT rồi Enter phải đi tiếp. Con trỏ về ô cuối, và phím Enter rơi
   * vào ô đó chứ không rơi vào nút "Kiểm tra" — nếu rơi vào nút thì mỗi lần bấm
   * Enter chỉ chấm lại câu cũ, không bao giờ sang câu sau.
   */
  await page.getByRole("button", { name: "Kiểm tra" }).click();
  await expect(boxes.nth(words.length - 1)).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByTitle(/^Câu 2 ·/)).toHaveAttribute("aria-current", "true");
});

test("từ đúng nhưng lệch ô thì ô trống không được tô đúng", async ({ page, request }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const story = await firstStory(request, token as string);
  test.skip(story === null, "cần một story dictation đã xuất bản có từ hai câu trở lên");

  await page.goto(`/learn/dictation/stories/${story!.storyId}`);
  await page.getByRole("checkbox", { name: "Gõ từng từ" }).check();

  const words = story!.items[0].transcript
    .toLowerCase()
    .replace(/[^a-z0-9'\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  test.skip(words.length < 3, "cần ít nhất ba từ");

  const boxes = page.getByRole("textbox", { name: /^Từ thứ/ });
  // Từ thứ hai nằm ở ô 1 (lệch một ô); ô 0 để trống. Chuỗi gộp vẫn khớp phần
  // còn lại, nên bộ chấm theo chuỗi cũ sẽ tô ô 0 là "thiếu" và ô 1 là "đúng".
  await boxes.nth(0).fill(words[1]);
  for (let index = 2; index < words.length; index += 1) {
    await boxes.nth(index).fill(words[index]);
  }
  await boxes.nth(words.length - 1).press("Enter");

  await expect(page.getByText("Chưa đúng — đối chiếu")).toBeVisible();
  // Ô trống phải là "thiếu", không được xanh chỉ vì từ ở ô bên cạnh khớp chuỗi.
  await expect(boxes.nth(1)).toHaveClass(/border-b-warn/);
  await expect(boxes.nth(2)).toHaveClass(/border-b-ok/);
});

test("bỏ trống một từ rồi chấm không được lộ đáp án", async ({ page, request }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const story = await firstStory(request, token as string);
  test.skip(story === null, "cần một story dictation đã xuất bản có từ hai câu trở lên");

  await page.goto(`/learn/dictation/stories/${story!.storyId}`);
  await page.getByRole("checkbox", { name: "Gõ từng từ" }).check();

  const boxes = page.getByRole("textbox", { name: /^Từ thứ/ });
  const words = story!.items[0].transcript
    .toLowerCase()
    .replace(/[^a-z0-9'\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  // Từ duy nhất trong câu để khẳng định "không xuất hiện" không bắt nhầm từ
  // trùng ở vị trí khác (kể cả từ đã gõ đúng).
  const blank = words.findIndex((word) => words.filter((other) => other === word).length === 1);
  test.skip(blank === -1, "cần một từ duy nhất trong câu");

  let lastFilled = 0;
  for (const [index, word] of words.entries()) {
    if (index === blank) continue;
    await boxes.nth(index).fill(word);
    lastFilled = index;
  }
  await boxes.nth(lastFilled).press("Enter");

  await expect(page.getByText("Chưa đúng — đối chiếu")).toBeVisible();
  // Lỗ hổng cũ: gõ các từ sau rồi để trống từ trước, chấm xong là đọc được
  // nguyên từ còn thiếu. Giờ nó phải là dấu sao, không phải chữ.
  await expect(page.getByText(words[blank], { exact: true })).toHaveCount(0);
});

test("độ khó: ít chỗ trống để một phần tư câu, nhiều chỗ trống để một nửa", async ({
  page,
  request,
}) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await skipTour(page);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const story = await firstStory(request, token as string);
  test.skip(story === null, "cần một story dictation đã xuất bản có từ hai câu trở lên");

  const wordsOf = (text: string) =>
    text
      .toLowerCase()
      .replace(/[^a-z0-9'\s]/g, " ")
      .split(/\s+/)
      .filter(Boolean);
  const words = wordsOf(story!.items[0].transcript);
  test.skip(words.length < 5, "cần ít nhất năm từ");

  await page.goto(`/learn/dictation/stories/${story!.storyId}`);
  const blanks = () => page.getByRole("textbox", { name: /^Từ thứ/ });
  const few = words.map((_, index) => index).filter((index) => index % 4 === 0);
  const many = words.map((_, index) => index).filter((index) => index % 2 === 0);

  await page.getByRole("button", { name: "Ít chỗ trống" }).click();
  await expect(blanks()).toHaveCount(few.length);
  // Câu đã hiện sẵn chữ, nhưng chưa gõ chỗ trống nào thì chưa có gì để chấm.
  await expect(page.getByRole("button", { name: "Kiểm tra" })).toBeDisabled();
  await expect(page.getByText(words[1], { exact: true }).first()).toBeVisible();

  await blanks().nth(0).fill(words[0]);
  await expect(page.getByRole("button", { name: "Kiểm tra" })).toBeEnabled();
  // Dấu cách nhảy qua các từ hiện sẵn, tới chỗ trống kế tiếp.
  await blanks().nth(0).press(" ");
  await expect(blanks().nth(1)).toBeFocused();

  for (const [order, index] of few.entries()) {
    await blanks().nth(order).fill(words[index]);
  }
  await blanks()
    .nth(few.length - 1)
    .press("Enter");
  await expect(page.getByText("Đúng rồi — bạn đã nghe ra cả câu.")).toBeVisible();

  /*
   * Chấm bằng NÚT cũng phải trả con trỏ về ô đang gõ. Không thì Enter kế tiếp
   * rơi trúng nút "Kiểm tra" vừa bấm: câu đúng rồi mà bấm Enter mãi không sang
   * câu sau, đúng lỗi đã gặp ở chế độ ít/nhiều chỗ trống.
   */
  await page.getByRole("button", { name: "Kiểm tra" }).click();
  await expect(blanks().nth(few.length - 1)).toBeFocused();

  await page.getByRole("button", { name: "Nhiều chỗ trống" }).click();
  await expect(blanks()).toHaveCount(many.length);
  // Đổi mức là kết quả cũ phải biến mất, không đứng lại bên các ô mới.
  await expect(page.getByText("Đúng rồi — bạn đã nghe ra cả câu.")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Kiểm tra" })).toBeDisabled();

  // Mức đã chọn sống sang câu sau — đi bằng dải số câu ở đầu trang.
  await page.getByTitle(/^Câu 2 ·/).click();
  const nextWords = wordsOf(story!.items[1].transcript);
  await expect(blanks()).toHaveCount(nextWords.filter((_, index) => index % 2 === 0).length);
});
