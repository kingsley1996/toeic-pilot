/**
 * Nhu cầu và hành động của con thú.
 *
 * Tệp này KHÔNG biết gì về mascot lẫn bối cảnh: không tên clip, không toạ độ,
 * không ảnh. Nó chỉ là số học thuần, nên đổi con thú hay đổi khung cảnh không
 * đụng tới nó, và nó kiểm được mà không cần trình duyệt.
 *
 * Chưa có bảng nào phía máy chủ, nên các chỉ số này sống trong bộ nhớ trang: đủ
 * để nút "cho ăn" có ý nghĩa, chưa đủ để gọi là nuôi thú. Chỗ móc backend về sau
 * là `freshNeeds()` (nạp từ máy chủ) và `applyAction()` (gửi lên).
 */

export type PetAction = "feed" | "poke" | "walk" | "rest";

/** Ba chỉ số, tất cả trong khoảng 0..1. */
export type PetNeeds = {
  /** No. Cạn dần theo thời gian. */
  fullness: number;
  /** Sức. Cạn khi đi lại, hồi khi ngủ. */
  energy: number;
  /** Vui. Lên khi được chơi cùng, xuống rất chậm. */
  mood: number;
};

/** Con thú đang làm gì, theo nghĩa ảnh hưởng tới chỉ số — không phải theo nghĩa hoạt ảnh. */
export type PetActivity = "resting" | "still" | "moving";

export const NEED_KEYS = ["fullness", "energy", "mood"] as const;

export function freshNeeds(): PetNeeds {
  // Không đầy 100%: một con thú mở ra đã đủ đầy mọi thứ thì mọi cái nút đều vô
  // nghĩa ở lần bấm đầu tiên, và người dùng học được rằng chúng không làm gì.
  return { fullness: 0.62, energy: 0.78, mood: 0.7 };
}

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

/*
 * Tốc độ đổi, tính theo ĐƠN VỊ MỖI GIÂY.
 *
 * Chọn chậm là có chủ đích: đây là góc thú cưng của một ứng dụng học, không phải
 * một game nuôi thú. Một chỉ số cạn trong hai phút biến nó thành việc phải làm,
 * và việc phải làm thứ hai bên cạnh việc học là thứ khiến người ta đóng hẳn bảng
 * này lại. Đói hết mất khoảng 10 phút MỞ BẢNG liên tục.
 */
const RATES = {
  fullnessDecay: 1 / 600,
  moodDecay: 1 / 900,
  energyDrain: 1 / 420,
  energyRestRecover: 1 / 100,
  energyIdleRecover: 1 / 1200,
  /** Đói thì vui cũng tụt: một con thú đói không thể "rất vui". */
  hungryMoodPenalty: 1 / 300,
};

export function decayNeeds(needs: PetNeeds, dt: number, activity: PetActivity): PetNeeds {
  const next: PetNeeds = {
    fullness: clamp01(needs.fullness - RATES.fullnessDecay * dt),
    energy: clamp01(
      needs.energy +
        (activity === "moving"
          ? -RATES.energyDrain
          : activity === "resting"
            ? RATES.energyRestRecover
            : RATES.energyIdleRecover) *
          dt,
    ),
    mood: clamp01(needs.mood - RATES.moodDecay * dt),
  };
  if (next.fullness < 0.25) {
    next.mood = clamp01(next.mood - RATES.hungryMoodPenalty * dt * (1 - next.fullness / 0.25));
  }
  return next;
}

/** Một hành động ảnh hưởng thế nào. Trả về chỉ số MỚI, không sửa tại chỗ. */
export function applyAction(needs: PetNeeds, action: PetAction): PetNeeds {
  switch (action) {
    case "feed":
      return {
        ...needs,
        fullness: clamp01(needs.fullness + 0.34),
        mood: clamp01(needs.mood + 0.1),
      };
    case "poke":
      // Chọc thì vui, nhưng chọc mãi thì hết vui — phần thưởng nhỏ dần theo mức
      // vui hiện tại, nên bấm liên tục không đẩy được thanh lên đầy.
      return { ...needs, mood: clamp01(needs.mood + 0.14 * (1 - needs.mood)) };
    case "walk":
      return { ...needs, mood: clamp01(needs.mood + 0.08) };
    case "rest":
      return needs;
  }
}

/**
 * Hành động có làm được lúc này không, và nếu không thì vì sao.
 *
 * Trả về LÝ DO chứ không trả về `false`: một cái nút mờ đi mà không nói vì sao
 * chỉ để lại người dùng đoán, và ở đây lý do luôn ngắn gọn và có thật.
 */
export function refuse(needs: PetNeeds, action: PetAction, asleep: boolean): string | null {
  if (action === "rest") return null;
  if (asleep) return null; // các hành động khác sẽ đánh thức nó, không bị từ chối
  if (action === "feed" && needs.fullness > 0.94) return "Đang no, chưa ăn thêm được";
  if (action === "walk" && needs.energy < 0.12) return "Hết sức rồi, cho ngủ một lát đã";
  return null;
}
