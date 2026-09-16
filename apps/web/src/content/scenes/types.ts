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
  | "pedestrian"
  // công trường xây dựng (topic `construction`)
  | "crane"
  | "scaffold"
  | "bulldozer"
  | "excavator"
  | "hard-hat"
  | "cement"
  | "concrete-mixer"
  | "steel-beam"
  | "foundation"
  | "contractor"
  | "worker"
  | "ladder"
  | "barrier"
  | "weld"
  // nhà ngoại ô + vườn (topic `residential`)
  | "roof"
  | "tile"
  | "chimney"
  | "eaves"
  | "gutter"
  | "vent"
  | "weathervane"
  | "balcony"
  | "bay-window"
  | "deck"
  | "porch"
  | "doorway"
  | "pane"
  | "trim"
  | "mailbox"
  | "mower"
  | "weed"
  | "shovel"
  | "flowerpot"
  | "shrub"
  | "hedge"
  | "fence"
  | "driveway"
  | "yard";

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
   * Điểm camera bay tới khi chọn (mặc định = `position`). Dành cho vật TRẢI
   * DÀI mà nhãn đứng ở đầu (diềm/máng xối): bay tới đầu thì thấy đầu, bay tới
   * giữa mới thấy cả vật.
   */
  focus?: [number, number, number];
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
  environment: "warehouse-lot" | "urban-intersection" | "construction-site" | "residential-yard";
  /**
   * Góc nhìn đầu của RIÊNG cảnh này. thiếu thì dùng mặc định của `SceneCanvas`.
   * Ngã tư đầy vật thể nhỏ hơn nhà kho nên cần khung hình chặt hơn.
   */
  home?: { pos: [number, number, number]; look: [number, number, number] };
  objects: SceneObjectDef[];
}
