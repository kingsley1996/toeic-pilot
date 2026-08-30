import {
  BookOpen,
  Clock,
  FlaskConical,
  Gauge,
  Headphones,
  Sparkles,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import type { Metadata } from "next";

import { Alert, ButtonLink, Meter, Panel, SectionHeader, Tag, cx } from "@/components/ui";

export const metadata: Metadata = { title: "Kết quả bài thi — TOEIC Pilot" };

/*
 * Trang xem trước giao diện kết quả — nhưng các con số KHÔNG còn là số bịa.
 *
 * Toàn bộ khối bên dưới lấy từ một lượt làm bài đã nộp thật trên stack dev
 * (`f21ba732`, đề `tp-form-06`, 200 câu, chấm bằng chính `score_attempt` và
 * bảng `score_conversion`). Trang vẫn tĩnh và vẫn không gọi API — nó chỉ đổi
 * nguồn của những con số từ trí tưởng tượng sang một lượt làm bài có thật.
 *
 * Đổi như vậy vì số bịa luôn tử tế với thiết kế: bản trước đặt mục tiêu 800 cho
 * một bài 742 điểm, nên khối "Mục tiêu" chỉ cần một trạng thái duy nhất — còn
 * thiếu bao nhiêu. Số thật là 730 với mục tiêu 700, tức là ĐÃ VƯỢT, và trạng
 * thái đó trước giờ không tồn tại trong thiết kế. Cũng vậy: bản trước dựng một
 * câu chuyện "đoạn kép là điểm nghẽn", còn số thật cho thấy đoạn kép (73%) lại
 * nhỉnh hơn đoạn đơn (64%).
 *
 * Một cảnh báo phải nói thẳng: các con số là THẬT theo nghĩa đi hết đường ống
 * của hệ thống, nhưng người làm bài là một bộ sinh số ngẫu nhiên có tỉ lệ đúng
 * đặt trước. Nên hình dạng tổng thể thì đáng tin, còn chênh lệch vài phần trăm
 * giữa hai trục cạnh nhau là nhiễu, không phải chân dung một người học.
 */

type CellState = "ok" | "bad" | "blank";

const ATTEMPT = {
  test: "TOEIC Pilot — Đề luyện 06 (Gemini 3.7 Flash)",
  collection: "Bộ đề TOEIC PILOT 2026 Vol.1",
  submittedAt: "20:19, 21/08/2026",
  mode: "Luyện thi",
  durationUsed: 107,
  durationLimit: 120,
  blankCount: 0,
  listeningRaw: 80,
  listeningScaled: 405,
  readingRaw: 70,
  readingScaled: 325,
  totalScaled: 730,
  // Lấy từ `user_profile.target_score` của chính tài khoản đó — và nó đã bị vượt.
  target: 700,
};

/*
 * Năm trong sáu trục suy ra thẳng từ `question.part`; chỉ trục "đoạn đơn / đoạn
 * kép" cần biết một cụm Part 7 có mấy văn bản, và cái đó đọc được từ
 * `question_set.passage_2/passage_3` chứ không cần tới nhãn kỹ năng — vốn mới
 * phủ được 2 trong 6 facet của taxonomy.
 *
 * `previous` là trung bình HAI lượt trước của cùng tài khoản (450 và 630 điểm),
 * không phải ba như bản mẫu cũ vẽ ra: tài khoản chỉ có đúng hai lượt trước đó.
 */
const RADAR_AXES: {
  label: string;
  sub: string;
  value: number;
  previous: number;
  /* Nhận xét nằm CẠNH con số nó nói về.
   *
   * Bản trước viết cứng trong phần hiển thị, chọn bằng `axis.sub === "Đoạn
   * kép"` — nên khi số thật cho ra một cặp điểm yếu khác, câu nhận xét vẫn nói
   * về đoạn kép và nói về một mốc thời gian mà hệ thống không hề đo. */
  note: string;
}[] = [
  {
    label: "P1",
    sub: "Tranh mô tả",
    value: 100,
    previous: 75,
    note: "Trọn 6 câu. Part 1 chỉ có 6 câu nên một lượt trọn điểm chưa nói được nhiều.",
  },
  {
    label: "P2",
    sub: "Hỏi đáp",
    value: 80,
    previous: 76,
    note: "20/25, gần như đứng yên so với hai lượt trước.",
  },
  {
    label: "P3–P4",
    sub: "Nghe dài",
    value: 78,
    previous: 59,
    note: "54/69 — phần tiến nhanh nhất của cả bài nghe.",
  },
  {
    label: "P5–P6",
    sub: "Ngữ pháp",
    value: 74,
    previous: 51,
    note: "34/46. Riêng Part 5 chỉ 20/30, và câu 105–109 sai liền năm câu — chuỗi sai dài nhất của cả bài.",
  },
  {
    label: "P7",
    sub: "Đoạn đơn",
    value: 64,
    previous: 47,
    note: "25/39 — thấp nhất bài, và là phần cần nhiều câu đúng nhất để kéo điểm Đọc.",
  },
  {
    label: "P7",
    sub: "Đoạn kép",
    value: 73,
    previous: 43,
    note: "11/15. Chỉ 15 câu nên khoảng tin cậy rất rộng: chênh với đoạn đơn ở đây chưa đủ để kết luận.",
  },
];

/*
 * Kết quả THẬT của 200 câu, theo đúng số thứ tự trong đề: `o` đúng, `x` sai,
 * `.` bỏ trống.
 *
 * Bản trước sinh bản đồ này bằng cách xáo trộn ngẫu nhiên đúng/sai trong từng
 * part, nên nó vẽ ra một thứ trông như dữ liệu mà không mang thông tin nào —
 * và nó giấu mất điều mà bản đồ tồn tại để cho thấy: những câu sai có ĐI THÀNH
 * CỤM hay không. Ở đây thấy ngay, ví dụ câu 101–110 (đầu Part 5) sai liền năm
 * câu trong tám.
 */
const ANSWER_MAP = [
  // câu 1–25
  "oooooooooooxoxooooooooxxo",
  // câu 26–50
  "xoooooooxoxoooooooooooooo",
  // câu 51–75
  "oooooxxooxxoooxooxoxoooxo",
  // câu 76–100
  "ooooooxooxoooxxoooooooxoo",
  // câu 101–125
  "ooxoxxxxxooooooxoooxoooox",
  // câu 126–150
  "xoooooooxoooooooxoooooooo",
  // câu 151–175
  "oxoooooooxoxoxooxxoxxxoox",
  // câu 176–200
  "xooxooooooxxoxoooooxxooxo",
].join("");

const HEATMAP: CellState[] = [...ANSWER_MAP].map((c) =>
  c === "o" ? "ok" : c === "x" ? "bad" : "blank",
);

/*
 * Khoảng số câu của từng part là thứ DUY NHẤT khai ở đây; số câu đúng suy ra từ
 * `ANSWER_MAP`.
 *
 * Bản trước khai số câu đúng thành một danh sách riêng, tách khỏi bản đồ 200 ô —
 * hai nguồn cho cùng một sự thật, và không có gì bắt chúng khớp nhau. Lúc dựng
 * trang này chúng đã lệch thật: bảng ghi Part 4 là 24 câu đúng trong khi bản đồ
 * đếm được 23. Cả hai đều trông hợp lý, và không ai nhìn 200 ô vuông để đếm tay.
 */
const PARTS: {
  part: number;
  name: string;
  section: "listening" | "reading";
  first: number;
  last: number;
}[] = [
  { part: 1, name: "Photos", section: "listening", first: 1, last: 6 },
  { part: 2, name: "Question-Response", section: "listening", first: 7, last: 31 },
  { part: 3, name: "Conversations", section: "listening", first: 32, last: 70 },
  { part: 4, name: "Talks", section: "listening", first: 71, last: 100 },
  { part: 5, name: "Incomplete Sentences", section: "reading", first: 101, last: 130 },
  { part: 6, name: "Text Completion", section: "reading", first: 131, last: 146 },
  { part: 7, name: "Reading Comprehension", section: "reading", first: 147, last: 200 },
];

/** Ô kết quả của một part, cắt thẳng từ bản đồ theo số câu. */
function cellsOf(part: { first: number; last: number }): CellState[] {
  return HEATMAP.slice(part.first - 1, part.last);
}

function radarPoint(index: number, value: number, cx: number, cy: number, radius: number) {
  const angle = -Math.PI / 2 + (index * Math.PI * 2) / 6;
  const r = (radius * value) / 100;
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)] as const;
}

function ringPoints(cx: number, cy: number, radius: number, value: number): string {
  return Array.from({ length: 6 }, (_, i) => radarPoint(i, value, cx, cy, radius).join(",")).join(
    " ",
  );
}

function Radar() {
  /*
   * Khung rộng hơn hình, vì NHÃN mới là thứ chạm mép chứ không phải lục giác.
   *
   * Bản mẫu đặt khung 380×330 quanh bán kính 112 và trông vẫn ổn — với dữ liệu
   * bịa. Số thật có một trục đạt 100%, đỉnh chạm vòng ngoài cùng, và nhãn
   * "P3–P4 · 78%" ở bên phải bị cắt mất đuôi. Nhãn nằm ngoài bán kính 1,24 lần
   * và còn kéo dài thêm bề rộng chữ của chính nó, nên khung phải chừa chỗ cho
   * cả hai.
   */
  const cx = 220;
  const cy = 160;
  const radius = 108;
  const current = RADAR_AXES.map((axis, i) =>
    radarPoint(i, axis.value, cx, cy, radius).join(","),
  ).join(" ");
  const previous = RADAR_AXES.map((axis, i) =>
    radarPoint(i, axis.previous, cx, cy, radius).join(","),
  ).join(" ");

  return (
    <svg
      viewBox="0 0 440 344"
      role="img"
      aria-label="Biểu đồ lục giác điểm thành thạo sáu nhóm kỹ năng"
      className="w-full"
    >
      {[33, 66, 100].map((step) => (
        <polygon
          key={step}
          points={ringPoints(cx, cy, radius, step)}
          fill="none"
          strokeWidth={step === 100 ? 1.5 : 1}
          className={step === 100 ? "stroke-rule-strong" : "stroke-rule"}
        />
      ))}
      {RADAR_AXES.map((_, i) => {
        const [x, y] = radarPoint(i, 100, cx, cy, radius);
        return (
          <line key={i} x1={cx} y1={cy} x2={x} y2={y} strokeWidth={1} className="stroke-rule" />
        );
      })}

      <polygon
        points={previous}
        strokeWidth={1.5}
        strokeDasharray="5 4"
        fillOpacity={0.08}
        className="stroke-accent-uk fill-accent-uk"
      />
      <polygon
        points={current}
        strokeWidth={2.5}
        fillOpacity={0.16}
        className="stroke-accent-us fill-accent-us"
      />

      {RADAR_AXES.map((axis, i) => (
        <circle
          key={axis.sub}
          cx={radarPoint(i, axis.value, cx, cy, radius)[0]}
          cy={radarPoint(i, axis.value, cx, cy, radius)[1]}
          r={3.5}
          className="fill-accent-us"
        />
      ))}

      {RADAR_AXES.map((axis, i) => {
        const [x, y] = radarPoint(i, 124, cx, cy, radius);
        const anchor = x > cx + 8 ? "start" : x < cx - 8 ? "end" : "middle";
        return (
          <text key={axis.sub} x={x} y={y} textAnchor={anchor} className="fill-ink">
            <tspan className="text-[13px] font-semibold">
              {axis.label} · {axis.value}%
            </tspan>
            <tspan x={x} dy={15} className="fill-ink-muted text-[11px]">
              {axis.sub}
            </tspan>
          </text>
        );
      })}
    </svg>
  );
}

function ScoreGauge() {
  const value = ATTEMPT.totalScaled;
  const max = 990;
  const target = ATTEMPT.target;
  /*
   * Mục tiêu 700 nằm ở khoảng 53° — tức là ngay TRÊN cung, không phải ngoài rìa
   * như mốc 800 của dữ liệu mẫu. Nhãn cũ neo thẳng xuống dưới vạch nên nó đè lên
   * chính đường cung. Giờ nhãn đi theo hướng của vạch và neo trái/phải theo phía,
   * và khung rộng ra để chứa nó.
   */
  const cx = 170;
  const cy = 132;
  const radius = 104;

  // Nửa vòng tròn: 180° (trái) → 0° (phải), phần trăm điểm chạy theo đó.
  const pointAt = (fraction: number) => {
    const angle = Math.PI - fraction * Math.PI;
    return [cx + radius * Math.cos(angle), cy - radius * Math.sin(angle)] as const;
  };
  const arc = (fraction: number) => {
    const [x1, y1] = pointAt(0);
    const [x2, y2] = pointAt(fraction);
    return `M ${x1} ${y1} A ${radius} ${radius} 0 0 1 ${x2} ${y2}`;
  };

  const targetAngle = Math.PI - (target / max) * Math.PI;
  const tickInner = [
    cx + (radius - 13) * Math.cos(targetAngle),
    cy - (radius - 13) * Math.sin(targetAngle),
  ] as const;
  const tickOuter = [
    cx + (radius + 13) * Math.cos(targetAngle),
    cy - (radius + 13) * Math.sin(targetAngle),
  ] as const;
  const labelAt = [
    cx + (radius + 24) * Math.cos(targetAngle),
    cy - (radius + 24) * Math.sin(targetAngle),
  ] as const;

  return (
    <svg
      viewBox="0 0 340 165"
      role="img"
      aria-label={`Tổng điểm ${value} trên 990, mục tiêu ${target}`}
      className="w-full"
    >
      <path d={arc(1)} fill="none" strokeWidth={13} className="stroke-recess" />
      <path d={arc(value / max)} fill="none" strokeWidth={13} className="stroke-action" />

      {/* Vạch mục tiêu: màu ok chứ không phải màu action, vì "tới được đây" là
          trạng thái đạt, không phải hành động. */}
      <line
        x1={tickInner[0]}
        y1={tickInner[1]}
        x2={tickOuter[0]}
        y2={tickOuter[1]}
        strokeWidth={2.5}
        className="stroke-ok"
      />
      <text
        x={labelAt[0]}
        y={labelAt[1]}
        textAnchor={labelAt[0] > cx + 6 ? "start" : labelAt[0] < cx - 6 ? "end" : "middle"}
        dominantBaseline="middle"
        className="fill-ok text-[11px] font-semibold"
      >
        mục tiêu {target}
      </text>

      <text x={cx} y={cy - 22} textAnchor="middle" className="fill-ink text-[40px] font-semibold">
        {value}
      </text>
      <text x={cx} y={cy} textAnchor="middle" className="fill-ink-muted text-[12px]">
        trên 990
      </text>
    </svg>
  );
}

export default function PreviewAttemptResultPage() {
  const totalCorrect = HEATMAP.filter((cell) => cell === "ok").length;
  const totalQuestions = HEATMAP.length;
  const short = ATTEMPT.target - ATTEMPT.totalScaled;
  const strengths = RADAR_AXES.filter((axis) => axis.value >= 75);
  const weaknesses = [...RADAR_AXES].sort((a, b) => a.value - b.value).slice(0, 2);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-12">
      <div className="flex flex-wrap items-center gap-2">
        <FlaskConical size={15} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
        <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">
          Trang xem trước — số đo từ một lượt làm bài thật, trang vẫn không gọi API
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1>Phân tích kết quả bài thi</h1>
          <p className="mt-1 text-ink-muted">
            <span className="font-semibold text-ink">{ATTEMPT.test}</span> · {ATTEMPT.collection} ·
            nộp lúc <span className="font-data text-[0.8125rem]">{ATTEMPT.submittedAt}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Tag tone="ok">{ATTEMPT.mode}</Tag>
          <Tag>đã nộp</Tag>
          <Tag tone={ATTEMPT.blankCount > 0 ? "warn" : "neutral"}>
            {ATTEMPT.blankCount} câu bỏ trống
          </Tag>
        </div>
      </div>

      {/* --- điểm tổng ------------------------------------------------------ */}
      <div className="mt-8 grid gap-4 lg:grid-cols-[1.2fr_1fr_1fr_1fr]">
        <Panel className="p-5 lg:col-span-1">
          <div className="flex items-center gap-2 text-ink-muted">
            <Gauge size={15} strokeWidth={1.75} aria-hidden />
            <span className="text-label font-semibold uppercase tracking-wide">Tổng điểm</span>
          </div>
          <ScoreGauge />
        </Panel>

        <Panel className="p-5">
          <div className="flex items-center gap-2 text-ink-muted">
            <Headphones size={15} strokeWidth={1.75} aria-hidden />
            <span className="text-label font-semibold uppercase tracking-wide">Nghe — L/C</span>
          </div>
          <p className="mt-3 font-data text-readout leading-none tabular-nums">
            {ATTEMPT.listeningScaled}
          </p>
          <p className="mt-2 text-small text-ink-muted">
            đúng <span className="font-data text-ink">{ATTEMPT.listeningRaw}</span>/100 câu thô
          </p>
          <div className="mt-3">
            <Meter value={ATTEMPT.listeningRaw} max={100} label="Câu đúng" />
          </div>
        </Panel>

        <Panel className="p-5">
          <div className="flex items-center gap-2 text-ink-muted">
            <BookOpen size={15} strokeWidth={1.75} aria-hidden />
            <span className="text-label font-semibold uppercase tracking-wide">Đọc — R/C</span>
          </div>
          <p className="mt-3 font-data text-readout leading-none tabular-nums">
            {ATTEMPT.readingScaled}
          </p>
          <p className="mt-2 text-small text-ink-muted">
            đúng <span className="font-data text-ink">{ATTEMPT.readingRaw}</span>/100 câu thô
          </p>
          <div className="mt-3">
            <Meter value={ATTEMPT.readingRaw} max={100} label="Câu đúng" />
          </div>
        </Panel>

        <Panel className="p-5">
          <div className="flex items-center gap-2 text-ink-muted">
            <Target size={15} strokeWidth={1.75} aria-hidden />
            <span className="text-label font-semibold uppercase tracking-wide">Mục tiêu</span>
          </div>
          <p className="mt-3 font-data text-readout leading-none tabular-nums">{ATTEMPT.target}</p>
          {/* HAI trạng thái, không phải một. Bản mẫu cũ chỉ có "còn thiếu N
              điểm" vì con số bịa ra luôn thấp hơn mục tiêu bịa ra; lượt thật
              đầu tiên chạy qua đây đã vượt mục tiêu, và câu "còn thiếu −30
              điểm" là thứ sẽ hiện ra nếu không ai nghĩ tới nhánh này. */}
          {short > 0 ? (
            <p className="mt-2 text-small text-alert">
              còn thiếu <span className="font-data font-semibold">{short}</span> điểm
            </p>
          ) : (
            <p className="mt-2 text-small text-ok">
              đã vượt <span className="font-data font-semibold">{-short}</span> điểm
            </p>
          )}
          <div className="mt-3 flex items-center gap-2 text-small text-ink-muted">
            <Clock size={14} strokeWidth={1.75} aria-hidden />
            <span className="font-data tabular-nums">
              {ATTEMPT.durationUsed}/{ATTEMPT.durationLimit} phút
            </span>
            <span>— còn {ATTEMPT.durationLimit - ATTEMPT.durationUsed} phút</span>
          </div>
        </Panel>
      </div>

      <div className="mt-6">
        <Alert tone="ok">
          Trả lời hết 200 câu và còn dư {ATTEMPT.durationLimit - ATTEMPT.durationUsed} phút. Khoảng
          cách với mục tiêu {ATTEMPT.target} không còn nằm ở tốc độ — nó nằm ở Part 5 và Part 7, hai
          phần đóng góp {200 - totalCorrect} câu sai thì mất{" "}
          {cellsOf(PARTS[4]!).filter((c) => c !== "ok").length +
            cellsOf(PARTS[6]!).filter((c) => c !== "ok").length}{" "}
          câu.
        </Alert>
      </div>

      {/* --- lục giác kỹ năng ------------------------------------------------ */}
      <div className="mt-4">
        <SectionHeader title="Điểm mạnh — điểm yếu theo kỹ năng" />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.15fr_1fr]">
        <Panel className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="m-0 p-0 text-subtitle font-semibold">Mức độ thành thạo</h3>
            <div className="flex items-center gap-4 text-small text-ink-muted">
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-0.5 w-5 bg-accent-us" aria-hidden />
                lượt này
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block h-0.5 w-5 border-t border-dashed border-accent-uk"
                  aria-hidden
                />
                trung bình 2 lượt trước
              </span>
            </div>
          </div>
          <div className="mt-2">
            <Radar />
          </div>
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel className="p-5">
            <div className="flex items-center gap-2 text-ok">
              <TrendingUp size={15} strokeWidth={2} aria-hidden />
              <span className="text-label font-semibold uppercase tracking-wide">Điểm mạnh</span>
            </div>
            <ul className="mt-3 space-y-2.5">
              {strengths.map((axis) => (
                <li key={axis.sub} className="flex items-baseline justify-between gap-3 text-small">
                  <span>
                    <span className="font-semibold">{axis.label}</span> · {axis.sub}
                  </span>
                  <span className="font-data font-semibold tabular-nums text-ok">
                    {axis.value}%
                  </span>
                </li>
              ))}
              <li className="text-small text-ink-muted">
                Nghe dài tăng {RADAR_AXES[2]!.value - RADAR_AXES[2]!.previous} điểm phần trăm và ngữ
                pháp tăng {RADAR_AXES[3]!.value - RADAR_AXES[3]!.previous} — hai mức tăng lớn nhất
                giữa lượt này và trung bình hai lượt trước.
              </li>
            </ul>
          </Panel>

          <Panel className="p-5">
            <div className="flex items-center gap-2 text-alert">
              <TrendingDown size={15} strokeWidth={2} aria-hidden />
              <span className="text-label font-semibold uppercase tracking-wide">
                Cần cải thiện
              </span>
            </div>
            <ul className="mt-3 space-y-2.5">
              {weaknesses.map((axis) => (
                <li key={axis.sub} className="text-small">
                  <span className="flex items-baseline justify-between gap-3">
                    <span>
                      <span className="font-semibold">{axis.label}</span> · {axis.sub}
                    </span>
                    <span className="font-data font-semibold tabular-nums text-alert">
                      {axis.value}%
                    </span>
                  </span>
                  <span className="mt-0.5 block text-ink-muted">{axis.note}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>

      {/* --- chi tiết từng part --------------------------------------------- */}
      <div className="mt-4">
        <SectionHeader title="Chi tiết từng phần" />
      </div>
      <Panel className="divide-y divide-rule">
        {PARTS.map((row) => {
          const cells = cellsOf(row);
          const total = cells.length;
          const correct = cells.filter((cell) => cell === "ok").length;
          const blank = cells.filter((cell) => cell === "blank").length;
          const answered = total - blank;
          const share = answered ? Math.round((correct / answered) * 100) : 0;
          return (
            <div
              key={row.part}
              className="grid gap-2 p-4 sm:grid-cols-[9rem_1fr_5rem] sm:items-center"
            >
              <div>
                <p className="text-small font-semibold">
                  Part {row.part} · {row.name}
                </p>
                <p className="text-label uppercase tracking-wide text-ink-faint">
                  {row.section === "listening" ? "Nghe" : "Đọc"} · câu {row.first}–{row.last}
                </p>
              </div>
              <div className="max-w-md">
                <Meter
                  value={correct}
                  max={total}
                  label={`${correct}/${total} đúng${blank ? ` · ${blank} bỏ trống` : ""}`}
                />
              </div>
              <p
                className={cx(
                  "font-data text-small font-semibold tabular-nums",
                  share >= 75 ? "text-ok" : share >= 60 ? "text-warn" : "text-alert",
                )}
              >
                {share}%
              </p>
            </div>
          );
        })}
      </Panel>

      {/* --- heatmap 200 câu --------------------------------------------------- */}
      <div className="mt-4">
        <SectionHeader title="Bản đồ 200 câu" />
      </div>
      <Panel className="p-5">
        <div
          className="grid gap-1"
          style={{ gridTemplateColumns: "repeat(25, minmax(0, 1fr))" }}
          role="img"
          aria-label={`Bản đồ kết quả: ${totalCorrect} câu đúng trên ${totalQuestions} câu`}
        >
          {HEATMAP.map((cell, i) => (
            <span
              key={i}
              title={`Câu ${i + 1} · ${cell === "ok" ? "đúng" : cell === "bad" ? "sai" : "bỏ trống"}`}
              className={cx(
                "aspect-square",
                cell === "ok" && "bg-ok/70",
                cell === "bad" && "bg-alert/55",
                cell === "blank" && "border border-rule-strong bg-recess",
              )}
            />
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-small text-ink-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 bg-ok/70" aria-hidden /> Đúng
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 bg-alert/55" aria-hidden /> Sai
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 border border-rule-strong bg-recess"
              aria-hidden
            />{" "}
            Bỏ trống
          </span>
          <span className="ml-auto font-data text-small tabular-nums">
            {totalCorrect}/{totalQuestions} đúng · trái → phải, câu 1 → 200
          </span>
        </div>
      </Panel>

      {/* --- tốc độ đọc -------------------------------------------------------- */}
      <div className="mt-4">
        <SectionHeader title="Tốc độ làm phần Đọc" />
      </div>
      <Panel className="p-5">
        {/*
         * Khối này từng vẽ bốn thanh "giây mỗi câu" so với mục tiêu. Không con
         * số nào trong đó dựng lại được từ dữ liệu thật, và đó là phát hiện
         * đáng giá nhất của việc thay số bịa bằng số đo: hệ thống hiện KHÔNG
         * ghi lại thời gian làm từng câu.
         */}
        <p className="text-small text-ink-muted">
          Chưa dựng được từ dữ liệu thật. Cần hai thứ mà lược đồ hiện tại không có:
        </p>
        <ul className="mt-3 space-y-2 text-small text-ink-muted">
          <li>
            <span className="font-semibold text-ink">Mốc thời gian trả lời còn giữ lại.</span>{" "}
            <span className="font-data text-[0.8125rem]">attempt_item.answered_at</span> bị ghi đè
            mỗi lần đổi đáp án, nên nó nói lần cuối chạm vào câu đó chứ không nói câu đó tốn bao lâu
            — và đổi ý một lần là mất luôn dấu vết lần đầu.
          </li>
          <li>
            <span className="font-semibold text-ink">Đồng hồ theo part.</span>{" "}
            <span className="font-data text-[0.8125rem]">attempt_part</span> chỉ có hai cột{" "}
            <span className="font-data text-[0.8125rem]">(attempt_id, part)</span> — nó trả lời
            &ldquo;lượt này gồm những part nào&rdquo;, không phải &ldquo;ở part này bao lâu&rdquo;.
          </li>
        </ul>
        <p className="mt-3 text-small text-ink-muted">
          Cho tới lúc đó, con số duy nhất về thời gian mà hệ thống thật sự biết là tổng thời gian
          của cả lượt:{" "}
          <span className="font-data tabular-nums text-ink">
            {ATTEMPT.durationUsed}/{ATTEMPT.durationLimit} phút
          </span>
          .
        </p>
      </Panel>

      {/* --- nhận xét gợi ý ---------------------------------------------------- */}
      <div className="mt-4">
        <SectionHeader title="Nhận xét và đề xuất luyện tập" />
      </div>
      <div className="ai-border">
        <div className="flex flex-col gap-4 rounded bg-panel p-5">
          <div className="flex items-center gap-2">
            <Sparkles size={16} strokeWidth={1.75} className="text-accent-uk" aria-hidden />
            <h3 className="m-0 p-0 text-subtitle font-semibold">Trợ giảng nhận xét</h3>
            <Tag tone="action">AI</Tag>
          </div>
          <p className="text-small text-ink-muted">
            Em đã vượt mục tiêu {ATTEMPT.target} và làm hết bài sớm {""}
            {ATTEMPT.durationLimit - ATTEMPT.durationUsed} phút, nên việc tiếp theo không phải là
            luyện nhanh hơn. Điểm Nghe {ATTEMPT.listeningScaled} đang kéo tổng điểm, còn Đọc{" "}
            {ATTEMPT.readingScaled} thì đứng lại ở hai chỗ: Part 5 (20/30) và Part 7 đoạn đơn
            (25/39). Riêng câu 105–109 sai liền năm câu — chuỗi dài nhất của cả bài — đáng xem lại
            theo cụm chứ không theo từng câu — sai liền nhau thường là một điểm ngữ pháp chứ không
            phải bảy lần đãng trí.
          </p>
          <div className="flex flex-wrap gap-2">
            <ButtonLink href="/learn/tests" size="sm">
              Luyện Part 5 ngữ pháp
            </ButtonLink>
            <ButtonLink href="/learn/tests" size="sm" variant="secondary">
              Luyện Part 7 đoạn đơn
            </ButtonLink>
            <Link
              href="/profile"
              className="text-small font-semibold text-action-ink underline-offset-2 hover:underline"
            >
              Nâng mục tiêu lên 800
            </Link>
          </div>
        </div>
      </div>

      <div className="mt-8">
        <Alert tone="warn">
          <strong>Số thật, nhưng viết cứng — và người làm bài là máy.</strong> Điểm, số câu đúng
          từng part, bản đồ 200 câu và cả hai lớp của lục giác đều đo từ ba lượt đã nộp của một tài
          khoản trên stack dev, chấm bằng chính <span className="font-data">score_attempt</span> và
          bảng <span className="font-data">score_conversion</span>. Hai điều trang này KHÔNG có:
          người làm bài là một bộ sinh số ngẫu nhiên đặt trước tỉ lệ đúng, nên chênh lệch nhỏ giữa
          hai trục là nhiễu chứ không phải chân dung ai; và phần &ldquo;Trợ giảng nhận xét&rdquo; do
          người viết tay theo đúng các con số ở trên, chưa có mô hình nào sinh ra nó. Khi nối
          backend, các khối sẽ đọc thẳng từ lượt làm — trừ khối tốc độ đọc, vốn còn thiếu dữ liệu ở
          tầng lược đồ.
        </Alert>
      </div>
    </div>
  );
}
