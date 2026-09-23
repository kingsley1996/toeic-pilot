import type { SceneDef } from "@/content/scenes/types";

/**
 * Sảnh sân bay (topic `airport`, 23 từ: 13 nhập mới qua pipeline +
 * 10 nối từ travel/park/business — boarding pass, luggage, customs, delay,
 * departure, passport, cancellation, layover, gate, itinerary).
 * Bố cục theo luồng bay thật (nam → bắc): cửa vào + INFO nam → check-in
 * tây → hải quan khai báo → soi chiếu an ninh (nút cổ chai giữa) → kiểm hộ
 * chiếu → phòng chờ + góc nối chuyến (airside) → podium soát vé SÁT cửa ra
 * máy bay bắc + đường băng ngoài tường kính thấp. Khoang mẫu đông-bắc: ghế
 * + ngăn trên tách mép 0.45 m, tách nhãn đứng 1.65 m (mẫu grill/chef).
 * Mũi tên nào cũng dư 0.05 trên 0.8 (§9.9).
 */
export const airportScene: SceneDef = {
  id: "airport-01",
  title: "Sảnh sân bay",
  description:
    "Giờ cao điểm trong sảnh khởi hành — quầy check-in nhộn nhịp, bảng chuyến bay nhảy liên tục và hành khách xếp hàng qua cửa an ninh ra đường băng.",
  topicSlug: "airport",
  sky: "#dfe6ea",
  environment: "airport-terminal",
  badges: ["new", "beta"],
  // Đông-nam trên cao nhìn chếch tây-bắc: quầy tây gần-trái, băng bắc xa.
  home: { pos: [9, 11, 22], look: [-1, 1, -3] },
  objects: [
    {
      id: "obj-checkin-counter",
      shape: "checkin-counter",
      headword: "check-in counter",
      partOfSpeech: "noun",
      // Quầy dài 6 m (x −13..−7), màn hình sau đỉnh 2.4.
      position: [-10, 0, 2],
      focusDistance: 7,
      hotspotY: 3.25,
      topY: 2.4,
      ringRadius: 3.2,
    },
    {
      id: "obj-ticket-agent",
      shape: "ticket-agent",
      headword: "ticket agent",
      partOfSpeech: "noun",
      // Góc tây-nam quầy, vai đón khách — nhãn cũ đè khít nhãn quầy
      // (probe: tâm cách nhau 2 px), ra góc này thì thoát cả quầy lẫn belt.
      position: [-13.5, 0, 3.0],
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-conveyor-belt",
      shape: "conveyor-belt",
      headword: "conveyor belt",
      partOfSpeech: "noun",
      // Băng dài 5 m sau quầy, vali trượt khi explore.
      position: [-10, 0, -1.3],
      focusDistance: 6,
      hotspotY: 2.2,
      topY: 1.35,
      ringRadius: 2.8,
    },
    {
      id: "obj-luggage",
      shape: "luggage-cart",
      headword: "luggage",
      partOfSpeech: "noun",
      // Xe đẩy đông quầy, vali chồng đỉnh 1.71.
      position: [-4.5, 0, 3.2],
      focusDistance: 4,
      hotspotY: 2.55,
      topY: 1.7,
      ringRadius: 1.2,
    },
    {
      id: "obj-carry-on",
      shape: "carry-on",
      headword: "carry-on",
      partOfSpeech: "noun",
      // Bục cân giữa sảnh, khỏi trục quầy–xe đẩy (probe: nhãn cũ kẹt
      // giữa luggage và counter). Cách mép ghế lounge 0.95 m theo X.
      position: [-4.2, 0, -0.8],
      focusDistance: 3.5,
      hotspotY: 1.85,
      topY: 1.0,
      ringRadius: 1.2,
    },
    {
      id: "obj-departure-board",
      shape: "departure-board",
      headword: "departure board",
      partOfSpeech: "noun",
      // Bảng tổng treo cột giữa sảnh, đỉnh 3.35 dưới tường 3.4.
      position: [0, 0, 3.0],
      focusDistance: 7,
      hotspotY: 4.2,
      topY: 3.35,
      ringRadius: 2.8,
    },
    {
      id: "obj-departure",
      shape: "departure-screen",
      headword: "departure",
      partOfSpeech: "noun",
      // 3 kiosk màn hình cách nhau 4 m, màu phân biệt trạng thái.
      position: [-4, 0, 7.5],
      focusDistance: 4,
      hotspotY: 3.45,
      topY: 2.6,
      ringRadius: 1.2,
    },
    {
      id: "obj-delay",
      shape: "delay-screen",
      headword: "delay",
      partOfSpeech: "noun",
      position: [0, 0, 7.5],
      focusDistance: 4,
      hotspotY: 3.45,
      topY: 2.6,
      ringRadius: 1.2,
    },
    {
      id: "obj-cancellation",
      shape: "cancel-screen",
      headword: "cancellation",
      partOfSpeech: "noun",
      position: [4, 0, 7.5],
      focusDistance: 4,
      hotspotY: 3.45,
      topY: 2.6,
      ringRadius: 1.2,
    },
    {
      id: "obj-announcement",
      shape: "announce-pole",
      headword: "announcement",
      partOfSpeech: "noun",
      // Cột loa góc tây-bắc airside (phủ phòng chờ + cửa ra máy bay).
      position: [-6.5, 0, -6.5],
      focusDistance: 4,
      hotspotY: 3.45,
      topY: 2.6,
      ringRadius: 1.2,
    },
    {
      id: "obj-departure-lounge",
      shape: "departure-lounge",
      headword: "departure lounge",
      partOfSpeech: "noun",
      // 2 dãy ghế giữa sảnh. Vật thấp: nhãn ôm lưng ghế.
      position: [-1, 0, -2.5],
      focusDistance: 5.5,
      hotspotY: 1.85,
      topY: 1.0,
      ringRadius: 2.4,
    },
    {
      id: "obj-layover",
      shape: "layover-corner",
      headword: "layover",
      partOfSpeech: "noun",
      // Góc nối chuyến đông-bắc airside (tránh pill stand theo probe).
      position: [12, 0, 0.5],
      focusDistance: 4,
      hotspotY: 3.05,
      topY: 2.2,
      ringRadius: 1.6,
    },
    {
      id: "obj-itinerary",
      shape: "info-desk",
      headword: "itinerary",
      partOfSpeech: "noun",
      // Quầy INFO chữ nhật + bảng lịch trình nghiêng (cột biển xanh đã bỏ).
      // Bảng đỉnh ~1.7 nên nhãn 2.55.
      position: [7, 0, 7.5],
      focusDistance: 4,
      hotspotY: 2.55,
      topY: 1.7,
      ringRadius: 1.2,
    },
    {
      id: "obj-boarding-pass",
      shape: "boarding-podium",
      headword: "boarding pass",
      partOfSpeech: "noun",
      // Podium soát vé SÁT cửa ra máy bay (đông cửa 2.5 m) — bản cũ lơ lửng
      // giữa sảnh là sai luồng. Thẻ trên giá quay về hàng chờ phía nam.
      position: [-1.0, 0, -10.3],
      focusDistance: 4,
      hotspotY: 2.7,
      topY: 1.85,
      ringRadius: 1.6,
    },
    {
      id: "obj-security-checkpoint",
      shape: "security-frame",
      headword: "security checkpoint",
      partOfSpeech: "noun",
      // Nút cổ chai giữa landside–airside, lệch đông cho kín nửa sảnh đông.
      // Khay vươn tới z 2.1, cách cột bảng 0.8 m.
      position: [5, 0, 0.3],
      focusDistance: 5.5,
      hotspotY: 3.55,
      topY: 2.7,
      ringRadius: 2.4,
    },
    {
      id: "obj-passport-control",
      shape: "passport-booth",
      headword: "passport control",
      partOfSpeech: "noun",
      // Ngay sau khung soi (đúng luồng xuất cảnh), mặt buồng về nam đón khách.
      position: [8, 0, -2.5],
      focusDistance: 4.5,
      hotspotY: 3.25,
      topY: 2.4,
      ringRadius: 1.6,
    },
    {
      id: "obj-passport",
      shape: "passport-stand",
      headword: "passport",
      partOfSpeech: "noun",
      // Bục hộ chiếu cạnh buồng kiểm (khách cầm sẵn trên tay).
      position: [10.5, 0, -3],
      focusDistance: 3.5,
      hotspotY: 2.0,
      topY: 1.15,
      ringRadius: 1.2,
    },
    {
      id: "obj-customs",
      shape: "customs-counter",
      headword: "customs",
      partOfSpeech: "noun",
      // Luồng thật: ra khỏi quầy check-in là gặp hải quan khai báo TRƯỚC
      // khi vào soi chiếu (bản cũ đặt sau passport control là ngược).
      position: [-7, 0, 5],
      focusDistance: 5,
      hotspotY: 3.45,
      topY: 2.6,
      ringRadius: 2.0,
    },
    {
      id: "obj-gate",
      shape: "gate-door",
      headword: "gate",
      partOfSpeech: "noun",
      // Cửa kính đôi trên tường bắc + biển GATE 12 đỉnh 3.15.
      position: [-6, 0, -11.5],
      focusDistance: 5,
      hotspotY: 4.0,
      topY: 3.15,
      ringRadius: 1.8,
    },
    {
      id: "obj-runway",
      shape: "runway-strip",
      headword: "runway",
      partOfSpeech: "noun",
      // Dải băng ngoài trời sát tường bắc; tường/kính/máy bay decor tắt
      // raycast nên tia bấm xuyên tới. Thân băng BẬT raycast (bấm thân cũng
      // ăn). Pill nhấc lên 1.4 cho dễ thấy từ xa.
      position: [-4, 0, -16.5],
      focusDistance: 12,
      hotspotY: 1.4,
      topY: 0.15,
      ringRadius: 3.5,
    },
    {
      id: "obj-overhead-bin",
      shape: "overhead-bin",
      headword: "overhead bin",
      partOfSpeech: "noun",
      // Tủ trên của cụm ghế mẫu — cụm trưng bày ở đông-nam cạnh INFO
      // (pill cũ thẳng trục camera với booth dù cách nhau 5 m).
      position: [12, 0, 3.5],
      focusDistance: 4.5,
      hotspotY: 3.5,
      topY: 2.65,
      ringRadius: 1.8,
    },
    {
      id: "obj-aisle-seat",
      shape: "aisle-seat",
      headword: "aisle seat",
      partOfSpeech: "noun",
      // 3 ghế mẫu + thảm lối đi ở đông-nam (hãng trưng bày cạnh INFO).
      position: [12, 0, 6],
      focusDistance: 4.5,
      hotspotY: 1.85,
      topY: 1.0,
      ringRadius: 1.8,
    },
    {
      id: "obj-flight-attendant",
      shape: "flight-attendant",
      headword: "flight attendant",
      partOfSpeech: "noun",
      // Tổ bay đi làn airside ra cửa (x 0..6, z −6.2): sau buồng kiểm, trước
      // cửa ra máy bay — đúng đường crew đi làm nhiệm vụ. Làn cách vách
      // kính lounge 0.95 m (xe đẩy sâu 0.45).
      // `position` là TRUNG ĐIỂM tuyến; pill patrol pointer-events-none nên
      // ngoài luật hotspot đứng yên (mẫu waiter nhà hàng).
      position: [3, 0, -6.2],
      patrol: { axis: "x", range: 3, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.65,
      topY: 1.8,
      ringRadius: 1.2,
    },
  ],
};
