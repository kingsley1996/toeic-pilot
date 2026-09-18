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

/* Đứng trong cửa sổ này quanh cuối câu thì nút play hiểu là "nghe tiếp câu
 * sau" (tiến), chứ không phải resume: lố qua mốc vài trăm ms do tick thưa vẫn
 * tính là vừa xong câu. Ngoài cửa sổ (tua đi xa) thì resume đúng chỗ dừng. */
const ADVANCE_GRACE = 1.0;

/* Pause chỉ khi tick trước đã ở gần chốt này: bằng chứng phát LIÊN TỤC tới
 * nơi. Rộng hơn JUMP_TOL một bậc để tick thưa (tab nền) không làm mất pause
 * thật — mất một lần pause thật rẻ hơn một lần pause oan rất nhiều. */
const APPROACH = 3;

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
  startLabel,
  onAdvance,
  onError,
  onTimeUpdate,
  replaySignal,
  followSignal,
}: {
  videoId: string;
  start: number;
  end: number;
  /** Mốc cuối mọi câu, tăng dần — chốt dừng bám vào đây chứ không bám `end`
   * của câu đang làm: tua sang câu khác rồi bấm play mà chốt `end` cũ là
   * pause ngay tức thì, bấm bao nhiêu lần cũng thế (đúng bug vừa sửa). */
  stops: number[];
  /** Chữ nút phát khi đang dừng: "Bắt đầu" ở câu đầu, "Tiếp tục" ở câu sau. */
  startLabel: string;
  /** Bấm play đúng lúc vừa xong câu đang làm thì tiến sang câu kế (trang cha
   * lo: đổi bài tập + seek + phát). Không có là nút "Tiếp tục" bấm ra "Nghe
   * lại" — nói dối trắng trợn. */
  onAdvance: () => void;
  onError?: (code: PlayerErrorCode) => void;
  /** Bắn giờ phát khi video đang chạy (500ms/lần) — trang cha dùng để
   * highlight + cuộn list Transcript theo. Không dùng để chấm hay lưu. */
  onTimeUpdate?: (seconds: number) => void;
  /** Tăng số là phát lại câu hiện tại (bấm lại vào dòng đang chọn). Đổi câu
   * đã tự phát qua start/end nên tín hiệu này chỉ cho bấm-trùng. */
  replaySignal?: number;
  /** Câu đổi do follow tự động (tua tới/video chạy sang): đồng bộ chốt theo,
   * KHÔNG seek, KHÔNG play/pause — giữ nguyên trạng thái phát. Không có đường
   * này là follow-advance rơi vào effect tự-phát bên dưới: tua tới câu khác
   * đang dừng mà nó seek về đầu câu rồi tự phát (giật + sai yêu cầu). */
  followSignal?: number;
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
  // Tổng thời lượng video để làm mẫu số đồng hồ — có sau khi metadata về, nên
  // nhớ riêng thay vì đọc mỗi render (chưa có là 0 suốt).
  const [duration, setDuration] = useState(0);

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

  /* Follow tự động đổi câu: đồng bộ chốt dừng + dẹp replay dở, giữ nguyên
   * play/pause + vị trí. KHAI BÁO TRƯỚC effect tự-phát dưới (effect chạy theo
   * thứ tự khai báo) để cờ silent tới nơi trước khi effect kia đọc. Bỏ qua khi
   * start/end không đổi theo (tín hiệu lạ): không treo cờ oan cho lần đổi sau. */
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
    cancelReplayRef.current?.();
  }, [followSignal, start, end]);

  /* Đổi segment thì tự phát lại; lần đầu (mount) thì không — chưa có tương tác,
   * trình duyệt sẽ chặn tiếng. `mountedRef` chỉ ghi trong effect nên không vi
   * phạm luật render thuần.
   *
   * Ngoại lệ: đổi do follow tự động (cờ silent ở trên) thì BỎ QUA — follow đã
   * đồng bộ chốt, replay ở đây là seek về đầu câu + phát (đúng thứ user cấm:
   * tua tới đang dừng mà tự phát). Đọc + xoá cờ trong cùng effect để cờ lạ
   * không rò sang lần đổi sau. */
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }
    const silent = silentRef.current;
    silentRef.current = false;
    if (!silent) replay();
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
   * chỉ đặt ở HAI chỗ có chủ ý — lúc bấm play/replay (đọc đồng bộ trong
   * handler) và lúc phát hiện NHẢY giờ (tua/seek/đơ mạng). Còn lệnh pause thì
   * có thêm HAI điều kiện BẮT BUỘC: đang phát THẬT (status YouTube xác nhận,
   * không phải suy từ giờ) và tick trước đã ở gần chốt (phát LIÊN TỤC tới
   * nơi). Thiếu vế đầu là bấm play thẳng trên video (bypass toggle — chỗ duy
   * nhất chốt trước đây) bị poll giết bằng chốt stale trong nửa giây, bấm bao
   * nhiêu lần cũng thế. Thiếu vế sau là đọc stale sau seek cũng bắn. */
  // Trạng thái phát cho poll đọc (effect chạy một lần nên không đọc state trực
  // tiếp được — state trong closure interval là ảnh cũ vĩnh viễn).
  const statusRef = useRef(status);
  useEffect(() => {
    statusRef.current = status;
  });
  // Lượt phát mới tính từ MỌI nguồn (nút mình, bấm thẳng vào video, autoplay
  // của YouTube): chốt lại theo vị trí lúc bắt đầu phát.
  const wasPlayingRef = useRef(false);
  useEffect(() => {
    const timer = window.setInterval(() => {
      const player = playerRef.current;
      if (!player) return;
      const total = player.getDuration();
      if (total > 0) setDuration((prev) => (prev === total ? prev : total));
      const current = player.getCurrentTime();
      const previous = lastTickRef.current;
      if (current !== previous) {
        // Nhảy giờ: chốt cũ vô nghĩa, chốt lại theo vị trí MỚI — và tuyệt đối
        // không pause ở tick này.
        if (Math.abs(current - previous) > JUMP_TOL) latchStop(current);
        lastTickRef.current = current;
        setNow(current);
        onTimeUpdateRef.current?.(current);
      }
      const playing = statusRef.current === "playing";
      if (playing && !wasPlayingRef.current) latchStop(current);
      wasPlayingRef.current = playing;
      const stop = stopRef.current;
      if (playing && stop != null && current >= stop - SEEK_EPS && previous >= stop - APPROACH) {
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
    // Đang tải dở (buffering) cũng coi như đang phát để bấm là dừng — kẹt tải
    // mà nút không ăn thì user chỉ còn nước F5.
    if (status === "playing" || status === "buffering") {
      player.pause();
      return;
    }
    playActive();
  };

  /* Nút play khi dừng có HAI nghĩa, chia theo vị trí đang đứng:
   * - Ngay cuối câu đang làm (vừa pause hết câu): TIẾN sang câu kế — cả ba
   *   (video, list, bài tập) cùng đi, đúng tên nút "Tiếp tục". Phát lại câu cũ
   *   ở đây là nói dối trắng trợn.
   * - Còn lại (giữa câu, tua đi nơi khác): resume đúng chỗ dừng + chốt lại —
   *   không lôi bài tập đi theo, chữ đang gõ dở được yên. */
  const playActive = () => {
    const player = playerRef.current;
    if (!player) return;
    const current = player.getCurrentTime();
    if (current >= end - SEEK_EPS && current < end + ADVANCE_GRACE) {
      onAdvance();
      return;
    }
    latchStop(current);
    player.play();
  };

  const changeRate = (next: number) => {
    setRate(next);
    playerRef.current?.setPlaybackRate(next);
  };

  const running = status === "playing" || status === "buffering";

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
          <Button size="sm" onClick={toggle} disabled={status === "loading"}>
            {running ? (
              <Pause size={14} strokeWidth={2} aria-hidden />
            ) : (
              <Play size={14} strokeWidth={2} aria-hidden />
            )}
            {running ? "Tạm dừng" : startLabel}
          </Button>
          <Button size="sm" variant="secondary" onClick={replay} disabled={status === "loading"}>
            <RotateCcw size={14} strokeWidth={2} aria-hidden />
            Nghe lại
          </Button>
          <span
            className="font-data text-small text-ink-muted"
            aria-label={`Đang ở ${formatTime(now)} trên tổng ${formatTime(duration)}`}
          >
            {formatTime(now)} / {duration > 0 ? formatTime(duration) : "–:––"}
          </span>
          {status === "buffering" && (
            <span className="text-small text-ink-faint">Đang tải video…</span>
          )}
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
