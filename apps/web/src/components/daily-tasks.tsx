"use client";

import {
  API_ROUTES,
  type DailyTaskPublic,
  type DailyTasksPublic,
  type ProgressionPublic,
} from "@toeic-pilot/shared";
import { Check, FileText, Headphones, RotateCcw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Panel, Skeleton, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useToast } from "@/lib/toast";

/**
 * Ba việc hôm nay — khối đầu tiên của `/dashboard`.
 *
 * Mục tiêu của tính năng này (USER-ROAD §6) là *mở lên là biết làm gì*, nên nó
 * luôn đúng ba dòng, luôn cùng thứ tự, và không có menu để chọn. Trạng thái ba
 * việc suy ra từ hoạt động trong ngày ở máy chủ; ở đây không tính gì cả.
 *
 * Ba chi tiết dễ làm hỏng khi sửa:
 *
 *   · **`target` đến từ máy chủ, không tính lại ở client.** Nó là một số CỐ
 *     ĐỊNH đã kẹp theo số từ thật sự có, không phải chính tình trạng — mục tiêu
 *     "ôn hết số từ đến hạn" chạy tới rồi lùi khi bạn ôn (§6.2).
 *   · **Xong cả ba thì khối THU LẠI một dòng, không biến mất.** Một khối biến
 *     mất đọc như hỏng, và người học mất luôn phần thưởng của việc đã làm xong.
 *   · **Chạm trần XP phải nói ra** (§2.4). Không nói thì người ta học tiếp và
 *     tưởng hệ thống hỏng khi thanh XP đứng yên.
 */

type TaskKind = DailyTaskPublic["kind"];

/**
 * Biểu tượng và lối đi của mỗi LOẠI việc.
 *
 * `Record<TaskKind, …>` chứ không phải bảng tra theo khe: khe là dữ liệu — admin
 * thêm, đổi tên, đổi mục tiêu, tắt — nên frontend không thể có một hàng cho từng
 * khe. Cái nó biết là loại việc, và đó là union đến từ OpenAPI: thêm một loại ở
 * backend mà quên khai ở đây là lỗi `tsc`, không phải một dòng không bấm được.
 *
 * NHÃN thì không nằm ở đây. Nhãn do admin đặt và đi kèm dữ liệu; viết lại nó
 * trong frontend là làm cho ô nhập trong màn quản trị không có tác dụng gì.
 */
const KINDS: Record<TaskKind, { hint: string; href: string; Icon: LucideIcon }> = {
  vocabulary_review: { hint: "lượt ôn", href: "/learn/review", Icon: RotateCcw },
  dictation_complete: { hint: "câu đúng trọn", href: "/learn/dictation", Icon: Headphones },
  attempt_answer: { hint: "câu đã trả lời", href: "/learn/tests", Icon: FileText },
};

function TaskRow({ task }: { task: DailyTaskPublic }) {
  const meta = KINDS[task.kind];
  const shown = Math.min(task.progress, task.target);
  const pct = task.target > 0 ? (shown / task.target) * 100 : 0;

  return (
    <li>
      <Link
        href={meta.href}
        className="flex items-center gap-3 rounded border border-rule-strong p-3 transition-colors hover:bg-recess"
      >
        <span
          aria-hidden
          className={cx(
            "grid h-8 w-8 shrink-0 place-items-center rounded",
            task.done ? "bg-ok-tint text-ok" : "bg-recess text-ink-muted",
          )}
        >
          {task.done ? (
            <Check size={16} strokeWidth={2.25} />
          ) : (
            <meta.Icon size={16} strokeWidth={1.75} />
          )}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className={cx("font-semibold", task.done && "text-ink-muted")}>{task.label}</span>
            <span className="font-data text-small tabular-nums text-ink-muted">
              {shown}/{task.target}
              <span className="ml-1 text-ink-faint">{meta.hint}</span>
            </span>
          </span>
          {/* Thanh tiến độ chỉ tăng: nó đếm hoạt động TRONG NGÀY, không đếm số
              việc còn lại. `shown` kẹp lại để làm 12/10 không tràn khỏi khung. */}
          <span
            role="progressbar"
            aria-valuenow={shown}
            aria-valuemin={0}
            aria-valuemax={task.target}
            aria-label={task.label}
            className="mt-2 block h-1.5 w-full overflow-hidden rounded bg-recess"
          >
            <span
              className={cx("block h-full transition-all", task.done ? "bg-ok" : "bg-action")}
              style={{ width: `${pct}%`, minWidth: shown > 0 ? "3px" : undefined }}
            />
          </span>
        </span>

        <span
          className={cx(
            "shrink-0 font-data text-small font-semibold tabular-nums",
            task.done ? "text-ok" : "text-ink-faint",
          )}
        >
          +{task.xp}
        </span>
      </Link>
    </li>
  );
}

/**
 * Báo cho người học biết họ vừa đóng được một việc, và `xp_awarded` là thứ nói
 * điều đó — không phải `done`.
 *
 * `done` là *trạng thái*: nó vẫn đúng suốt phần còn lại của ngày, nên báo theo
 * nó sẽ chúc mừng lại mỗi lần mở trang chủ. `xp_awarded` là *sự kiện*: nó đếm
 * XP vừa trao TRONG CHÍNH LẦN ĐỌC NÀY, và vì `source_id` sinh tất định từ
 * (người, ngày, khe) nên lần đọc thứ hai luôn trả 0. Máy chủ đã có sẵn câu trả
 * lời "vừa mới xong"; phía trình duyệt không cần tự nhớ gì cả.
 *
 * Không nói "vừa xong MỘT việc": hai khe có thể đóng cùng lúc giữa hai lần đọc,
 * và `xp_awarded` là tổng, không tách ra được. Câu chữ ở đây đúng cho cả hai
 * trường hợp thay vì đúng cho trường hợp hay gặp.
 */
function announceAward(data: DailyTasksPublic, show: ReturnType<typeof useToast>["show"]) {
  if (data.xp_awarded <= 0) return;
  const left = data.tasks.filter((task) => !task.done).length;
  show({
    tone: "ok",
    title: "Đã xong việc hôm nay",
    description:
      left === 0
        ? `+${data.xp_awarded} XP. Học thêm vẫn tính vào XP và chuỗi ngày.`
        : `+${data.xp_awarded} XP. Còn ${left} việc nữa.`,
    // Ngày nằm trong khoá: qua nửa đêm là một ngày khác, và tin của hôm nay
    // không được thay chỗ tin của hôm qua đang còn trên màn hình.
    dedupeKey: `daily-${data.date}`,
  });
}

export function DailyTasksPanel({ token }: { token: string | null }) {
  const [daily, setDaily] = useState<DailyTasksPublic | null>(null);
  const [progression, setProgression] = useState<ProgressionPublic | null>(null);
  const { show } = useToast();

  useEffect(() => {
    if (!token) return;
    let alive = true;
    // Đọc daily task TRƯỚC rồi mới đọc level, và thứ tự đó là bắt buộc:
    // `GET /daily-tasks` là lần đọc có ghi — nó trao XP cho việc vừa xong — nên
    // gọi song song sẽ hay đọc được số XP của trước khi trao, và người học thấy
    // việc đóng lại mà điểm không nhích. Nạp lại trang thì nó đúng, đó chính là
    // kiểu lỗi không ai báo.
    apiFetch<DailyTasksPublic>(API_ROUTES.dailyTasks, { token })
      .then((data) => {
        if (alive) setDaily(data);
        /*
         * NGOÀI cờ `alive`, và đây là chỗ đã sai một lần.
         *
         * StrictMode ở bản dev chạy effect, dọn dẹp, rồi chạy lại — nên cờ
         * `alive` của lần chạy ĐẦU đã tắt trước khi phản hồi của chính nó về.
         * Mà lần đọc đầu mới là lần TRAO thưởng: lần thứ hai máy chủ trả
         * `xp_awarded = 0` vì `source_id` tất định. Đặt lời chúc mừng sau `if
         * (alive)` nghĩa là nó rơi vào đúng cái phản hồi bị bỏ đi, và không bao
         * giờ hiện ra.
         *
         * Cờ `alive` bảo vệ state CỦA COMPONENT NÀY, và nó đúng cho `setDaily`.
         * Toast thì thuộc về một provider sống lâu hơn component; chuyện được
         * báo cũng đã xảy ra rồi ở máy chủ, nên hàng thông báo vẫn phải nghe
         * thấy dù cái khối gọi nó đã bị tháo.
         */
        announceAward(data, show);
        return apiFetch<ProgressionPublic>(API_ROUTES.progression, { token });
      })
      .then((data) => {
        if (alive && data) setProgression(data);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token, show]);

  if (!daily) {
    return (
      <Panel className="mb-4 p-5" aria-busy>
        <Skeleton className="h-5 w-40" />
        <Skeleton className="mt-4 h-40" />
      </Panel>
    );
  }

  // Admin tắt hết mọi khe là một cấu hình hợp lệ, và khi đó khối này không có gì
  // để nói — ẩn hẳn, chứ không dựng một cái vỏ rỗng trên đầu trang chủ.
  if (daily.tasks.length === 0) return null;

  const done = daily.tasks.filter((task) => task.done).length;
  const allDone = done === daily.tasks.length;
  const capped = progression !== null && progression.xp_today >= progression.daily_cap;
  const sameXp =
    daily.tasks.length > 0 && daily.tasks.every((task) => task.xp === daily.tasks[0].xp)
      ? daily.tasks[0].xp
      : null;

  return (
    /* `role="region"` + tên: khối này là mốc điều hướng đầu trang chứ không
       phải một hộp trang trí, nên người dùng bàn phím và trình đọc màn hình phải
       nhảy thẳng vào được. Nó cũng là thứ cho e2e một chỗ bám ổn định. */
    <Panel className="mb-4 p-5" role="region" aria-labelledby="daily-tasks-title">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 id="daily-tasks-title" className="text-subtitle">
          Việc hôm nay
        </h2>
        {progression && (
          <p className="font-data text-small tabular-nums text-ink-muted">
            Level {progression.level}
            <span className="mx-1.5 text-ink-faint">·</span>
            {progression.xp_today}/{progression.daily_cap} XP hôm nay
          </p>
        )}
      </div>

      {allDone ? (
        /* Xong cả ba thì thu lại một dòng chứ KHÔNG biến mất (§6.4): một khối
           biến mất đọc như hỏng, và nó lấy mất phần thưởng của việc đã làm. */
        <p className="mt-3 flex items-center gap-2 text-ok">
          <Check size={16} strokeWidth={2.25} aria-hidden />
          <span className="text-ink">
            Xong cả ba việc hôm nay. Học thêm vẫn tính vào XP và chuỗi ngày.
          </span>
        </p>
      ) : (
        <>
          {/* Chỉ nói "mỗi việc cộng N XP" khi mọi khe THẬT SỰ cùng mức — mức
              thưởng nằm trên từng khe và admin đặt khác nhau được, nên câu đó sẽ
              sai ngay lần đầu ai đó dùng tới khả năng ấy. Số điểm của từng việc
              vẫn in ở cuối mỗi dòng. */}
          <p className="mt-1 text-small text-ink-muted">
            Xong {done}/{daily.tasks.length} việc
            {sameXp !== null && ` · mỗi việc cộng ${sameXp} XP`}.
          </p>
          <ul className="mt-4 space-y-2">
            {daily.tasks.map((task) => (
              <TaskRow key={task.slot_id} task={task} />
            ))}
          </ul>
        </>
      )}

      {/* Chạm trần thì phải nói (§2.4). Hoạt động vẫn ghi bình thường — SM-2,
          tiến độ dictation, lượt làm đề không bao giờ bị luật XP đụng vào — nên
          câu này nói đúng chuyện gì dừng và chuyện gì không. */}
      {capped && (
        <p className="mt-4 border-t border-rule pt-3 text-small text-ink-muted">
          Hôm nay đã đạt tối đa {progression?.daily_cap} XP. Tiến độ học vẫn được ghi bình thường,
          chỉ có điểm là dừng tới ngày mai.
        </p>
      )}
    </Panel>
  );
}
