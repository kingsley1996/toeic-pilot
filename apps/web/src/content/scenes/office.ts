import type { SceneDef } from "@/content/scenes/types";

/**
 * Văn phòng mở: sáng thứ Hai, 8 giờ (đồng hồ chỉ đúng 8h) — nhóm personnel
 * quẹt máy attendance vào ca theo bảng shift, intern ôm hồ sơ, supervisor
 * đi tuần giám sát, candidate chờ ở lễ tân để interview.
 *
 * Neo nhãn tính bằng projection màn hình từ camera đầu (kỹ thuật warehouse):
 * góc đông-nam nén cả dãy tây-bắc vào một cột, đo khoảng cách thế giới
 * không thấy chồng nhãn. Hai vật patrol (supervisor, intern, personnel)
 * nằm ngoài luật "mọi hotspot đều bấm được" một cách chủ ý — pill của nó
 * `pointer-events-none`, bấm vào thân vẫn ăn.
 */
export const officeScene: SceneDef = {
  id: "office-01",
  title: "Văn phòng mở",
  description:
    "Buổi sáng trong văn phòng — lễ tân đón khách, nhóm làm việc quanh bảng trắng và mọi bảng tin trên tường.",
  topicSlug: "office",
  sky: "#e8eaec",
  environment: "office-floor",
  // Phòng rộng 26 m mà dùng home mặc định là đồ xa dồn thành chùm —
  // camera riêng tiến vào tây-nam + nhìn chếch bắc để chùm tây-bắc tách ra
  // (đã quét 4 home, chỉ home này là 21 nhãn đều hở tâm).
  home: { pos: [6, 9, 15], look: [-1.5, 1, -3] },
  badges: ["new", "beta"],
  objects: [
    {
      id: "obj-reception",
      shape: "reception-desk",
      headword: "reception",
      partOfSpeech: "noun",
      // Giữa quầy theo trục vách logo (logo x 0.15..3.85, tâm x = 2) —
      // quầy đón chính giữa dưới logo mới đúng bố cục lễ tân.
      position: [2, 0, -7.2],
      focusDistance: 4,
      hotspotY: 2.1,
      topY: 1.2,
      ringRadius: 1.8,
    },
    {
      id: "obj-directory",
      shape: "directory-board",
      headword: "directory",
      partOfSpeech: "noun",
      // Tường bắc, tây nhất trong 4 bảng tường.
      position: [-9.5, 0, -9.6],
      focusDistance: 4,
      hotspotY: 3.1,
      topY: 2.2,
      ringRadius: 1.4,
    },
    {
      id: "obj-badge",
      shape: "badge-stand",
      headword: "badge",
      partOfSpeech: "noun",
      // Thẻ khách lấy ở cửa kính lối vào (đúng đời thực: quẹt máy + lấy
      // thẻ rồi mới vào gặp lễ tân) — tây cửa, cách trụ 1.6 m, làn
      // personnel 2 m. (Bản cạnh quầy là cùng tia nhìn với payroll.)
      position: [1.0, 0, 6.5],
      focusDistance: 3,
      hotspotY: 2.8,
      topY: 1.9,
      ringRadius: 1.0,
    },
    {
      id: "obj-appointment",
      shape: "appointment-calendar",
      headword: "appointment",
      partOfSpeech: "noun",
      // Giá chữ A đứng phía đông — lịch tháng + 1 ô khoanh đỏ. Xuống đất
      // vì tường bắc hết chỗ: đứng cạnh evaluation là pill dài của lịch
      // đè lên memo. Cách collaborate 2 m, máy attendance 5 m.
      position: [10.5, 0, -1.0],
      focusDistance: 3,
      hotspotY: 3.15,
      topY: 2.25,
      ringRadius: 1.0,
    },
    {
      id: "obj-punctual",
      shape: "punctual-clock",
      headword: "punctual",
      partOfSpeech: "adjective",
      // Treo cao tường bắc giữa directory và logo (kim chỉ 8h đúng) —
      // nhãn cao nhất cảnh. (Bản giữa directory là cùng tia nhìn với nó.)
      position: [-3.5, 0, -9.6],
      focusDistance: 5,
      hotspotY: 4.1,
      topY: 3.2,
      ringRadius: 1.2,
    },
    {
      id: "obj-cabinet",
      shape: "office-cabinet",
      headword: "cabinet",
      partOfSpeech: "noun",
      // Áp tường tây quay mặt +X vào phòng (`rotationY` π/2 — sâu 0.6
      // thành mặt 0.9): lưng cách tường 0.15 m, cách bảng shift 1 m theo z.
      position: [-12.4, 0, -7.5],
      rotationY: Math.PI / 2,
      focusDistance: 3.5,
      hotspotY: 2.35,
      topY: 1.45,
      ringRadius: 1.2,
    },
    {
      id: "obj-stationery",
      shape: "stationery-shelf",
      headword: "stationery",
      partOfSpeech: "noun",
      // Áp tường tây quay mặt +X vào phòng (`rotationY` π/2 — sâu 0.5
      // thành mặt 1.4): lưng cách tường 0.15 m, cách bảng shift 2.5 m.
      // Nhãn treo 2.7 (mũi tên dài) cho thoát khỏi nhãn extension cùng cột.
      position: [-12.45, 0, -1.0],
      rotationY: Math.PI / 2,
      focusDistance: 3.5,
      hotspotY: 2.7,
      topY: 1.4,
      ringRadius: 1.2,
    },
    {
      id: "obj-extension",
      shape: "extension-phone",
      headword: "extension",
      partOfSpeech: "noun",
      // Ô cubicle 1 (x −10.75..−8): bàn ở −9.4 cho lọt ô. Nhãn treo 2.6
      // (mũi tên dài kiểu crosswalk) để tách khỏi nhãn revise cùng hàng.
      position: [-9.4, 0, -2.2],
      focusDistance: 3.5,
      hotspotY: 2.6,
      topY: 1.45,
      ringRadius: 1.4,
    },
    {
      id: "obj-payroll",
      shape: "payroll-set",
      headword: "payroll",
      partOfSpeech: "noun",
      // Trong phòng payroll riêng góc đông-nam (tường bắc z = 3, tường tây
      // x = 9, mở hướng nam ra cửa kính) — bàn quay mặt +Z ra lối vào.
      // Cách tường bắc 0.9 m, tường tây 1.25 m, tường đông 1.2 m. Lùi bắc
      // cho nhãn khỏi lọt mép dưới khung camera riêng.
      position: [11.0, 0, 4.3],
      focusDistance: 3,
      hotspotY: 1.95,
      topY: 1.05,
      ringRadius: 1.0,
    },
    {
      id: "obj-shift",
      shape: "shift-board",
      headword: "shift",
      partOfSpeech: "noun",
      // Treo tường tây quay mặt +X vào phòng (`rotationY` π/2) — lưới ca
      // Sáng/Chiều/Đêm, khác danh bạ ở cấu trúc ô. Đặt giữa hai món tây
      // (tủ/kệ) để nhãn tách cả hai theo trục đứng.
      position: [-12.55, 0, -3.5],
      rotationY: Math.PI / 2,
      focusDistance: 4,
      hotspotY: 3.05,
      topY: 2.15,
      ringRadius: 1.4,
    },
    {
      id: "obj-memo",
      shape: "memo-board",
      headword: "memo",
      partOfSpeech: "noun",
      // Tường bắc — nhiều note màu ghim bảng ("tin dán"), khác revise
      // 1 tờ nằm bàn. Lùi tây nhường chỗ cho loa notify.
      position: [5.9, 0, -9.6],
      focusDistance: 4,
      hotspotY: 3.0,
      topY: 2.1,
      ringRadius: 1.4,
    },
    {
      id: "obj-attendance",
      shape: "attendance-recorder",
      headword: "attendance",
      partOfSpeech: "noun",
      // Đứng cạnh cửa kính lối vào phía nam (trụ đông x = 5.0): máy quay
      // mặt +Z đón khách bước vào. Lùi bắc 1 m cho nhãn khỏi lọt mép dưới
      // khung camera riêng. Cách cánh kính 0.9 m, làn personnel 2.6 m.
      position: [6.0, 0, 6.8],
      focusDistance: 3,
      hotspotY: 2.4,
      topY: 1.5,
      ringRadius: 1.0,
    },
    {
      id: "obj-revise",
      shape: "revise-set",
      headword: "revise",
      partOfSpeech: "verb",
      // Ô cubicle 2 (x −8..−5.25): bàn ở −6.6 cho lọt ô, cách vách 0.35 m.
      position: [-6.6, 0, -2.2],
      focusDistance: 3.5,
      hotspotY: 1.8,
      topY: 0.9,
      ringRadius: 1.4,
    },
    {
      id: "obj-evaluation",
      shape: "evaluation-board",
      headword: "evaluation",
      partOfSpeech: "noun",
      // Tường bắc đầu đông (sát góc, tường tới x = 13) — giấy lớn +
      // checkbox + ✓ đỏ, khác 3 bảng còn lại.
      position: [11.5, 0, -9.6],
      focusDistance: 4,
      hotspotY: 3.15,
      topY: 2.25,
      ringRadius: 1.2,
    },
    {
      id: "obj-notify",
      shape: "notify-speaker",
      headword: "notify",
      partOfSpeech: "verb",
      // Treo cao tường bắc giữa logo và memo — "cái phát thông báo",
      // khác điện thoại bàn ở cao độ + hướng phát. Nhãn cao nhì cảnh
      // sau đồng hồ. (Bản đầu đông là nhãn lọt khỏi khung hình.)
      position: [4.3, 0, -9.6],
      focusDistance: 4,
      hotspotY: 4.0,
      topY: 3.1,
      ringRadius: 1.0,
    },
    {
      id: "obj-supervisor",
      shape: "supervisor",
      headword: "supervisor",
      partOfSpeech: "noun",
      // Đi tuần ngang giữa phòng (x −4..0) — đúng nghĩa "giám sát": đi mới
      // thấy hết việc. Có `patrol` nên `rotationY` vô nghĩa; nhãn chạy
      // `pointer-events-none` nên nằm ngoài luật hotspot đứng yên.
      position: [-2, 0, 0.5],
      patrol: { axis: "x", range: 2, speed: 0.45 },
      focusDistance: 4,
      hotspotY: 2.9,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-intern",
      shape: "intern",
      headword: "intern",
      partOfSpeech: "noun",
      // Ôm hồ sơ chạy việc làn nam (z = 2.5), cách làn supervisor 2 m,
      // cách bàn revise 4.7 m. Cùng tốc độ museum (0.5).
      position: [-4, 0, 2.5],
      patrol: { axis: "x", range: 2.5, speed: 0.5 },
      focusDistance: 4,
      hotspotY: 2.9,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-candidate",
      shape: "candidate",
      headword: "candidate",
      partOfSpeech: "noun",
      // Ôm folder chờ giữa phòng (nam ô cubicle, cách vách 0.5 m) — mắt
      // vẫn nối sang cụm interview. Mặt +X về phía quầy. Lùi nam cho nhãn
      // thoát khỏi chùm tường bắc.
      // Cách bàn revise 1.7 m theo z, làn intern 1.15 m.
      position: [-7.0, 0, 0.8],
      focusDistance: 4,
      hotspotY: 2.65,
      topY: 1.75,
      ringRadius: 1.2,
    },
    {
      id: "obj-interview",
      shape: "interview",
      headword: "interview",
      partOfSpeech: "verb",
      // Giữa-đông: bàn tròn + 2 người đối mặt. Dời nam khỏi reception cho
      // nhãn tách hàng (trục nhìn đông-nam). Cách cụm collaborate 1 m.
      position: [4.2, 0, 0.3],
      focusDistance: 4.5,
      hotspotY: 2.9,
      topY: 1.75,
      ringRadius: 2.0,
    },
    {
      id: "obj-personnel",
      shape: "personnel-team",
      headword: "personnel",
      partOfSpeech: "noun",
      // Đội 3 người đi làn nam (x −0.2..4.2): cùng patrol là cùng pha giữ
      // đội hình (idiom tour museum). Cách cụm interview 2.1 m theo z,
      // cách collaborate 1.6 m theo x.
      position: [2, 0, 4.0],
      patrol: { axis: "x", range: 2.2, speed: 0.5 },
      focusDistance: 5,
      hotspotY: 2.9,
      topY: 1.75,
      ringRadius: 2.2,
    },
    {
      id: "obj-collaborate",
      shape: "collaborate",
      headword: "collaborate",
      partOfSpeech: "verb",
      // Đông phòng: bảng trắng + 2 người cùng phía nhìn vào bảng (không
      // bàn, cùng hướng — ngược với interview). Mặt bảng +Z về camera.
      position: [7.5, 0, 0.5],
      focusDistance: 4.5,
      hotspotY: 2.75,
      topY: 1.85,
      ringRadius: 2.0,
    },
  ],
};
