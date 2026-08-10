"use client";

import {
  API_ROUTES,
  type AttemptResult,
  type AttemptState,
  type QuestionPublic,
} from "@toeic-pilot/shared";
import { BookOpen, Clock, Flag, Headphones, LogOut, Send } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Modal } from "@/components/modal";
import { Alert, Button, EmptyState, Page, Skeleton, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { type Block, clock, groupQuestions } from "@/lib/attempt";
import { useRequireSession } from "@/lib/session";

/*
 * Màn làm bài.
 *
 * Ba điều định hình toàn bộ file này:
 *
 * 1. **Đồng hồ do máy chủ tính.** `remaining_seconds` là nguồn sự thật; ở đây
 *    chỉ đếm lùi cho mượt. Đồng hồ máy khách chỉnh được, nên một bài thi tin
 *    vào `Date.now()` là một bài thi không có giới hạn thời gian.
 * 2. **Mỗi lần chọn đáp án là một lần lưu.** Không có nút "Lưu". Người làm bài
 *    đóng tab giữa chừng rồi mở lại phải thấy nguyên trạng — và vì máy chủ đã
 *    ghi từng câu, việc đó là mặc định chứ không phải tính năng.
 * 3. **Đáp án đúng không tồn tại ở đây khi đang thi.** `correct_option_id` chỉ
 *    có ở chế độ Luyện tập hoặc sau khi nộp. Không rẽ nhánh theo `review_mode`
 *    để quyết định *hiển thị* — cứ hiện thứ máy chủ gửi; nếu nó không gửi thì
 *    không có gì để lộ.
 */

export default function AttemptRunnerPage() {
  const params = useParams<{ attemptId: string }>();
  const attemptId = params.attemptId;
  const router = useRouter();
  const { status, token } = useRequireSession();

  const [state, setState] = useState<AttemptState | null>(null);
  const [failed, setFailed] = useState(false);
  const [activePart, setActivePart] = useState<number | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Cuộn tới một câu ở part khác cần đổi tab trước rồi mới cuộn được. Giữ ở ref
  // chứ không ở state: ghi state trong effect là đúng thứ `react-hooks/
  // set-state-in-effect` cấm, và ở đây không cần render lại vì đích đến.
  const pendingScroll = useRef<number | null>(null);

  const fetchState = useCallback(
    () => apiFetch<AttemptState>(API_ROUTES.attempt(attemptId), { token: token ?? undefined }),
    [attemptId, token],
  );

  const applyState = useCallback((data: AttemptState) => {
    setState(data);
    setRemaining(data.remaining_seconds);
    // `?? current` chứ không gán đè: nạp lại sau khi nộp bài không được kéo
    // người dùng về Part 1 khi họ đang xem Part 7.
    setActivePart((current) => current ?? data.parts[0]?.part ?? null);
  }, []);

  // Dạng `.then()` chứ không `await` trong thân effect: quy tắc
  // `react-hooks/set-state-in-effect` chặn mọi lời gọi setState đồng bộ ở đó,
  // và cả repo đã dùng đúng dạng này (xem `learn/tests/page.tsx`).
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchState()
      .then((data) => {
        if (!cancelled) applyState(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [applyState, fetchState, token]);

  const submit = useCallback(async () => {
    if (!token || submitting) return;
    setSubmitting(true);
    try {
      const outcome = await apiFetch<AttemptResult>(API_ROUTES.attemptSubmit(attemptId), {
        method: "POST",
        token,
      });
      setResult(outcome);
      // Nạp lại vì bài đã nộp: giờ máy chủ mới gửi kèm đáp án đúng.
      applyState(await fetchState());
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      setError("Không nộp được bài. Kiểm tra kết nối rồi thử lại.");
    } finally {
      setSubmitting(false);
      setConfirming(false);
    }
  }, [applyState, attemptId, fetchState, submitting, token]);

  // Đếm lùi. Chạm 0 thì tự nộp — máy chủ cũng sẽ chốt bài ở request kế tiếp,
  // nhưng để người dùng ngồi trước một đồng hồ 00:00 mà không có gì xảy ra là
  // để họ tự hỏi mình có mất bài không.
  useEffect(() => {
    if (remaining === null || result !== null) return;
    if (remaining <= 0) {
      // `setTimeout(…, 0)` chứ không gọi thẳng: `submit` đặt state ngay lập
      // tức, và đặt state đồng bộ trong thân effect là thứ
      // `react-hooks/set-state-in-effect` cấm — nó gây render dây chuyền.
      const now = window.setTimeout(() => void submit(), 0);
      return () => window.clearTimeout(now);
    }
    const timer = window.setTimeout(() => setRemaining((value) => (value ?? 1) - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [remaining, result, submit]);

  useEffect(() => {
    const target = pendingScroll.current;
    if (target === null) return;
    pendingScroll.current = null;
    document.getElementById(`q-${target}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activePart]);

  const answered = state?.questions.filter((q) => q.selected_option_id).length ?? 0;
  const done = result !== null || state?.status === "submitted" || state?.status === "expired";

  const visible = useMemo(
    () => (state ? state.questions.filter((q) => q.part === activePart) : []),
    [state, activePart],
  );
  const blocks = useMemo(() => groupQuestions(visible), [visible]);

  async function choose(question: QuestionPublic, optionId: string) {
    if (!token || done) return;
    const next = question.selected_option_id === optionId ? null : optionId;
    patch(question.id, { selected_option_id: next });
    try {
      await apiFetch(API_ROUTES.attemptAnswer(attemptId, question.id), {
        method: "PATCH",
        token,
        body: JSON.stringify({ selected_option_id: next }),
      });
    } catch {
      // Trả lại giá trị cũ: một ô tick sai sự thật tệ hơn một thông báo lỗi,
      // vì nó khiến người làm bài tin rằng câu đó đã được ghi nhận.
      patch(question.id, { selected_option_id: question.selected_option_id });
      setError("Không lưu được đáp án. Kiểm tra kết nối.");
    }
  }

  async function toggleFlag(question: QuestionPublic) {
    if (!token || done) return;
    patch(question.id, { flagged: !question.flagged });
    try {
      await apiFetch(API_ROUTES.attemptAnswer(attemptId, question.id), {
        method: "PATCH",
        token,
        body: JSON.stringify({ flagged: !question.flagged }),
      });
    } catch {
      patch(question.id, { flagged: question.flagged });
    }
  }

  function patch(questionId: string, change: Partial<QuestionPublic>) {
    setState((current) =>
      current === null
        ? current
        : {
            ...current,
            questions: current.questions.map((q) =>
              q.id === questionId ? { ...q, ...change } : q,
            ),
          },
    );
  }

  function jumpTo(question: QuestionPublic) {
    if (question.part === activePart) {
      document
        .getElementById(`q-${question.number}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    pendingScroll.current = question.number;
    setActivePart(question.part);
  }

  if (status === "loading" || (state === null && !failed)) {
    return (
      <Page>
        <Skeleton className="h-10 w-64" />
        <Skeleton className="mt-6 h-96 w-full" />
      </Page>
    );
  }

  if (failed || state === null) {
    return (
      <Page>
        <EmptyState
          icon={BookOpen}
          title="Không mở được lượt làm này"
          description="Có thể nó thuộc về tài khoản khác, hoặc đường dẫn bị gõ sai."
          action={<Button onClick={() => router.push("/learn/tests")}>Về danh sách đề</Button>}
        />
      </Page>
    );
  }

  return (
    <div className="min-h-dvh bg-ground">
      {/* Thanh trên cùng dính. Bóng ở đây là một trong ba ngoại lệ của §6.3:
          nó nói rằng có nội dung đang trôi bên dưới. */}
      <header className="sticky top-0 z-30 border-b border-rule-strong bg-panel shadow-[0_1px_3px_rgb(0_0_0/0.08)]">
        <div className="flex items-center gap-4 px-4 py-2.5">
          <p className="min-w-0 flex-1 truncate font-semibold">{state.test_title}</p>

          <Countdown seconds={remaining} done={done} />

          <div className="flex shrink-0 items-center gap-2">
            {!done && (
              <Button size="sm" onClick={() => setConfirming(true)} disabled={submitting}>
                <Send size={14} strokeWidth={2} aria-hidden />
                Nộp bài
              </Button>
            )}
            <Button size="sm" variant="secondary" onClick={() => router.push(`/learn/tests`)}>
              <LogOut size={14} strokeWidth={2} aria-hidden />
              Thoát
            </Button>
          </div>
        </div>

        <PartTabs state={state} active={activePart} onSelect={(part) => setActivePart(part)} />
      </header>

      {error && (
        <div className="px-4 pt-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      {result && <ResultBanner result={result} />}

      <div className="mx-auto flex w-full max-w-[110rem] gap-6 px-4 py-6">
        <main className="min-w-0 flex-1 space-y-8">
          {blocks.length === 0 ? (
            <p className="text-ink-muted">Phần này không có câu nào trong lượt làm của bạn.</p>
          ) : (
            blocks.map((block) => (
              <StimulusBlock
                key={block.key}
                block={block}
                done={done}
                onChoose={choose}
                onFlag={toggleFlag}
              />
            ))
          )}
        </main>

        <QuestionGrid state={state} answered={answered} activePart={activePart} onJump={jumpTo} />
      </div>

      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Nộp bài?"
        description={
          answered < state.question_count
            ? `Bạn còn ${state.question_count - answered} câu chưa trả lời. Câu bỏ trống được tính là sai.`
            : "Bạn đã trả lời hết các câu."
        }
      >
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirming(false)}>
            Quay lại làm tiếp
          </Button>
          <Button onClick={() => void submit()} disabled={submitting}>
            {submitting ? "Đang nộp…" : "Nộp bài"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

function Countdown({ seconds, done }: { seconds: number | null; done: boolean }) {
  if (done) {
    return <span className="shrink-0 text-small font-semibold text-ok">Đã nộp</span>;
  }
  if (seconds === null) {
    return <span className="shrink-0 text-small text-ink-muted">Không giới hạn giờ</span>;
  }
  // Dưới năm phút thì đổi màu. Không nhấp nháy: một thứ nhấp nháy trong tầm mắt
  // suốt năm phút cuối là thứ lấy đi sự tập trung đúng lúc cần nhất.
  const low = seconds <= 300;
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1.5 rounded border px-2.5 py-1 font-data tabular-nums",
        low ? "border-alert text-alert" : "border-rule-strong text-ink",
      )}
      aria-live={low ? "polite" : "off"}
    >
      <Clock size={14} strokeWidth={2} aria-hidden />
      {clock(seconds)}
    </span>
  );
}

function PartTabs({
  state,
  active,
  onSelect,
}: {
  state: AttemptState;
  active: number | null;
  onSelect: (part: number) => void;
}) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto border-t border-rule px-4 py-1.5">
      {state.parts.map((part, index) => {
        const previous = state.parts[index - 1];
        const boundary = index === 0 || previous.section !== part.section;
        // Đếm tại chỗ chứ KHÔNG dùng `part.answered`: con số đó là ảnh chụp lúc
        // nạp trang, còn đáp án thì được lưu từng câu mà không nạp lại. Bản đầu
        // dùng nó, và kết quả là thanh bên hiện 1/17 trong khi tab vẫn hiện 0/1
        // — hai con số cùng nói về một việc mà không khớp nhau.
        const answered = state.questions.filter(
          (question) => question.part === part.part && question.selected_option_id,
        ).length;
        return (
          <div key={part.part} className="flex items-center gap-1">
            {boundary && (
              <span className="px-1.5 text-ink-faint" title={part.section}>
                {part.section === "listening" ? (
                  <Headphones size={15} strokeWidth={1.75} aria-hidden />
                ) : (
                  <BookOpen size={15} strokeWidth={1.75} aria-hidden />
                )}
              </span>
            )}
            <button
              type="button"
              onClick={() => onSelect(part.part)}
              aria-current={active === part.part}
              className={cx(
                "inline-flex shrink-0 items-center gap-1.5 rounded px-2.5 py-1 text-small font-semibold",
                active === part.part
                  ? "bg-action text-on-action"
                  : "text-ink-muted hover:bg-recess hover:text-ink",
              )}
            >
              P{part.part}
              <span
                className={cx(
                  "font-data tabular-nums text-label",
                  active === part.part ? "opacity-80" : "text-ink-faint",
                )}
              >
                {answered}/{part.total}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}

function ResultBanner({ result }: { result: AttemptResult }) {
  return (
    <div className="border-b border-rule-strong bg-recess px-4 py-5">
      <div className="mx-auto flex w-full max-w-[110rem] flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <p className="text-label uppercase text-ink-muted">Số câu đúng</p>
          <p className="font-data text-2xl tabular-nums">
            {result.correct_count}
            <span className="text-ink-faint">/{result.question_count}</span>
          </p>
        </div>
        {result.listening_scaled !== null && (
          <div>
            <p className="text-label uppercase text-ink-muted">Nghe</p>
            <p className="font-data text-2xl tabular-nums">{result.listening_scaled}</p>
          </div>
        )}
        {result.reading_scaled !== null && (
          <div>
            <p className="text-label uppercase text-ink-muted">Đọc</p>
            <p className="font-data text-2xl tabular-nums">{result.reading_scaled}</p>
          </div>
        )}
        {result.total_scaled !== null && (
          <div>
            <p className="text-label uppercase text-ink-muted">Tổng quy đổi</p>
            <p className="font-data text-2xl font-semibold tabular-nums text-action-ink">
              {result.total_scaled}
            </p>
          </div>
        )}
        {/* Vì sao KHÔNG có điểm quy đổi, khi không có. `scoring.py` từ chối đoán,
            nên giao diện phải nói ra lý do thay vì hiện số 0. */}
        {result.scale_note && (
          <p className="max-w-xl text-small text-ink-muted">{result.scale_note}</p>
        )}
      </div>
    </div>
  );
}

function StimulusBlock({
  block,
  done,
  onChoose,
  onFlag,
}: {
  block: Block;
  done: boolean;
  onChoose: (question: QuestionPublic, optionId: string) => void;
  onFlag: (question: QuestionPublic) => void;
}) {
  const questions = (
    <div className="space-y-4">
      {block.questions.map((question) => (
        <QuestionCard
          key={question.id}
          question={question}
          done={done}
          onChoose={onChoose}
          onFlag={onFlag}
        />
      ))}
    </div>
  );

  // Không có ngữ liệu (Part 2, Part 5) thì không dựng lưới hai cột chỉ để bỏ
  // trống một nửa: một cột rỗng đọc như thứ đang tải dở.
  if (!block.hasStimulus) {
    return <section className="max-w-3xl">{questions}</section>;
  }

  return (
    <section className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-3 lg:sticky lg:top-32 lg:self-start">
        {block.title && <p className="text-small font-semibold text-ink-muted">{block.title}</p>}

        {/* Ảnh nằm ở object store ngoài, và `next/image` cần khai domain cho
            từng nhà cung cấp trong `next.config` — trong khi nhà cung cấp ở
            đây là một biến môi trường (ADR-006 §2.8). Nên dùng <img> thẳng. */}
        {block.imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={block.imageUrl}
            alt={block.imageAlt ?? ""}
            // Chặn chiều cao: ảnh Part 1 là ảnh dọc thì nó đẩy trình phát audio
            // xuống dưới màn hình, và người làm bài phải cuộn đi tìm nút Play ở
            // một phần thi tính bằng giây.
            className="max-h-[55vh] w-full rounded border border-rule object-contain"
          />
        )}

        {/* Ghi công là ĐIỀU KIỆN của giấy phép, không phải chú thích tuỳ chọn:
            ảnh CC-BY chỉ được dùng khi có ghi công (ADR-004 §4.2). Lưu vào
            database mà không hiện ra vẫn là vi phạm. */}
        {block.imageUrl && block.imageCredit && (
          <p className="text-label text-ink-faint">{block.imageCredit}</p>
        )}

        {block.audioUrl && (
          // `controls` gốc của trình duyệt, không tự dựng player: nó đã có tua,
          // âm lượng, tốc độ phát và phím tắt — và quan trọng hơn, nó đọc được
          // bằng trình đọc màn hình mà không cần ta làm gì thêm.
          /* `preload="metadata"`, không phải `"none"`: với `"none"` trình duyệt
             chưa tải header nên thanh phát hiện "0:00 / 0:00", và người làm bài
             không biết clip dài bao nhiêu trước khi bấm — thứ họ cần biết ở một
             bài thi có giới hạn giờ. Metadata chỉ vài KB, không phải cả file. */
          <audio src={block.audioUrl} controls preload="metadata" className="w-full">
            Trình duyệt của bạn không phát được audio.
          </audio>
        )}

        {block.passages.map((passage, index) => (
          <article
            key={index}
            className="whitespace-pre-wrap rounded border border-rule bg-panel p-4 text-small leading-relaxed"
          >
            {passage}
          </article>
        ))}
      </div>

      {questions}
    </section>
  );
}

function QuestionCard({
  question,
  done,
  onChoose,
  onFlag,
}: {
  question: QuestionPublic;
  done: boolean;
  onChoose: (question: QuestionPublic, optionId: string) => void;
  onFlag: (question: QuestionPublic) => void;
}) {
  // Part 1 và 2 KHÔNG in đáp án — ETS chỉ đọc lên. `content` là NULL ở đó, và
  // đó là giá trị đúng chứ không phải dữ liệu thiếu, nên giao diện thu về những
  // ô chữ cái thay vì hiện bốn dòng trống.
  const lettersOnly = question.options.every((option) => option.content === null);

  return (
    <div
      id={`q-${question.number}`}
      className="scroll-mt-32 rounded border border-rule-strong bg-panel p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold">Câu {question.number}</p>
        <button
          type="button"
          onClick={() => onFlag(question)}
          disabled={done}
          aria-pressed={question.flagged}
          className={cx(
            "inline-flex items-center gap-1.5 rounded px-2 py-1 text-small font-semibold disabled:opacity-45",
            question.flagged ? "text-warn" : "text-ink-muted hover:text-ink",
          )}
        >
          <Flag
            size={14}
            strokeWidth={2}
            aria-hidden
            fill={question.flagged ? "currentColor" : "none"}
          />
          Đánh dấu
        </button>
      </div>

      {question.prompt_text && (
        <p className="mt-2 whitespace-pre-wrap leading-relaxed">{question.prompt_text}</p>
      )}

      <div className={cx("mt-3", lettersOnly ? "flex flex-wrap gap-2" : "space-y-2")}>
        {question.options.map((option) => {
          const chosen = question.selected_option_id === option.id;
          const correct = question.correct_option_id === option.id;
          // `correct_option_id` chỉ tồn tại ở chế độ Luyện tập hoặc sau khi nộp.
          // Không cần hỏi "đang ở chế độ nào" — nếu máy chủ không gửi thì
          // `revealed` là false và không có gì để lộ.
          const revealed = question.correct_option_id !== null;

          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onChoose(question, option.id)}
              disabled={done}
              aria-pressed={chosen}
              className={cx(
                "rounded border text-left disabled:cursor-default",
                lettersOnly ? "h-10 w-12 font-semibold" : "flex w-full items-start gap-3 p-3",
                revealed && correct
                  ? "border-ok bg-ok-tint text-ok"
                  : revealed && chosen
                    ? "border-alert bg-alert-tint text-alert"
                    : chosen
                      ? "border-action bg-action-tint text-action-ink"
                      : "border-rule bg-panel hover:border-rule-strong",
              )}
            >
              {lettersOnly ? (
                <span className="block text-center">{option.label}</span>
              ) : (
                <>
                  <span
                    className={cx(
                      "grid h-6 w-6 shrink-0 place-items-center rounded border text-label font-semibold",
                      chosen || (revealed && correct) ? "border-current" : "border-rule-strong",
                    )}
                  >
                    {option.label}
                  </span>
                  <span className="leading-relaxed">{option.content}</span>
                </>
              )}
            </button>
          );
        })}
      </div>

      {question.explanation && (
        <p className="mt-3 rounded border border-rule bg-recess p-3 text-small leading-relaxed">
          {question.explanation}
        </p>
      )}
    </div>
  );
}

function QuestionGrid({
  state,
  answered,
  activePart,
  onJump,
}: {
  state: AttemptState;
  answered: number;
  activePart: number | null;
  onJump: (question: QuestionPublic) => void;
}) {
  const percent = state.question_count ? Math.round((answered / state.question_count) * 100) : 0;

  return (
    <aside className="hidden w-64 shrink-0 xl:block">
      <div className="sticky top-32 rounded border border-rule-strong bg-panel p-4">
        <div className="flex items-baseline justify-between gap-2">
          <p className="font-semibold">Tiến độ</p>
          <p className="font-data text-small tabular-nums text-ink-muted">
            {answered}/{state.question_count} ({percent}%)
          </p>
        </div>
        <div className="mt-2 h-1.5 rounded bg-recess">
          <div className="h-full rounded bg-action" style={{ width: `${percent}%` }} />
        </div>

        <div className="mt-4 max-h-[calc(100dvh-16rem)] space-y-4 overflow-y-auto">
          {state.parts.map((part) => (
            <div key={part.part}>
              <p className="text-label font-semibold uppercase text-ink-muted">
                Part {part.part} ({part.first_number}–{part.last_number})
              </p>
              <div className="mt-1.5 grid grid-cols-5 gap-1.5">
                {state.questions
                  .filter((question) => question.part === part.part)
                  .map((question) => (
                    <button
                      key={question.id}
                      type="button"
                      onClick={() => onJump(question)}
                      title={question.flagged ? "Đã đánh dấu" : undefined}
                      className={cx(
                        "relative h-8 rounded border font-data text-small tabular-nums",
                        question.selected_option_id
                          ? "border-action bg-action-tint text-action-ink"
                          : "border-rule text-ink-muted hover:border-rule-strong",
                        activePart === question.part && "opacity-100",
                      )}
                    >
                      {question.number}
                      {/* Đánh dấu là một chấm ở góc, không phải một màu nền
                          khác: câu vừa được đánh dấu vừa đã trả lời là chuyện
                          bình thường, và hai trạng thái đó phải cùng đọc được. */}
                      {question.flagged && (
                        <span className="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full bg-warn" />
                      )}
                    </button>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
