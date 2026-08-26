import { type APIRequestContext, expect, test } from "@playwright/test";

/*
 * Ba việc hôm nay trên `/dashboard` (USER-ROAD §6).
 *
 * Bài này bắc qua ĐÚNG chỗ nối mà cả hai phía đều xanh khi đứng riêng: máy chủ
 * suy ra tiến độ từ hoạt động trong ngày và trao XP ngay trong lần đọc, còn
 * trình duyệt phải in ra cả hai thứ đó cùng lúc. Nó đã được kiểm bằng cách làm
 * hỏng thật hai lần: ẩn dòng việc đã xong khỏi danh sách, và bỏ phần trao
 * thưởng ở `GET /daily-tasks` — mỗi lần một khẳng định khác nhau đỏ lên.
 *
 * ĐÃ ĐO và KHÔNG bắt được: đọc hai endpoint SONG SONG thay vì nối tiếp vẫn xanh
 * ba lần chạy liền. Thứ tự đó vẫn đúng và lý do nằm ở `daily-tasks.tsx` — đọc
 * điểm trước khi thưởng kịp ghi thì việc đóng lại mà điểm không nhích — nhưng
 * đây là một cuộc đua vài mili giây, nên đừng tin bài này canh giùm nó.
 *
 * Hoạt động được làm qua API chứ không qua giao diện dictation: luồng dictation
 * đã có đường kiểm riêng, và dựng lại nó ở đây chỉ làm bài chậm và dễ vỡ mà
 * không kiểm thêm thứ gì thuộc về khối này.
 */
const API_BASE = "http://localhost:8000";

/** Số câu dictation phải làm đúng trọn để đóng khe 2 — bằng `TARGET_DICTATION`. */
const DICTATION_TARGET = 3;

function freshEmail(): string {
  return `daily-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

/**
 * Làm đúng trọn `DICTATION_TARGET` câu, trả về số câu thật sự hoàn thành.
 *
 * Bản chép được lấy từ chính `GET /dictation/{id}` — đó là đáp án và máy chủ cố
 * ý gửi nó về cho trình duyệt (xem `DictationDetail.transcript`), nên ở đây
 * không cần dữ liệu cố định nào.
 */
async function completeDictation(request: APIRequestContext, token: string): Promise<number> {
  const auth = { Authorization: `Bearer ${token}` };
  const list = await request.get(`${API_BASE}/api/v1/dictation?limit=${DICTATION_TARGET}`, {
    headers: auth,
  });
  if (!list.ok()) return 0;

  let done = 0;
  for (const row of (await list.json()).items ?? []) {
    const detail = await request.get(`${API_BASE}/api/v1/dictation/${row.id}`, { headers: auth });
    if (!detail.ok()) continue;
    const result = await request.post(`${API_BASE}/api/v1/dictation/${row.id}/attempts`, {
      headers: auth,
      data: { submitted_text: (await detail.json()).transcript },
    });
    if (result.ok() && (await result.json()).is_complete) done += 1;
  }
  return done;
}

test("tài khoản mới thấy ba việc, làm xong một việc thì nó đóng và XP tăng", async ({
  page,
  request,
}) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const panel = page.getByRole("region", { name: "Việc hôm nay" });
  await expect(panel.getByRole("link", { name: /Ôn từ vựng/ })).toBeVisible();
  await expect(panel.getByRole("link", { name: /Nghe chép chính tả/ })).toBeVisible();
  await expect(panel.getByRole("link", { name: /Luyện đề/ })).toBeVisible();
  // Tài khoản mới chưa làm gì, nên con số XP hôm nay phải là 0 — không phải
  // "chưa có". Khối này in ra một cái thang, và một cái thang không có mốc bắt
  // đầu thì không đọc được.
  await expect(panel.getByText(/0\/120 XP hôm nay/)).toBeVisible();

  /*
   * Chưa làm gì thì KHÔNG có thông báo tạm. Khẳng định phủ định này chỉ có
   * nghĩa vì nó đứng SAU mấy dòng trên: `toHaveCount(0)` được thoả ngay lập tức
   * trên một trang chưa nạp xong, nên phải neo vào một thứ CÓ THẬT dựng ra từ
   * cùng lần đọc ấy — ở đây là con số XP — rồi mới hỏi tới cái vắng mặt.
   */
  const toasts = page.getByRole("status").getByText("Đã xong việc hôm nay");
  await expect(toasts).toHaveCount(0);

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  expect(token).toBeTruthy();

  const completed = await completeDictation(request, token as string);
  test.skip(
    completed < DICTATION_TARGET,
    `cần ${DICTATION_TARGET} câu dictation đã xuất bản, chỉ hoàn thành được ${completed}`,
  );

  await page.reload();

  // Việc đã đóng: dòng nghe chép biến khỏi danh sách việc-còn-lại và đếm còn 2.
  await expect(panel.getByText(/Xong 1\/3 việc/)).toBeVisible();
  await expect(panel.getByText(/3\/3\s*câu đúng trọn/)).toBeVisible();

  // Và XP đã nhích TRONG CÙNG lần dựng đó: 3 câu × 5 + 10 thưởng việc = 25.
  await expect(panel.getByText(/25\/120 XP hôm nay/)).toBeVisible();

  /*
   * Thông báo tạm bắn ra ở ĐÚNG lần đọc trao thưởng, không phải mỗi lần thấy
   * `done`. Nó nằm trong vùng `aria-live` lịch sự, và vùng ấy phải có sẵn trong
   * DOM từ trước — chèn cả vùng lẫn nội dung cùng lúc thì trình đọc màn hình
   * không đọc gì, một lỗi chỉ nghe thấy chứ không nhìn thấy.
   *
   * "Còn 2 việc nữa" là phần đáng giá của khẳng định này: nó chứng minh con số
   * đến từ chính lần đọc vừa rồi chứ không phải một câu chữ cố định.
   */
  const toast = page.getByRole("status").getByText("Đã xong việc hôm nay");
  await expect(toast).toBeVisible();
  await expect(page.getByRole("status").getByText(/\+10 XP\. Còn 2 việc nữa\./)).toBeVisible();

  // Nạp lại lần nữa: máy chủ trả `xp_awarded = 0` vì `source_id` tất định, nên
  // không chúc mừng lại chuyện đã chúc mừng rồi.
  await page.reload();
  await expect(panel.getByText(/25\/120 XP hôm nay/)).toBeVisible();
  await expect(page.getByRole("status").getByText("Đã xong việc hôm nay")).toHaveCount(0);
});
