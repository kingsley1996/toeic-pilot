import type { SceneDef } from "@/content/scenes/types";

/**
 * Công viên (topic `park`, 23 từ — 20 nhập mới qua pipeline + bench/hedge/
 * lamppost gắn lại từ topic cũ).
 *
 * Bố cục nam→bắc: cổng (z 12) → lối đi → quảng trường đài phun (z −1) → hồ
 * phía bắc (z −11). Đông là ao + cầu + khu vui chơi, tây là vườn hoa + chòi +
 * thảm picnic. `bench`/`lamppost`/`hedge` dùng lại shape của museum/urban/
 * residence nên def theo đúng hướng gốc của chúng (bench dài X, lamppost tay
 * Z, hedge dài Z).
 *
 * Hai cặp chồng tâm tách nhãn theo cao độ (mẫu pedestal/sculpture): bridge
 * bay trên pond, picnic ngồi trên lawn. Mũi tên nào cũng dư 0.05 trên 0.8
 * (§9.9: 0.8 đúng boong là float thành 0.7999 và mất mũi tên).
 */
export const parkScene: SceneDef = {
  id: "park-grounds-01",
  title: "Công viên xanh",
  description:
    "Công viên nhộn nhịp — đài phun giữa quảng trường, cầu cong qua ao, trẻ em chơi xích đu và người bán bóng bay dọc lối đi.",
  topicSlug: "park",
  sky: "#cfe4ef",
  environment: "park-grounds",
  badges: ["new", "beta"],
  // Từ nam hơi cao nhìn chếch bắc: cổng gần, hồ xa, cụm đông/tây tách hai bên.
  home: { pos: [4, 13, 24], look: [-1, 1.5, -3] },
  objects: [
    {
      id: "obj-gate",
      shape: "gate",
      headword: "gate",
      partOfSpeech: "noun",
      // Cổng nam, khoảng trống rào x ±3 — hai cánh mở vào trong.
      position: [0, 0, 12],
      focusDistance: 10,
      hotspotY: 4.6,
      topY: 3.65,
      ringRadius: 3.5,
    },
    {
      id: "obj-statue",
      shape: "statue",
      headword: "statue",
      partOfSpeech: "noun",
      // Tây cổng, né cánh cổng mở (x −3.2) 1 m.
      position: [-4.5, 0, 10.5],
      focusDistance: 6,
      hotspotY: 3.6,
      topY: 2.7,
      ringRadius: 1.8,
    },
    {
      id: "obj-lamppost",
      shape: "lamppost",
      headword: "lamppost",
      partOfSpeech: "noun",
      // Đông lối đi (lối rộng x ±1.1), tay đèn sẵn theo Z song song lối.
      // Lùi khỏi làn người bán bóng (x 2.0) cho khỏi bị đi xuyên cột.
      position: [3.2, 0, 9],
      focusDistance: 7,
      hotspotY: 5.4,
      topY: 4.5,
      ringRadius: 2,
    },
    {
      id: "obj-path",
      shape: "path",
      headword: "path",
      partOfSpeech: "noun",
      // Giữa lối từ cổng tới đài phun (tấm z −1..11, nhãn giữa tấm).
      // Vật bẹt: nhãn ôm mặt, không mũi tên.
      position: [0, 0, 5],
      focusDistance: 9,
      hotspotY: 0.9,
      ringRadius: 5,
    },
    {
      id: "obj-fountain",
      shape: "fountain",
      headword: "fountain",
      partOfSpeech: "noun",
      // Tâm quảng trường, tia nước lên y 4.
      position: [0, 0, -1],
      focusDistance: 10,
      hotspotY: 5.0,
      topY: 4.0,
      ringRadius: 3,
    },
    {
      id: "obj-sundial",
      shape: "sundial",
      headword: "sundial",
      partOfSpeech: "noun",
      // Đông đài phun, cách mép bể 2 m.
      position: [4.5, 0, 0.5],
      focusDistance: 4,
      hotspotY: 2.3,
      topY: 1.4,
      ringRadius: 1.4,
    },
    {
      id: "obj-bench",
      shape: "bench",
      headword: "bench",
      partOfSpeech: "noun",
      // Tây đài phun ngắm nước (shape dài X, không cần xoay).
      position: [-4.8, 0, 1],
      focusDistance: 4,
      hotspotY: 1.4,
      topY: 0.53,
      ringRadius: 1.8,
    },
    {
      id: "obj-lantern",
      shape: "lantern",
      headword: "lantern",
      partOfSpeech: "noun",
      // Tây lối đi, đối xứng lamppost bên kia.
      position: [-2.5, 0, 6],
      focusDistance: 4,
      hotspotY: 2.6,
      topY: 1.65,
      ringRadius: 1.2,
    },
    {
      id: "obj-flowerbed",
      shape: "flowerbed",
      headword: "flowerbed",
      partOfSpeech: "noun",
      // Luống dài X trong vườn tây.
      position: [-8.5, 0, 3],
      focusDistance: 5,
      hotspotY: 1.8,
      topY: 0.9,
      ringRadius: 2.2,
    },
    {
      id: "obj-birdbath",
      shape: "birdbath",
      headword: "birdbath",
      partOfSpeech: "noun",
      // Góc vườn tây-bắc, gần luống hoa cho chim có chỗ đậu.
      position: [-6.5, 0, -3.5],
      focusDistance: 4,
      hotspotY: 2.2,
      topY: 1.3,
      ringRadius: 1.2,
    },
    {
      id: "obj-pond",
      shape: "pond",
      headword: "pond",
      partOfSpeech: "noun",
      // Mép tây-nam ao — cầu chiếm giữa ao nên nhãn ra mép cho khỏi đè.
      // Mặt nước bẹt: nhãn ôm mặt, không mũi tên.
      position: [5, 0, -3.8],
      focus: [7, 0.2, -5],
      focusDistance: 7,
      hotspotY: 1.1,
      ringRadius: 3,
    },
    {
      id: "obj-bridge",
      shape: "bridge",
      headword: "bridge",
      partOfSpeech: "noun",
      // Vòm 6 m bắc qua ao theo trục X, hai trụ đá đứng trên bờ (x ±2.9).
      position: [7, 0, -5],
      focusDistance: 8,
      hotspotY: 3.2,
      topY: 2.35,
      ringRadius: 3.5,
    },
    {
      id: "obj-lake",
      shape: "lake",
      headword: "lake",
      partOfSpeech: "noun",
      // Mặt nước lớn phía bắc, bến chìa về phía quảng trường.
      // Vật bẹt: nhãn ôm mặt.
      position: [-3, 0, -11],
      focusDistance: 11,
      hotspotY: 1.1,
      ringRadius: 4.5,
    },
    {
      id: "obj-gazebo",
      shape: "gazebo",
      headword: "gazebo",
      partOfSpeech: "noun",
      // Tây-bắc nhìn ra hồ, cách mép nước 1 m.
      position: [-11, 0, -7.5],
      focusDistance: 8,
      hotspotY: 5.4,
      topY: 4.45,
      ringRadius: 3,
    },
    {
      id: "obj-hammock",
      shape: "hammock",
      headword: "hammock",
      partOfSpeech: "noun",
      // Dọc biên tây giữa hai cụm cây decor. Đỉnh thật là bóng cọc
      // (1.56) nên topY 1.6 (2.4 − 1.6 = 0.8 đúng boong là mất mũi tên).
      position: [-12.5, 0, 1],
      focusDistance: 6,
      hotspotY: 2.5,
      topY: 1.6,
      ringRadius: 2.6,
    },
    {
      id: "obj-hedge",
      shape: "hedge",
      headword: "hedge",
      partOfSpeech: "noun",
      // Hàng cây biên tây (shape dài Z + người tỉa đầu nam), trong rào.
      position: [-13.5, 0, -3],
      focusDistance: 6,
      hotspotY: 2.0,
      topY: 1.0,
      ringRadius: 3,
    },
    {
      id: "obj-lawn",
      shape: "lawn",
      headword: "lawn",
      partOfSpeech: "noun",
      // Thảm tây-nam (x −10.5..−3.5, z 3..8) — picnic ngồi giữa thảm nên
      // nhãn lawn ra góc tây-bắc thảm cho khỏi đè.
      // Vật bẹt: nhãn ôm mặt.
      position: [-8.5, 0, 4],
      focus: [-7, 0, 5.5],
      focusDistance: 9,
      hotspotY: 1.0,
      ringRadius: 4,
    },
    {
      id: "obj-picnic",
      shape: "picnic",
      headword: "picnic",
      partOfSpeech: "noun",
      // Giữa thảm lawn (vệt đất canvas khớp điểm này), người dọn đứng cạnh.
      // Mũi tên xuống giỏ đồ giữa thảm (đỉnh giỏ 0.41) — đầu người đứng
      // lệch tâm nên không xuyên.
      position: [-5, 0, 7.5],
      focusDistance: 5,
      hotspotY: 2.2,
      topY: 0.5,
      ringRadius: 2,
    },
    {
      id: "obj-swing",
      shape: "swing",
      headword: "swing",
      partOfSpeech: "noun",
      // Khu vui chơi đông-nam, khung dài X.
      position: [9, 0, 6],
      focusDistance: 7,
      hotspotY: 3.8,
      topY: 2.85,
      ringRadius: 2.4,
    },
    {
      id: "obj-seesaw",
      shape: "seesaw",
      headword: "seesaw",
      partOfSpeech: "noun",
      // Tây xích đu, ván dài X, né làn người bán bóng (x 2.5) 1.4 m.
      // Đỉnh thật là tay cầm (1.65) nên nhãn lên 2.5.
      position: [5.5, 0, 9],
      focusDistance: 5,
      hotspotY: 2.5,
      topY: 1.65,
      ringRadius: 2,
    },
    {
      id: "obj-sandbox",
      shape: "sandbox",
      headword: "sandbox",
      partOfSpeech: "noun",
      // Đông-nam gần xích đu (vệt đất canvas khớp điểm này).
      // Vật bẹt: nhãn ôm mặt.
      position: [11.5, 0, 8.5],
      focusDistance: 5,
      hotspotY: 1.3,
      ringRadius: 1.8,
    },
    {
      id: "obj-kite",
      shape: "kite",
      headword: "kite",
      partOfSpeech: "noun",
      // Diều bay phía đông, dây thẳng xuống cuộn dây dưới đất.
      // Đỉnh thật 5.75 (chóp diều) nên topY 5.8, nhãn lên 6.65.
      position: [12, 0, -1],
      focusDistance: 8,
      hotspotY: 6.65,
      topY: 5.8,
      ringRadius: 1.5,
    },
    {
      id: "obj-balloon",
      shape: "balloon",
      headword: "balloon",
      partOfSpeech: "noun",
      // Người bán bóng đi dọc cỏ phía đông (x 5.5, z −2..8 — làn 10 m).
      // Không dùng vòng rect quanh đài phun: neo recall của rect là TÂM vòng
      // nên vào recall là đứng giữa bể nước, che đúng lúc quiz hỏi fountain.
      // Làn cũng phải NÉ pill tĩnh: wrapper drei của vật patrol phủ rộng hơn
      // chấm tròn, đi giữa cụm nhãn là thỉnh thoảng đè 4–5 hotspot cùng lúc
      // (dù click thật vẫn xuyên qua vì pointer-events-none, e2e đo bằng
      // elementFromPoint nên vẫn rớt).
      // Nhãn treo cao trên chùm bóng (quy ước vật patrol, §7.5).
      position: [5.5, 0, 3],
      patrol: { axis: "z", range: 5, speed: 0.5 },
      focusDistance: 5,
      hotspotY: 4.2,
      topY: 3.3,
      ringRadius: 1.5,
    },
  ],
};
