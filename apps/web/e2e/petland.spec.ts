import { expect, test, type Page } from "@playwright/test";

/*
 * Góc thú cưng, bản bản-đồ-ô (ADR-010).
 *
 * Bài kiểm cũ đo bản cũ: phối cảnh dọc đường đi, lớp hạt lửa trại, chọc và cho
 * ăn trên một bức tranh. Cả ba thứ đó không còn tồn tại, nên giữ lại là giữ một
 * bức ảnh xanh về một tính năng đã bị thay.
 *
 * Ba bài dưới đây đo ba chỗ nối mà `tsc` và `eslint` đều không thấy: vị trí sau
 * khi NẠP LẠI trang, vị trí sau khi kéo, và kích thước khung khi mở toàn bản đồ.
 */

function freshEmail(): string {
  return `e2e-pet-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
}

async function signUp(page: Page) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(freshEmail());
  await page.locator('input[name="password"]').fill("mat-khau-du-dai-123");
  await page.getByRole("button", { name: "Tạo tài khoản" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

const launcher = (page: Page) => page.getByRole("button", { name: "Thú cưng" });

test("sau khi nạp lại trang, góc thú cưng vẫn ở nửa dưới màn hình", async ({ page }) => {
  /*
   * Đây là một lỗi CÓ THẬT đã gặp, và nó là bẫy ba trạng thái của phiên.
   *
   * Lượt dựng đầu tiên `status` là `loading` nên component trả `null`; hiệu ứng
   * đặt chỗ chạy lúc đó, không thấy node nào, và không chạy lại khi phiên phân
   * giải xong — bảng nằm nguyên ở toạ độ inline khởi tạo, tức góc TRÊN TRÁI.
   *
   * Chỉ lộ ra khi NẠP LẠI trang: điều hướng bên trong app không dựng lại
   * `SidebarShell`, nên phiên đã sẵn sàng từ trước và mọi thứ trông bình thường.
   * Vì thế bài này phải `reload()`, không được chỉ `goto()`.
   */
  await signUp(page);
  await page.reload();

  const box = await launcher(page).boundingBox();
  expect(box).not.toBeNull();
  const view = page.viewportSize();
  expect(view).not.toBeNull();
  expect(box!.y).toBeGreaterThan(view!.height / 2);
});

test("kéo góc thú cưng sang chỗ khác thì chỗ đó được nhớ", async ({ page }) => {
  await signUp(page);

  const handle = page.getByTitle("Kéo để đổi chỗ");
  const before = await launcher(page).boundingBox();
  expect(before).not.toBeNull();

  const grip = await handle.boundingBox();
  await page.mouse.move(grip!.x + grip!.width / 2, grip!.y + grip!.height / 2);
  await page.mouse.down();
  await page.mouse.move(520, 260, { steps: 12 });
  await page.mouse.up();

  const after = await launcher(page).boundingBox();
  expect(after!.y).toBeLessThan(before!.y - 50);

  // Nạp lại: `localStorage` phải giữ chỗ. Đây là nửa còn lại của bài đầu — đặt
  // chỗ đúng lúc mount thì cũng phải đọc được chỗ ĐÃ LƯU chứ không phải mặc định.
  await page.reload();
  const reloaded = await launcher(page).boundingBox();
  expect(Math.abs(reloaded!.y - after!.y)).toBeLessThan(24);
});

test("mở toàn bản đồ thì khung nhìn rộng ra", async ({ page }) => {
  await signUp(page);
  await launcher(page).click();

  const canvas = page.locator("canvas");
  await expect(canvas).toBeVisible();
  const small = await canvas.boundingBox();

  await page.getByRole("button", { name: "Xem toàn bản đồ" }).click();
  const large = await canvas.boundingBox();

  expect(large!.width).toBeGreaterThan(small!.width);
  // Cùng MỘT canvas: `setView` đổi khung tại chỗ chứ không dựng lại sân khấu —
  // mỗi lần dựng lại là một WebGL context nữa, và trình duyệt chỉ cho vài cái.
  await expect(canvas).toHaveCount(1);
});

test("cho ăn làm chỉ số no tăng, và ăn tiếp khi đã no thì bị từ chối có lý do", async ({
  page,
  request,
}) => {
  /*
   * Bài này bắc qua chỗ nối mà cả hai phía đứng riêng đều xanh: máy chủ trừ dần
   * theo `needs_at` và trả về nhu cầu MỚI, còn trình duyệt phải vẽ đúng con số
   * đó chứ không phải con số nó tự cộng.
   *
   * Đọc chỉ số qua API chứ không qua thanh chỉ số: thanh cố ý KHÔNG in phần
   * trăm (`petland-ui.tsx` giải thích vì sao), nên nó không đọc được thành số.
   * Cái phải kiểm ở giao diện là nút có gọi đúng thứ không và lời từ chối có
   * hiện ra không.
   */
  await signUp(page);
  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const auth = { Authorization: `Bearer ${token}` };
  const read = async () =>
    (await (await request.get("http://localhost:8000/api/v1/pet", { headers: auth })).json()).needs
      .fullness as number;

  await launcher(page).click();
  const feed = page.getByRole("button", { name: /Cho ăn/i });
  await expect(feed).toBeVisible();

  const before = await read();
  await feed.click();
  await expect.poll(read).toBeGreaterThan(before);

  /*
   * Đã no thì nút TỰ MỜ, kèm lý do trong `title` — người dùng không bao giờ chạm
   * tới lỗi 409, và đó là chủ ý.
   *
   * Bản đầu của bài này chờ dòng chữ từ chối hiện ra, và nó sai: một con thú
   * bắt đầu ở 0,62 cộng 0,35 là 0,97, tức vượt ngưỡng ngay sau MỘT lần cho ăn,
   * nên cái nút đã tự khoá trước khi có gì để từ chối. Lỗi 409 vẫn phải đúng —
   * nó chặn đường gọi thẳng API — nhưng nó được `tests/test_pet_state.py` canh,
   * chứ không phải ở đây.
   */
  await expect(feed).toBeDisabled();
  await expect(feed).toHaveAttribute("title", /đang no/i);
});

test("chăm thú cưng làm nó lên level, và chạm trần ngày thì nói ra", async ({ page }) => {
  await signUp(page);
  await launcher(page).click();

  await expect(page.getByText(/^Lv \d+$/)).toBeVisible();
  const poke = page.getByRole("button", { name: /Chọc/i });

  /*
   * Bấm cho tới khi kịch trần. Ba mươi lần chọc là đúng ba mươi XP, tức vừa đủ
   * trần — nên vòng lặp này chạm tới nó chứ không phải chỉ tiến gần.
   *
   * Nút KHÔNG tự mờ khi hết XP, và đó là chủ ý: chăm con thú vẫn có tác dụng
   * lên nhu cầu sau khi điểm đã dừng. Khoá nút ở đó sẽ nói dối rằng hành động
   * không còn nghĩa gì.
   */
  for (let i = 0; i < 31; i += 1) {
    await poke.click();
    await page.waitForTimeout(40);
  }

  await expect(page.getByText(/đã nhận đủ 30 XP/i)).toBeVisible();
});

test("màn trứng in tỉ lệ, và không có ruby thì nút mở bị khoá", async ({ page, request }) => {
  /*
   * Chỗ nối được đo ở đây là **màn hình đọc đúng thứ máy chủ nói**, không phải
   * phép quay — phép quay có bài riêng bên API, nơi `rng` cắm vào được.
   *
   * Tỉ lệ phải hiện ra (ADR-010 §6.4): đây là sản phẩm học cho học sinh, và che
   * tỉ lệ là thứ không nên làm với đối tượng đó. Bài này khoá cái đó lại ở tầng
   * giao diện, vì một endpoint trả về `chances` mà không ai vẽ ra thì vẫn xanh
   * ở mọi bài kiểm phía API.
   *
   * Và nút phải KHOÁ khi chưa đủ ruby, không phải bấm rồi ăn một lỗi 409: điều
   * kiện `can_open` do máy chủ tính, nên nút chỉ việc nghe theo.
   */
  await signUp(page);
  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const wallet = await (
    await request.get("http://localhost:8000/api/v1/ruby", {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json();
  expect(wallet.balance).toBe(0);

  await launcher(page).click();
  await page.getByRole("button", { name: "Mở trứng" }).first().click();

  const open = page.getByRole("button", { name: "Mở trứng", exact: true });
  await expect(open).toBeDisabled();
  await expect(page.getByText(/còn 0 ruby/)).toBeVisible();

  // Bảng tỉ lệ mở ra được và có đủ mười hai loài, mỗi dòng kèm phần trăm.
  await page.getByRole("button", { name: /Xem tỉ lệ/ }).click();
  const rows = page.locator("li", { hasText: "%" });
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThanOrEqual(12);
});

test("lái bằng bàn phím đi ĐÚNG hướng, và thả phím thì đứng đúng ô", async ({ page, request }) => {
  /*
   * Bài này canh một lỗi CÓ THẬT và rất khó nhìn ra từ mã: con thú được vẽ ở ô
   * TRƯỚC ô nó thật sự đang đứng.
   *
   * Một bước là cặp (`from` → `tile`) cộng `progress`; đứng yên nghĩa là `from`
   * trùng `tile`. Bản hỏng đặt `progress = 0` khi hàng đợi cạn mà không kéo
   * `from` về `tile`, nên hình vẽ tụt lại một ô so với vị trí logic — và bước
   * sau bắt đầu bằng một cú dịch tới ô logic ấy. Bấm sang trái ngay sau khi đi
   * sang phải thì cú dịch đó là dịch SANG PHẢI, đúng như người dùng báo.
   *
   * Đo bằng API chứ không bằng canvas: vị trí là dữ liệu máy chủ, còn canvas thì
   * không có DOM nào để mà đọc. Và khẳng định được viết theo kiểu KHÔNG BAO GIỜ
   * ĐI NGƯỢC thay vì "phải đi đúng N ô", vì bản đồ có tường — bị chặn thì đứng
   * yên là hợp lệ, còn đi ngược hướng thì không bao giờ hợp lệ.
   */
  await signUp(page);
  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const auth = { Authorization: `Bearer ${token}` };
  const where = async () => {
    const pet = await (
      await request.get("http://localhost:8000/api/v1/pet", { headers: auth })
    ).json();
    return { x: pet.tile_x as number, y: pet.tile_y as number };
  };

  await launcher(page).click();
  const map = page.getByRole("application", { name: /Bản đồ Petland/ });
  await expect(map).toBeVisible();
  await map.focus();

  /*
   * Chờ vị trí ĐỨNG YÊN trước khi lấy mốc.
   *
   * Lượt nạp đầu có thể tự dời con thú: ô đã lưu được `nearestWalkable` kéo về
   * chỗ đứng được nếu bản đồ đã đổi. Lấy mốc trước lúc ấy thì bài kiểm đo cả cú
   * dời đó và đỏ vì một lý do chẳng liên quan gì tới bàn phím.
   */
  let start = await where();
  await expect
    .poll(
      async () => {
        const now = await where();
        const same = now.x === start.x && now.y === start.y;
        start = now;
        return same;
      },
      { timeout: 5000 },
    )
    .toBe(true);

  // Bốn nhịp sang phải. `expect.poll` vì vị trí chỉ được ghi khi con thú DỪNG
  // HẲN — ghi từng ô sẽ là bốn request cho một lần giữ phím.
  for (let i = 0; i < 4; i += 1) {
    await page.keyboard.press("d");
    await page.waitForTimeout(340);
  }
  await expect.poll(async () => (await where()).x).toBeGreaterThanOrEqual(start.x);
  const right = await where();
  expect(right.y).toBe(start.y);

  // Và sang trái: KHÔNG được nhích sang phải dù chỉ một ô.
  for (let i = 0; i < 4; i += 1) {
    await page.keyboard.press("a");
    await page.waitForTimeout(340);
  }
  const left = await where();
  expect(left.x).toBeLessThanOrEqual(right.x);
  expect(left.y).toBe(start.y);

  // Đi lên rồi đi xuống, cùng một luật cho trục dọc.
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("w");
    await page.waitForTimeout(340);
  }
  const up = await where();
  expect(up.y).toBeLessThanOrEqual(left.y);

  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("s");
    await page.waitForTimeout(340);
  }
  expect((await where()).y).toBeGreaterThanOrEqual(up.y);
});

test("bấm nút trong bảng xong, bàn phím vẫn lái được", async ({ page, request }) => {
  /*
   * Lỗi CÓ THẬT người dùng báo: "nhiều lúc các phím di chuyển không nhận, ví dụ
   * sau khi chạm npc và tắt".
   *
   * Bàn phím chỉ lái khi bảng đang giữ focus. Bấm bất cứ nút nào — cho ăn, mở
   * trứng, hay cái X đóng thẻ nhiệm vụ — là focus rời khỏi khung bản đồ, và cái
   * X thì còn tệ hơn: nó tự bị gỡ khỏi cây nên trình duyệt đẩy focus ra
   * `document.body`, tức là ra ngoài bảng. Từ đó phím chết lặng, không có gì
   * trên màn hình nói vì sao.
   *
   * Bài này không cần một NPC nào — đường hỏng là focus, và mọi cái nút trong
   * bảng đều đi qua đúng đường ấy. Đó cũng là lý do nó kiểm được, còn cú húc vào
   * NPC thì không: sinh khách đòi quyền admin.
   */
  await signUp(page);
  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const auth = { Authorization: `Bearer ${token}` };
  const at = async () =>
    (await (await request.get("http://localhost:8000/api/v1/pet", { headers: auth })).json())
      .tile_x as number;

  await launcher(page).click();
  const map = page.getByRole("application", { name: /Bản đồ Petland/ });
  await expect(map).toBeVisible();
  await map.focus();

  // 1. Bấm một nút trong hàng hành động: focus rời bản đồ.
  await page.getByRole("button", { name: /Cho ăn/i }).click();
  const afterFeed = await at();
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("d");
    await page.waitForTimeout(340);
  }
  await expect
    .poll(at, { message: "bấm nút xong thì bàn phím phải vẫn lái được" })
    .toBeGreaterThan(afterFeed);

  // 2. Mở một cột bên phải rồi ĐÓNG lại — đường mà cái X của thẻ nhiệm vụ đi.
  await page.getByRole("button", { name: /Mở trứng/i }).click();
  await page.getByRole("button", { name: /Đóng màn trứng/i }).click();
  const afterPanel = await at();
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("a");
    await page.waitForTimeout(340);
  }
  await expect
    .poll(at, { message: "đóng cột bên phải xong thì bàn phím phải vẫn lái được" })
    .toBeLessThan(afterPanel);

  /*
   * 3. Và nửa còn lại: bấm RA NGOÀI bảng thì bàn phím thôi lái.
   *
   * Đây là chốt chặn của chính cách sửa ở trên. Bảng nghe phím ở `window`, nên
   * không có cổng "đang chơi ở bảng này" thì gõ chữ "w" trong một ô nhập ở màn
   * gõ lại từ sẽ lái con thú — và người dùng không đời nào nối được hai chuyện
   * đó với nhau.
   */
  await page.locator("main").click({ position: { x: 5, y: 5 } });
  const parked = await at();
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("d");
    await page.waitForTimeout(340);
  }
  expect(await at()).toBe(parked);
});
