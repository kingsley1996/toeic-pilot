"use client";

import {
  API_ROUTES,
  type GrammarTopicPublic,
  type PartAnswerResult,
  type PartDrillQuestion,
  type PartLabelCount,
  type PartSessionDetail,
} from "@toeic-pilot/shared";
import { ArrowLeft, ArrowRight, Check, Clock, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { MarkdownLite } from "@/components/markdown-lite";
import { Modal } from "@/components/modal";
import { Button, Page, PageHeader, Panel, SkeletonList, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { clock } from "@/lib/attempt";
import { useSession } from "@/lib/session";
import { getPartMeta } from "@/lib/parts";

/**
 * Một phiên luyện theo part — làm, chấm tức thì, và XEM LẠI được.
 *
 * Ba chế độ trên cùng một đường dẫn (như `/learn/attempts/[id]` của khu đề thi):
 * đang làm → câu đầu chưa trả lời; tổng kết → phiên đã finished và chưa bấm
 * "xem lại"; xem lại → liệt kê hết, câu nào cũng đã lộ đáp án.
 *
 * Server là nơi chốt đúng/sai và lộ đáp án theo từng câu — client chỉ hiển thị
 * những gì nó trả về.
 */

type LocalAnswer = { pickedOptionId: string; result: PartAnswerResult };

export default function PartSessionPage() {
  const id = String(useParams().id);
  const { token } = useSession();
  const [sess, setSess] = useState<PartSessionDetail | null>(null);
  const [topics, setTopics] = useState<GrammarTopicPublic[]>([]);
  const [answers, setAnswers] = useState<Record<string, LocalAnswer>>({});
  const [viewIdx, setViewIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(
    () => apiFetch<PartSessionDetail>(API_ROUTES.partSession(id), { token: token ?? undefined }),
    [id, token],
  );

  useEffect(() => {
    // Danh sách công khai — chỉ để map slug → id cho deep-link "Ôn Ngữ pháp".
    apiFetch<GrammarTopicPublic[]>(API_ROUTES.grammarTopics)
      .then(setTopics)
      .catch(() => {});
    if (!token) return;
    load()
      .then((s) => {
        setSess(s);
        setRemaining(s.remaining_seconds);
        // Phiên đã trả lời một phần (mở lại từ lịch sử): tái dựng phản hồi từ
        // chính payload — server đã lộ theo từng câu được trả lời.
        const seeded: Record<string, LocalAnswer> = {};
        for (const item of s.items) {
          if (item.is_correct !== null && item.selected_option_id && item.correct_option_id) {
            const spoken: Record<string, string> = {};
            for (const o of item.question.options) {
              if (o.spoken_text) spoken[o.id] = o.spoken_text;
            }
            seeded[item.question.id] = {
              pickedOptionId: item.selected_option_id,
              result: {
                is_correct: item.is_correct,
                correct_option_id: item.correct_option_id,
                explanation: item.explanation ?? null,
                labels: item.question.labels,
                spoken,
                transcript: item.question.transcript,
              },
            };
          }
        }
        setAnswers(seeded);
        const firstOpen = s.items.findIndex((i) => !seeded[i.question.id]);
        setViewIdx(firstOpen === -1 ? 0 : firstOpen);
      })
      .catch(() => setError("Không tải được phiên này."));
  }, [load, token]);

  const meta = useMemo(() => getPartMeta(sess?.part), [sess]);
  const current = sess?.items[viewIdx];
  const finished =
    Boolean(sess?.finished_at) || (sess ? sess.items.every((i) => answers[i.question.id]) : false);

  /*
   * Đếm lùi — `remaining_seconds` của máy chủ là nguồn sự thật, ở đây chỉ vẽ
   * và trôi. Chạm 0 thì nạp lại: server chốt phiên `expired` ngay lần đọc đó
   * và màn tổng kết hiện ra. Không có nút nộp riêng — đồng hồ và câu cuối
   * cùng về một chỗ.
   */
  useEffect(() => {
    if (remaining === null || finished) return;
    if (remaining <= 0) {
      // `setTimeout(…, 0)`: setState đồng bộ trong thân effect là thứ
      // `react-hooks/set-state-in-effect` cấm.
      const now = window.setTimeout(() => void load().then(setSess), 0);
      return () => window.clearTimeout(now);
    }
    const timer = window.setTimeout(() => setRemaining((v) => (v ?? 1) - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [remaining, finished, load]);

  async function answer(question: PartDrillQuestion, optionId: string) {
    if (!sess || !token || answers[question.id] || busy) return;
    setBusy(true);
    try {
      const result = await apiFetch<PartAnswerResult>(API_ROUTES.partSessionAnswer(sess.id), {
        method: "POST",
        token,
        body: JSON.stringify({ question_id: question.id, option_id: optionId }),
      });
      setAnswers((a) => ({ ...a, [question.id]: { pickedOptionId: optionId, result } }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không nộp được câu này.");
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    if (!sess || !token) return;
    const s = await apiFetch<PartSessionDetail>(API_ROUTES.partSessionFinish(sess.id), {
      method: "POST",
      token,
    });
    setSess(s);
    setConfirming(false);
  }

  if (error && !sess) {
    return (
      <Page className="max-w-3xl">
        <p className="text-small text-alert">{error}</p>
      </Page>
    );
  }
  if (!sess || !meta) {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  const crumbs = [
    { href: "/learn/parts", label: "Luyện theo phần" },
    { href: `/learn/parts/${meta.part}`, label: `Part ${meta.part}` },
  ];
  const answeredList = Object.values(answers);
  const correctCount = answeredList.filter((a) => a.result.is_correct).length;
  const passageBySet = new Map<string, PartDrillQuestion["passages"]>();
  for (const item of sess.items) {
    if (item.question.set_id && item.question.passages.length > 0) {
      passageBySet.set(item.question.set_id, item.question.passages);
    }
  }

  /* --- tổng kết ------------------------------------------------------------- */
  if (finished && !reviewing) {
    const missedLabels: PartLabelCount[] = [];
    for (const a of answeredList) {
      if (a.result.is_correct) continue;
      for (const l of a.result.labels) {
        if (!missedLabels.some((m) => m.code === l.code)) missedLabels.push(l);
      }
    }
    return (
      <Page className="max-w-3xl">
        <Breadcrumbs trail={crumbs} />
        <PageHeader eyebrow={`Part ${meta.part}`} title="Kết quả phiên luyện" />
        <Panel className="mt-6 p-6 text-center">
          <p className="font-data text-title font-semibold tabular-nums">
            {correctCount}/{sess.items.length}
          </p>
          <p className="mt-1 text-small text-ink-muted">
            {sess.expired
              ? "Hết giờ — phiên tự nộp."
              : correctCount === sess.items.length
                ? "Chính xác tuyệt đối."
                : "Sai ở đây rẻ hơn sai trong phòng thi."}
          </p>
        </Panel>

        {missedLabels.length > 0 && (
          <div className="mt-6">
            <h2 className="text-subtitle font-semibold">Điểm yếu theo nhãn</h2>
            <div className="mt-3 space-y-2">
              {missedLabels.map((l) => {
                const topicId = topics.find((t) => t.slug === l.grammar_topic_slug)?.id;
                return (
                  <div
                    key={l.code}
                    className="flex items-center gap-3 rounded border border-rule-strong p-3"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="font-semibold">{l.title}</span>
                      <span className="block text-small text-ink-muted">Part {meta.part}</span>
                    </span>
                    {topicId ? (
                      <Link
                        href={`/learn/grammar/${topicId}`}
                        className="inline-flex items-center gap-1 text-small font-semibold text-action hover:underline"
                      >
                        Ôn Ngữ pháp
                        <ArrowRight size={12} strokeWidth={2} aria-hidden />
                      </Link>
                    ) : (
                      <Link
                        href={`/learn/parts/${meta.part}/drill`}
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
          <Button onClick={() => setReviewing(true)}>Xem lại từng câu</Button>
          <Link
            href={`/learn/parts/${meta.part}/drill`}
            className="inline-flex items-center rounded border border-rule-strong px-4 py-2 text-small font-semibold hover:bg-recess"
          >
            Luyện tiếp phiên mới
          </Link>
          <Link
            href="/learn/parts/sessions"
            className="inline-flex items-center rounded px-4 py-2 text-small font-semibold text-ink-muted hover:text-ink"
          >
            Lịch sử phiên
          </Link>
        </div>
      </Page>
    );
  }

  /* --- xem lại toàn bộ ------------------------------------------------------ */
  if (reviewing) {
    return (
      <Page className="max-w-3xl">
        <Breadcrumbs trail={crumbs} />
        <PageHeader
          eyebrow={`Part ${meta.part}`}
          title="Xem lại phiên"
          description={`${correctCount}/${sess.items.length} câu đúng · ${sess.label_titles.join(", ") || "Tất cả"}`}
        />
        <div className="mt-6 space-y-6">
          {sess.items.map((item) => (
            <QuestionCard
              key={item.question.id}
              n={item.position}
              question={item.question}
              passages={
                item.question.set_id
                  ? (passageBySet.get(item.question.set_id) ?? [])
                  : item.question.passages
              }
              answer={answers[item.question.id]}
              disabled
            />
          ))}
        </div>
        <div className="mt-8 flex gap-3 border-t border-rule pt-5">
          <Button variant="quiet" onClick={() => setReviewing(false)}>
            <ArrowLeft size={13} strokeWidth={2} className="mr-1.5" aria-hidden />
            Về tổng kết
          </Button>
        </div>
      </Page>
    );
  }

  /* --- đang làm ------------------------------------------------------------- */
  if (!current) {
    // Phiên rỗng không thể tồn tại (server chặn), nhưng nếu items đã hết mà
    // chưa finished thì chốt luôn, đừng để người học đứng ở trang trắng.
    void finish();
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={2} />
      </Page>
    );
  }
  const idx = viewIdx;
  const answeredCurrent = answers[current.question.id];
  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={crumbs} />
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-subtitle font-semibold">
          Part {meta.part} · Câu {idx + 1}/{sess.items.length}
        </h1>
        <div className="flex items-center gap-3">
          <span className="font-data text-small tabular-nums text-ink-muted">
            đúng {correctCount}
          </span>
          {remaining !== null && (
            <span
              className={cx(
                "inline-flex items-center gap-1.5 rounded border px-2.5 py-1 font-data text-small tabular-nums",
                remaining <= 300 ? "border-alert text-alert" : "border-rule-strong text-ink",
              )}
              aria-live={remaining <= 300 ? "polite" : "off"}
            >
              <Clock size={14} strokeWidth={2} aria-hidden />
              {clock(remaining)}
            </span>
          )}
          <Button variant="secondary" size="sm" onClick={() => setConfirming(true)}>
            Nộp bài
          </Button>
        </div>
      </div>
      <div
        role="progressbar"
        aria-valuenow={answeredCurrent ? idx + 1 : idx}
        aria-valuemin={0}
        aria-valuemax={sess.items.length}
        aria-label="Tiến độ phiên"
        className="mt-2 h-1.5 w-full overflow-hidden rounded bg-recess"
      >
        <div
          className="block h-full bg-action transition-all"
          style={{ width: `${((answeredCurrent ? idx + 1 : idx) / sess.items.length) * 100}%` }}
        />
      </div>

      <QuestionCard
        n={idx + 1}
        question={current.question}
        passages={
          current.question.set_id
            ? (passageBySet.get(current.question.set_id) ?? [])
            : current.question.passages
        }
        answer={answeredCurrent}
        busy={busy}
        onPick={(optionId) => void answer(current.question, optionId)}
      />

      {answeredCurrent && (
        <div className="mt-5 flex justify-end">
          <Button
            onClick={() => {
              if (idx + 1 >= sess.items.length) void finish();
              else setViewIdx(idx + 1);
            }}
          >
            {idx + 1 === sess.items.length ? "Xem kết quả" : "Câu tiếp theo"}
            <ArrowRight size={13} strokeWidth={2} className="ml-1.5" aria-hidden />
          </Button>
        </div>
      )}

      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Nộp bài?"
        description="Nộp rồi thì không quay lại làm tiếp được. Câu bỏ trống không được tính."
      >
        <p className="mb-4 text-small">
          Đã trả lời{" "}
          <span className="font-data tabular-nums text-ink">
            {answeredList.length}/{sess.items.length}
          </span>{" "}
          {remaining !== null && (
            <>
              {" "}
              · còn <span className="font-data tabular-nums text-ink">{clock(remaining)}</span>
            </>
          )}
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirming(false)}>
            Quay lại làm tiếp
          </Button>
          <Button onClick={() => void finish()}>Nộp bài</Button>
        </div>
      </Modal>
    </Page>
  );
}

function QuestionCard({
  n,
  question,
  passages,
  answer,
  onPick,
  busy,
  disabled,
}: {
  n: number;
  question: PartDrillQuestion;
  passages: PartDrillQuestion["passages"];
  answer?: LocalAnswer;
  onPick?: (optionId: string) => void;
  busy?: boolean;
  disabled?: boolean;
}) {
  const revealed = Boolean(answer);
  return (
    <Panel className="mt-4 p-5">
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <span className="font-data text-small text-ink-faint">Câu {n}</span>
        {question.labels.map((l) => (
          <span
            key={l.code}
            className="rounded bg-recess px-2 py-0.5 font-data text-small text-ink-muted"
          >
            {l.title}
          </span>
        ))}
      </div>
      {question.audio_url && (
        <audio controls src={question.audio_url} className="mb-4 w-full" preload="metadata">
          <track kind="captions" />
        </audio>
      )}
      {question.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={question.image_url}
          alt=""
          className="mb-4 max-h-64 rounded border border-rule object-contain"
        />
      )}
      {passages.length > 0 && (
        <div className="mb-4 max-h-72 space-y-3 overflow-y-auto rounded bg-recess p-4 text-small leading-relaxed">
          {passages.map((p, i) => (
            <div key={i}>
              {p.text && (
                <div className="whitespace-pre-line">
                  <MarkdownLite text={p.text} />
                </div>
              )}
              {p.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={p.image_url} alt={p.image_alt ?? ""} className="mt-2 max-h-56 rounded" />
              )}
            </div>
          ))}
        </div>
      )}

      {question.prompt_text && <p className="text-lesson font-medium">{question.prompt_text}</p>}

      <div className="mt-4 space-y-2" role="radiogroup" aria-label="Các lựa chọn">
        {question.options.map((o) => {
          const isCorrect = o.id === answer?.result.correct_option_id;
          const isPicked = answer?.pickedOptionId === o.id;
          // Part 1/2 không in chữ nào lúc làm — lời đọc về sau theo đúng luật
          // lộ của `attempt.py`: chỉ khi câu đã được trả lời.
          const text = o.content ?? (revealed ? answer?.result.spoken[o.id] : null);
          const state = !revealed
            ? "border-rule-strong hover:bg-recess"
            : isCorrect
              ? "border-ok bg-ok-tint"
              : isPicked
                ? "border-alert bg-alert-tint"
                : "border-rule-strong opacity-60";
          return (
            <button
              key={o.id}
              type="button"
              role="radio"
              aria-checked={isPicked}
              disabled={revealed || busy || disabled}
              onClick={() => onPick?.(o.id)}
              className={cx(
                "flex w-full items-center gap-3 rounded border p-3 text-left transition-colors",
                state,
              )}
            >
              <span className="font-data text-small font-semibold text-ink-muted">{o.label}</span>
              <span className="min-w-0 flex-1">{text}</span>
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

      {revealed && question.transcript.length + (answer?.result.transcript.length ?? 0) > 0 && (
        <div className="mt-4 rounded border border-rule bg-recess p-4">
          <p className="text-label font-semibold uppercase text-ink-faint">Lời thoại</p>
          <div className="mt-2 space-y-1.5 text-small">
            {(answer?.result.transcript.length
              ? answer.result.transcript
              : question.transcript
            ).map((t, i) => (
              <p key={i}>
                <span className="font-data font-semibold text-ink-muted">{t.speaker}: </span>
                {t.text}
              </p>
            ))}
          </div>
        </div>
      )}

      {answer && (
        <p
          className={cx(
            "mt-3 text-small font-semibold",
            answer.result.is_correct ? "text-ok" : "text-alert",
          )}
        >
          {answer.result.is_correct ? "Chính xác." : "Chưa đúng."}
        </p>
      )}
      {answer?.result.explanation && (
        <p className="mt-1 text-small leading-relaxed text-ink-muted">
          {answer.result.explanation}
        </p>
      )}
    </Panel>
  );
}
