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

export type PetAction = "feed" | "poke" | "walk";

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
  return null;
}
