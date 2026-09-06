import type { LucideIcon } from "lucide-react";
import { BookOpenText, FileText, Image, MessagesSquare, Mic, Pencil, Users } from "lucide-react";

/**
 * Dữ liệu tĩnh cho khu "Luyện theo part" — SỰ THẬT TẠM THỜI.
 *
 * `questionCount` và `labels` là số ĐO THẬT từ kho ngày 2026-09-06 (đếm câu
 * published theo `question.part` × `question_label`), nên phân loại nhãn phản
 * ánh đúng dữ liệu sẽ chạy qua API sau này. Câu drill vẫn mock; khi
 * `GET /practice/parts/{part}` ra đời, chỉ tệp này đổi sang `apiFetch`.
 *
 * Nội dung chiến thuật KHÔNG ở đây — mỗi part một tệp markdown trong
 * `content/parts/`, đọc bởi server component, cùng triết lý "viết offline như
 * bài ngữ pháp".
 */

export type PartLabel = {
  code: string;
  title: string;
  count: number;
  /** Chủ đề ngữ pháp tương ứng (facet `grammar`) — deep-link sang mô-đun. */
  grammarSlug?: string;
};

export type PartMockQuestion = {
  prompt: string;
  options: { label: string; content: string }[];
  correct: string;
  explanation: string;
  /** Part 1–4: có audio (mock: hiện nút play, chưa phát gì). */
  audio?: boolean;
  /** Part 6–7: có đoạn văn kèm câu. */
  passage?: string;
  /** Nhãn taxonomy của câu — drill lọc và tổng kết theo cái này. */
  label: string;
};

export type PartInfo = {
  part: number;
  title: string;
  short: string;
  Icon: LucideIcon;
  questionCount: number;
  minutes: string;
  labels: PartLabel[];
  drill: PartMockQuestion[];
};

export const PARTS: PartInfo[] = [
  {
    part: 1,
    title: "Mô tả tranh",
    short: "Chọn câu mô tả đúng nhất bức tranh",
    Icon: Image,
    questionCount: 128,
    minutes: "~6 phút · 6 câu",
    labels: [
      { code: "PART_1_PERSON_DESCRIPTION", title: "Người đang làm gì", count: 17 },
      { code: "PART_1_PERSON_AND_OBJECT_DESCRIPTION", title: "Người và vật", count: 8 },
      { code: "PART_1_OBJECT_OR_SCENE_DESCRIPTION", title: "Vật / khung cảnh", count: 5 },
    ],
    drill: [
      {
        prompt: "Chọn câu mô tả đúng nhất bức tranh.",
        audio: true,
        label: "PART_1_PERSON_AND_OBJECT_DESCRIPTION",
        options: [
          { label: "(A)", content: "The packages are being loaded onto a truck." },
          { label: "(B)", content: "The workers are unloading a truck." },
          { label: "(C)", content: "A truck is parked outside the warehouse." },
          { label: "(D)", content: "The delivery will arrive in one hour." },
        ],
        correct: "A",
        explanation:
          "Tranh cho thấy người đang chuyển thùng LÊN xe (loading), không phải dỡ xuống. C đúng sự thật phụ nhưng không phải hành động chính; D là suy diễn tương lai — không bao giờ là đáp án Part 1.",
      },
    ],
  },
  {
    part: 2,
    title: "Hỏi – đáp",
    short: "Chọn phản hồi đúng cho một câu hỏi hoặc lời chào",
    Icon: MessagesSquare,
    questionCount: 102,
    minutes: "~11 phút · 30 câu",
    labels: [
      { code: "PART_2_WHO_QUESTION", title: "Câu hỏi Who", count: 17 },
      { code: "PART_2_REQUEST_OR_SUGGESTION", title: "Yêu cầu / gợi ý", count: 16 },
      { code: "PART_2_HOW_QUESTION", title: "Câu hỏi How", count: 14 },
      { code: "PART_2_WHERE_QUESTION", title: "Câu hỏi Where", count: 14 },
      { code: "PART_2_YES_NO_QUESTION", title: "Câu hỏi Yes/No", count: 14 },
      { code: "PART_2_WHEN_QUESTION", title: "Câu hỏi When", count: 13 },
      { code: "PART_2_CHOICE_QUESTION", title: "Câu hỏi lựa chọn", count: 13 },
      { code: "PART_2_WHY_QUESTION", title: "Câu hỏi Why", count: 10 },
    ],
    drill: [
      {
        prompt: "Chọn phản hồi phù hợp nhất.",
        audio: true,
        label: "PART_2_WHERE_QUESTION",
        options: [
          { label: "(A)", content: "It's on the third floor." },
          { label: "(B)", content: "I'll show you the way." },
          { label: "(C)", content: "Yes, it is available." },
        ],
        correct: "B",
        explanation:
          'Câu hỏi: "Could you tell me where the meeting room is?" — A trả lời thẳng địa điểm nhưng sai vai (người hỏi cần đi tới, không cần con số tầng); B là trả lời gián tiếp điển hình: dẫn đi. C Yes/No với câu hỏi Wh- → loại.',
      },
    ],
  },
  {
    part: 3,
    title: "Hội thoại ngắn",
    short: "Nghe hội thoại 2–4 người, trả lời 3 câu",
    Icon: Users,
    questionCount: 216,
    minutes: "~13 phút · 30 câu",
    labels: [
      { code: "PART_3_CONVERSATION_DETAIL", title: "Chi tiết hội thoại", count: 51 },
      { code: "PART_3_TOPIC_OR_PURPOSE", title: "Chủ đề / mục đích", count: 27 },
      { code: "PART_3_REQUEST_OR_SUGGESTION", title: "Yêu cầu / gợi ý", count: 22 },
      { code: "PART_3_SPEAKER_IDENTITY", title: "Người nói là ai", count: 19 },
      { code: "PART_3_FUTURE_ACTION", title: "Hành động tiếp theo", count: 16 },
      { code: "PART_3_LOCATION", title: "Địa điểm", count: 13 },
    ],
    drill: [
      {
        prompt: "What does the woman call about?",
        audio: true,
        label: "PART_3_TOPIC_OR_PURPOSE",
        options: [
          { label: "(A)", content: "A delayed shipment" },
          { label: "(B)", content: "A billing error" },
          { label: "(C)", content: "A scheduled meeting" },
          { label: "(D)", content: "A damaged invoice" },
        ],
        correct: "B",
        explanation:
          "Người nữ mở đầu: \"I'm calling about the invoice we received — the amount doesn't match our order.\" Từ khóa invoice + amount không khớp = billing error. A và C là các danh từ có thật trong đoạn nhưng sai vai.",
      },
    ],
  },
  {
    part: 4,
    title: "Độc thoại",
    short: "Nghe thông báo / bài nói đơn độc, trả lời 3 câu",
    Icon: Mic,
    questionCount: 198,
    minutes: "~11 phút · 30 câu",
    labels: [
      { code: "PART_4_DETAIL", title: "Chi tiết", count: 39 },
      { code: "PART_4_TOPIC_OR_PURPOSE", title: "Chủ đề / mục đích", count: 19 },
      { code: "PART_4_REQUEST_OR_SUGGESTION", title: "Yêu cầu / gợi ý", count: 18 },
      { code: "PART_4_SPEAKER_OR_LOCATION", title: "Người nói / địa điểm", count: 17 },
      { code: "PART_4_FUTURE_ACTION", title: "Hành động tiếp theo", count: 15 },
      { code: "PART_4_IMPLICATION", title: "Suy luận ẩn ý", count: 7 },
    ],
    drill: [
      {
        prompt: "What are listeners asked to do?",
        audio: true,
        label: "PART_4_REQUEST_OR_SUGGESTION",
        options: [
          { label: "(A)", content: "Submit expense reports by Friday" },
          { label: "(B)", content: "Attend a training session" },
          { label: "(C)", content: "Clear their desks before leaving" },
          { label: "(D)", content: "Update their passwords" },
        ],
        correct: "C",
        explanation:
          'Câu cuối thông báo: "...please remember to remove all confidential documents from your desk before you leave tonight." Clear desks = remove documents — paraphrase chuẩn. A và D dùng từ có trong audio (expense, password) nhưng sai vai.',
      },
    ],
  },
  {
    part: 5,
    title: "Hoàn thành câu",
    short: "Chọn từ đúng để điền vào câu đơn",
    Icon: FileText,
    questionCount: 240,
    minutes: "~12 phút · 30 câu",
    labels: [
      { code: "PART_5_GRAMMAR", title: "Ngữ pháp", count: 64 },
      { code: "PART_5_VOCABULARY", title: "Từ vựng", count: 32 },
      { code: "PART_5_PART_OF_SPEECH", title: "Từ loại", count: 27 },
      { code: "GRAMMAR_PREPOSITION", title: "Giới từ", count: 15, grammarSlug: "gioi-tu" },
      { code: "GRAMMAR_TENSE", title: "Thì", count: 12, grammarSlug: "thi" },
      { code: "GRAMMAR_ADJECTIVE", title: "Tính từ", count: 12, grammarSlug: "tinh-tu" },
      { code: "GRAMMAR_ADVERB", title: "Trạng từ", count: 12, grammarSlug: "trang-tu" },
      { code: "GRAMMAR_NOUN", title: "Danh từ", count: 12, grammarSlug: "danh-tu" },
      {
        code: "GRAMMAR_PARTICIPLE",
        title: "Phân từ",
        count: 11,
        grammarSlug: "phan-tu-va-cau-truc-phan-tu",
      },
      { code: "GRAMMAR_PRONOUN", title: "Đại từ", count: 10, grammarSlug: "dai-tu" },
      { code: "GRAMMAR_VOICE", title: "Thể", count: 8, grammarSlug: "the" },
      { code: "GRAMMAR_CONJUNCTION", title: "Liên từ", count: 8, grammarSlug: "lien-tu" },
      {
        code: "GRAMMAR_RELATIVE_CLAUSE",
        title: "Mệnh đề quan hệ",
        count: 7,
        grammarSlug: "menh-de-quan-he",
      },
    ],
    drill: [
      {
        prompt:
          "The coordinator made a ------- about the meeting schedule after reviewing the travel itinerary.",
        label: "GRAMMAR_NOUN",
        options: [
          { label: "(A)", content: "decide" },
          { label: "(B)", content: "decided" },
          { label: "(C)", content: "decisive" },
          { label: "(D)", content: "decision" },
        ],
        correct: "D",
        explanation:
          '"made a ___" — sau mạo từ cần danh từ: decision. Bốn đáp án là 4 từ loại của cùng gốc: V / V-past / adj / N.',
      },
    ],
  },
  {
    part: 6,
    title: "Hoàn thành đoạn văn",
    short: "Điền từ và câu vào một bài viết ngắn",
    Icon: Pencil,
    questionCount: 156,
    minutes: "~8 phút · 16 câu",
    labels: [
      { code: "PART_6_GRAMMAR", title: "Ngữ pháp", count: 34 },
      { code: "PART_6_VOCABULARY", title: "Từ vựng", count: 16 },
      { code: "PART_6_SENTENCE_INSERTION", title: "Điền cả câu", count: 14 },
      { code: "GRAMMAR_PREPOSITION", title: "Giới từ", count: 14, grammarSlug: "gioi-tu" },
      { code: "GRAMMAR_VOICE", title: "Thể", count: 9, grammarSlug: "the" },
      { code: "GRAMMAR_PRONOUN", title: "Đại từ", count: 7, grammarSlug: "dai-tu" },
      { code: "GRAMMAR_TENSE", title: "Thì", count: 6, grammarSlug: "thi" },
    ],
    drill: [
      {
        prompt: "Chọn câu phù hợp để điền vào chỗ trống.",
        passage:
          "All employees working remotely must log their hours in the new system. Managers will review these logs weekly to balance workloads across teams. ______ This ensures that no one is assigned more than their fair share during peak periods.",
        label: "PART_6_SENTENCE_INSERTION",
        options: [
          { label: "(A)", content: "The system also supports video conferencing." },
          {
            label: "(B)",
            content: "The data collected will not be used for performance evaluation.",
          },
          { label: "(C)", content: "These reviews help identify overloaded staff early." },
          { label: "(D)", content: "Remote work was introduced last year." },
        ],
        correct: "C",
        explanation:
          'Câu sau bắt đầu "This ensures..." — This trỏ lại hành động ở câu điền vào. C khớp: reviews → identify overloaded staff → ensures fair share. A lạc chủ đề, B phủ định trái mạch, D quay về quá khứ trong khi đoạn nói hiện tại-tương lai.',
      },
    ],
  },
  {
    part: 7,
    title: "Đọc hiểu",
    short: "Email, quảng cáo, bài báo — đọc và trả lời",
    Icon: BookOpenText,
    questionCount: 288,
    minutes: "~30 phút · 29 câu",
    labels: [
      { code: "PART_7_INFERENCE", title: "Suy luận", count: 71 },
      { code: "PART_7_INFORMATION_RETRIEVAL", title: "Tìm thông tin", count: 54 },
      { code: "PART_7_TOPIC_OR_PURPOSE", title: "Chủ đề / mục đích", count: 38 },
      { code: "PART_7_VOCABULARY_IN_CONTEXT", title: "Từ vựng trong ngữ cảnh", count: 22 },
      { code: "PART_7_FALSE_INFORMATION", title: "Câu NOT / loại trừ", count: 20 },
      { code: "PART_7_SENTENCE_INSERTION", title: "Điền câu vào bài", count: 6 },
    ],
    drill: [
      {
        prompt: "Why does Ms. Ito write to Mr. Bauer?",
        passage:
          "FROM: M. Ito\nTO: D. Bauer\nSUBJECT: Site visit\n\nMr. Bauer, our site visit on Thursday is confirmed. However, the client asked whether we could bring the safety report from the March inspection rather than the January one. Could you print the updated version? The access code for the gate will be sent to your phone the morning of the visit.",
        label: "PART_7_TOPIC_OR_PURPOSE",
        options: [
          { label: "(A)", content: "To request a document be prepared" },
          { label: "(B)", content: "To confirm the time of a visit" },
          { label: "(C)", content: "To report a problem with a gate code" },
          { label: "(D)", content: "To reschedule an inspection" },
        ],
        correct: "A",
        explanation:
          'Lý do viết nằm ở yêu cầu: "Could you print the updated version?" = request a document. B là chi tiết phụ (visit đã confirmed rồi), C và D lấy từ có thật (gate code, March inspection) nhưng sai vai — mẫu bẫy kinh điển của Part 7.',
      },
    ],
  },
];

export function getPart(part: string | undefined): PartInfo | undefined {
  return PARTS.find((p) => String(p.part) === part);
}

export function labelTitle(info: PartInfo, code: string): PartLabel | undefined {
  return info.labels.find((l) => l.code === code);
}
