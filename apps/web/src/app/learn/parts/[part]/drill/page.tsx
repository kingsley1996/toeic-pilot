"use client";

import { ArrowRight, Check, Dumbbell, Play, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { Button, EmptyState, Page, PageHeader, Panel, SkeletonList, cx } from "@/components/ui";
import { getPart, labelTitle, type PartMockQuestion } from "@/lib/parts";

/**
 * Drill một part — GIAO DIỆN DUY NHẤT, dữ liệu mock.
 *
 * Luồng thật (`GET /practice/parts/{part}` + ghi attempt + XP) chưa tồn tại.
 * Phiên ở đây lặp câu mock ba lần để nhìn đủ trạng thái: chọn → nộp → phản hồi
 * → câu tiếp → tổng kết. `?label=CODE` (nhãn taxonomy thật của câu) lọc nội dung
 * và đổi tiêu đề phiên — drill thật sẽ nhận đúng tham số đó từ API.
 */

const SESSION_LEN = 3;

function buildSession(questions: PartMockQuestion[]): PartMockQuestion[] {
  if (questions.length === 0) return [];
  return Array.from({ length: SESSION_LEN }, (_, i) => questions[i % questions.length]!);
}

function Drill({ partCode, label }: { partCode: string; label: string | null }) {
  const info = getPart(partCode);
  const labelInfo = info && label ? labelTitle(info, label) : undefined;
  const pool = info ? (label ? info.drill.filter((q) => q.label === label) : info.drill) : [];
  const [session, setSession] = useState<PartMockQuestion[]>(() => buildSession(pool));
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [results, setResults] = useState<boolean[]>([]);

  if (!info) {
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

  if (session.length === 0) {
    return (
      <Page className="max-w-3xl">
        <Breadcrumbs
          trail={[
            { href: "/learn/parts", label: "Luyện theo phần" },
            { href: `/learn/parts/${info.part}`, label: `Part ${info.part}` },
          ]}
        />
        <EmptyState
          icon={Dumbbell}
          title="Bản mock chưa có câu cho nhãn này"
          description="Khi API thật chạy, mọi nhãn của phần này đều có câu — số liệu nhãn trên trang chiến thuật đo từ kho thật."
        />
        <div className="mt-4 text-center">
          <Link
            href={`/learn/parts/${info.part}/drill`}
            className="text-small font-semibold text-action hover:underline"
          >
            Luyện toàn bộ Part {info.part}
          </Link>
        </div>
      </Page>
    );
  }

  const done = idx >= session.length;
  const correctCount = results.filter(Boolean).length;

  function restart() {
    setSession(buildSession(pool));
    setIdx(0);
    setPicked(null);
    setRevealed(false);
    setResults([]);
  }

  function submit() {
    if (!picked) return;
    const q = session[idx]!;
    setResults((r) => [...r, picked === q.correct]);
    setRevealed(true);
  }

  function next() {
    setIdx((i) => i + 1);
    setPicked(null);
    setRevealed(false);
  }

  const crumbs = [
    { href: "/learn/parts", label: "Luyện theo phần" },
    { href: `/learn/parts/${info.part}`, label: `Part ${info.part}` },
  ];

  /* --- tổng kết phiên ------------------------------------------------------ */
  if (done) {
    // Gom câu sai theo nhãn — cùng đơn vị phân loại với trang chiến thuật.
    const missedCodes = [...new Set(session.filter((_, i) => !results[i]).map((q) => q.label))];
    return (
      <Page className="max-w-3xl">
        <Breadcrumbs trail={crumbs} />
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

        {missedCodes.length > 0 && (
          <div className="mt-6">
            <h2 className="text-subtitle font-semibold">Điểm yếu theo nhãn</h2>
            <div className="mt-3 space-y-2">
              {missedCodes.map((code) => {
                const l = labelTitle(info, code);
                return (
                  <div
                    key={code}
                    className="flex items-center gap-3 rounded border border-rule-strong p-3"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="font-semibold">{l?.title ?? code}</span>
                      <span className="block text-small text-ink-muted">
                        {l ? `${l.count} câu trong kho · Part ${info.part}` : code}
                      </span>
                    </span>
                    {l?.grammarSlug ? (
                      <Link
                        href="/learn/grammar"
                        className="inline-flex items-center gap-1 text-small font-semibold text-action hover:underline"
                      >
                        Ôn Ngữ pháp
                        <ArrowRight size={12} strokeWidth={2} aria-hidden />
                      </Link>
                    ) : (
                      <Link
                        href={`/learn/parts/${info.part}/drill?label=${code}`}
                        className="inline-flex items-center gap-1 text-small font-semibold text-action hover:underline"
                      >
                        Luyện riêng nhãn này
                        <ArrowRight size={12} strokeWidth={2} aria-hidden />
                      </Link>
                    )}
                  </div>
                );
              })}
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
  const qLabel = labelTitle(info, q.label);
  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={crumbs} />

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
        <div className="mb-3 flex items-center gap-2">
          <span className="rounded bg-recess px-2 py-0.5 font-data text-small text-ink-muted">
            {qLabel?.title ?? q.label}
          </span>
          {labelInfo && <span className="text-small text-ink-faint">· đang lọc theo nhãn</span>}
        </div>
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
          {!results[results.length - 1] && qLabel?.grammarSlug && (
            <Link
              href="/learn/grammar"
              className="mt-2 inline-flex items-center gap-1 text-small font-semibold text-action hover:underline"
            >
              Ôn chủ đề {qLabel.title}
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

export default function PartDrillPage() {
  const part = String(useParams().part);
  const label = useSearchParams().get("label");
  return (
    // useSearchParams đẩy route khỏi render tĩnh nếu không có Suspense boundary
    // — cùng khuôn với `learn/vocabulary/[slug]`.
    <Suspense fallback={<SkeletonList rows={4} />}>
      <Drill partCode={part} label={label} />
    </Suspense>
  );
}
