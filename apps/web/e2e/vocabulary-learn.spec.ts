import { type APIRequestContext, type Page, expect, test } from "@playwright/test";

/*
 * Luồng học từ vựng theo chủ đề (`TopicSession`): mở cuốn sách → gõ/lật/chọn →
 * tự chấm bằng năm nút → sang từ kế.
 *
 * Ba chỗ nối mà không lớp nào khác chạm tới, và cả ba đều hỏng IM LẶNG:
 *
 *   · Bàn cờ nằm TRÊN MÁY CHỦ. Nếu `PUT /vocabulary-topic-sessions` không được
 *     gọi, hoặc phía đọc lại không khớp được với hồ từ, thì mọi thứ trông vẫn
 *     bình thường cho tới khi người học F5 và bị ném về từ đầu tiên. Không có
 *     lỗi nào hiện ra, và test backend thì xanh vì endpoint tự nó đúng.
 *   · Bàn cờ thuộc về CHỦ ĐỀ, không thuộc về tab: chuyển gõ từ → thẻ lật là đổi
 *     cách tương tác với CÙNG một từ, không phải bắt đầu lại. Bài này kiểm HÀNH
 *     VI đó chứ không kiểm cơ chế nào tạo ra nó — và đã đo: cho `key` của
 *     component kèm theo tab (tức remount mỗi lần đổi tab) vẫn XANH, vì bàn cờ
 *     nằm trên máy chủ nên lần dựng lại đọc về đúng chỗ cũ. Cái làm nó đỏ là
 *     mất chỗ thật, ví dụ đặt lại `index` khi `mode` đổi.
 *   · Gõ từ đi qua HAI endpoint — `/recall-check` chấm chính tả, `/review` ghi
 *     điểm — và cái bẫy là ghi điểm hai lần cho một từ. Bài này đếm request thật
 *     chứ không tin vào con số hiện trên màn hình.
 *
 * KHÁC `vocabulary.spec.ts`: file kia bị bỏ qua cứng bằng `test.skip(true, …)`
 * vì CI chạy database trắng. Ở đây điều kiện được HỎI LÚC CHẠY — có chủ đề đủ từ
 * thì chạy thật trên ngăn xếp dev, không có thì bỏ qua kèm lý do nói rõ thiếu
 * cái gì. Cùng khuôn với test `integration` phía API: tự bỏ qua khi thiếu điều
 * kiện, chứ không tắt vĩnh viễn — một bài bị tắt cứng thì không bao giờ chạy
 * lại, kể cả sau khi CI đã seed được dữ liệu.
 */

// `request` của Playwright dùng baseURL của trang học (:3000); API ở :8000.
const API_BASE = "http://localhost:8000";

// Trắc nghiệm cần 1 đáp án đúng + 3 nhiễu, nên chủ đề phải có ít nhất bằng đó.
const MIN_ENTRIES = 4;

interface Target {
  itemId: string;
  topicName: string;
  entryCount: number;
}

/**
 * Tìm một cuốn sách mà CHỦ ĐỀ ĐẦU TIÊN của nó đủ từ để học.
 *
 * Phải là chủ đề đầu tiên chứ không phải "một chủ đề bất kỳ": trang tự chọn
 * `topics[0]` khi mở, nên số từ dùng để đối chiếu bộ đếm phải lấy đúng của nó.
 */
async function findLearnableTopic(request: APIRequestContext): Promise<Target | null> {
  const collections = await request.get(`${API_BASE}/api/v1/vocabulary-collections`);
  if (!collections.ok()) return null;

  for (const collection of await collections.json()) {
    const detail = await request.get(
      `${API_BASE}/api/v1/vocabulary-collections/${collection.slug}`,
    );
    if (!detail.ok()) continue;

    for (const item of (await detail.json()).items ?? []) {
      const itemDetail = await request.get(
        `${API_BASE}/api/v1/vocabulary-collection-items/${item.id}`,
      );
      if (!itemDetail.ok()) continue;

      const first = ((await itemDetail.json()).topics ?? [])[0];
      if (first && first.entry_count >= MIN_ENTRIES) {
        return { itemId: item.id, topicName: first.name, entryCount: first.entry_count };
      }
    }
  }
  return null;
}

async function signUp(page: Page): Promise<void> {
  await page.goto("/register");
  await page
    .getByLabel("Email")
    .fill(`vocab-learn-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`);
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

/** "Từ 3/42" — bộ đếm là thứ duy nhất nói ván đang đứng ở đâu. */
function counter(page: Page) {
  return page.getByText(/^Từ \d+\/\d+$/);
}

/** Năm nút tự chấm chỉ hiện sau khi xong phần tương tác. */
function gradePrompt(page: Page) {
  return page.getByText("Bạn nhớ từ này thế nào?");
}

test("gõ một từ rồi tự chấm: ghi ĐÚNG một lượt ôn, và F5 vẫn đứng ở từ kế tiếp", async ({
  page,
  request,
}) => {
  const target = await findLearnableTopic(request);
  test.skip(
    target === null,
    `Ngăn xếp chưa có chủ đề từ vựng nào ≥ ${MIN_ENTRIES} từ — seed nội dung từ vựng trước`,
  );
  const { itemId, entryCount } = target!;

  // Đếm request THẬT: màn hình có thể hiện đúng trong khi phía dưới ghi hai lần.
  const reviewGrades: number[] = [];
  let recallChecks = 0;
  let boardWrites = 0;
  page.on("request", (req) => {
    const url = req.url();
    if (req.method() === "POST" && /\/api\/v1\/vocabulary\/[0-9a-f-]+\/review$/.test(url)) {
      reviewGrades.push(JSON.parse(req.postData() ?? "{}").grade);
    }
    if (req.method() === "POST" && /\/recall-check$/.test(url)) recallChecks += 1;
    if (req.method() === "PUT" && /\/vocabulary-topic-sessions\//.test(url)) boardWrites += 1;
  });

  await signUp(page);
  await page.goto(`/learn/vocabulary/collection-items/${itemId}`);

  await expect(page.getByRole("heading", { name: "Danh sách chủ đề (topic)" })).toBeVisible();
  await expect(counter(page)).toHaveText(`Từ 1/${entryCount}`);

  // Tab mặc định là gõ từ. Gõ SAI có chủ đích: đường sai mới là đường in ra đáp
  // án, và đáp án đúng phải hiện ra thì tự chấm mới có nghĩa.
  const input = page.getByLabel("Viết lại từ tiếng Anh");
  await expect(input).toBeVisible();
  await input.fill("chac-chan-khong-phai-tu-nay");
  await page.getByRole("button", { name: /Kiểm tra/ }).click();
  await expect(page.getByText("Chưa đúng")).toBeVisible();

  // Máy chấm xong thì tới lượt người học tự chấm — KHÔNG có điểm nào được ghi
  // trước bước này.
  await expect(gradePrompt(page)).toBeVisible();
  expect(reviewGrades, "/recall-check không được ghi lượt ôn nào").toHaveLength(0);

  // "Thành thạo" là grade 6 — bậc mở rộng ngoài SM-2 gốc, đưa từ thẳng lên
  // đã-thuộc. Nếu nút này gửi 5 (hoặc endpoint từ chối 6) thì lời hứa của nhãn
  // là sai, mà trên màn hình vẫn thấy sang từ kế như thường.
  await page.getByRole("button", { name: /Thành thạo/ }).click();
  await expect(counter(page)).toHaveText(`Từ 2/${entryCount}`);

  expect(reviewGrades, "một từ, một lượt ôn — không hơn").toEqual([6]);
  expect(recallChecks).toBe(1);
  expect(boardWrites, "mở ván ghi một lần, chấm xong ghi một lần").toBeGreaterThanOrEqual(2);

  // Thanh tiến độ đếm từ ĐÃ CHẤM, đọc lại từ máy chủ chứ không tự cộng ở client.
  await expect(page.getByLabel(`Tiến độ 1 trên ${entryCount} từ`)).toBeVisible();

  // Đây là bài kiểm chính: bàn cờ nằm trên máy chủ, nên tải lại trang phải nối
  // tiếp đúng chỗ. localStorage hay state trong bộ nhớ đều xanh cho tới dòng này.
  await page.reload();
  await expect(counter(page)).toHaveText(`Từ 2/${entryCount}`);
});

test("chuyển giữa ba module vẫn là cùng một ván, và mỗi module tự mở được màn chấm", async ({
  page,
  request,
}) => {
  const target = await findLearnableTopic(request);
  test.skip(
    target === null,
    `Ngăn xếp chưa có chủ đề từ vựng nào ≥ ${MIN_ENTRIES} từ — seed nội dung từ vựng trước`,
  );
  const { entryCount, itemId } = target!;

  await signUp(page);
  await page.goto(`/learn/vocabulary/collection-items/${itemId}`);
  await expect(counter(page)).toHaveText(`Từ 1/${entryCount}`);

  // Gõ từ, lối "Tôi chưa biết": lối ra trung thực, không phải bịa một câu trả lời.
  await page.getByRole("button", { name: "Tôi chưa biết" }).click();
  await expect(page.getByText("Chưa biết từ này")).toBeVisible();
  await page.getByRole("button", { name: /Học lại/ }).click();
  await expect(counter(page)).toHaveText(`Từ 2/${entryCount}`);

  // Đổi tab KHÔNG được xáo lại ván: cùng chủ đề, cùng bàn cờ, chỉ khác cách từ
  // hiện ra.
  await page.getByRole("button", { name: "Thẻ lật" }).click();
  await expect(counter(page)).toHaveText(`Từ 2/${entryCount}`);

  // Thẻ lật: cả tấm thẻ là một cái nút, lật ra mới có gì để tự chấm.
  await expect(gradePrompt(page)).toHaveCount(0);
  await page.getByRole("button", { name: "Lật thẻ để xem nghĩa" }).click();
  await expect(gradePrompt(page)).toBeVisible();
  await page.getByRole("button", { name: /^Dễ/ }).click();
  await expect(counter(page)).toHaveText(`Từ 3/${entryCount}`);

  await page.getByRole("button", { name: "Trắc nghiệm" }).click();
  await expect(counter(page)).toHaveText(`Từ 3/${entryCount}`);

  /*
   * Chỉ kiểm được tới đây: dãy đáp án có hiện ra, và chọn một cái thì mở màn
   * chấm. KHÔNG kiểm chuyện "các lựa chọn phải khác nhau từng đôi một" — dù đó
   * là một quy tắc thật của `buildOptions` (hai từ khác nhau vẫn dịch ra cùng
   * một tiếng Việt, và hai ô chữ y hệt nhau thì chỉ một ô được tô đúng).
   *
   * Lý do: nhiễu bốc ngẫu nhiên 3 trong hơn 40 từ, nên ngay cả khi hồ từ CÓ một
   * cặp trùng nghĩa, xác suất cả cặp cùng rơi vào một câu là vài phần nghìn. Đã
   * thử gây lại lỗi đó và chạy ba lượt: xanh cả ba. Một khẳng định gần như không
   * bao giờ đỏ là chi phí không đổi lấy gì — quy tắc đó sống bằng lập luận viết
   * ngay tại `buildOptions`, không bằng dòng test này.
   */
  const options = page.getByRole("group", { name: "Các nghĩa để chọn" }).getByRole("button");
  await expect(options.first()).toBeVisible();

  await options.first().click();
  await expect(gradePrompt(page)).toBeVisible();
});
