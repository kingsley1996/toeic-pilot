"use client";

import { AudioLines, Headphones, RotateCcw } from "lucide-react";

import { ButtonLink, Panel, Skeleton, cx } from "@/components/ui";
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

/* Vòng học LÀ một chuỗi có thứ tự, nên đánh số ở đây mã hoá một thông tin thật
   chứ không trang trí. */
const LOOP = [
  {
    Icon: Headphones,
    title: "Nghe một câu",
    body: "Phát lại bao nhiêu lần cũng được. Audio sinh sẵn ngoài luồng, không chờ máy chủ.",
  },
  {
    Icon: AudioLines,
    title: "Gõ lại đúng những gì nghe được",
    body: "Bỏ qua hoa thường và dấu câu — cái được chấm là bạn có nghe ra từ đó không.",
  },
  {
    Icon: RotateCcw,
    title: "Lịch ôn tự giãn ra",
    body: "SM-2 dùng chính mức độ chật vật của bạn để quyết định ngày ôn kế tiếp: 1 ngày, 6 ngày, rồi nhân dần.",
  },
];

export default function HomePage() {
  const { status } = useSession();
  const accuracy = ((DEMO.matched / DEMO.expected) * 100).toFixed(0);

  return (
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
            hổng hiện ra ở mức từ — chỗ duy nhất sửa được.
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
              <>
                <ButtonLink href="/learn" size="lg">
                  Vào học
                </ButtonLink>
              </>
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

      {/* --- vòng học --------------------------------------------------- */}
      <section className="mt-16 border-t border-rule pt-10">
        <h2>Một vòng, ba bước</h2>
        <ol className="mt-6 grid gap-px overflow-hidden rounded border border-rule bg-rule sm:grid-cols-3">
          {LOOP.map(({ Icon, title, body }, index) => (
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

      {/* Nói thật về hiện trạng. Một trang giới thiệu hứa nhiều hơn thứ đang có
          là cách nhanh nhất để mất niềm tin ngay lần dùng đầu tiên. */}
      <p className="mt-10 text-small text-ink-faint">
        Đang trong giai đoạn xây dựng nội dung. Phần luyện đề TOEIC đầy đủ chưa mở.
      </p>
    </div>
  );
}
