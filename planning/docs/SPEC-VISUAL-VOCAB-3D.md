# SPEC: Visual Vocab 3D — bản dựng MVP

Nguồn cảm hứng: [`visual_vocabulary_3d_specification.md`](visual_vocabulary_3d_specification.md)
(bản proposal, giữ nguyên — tệp này thu gọn nó thành cái dựng được). Đây là **mặc định
dựng để sửa**, không phải cam kết kiến trúc.

## 0. Một câu về phạm vi

MVP = MỘT cảnh 3D ("Road & Traffic", ~8–10 từ) với Explore + Learn + Recall, chấm điểm
thẳng vào SM-2 đã có. Backend **không đổi một dòng nào**.

## 1. Đã có sẵn — dùng lại, đừng dựng lại

| Spec gọi nó là | Trong repo là |
|---|---|
| Vocabulary DB (§4.2) | `GET /api/v1/vocabulary/{entry_id}` → `VocabularyDetail`: headword, phonetic (IPA), meaning_vi/en, example, audio 4 accents (`AudioClip[]`, URL public sẵn) |
| SRS Engine (Level 6) | `POST /api/v1/vocabulary/{entry_id}/review` + `app/services/srs.py` (grades 0/3/4/5/6) |
| Danh sách từ của chủ đề | `GET /api/v1/vocabulary?topic=<slug>&limit=200` |
| Bottom sheet / audio button | `audio-button.tsx`, khuôn thẻ trong `learn/vocabulary/` |

`CollocationDetail`, XP, ruby — tất cả đi theo `/review` một cách miễn phí vì đó là cùng
một engine học viên vẫn dùng ở thẻ lật.

## 2. Quyết định của bản dựng

1. **Scene là file tĩnh trong repo, không phải database.** `apps/web/src/content/scenes/road-traffic.ts`,
   typed bằng `satisfies SceneDef`. Vị trí object là thứ phải *nhìn mà chỉnh* — vòng đời
   của nó là code review + deploy, không phải admin CRUD. Bảng DB + endpoint + màn admin
   là ba tầng hạ tầng cho một tệp thay đổi vài lần mỗi năm.
2. **`modelPath` → `shape`.** Không có `.glb`, không có Draco, không có pipeline asset.
   8–12 vật dựng từ three primitives qua registry `const shapes: Record<ShapeKey, FC>`:
   pothole = cylinder dẹt tối màu, cone = `ConeGeometry`, taxi = hai box bo góc… Tên miền
   vấn đề (đường sá, đồ vật) rất hợp low-poly hình học. Khi một key trong registry xấu
   đến mức người học nhận ra, ĐÓ là lúc thay nó bằng GLB đơn lẻ — schema scene không đổi.
   (License từng là lý do cả một ADR-004; primitive không có vấn đề đó.)
3. **Ràng buộc từ vựng bằng (headword, partOfSpeech) + topic slug, không bằng UUID.**
   UUID dev và production là hai vũ điệu khác nhau; scene file commit vào repo thì phải
   chạy được trên cả hai. Trang học resolve bằng một call `?topic=<slug>&limit=200` rồi
   map client-side. `headword` KHÔNG duy nhất (khoá thật là cặp với pos) — cả hai trường
   đều bắt buộc. Từ resolve hỏng → banner đỏ ngay trên trang, không âm thầm ẩn hotspot.
4. **Không Zustand, không GSAP.** State của một trang là `useState`/`useRef`; repo không
   có global store nào và camera lerp ăn damping của drei (`OrbitControls` + `useFrame`).
5. **Canvas là client-only**: `next/dynamic` với `ssr: false`. Deps: `three`,
   `@react-three/fiber@^9.7` (React 19), `@react-three/drei@^10.7`.
6. **Cửa đăng nhập y hệt từ vựng**: `useRequireSession` + `LoginModal` ở danh sách, vì
   lý do cũ đã ghi ở `frontend.md` — SM-2 progress *là* tính năng, không phải phần thưởng
   kèm theo.
7. **Chấm điểm Recall qua hai grade duy nhất**: click đúng = `4` (Good), click sai = `0`
   (Forgot) rồi cho bấm lại. Không tự chế thang điểm riêng — bài học từ
   `AI-ENGINEERING-PLAN.md` §2: chấm điểm không bao giờ chạm LLM, và ở đây nó cũng không
   cần chạm thêm code nào.

## 3. Vòng học của MVP

Ba chế độ trên MỘT cảnh (đường dọc 1→3→4→6 của spec gốc):

- **Explore (L2)**: hotspot `Html` của drei trên mỗi object; click → camera bay tới
  `cameraFocus` (lerp) + bottom sheet (L3) với IPA/audio/nghĩa/ví dụ, nút "Đã thuộc"
  = grade 6 qua `/review` đã có.
- **Recall (L4)**: ẩn hết label, banner "Find: pothole", click object → outline
  xanh/đỏ + gọi `/review`. Hết danh sách thì hiện tổng.
- **Level 1 (cinematic pan), Level 5 (điền câu), Level 6 tự động**: L5 về bản chất đã là
  quiz Part 5/collocation đang tồn tại — không dựng trùng. L1 là mỹ phẩm. L6 miễn phí
  vì mọi chấm điểm đã đi thẳng vào SRS.

## 4. Các bước dựng (thứ tự phụ thuộc)

- [x] **W1. Deps + skeleton trang**: `pnpm --filter @toeic-pilot/web add three @react-three/fiber @react-three/drei`
  (nhớ `up -d --build` — bẫy package.json-vs-lock trong CLAUDE.md). Route
  `/learn/scenes`, `/learn/scenes/[sceneId]`, dynamic import, Canvas rỗng + lights theo
  `environment` của scene file.
- [x] **W2. types + registry shapes**: `SceneDef`/`SceneObject` (TS, colocated với
  scenes), `ShapeKey` union, 8–12 hình từ primitives, vật được chọn đúng khi click
  (raycast lên group, không mesh con).
- [x] **W3. Explore + Learn**: hotspot, camera lerp có damping, bottom sheet nối
  `GET /vocabulary/{entry_id}` + `audio-button`, nút Mastered.
- [x] **W4. Recall**: chế độ quiz, outline đúng/sai (drei `Outlines`), chuỗi `/review`,
  tổng kết cuối lượt.
- [x] **W5. Scene content + a11y**: `road-traffic.ts` với 8–10 từ đã có trong kho
  (chọn theo topic Transportation sẵn có — **không** tạo entry mới, đừng vì một cảnh
  mà nhập tay từ vựng chưa qua đường ống import), `<details>` liệt kê toàn bộ từ cho
  screen reader (§8.3 spec gốc), thẻ scene ở hub học.
- [x] **W6. Smoke e2e**: `e2e/visual-vocab.spec.ts` — mở cảnh, bấm hotspot ra sheet,
  Recall click đúng giảm due-count. Lưu ý đã ghi ở `frontend.md`: assertion phủ định
  cần anchor, đừng `toHaveCount(0)` trần.

## 5. Scope-out — và điều gì kích hoạt dựng nó

| Bỏ | Thêm khi |
|---|---|
| AI Scene Planner (§5 spec gốc) | Có scene thứ 3 trở đi mà việc viết tay toạ độ bắt đầu chậm hơn viết prompt |
| GLB + Draco + budget 150KB | Một `shape` primitive lộ rõ giới hạn trước mắt người học |
| Scene trong DB + admin CRUD | Người sửa scene không còn là dev — editor cần tự chỉnh vị trí object |
| Scene thứ hai trở lên | Cảnh đầu có người học thật; chủ đề tiếp theo chọn theo feedback, không đoán |
| Service Worker cache assets | Bao giờ có GLB thì hãy nói tới cache — hiện asset nằm trong bundle, browser cache sẵn |
| Level 5 điền câu | Nó đã tồn tại dưới dạng quiz collocation/Part 5 |

## 6. Rủi ro đã biết

- **Bundle**: `three` ~150KB gzip vào chunk của riêng route — dynamic import giữ nó khỏi
  mọi trang khác; đừng import ở hub list.
- **Turbopack dev + three**: nếu dev server gặp vấn đề với R3F, fallback là `next build`
  + `start` để dựng, không downgrade engine.
- **Mobile fps (§8.2)**: low-poly primitives không có cửa sập dưới 45fps; nếu sập thì
  lỗi là `Html` hotspots (DOM overlay), hướng sửa là `Billboard` + sprite thay vì thêm config.

## 7. Bài học dựng cảnh (urban-02, 2026-09) — đọc trước khi làm cảnh 3

1. **Đơn vị canvas**: `lineWidth`/`setLineDash` tính bằng user-unit (mét), transform tự
   scale ra pixel. Nhân thừa `PX_PER_M` là mọi vạch nở 64 lần, phủ kín canvas, nét cuối
   thắng hết — vẫn ra hình nên hỏng im lặng (comment cảnh báo ở `useStreetPlan`).
2. **Canvas lật dọc**: flipY + plane xoay −90° ⇒ world z = −(draw y). Chi tiết BẤT ĐỐI
   XỨNG (khúc cong) phải tính dấu bằng số, không đoán bằng mắt.
3. **HMR giữ `useMemo`**: texture đất memo rỗng — sửa file mà tab cũ không đổi hình.
   Verify visual bằng marker test (đổi 1 màu → chụp → revert), hoặc restart container +
   hard-refresh tab. Đừng tin mắt thường sau khi sửa texture.
4. **Vị trí tính bằng số**: script node kiểm chứng trước khi sửa (vật ở đâu, cách nhau
   bao xa: `armPoint` + nghịch đảo của nó). Quy ước hiện tại: arm0 = trục X, arm1 = trục Z.
5. **Nhãn**: prop `pointerEvents` của drei `Html` chỉ ăn ở chế độ `transform` — chống nhãn
   đè nhãn bằng bố cục (`position`/`hotspotY`), không bằng prop. Vật chạy (`patrol`): nhãn
   `pointer-events-none`, bấm vào thân; test miễn thị có chủ ý. Nhãn của vật chuyển động
   phải treo cao hơn thân vật — test "mọi hotspot đều bấm được" giữ bất biến này.
6. **`Mover`**: `patrol.yaw` phải xoay tuyến (từng bị bỏ qua → xe cắt qua vỉa hè). Vật có
   `patrol` thì `rotationY` của def vô nghĩa — hướng do vận tốc quyết định.
7. **Mũi tên nhãn**: nét đứt, dừng ở mặt vật (`topY`), không xuyên xuống đất; chỉ vẽ ở
   explore (recall là lộ đáp án); tắt `raycast` để không nuốt click.
8. **Hướng mặc định của shape**: Person mũi +X; Signboard mặt +Z; RoadSign/TrafficSignal
   mặt +X — tính `rotationY` từ hướng cần quay rồi xem ảnh xác nhận. Ghế: lưng ở sau
   người ngồi, kiểm tra mặt ngồi quay về đâu.
9. **Decor ≠ từ vựng**: xe nền, cửa/vạch/đèn thừa không nhãn, không vào bảng từ. Bỏ object
   khỏi scene không xoá từ trong DB (recall chỉ hỏi object còn lại).
10. **Ràng buộc cặp**: `CURVE_SEGS` (OX/OZ) với def position; Overpass tự xoay trong
    component (def không đặt `rotationY`); đổi `ARMS.yaw` là đảo góc/cửa cũ nằm giữa đường.
11. **Verify**: tsc + eslint (React 19: không đọc `.current` trong render, ref đặt tên
    `*Ref`, đọc/ghi chỉ trong `useFrame`) + e2e visual-vocab + regen preview
    (`SCENE_PREVIEWS=1`) + MẮT XEM ẢNH preview. Snapshot với nhãn chuyển động có thể flake
    một lần: chạy lại 2–3 lần trước khi kết luận.

## 8. Bài học cảnh 3 (construction-03, 2026-09)

1. **`Box` lấy gốc chân, không lấy tâm.** Chuyển toạ độ tĩnh vào nhóm chuyển động
   (xe con cần cẩu) phải trừ gốc nhóm khỏi ĐÁY — trừ nhầm tâm là cả chùm cáp/móc
   lơ lửng xuyên qua cần, vẫn ra hình nên hỏng im lặng. `TiltBox` (mesh trần) thì
   ngược lại: `position` của nó là tâm.
2. **Dấu nghiêng phải tính, không đoán.** `rotation.x` dương ngả đỉnh về +Z (ra
   ngoài); tựa vào khung ở −Z phải là âm. Cùng họ với bẫy lật dọc §7.2: thang
   "trông vẫn là thang" nên sai dấu không ai thấy cho tới khi đặt cạnh khung.
3. **Vật nằm trong footprint hàng xóm là bấm nhầm hàng xóm.** Thang đứng x = 5.9,
   lọt giữa cột biên giàn (5.8) và ván (5.7..10.3) — raycast ăn mesh scaffold.
   Kiểm footprint bằng số trước khi đặt; vật tựa khung thuộc về MẶT NGOÀI khung.
4. **Mũi tên nằm trên vật, không xuyên qua.** Gỡ `topY` để "lấy mũi tên" là sai
   hướng: thiếu nó, sợi vẽ từ nhãn xuống đất và xuyên qua thân vật (warehouse
   vẫn thế). Đúng là `topY` thật + nhãn nổi lên trên (mẫu crosswalk urban §7.5).
5. **Animation trong shape phải đọc mode từ context.** Registry
   `Record<ShapeKey, FC>` không mang prop — đổi nó là đụng mọi shape. Thêm
   `SceneMotionContext` ở file shapes gốc (khỏi import vòng), `SceneObject`
   cung cấp đúng cờ `animated` của `Mover`: recall/chọn/reduced-motion đứng yên
   mà shape không tự bịa cờ riêng.
6. **Đổi tên từ = từ mới.** Sửa headword làm audio cũ lệch hash im lặng
   (`frontend.md`); scene muốn chữ khác thì nhập entry mới + audio mới, từ cũ ở
   lại published không hotspot (tiền lệ `underpass`). `concrete` → `concrete mixer`.
7. **Texture phải deterministic.** Không `Math.random` trong canvas nền — hai lần
   load ra hai ảnh khác nhau thì preview flake mà không có gì sai.
8. **`push_media --prefix audio` verify cả 11k file rồi mới đẩy.** Treo quá
   timeout mà không in một dòng (stdout nằm trong buffer). Đẩy theo keys của
   topic (lọc từ DB, gọi `push()` trực tiếp): 112 keys xong trong vài phút.
