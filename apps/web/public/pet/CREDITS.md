# Tài nguyên hình ảnh của góc thú cưng

Hai tệp trong thư mục này là **tấm ghép ô** (`tilemap_packed.png`) lấy nguyên từ
hai gói, chỉ đổi tên cho dễ đọc. Không sửa pixel nào.

| Tệp | Gói gốc | Cỡ | Nội dung |
|---|---|---|---|
| `town.png` | [Tiny Town](https://kenney.nl/assets/tiny-town) — Kenney | 5,0 KB · 12×11 = 132 ô | cỏ, cây, bụi, nấm, hàng rào, nhà, biển báo |
| `farm.png` | [Tiny Farm](https://kenney.nl/assets/tiny-farm) — Kenney | 5,5 KB · 12×11 = 132 ô | luống đất cày, rau củ, hoa hướng dương, kiện cỏ, máng nước, xô |
| `water.png` | [Tiny Battle](https://kenney.nl/assets/tiny-battle) — Kenney | 8,6 KB · 18×11 = 198 ô | **bộ ghép bờ nước** (ao, hồ), đường, cây |
| `stone.png` | [Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon) — Kenney | 5,2 KB · 12×11 = 132 ô | **gạch lát nền**, tường đá, cửa |
| `creatures.png` | [Tiny Creatures](https://opengameart.org/content/tiny-creatures) — Clint Bellanger | 11,5 KB · 10×18 = 180 ô | hơn 50 động vật và hơn 100 sinh vật huyền thoại |
| `dinos.png` | **NGUỒN CHƯA XÁC ĐỊNH — xem dưới** | 10×2 = 16 ô | mười sáu khủng long |
| `myth.png` | **NGUỒN CHƯA XÁC ĐỊNH — xem dưới** | 10×4 = 32 ô | rồng, kỳ lân, phượng hoàng, sư tử, nhân sư, cửu vĩ hồ, voi ma mút |

- **Giấy phép: cả hai đều CC0 1.0** (Creative Commons Zero, Public Domain
  Dedication). Nguyên văn: *"free to use in personal, educational and commercial
  projects. Support my work by crediting … (this is not mandatory)."*
- **Ghi công: không bắt buộc.** Ghi ở đây vì câu hỏi "tệp này ở đâu ra, có được
  dùng không" phải trả lời được cho từng tệp — cùng kỷ luật với
  `question.source` không có giá trị mặc định, và với `public/sounds/CREDITS.md`.

## Vì sao hai gói này, và vì sao chúng ghép được

Tiny Creatures nói thẳng trong `License.txt` của nó rằng đây là **bản mở rộng
cho Tiny Dungeon và Tiny Town của Kenney**. Nên hai tệp trên không phải hai
nguồn rời được ép cho giống nhau — chúng vốn được vẽ để đứng cạnh nhau: cùng ô
16×16, cùng bảng màu, cùng độ dày viền.

Đồng nhất phong cách là thứ khó đạt nhất khi gom nhiều nguồn, và là lý do
ADR-010 §14.4 chọn tải một bộ có sẵn thay vì tự vẽ từng con.

Ba gói của Kenney **không có sinh vật nào**, Tiny Creatures **không có cảnh nền**,
và chỉ Tiny Battle có **nước**. Mỗi gói thiếu đúng thứ gói kia có.

## Hai điều phải biết trước khi dùng

**1. Sprite MỘT khung.** Không có khung hoạt ảnh nào. Mỗi sinh vật là một ô
16×16 duy nhất. Đó là đánh đổi có chủ ý chứ không phải thiếu sót phát hiện muộn
— xem ADR-010 §14.5: chuyển động (thở khi đứng, nhún khi đi) được sinh **bằng
phép biến hình lúc vẽ**. Đổi lại, thêm một loài tốn đúng **một số** trong bảng,
không tốn 10–26 khung vẽ tay.

**2. Mọi con đều quay MẶT SANG PHẢI.** `Tilesheet.txt` của gói nói rõ điều này.
Quay trái là lật ngang lúc vẽ — đúng cơ chế `anchorX` đã có sẵn trong
`petland-sprite.ts`. Đừng vẽ thêm bản quay trái.

## Cách đánh số ô

`creatures.png` là lưới **10 cột**, không có khoảng cách giữa các ô. Nên với chỉ
số `i`:

```
cột = i % 10        x = cột * 16
hàng = i // 10      y = hàng * 16
```

`town.png`, `farm.png` và `stone.png` là lưới **12 cột**; `water.png` là **18 cột**. Số cột
nằm ở `SHEET_COLS` trong `petland-map.ts` — sai số cột thì ô vẫn vẽ ra, chỉ là
vẽ nhầm ô, nên không có gì báo.

## `dinos.png` và `myth.png` — chưa trả lời được câu "ở đâu ra"

**Hai tệp này đang thiếu đúng thứ mà tài liệu này tồn tại để ghi.** Chúng được
đóng bằng `app.content.pack_sprites` từ `~/Downloads/dinasour-assets.png`,
`god-pet.png`, `god-pet-02.png` và `god-pet-03.png`; cả bốn ảnh gốc có nền
magenta phẳng — dấu vết của một đường sinh ảnh. Nhưng "sinh bằng model nào, hay tải từ đâu" thì chưa ai
ghi lại, nên **giấy phép chưa biết**.

Đừng suy ra từ việc nó trông giống hàng tự sinh. Cùng kỷ luật với
`question.source` không có giá trị mặc định: một ô trống phải đọc ra là ô trống,
không phải là một phỏng đoán.

Cần điền trước khi phát hành: nguồn, tác giả (nếu có), giấy phép. Nếu nó do
chính dự án sinh ra thì ghi model và ngày, và chuyện bản quyền chấm dứt ở đó.

`myth.png` giữ **cả 44 ô**, kể cả những ô đọc kém. Ô 32–43 đến từ
`god-pet-03.png`, thêm ngày 2026-09-08; ba mươi hai ô đầu giữ nguyên **từng
pixel**, và điều đó được kiểm trước khi ghi chứ không phải suy ra — `pet_species`
tham chiếu ô theo CHỈ SỐ, nên một ô xê dịch là một loài đang nuôi đổi hình mà
không gì báo. Thứ tự `--input` là thứ giữ chỉ số đứng yên: thêm ảnh mới vào
CUỐI, không bao giờ chèn vào giữa. Chất lượng chênh nhau rõ giữa
hai ảnh gốc — `god-pet-02.png` ra 16 ô sạch, `god-pet.png` thì phần lớn nhoè — và
khác biệt nằm ở **cỡ pixel của ảnh gốc**, không ở đề tài: bộ sau vẽ khối to hơn
hẳn nên phép thu về 16×16 giữ được hình. Xem `PETLAND-SPRITE-PROMPTS.md` §0.

Nhưng "đọc được hay không" là **quyết định của người ra nội dung**, nên tấm giữ
đủ và màn quản trị hiện cả tấm để chọn bằng mắt. Lọc sẵn ở bước đóng gói là thay
người khác quyết, và một ô bị bỏ thì không có đường nào nhìn thấy lại.

**Chúng KHÔNG phải bản gốc, và đó là điều phải ghi kèm giấy phép.** `pack_sprites`
thu ảnh về 16×16 rồi **ép màu về đúng bảng 22 màu của `creatures.png`** và tô lại
vành ngoài bằng màu viền. Tệp trong repo là bản đã biến đổi, không phải bản nhận
về.
