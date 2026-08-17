"use client";

import { API_ROUTES, type TopicPublic, type VocabularyPage } from "@toeic-pilot/shared";
import {
  AudioLines,
  BookOpen,
  FileText,
  Headphones,
  Layers,
  RotateCcw,
  Keyboard,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ButtonLink, Panel, Skeleton, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/**
 * Một lần chấm có thật, dựng sẵn.
 *
 * Hero cho thấy CƠ CHẾ chứ không mô tả nó. Chấm theo từng từ là điều khác biệt
 * nhất của sản phẩm — mọi app khác chỉ nói đúng hay sai cả câu — và không có
 * cách nào giải thích nó nhanh bằng việc nhìn thấy nó một lần.
 *
 * Câu này lấy từ `content/sources/dictation_office_life.jsonl`, và phần chấm là
 * kết quả thật của `app/services/dictation.py` với bài nộp bên dưới. Không bịa.
 */
const DEMO = {
  transcript: "The quarterly report is due before the end of the month.",
  typed: "The quarterly report is do before the end of month.",
  diff: [
    { word: "The", op: "match" },
    { word: "quarterly", op: "match" },
    { word: "report", op: "match" },
    { word: "is", op: "match" },
    { word: "due", op: "missing" },
    { word: "do", op: "extra" },
    { word: "before", op: "match" },
    { word: "the", op: "match" },
    { word: "end", op: "match" },
    { word: "of", op: "match" },
    { word: "the", op: "missing" },
    { word: "month", op: "match" },
  ],
  matched: 9,
  expected: 11,
};

const DIFF_STYLE: Record<string, string> = {
  match: "text-ink",
  missing: "text-alert line-through decoration-2",
  extra: "text-warn italic",
};

const ACCENTS = [
  { label: "US", dot: "bg-accent-us", name: "Mỹ" },
  { label: "UK", dot: "bg-accent-uk", name: "Anh" },
  { label: "AU", dot: "bg-accent-au", name: "Úc" },
  { label: "CA", dot: "bg-accent-ca", name: "Canada" },
];

/*
 * Năm bậc tự chấm, đúng thang mà `app/services/srs.py` hiểu. Bày ra ở đây vì
 * bậc thứ năm là thứ phân biệt sản phẩm này với một bộ thẻ lật thường: học viên
 * KHẲNG ĐỊNH đã thuộc, và engine tôn trọng bằng cách nhảy thẳng lên mốc
 * đã-thuộc thay vì bắt chờ ba tuần.
 */
const GRADES = [
  { label: "Học lại", bar: "bg-alert" },
  { label: "Khó", bar: "bg-warn" },
  { label: "Tốt", bar: "bg-ink-muted" },
  { label: "Dễ", bar: "bg-action" },
  { label: "Thành thạo", bar: "bg-ok" },
];

export default function HomePage() {
  const { status } = useSession();
  const accuracy = ((DEMO.matched / DEMO.expected) * 100).toFixed(0);

  /*
   * Số từ và số chủ đề ĐỌC TỪ MÁY CHỦ, không viết cứng vào trang.
   *
   * Một trang giới thiệu ghi cứng "300 từ" sẽ đúng đúng một lần rồi sai mãi, và
   * không có gì báo — cùng kiểu hỏng đã làm bảng số liệu trong ROADMAP lệch hẳn
   * một chục migration. Hỏng thì ẩn con số đi chứ không rơi về một số đoán.
   *
   * Số từ lấy từ `total` của trang đầu tiên, KHÔNG phải tổng `entry_count` của
   * các chủ đề: `vocabulary_topic` là quan hệ nhiều-nhiều, nên một từ xếp vào
   * hai chủ đề sẽ được cộng hai lần và trang giới thiệu khoe nhiều từ hơn số
   * thật. `limit=1` vì chỉ cần con số — cùng luật đã ghi cho `/learn/dictation`.
   */
  const [topics, setTopics] = useState<TopicPublic[] | null>(null);
  const [wordCount, setWordCount] = useState<number | null>(null);
  useEffect(() => {
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then(setTopics)
      .catch(() => {});
    apiFetch<VocabularyPage>(`${API_ROUTES.vocabulary}?limit=1`)
      .then((page) => setWordCount(page.total))
      .catch(() => {});
  }, []);

  return (
    /* Không còn lưới riêng ở đây: nền lưới đã là của TOÀN KHUNG
       (`components/shell.tsx` → `.grid-backdrop`). Giữ thêm một lớp nữa ở đây
       sẽ chồng hai lưới lệch pha lên nhau — hai bộ đường kẻ cách nhau vài pixel
       trông như lỗi render chứ không như một lưới đậm hơn. */
    <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:py-16">
      {/* --- hero ----------------------------------------------------- */}
      <section className="grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:items-center">
        <div>
          <p className="text-label font-semibold uppercase text-action-ink">
            Luyện nghe &amp; từ vựng TOEIC
          </p>
          <h1 className="mt-3 text-[2rem] leading-[2.5rem] sm:text-[2.5rem] sm:leading-[3rem]">
            Biết chính xác mình nghe sót từ nào.
          </h1>
          <p className="mt-4 max-w-lg text-ink-muted">
            Không phải đúng hay sai cả câu. Mỗi bài nghe được đối chiếu từng từ với đáp án, nên chỗ
            hổng hiện ra ở mức từ — chỗ duy nhất sửa được. Từ vựng cũng vậy: lịch ôn bám theo trí
            nhớ của bạn chứ không theo lịch cố định.
          </p>

          {/* Ba trạng thái, không phải hai. Coi "loading" là chưa đăng nhập sẽ
                hiện "Bắt đầu miễn phí" một nhịp cho người đã đăng nhập rồi mới
                đổi lại — đúng kiểu lỗi nhấp nháy mà header từng mắc. */}
          <div className="mt-7 flex flex-wrap gap-2.5">
            {status === "loading" && (
              <>
                <Skeleton className="h-11 w-40" />
                <Skeleton className="h-11 w-40" />
              </>
            )}
            {status === "authenticated" && (
              <ButtonLink href="/dashboard" size="lg">
                Vào học
              </ButtonLink>
            )}
            {status === "anonymous" && (
              <>
                <ButtonLink href="/register" size="lg">
                  Bắt đầu miễn phí
                </ButtonLink>
                <ButtonLink href="/login" variant="secondary" size="lg">
                  Tôi đã có tài khoản
                </ButtonLink>
              </>
            )}
          </div>
        </div>

        {/* Mặt đọc của thiết bị: một lần chấm thật. */}
        <Panel className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-rule bg-recess px-4 py-2">
            <span className="flex items-center gap-1.5 text-label font-semibold uppercase text-ink-muted">
              <Headphones size={12} strokeWidth={2} aria-hidden />
              Kết quả chấm
            </span>
            <span className="font-data text-label uppercase text-ink-faint">theo từng từ</span>
          </div>

          <div className="px-5 py-5">
            <p className="text-label font-semibold uppercase text-ink-faint">Bạn đã gõ</p>
            <p className="mt-1.5 font-data text-small text-ink-muted">{DEMO.typed}</p>

            <p className="mt-5 text-label font-semibold uppercase text-ink-faint">Đối chiếu</p>
            {/* Hiện ra từng từ, trái sang phải — vì đó chính là cách người ta
                  nghe lại câu. Khoảnh khắc dàn dựng duy nhất của cả app (§7). */}
            <p className="mt-1.5 text-subtitle leading-9">
              {DEMO.diff.map((word, position) => (
                <span
                  key={`${word.op}-${position}`}
                  className={cx("animate-settle", DIFF_STYLE[word.op])}
                  style={{ animationDelay: `${Math.min(position * 24, 600)}ms` }}
                >
                  {word.word}{" "}
                </span>
              ))}
            </p>

            <div className="mt-5 flex items-end justify-between border-t border-rule pt-4">
              <div>
                <p className="text-label font-semibold uppercase text-ink-faint">Độ chính xác</p>
                <p className="font-data text-readout leading-none text-ink">
                  {accuracy}
                  <span className="text-title text-ink-faint">%</span>
                </p>
              </div>
              <p className="font-data text-small text-ink-muted">
                {DEMO.matched}/{DEMO.expected} từ
              </p>
            </div>

            <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-small text-ink-muted">
              <span className="flex items-center gap-1.5">
                <span aria-hidden className="h-2 w-2 bg-ink" /> đúng
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden className="h-2 w-2 bg-alert" /> nghe sót
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden className="h-2 w-2 bg-warn" /> gõ thừa
              </span>
            </div>
          </div>
        </Panel>
      </section>

      {/* --- ba khu học ------------------------------------------------ */}
      {/* Đúng ba mục của thanh điều hướng sau khi đăng nhập. Trang giới thiệu
            mô tả một cấu trúc khác với cấu trúc thật là dạy sai người dùng ngay
            trước khi họ bước vào. */}
      <section className="mt-16 border-t border-rule pt-10">
        <h2>Ba khu học</h2>
        {/* KHÔNG nói "chung một hàng đợi": chỉ TỪ VỰNG chạy trên SM-2. Dictation
              tính theo câu đã làm xong, không có ngày đến hạn — gộp hai thứ vào
              một câu cho gọn là hứa một cơ chế không tồn tại. */}
        <p className="mt-2 max-w-2xl text-ink-muted">
          Từ vựng chạy trên lịch ôn giãn dần và nhớ chỗ bạn đang học dở. Dictation chấm từng từ và
          đếm câu đã nghe xong. Luyện đề thì đứng riêng: nó đo, không dạy.
        </p>

        <div className="mt-6 grid gap-px overflow-hidden rounded border border-rule bg-rule sm:grid-cols-3">
          <div className="bg-panel p-5">
            <BookOpen size={16} strokeWidth={1.75} aria-hidden className="text-ink-muted" />
            <h3 className="mt-3">Từ vựng</h3>
            <p className="mt-1.5 text-small text-ink-muted">
              Ba cách gặp cùng một từ — gõ lại, thẻ lật, trắc nghiệm — rồi bạn tự chấm mình nhớ tới
              đâu. Chỗ học dở lưu trên máy chủ, nên đổi máy vẫn đúng chỗ.
            </p>
            {/* Con số chỉ hiện khi máy chủ trả lời; hỏng thì mất số, không đoán. */}
            {wordCount !== null && topics !== null && (
              <p className="mt-3 font-data text-small tabular-nums text-ink-faint">
                {wordCount} từ · {topics.length} chủ đề
              </p>
            )}
          </div>

          <div className="bg-panel p-5">
            <Headphones size={16} strokeWidth={1.75} aria-hidden className="text-ink-muted" />
            <h3 className="mt-3">Dictation</h3>
            <p className="mt-1.5 text-small text-ink-muted">
              Nghe một câu, gõ lại, và nhận đúng bảng đối chiếu ở trên. Bỏ qua hoa thường và dấu câu
              — cái được chấm là bạn có nghe ra từ đó không.
            </p>
          </div>

          <div className="bg-panel p-5">
            <FileText size={16} strokeWidth={1.75} aria-hidden className="text-ink-muted" />
            <h3 className="mt-3">Luyện đề</h3>
            <p className="mt-1.5 text-small text-ink-muted">
              Làm đề có tính giờ, nộp, rồi xem lại từng câu kèm đáp án đúng. Đồng hồ chạy ở máy chủ,
              nên đóng tab không phải là cách dừng bài.
            </p>
          </div>
        </div>
      </section>

      {/* --- bốn giọng -------------------------------------------------- */}
      <section className="mt-16 border-t border-rule pt-10">
        <div className="grid gap-8 sm:grid-cols-[1fr_auto] sm:items-end">
          <div>
            <h2>Bốn giọng, cho mọi từ</h2>
            <p className="mt-2 max-w-xl text-ink-muted">
              Bài nghe TOEIC dùng bốn giọng bản ngữ, và giọng Úc là chỗ nhiều người mất điểm nhất
              chỉ vì chưa quen. Mỗi từ ở đây đều được đọc bằng cả bốn — kể cả câu ví dụ.
            </p>
          </div>
          <div className="flex gap-1.5">
            {ACCENTS.map((accent) => (
              <span
                key={accent.label}
                title={`Giọng ${accent.name}`}
                className="inline-flex h-8 items-center gap-1.5 rounded-pill border border-rule-strong px-2.5 text-label font-semibold uppercase text-ink-muted"
              >
                <span aria-hidden className={cx("h-1.5 w-1.5 rounded-pill", accent.dot)} />
                {accent.label}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* --- lịch ôn ---------------------------------------------------- */}
      <section className="mt-16 border-t border-rule pt-10">
        <div className="grid gap-8 lg:grid-cols-[1fr_1fr] lg:items-start">
          <div>
            <h2>Lịch ôn giãn ra theo trí nhớ của bạn</h2>
            <p className="mt-2 text-ink-muted">
              Sau mỗi từ, bạn chọn một trong năm mức. SM-2 dùng chính mức độ chật vật đó để quyết
              định ngày ôn kế tiếp: 1 ngày, 6 ngày, rồi nhân dần. Nhớ tốt thì từ đó giãn ra và
              nhường chỗ cho từ khác.
            </p>
            <p className="mt-3 text-ink-muted">
              Bậc thứ năm là lối tắt trung thực: bạn khẳng định đã thuộc, và lịch nhảy thẳng lên mốc
              đã-thuộc thay vì bắt bạn chờ ba tuần để chứng minh điều mình đã biết.
            </p>
          </div>

          {/* Cùng dãy nút mà học viên thật sự bấm, không phải một hình minh
                hoạ vẽ lại. Thứ tự và màu vạch lấy đúng từ `_games.tsx`. */}
          <Panel className="p-5">
            <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-ink-faint">
              <Layers size={12} strokeWidth={2} aria-hidden />
              Bạn nhớ từ này thế nào?
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {GRADES.map((grade, index) => (
                <span
                  key={grade.label}
                  className="flex items-center gap-2.5 rounded border border-rule-strong bg-panel px-2.5 py-2"
                >
                  <span aria-hidden className={cx("h-7 w-1 shrink-0", grade.bar)} />
                  <span className="min-w-0">
                    <span className="block text-small font-semibold">{grade.label}</span>
                    <span className="block font-data text-label text-ink-faint">{index + 1}</span>
                  </span>
                </span>
              ))}
            </div>
            <p className="mt-3 flex items-center gap-2 text-small text-ink-faint">
              <Keyboard size={14} strokeWidth={1.75} aria-hidden />
              Bấm phím 1–5, không cần rời tay khỏi bàn phím.
            </p>
          </Panel>
        </div>
      </section>

      {/* --- cách một buổi học diễn ra ---------------------------------- */}
      <section className="mt-16 border-t border-rule pt-10">
        <h2>Một buổi học, ba bước</h2>
        <ol className="mt-6 grid gap-px overflow-hidden rounded border border-rule bg-rule sm:grid-cols-3">
          {[
            {
              Icon: RotateCcw,
              title: "Mở phần đến hạn trước",
              body: "Trang chủ nói thẳng hôm nay còn bao nhiêu từ tới hạn, và mở đúng vào chúng.",
            },
            {
              Icon: AudioLines,
              title: "Gặp lại từng từ",
              body: "Gõ lại, lật thẻ, hoặc chọn nghĩa — cùng một danh sách, ba cách hỏi khác nhau.",
            },
            {
              Icon: Layers,
              title: "Chấm rồi đi tiếp",
              body: "Mỗi lần chấm ghi ngay một mốc ôn mới. Bỏ dở giữa chừng cũng không mất chỗ.",
            },
          ].map(({ Icon, title, body }, index) => (
            <li key={title} className="bg-panel p-5">
              <div className="flex items-center gap-2.5">
                <span className="font-data text-small text-ink-faint">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <Icon size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
              </div>
              <h3 className="mt-3">{title}</h3>
              <p className="mt-1.5 text-small text-ink-muted">{body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Nói thật về hiện trạng. Một trang giới thiệu hứa nhiều hơn thứ đang
            có là cách nhanh nhất để mất niềm tin ngay lần dùng đầu tiên. Câu cũ
            nói "phần luyện đề chưa mở" — nay luồng làm đề đã chạy đầu-cuối, nên
            thứ còn thiếu là NỘI DUNG chứ không phải tính năng, và câu này phải
            nói đúng điều đó. */}
      <p className="mt-12 text-small text-ink-faint">
        Từ vựng đã đủ để học hằng ngày. Dictation và bộ đề vẫn đang được soạn thêm — luồng làm bài
        chạy đầy đủ, nhưng số đề còn ít.
      </p>
    </div>
  );
}
