/**
 * Cảnh từ vựng 3D — định nghĩa sống ở đây, không ở database
 * (`SPEC-VISUAL-VOCAB-3D.md` §2.1). Vị trí object là thứ phải nhìn mà chỉnh,
 * nên vòng đời của nó là code review + deploy.
 *
 * Từ vựng KHÔNG được tham chiếu bằng UUID: UUID của dev và production là hai
 * vũ điệu khác nhau, còn cặp (headword, part_of_speech) là khoá duy nhất thật
 * của `vocabulary_entry`. Trang học resolve một lần bằng `?topic=<slug>` rồi
 * map client-side; từ nào resolve hỏng phải hiện ra trên trang, không được ẩn
 * hotspot âm thầm.
 */

/** Nhãn trạng thái của một cảnh, dịch sang chữ ở `learn/vocabulary/page.tsx`. */
export type SceneBadge = "new" | "beta";

export type ShapeKey =
  | "warehouse"
  | "depot"
  | "loading-bay"
  | "forklift"
  | "courier-van"
  | "pallet"
  | "consignment-crate"
  | "clipboard"
  // ngã tư đô thị (`urban_intersection_3d_scene_spec.md` §3)
  | "overpass"
  | "intersection"
  | "crosswalk"
  | "sidewalk"
  | "pavement"
  | "curb"
  | "curve"
  | "lane"
  | "billboard"
  | "signal"
  | "road-sign"
  | "lamppost"
  | "pedestrian";

/**
 * Nhịp đi–về quanh một điểm neo: `range` là nửa quãng đường (mét), `speed` là
 * m/giây ở giữa quãng (nhịp cos nên nó tự chậm lại ở hai đầu, không quay gập).
 * Một trục cộng một góc xoay là đủ cho cả hai cảnh — mọi tuyến ở đây đều thẳng.
 */
export interface Patrol {
  axis: "x" | "z";
  /** Xoay tuyến trong mặt phẳng nền — đại lộ của cảnh ngã tư chạy chéo, không
   *  chạy theo trục. Mặc định 0: tuyến song song với `axis`. */
  yaw?: number;
  range: number;
  speed: number;
}

export interface SceneObjectDef {
  id: string;
  shape: ShapeKey;
  /** Cặp khoá của `vocabulary_entry` — cả hai trường đều bắt buộc vì headword không duy nhất. */
  headword: string;
  partOfSpeech: string;
  position: [number, number, number];
  /**
   * Xe chạy: `position` là TRUNG ĐIỂM của tuyến, không phải chỗ nó đỗ. Camera
   * vẫn bay tới `position` nên `range` phải đủ ngắn để vật được chọn vẫn nằm
   * trong khung lúc người học đọc thẻ từ.
   */
  patrol?: Patrol;
  /**
   * Tính bằng radians; chỉ trục Y — các shape tự dựng không cần nghiêng.
   * Vật có `patrol` thì trường này vô nghĩa: hướng của nó do vận tốc quyết định.
   */
  rotationY?: number;
  scale?: number;
  /** Camera dừng cách đích ngần này (mét) khi object được chọn. */
  focusDistance: number;
  /** Độ cao của hotspot so với gốc group của object. */
  hotspotY: number;
  /**
   * Mặt trên của vật (mũi tên nhãn dừng ở đây, không xuyên xuống đất).
   * Thiếu thì 0.5 — vật thấp/bẹt không cần.
   */
  topY?: number;
  /** Bán kính vòng sáng dưới chân object khi được chọn. */
  ringRadius: number;
}

export interface SceneDef {
  id: string;
  title: string;
  description: string;
  /** Slug `topic` chứa toàn bộ từ của cảnh — nguồn resolve. */
  topicSlug: string;
  /** Nhãn trên card ở `/learn/vocabulary`. "beta" = cảnh chưa qua mắt người duyệt. */
  badges?: SceneBadge[];
  /** Màu nền canvas — 3D không ăn token CSS, đây là bảng màu riêng (`§2.2`). */
  sky: string;
  /** Nền cảnh: mặt đất + những thứ bối cảnh. Mỗi cảnh một bộ, không dùng lẫn. */
  environment: "warehouse-lot" | "urban-intersection";
  /**
   * Góc nhìn đầu của RIÊNG cảnh này. thiếu thì dùng mặc định của `SceneCanvas`.
   * Ngã tư đầy vật thể nhỏ hơn nhà kho nên cần khung hình chặt hơn.
   */
  home?: { pos: [number, number, number]; look: [number, number, number] };
  objects: SceneObjectDef[];
}

const warehouseScene: SceneDef = {
  id: "warehouse-01",
  title: "Trong nhà kho",
  description: "Kho hàng, bến dỡ hàng và đường ra — nơi logistics TOEIC sống.",
  topicSlug: "logistics",
  sky: "#e9edf0",
  environment: "warehouse-lot",
  badges: ["new"],
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
  ],
};

/**
 * Ngã tư: đại lộ dọc trục X (cong ở đầu tây), đường phụ dọc trục Z, cắt nhau
 * ở gốc. Toạ độ là số thế giới (arm0 trùng trục X nên along = x, across = z).
 * `signal`/biển đứng góc gần tâm chứ không cắm giữa đường như bảng spec.
 */
const urbanScene: SceneDef = {
  id: "urban-02",
  title: "Ngã tư thành phố",
  description: "Ngã tư cắt nhau ở giữa — cầu vượt nửa trái, đèn thành hàng, người đi trên vạch.",
  topicSlug: "urban-traffic",
  sky: "#dfe7ef",
  environment: "urban-intersection",
  badges: ["new", "beta"],
  home: { pos: [13.5, 11.5, 19.5], look: [0, 1, 0] },
  objects: [
    {
      id: "obj-intersection",
      shape: "intersection",
      headword: "intersection",
      partOfSpeech: "noun",
      position: [0, 0, 0],
      focusDistance: 13,
      hotspotY: 1.4,
      ringRadius: 6.4,
    },
    {
      id: "obj-overpass",
      shape: "overpass",
      headword: "overpass",
      partOfSpeech: "noun",
      // Nửa trái (x = -9), deck ngang đại lộ — trụ (±4) và chân cầu rớt đúng
      // vỉa hè hai bên, không cắm giữa nhựa.
      position: [-9, 0, 0],
      focusDistance: 13,
      hotspotY: 4.9,
      topY: 4,
      ringRadius: 6,
    },
    {
      id: "obj-crosswalk",
      shape: "crosswalk",
      headword: "crosswalk",
      partOfSpeech: "noun",
      // Ngang đại lộ phía đông (x = +5.5). Vạch trang trí trùng ở đây đã gỡ
      // trong `UrbanEnvironment`, không thì hai lớp vạch chồng nhau gây nháy.
      // Nhãn treo CAO (2.6 m): người đi bộ đi qua đúng chân vạch, nhãn thấp là
      // thân người che mất cú bấm (test "mọi hotspot đều bấm được" bắt được).
      position: [5.5, 0, 0],
      focusDistance: 6.5,
      hotspotY: 2.6,
      ringRadius: 4,
    },
    {
      id: "obj-lane",
      shape: "lane",
      headword: "lane",
      partOfSpeech: "noun",
      position: [12, 0, 0],
      focusDistance: 7,
      hotspotY: 0.9,
      ringRadius: 5,
    },
    {
      id: "obj-curb",
      shape: "curb",
      headword: "curb",
      partOfSpeech: "noun",
      position: [7, 0, 3.45],
      focusDistance: 5,
      hotspotY: 0.8,
      ringRadius: 3.4,
    },
    {
      id: "obj-curve",
      shape: "curve",
      headword: "curve",
      partOfSpeech: "noun",
      // Đầu tây, trên đoạn cong (phía gần camera). `CURVE_SEGS` tính toạ độ
      // tương đối từ đúng điểm này — dời def mà không dời OX/OZ bên kia là dải
      // cua lệch khỏi vạch.
      position: [-13, 0, 5.2],
      focusDistance: 9,
      hotspotY: 2.3,
      ringRadius: 5.5,
    },
    {
      id: "obj-sidewalk",
      shape: "sidewalk",
      headword: "sidewalk",
      partOfSpeech: "noun",
      position: [9, 0, 4.7],
      focusDistance: 7,
      hotspotY: 1.6,
      ringRadius: 3.6,
    },
    {
      id: "obj-pavement",
      shape: "pavement",
      headword: "pavement",
      partOfSpeech: "noun",
      position: [-9, 0, -4.7],
      focusDistance: 7,
      hotspotY: 1.4,
      ringRadius: 3.4,
    },
    {
      id: "obj-signal",
      shape: "signal",
      headword: "signal",
      partOfSpeech: "noun",
      // Góc đông-nam gần tâm, mặt quay về tâm (hướng +Z).
      position: [5.6, 0, -3.4],
      rotationY: -Math.PI / 2,
      focusDistance: 5.5,
      hotspotY: 3.7,
      topY: 2.7,
      ringRadius: 1.8,
    },
    {
      id: "obj-road-sign",
      shape: "road-sign",
      headword: "road sign",
      partOfSpeech: "noun",
      // Góc tây-bắc gần tâm, mặt quay RA NGOÀI (đón xe tới) — lộn nửa vòng
      // so với hướng vào tâm.
      position: [-5.6, 0, 3.4],
      rotationY: -Math.PI * 0.75,
      focusDistance: 5,
      hotspotY: 3,
      ringRadius: 1.6,
    },
    {
      id: "obj-lamppost",
      shape: "lamppost",
      headword: "lamppost",
      partOfSpeech: "noun",
      // Một trong ba đèn thành hàng ở mép bắc (z = 4.9).
      position: [5.2, 0, 4.9],
      focusDistance: 8,
      hotspotY: 4.7,
      ringRadius: 2,
    },
    {
      id: "obj-billboard",
      shape: "billboard",
      headword: "billboard",
      partOfSpeech: "noun",
      // Nhãn treo trên mặt bảng: tấm mặt tới 6.3 m sau scale (cao hơn nóc
      // khung 4.7 m), nhãn 5.2 m là lọt giữa mặt chữ.
      position: [11, 0, -5],
      rotationY: 0.1,
      focusDistance: 11,
      hotspotY: 6.8,
      topY: 6.3,
      ringRadius: 5,
    },
    {
      id: "obj-pedestrian",
      shape: "pedestrian",
      headword: "pedestrian",
      partOfSpeech: "noun",
      // Người đi BỘ qua đường trên vạch (giữa vạch, ngang đại lộ). `cross`
      // (động từ) đã bỏ: hai nhãn cho một người đi vừa thừa vừa chồng nhau —
      // từ trong DB giữ nguyên, chỉ mất hotspot như `underpass`.
      position: [5.5, 0, 0],
      patrol: { axis: "z", range: 3, speed: 0.55 },
      focusDistance: 5,
      hotspotY: 1.95,
      ringRadius: 1.2,
    },
  ],
};

export const SCENES: SceneDef[] = [warehouseScene, urbanScene];

export function getScene(id: string): SceneDef | undefined {
  return SCENES.find((scene) => scene.id === id);
}
