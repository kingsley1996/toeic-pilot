"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { petLine } from "@/components/petland-lines";
import { type PetCondition } from "@/components/petland-pet";
import { cx } from "@/components/ui";
import { subscribeToPetNotices, type PetNotice } from "@/lib/pet-notice";
import { getSidebarState, serverSidebarState, subscribeToSidebar } from "@/lib/sidebar";
import { playSound } from "@/lib/sound";

/**
 * Thông báo của góc thú cưng, xếp NGAY TRÊN thẻ thú cưng ở sidebar.
 *
 * Chỗ đứng của nó theo con thú, không theo màn hình: thẻ ở sidebar là nhà cố
 * định của con thú, nên "+8 XP" nổi lên từ đúng chỗ ấy đọc ra là chuyện của nó,
 * không cần ai nối hai thứ lại. Trước đây toast bám vào bảng nổi, và bảng thì
 * mặc định đóng — nên phần lớn thời gian không có gì để bám vào.
 *
 * Rộng bằng đúng thẻ: nó dựng bên trong cùng một khung `relative` có cùng lề, và
 * mỗi thẻ báo là `w-full`. Một cái toast hẹp hơn hay rộng hơn thẻ ngay dưới nó
 * đọc ra là hai thành phần rời nhau chứ không phải một cái phát ra từ cái kia.
 *
 * **Sidebar thu gọn thì nó dời sang bên phải con thú.** Ở dải 64px không còn bề
 * ngang nào để đặt một dòng chữ, và xếp lên trên thì thẻ báo rộng gấp ba cái cột
 * nó mọc ra — đọc ra là một mảng trôi nổi chứ không phải lời của con thú. Bề
 * rộng giữ nguyên như lúc mở, nên thẻ báo không đổi hình khi người dùng thu
 * sidebar lại.
 *
 * **Dựng HAI lần, và chỉ một bản nhìn thấy được.** `SidebarContent` dựng cả ở
 * cột trái lẫn ngăn kéo mobile; cột trái là `hidden` dưới `lg` còn ngăn kéo chỉ
 * tồn tại dưới `lg`, nên đúng một bản hiện ra. Thứ KHÔNG tự tách ra là tiếng báo
 * — xem `sounded` bên dưới.
 *
 * Tự giữ hàng đợi riêng, không dùng `lib/toast.tsx`: cái kia là một provider
 * duy nhất ở gốc ứng dụng với khung nhìn `fixed` của nó, và nhét thẻ của góc thú
 * cưng vào đó là đúng thứ đang muốn tránh.
 */

/** Bao lâu thì một thẻ tự đi. Đủ đọc một dòng, không đủ để chắn đường. */
const LIFE_MS = 2600;
const MAX_VISIBLE = 3;

type Shown = PetNotice & { id: number };

let counter = 0;

/*
 * Đã kêu cho thẻ báo này chưa.
 *
 * Hai bản `PetlandToast` cùng nghe một kênh, và bản không nhìn thấy được vẫn
 * chạy `playSound` — hai tiếng lệch nhau vài mili giây nghe ra là một tiếng vỡ.
 * Dedupe được vì `notifyPet` phát đúng MỘT đối tượng cho mọi bên nghe, nên danh
 * tính đối tượng là khoá sẵn có; `WeakSet` để thẻ báo đi rồi thì khoá đi theo.
 */
const sounded = new WeakSet<PetNotice>();

/** "+0.04" thành "+4%" — phần trăm đọc được, số thập phân ba chữ thì không. */
function moodLabel(mood: number): string {
  return `+${Math.max(1, Math.round(mood * 100))}% vui`;
}

export function PetlandToast({ condition }: { condition?: PetCondition }) {
  const [shown, setShown] = useState<Shown[]>([]);
  const line = useIdleLine(condition);

  /* `serverSidebarState` báo "chưa biết" lúc dựng ở máy chủ — cùng ba trạng thái
     mà `session` có, và ở đây "chưa biết" xử như mở rộng, đúng bề rộng mà HTML
     máy chủ trả về. */
  const collapsed =
    useSyncExternalStore(subscribeToSidebar, getSidebarState, serverSidebarState) === "collapsed";

  useEffect(
    () =>
      subscribeToPetNotices((notice) => {
        // Phát trước khi dựng: tiếng và hình phải đến cùng lúc, và `playSound`
        // tự im khi người dùng đã tắt hoặc khi trình duyệt chặn.
        if (notice.sound && !sounded.has(notice)) {
          sounded.add(notice);
          playSound(notice.sound);
        }
        counter += 1;
        const id = counter;
        setShown((prev) => {
          const at = notice.dedupeKey
            ? prev.findIndex((one) => one.dedupeKey === notice.dedupeKey)
            : -1;
          if (at >= 0) {
            const next = [...prev];
            next[at] = { ...notice, id };
            return next;
          }
          return [...prev, { ...notice, id }].slice(-MAX_VISIBLE);
        });
        window.setTimeout(() => {
          setShown((prev) => prev.filter((one) => one.id !== id));
        }, LIFE_MS);
      }),
    [],
  );

  if (shown.length === 0 && line === null) return null;

  return (
    /* `aria-live="polite"`: những thẻ này chỉ báo tin vui, không có gì cần cắt
       ngang thứ người đọc màn hình đang đọc. */
    <div
      className={cx(
        "pointer-events-none absolute z-20 flex flex-col gap-1.5",
        collapsed ? "bottom-1 left-full ml-1.5 w-52" : "inset-x-2 bottom-full mb-1.5",
      )}
      aria-live="polite"
    >
      {shown.map((notice) => (
        <div
          key={notice.id}
          className={cx(
            "animate-settle w-full rounded border bg-panel px-2 py-1.5",
            notice.tone === "alert"
              ? "border-alert"
              : notice.tone === "warn"
                ? "border-warn"
                : "border-ok",
          )}
        >
          <p className="text-small font-semibold text-ink">{notice.title}</p>
          {notice.detail && <p className="text-label text-ink-muted">{notice.detail}</p>}
          {notice.gains && (
            <p className="mt-0.5 flex items-center gap-2 font-data text-label tabular-nums">
              {notice.gains.xp !== undefined && (
                <span className="text-action-ink">+{notice.gains.xp} XP</span>
              )}
              {notice.gains.mood !== undefined && (
                <span className="text-ok">{moodLabel(notice.gains.mood)}</span>
              )}
              {notice.gains.ruby !== undefined && (
                <span className="flex items-center gap-1 text-warn">
                  {/* Viên ruby vẽ bằng CSS: `pixel-icon` không có mặt hàng nào
                      cho nó, và thêm một ô vào bộ biểu tượng chỉ vì một cái
                      toast là mở rộng bộ art cho một chỗ dùng. */}
                  <span aria-hidden className="h-2 w-2 rotate-45 rounded-[1px] bg-alert" />+
                  {notice.gains.ruby}
                </span>
              )}
            </p>
          )}
        </div>
      ))}

      {/* Lời của con thú xếp CUỐI, tức là gần nó nhất khi chồng mọc lên trên. */}
      {line !== null && <SpeechBubble line={line} pointsLeft={collapsed} />}
    </div>
  );
}

/**
 * Thỉnh thoảng cho con thú nói một câu.
 *
 * Hiện ngắn rồi im lâu: nó là thứ đứng cạnh chỗ người ta đang học, nên nhịp phải
 * là thỉnh thoảng liếc thấy chứ không phải một cái bảng chữ chạy. Khoảng im
 * **ngẫu nhiên** trong một quãng, vì một câu bật ra đúng mỗi 40 giây thì sau
 * hai lần người ta đọc ra cái đồng hồ chứ không đọc ra con thú.
 *
 * Im khi tab bị ẩn, và im luôn khi chưa biết tình trạng: một câu bốc theo tình
 * trạng mặc định trong lúc con thú thật đang kiệt sức là nói sai về nó.
 */
const SAY_MS = 5200;
const QUIET_MIN_MS = 24_000;
const QUIET_MAX_MS = 52_000;

function useIdleLine(condition: PetCondition | undefined): string | null {
  const [line, setLine] = useState<string | null>(null);

  useEffect(() => {
    if (condition === undefined) return;
    let timer = 0;
    let last: string | undefined;

    const wait = () => {
      timer = window.setTimeout(say, QUIET_MIN_MS + Math.random() * (QUIET_MAX_MS - QUIET_MIN_MS));
    };
    const hide = () => {
      setLine(null);
      wait();
    };
    const say = () => {
      if (document.hidden) {
        timer = window.setTimeout(say, QUIET_MIN_MS);
        return;
      }
      last = petLine(condition, last);
      setLine(last);
      timer = window.setTimeout(hide, SAY_MS);
    };

    // Bắt đầu bằng `wait`, không bằng `hide`: mỗi lần chuyển trang là một lần
    // dựng lại, nên nói ngay lúc dựng thì câu thoại đọc ra là một thông báo hệ
    // thống. Đây cũng là lý do vòng lặp không đặt state ngay trong thân effect —
    // `react-hooks/set-state-in-effect` chặn đúng lối viết ấy.
    wait();
    return () => {
      window.clearTimeout(timer);
      // Tình trạng đổi giữa lúc đang nói: hẹn giờ bị huỷ, nên không dọn ở đây
      // thì câu cũ đứng lại vĩnh viễn — và nó đang nói sai về con thú.
      setLine(null);
    };
  }, [condition]);

  return condition === undefined ? null : line;
}

/**
 * Bong bóng thoại: khung có đuôi chỉ về phía con thú, chữ chạy dần ra.
 *
 * Cái đuôi mới là thứ làm nó thành lời NÓI. Thiếu nó thì một khung chữ nổi cạnh
 * con thú đọc ra là thông báo của hệ thống, đúng thứ mà thẻ thưởng ngay trên nó
 * đang là — và khi hai thứ trông giống nhau thì con số thật bị pha loãng theo.
 * Đuôi là một ô vuông xoay 45°, chỉ tô hai cạnh viền: cách này giữ được cả nền
 * lẫn viền nối liền với thân bong bóng, và không cần bóng đổ (hệ thiết kế cấm).
 *
 * Chỉ hướng xuống hoặc sang trái, theo đúng chỗ bong bóng đang đứng so với con
 * thú: sidebar mở thì nó ở trên, thu gọn thì nó ở bên phải.
 */
function SpeechBubble({ line, pointsLeft }: { line: string; pointsLeft: boolean }) {
  const typed = useTyped(line);
  return (
    <div className="animate-settle relative w-full rounded border border-rule bg-panel px-2 py-1.5">
      {/*
       * Hai lớp chồng lên nhau trong MỘT ô lưới: bản vô hình giữ chỗ cho cả câu,
       * bản đang gõ nằm đè lên. Không có nó thì bong bóng cao thêm một dòng ngay
       * giữa lúc gõ, và cả chồng thẻ phía trên nhảy theo.
       */}
      <p aria-hidden className="grid text-small italic text-ink-muted">
        <span className="invisible [grid-area:1/1]">{line}</span>
        <span className="[grid-area:1/1]">
          {typed}
          {typed.length < line.length && <span className="animate-blink">|</span>}
        </span>
      </p>
      {/* Người đọc màn hình nhận cả câu một lần, không nhận từng ký tự. */}
      <p className="sr-only">{line}</p>
      <span
        aria-hidden
        className={cx(
          "absolute h-2 w-2 rotate-45 border-rule bg-panel",
          pointsLeft
            ? "-left-[5px] top-1/2 -mt-1 border-b border-l"
            : "-bottom-[5px] left-4 border-b border-r",
        )}
      />
    </div>
  );
}

/**
 * Chữ hiện dần từng ký tự.
 *
 * Không đặt state trong thân effect — `react-hooks/set-state-in-effect` chặn lối
 * viết đó — nên cả trường hợp "tắt hiệu ứng" cũng đi qua chính cái đồng hồ ấy,
 * chỉ khác bước nhảy: một nhịp là xong cả câu.
 */
const TYPE_MS = 26;

function useTyped(line: string): string {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    const step = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? line.length : 1;
    let at = 0;
    const id = window.setInterval(() => {
      at += step;
      setShown(at);
      if (at >= line.length) window.clearInterval(id);
    }, TYPE_MS);
    return () => window.clearInterval(id);
  }, [line]);

  return line.slice(0, shown);
}
