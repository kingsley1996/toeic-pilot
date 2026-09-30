---
name: scene-3d
description: Dung 1 canh 3D visual-vocabulary moi (scene file + shapes + environment + verify) — dung khi them canh thu N cho /learn/scenes
---

# Scene-3D: dựng một cảnh từ vựng 3D mới

Thêm một cảnh vào `/learn/scenes` (định nghĩa sống trong code, không ở DB).
Mọi đường dẫn dưới đây tính từ `apps/web/`.

## 0. Đọc trước khi đụng code

`planning/docs/SPEC-VISUAL-VOCAB-3D.md` §7–§9 (bài học cảnh urban/construction/
residence) + §10–§12 nếu là indoor/outdoor rộng. Toàn là lỗi "vẫn ra hình" —
chỉ bắt bằng số, không bắt bằng mắt. Luật vùng mã đầy đủ: `CLAUDE.md`.

## 1. Chuẩn bị: từ vựng trước, hình sau

- Cảnh ràng buộc từ bằng cặp `(headword, part_of_speech)` — cả hai bắt buộc,
  headword không duy nhất (`content/scenes/types.ts`). Topic (`topicSlug`)
  phải chứa đủ entry published, không thì canvas đẹp mà thiếu hotspot (e2e
  chỉ lỗi này mới bắt được).
- Đổi tên headword = từ mới: audio cũ lệch hash im lặng. Muốn chữ khác thì
  nhập entry mới + audio mới, từ cũ ở lại published không hotspot.
- Decor (xe nền, cửa, vạch thừa) không nhãn, không vào bảng từ. Bỏ object
  khỏi scene không xoá từ trong DB.
- Spec gợi ý (không bắt buộc): `planning/scenes/<ten>_spec.md` theo mẫu các
  file có sẵn — chốt danh sách từ + bố cục nam→bắc trước khi vẽ.

## 2. Scene file — `src/content/scenes/<ten>.ts`

`SceneDef`: `id`, `title`, `description`, `topicSlug`, `sky` (3D không ăn
token CSS), `environment` (mỗi cảnh một bộ, không dùng lẫn), `home`
(indoor/outdoor rộng BẮT BUỘC home riêng — home mặc định dồn pill thành chùm),
`badges: ["new", "beta"]` cho tới khi mắt người duyệt, `objects`.

Mỗi object (`SceneObjectDef`):

- `position` tính bằng số, kiểm footprint hàng xóm trước khi đặt — vật lọt
  vào footprint lân cận là bấm nhầm lân cận. Vật tựa khung thuộc MẶT NGOÀI.
- `hotspotY − topY ≥ 0.85` (quy tắc 0.8 + dư float 0.05 — đúng 0.8 là
  `0.7999…` và mất mũi tên im lặng). Vật bẹt (mặt đất/nước/lối): nhãn ôm
  mặt, không mũi tên. Nhãn vật patrol treo cao hơn thân.
- `focus` cho vật trải dài mà nhãn đứng ở đầu; `patrol` tuyến thẳng
  (`axis`+`range`+`speed`, `rect` chỉ khi tâm vòng là chỗ trống — neo recall
  của rect là TÂM vòng) hoặc bỏ. Có `patrol` thì `rotationY` vô nghĩa, đừng
  đặt. Làn patrol né pill tĩnh ≥1 m, không đi giữa cụm nhãn.
- Hướng gốc khi dùng lại shape: Person mũi +X; Signboard mặt +Z;
  RoadSign/TrafficSignal mặt +X; bench/lamppost/hedge theo đúng hướng file
  gốc đã vẽ (ghi trong comment từng scene cũ).
- `focusDistance` đủ gần để đọc thẻ từ; `ringRadius` ôm chân vật.

## 3. Đăng ký type — `src/content/scenes/types.ts` + `index.ts`

- Thêm `ShapeKey` cho từng từ mới (nhóm theo topic, comment như các nhóm cũ),
  thêm `environment` vào union, thêm scene vào `SCENES` trong `index.ts`.
  Thiếu shape nào là `tsc` kêu ở registry — đó là lưới an toàn, đừng né.

## 4. Shapes — `src/components/scenes/scene-shapes-<ten>.tsx`

- Export `<TEN>_SHAPES: Record<ShapeKey, FC>` (registry không mang prop —
  animation đọc mode từ `SceneMotionContext` ở file shapes gốc, không thêm
  prop) + `<Ten>Environment` (đất + bối cảnh). Dùng lại primitive
  `scene-shapes.tsx`: `Box` (gốc CHÂN — chuyển toạ độ vào group chuyển động
  phải trừ từ ĐÁY), `TiltBox`/mesh trần (lấy tâm), `Person` (đã có 2 tay —
  cần tay cầm thì viết thân riêng), `Wheel`, `Cone`, `Signboard` (biển nào
  cũng dùng lại — mặt biển canvas offline, drei `Text` là chờ mạng).
- Dấu xoay/nghiêng TÍNH ra hai đầu mút số, không đoán: `rotation.x` dương
  ngả đỉnh về +Z; Torus sống trong mặt XY (vành trên đất phải xoay X −π/2);
  Cylinder trục Y (mặt đồng hồ/bàn tròn xoay X π/2); arc π mặc định đã là
  nửa trên đứng.
- Lớp phủ mặt nổi tối thiểu 0.02 (dưới là flicker ở xa — gần thì đẹp nên
  mắt thường không thấy, chỉ preview thấy). Đồ trên mặt: đáy lút 0.005,
  không đồng phẳng, không lơ lửng. Đồ trong khay: đỉnh qua miệng khay.
- Kính decor: một `GlassPane` chung + tắt raycast; khung lút vào kính.
  Mũi tên nhãn tắt raycast, dừng ở `topY`, chỉ vẽ ở explore.
- Texture canvas deterministic — cấm `Math.random` (hai lần load hai ảnh
  là preview flake). Mọi cảnh mới đều có biển thương hiệu đặt SAU lưng
  object (trong footprint đất, ngoài footprint hàng xóm, đúng cỡ bối cảnh).
- Nối vào `scene-viewer.tsx`: spread `<TEN>_SHAPES` vào map registry +
  thêm nhánh `environment` cho `<Ten>Environment`.

## 5. Verify (§7.11) — thiếu một là chưa xong

1. `tsc` + `eslint` (React 19: không đọc `.current` trong render, ref tên
   `*Ref`, đọc/ghi chỉ trong `useFrame`).
2. e2e `visual-vocab` — đòi thấy TỪNG object bằng tên, không đếm số lượng.
3. Regen preview: `SCENE_PREVIEWS=1 pnpm exec playwright test
   e2e/scene-previews.spec.ts` (reduced-motion, `?plain=1`, ảnh vào
   `public/scenes/<id>.png` — SẢN PHẨM PHẢI COMMIT).
4. MẮT XEM ẢNH preview: đối chiếu cảnh cũ gần nhất trước khi đoán hỏng/đúng
   (đen không chắc hỏng — urban cũng đen). Ảnh trắng trơn + pill đủ = chụp
   trúng lúc HMR reload, chạy lại, đừng sửa code theo.
5. Chỉ commit ảnh cảnh mới — regen làm lệch ảnh cũ vài trăm byte (nhiễu
   render), revert diff rác.

Xong khi: resolve đủ hotspot bằng tên, bấm được mọi hotspot (kể cả vật
patrol — nhãn `pointer-events-none`, bấm thân), recall đổ đúng
`/vocabulary/{id}/review`, preview mắt-ok đã commit.
