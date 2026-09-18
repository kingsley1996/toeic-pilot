"use client";

import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  createYouTubePlayer,
  replaySegment,
  type ListeningPlayer,
  type PlayerErrorCode,
  type PlayerStatus,
} from "@/lib/listening-player";
import { Alert, Button, cx } from "@/components/ui";

const RATES = [0.75, 1, 1.25] as const;

const ERROR_MESSAGE: Record<PlayerErrorCode, string> = {
  VIDEO_NOT_EMBEDDABLE:
    "Video này tắt chế độ nhúng nên không phát trong bài học được. Transcript vẫn dùng được — bấm nút bên dưới để nghe trên YouTube.",
  VIDEO_UNAVAILABLE: "Không mở được video này (đã xoá hoặc để riêng tư). Thử một URL khác.",
  PLAYER_ERROR: "Trình phát gặp sự cố. Tải lại trang rồi thử lại.",
};

function formatTime(totalSeconds: number): string {
  const total = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

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
  onError,
}: {
  videoId: string;
  start: number;
  end: number;
  onError?: (code: PlayerErrorCode) => void;
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
    const frame = document.createElement("iframe");
    frame.src = `https://www.youtube.com/embed/${videoId}?enablejsapi=1&rel=0`;
    frame.title = "Video bài học";
    frame.allow = "accelerometer; autoplay; encrypted-media; picture-in-picture";
    frame.allowFullscreen = true;
    frame.className = "h-full w-full";
    wrap.append(frame);
    let alive = true;
    createYouTubePlayer(frame, videoId, {
      onStatus: (next) => {
        if (alive) setStatus(next);
      },
      onError: (code) => {
        if (!alive) return;
        setFailed(code);
        onErrorRef.current?.(code);
      },
    })
      .then((player) => {
        if (!alive) {
          player.destroy();
          return;
        }
        playerRef.current = player;
      })
      .catch(() => {
        if (alive) setFailed("PLAYER_ERROR");
      });
    return () => {
      alive = false;
      cancelReplayRef.current?.();
      playerRef.current?.destroy();
      playerRef.current = null;
      frame.remove();
    };
  }, [videoId]);

  const replay = useCallback(() => {
    const player = playerRef.current;
    if (!player || failed) return;
    cancelReplayRef.current?.();
    cancelReplayRef.current = replaySegment(player, start, end, setNow);
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

  const toggle = () => {
    if (status === "playing") playerRef.current?.pause();
    else playerRef.current?.play();
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
