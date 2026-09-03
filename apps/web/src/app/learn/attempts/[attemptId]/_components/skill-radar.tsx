"use client";

import { type SkillScore } from "@toeic-pilot/shared";

/*
 * Biểu đồ đa giác cho hồ sơ kỹ năng.
 *
 * Vẽ tay bằng SVG chứ không kéo thư viện chart: cả biểu đồ này là vài phép
 * lượng giác, còn một thư viện đem theo runtime riêng, chủ đề màu riêng và bo
 * góc riêng — ba thứ design system ở đây quy định chặt (§6.2, §6.3).
 *
 * Nó trả lời câu hỏi mà danh sách số không trả lời được: hồ sơ này LỆCH về
 * phía nào. Bảy trục cạnh nhau cho thấy ngay một hình méo về một góc, trong khi
 * bảy dòng số phải đọc hết rồi tự so trong đầu. Danh sách số vẫn nằm bên cạnh,
 * vì hình đa giác không đọc ra được "7/14".
 */

const AXES = 7;
const SIZE = { w: 420, h: 330, cx: 210, cy: 158, r: 104 };
const RINGS = [0.25, 0.5, 0.75, 1];

/** Bỏ tiền tố lặp lại ở mọi nhãn, giữ phần thật sự phân biệt chúng. */
function short(name: string): string {
  const trimmed = name
    .replace(/^Câu hỏi về\s+/i, "")
    .replace(/^Câu hỏi\s+/i, "")
    .replace(/^Câu\s+/i, "");
  const cleaned = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  return cleaned.length > 26 ? `${cleaned.slice(0, 25).trimEnd()}…` : cleaned;
}

/** Ngắt nhãn thành tối đa hai dòng, ưu tiên ngắt ở khoảng trắng gần giữa. */
function wrap(text: string): string[] {
  if (text.length <= 14) return [text];
  const words = text.split(" ");
  const lines: string[] = ["", ""];
  for (const word of words) {
    const index = lines[0].length < text.length / 2 ? 0 : 1;
    lines[index] = lines[index] ? `${lines[index]} ${word}` : word;
  }
  return lines.filter(Boolean);
}

function point(index: number, ratio: number) {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / AXES;
  return {
    x: SIZE.cx + SIZE.r * ratio * Math.cos(angle),
    y: SIZE.cy + SIZE.r * ratio * Math.sin(angle),
  };
}

function polygon(ratios: number[]): string {
  return ratios.map((ratio, index) => Object.values(point(index, ratio)).join(",")).join(" ");
}

export function SkillRadar({ skills }: { skills: SkillScore[] }) {
  // Đúng bảy trục, luôn luôn. Ít hơn thì hình sụp thành tam giác và không còn
  // là hồ sơ; nhiều hơn thì nhãn chồng lên nhau ở khổ điện thoại.
  const shown = skills.slice(0, AXES);
  if (shown.length < 3) return null;

  const ratios = shown.map((skill) => skill.correct / skill.count);
  const average = ratios.reduce((sum, ratio) => sum + ratio, 0) / ratios.length;

  return (
    <svg
      viewBox={`0 0 ${SIZE.w} ${SIZE.h}`}
      className="h-auto w-full max-w-md"
      role="img"
      aria-label={`Hồ sơ kỹ năng: ${shown
        .map((skill) => `${short(skill.name)} ${skill.correct} trên ${skill.count}`)
        .join(", ")}`}
    >
      {RINGS.map((ring) => (
        <polygon
          key={ring}
          points={polygon(Array.from({ length: shown.length }, () => ring))}
          className="fill-none stroke-rule"
          strokeWidth={1}
        />
      ))}

      {shown.map((skill, index) => {
        const outer = point(index, 1);
        return (
          <line
            key={skill.name}
            x1={SIZE.cx}
            y1={SIZE.cy}
            x2={outer.x}
            y2={outer.y}
            className="stroke-rule"
            strokeWidth={1}
          />
        );
      })}

      {/* Vòng trung bình của chính người học: một hình méo chỉ đọc được khi có
          thứ để so, và mốc tự nhiên nhất là mức trung bình của chính họ. */}
      <polygon
        points={polygon(Array.from({ length: shown.length }, () => average))}
        className="fill-none stroke-ink-faint"
        strokeWidth={1}
        strokeDasharray="3 3"
      />

      <polygon points={polygon(ratios)} className="fill-action/15 stroke-action" strokeWidth={2} />

      {ratios.map((ratio, index) => {
        const dot = point(index, ratio);
        return (
          <circle
            key={shown[index].name}
            cx={dot.x}
            cy={dot.y}
            r={3.5}
            className={ratio < average ? "fill-warn" : "fill-action"}
          />
        );
      })}

      {shown.map((skill, index) => {
        const at = point(index, 1.16);
        const anchor = Math.abs(at.x - SIZE.cx) < 10 ? "middle" : at.x > SIZE.cx ? "start" : "end";
        const lines = wrap(short(skill.name));
        return (
          <text
            key={skill.name}
            x={at.x}
            y={at.y - (lines.length - 1) * 5}
            textAnchor={anchor}
            className="fill-ink-muted text-[10px]"
          >
            {lines.map((line, row) => (
              <tspan key={line} x={at.x} dy={row === 0 ? 0 : 11}>
                {line}
              </tspan>
            ))}
            <tspan x={at.x} dy={11} className="fill-ink font-semibold">
              {Math.round(ratios[index] * 100)}%
            </tspan>
          </text>
        );
      })}
    </svg>
  );
}
