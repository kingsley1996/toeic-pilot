---
paths:
  - "apps/web/src/content/scenes/**"
  - "apps/web/src/components/scene-*.tsx"
  - "planning/scenes/**"
---

# Visual vocab 3D scenes

**Tạo hay sửa cảnh 3D thì đọc `planning/docs/SPEC-VISUAL-VOCAB-3D.md` trước —
nhất là §7–§9.** Mọi bẫy hỏng im lặng của các cảnh trước nằm ở đó: đơn vị
canvas, dấu lật dọc, rào/yard vẽ theo footprint số, biển thương hiệu,
camera nhìn theo nhãn chứ không theo đất. Đọc xong vẫn verify như §7.11:
tsc + eslint + e2e visual-vocab + regen preview (`SCENE_PREVIEWS=1`) + mắt
xem ảnh preview.
