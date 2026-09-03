"use client";

import { useEffect, useState } from "react";

import { cx } from "@/components/ui";
import { playSound } from "@/lib/sound";
import { subscribeToPetNotices, type PetNotice } from "@/lib/pet-notice";

/**
 * Thông báo của góc thú cưng, xếp ở góc DƯỚI PHẢI của chính bảng.
 *
 * Dưới phải chứ không trên phải: bảng chỉ số và mấy cái nút hành động nằm ở đáy,
 * nên một thẻ nổi lên từ đó đọc ra là "vừa có chuyện xảy ra với con thú" — cùng
 * chỗ mắt đang nhìn. Trên phải là nơi toast toàn trang sống, và hai lớp thông
 * báo chồng lên nhau ở một góc là hai lớp che nhau.
 *
 * `absolute` chứ không `fixed`: nó thuộc về bảng, nên nó phải đi theo bảng khi
 * người dùng kéo bảng sang chỗ khác. `fixed` sẽ khiến thẻ đứng lại một góc màn
 * hình trong khi con thú đã ở góc kia.
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

/** "+0.04" thành "+4%" — phần trăm đọc được, số thập phân ba chữ thì không. */
function moodLabel(mood: number): string {
  return `+${Math.max(1, Math.round(mood * 100))}% vui`;
}

export function PetlandToast() {
  const [shown, setShown] = useState<Shown[]>([]);

  useEffect(
    () =>
      subscribeToPetNotices((notice) => {
        // Phát trước khi dựng: tiếng và hình phải đến cùng lúc, và `playSound`
        // tự im khi người dùng đã tắt hoặc khi trình duyệt chặn.
        if (notice.sound) playSound(notice.sound);
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

  if (shown.length === 0) return null;

  return (
    /* `aria-live="polite"`: những thẻ này chỉ báo tin vui, không có gì cần cắt
       ngang thứ người đọc màn hình đang đọc. */
    <div
      className="pointer-events-none absolute bottom-2 right-2 z-20 flex flex-col items-end gap-1.5"
      aria-live="polite"
    >
      {shown.map((notice) => (
        <div
          key={notice.id}
          className={cx(
            "animate-settle rounded border bg-panel px-2.5 py-1.5",
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
    </div>
  );
}
