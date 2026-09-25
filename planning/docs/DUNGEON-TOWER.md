# Tháp Dungeon — leo 100 tầng, đánh theo lượt bằng câu hỏi (spec)

Pha hiện tại: leo tháp 100 tầng. Quái random từ sheet `myth` có sẵn.
Vào tháp qua một cổng đặt trên map chính. Editor quản nhiều map theo `slug`.

## Luật tái dùng (không dựng bộ máy thứ hai)

- Mỗi lượt đánh = một bước của `Encounter` kind=`dungeon`. Đúng → `steps_done+1`
  (pet chém, tái dùng animation `fight`); sai/`give_up` → quái chém (pet mất HP).
  Hết bước = hết tầng. SM-2, ruby, XP đi qua đúng đường encounter cũ.
- Máy chủ KHÔNG biết sprite: mặt quái do client chọn từ sheet myth theo seed
  `battle_id` (cùng lý do `encounter.py` đã ghi: server không đọc map/sprite).
- Map tầng sinh ở CLIENT, deterministic theo seed = số tầng (server không biết
  chỉ số ô đá; bảng `solid` đi kèm layout sinh ra, không qua validator save-map).

## Số (services/dungeon.py là nguồn sự thật duy nhất)

- `MAX_FLOOR = 100`
- `MONSTER_HP(f) = 3 + f // 10` → tầng 1: 3 câu, tầng 100: 13 câu
- `MONSTER_DMG(f) = 2 + f // 15` → 2..8
- `PET_MAX_HP(level) = 20 + 2 * level`
- `HEAL_PER_CLEAR = 6` (không quá max), `BATTLE_LIFE = 24h`
- `reward_ruby = 10 + floor // 5`, XP = `10 + floor // 2`
- Checkpoint mỗi 10 tầng: chết → quay về `checkpoint`, HP đầy, battle mới.

## DB (3 migration việc nhỏ)

1. `petland_map` khoá theo `slug` (thay `CHECK id=1`): backfill hàng cũ
   `slug='main'`; thêm `portal_x/portal_y NULL` (cổng vào tháp, optional,
   phải trong biên + đi được — kiểm ở Pydantic).
2. `ck_encounter_kind` thêm `'dungeon'`. `sync()` vẫn bỏ qua kind này
   (không nhịp hẹn, không trần, không hiện ở map chính).
3. Bảng `dungeon_run`: `user_id` PK/FK cascade, `floor`, `checkpoint`,
   `pet_hp`, `status` (`fighting|dead|done`), `battle_id` UUID nullable
   (không FK, cùng lý do `target_id`), `updated_at`.

## API

- `GET /petland/map/{slug}` / `PUT /admin/petland/map/{slug}` /
  `GET /admin/petland/maps` (+ `DELETE`); `GET /petland/map` cũ = slug `main`.
- `GET /dungeon/state` → `{run, battle: EncounterPublic|null}`; tự tạo run,
  tự mở battle mới khi chưa có (battle hết hạn 24h → mở lại cùng tầng,
  không phạt).
- `POST /dungeon/retry` (chết → về checkpoint), battle thắng tầng 100
  → `status=done`.
- `POST /pet/encounters/{id}/answer` móc thêm nhánh `kind == "dungeon"`:
  sai → trừ HP + kiểm chết; đúng-xong → sang tầng (checkpoint/heal/thưởng);
  `EncounterResult.dungeon: DungeonView | null`, `EncounterPublic.kind`
  thêm `"dungeon"` → regen contract.

## Web (pha sau)

- `/dungeon`: layout tầng deterministic (đá stone), quái myth theo seed battle,
  tái dùng `createStage` + `QuestCard` + animation fight, thanh HP, nút rời tháp.
- Map chính: đứng lên ô `portal` → hỏi "Vào tháp?" → sang `/dungeon`.
- `/admin/petland`: chọn slug, tạo map, tool đặt cổng.
