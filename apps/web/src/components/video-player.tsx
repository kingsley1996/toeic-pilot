"use client";

import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Alert, Button, cx } from "@/components/ui";
import { SEEK_EPS, formatTime } from "@/lib/listening-player";

const RATES = [0.75, 1, 1.25] as const;

/* Pause chỉ khi tick trước đã ở gần chốt này: bằng chứng phát LIÊN TỤC tới
 * nơi — cùng lý do APPROACH của `ListeningPlayerView`. */
const APPROACH = 3;

/** Handle kênh từ URL TikTok (`/@user/video/...`) — không có thì giấu dòng kênh. */
function tiktokHandle(url?: string): string | null {
  if (!url) return null;
  const match = /@([^/?#]+)/.exec(url);
  return match ? match[1] : null;
}

/**
 * Phát file tự host (bài TikTok đã ingest) với cùng ngữ nghĩa câu như player
 * YouTube: đổi câu là seek + phát, hết câu tự dừng, video chạy thì báo giờ để
 * trang cha follow highlight. `<video>` native có sẵn sự kiện seeked/play nên
 * không cần vòng poll như IFrame API.
 *
 * Khung giả giao diện TikTok (nền đen, logo, @kênh, caption phủ dưới video)
 * để bài tự host vẫn nhận ra là TikTok — nút học từng câu giữ nguyên vì đó là
 * giá trị của Lab, TikTok thật không có.
 *
 * Không autoplay lúc mount (trình duyệt chặn tiếng): lần đầu bấm tay, đổi câu
 * sau thì tự phát — cùng luật `ListeningPlayerView`.
 */
export function VideoPlayerView({
  videoUrl,
  sourceUrl,
  title,
  start,
  end,
  stops,
  startLabel,
  onAdvance,
  onTimeUpdate,
  replaySignal,
  followSignal,
}: {
  videoUrl: string;
  /** Link xem gốc — lối thoát khi file lỗi. */
  sourceUrl?: string;
  /** Caption hiện dưới video như mô tả TikTok. */
  title?: string;
  start: number;
  end: number;
  /** Mốc cuối mọi câu, tăng dần — chốt dừng bám vào đây (xem `ListeningPlayerView`). */
  stops: number[];
  startLabel: string;
  onAdvance: () => void;
  onTimeUpdate?: (seconds: number) => void;
  replaySignal?: number;
  followSignal?: number;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate;
  });
  const [playing, setPlaying] = useState(false);
  const [failed, setFailed] = useState(false);
  const [rate, setRate] = useState<number>(1);
  const [duration, setDuration] = useState(0);
  const [now, setNow] = useState(start);
  /* Đổi video thì giờ/chốt cũ vô nghĩa — pattern "điều chỉnh state trong
   * render" (không phải effect) như `ListeningPlayerView`. */
  const [prevSrc, setPrevSrc] = useState({ videoUrl, start });
  if (prevSrc.videoUrl !== videoUrl || prevSrc.start !== start) {
    setPrevSrc({ videoUrl, start });
    setNow(start);
  }
  const stopRef = useRef<number | null>(null);
  const lastTickRef = useRef(-1);
  const stopsRef = useRef(stops);
  useEffect(() => {
    stopsRef.current = stops;
  });

  const latchStop = useCallback((current: number) => {
    stopRef.current = stopsRef.current.find((stop) => stop > current + SEEK_EPS) ?? null;
  }, []);

  const replay = useCallback(() => {
    const video = videoRef.current;
    if (!video || failed) return;
    stopRef.current = end;
    video.currentTime = start;
    void video.play().catch(() => {});
  }, [start, end, failed]);

  /* Follow đổi câu: đồng bộ chốt, giữ nguyên play/pause + vị trí. KHAI BÁO
   * TRƯỚC effect tự-phát dưới (effect chạy theo thứ tự khai báo) — cùng mẹo
   * `ListeningPlayerView`. */
  const silentRef = useRef(false);
  const lastFollowRef = useRef(followSignal);
  const prevSegRef = useRef({ start, end });
  useEffect(() => {
    const signalChanged = lastFollowRef.current !== followSignal;
    lastFollowRef.current = followSignal;
    const segChanged = prevSegRef.current.start !== start || prevSegRef.current.end !== end;
    prevSegRef.current = { start, end };
    if (!signalChanged || !segChanged) return;
    silentRef.current = true;
    stopRef.current = end;
  }, [followSignal, start, end]);

  /* Đổi câu thì tự phát lại, trừ lần mount đầu và đổi do follow. */
  const mountedRef = useRef(false);
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    const silent = silentRef.current;
    silentRef.current = false;
    if (!silent) replay();
  }, [replay]);

  /* Bấm lại đúng câu đang chọn: tín hiệu đếm riêng (start/end không đổi). */
  const lastSignalRef = useRef(replaySignal);
  useEffect(() => {
    if (lastSignalRef.current === replaySignal) return;
    lastSignalRef.current = replaySignal;
    replay();
  }, [replaySignal, replay]);

  /* Bắt đầu tải video mới thì chốt/giờ cũ vô nghĩa (event, không effect). */
  function handleLoadStart() {
    stopRef.current = null;
    lastTickRef.current = -1;
  }

  function handleTimeUpdate() {
    const video = videoRef.current;
    if (!video) return;
    const current = video.currentTime;
    const previous = lastTickRef.current;
    lastTickRef.current = current;
    setNow(current);
    onTimeUpdateRef.current?.(current);
    const stop = stopRef.current;
    if (
      !video.paused &&
      stop != null &&
      current >= stop - SEEK_EPS &&
      previous >= stop - APPROACH
    ) {
      video.pause();
      setNow(stop);
    }
  }

  const toggle = () => {
    const video = videoRef.current;
    if (!video || failed) return;
    if (!video.paused) {
      video.pause();
      return;
    }
    playActive();
  };

  /* Nút play khi dừng có hai nghĩa như player YouTube: ngay cuối câu thì tiến,
   * còn lại resume đúng chỗ dừng + chốt lại. */
  const playActive = () => {
    const video = videoRef.current;
    if (!video || failed) return;
    const current = video.currentTime;
    if (current >= end - SEEK_EPS && current < end + 1.0) {
      onAdvance();
      return;
    }
    latchStop(current);
    void video.play().catch(() => {});
  };

  const changeRate = (next: number) => {
    setRate(next);
    if (videoRef.current) videoRef.current.playbackRate = next;
  };

  const handle = tiktokHandle(sourceUrl);

  return (
    <div className="mx-auto w-full max-w-[320px] space-y-3">
      <div className="relative overflow-hidden rounded border border-rule bg-black">
        {/* Dọc 9:16 của TikTok thì hãm chiều cao, ngang thì full khung. */}
        <video
          ref={videoRef}
          src={videoUrl}
          preload="metadata"
          playsInline
          onLoadStart={handleLoadStart}
          onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
          onPlay={() => {
            latchStop(videoRef.current?.currentTime ?? 0);
            setPlaying(true);
          }}
          onPause={() => setPlaying(false)}
          onSeeked={() => latchStop(videoRef.current?.currentTime ?? 0)}
          onTimeUpdate={handleTimeUpdate}
          onError={() => setFailed(true)}
          className="max-h-[440px] w-full"
        />
        {/* Logo góc trên — nốt nhạc tự vẽ (lucide không có icon brand), chữ
          trắng trên nền đen là đủ nhận ra, không nhái màu chromatic của họ. */}
        <span className="absolute left-2 top-2 inline-flex items-center gap-1.5 rounded bg-black/70 px-2 py-1">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="#fff" aria-hidden>
            <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
          </svg>
          <span className="text-label font-bold text-white">TikTok</span>
        </span>
        <div className="absolute inset-x-0 bottom-0 space-y-0.5 bg-gradient-to-t from-black/85 to-transparent px-3 pb-2.5 pt-10">
          {handle && sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="block w-fit font-semibold text-white"
            >
              @{handle}
            </a>
          )}
          {title && <p className="line-clamp-2 text-small leading-snug text-white/90">{title}</p>}
          <p className="text-small text-white/75">♪ âm thanh gốc</p>
        </div>
      </div>
      {failed ? (
        <Alert tone="warn">
          <p>Không phát được file video này.</p>
          {sourceUrl && (
            <a
              className="mt-1 inline-block font-semibold text-action-ink underline"
              href={sourceUrl}
              target="_blank"
              rel="noreferrer"
            >
              Mở video gốc
            </a>
          )}
        </Alert>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={toggle}>
            {playing ? (
              <Pause size={14} strokeWidth={2} aria-hidden />
            ) : (
              <Play size={14} strokeWidth={2} aria-hidden />
            )}
            {playing ? "Tạm dừng" : startLabel}
          </Button>
          <Button size="sm" variant="secondary" onClick={replay}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden />
            Nghe lại
          </Button>
          <span className="font-data text-small text-ink-muted">
            {formatTime(now)} / {duration > 0 ? formatTime(duration) : "–:––"}
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
