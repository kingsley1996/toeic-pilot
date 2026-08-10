import type { PassagePublic, QuestionPublic } from "@toeic-pilot/shared";

/**
 * Một khối ngữ liệu và các câu hỏi thuộc về nó.
 *
 * Part 3, 4, 6 và 7 gom nhiều câu dưới **một** ngữ liệu dùng chung — một đoạn
 * hội thoại, một bài nói, một email. Ba part còn lại thì mỗi câu đứng riêng.
 * Gộp cả hai vào cùng một hình dạng để màn làm bài chỉ có một cách dựng, thay
 * vì bảy nhánh theo part.
 */
export type Block = {
  key: string;
  title: string | null;
  audioUrl: string | null;
  imageUrl: string | null;
  imageAlt: string | null;
  imageCredit: string | null;
  passages: PassagePublic[];
  questions: QuestionPublic[];
  /** Có gì để hiện ở cột trái không. Part 2 và 5 thì không. */
  hasStimulus: boolean;
};

export function groupQuestions(questions: QuestionPublic[]): Block[] {
  const blocks: Block[] = [];

  for (const question of questions) {
    const previous = blocks[blocks.length - 1];
    // Chỉ gộp các câu LIỀN NHAU cùng `set_id`. So với việc gom theo một Map,
    // cách này giữ nguyên thứ tự đề — mà thứ tự chính là thứ người làm bài
    // dùng để định vị mình đang ở đâu.
    if (question.set_id && previous && previous.key === question.set_id) {
      previous.questions.push(question);
      continue;
    }

    const audioUrl = question.audio_url;
    const imageUrl = question.image_url;
    const passages = question.passages ?? [];
    blocks.push({
      key: question.set_id ?? question.id,
      title: question.set_title,
      audioUrl,
      imageUrl,
      imageAlt: question.image_alt,
      imageCredit: credit(question.image_attribution, question.image_license),
      passages,
      questions: [question],
      hasStimulus: Boolean(audioUrl || imageUrl || passages.length),
    });
  }

  return blocks;
}

/**
 * Giây -> "119:43".
 *
 * Phút chứ không phải giờ: một đề TOEIC đầy đủ là 120 phút, và "119:43" đọc ra
 * ngay còn "1:59:43" bắt người ta phải quy đổi trong đầu giữa lúc đang làm bài.
 */
export function clock(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safe / 60);
  return `${minutes}:${String(safe % 60).padStart(2, "0")}`;
}

/**
 * Một dòng ghi công từ `attribution` + `license`.
 *
 * Chỉ nối giấy phép vào khi nó CHƯA nằm sẵn trong chuỗi ghi công. Wikimedia
 * dựng sẵn câu ghi công đầy đủ — *"Tác giả, \"Tên ảnh\", CC BY 4.0, via
 * Wikimedia Commons"* — nên nối thẳng sẽ ra "… CC BY 4.0 · CC BY 4.0", và một
 * dòng ghi công lặp lại chính nó đọc như lỗi hiển thị chứ không như sự tôn
 * trọng giấy phép.
 */
export function credit(attribution: string | null, license: string | null): string | null {
  if (!attribution) return license;
  if (!license || attribution.includes(license)) return attribution;
  return `${attribution} · ${license}`;
}
