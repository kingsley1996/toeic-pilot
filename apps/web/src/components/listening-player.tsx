"use client";

import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  createYouTubePlayer,
  defaultFrameFactory,
  formatTime,
  PlayerFailed,
  replaySegment,
  SEEK_EPS,
  type ListeningPlayer,
  type PlayerErrorCode,
  type PlayerStatus,
} from "@/lib/listening-player";
import { Alert, Button, cx } from "@/components/ui";

const RATES = [0.75, 1, 1.25] as const;

/* Nhảy giờ (tua/seek/đơ mạng rồi vọt) thì chốt cũ vô nghĩa — chốt lại. Ngưỡng
 * trên bước tick thường (0.5s, kể cả 1.25x) để rung nhỏ không chốt đi chốt lại. */
const JUMP_TOL = 1.5;

const ERROR_MESSAGE: Record<PlayerErrorCode, string> = {
  VIDEO_NOT_EMBEDDABLE:
    "Video này tắt chế độ nhúng nên không phát trong bài học được. Transcript vẫn dùng được — bấm nút bên dưới để nghe trên YouTube.",
  VIDEO_UNAVAILABLE: "Không mở được video này (đã xoá hoặc để riêng tư). Thử một URL khác.",
  PLAYER_ERROR: "Trình phát gặp sự cố. Tải lại trang rồi thử lại.",
};

/**
 * Khung phát lại một segment của bài Listening Lab.
 *
 * Không autoplay lúc mount: trình duyệt chặn phát có tiếng khi chưa có tương
 * tác, nên lần phát đầu luôn phải bắt đầu từ tay user (nút Nghe lại). Đổi sang
 * segment khác (bằng một cú bấm) thì tự phát lại — cú bấm đó là tương tác rồi.
 */
export function ListeningPlayerView({
  videoId,
  start,
  end,
  stops,
  onError,
  onTimeUpdate,
  replaySignal,
}: {
  videoId: string;
  start: number;
  end: number;
  /** Mốc cuối mọi câu, tăng dần — chốt dừng bám vào đây chứ không bám `end`
   * của câu đang làm: tua sang câu khác rồi bấm play mà vẫn chốt `end` cũ là
   * pause ngay tức thì, bấm bao nhiêu lần cũng thế (đúng bug vừa sửa). */
  stops: number[];
  onError?: (code: PlayerErrorCode) => void;
  /** Bắn giờ phát khi video đang chạy (500ms/lần) — trang cha dùng để
   * highlight + cuộn list Transcript theo. Không dùng để chấm hay lưu. */
  onTimeUpdate?: (seconds: number) => void;
  /** Tăng số là phát lại câu hiện tại (bấm lại vào dòng đang chọn). Đổi câu
   * đã tự phát qua start/end nên tín hiệu này chỉ cho bấm-trùng. */
  replaySignal?: number;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<ListeningPlayer | null>(null);
  const cancelReplayRef = useRef<(() => void) | null>(null);
  const mountedRef = useRef(false);
  /* `onError` của parent có thể là hàm inline (đổi mỗi render) — giữ qua ref để
   * effect dựng player không phải dựng lại theo. Ghi ref trong effect là cập
   * nhật đăng ký, không phải state. */
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onErrorRef.current = onError;
  });
  /* Parent truyền inline là đổi mỗi render — giữ qua ref để effect poll dưới
   * không phải dựng lại theo, cùng mẹo với onErrorRef. */
  const onTimeUpdateRef = useRef(onTimeUpdate);
  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate;
  });

  const [status, setStatus] = useState<PlayerStatus>("loading");
  const [failed, setFailed] = useState<PlayerErrorCode | null>(null);
  const [rate, setRate] = useState<number>(1);

  /* Đồng hồ hiển thị: reset khi đổi segment — pattern "điều chỉnh state trong
   * render" của React docs cho đúng case này (không phải effect). */
  const [prevSeg, setPrevSeg] = useState({ start, end });
  const [now, setNow] = useState(start);
  if (prevSeg.start !== start || prevSeg.end !== end) {
    setPrevSeg({ start, end });
    setNow(start);
  }

  /* Iframe do effect tự tạo và tự dọn, React chỉ giữ khung bọc rỗng.
   *
   * Bài học đắt giá ở đây: iframe do React render rồi đưa cho `YT.Player` thì
   * API thay node ngay dưới chân React (nâng cấp = thay thế). Remount sau đó
   * (StrictMode dev, đổi video) dựng player trên node đã rời DOM: request embed
   * vẫn đi, onReady có khi vẫn bắn, nhưng iframe nằm ngoài document — mắt thấy
   * là khung rỗng, nút treo `loading`, không một lỗi nào. Ai sở hữu node thì
   * người đó dọn: effect tạo thì cleanup `frame.remove()`, React không mó vào
   * trong khung này bao giờ. */
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const makeFrame = () => {
      const frame = defaultFrameFactory(videoId)();
      wrap.append(frame);
      return frame;
    };
    let alive = true;
    let frame: HTMLIFrameElement | null = null;
    createYouTubePlayer(makeFrame, videoId, {
      onStatus: (next) => {
        if (alive) setStatus(next);
      },
      onError: (code) => {
        if (!alive) return;
        setFailed(code);
        onErrorRef.current?.(code);
      },
    })
      .then(({ player, frame: builtFrame }) => {
        if (!alive) {
          player.destroy();
          builtFrame.remove();
          return;
        }
        frame = builtFrame;
        playerRef.current = player;
      })
      .catch((err: unknown) => {
        if (!alive) return;
        // Lỗi player thật đã hiện alert đúng mã qua onError — ở đây chỉ còn
        // timeout/dud (hết 2 lượt thử), mới hiện alert chung.
        if (!(err instanceof PlayerFailed)) setFailed("PLAYER_ERROR");
      });
    return () => {
      alive = false;
      cancelReplayRef.current?.();
      playerRef.current?.destroy();
      playerRef.current = null;
      frame?.remove();
    };
  }, [videoId]);

  const lastTickRef = useRef(-1);
  const stopsRef = useRef(stops);
  useEffect(() => {
    stopsRef.current = stops;
  });
  const stopRef = useRef<number | null>(null);
  const latchStop = useCallback((current: number) => {
    stopRef.current = stopsRef.current.find((stop) => stop > current + SEEK_EPS) ?? null;
  }, []);

  const replay = useCallback(() => {
    const player = playerRef.current;
    if (!player || failed) return;
    cancelReplayRef.current?.();
    // Chốt đúng cuối câu sắp phát — poll khỏi phải đoán qua nhảy giờ.
    stopRef.current = end;
    cancelReplayRef.current = replaySegment(player, start, end, (current) => {
      setNow(current);
      onTimeUpdateRef.current?.(current);
    });
  }, [start, end, failed]);

  /* Đổi segment thì tự phát lại; lần đầu (mount) thì không — chưa có tương tác,
   * trình duyệt sẽ chặn tiếng. `mountedRef` chỉ ghi trong effect nên không vi
   * phạm luật render thuần. */
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    replay();
  }, [replay]);

  /* Bấm lại đúng dòng đang chọn: start/end không đổi nên effect trên không
   * thấy gì — tín hiệu đếm riêng cho ca này. Khởi bằng giá trị prop nên lần
   * đầu luôn bằng nhau (không phát lén lúc mount). */
  const lastSignalRef = useRef(replaySignal);
  useEffect(() => {
    if (lastSignalRef.current === replaySignal) return;
    lastSignalRef.current = replaySignal;
    replay();
  }, [replaySignal, replay]);

  /* Bám giờ phát mọi lúc — kể cả tua tay lúc đang dừng, vì YouTube không bắn
   * event seek khi paused nên chỉ còn cách hỏi. Chỉ render khi giờ đổi nên lúc
   * đứng yên là im lặng hoàn toàn.
   *
   * Và LUÔN dừng cuối câu: chốt dừng là mốc stops CHỨA vị trí đang phát. Chốt
   * chỉ đặt ở HAI chỗ có chủ ý — lúc bấm play (đọc đồng bộ trong handler, dưới)
   * và lúc phát hiện NHẢY giờ (tua/seek/đơ mạng). Tuyệt đối không chốt lại theo
   * giờ trôi: đọc stale sau seek (vẫn giờ cũ vài tick) mà chốt lại là pause
   * ngay — đúng bug "tua rồi play là pause liên tục", và mọi guard vá thêm chỉ
   * đẻ race mới. */
  useEffect(() => {
    const timer = window.setInterval(() => {
      const player = playerRef.current;
      if (!player) return;
      const current = player.getCurrentTime();
      if (current !== lastTickRef.current) {
        if (Math.abs(current - lastTickRef.current) > JUMP_TOL) latchStop(current);
        lastTickRef.current = current;
        setNow(current);
        onTimeUpdateRef.current?.(current);
      }
      const stop = stopRef.current;
      if (stop != null && current >= stop - SEEK_EPS) {
        player.pause();
        setNow(stop);
        onTimeUpdateRef.current?.(current);
      }
    }, 500);
    return () => window.clearInterval(timer);
  }, [latchStop]);

  const toggle = () => {
    const player = playerRef.current;
    if (!player) return;
    if (status === "playing") {
      player.pause();
      return;
    }
    // Bấm play là một lượt phát mới: chốt ngay trong handler (đọc đồng bộ, một
    // lần duy nhất) để nghe hết CÂU CHỨA vị trí hiện tại. Không chốt ở đây mà
    // để poll tự chốt thì đọc stale vài tick đầu là đủ để pause oan.
    latchStop(player.getCurrentTime());
    player.play();
  };

  const changeRate = (next: number) => {
    setRate(next);
    playerRef.current?.setPlaybackRate(next);
  };

  return (
    <div className="space-y-3">
      {/* Khung bọc RỖNG có chủ ý — iframe bên trong do effect quản (xem trên).
          Tỉ lệ 16:9 nằm ở khung này, iframe chỉ `h-full w-full` theo. */}
      <div
        ref={wrapRef}
        className="aspect-video w-full overflow-hidden rounded border border-rule bg-recess"
      />

      {failed ? (
        <Alert tone="warn">
          <p>{ERROR_MESSAGE[failed]}</p>
          <a
            className="mt-1 inline-block font-semibold text-action-ink underline"
            href={`https://www.youtube.com/watch?v=${videoId}`}
            target="_blank"
            rel="noreferrer"
          >
            Mở video trên YouTube
          </a>
        </Alert>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={replay} disabled={status === "loading"}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden />
            Nghe lại
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={toggle}
            disabled={status === "loading"}
            aria-label={status === "playing" ? "Tạm dừng" : "Phát"}
          >
            {status === "playing" ? (
              <Pause size={14} strokeWidth={2} aria-hidden />
            ) : (
              <Play size={14} strokeWidth={2} aria-hidden />
            )}
          </Button>
          <span
            className="font-data text-small text-ink-muted"
            aria-label={`Đang ở ${formatTime(now)} trên đoạn tới ${formatTime(end)}`}
          >
            {formatTime(now)} / {formatTime(end)}
          </span>
          <span className="ml-auto flex gap-1" role="group" aria-label="Tốc độ phát">
            {RATES.map((value) => (
              <Button
                key={value}
                size="sm"
                variant={rate === value ? "primary" : "secondary"}
                aria-pressed={rate === value}
                onClick={() => changeRate(value)}
                className={cx(rate !== value && "px-2")}
              >
                {value}x
              </Button>
            ))}
          </span>
        </div>
      )}
    </div>
  );
}
