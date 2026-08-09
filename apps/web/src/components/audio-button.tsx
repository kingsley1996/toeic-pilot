"use client";

import type { AudioClip } from "@toeic-pilot/shared";
import { useRef, useState } from "react";

import { cx } from "@/components/ui";

/** BCP-47 is what the API speaks; a two-letter chip is what fits on a button. */
const ACCENT_LABEL: Record<string, string> = {
  "en-US": "US",
  "en-GB": "UK",
  "en-AU": "AU",
  "en-CA": "CA",
};

/**
 * Plays one clip and shows that it is playing.
 *
 * A plain `Audio` object rather than the Web Audio API: it needs no CORS on the
 * media origin, which is what lets the clips be served straight from the object
 * store instead of being proxied (PHASE2-AUDIO A5).
 */
export function AccentButton({ clip }: { clip: AudioClip }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  function play() {
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
      onClick={play}
      aria-label={`Nghe giọng ${ACCENT_LABEL[clip.accent] ?? clip.accent}`}
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
        playing
          ? "border-brand bg-brand-soft text-brand-text"
          : "border-border-strong hover:border-brand hover:text-brand-text",
      )}
    >
      <span aria-hidden>{playing ? "▮▮" : "▶"}</span>
      {ACCENT_LABEL[clip.accent] ?? clip.accent}
    </button>
  );
}

export function AccentRow({ clips, className }: { clips: AudioClip[]; className?: string }) {
  if (clips.length === 0) return null;
  return (
    <div className={cx("flex flex-wrap gap-2", className)}>
      {clips.map((clip) => (
        <AccentButton key={clip.accent} clip={clip} />
      ))}
    </div>
  );
}
