import type { SceneDef } from "@/content/scenes/types";

/**
 * Phòng khách sạn (topic `hotel`, 18 từ: 15 nhập mới qua pipeline + 3 nối từ
 * housing/travel — balcony, curtain, baggage). Làm lại từ sảnh thất bại: sảnh
 * ép từ trừu tượng khó hình dung; phòng toàn đồ vật cụ thể.
 *
 * Bố cục: phòng ngủ tây (giường dọc Z đầu bắc) + phòng tắm kính đông-nam +
 * ban công ngoài tường bắc. Gối nằm TRÊN nệm như grill/chef cùng X tách đứng
 * — probe quyết định có giữ được không.
 *
 * Mũi tên nào cũng dư 0.05 trên 0.8 (§9.9). Không vật patrol (phòng tĩnh).
 */
export const hotelRoomScene: SceneDef = {
  id: "hotel-room-01",
  title: "Phòng khách sạn",
  description:
    "Căn phòng suite ấm cúng — giường êm với gối chăn phẳng phiu, phòng tắm kính với bồn tắm và vòi sen, ban công nhìn ra thành phố.",
  topicSlug: "hotel",
  sky: "#dfe6ea",
  environment: "hotel-room",
  badges: ["new", "beta"],
  // Đông-nam trên cao nhìn chếch tây-bắc: đứng xa cho phòng tắm đông-nam
  // lọt khung mà không quá xiên (bản đầu gần quá, buồng tắm ngoài frustum).
  home: { pos: [8, 10, 21], look: [-1.5, 1, -2.5] },
  objects: [
    {
      id: "obj-bed",
      shape: "bed-frame",
      headword: "bed",
      partOfSpeech: "noun",
      // Giường đôi dọc Z đầu bắc, ga phủ đỉnh 0.875.
      position: [-5, 0, -3.1],
      focusDistance: 6,
      hotspotY: 1.75,
      topY: 0.9,
      ringRadius: 2.8,
    },
    {
      id: "obj-pillow",
      shape: "pillow-pair",
      headword: "pillow",
      partOfSpeech: "noun",
      // Cặp gối TRÊN nệm, lệch đông 0.5 m cho pill khỏi trục pill giường
      // (cùng X là chồng khít theo probe) — vẫn trong nệm như gối xô lệch.
      position: [-4.5, 0, -4.6],
      focusDistance: 4,
      hotspotY: 1.9,
      topY: 1.05,
      ringRadius: 1.4,
    },
    {
      id: "obj-blanket",
      shape: "blanket-bench",
      headword: "blanket",
      partOfSpeech: "noun",
      // Chăn gấp trên băng cuối giường, cách chân giường 0.45 m.
      position: [-5, 0, -0.2],
      focusDistance: 4,
      hotspotY: 1.65,
      topY: 0.8,
      ringRadius: 1.6,
    },
    {
      id: "obj-alarm-clock",
      shape: "alarm-clock",
      headword: "alarm clock",
      partOfSpeech: "noun",
      // Tủ đầu giường tây, cách khung giường 0.55 m.
      position: [-7.6, 0, -4.8],
      focusDistance: 3.5,
      hotspotY: 1.95,
      topY: 1.1,
      ringRadius: 1.2,
    },
    {
      id: "obj-television",
      shape: "tv-set",
      headword: "television",
      partOfSpeech: "noun",
      // TV lớn THẲNG TRỤC giường (nam giường, mặt về bắc). Xoay π giữ trục
      // thẳng; màn ngồi trực tiếp lên tủ, đỉnh 1.845.
      position: [-5.5, 0, 2.2],
      rotationY: Math.PI,
      focusDistance: 5,
      hotspotY: 2.7,
      topY: 1.85,
      ringRadius: 1.8,
    },
    {
      id: "obj-air-conditioner",
      shape: "aircon-wall",
      headword: "air conditioner",
      partOfSpeech: "noun",
      // Treo tường bắc đông-biển hiệu (cách biển 0.85, khỏi đè pill nhau).
      position: [6, 0, -8.7],
      focusDistance: 4.5,
      hotspotY: 3.6,
      topY: 2.75,
      ringRadius: 1.4,
    },
    {
      id: "obj-closet",
      shape: "closet-wardrobe",
      headword: "closet",
      partOfSpeech: "noun",
      // Tủ quần áo đông-bắc, nóc đỉnh 2.27.
      position: [9, 0, -6],
      focusDistance: 5,
      hotspotY: 3.15,
      topY: 2.3,
      ringRadius: 1.8,
    },
    {
      id: "obj-hanger",
      shape: "hanger-rack",
      headword: "hanger",
      partOfSpeech: "noun",
      // Giá treo di động tây tủ, cách 0.5 m.
      position: [6.5, 0, -6],
      focusDistance: 4,
      hotspotY: 2.55,
      topY: 1.7,
      ringRadius: 1.4,
    },
    {
      id: "obj-safe",
      shape: "safe-box",
      headword: "safe",
      partOfSpeech: "noun",
      // Két trên kệ thấp tường đông.
      position: [11, 0, -3.5],
      focusDistance: 3.5,
      hotspotY: 1.8,
      topY: 0.95,
      ringRadius: 1.2,
    },
    {
      id: "obj-minibar",
      shape: "minibar-fridge",
      headword: "minibar",
      partOfSpeech: "noun",
      // Tủ hốc mở + cửa kính mở + biển MINIBAR, nắp đỉnh 1.2.
      // Đẩy về nam 1 m cho pill khỏi kẹt safe 4 px theo probe.
      position: [11, 0, 0],
      focusDistance: 3.5,
      hotspotY: 2.1,
      topY: 1.25,
      ringRadius: 1.4,
    },
    {
      id: "obj-kettle",
      shape: "kettle-tray",
      headword: "kettle",
      partOfSpeech: "noun",
      // Khay trà trên bàn đông-tây (ra khỏi trục shower theo probe).
      position: [6.5, 0, 1.5],
      focusDistance: 3.5,
      hotspotY: 1.7,
      topY: 0.85,
      ringRadius: 1.2,
    },
    {
      id: "obj-towel",
      shape: "towel-rack",
      headword: "towel",
      partOfSpeech: "noun",
      // Giá khăn 2 khăn trong buồng tắm.
      position: [10, 0, 8],
      focusDistance: 3.5,
      hotspotY: 2.2,
      topY: 1.35,
      ringRadius: 1.2,
    },
    {
      id: "obj-bathtub",
      shape: "bathtub-tub",
      headword: "bathtub",
      partOfSpeech: "noun",
      // Bồn tắm giữa buồng, vòi đầu tây.
      position: [9.5, 0, 6],
      focusDistance: 4.5,
      hotspotY: 1.7,
      topY: 0.85,
      ringRadius: 1.8,
    },
    {
      id: "obj-shower",
      shape: "shower-stall",
      headword: "shower",
      partOfSpeech: "noun",
      // Buồng sen góc tây-bắc buồng tắm, bát sen đỉnh 2.1.
      position: [8.4, 0, 4],
      focusDistance: 4,
      hotspotY: 2.95,
      topY: 2.1,
      ringRadius: 1.4,
    },
    {
      id: "obj-balcony",
      shape: "balcony-door",
      headword: "balcony",
      partOfSpeech: "noun",
      // Vách kính trượt NGAY mặt cửa mở tường bắc (khung khít mép mở).
      // Pill ngay cửa, khỏi mũi tên.
      position: [-3, 0, -8.8],
      focusDistance: 5.5,
      hotspotY: 2.0,
      topY: 2.55,
      ringRadius: 2.0,
    },
    {
      id: "obj-curtain",
      shape: "curtain-pair",
      headword: "curtain",
      partOfSpeech: "noun",
      // Rèm 2 bên vách kính, áp sát tường (cách mặt tường 0.45).
      position: [-3, 0, -8.4],
      focusDistance: 4.5,
      hotspotY: 3.45,
      topY: 2.6,
      ringRadius: 1.8,
    },
    {
      id: "obj-baggage",
      shape: "baggage-rack",
      headword: "baggage",
      partOfSpeech: "noun",
      // Giá 4 chân + 2 vali cạnh cụm tủ (cách hanger theo đứng cho khỏi
      // cùng cột pill theo probe).
      position: [6.8, 0, -2.8],
      focusDistance: 4,
      hotspotY: 2.05,
      topY: 1.2,
      ringRadius: 1.4,
    },
    {
      id: "obj-rug",
      shape: "rug-mat",
      headword: "rug",
      partOfSpeech: "noun",
      // Thảm 3 lớp tây-nam (dưới sofa). Vật bẹt: nhãn ôm mặt thảm.
      position: [-10.5, 0, 5.5],
      focusDistance: 5,
      hotspotY: 1.0,
      topY: 0.1,
      ringRadius: 2.4,
    },
    {
      id: "obj-sofa",
      shape: "sofa-chair",
      headword: "sofa",
      partOfSpeech: "noun",
      // Sofa dài dọc tường trái, lưng tựa tây mặt ra đông. Chân đứng
      // trên thảm (không lơ lửng).
      position: [-10.8, 0, 5.8],
      rotationY: Math.PI / 2,
      focusDistance: 4.5,
      hotspotY: 2.15,
      topY: 1.3,
      ringRadius: 1.6,
    },
  ],
};
