"use client";

import { API_ROUTES, type StudyPlanPublic } from "@toeic-pilot/shared";
import { BookOpen, Calendar, CheckCircle2, Circle, RefreshCw, Target } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { Alert, ButtonLink, Page, PageHeader, Panel, SkeletonList, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Kế hoạch học hiện hành (SPEC-PLACEMENT §6).
 *
 * Tiến độ là hàng "đã xong" SUY từ bản ghi học thật — bài ngữ pháp đã hoàn
 * thành, phiên part đã mở sau lúc kế hoạch sinh. Không có nút tick ở đây:
 * nhấn tick mà học thật chưa xảy ra là tự dối. Muốn xong một mục → học nó.
 */
/* useSearchParams đẩy route ra khỏi render tĩnh trừ khi nằm trong Suspense
   boundary — cùng chú thích với `vocabulary/[slug]`. */
export default function StudyPlanPage() {
  return (
    <Suspense
      fallback={
        <Page className="max-w-2xl">
          <SkeletonList rows={4} />
        </Page>
      }
    >
      <PlanView />
    </Suspense>
  );
}

function PlanView() {
  const { token } = useRequireSession();
  const searchParams = useSearchParams();
  const from = searchParams.get("from");
  const [plan, setPlan] = useState<StudyPlanPublic | null>(null);
  const [none, setNone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = useCallback(
    async (attemptId: string | null) => {
      if (!token) return;
      setBusy(true);
      setError(null);
      try {
        const p = await apiFetch<StudyPlanPublic>(API_ROUTES.studyPlanGenerate, {
          method: "POST",
          token,
          body: JSON.stringify(attemptId ? { attempt_id: attemptId } : {}),
        });
        setPlan(p);
        setNone(false);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Không sinh được kế hoạch.");
      } finally {
        setBusy(false);
      }
    },
    [token],
  );

  const load = useCallback(() => {
    if (!token) return;
    apiFetch<StudyPlanPublic | null>(API_ROUTES.studyPlan, { token })
      .then((p) => {
        if (p === null) setNone(true);
        else setPlan(p);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được kế hoạch."));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const t = window.setTimeout(() => {
      if (!from) {
        load();
        return;
      }
      // Kiểm kế hoạch hiện có TRƯỚC khi gọi generate: nút "Tạo kế hoạch học"
      // bấm lại từ cùng một kết quả thì chỉ GET xem lại — POST chỉ chạy khi
      // chưa có kế hoạch hoặc `from` là lượt placement khác (mới hơn).
      apiFetch<StudyPlanPublic | null>(API_ROUTES.studyPlan, { token })
        .then((p) => {
          if (p && p.placement_attempt_id === from) setPlan(p);
          else void generate(from);
        })
        .catch(() => void generate(from));
    }, 0);
    return () => window.clearTimeout(t);
  }, [from, generate, load, token]);

  async function regenerate() {
    await generate(null);
  }

  if (error) {
    return (
      <Page className="max-w-2xl">
        <Alert tone="alert">{error}</Alert>
      </Page>
    );
  }
  if (!plan && !none) {
    return (
      <Page className="max-w-2xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }
  if (plan === null) {
    return (
      <Page className="max-w-2xl">
        <PageHeader
          eyebrow="Kế hoạch học"
          title="Chưa có kế hoạch"
          description="Làm bài test đầu vào để kế hoạch biết bạn đang ở đâu."
        />
        <div className="mt-6">
          <ButtonLink href="/learn/placement">Làm bài test đầu vào</ButtonLink>
        </div>
      </Page>
    );
  }

  const allDone = plan.done_count === plan.items.length && plan.items.length > 0;

  return (
    <Page className="max-w-2xl">
      <PageHeader
        eyebrow="Kế hoạch học"
        title={allDone ? "Kế hoạch đã hoàn thành" : "Kế hoạch dựa trên bài test đầu vào"}
        description={
          allDone
            ? "Bạn đã đi hết lời khuyên mà bài test đầu vào đưa ra."
            : "Các mục sắp theo thứ tự ưu tiên: kỹ năng yếu nhất trước. Xong một mục bằng cách học thật, không bằng nút bấm."
        }
      />

      {allDone && (
        <Panel className="mt-6 p-6 text-center">
          <p className="text-label font-semibold uppercase text-ink-faint">Hoàn thành</p>
          <p className="mt-2 font-data text-title font-semibold tabular-nums">
            {plan.done_count}/{plan.items.length}
          </p>
          <p className="mt-2 max-w-md mx-auto text-small text-ink-muted">
            {plan.target_score !== null
              ? `Bước kiểm chứng tốt nhất bây giờ: một đề thi thử — xem bạn đã tiến gần ${plan.target_score} điểm mục tiêu chưa.`
              : "Bước kiểm chứng tốt nhất bây giờ: một đề thi thử — xem trình độ đã nhích bao nhiêu."}
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-3">
            <ButtonLink href="/learn/tests">Làm đề thi thử</ButtonLink>
            <ButtonLink href="/learn/placement" variant="secondary">
              Đo lại trình độ
            </ButtonLink>
          </div>
        </Panel>
      )}

      <Panel className={cx("p-4", allDone && "mt-4")}>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="inline-flex items-center gap-1.5 text-small text-ink-muted">
            <Target size={14} strokeWidth={2} aria-hidden />
            Mục tiêu:{" "}
            <span className="font-data tabular-nums text-ink">{plan.target_score ?? "—"}</span>
          </span>
          <span className="inline-flex items-center gap-1.5 text-small text-ink-muted">
            <Calendar size={14} strokeWidth={2} aria-hidden />
            Ngày thi:{" "}
            <span className="font-data tabular-nums text-ink">
              {plan.exam_date ? new Date(plan.exam_date).toLocaleDateString("vi-VN") : "—"}
            </span>
          </span>
          <span className="ml-auto text-small font-semibold text-ink-muted">
            {plan.done_count}/{plan.items.length} mục đã xong
          </span>
        </div>
      </Panel>

      <div className="mt-4 space-y-2">
        {plan.items.map((item) => (
          <Panel key={item.position} className="flex items-center gap-3 p-4">
            {item.done ? (
              <CheckCircle2 size={18} strokeWidth={2} className="shrink-0 text-ok" aria-hidden />
            ) : (
              <Circle size={18} strokeWidth={2} className="shrink-0 text-ink-faint" aria-hidden />
            )}
            <span className="min-w-0 flex-1">
              <span
                className={cx(
                  "font-semibold",
                  item.done && "text-ink-muted line-through decoration-ink-faint",
                )}
              >
                {item.label}
              </span>
              {item.reason && (
                <span className="block text-small text-ink-muted">{item.reason}</span>
              )}
            </span>
            {item.kind === "grammar_lesson" && item.ref_id ? (
              <ButtonLink href={`/learn/grammar/${item.ref_id}`} size="sm">
                <BookOpen size={13} strokeWidth={2} className="mr-1" aria-hidden />
                Học
              </ButtonLink>
            ) : (
              <ButtonLink href={`/learn/parts/${item.part}/drill`} size="sm" variant="secondary">
                <BookOpen size={13} strokeWidth={2} className="mr-1" aria-hidden />
                Luyện
              </ButtonLink>
            )}
          </Panel>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-3 border-t border-rule pt-5">
        <button
          type="button"
          onClick={() => void regenerate()}
          disabled={busy}
          className="inline-flex items-center gap-1.5 text-small font-semibold text-ink-muted hover:text-ink disabled:opacity-50"
        >
          <RefreshCw size={13} strokeWidth={2} aria-hidden />
          {busy ? "Đang sinh lại…" : "Sinh lại kế hoạch từ kết quả mới nhất"}
        </button>
        <Link
          href="/dashboard"
          className="ml-auto inline-flex items-center text-small font-semibold text-ink-muted hover:text-ink"
        >
          Về trang học
        </Link>
      </div>
    </Page>
  );
}
