import type { SceneDef } from "@/content/scenes/types";

/**
 * Công trường: đất trống 36 m, móng ở giữa-bắc, cần cẩu tây-bắc, khung nhà
 * đang xây + giàn giáo đông-bắc, xe ủi chạy làn nam, nhà thầu đi tuần quanh
 * móng. Toạ độ tay tính theo lưới (không arm chéo như urban nên không cần
 * helper) — dời object trang trí trong `ConstructionEnvironment` thì kiểm tra
 * lại khoảng cách với object có nhãn gần nhất.
 *
 * `demolish` và `concrete` vẫn published trong topic nhưng không còn hotspot
 * (cùng cách `underpass` ở urban: bỏ object khỏi scene không xoá từ trong DB).
 */
export const constructionScene: SceneDef = {
  id: "construction-03",
  title: "Công trường xây dựng",
  description: "Đất trống đang thi công — cần cẩu, khung nhà đang xây, xe ủi chạy làn nam.",
  topicSlug: "construction",
  sky: "#e6e2d4",
  environment: "construction-site",
  badges: ["new", "beta"],
  home: { pos: [14.5, 11, 20], look: [-1, 1, -1] },
  objects: [
    {
      id: "obj-crane",
      shape: "crane",
      headword: "crane",
      partOfSpeech: "noun",
      position: [-10, 0, -8],
      focusDistance: 14,
      hotspotY: 9.5,
      topY: 10,
      ringRadius: 4,
    },
    {
      id: "obj-scaffold",
      shape: "scaffold",
      headword: "scaffold",
      partOfSpeech: "noun",
      position: [8, 0, -9],
      focusDistance: 8,
      hotspotY: 5.9,
      topY: 4.7,
      ringRadius: 3.5,
    },
    {
      id: "obj-foundation",
      shape: "foundation",
      headword: "foundation",
      partOfSpeech: "noun",
      // Đế 3D khít giữa sân bê tông vẽ trong texture (x −3.6..3.6, z −7..−1).
      position: [0, 0, -4],
      focusDistance: 7,
      hotspotY: 2.5,
      topY: 1.25,
      ringRadius: 4,
    },
    {
      id: "obj-steel-beam",
      shape: "steel-beam",
      headword: "steel beam",
      partOfSpeech: "noun",
      position: [-5, 0, 5.5],
      focusDistance: 5,
      hotspotY: 2.4,
      topY: 1.2,
      ringRadius: 2.8,
    },
    {
      id: "obj-cement",
      shape: "cement",
      headword: "cement",
      partOfSpeech: "noun",
      position: [6.5, 0, -5],
      focusDistance: 4,
      hotspotY: 2,
      topY: 0.75,
      ringRadius: 2,
    },
    {
      id: "obj-concrete-mixer",
      shape: "concrete-mixer",
      headword: "concrete mixer",
      partOfSpeech: "noun",
      position: [11, 0, -3],
      focusDistance: 5.5,
      hotspotY: 3.2,
      topY: 2.1,
      ringRadius: 2.4,
    },
    {
      id: "obj-excavator",
      shape: "excavator",
      headword: "excavator",
      partOfSpeech: "noun",
      // Mặt quay vào tâm (mũi +X mặc định nên lộn nửa vòng).
      position: [11.5, 0, 4],
      rotationY: Math.PI,
      focusDistance: 6,
      hotspotY: 4,
      topY: 2.9,
      ringRadius: 3,
    },
    {
      id: "obj-bulldozer",
      shape: "bulldozer",
      headword: "bulldozer",
      partOfSpeech: "noun",
      // Làn nam (z = 8.5) có vệt bánh vẽ sẵn trong texture — `position` là
      // trung điểm tuyến, cách đống dầm (z = 5.5) 3 m nên không cào vào.
      position: [0, 0, 8.5],
      patrol: { axis: "x", range: 5, speed: 1.2 },
      focusDistance: 5.5,
      hotspotY: 3.5,
      topY: 2.4,
      ringRadius: 2.4,
    },
    {
      id: "obj-ladder",
      shape: "ladder",
      headword: "ladder",
      partOfSpeech: "noun",
      // Tựa mặt TÂY khung nhà (mép sàn x = 5.2): chân đứng x = 4.5, đỉnh lùi
      // đúng 0.7 m chạm mép sàn. Đứng TRƯỚC mặt giàn (x = 5.9 cũ) là lọt giữa
      // cột biên (5.8) và ván (5.7..10.3) — bấm vào thang ăn sang scaffold.
      // `rotationY` −π/2 xoay hướng ngả local −Z thành +X (cùng cách tính urban).
      position: [4.5, 0, -9.5],
      rotationY: -Math.PI / 2,
      focusDistance: 3.5,
      hotspotY: 4.2,
      topY: 3.1,
      ringRadius: 1.4,
    },
    {
      id: "obj-barrier",
      shape: "barrier",
      headword: "barrier",
      partOfSpeech: "noun",
      // Trước hàng rào nam (z = 12) để đọc thành "đoạn rào gần nhất".
      position: [3.5, 0, 10.5],
      focusDistance: 4,
      hotspotY: 2.1,
      topY: 0.95,
      ringRadius: 2,
    },
    {
      id: "obj-hard-hat",
      shape: "hard-hat",
      headword: "hard hat",
      partOfSpeech: "noun",
      position: [-1.5, 0, 2.5],
      focusDistance: 3,
      hotspotY: 2.4,
      topY: 1.3,
      ringRadius: 1.2,
    },
    {
      id: "obj-contractor",
      shape: "contractor",
      headword: "contractor",
      partOfSpeech: "noun",
      // Đi tuần ngang trước móng (x −7.5..−3.5): có `patrol` nên `rotationY`
      // vô nghĩa, hướng do vận tốc quyết định.
      position: [-5.5, 0, -1.5],
      patrol: { axis: "x", range: 2, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.9,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-worker",
      shape: "worker",
      headword: "construction worker",
      partOfSpeech: "noun",
      // Đi làm ngang ở tây-nam (x −8.7..−6.3): tuyến cách tuyến nhà thầu
      // (z = −1.5) đúng 4 m nên hai nhãn chạy không chạm nhau.
      position: [-7.5, 0, 2.5],
      patrol: { axis: "x", range: 1.2, speed: 0.4 },
      focusDistance: 4,
      hotspotY: 2.9,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-weld",
      shape: "weld",
      headword: "weld",
      partOfSpeech: "verb",
      position: [8.5, 0, 7.5],
      focusDistance: 4,
      hotspotY: 2,
      topY: 0.75,
      ringRadius: 1.8,
    },
  ],
};
