import type { SceneDef } from "@/content/scenes/types";

/**
 * Nhà ngoại ô + vườn (`planning/scenes/residential-house-garden-3d-scene-spec.md`).
 * Nhà ở [-6, 0, -8], mặt trước +Z. Thân tường là decor trong
 * `ResidenceEnvironment`; mọi object gắn nhà (mái, ban công, cửa…) đặt KHỚP
 * mặt tường, dời nhà là dời cả cụm — không object nào đứng riêng.
 *
 * Nhãn nổi lên trên + `topY` thật để mũi tên nằm trọn trong không khí (quy ước
 * từ construction). Hai object trải dài (eaves/gutter) đặt gốc nhóm ở ĐẦU có
 * nhãn, thân trải về phía còn lại của mặt nhà.
 */
export const residenceScene: SceneDef = {
  id: "residential-yard-01",
  title: "Nhà ngoại ô và vườn",
  description:
    "Ngôi nhà hai tầng giữa khu vườn xanh — mái ngói, ban công rộng và người đang cắt cỏ quanh sân.",
  topicSlug: "residential",
  sky: "#dce9f2",
  environment: "residential-yard",
  badges: ["new", "beta"],
  // Nhìn CHÍNH NAM hơi từ trên: mặt nhà trải ngang, nhãn mái xếp tầng trên
  // nhãn tường theo cao độ — góc chéo đông-nam dồn cả hai lớp thành một đống
  // (e2e "mọi hotspot đều bấm được" bắt được, 8 cái kẹt). Lùi ra 32 m: hàng
  // mặt nhà cần ~100px/khe mà ở 28 m chỉ có ~70px.
  home: { pos: [3, 14.5, 26], look: [-3, 2, -3] },
  objects: [
    {
      id: "obj-roof",
      shape: "roof",
      headword: "roof",
      partOfSpeech: "noun",
      // Giữa nóc (shape đối xứng quanh gốc — dời def là dời cả mái lệch tường).
      // Nhãn ôm sống nóc (không mũi tên) cho khỏi chen chimney/weathervane.
      position: [-6, 0, -8],
      focusDistance: 13,
      hotspotY: 8,
      topY: 7.7,
      ringRadius: 6,
    },
    {
      id: "obj-tile",
      shape: "tile",
      headword: "tile",
      partOfSpeech: "noun",
      // Ngói dự trữ sau nhà phía đông (cạnh nào ở tây cũng chen nhãn khác).
      position: [9, 0, -11],
      focusDistance: 4,
      hotspotY: 2,
      topY: 0.9,
      ringRadius: 1.6,
    },
    {
      id: "obj-chimney",
      shape: "chimney",
      headword: "chimney",
      partOfSpeech: "noun",
      // Chân chôn trong dốc sau (shape mang cao độ, gốc nhóm ở đất).
      // Lùi về tây cho khỏi chen nhãn roof (dốc nào cũng cao như nhau).
      position: [-9.5, 0, -9.5],
      focusDistance: 10,
      hotspotY: 9.6,
      topY: 9,
      ringRadius: 2,
    },
    {
      id: "obj-eaves",
      shape: "eaves",
      headword: "eaves",
      partOfSpeech: "noun",
      // Nhãn đầu đông (né gutter giữa + pane tây), thân trải dài che hết mặt.
      // Bay tới GIỮA diềm chứ không tới đầu (đầu thì thấy đầu).
      position: [0, 0, -3.8],
      focus: [-6, 5.5, -3.8],
      focusDistance: 8,
      hotspotY: 6.5,
      topY: 5.55,
      ringRadius: 4.5,
    },
    {
      id: "obj-gutter",
      shape: "gutter",
      headword: "gutter",
      partOfSpeech: "noun",
      // Nhãn lên cao cho khỏi chen balcony (mũi tên dài trong không khí,
      // đè lên canvas chứ không nuốt click vì raycast tắt).
      position: [-5, 0, -3.8],
      focus: [-5, 5.5, -3.8],
      focusDistance: 8,
      hotspotY: 7.2,
      topY: 5.4,
      ringRadius: 4.5,
    },
    {
      id: "obj-vent",
      shape: "vent",
      headword: "vent",
      partOfSpeech: "noun",
      // Áp mặt đầu hồi đông (mặt tường ở local x = 4.8).
      position: [-1.2, 0, -8],
      focusDistance: 6,
      hotspotY: 7.8,
      topY: 6.9,
      ringRadius: 1.5,
    },
    {
      id: "obj-weathervane",
      shape: "weathervane",
      headword: "weathervane",
      partOfSpeech: "noun",
      // Trên nóc nóc nhà phía đông, chân ở y 7.7.
      position: [-1.5, 0, -8],
      focusDistance: 9,
      hotspotY: 9.7,
      topY: 8.85,
      ringRadius: 2,
    },
    {
      id: "obj-balcony",
      shape: "balcony",
      headword: "balcony",
      partOfSpeech: "noun",
      // Đua ra mặt trước tầng trên (sàn y 2.7). Nhãn vào giữa sàn cho khỏi
      // chen pane (vòng sáng + focus vẫn trúng sàn).
      position: [-7.6, 0, -4],
      focusDistance: 6,
      hotspotY: 4.8,
      topY: 3.9,
      ringRadius: 2.5,
    },
    {
      id: "obj-bay-window",
      shape: "bay-window",
      headword: "bay window",
      partOfSpeech: "noun",
      // Lưng áp tường (mặt tường ở world z = −4.5), kính chìa ra −3.4.
      // Nhãn ôm nắp (không mũi tên), né deck/balcony hai bên.
      position: [-8.5, 0, -4.05],
      focusDistance: 5,
      hotspotY: 2.9,
      topY: 2.65,
      ringRadius: 2,
    },
    {
      id: "obj-deck",
      shape: "deck",
      headword: "deck",
      partOfSpeech: "noun",
      // Áp hông tây nhà (mặt tường x = −10.5). Nhãn góc tây-nam, khỏi cụm
      // mặt trước (vòng sáng vẫn chạm sàn).
      position: [-13.5, 0, -6],
      focusDistance: 6,
      hotspotY: 2.4,
      topY: 1.4,
      ringRadius: 2.5,
    },
    {
      id: "obj-porch",
      shape: "porch",
      headword: "porch",
      partOfSpeech: "noun",
      // Treo cao giữa hiên (mũi tên dài trong không khí): nhãn thấp chen
      // doorway, nhãn đông chen gutter, nhãn tây chen balcony.
      position: [-4.0, 0, -2.8],
      focusDistance: 5.5,
      hotspotY: 5.2,
      topY: 3.3,
      ringRadius: 2.5,
    },
    {
      id: "obj-doorway",
      shape: "doorway",
      headword: "doorway",
      partOfSpeech: "noun",
      // Dưới mái hiên (mái ở y 3.2) nên nhãn ôm cửa, không vẽ mũi tên.
      // Lố 0.4 m khỏi mép đông cho khỏi chen porch (nhìn không ra).
      position: [-2.2, 0, -4.4],
      focusDistance: 4,
      hotspotY: 2.9,
      topY: 2.45,
      ringRadius: 1.5,
    },
    {
      id: "obj-pane",
      shape: "pane",
      headword: "pane",
      partOfSpeech: "noun",
      // Cửa sổ tầng trên phía tây, ngay trên cửa sổ lồi.
      // Nhãn lố khỏi mép kính cho khỏi chen balcony (margin 2px cũng flip
      // theo từng lần chạy — probe `zz-probe` đo thật, không đoán).
      position: [-11.1, 0, -4.3],
      focusDistance: 5,
      hotspotY: 5.3,
      topY: 5.1,
      ringRadius: 1.5,
    },
    {
      id: "obj-trim",
      shape: "trim",
      headword: "trim",
      partOfSpeech: "noun",
      // Nẹp đầu hồi + góc tường phía tây. Nhãn giữa nẹp (ôm vật, không mũi
      // tên): thấp nữa là chen pane cùng cao độ, cao nữa là chen chimney.
      position: [-11.2, 0, -8],
      focusDistance: 7,
      hotspotY: 7,
      topY: 7.3,
      ringRadius: 2.5,
    },
    {
      id: "obj-mailbox",
      shape: "mailbox",
      headword: "mailbox",
      partOfSpeech: "noun",
      // Ngoài rào, cạnh cổng đi bộ (hộp thư đứng ở lề đường, không trong sân).
      position: [-6.5, 0, 8.6],
      focusDistance: 4,
      hotspotY: 2.2,
      topY: 1.2,
      ringRadius: 1.4,
    },
    {
      id: "obj-mower",
      shape: "mower",
      headword: "mower",
      partOfSpeech: "noun",
      // Đẩy dọc bãi cỏ (z = 6.5) trên tấm yard (mặt tấm y 0.06).
      position: [3, 0.06, 6.5],
      patrol: { axis: "x", range: 5, speed: 0.9 },
      focusDistance: 5,
      hotspotY: 1.6,
      ringRadius: 1.8,
    },
    {
      id: "obj-weed",
      shape: "weed",
      headword: "weed",
      partOfSpeech: "noun",
      // Mép làn máy cắt, né nhãn fence (máy không bao giờ chạy tới đây nên
      // thân máy cũng không che được).
      position: [-3.5, 0.06, 7.0],
      focusDistance: 3.5,
      hotspotY: 1,
      ringRadius: 1.2,
    },
    {
      id: "obj-shovel",
      shape: "shovel",
      headword: "shovel",
      partOfSpeech: "noun",
      // Trong rào (cách rào đông 2 m, rào nam 3.5 m), né làn máy cắt.
      position: [8.5, 0, 4.5],
      focusDistance: 4,
      hotspotY: 1.8,
      ringRadius: 1.5,
    },
    {
      id: "obj-flowerpot",
      shape: "flowerpot",
      headword: "flowerpot",
      partOfSpeech: "noun",
      position: [-4.2, 0, -2.8],
      focusDistance: 3.5,
      hotspotY: 1.3,
      ringRadius: 1.4,
    },
    {
      id: "obj-shrub",
      shape: "shrub",
      headword: "shrub",
      partOfSpeech: "noun",
      // Nhãn ra trước bụi (nam 1.8 m) cho khỏi chen bay-window — chỉ nhãn chạm
      // nhau mới tính, nhãn đè lên thân vật khác không sao.
      position: [-10.5, 0, -2.0],
      focusDistance: 4,
      hotspotY: 1.6,
      ringRadius: 1.8,
    },
    {
      id: "obj-hedge",
      shape: "hedge",
      headword: "hedge",
      partOfSpeech: "noun",
      // Hàng rào cây biên tây, người tỉa đứng đầu nam (tĩnh, trong shape).
      position: [-12.5, 0, 2],
      focusDistance: 6,
      hotspotY: 2.2,
      topY: 1,
      ringRadius: 3,
    },
    {
      id: "obj-fence",
      shape: "fence",
      headword: "fence",
      partOfSpeech: "noun",
      // Trên hàng rào nam (đoạn này bỏ decor), đọc thành đoạn gần nhất.
      position: [0, 0, 8],
      focusDistance: 4.5,
      hotspotY: 2.1,
      topY: 1,
      ringRadius: 2,
    },
    {
      id: "obj-driveway",
      shape: "driveway",
      headword: "driveway",
      partOfSpeech: "noun",
      // Tấm bê tông ra cổng hông, xe decor đỗ giữa.
      position: [4.5, 0, -1],
      focusDistance: 7,
      hotspotY: 0.8,
      ringRadius: 4.5,
    },
    {
      id: "obj-yard",
      shape: "yard",
      headword: "yard",
      partOfSpeech: "noun",
      // Góc đông-nam thảm cỏ — giữa thảm là làn máy cắt quét qua.
      position: [7, 0, 7.5],
      focusDistance: 9,
      hotspotY: 1.4,
      ringRadius: 6,
    },
  ],
};
