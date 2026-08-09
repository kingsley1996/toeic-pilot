"use client";

import type { AudioClip } from "@toeic-pilot/shared";
import { CircleSlash, Pause } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cx } from "@/components/ui";

/**
 * Bốn giọng TOEIC — thang phân loại đúng bốn giá trị, mang DỮ LIỆU chứ không
 * trang trí (DESIGN-SYSTEM §4).
 *
 * Ba điều ràng buộc bảng này, theo thứ tự:
 *
 *  1. Không dùng màu cờ. Bốn lá cờ này dùng gần như cùng một bộ màu nên chúng
 *     không phân biệt được với nhau — câu trả lời hiển nhiên lại là câu sai.
 *  2. Bốn màu nằm trên một BẬC THANG ĐỘ SÁNG (tỉ số ~1.3x giữa hai màu liền
 *     kề), nên chúng vẫn phân biệt được khi chuyển sang thang xám.
 *  3. Nhãn hai chữ LUÔN hiện. Màu là mã hoá dư thừa, không bao giờ là kênh
 *     thông tin duy nhất.
 *
 * Tên class phải viết tĩnh: Tailwind quét mã nguồn bằng chuỗi, nên
 * `bg-accent-${x}` sẽ không sinh ra CSS nào.
 */
const ACCENTS: Record<string, { label: string; on: string; dot: string; ring: string }> = {
  "en-US": {
    label: "US",
    on: "bg-accent-us text-panel",
    dot: "bg-accent-us",
    ring: "border-accent-us",
  },
  "en-GB": {
    label: "UK",
    on: "bg-accent-uk text-panel",
    dot: "bg-accent-uk",
    ring: "border-accent-uk",
  },
  "en-AU": {
    label: "AU",
    on: "bg-accent-au text-panel",
    dot: "bg-accent-au",
    ring: "border-accent-au",
  },
  "en-CA": {
    label: "CA",
    on: "bg-accent-ca text-panel",
    dot: "bg-accent-ca",
    ring: "border-accent-ca",
  },
};

const FALLBACK = { label: "??", on: "bg-ink text-panel", dot: "bg-ink", ring: "border-ink" };

/** `m:ss.d` — thời lượng là số đo, nên nó dùng font data và thẳng cột. */
function formatDuration(ms: number | null | undefined): string | null {
  if (!ms || ms <= 0) return null;
  const total = ms / 1000;
  const minutes = Math.floor(total / 60);
  const seconds = (total % 60).toFixed(1).padStart(4, "0");
  return `${minutes}:${seconds}`;
}

/**
 * Phát một clip và cho thấy nó đang phát.
 *
 * Dùng đối tượng `Audio` thuần chứ không phải Web Audio API: nó không đòi CORS
 * trên nguồn media, và đó chính là thứ cho phép clip được phục vụ thẳng từ
 * object store thay vì phải proxy qua API (PHASE2-AUDIO §A5).
 */
export function AccentChip({ clip }: { clip: AudioClip }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const style = ACCENTS[clip.accent] ?? FALLBACK;
  const duration = formatDuration(clip.duration_ms);

  // Rời trang giữa chừng mà không dừng thì tiếng vẫn chạy tiếp trên một
  // component đã bị gỡ.
  useEffect(() => () => audio.current?.pause(), []);

  function toggle() {
    if (playing) {
      audio.current?.pause();
      setPlaying(false);
      return;
    }
    audio.current?.pause();
    const element = new Audio(clip.url);
    audio.current = element;
    element.addEventListener("ended", () => setPlaying(false));
    element.addEventListener("error", () => setPlaying(false));
    setPlaying(true);
    void element.play().catch(() => setPlaying(false));
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`${playing ? "Dừng" : "Nghe"} giọng ${style.label}`}
      aria-pressed={playing}
      className={cx(
        "inline-flex h-8 items-center gap-1.5 rounded-pill border px-2.5 text-label font-semibold uppercase transition-colors",
        playing
          ? cx(style.on, "border-transparent")
          : cx("border-rule-strong text-ink-muted hover:text-ink", `hover:${style.ring}`),
      )}
    >
      {playing ? (
        <Pause size={12} strokeWidth={2} aria-hidden />
      ) : (
        <span aria-hidden className={cx("h-1.5 w-1.5 rounded-pill", style.dot)} />
      )}
      {style.label}
      {duration && (
        <span
          className={cx(
            "font-data text-[0.625rem] normal-case",
            playing ? "opacity-80" : "text-ink-faint",
          )}
        >
          {duration}
        </span>
      )}
    </button>
  );
}

/** Một chỗ trống cho giọng chưa có clip. */
function MissingChip({ accent }: { accent: string }) {
  const style = ACCENTS[accent] ?? FALLBACK;
  return (
    <span
      title={`Chưa có clip giọng ${style.label}`}
      className="inline-flex h-8 cursor-not-allowed items-center gap-1.5 rounded-pill border border-dashed border-rule-strong px-2.5 text-label font-semibold uppercase text-ink-faint"
    >
      <CircleSlash size={12} strokeWidth={2} aria-hidden />
      {style.label}
    </span>
  );
}

/**
 * Bốn giọng của một mục.
 *
 * Giọng thiếu clip vẫn hiện, ở dạng vô hiệu hoá — KHÔNG ẩn đi. Người học cần
 * biết giọng đó tồn tại nhưng chưa được thu, chứ không phải tưởng app chỉ có ba
 * giọng.
 */
export function AccentRow({
  clips,
  className,
  showMissing = false,
}: {
  clips: AudioClip[];
  className?: string;
  showMissing?: boolean;
}) {
  const present = new Set(clips.map((clip) => clip.accent));
  const missing = showMissing ? Object.keys(ACCENTS).filter((a) => !present.has(a)) : [];
  if (clips.length === 0 && missing.length === 0) return null;

  return (
    <div className={cx("flex flex-wrap items-center gap-1.5", className)}>
      {Object.keys(ACCENTS)
        .map((accent) => clips.find((clip) => clip.accent === accent))
        .filter((clip): clip is AudioClip => clip !== undefined)
        .map((clip) => (
          <AccentChip key={clip.accent} clip={clip} />
        ))}
      {clips
        .filter((clip) => !(clip.accent in ACCENTS))
        .map((clip) => (
          <AccentChip key={clip.accent} clip={clip} />
        ))}
      {missing.map((accent) => (
        <MissingChip key={accent} accent={accent} />
      ))}
    </div>
  );
}
