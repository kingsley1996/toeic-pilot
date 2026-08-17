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

/* Trang xem trước THUẦN UI: mọi con số bên dưới là dữ liệu mẫu, không gọi API. */

type CellState = "ok" | "bad" | "blank";

const ATTEMPT = {
  test: "TOEIC 2026 — Test 1",
  collection: "Bộ đề TOEIC 2026",
  submittedAt: "09:47, 15/08/2026",
  mode: "Luyện thi",
  durationUsed: 120,
  durationLimit: 120,
  blankCount: 3,
  listeningRaw: 69,
  listeningScaled: 370,
  readingRaw: 70,
  readingScaled: 372,
  totalScaled: 742,
  target: 800,
};

const RADAR_AXES: { label: string; sub: string; value: number; previous: number }[] = [
  { label: "P1", sub: "Tranh mô tả", value: 83, previous: 80 },
  { label: "P2", sub: "Hỏi đáp", value: 72, previous: 68 },
  { label: "P3–P4", sub: "Nghe dài", value: 66, previous: 64 },
  { label: "P5–P6", sub: "Ngữ pháp", value: 79, previous: 70 },
  { label: "P7", sub: "Đoạn đơn", value: 74, previous: 60 },
  { label: "P7", sub: "Đoạn kép", value: 48, previous: 45 },
];

const PARTS: {
  part: number;
  name: string;
  section: "listening" | "reading";
  total: number;
  correct: number;
  blank: number;
  time: string;
  timeNote: string;
}[] = [
  {
    part: 1,
    name: "Photos",
    section: "listening",
    total: 6,
    correct: 5,
    blank: 0,
    time: "—",
    timeNote: "45 phút theo băng",
  },
  {
    part: 2,
    name: "Question-Response",
    section: "listening",
    total: 25,
    correct: 18,
    blank: 0,
    time: "—",
    timeNote: "nghe theo băng",
  },
  {
    part: 3,
    name: "Conversations",
    section: "listening",
    total: 39,
    correct: 24,
    blank: 0,
    time: "—",
    timeNote: "nghe theo băng",
  },
  {
    part: 4,
    name: "Talks",
    section: "listening",
    total: 30,
    correct: 22,
    blank: 0,
    time: "—",
    timeNote: "nghe theo băng",
  },
  {
    part: 5,
    name: "Incomplete Sentences",
    section: "reading",
    total: 30,
    correct: 25,
    blank: 0,
    time: "14:00",
    timeNote: "mục tiêu 15:00",
  },
  {
    part: 6,
    name: "Text Completion",
    section: "reading",
    total: 16,
    correct: 12,
    blank: 0,
    time: "09:20",
    timeNote: "mục tiêu 08:00",
  },
  {
    part: 7,
    name: "Reading Comprehension",
    section: "reading",
    total: 54,
    correct: 33,
    blank: 3,
    time: "51:40",
    timeNote: "mục tiêu 52:00",
  },
];

const PACING: { label: string; actual: number; target: number; unit: string }[] = [
  { label: "P5 — mỗi câu", actual: 28, target: 30, unit: "giây" },
  { label: "P6 — mỗi câu", actual: 35, target: 30, unit: "giây" },
  { label: "P7 đoạn đơn — mỗi câu", actual: 78, target: 70, unit: "giây" },
  { label: "P7 đoạn kép — mỗi câu", actual: 105, target: 85, unit: "giây" },
];

function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle<T>(items: T[], random: () => number): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

const HEATMAP: CellState[] = (() => {
  const random = mulberry32(20260815);
  const cells: CellState[] = [];
  for (const row of PARTS) {
    const answered = row.total - row.blank;
    const answeredCells = shuffle<CellState>(
      [...Array(row.correct).fill("ok"), ...Array(answered - row.correct).fill("bad")],
      random,
    );
    cells.push(...answeredCells, ...Array(row.blank).fill("blank"));
  }
  return cells;
})();

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
  const cx = 190;
  const cy = 158;
  const radius = 112;
  const current = RADAR_AXES.map((axis, i) =>
    radarPoint(i, axis.value, cx, cy, radius).join(","),
  ).join(" ");
  const previous = RADAR_AXES.map((axis, i) =>
    radarPoint(i, axis.previous, cx, cy, radius).join(","),
  ).join(" ");

  return (
    <svg
      viewBox="0 0 380 330"
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
        const [x, y] = radarPoint(i, 126, cx, cy, radius);
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
  const cx = 150;
  const cy = 128;
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

  return (
    <svg
      viewBox="0 0 300 148"
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
        x={tickOuter[0]}
        y={tickOuter[1] + 22}
        textAnchor="middle"
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
  const totalCorrect = PARTS.reduce((sum, row) => sum + row.correct, 0);
  const totalQuestions = PARTS.reduce((sum, row) => sum + row.total, 0);
  const strengths = RADAR_AXES.filter((axis) => axis.value >= 75);
  const weaknesses = [...RADAR_AXES].sort((a, b) => a.value - b.value).slice(0, 2);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:py-12">
      <div className="flex flex-wrap items-center gap-2">
        <FlaskConical size={15} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
        <span className="text-label font-semibold uppercase tracking-wide text-ink-muted">
          Trang xem trước — dữ liệu mẫu, không kết nối máy chủ
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
          <p className="mt-2 text-small text-alert">
            còn thiếu{" "}
            <span className="font-data font-semibold">{ATTEMPT.target - ATTEMPT.totalScaled}</span>{" "}
            điểm
          </p>
          <div className="mt-3 flex items-center gap-2 text-small text-ink-muted">
            <Clock size={14} strokeWidth={1.75} aria-hidden />
            <span className="font-data tabular-nums">
              {ATTEMPT.durationUsed}/{ATTEMPT.durationLimit} phút
            </span>
            <span>— hết giờ</span>
          </div>
        </Panel>
      </div>

      <div className="mt-6">
        <Alert tone="warn">
          Bài thi kết thúc đúng giờ và còn {ATTEMPT.blankCount} câu chưa kịp trả lời ở cuối Part 7 —
          tốc độ đọc đoạn kép đang là điểm nghẽn lớn nhất.
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
                trung bình 3 lượt trước
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
                Ngữ pháp tăng {RADAR_AXES[3]!.value - RADAR_AXES[3]!.previous} điểm phần trăm so với
                trước — chiến lược luyện Part 5 đang hiệu quả.
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
                  <span className="mt-0.5 block text-ink-muted">
                    {axis.sub === "Đoạn kép"
                      ? "Sai nhiều ở câu suy luận và tìm chi tiết rải giữa hai văn bản; thời gian mỗi câu vượt mục tiêu 20 giây."
                      : "Mất dấu sau lượt nói thứ hai của người nói; cần luyện nghe nối giữa các câu."}
                  </span>
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
          const answered = row.total - row.blank;
          const share = answered ? Math.round((row.correct / answered) * 100) : 0;
          return (
            <div
              key={row.part}
              className="grid gap-2 p-4 sm:grid-cols-[8rem_1fr_7rem_7rem] sm:items-center"
            >
              <div>
                <p className="text-small font-semibold">
                  Part {row.part} · {row.name}
                </p>
                <p className="text-label uppercase tracking-wide text-ink-faint">
                  {row.section === "listening" ? "Nghe" : "Đọc"}
                </p>
              </div>
              <div className="max-w-md">
                <Meter
                  value={row.correct}
                  max={row.total}
                  label={`${row.correct}/${row.total} đúng${row.blank ? ` · ${row.blank} bỏ trống` : ""}`}
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
              <p className="text-small text-ink-muted">
                <span className="font-data tabular-nums">{row.time}</span>
                <span className="block text-label text-ink-faint">{row.timeNote}</span>
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
      <Panel className="divide-y divide-rule">
        {PACING.map((row) => {
          const over = row.actual > row.target;
          const pct = Math.min(
            100,
            Math.round((row.actual / Math.max(row.actual, row.target)) * 100),
          );
          const targetPct = Math.min(
            100,
            Math.round((row.target / Math.max(row.actual, row.target)) * 100),
          );
          return (
            <div key={row.label} className="p-4">
              <div className="flex items-baseline justify-between text-small">
                <span className="font-semibold">{row.label}</span>
                <span className={cx("font-data tabular-nums", over ? "text-alert" : "text-ok")}>
                  {row.actual}s / mục tiêu {row.target}s
                  {over ? ` · vượt ${row.actual - row.target}s` : ""}
                </span>
              </div>
              <div className="relative mt-2 h-2 w-full bg-recess">
                <div
                  className={cx("h-full", over ? "bg-alert/80" : "bg-ok/75")}
                  style={{ width: `${over ? 100 : pct}%` }}
                />
                <span
                  className="absolute top-[-3px] h-3.5 w-0.5 bg-ink"
                  style={{ left: `${over ? targetPct : 100}%` }}
                  aria-hidden
                />
              </div>
              <p className="mt-1.5 text-label uppercase tracking-wide text-ink-faint">
                vạch đen = mục tiêu · {row.unit}/câu
              </p>
            </div>
          );
        })}
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
            Em nghe tốt dạng ngắn (Part 1–2) và nắm chắc ngữ pháp Part 5, nhưng hụt hơi ở nghe hội
            thoại dài và đọc đoạn kép. Khoảng cách tới mục tiêu {ATTEMPT.target} chủ yếu nằm ở hai
            vùng đó — nếu kéo mỗi vùng lên 70% là đủ bù {ATTEMPT.target - ATTEMPT.totalScaled} điểm.
          </p>
          <div className="flex flex-wrap gap-2">
            <ButtonLink href="/learn/tests" size="sm">
              Luyện Part 3–4 nghe dài
            </ButtonLink>
            <ButtonLink href="/learn/tests" size="sm" variant="secondary">
              Luyện Part 7 đoạn kép
            </ButtonLink>
            <Link
              href="/dashboard"
              className="text-small font-semibold text-action-ink underline-offset-2 hover:underline"
            >
              Đặt kế hoạch 14 ngày tới mục tiêu 800
            </Link>
          </div>
        </div>
      </div>

      <div className="mt-8">
        <Alert tone="warn">
          <strong>Dữ liệu mẫu.</strong> Trang này chỉ dùng để duyệt giao diện — mọi con số là giả
          lập, kể cả lục giác, bản đồ câu và nhận xét trợ giảng. Khi nối backend thật, các khối sẽ
          đọc từ kết quả lượt làm và nhãn kỹ năng (72 mã theo taxonomy) thay vì dữ liệu cứng.
        </Alert>
      </div>
    </div>
  );
}
