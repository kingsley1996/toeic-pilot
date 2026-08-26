/**
 * Tiếng báo của giao diện, và cái công tắc tắt nó.
 *
 * Cùng khuôn với `theme.ts`, và vì cùng một lý do đã ghi ở đó: sự kiện `storage`
 * của trình duyệt chỉ bắn ở CÁC TAB KHÁC, nên ghi rồi mong React tự nhận ra sẽ
 * âm thầm không bao giờ chạy trong chính tab vừa ghi. Danh sách `listeners` là
 * phần bù cho chỗ đó.
 *
 * Khác `theme.ts` ở một điểm: **hai trạng thái, không phải ba.** Theme có
 * `system` vì hệ điều hành có một câu trả lời để đi theo. Âm thanh thì không —
 * `prefers-reduced-motion` nói về chuyển động, không nói về tiếng, và không có
 * `prefers-reduced-sound`. Nên chỉ còn bật hoặc tắt, và **mặc định là bật**: một
 * phản hồi mà không ai tìm ra cách bật lên thì coi như không tồn tại.
 */

const KEY = "sound";
const listeners = new Set<() => void>();

/** Đủ nghe trong phòng yên, không giật mình khi cắm tai nghe. */
const VOLUME = 0.45;

const SOURCES = {
  complete: "/sounds/complete.mp3",
} as const;

export type SoundName = keyof typeof SOURCES;

function notify(): void {
  for (const listener of listeners) listener();
}

export function subscribeToSound(onChange: () => void): () => void {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function isSoundOn(): boolean {
  if (typeof window === "undefined") return true;
  try {
    // Chỉ chuỗi "off" mới tắt. Mọi giá trị khác — kể cả rác còn sót từ một phiên
    // bản trước — đọc thành bật, nên một ô localStorage hỏng không lặng lẽ lấy
    // mất tính năng.
    return localStorage.getItem(KEY) !== "off";
  } catch {
    // Safari riêng tư ném lỗi khi đọc localStorage.
    return true;
  }
}

/** Máy chủ không có localStorage, nên nó chỉ báo được "chưa biết". */
export function serverSoundPref(): undefined {
  return undefined;
}

export function setSoundOn(on: boolean): void {
  try {
    if (on) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, "off");
  } catch {
    /* không lưu được thì vẫn đổi được trong phiên này */
  }
  notify();
}

/*
 * Mỗi tên một phần tử `Audio`, dựng lúc cần và giữ lại.
 *
 * Dựng mới mỗi lần phát nghĩa là tải lại file mỗi lần — trình duyệt cache được,
 * nhưng lần phát đầu sau mỗi lần dựng vẫn phải chờ decode, nên tiếng sẽ trễ so
 * với cú bấm đúng vào lúc nó cần khớp nhất.
 */
const players = new Map<SoundName, HTMLAudioElement>();

/**
 * Phát một tiếng báo, và **không bao giờ làm hỏng việc đang diễn ra vì nó**.
 *
 * `play()` trả về một Promise bị từ chối khi trình duyệt chặn tự phát, và nó
 * chặn thật: âm thanh chỉ được phép chạy sau khi người dùng đã tương tác với
 * trang. Ngay sau một lần nạp lại trang thì chưa có tương tác nào, nên mọi
 * thông báo bắn ra từ một lần `fetch` lúc mở trang sẽ bị chặn — đó là lý do chỉ
 * những thông báo đi ngay sau một cú bấm mới xin tiếng (xem `ToastInput.sound`).
 *
 * Promise bị từ chối mà không ai bắt sẽ thành `unhandledrejection` trong
 * console, và một lỗi đỏ vì cái chuông là thứ khiến người ta đi tìm bug ở chỗ
 * không có bug.
 */
export function playSound(name: SoundName): void {
  if (typeof window === "undefined" || !isSoundOn()) return;
  let player = players.get(name);
  if (!player) {
    player = new Audio(SOURCES[name]);
    player.volume = VOLUME;
    players.set(name, player);
  }
  // Gõ nhanh hai câu liền nhau thì tiếng thứ hai phải bắt đầu lại từ đầu, chứ
  // không bị bỏ qua vì phần tử đang bận phát.
  player.currentTime = 0;
  void player.play().catch(() => {});
}
