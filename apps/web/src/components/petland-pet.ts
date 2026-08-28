/**
 * Từ vựng chung về nhu cầu và hành động của con thú.
 *
 * **Chỉ còn KIỂU và tên, không còn phép tính.** Bản trước tự trừ dần chỉ số và
 * tự áp dụng hành động ngay trong trình duyệt, vì lúc đó không có bảng nào phía
 * máy chủ. Giờ có: `pet_state` giữ ảnh chụp cộng mốc `needs_at`, và
 * `app/services/pet.py` là nơi duy nhất biết trừ bao nhiêu mỗi giây.
 *
 * **Không dựng lại phép tính đó ở đây, dù nghe hợp lý.** Bộ chấm dictation có
 * hai bản — một ở máy chủ, một ở trình duyệt — và `lib/dictation.ts` phải là bản
 * dịch từng bước của `services/dictation.py`, kèm cảnh báo rằng hai bên trôi
 * khỏi nhau là hỏng theo kiểu không ai báo cáo được. Ở đó cái giá là xứng đáng
 * vì phản hồi phải tức thì. Ở đây thì không: nhu cầu đổi theo NGÀY, nên một
 * thanh chỉ số đứng yên tới lần đọc sau là hoàn toàn đúng, và một bản sao thứ
 * hai của công thức chỉ tạo thêm chỗ để lệch.
 */

export type PetAction = "feed" | "poke" | "walk" | "sleep" | "wake";

/**
 * Giây cho mỗi Ô con thú đi qua.
 *
 * 0,18 (bản trước) là 5,5 ô mỗi giây — con thú lướt qua bản đồ nhanh hơn mắt
 * kịp bám, và nhanh hơn hẳn mấy con vật hậu cảnh, nên nó đọc ra là trượt chứ
 * không phải bước. 0,3 là hơn ba ô mỗi giây: vẫn tới nơi ngay khi bấm, nhưng
 * nhìn ra được từng bước chân — mà cái nhún khi đi được sinh theo TỪNG Ô, nên
 * chính tốc độ này quyết định nhịp chân trông có thật hay không.
 *
 * Ở đây chứ không ở `petland.tsx`: bàn thử `/petlab` cũng đi bộ, và trước đó nó
 * chép cứng 0,18 vào chỗ riêng — hai con số cho một nhịp là chỗ chỉnh một bên
 * rồi tưởng đã chỉnh cả hai.
 */
export const STEP_SECONDS = 0.3;

/** Ba chỉ số, tất cả trong khoảng 0..1, đúng như máy chủ trả về. */
export type PetNeeds = {
  /** No. */
  fullness: number;
  /** Sức. */
  energy: number;
  /** Vui. */
  mood: number;
};

export const NEED_KEYS = ["fullness", "energy", "mood"] as const;

/**
 * Ngưỡng để LÀM MỜ nút, không phải để từ chối.
 *
 * Máy chủ mới là bên quyết định — nó trả 409 kèm lý do bằng lời. Bảng này chỉ
 * để nút bấm trông đúng trước khi bấm; giữ nó gần với ngưỡng thật ở
 * `services/pet.py`, và nếu hai bên lệch thì hậu quả nhẹ nhất có thể: một cái
 * nút mờ mà lẽ ra bấm được, hoặc một lời từ chối lịch sự.
 */
export const FEED_FULL_ABOVE = 0.95;
export const WALK_TIRED_BELOW = 0.15;
/**
 * Đói thì chưa dắt đi dạo được — đây là thứ dựng nên THỨ TỰ giữa ba cái nút.
 *
 * Không có nó thì ba hành động độc lập hoàn toàn, thứ tự bấm không bao giờ quan
 * trọng, và một hệ mà thứ tự không quan trọng thì chỉ còn là ba cái nút bấm cho
 * hết. Ngưỡng phải khớp `WALK_HUNGRY_BELOW` ở `app/services/pet.py`.
 */
export const WALK_HUNGRY_BELOW = 0.2;
/**
 * Gần đầy sức thì không ngủ được, cùng lý do đã no thì không ăn thêm.
 *
 * Ngưỡng cao hơn ngưỡng no một chút vì ngủ tốn HÀNG GIỜ: đánh đổi ấy chỉ để
 * nhích vài phần trăm là tệ, và lời từ chối nên nói hộ người dùng. Khớp
 * `SLEEP_REFUSED_ABOVE` ở `app/services/pet.py`.
 */
export const SLEEP_NOT_TIRED_ABOVE = 0.9;
/** Dưới mức này thì đói. Khớp `HUNGRY_BELOW` ở `app/services/pet.py`. */
export const HUNGRY_BELOW = 0.25;
/** Từ mức này trở lên thì vui hẳn — ngưỡng của riêng giao diện, không có ở máy chủ. */
export const CHEERFUL_ABOVE = 0.75;

/**
 * Tình trạng con thú, gộp ba chỉ số thành MỘT từ (ADR-013 §2).
 *
 * Một từ chứ không ba con số, vì cả tầng vẽ lẫn dòng chữ trong HUD đều cần cùng
 * một câu trả lời: *nó đang thế nào*. Hai chỗ tự đọc ba chỉ số rồi tự kết luận là
 * hai bộ ngưỡng sẽ lệch nhau, và lúc đó con thú ngồi bệt trong khi dòng chữ nói
 * nó vui vẻ.
 *
 * Thứ tự ưu tiên là thứ tự cấp bách: kiệt sức trước đói, đói trước vui.
 */
export type PetCondition = "exhausted" | "hungry" | "cheerful" | "content";

export function conditionOf(needs: PetNeeds): PetCondition {
  if (needs.energy < WALK_TIRED_BELOW) return "exhausted";
  if (needs.fullness < HUNGRY_BELOW) return "hungry";
  if (needs.mood >= CHEERFUL_ABOVE) return "cheerful";
  return "content";
}

export const CONDITION_LABEL: Record<PetCondition, string> = {
  exhausted: "Đang kiệt sức",
  hungry: "Đang đói",
  cheerful: "Đang vui",
  content: "Bình thường",
};

/**
 * Bán kính đi lang thang, tính bằng ô. `null` nghĩa là đứng yên.
 *
 * Đây là chỗ ba chỉ số trở nên NHÌN THẤY ĐƯỢC mà không cần thêm cơ chế nào: no và
 * vui thì đi xa, đói thì quanh quẩn, kiệt sức thì ngồi. Người dùng đọc ra tình
 * trạng từ chính con thú trước, rồi mới liếc sang thanh chỉ số để xác nhận.
 *
 * Lang thang KHÔNG tốn nhu cầu (ADR-013 §4): tốn thì con thú tự làm cạn chính nó
 * trong lúc người dùng vắng mặt, và mở bảng ra đã thấy mọi thanh chạm đáy là một
 * lời trách móc.
 */
export function wanderRange(condition: PetCondition, reduced = false): number | null {
  // Người dùng xin giảm chuyển động thì con thú KHÔNG tự đi: một khung cảnh tự
  // động đậy lên là đúng thứ họ vừa nói là không muốn. Chốt ở đây chứ không ở
  // vòng vẽ, vì ở đây nó đo được — bài kiểm ảnh chụp không với tới nổi (nó chỉ
  // thấy hai khung hình liền nhau, còn chuyến đi thì vài giây mới tới một lần).
  if (reduced) return null;
  if (condition === "exhausted") return null;
  if (condition === "hungry") return 2;
  return condition === "cheerful" ? 6 : 4;
}

/**
 * Lý do chưa làm được, bằng lời — hoặc `null` nếu làm được.
 *
 * Trả về CÂU CHỮ chứ không phải `boolean`: một cái nút mờ đi mà không nói vì sao
 * chỉ để lại người dùng đoán. Câu ở đây chép đúng câu máy chủ trả trong lỗi 409,
 * nên dù bấm được vào (hai bên lệch ngưỡng) thì người dùng vẫn đọc được cùng một
 * lời giải thích chứ không phải hai lời khác nhau.
 */
export function whyUnavailable(needs: PetNeeds, action: PetAction): string | null {
  if (action === "feed" && needs.fullness >= FEED_FULL_ABOVE) {
    return "Nó đang no, chưa ăn thêm được.";
  }
  if (action === "walk" && needs.energy < WALK_TIRED_BELOW) {
    return "Nó đang mệt, để nó nghỉ đã.";
  }
  if (action === "walk" && needs.fullness < WALK_HUNGRY_BELOW) {
    return "Nó đang đói, cho ăn trước đã.";
  }
  if (action === "sleep" && needs.energy >= SLEEP_NOT_TIRED_ABOVE) {
    return "Nó chưa buồn ngủ.";
  }
  return null;
}

/* --- bước đi trên lưới ô ----------------------------------------------- */

/** Một ô trên bản đồ. Nhắc lại ở đây để tệp này không phải nhập gì. */
export type Tile = { x: number; y: number };

/**
 * Trạng thái đi lại của con thú.
 *
 * **Bước đang diễn ra là cặp (`from` → `tile`) cộng `progress`; `queue` giữ
 * những ô SAU đó và không bao giờ chứa ô đang đi.** Đứng yên nghĩa là `from`
 * trùng `tile` — đó là bất biến mà mọi hàm dưới đây phải giữ, và đánh mất nó là
 * cách cả ba lỗi đã gặp sinh ra:
 *
 *   · Đặt `progress = 0` mà không kéo `from` về `tile` thì hình vẽ tụt lại một
 *     ô so với vị trí logic — con thú đứng lùi một ô so với chỗ máy chủ ghi.
 *   · Bước sau khi đó bắt đầu bằng một cú dịch tới ô logic ấy, nên nó "nhảy".
 *   · Và nếu cú dịch ấy đi ngược hướng vừa bấm, người dùng thấy "bấm sang trái
 *     mà nhảy sang phải".
 *
 * Tách khỏi `petland.tsx` vì ở đó nó nằm trong một closure của
 * `requestAnimationFrame` và cách duy nhất để kiểm là bấm thử bằng tay — mà một
 * lỗi lệch một ô thì mắt rất dễ bỏ qua. Ở đây nó là số học thuần, chạy được
 * thẳng bằng `node --experimental-strip-types`.
 */
export type Walk = {
  from: Tile;
  tile: Tile;
  /** 0..1 giữa `from` và `tile`. Luôn 0 khi đứng yên. */
  progress: number;
  /** Những ô sẽ đi TIẾP, không gồm ô đang đi. */
  queue: Tile[];
  facing: "left" | "right";
};

/** Người gọi cấp ô kế tiếp khi con thú vừa tới một ô. `null` là hết chỗ đi. */
export type Steer = (at: Tile) => Tile | null;

export function restAt(tile: Tile, facing: "left" | "right" = "right"): Walk {
  return { from: tile, tile, progress: 0, queue: [], facing };
}

export function atRest(walk: Walk): boolean {
  return walk.from.x === walk.tile.x && walk.from.y === walk.tile.y;
}

/** Mở một bước mới từ ô đang đứng. `false` nghĩa là không còn chỗ để đi. */
function begin(walk: Walk, steer: Steer): boolean {
  const next = walk.queue.shift() ?? steer(walk.tile);
  if (!next) return false;
  walk.from = walk.tile;
  walk.facing = next.x < walk.tile.x ? "left" : next.x > walk.tile.x ? "right" : walk.facing;
  walk.tile = next;
  return true;
}

/**
 * Đẩy trạng thái đi lại tới `dt` giây. Sửa TẠI CHỖ và trả về chính nó.
 *
 * Phần dư của `progress` được mang sang ô kế tiếp chứ không vứt: vứt nó thì cứ
 * mỗi ô con thú khựng mất hơn nửa khung hình, và mắt đọc ra là giật chứ không
 * đọc ra là chậm.
 */
export function advance(walk: Walk, dt: number, steer: Steer, stepSeconds = STEP_SECONDS): Walk {
  let moving = !atRest(walk);
  if (!moving) {
    walk.progress = 0;
    moving = begin(walk, steer);
  }
  if (!moving) return walk;

  walk.progress += dt / stepSeconds;
  while (walk.progress >= 1) {
    walk.progress -= 1;
    if (!begin(walk, steer)) {
      // Dừng hẳn: kéo `from` về `tile` để con thú đứng đúng ô của nó.
      walk.from = walk.tile;
      walk.progress = 0;
      break;
    }
  }
  return walk;
}

/**
 * Người dùng giành quyền lái: bỏ tuyến đã xếp, giữ nguyên bước đang đi.
 *
 * Bước đang đi không nằm trong `queue`, nên xoá `queue` không làm con thú nhảy.
 * Giữ lại `queue[0]` — như một bản đã từng làm — là giữ đúng ô kế tiếp theo
 * hướng CŨ: bấm sang trái thì con thú vẫn đi thêm một ô sang phải trước đã.
 *
 * Rồi xếp ngay một ô theo hướng mới, kể cả khi đang đi dở: vòng vẽ chỉ đọc
 * trạng thái phím mỗi khung hình, nên một cú gõ ngắn hơn một khung sẽ nhả phím
 * trước khi nó kịp nhìn.
 */
export function takeOver(walk: Walk, steer: Steer): Walk {
  walk.queue = [];
  const next = steer(walk.tile);
  if (next) walk.queue = [next];
  return walk;
}

/* --- vốn tiết mục theo bậc hiếm (ADR-013 §5) ---------------------------- */

/**
 * Việc con thú biết làm thêm, mở dần theo bậc hiếm.
 *
 * **Không có tiết mục nào làm nó MẠNH hơn** — không nhanh hơn, không kiếm nhiều
 * ruby hơn, không giúp học tốt hơn. Cộng lực theo bậc sẽ biến gacha thành đường
 * tăng sức mạnh trong một ứng dụng học, và lúc đó "mở trứng có đáng không" trở
 * thành câu hỏi về điểm số chứ không phải về việc thích con nào.
 *
 * Cộng dồn: bậc trên có tất cả những gì bậc dưới có. Nhìn hai con cạnh nhau là
 * biết con nào hiếm hơn, mà không con nào hơn con nào.
 */
export type PetTrick =
  /** Nhảy tại chỗ kể cả khi chỉ đang bình thường — con thường chỉ nhảy lúc vui. */
  | "bounce"
  /** Để lại vệt mờ dưới chân khi đi. */
  | "trail"
  /** Đứng yên thì quay mặt theo con trỏ. */
  | "watch"
  /** Tự đi về phía khách trên bản đồ thay vì đi lang thang ngẫu nhiên. */
  | "greet"
  /** Lơ lửng trên mặt đất, không chạm chân xuống. */
  | "float";

const TRICKS: Record<string, readonly PetTrick[]> = {
  common: [],
  uncommon: ["bounce"],
  rare: ["bounce", "trail"],
  epic: ["bounce", "trail", "watch"],
  legendary: ["bounce", "trail", "watch", "greet"],
  god: ["bounce", "trail", "watch", "greet", "float"],
};

export function tricksOf(tier: string | undefined): ReadonlySet<PetTrick> {
  return new Set(TRICKS[tier ?? "common"] ?? []);
}
