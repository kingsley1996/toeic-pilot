"use client";

import {
  API_ROUTES,
  type AttemptResult,
  type AttemptState,
  type QuestionPublic,
} from "@toeic-pilot/shared";
import { ArrowLeft, BookOpen, Clock, Flag, Headphones, LogOut, Send } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Modal } from "@/components/modal";
import { ThemeToggle } from "@/components/theme-toggle";
import { Alert, Button, ButtonLink, EmptyState, Page, Skeleton, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { type Block, clock, credit, groupQuestions } from "@/lib/attempt";
import { CoachBlock } from "@/components/coach-block";
import { CoachChat } from "@/components/coach-chat";
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
  // Sau khi nộp, trang này có hai mặt: bảng kết quả và bài đã chấm. Mặc định là
  // kết quả — "tôi được bao nhiêu" là câu hỏi đầu tiên, xem lại từng câu là câu
  // thứ hai.
  const [view, setView] = useState<"result" | "review">("result");
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const [remaining, setRemaining] = useState<number | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);
  // Hai lối rời màn: nộp bài, và bỏ đi. Một state ba giá trị chứ không hai cờ
  // riêng — hai hộp thoại không bao giờ được mở cùng lúc.
  const [confirming, setConfirming] = useState<"submit" | "exit" | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /*
   * Câu đang xem — đặt bằng CÚ BẤM, không suy ra từ cuộn.
   *
   * Cuộn qua một câu không có nghĩa là đang làm câu đó, nên dấu hiệu bám theo
   * khung nhìn cứ nhảy trong khi người ta chỉ đang đọc lướt. Đánh dấu chỗ đứng
   * phải là thứ người dùng tự đặt.
   */
  const [current, setCurrent] = useState<number | null>(null);

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
        if (cancelled) return;
        applyState(data);
        // Mở lại một lượt ĐÃ nộp thì cũng phải thấy bảng kết quả. `POST /submit`
        // trả kết quả đúng một lần, nên không đọc lại ở đây thì một lần F5 sẽ
        // đưa người học thẳng sang màn xem đáp án và điểm biến mất không lý do.
        if (data.status !== "in_progress") {
          apiFetch<AttemptResult>(API_ROUTES.attemptResult(attemptId), { token })
            .then((finished) => {
              if (!cancelled) setResult(finished);
            })
            .catch(() => {
              /* không có kết quả thì vẫn xem lại bài được */
            });
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [applyState, attemptId, fetchState, token]);

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
      setConfirming(null);
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

  /*
   * Tải lại trang hay đóng tab thì `router` không biết gì — chỉ `beforeunload`
   * chặn được, và nó dùng hộp thoại của TRÌNH DUYỆT (không đổi được lời).
   *
   * Chỉ gắn khi bài đang làm dở: hỏi lại sau khi đã nộp là chặn người ta rời
   * khỏi một trang không còn gì để mất, và một cảnh báo vô cớ dạy người dùng
   * bấm bỏ qua mọi cảnh báo về sau.
   */
  useEffect(() => {
    // Tính tại chỗ thay vì dùng `done`: biến đó khai báo bên dưới.
    const finished = result !== null || state?.status !== "in_progress";
    if (finished) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      // Vẫn cần cho trình duyệt cũ; trình duyệt hiện đại bỏ qua nội dung.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [result, state]);

  useEffect(() => {
    const target = pendingScroll.current;
    if (target === null) return;
    pendingScroll.current = null;
    document.getElementById(`q-${target}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activePart]);

  const answered = state?.questions.filter((q) => q.selected_option_id).length ?? 0;
  const done = result !== null || state?.status === "submitted" || state?.status === "expired";
  const flaggedCount = state?.questions.filter((q) => q.flagged).length ?? 0;

  const visible = useMemo(() => {
    if (!state) return [];
    const inPart = state.questions.filter((q) => q.part === activePart);
    return inPart.filter((q) => matchesFilter(q, filter));
  }, [state, activePart, filter]);
  const blocks = useMemo(() => groupQuestions(visible), [visible]);

  async function choose(question: QuestionPublic, optionId: string) {
    if (!token || done) return;
    const next = question.selected_option_id === optionId ? null : optionId;
    // Trả lời xong thì câu đó đã có trạng thái riêng; dấu "đang xem" hết việc.
    setCurrent(null);
    patch(question.id, { selected_option_id: next });
    try {
      const fresh = await apiFetch<AttemptState>(API_ROUTES.attemptAnswer(attemptId, question.id), {
        method: "PATCH",
        token,
        body: JSON.stringify({ selected_option_id: next }),
      });
      /*
       * Ở chế độ Luyện tập, máy chủ chỉ gửi lời giải SAU khi câu đó đã có đáp
       * án — với Part 1 và 2 thì "lời giải" bao gồm cả nguyên văn lời đọc, và
       * gửi sớm là xoá mất phần nghe. Nên phải lấy lại đúng câu vừa trả lời.
       *
       * Lấy một câu chứ không thay cả `state`: lần bấm kế tiếp có thể đã xảy ra
       * trong lúc chờ, và bản trả về này sẽ ghi đè ngược lên nó.
       */
      const updated = fresh.questions.find((q) => q.id === question.id);
      if (updated) {
        patch(question.id, {
          options: updated.options,
          correct_option_id: updated.correct_option_id,
          explanation: updated.explanation,
        });
      }
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
    setCurrent(question.number);
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
              <Button size="sm" onClick={() => setConfirming("submit")} disabled={submitting}>
                <Send size={14} strokeWidth={2} aria-hidden />
                Nộp bài
              </Button>
            )}
            {/*
             * Sau khi nộp thì rời đi KHÔNG mất gì: đáp án đã lưu, điểm đã chốt,
             * và lượt làm bài vẫn nằm trong lịch sử. Một hộp thoại xác nhận cho
             * một hành động không mất gì là nhiễu — và tệ hơn, nó dạy người dùng
             * bấm qua hộp thoại mà không đọc, đúng lúc ta cần họ đọc là lúc bài
             * còn dở.
             */}
            <Button
              size="sm"
              variant="secondary"
              onClick={() => (done ? router.push("/learn/tests") : setConfirming("exit"))}
            >
              <LogOut size={14} strokeWidth={2} aria-hidden />
              {done ? "Xong" : "Thoát"}
            </Button>
            {/* Chọn theme ngay tại đây: màn làm bài cố ý không có header của khu
                học, nên đây là nơi DUY NHẤT đổi được — và một bài thi 120 phút
                là đúng lúc người ta muốn chuyển sang nền tối. */}
            <ThemeToggle />
          </div>
        </div>

        <PartTabs state={state} active={activePart} onSelect={(part) => setActivePart(part)} />
      </header>

      {error && (
        <div className="px-4 pt-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      {done && view === "result" && result ? (
        <ResultScreen result={result} state={state} onReview={() => setView("review")} />
      ) : (
        <>
          {done && (
            <ReviewToolbar
              filter={filter}
              onFilter={setFilter}
              shown={visible.length}
              onBack={result ? () => setView("result") : null}
            />
          )}

          <div className="mx-auto flex w-full max-w-[110rem] gap-6 px-4 py-6">
            <main className="min-w-0 flex-1 space-y-8">
              {blocks.length === 0 ? (
                <p className="text-ink-muted">
                  {done && filter !== "all"
                    ? "Không có câu nào khớp bộ lọc trong phần này."
                    : "Phần này không có câu nào trong lượt làm của bạn."}
                </p>
              ) : (
                blocks.map((block) => (
                  <StimulusBlock
                    key={block.key}
                    block={block}
                    done={done}
                    attemptId={attemptId}
                    token={token}
                    onView={setCurrent}
                    onChoose={choose}
                    onFlag={toggleFlag}
                  />
                ))
              )}
            </main>

            <QuestionGrid state={state} answered={answered} current={current} onJump={jumpTo} />
          </div>
        </>
      )}

      <Modal
        open={confirming === "submit"}
        onClose={() => setConfirming(null)}
        title="Nộp bài?"
        description="Nộp rồi thì không quay lại làm tiếp được. Câu bỏ trống tính là sai."
      >
        {/* Bốn con số, không phải một câu văn. Người sắp nộp bài cần đối chiếu
            nhanh xem còn sót gì — và "còn 3 câu chưa trả lời" giấu mất chuyện
            họ đã đánh dấu 5 câu để quay lại mà chưa quay lại. */}
        <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-2 text-small sm:grid-cols-4">
          <Tally label="Đã trả lời" value={`${answered}/${state.question_count}`} />
          <Tally
            label="Chưa trả lời"
            value={state.question_count - answered}
            tone={answered < state.question_count ? "warn" : undefined}
          />
          <Tally
            label="Đã đánh dấu"
            value={flaggedCount}
            tone={flaggedCount > 0 ? "warn" : undefined}
          />
          <Tally
            label="Thời gian còn"
            value={remaining === null ? "không giới hạn" : formatClock(remaining)}
          />
        </dl>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirming(null)}>
            Quay lại làm tiếp
          </Button>
          <Button onClick={() => void submit()} disabled={submitting}>
            {submitting ? "Đang nộp…" : "Nộp bài"}
          </Button>
        </div>
      </Modal>

      {/* Chỉ sau khi nộp: máy chủ trả 409 nếu chưa, và một hộp chat bấm được
          rồi báo lỗi là một lời mời hỏng. */}
      {done && <CoachChat attemptId={attemptId} token={token} />}

      <Modal
        open={confirming === "exit" && !done}
        onClose={() => setConfirming(null)}
        title="Thoát khỏi bài thi?"
        /*
         * Nói ĐÚNG cái mất, không doạ chung chung. Đáp án đã lưu ở máy chủ ngay
         * lúc chọn, nên rời đi không mất bài — nhưng đồng hồ vẫn chạy ở máy chủ,
         * và hết giờ thì bài tự nộp dù người ta đang ở đâu.
         */
        description="Đáp án đã chọn được lưu rồi, nên bạn quay lại làm tiếp được. Nhưng đồng hồ vẫn chạy khi bạn rời đi, và hết giờ thì bài tự nộp."
      >
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirming(null)}>
            Ở lại làm tiếp
          </Button>
          <Button variant="destructive" onClick={() => router.push("/learn/tests")}>
            Thoát
          </Button>
        </div>
      </Modal>
    </div>
  );
}

type ReviewFilter = "all" | "wrong" | "blank" | "flagged";

const FILTERS: { value: ReviewFilter; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "wrong", label: "Câu sai" },
  { value: "blank", label: "Bỏ trống" },
  { value: "flagged", label: "Đã đánh dấu" },
];

/**
 * Câu này có lọt qua bộ lọc đang chọn không.
 *
 * "Sai" và "bỏ trống" là hai thứ KHÁC nhau ở đây, dù chấm điểm thì cả hai đều
 * không được điểm: bỏ trống là hết giờ hoặc bỏ qua, còn sai là đã cân nhắc rồi
 * chọn nhầm — và hai loại đó cần đọc lại theo hai kiểu khác nhau.
 */
function matchesFilter(question: QuestionPublic, filter: ReviewFilter): boolean {
  if (filter === "all") return true;
  if (filter === "flagged") return question.flagged;
  if (filter === "blank") return question.selected_option_id === null;
  return (
    question.selected_option_id !== null &&
    question.correct_option_id !== null &&
    question.selected_option_id !== question.correct_option_id
  );
}

/** Giây -> "42 phút 15 giây", cho chỗ đọc chậm chứ không phải đồng hồ đếm ngược. */
function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safe / 60);
  return minutes ? `${minutes} phút ${safe % 60} giây` : `${safe} giây`;
}

function Tally({ label, value, tone }: { label: string; value: string | number; tone?: "warn" }) {
  return (
    <div>
      <dt className="text-label uppercase text-ink-faint">{label}</dt>
      <dd className={cx("font-data tabular-nums", tone === "warn" ? "text-warn" : "text-ink")}>
        {value}
      </dd>
    </div>
  );
}

/**
 * Thanh lọc khi xem lại bài đã chấm.
 *
 * Bộ lọc chạy TRONG part đang mở, không cắt ngang cả đề: người xem lại vẫn đi
 * theo cấu trúc đề, và "câu sai của Part 3" là câu hỏi thật, còn "câu sai thứ
 * mười bảy của cả bài" thì không.
 */
function ReviewToolbar({
  filter,
  onFilter,
  shown,
  onBack,
}: {
  filter: ReviewFilter;
  onFilter: (value: ReviewFilter) => void;
  shown: number;
  onBack: (() => void) | null;
}) {
  return (
    <div className="border-b border-rule bg-recess px-4 py-2.5">
      <div className="mx-auto flex w-full max-w-[110rem] flex-wrap items-center gap-2">
        {onBack && (
          <Button size="sm" variant="secondary" onClick={onBack}>
            <ArrowLeft size={14} strokeWidth={2} aria-hidden />
            Kết quả
          </Button>
        )}
        <div className="flex flex-wrap items-center gap-1.5">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onFilter(option.value)}
              aria-pressed={filter === option.value}
              className={cx(
                "rounded border px-2.5 py-1 text-small font-semibold",
                filter === option.value
                  ? "border-rule-strong bg-panel text-ink"
                  : "border-transparent text-ink-muted hover:text-ink",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
        <span className="font-data text-small tabular-nums text-ink-faint">{shown} câu</span>
      </div>
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

/**
 * Bảng kết quả sau khi nộp.
 *
 * Thay cho danh sách câu chứ không nằm đè lên nó: câu hỏi đầu tiên sau khi nộp
 * là "tôi được bao nhiêu", còn xem lại từng câu là việc thứ hai và có nút riêng.
 *
 * Điểm quy đổi chỉ hiện khi máy chủ THẬT SỰ gửi. `scoring.py` từ chối quy đổi
 * một đề rút gọn — bảng điểm dựng cho 200 câu, nên đề 40 câu tra vào đó sẽ chạm
 * sàn và in ra "Nghe 5 · Đọc 5" cho một người làm đúng 60%. Chỗ trống đó được
 * lấp bằng `scale_note` nói lý do, không phải bằng số 0.
 */
function ResultScreen({
  result,
  state,
  onReview,
}: {
  result: AttemptResult;
  state: AttemptState;
  onReview: () => void;
}) {
  const answered = state.questions.filter((q) => q.selected_option_id).length;
  const flagged = state.questions.filter((q) => q.flagged).length;
  const percent = result.question_count
    ? Math.round((result.correct_count / result.question_count) * 100)
    : 0;

  // Đúng/tổng theo từng part, tính từ chính danh sách câu — sau khi nộp mỗi câu
  // đã mang `correct_option_id`, nên không cần endpoint thống kê riêng.
  const byPart = state.parts.map((part) => {
    const questions = state.questions.filter((q) => q.part === part.part);
    const correct = questions.filter(
      (q) => q.selected_option_id !== null && q.selected_option_id === q.correct_option_id,
    ).length;
    return { ...part, correct, count: questions.length };
  });

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8">
      <p className="text-label uppercase text-ink-muted">Kết quả</p>
      <h1 className="mt-1 text-title">{state.test_title}</h1>

      <div className="mt-6 rounded border border-rule-strong bg-panel p-5">
        <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
          <div>
            <p className="text-label uppercase text-ink-muted">Số câu đúng</p>
            <p className="font-data text-3xl font-semibold tabular-nums">
              {result.correct_count}
              <span className="text-ink-faint">/{result.question_count}</span>
            </p>
          </div>
          <div>
            <p className="text-label uppercase text-ink-muted">Độ chính xác</p>
            <p className="font-data text-3xl tabular-nums">{percent}%</p>
          </div>
          {result.total_scaled !== null && (
            <div>
              <p className="text-label uppercase text-ink-muted">Tổng quy đổi</p>
              <p className="font-data text-3xl font-semibold tabular-nums text-action-ink">
                {result.total_scaled}
              </p>
            </div>
          )}
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
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-rule pt-4 sm:grid-cols-4">
          <Tally label="Đã trả lời" value={`${answered}/${result.question_count}`} />
          <Tally
            label="Bỏ trống"
            value={result.question_count - answered}
            tone={answered < result.question_count ? "warn" : undefined}
          />
          <Tally label="Đã đánh dấu" value={flagged} />
          <Tally label="Thời gian đã dùng" value={formatClock(result.elapsed_seconds)} />
        </dl>

        {result.scale_note && (
          <p className="mt-4 rounded border border-rule bg-recess p-3 text-small text-ink-muted">
            {result.scale_note}
          </p>
        )}
      </div>

      <section className="mt-8">
        <h2 className="text-label font-semibold uppercase text-ink-muted">Theo từng phần</h2>
        <div className="mt-3 space-y-2">
          {byPart
            .filter((part) => part.count > 0)
            .map((part) => {
              const share = part.count ? Math.round((part.correct / part.count) * 100) : 0;
              return (
                <div
                  key={part.part}
                  className="flex items-center gap-3 rounded border border-rule bg-panel px-3 py-2.5"
                >
                  <span className="w-28 shrink-0 text-small font-semibold">
                    Part {part.part}
                    <span className="ml-1.5 font-normal text-ink-faint">{part.section}</span>
                  </span>
                  <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-pill bg-recess">
                    <div
                      className={cx("h-full", share >= 50 ? "bg-ok" : "bg-warn")}
                      style={{ width: `${share}%` }}
                    />
                  </div>
                  <span className="w-20 shrink-0 text-right font-data text-small tabular-nums">
                    {part.correct}/{part.count}
                  </span>
                  <span className="w-12 shrink-0 text-right font-data text-small tabular-nums text-ink-muted">
                    {share}%
                  </span>
                </div>
              );
            })}
        </div>
      </section>

      <div className="mt-8 flex flex-wrap gap-2">
        <Button onClick={onReview}>Xem chi tiết từng câu</Button>
        <ButtonLink href="/learn/tests" variant="secondary">
          Về danh sách đề
        </ButtonLink>
      </div>
    </div>
  );
}

function StimulusBlock({
  block,
  done,
  attemptId,
  token,
  onView,
  onChoose,
  onFlag,
}: {
  block: Block;
  done: boolean;
  attemptId: string;
  token: string | null;
  onView: (number: number) => void;
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
          attemptId={attemptId}
          token={token}
          onView={onView}
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

        {block.transcript.length > 0 && (
          /* Đóng sẵn, không mở sẵn. Lời thoại về được nghĩa là người học đã trả
             lời xong, nhưng họ có thể muốn nghe lại lần nữa trước khi đọc — mở
             sẵn thì mắt đọc trước tai, và lần nghe lại đó mất giá trị. */
          <details className="rounded border border-rule bg-panel">
            <summary className="cursor-pointer select-none px-4 py-2 text-small font-medium">
              Full transcript
            </summary>
            <div className="space-y-2 border-t border-rule px-4 py-3">
              {block.transcript.map((turn, index) => (
                <p key={index} className="text-small leading-relaxed">
                  <span className="text-ink-faint">{turn.speaker}: </span>
                  {turn.text}
                </p>
              ))}
            </div>
          </details>
        )}

        {block.passages.map((passage, index) => (
          <article key={index} className="rounded border border-rule bg-panel p-4">
            {passage.text && (
              <p className="whitespace-pre-wrap text-small leading-relaxed">{passage.text}</p>
            )}
            {passage.image_url && (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={passage.image_url}
                  alt={passage.image_alt ?? ""}
                  className={cx(
                    "max-h-[60vh] w-full rounded border border-rule object-contain",
                    passage.text && "mt-3",
                  )}
                />
                {/* Ghi công là điều kiện của giấy phép ở MỌI nơi ảnh xuất hiện,
                    không riêng Part 1 (ADR-004 §4.2). */}
                {credit(passage.image_attribution, passage.image_license) && (
                  <p className="mt-1.5 text-label text-ink-faint">
                    {credit(passage.image_attribution, passage.image_license)}
                  </p>
                )}
              </>
            )}
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
  attemptId,
  token,
  onView,
  onChoose,
  onFlag,
}: {
  question: QuestionPublic;
  done: boolean;
  attemptId: string;
  token: string | null;
  onView: (number: number) => void;
  onChoose: (question: QuestionPublic, optionId: string) => void;
  onFlag: (question: QuestionPublic) => void;
}) {
  // Part 1 và 2 KHÔNG in đáp án — ETS chỉ đọc lên. `content` là NULL ở đó, và
  // đó là giá trị đúng chứ không phải dữ liệu thiếu, nên giao diện thu về những
  // ô chữ cái thay vì hiện bốn dòng trống.
  const lettersOnly = question.options.every((option) => option.content === null);
  // Chỉ khi đã lộ, máy chủ mới gửi kèm lời đọc và bản dịch — và ô chữ cái rộng
  // 48px không chứa nổi một câu, nên chữ tràn ra ngoài rồi đè lên ô bên cạnh.
  // Lộ rồi thì bố cục phải quay về danh sách đầy chiều ngang; ô chữ cái chỉ
  // đúng ở đúng trạng thái nó được dựng cho, là lúc chưa có gì để đọc.
  const spoken = question.options.some(
    (option) => option.spoken_text !== null || option.content_vi !== null,
  );
  const chips = lettersOnly && !spoken;

  return (
    <div
      id={`q-${question.number}`}
      // Bấm vào thẻ để đánh dấu đang xem câu này. Bỏ qua cú bấm phát ra từ một
      // nút bên trong — chọn đáp án hay đánh dấu có ý nghĩa riêng của chúng, và
      // để chúng nổi lên đây sẽ ghi đè lại đúng thứ vừa được xử lý.
      onClick={(event) => {
        if (!(event.target as HTMLElement).closest("button")) onView(question.number);
      }}
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

      <div className={cx("mt-3", chips ? "flex flex-wrap gap-2" : "space-y-2")}>
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
                chips ? "h-10 w-12 font-semibold" : "flex w-full items-start gap-3 p-3",
                revealed && correct
                  ? "border-ok bg-ok-tint text-ok"
                  : revealed && chosen
                    ? "border-alert bg-alert-tint text-alert"
                    : chosen
                      ? "border-action bg-action-tint text-action-ink"
                      : "border-rule bg-panel hover:border-rule-strong",
              )}
            >
              {chips ? (
                /*
                 * Part 1 và 2: lúc làm bài chỉ có chữ cái, vì đề thi không in
                 * gì — đọc được bốn câu trả lời thì phần kiểm kỹ năng NGHE
                 * không còn đo thứ nó định đo.
                 */
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
                  <span className="min-w-0 leading-relaxed">
                    {option.content ?? option.spoken_text}
                    {/* Bản dịch xuống dòng riêng, cỡ nhỏ hơn: nó là chú thích
                        cho nguyên văn chứ không phải một đáp án thứ hai. Cùng
                        dòng thì mắt đọc thành một câu song ngữ dài. */}
                    {option.content_vi && (
                      <span className="mt-0.5 block text-small text-ink-muted">
                        {option.content_vi}
                      </span>
                    )}
                  </span>
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

      {/*
       * Chỉ hiện SAU KHI NỘP, và chỉ cho câu làm sai hoặc bỏ trống.
       *
       * Trước khi nộp thì máy chủ trả 409 — nhưng giao diện không được dựa vào
       * đó: một nút bấm được rồi báo lỗi là một nút hứa sai. Và câu làm ĐÚNG thì
       * không có gì để chẩn đoán; đưa nút ra đó chỉ mời người ta đốt hạn mức.
       */}
      {done &&
        question.correct_option_id !== null &&
        question.selected_option_id !== question.correct_option_id && (
          <CoachBlock attemptId={attemptId} questionId={question.id} token={token} />
        )}
    </div>
  );
}

function QuestionGrid({
  state,
  answered,
  current,
  onJump,
}: {
  state: AttemptState;
  answered: number;
  current: number | null;
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

        {/* Đệm trong vùng cuộn để vòng "đang xem" có chỗ: nó vẽ NGOÀI hộp, mà
            `overflow-y-auto` cắt cả hai chiều — không có đệm thì ô ở rìa hiện
            một vòng đứt đoạn, đọc như lỗi vẽ chứ không như một trạng thái. */}
        <div className="mt-4 max-h-[calc(100dvh-16rem)] space-y-4 overflow-y-auto p-1.5">
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
                      aria-current={current === question.number ? "true" : undefined}
                      title={gridTitle(question, current === question.number)}
                      className={gridClass(question, current === question.number)}
                    >
                      {question.number}
                      {/* Đánh dấu là một chấm ở góc, không phải một màu nền
                          khác: câu vừa được đánh dấu vừa đã trả lời là chuyện
                          bình thường, và hai trạng thái đó phải cùng đọc được. */}
                      {question.flagged && (
                        // Viền cùng màu nền để chấm tách khỏi ô kể cả khi ô đã
                        // được tô — trên nền `action-tint` nó nhoè vào, và
                        // trạng thái đánh dấu biến mất đúng ở những câu hay
                        // được đánh dấu nhất.
                        <span className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-pill border border-panel bg-warn" />
                      )}
                    </button>
                  ))}
              </div>
            </div>
          ))}
        </div>

        <Legend />
      </div>
    </aside>
  );
}

/* Bốn trạng thái dùng ba KÊNH thị giác khác nhau, nên chúng chồng lên nhau
 * được mà vẫn đọc riêng ra được:
 *
 *   nền + viền   chưa trả lời  <->  đã trả lời   (loại trừ nhau)
 *   vòng ngoài   đang xem                        (chồng lên cả hai)
 *   chấm góc     đánh dấu                        (chồng lên cả hai)
 *
 * Dùng cùng một kênh cho hai trạng thái độc lập là cách chắc chắn nhất để một
 * trong hai biến mất khi cả hai cùng đúng.
 */
function gridClass(question: QuestionPublic, isCurrent: boolean): string {
  return cx(
    "relative h-8 rounded border font-data text-small tabular-nums",
    question.selected_option_id
      ? "border-action bg-action-tint font-semibold text-action-ink"
      : "border-rule bg-panel text-ink-muted hover:border-rule-strong",
    /*
     * Vòng vẽ bằng PSEUDO-ELEMENT, không phải `outline` và cũng không `ring`.
     * Cả hai lối kia đều đã có chủ:
     *
     *   `ring` của Tailwind biên dịch ra box-shadow — §6.3 chỉ chừa box-shadow
     *   cho vòng focus, header dính và lớp phủ thật.
     *
     *   `outline` thuộc về hệ thống focus. `globals.css` có
     *   `:focus:not(:focus-visible) { outline: none }`, và selector đó nặng
     *   (0,2,0) hơn utility `.outline-2` (0,1,0) nên nó THẮNG. Bấm chuột vào
     *   một `<button>` cho `:focus` mà không cho `:focus-visible`, tức vòng bị
     *   xoá đúng trên ô vừa bấm — nhìn từ phía người dùng là vòng không bao giờ
     *   nằm ở ô mình bấm mà nhấp nháy sang ô bên cạnh.
     */
    isCurrent &&
      "after:pointer-events-none after:absolute after:-inset-[3px] after:rounded after:border-2 after:border-action-ink",
  );
}

function gridTitle(question: QuestionPublic, isCurrent: boolean): string {
  const states = [
    question.selected_option_id ? "đã trả lời" : "chưa trả lời",
    ...(isCurrent ? ["đang xem"] : []),
    ...(question.flagged ? ["đã đánh dấu"] : []),
  ];
  return `Câu ${question.number} — ${states.join(", ")}`;
}

function Legend() {
  return (
    // Chú giải chứ không để người dùng tự đoán: bốn trạng thái mà chỉ có màu
    // sắc phân biệt thì người mới nhìn không biết cái nào nghĩa là gì, và họ
    // đang giữa một bài thi tính giờ.
    <ul className="mt-4 space-y-1.5 border-t border-rule pt-3 text-small text-ink-muted">
      {[
        { label: "Chưa trả lời", box: "border-rule bg-panel", dot: false },
        { label: "Đã trả lời", box: "border-action bg-action-tint", dot: false },
        {
          label: "Đang xem",
          box: "border-rule bg-panel after:pointer-events-none after:absolute after:-inset-[3px] after:rounded after:border-2 after:border-action-ink",
          dot: false,
        },
        { label: "Đã đánh dấu", box: "border-rule bg-panel", dot: true },
      ].map((item) => (
        <li key={item.label} className="flex items-center gap-2.5">
          <span className={cx("relative h-4 w-4 shrink-0 rounded border", item.box)}>
            {item.dot && (
              <span className="absolute -right-1 -top-1 h-2 w-2 rounded-pill border border-panel bg-warn" />
            )}
          </span>
          {item.label}
        </li>
      ))}
    </ul>
  );
}
