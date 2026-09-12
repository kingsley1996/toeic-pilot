"use client";

import {
  type PlacementGate,
  type StudyPlanItemPublic,
  type StudyPlanPublic,
} from "@toeic-pilot/shared";
import { ChevronDown, ChevronLeft, ChevronRight, ClipboardCheck, Flag } from "lucide-react";
import { useMemo, useState } from "react";

import { ButtonLink, cx } from "@/components/ui";

/**
 * Lịch kế hoạch học — lưới tháng tự vẽ, không thư viện.
 *
 * Đã thử `react-day-picker` và bỏ: nó là DATE PICKER — ô vuông, số căn giữa,
 * mọi thứ sinh ra để bấm chọn một ngày. Nhét danh sách nhiệm vụ vào ô của nó
 * là đánh nhau với style của lib ở mọi dòng CSS. Một lưới `grid-cols-7` với
 * số học ngày thuần Việt ở đây ít code hơn VÀ kiểm soát được mật độ chữ trong
 * ô — đúng chỗ bản lib hỏng.
 *
 * Ngày của mỗi mục KHÔNG nằm trong database: API đóng gói hàng đợi theo phút
 * trên lịch neo `starts_at` (mỗi ngày ≤ phút/ngày, mỗi tuần ≤ số ngày học —
 * phần còn lại của tuần là nghỉ). Tick một mục KHÔNG dịch các mục khác: ngày
 * hẹn là lời hẹn đọc được. Mục đã xong đứng nguyên ở ô hẹn, mang ✓
 * của bản ghi học — cái ✓ đứng đúng chỗ việc xảy ra, còn ô hẹn thì trống.
 *
 * "Hôm nay" lấy từ máy chủ (`plan.today`), không `new Date()`: múi máy khác
 * múi người học là cả lưới lệch một cột, im lặng — cùng bài học với lịch hoạt
 * động ở /profile. Mọi phép tính ngày chạy trên chuỗi `yyyy-MM-dd` (so sánh
 * chuỗi là so sánh chronologic với ISO), Date chỉ xuất hiện ở biên để đọc
 * số ngày/tháng của ô.
 */

const CORE_KINDS = new Set(["grammar_lesson", "part_drill", "mini_test", "mock_test"]);
const TEST_KINDS = new Set(["mini_test", "mock_test"]);
const WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
/** Số chip tối đa trong một ô — phần thừa vào "+n", bản đầy đủ ở panel ngày.
 * Nhiều hơn là chữ chồng chữ, tức là cái lưới hỏng. */
const CHIPS_PER_CELL = 3;

export function isCorePlanItem(item: StudyPlanItemPublic): boolean {
  return CORE_KINDS.has(item.kind);
}

/** Mục kiểm tra: khép bằng BÀI NỘP, không bằng tick (API từ chối 409 với hai
 * kind này). UI phải nói cùng một điều — checkbox khoá ngay từ đầu. */
export function isPlanTestItem(item: StudyPlanItemPublic): boolean {
  return TEST_KINDS.has(item.kind);
}

/** Màu chấm/chip: xong là xanh, lời khuyên lõi là accent, bài kiểm tra là
 * warn (nó là sự kiện ĐO, khác một buổi học), nhịp nền trung tính. */
function dotClass(item: StudyPlanItemPublic): string {
  if (item.done) return "bg-ok";
  if (isPlanTestItem(item)) return "bg-warn";
  return isCorePlanItem(item) ? "bg-action" : "bg-rule-strong";
}

/** Một bảng đường dẫn cho mọi chỗ nhảy tới việc của một mục — hai chỗ tự nối
 * URL là hai chỗ có thể lệch (bug cũ: lesson id bị đưa vào route topic).
 * `item.link` do generator dựng (drill kèm `?labels=`, board từ vựng theo chủ
 * đề) THẮNG; bảng kind chỉ còn là đường cho hàng cũ thiếu link. */
export function planItemHref(item: StudyPlanItemPublic): string {
  if (item.link) return item.link;
  if (item.kind === "grammar_lesson") {
    return item.topic_id && item.ref_id
      ? `/learn/grammar/${item.topic_id}/${item.ref_id}`
      : "/learn/grammar";
  }
  if (item.kind === "part_drill") return `/learn/parts/${item.part}/drill`;
  if (item.kind === "vocab_review") return "/learn/review";
  if (item.kind === "mini_test") return "/learn/placement";
  if (item.kind === "mock_test") {
    return item.collection_slug && item.test_slug
      ? `/learn/tests/${item.collection_slug}/${item.test_slug}?plan=mock`
      : "/learn/tests";
  }
  return "/learn/dictation";
}

export function planItemCta(item: StudyPlanItemPublic): string {
  if (item.kind === "grammar_lesson") return "Học";
  if (item.kind === "part_drill") return "Luyện";
  if (item.kind === "vocab_review") return "Ôn";
  if (item.kind === "mini_test") return "Đo lại";
  if (item.kind === "mock_test") return "Thi thử";
  return "Chép";
}

/** Chỉ worth nhắc cooldown khi cửa mở MUỘN HƠN ngày hẹn của chính ô đó —
 * nhắc sớm hơn là chữ thừa làm người học tưởng mình bị chặn. */
function cooldownOpensAfter(item: StudyPlanItemPublic, gate?: PlacementGate | null): boolean {
  if (!gate || gate.cooldown_ok || !gate.next_available_at || !item.day) return false;
  const opens = new Date(gate.next_available_at).toLocaleDateString("sv-SE");
  return opens > item.day;
}

/** Ô lịch của một mục: LUÔN là ngày hẹn. Tick hôm nay cho mục hẹn tuần sau
 * phải để lại ✓ ở đúng ô tuần sau — đổi ô theo ngày xong thật là cái "dồn
 * task" người học đã bác, kể cả khi nó chỉ là hiển thị. */
export function planItemDate(item: StudyPlanItemPublic): string | null {
  return item.day ?? null;
}

const iso = (y: number, m: number, d: number): string =>
  `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

function shiftMonth(anchor: Date, delta: number): Date {
  return new Date(anchor.getFullYear(), anchor.getMonth() + delta, 1);
}

export function PlanCalendar({
  plan,
  onTick,
  onPickMock,
  placementGate,
}: {
  plan: StudyPlanPublic;
  onTick: (item: StudyPlanItemPublic, done: boolean) => void;
  onPickMock: (item: StudyPlanItemPublic, testId: string) => void;
  placementGate?: PlacementGate | null;
}) {
  const byDay = useMemo(() => {
    const map = new Map<string, StudyPlanItemPublic[]>();
    for (const item of plan.items) {
      const day = planItemDate(item);
      if (!day) continue;
      map.set(day, [...(map.get(day) ?? []), item]);
    }
    return map;
  }, [plan.items]);

  // Lưới trải từ tháng của ngày sớm nhất có việc (kể cả tick hôm qua) tới
  // tháng của ngày thi / buổi hẹn cuối. Chuỗi `yyyy-MM-dd` so sánh được đúng
  // theo thứ tự thời gian — không cần Date cho việc đó.
  const days = plan.items
    .map(planItemDate)
    .filter((d): d is string => Boolean(d))
    .sort();
  const minDay = [plan.today, ...days].reduce((a, b) => (a <= b ? a : b));
  const maxDay = [plan.today, plan.exam_date ?? "", ...days].reduce((a, b) => (a >= b ? a : b));
  const firstCursor = new Date(Number(minDay.slice(0, 4)), Number(minDay.slice(5, 7)) - 1, 1);
  const lastCursor = new Date(Number(maxDay.slice(0, 4)), Number(maxDay.slice(5, 7)) - 1, 1);

  const [cursor, setCursor] = useState(firstCursor);
  const [openDay, setOpenDay] = useState<string | null>(null);

  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const canPrev = cursor > firstCursor;
  const canNext = cursor < lastCursor;

  const cells: Array<string | null> = [];
  for (let i = 0; i < (new Date(year, month, 1).getDay() + 6) % 7; i += 1) cells.push(null);
  for (let d = 1; d <= new Date(year, month + 1, 0).getDate(); d += 1)
    cells.push(iso(year, month, d));

  // Danh sách tháng cho dropdown: mọi tháng từ tháng đầu tới tháng cuối của
  // kế hoạch (kèm cap phòng khi ngày thi bị đặt cả thế kỷ sau).
  const monthList: Date[] = [];
  for (let m = firstCursor; m <= lastCursor && monthList.length < 120; m = shiftMonth(m, 1))
    monthList.push(m);

  // Toolbar kiểu lịch: tiêu đề "Tháng 9 2026" LÀ control — một `<select>`
  // native phủ trong suốt lên đúng chữ đó. Chọn native vì nó miễn bàn phím,
  // screen reader và dropdown của hệ điều hành; phần nhìn là chữ đậm + mũi
  // tên nhỏ, không ô viền — hai cái select có viền kiểu form trước đây làm
  // thanh điều hướng trông như biểu mẫu, không như lịch.
  return (
    <div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Tháng trước"
          disabled={!canPrev}
          onClick={() => setCursor(shiftMonth(cursor, -1))}
          className="rounded p-1 text-ink-muted hover:bg-recess hover:text-ink disabled:opacity-40"
        >
          <ChevronLeft size={18} aria-hidden />
        </button>
        <span className="relative inline-flex items-center">
          <span className="pointer-events-none block px-7 py-1 font-semibold text-ink">
            Tháng {month + 1} {year}
          </span>
          <ChevronDown
            size={13}
            aria-hidden
            className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-ink-faint"
          />
          <select
            aria-label="Chọn tháng"
            value={`${year}-${month}`}
            onChange={(e) => {
              const [y, m] = e.target.value.split("-").map(Number);
              setCursor(new Date(y, m, 1));
            }}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          >
            {monthList.map((m) => (
              <option
                key={iso(m.getFullYear(), m.getMonth(), 1)}
                value={`${m.getFullYear()}-${m.getMonth()}`}
              >
                Tháng {m.getMonth() + 1} {m.getFullYear()}
              </option>
            ))}
          </select>
        </span>
        <button
          type="button"
          aria-label="Tháng sau"
          disabled={!canNext}
          onClick={() => setCursor(shiftMonth(cursor, 1))}
          className="rounded p-1 text-ink-muted hover:bg-recess hover:text-ink disabled:opacity-40"
        >
          <ChevronRight size={18} aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => {
            setCursor(
              new Date(Number(plan.today.slice(0, 4)), Number(plan.today.slice(5, 7)) - 1, 1),
            );
            setOpenDay(plan.today);
          }}
          className="ml-1 text-small font-semibold text-ink-muted underline-offset-2 hover:text-ink hover:underline"
        >
          Về hôm nay
        </button>
      </div>

      <div role="grid" aria-label={`Lịch tháng ${month + 1} ${year}`} className="mt-2">
        <div className="grid grid-cols-7 gap-0.5 text-center text-label font-semibold text-ink-faint sm:gap-1">
          {WEEKDAYS.map((w) => (
            <span key={w}>{w}</span>
          ))}
        </div>
        <div className="mt-1 grid auto-rows-fr grid-cols-7 gap-0.5 sm:gap-1">
          {cells.map((day, index) =>
            day === null ? (
              <span key={`blank-${index}`} aria-hidden />
            ) : (
              <DayCell
                key={day}
                day={day}
                items={byDay.get(day) ?? []}
                isToday={day === plan.today}
                isExam={day === plan.exam_date}
                isRest={isRestDay(day, plan.today, plan.study_days_per_week)}
                open={day === openDay}
                onOpen={() => setOpenDay(day === openDay ? null : day)}
              />
            ),
          )}
        </div>
      </div>

      {openDay && (
        <DayDetail
          day={openDay}
          items={byDay.get(openDay) ?? []}
          isExam={openDay === plan.exam_date}
          onTick={onTick}
          onPickMock={onPickMock}
          placementGate={placementGate}
          mockOptions={plan.mock_options}
        />
      )}
    </div>
  );
}

/** Ngày thứ `k` của tuần học, đếm offset từ hôm nay — cùng công thức với
 * `_study_date` của packer bên API. Lịch KHÔNG tô ngày nghỉ dựa trên `day % 7`
 * cố định vì ngày học được neo vào hôm nay của người học, không vào thứ mấy
 * trong tuần. Ô có mục (kể cả đã xong) không bao giờ coi là nghỉ. */
export function isRestDay(day: string, today: string, daysPerWeek: number): boolean {
  if (daysPerWeek >= 7) return false;
  const off =
    Math.round(
      (new Date(`${day}T12:00:00Z`).getTime() - new Date(`${today}T12:00:00Z`).getTime()) /
        86_400_000,
    ) % 7;
  return off >= daysPerWeek;
}

function DayCell({
  day,
  items,
  isToday,
  isExam,
  isRest,
  open,
  onOpen,
}: {
  day: string;
  items: StudyPlanItemPublic[];
  isToday: boolean;
  isExam: boolean;
  isRest: boolean;
  open: boolean;
  onOpen: () => void;
}) {
  const doneCount = items.filter((i) => i.done).length;
  const allDone = items.length > 0 && doneCount === items.length;
  const hasTest = items.some(isPlanTestItem);
  const shown = items.slice(0, CHIPS_PER_CELL);
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={
        items.length
          ? `${Number(day.slice(8, 10))} — ${items.map((i) => i.label).join(", ")}`
          : String(Number(day.slice(8, 10)))
      }
      className={cx(
        "flex flex-col rounded border border-rule p-1 text-left",
        "min-h-12 align-top transition-none hover:bg-recess",
        "sm:min-h-24 sm:p-1.5",
        // Ưu tiên nền một mạch if/else — hai class `bg-*` cùng đánh thì thứ tự
        // trong CSS mới thắng, còn ở đây thứ tự NGỮ NGHĨA phải cố định:
        // Thi > đã xong hết > ngày đo > nghỉ > panel. Ngày nghỉ không mục nào
        // mới là recess: ô trống kiểu panel đọc là "quên chưa xếp".
        isExam
          ? "border-rule-strong bg-action-tint"
          : allDone
            ? "border-ok/40 bg-ok-tint"
            : hasTest
              ? "bg-warn-tint"
              : items.length === 0 && isRest
                ? "bg-recess"
                : "bg-panel",
        isToday && "border-warn",
        open && "border-rule-strong bg-recess",
      )}
    >
      <span className="flex items-baseline justify-between gap-1">
        <span
          className={cx(
            "font-data text-label tabular-nums",
            isToday ? "font-semibold text-warn" : "text-ink-faint",
          )}
        >
          {Number(day.slice(8, 10))}
        </span>
        {isExam ? (
          <span className="inline-flex items-center gap-0.5 text-label font-semibold text-action-ink">
            <Flag size={10} aria-hidden />
            Thi
          </span>
        ) : allDone ? (
          <span className={cx("text-label font-semibold text-ok", hasTest && "mr-0.5")} aria-hidden>
            ✓
          </span>
        ) : (
          hasTest && <ClipboardCheck size={12} className="text-warn" aria-hidden />
        )}
      </span>
      {/*
        Hai hình thái theo bề rộng. Ở màn điện thoại một ô lịch chỉ rộng cỡ
        40px — nhét chữ vào là hoặc vỡ cột, hoặc thành một đống không đọc được.
        Nên dưới `sm` mỗi mục chỉ là MỘT chấm màu (đủ để thấy hôm nào có việc,
        hôm nào trống, hôm nào xong hết — màu đã mang cả ba thông tin đó), bản
        đầy đủ chữ nằm ở panel chi tiết khi chạm vào. Từ `sm` trở lên ô đủ rộng
        thì hiện chip chữ như thiết kế trên desktop. `aria-label` của nút đã liệt
        kê toàn bộ nhãn nên người đọc màn hình không phụ thuộc phần chữ này.
      */}
      <span className="mt-auto flex flex-wrap gap-1 pt-1 sm:hidden">
        {items.map((item) => (
          <span
            key={item.position}
            aria-hidden
            className={cx("h-1.5 w-1.5 rounded-full", dotClass(item))}
          />
        ))}
      </span>
      <span className="mt-1 hidden space-y-1 sm:block">
        {shown.map((item) => (
          <span key={item.position} className="flex items-start gap-1">
            <span
              aria-hidden
              className={cx("mt-1 h-1.5 w-1.5 shrink-0 rounded-full", dotClass(item))}
            />
            <span
              className={cx(
                "min-w-0 break-words text-label leading-tight",
                item.done ? "text-ink-faint line-through" : "text-ink",
              )}
            >
              {item.label}
            </span>
          </span>
        ))}
        {items.length > shown.length && (
          <span className="block text-label text-ink-faint">
            +{items.length - shown.length} nữa
          </span>
        )}
      </span>
    </button>
  );
}

function DayDetail({
  day,
  items,
  isExam,
  onTick,
  onPickMock,
  placementGate,
  mockOptions,
}: {
  day: string;
  items: StudyPlanItemPublic[];
  isExam: boolean;
  onTick: (item: StudyPlanItemPublic, done: boolean) => void;
  onPickMock: (item: StudyPlanItemPublic, testId: string) => void;
  placementGate?: PlacementGate | null;
  mockOptions: StudyPlanPublic["mock_options"];
}) {
  if (isExam) {
    return (
      <div className="mt-3 rounded border border-rule-strong bg-action-tint p-4">
        <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-action-ink">
          <Flag size={12} aria-hidden />
          Ngày thi
        </p>
        <p className="mt-1.5 text-small text-ink-muted">
          {new Date(`${day}T12:00:00`).toLocaleDateString("vi-VN", {
            weekday: "long",
            day: "numeric",
            month: "long",
          })}{" "}
          — ngày đích của lộ trình. Không còn việc nào để tick hôm nay. Những gì cần luyện đã ở
          phía sau; giờ là lúc bước vào phòng thi, giữ bình tĩnh, đọc kỹ từng câu và hoàn thành đến
          câu cuối.
        </p>
      </div>
    );
  }
  return (
    <div className="mt-3 rounded border border-rule bg-recess p-3">
      <p className="text-label font-semibold uppercase text-ink-faint">
        {new Date(`${day}T12:00:00`).toLocaleDateString("vi-VN", {
          day: "numeric",
          month: "long",
          year: "numeric",
        })}
      </p>
      {items.length === 0 ? (
        <p className="mt-1 text-small text-ink-muted">Ngày này không có mục nào.</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {items.map((item) => (
            <li key={item.position} className="flex items-start gap-2.5 text-small">
              {/* Checkbox native: ô tick tay của người học. Mục đã xong vì học
                  THẬT thì khoá lại — "bỏ xong" một việc đã xảy ra là nói dối.
                  Mục KIỂM TRA khoá từ đầu ở mọi trạng thái: nó khép bằng bài
                  nộp (API từ chối tick với 409), tick ở đây là được phép xưng
                  "đã đo" mà chưa đo. `readOnly`+con trỏ vì lib không có kiểu
                  "disabled nhưng vẫn hiện bật". */}
              <input
                type="checkbox"
                checked={item.done}
                disabled={isPlanTestItem(item) || (item.done && !item.manual_done)}
                onChange={(event) => onTick(item, event.target.checked)}
                title={
                  isPlanTestItem(item)
                    ? item.done
                      ? "Đã ghi nhận bằng bài nộp"
                      : "Tự ghi nhận khi bạn nộp bài — không tick tay được"
                    : item.done && !item.manual_done
                      ? "Đã xong vì học thật — không bỏ tick được ở đây"
                      : "Đánh dấu đã xong"
                }
                className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-[var(--action)] disabled:cursor-not-allowed"
                aria-label={`Hoàn thành: ${item.label}`}
              />
              <span className="min-w-0 flex-1">
                <span className={cx("font-semibold", item.done && "text-ink-muted line-through")}>
                  {item.label}
                </span>
                {item.reason && <span className="block text-ink-muted">{item.reason}</span>}
                {/* Đề thi thử là LỰA CHỌN, không phải lời hứa ghim: rút ngẫu
                    nhiên lúc sinh (đổi cùng kho đề với "Sinh lại") và chọn
                    tay được tới lúc nộp. Đã nộp rồi thì select biến mất —
                    lịch sử của bài đã làm không phải con trỏ UI. */}
                {item.kind === "mock_test" && !item.done && mockOptions.length > 0 && (
                  <select
                    aria-label="Chọn đề thi thử"
                    value={item.ref_id ?? ""}
                    onChange={(event) => onPickMock(item, event.target.value)}
                    className="mt-1 block w-full rounded border border-rule bg-panel px-2 py-1 text-small text-ink"
                  >
                    {mockOptions.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.title}
                      </option>
                    ))}
                  </select>
                )}
                {/* Cooldown chỉ ĐÁNG NÓI khi nó mở muộn hơn ô hẹn — ghi "đo lại
                    được từ 14/9" dưới một mục hẹn 19/9 là lời thừa gây confuse
                    (cửa mở trước, đến hẹn tự nhiên bấm được). Muộn hơn hẹn thì
                    phải nói, vì ô hẹn sẽ trễ. `sv-SE` trả đúng định dạng ISO để
                    so chuỗi với `item.day`. */}
                {item.kind === "mini_test" &&
                  !item.done &&
                  item.day &&
                  cooldownOpensAfter(item, placementGate) && (
                    <span className="block text-label text-warn">
                      Được đo lại từ{" "}
                      {new Date(placementGate?.next_available_at ?? 0).toLocaleDateString("vi-VN", {
                        day: "numeric",
                        month: "short",
                      })}{" "}
                      {new Date(placementGate?.next_available_at ?? 0).toLocaleTimeString("vi-VN", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  )}
              </span>
              <span className="shrink-0 font-data text-label tabular-nums text-ink-faint">
                {item.est_minutes}′
              </span>
              <ButtonLink href={planItemHref(item)} size="sm" variant="secondary">
                {planItemCta(item)}
              </ButtonLink>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
