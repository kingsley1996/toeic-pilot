# Sinh sprite Petland — hợp đồng định dạng và prompt

Prompt để làm thêm ô sinh vật hạng **huyền thoại** và **thần**, đứng cạnh được
`creatures.png` hiện có.

Đo ngày **2026-09-07** trên chính tấm ghép đang chạy: 180 ô, 34 040 pixel đục.

---

## 0. Đọc trước: đường sinh ảnh KHÔNG tự nó ra được asset dùng ngay

Đã thử ba vòng với FLUX.2-klein, có gửi kèm 12 ô hiện có làm ảnh tham chiếu.
Kết quả: model **hiểu phong cách** — nó chịu nền magenta, chia đúng lưới, vẽ
bốn vị thần phân biệt được, và ở 1024px trông rất giống. Nhưng nó **không vẽ
được 16×16**: nó vẽ một bức tranh *về* pixel art ở độ phân giải cao, và ta phải
thu nhỏ — mà thu nhỏ là phép trung bình, đúng thứ phá hỏng phong cách này.

Ở 16×16 chỉ có 256 pixel, nên **mỗi pixel là một quyết định thiết kế, không phải
một chi tiết kết xuất.** Con nào silhouette đơn giản (chim, khối tròn) thì sống
sót; con nào có đạo cụ mảnh (đinh ba, tia sét) thì thành nhiễu.

### Thứ quyết định là CỠ PIXEL CỦA ẢNH GỐC, không phải prompt

Đo trên ba mẻ thật, cùng một prompt, cùng một đường hậu xử lý:

| Ảnh gốc | Ô dùng được |
|---|---|
| `god-pet-02.png` | **16/16** |
| `dinasour-assets.png` | 13/16 |
| `god-pet.png` | **2/16** |

Khác biệt không nằm ở đề tài mà ở **độ thô của bản vẽ**. Bộ tốt nhất vẽ mỗi "pixel
nghệ thuật" thành một khối lớn và đều; bộ tệ nhất vẽ chi tiết mịn hơn, trông đẹp ở
1024px và **tan hết** khi thu về 16×16. Số màu mỗi ô là dấu hiệu đọc được sớm: bộ
tốt ra 6–12 màu, bộ hỏng ra tới 17 — vượt cả khoảng 3–11 của tấm gốc.

Nên khi một mẻ ra kém, đừng sửa phép thu nhỏ. Sinh lại và **đòi khối to hơn**.

Nên tài liệu này phục vụ **hai** người đọc, và phần §1–§2 giống hệt nhau cho cả
hai: một model sinh ảnh (ra bản nháp, người sửa tay sau), hoặc một hoạ sĩ pixel
được thuê (ra asset dùng ngay). Với 16×16 và 22 màu, vẽ tay 8–10 ô là việc vài
tiếng, không phải vài ngày.

**Chi phí máy, đo được:** FLUX.2-klein 4-bit, đỉnh **12,44 GB** trên máy 16 GB,
**~4 phút** một tấm 1024×1024. Đừng thử Qwen-Image — nó làm treo máy, và lý do
nằm ở `~/.claude/skills/_imagegen/CLAUDE-CODE-ADAPTER.md`.

## 1. Hợp đồng định dạng, đo từ tấm đang chạy

| | Giá trị |
|---|---|
| Ô | **16×16**, không khoảng cách, lưới 10 cột |
| Khung hình | **một**. Không có hoạt ảnh — chuyển động sinh bằng phép biến hình lúc vẽ (ADR-010 §14.5) |
| Hướng | **quay mặt sang PHẢI**. Quay trái là lật ngang lúc vẽ; đừng vẽ bản thứ hai |
| Nền | trong suốt |
| Số màu mỗi con | trung vị **5**, khoảng 3–11 — kể cả màu viền |
| Diện tích lấp | trung vị **202/256 pixel (79%)** |
| Khung bao | trung vị **16×16** — con vật **CHẠM MÉP Ô** |

Hai dòng cuối là chỗ dễ làm sai nhất, và nó ngược với lời khuyên thông thường
khi prompt sprite sheet. Bộ này **không chừa lề**: con vật lấp gần kín ô và
đụng cả bốn cạnh. Bảo model "chừa lề rộng, không chạm mép" sẽ ra một con nhỏ
lọt thỏm, đứng cạnh 180 ô kia là thấy ngay.

## 2. Bảng màu — 22 màu, không thêm màu thứ 23

Viền là **`#3F2631`** và nó chiếm **50,5%** toàn bộ pixel đục của tấm ghép; trong
một con vật, **48%** số pixel là viền. Viền không phải đường bao — nó là **một
nửa bức vẽ**. Đó là thứ làm bộ này nhận ra được từ xa, và là thứ biến mất đầu
tiên khi thu nhỏ một ảnh độ phân giải cao.

```
Viền     #3F2631        Nền tối   #262B44

Xám lam  #52607C  #8B9BB4  #C0CBDC  #FFFFFF
Da/nâu   #763B36  #BD6C4A  #E19A65  #F7C282  #EAA56C
Lửa      #E84537  #FF706D  #FEAE34  #FEE761
Nước     #0099DB  #75E3FF
Lục      #25956A  #43E1B3  #69FFD4
Tím      #9B4CA3  #D176D0
```

Không có vàng kim riêng. Hào quang của cả ba thiên thần (ô 35, 36, 37) chỉ dùng
**`#FEE761`**, sáu tới chín pixel mỗi con — vàng ở bộ này là một điểm nhấn nhỏ,
không phải một mảng. `#FEAE34` là cam, dùng cho lửa. Không có tím sẫm: `#9B4CA3`
là tím đậm nhất, dành cho phép thuật và hư không.

Ba ô thiên thần ấy cũng cho thấy tỉ lệ viền rõ nhất: **81–90 trong khoảng 190
pixel** của mỗi con là `#3F2631`.

## 3. Đầu prompt dùng chung

Dán nguyên khối này trước mọi mô tả ở §4.

```
A 16x16 pixel art creature sprite in the exact style of the reference image
(Tiny Creatures by Clint Bellanger, an expansion for Kenney's Tiny Dungeon).

Hard rules:
- The creature is enclosed by a THICK dark outline in #3F2631, two pixels wide
  on the outer silhouette. This outline is about half of all drawn pixels — it
  is the defining feature of the style, not a thin border.
- Flat cel colour only. No gradients, no dithering, no anti-aliasing, no
  highlights, no drop shadows, no gloss.
- At most FIVE colours in total, including the outline, taken only from this
  palette: #3F2631 #262B44 #52607C #8B9BB4 #C0CBDC #FFFFFF #763B36 #BD6C4A
  #E19A65 #F7C282 #E84537 #FF706D #FEAE34 #FEE761 #0099DB #75E3FF #25956A
  #43E1B3 #9B4CA3 #D176D0
- The creature FILLS the tile: it occupies about 79% of the 16x16 square and
  touches all four edges. Do NOT leave a margin around it.
- Chunky proportions: the head is roughly 40% of the total height. Bodies are
  compact rounded blobs, not realistic anatomy.
- Eyes are single solid dark dots or 1x2 dark rectangles. No pupils, no
  eyelashes, no mouth detail beyond one or two pixels.
- The creature faces RIGHT.
- One single frame. No animation, no motion blur, no multiple poses.
- Solid #FF00FF magenta background.
```

## 4. Mô tả từng con

Xếp theo **độ đơn giản của silhouette**, dễ trước. Ở 16×16 đó là yếu tố quyết
định con nào ra được: hình khối tròn và chim thì sống sót, đạo cụ mảnh thì không.

### Hạng thần

| # | Con | Mô tả dán vào sau khối §3 | Ghi chú silhouette |
|---|---|---|---|
| T1 | Thần mặt trời | `A sun deity: a round face in #F7C282 surrounded by a full ring of blunt triangular rays in #FEAE34 and #FEE761. The rays form the outer silhouette.` | Khối tròn — an toàn nhất |
| T2 | Thần bóng tối | `A void deity: a hooded figure, robe in #262B44 and #52607C, hood opening solid #3F2631 with two glowing #D176D0 dots for eyes. No visible face or hands.` | Khối liền, đối trọng của ô 35–37 |
| T3 | Thần cây | `A forest deity: a squat figure whose head is a rounded canopy in #25956A and #43E1B3, body a thick #763B36 trunk. Two dark dot eyes on the trunk.` | Hai khối chồng |
| T4 | Thần sấm | `A storm deity: an old man with a large #FFFFFF beard covering the chest, robe in #52607C, and a short thick #FEE761 zigzag bolt held close to the body at chest height.` | **Tia sét phải NGẮN và DÀY** — dài mảnh thì mất |
| T5 | Thần biển | `A sea deity: a #0099DB figure with a #C0CBDC crown of three blunt points, a #75E3FF wave curling behind the shoulders. No trident.` | **Bỏ đinh ba** — thử rồi, thành nhiễu |
| T6 | Thần thời gian | `A time deity: a hooded figure in #8B9BB4 holding a large #FEAE34 hourglass that occupies the lower half of the tile.` | Đồng hồ cát phải to |

### Hạng huyền thoại

| # | Con | Mô tả dán vào sau khối §3 | Ghi chú silhouette |
|---|---|---|---|
| H1 | Phượng hoàng | `A phoenix: a compact bird with a #E84537 body, #FEAE34 and #FEE761 tail flames fanning up and back, small #FEE761 beak, one dark dot eye.` | Chim — sống sót tốt nhất |
| H2 | Chim sấm | `A thunderbird: a broad dark #52607C bird with wings spread, #FEE761 markings on the wing edges, one dark dot eye.` | Như trên |
| H3 | Cửu vĩ hồ | `A nine-tailed fox: a #BD6C4A fox with a fan of thick tails in #E19A65 spreading behind it, #FFFFFF tail tips, one dark dot eye.` | Đuôi phải **dày**, không mảnh |
| H4 | Rồng mây | `An eastern dragon: a long #25956A serpentine body coiled into an S shape filling the tile, #43E1B3 belly, small #FEE761 horns. No wings.` | Cuộn chữ S để lấp ô |
| H5 | Nghê đá | `A stone guardian lion: a squat #8B9BB4 lion statue with a thick curled #C0CBDC mane, blocky legs, two dark dot eyes.` | Khối vuông chắc |
| H6 | Thuỷ mã | `A water horse: a #0099DB horse whose mane and tail are #75E3FF wave crests, standing in profile facing right.` | Cùng khuôn ngựa ô 30/51/54 |

## 5. Sau khi có ảnh

Model trả về ảnh lớn, không phải 16×16. Bốn bước, đều tất định:

1. **Tách ô và bỏ nền magenta** — ngưỡng rộng tay, `R>175 & G<115 & B>100`.
2. **Thu bằng lấy mẫu GẦN NHẤT (`Image.NEAREST`)**, không bao giờ dùng lấy mẫu
   nội suy. Đây là bước quyết định: nội suy làm nhoè và phong cách này chết ngay
   ở đó.
3. **Ép về bảng màu §2** — với mỗi pixel, chọn màu gần nhất theo khoảng cách RGB.
4. **Vẽ lại viền** nếu bước 2 làm mỏng nó: nở alpha ra một vòng rồi tô `#3F2631`.

Rồi **nhìn ở đúng cỡ 16px, không nhìn bản phóng to** — cùng bài học mà
`BRAND-ASSETS.md` §4 đã ghi cho favicon. Một con đẹp ở 512px mà nhoè ở 16px là
chuyện thường, và ô trong game là chỗ duy nhất người dùng thật sự nhìn thấy.

## 6. Ba thứ model làm không được

**Không vẽ được đúng 256 pixel.** Xem §0. Thứ nhận về là bản nháp bố cục.

**Không giữ được đạo cụ mảnh.** Đinh ba, quyền trượng, kiếm, tia sét dài — tất
cả thành mấy chấm xám. Đo được ở vòng thử: cây đinh ba của thần biển không đọc
ra được ở bất kỳ cách thu nhỏ nào. Vì thế T5 đã **bỏ hẳn đinh ba**, và T4 đòi
tia sét *ngắn và dày*. Sửa mô tả, đừng sửa cách thu nhỏ.

**Không quay mặt đúng.** Cả bốn con của vòng thử đều quay ra trước, một con quay
trái, dù prompt nói RIGHT. Kiểm bằng mắt và lật ngang nếu cần — rẻ hơn sinh lại.

## 7. Lắp vào hệ — đường đã dựng (2026-09-07)

Ô mới **không vào được `creatures.png`**: tấm ấy đủ 180 ô. Nên có tấm thứ hai, và
ba chỗ từng khoá cứng vào tấm gốc nay đã mở:

**`pet_species.sheet`** (migration 072). Không có cột này thì ô 5 của `dinos.png`
và ô 5 của `creatures.png` là **cùng một hàng dữ liệu**, và con nào vẽ ra thì tuỳ
tệp nào frontend nạp trước. CHECK cũ ghi cứng `tile < 180` đã nới thành `tile >= 0`:
trần trên là thuộc tính của TẤM, mà database không biết tấm nào bao nhiêu ô.

**Trần ấy kiểm ở tầng schema**, qua `CREATURE_SHEET_TILES`. Với một lượt PATCH,
phép kiểm phải đọc giá trị **sau** khi áp thay đổi — gửi mỗi `sheet` mà không gửi
`tile` vẫn có thể làm ô đang lưu vượt trần — nên nó nằm ở nơi gọi, không ở schema.

**`CreatureSheetId` khai ở API**, không ở frontend. Cùng lý do đã ghi cho `PetId`:
khai ở API thì nó đi qua OpenAPI thành union TypeScript, nên `Record<CreatureSheetId,
CreatureSheet>` thiếu một tấm là lỗi `tsc`. Điều đó đã tự chứng minh ngay trong lô
này: `tsc` chỉ ra hai schema nữa cũng cần cột tấm (`EggChance`, `PetOwnedPublic`)
mà không ai phải nhớ.

**`petland-sprite.ts` là nơi duy nhất biết đường dẫn ảnh và số cột.** Trước lô này
`creatures.png` được viết cứng ở **bốn** tệp và hình học bị chép lại ở hai — trong
đó một tệp có sẵn dòng comment thú nhận nó là "bản sao thứ hai". Số cột đã bị đoán
sai một lần rồi: nút thu gọn lấy 12 cột của tấm NỀN cho tấm sinh vật 10 cột, cắt ra
một mảnh của con khác, đủ giống một con thú để không ai nhận ra.

### Thêm một tấm, các bước

```bash
# 1. Đóng ảnh thô thành tấm ghép. Mặc định chỉ BÁO CÁO, không ghi.
cd apps/api
uv run python -m app.content.pack_sprites --input ~/Downloads/raw.png --sheet dinos
uv run python -m app.content.pack_sprites --input ~/Downloads/raw.png --sheet dinos --commit
```

2. Một dòng ở `CREATURE_SHEET_TILES` (`app/models/pet.py`) và một dòng ở
   `CreatureSheetId` (`app/schemas/pet.py`).
3. Một dòng ở `CREATURE_SHEETS` (`petland-sprite.ts`) — url, cols, rows.
4. `pnpm gen:api-types`, rồi `tsc` sẽ chỉ ra chỗ nào còn thiếu.
5. **Ghi nguồn và giấy phép vào `public/pet/CREDITS.md`.** Không phải thủ tục:
   tệp ấy tồn tại để trả lời "tệp này ở đâu ra, có được dùng không" cho từng tệp.

`pack_sprites` nhận nền bằng **liên thông từ mép**, không bằng ngưỡng màu, và đó
là chỗ hai vòng đầu đều sai: một con vật thân tím có màu gần magenta, nên ngưỡng
đủ rộng để xoá viền nhoè cũng đủ rộng để ăn mất cả con vật. Đo được: siết ngưỡng
thì mất hẳn con tím và một phần con cổ dài; nới ra thì rìa đầy đốm tím. Liên thông
không có đánh đổi ấy.

Nó cũng **tô lại vành ngoài bằng màu viền** — không phải thủ thuật, mà là luật ở
§1: mọi ô của bộ này có viền kín bao quanh. Bước đó dọn đúng khuyết tật còn lại
sau phép tách nền, vì pixel ở ranh giới là nửa nền nửa viền và khi ép bảng màu thì
rơi vào **tím** (`#9B4CA3` là màu gần magenta nhất trong bảng).

## 8. Vẫn rẻ hơn: dùng ô đã có

180 ô mới dùng 48. Bảy ô hạng thần đang bỏ không — **49** (tinh linh băng, hoàn bộ
tứ đại), **38** và **39** (đại quỷ, tiểu quỷ — đối trọng của bộ thiên thần 35–37),
**4** (thần chết), **89** (lõi sáng), **75** (cổng hư không), **108** (thần thú
vàng) — cùng khoảng mười ô hạng huyền thoại (**32**, **34** rồng; **53** ngựa bóng
đêm; **104**, **105** sư tử có cánh; **90**, **91** nhân sư; **96**, **97** vua
quái; **42**, **43** người cây, người tuyết).

Do chính tác giả gốc vẽ, CC0, và promote được ngay ở `/admin/petland/creatures` mà
không cần một dòng mã nào.
