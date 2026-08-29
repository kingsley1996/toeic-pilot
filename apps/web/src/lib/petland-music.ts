/**
 * Nhạc nền cho góc thú cưng, và cái công tắc của riêng nó.
 *
 * **Công tắc RIÊNG, không dùng chung với `sound.ts`.** Tiếng báo là một tiếng
 * chuông nửa giây sau khi bấm; nhạc nền chạy suốt lúc người ta đang học. Gộp
 * một công tắc nghĩa là ai muốn tắt nhạc thì mất luôn phản hồi khi làm đúng —
 * hai thứ phiền theo hai mức khác hẳn nhau.
 *
 * **Mặc định TẮT**, ngược với `sound.ts`. Hai lý do, và lý do thứ hai mới là
 * lý do cứng: nhạc tự bật trong một ứng dụng học là xâm phạm, và trình duyệt
 * CHẶN tự phát khi chưa có tương tác — nên "mặc định bật" sẽ âm thầm không kêu
 * ở lần mở trang đầu và trông như hỏng. Ở đây chính cú bấm bật là tương tác
 * cho phép phát.
 *
 * Nhạc chỉ chạy khi bảng thú cưng đang mở; đóng bảng là dừng. Nó thuộc về cái
 * góc ấy, không thuộc về cả ứng dụng.
 */

const KEY = "petland-music";
const SRC = "/sounds/petland.mp3";

/** Nhỏ hơn tiếng báo: thứ chạy nền phải lùi lại sau tiếng của giao diện. */
const VOLUME = 0.28;
const FADE_MS = 700;

const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

export function subscribeToMusic(onChange: () => void): () => void {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function isMusicOn(): boolean {
  if (typeof window === "undefined") return false;
  try {
    // Chỉ chuỗi "on" mới bật — ngược chiều với `sound.ts`, vì mặc định ngược nhau.
    return localStorage.getItem(KEY) === "on";
  } catch {
    return false;
  }
}

/** Máy chủ không có localStorage, nên nó chỉ báo được "chưa biết". */
export function serverMusicPref(): undefined {
  return undefined;
}

export function setMusicOn(on: boolean): void {
  try {
    if (on) localStorage.setItem(KEY, "on");
    else localStorage.removeItem(KEY);
  } catch {
    /* không lưu được thì vẫn đổi được trong phiên này */
  }
  notify();
}

let player: HTMLAudioElement | null = null;
let fading: number | null = null;

function fadeTo(target: number, done?: () => void): void {
  if (!player) return;
  if (fading !== null) window.clearInterval(fading);
  const step = (target - player.volume) / (FADE_MS / 40);
  fading = window.setInterval(() => {
    if (!player) return;
    const next = player.volume + step;
    const arrived = step >= 0 ? next >= target : next <= target;
    player.volume = Math.min(1, Math.max(0, arrived ? target : next));
    if (arrived) {
      if (fading !== null) window.clearInterval(fading);
      fading = null;
      done?.();
    }
  }, 40);
}

/**
 * Bắt đầu phát, hoặc không làm gì nếu đang tắt.
 *
 * Tệp nhạc có thể chưa có mặt — lúc đó `play()` bị từ chối và **im lặng bỏ
 * qua**. Một góc thú cưng không mở được vì thiếu bài nhạc là cái giá sai.
 */
export function startMusic(): void {
  if (typeof window === "undefined" || !isMusicOn()) return;
  if (!player) {
    player = new Audio(SRC);
    player.loop = true;
    player.preload = "none";
  }
  player.volume = 0;
  void player
    .play()
    .then(() => fadeTo(VOLUME))
    .catch(() => {});
}

export function stopMusic(): void {
  if (!player) return;
  const target = player;
  fadeTo(0, () => {
    target.pause();
    target.currentTime = 0;
  });
}
