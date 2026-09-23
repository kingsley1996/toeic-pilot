import type { SceneDef } from "@/content/scenes/types";

/**
 * Nhà hàng (topic `restaurant`, 21/37 từ lấy sẵn trong kho — không nhập mới).
 * Indoor thứ hai: cửa nam (host + menu) → bàn giữa → bếp mở đông-bắc →
 * quầy thu ngân tây-bắc. Đồ nhỏ tự mang bàn riêng (quy ước office) để nhãn
 * nào cũng có vật đủ lớn để bấm; hai object quầy thu ngân tách ngang 2 m
 * trên cùng quầy decor (mẫu pedestal/sculpture tách nhãn).
 *
 * Mũi tên nào cũng dư 0.05 trên 0.8 (§9.9). Bồi bàn đi làn giữa phòng —
 * làn né pill tĩnh ~2 m trở lên (bài học làn balloon park §11.6).
 */
export const restaurantScene: SceneDef = {
  id: "restaurant-01",
  title: "Nhà hàng",
  description:
    "Giờ ăn tối trong nhà hàng — bồi bàn bưng khay giữa các bàn, đầu bếp nướng thịt ở bếp mở và quầy buffet đầy món.",
  topicSlug: "restaurant",
  sky: "#e8eaec",
  environment: "restaurant-hall",
  badges: ["new", "beta"],
  // Từ nam-tây nhìn chếch đông-bắc: cửa gần, bếp xa, dãy bàn tách hai bên.
  home: { pos: [6, 9.5, 16], look: [-1, 1, -2] },
  objects: [
    {
      id: "obj-menu",
      shape: "menu-board",
      headword: "menu",
      partOfSpeech: "noun",
      // Bảng trên kệ đỡ đông cửa vào, mặt canvas +Z quay về khách.
      // Bảng cao tới y 2.25 nên nhãn lên 3.1.
      position: [1.8, 0, 6.5],
      focusDistance: 4,
      hotspotY: 3.1,
      topY: 2.25,
      ringRadius: 1.2,
    },
    {
      id: "obj-host",
      shape: "host-stand",
      headword: "host",
      partOfSpeech: "noun",
      // Bục tây cửa, host đứng sau bục mặt về khách (+Z).
      position: [-1.5, 0, 6.8],
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-seating",
      shape: "table-set",
      headword: "seating",
      partOfSpeech: "noun",
      // Bàn tròn chính giữa phòng. Nhãn ôm nến (không mũi tên): mũi tên
      // xuống mặt bàn là xuyên qua nến.
      position: [0, 0, 0.5],
      focusDistance: 5,
      hotspotY: 1.8,
      topY: 1.1,
      ringRadius: 2,
    },
    {
      id: "obj-reserve",
      shape: "reserve-table",
      headword: "reserve",
      partOfSpeech: "verb",
      // Bàn vuông tây, bảng RESERVED dựng giữa mặt bàn.
      position: [-5.5, 0, 0],
      focusDistance: 4,
      hotspotY: 2.1,
      topY: 1.25,
      ringRadius: 1.6,
    },
    {
      id: "obj-diner",
      shape: "diner-set",
      headword: "diner",
      partOfSpeech: "noun",
      // Hai thực khách đối mặt qua bàn tròn đông.
      position: [5.5, 0, 0.5],
      focusDistance: 4.5,
      hotspotY: 2.3,
      topY: 1.4,
      ringRadius: 2,
    },
    {
      id: "obj-appetizer",
      shape: "appetizer-plate",
      headword: "appetizer",
      partOfSpeech: "noun",
      // Đĩa salad ĐẦY (5 lá + 3 cà chua) — đầy mới là khai vị.
      position: [-8.5, 0, 2.5],
      focusDistance: 3.5,
      hotspotY: 1.8,
      topY: 0.95,
      ringRadius: 1.2,
    },
    {
      id: "obj-dessert",
      shape: "dessert-plate",
      headword: "dessert",
      partOfSpeech: "noun",
      // Bánh kem dâu trên đĩa chân cao (khác đĩa bẹt khai vị).
      position: [-8.5, 0, -1.5],
      focusDistance: 3.5,
      hotspotY: 2.1,
      topY: 1.2,
      ringRadius: 1.2,
    },
    {
      id: "obj-beverage",
      shape: "beverage-set",
      headword: "beverage",
      partOfSpeech: "noun",
      // Bình nước quả + 2 ly (nước thấy qua kính).
      position: [8.5, 0, 2.5],
      focusDistance: 3.5,
      hotspotY: 2.1,
      topY: 1.25,
      ringRadius: 1.2,
    },
    {
      id: "obj-napkin",
      shape: "napkin-set",
      headword: "napkin",
      partOfSpeech: "noun",
      // Khăn gấp chóp trên đĩa trống — chóp mới là "đã gấp".
      position: [8.5, 0, -1.5],
      focusDistance: 3.5,
      hotspotY: 1.9,
      topY: 1.05,
      ringRadius: 1.2,
    },
    {
      id: "obj-utensil",
      shape: "utensil-set",
      headword: "utensil",
      partOfSpeech: "noun",
      // Khay dao-nĩa-thìa (nĩa 3 răng mini).
      position: [-2.5, 0, -4],
      focusDistance: 3.5,
      hotspotY: 1.8,
      topY: 0.9,
      ringRadius: 1.2,
    },
    {
      id: "obj-refill",
      shape: "refill-pitcher",
      headword: "refill",
      partOfSpeech: "verb",
      // Bình quai + 2 ly rỗng chờ rót thêm.
      position: [2.5, 0, -4],
      focusDistance: 3.5,
      hotspotY: 2.1,
      topY: 1.25,
      ringRadius: 1.2,
    },
    {
      id: "obj-garnish",
      shape: "garnish-plate",
      headword: "garnish",
      partOfSpeech: "verb",
      // Bàn inox bếp (khác bàn gỗ khu ăn): đĩa trắng + vài lá thơm —
      // ít mới là trang trí, ngược với khai vị. Lùi khỏi quầy buffet mới
      // dài ra (x tới 7.8) và khỏi xe catering.
      position: [6.9, 0, -7.0],
      focusDistance: 3.5,
      hotspotY: 1.9,
      topY: 1.05,
      ringRadius: 1.2,
    },
    {
      id: "obj-buffet",
      shape: "buffet-counter",
      headword: "buffet",
      partOfSpeech: "noun",
      // Quầy dài đông-bắc (x 7.8..12.2): 3 khay nắp mở + chồng đĩa +
      // nồi súp + rổ bánh mì đầu đông.
      position: [10, 0, -6],
      focusDistance: 5.5,
      hotspotY: 2.1,
      topY: 1.25,
      ringRadius: 2.6,
    },
    {
      id: "obj-grill",
      shape: "grill-stove",
      headword: "grill",
      partOfSpeech: "verb",
      // Bếp góc đông-bắc sát tường (cách tường đông 0.75, tường bắc 1.4).
      // Nhãn cao nhất cụm bếp (chụp hút lên y 3.0), tách chef theo đứng.
      position: [11.5, 0, -8],
      focusDistance: 5,
      hotspotY: 3.9,
      topY: 3.0,
      ringRadius: 1.6,
    },
    {
      id: "obj-chef",
      shape: "chef-figure",
      headword: "chef",
      partOfSpeech: "noun",
      // Trước bếp, cùng trục X với buffet nhưng nhãn thấp hơn grill 1 m.
      position: [10, 0, -8],
      focusDistance: 4,
      hotspotY: 2.9,
      topY: 2.0,
      ringRadius: 1.2,
    },
    {
      id: "obj-ingredient",
      shape: "ingredient-crate",
      headword: "ingredient",
      partOfSpeech: "noun",
      // Hai thùng rau/cà rốt SAU quầy buffet (cách bếp, cách garnish
      // 0.25, khỏi làn xe catering). Vật thấp: nhãn ôm thùng.
      position: [8.5, 0, -7.2],
      focusDistance: 3.5,
      hotspotY: 1.5,
      topY: 0.6,
      ringRadius: 1.4,
    },
    {
      id: "obj-catering",
      shape: "catering-cart",
      headword: "catering",
      partOfSpeech: "noun",
      // Xe đẩy 3 tầng tây bếp, khay phủ khăn tầng trên + nhân viên đẩy
      // sau tay cầm. Đẩy dọc làn đông (x 4.5, z −7.5..−3): né refill 2 m
      // phía tây, né garnish 2.4 m phía đông. `Mover` tự xoay theo hướng —
      // đi nam thì người sau xe (đẩy), đi bắc thì trước xe mặt vào xe (kéo).
      // Pill pointer-events-none nên ngoài luật hotspot đứng yên.
      position: [4.5, 0, -5.25],
      patrol: { axis: "z", range: 2.25, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.2,
      topY: 1.35,
      ringRadius: 1.4,
    },
    {
      id: "obj-waiter",
      shape: "waiter-figure",
      headword: "waiter",
      partOfSpeech: "noun",
      // Bưng khay đi làn giữa phòng (x −3..3, z 3.5) — né bàn chính 3 m,
      // né menu/host 3 m. Khay kê đầu tay (y 1.86) nên nhãn ôm khay;
      // pill pointer-events-none nên ngoài luật hotspot đứng yên.
      position: [0, 0, 3.5],
      patrol: { axis: "x", range: 3, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.7,
      topY: 1.88,
      ringRadius: 1.2,
    },
    {
      id: "obj-takeout",
      shape: "takeout-bag",
      headword: "takeout",
      partOfSpeech: "noun",
      // Đầu tây quầy thu ngân decor (quầy x −12.2..−7.8) — túi + hộp xốp.
      position: [-11, 0, -6],
      focusDistance: 3.5,
      hotspotY: 2.3,
      topY: 1.45,
      ringRadius: 1.2,
    },
    {
      id: "obj-gratuity",
      shape: "gratuity-jar",
      headword: "gratuity",
      partOfSpeech: "noun",
      // Đầu đông quầy thu ngân — hũ kính thấy tiền xanh + bảng TIP.
      position: [-9, 0, -6],
      focusDistance: 3.5,
      hotspotY: 2.3,
      topY: 1.45,
      ringRadius: 1.2,
    },
    {
      id: "obj-recipe",
      shape: "recipe-shelf",
      headword: "recipe",
      partOfSpeech: "noun",
      // Kệ sách áp tường ĐÔNG gần bếp, quay mặt −X vào phòng
      // (lưng cách tường 0.14).
      position: [12.5, 0, -3],
      rotationY: -Math.PI / 2,
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
  ],
};
