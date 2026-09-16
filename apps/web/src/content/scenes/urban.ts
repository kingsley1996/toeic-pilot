import type { SceneDef } from "@/content/scenes/types";

/**
 * Ngã tư: đại lộ dọc trục X (cong ở đầu tây), đường phụ dọc trục Z, cắt nhau
 * ở gốc. Toạ độ là số thế giới (arm0 trùng trục X nên along = x, across = z).
 * `signal`/biển đứng góc gần tâm chứ không cắm giữa đường như bảng spec.
 */
export const urbanScene: SceneDef = {
  id: "urban-02",
  title: "Ngã tư thành phố",
  description:
    "Ngã tư giao nhau — cầu vượt bên trái, đèn giao thông, biển báo, vỉa hè và người đi bộ qua vạch.",
  topicSlug: "urban-traffic",
  sky: "#dfe7ef",
  environment: "urban-intersection",
  badges: ["new", "beta"],
  home: { pos: [13.5, 11.5, 19.5], look: [0, 1, 0] },
  objects: [
    {
      id: "obj-intersection",
      shape: "intersection",
      headword: "intersection",
      partOfSpeech: "noun",
      position: [0, 0, 0],
      focusDistance: 13,
      hotspotY: 1.4,
      ringRadius: 6.4,
    },
    {
      id: "obj-overpass",
      shape: "overpass",
      headword: "overpass",
      partOfSpeech: "noun",
      // Nửa trái (x = -9), deck ngang đại lộ — trụ (±4) và chân cầu rớt đúng
      // vỉa hè hai bên, không cắm giữa nhựa.
      position: [-9, 0, 0],
      focusDistance: 13,
      hotspotY: 4.9,
      topY: 4,
      ringRadius: 6,
    },
    {
      id: "obj-crosswalk",
      shape: "crosswalk",
      headword: "crosswalk",
      partOfSpeech: "noun",
      // Ngang đại lộ phía đông (x = +5.5). Vạch trang trí trùng ở đây đã gỡ
      // trong `UrbanEnvironment`, không thì hai lớp vạch chồng nhau gây nháy.
      // Nhãn treo CAO (2.6 m): người đi bộ đi qua đúng chân vạch, nhãn thấp là
      // thân người che mất cú bấm (test "mọi hotspot đều bấm được" bắt được).
      position: [5.5, 0, 0],
      focusDistance: 6.5,
      hotspotY: 2.6,
      ringRadius: 4,
    },
    {
      id: "obj-lane",
      shape: "lane",
      headword: "lane",
      partOfSpeech: "noun",
      position: [12, 0, 0],
      focusDistance: 7,
      hotspotY: 0.9,
      ringRadius: 5,
    },
    {
      id: "obj-curb",
      shape: "curb",
      headword: "curb",
      partOfSpeech: "noun",
      position: [7, 0, 3.45],
      focusDistance: 5,
      hotspotY: 0.8,
      ringRadius: 3.4,
    },
    {
      id: "obj-curve",
      shape: "curve",
      headword: "curve",
      partOfSpeech: "noun",
      // Đầu tây, trên đoạn cong (phía gần camera). `CURVE_SEGS` tính toạ độ
      // tương đối từ đúng điểm này — dời def mà không dời OX/OZ bên kia là dải
      // cua lệch khỏi vạch.
      position: [-13, 0, 5.2],
      focusDistance: 9,
      hotspotY: 2.3,
      ringRadius: 5.5,
    },
    {
      id: "obj-sidewalk",
      shape: "sidewalk",
      headword: "sidewalk",
      partOfSpeech: "noun",
      position: [9, 0, 4.7],
      focusDistance: 7,
      hotspotY: 1.6,
      ringRadius: 3.6,
    },
    {
      id: "obj-pavement",
      shape: "pavement",
      headword: "pavement",
      partOfSpeech: "noun",
      position: [-9, 0, -4.7],
      focusDistance: 7,
      hotspotY: 1.4,
      ringRadius: 3.4,
    },
    {
      id: "obj-signal",
      shape: "signal",
      headword: "signal",
      partOfSpeech: "noun",
      // Góc đông-nam gần tâm, mặt quay về tâm (hướng +Z).
      position: [5.6, 0, -3.4],
      rotationY: -Math.PI / 2,
      focusDistance: 5.5,
      hotspotY: 3.7,
      topY: 2.7,
      ringRadius: 1.8,
    },
    {
      id: "obj-road-sign",
      shape: "road-sign",
      headword: "road sign",
      partOfSpeech: "noun",
      // Góc tây-bắc gần tâm, mặt quay RA NGOÀI (đón xe tới) — lộn nửa vòng
      // so với hướng vào tâm.
      position: [-5.6, 0, 3.4],
      rotationY: -Math.PI * 0.75,
      focusDistance: 5,
      hotspotY: 3,
      ringRadius: 1.6,
    },
    {
      id: "obj-lamppost",
      shape: "lamppost",
      headword: "lamppost",
      partOfSpeech: "noun",
      // Một trong ba đèn thành hàng ở mép bắc (z = 4.9).
      position: [5.2, 0, 4.9],
      focusDistance: 8,
      hotspotY: 4.7,
      ringRadius: 2,
    },
    {
      id: "obj-billboard",
      shape: "billboard",
      headword: "billboard",
      partOfSpeech: "noun",
      // Nhãn treo trên mặt bảng: tấm mặt tới 6.3 m sau scale (cao hơn nóc
      // khung 4.7 m), nhãn 5.2 m là lọt giữa mặt chữ.
      position: [11, 0, -5],
      rotationY: 0.1,
      focusDistance: 11,
      hotspotY: 6.8,
      topY: 6.3,
      ringRadius: 5,
    },
    {
      id: "obj-pedestrian",
      shape: "pedestrian",
      headword: "pedestrian",
      partOfSpeech: "noun",
      // Người đi BỘ qua đường trên vạch (giữa vạch, ngang đại lộ). `cross`
      // (động từ) đã bỏ: hai nhãn cho một người đi vừa thừa vừa chồng nhau —
      // từ trong DB giữ nguyên, chỉ mất hotspot như `underpass`.
      position: [5.5, 0, 0],
      patrol: { axis: "z", range: 3, speed: 0.55 },
      focusDistance: 5,
      hotspotY: 1.95,
      ringRadius: 1.2,
    },
  ],
};
