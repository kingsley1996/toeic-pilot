"use client";

import { Music, Music2 } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

import { cx } from "@/components/ui";
import {
  isMusicOn,
  serverMusicPref,
  setMusicOn,
  startMusic,
  stopMusic,
  subscribeToMusic,
} from "@/lib/petland-music";

/**
 * Bật/tắt nhạc nền, và cũng là thứ điều khiển việc phát.
 *
 * Gộp nút với việc phát để bảng thú cưng chỉ cần đặt nút này vào là xong —
 * không có effect nào nằm rải ở chỗ khác phải nhớ dọn. Rời bảng là dừng nhạc,
 * vì nhạc thuộc về cái góc ấy chứ không thuộc cả ứng dụng.
 *
 * `undefined` ở lần dựng đầu là "chưa đọc được localStorage", giữ nguyên chứ
 * không đoán — cùng luật với `SoundToggle` và bộ chọn theme.
 */
export function PetlandMusicToggle() {
  const on = useSyncExternalStore(subscribeToMusic, isMusicOn, serverMusicPref);

  useEffect(() => {
    if (on === true) startMusic();
    return stopMusic;
  }, [on]);

  const label = on === true ? "Tắt nhạc nền" : "Bật nhạc nền";
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={on === undefined ? undefined : on}
      title={label}
      // Đặt tuỳ chọn TRƯỚC rồi mới phát: `startMusic` tự đọc lại tuỳ chọn, nên
      // gọi ngược thứ tự thì lần bấm đầu không kêu.
      onClick={() => setMusicOn(on !== true)}
      className={cx(
        "grid h-8 w-8 place-items-center rounded border border-rule transition-colors",
        on === true
          ? "border-action text-action-ink"
          : "text-ink-faint hover:bg-recess/60 hover:text-ink-muted",
      )}
    >
      {on === true ? (
        <Music size={14} strokeWidth={2} aria-hidden />
      ) : (
        <Music2 size={14} strokeWidth={2} aria-hidden />
      )}
    </button>
  );
}
