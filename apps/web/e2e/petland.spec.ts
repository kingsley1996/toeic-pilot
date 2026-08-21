import { expect, test } from "@playwright/test";

/*
 * Góc thú cưng.
 *
 * Test này tồn tại vì một lý do rất hẹp: khiếu nại duy nhất từng có về phần này
 * là "chuyển động bị giật và có khi đứng", và đó KHÔNG phải thứ một test render
 * bắt được — component vẫn dựng ra đúng cây DOM khi con thú đứng im. Cái phải đo
 * là vị trí thay đổi theo thời gian, và nó chỉ đo được trong một trình duyệt
 * thật, nơi `requestAnimationFrame` thực sự chạy.
 *
 * Đây cũng là lý do phép đo bằng tay qua DevTools không kết luận được: một tab ở
 * nền có `visibilityState === "hidden"` thì trình duyệt DỪNG `requestAnimationFrame`,
 * nên mọi mẫu đọc được đều là "đứng yên" — đúng triệu chứng đang muốn loại trừ.
 */

function freshEmail(): string {
  return `e2e-pet-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

/** Trạng thái con thú, đọc thẳng từ style mà vòng lặp animation ghi ra. */
const SNAP = `(() => {
  const el = document.querySelector('[aria-label="Chọc cho thú cưng phản ứng"]');
  if (!el) return null;
  return {
    x: Number((el.style.transform.match(/translate3d\\((-?\\d+)px/) ?? [0, 0])[1]),
    y: Number((el.style.transform.match(/px, (-?\\d+)px/) ?? [0, 0])[1]),
    /*
     * Đọc Ý ĐỊNH, không đọc tên tệp ảnh.
     *
     * \`data-intent\` là từ vựng chung giữa phần điều khiển và bộ sprite
     * (\`petland-sprite.ts\`): nó nói về hành vi chứ không về nghệ thuật, nên bài
     * kiểm vẫn đúng sau khi đổi mascot sang bộ khung hình khác, tên khác. Bản
     * trước bóc tên clip ra từ \`url(/mascots/dino/walk.png)\`, tức ghim chặt vào
     * đúng con dino hiện tại.
     */
    intent: el.dataset.intent ?? "",
    frame: el.style.backgroundPosition,
    scale: Math.abs(Number((el.style.transform.match(/scale\\((-?[\\d.]+)/) ?? [0, 1])[1])),
  };
})()`;

/*
 * Chờ vòng lặp animation ghi lần ĐẦU trước khi đọc bất cứ thứ gì.
 *
 * `toBeVisible()` xong là nút đã ở trong DOM, nhưng lần ghi đầu của vòng lặp mới
 * xảy ra ở khung hình kế tiếp — nên đọc ngay có thể lấy được một `transform`
 * rỗng, tức `y = 0` và `scale = 1`: hai giá trị hợp lệ về kiểu và vô nghĩa về
 * nội dung, và bài kiểm phối cảnh sẽ đỏ ở dòng khẳng định mặt đất dốc, chỗ chẳng
 * liên quan gì tới nguyên nhân.
 *
 * Đây là phòng thủ cho một cuộc đua CÓ THẬT, không phải bản vá cho một lần đỏ đã
 * quan sát được: những lần đỏ chập chờn gặp trong lúc dựng phần này hoá ra là do
 * bộ giới hạn tốc độ của `/auth/register`, không phải do cuộc đua này.
 */
async function waitForPet(page: import("@playwright/test").Page) {
  await expect
    .poll(async () => ((await page.evaluate(SNAP)) as { y: number } | null)?.y ?? 0)
    .toBeGreaterThan(0);
}

test("thú cưng đi, đổi khung hình và nhảy được", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Thú cưng" }).click();
  const sprite = page.getByRole("button", { name: "Chọc cho thú cưng phản ứng" });
  await expect(sprite).toBeVisible();
  await waitForPet(page);

  /*
   * Đứng yên vẫn phải ĐỔI KHUNG HÌNH. Đây là nửa dễ quên: một con thú đứng im
   * mà khung hình cũng đứng im thì trông y hệt một tấm ảnh, và không có gì báo
   * lỗi — chính là "có khi đứng" trong lời khiếu nại.
   */
  const idleFrames = new Set<string>();
  for (let i = 0; i < 12; i += 1) {
    idleFrames.add(((await page.evaluate(SNAP)) as { frame: string }).frame);
    await page.waitForTimeout(60);
  }
  expect(idleFrames.size).toBeGreaterThan(1);

  // Giữ phím sang phải: vị trí phải TĂNG ĐỀU, và clip phải đổi sang bước đi.
  await page.keyboard.down("ArrowRight");
  const walk: Array<{ x: number; intent: string }> = [];
  for (let i = 0; i < 10; i += 1) {
    walk.push((await page.evaluate(SNAP)) as { x: number; intent: string });
    await page.waitForTimeout(80);
  }
  await page.keyboard.up("ArrowRight");

  expect(walk.at(-1)!.x).toBeGreaterThan(walk[0]!.x + 20);
  expect(walk.some((s) => s.intent === "walk")).toBe(true);
  /*
   * Không có mẫu nào ĐỨNG YÊN giữa chừng. Bản trước tách vị trí và khung hình
   * thành hai đồng hồ (`requestAnimationFrame` và `setInterval`), và chúng trôi
   * khỏi nhau — đây là phép đo phân biệt được hai kiến trúc đó.
   */
  const steps = walk.slice(1).map((s, i) => s.x - walk[i]!.x);
  expect(steps.filter((d) => d <= 0)).toHaveLength(0);

  /*
   * Nhảy: phải rời mặt đất rồi quay lại ĐÚNG chỗ cũ.
   *
   * `y` ở đây là toạ độ trong bức tranh chứ không phải độ cao so với mặt đất —
   * mặt đất dốc dọc đường đi nên nó khác nhau ở mỗi chỗ đứng. Phải chốt mốc
   * trước khi nhảy rồi so tương đối; so với 0 là so với một mặt đất không tồn
   * tại, và phép kiểm sẽ đỏ ở mọi chỗ đứng.
   */
  const ground = ((await page.evaluate(SNAP)) as { y: number }).y;
  await page.keyboard.press("Space");
  let peak = ground;
  for (let i = 0; i < 10; i += 1) {
    peak = Math.min(peak, ((await page.evaluate(SNAP)) as { y: number }).y);
    await page.waitForTimeout(70);
  }
  expect(peak).toBeLessThan(ground - 20);
  await expect.poll(async () => ((await page.evaluate(SNAP)) as { y: number }).y).toBe(ground);
});

/*
 * Phối cảnh: con thú phải NHỎ ĐI khi đi về phía sau, và mặt đất phải DỐC.
 *
 * Không có phép kiểm này thì một đường đi với `scale` cố định vẫn chạy hoàn hảo,
 * và cái sai chỉ lộ ra ở chỗ con thú bước lên cầu rồi cao ngang cái lan can —
 * thứ trông như lỗi vẽ chứ không như lỗi toạ độ, nên sẽ bị đổ cho bức tranh.
 */
test("đi về phía cầu thì con thú nhỏ lại theo phối cảnh", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Thú cưng" }).click();
  await expect(page.getByRole("button", { name: "Chọc cho thú cưng phản ứng" })).toBeVisible();
  await waitForPet(page);

  const near = (await page.evaluate(SNAP)) as { scale: number; y: number };
  await page.keyboard.down("ArrowRight");
  await page.waitForTimeout(1800);
  await page.keyboard.up("ArrowRight");
  const far = (await page.evaluate(SNAP)) as { scale: number; y: number };

  expect(far.scale).toBeLessThan(near.scale);
  expect(far.y).toBeLessThan(near.y);
});

/*
 * Lớp hạt (sao, mặt nước, đốm lửa, đom đóm) phải THỰC SỰ vẽ và thực sự đổi.
 *
 * Đây là chỗ dễ hỏng im lặng nhất trong cả màn: một canvas không vẽ gì trông y
 * hệt một canvas chưa được thêm vào, và bức tranh nền vẫn đẹp như thường nên
 * không ai nghi ngờ. Chuyện đó đã xảy ra một lần — một cái chốt so sánh với
 * `NaN` khiến toàn bộ phần ánh sáng không bao giờ chạy mà không ném lỗi nào.
 *
 * Hai điều kiện, và cần cả hai: canvas phải CÓ pixel sáng (không vẽ gì thì tổng
 * bằng 0), và tổng đó phải ĐỔI giữa hai lần đọc (vẽ một lần rồi đứng im cũng là
 * hỏng).
 */
test("lớp hạt của khu trại có vẽ và có chuyển động", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Thú cưng" }).click();
  await expect(page.getByRole("button", { name: "Chọc cho thú cưng phản ứng" })).toBeVisible();

  const signature = () =>
    page.evaluate(() => {
      const c = document.querySelector("canvas") as HTMLCanvasElement | null;
      if (!c) return null;
      const d = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
      let sum = 0;
      // Lấy mẫu thưa: đọc cả triệu pixel qua cầu CDP thì test chậm hơn nhiều so
      // với giá trị nó mang lại, và một bước lẻ vẫn quét khắp mặt canvas.
      for (let i = 0; i < d.length; i += 4 * 37) sum += d[i] + d[i + 1] + d[i + 2];
      return sum;
    });

  /* Chờ tới lần vẽ ĐẦU thay vì đọc ngay: canvas mới gắn vào DOM thì rỗng, nên
     một lần đọc sớm cho tổng bằng 0 và bài kiểm đỏ vì lý do không liên quan gì
     tới lớp hạt. Cùng loại với `waitForPet` ở trên. */
  await expect.poll(signature).toBeGreaterThan(0);
  const first = await signature();
  await expect.poll(signature).not.toBe(first);
});

/*
 * Cho ăn và chọc.
 *
 * Hai hành động này đi qua đúng cái ranh giới mà cách chia tệp sinh ra để bảo vệ:
 * giao diện (`petland-ui.tsx`) gửi một `PetAction`, phần điều khiển dịch nó thành
 * ý định và chuyển động, còn `petland-pet.ts` đổi các chỉ số. Bài kiểm bám vào ý
 * định và vào những mẩu phản hồi, không bám vào ảnh — nên đổi mascot hay đổi bối
 * cảnh đều không làm nó đỏ.
 */
test("chọc thì thú phản ứng, cho ăn thì nó đi tới chỗ ăn rồi ăn", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Thú cưng" }).click();
  await waitForPet(page);

  const intent = async () => ((await page.evaluate(SNAP)) as { intent: string }).intent;
  const posX = async () => ((await page.evaluate(SNAP)) as { x: number }).x;

  // Chọc: nhảy lên, và bay ra vài mẩu phản hồi.
  await page.getByRole("button", { name: "Chọc", exact: true }).click();
  await expect.poll(intent).toBe("hop");
  expect(await page.locator(".pet-bit").count()).toBeGreaterThan(0);

  /*
   * Cho ăn: miếng ăn rơi xuống CÁCH một quãng, con thú đi tới, rồi ăn. Kiểm cả
   * chặng đi chứ không chỉ kiểm chỉ số cuối — nếu chỉ kiểm chỉ số thì một bản làm
   * tắt, cộng thẳng vào độ no mà không có gì di chuyển, vẫn xanh.
   */
  await expect.poll(intent).toBe("stand");
  const before = await posX();

  await page.getByRole("button", { name: "Cho ăn", exact: true }).click();
  await expect.poll(intent).toBe("walk");
  // Trong lúc đi, nút bị khoá: cho ăn chồng lên nhau thì miếng ăn thứ nhất biến
  // mất giữa chừng và con thú đổi hướng đột ngột.
  await expect(page.getByRole("button", { name: "Cho ăn", exact: true })).toBeDisabled();

  // Đi THẬT, chứ không phải chỉ đổi hoạt ảnh.
  await expect
    .poll(async () => Math.abs((await posX()) - before), { timeout: 15_000 })
    .toBeGreaterThan(60);

  // Ăn xong thì nút mở lại.
  await expect(page.getByRole("button", { name: "Cho ăn", exact: true })).toBeEnabled({
    timeout: 25_000,
  });
});

/*
 * Bài kiểm này đọc TÊN TỆP ảnh, ngược với `SNAP` ở trên vốn cố tình chỉ đọc
 * `data-intent` để sống sót qua việc đổi mascot. Ở đây danh tính mascot chính
 * là thứ đang được kiểm, nên tên tệp là đúng thứ phải nhìn.
 */
const SHEET = `(() => {
  const el = document.querySelector('[aria-label="Chọc cho thú cưng phản ứng"]');
  return el ? el.style.backgroundImage : "";
})()`;

test("chọn thú cưng: đổi được, và lựa chọn đi theo tài khoản", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Thú cưng" }).click();
  await expect(page.getByRole("button", { name: "Chọc cho thú cưng phản ứng" })).toBeVisible();

  // Tài khoản mới chưa chọn gì: cột `pet` là NULL và frontend rơi về con mặc định.
  await expect.poll(() => page.evaluate(SHEET)).toContain("/mascots/cat/");

  await page.getByRole("radio", { name: "Khủng long" }).click();
  await expect.poll(() => page.evaluate(SHEET)).toContain("/mascots/rex/");

  /*
   * Đây là nửa có giá trị của bài kiểm. Đổi mascot trên màn hình thì một biến
   * trong bộ nhớ cũng làm được; thứ phân biệt "lưu trên máy chủ" với "lưu ở
   * trình duyệt" là nó sống sót qua một vòng đời trang. Nạp lại xoá sạch state
   * của React, nên nếu lựa chọn không thực sự tới `user_profile.pet` thì con mèo
   * quay lại đây.
   *
   * Lưu ý có một nhịp hiện con mặc định trước khi hồ sơ về tới nơi — `poll` chờ
   * qua nhịp đó. Đổi thành `expect(...)` một lần sẽ đỏ chập chờn.
   */
  await page.reload();
  await page.getByRole("button", { name: "Thú cưng" }).click();
  await expect(page.getByRole("button", { name: "Chọc cho thú cưng phản ứng" })).toBeVisible();
  await expect.poll(() => page.evaluate(SHEET)).toContain("/mascots/rex/");
});
