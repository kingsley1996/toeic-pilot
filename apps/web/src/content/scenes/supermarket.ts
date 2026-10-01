import type { SceneDef } from "@/content/scenes/types";

/**
 * Siêu thị (topic `supermarket`, 24 từ — 19 nhập mới + receipt/coupon/
 * discount/promotion/refund gắn lại từ topic cũ).
 *
 * Bố cục nam→bắc: tường kính nam (entrance x −6, exit x +6) → sảnh giữa với
 * 3 dãy kệ song song Z + xe đẩy patrol aisle giữa → quầy thu ngân bắc +
 * bakery/deli hai góc. Đông là produce, tây là dairy/freezer.
 *
 * Một object một dãy: chỉ dãy kệ giữa mang nhãn `shelf`, hai dãy bên là
 * decor trong environment (không hotspot — recall chỉ hỏi object còn lại).
 * Tương tự checkout: một shape 3 làn, một nhãn.
 *
 * Nhãn treo cao tính dư 0.05 trên 0.8 (§9.9). Đồ trên mặt quầy (receipt/
 * barcode/bag): đáy lút 0.005, nhãn ôm mặt hoặc mũi tên ngắn, tách khỏi
 * nhãn checkout bằng cao độ + vị trí x.
 */
export const supermarketScene: SceneDef = {
  id: "supermarket-aisles-01",
  title: "Siêu thị",
  description:
    "Buổi mua sắm trong siêu thị — dãy kệ đầy hàng, xe đẩy dọc lối đi, quầy thu ngân và góc khuyến mãi cuối tuần.",
  topicSlug: "supermarket",
  sky: "#dfe9ef",
  environment: "supermarket-hall",
  // Trong nhà: camera ngoài tường kính nam nhìn xuyên vào (mẫu office) —
  // đứng trong phòng là tường bắc dồn pill (§10.1).
  home: { pos: [2, 8, 18], look: [-0.5, 1, -4] },
  badges: ["new", "beta"],
  objects: [
    {
      id: "obj-entrance",
      shape: "entry-door",
      headword: "entrance",
      partOfSpeech: "noun",
      // Cửa trượt tây trên tường kính nam. Biển IN/EXIT trên đầu (topY 3.3)
      // nên nhãn ôm nóc biển, không mũi tên.
      position: [-6, 0, 10],
      focusDistance: 8,
      hotspotY: 3.6,
      topY: 3.3,
      ringRadius: 2,
    },
    {
      id: "obj-exit",
      shape: "exit-door",
      headword: "exit",
      partOfSpeech: "noun",
      // Cửa trượt đông — shape riêng biển EXIT xanh (phân biệt với IN).
      position: [6, 0, 10],
      focusDistance: 8,
      hotspotY: 3.6,
      topY: 3.3,
      ringRadius: 2,
    },
    {
      id: "obj-basket",
      shape: "basket-stack",
      headword: "basket",
      partOfSpeech: "noun",
      // Chồng giỏ cạnh cửa vào, đông bảng mua sắm.
      position: [-3.2, 0, 8.6],
      focusDistance: 4,
      hotspotY: 1.9,
      topY: 1.0,
      ringRadius: 1,
    },
    {
      id: "obj-list",
      shape: "list-board",
      headword: "shopping list",
      partOfSpeech: "noun",
      // Bảng danh sách đông sảnh, mặt +Z về cửa (về camera). x 1.8: né trụ
      // mặt tiền x 3.5 (bay tới là trụ án ngữ) mà vẫn tách cột nhìn với
      // biển aisle (x 0.2) — wrapper drei của bảng gần camera phủ rộng.
      position: [1.8, 0, 8.8],
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-shelf",
      shape: "gondola-shelf",
      headword: "shelf",
      partOfSpeech: "noun",
      // Dãy giữa (x −2.5, z −3..5). Nhãn vào giữa dãy — bay tới đầu thì
      // chỉ thấy đầu (§types `focus`).
      position: [-2.5, 0, 1],
      focus: [-2.5, 1, 1],
      focusDistance: 6,
      hotspotY: 2.9,
      topY: 2.0,
      ringRadius: 3.5,
    },
    {
      id: "obj-aisle",
      shape: "aisle-sign",
      headword: "aisle",
      partOfSpeech: "noun",
      // Cổng biển số 5 đầu ĐÔNG aisle (x 2.6): làn xe ngang quét dải
      // x −3.5..0.5, để cổng ở cột cũ (x 0.2) là wrapper drei của pill xe
      // đè pill biển. Chân cổng z 6.2, làn xe tới z 3.9 là dừng.
      position: [2.6, 0, 6.2],
      focusDistance: 6,
      hotspotY: 3.5,
      topY: 2.6,
      ringRadius: 2,
    },
    {
      id: "obj-cart",
      shape: "shop-cart",
      headword: "cart",
      partOfSpeech: "noun",
      // Patrol ngang aisle ĐÔNG-TÂY phía nam dãy kệ giữa (z 3, x −3.5..0.5):
      // kệ dài theo X nên làn cũ x 1.4 đâm xuyên dãy giữa (x −6.5..1.5).
      // Làn này hở cả hai đầu (tây hết x −4, đông hết x 1.5) và hở price-tag
      // (z ≥5.4) lẫn cổng biển (z 6.2). Cách pill tĩnh gần nhất >2 m (§11.6).
      // Nhãn treo cao trên thân xe (§7.5) — đỉnh thật là đầu người đẩy
      // (1.72) nên topY theo nó, không theo giỏ.
      position: [-1.5, 0, 3],
      patrol: { axis: "x", range: 2, speed: 0.5 },
      focusDistance: 5,
      hotspotY: 2.3,
      topY: 1.75,
      ringRadius: 1.4,
    },
    {
      id: "obj-tag",
      shape: "endcap-tag",
      headword: "price tag",
      partOfSpeech: "noun",
      // Đầu cap cuối nam dãy kệ giữa — tách khỏi nhãn shelf bằng z.
      position: [-2.5, 0, 5.9],
      focusDistance: 4,
      hotspotY: 2.0,
      topY: 1.1,
      ringRadius: 1,
    },
    {
      id: "obj-produce",
      shape: "produce-stand",
      headword: "produce",
      partOfSpeech: "noun",
      // Sạp rau phía đông, bàn gỗ + thùng hàng.
      position: [11, 0, 3],
      focusDistance: 6,
      hotspotY: 2.5,
      topY: 1.6,
      ringRadius: 2.2,
    },
    {
      id: "obj-scale",
      shape: "produce-scale",
      headword: "scale",
      partOfSpeech: "noun",
      // Cân bàn giữa sảnh đông — đứng riêng ngoài footprint produce (bay
      // tới từ nam là sạp rau che mất) mà vẫn cạnh sạp cho đúng chuyện.
      position: [7.8, 0, 5.0],
      focusDistance: 4,
      hotspotY: 2.4,
      topY: 1.5,
      ringRadius: 1,
    },
    {
      id: "obj-sample",
      shape: "sample-stand",
      headword: "sample",
      partOfSpeech: "noun",
      // Khay ăn thử đông-nam, giữa produce và lối đi chính.
      position: [8.5, 0, 6.5],
      focusDistance: 4,
      hotspotY: 2.2,
      topY: 1.3,
      ringRadius: 1,
    },
    {
      id: "obj-dairy",
      shape: "dairy-cooler",
      headword: "dairy",
      partOfSpeech: "noun",
      // Tủ sữa mở áp tường tây, mặt +X vào phòng. KHÔNG yaw: shape đã dựng
      // mặt mở theo +X, yaw π/2 là quay mặt mở vào tường tây (mắt kiểm cận
      // dairy lần 1: chỉ thấy lưng tủ). Dài 2.4 theo X: lưng hở tường 0.7,
      // mặt hở dãy kệ decor 0.35.
      position: [-12.75, 0, -2],
      focusDistance: 5,
      hotspotY: 2.6,
      topY: 1.7,
      ringRadius: 2,
    },
    {
      id: "obj-freezer",
      shape: "chest-freezer",
      headword: "freezer",
      partOfSpeech: "noun",
      // Tủ đông ĐỨNG cửa kính tây-bắc — food đối mặt camera, không phải
      // nhìn từ trên như tủ nằm. Cao 2.0 m.
      position: [-12.6, 0, -6.5],
      focusDistance: 5,
      hotspotY: 2.9,
      topY: 2.05,
      ringRadius: 2,
    },
    {
      id: "obj-bakery",
      shape: "bakery-counter",
      headword: "bakery",
      partOfSpeech: "noun",
      // Quầy bánh đông-bắc, đối xứng deli bên tây.
      position: [10, 0, -7],
      focusDistance: 6,
      hotspotY: 2.6,
      topY: 1.7,
      ringRadius: 2.2,
    },
    {
      id: "obj-deli",
      shape: "deli-counter",
      headword: "deli",
      partOfSpeech: "noun",
      // Quầy đồ nguội kính tây-bắc.
      position: [-10, 0, -7],
      focusDistance: 6,
      hotspotY: 2.7,
      topY: 1.8,
      ringRadius: 2.2,
    },
    {
      id: "obj-checkout",
      shape: "checkout-lane",
      headword: "checkout",
      partOfSpeech: "noun",
      // Một shape 3 làn, một nhãn — 3 object là 3 nhãn đè nhau.
      // Nhãn lên 2.7 cho thoát khỏi receipt/barcode/bag trên mặt quầy.
      position: [0, 0, -8.5],
      focus: [0.5, 0.9, -8.5],
      focusDistance: 7,
      hotspotY: 2.7,
      topY: 0.95,
      ringRadius: 4,
    },
    {
      id: "obj-cashier",
      shape: "cashier",
      headword: "cashier",
      partOfSpeech: "noun",
      // Thu ngân SAU quầy làn TÂY, mặt +Z về khách (θ = atan2(−1, 0)) —
      // để làn giữa là pill thu ngân đè pill checkout cùng cột. Đứng 7 m +
      // nhìn hơi từ trên (y 1.5) cho thấy người qua mặt quầy thấp (0.9).
      // Tách receipt/barcode bằng x.
      position: [-2.4, 0, -9.4],
      rotationY: -Math.PI / 2,
      focus: [-2.4, 1.5, -9.4],
      focusDistance: 7,
      hotspotY: 2.6,
      topY: 1.72,
      ringRadius: 1,
    },
    {
      id: "obj-receipt",
      shape: "receipt-slip",
      headword: "receipt",
      partOfSpeech: "noun",
      // Giấy in trên quầy tây — vật nhỏ nên nhãn ôm sát (1.4) thay vì
      // treo cao; thấp hơn nhãn checkout 1.3 m nên không đè.
      position: [-2, 0, -8.3],
      focusDistance: 3,
      hotspotY: 1.4,
      topY: 0.945,
      ringRadius: 0.6,
    },
    {
      id: "obj-barcode",
      shape: "barcode-box",
      headword: "barcode",
      partOfSpeech: "noun",
      // Hộp ngũ cốc dựng trên quầy, mặt mã vạch về camera.
      position: [-1, 0, -8.3],
      focusDistance: 3,
      hotspotY: 2.3,
      topY: 1.42,
      ringRadius: 0.6,
    },
    {
      id: "obj-bag",
      shape: "paper-bags",
      headword: "bag",
      partOfSpeech: "noun",
      // Chồng túi giấy cuối đông quầy — đông receipt 4.5 m theo x.
      position: [2.5, 0, -8.5],
      focusDistance: 3.5,
      hotspotY: 2.4,
      topY: 1.47,
      ringRadius: 0.8,
    },
    {
      id: "obj-promo",
      shape: "promo-tower",
      headword: "promotion",
      partOfSpeech: "noun",
      // Tháp hàng giữa sảnh trước quầy — điểm hút mắt của cảnh.
      position: [8.5, 0, -1],
      focusDistance: 6,
      hotspotY: 3.0,
      topY: 2.1,
      ringRadius: 2.4,
    },
    {
      id: "obj-coupon",
      shape: "coupon-stand",
      headword: "coupon",
      partOfSpeech: "noun",
      // Biển chữ A trước quầy tây — xuống đất vì tường bắc hết chỗ (§10.3).
      position: [-4, 0, -6],
      focusDistance: 4,
      hotspotY: 2.5,
      topY: 1.6,
      ringRadius: 1,
    },
    {
      id: "obj-discount",
      shape: "discount-totem",
      headword: "discount",
      partOfSpeech: "noun",
      // Cột biển cam cạnh tháp khuyến mãi — cách 2.4 m, không chung tia
      // nhìn với nhãn promotion từ camera đầu.
      position: [6.3, 0, 0.8],
      focusDistance: 5,
      hotspotY: 3.35,
      topY: 2.45,
      ringRadius: 1.2,
    },
    {
      id: "obj-refund",
      shape: "service-desk",
      headword: "refund",
      partOfSpeech: "noun",
      // Quầy dịch vụ KH tây-nam, gần cửa vào đúng đời (đổi trả ngay khi vào).
      // Dời z 8 cho hở đầu nam dãy kệ decor tây (kết z 7). Focus vào mặt
      // quầy + đứng 3.5 m: 6 m là camera hạ ngoài tường tây nhìn vào tường.
      position: [-11, 0, 8],
      focus: [-11, 1.0, 8.2],
      focusDistance: 3.5,
      hotspotY: 2.8,
      topY: 1.9,
      ringRadius: 1.6,
    },
  ],
};
