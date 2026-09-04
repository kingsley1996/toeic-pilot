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

/*
 * Đường vào góc thú cưng là THẺ Ở SIDEBAR, không còn nút nổi nào nữa.
 *
 * Chốt theo `title` chứ không theo tên hiển thị: tên trên thẻ là tên loài, và nó
 * đổi theo con thú mà tài khoản mới bốc được.
 *
 * Giới hạn trong `<aside>` vì `SidebarContent` còn dựng một bản nữa cho ngăn kéo
 * mobile — cùng một thẻ ở hai chỗ sẽ làm chế độ strict của Playwright từ chối.
 */
const openPet = (page: Page) => page.locator("aside").getByTitle("Mở góc thú cưng");

/** Thanh tiêu đề của bảng, cũng chính là tay cầm kéo. */
const panelBar = (page: Page) => page.getByTitle("Kéo để đổi chỗ");

test("sau khi nạp lại trang, bảng thú cưng mở ra nằm trong màn hình", async ({ page }) => {
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
  await openPet(page).click();

  const box = await panelBar(page).boundingBox();
  expect(box).not.toBeNull();
  const view = page.viewportSize();
  expect(view).not.toBeNull();
  // Toạ độ khởi tạo là (-9999, -9999): còn nằm ở đó nghĩa là `settle` không chạy.
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(view!.width);
});

test("kéo góc thú cưng sang chỗ khác thì chỗ đó được nhớ", async ({ page }) => {
  await signUp(page);

  await openPet(page).click();

  const before = await panelBar(page).boundingBox();
  expect(before).not.toBeNull();

  // Bám mép TRÁI thanh tiêu đề: giữa thanh là chỗ mấy cái nút đóng/phóng to đứng,
  // và một cú `mouse.down()` trúng nút thì không kéo được gì cả.
  await page.mouse.move(before!.x + 16, before!.y + before!.height / 2);
  await page.mouse.down();
  await page.mouse.move(520, 260, { steps: 12 });
  await page.mouse.up();

  const after = await panelBar(page).boundingBox();
  expect(after!.y).toBeLessThan(before!.y - 50);

  // Nạp lại: `localStorage` phải giữ chỗ. Đây là nửa còn lại của bài đầu — đặt
  // chỗ đúng lúc mount thì cũng phải đọc được chỗ ĐÃ LƯU chứ không phải mặc định.
  await page.reload();
  await openPet(page).click();
  const reloaded = await panelBar(page).boundingBox();
  expect(Math.abs(reloaded!.y - after!.y)).toBeLessThan(24);
});

test("mở toàn bản đồ thì khung nhìn rộng ra", async ({ page }) => {
  await signUp(page);
  await openPet(page).click();

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

  await openPet(page).click();
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

test("chọc một con đã vui sẵn thì thôi sinh điểm", async ({ page, request }) => {
  /*
   * Bài này thay cho một bài cũ chốt "chạm trần ngày thì nói ra", và lý do thay
   * đáng ghi lại: bài cũ chỉ tới được mốc 30 XP bằng cách bấm "Chọc" ba mươi
   * lần — tức nó xanh nhờ ĐÚNG cái lỗ hổng đã bịt. Một con thú mới chỉ kiếm
   * được chừng hai mươi điểm bằng đường chăm sóc hợp lệ (một lần ăn, ba lần đi
   * dạo), nên mốc ấy giờ không tới được trong một phiên, và đó là chủ ý.
   *
   * Thứ đo ở đây là luật thay thế: chọc cộng vui theo phần CÒN THIẾU, và thôi
   * sinh điểm khi con thú đã vui sẵn. Đi qua đúng cái nút thật, rồi hỏi máy chủ
   * — con số trên bảng là thanh XP, không đọc thành số được.
   */
  await signUp(page);
  await openPet(page).click();

  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const readPet = async () =>
    (
      await request.get("http://localhost:8000/api/v1/pet", {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json();

  const poke = page.getByRole("button", { name: /Chọc/i });

  // Con thú mới bắt đầu ở vui 0,70 — ngay dưới mốc "đang vui" (0,75). Vài cú
  // bấm là qua, và đó chính là điều bài này muốn thấy.
  for (let i = 0; i < 6; i += 1) {
    await poke.click();
    await page.waitForTimeout(120);
  }
  const cheerful = await readPet();
  expect(cheerful.needs.mood).toBeGreaterThanOrEqual(0.75);

  const before = cheerful.xp_today;
  const moodBefore = cheerful.needs.mood;
  for (let i = 0; i < 5; i += 1) {
    await poke.click();
    await page.waitForTimeout(120);
  }
  const after = await readPet();

  expect(after.xp_today).toBe(before);
  // Nhưng nút KHÔNG chết: vui vẫn nhích lên. Chặn hẳn sẽ là phạt người dùng,
  // còn một nút bấm không làm gì thì đọc ra là hỏng.
  expect(after.needs.mood).toBeGreaterThan(moodBefore);
  expect(after.needs.mood).toBeLessThan(1);
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

  await openPet(page).click();
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

  await openPet(page).click();
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

  await openPet(page).click();
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
  // Nhắm CÁI NÚT Ở THANH TIÊU ĐỀ, không nhắm theo nhãn khi đóng: màn trứng có
  // cái X của riêng nó và cũng mang nhãn "Đóng màn trứng", nên tìm theo tên thì
  // Playwright báo strict mode violation — CI đỏ ở đó còn máy này thì không, vì
  // hai lần chạy khác nhau ở chỗ màn trứng có kịp dựng xong hay chưa.
  const eggToggle = page.getByRole("button", { name: /trứng/i }).first();
  await eggToggle.click();
  await eggToggle.click();
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

test("tab bị ẩn thì bảng thôi vẽ", async ({ page }) => {
  /*
   * ADR-010 §10 đòi vòng lặp phải dừng khi tab bị ẩn, và đó là món nợ về PIN:
   * cái bảng này vẽ WebGL sáu chục lần một giây, để nó chạy sau lưng người dùng
   * là đốt pin cho một khung hình không ai nhìn.
   *
   * Đếm mọi lượt `requestAnimationFrame` của trang, cài TRƯỚC khi app chạy.
   * Playwright không ẩn tab thật được (`bringToFront` sang trang khác vẫn để
   * `document.hidden === false` — đã đo), nên ép thuộc tính rồi bắn đúng sự kiện
   * mà trình duyệt sẽ bắn.
   *
   * Đo được: trang chưa mở bảng gọi rAF **0 lần** một giây; mở bảng ra là ~135;
   * ẩn đi còn ~60. Phần còn lại là ticker nội bộ của Pixi — nó làm việc dọn dẹp
   * chứ không vẽ, và `app.stop()` không tắt được nó. Cả vòng vẽ của bảng lẫn
   * ticker của renderer đều đã dừng.
   */
  await page.addInitScript(() => {
    const real = window.requestAnimationFrame.bind(window);
    (window as unknown as { rafCount: number }).rafCount = 0;
    window.requestAnimationFrame = (cb: FrameRequestCallback) => {
      (window as unknown as { rafCount: number }).rafCount += 1;
      return real(cb);
    };
  });
  await signUp(page);

  const read = () => page.evaluate(() => (window as unknown as { rafCount: number }).rafCount);
  // Nền: chưa mở bảng thì trang không dùng rAF chút nào.
  const idle0 = await read();
  await page.waitForTimeout(1000);
  expect((await read()) - idle0).toBeLessThan(5);

  await openPet(page).click();
  await expect(page.locator("canvas")).toBeVisible();
  const busy0 = await read();
  await page.waitForTimeout(1000);
  const busy = (await read()) - busy0;
  expect(busy).toBeGreaterThan(50);

  await page.evaluate(() => {
    Object.defineProperty(document, "hidden", { value: true, configurable: true });
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForTimeout(250);
  const quiet0 = await read();
  await page.waitForTimeout(1000);
  const quiet = (await read()) - quiet0;

  /*
   * Đo phần công việc BIẾN MẤT, không đo tỉ lệ còn lại.
   *
   * Bản đầu là `quiet < busy / 2` và nó đỏ trên CI: phần dư — ticker nội bộ của
   * Pixi, thứ không tắt được từ đây — là một con số gần như CỐ ĐỊNH (~60 lượt
   * mỗi giây), trong khi `busy` thì tuỳ máy. CI chạy bản production trên máy ảo
   * và chỉ đạt ~110 thay vì ~135 như máy dev, nên `busy / 2` tụt xuống dưới cái
   * phần dư cố định ấy và bài đỏ vì một lý do chẳng liên quan gì tới cái chốt nó
   * đang canh.
   *
   * Hiệu số thì nói đúng điều cần nói: "ít nhất chừng này lượt vẽ mỗi giây đã
   * ngừng". Đo được: máy dev 135 → 60 (mất 75), CI 110 → 61 (mất 49). Gỡ chốt
   * ra thì hiệu số về 0 và bài đỏ.
   */
  expect(busy - quiet).toBeGreaterThan(25);
});

test("xin giảm chuyển động thì vẫn chơi được bình thường", async ({ page, request }) => {
  /*
   * ADR-010 §10: KHÔNG tắt cả góc thú cưng — nó là một cái game nhỏ, tắt đi thì
   * không còn gì. Cách chốt là bỏ nội suy, bỏ thở và nhún, bỏ hoạt ảnh nền.
   *
   * Bài này chỉ ghim NỬA SAU: nó vẫn phải chơi được. Nửa trước — "khung cảnh
   * đứng im" — đã thử ghim bằng cách chụp canvas hai lần và so byte, và KHÔNG
   * ghim được:
   *
   *   · Cách nhau 600ms thì bài đỏ khoảng một lượt trong ba, vì lớp phủ bầu trời
   *     nội suy theo giờ Petland (một ngày = một giờ thật) và thỉnh thoảng vượt
   *     một bậc màu ngay giữa hai tấm.
   *   · Chụp liền nhau thì hết chập chờn, nhưng cũng thôi bắt được gì: bỏ hẳn
   *     chốt giảm-chuyển-động của nhịp thở mà bài vẫn xanh.
   *   · `page.clock` đóng băng đồng hồ tường thì bài đỏ MỌI lượt.
   *
   * Cửa sổ đủ rộng để thấy chuyển động cũng đủ rộng để bầu trời trôi. §10 của
   * ADR-010 đã viết sẵn kết luận này: "phải kiểm bằng mắt chứ không bằng test".
   * Thứ ghim được bằng máy là luật THUẦN — `wanderRange(condition, reduced)` —
   * và nó nằm ở `scripts/check-petland-walk.mjs`.
   */
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signUp(page);
  const token = await page.evaluate(() => window.localStorage.getItem("toeic_pilot_access_token"));
  const auth = { Authorization: `Bearer ${token}` };
  const at = async () =>
    (await (await request.get("http://localhost:8000/api/v1/pet", { headers: auth })).json())
      .tile_x as number;

  await openPet(page).click();
  const canvas = page.locator("canvas");
  await expect(canvas).toBeVisible();

  const map = page.getByRole("application", { name: /Bản đồ Petland/ });
  await map.focus();
  const before = await at();
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("d");
    await page.waitForTimeout(340);
  }
  await expect
    .poll(at, { message: "giảm chuyển động KHÔNG được làm con thú thôi đi được" })
    .toBeGreaterThan(before);
});
