/**
 * Toàn bộ chữ hiển thị của trang giới thiệu, gom về một chỗ.
 *
 * Tệp này là **nguồn thật**, không phải bản chụp: `app/page.tsx` và
 * `remotion/mocks.tsx` đọc từ đây, nên sửa ở đây là trang đổi theo. Một bản
 * trích chỉ để đọc sẽ lệch khỏi trang ngay lần sửa đầu tiên mà không ai biết.
 *
 * Dịch sang ngôn ngữ khác: chép tệp này, dịch phần chữ, đổi `import` ở hai tệp
 * kia. Không có chữ nào của trang nằm ngoài đây, trừ hai ngoại lệ ghi ở cuối.
 *
 * **Icon đi theo tên, không theo thứ tự.** Mỗi mục mang `icon: "book-open"` và
 * `page.tsx` tra bảng để lấy component. Nếu ghép theo chỉ số mảng thì người dịch
 * thêm hay bớt một mục là icon lệch hết mà TypeScript không kêu gì.
 *
 * **Số trong khối `dashboard` là minh hoạ, cố ý.** Chỉ `vocabulary` đọc số thật
 * từ máy chủ; xem chú thích ở `page.tsx`.
 */

export type IconName =
  "book-open" | "headphones" | "pencil-line" | "target" | "bar-chart" | "clock" | "flame";

export const landing = {
  hero: {
    eyebrow: "Học TOEIC theo cách dễ duy trì hơn",
    titleTop: "Học TOEIC.",
    titleAccent: "Tinh gọn, hiệu quả.",
    lead: "Học từ vựng, luyện nghe chép chính tả và làm đề TOEIC Listening & Reading — tất cả trong một nền tảng giúp bạn học đều đặn và biết mình đang tiến bộ ở đâu.",
    ctaSignedIn: "Vào học",
    ctaSignedOut: "Bắt đầu miễn phí",
    ctaSecondary: "Khám phá nền tảng",
    trust: ["Luyện từ vựng", "Nghe chép chính tả", "Luyện đề TOEIC LR"],
  },

  /** Khung "màn hình sản phẩm" ở hero. Số là minh hoạ trừ dòng từ vựng. */
  dashboard: {
    greeting: "Chào buổi tối",
    title: "Tổng quan việc học",
    goal: "Mục tiêu 700",
    progressLabel: "Tiến độ TOEIC",
    score: "560",
    scoreOf: "/ 700",
    rows: [
      { label: "Listening", value: "62%" },
      { label: "Reading", value: "71%" },
    ],
    vocabularyLabel: "Từ vựng",
    /** `{n}` được thay bằng số từ đọc từ máy chủ. */
    vocabularyValue: "{n} từ",
    todayLabel: "Hôm nay",
    todayTitle: "Từ vựng",
    todayNote: "10 phút",
    nextLabel: "Tiếp theo",
    nextTitle: "Nghe chép chính tả",
    nextNote: "Part 3",
  },

  problems: {
    kicker: "Học TOEIC không dễ duy trì",
    title: "Biết mình cần học gì mới chỉ là bước đầu.",
    lead: "Để đạt được điểm mục tiêu, bạn cần nhiều hơn một danh sách từ vựng hay một bộ câu hỏi. Bạn cần một cách học đủ rõ ràng để biết nên tập trung vào đâu, và đủ thú vị để có thể duy trì mỗi ngày.",
    items: [
      {
        title: "Học mãi một kiểu sẽ dễ chán",
        body: "Học từ vựng, làm hết câu này đến câu khác rồi lặp lại mỗi ngày rất dễ biến việc học thành một nhiệm vụ nhàm chán.",
      },
      {
        title: "Dễ mất động lực giữa chừng",
        body: "Điểm mục tiêu có thể còn khá xa, trong khi bạn lại khó cảm nhận được thành quả từ những buổi học nhỏ mỗi ngày.",
      },
      {
        title: "Không biết mình nên tập trung vào đâu",
        body: "Bạn có thể làm rất nhiều bài nhưng vẫn không rõ mình yếu ở kỹ năng nào, đang tiến bộ ra sao và nên học gì tiếp theo.",
      },
    ],
  },

  loop: {
    kicker: "Một vòng học liền mạch",
    title: "Học → luyện → tiến bộ.",
    lead: "TOEIC Pilot tập trung những hoạt động quan trọng nhất vào một nơi, để mỗi lần bạn mở app đều biết mình nên học gì và có thể bắt đầu ngay.",
    steps: [
      { label: "Học", icon: "book-open" as IconName },
      { label: "Luyện", icon: "headphones" as IconName },
      { label: "Tiến bộ", icon: "bar-chart" as IconName },
    ],
    footLeft: "Học đều mỗi ngày",
    footRight: "+ tạo thành thói quen",
    features: [
      {
        title: "Từ vựng",
        body: "Học từ vựng TOEIC theo chủ đề và ôn lại những từ bạn thường quên hoặc dễ nhầm.",
        icon: "book-open" as IconName,
      },
      {
        title: "Nghe chép chính tả",
        body: "Nghe từng câu, tự gõ lại những gì mình nghe được và luyện khả năng nhận diện từ trong tiếng Anh nói.",
        icon: "headphones" as IconName,
      },
      {
        title: "Luyện đề TOEIC",
        body: "Luyện từng Part từ 1–7 hoặc thử sức với một bài Listening & Reading hoàn chỉnh.",
        icon: "pencil-line" as IconName,
      },
      {
        title: "Theo dõi tiến độ",
        body: "Xem kết quả luyện tập để biết mình đang mạnh ở đâu, yếu ở đâu và nên cải thiện điều gì tiếp theo.",
        icon: "target" as IconName,
      },
    ],
  },

  vocabulary: {
    kicker: "Từ vựng",
    title: "Học đúng những từ bạn cần cho TOEIC.",
    lead: "Học từ vựng theo chủ đề, nghe phát âm và luyện tập ngay sau khi học — để từ mới không chỉ nằm trong danh sách mà thực sự trở thành vốn từ của bạn.",
    bullets: ["Từ vựng theo chủ đề", "Nghe phát âm", "Ôn tập tương tác"],
  },

  dictation: {
    kicker: "Nghe chép chính tả",
    title: "Nghe kỹ hơn. Hiểu nhanh hơn.",
    lead: "Nghe một câu tiếng Anh, tự viết lại những gì bạn nghe được và phát hiện chính xác những từ hoặc âm thanh mà mình thường bỏ sót.",
    bullets: ["Luyện nghe hiểu", "Nhận diện từ khi nghe", "Cải thiện chính tả"],
    /* Lối vào DUY NHẤT từ trang chủ tới phần học, và nó phải nằm ở đây.
       Thanh trên chỉ dựng nav cho người đã đăng nhập, nên khách vãng lai không
       có đường nào khác — nói "dùng được không cần tài khoản" mà không cho họ
       chỗ bấm thì lời đó không có thật. */
    cta: "Nghe thử ngay — không cần tài khoản",
  },

  exam: {
    kicker: "TOEIC Listening & Reading",
    title: "Luyện tập sát với format bài thi.",
    lead: "Luyện từng Part khi muốn tập trung vào một kỹ năng, hoặc làm trọn một đề Listening & Reading khi muốn kiểm tra khả năng của mình trong điều kiện giống bài thi.",
    bullets: [
      "Đầy đủ Part 1–7",
      "Luyện tập có tính giờ",
      "Đề Listening & Reading hoàn chỉnh",
      "Giải thích đáp án rõ ràng",
    ],
  },

  quality: {
    kicker: "Chất lượng nội dung",
    title: "AI tạo đề. Chuyên gia kiểm duyệt.",
    lead: "TOEIC Pilot sử dụng AI để xây dựng nội dung luyện tập theo format TOEIC, sau đó đưa qua các bước kiểm tra tự động và được người có chuyên môn tiếng Anh kiểm duyệt trước khi đến với người học.",
    steps: [
      {
        title: "Xác định yêu cầu",
        body: "Format, Part, độ khó và các yêu cầu của từng dạng bài được xác định ngay từ đầu.",
      },
      {
        title: "AI tạo nội dung",
        body: "AI xây dựng nội dung bài luyện từ đầu, bao gồm câu hỏi, đáp án và các thành phần cần thiết.",
      },
      {
        title: "Kiểm tra tự động",
        body: "Hệ thống tự động kiểm tra cấu trúc, đáp án và các yêu cầu bắt buộc của bài.",
      },
      {
        title: "Chuyên gia kiểm duyệt",
        body: "Nội dung được người có chuyên môn tiếng Anh xem lại trước khi được đưa vào hệ thống.",
      },
    ],
    noteStrong: "AI giúp tạo nhanh. Con người đảm bảo chất lượng.",
    noteBody:
      "TOEIC Pilot là nền tảng luyện thi độc lập. Nội dung luyện tập được xây dựng theo format TOEIC và không phải nội dung chính thức của ETS.",
  },

  pet: {
    kicker: "Thêm một chút động lực",
    title: "Một góc nhỏ để bạn có thêm lý do quay lại.",
    lead: "Góc thú cưng là một phần nhỏ, hoàn toàn tuỳ chọn. Khi muốn đổi không khí, bạn có thể hoàn thành bài tập từ vựng và nghe chép chính tả để kiếm Ruby, ấp trứng và mở khoá những người bạn mới.",
    bullets: [
      "Bật hoặc tắt góc thú cưng tuỳ thích",
      "Kiếm Ruby thông qua việc học",
      "Ấp trứng và sưu tầm thú cưng",
    ],
    speciesLabel: "45 loài, sáu bậc hiếm",

    /* Chữ cho cảnh động ở `remotion/petland.tsx`.
       Cảnh diễn đúng cơ chế trung tâm của Petland (ADR-013): ba chỉ số không
       phải là số để ngắm, chúng đổi CÁCH CON THÚ ĐI. Đói thì nó quanh quẩn
       bán kính hai ô; cho ăn xong thì vui, và vui thì nó đi xa gấp ba. */
    scene: {
      hungry: "Đang đói — nó chỉ quanh quẩn gần nhà",
      feeding: "Cho ăn",
      cheerful: "Đang vui — nó đi xa hơn hẳn",

      /* Cuộc chạm mặt (ADR-012). Ở đây là **kẻ xâm nhập**, không phải NPC
         thường: cùng bộ máy, chỉ khác ba con số — nhiều bước hơn (3 thay vì 1),
         thưởng lớn hơn (20 ruby thay vì 5), và hiếm hơn. Dấu cảnh báo đỏ trên
         đầu nó là KHUNG CẢNH chứ không phải lời đe doạ: không đẩy lui được thì
         nó biến mất và không có gì xảy ra (§4). Số và chữ chép từ
         `EncounterSetting` và `petland-quest.tsx`. */
      encounter: "Một kẻ xâm nhập xuất hiện",
      questName: "Kẻ xâm nhập",
      questSteps: "1/3",
      questTimer: "0:18",
      questLead: "Đẩy lui để nhận ruby.",
      questPrompt: "hoá đơn",
      questPos: "noun",
      questPlaceholder: "Gõ từ tiếng Anh",
      questAnswer: "invoice",
      questSubmit: "Trả lời",
      questCorrect: "Đã đẩy lui",
      questReward: "+20 ruby",
    },
  },

  habits: {
    kicker: "Học đều quan trọng hơn học thật lâu",
    title: "Mỗi ngày một chút, rồi bạn sẽ đi rất xa.",
    lead: "Bạn không cần lúc nào cũng có một buổi học hai tiếng. Chỉ cần dành một khoảng thời gian nhỏ nhưng đều đặn, bạn vẫn có thể tiến bộ từng ngày.",
    items: [
      {
        title: "Buổi học 10–20 phút",
        body: "Dễ dàng hoàn thành một bài từ vựng, một lượt nghe chép hoặc một phần luyện đề trong khoảng thời gian bạn có.",
        icon: "clock" as IconName,
      },
      {
        title: "Nhìn thấy sự tiến bộ",
        body: "Theo dõi kết quả luyện tập để hiểu rõ điểm mạnh, điểm yếu và những kỹ năng đang được cải thiện.",
        icon: "bar-chart" as IconName,
      },
      {
        title: "Duy trì thói quen",
        body: "Phần thưởng hằng ngày và góc thú cưng tuỳ chọn giúp việc học bớt khô khan và dễ duy trì hơn.",
        icon: "flame" as IconName,
      },
    ],
  },

  final: {
    kicker: "Bắt đầu bất cứ lúc nào",
    titleTop: "Điểm mục tiêu của bạn",
    titleBottom: "bắt đầu từ buổi học hôm nay.",
    lead: "Học từ vựng. Rèn kỹ năng nghe. Luyện đề TOEIC. Và từng bước tiến gần hơn đến điểm số bạn muốn.",
  },

  /*
   * Chân trang, và nó hiện ở BA trang chứ không riêng trang giới thiệu —
   * `TopBarShell` dựng nó cho `/`, `/login` và `/register`. Chữ vẫn để đây vì
   * tệp này tồn tại để dịch cả trang bằng cách chép đúng một tệp, và một chân
   * trang nằm ngoài nó sẽ là chỗ duy nhất còn tiếng Việt sau khi dịch xong.
   *
   * KHÔNG có nhãn của ba mục nội dung ở đây: chúng lấy thẳng từ `CONTENT_LINKS`
   * của `app-shell.tsx`, cùng nguồn với thanh trên. Chép lại vào đây thì đổi tên
   * một mục ở nav xong chân trang vẫn gọi nó bằng tên cũ, và không gì báo.
   */
  footer: {
    tagline:
      "Học TOEIC dễ dàng hơn — từ vựng, nghe chép chính tả và luyện đề, tất cả trong một nơi.",
    learnLabel: "Học",
    accountLabel: "Tài khoản",
    signIn: "Đăng nhập",
    signUp: "Tạo tài khoản",
    dashboard: "Vào học",
    /* Nói ra vì đây là câu hỏi đầu tiên của người vừa đọc xong trang, và câu trả
       lời có thật: `/register` không hỏi thẻ, không có bậc trả tiền nào. */
    free: "Miễn phí, không quảng cáo.",
    made: "Nội dung học do đội ngũ tự biên soạn.",
  },

  petWidget: {
    toggle: "Góc thú cưng",
    title: "Góc thú cưng",
    ruby: "◆ 320 Ruby",
    footStrong: "Học tiếp để kiếm Ruby.",
    footNote: "Hoàn thành bài tập từ vựng và nghe chép chính tả để mở khoá quả trứng tiếp theo.",
  },

  /*
   * Chữ trong ba cảnh Remotion. Phần tiếng Anh ở đây là NGỮ LIỆU bài tập, không
   * phải lời quảng cáo: dịch nó sang tiếng Việt là làm hỏng thứ mà ô đó đang
   * minh hoạ. Chỉ dịch nhãn tiếng Việt quanh nó.
   */
  mocks: {
    vocab: {
      label: "Business · Từ vựng",
      word: "invoice",
      phonetic: "/ˈɪnvɔɪs/",
      partOfSpeech: "noun",
      definition: "a document showing goods or services and the amount to be paid",
      playLabel: "Nghe phát âm",
      accents: ["US", "UK", "AU", "CA"],
    },

    dictation: {
      label: "Nghe và gõ lại",
      playing: "Đang phát…",
      listen: "Nghe kỹ",
      sentenceBefore: "The meeting has been",
      answer: "rescheduled",
      sentenceAfter: "for Friday.",
      hint: "Có thể nghe lại nếu bạn chưa nghe rõ.",
      done: "Chính xác — bạn có thể nghe lại một lần nữa nếu muốn.",
    },

    exam: {
      label: "Part 5 · Câu chưa hoàn chỉnh",
      question: "Customers can monitor the estimated ______ of their shipments.",
      options: ["arrival", "arrived", "arriving", "arrive"],
      correctIndex: 0,
    },
  },
} as const;

/*
 * HAI CHỖ CỐ Ý KHÔNG NẰM Ở ĐÂY:
 *
 * 1. Tên loài và bậc hiếm trong `components/petland-preview.tsx` — chúng soi
 *    chiếu `DEFAULT_PET_SPECIES` bên API. Đổi ở một phía là hai phía lệch nhau,
 *    và người học sẽ thấy hai cái tên cho cùng một con thú.
 *
 * 2. Chữ trong thanh trên và chân trang (`components/shell.tsx`) — dùng chung
 *    với mọi trang khác, không riêng trang giới thiệu.
 */
