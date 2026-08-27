/**
 * Lời thoại của những vị khách ghé Petland.
 *
 * Sống ở frontend cùng chỗ với bảng phân vai sinh vật (`petland-bestiary.ts`),
 * và vì cùng một lý do: đây là **lời thoại**, không phải dữ liệu miền. Máy chủ
 * không cần biết con vật nói gì để chấm một bài tập, còn đưa nó thành hàng dữ
 * liệu là mời một màn quản trị, một migration và một endpoint vào chỗ chỉ cần
 * hai chục câu văn.
 *
 * Chọn theo id cuộc chạm mặt chứ không bốc ngẫu nhiên: **cùng một vị khách phải
 * luôn nói cùng một câu**, kể cả sau khi tải lại trang. Bốc lại mỗi lần dựng thì
 * câu thoại đổi giữa hai lần chớp mắt, và cái làng đọc ra là một cỗ máy phát
 * chữ chứ không phải mấy nhân vật.
 *
 * Tiếng Việt vì đây là phần người học nhìn thấy; chỉ khu `/admin` mới dùng tiếng
 * Anh.
 */

/** Người đi đường nhờ giúp một việc nhỏ. Không ai ra lệnh, và không ai vội. */
const FRIENDLY: readonly string[] = [
  "Chào bạn! Mình đang bí một chỗ, giúp mình một chút được không?",
  "Ơ, con thú xinh quá. Mà này, bạn rảnh một phút không?",
  "Mình có câu này nghĩ mãi không ra. Bạn thử xem giúp nhé?",
  "Đi ngang qua thấy bạn, tiện hỏi một câu thôi.",
  "Giúp mình câu này rồi mình đãi bạn ít ruby nhé!",
  "Bạn học tiếng Anh lâu chưa? Thử câu này xem sao.",
  "Mình quên mất từ này rồi. Bạn nhớ không?",
  "Một câu thôi, nhanh lắm. Hứa đấy!",
];

/**
 * Kẻ xâm nhập nói năng hung hăng, nhưng **không doạ mất mát**.
 *
 * ADR-012 §4: bỏ qua một đợt xâm nhập thì không mất gì cả. Nên lời thoại được
 * phép trêu chọc, không được phép nói "không đuổi ta đi thì con thú của ngươi
 * sẽ đói" — một lời doạ mà hệ thống không thực hiện là nói dối người học, còn
 * một lời doạ có thực hiện thì đúng thứ tài liệu ấy từ chối.
 */
const HOSTILE: readonly string[] = [
  "Ha! Đất này của ta rồi. Trừ khi ngươi trả lời được ba câu.",
  "Ngươi mà biết mấy từ này á? Ta không tin đâu.",
  "Ba câu. Đúng cả ba thì ta đi. Sai thì ta ở lại xem ngươi vật lộn.",
  "Đừng lo, ta không phá gì đâu. Ta chỉ đứng đây thôi. Mãi mãi.",
  "Muốn ta biến mất? Chứng minh cái đầu ngươi có chữ đi.",
  "Ta nghe nói ngươi học giỏi lắm. Xem nào.",
];

/** Câu người ta nói khi bạn bấm vào họ lần nữa lúc đang làm dở. */
const NUDGE: readonly string[] = [
  "Mình vẫn đợi đây nhé.",
  "Từ từ thôi, không vội đâu.",
  "Cứ suy nghĩ kỹ đi.",
];

const HOSTILE_NUDGE: readonly string[] = [
  "Chậm thế. Ta còn cả ngày đấy.",
  "Nghĩ đi. Ta không đi đâu cả.",
  "Vẫn chưa xong à?",
];

/** Số nhỏ, ổn định, sinh ra từ một chuỗi — cùng cách `petland.tsx` gieo mầm. */
function seedOf(text: string): number {
  return [...text].reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
}

/**
 * Câu chào của một vị khách.
 *
 * `step` là số bước đã làm xong: bước 0 là lần gặp đầu nên nói câu chào, còn từ
 * bước thứ hai trở đi thì nói câu giục — chào lại y hệt sau khi người ta vừa
 * trả lời đúng một câu đọc ra là nhân vật không nhớ gì cả.
 */
export function speechFor(id: string, danger: boolean, step: number): string {
  const lines = step > 0 ? (danger ? HOSTILE_NUDGE : NUDGE) : danger ? HOSTILE : FRIENDLY;
  return lines[(seedOf(id) + step) % lines.length];
}
