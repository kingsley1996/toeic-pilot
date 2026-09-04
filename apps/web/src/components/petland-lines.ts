/**
 * Con thú tự nói gì lúc đứng yên trong thẻ ở sidebar.
 *
 * Khác `petland-speech.ts` ở một điểm quyết định cả cách viết: lời của khách
 * **cố định theo id** vì cùng một nhân vật phải luôn nói cùng một câu, còn lời
 * của con thú thì **bốc ngẫu nhiên**, vì đây là con thú của chính người học và
 * nó nói suốt cả ngày — lặp lại một câu duy nhất thì sau buổi thứ hai nó thôi
 * là một sinh vật và thành một dòng chữ dán trên màn hình.
 *
 * Nhưng ngẫu nhiên TRONG một tình trạng, không ngẫu nhiên hoàn toàn: câu nói là
 * cách thứ hai để đọc ba cái chỉ số, và một con thú đang kiệt sức mà reo "hôm
 * nay vui ghê" thì phá chính thứ mấy con số đang cố nói. Cùng bốn tình trạng mà
 * `conditionOf` chia, nên thêm một tình trạng ở đó thì `tsc` bắt ở đây.
 *
 * Không doạ và không sai khiến. ADR-012 §4 cấm doạ mất mát ở lời của kẻ xâm
 * nhập vì hệ thống không thực hiện lời doạ ấy; con thú thì còn gần hơn thế — nó
 * là thứ người học nuôi, nên nó xin chứ không đòi.
 *
 * Tiếng Việt vì đây là phần người học nhìn thấy.
 */

import { type PetCondition } from "@/components/petland-pet";

const LINES: Record<PetCondition, readonly string[]> = {
  sick: [
    "Mình thấy không ổn lắm…",
    "Bạn ở lại với mình một lát nhé?",
    "Hình như có ai đang tới. Bạn giúp mình với.",
    "Mình cần bạn một chút.",
  ],
  exhausted: [
    "Mình mỏi chân quá…",
    "Cho mình chợp mắt một lát nhé?",
    "Hôm nay đi nhiều rồi, mình hết pin rồi.",
    "Zzz… ơ, bạn vẫn ở đây à?",
  ],
  hungry: [
    "Bụng mình kêu rồi đấy.",
    "Có gì ăn không bạn ơi?",
    "Mình nghĩ tới đồ ăn suốt từ nãy.",
    "Học xong nhớ cho mình ăn nhé.",
  ],
  sad: [
    "Mình hơi buồn một chút…",
    "Lâu rồi bạn không chơi với mình.",
    "Bạn nói chuyện với mình một lát nhé?",
    "Mình vẫn ở đây mà.",
  ],
  cheerful: [
    "Hôm nay vui ghê!",
    "Bạn học chăm thật đấy.",
    "Mình thấy khoẻ lắm, đi dạo không?",
    "Cứ thế này thì mình lên level mất!",
  ],
  content: [
    "Bạn đang học gì thế?",
    "Mình ngồi đây đợi bạn nhé.",
    "Làm thêm một câu nữa đi.",
    "Mình vẫn ổn, bạn cứ tập trung.",
    "Lúc nào rảnh thì ghé chơi với mình.",
  ],
};

/**
 * Một câu bất kỳ hợp với tình trạng hiện tại.
 *
 * Nhận `avoid` để không bốc trúng đúng câu vừa nói: bốc ngẫu nhiên trên năm câu
 * thì cứ năm lần lại có một lần trùng liền nhau, và trùng liền nhau đọc ra là
 * hỏng chứ không phải ngẫu nhiên.
 */
export function petLine(condition: PetCondition, avoid?: string): string {
  const all = LINES[condition];
  const pool = all.length > 1 && avoid ? all.filter((line) => line !== avoid) : all;
  return pool[Math.floor(Math.random() * pool.length)];
}
