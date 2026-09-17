import type { SceneDef } from "@/content/scenes/types";

/**
 * Phòng trưng bày bảo tàng (`planning/scenes/museum-3d-scene-spec.md`).
 * Tường bắc là object `gallery-wall` ở z = −12 (mặt nam z = −11.8) — mọi vật
 * treo tường (painting/mural/placard/spotlight) đặt KHỚP mặt này. Bệ trung tâm
 * [0, −4]: pedestal + sculpture + stanchion chồng tâm nên nhãn tách theo cao
 * độ, riêng stanchion đặt def ở cọc góc cho khỏi đè nhãn bệ.
 *
 * Headword lấy theo cột Term của spec (ưu tiên cụm đầu; `pamphlet` và
 * `admission ticket` lấy cụm sau vì `brochure`/`ticket` đã có nghĩa khác
 * trong kho — unique theo cặp (headword, pos)). Topic `museum` đang
 * nhập qua pipeline — từ nào chưa published thì banner đỏ tới khi pipeline
 * xong, không âm thầm ẩn hotspot (§2.3). `turnstile` published nhưng không
 * hotspot (tiền lệ `demolish` ở construction): bỏ khỏi cảnh cho đỡ chật cửa
 * mà không xoá từ trong DB.
 */
export const museumScene: SceneDef = {
  id: "museum-tour-01",
  title: "Bảo tàng và triển lãm",
  description:
    "Phòng trưng bày nhộn nhịp — hướng dẫn viên đang thuyết minh bên tượng, khách đeo tai nghe và tủ kính đựng hiện vật.",
  topicSlug: "museum",
  sky: "#d9d2c2",
  environment: "museum-hall",
  badges: ["new", "beta"],
  home: { pos: [13, 11, 15], look: [0, 1.8, 0] },
  objects: [
    {
      id: "obj-museum",
      shape: "museum",
      headword: "museum",
      partOfSpeech: "noun",
      // Cổng tân cổ điển ở nam, lệch khỏi trục nhìn chính nên không che phòng.
      position: [0, 0, 12.5],
      focusDistance: 12,
      hotspotY: 7.3,
      topY: 6.45,
      ringRadius: 4,
    },
    {
      id: "obj-gallery-wall",
      shape: "gallery-wall",
      headword: "gallery wall",
      partOfSpeech: "noun",
      position: [0, 0, -12],
      focusDistance: 14,
      hotspotY: 5.9,
      topY: 5,
      ringRadius: 6,
    },
    {
      id: "obj-painting",
      shape: "painting",
      headword: "painting",
      partOfSpeech: "noun",
      // Áp mặt nam tường (z = −11.8), khung lố ra −11.64.
      position: [-5, 0, -11.7],
      focusDistance: 6,
      hotspotY: 4.8,
      topY: 3.9,
      ringRadius: 2,
    },
    {
      id: "obj-mural",
      shape: "mural",
      headword: "mural",
      partOfSpeech: "noun",
      position: [5.5, 0, -11.72],
      focusDistance: 7,
      hotspotY: 5.0,
      topY: 4.1,
      ringRadius: 3.5,
    },
    {
      id: "obj-placard",
      shape: "placard",
      headword: "placard",
      partOfSpeech: "noun",
      position: [-2.6, 0, -11.7],
      focusDistance: 3.5,
      hotspotY: 2.95,
      topY: 2.1,
      ringRadius: 1.2,
    },
    {
      id: "obj-archway",
      shape: "archway",
      headword: "archway",
      partOfSpeech: "noun",
      // Đầu tây tường (tường trải x −9..9), lấp khoảng hở tới tường hông.
      position: [-11.5, 0, -12],
      focusDistance: 6,
      hotspotY: 4.65,
      topY: 3.8,
      ringRadius: 2.5,
    },
    {
      id: "obj-exit",
      shape: "exit",
      headword: "emergency exit",
      partOfSpeech: "noun",
      // Đầu đông tường, cạnh guard.
      position: [11.5, 0, -12],
      focusDistance: 5,
      hotspotY: 4.0,
      topY: 3.15,
      ringRadius: 1.8,
    },
    {
      id: "obj-spotlight",
      shape: "spotlight",
      headword: "spotlight",
      partOfSpeech: "noun",
      // Ray trên tường giữa tranh và bảng tin — nhãn cách nhãn tranh 2 m.
      position: [-3, 0, -11.2],
      focusDistance: 6,
      hotspotY: 5.9,
      topY: 5,
      ringRadius: 2.5,
    },
    {
      id: "obj-restoration",
      shape: "restoration",
      headword: "restoration",
      partOfSpeech: "noun",
      // Giá vẽ quay mặt vào phòng, curator đứng trước chếch tây.
      position: [5.5, 0, -8.5],
      focusDistance: 4,
      hotspotY: 2.8,
      topY: 1.9,
      ringRadius: 1.6,
    },
    {
      id: "obj-pedestal",
      shape: "pedestal",
      headword: "pedestal",
      partOfSpeech: "noun",
      // Tây thảm cho khỏi chắn lối đi — cả cụm (bệ/tượng/dây) cùng tâm này.
      // Def lệch tây khỏi bệ để nhãn khỏi đè tượng (thân lùi đông trong
      // shape); zoom vào tâm bệ qua `focus`.
      position: [-5.7, 0, -5],
      focus: [-4.5, 0, -5],
      focusDistance: 4,
      hotspotY: 2.1,
      topY: 1.22,
      ringRadius: 1.6,
    },
    {
      id: "obj-sculpture",
      shape: "sculpture",
      headword: "sculpture",
      partOfSpeech: "noun",
      // Gốc nhóm trên mặt bệ (y = 1.1) — shape mang cao độ. Nhãn cao hơn
      // nhãn bệ 1 m để bấm phân biệt được.
      position: [-4.5, 1.1, -5],
      focusDistance: 4,
      hotspotY: 2.0,
      topY: 1.15,
      ringRadius: 1.2,
    },
    {
      id: "obj-stanchion",
      shape: "stanchion",
      headword: "stanchion",
      partOfSpeech: "noun",
      // Def ở cọc góc tây-nam của cụm mới (tâm [−4.5, −5]) — góc đông-nam
      // nằm dưới làn guide đi tuần (wrapper drei vẫn nuốt click dù nút
      // pointer-events-none). Vòng sáng vẫn chạm bệ giữa.
      position: [-6.3, 0, -3.2],
      focusDistance: 5,
      hotspotY: 1.8,
      topY: 0.95,
      ringRadius: 2.6,
    },
    {
      id: "obj-display-case",
      shape: "display-case",
      headword: "display case",
      partOfSpeech: "noun",
      position: [-6, 0, -1],
      focusDistance: 4.5,
      hotspotY: 3.3,
      topY: 2.4,
      ringRadius: 1.8,
    },
    {
      id: "obj-artifact",
      shape: "artifact",
      headword: "artifact",
      partOfSpeech: "noun",
      // Bình gốm TRONG tủ (gốc nhóm trên mặt đế y = 0.9); def lệch đông cho
      // khỏi đè nhãn tủ (thân lùi tây trong shape), zoom vào bình qua `focus`.
      position: [-4.7, 0.9, -1],
      focus: [-6, 0.9, -1],
      focusDistance: 4.5,
      hotspotY: 3.8,
      topY: 0.85,
      ringRadius: 1.4,
    },
    {
      id: "obj-guide",
      shape: "guide",
      headword: "tour guide",
      partOfSpeech: "noun",
      // Đi tuần cùng nhịp với cả nhóm khách (cùng patrol là cùng pha —
      // `Mover` khởi động đồng bộ). Có patrol thì `rotationY` vô nghĩa.
      position: [-2.4, 0, -2.2],
      patrol: { axis: "x", range: 2, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-visitor",
      shape: "visitor",
      headword: "visitor",
      partOfSpeech: "noun",
      // Đầu tây vòng cung khán giả, đi cùng nhịp guide.
      position: [-3.7, 0, 0.6],
      patrol: { axis: "x", range: 2, speed: 0.5 },
      focusDistance: 5,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 2.2,
    },
    {
      id: "obj-audio-guide",
      shape: "audio-guide",
      headword: "audio guide",
      partOfSpeech: "noun",
      // Đầu đông vòng cung, đi cùng nhịp guide.
      position: [-0.6, 0, 1.6],
      patrol: { axis: "x", range: 2, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.7,
      topY: 1.8,
      ringRadius: 1.2,
    },
    {
      id: "obj-brochure",
      shape: "brochure",
      headword: "pamphlet",
      partOfSpeech: "noun",
      // Ngoài vòng cung phía đông-nam, đi cùng nhịp guide.
      position: [1.2, 0, 2.2],
      patrol: { axis: "x", range: 2, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-ticket",
      shape: "ticket",
      headword: "admission ticket",
      partOfSpeech: "noun",
      // Khách đang bước vào cửa, vé trên tay.
      position: [4.5, 0, 7.5],
      patrol: { axis: "x", range: 1.5, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-curator",
      shape: "curator",
      headword: "curator",
      partOfSpeech: "noun",
      // Trước giá vẽ, đi tới lui ngắm tranh đang sửa.
      position: [4, 0, -7.2],
      patrol: { axis: "x", range: 0.8, speed: 0.4 },
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-guard",
      shape: "guard",
      headword: "security guard",
      partOfSpeech: "noun",
      // Đi tuần dọc hông đông, giữa cửa thoát hiểm và giá vẽ.
      position: [9, 0, -7.5],
      patrol: { axis: "z", range: 2, speed: 0.4 },
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-bench",
      shape: "bench",
      headword: "bench",
      partOfSpeech: "noun",
      // Dọc mép đông thảm (không chắn lối): dài theo trục Z.
      position: [3.5, 0, 4],
      rotationY: Math.PI / 2,
      focusDistance: 5,
      hotspotY: 1.4,
      topY: 0.53,
      ringRadius: 1.8,
    },
    {
      id: "obj-kiosk",
      shape: "kiosk",
      headword: "interactive kiosk",
      partOfSpeech: "noun",
      // Màn hình xoay sẵn về −X (giữa phòng) trong shape.
      position: [8, 0, 3],
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.7,
      ringRadius: 1.4,
    },
    {
      id: "obj-donation-box",
      shape: "donation-box",
      headword: "donation box",
      partOfSpeech: "noun",
      position: [-4.5, 0, 8.5],
      focusDistance: 3.5,
      hotspotY: 2.4,
      topY: 1.55,
      ringRadius: 1.2,
    },
    {
      id: "obj-cloakroom",
      shape: "cloakroom",
      headword: "cloakroom",
      partOfSpeech: "noun",
      // Áp tường tây (x = −14), quầy lố tới −12.2.
      position: [-11, 0, 3],
      focusDistance: 5,
      hotspotY: 2.9,
      topY: 2,
      ringRadius: 2.2,
    },
    {
      id: "obj-souvenir",
      shape: "souvenir",
      headword: "souvenir",
      partOfSpeech: "noun",
      position: [11, 0, 3],
      focusDistance: 5,
      hotspotY: 2.45,
      topY: 1.6,
      ringRadius: 2,
    },
    {
      id: "obj-exhibit",
      shape: "exhibit",
      headword: "exhibit",
      partOfSpeech: "noun",
      // Panô áp tường tây (mặt +X vào phòng), lưng cách tường 0.5 m.
      position: [-13.2, 0, 6.5],
      rotationY: Math.PI / 2,
      focusDistance: 4,
      hotspotY: 3.1,
      topY: 2.25,
      ringRadius: 1.5,
    },
  ],
};
