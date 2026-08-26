# ADR-010 — Nuôi thú ảo pixel art: bản đồ ô, level pet, và gacha trứng

Trạng thái: **đề xuất**, chưa dựng dòng nào. Viết 2026-08-26.

Thay cho góc thú cưng hiện tại (ROADMAP §4r). Đây là **thay kiến trúc**, không
phải chỉnh sửa: hai bản trả lời hai câu hỏi khác nhau, nên phần lớn code cũ
không chuyển tiếp được.

---

## 0. Bản đang có làm gì, và vì sao nó không tới được đích

Đo trên code hiện tại, không phải cảm nhận:

| | Bản hiện tại | Yêu cầu mới |
|---|---|---|
| Không gian | **1 chiều** — vị trí là *một số*, quãng đường đã đi trên `PATH` gồm 11 điểm neo | Bản đồ **ô 2 chiều** |
| Nền | Một ảnh JPEG vẽ sẵn 1360×768, phối cảnh xiên | Tilemap pixel art |
| Trạng thái | **Chỉ trong bộ nhớ trang** (`petland-pet.ts` nói thẳng điều đó) | Lưu ở máy chủ |
| Level pet | Không có | Có |
| Gacha | Không có | Có, mở khoá theo level user |
| Mascot | 2 con, cố định trong `PetId` | Bộ sưu tập mở rộng được |

Điểm chết là **`petland-scene.ts`**: vị trí con thú là một số vô hướng, `y` và
`scale` suy ra từ nó. Không có cách nào nhét toạ độ ô vào mô hình đó — "sang
trái" trên đường đi cong không phải "sang ô bên trái". Cả `check-petland-fit.mjs`
(đi 241 mẫu dọc đường) cũng gắn vào đúng giả định ấy.

**Cái giữ lại được:**

- `scripts/pack-pet.mjs` và `scripts/png.mjs` — đóng gói sprite sheet, đo `cell`
  / `footY` / `anchorX`. Không dính đường đi.
- `src/components/petland-pet.ts` — nhu cầu và hành động là số học thuần, không
  React, không ảnh. Đây là tầng thiết kế đúng nhất của bản cũ và nên giữ nguyên
  triết lý.
- `scripts/check-petland-layers.mjs` — luật tầng, chỉ cần thay danh sách tệp.
- `assets/mascots/**` — 26 khung gốc của con mèo.

**Cái bỏ:** `petland-scene.ts`, phần đi lại trong `petland.tsx`, và
`check-petland-fit.mjs` (viết lại theo lưới ô).

---

## 1. Năm ràng buộc không được phá

Bốn cái đầu đã có sẵn trong dự án; cái thứ năm là do bản này sinh ra.

1. **Không đổ bóng, một bán kính 4px, `rule-strong` cho ranh giới**
   (DESIGN-SYSTEM §6). Áp cho *khung* quanh canvas. Bên trong canvas là pixel
   art nên nó có ngôn ngữ riêng — nhưng khung, nút, thanh chỉ số thì vẫn là hệ
   thiết kế của app.
2. **Màn làm bài không có thú cưng.** `bareLayout` trong `app-shell.tsx` đã loại
   nó, và lý do vẫn nguyên: một con thú nhảy nhót cạnh người đang tính giờ làm
   bài cạnh tranh trực tiếp với sự tập trung.
3. **Level user không bao giờ tụt** (`user_profile.level_reached`, USER-ROAD
   §2.1). Hệ quả trực tiếp cho gacha ở §6.
4. **`prefers-reduced-motion` tắt chuyển động** (DESIGN-SYSTEM §7). Một game
   pixel không thể "tắt hết", nên phải định nghĩa bản tĩnh của nó.
5. **Vòng lặp phải ngủ khi không nhìn thấy.** Bản cũ chạy `requestAnimationFrame`
   khi bảng mở. Bản mới có tilemap và nhiều sprite hơn, nên phải dừng hẳn khi tab
   ẩn (`visibilitychange`) và khi canvas ra khỏi khung nhìn
   (`IntersectionObserver`). Không có nó, đây là tính năng ngốn pin nhất app.

---

## 2. Quyết định 1 — **PixiJS**, không phải Phaser, không phải tự viết tiếp

Hôm nay `apps/web` có đúng **ba** dependency chạy thật: `next`, `react`,
`lucide-react`. Thêm thư viện game là quyết định lớn nhất trong tài liệu này.

| | Ưu | Nhược |
|---|---|---|
| **PixiJS v8** | Renderer thuần, WebGL + fallback canvas; `nearest` scaling cho pixel art; sprite sheet sẵn; **không có ý kiến về logic game** | ~200–400KB gz, phải tự viết vòng lặp và va chạm |
| Phaser 3 | Đủ mọi thứ: scene, physics, tween, input | ~900KB+; **nuốt luôn phần logic** vào hệ scene của nó |
| kaplay | Nhẹ (~150KB), API dễ | Cộng đồng nhỏ hơn, API còn đổi |
| Tự viết tiếp | 0KB, đã có sẵn công cụ sprite | Tự viết tilemap + A\* + tween + batching là vài tuần, và mỗi dòng đều là dòng phải tự bảo trì |

**Chọn PixiJS, và lý do quyết định không phải kích thước mà là tầng.**
`petland-pet.ts` tồn tại được vì nhu cầu và hành động là *số học thuần, không
React, không ảnh* — kiểm được không cần trình duyệt. Phaser sẽ kéo logic vào
`Scene`, và lúc đó tầng thuần ấy không còn dựng lại được. Pixi chỉ vẽ, nên ranh
giới hiện có sống tiếp: **state và luật ở module thuần, Pixi chỉ đọc state để
vẽ.**

Ba việc phải làm cùng lúc với việc thêm dependency:

- **Đo bundle trước khi cam kết.** Dựng một trang thử chỉ import Pixi, chạy
  `pnpm build`, ghi lại con số. Nếu route `/learn/pet` vượt ~500KB gz thì xem
  lại. Con số này phải nằm trong ROADMAP, không nằm trong trí nhớ.
- **`dynamic(() => import(...), { ssr: false })`.** Pixi đụng `window` ngay khi
  nạp.
- **`docker compose up -d --build`**, không phải `up -d`. Thêm một dependency JS
  mà chỉ `restart` thì container từ chối khởi động vì lockfile lệch — và lời từ
  chối đến muộn, ở lần restart tiếp theo chứ không phải lúc thêm.

### 2.1 Một câu hỏi phải trả lời trước khi `pnpm add`

CLAUDE.md ghi: P1-7b (token trong `localStorage` thay vì cookie httpOnly) được
**hoãn kèm lý do**, và lý do đó là *app không có script bên thứ ba nào*. Thêm
bất kỳ script bên thứ ba nào thì lý do ấy hết hiệu lực.

Đọc chặt thì luật đó nói về `<script src>` từ CDN, còn Pixi là dependency được
bundle. Nhưng lập luận gốc là **bề mặt tấn công XSS**, và một thư viện bundle
vẫn là code bên thứ ba chạy trong trang: một lần chuỗi cung ứng bị chiếm là đọc
được `localStorage`.

**ĐÃ CHỐT (2026-08-26): dùng Pixi bình thường, không trả P1-7b trước.** Đọc luật
theo nghĩa hẹp — cấm là cấm `<script src>` trỏ ra ngoài, không cấm dependency
được bundle và ghim phiên bản trong lockfile.

Ghi lại để lần sau khỏi tranh luận lại, và ghi cả cái giá: từ đây `apps/web` có
code bên thứ ba chạy trong trang, nên lý do hoãn P1-7b **mỏng hơn trước một
bậc**. Hai việc phải kèm theo và không được coi là tuỳ chọn:

* **Ghim phiên bản chính xác**, không dùng dải `^`. Một bản vá tự trôi vào là
  đúng đường mà chuỗi cung ứng bị lợi dụng.
* **Không thêm plugin Pixi bên thứ ba** mà không hỏi lại. Một thư viện là một
  quyết định; một hệ sinh thái plugin là một cánh cửa.

---

## 3. Quyết định 2 — bản đồ ô, di chuyển nội suy

**Lưới `TILE = 16px` nguồn, phóng số nguyên.** Pixel art vỡ khi phóng lẻ, nên hệ
số phóng luôn là số nguyên (2×, 3×, 4×) tính từ bề rộng khung chứa, và
`roundPixels = true`.

**Bản đồ 20×15 ô** (320×240 nguồn — đúng tỉ lệ 4:3 quen thuộc của máy chơi game
cổ). Ba lớp:

```
ground   — nền, luôn vẽ
objects  — cây, bát ăn, giường, hàng rào
collision— 0/1, KHÔNG vẽ, chỉ để chặn
```

**Vị trí con thú là một cặp số nguyên `(tx, ty)`, không phải toạ độ pixel.** Đó
là điều khiến bản này khác bản cũ và là điều làm mọi thứ sau đó đơn giản: lưu
vào database là hai số nguyên nhỏ, va chạm là một phép tra bảng, và "đi tới bát
ăn" là tìm đường chứ không phải nội suy trên một đường cong.

**Mượt mà đến từ nội suy giữa hai ô, không phải từ việc bỏ lưới.** Con thú luôn
*ở* một ô; khi di chuyển nó có thêm `progress ∈ [0,1)` giữa ô hiện tại và ô kế.
Vẽ ở `lerp(from, to, ease(progress))`, ~180ms mỗi ô. Đây là cách mọi game Zelda
2D làm, và nó cho cả hai thứ: lưới sạch cho logic, chuyển động liền cho mắt.

**Tìm đường bằng BFS, không phải A\*.** Bản đồ 300 ô, BFS chạy trong micro giây
và không có heuristic nào để viết sai. A\* chỉ đáng khi bản đồ lớn hơn hàng chục
lần.

**Bấm vào ô thì đi tới đó.** Không phím mũi tên làm chính — đây là một góc trong
app học, không phải một game người ta cầm bàn phím để chơi. (Bàn phím vẫn phải
dùng được cho trợ năng: xem §10.)

---

## 4. Quyết định 3 — trạng thái sống ở máy chủ

Bảng mới `pet_state`, khoá chính **là** `user_id` (mỗi người một con đang nuôi):

```
user_id      uuid  PK, FK users ON DELETE CASCADE
species      text          -- mã loài, tham chiếu pet_species.code
nickname     text NULL     -- người học tự đặt
level        int           -- KHÔNG lưu, xem §5
xp           int
level_reached int          -- mốc cao nhất, chỉ tăng
tile_x, tile_y int
facing       text          -- 'left' | 'right'
fullness, energy, mood  numeric(4,3)
needs_at     timestamptz   -- MỐC THỜI GIAN của ba số trên
hatched_at   timestamptz
```

Hai điều ở đây quyết định cả tính năng.

### 4.1 Nhu cầu **suy ra từ mốc thời gian**, không do client đếm

Bản cũ trừ dần theo `dt` của vòng `rAF`, nên đồng hồ chỉ chạy khi bảng đang mở.
Nghĩa là mở bảng cả buổi thì con thú đói, còn đóng tab một tuần thì nó vẫn no
nguyên — hoàn toàn ngược với trực giác của người nuôi.

Lưu `needs_at` và tính lại lúc **đọc**: `fullness_now = decay(fullness,
now - needs_at)`. Đây đúng là luật `profile_stats.py` đã dùng cho chuỗi ngày và
`StoryProgress` đã dùng cho tiến độ: **suy ra ở mỗi lần đọc, không lưu bộ đếm
chạy song song với lịch sử.** Client vẫn nội suy để thanh chỉ số nhích mượt,
nhưng con số của máy chủ là con số thật.

### 4.2 Ghi vị trí có **tiết lưu và nối tiếp**

Con thú đi qua 12 ô là 12 lần đổi vị trí. Ghi từng lần là 12 request cho một
lần bấm.

- Ghi khi **dừng hẳn**, cộng một `debounce` ~2 giây.
- Và **nối các lệnh ghi qua một promise duy nhất**, đúng như `persistBoard` của
  màn học từ vựng. Lý do y hệt: hai lệnh ghi cách nhau vài chục mili giây có thể
  về sai thứ tự, và khi đó vị trí lưu lại là vị trí *cũ hơn* — vẫn hợp lệ, vẫn
  không có lỗi nào, chỉ là sai. Con thú "nhảy ngược" sau khi tải lại trang.
- Hỏng thì **không chặn**: mất một mốc vị trí thì lần sau con thú đứng ở chỗ hơi
  khác. Không đáng để chặn thao tác.

---

## 5. Quyết định 4 — level của pet

**`level` không phải một cột.** `level_from_pet_xp(xp)` tra bảng ngưỡng, giống
hệt cách level user được suy ra từ `SUM(xp_event.amount)`. Lưu cả `xp` lẫn
`level` là hai nguồn sự thật cho một con số, và cái sai sẽ là cái không ai đọc.

**`level_reached` là mốc cao nhất chỉ tăng**, y như `user_profile.level_reached`:
chỉnh lại đường cong XP về sau không được lấy mất level của ai đã đạt.

**Nhưng KHÔNG dựng sổ cái `pet_xp_event`.** Sổ cái của user tồn tại vì XP ở đó
nuôi level, huy hiệu, nhiệm vụ ngày và trần ngày — nhiều thứ đọc chung một nguồn
nên nó phải là lịch sử. XP pet chỉ nuôi đúng một thứ là level pet. Một bộ đếm
cộng với mốc cao nhất là đủ, và rẻ hơn hẳn.

Nếu sau này XP pet mua được thứ gì thật (thức ăn, đồ trang trí) thì **đánh đổi
này hết hạn** và phải chuyển sang sổ cái trước khi thêm chỗ tiêu. Ghi câu đó
vào chính docstring của bảng.

**Nguồn XP pet: chính các hành động.** `feed` / `poke` / `walk`, mỗi hành động
một mức, có **trần ngày** như XP user và vì cùng một lý do — không có trần thì
bấm "chọc" 500 lần là max level, và lúc đó level pet không nói lên điều gì.

---

## 6. Quyết định 5 — gacha trứng

### 6.1 Quay ở **máy chủ**, không bàn cãi

Kết quả quay đi thẳng vào bộ sưu tập vĩnh viễn. Quay ở client là để người dùng
tự quyết định mình nhận được gì — chỉ cần mở devtools. `POST /pet/eggs/{tier}/open`
trả về con vừa nở; client chỉ *diễn hoạt* kết quả đó.

### 6.2 Tiền tệ **không được là XP user**

Đây là cái bẫy dễ rơi nhất. XP user nuôi level, mà **level không bao giờ tụt** —
đó là thuộc tính sổ cái `xp_event` được dựng ra để có. Cho tiêu XP mở trứng là
phá đúng thuộc tính ấy, hoặc buộc phải dựng một khái niệm "XP đã tiêu" song song
với sổ cái, và hai con số đó sẽ lệch nhau.

Đề xuất: **`egg_token`**, một bộ đếm riêng, kiếm từ việc hoàn thành nhiệm vụ
ngày (nguồn đã có sẵn và đã có trần). Tiêu token không đụng gì tới level.

### 6.3 Mở khoá theo level user, và **cấu hình là hàng, không phải hằng số**

Theo đúng khuôn `frame_tier` / `badge_rule` (ROADMAP §4w): mọi con số sửa được ở
`/admin`, không phải sửa code rồi deploy.

```
pet_species   code PK, label, tier, sprite_key, tone, status
egg_tier      code PK, label, min_level, token_cost, position
egg_drop      tier_code + species_code + weight     -- bảng tỉ lệ
```

Bốn thuộc tính phải giữ, mỗi cái đều hỏng im lặng nếu bỏ:

- **`min_level` đọc từ hàng, không hardcode.** Cùng lý do khung avatar chọn theo
  `max(min_level)` chứ không theo chuỗi `"challenger"`: một mã hardcode thành
  `None` im lặng vào ngày ai đó đổi tên.
- **`sprite_key` là tập đóng phía frontend**, y như `BadgePublic.icon`: backend
  thêm loài mà frontend chưa có ảnh thì phải là lỗi `tsc`, không phải một ô
  trống lúc chạy.
- **Trùng thì đổi thành mảnh.** Không có nó, người chơi mở trứng thứ mười và
  nhận đúng con đã có — trải nghiệm đó dạy người ta ngừng mở.
- **Bộ đếm an ủi (pity).** Sau N lần không ra hạng hiếm thì lần sau chắc chắn ra.
  Ngẫu nhiên thuần cho ra những chuỗi xui mà người chơi đọc là "hỏng".

### 6.4 Nói ra tỉ lệ

In tỉ lệ từng hạng ngay trên màn mở trứng. Nhiều nơi đã luật hoá việc này, và
kể cả không có luật thì đây là sản phẩm học cho học sinh — che tỉ lệ là thứ
không nên làm với đối tượng đó.

---

## 7. Bốn bảng mồ côi phải dọn

Database dev đang mang `pet`, `learner_pet`, `pet_feed`, `pet_feed_log` — dấu
vết của một tính năng dựng tại máy rồi hoàn tác code mà không hoàn tác database
(ROADMAP §4r, migration `029` ghi rõ). Không bảng nào nằm trong
`Base.metadata` (46 bảng, đã kiểm).

Migration mới **viết tay** và `DROP` cả bốn. Cảnh báo trong `029` vẫn nguyên giá
trị: chạy `--autogenerate` ở trạng thái này sẽ tự sinh bốn lệnh DROP mà không ai
yêu cầu — nên lần này chúng ta *cố ý* xoá, và ghi lý do vào migration.

---

## 8. Kiến trúc tệp và luật tầng mới

Giữ nguyên triết lý đã có, đổi danh sách:

```
petland-pet.ts      nhu cầu + hành động        — số học thuần, cấm React, cấm ảnh
petland-map.ts      lưới, va chạm, BFS         — số học thuần, cấm Pixi, cấm React
petland-sprite.ts   số đo mascot + atlas       — cấm scene, cấm Pixi
petland-render.ts   Pixi: nạp texture, vẽ      — chỗ DUY NHẤT import "pixi.js"
petland-ui.tsx      nút, thanh chỉ số, gacha   — cấm sprite/map/render
petland.tsx         ghép, vòng lặp, đồng bộ    — chỗ duy nhất biết cả hai phía
```

`scripts/check-petland-layers.mjs` mở rộng bằng hai luật mới, và luật quan trọng
nhất là: **chỉ `petland-render.ts` được `import "pixi.js"`**. Không có nó, sáu
tháng nữa "đổi renderer" là một cuộc tìm kiếm toàn dự án — và đó chính là loại
việc script này ra đời để chặn.

---

## 9. Các lát cắt, theo thứ tự

Mỗi lát tự đứng được và tự chứng minh được.

| # | Lát | Xong nghĩa là |
|---|---|---|
| 1 | ~~Đo bundle + quyết P1-7b~~ · **XONG 2026-08-26** | Xem §15 |
| 2 | Dọn 4 bảng mồ côi + `pet_state` | Migration chạy được cả lên lẫn xuống |
| 3 | Tilemap tĩnh + con thú đứng yên | Góc thú cưng vẽ bản đồ, con thú ở đúng ô đã lưu, camera đúng chỗ (§13) |
| 4 | Bấm ô → đi, BFS + nội suy | Đi vòng qua chướng ngại, dừng đúng ô, lưu vị trí |
| 5 | Nhu cầu suy từ `needs_at` + ba hành động | Đóng tab một ngày rồi mở lại thấy nó đói |
| 6 | Level pet + trần ngày | Bấm chọc 500 lần không lên được max |
| 7 | `pet_species` + admin | Thêm loài không cần deploy |
| 8 | Gacha: token, tier, quay ở server, pity | Tỉ lệ in ra màn hình khớp bảng cấu hình |
| 9 | Bộ sưu tập + đổi con đang nuôi | Đổi con giữ nguyên vị trí và nhu cầu |

Lát 1 đứng trước mọi thứ có chủ ý: cả hai câu hỏi của nó đều có thể lật ngược
lựa chọn thư viện, và lật sau lát 4 thì mất cả lát 3 lẫn lát 4.

---

## 10. Cái phải đo, và cái chưa biết

- **Bundle.** Chưa đo. Vì là góc nhỏ nằm trong `SidebarShell`, Pixi sẽ dính vào
  **mọi trang có sidebar**, không chỉ một route — nên phải `dynamic(..., { ssr:
  false })` và chỉ nạp khi bảng được mở lần đầu, nếu không mỗi lần vào trang từ
  vựng cũng kéo theo cả thư viện game.
- **Trợ năng.** Một canvas là một ô đen với trình đọc màn hình. Tối thiểu: bản
  đồ có `role="application"` + nhãn, các nút hành động là `<button>` thật nằm
  ngoài canvas (đã đúng ở bản cũ), và **điều khiển bằng phím mũi tên phải chạy
  được** — bấm chuột vào ô không thể là đường duy nhất.
- **`prefers-reduced-motion`.** Không thể tắt cả game. Đề xuất: bỏ nội suy (nhảy
  thẳng sang ô đích), bỏ hoạt ảnh nền, giữ nguyên khung idle. Phải kiểm bằng mắt
  chứ không bằng test.
- **Pin.** Vòng lặp phải dừng khi tab ẩn và khi canvas ra khỏi khung nhìn. Đo
  bằng Chrome Performance, ghi lại con số.
- **Sprite cho nhiều loài.** Mỗi loài cần 5 clip. `generate2dsprite` với anchor
  sheet cho ra kết quả dùng được (ROADMAP §4r), nhưng đó là *một* con và mất
  công. Mở gacha 12 loài là 12 lần như thế — **đây là chi phí lớn nhất của tính
  năng và nó là chi phí nội dung, không phải chi phí code.** Nên lát 8 cần một
  câu trả lời cho "12 loài lấy ở đâu ra" trước khi bắt đầu, không phải sau.

## 11. Cố ý KHÔNG làm

- **Không multiplayer, không thăm nhà nhau.** Mở ra là mở cả một tầng đồng bộ,
  kiểm duyệt nội dung (tên thú), và chống lạm dụng.
- **Không mua bằng tiền thật.** Gacha có tiền thật là một sản phẩm khác, với một
  bộ nghĩa vụ pháp lý khác.
- **Không để thú chết.** Một app học phạt người dùng vì nghỉ ba ngày là một app
  người ta không quay lại. Cùng lý do huy hiệu chuỗi ngày dùng `longest_streak`
  chứ không `current_streak`.
- **Không đưa thú vào màn làm bài.** Đã nói ở §1, nhắc lại vì đây là thứ dễ bị
  "thêm cho vui" nhất.

---

## 12. Ba quyết định đã chốt (2026-08-26)

1. **Pixi: dùng bình thường.** Chi tiết và cái giá kèm theo ở §2.1.
2. **Chỗ đứng: góc nhỏ**, không có trang riêng. Xem §13 — nó đổi kích cỡ bản đồ
   và cách camera hoạt động, chứ không chỉ đổi chỗ đặt.
3. **Sprite: xem bảng kê ở §14.** Con số thật nhỏ hơn "12 bộ × 5 clip" khá nhiều.

---

## 13. Hệ quả của "góc nhỏ": camera, không phải bản đồ tí hon

Khung hiện tại là **460×250** (`VIEW_W`/`VIEW_H`), kèm một chế độ mở rộng đã có
sẵn. Nên "góc nhỏ" **không** có nghĩa là thế giới phải nhỏ — nó có nghĩa là
**khung nhìn nhỏ và có camera**, đúng như bản cũ đang làm.

```
TILE            16px nguồn
Thế giới        20 × 15 ô  = 320 × 240 nguồn
Góc nhỏ         zoom 2× → thấy ~14 × 7 ô, camera bám con thú
Mở rộng         zoom 2× → 640 × 480, thấy TRỌN thế giới, camera đứng yên
```

Mọi hệ số phóng là **số nguyên**. Đây là ràng buộc cứng của pixel art: phóng 1.7×
làm mỗi pixel nguồn phủ 1.7 pixel màn hình, và hàng nào rơi vào ranh giới thì
dày mỏng khác nhau — ảnh trông "bẩn" theo kiểu không chỉ ra được nguyên nhân.
Khung 460×250 không chia hết cho 32, nên **canvas là 448×224 (14×7 ô) đặt giữa
khung**, phần thừa là nền. Ép canvas lấp đầy khung là ép phóng lẻ.

Camera bám con thú theo **ô, có vùng chết ở giữa**: chỉ cuộn khi con thú ra khỏi
vùng 4×3 ô trung tâm. Camera bám từng pixel làm cả bản đồ rung nhẹ suốt lúc con
thú đi — mắt đọc ra là nền trôi chứ không phải con thú đi.

---

## 14. Bảng kê tài nguyên hình ảnh — thứ thật sự cần

### 14.1 Hai bộ sprite đang có **không dùng lại được**, và đây là lý do

| | Đang có | Cần cho bản mới |
|---|---|---|
| Ô sprite | **151×117** (mèo), 125×117 (rex) | **32×32** |
| Phong cách | Khuếch tán sinh ra ở độ phân giải cao | Pixel art ở đúng độ phân giải đích |
| Dung lượng | ~75KB mỗi dải | ~2–4KB mỗi dải |

Cả hai lý do đều chặn, và lý do thứ hai chặn nặng hơn: **thu nhỏ một bức vẽ mượt
xuống 32×32 không ra pixel art**, nó ra một vũng màu nhoè. Pixel art là bảng màu
hạn chế và từng pixel được đặt ở đúng độ phân giải cuối. Đó là việc khác hẳn với
việc đã làm ở §4r.

151px ngang cạnh ô 16px cũng là con thú rộng **hơn chín ô** — không phải chuyện
chỉnh hệ số phóng.

### 14.2 Một bộ sprite gồm những gì

Ô **32×32**, tức 2×2 ô bản đồ. Con thú *chiếm* một ô về mặt logic nhưng được vẽ
cao hai ô, để có chỗ cho tai và đuôi.

- **Nhìn NGANG, chỉ một chiều.** Quay trái là lật ngang (`anchorX` đã là điểm lật
  sẵn trong `petland-sprite.ts`). Không làm bộ 4 hướng kiểu JRPG: nó nhân đôi tới
  gấp ba lượng vẽ để đổi lấy một thứ mà ở khung 448×224 gần như không ai để ý.
- **Dải ngang, PNG RGBA, nền trong suốt**, một hàng, rộng `số khung × 32`, cao 32.
  Đúng thứ `scripts/pack-pet.mjs` đang xuất ra.
- **`footY` và `anchorX` giống hệt nhau ở MỌI clip của cùng một loài.** Đây là
  bất biến `check-petland-fit.mjs` kiểm tuyệt đối; lệch một pixel là con thú lơ
  lửng hoặc lún, đều đặn tới mức đọc ra như một lựa chọn thiết kế chứ không như
  lỗi.
- **Bảng màu ≤ 32 màu mỗi loài**, để nó còn đọc ra là pixel art khi phóng 2×.

**Số khung, và cái nào thật sự bắt buộc.** `MASCOTS` đã cho phép một loài thiếu
hẳn một clip — `rex` hiện không có `walk` — nên bảng dưới đây có ba mức:

| Clip | Khung | fps | Mức | Thiếu thì sao |
|---|---|---|---|---|
| `idle` | 4 | 5 | **bắt buộc** | không có gì để vẽ lúc đứng yên |
| `walk` | 6 | 9 | **bắt buộc** | trượt trên bản đồ như bị kéo |
| `sleep` | 4 | 5 | nên có | rơi về `idle`, chấp nhận được |
| `run` | 6 | 13 | tuỳ | rơi về `walk` |
| `hop` | 6 | — | tuỳ | rơi về `idle` |

**Tối thiểu 10 khung/loài** (idle + walk). Đủ bộ là 26 khung — đúng bằng con mèo
hiện có. Với 12 loài: **120 khung ở mức tối thiểu**, 312 ở mức đầy đủ. Đó là
khoảng cách đáng để chọn có ý thức, không phải để mặc định làm đầy.

### 14.3 Ngoài con thú, còn ba thứ nữa

Bản kế hoạch trước bỏ sót, và đây mới là phần dễ đánh giá thấp:

1. **Tileset bản đồ** — một sheet ô 16×16: cỏ, đường, nước, hàng rào, cây, nhà,
   bát ăn, giường. Ước ~40–60 ô. **Không có nó thì không có gì để đứng lên.**
2. **Trứng gacha** — một sprite trứng 32×32 cho mỗi hạng (~4 hạng), cộng một clip
   nứt vỏ 4–6 khung dùng chung. Đổi màu theo hạng bằng `tint` được, nên có thể
   chỉ cần **một** bộ.
3. **Mẩu hiệu ứng** — tim, ngôi sao, giọt mồ hôi, 8×8 hoặc 16×16. Bản cũ đã có
   `petland-fx.ts`, chỉ cần vẽ lại ở cỡ nhỏ.

### 14.4 ĐÃ CHỌN: Tiny Town + Tiny Creatures, cả hai CC0 (2026-08-26)

Đã tải, đã mở ảnh ra xem thật, đã cài vào `apps/web/public/pet/`:

| Tệp | Gói | Cỡ | Nội dung |
|---|---|---|---|
| `town.png` | [Tiny Town](https://kenney.nl/assets/tiny-town) — Kenney | 5,0 KB · 132 ô | cỏ, đường đất, cây, bụi, nấm, hàng rào, nhà |
| `creatures.png` | [Tiny Creatures](https://opengameart.org/content/tiny-creatures) — Clint Bellanger | 11,5 KB · 180 ô | **hơn 50 động vật** + hơn 100 sinh vật huyền thoại |

**Tổng 24 KB cho toàn bộ phần nhìn**, và đó là con số đo từ tệp đã nằm trong
repo, không phải ước lượng.

**Cả hai CC0**, ghi công không bắt buộc; vẫn ghi ở `public/pet/CREDITS.md`.

**Vì sao hai gói này ghép được, mà không phải hai nguồn bất kỳ:** `License.txt`
của Tiny Creatures nói thẳng nó là **bản mở rộng cho Tiny Dungeon và Tiny Town
của Kenney**. Chúng vốn được vẽ để đứng cạnh nhau — cùng ô 16×16, cùng bảng màu,
cùng độ dày viền. Đây là thứ khó đạt nhất khi gom nhiều nguồn, và ở đây nó có
sẵn chứ không phải do ép.

**Mọi con đều quay mặt sang PHẢI** (`Tilesheet.txt` nói rõ), nên quay trái là lật
ngang lúc vẽ — đúng cơ chế `anchorX` đã có.

### 14.4b Mười hai loài đầu tiên, đã chọn theo chỉ số ô

Đã phóng to từng con để xác nhận chứ không đoán theo mô tả. Chỉ số là vị trí
trong `creatures.png` (lưới 10 cột).

| Hạng | Loài | Ô |
|---|---|---|
| thường | vịt · sóc · ếch | 150 · 175 · 147 |
| khá | mèo · khỉ · rùa | 169 · 168 · 149 |
| hiếm | cú · hươu · gấu mèo | 117 · 161 · 178 |
| cực hiếm | hổ · gấu · hươu cao cổ | 157 · 165 · 159 |

Bảng này là **dữ liệu khởi tạo cho `pet_species`, không phải hằng số trong code**
(§6.3). Còn hơn 40 con nữa trong gói để mở rộng mà không phải tải thêm gì.

### 14.4c Hai ứng viên đã loại, kèm lý do

- **Kenney Tiny Farm** — đã tải và mở ảnh: chỉ **3 con vật** (bò, bò khác màu,
  gà), phần còn lại là cây trồng và nông cụ. Không đủ cho gacha. Đáng giữ lại làm
  **trang trí bản đồ** (luống đất, hàng rào, hoa hướng dương) nếu cần sau này.
- **Kenney Tiny Dungeon** — đã cài rồi lại gỡ. Dàn sinh vật là quái ngục tối
  (slime, nhện, ma, bộ xương): hợp mô-típ gacha nhưng sai tông cho một góc nuôi
  thú trong app học. Tấm ghép của nó vẫn nằm trong gói Tiny Creatures nếu sau
  này cần quái làm hạng hiếm.
- **[Animal Icons](https://ydo4ki.itch.io/animalicons)** (15 con, CC0, 16×16) —
  nội dung hợp lệ nhưng **itch.io không trả tệp cho `curl`**, nó chặn bằng một
  trang trung gian. Thử hai cách rồi dừng. Ghi lại vì đây là ràng buộc chung:
  **nguồn nào không tải được bằng dòng lệnh thì không tự động hoá lại được** —
  OpenGameArt và kenney.nl phục vụ tệp trực tiếp, itch.io thì không.

### 14.5 Hệ quả lớn nhất: sprite MỘT khung, chuyển động sinh lúc vẽ

Gói của Kenney **không có khung hoạt ảnh nào**. Mỗi sinh vật là một ô 16×16.

Điều này lật ngược §14.2: không còn "idle 4 khung, walk 6 khung". Thay vào đó
chuyển động được **sinh bằng phép biến hình lúc vẽ**, trên đúng một ảnh:

```
đứng yên   scaleY nhấp nhô ±4%, chu kỳ ~1,6s   → nhịp thở
đi         nhún dọc 1px theo tiến độ giữa hai ô + nghiêng nhẹ
ngủ        đứng yên, biên độ thở chậm hơn, thêm mẩu "z"
ăn         hai lần nhún nhanh về phía bát
```

Đây không phải bản thay thế hạng hai. Ở ô 16px phóng 2×, biên độ chuyển động
thật chỉ vài pixel, nên mắt đọc *nhịp* chứ không đọc *khung hình* — và một sprite
một khung có nhịp đúng trông sống hơn một sprite bốn khung có nhịp sai.

Ba thứ nó đổi, và cả ba đều theo hướng tốt:

- **Thêm một loài tốn đúng một toạ độ ô** trong bảng, không tốn 10–26 khung vẽ.
  Gacha 12 loài trở thành 12 dòng dữ liệu, và đó là khác biệt giữa "làm được
  trong tuần này" với "chờ nội dung".
- **`petland-sprite.ts` đơn giản hẳn**: không còn `frames`, `fps`, `loop`, không
  còn dải ảnh mỗi clip. Chỉ còn ô nào trong tấm ghép.
- **`check-petland-fit.mjs` gần như không còn việc.** Bất biến `footY`/`anchorX`
  giống nhau giữa các clip tồn tại vì có nhiều clip; một khung thì không có gì
  để lệch. Phép kiểm còn lại rất nhỏ: mọi toạ độ ô phải nằm trong tấm ghép.

Cái mất: không có dáng đi thật (chân không bước). Ở cỡ này thì đó là thứ **không
nhìn thấy được** — nhưng phải nói ra ở đây, vì nếu sau này phóng to lên hoặc
chuyển sang trang riêng thì đánh đổi này hết hạn.

---

## 15. Lát 1 đã xong — con số thật (2026-08-26)

Đo bằng cách build hai lần và trừ, không phải đọc trang npm: một lần có trang
dùng Pixi, một lần gỡ hẳn trang đó ra khỏi `src/app/`.

| | tệp chunk | raw | **gzip** |
|---|---|---|---|
| Không Pixi | 54 | 1 081 KB | **353 KB** |
| Có Pixi | 66 | 1 630 KB | **516 KB** |
| **Chênh lệch** | **+12** | +549 KB | **+163 KB** |

**Kết luận: Pixi ở lại.** 163 KB gzip nằm dưới hẳn ngưỡng ~500 KB đã đặt cho
route này ở §2.

Điều đáng chú ý hơn con số: phần thêm vào là **12 tệp chunk MỚI**, không phải
các chunk sẵn có phình ra. Đó là dấu hiệu `dynamic(() => import(...), { ssr:
false })` đang làm đúng việc — Pixi nằm ở chunk nạp lười, không nằm trong gói
dùng chung mà mọi trang phải tải.

**Nhưng điều đó CHƯA đủ, và đây là rủi ro còn nguyên.** Góc thú cưng sống trong
`SidebarShell`, tức có mặt ở mọi trang có sidebar. Chunk nạp lười chỉ rẻ khi nó
không được yêu cầu; nếu bảng tự dựng sân khấu ngay lúc mount thì Pixi tải ở mọi
trang, và 163 KB quay lại thành chi phí thường trực. **Sân khấu chỉ được dựng
khi người dùng MỞ bảng**, không phải khi bảng xuất hiện. Đây là ràng buộc của
lát 3, không phải chuyện tối ưu để dành.

### Đã viết trong lát này

- `src/components/petland-map.ts` — lưới 20×15, va chạm, BFS. Số học thuần,
  không React, không Pixi. Bản đồ viết bằng **chữ** chứ không phải mảng số: một
  hàng rào thủng lộ ra lúc đọc mã, chứ không lộ lúc con thú đi xuyên qua.
- `src/components/petland-render.ts` — tệp duy nhất `import "pixi.js"`.
- `src/app/petlab/` — **trang tạm để đo**, và hiện là chỗ duy nhất chạy thử
  được. **Phải xoá ở lát 3** khi góc nhỏ tiếp quản. Ghi ở đây vì một route bỏ
  quên là thứ vô hình: Next chỉ định tuyến thư mục có `page.tsx`, nên nó không
  gây lỗi gì cả, chỉ âm thầm ở lại.

### Hai chi tiết của Pixi đã trả giá trước

- **`scaleMode = "nearest"` phải đặt TRƯỚC lần nạp texture đầu tiên.** Mặc định
  là `linear`, thứ nội suy giữa các pixel — đúng cho ảnh chụp, sai hoàn toàn cho
  pixel art. Đặt sau khi nạp thì texture đầu tiên đã mang chế độ cũ, mà texture
  đầu tiên là tấm nền, tức đúng thứ chiếm nhiều diện tích nhất.
- **`app.destroy(true, { children: true })` khi gỡ.** Không gọi thì mỗi lần mở
  lại bảng là thêm một WebGL context, và trình duyệt chỉ cho vài cái trước khi
  từ chối — lỗi xuất hiện sau vài lần điều hướng, tức xa hẳn nguyên nhân.
