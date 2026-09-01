"use client";

/**
 * Ba ô minh hoạ của trang giới thiệu, chạy thật thay vì đứng yên.
 *
 * Chúng dùng **đúng class CSS của trang** (`.l-mock-inner`, `.l-word`, …) chứ
 * không tự dựng bảng màu riêng: Remotion vẽ vào cùng document, nên `.landing`
 * vẫn phủ tới và ba ô này tự đúng ở cả hai chế độ sáng tối. Cảnh chỉ thêm
 * chuyển động lên đúng khối tĩnh đã có.
 *
 * Mỗi ô một composition riêng, không phải một cảnh ba phần: ba ô nằm ở ba dải
 * cách xa nhau, và ghép chung sẽ bắt người xem ở dải này chờ hết phần của dải
 * kia. `MockPlayer` chỉ cho cảnh chạy khi nó thật sự nằm trong khung nhìn.
 */

import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export const FPS = 30;

/* ── 1. Thẻ từ vựng ──────────────────────────────────────────────────────── */

export const VOCAB_DURATION = 300;
const WORD = "invoice";
const ACCENTS = ["US", "UK", "AU", "CA"];

export function VocabCard() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Gõ từng chữ: người xem thấy từ được đánh ra, không phải hiện sẵn.
  const typed = Math.min(WORD.length, Math.max(0, Math.floor((frame - 10) / 4)));
  const caret = frame > 10 && typed < WORD.length;

  const after = (at: number) =>
    interpolate(frame, [at, at + 12], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

  const phonetic = after(48);
  const definition = after(64);

  return (
    <div className="l-mock-inner">
      <div className="l-label">Business · Từ vựng</div>
      <div className="l-word">
        {WORD.slice(0, typed)}
        {caret && <span style={{ opacity: frame % 16 < 8 ? 1 : 0 }}>|</span>}
      </div>
      <div className="l-phonetic" style={{ opacity: phonetic }}>
        /ˈɪnvɔɪs/
      </div>
      <div
        className="l-definition"
        style={{ opacity: definition, transform: `translateY(${(1 - definition) * 6}px)` }}
      >
        <b>noun</b>
        <br />
        <span>a document showing goods or services and the amount to be paid</span>
      </div>
      <div className="l-audio">
        <div className="l-play">▶</div>
        <span className="l-audio-label">Nghe phát âm</span>
        {ACCENTS.map((code, i) => {
          // Bốn giọng sáng lên LẦN LƯỢT — đó là điều ô này muốn nói: cùng một từ,
          // bốn bản thu khác nhau.
          const at = 96 + i * 34;
          const pop = spring({ frame: frame - at, fps, durationInFrames: 10 });
          const lit = frame >= at && frame < at + 30;
          return (
            <span
              key={code}
              className="l-chip"
              style={{
                transform: `scale(${1 + pop * 0.08 * (lit ? 1 : 0)})`,
                borderColor: lit ? "var(--l-orange)" : "var(--l-line)",
                color: lit ? "var(--l-orange-dark)" : "inherit",
              }}
            >
              {code}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/* ── 2. Nghe chép chính tả ───────────────────────────────────────────────── */

export const DICTATION_DURATION = 330;
const ANSWER = "rescheduled";

export function DictationBox() {
  const frame = useCurrentFrame();

  // Sóng âm chạy trước, rồi mới tới lượt gõ: nghe xong mới chép.
  const listening = frame < 110;
  const typed = Math.min(ANSWER.length, Math.max(0, Math.floor((frame - 120) / 5)));
  const done = typed === ANSWER.length;
  const settle = interpolate(frame, [230, 246], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div className="l-dark-box">
      <div className="l-dark-label">Nghe và gõ lại</div>
      <div className="l-listen">
        <span style={{ display: "inline-flex", alignItems: "flex-end", gap: 3, height: 20 }}>
          {Array.from({ length: 14 }).map((_, i) => {
            // Dáng sóng tất định theo chỉ số: ngẫu nhiên thật sẽ làm cùng một
            // cảnh trông khác nhau ở hai lần xem.
            const base = 5 + ((Math.sin(i * 1.7) + 1) / 2) * 13;
            const wob = listening ? (Math.sin(frame / 4 + i) + 1) / 2 : 0;
            return (
              <span
                key={i}
                style={{
                  width: 3,
                  borderRadius: 3,
                  height: base * (0.45 + wob * 0.55),
                  background: listening ? "var(--l-orange)" : "var(--l-line)",
                }}
              />
            );
          })}
        </span>
        {listening ? "Đang phát…" : "Nghe kỹ"}
      </div>
      <div className="l-line" />
      <div className="l-answer">
        The meeting has been{" "}
        <b
          style={{
            color: done ? "var(--l-green)" : undefined,
            borderBottom: done ? "none" : "1px solid currentColor",
          }}
        >
          {typed === 0 ? "   " : ANSWER.slice(0, typed)}
        </b>{" "}
        for Friday.
      </div>
      <div className="l-legend" style={{ opacity: done ? settle : 1 }}>
        {done
          ? "Đúng rồi — nghe lại lần nữa nếu muốn chắc."
          : "Bấm phát lại nếu bạn cần nghe thêm một lần."}
      </div>
    </div>
  );
}

/* ── 3. Câu Part 5 ───────────────────────────────────────────────────────── */

export const EXAM_DURATION = 360;
const OPTIONS = ["arrival", "arrived", "arriving", "arrive"];
const CORRECT = 0;

export function ExamQuestion() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Đồng hồ ĐẾM NGƯỢC, vì màn làm bài đếm ngược — đếm lên là tả sai sản phẩm.
  const left = Math.max(0, 37 - Math.floor(frame / fps));
  const picked = frame > 250;
  const graded = frame > 290;

  return (
    <div className="l-mock-inner">
      <div className="l-q-head">
        <span className="l-label">Part 5 · Câu chưa hoàn chỉnh</span>
        <b style={{ color: left <= 10 ? "var(--l-orange-dark)" : undefined }}>
          00:{String(left).padStart(2, "0")}
        </b>
      </div>
      <p className="l-question">Customers can monitor the estimated ______ of their shipments.</p>
      <div className="l-options">
        {OPTIONS.map((opt, i) => {
          const at = 40 + i * 22;
          const enter = spring({ frame: frame - at, fps, durationInFrames: 14 });
          const chosen = picked && i === CORRECT;
          return (
            <div
              key={opt}
              className="l-option"
              style={{
                opacity: enter,
                transform: `translateY(${(1 - enter) * 8}px)`,
                borderColor: chosen ? "var(--l-orange)" : "var(--l-line)",
                background: chosen ? "var(--l-orange-tint)" : undefined,
              }}
            >
              <b>{String.fromCharCode(65 + i)}.</b>
              <span>{opt}</span>
              {graded && chosen && (
                <span style={{ marginLeft: "auto", color: "var(--l-green)", fontWeight: 800 }}>
                  ✓
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
