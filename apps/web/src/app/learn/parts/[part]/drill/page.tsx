"use client";

import { ArrowRight, Check, Dumbbell, Play, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { Button, EmptyState, Page, PageHeader, Panel } from "@/components/ui";
import { cx } from "@/components/ui";
import { getPart, type PartMockQuestion } from "@/lib/parts";

/**
 * Drill một part — GIAO DIỆN DUY NHẤT, dữ liệu mock.
 *
 * Luồng thật (`GET /practice/parts/{part}` + ghi attempt + XP) chưa tồn tại;
 * phiên ở đây lặp câu mock `lib/parts.ts` ba lần để nhìn thấy đủ các trạng
 * thái: chọn → nộp → phản hồi → câu tiếp → tổng kết. Audio và passage cũng
 * mock (nút play không phát gì) — hình dạng chỗ của chúng mới là thứ cần duyệt.
 */

const SESSION_LEN = 3;

function buildSession(question: PartMockQuestion): PartMockQuestion[] {
  return Array.from({ length: SESSION_LEN }, () => question);
}

export default function PartDrillPage() {
  const info = getPart(String(useParams().part));
  const [session, setSession] = useState<PartMockQuestion[] | null>(
    info ? buildSession(info.drill[0]!) : null,
  );
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [results, setResults] = useState<boolean[]>([]);

  if (!info || !session) {
    return (
      <Page className="max-w-3xl">
        <EmptyState
          icon={Dumbbell}
          title="Không có phần này"
          description="Bài thi TOEIC có bảy phần, từ 1 đến 7."
        />
      </Page>
    );
  }

  const done = idx >= session.length;
  const correctCount = results.filter(Boolean).length;

  function restart() {
    setSession(buildSession(info!.drill[0]!));
    setIdx(0);
    setPicked(null);
    setRevealed(false);
    setResults([]);
  }

  function submit() {
    if (!picked) return;
    const q = session![idx]!;
    setResults((r) => [...r, picked === q.correct]);
    setRevealed(true);
  }

  function next() {
    setIdx((i) => i + 1);
    setPicked(null);
    setRevealed(false);
  }

  /* --- tổng kết phiên ------------------------------------------------------ */
  if (done) {
    const missed = session.filter((_, i) => !results[i]);
    const grammarHints = [
      ...new Map(missed.filter((q) => q.grammarSlug).map((q) => [q.grammarSlug!, q])).values(),
    ];
    return (
      <Page className="max-w-3xl">
        <Breadcrumbs
          trail={[
            { href: "/learn/parts", label: "Luyện theo phần" },
            { href: `/learn/parts/${info.part}`, label: `Part ${info.part}` },
          ]}
        />
        <PageHeader eyebrow={`Part ${info.part}`} title="Kết quả phiên luyện" />

        <Panel className="mt-6 p-6 text-center">
          <p className="font-data text-title font-semibold tabular-nums">
            {correctCount}/{session.length}
          </p>
          <p className="mt-1 text-small text-ink-muted">
            {correctCount === session.length
              ? "Chính xác tuyệt đối."
              : "Sai ở đây rẻ hơn sai trong phòng thi."}
          </p>
        </Panel>

        {grammarHints.length > 0 && (
          <div className="mt-6">
            <h2 className="text-subtitle font-semibold">Luyện thêm theo điểm yếu</h2>
            <div className="mt-3 space-y-2">
              {grammarHints.map((q) => (
                <Link
                  key={q.grammarSlug}
                  href="/learn/grammar"
                  className="flex items-center gap-3 rounded border border-rule-strong p-3 hover:bg-recess"
                >
                  <span className="min-w-0 flex-1">
                    <span className="font-semibold">Chủ đề {q.grammarTitle}</span>
                    <span className="block text-small text-ink-muted">
                      Bạn sai câu kiểm điểm ngữ pháp này
                    </span>
                  </span>
                  <ArrowRight size={15} strokeWidth={2} className="text-ink-faint" aria-hidden />
                </Link>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8 flex flex-wrap gap-3 border-t border-rule pt-5">
          <Button onClick={restart}>
            <RotateCcw size={13} strokeWidth={2} aria-hidden />
            Làm lại
          </Button>
          <Link
            href={`/learn/parts/${info.part}`}
            className="inline-flex items-center rounded border border-rule-strong px-4 py-2 text-small font-semibold hover:bg-recess"
          >
            Xem lại chiến thuật
          </Link>
        </div>
      </Page>
    );
  }

  /* --- một câu -------------------------------------------------------------- */
  const q = session[idx]!;
  return (
    <Page className="max-w-3xl">
      <Breadcrumbs
        trail={[
          { href: "/learn/parts", label: "Luyện theo phần" },
          { href: `/learn/parts/${info.part}`, label: `Part ${info.part}` },
        ]}
      />

      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-subtitle font-semibold">
          Part {info.part} · Câu {idx + 1}/{session.length}
        </h1>
        <span className="font-data text-small tabular-nums text-ink-muted">
          đúng {correctCount}
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={idx + (revealed ? 1 : 0)}
        aria-valuemin={0}
        aria-valuemax={session.length}
        aria-label="Tiến độ phiên"
        className="mt-2 h-1.5 w-full overflow-hidden rounded bg-recess"
      >
        <div
          className="block h-full bg-action transition-all"
          style={{ width: `${((idx + (revealed ? 1 : 0)) / session.length) * 100}%` }}
        />
      </div>

      <Panel className="mt-5 p-5">
        {q.audio && (
          <button
            type="button"
            className="mb-4 inline-flex items-center gap-2 rounded border border-rule-strong px-3 py-2 text-small font-semibold hover:bg-recess"
            aria-label="Nghe đoạn ghi âm (mock — chưa có audio)"
          >
            <Play size={14} strokeWidth={2} aria-hidden />
            Nghe đoạn ghi âm
          </button>
        )}
        {q.passage && (
          <div className="mb-4 rounded bg-recess p-4 text-small leading-relaxed whitespace-pre-line">
            {q.passage}
          </div>
        )}

        <p className="text-lesson font-medium">{q.prompt}</p>

        <div className="mt-4 space-y-2" role="radiogroup" aria-label="Các lựa chọn">
          {q.options.map((o) => {
            const isCorrect = o.label === `(${q.correct})`;
            const isPicked = picked === o.label;
            const state = !revealed
              ? picked === o.label
                ? "border-action bg-action/5"
                : "border-rule-strong hover:bg-recess"
              : isCorrect
                ? "border-ok bg-ok-tint"
                : isPicked
                  ? "border-alert bg-alert-tint"
                  : "border-rule-strong opacity-60";
            return (
              <button
                key={o.label}
                type="button"
                role="radio"
                aria-checked={picked === o.label}
                disabled={revealed}
                onClick={() => setPicked(o.label)}
                className={cx(
                  "flex w-full items-center gap-3 rounded border p-3 text-left transition-colors",
                  state,
                )}
              >
                <span className="font-data text-small font-semibold text-ink-muted">{o.label}</span>
                <span className="min-w-0 flex-1">{o.content}</span>
                {revealed && isCorrect && (
                  <Check size={15} strokeWidth={2.25} className="shrink-0 text-ok" aria-hidden />
                )}
                {revealed && isPicked && !isCorrect && (
                  <X size={15} strokeWidth={2.25} className="shrink-0 text-alert" aria-hidden />
                )}
              </button>
            );
          })}
        </div>
      </Panel>

      {revealed && (
        <Panel className="mt-4 p-4">
          <p
            className={cx(
              "text-small font-semibold",
              results[results.length - 1] ? "text-ok" : "text-alert",
            )}
          >
            {results[results.length - 1] ? "Chính xác." : `Đáp án đúng là (${q.correct}).`}
          </p>
          <p className="mt-1 text-small leading-relaxed text-ink-muted">{q.explanation}</p>
          {!results[results.length - 1] && q.grammarSlug && (
            <Link
              href="/learn/grammar"
              className="mt-2 inline-flex items-center gap-1 text-small font-semibold text-action hover:underline"
            >
              Ôn chủ đề {q.grammarTitle}
              <ArrowRight size={12} strokeWidth={2} aria-hidden />
            </Link>
          )}
        </Panel>
      )}

      <div className="mt-5 flex justify-end gap-3">
        {!revealed ? (
          <Button disabled={!picked} onClick={submit}>
            Nộp
          </Button>
        ) : (
          <Button onClick={next}>
            {idx + 1 === session.length ? "Xem kết quả" : "Câu tiếp theo"}
            <ArrowRight size={13} strokeWidth={2} className="ml-1.5" aria-hidden />
          </Button>
        )}
      </div>
    </Page>
  );
}
