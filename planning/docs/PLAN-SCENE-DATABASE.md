# PLAN: Chuyển cảnh 3D từ file TS sang database

**Trạng thái:** kế hoạch, chưa làm. **Điều kiện kích hoạt:** số cảnh vượt ~10
hoặc người sửa vị trí object không còn là dev (đúng hai cổng đã ghi trong
`SPEC-VISUAL-VOCAB-3D.md` §5: "Scene trong DB + admin CRUD — người sửa scene
không còn là dev").

Tài liệu này không thay §2.1 của SPEC — nó là đường đi khi §2.1 hết đúng. Chừng
nào còn 4 cảnh do dev sửa bằng code review, file vẫn là đáp án rẻ nhất.

## 0. Cái gì chuyển, cái gì ở lại code vĩnh viễn

| Chuyển vào DB | Ở lại code |
|---|---|
| `SceneDef`: id, title, description, topicSlug, badges, sky, environment key, home | Mọi `ShapeKey` vẽ hình thế nào (registry `Record<ShapeKey, FC>`) |
| `SceneObjectDef`: shape key, (headword, pos), position, patrol, rotationY, scale, focusDistance, focus, hotspotY, topY, ringRadius | Mọi `*Environment` vẽ nền ra sao |
| Trạng thái publish, thứ tự, người sửa + giờ sửa | `SceneViewer`: Mover, CameraRig, mũi tên, recall, chấm điểm |

Nguyên tắc: **DB chứa THAM CHIẾU (key + số), không chứa HÌNH**. Một key lạ trong
DB phải fail closed (banner đỏ như từ resolve hỏng), không crash canvas. Đây là
cùng luật "closed set" của `frontend.md` (badge `icon`, frame `tone`): frontend
phải biết vẽ thì mới cho lưu.

## 1. Vì sao không FK vào `vocabulary_entry`

Cùng lý do file không dùng UUID (§2.3 SPEC): id dev và production là hai vũ điệu
khác nhau. `scene_object` lưu đúng cặp `(headword, part_of_speech)` + `topic_slug`
dạng text, resolve lúc chạy qua `?topic=` như hiện tại. Đổi một headword thì object
đó rớt khỏi cảnh kèm banner — không bao giờ âm thầm mất.

Hệ quả cho sync: topic phải lên production TRƯỚC scene (như audio phải push trước
hàng). Lượt sync sai thứ tự cho ra cảnh thiếu object mà database vẫn xanh.

## 2. Schema (dự kiến)

```sql
scene (
  id uuid PK,                 -- gieo một lần, ổn định hai bên (xem §5)
  slug text UNIQUE NOT NULL,  -- 'warehouse-01' — URL và tên file preview
  title text, description text,
  topic_slug text NOT NULL,   -- không FK: topic có thể tới sau (§1)
  badges text[] DEFAULT '{}', -- CHECK từng phần tử IN ('new','beta')
  sky text NOT NULL,           -- hex, CHECK regex
  environment text NOT NULL,   -- key vào registry, validate ở API (closed set)
  home_pos jsonb, home_look jsonb,  -- [x,y,z] hoặc NULL = mặc định viewer
  status text NOT NULL DEFAULT 'draft',  -- draft | published
  position int NOT NULL,       -- thứ tự ở hub
  updated_by uuid, updated_at timestamptz
);
scene_object (
  scene_id uuid FK scene(id) ON DELETE CASCADE,
  object_id text NOT NULL,    -- 'obj-crane': ổn định để e2e `data-object-id` sống
  shape text NOT NULL,        -- key vào registry, validate ở API
  headword text NOT NULL, part_of_speech text NOT NULL,
  position jsonb NOT NULL,    -- [x,y,z]
  patrol jsonb,               -- NULL hoặc {axis, yaw?, range, speed}
  rotation_y float, scale float,
  focus jsonb,                -- NULL hoặc [x,y,z]
  focus_distance float NOT NULL CHECK (> 0),
  hotspot_y float NOT NULL, top_y float,
  ring_radius float NOT NULL,
  PRIMARY KEY (scene_id, object_id)
);
```

Validate số ở **cả hai tầng**: CHECK ở Postgres (không bao giờ tin client) +
Pydantic ở API (báo lỗi đọc được cho admin). Riêng quân số âm/không-số của
`focus_distance`, `ring_radius` phải CHECK — số 0 ở đây là vòng sáng biến mất
hoặc camera bay vào trong vật, hỏng im lặng.

## 3. Di trú không downtime: DB là override, file là default

Sao chép mẫu `petland_map` (đã trả giá rồi trong `frontend.md`): bảng rỗng nghĩa
là "chưa ai sửa trên web", file TS trong repo tiếp tục chạy. `GET /scenes/:slug`
trả **204 khi chưa có override** — "not configured" là đường bình thường, không
phải lỗi (cùng lý do petland trả 204 chứ không 404).

Thứ tự triển khai:

1. Migration tạo hai bảng (trống) + endpoint đọc (kèm merge fallback file).
2. Script backfill một lần: đọc 4 file TS hiện tại, ghi vào DB dev. Chạy xong
   diff JSON DB vs file phải rỗng — đó là cổng chấp nhận của bước này.
3. Frontend đọc DB trước, rỗng thì dùng file (không đổi hành vi một pixel).
4. Admin CRUD sau cùng. Xoá hàng override = rollback tức thời về file.

Không bao giờ xoá file TS: nó là default, là tài liệu, và là đường sống khi DB
lỗi. Ngày nào không còn ai nhớ vì sao giữ hai bản, đọc lại §3 này.

## 4. Admin UI (làm sau §3, không cùng đợt)

- Danh sách + form số cho từng object (position/patrol/hotspotY…), preview IU
  frame nhúng đúng route scene với `?draft=1` — **không dựng editor kéo-thả 3D**:
  kéo-thả là một dự án con (raycast, gizmo, undo), trong khi chu trình thật là
  "sửa số → nhìn preview → sửa tiếp", và công cụ regen preview (`SCENE_PREVIEWS=1`)
  đã tồn tại.
- Cổng publish từ chối khi: shape/environment key lạ, từ resolve hỏng trong
  topic, clip audio thiếu (hỏi `media_state`, cùng cổng publish từ vựng).
- Quyền `editor` (theo `admin_vocabulary`), không phải `admin` — sửa vị trí là
  quyền biên tập, không phải quyền vận hành (phân biệt đã ghi ở progression).
- Mọi lượt ghi log `updated_by/at`. Không cần bảng history v1: vị trí cũ nằm
  trong file default, vị trí mới nhất nằm trong DB — hai điểm đã đủ rollback.
  History từng số là v2, khi nào mất vị trí đẹp vì ghi đè mới trả giá.

## 5. Sync dev → production

Cùng đường `dump_learning_content.py` (§5b `SYNC-TEST-TO-PRODUCTION.md`):
thêm `scene` + `scene_object` vào danh sách bảng, `ON CONFLICT DO UPDATE`.
UUID gieo một lần bằng backfill (§3.2) rồi giữ nguyên hai bên — **tuyệt đối
không regenerate id**, vì `scene_object.scene_id` và mọi link ngoài (preview,
e2e `data-object-id` là `object_id` text nên miễn nhiễm) ăn theo id đó.

Diễn tập 3 bước như lệ (schema → prod state → áp), đếm lại số scene/object.

## 6. Frontend refactor (nhỏ, theo sau backend)

- `getScene(slug)` thành async: fetch `/scenes/:slug`, 204 thì import file
  cùng slug (dynamic import giữ `three` khỏi các route khác — đừng import tĩnh
  cả 4 file vào hub).
- `SceneDef` của TS tiếp tục là kiểu dùng trong viewer; Pydantic là truth của
  API; contract test pin hai bên bằng nhau (cùng mẫu `api-types`).
- e2e không đổi một dòng: nó đọc `SCENES`… — SAI, nó phải đọc từ API. Viết lại
  vòng lặp hotspot-test lấy danh sách object từ response thay vì import file,
  nếu không test đang giữ bất biến cho code chứ không cho dữ liệu. Đây là việc
  dễ quên nhất cả kế hoạch.

## 7. Không làm (và điều gì kích hoạt)

| Không | Khi nào mới làm |
|---|---|
| Editor kéo-thả 3D trong admin | Sửa số + preview thành nút cổ chai đo được (đếm vòng lặp/sửa) |
| AI Scene Planner (sinh toạ độ bằng prompt) | SPEC §5 đã ghi: viết tay chậm hơn viết prompt — nay 4 cảnh, chưa tới |
| Geometry/shape trong DB | Không bao giờ: đó là code, lưu vào DB là mất typecheck + review |
| Xoá file TS | Không bao giờ (§3) |
| Scene versioning đầy đủ | Khi mất vị trí đẹp vì ghi đè (lúc đó mới có case) |

## 8. Rủi ro hỏng im lặng (đọc khi implement)

1. **Key lạ trong DB.** Shape deploy sau content sync → cảnh thiếu object mà
   không lỗi. Publish gate (§4) chặn ở lối vào; fallback file KHÔNG che được
   vì row tồn tại (override thắng default cả khi thiếu key — fail closed đúng
   nghĩa: banner, không object).
2. **Topic tới sau scene.** Object resolve hỏng hàng loạt, banner đỏ cả cảnh.
   Sync order: topic (+ audio push) trước, scene sau (§1).
3. **Số âm/không-số.** `focus_distance = 0` bay camera vào trong vật;
   `ring_radius = 0` mất vòng sáng; `patrol.range = 0` đứng yên nhưng vẫn mất
   `rotationY` (Mover bỏ qua) → vật quay mặt sai vĩnh viễn. CHECK ở DB (§2).
4. **Preview lệch DB.** Ảnh `public/scenes/*.png` commit theo file; khi scene
   sống bằng DB, regen phải đọc từ API dev (kèm `?draft=1` nếu cần), không đọc
   file nữa — nếu không ảnh là của một cảnh không còn tồn tại.
5. **e2e giữ file.** §6: test phải đọc API, không import `SCENES`.
