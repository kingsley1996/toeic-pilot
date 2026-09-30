---
paths:
  - "apps/web/src/content/scenes/**"
  - "apps/web/src/components/scenes/**"
  - "planning/scenes/**"
---

# Visual vocab 3D scenes

**Tạo hay sửa cảnh 3D thì đọc `planning/docs/SPEC-VISUAL-VOCAB-3D.md` trước —
nhất là §7–§9.** Mọi bẫy hỏng im lặng của các cảnh trước nằm ở đó: đơn vị
canvas, dấu lật dọc, rào/yard vẽ theo footprint số, biển thương hiệu,
camera nhìn theo nhãn chứ không theo đất. Đọc xong vẫn verify như §7.11:
tsc + eslint + e2e visual-vocab + regen preview (`SCENE_PREVIEWS=1`) + mắt
xem ảnh preview.

Tạo cảnh mới từ đầu thì làm theo skill `scene-3d`
(`.claude/skills/scene-3d/SKILL.md`) — quy trình scene file + shapes +
environment + verify, khỏi dò lại từng tệp.
