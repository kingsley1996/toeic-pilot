import type { LucideIcon } from "lucide-react";
import { BookOpenText, FileText, Image, MessagesSquare, Mic, Pencil, Users } from "lucide-react";

/**
 * Dữ liệu tĩnh cho khu "Luyện theo part" — SỰ THẬT TẠM THỜI.
 *
 * Mọi con số ở đây (question_count, câu drill) là mock để duyệt giao diện;
 * `GET /practice/parts/{part}` chưa tồn tại. Khi API xong, chỉ tệp này đổi
 * sang `apiFetch` — ba trang tiêu thụ nó không phải sửa gì thêm.
 */

export type PartMockQuestion = {
  prompt: string;
  options: { label: string; content: string }[];
  correct: string;
  explanation: string;
  /** Part 1–4: có audio (mock: hiện nút play, chưa phát gì). */
  audio?: boolean;
  /** Part 6–7: có đoạn văn kèm câu. */
  passage?: string;
  /** Nhãn grammar của câu sai — drill thật suy ra link ngữ pháp từ nó. */
  grammarSlug?: string;
  grammarTitle?: string;
};

export type PartInfo = {
  part: number;
  title: string;
  short: string;
  Icon: LucideIcon;
  questionCount: number;
  minutes: string;
  /** Trang chiến thuật — markdown-lite, viết offline như bài ngữ pháp. */
  tactics: string;
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
    tactics: `# Chiến thuật Part 1: mô tả tranh

## 1. Hình dạng của phần này

Một bức tranh, **bốn câu thu sẵn**, không in trong đề. Bạn nghe bốn mô tả và chọn cái khớp nhất. Mỗi tranh 6 giây — không có thời gian dịch cả bốn câu, chỉ có thời gian **loại**.

## 2. Ba bẫy kinh điển

- **Sai chủ thể**: "The woman is signing a document" — đúng hành động *signing*, sai người: người ký là người đàn ông. Nghe **cụm chủ ngữ trước tiên**.
- **Đồng âm gần**: *office/officer, paperwork/workshop, construction/obstruction*. Đề thi cố tình chọn cặp này cho đáp án nhiễu.
- **Thì và thể**: tranh cho thấy hành động **đang xảy ra** → hầu hết đáp án đúng bắt đầu "is/are + V-ing". Câu bị động ("The packages **are being loaded**") đúng khi người ta không xuất hiện; câu hoàn thành ("The meeting **has started**") hiếm khi tả được một khoảnh khắc tĩnh.

## 3. Trước khi nghe: 5 giây đọc tranh

Đọc tranh như đọc biển báo — ai, ở đâu, đang làm gì, vật nổi bật nào. Đáp án đúng thường nói về **hành động chính của người nổi bật nhất**, không phải chi tiết góc tranh.

## 4. Quy trình

- **Nghe lần 1** — loại ngay câu sai chủ thể hoặc sai thì.
- **Nghe lần 2** — giữa hai ứng viên, chọn câu tả **điều đang thấy**, không phải điều *có thể suy ra*.
- Không bao giờ để trống: xác suất đúng khi đoán có loại trừ là 50%, để trống là 0.`,
    drill: [
      {
        prompt: "Chọn câu mô tả đúng nhất bức tranh.",
        audio: true,
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
    tactics: `# Chiến thuật Part 2: hỏi và đáp

## 1. Ba loại kích thước bằng một câu

- **Câu hỏi Wh-**: What, Where, When, Who, Why, How — đáp án phải trả lời ĐÚNG từ để hỏi
- **Câu hỏi Yes/No**: đảo be/trợ động từ lên đầu — đáp án KHÔNG cần bắt đầu bằng Yes/No
- **Lời phát biểu**: "The printer is jammed again." — không dấu hỏi, nhưng vẫn cần phản hồi phù hợp

## 2. Bẫy số một: trả lời gián tiếp

Đề thi hiện đại **tránh đáp án trả lời thẳng**. "When does the meeting start?" → không phải "At 9 a.m." mà là **"Check the calendar invite"** hay **"It was moved, remember?"**. Quen với kiểu lách câu hỏi này — nó chiếm đa số câu khó.

## 3. Bẫy số hai: đồng âm từ để hỏi

| Nghe thấy | Tưởng là | Thực ra |
|---|---|---|
| "Where's..." | Where | **Where is** vs **Who is** — phân biệt bằng đáp án |
| "Why'd..." | Why | **Why did** hoặc **Who would** |
| "What's..." | What | **What is** / **What has** |

Mẹo: đáp án nói về lý do → câu hỏi là Why; nói về địa điểm → Where. **Nghe đáp án để kiểm lời hỏi.**

## 4. Loại theo tín hiệu

- Câu hỏi "Why...?" mà đáp án bắt đầu "Because of" + danh từ đứng một mình → thường sai ngữ pháp
- Câu hỏi chọn lựa "Would you prefer tea or coffee?" → đáp án chọn một vế, không Yes/No
- Lời cảm ơn → "Not at all / Anytime", không phải "Yes, please"

## 5. Quy trình

Nghe **câu hỏi** → hình dung câu trả lời trong đầu → nghe ba lựa chọn tìm cái gần với hình dung đó. Đừng phân tích cả ba — chỉ cần nhận ra cái khớp.`,
    drill: [
      {
        prompt: "Chọn phản hồi phù hợp nhất.",
        audio: true,
        options: [
          { label: "(A)", content: "It's on the third floor." },
          { label: "(B)", content: "I'll show you the way." },
          { label: "(C)", content: "Yes, it is available." },
        ],
        correct: "B",
        grammarSlug: "dai-tu",
        grammarTitle: "Đại từ",
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
    tactics: `# Chiến thuật Part 3: hội thoại

## 1. Hình dạng

Một đoạn hội thoại (2–4 người), **3 câu hỏi mỗi đoạn**. Câu hỏi in sẵn trong đề — đây là phần duy nhất của khu nghe bạn được ĐỌC TRƯỚC.

## 2. Đọc trước đáp án = nửa số điểm

Trước audio chạy, quét 12 dòng đáp án của 3 câu hỏi. Việc cần làm không phải dịch mà **tìm điểm khác nhau** giữa các lựa chọn: "At 9 / At 10 / At 11" → biết mình đang chờ nghe **giờ**. "To repair a printer / To order supplies / To schedule a meeting" → chờ nghe **mục đích**.

## 3. Ba loại câu hỏi lặp lại vô hạn

- **Chi tiết**: ai, ở đâu, khi nào, bao nhiêu — thường nằm ở **giữa** đoạn, theo thứ tự xuất hiện
- **Ý định**: Why does the man call? — câu trả lời thường là **câu đầu tiên** của người gọi
- **Suy luận**: What will happen next? / What does the woman imply? — nằm ở **cuối** đoạn, và đáp án đúng **không lặp nguyên văn** nào trong audio (paraphrase)

## 4. Bẫy đánh lạc hướng

Mọi con số, địa danh, tên riêng trong audio đều xuất hiện ở **cả ba đáp án** của ít nhất một câu. Cái bạn nghe thấy đầu tiên thường là nhiễu; đáp án đúng là cái khớp với **vai trò** được hỏi.

## 5. Quy trình

Đọc đáp án trước → nghe trọn đoạn, đánh dấu chỗ khớp → trả lời theo thứ tự câu hỏi, không theo thứ tự trong đầu bạn.`,
    drill: [
      {
        prompt: "What does the woman call about?",
        audio: true,
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
    tactics: `# Chiến thuật Part 4: độc thoại

## 1. Khác gì Part 3

Một người nói — thông báo nội bộ, quảng cáo, hướng dẫn, bài phát biểu. Không có hội thoại để dựa, nên **tín hiệu cấu trúc** thay thế cho ngữ cảnh: câu mở đầu nêu chủ đề, câu cuối nêu hành động cần làm.

## 2. Ba câu hỏi gần như luôn có

- **Chủ đề/mục đích**: What is the announcement about? → câu đầu tiên
- **Chi tiết**: số phòng, giờ, giá, tên — nghe khi thấy chúng trong đáp án
- **Hành động được yêu cầu**: What should listeners do? → thường câu cuối: "please remember to...", "attendees are asked to..."

## 3. Giọng đọc và ngữ cảnh

Mở đầu kiểu "Good afternoon, this is Kate Miller from station management" = thông báo nhà ga; "Our sponsor brings you..." = quảng cáo. Nhận ra **loại văn bản** từ 5 giây đầu giúp đoán bộ câu hỏi.

## 4. Paraphrase — cùng luật với Part 3

Đáp án đúng hầu như không lặp nguyên văn. "The pool closes at 9" → "The pool is **not available after 9 p.m.**". Nghe thấy từ **giống hệt** trong một đáp án: nghi ngờ, đó là cái bẫy.

## 5. Quy trình

Đọc trước đáp án → câu đầu nghe chủ đề → chi tiết theo đáp án → câu cuối nghe yêu cầu. Không panic khi lỡ một câu: mỗi đoạn 3 câu độc lập nhau.`,
    drill: [
      {
        prompt: "What are listeners asked to do?",
        audio: true,
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
    tactics: `# Chiến thuật Part 5: hoàn thành câu

## 1. Hai họ câu hỏi

- **Từ vựng**: bốn từ khác nhau hẳn — "The package was *delivered/shipped/received/sent*"
- **Ngữ pháp**: bốn dạng của **cùng một gốc từ** — decide / decided / decisive / decision

Họ ngữ pháp chiếm đa số, và **không cần dịch câu** để làm: chỉ cần biết chỗ trống cần từ loại gì.

## 2. Chỗ trống cần gì — bảng tra nhanh

| Quanh chỗ trống là | Cần |
|---|---|
| a/an/the + ___ + danh từ | tính từ |
| a/an/the + ___ (hết cụm) | danh từ |
| be/seem/become + ___ | tính từ |
| ___ + danh từ phía sau, trước động từ chính | trạng từ hoặc tính từ — xem vị trí |
| chủ ngữ + ___ + tân ngữ | động từ |
| giới từ (in, for, of, before...) + ___ | danh từ / V-ing |

## 3. Tốc độ: 20 giây một câu

Đọc **nửa câu quanh chỗ trống**, không đọc cả câu. Nếu 4 đáp án là 4 từ loại khác nhau (đuôi -ly, -tion, -ed, -ing) → bài toán từ loại, giải bằng bảng trên. Nếu cùng một từ loại → mới cần nghĩa và giới từ đi kèm.

## 4. Lý thuyết đầy đủ ở mô-đun Ngữ pháp

Toàn bộ ngữ pháp Part 5 — từ loại, thì, thể, mệnh đề, giới từ, liên từ — có thành giáo trình 18 chủ đề có bài tập. Phần luyện dưới đây chỉ là tốc độ.`,
    drill: [
      {
        prompt:
          "The coordinator made a ------- about the meeting schedule after reviewing the travel itinerary.",
        options: [
          { label: "(A)", content: "decide" },
          { label: "(B)", content: "decided" },
          { label: "(C)", content: "decisive" },
          { label: "(D)", content: "decision" },
        ],
        correct: "D",
        grammarSlug: "danh-tu",
        grammarTitle: "Danh từ",
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
    tactics: `# Chiến thuật Part 6: hoàn thành đoạn văn

## 1. Bốn loại chỗ trống

- **Từ vựng** (như Part 5 nhưng cần ngữ cảnh đoạn): chọn từ hợp nghĩa cả câu
- **Ngữ pháp** (như Part 5): từ loại, thì — đọc câu chứa chỗ trống là đủ
- **Câu**: điền **cả một câu** vào đoạn — loại khó nhất, cần đọc câu trước và sau
- **Từ/cụm nối**: However / Therefore / For example / In addition — quan hệ logic giữa hai câu

## 2. Câu hỏi "điền cả câu": đọc hai câu kề

Đáp án đúng thường **nhắc lại một từ khoá** của câu trước hoặc mở đầu bằng từ nối khớp quan hệ (ví dụ câu trước nêu vấn đề → đáp án nêu giải pháp). Đáp án sai thường khớp ngữ pháp nhưng **phá mạch**: chủ đề nhảy sang việc khác.

## 3. Mạo từ và liên từ là điểm mới so với Part 5

Part 6 hay kiểm "the/this/such" trỏ ngược về danh từ đã nhắc — "This policy" chỉ chính sách **đã được mô tả ở câu trước**. Không có gì phía trước để trỏ → loại.

## 4. Quy trình

Làm Part 5-style trước (nhanh, chắc), để câu hỏi "điền cả câu" cuối cùng — lúc đó bạn đã đọc cả đoạn và mạch văn rõ hơn.`,
    drill: [
      {
        prompt: "Chọn câu phù hợp để điền vào chỗ trống.",
        passage:
          "All employees working remotely must log their hours in the new system. Managers will review these logs weekly to balance workloads across teams. ______ This ensures that no one is assigned more than their fair share during peak periods.",
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
    tactics: `# Chiến thuật Part 7: đọc hiểu

## 1. Hình dạng

Nhiều đoạn văn ngắn: email, thông báo, quảng cáo, hoá đơn, bài viết — đơn hoặc **ghép cặp** (double/triple passage: email + phản hồi, quảng cáo + hoá đơn). 29 câu, phần điểm lớn nhất của khu đọc.

## 2. Bốn loại câu hỏi — mỗi loại một cách làm

- **Ý chính**: What is the main purpose...? → đọc **câu đầu + câu cuối** của đoạn
- **Chi tiết**: Where/When/How much...? → **scanning**: lấy từ khoá trong câu hỏi, tìm lại trong bài (thường giữ nguyên từ hoặc đổi họ từ: inform → information)
- **Suy luận / NOT**: "Which is NOT mentioned?" → chỉ tìm 3 cái CÓ, cái còn lại là đáp án
- **Từ vựng trong ngữ cảnh**: "the word *them* refers to" → đọc câu chứa từ, tìm danh từ số nhiều ngay trước

## 3. Passage ghép: câu hỏi nằm ở MỐI liên kết

Đề cặp luôn có ít nhất một câu hỏi chỉ trả lời được bằng **cả hai văn bản**: "Based on the email and the invoice, when will the order arrive?" — thông tin bị tách đôi cố ý.

## 4. Quản thời gian — bài học quyết định Part 7

29 câu / 30 phút ≈ 60 giây một câu kể cả đọc. Chiến thuật: đọc **câu hỏi trước khi đọc bài**, trả lời từng câu khi tìm thấy, không đọc thụ động rồi mới quay lại. Câu nào sau 90 giây chưa ra → đánh dấu, đoán, đi tiếp.

## 5. Bẫy trả lời

Đáp án nhiễu lấy **nguyên văn từ bài** nhưng sai vai (đúng sự kiện, sai câu hỏi). Đáp án đúng thường là **paraphrase** — cùng nghĩa, khác chữ. Thấy từ giống hệt: đọc kỹ cả câu.`,
    drill: [
      {
        prompt: "Why does Ms. Ito write to Mr. Bauer?",
        passage:
          "FROM: M. Ito\nTO: D. Bauer\nSUBJECT: Site visit\n\nMr. Bauer, our site visit on Thursday is confirmed. However, the client asked whether we could bring the safety report from the March inspection rather than the January one. Could you print the updated version? The access code for the gate will be sent to your phone the morning of the visit.",
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
