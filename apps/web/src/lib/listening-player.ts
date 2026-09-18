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

/* Seek của YouTube không tới ngay tick sau — cho phép lệch một chút khi nhận
 * biết "đã tới segment", chứ không là seek đáp xuống 18.59 cho start=18.64 thì
 * chờ tới hết giờ cũng không phát. */
const SEEK_EPS = 0.2;

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
    // Seek là bất đồng bộ: đổi từ câu sau về câu trước thì vài tick đầu vẫn
    // đọc giờ CŨ (>= end) — dừng ngay là câu mới không bao giờ phát. Chờ tới
    // khi giờ phát chạm segment mới bắt đầu tính giờ dừng.
    if (current < start - SEEK_EPS) return;
    onTick?.(current);
    if (current >= end) {
      window.clearInterval(timer);
      player.pause();
      onTick?.(end);
    }
  }, 250);
  return () => window.clearInterval(timer);
}

/* Đếm khung để đặt id/src duy nhất (dưới). */
let frameSeq = 0;

export type FrameFactory = () => HTMLIFrameElement;

/** Khung iframe mới cho player. Mỗi lần gọi là node + src mới hoàn toàn —
 * API YouTube tra player theo iframe mà nó từng thấy, nên dựng lại trên node
 * hay src đã dùng là xin dính bản ghi nội bộ của player cũ. */
export function defaultFrameFactory(videoId: string): FrameFactory {
  return () => {
    frameSeq += 1;
    const frame = document.createElement("iframe");
    frame.id = `listening-frame-${frameSeq}`;
    // KHÔNG thêm param lạ vào src để làm duy nhất: đã thử (`labframe`) và
    // /embed trả trang lỗi → player không bao giờ init (dud 100%, còn tệ hơn
    // bệnh cần chữa). Duy nhất bằng id + node mới là đủ.
    frame.src = `https://www.youtube.com/embed/${videoId}?enablejsapi=1&rel=0`;
    frame.title = "Video bài học";
    frame.allow = "accelerometer; autoplay; encrypted-media; picture-in-picture";
    frame.allowFullscreen = true;
    frame.className = "h-full w-full";
    return frame;
  };
}

export async function createYouTubePlayer(
  makeFrame: FrameFactory,
  videoId: string,
  events: PlayerEvents,
): Promise<{ player: ListeningPlayer; frame: HTMLIFrameElement }> {
  await loadScript();
  const namespace = window.YT;
  if (!namespace) throw new Error("youtube iframe api failed to load");

  /* Dud KHÔNG nhận ra được lúc `new` vừa xong: method của wrapper gắn bất đồng
   * bộ sau đó, nên kiểm hình dạng đồng bộ là loại luôn cả player lành (đã thử
   * và ăn PLAYER_ERROR oan 100%). Dấu hiệu dud thật là onReady KHÔNG BAO GIỜ
   * tới — nút treo `loading`, không lỗi. Đợi ready có hạn, quá hạn thì vứt
   * khung làm khung mới, thử lại đúng một lần rồi mới chịu thua. */
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const frame = makeFrame();
    const outcome = await tryBuild(namespace, frame, videoId, events);
    if (outcome.status === "ready") return { player: outcome.player, frame };
    frame.remove();
    // Lỗi player thật (video cấm nhúng, video chết...) thì onError đã hiện
    // alert đúng mã — thử lại cũng ra y thế, ném luôn để component khỏi đè
    // PLAYER_ERROR chung chung lên trên.
    if (outcome.status === "player-error") throw new PlayerFailed(outcome.code);
  }
  throw new Error("youtube player did not become ready");
}

/** Lỗi player thật từ YouTube (mã cụ thể đã tới UI qua onError). Phân biệt với
 * `Error` thường (timeout/dud) để component không hiện nhầm alert chung. */
export class PlayerFailed extends Error {
  constructor(public code: PlayerErrorCode) {
    super(code);
    this.name = "PlayerFailed";
  }
}

/* Đợi onReady: player lành báo trong 1–3 giây; dud thì im vĩnh viễn. */
const READY_TIMEOUT_MS = 8000;

function tryBuild(
  namespace: YouTubeNamespace,
  frame: HTMLIFrameElement,
  videoId: string,
  events: PlayerEvents,
): Promise<
  | { status: "ready"; player: ListeningPlayer }
  | { status: "player-error"; code: PlayerErrorCode }
  | { status: "timeout" }
> {
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

  /* `frame` phải là node React không quản (effect tự tạo/dọn qua factory).
   * Đưa node do React render cho API là mất nó sau remount: API thay node ngay
   * dưới chân React, lần dựng sau xài node đã rời DOM — request embed vẫn đi
   * mà iframe nằm ngoài document. Chi tiết ở component gọi hàm này. */
  const player: ListeningPlayer = {
    play: () => run(() => instance?.playVideo()),
    pause: () => run(() => instance?.pauseVideo()),
    seek: (seconds) => run(() => instance?.seekTo(seconds, true)),
    getCurrentTime: () => instance?.getCurrentTime() ?? 0,
    setPlaybackRate: (rate) => run(() => instance?.setPlaybackRate(rate)),
    destroy: () => {
      destroyed = true;
      queue.length = 0;
      try {
        instance?.destroy();
      } catch {
        /* player dởm cũng kẹt ở đây — đã vứt khung, không cần nó dọn đẹp */
      }
      instance = null;
    },
  };

  return new Promise((resolve) => {
    let settled = false;
    const done = (
      outcome:
        | { status: "ready"; player: ListeningPlayer }
        | { status: "player-error"; code: PlayerErrorCode }
        | { status: "timeout" },
    ) => {
      // onError có thể tới SAU timeout (dud nằm im rồi mới báo lỗi): promise
      // chỉ nhận kết quả đầu, và callback UI cũng chỉ bắn một lần.
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      resolve(outcome);
    };
    const timer = window.setTimeout(() => {
      player.destroy();
      done({ status: "timeout" });
    }, READY_TIMEOUT_MS);
    let instance_: YouTubePlayerInstance | null = null;
    try {
      instance_ = new namespace.Player(frame, {
        videoId,
        height: "100%",
        width: "100%",
        playerVars: { enablejsapi: 1, rel: 0 },
        events: {
          onReady: () => {
            if (destroyed) return;
            instance = instance_;
            events.onStatus?.("ready");
            queue.splice(0).forEach((fn) => fn());
            done({ status: "ready", player });
          },
          onError: (event) => {
            const code = toErrorCode(event.data);
            events.onError?.(code);
            player.destroy();
            done({ status: "player-error", code });
          },
          onStateChange: (event) => {
            if (event.data === YT_STATE.PLAYING) events.onStatus?.("playing");
            else if (event.data === YT_STATE.PAUSED) events.onStatus?.("paused");
            else if (event.data === YT_STATE.ENDED) events.onStatus?.("ended");
            else if (event.data === YT_STATE.CUED) events.onStatus?.("ready");
          },
        },
      });
    } catch {
      done({ status: "timeout" });
    }
  });
}
