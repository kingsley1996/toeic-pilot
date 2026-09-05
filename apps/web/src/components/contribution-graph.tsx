"use client";

import type { StudyDay } from "@toeic-pilot/shared";
import { useMemo } from "react";

import { cx } from "@/components/ui";

/*
 * Lưới hoạt động một năm, kiểu lịch đóng góp.
 *
 * Đây là một THIẾT BỊ ĐO chứ không phải hình trang trí: mỗi ô là một ngày có
 * thật, cột là tuần, hàng là thứ trong tuần. Nó trả lời được câu mà bốn con số
 * thống kê không trả lời nổi — "mình học đều hay học dồn" — và câu đó là câu
 * quyết định người ta có thi được hay không.
 *
 * Màu dùng thang `ok`, KHÔNG dùng `action`. Chu sa là màu của hành động (§2.1);
 * ba trăm ô chu sa trên một trang sẽ đánh nhau với chính cái nút Lưu ở dưới, và
 * "ngày đã học" là một thành tựu chứ không phải một lời mời bấm.
 */

/** Chủ nhật đầu tuần, khớp với `WEEKDAYS` bên dưới. */
const WEEKDAYS = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
const MONTHS = [
  "Th1",
  "Th2",
  "Th3",
  "Th4",
  "Th5",
  "Th6",
  "Th7",
  "Th8",
  "Th9",
  "Th10",
  "Th11",
  "Th12",
];

/*
 * Bốn bậc, và các ngưỡng là số lượt học chứ không phải phân vị.
 *
 * Phân vị (kiểu "20% ngày bận nhất") làm ô đổi màu khi những NGÀY KHÁC thay
 * đổi, nên một ngày đã qua có thể nhạt đi vì hôm nay học nhiều — thang đo mà
 * quá khứ tự viết lại thì không đo được gì.
 */
const LEVELS = ["bg-recess", "bg-ok/25", "bg-ok/50", "bg-ok/75", "bg-ok"] as const;

function levelFor(total: number): number {
  if (total === 0) return 0;
  if (total < 5) return 1;
  if (total < 15) return 2;
  if (total < 30) return 3;
  return 4;
}

/** `YYYY-MM-DD` → Date ở UTC, để không bao giờ lệch một ngày vì múi giờ máy. */
function parseDay(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y!, m! - 1, d!));
}

function toIso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

type Cell = {
  iso: string;
  total: number;
  reviews: number;
  dictation: number;
  grammar: number;
  inRange: boolean;
};

export function ContributionGraph({
  calendar,
  today,
  windowDays,
}: {
  calendar: StudyDay[];
  today: string;
  windowDays: number;
}) {
  const { weeks, monthLabels, activeDays } = useMemo(() => {
    const byDay = new Map(calendar.map((day) => [day.date, day]));
    const end = parseDay(today);
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - (windowDays - 1));

    /*
     * Lùi điểm bắt đầu về Chủ nhật gần nhất để mọi cột đều là một tuần đủ. Các
     * ô rơi ra trước cửa sổ được dựng nhưng đánh dấu `inRange: false` — vẽ chúng
     * mờ đi thay vì bỏ trống giữ cho lưới là hình chữ nhật, còn bỏ trống sẽ làm
     * cột đầu ngắn hơn và trông như một lỗi hiển thị.
     */
    const gridStart = new Date(start);
    gridStart.setUTCDate(gridStart.getUTCDate() - gridStart.getUTCDay());

    const columns: Cell[][] = [];
    const labels: Array<{ column: number; text: string }> = [];
    const cursor = new Date(gridStart);
    let lastMonth = -1;

    while (cursor <= end) {
      const column: Cell[] = [];
      for (let weekday = 0; weekday < 7; weekday += 1) {
        const iso = toIso(cursor);
        const day = byDay.get(iso);
        const reviews = day?.reviews ?? 0;
        const dictation = day?.dictation_items ?? 0;
        const grammar = day?.grammar ?? 0;
        column.push({
          iso,
          reviews,
          dictation,
          grammar,
          total: reviews + dictation + grammar,
          inRange: cursor >= start && cursor <= end,
        });
        cursor.setUTCDate(cursor.getUTCDate() + 1);
      }
      // Nhãn tháng đặt ở cột chứa ngày đầu tiên của tháng mới, không phải cứ
      // bốn cột một nhãn — tháng dài ngắn khác nhau nên cách đều sẽ trôi dần.
      const month = parseDay(column[0]!.iso).getUTCMonth();
      if (month !== lastMonth) {
        labels.push({ column: columns.length, text: MONTHS[month]! });
        lastMonth = month;
      }
      columns.push(column);
    }

    return {
      weeks: columns,
      monthLabels: labels,
      activeDays: columns.flat().filter((cell) => cell.inRange && cell.total > 0).length,
    };
  }, [calendar, today, windowDays]);

  return (
    <div>
      {/* Cuộn ngang trong chính nó: 53 cột không vừa màn hình điện thoại, và để
          cả trang cuộn ngang là hỏng bố cục mọi thứ khác. */}
      <div className="overflow-x-auto pb-1">
        <div className="inline-block min-w-full">
          <div className="flex gap-1">
            {/* Cột nhãn thứ: chỉ T2/T4/T6 như lịch đóng góp thật — bảy nhãn
                chồng lên nhau ở cỡ chữ này thì không đọc được cái nào. */}
            <div className="mr-1 flex shrink-0 flex-col gap-[3px] pt-[18px]">
              {WEEKDAYS.map((label, index) => (
                <span
                  key={label}
                  className="h-[13px] font-data text-[9px] leading-[13px] text-ink-faint"
                >
                  {index % 2 === 1 ? label : ""}
                </span>
              ))}
            </div>

            <div>
              <div className="relative mb-1 h-[14px]">
                {monthLabels.map((label) => (
                  <span
                    key={`${label.column}-${label.text}`}
                    className="absolute font-data text-[9px] leading-[14px] text-ink-faint"
                    style={{ left: `${label.column * 16}px` }}
                  >
                    {label.text}
                  </span>
                ))}
              </div>

              <div className="flex gap-[3px]">
                {weeks.map((week) => (
                  <div key={week[0]!.iso} className="flex flex-col gap-[3px]">
                    {week.map((cell) => (
                      <span
                        key={cell.iso}
                        title={
                          cell.inRange
                            ? `${cell.iso}: ${cell.reviews} lượt ôn · ${cell.dictation} câu nghe · ${cell.grammar} câu ngữ pháp`
                            : cell.iso
                        }
                        className={cx(
                          "h-[13px] w-[13px] rounded",
                          cell.inRange ? LEVELS[levelFor(cell.total)] : "bg-recess/40",
                        )}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-2.5 flex items-center justify-between gap-4 text-small text-ink-muted">
        <span>
          <span className="font-data text-ink">{activeDays}</span> ngày đã học trong{" "}
          {windowDays === 365 ? "một năm" : `${windowDays} ngày`} qua
        </span>
        <span className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase text-ink-faint">ít</span>
          {LEVELS.map((tone) => (
            <span key={tone} className={cx("h-[11px] w-[11px] rounded", tone)} />
          ))}
          <span className="text-[10px] uppercase text-ink-faint">nhiều</span>
        </span>
      </div>
    </div>
  );
}
