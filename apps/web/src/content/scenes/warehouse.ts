import type { SceneDef } from "@/content/scenes/types";

export const warehouseScene: SceneDef = {
  id: "warehouse-01",
  title: "Trong nhà kho",
  description:
    "Kho hàng nhộn nhịp — quản lý kho đi kiểm hàng giữa xe tải, kệ hàng, chồng kiện và phiếu giao hàng.",
  topicSlug: "logistics",
  sky: "#e9edf0",
  environment: "warehouse-lot",
  badges: ["new", "beta"],
  objects: [
    {
      id: "obj-warehouse",
      shape: "warehouse",
      headword: "warehouse",
      partOfSpeech: "noun",
      position: [-4.5, 0, -5.5],
      focusDistance: 10.5,
      hotspotY: 4.1,
      ringRadius: 4.6,
    },
    {
      id: "obj-loading-bay",
      shape: "loading-bay",
      headword: "loading bay",
      partOfSpeech: "noun",
      position: [2.8, 0, -3.4],
      focusDistance: 5.5,
      hotspotY: 2.6,
      ringRadius: 1.7,
    },
    {
      id: "obj-depot",
      shape: "depot",
      headword: "depot",
      partOfSpeech: "noun",
      position: [7.6, 0, -5.8],
      focusDistance: 7,
      hotspotY: 3.1,
      ringRadius: 2.6,
    },
    {
      id: "obj-forklift",
      shape: "forklift",
      headword: "forklift",
      partOfSpeech: "noun",
      position: [-0.6, 0, -0.9],
      rotationY: -0.6,
      focusDistance: 4.4,
      hotspotY: 2.2,
      ringRadius: 1.5,
    },
    {
      id: "obj-pallet",
      shape: "pallet",
      headword: "pallet",
      partOfSpeech: "noun",
      position: [2.4, 0, 0.8],
      rotationY: 0.35,
      focusDistance: 2.8,
      hotspotY: 0.8,
      ringRadius: 1.0,
    },
    {
      id: "obj-consignment",
      shape: "consignment-crate",
      headword: "consignment",
      partOfSpeech: "noun",
      // Dịch ra sau-trái so với spec: ở góc nhìn đầu, nhãn của nó đè đúng giữa
      // nhãn `forklift` và ăn mất cú bấm (test "mọi hotspot đều bấm được").
      position: [-3.1, 0, 2.7],
      rotationY: 0.2,
      focusDistance: 3.4,
      hotspotY: 1.9,
      ringRadius: 1.1,
    },
    {
      id: "obj-courier",
      shape: "courier-van",
      headword: "courier",
      partOfSpeech: "noun",
      position: [5.2, 0, 4.2],
      patrol: { axis: "x", range: 4.5, speed: 0.9 },
      focusDistance: 5,
      hotspotY: 2.4,
      ringRadius: 1.9,
    },
    {
      id: "obj-clipboard",
      shape: "clipboard",
      headword: "tracking number",
      partOfSpeech: "noun",
      position: [6.4, 0, -1.4],
      /* 0.3 = hướng camera mặc định: phiếu kiểm kê quay mặt về nơi người học
         đứng, để ngược thì chỉ thấy tấm bảng nâu. */
      rotationY: 0.3,
      focusDistance: 2.8,
      hotspotY: 2.0,
      ringRadius: 0.9,
    },
    {
      id: "obj-manager",
      shape: "warehouse-manager",
      headword: "warehouse manager",
      partOfSpeech: "noun",
      // Đi tuần ngang giữa sân tây (x −3.6..−2.2): cách càng forklift ~1 m,
      // consignment 2.8 m. Nhãn trạm nào cũng có hàng xóm trong tầm 2 m nên
      // vị trí neo tính bằng projection màn hình từ camera đầu, không đo
      // khoảng cách thế giới mà đoán.
      // Có `patrol` nên `rotationY` vô nghĩa.
      position: [-2.9, 0, -0.6],
      patrol: { axis: "x", range: 0.7, speed: 0.45 },
      focusDistance: 4,
      hotspotY: 2.9,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-cargo",
      shape: "cargo-stack",
      headword: "cargo",
      partOfSpeech: "noun",
      // Đông-nam kho: cách clipboard (6.4,−1.4) 4.2 m, mặt trước (z 2.2)
      // cách làn xe courier 1.5 m.
      position: [9.5, 0, 1.5],
      rotationY: -0.2,
      focusDistance: 4.5,
      hotspotY: 3.2,
      topY: 2.3,
      ringRadius: 1.8,
    },
    {
      id: "obj-freight",
      shape: "freight-truck",
      headword: "freight",
      partOfSpeech: "noun",
      // Xe tải đỗ dọc lề tây (z 3.6..5.6 nằm gọn trong đường 3.0..6.2):
      // xe ĐẬU trên đường là cố ý và đọc tự nhiên, còn container cũ nửa
      // nằm nửa ngoài đường nên đọc như đặt nhầm. Làn courier chỉ tới
      // x 0.7, cách đầu xe (−3.7) 4.4 m nên không bao giờ chạm.
      position: [-6.0, 0, 4.6],
      focusDistance: 7,
      hotspotY: 3.75,
      topY: 2.85,
      ringRadius: 3.0,
    },
    {
      id: "obj-store",
      shape: "storage-rack",
      headword: "store",
      partOfSpeech: "verb",
      // Kệ đông sân: cách clipboard 2.7 m, pallet ~2 m, làn courier 1.4 m
      // (đo mép mesh). Nhãn đứng dưới-trái nhãn bến, đủ hở tâm theo trục
      // nhìn đông-nam (tính bằng projection, không đoán bằng mắt).
      position: [6.0, 0, 1.8],
      rotationY: 0.2,
      focusDistance: 4,
      hotspotY: 3.7,
      topY: 2.8,
      ringRadius: 1.8,
    },
    {
      id: "obj-dispatch-note",
      shape: "dispatch-note",
      headword: "dispatch note",
      partOfSpeech: "noun",
      // Kiện + phiếu khổ lớn bên kia đường (đông-nam): vừa lấp khoảng trống
      // nam đường, vừa tách khỏi chùm nhãn sân chính. z 7.3 để vào gọn
      // khung hình camera đầu (z 8.5 là nửa kiện ra ngoài mép dưới).
      // Cách làn courier 2 m, cargo 5.8 m.
      position: [10.0, 0, 7.3],
      rotationY: -0.3,
      focusDistance: 3.5,
      hotspotY: 2.25,
      topY: 1.35,
      ringRadius: 1.4,
    },
    {
      id: "obj-fragile",
      shape: "fragile-box",
      headword: "fragile",
      partOfSpeech: "adjective",
      // Kiện dễ vỡ bên kia đường (tây-nam): tem FRAGILE + ly nứt quay về
      // camera (mặt +Z, yaw 0.3). Lùi ra x −7.3 cho tia nhìn tới nhãn lọt
      // qua hông mái kho phụ (giữa tuyệt đối là mái chôn nhãn). Cách đuôi
      // xe tải 2.45 m theo trục z.
      position: [-7.3, 0, 8.5],
      rotationY: 0.3,
      focusDistance: 3,
      hotspotY: 1.8,
      topY: 0.9,
      ringRadius: 1.1,
    },
  ],
};
