import type { SceneDef } from "@/content/scenes/types";

/**
 * Phòng đọc (topic `positions`, 24 từ: 10 preposition + 4 phrase đợt 1,
 * thêm 5 preposition + 2 phrase + 1 verb + 1 adverb + 1 preposition đợt 2 —
 * toàn bộ là từ chỉ vị trí tương đối, câu trả lời đúng của Part 1 dạng
 * "A [noun] is [prep] the [noun]").
 *
 * Mỗi object là một tiểu cảnh diễn đúng quan hệ đó (bàn + sách cho `on`,
 * ghế dài + thùng cho `under`...), hotspot mang tên giới từ. Phòng tĩnh,
 * không patrol. Mũi tên nào cũng dư 0.05 trên 0.8 (§9.9).
 *
 * Bố cục: tường bắc (cửa sổ + kệ `below`, giá sách `against`, bàn + tủ
 * `behind`, thùng chồng `on top of`) → cánh tây (`on`, `under`, `above`)
 * → giữa phòng (`around`, `between`, `in the middle of`) → nam/đông
 * (`beside`, `in front of`, `across from`, `near`). Cặp gần nhất ≥ 4 m.
 */
export const positionsScene: SceneDef = {
  id: "positions-room-01",
  title: "Vị trí đồ vật",
  description:
    "Căn phòng đọc đầy đủ đồ đạc — sách trên bàn, thùng dưới ghế, tranh trên sofa: học giới từ chỉ vị trí qua đúng cảnh Part 1 hay hỏi.",
  topicSlug: "positions",
  sky: "#dfe6ea",
  environment: "positions-room",
  // Đông-nam trên cao nhìn chếch tây-bắc: cả 4 tường lọt khung mà tường bắc
  // (xa nhất, 4 nhãn) không dồn pill (§10.1).
  home: { pos: [9, 10, 20], look: [-1.5, 1, -2] },
  badges: ["new", "beta"],
  objects: [
    {
      id: "obj-on",
      shape: "pos-book-on-table",
      headword: "on",
      partOfSpeech: "preposition",
      // Bàn phụ + chồng sách trên mặt (đỉnh 0.71).
      position: [-10, 0, -3],
      focusDistance: 4,
      hotspotY: 1.6,
      topY: 0.71,
      ringRadius: 1.2,
    },
    {
      id: "obj-under",
      shape: "pos-crate-under-bench",
      headword: "under",
      partOfSpeech: "preposition",
      // Thùng lút dưới gầm ghế dài (mặt ghế đỉnh 0.55).
      position: [-10, 0, 1.5],
      focusDistance: 4,
      hotspotY: 1.45,
      topY: 0.55,
      ringRadius: 1.4,
    },
    {
      id: "obj-above",
      shape: "pos-painting-above-sofa",
      headword: "above",
      partOfSpeech: "preposition",
      // Sofa tựa tường tây + tranh treo trên tường (khung tới 2.5).
      position: [-10.5, 0, 6],
      focusDistance: 4.5,
      hotspotY: 3.4,
      topY: 2.5,
      ringRadius: 1.8,
    },
    {
      id: "obj-below",
      shape: "pos-shelf-below-window",
      headword: "below",
      partOfSpeech: "preposition",
      // Kệ sách gắn dưới cửa sổ tường bắc (khung cửa tới 2.5).
      position: [-7, 0, -8.2],
      focusDistance: 4.5,
      hotspotY: 3.4,
      topY: 2.5,
      ringRadius: 1.6,
    },
    {
      id: "obj-beside",
      shape: "pos-plant-beside-chair",
      headword: "beside",
      partOfSpeech: "preposition",
      // Ghế đôi + chậu cây đặt cạnh bên (đỉnh ghế 1.0).
      position: [4, 0, 5.5],
      focusDistance: 4.5,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 1.8,
    },
    {
      id: "obj-between",
      shape: "pos-plant-between-chairs",
      headword: "between",
      partOfSpeech: "preposition",
      // Chậu cây ở giữa hai ghế bành (đỉnh ghế 1.0).
      position: [4.5, 0, -0.5],
      focusDistance: 4.5,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 2.2,
    },
    {
      id: "obj-behind",
      shape: "pos-cabinet-behind-desk",
      headword: "behind",
      partOfSpeech: "preposition",
      // Tủ đứng sau bàn làm việc (nóc tủ 1.1).
      position: [5.5, 0, -6.5],
      focusDistance: 5,
      hotspotY: 2.0,
      topY: 1.1,
      ringRadius: 2.2,
    },
    {
      id: "obj-in-front-of",
      shape: "pos-mat-in-front-of-door",
      headword: "in front of",
      partOfSpeech: "phrase",
      // Thảm chùi trước cửa đông (khung cửa tới 2.5). Dời lên z 0.5 cho
      // hở sofa across-from (cách ~5 m thay vì 3 m).
      position: [10.2, 0, 0.5],
      focusDistance: 4.5,
      hotspotY: 3.4,
      topY: 2.5,
      ringRadius: 1.6,
    },
    {
      id: "obj-across-from",
      shape: "pos-sofa-across-from-tv",
      headword: "across from",
      partOfSpeech: "phrase",
      // Sofa nhìn nam, TV đối diện qua khoảng trống (đỉnh TV 1.45).
      position: [8.5, 0, 6.5],
      focusDistance: 5,
      hotspotY: 2.35,
      topY: 1.45,
      ringRadius: 2.4,
    },
    {
      id: "obj-against",
      shape: "pos-shelf-against-wall",
      headword: "against",
      partOfSpeech: "preposition",
      // Giá sách cao dựa tường bắc (nóc 2.2).
      position: [-1, 0, -8.2],
      focusDistance: 4.5,
      hotspotY: 3.1,
      topY: 2.2,
      ringRadius: 1.6,
    },
    {
      id: "obj-around",
      shape: "pos-chairs-around-table",
      headword: "around",
      partOfSpeech: "preposition",
      // 4 ghế xếp xung quanh bàn tròn (lưng ghế đỉnh 1.0).
      position: [-2, 0, 0],
      focusDistance: 5.5,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 2.6,
    },
    {
      id: "obj-on-top-of",
      shape: "pos-crates-on-top-of-each-other",
      headword: "on top of",
      partOfSpeech: "phrase",
      // 3 thùng xếp chồng lên nhau (nóc 1.8).
      position: [10.5, 0, -6.5],
      focusDistance: 4,
      hotspotY: 2.7,
      topY: 1.8,
      ringRadius: 1.4,
    },
    {
      id: "obj-near",
      shape: "pos-stand-near-door",
      headword: "near",
      partOfSpeech: "preposition",
      // Giá treo áo đặt gần cửa nam (khung cửa tới 2.5).
      position: [-6.5, 0, 7.8],
      focusDistance: 4.5,
      hotspotY: 3.4,
      topY: 2.5,
      ringRadius: 1.8,
    },
    {
      id: "obj-in-the-middle-of",
      shape: "pos-rug-in-middle-of-room",
      headword: "in the middle of",
      partOfSpeech: "phrase",
      // Thảm tròn + bàn thấp giữa khoảng trống (mặt bàn 0.4).
      position: [-2.5, 0, 5.5],
      focusDistance: 4.5,
      hotspotY: 1.3,
      topY: 0.4,
      ringRadius: 2.0,
    },
    {
      id: "obj-next-to",
      shape: "pos-chair-next-to-table",
      headword: "next to",
      partOfSpeech: "phrase",
      // Ghế sát cạnh bàn phụ, cách 0.275 m (gần mà không chạm — khác adjacent).
      position: [-6, 0, 3],
      focusDistance: 4,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 1.4,
    },
    {
      id: "obj-underneath",
      shape: "pos-slippers-under-bed",
      headword: "underneath",
      partOfSpeech: "preposition",
      // Dép thò ra khỏi gầm giường (nệm đỉnh 0.615, gối 0.76).
      position: [2, 0, -4],
      focusDistance: 4.5,
      hotspotY: 1.7,
      topY: 0.8,
      ringRadius: 2.2,
    },
    {
      id: "obj-opposite",
      shape: "pos-chairs-opposite",
      headword: "opposite",
      partOfSpeech: "preposition",
      // Hai ghế bành quay mặt vào nhau (đỉnh lưng 1.0).
      position: [1.5, 0, 2.5],
      focusDistance: 4.5,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 2.2,
    },
    {
      id: "obj-adjacent-to",
      shape: "pos-cabinet-adjacent-desk",
      headword: "adjacent to",
      partOfSpeech: "phrase",
      // Tủ chạm mép bàn, khe hở 0 (nóc tủ 1.1).
      position: [1.3, 0, 7.5],
      focusDistance: 4.5,
      hotspotY: 2.0,
      topY: 1.1,
      ringRadius: 2.2,
    },
    {
      id: "obj-along",
      shape: "pos-books-along-shelf",
      headword: "along",
      partOfSpeech: "preposition",
      // Dãy sách dọc kệ thấp (ngọn cây chặn đầu 0.955).
      position: [-3.5, 0, -5],
      focusDistance: 4.5,
      hotspotY: 1.85,
      topY: 0.96,
      ringRadius: 2.0,
    },
    {
      id: "obj-alongside",
      shape: "pos-chairs-alongside-table",
      headword: "alongside",
      partOfSpeech: "preposition",
      // Hai ghế cùng một bên bàn dài (lưng ghế đỉnh 1.0).
      position: [6.5, 0, 2.5],
      focusDistance: 5,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 2.4,
    },
    {
      id: "obj-facing",
      shape: "pos-chair-facing-bookcase",
      headword: "facing",
      partOfSpeech: "verb",
      // Ghế nhìn đông về tủ sách thấp (cách 1 m, đỉnh ghế 1.0).
      position: [-6.5, 0, -1],
      focusDistance: 4.5,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 2.2,
    },
    {
      id: "obj-upstairs",
      shape: "pos-stairs-upstairs",
      headword: "upstairs",
      partOfSpeech: "adverb",
      // Cầu thang leo về đông + lan can (thanh chéo tới 2.84).
      position: [8.5, 0, -2.5],
      focusDistance: 5.5,
      hotspotY: 3.75,
      topY: 2.85,
      ringRadius: 2.4,
    },
    {
      id: "obj-inside",
      shape: "pos-vase-inside-cabinet",
      headword: "inside",
      partOfSpeech: "preposition",
      // Bình trên đợt giữa tủ mở cửa (nóc tủ 1.1).
      position: [-10.5, 0, -6.5],
      focusDistance: 4,
      hotspotY: 2.0,
      topY: 1.1,
      ringRadius: 1.6,
    },
    {
      id: "obj-outside",
      shape: "pos-flowerbed-outside-fence",
      headword: "outside",
      partOfSpeech: "preposition",
      // Luống hoa phía ngoài hàng rào (đỉnh trụ 1.0).
      position: [10.8, 0, 3.5],
      focusDistance: 4.5,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 2.0,
    },
  ],
};
