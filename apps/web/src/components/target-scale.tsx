"use client";

import { cx } from "@/components/ui";

/*
 * Thang điểm có vạch chia — thành phần chữ ký của sản phẩm (DESIGN-SYSTEM §10).
 *
 * Vạch chia là NGƯỠNG THẬT: 255 · 405 · 605 · 785 · 905 là sáu bậc năng lực ETS
 * công bố, không phải mốc tròn cho đẹp. Đó là điểm khác nhau giữa một thiết bị
 * đo và một dải gradient — vạch chia trả lời được câu "800 nghĩa là gì", còn
 * gradient thì không.
 *
 * Thành phần này KHÔNG in lại con số mục tiêu, dù §10 vẽ nó cỡ lớn ở phía trên.
 * Trong trang hồ sơ, con số đã nằm ngay ô "Điểm mục tiêu" phía trên; in lần nữa
 * thì hai lần xuất hiện của cùng một dữ kiện trông như một lỗi hiển thị, và
 * phần thang — thứ DUY NHẤT trả lời được "800 đứng ở đâu" — bị lu mờ theo. Con
 * số cỡ lớn của §10 dành cho điểm ƯỚC TÍNH, thứ chưa tồn tại cho tới khi phần
 * thi thử mở.
 *
 * Bo góc 0 ở thanh và vạch chia: ngoại lệ `radius-none` mà §6.2 dành riêng cho
 * thang điểm. Vạch chia của thiết bị đo không bo tròn.
 */

const MIN = 10;
const MAX = 990;

const BANDS = [
  { from: 10, label: "Cơ bản" },
  { from: 255, label: "Sơ cấp" },
  { from: 405, label: "Sơ cấp+" },
  { from: 605, label: "Hạn chế" },
  { from: 785, label: "Làm việc+" },
  { from: 905, label: "Quốc tế" },
];

const TICKS = [10, 255, 405, 605, 785, 905, 990];

function pct(score: number): number {
  return ((score - MIN) / (MAX - MIN)) * 100;
}

export function bandFor(score: number): string {
  return [...BANDS].reverse().find((band) => score >= band.from)?.label ?? BANDS[0]!.label;
}

export function TargetScale({ target }: { target: number }) {
  const current = bandFor(target);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <p className="text-label font-semibold uppercase text-ink-faint">Trên thang năng lực</p>
        <p className="font-data text-small tabular-nums text-ink-muted">
          {target} / {MAX}
        </p>
      </div>

      <div className="mt-4">
        {/* Thanh đo. `rounded-none` là ngoại lệ có chủ ý, không phải sơ suất. */}
        <div className="relative h-2.5 w-full rounded-none bg-recess">
          <div
            className="absolute inset-y-0 left-0 rounded-none bg-action/25"
            style={{ width: `${pct(target)}%` }}
          />
          {/* Vạch mục tiêu là một VẠCH RIÊNG, không phải điểm cuối của thang:
              đây là mốc người học tự đặt, còn thang là thang của kỳ thi. */}
          <div
            className="absolute -top-1.5 bottom-[-6px] w-0.5 bg-action"
            style={{ left: `calc(${pct(target)}% - 1px)` }}
          />
        </div>

        <div className="relative mt-2 h-4">
          {TICKS.map((tick) => (
            <span
              key={tick}
              className={cx(
                "absolute top-0 font-data text-[10px] leading-4 tabular-nums text-ink-faint",
                tick === MIN && "translate-x-0",
                tick === MAX && "-translate-x-full",
                tick !== MIN && tick !== MAX && "-translate-x-1/2",
              )}
              style={{ left: `${pct(tick)}%` }}
            >
              {tick}
            </span>
          ))}
        </div>

        {/*
         * Tên các bậc, đặt đúng bề rộng của bậc đó trên thang.
         *
         * Đây mới là phần trả lời câu hỏi mà ô "Điểm mục tiêu" phía trên không
         * trả lời được: 800 nằm trong bậc nào, và còn cách bậc kế tiếp bao xa.
         * Bậc đang chứa mục tiêu được tô đậm — phần còn lại là ngữ cảnh.
         */}
        <div className="mt-1.5 flex">
          {BANDS.map((band, index) => {
            const next = BANDS[index + 1]?.from ?? MAX;
            const width = pct(next) - pct(band.from);
            const active = band.label === current;
            return (
              <span
                key={band.label}
                style={{ width: `${width}%` }}
                className={cx(
                  "truncate border-l border-rule pl-1 text-[10px] leading-4",
                  active ? "font-semibold text-ink" : "text-ink-faint",
                )}
              >
                {band.label}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
