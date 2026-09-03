"use client";

import {
  API_ROUTES,
  type AttemptResult,
  type AttemptState,
  type QuestionPublic,
} from "@toeic-pilot/shared";
import { BookOpen, LogOut, Send } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Modal } from "@/components/modal";
import { ThemeToggle } from "@/components/theme-toggle";
import { Alert, Button, EmptyState, Page, Skeleton } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { groupQuestions } from "@/lib/attempt";
import { CoachChat } from "@/components/coach-chat";
import { useRequireSession } from "@/lib/session";
import { Countdown } from "./_components/countdown";
import { PartTabs } from "./_components/part-tabs";
import { QuestionGrid } from "./_components/question-grid";
import { ResultScreen } from "./_components/result-screen";
import { ReviewToolbar } from "./_components/review-toolbar";
import { type ReviewFilter, Tally, formatClock, matchesFilter } from "./_components/shared";
import { StimulusBlock } from "./_components/stimulus-block";

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

/**
 * Hộp "Hỏi trợ giảng" đang TẮT, ở cả màn kết quả lẫn màn xem lại.
 *
 * Tắt bằng một cờ có tên chứ không xoá lời gọi: đây là một quyết định tạm, và
 * một hằng số đọc được nói ra điều đó — còn một dòng JSX bị xoá thì người sau
 * chỉ thấy `coach-chat.tsx` nằm đó không ai dùng và không biết là cố ý hay bỏ
 * quên. Bật lại bằng cách đổi thành `true`; toàn bộ dây nối vẫn nguyên.
 */
const SHOW_COACH_CHAT = false;

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
    // `view` cũng nằm trong deps: khi nhảy từ màn kết quả sang một cụm CÙNG
    // part đang mở, `setActivePart` không đổi giá trị nên effect không chạy và
    // trang đứng yên ở đầu danh sách.
  }, [activePart, view]);

  const answered = state?.questions.filter((q) => q.selected_option_id).length ?? 0;
  const done = result !== null || state?.status === "submitted" || state?.status === "expired";
  const showingResult = done && view === "result";
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

  /** Mở phần xem lại, và nếu có đích thì cuộn thẳng tới đó. */
  function reviewAt(target?: QuestionPublic) {
    setView("review");
    if (!target) return;
    setCurrent(target.number);
    pendingScroll.current = target.number;
    setActivePart(target.part);
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

        {/* Không có tab part ở màn KẾT QUẢ: ở đó không còn gì để điều hướng
            tới, và một hàng tab bấm được nhưng không đưa đi đâu là một lời hứa
            sai. Chúng quay lại ngay khi bấm "Xem chi tiết từng câu". */}
        {!showingResult && (
          <PartTabs state={state} active={activePart} onSelect={(part) => setActivePart(part)} />
        )}
        {/* Thanh lọc nằm TRONG header, không phải dưới nó.
            Nó mang nút "← Kết quả", và bấm một cụm ở màn kết quả sẽ cuộn thẳng
            xuống giữa một đề 200 câu — một thanh không dính thì trôi khỏi màn
            hình đúng lúc người ta cần nó, và đường về duy nhất trông như không
            tồn tại. */}
        {!showingResult && done && (
          <ReviewToolbar
            filter={filter}
            onFilter={setFilter}
            shown={visible.length}
            onBack={result ? () => setView("result") : null}
          />
        )}
      </header>

      {error && (
        <div className="px-4 pt-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      {showingResult && result ? (
        <ResultScreen result={result} state={state} onReview={reviewAt} />
      ) : (
        <>
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
      {SHOW_COACH_CHAT && done && <CoachChat attemptId={attemptId} token={token} />}

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
