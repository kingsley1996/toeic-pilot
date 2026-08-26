"use client";

import { Volume2, VolumeX } from "lucide-react";
import { useSyncExternalStore } from "react";

import { cx } from "@/components/ui";
import { isSoundOn, serverSoundPref, setSoundOn, subscribeToSound } from "@/lib/sound";

/**
 * Bật/tắt tiếng báo. Hai trạng thái, cùng hình dạng với `ThemeToggle` bên cạnh.
 *
 * `undefined` ở lần dựng đầu là trạng thái thứ ba — "chưa đọc được
 * localStorage" — và nó được giữ nguyên chứ không đoán bừa, y như bộ chọn theme:
 * đoán rồi sửa lại sau khi hydrate là cái nút tự đổi hình ngay trước mắt người
 * dùng.
 *
 * `aria-pressed` nói trạng thái, `aria-label` nói VIỆC nút sẽ làm. Một nút loa
 * không có nhãn thì trình đọc màn hình chỉ đọc được "button", và người dùng
 * không biết bấm vào là bật hay tắt.
 */
export function SoundToggle() {
  const on = useSyncExternalStore(subscribeToSound, isSoundOn, serverSoundPref);
  const label = on === false ? "Bật tiếng báo" : "Tắt tiếng báo";

  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={on === undefined ? undefined : on}
      title={label}
      onClick={() => setSoundOn(on === false)}
      className={cx(
        "grid h-8 w-8 place-items-center rounded border border-rule transition-colors",
        on === false
          ? "text-ink-faint hover:bg-recess/60 hover:text-ink-muted"
          : "text-ink-muted hover:bg-recess hover:text-ink",
      )}
    >
      {on === false ? (
        <VolumeX size={14} strokeWidth={2} aria-hidden />
      ) : (
        <Volume2 size={14} strokeWidth={2} aria-hidden />
      )}
    </button>
  );
}
