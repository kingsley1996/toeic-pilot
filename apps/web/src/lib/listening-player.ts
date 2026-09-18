/**
 * Adapter phát lại cho Listening Lab — đúng interface SPEC §10, UI chỉ biết
 * interface này, không biết nguồn là YouTube hay gì khác.
 *
 * Không thêm dep: IFrame Player API của YouTube đủ seek/rate, nạp bằng script
 * tag theo đúng mẹo singleton của `components/turnstile.tsx`.
 */

/** Đúng 5 phương thức SPEC §10. UI chỉ biết interface này, không biết nguồn là
 * YouTube hay gì khác. `destroy` thêm cho vòng đời component (gỡ player khi
 * unmount) — không phải hành vi playback. */
export interface ListeningPlayer {
  play(): void;
  pause(): void;
  seek(seconds: number): void;
  getCurrentTime(): number;
  setPlaybackRate(rate: number): void;
  destroy(): void;
}

export type PlayerStatus = "loading" | "ready" | "playing" | "paused" | "ended";

export type PlayerErrorCode = "VIDEO_NOT_EMBEDDABLE" | "VIDEO_UNAVAILABLE" | "PLAYER_ERROR";

export type PlayerEvents = {
  onStatus?: (status: PlayerStatus) => void;
  onError?: (code: PlayerErrorCode) => void;
};

/* Kiểu tối thiểu của thứ IFrame API gắn vào `window` — chỉ khai những gì dùng,
 * không kéo `@types/youtube` cho một adapter. */
type YouTubePlayerInstance = {
  playVideo(): void;
  pauseVideo(): void;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  getCurrentTime(): number;
  setPlaybackRate(rate: number): void;
  loadVideoById(videoId: string): void;
  destroy(): void;
};

type YouTubeNamespace = {
  Player: new (
    el: HTMLElement,
    options: {
      videoId: string;
      /* BẮT BUỘC dù div đã có cỡ CSS: thiếu là API vẫn bắn onReady nhưng không
       * đẻ iframe (đã bắt tận tay — nút Nghe lại treo `loading` vĩnh viễn mà
       * không một lỗi nào). '100%' để khung `aspect-video` quyết cỡ thật. */
      height: string;
      width: string;
      playerVars: Record<string, unknown>;
      events: {
        onReady: () => void;
        onError: (event: { data: number }) => void;
        onStateChange: (event: { data: number }) => void;
      };
    },
  ) => YouTubePlayerInstance;
};

declare global {
  interface Window {
    YT?: YouTubeNamespace;
    onYouTubeIframeAPIReady?: () => void;
  }
}

const SCRIPT_SRC = "https://www.youtube.com/iframe_api";

/* Trạng thái số của IFrame API — magic number gom một chỗ để dưới không rải rác. */
const YT_STATE = { ENDED: 0, PLAYING: 1, PAUSED: 2, CUED: 5 } as const;

/* Mã lỗi onError của IFrame API: 101/150 là chủ video tắt embed, 100/105 là
 * video không tồn tại/riêng tư. Hai nhóm này UI phải nói hai câu khác nhau. */
function toErrorCode(data: number): PlayerErrorCode {
  if (data === 101 || data === 150) return "VIDEO_NOT_EMBEDDABLE";
  if (data === 100 || data === 105) return "VIDEO_UNAVAILABLE";
  return "PLAYER_ERROR";
}

/* Script tải MỘT lần cho cả trang — cùng lý do với turnstile: nhúng hai lần là
 * dựng lại namespace dưới chân player đang chạy. */
let scriptLoad: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve();
  scriptLoad ??= new Promise<void>((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      resolve();
    };
    // Treo callback cũ: trang khác cũng có thể đang đợi API này (hôm nay chưa
    // có, nhưng ghi đè im lặng là kiểu hỏng chỉ lộ khi trang thứ hai xuất hiện).
    const tag = document.createElement("script");
    tag.src = SCRIPT_SRC;
    tag.async = true;
    tag.onerror = () => {
      scriptLoad = null;
      reject(new Error("youtube iframe api failed to load"));
    };
    document.head.append(tag);
  });
  return scriptLoad;
}

/**
 * Phát lại một segment: nhảy tới `start`, chạy, dừng ở `end`. Trả về hàm huỷ —
 * component gọi khi đổi segment/unmount, không thì interval chạy mãi sau lưng.
 *
 * Poll 250ms thay vì rAF: dictation không cần chính xác từng khung hình, và
 * interval ngủ được khi tab nền (rAF thì không chạy, nhưng cũng không tốn).
 */
export function replaySegment(
  player: Pick<ListeningPlayer, "seek" | "play" | "pause" | "getCurrentTime">,
  start: number,
  end: number,
  onTick?: (current: number) => void,
): () => void {
  player.seek(start);
  player.play();
  const timer = window.setInterval(() => {
    const current = player.getCurrentTime();
    onTick?.(current);
    if (current >= end) {
      window.clearInterval(timer);
      player.pause();
      onTick?.(end);
    }
  }, 250);
  return () => window.clearInterval(timer);
}

export async function createYouTubePlayer(
  frame: HTMLIFrameElement,
  videoId: string,
  events: PlayerEvents,
): Promise<ListeningPlayer> {
  await loadScript();
  const namespace = window.YT;
  if (!namespace) throw new Error("youtube iframe api failed to load");

  let instance: YouTubePlayerInstance | null = null;
  let destroyed = false;

  /* Lệnh gọi trước khi player ready (seek/play ngay sau mount) xếp hàng ở đây
   * thay vì rơi mất — IFrame API chưa có instance thì gọi là ném lỗi. */
  const queue: Array<() => void> = [];
  const run = (fn: () => void) => {
    if (destroyed) return;
    if (instance) fn();
    else queue.push(fn);
  };

  /* `frame` phải là node React không quản (effect tự `createElement`/`remove`).
   * Đưa node do React render cho API là mất nó sau remount: API thay node ngay
   * dưới chân React, lần dựng sau xài node đã rời DOM — request embed vẫn đi
   * mà iframe nằm ngoài document. Chi tiết ở component gọi hàm này. */
  instance = new namespace.Player(frame, {
    videoId,
    height: "100%",
    width: "100%",
    playerVars: { enablejsapi: 1, rel: 0 },
    events: {
      onReady: () => {
        if (destroyed) return;
        events.onStatus?.("ready");
        queue.splice(0).forEach((fn) => fn());
      },
      onError: (event) => events.onError?.(toErrorCode(event.data)),
      onStateChange: (event) => {
        if (event.data === YT_STATE.PLAYING) events.onStatus?.("playing");
        else if (event.data === YT_STATE.PAUSED) events.onStatus?.("paused");
        else if (event.data === YT_STATE.ENDED) events.onStatus?.("ended");
        else if (event.data === YT_STATE.CUED) events.onStatus?.("ready");
      },
    },
  });

  return {
    play: () => run(() => instance?.playVideo()),
    pause: () => run(() => instance?.pauseVideo()),
    seek: (seconds) => run(() => instance?.seekTo(seconds, true)),
    getCurrentTime: () => instance?.getCurrentTime() ?? 0,
    setPlaybackRate: (rate) => run(() => instance?.setPlaybackRate(rate)),
    destroy: () => {
      destroyed = true;
      queue.length = 0;
      instance?.destroy();
      instance = null;
    },
  };
}
