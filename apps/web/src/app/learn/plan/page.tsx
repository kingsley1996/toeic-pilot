"use client";

import {
  API_ROUTES,
  type PlacementGate,
  type StudyPlanItemPublic,
  type StudyPlanPublic,
  type UserProfilePublic,
  type PlanEvaluationPublic,
  type PlanVersionPublic,
} from "@toeic-pilot/shared";
import { Calendar, Pencil } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { PlanCalendar, isCorePlanItem } from "@/components/plan-calendar";
import {
  Alert,
  Button,
  ButtonLink,
  Field,
  Input,
  Page,
  PageHeader,
  Panel,
  SkeletonList,
  Tag,
  cx,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Kế hoạch học hiện hành (SPEC-PLACEMENT §6).
 *
 * Một mục được coi là xong theo HAI nguồn, hiển thị chung nhưng không lẫn:
 * bản ghi học thật (bài ngữ pháp đã hoàn thành, phiên part đã trả lời) tự tick
 * và KHÔNG bỏ tick được ở đây — bỏ dấu một việc đã xảy ra là nói dối; hoặc ô
 * tick tay trong chi tiết ngày (`done_at`), đường duy nhất khép một buổi nhịp
 * nền. Muốn tick ở đâu thì học ở đó hoặc bấm ở đó, lịch tự trôi theo.
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
  const [gate, setGate] = useState<PlacementGate | null>(null);
  const [profile, setProfile] = useState<UserProfilePublic | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [profileLoaded, setProfileLoaded] = useState(false);
  // null = không mở. `attemptId` là lượt placement sẽ được dựng plan khi form
  // hợp lệ — đường `?from=` mang nó tới, đường hero lấy từ gate.
  const [modal, setModal] = useState<{ attemptId: string | null } | null>(null);
  const [evaluation, setEvaluation] = useState<PlanEvaluationPublic | null>(null);
  const [versions, setVersions] = useState<PlanVersionPublic[]>([]);

  // Mục tiêu/ngày thi SỬA được ngay trên màn này — nhưng nguồn sự thật vẫn là
  // `user_profile` (SPEC-PLACEMENT: một nguồn cho cả form placement lẫn profile),
  // nên đây chỉ là một cửa nữa ghi vào ô đó, không phải cột thứ hai.
  useEffect(() => {
    if (!token || !plan) return;
    apiFetch<PlanEvaluationPublic>(API_ROUTES.studyPlanEvaluation, { token })
      .then(setEvaluation)
      .catch(() => setEvaluation(null));
    apiFetch<PlanVersionPublic[]>(API_ROUTES.studyPlanVersions, { token })
      .then(setVersions)
      .catch(() => setVersions([]));
  }, [token, plan?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!token) return;
    apiFetch<UserProfilePublic>(API_ROUTES.profile, { token })
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setProfileLoaded(true));
  }, [token]);

  const fetchGate = useCallback(() => {
    if (!token) return;
    apiFetch<PlacementGate>(API_ROUTES.placementGate, { token })
      .then(setGate)
      .catch(() => setGate(null));
  }, [token]);

  const generate = useCallback(
    async (attemptId: string | null, source: "rule" | "llm" = "rule", force = false) => {
      if (!token) return;
      setBusy(true);
      setError(null);
      try {
        const p = await apiFetch<StudyPlanPublic>(API_ROUTES.studyPlanGenerate, {
          method: "POST",
          token,
          body: JSON.stringify({
            attempt_id: attemptId,
            source,
            force,
          }),
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
        if (p === null) {
          setNone(true);
          // Chưa có kế hoạch ≠ chưa làm test đầu vào. Hai đường đó phải khác
          // nhau trên màn hình — người đã làm test mà quên bấm "Tạo kế hoạch"
          // ở trang kết quả không thể quay lại bằng CTA "Làm bài test".
          fetchGate();
        } else {
          setPlan(p);
          // Gate placement theo chân plan: mục "Kiểm tra lại" phải nói được
          // cửa mở lúc nào khi cooldown 7 ngày còn chặn — lịch không tự dời
          // ngày để né cửa, và người học đến đúng ô hẹn thì cần biết còn bao
          // lâu nữa, không phải bấm vào một tường "chưa tới lượt".
          if (p.items.some((i) => !i.done && i.kind === "mini_test")) {
            apiFetch<PlacementGate>(API_ROUTES.placementGate, { token })
              .then(setGate)
              .catch(() => setGate(null));
          }
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Không tải được kế hoạch."));
  }, [token, fetchGate]);

  // "Tạo kế hoạch" không được im lặng dựng lịch từ hồ sơ thiếu: chưa có
  // target/ngày thi thì MỞ MODAL với giá trị điền sẵn trước. `autoStarted`
  // giữ hiệu ứng `?from=` không bấm hai lần khi profile vừa load xong.
  const autoStarted = useRef(false);
  function startCreate(attemptId: string | null) {
    if (!profile?.target_score || !profile?.exam_date) {
      setNone(true);
      fetchGate();
      setModal({ attemptId });
      return;
    }
    void generate(attemptId);
  }

  async function createWithTargets(fields: TargetFields) {
    try {
      await patchTargets(fields);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được.");
      return;
    }
    const attemptId = modal?.attemptId ?? gate?.latest_attempt_id ?? null;
    setModal(null);
    await generate(attemptId);
  }

  useEffect(() => {
    if (!token) return;
    const t = window.setTimeout(() => {
      if (!from) {
        load();
        return;
      }
      if (!profileLoaded) return;
      // Kiểm kế hoạch hiện có TRƯỚC khi gọi generate: nút "Tạo kế hoạch học"
      // bấm lại từ cùng một kết quả thì chỉ GET xem lại — POST chỉ chạy khi
      // chưa có kế hoạch hoặc `from` là lượt placement khác (mới hơn).
      apiFetch<StudyPlanPublic | null>(API_ROUTES.studyPlan, { token })
        .then((p) => {
          if (p && p.placement_attempt_id === from) {
            setPlan(p);
          } else if (!autoStarted.current) {
            autoStarted.current = true;
            startCreate(from);
          }
        })
        .catch(() => {
          if (!autoStarted.current) {
            autoStarted.current = true;
            startCreate(from);
          }
        });
    }, 0);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from, load, token, profileLoaded, profile]);

  async function tickItem(item: StudyPlanItemPublic, done: boolean) {
    if (!token) return;
    setError(null);
    try {
      // Server trả lại cả kế hoạch đã tính lại ngày (tick làm hàng đợi trôi),
      // nên một PATCH là đủ — không GET lại.
      setPlan(
        await apiFetch<StudyPlanPublic>(API_ROUTES.studyPlanItemTick(item.position), {
          method: "PATCH",
          token,
          body: JSON.stringify({ done }),
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được tick.");
    }
  }

  async function patchTargets(fields: TargetFields) {
    if (!token) return;
    // Gửi rõ cả key để trống = NULL: PATCH phân biệt "xoá" với "bỏ qua",
    // và một `field or existing` sẽ biến "xoá ngày thi" thành no-op im lặng.
    const updated = await apiFetch<UserProfilePublic>(API_ROUTES.profile, {
      method: "PATCH",
      token,
      body: JSON.stringify({
        target_score: fields.target === "" ? null : Number(fields.target),
        exam_date: fields.exam === "" ? null : fields.exam,
        minutes_per_day: fields.minutes === "" ? null : Number(fields.minutes),
        study_days_per_week: fields.days === "" ? null : Number(fields.days),
      }),
    });
    setProfile(updated);
  }

  async function saveTargets(fields: TargetFields) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await patchTargets(fields);
      // Ngày thi/quỹ thời gian đổi là lịch đổi (packing theo phút, nhịp theo
      // tuần) — sinh lại force để phần đã qua không còn là danh sách cũ dán
      // trên lịch mới.
      if (plan) await generate(null, "rule", true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không lưu được.");
    } finally {
      setBusy(false);
    }
  }

  async function pickMock(item: StudyPlanItemPublic, testId: string) {
    if (!token) return;
    setError(null);
    try {
      setPlan(
        await apiFetch<StudyPlanPublic>(API_ROUTES.studyPlanItemTick(item.position), {
          method: "PATCH",
          token,
          body: JSON.stringify({ test_id: testId }),
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đổi được đề thi thử.");
    }
  }

  async function repack() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      setPlan(
        await apiFetch<StudyPlanPublic>(API_ROUTES.studyPlanRepack, {
          method: "POST",
          token,
          body: JSON.stringify({}),
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không dời được lịch.");
    } finally {
      setBusy(false);
    }
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
    // Hai trạng thái, một màn hình. Trước đây chỉ có một: ai làm test đầu vào
    // xong mà rời trang kết quả chưa bấm "Tạo kế hoạch" thì kẹt — CTA duy nhất
    // đưa họ đi làm lại bài test đã làm rồi (và còn bị cooldown chặn).
    const donePlacement = Boolean(gate?.latest_attempt_id);
    const resuming = Boolean(gate?.in_progress_attempt_id);
    return (
      <Page className="max-w-2xl">
        <PageHeader
          eyebrow="Kế hoạch học"
          title="Chưa có kế hoạch"
          description={
            donePlacement
              ? resuming
                ? "Bạn đang có một bài test đầu vào làm dở — học xong nó rồi kế hoạch sẽ có đủ số liệu."
                : "Bạn đã làm bài test đầu vào. Kế hoạch đọc kết quả đó để biết nên học gì trước."
              : "Làm bài test đầu vào để kế hoạch biết bạn đang ở đâu."
          }
        />
        <div className="mt-6 flex flex-wrap gap-3">
          {donePlacement && !resuming && (
            <Button disabled={busy} onClick={() => startCreate(gate?.latest_attempt_id ?? null)}>
              {busy ? "Đang dựng…" : "Tạo kế hoạch học"}
            </Button>
          )}
          {resuming && <ButtonLink href="/learn/placement">Tiếp tục bài test</ButtonLink>}
          <ButtonLink href="/learn/placement" variant="secondary">
            {donePlacement ? "Xem lại bài test đầu vào" : "Làm bài test đầu vào"}
          </ButtonLink>
        </div>
        {donePlacement && !resuming && (
          <div className="mt-5">
            <Alert tone="info">
              Chưa có mục tiêu và ngày thi trong hồ sơ — bấm “Tạo kế hoạch học” sẽ mở hộp thông tin
              với giá trị điền sẵn.
            </Alert>
          </div>
        )}
        {modal && (
          <CreatePlanModal
            profile={profile}
            busy={busy}
            onSubmit={createWithTargets}
            onClose={() => setModal(null)}
          />
        )}
      </Page>
    );
  }

  // `done_count` đếm mục LÕI (kế hoạch thật khép được); nhịp nền không bao giờ
  // xong và cũng không được kéo mẫu số "0/88 mục" xuống — người học cần thấy
  // mình đã đi hết lời khuyên, không phải một tỉ lệ vĩnh viễn rẻ.
  const core = plan.items.filter(isCorePlanItem);
  const allDone = core.length > 0 && plan.done_count === core.length;
  // Mục chưa xong có ngày hẹn TRƯỚC hôm nay = người học đang trễ lịch. Lịch
  // không tự trôi (điều đã chốt), nên đây là tín hiệu duy nhất và đường duy
  // nhất là nút "Dời lịch" bên dưới lưới.
  const missed = plan.items.some((i) => !i.done && i.day != null && i.day < plan.today);

  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Kế hoạch học"
        title={allDone ? "Kế hoạch đã hoàn thành" : "Kế hoạch dựa trên bài test đầu vào"}
        description={
          allDone
            ? "Bạn đã đi hết lời khuyên mà bài test đầu vào đưa ra."
            : "Ưu tiên các kỹ năng yếu nhất trước. Tick một mục sau khi bạn thực sự hoàn thành việc học."
        }
      />

      {allDone && (
        <Panel className="mt-6 p-6 text-center">
          <p className="text-label font-semibold uppercase text-ink-faint">Hoàn thành</p>
          <p className="mt-2 font-data text-title font-semibold tabular-nums">
            {plan.done_count}/{core.length}
          </p>
          <p className="mt-2 max-w-md mx-auto text-small text-ink-muted">
            {plan.target_score !== null
              ? `Bước kiểm chứng tốt nhất bây giờ: một đề thi thử — xem bạn đã tiến gần ${plan.target_score} điểm mục tiêu chưa.`
              : "Bước kiểm chứng tốt nhất bây giờ: một đề thi thử — xem trình độ đã nhích bao nhiêu."}
          </p>
          {/* Không có nút "đo lại" ở đây: allDone vừa đóng bằng một bài nộp
              gần nhất thì cooldown 7 ngày CHẮC CHẮN còn chặn — một nút bấm
              ra tường lỗi không phải bước tiếp theo. Nhịp đo đã có lịch lo;
              kiểm chứng cuối kế hoạch là đề thi thử. */}
          <div className="mt-4 flex flex-wrap justify-center gap-3">
            <ButtonLink href="/learn/tests">Làm đề thi thử</ButtonLink>
          </div>
        </Panel>
      )}

      <Panel className={cx("p-4", allDone && "mt-4")}>
        <p className="text-label font-semibold uppercase text-ink-faint">Bạn đang ở đâu</p>
        {/* Hai con số phải đọc được từ xa: đang ở đâu và đích là đâu. Phần chữ
            nhỏ bên dưới là ngữ cảnh, không phải nội dung chính. */}
        <div className="mt-2 flex flex-wrap items-end gap-x-10 gap-y-3">
          <div>
            <p className="text-label font-semibold uppercase text-ink-faint">Ước lượng hiện tại</p>
            <p className="font-data text-hero leading-none tabular-nums">
              {plan.estimate?.total ?? "—"}
            </p>
            {plan.estimate && (
              <p className="mt-1.5 text-small text-ink-muted">
                trong khoảng {plan.estimate.band_low}–{plan.estimate.band_high} ·{" "}
                {plan.estimate.cefr}
              </p>
            )}
          </div>
          <div>
            <p className="text-label font-semibold uppercase text-ink-faint">Điểm mục tiêu</p>
            <p className="font-data text-hero leading-none tabular-nums text-accent">
              {profile?.target_score ?? plan.target_score ?? "—"}
            </p>
            {plan.gap != null && (
              <p className="mt-1.5 text-small text-ink-muted">
                {plan.gap > 0 ? `còn ${Math.abs(plan.gap)} điểm tới đích` : "đã vượt mục tiêu"}
              </p>
            )}
          </div>
        </div>
        {plan.feasibility && (
          <div className="mt-2">
            <FeasibilityTag value={plan.feasibility} />
          </div>
        )}

        {/* Mục tiêu/ngày thi sống chung với "bạn đang ở đâu": hai cái là một
            câu hỏi duy nhất — cách đích bao xa, và mình nói mình đi thế nào. */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-rule pt-3">
          <span className="inline-flex items-center gap-1.5 text-small text-ink-muted">
            <Calendar size={14} strokeWidth={2} aria-hidden />
            Ngày thi:{" "}
            <span className="font-data tabular-nums text-ink">
              {(() => {
                const d = profile?.exam_date ?? plan.exam_date;
                return d ? new Date(d).toLocaleDateString("vi-VN") : "—";
              })()}
            </span>
            {plan.days_left != null && plan.days_left >= 0 && (
              <span className="text-ink-faint">(còn {plan.days_left} ngày)</span>
            )}
          </span>
          <span className="ml-auto inline-flex items-center gap-3">
            <span className="text-small font-semibold text-ink-muted">
              {plan.done_count}/{core.length} mục đã xong
            </span>
            <button
              type="button"
              onClick={() => setEditing(!editing)}
              aria-label="Sửa mục tiêu, ngày thi, thời gian học"
              aria-expanded={editing}
              className="text-ink-faint hover:text-ink"
            >
              <Pencil size={14} strokeWidth={2} aria-hidden />
            </button>
          </span>
        </div>

        <button
          type="button"
          onClick={() => setDetailsOpen(!detailsOpen)}
          aria-expanded={detailsOpen}
          className="mt-3 text-small font-semibold text-ink-muted underline-offset-2 hover:text-ink hover:underline"
        >
          {detailsOpen ? "Ẩn chi tiết" : "Xem chi tiết — phân tích theo dạng câu"}
        </button>
        {detailsOpen && plan.top_focus.length > 0 && (
          <Panel className="mt-3 p-4">
            <p className="text-label font-semibold uppercase text-ink-faint">Theo dạng câu</p>
            <p className="mt-1 text-small text-ink-muted">
              Phân loại từng câu sai trong test đầu vào — bấm một ô để luyện đúng dạng đó.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {plan.top_focus.map((f) => (
                <Link
                  key={f.code}
                  href={`/learn/parts/${f.part}/drill?labels=${encodeURIComponent(f.code)}`}
                  className="rounded border border-rule bg-recess px-2.5 py-1 text-small text-ink hover:border-rule-strong"
                >
                  {f.label}{" "}
                  <span className="font-data tabular-nums text-ink-faint">
                    {f.correct}/{f.total}
                  </span>
                </Link>
              ))}
            </div>
          </Panel>
        )}
        {detailsOpen && <PlanWhy plan={plan} target={profile?.target_score ?? plan.target_score} />}
        <TargetForm
          open={editing}
          onClose={() => setEditing(false)}
          initialTarget={profile?.target_score ?? plan.target_score}
          initialExam={profile?.exam_date ?? plan.exam_date}
          initialMinutes={profile?.minutes_per_day ?? null}
          initialDays={profile?.study_days_per_week ?? null}
          busy={busy}
          onSave={saveTargets}
        />
      </Panel>

      <Panel className="mt-4 p-3">
        <p className="mb-2 px-1 text-label font-semibold uppercase text-ink-faint">
          Lịch học — {plan.minutes_per_day}′ × {plan.study_days_per_week} ngày mỗi tuần
        </p>
        <PlanCalendar plan={plan} onTick={tickItem} onPickMock={pickMock} placementGate={gate} />
        <p className="mt-2 px-1 text-small text-ink-muted">
          Chọn một ngày để xem và đánh dấu các việc cần làm trong ngày đó.
        </p>
        {missed && (
          <div className="mt-2 flex flex-wrap items-center gap-3 px-1">
            <p className="text-small text-warn">
              Vài mục đã hẹn đang nằm sau bạn — lịch không tự dồn lên khi bạn trễ.
            </p>
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => void repack()}>
              Dời phần còn lại từ hôm nay
            </Button>
          </div>
        )}
      </Panel>

      <ProgressPanel plan={plan} evaluation={evaluation} versions={versions} busy={busy} />

      <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-rule pt-5">
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

type TargetFields = { target: string; exam: string; minutes: string; days: string };

/**
 * Khối "vì sao" trong Xem chi tiết. CẤU TRÚC, không phải chuỗi: cùng số đó
 * server trả trong `why` cho API/test, còn màn hình thì quyền in đậm con số
 * và badge hóa dòng đầu — parse lại văn bản để tô đậm là hai nguồn chữ trôi
 * nhau, còn dựng từ field thì chỉ có một nguồn số.
 */
function PlanWhy({ plan, target }: { plan: StudyPlanPublic; target: number | null }) {
  if (!plan.estimate) {
    return plan.why ? (
      <p className="mt-3 text-small whitespace-pre-line text-ink-muted">{plan.why}</p>
    ) : null;
  }
  const est = plan.estimate;
  const weekly = plan.minutes_per_day * plan.study_days_per_week;
  const num = (children: ReactNode) => (
    <span className="font-data font-semibold tabular-nums text-ink">{children}</span>
  );
  const chip = "rounded border border-rule bg-recess px-2.5 py-1 text-small";
  return (
    <div className="mt-3 space-y-3 text-small text-ink-muted">
      <div className="flex flex-wrap gap-2">
        <span className={chip}>
          {num(est.total)}
          {target != null ? (
            <>
              {" → "}
              {num(target)} điểm
            </>
          ) : (
            " điểm ước lượng"
          )}
        </span>
        {plan.weeks_left != null && <span className={chip}>{num(plan.weeks_left)} tuần</span>}
        <span className={chip}>{num(weekly)} phút/tuần</span>
        {plan.feasibility && <FeasibilityTag value={plan.feasibility} />}
      </div>
      <p>
        Bài test đầu vào ước lượng bạn đang ở mức {num(`${est.total} điểm`)} (Nghe{" "}
        {num(est.listening)} · Đọc {num(est.reading)},{" "}
        <span className="font-semibold text-ink">{est.cefr}</span>)
        {target != null && plan.gap != null && plan.gap > 0 ? (
          <>
            , còn cách mục tiêu {num(`${target} điểm`)} khoảng {num(plan.gap)} điểm.
          </>
        ) : target != null ? (
          <>, đã chạm mục tiêu {num(`${target} điểm`)}.</>
        ) : (
          "."
        )}
      </p>
      {plan.top_focus.length > 0 && (
        <p>
          Kế hoạch ưu tiên những kỹ năng yếu nhất:{" "}
          {plan.top_focus.map((f, i) => (
            <span key={f.code}>
              {i > 0 && (
                <span aria-hidden className="text-ink-faint">
                  {" → "}
                </span>
              )}
              <span className="font-semibold text-ink">{f.label}</span>
            </span>
          ))}
          .
        </p>
      )}
      {plan.top_focus.length > 0 && (
        <p>
          Các kỹ năng đã mạnh chỉ được bố trí một phần nhỏ để duy trì, không chiếm ngân sách luyện
          tập chính.
        </p>
      )}
      <p>Điểm số là ước lượng từ bài test đầu vào, không phải điểm chính thức.</p>
    </div>
  );
}

/** Mặc định ngày thi = hôm nay + 3 tháng, tính theo lịch máy người dùng —
 * kế hoạch dựng từ hôm nay thì mốc "3 tháng" phải là 3 tháng của họ. */
function examDefault(): string {
  const d = new Date();
  d.setMonth(d.getMonth() + 3);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function CreatePlanModal({
  profile,
  busy,
  onSubmit,
  onClose,
}: {
  profile: UserProfilePublic | null;
  busy: boolean;
  onSubmit: (fields: TargetFields) => Promise<void> | void;
  onClose: () => void;
}) {
  const [fields, setFields] = useState<TargetFields>({
    target: String(profile?.target_score ?? 600),
    exam: profile?.exam_date ?? examDefault(),
    days: String(profile?.study_days_per_week ?? 6),
    minutes: String(profile?.minutes_per_day ?? 30),
  });
  const set = (key: keyof TargetFields) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setFields({ ...fields, [key]: event.target.value });
  return (
    <div
      role="presentation"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-label="Thông tin dựng kế hoạch học"
        onClick={(event) => event.stopPropagation()}
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmit(fields);
        }}
        className="w-full max-w-md rounded border border-rule bg-panel p-5"
      >
        <p className="text-label font-semibold uppercase text-ink-faint">Tạo kế hoạch học</p>
        <p className="mt-1 text-small text-ink-muted">
          Kế hoạch cần bốn con số này. Đã điền sẵn giá trị thường dùng — sửa nếu bạn muốn.
        </p>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Điểm mục tiêu" hint="10–990, bước 5.">
            <Input
              type="number"
              autoComplete="off"
              min={10}
              max={990}
              step={5}
              value={fields.target}
              onChange={set("target")}
            />
          </Field>
          <Field label="Ngày thi dự kiến">
            <Input type="date" value={fields.exam} onChange={set("exam")} />
          </Field>
          <Field label="Buổi học mỗi tuần" hint="1–7.">
            <Input
              type="number"
              autoComplete="off"
              min={1}
              max={7}
              value={fields.days}
              onChange={set("days")}
            />
          </Field>
          <Field label="Phút mỗi buổi" hint="5–480.">
            <Input
              type="number"
              autoComplete="off"
              min={5}
              max={480}
              step={5}
              value={fields.minutes}
              onChange={set("minutes")}
            />
          </Field>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Hủy
          </Button>
          <Button type="submit" size="sm" disabled={busy}>
            {busy ? "Đang dựng…" : "Dựng kế hoạch"}
          </Button>
        </div>
      </form>
    </div>
  );
}

/** §10: ba nhãn feasibility, không lời hứa nào. Màu theo tone đã có, chữ
 * Việt để "FEASIBLE" không lọt vào mặt người học như một HTTP code. */
function FeasibilityTag({ value }: { value: "FEASIBLE" | "CHALLENGING" | "HIGH_RISK" }) {
  const [tone, label] =
    value === "FEASIBLE"
      ? (["ok", "Khả thi với lịch hiện tại"] as const)
      : value === "CHALLENGING"
        ? (["warn", "Khá sát — cần học đều"] as const)
        : (["alert", "Khó đạt với lịch hiện tại"] as const);

  return <Tag tone={tone}>{label}</Tag>;
}

/**
 * Chỉnh mục tiêu + ngày thi + quỹ thời gian NGAY TRÊN trang kế hoạch.
 *
 * Đây là bản sao tối giản của khối "Mục tiêu ôn thi" ở `/profile` — cùng ghi
 * vào `user_profile`, không có bản thứ hai của các cột này. Để trống = xoá
 * (PATCH phân biệt null với vắng mặt). Sau khi lưu, trang sinh lại kế hoạch
 * force: bốn ô này là đúng bộ đầu vào của planner — sửa cái nào cũng đổi
 * lịch, mà lịch dựng từ đầu vào cũ thì không còn là kế hoạch cho người này.
 */
function TargetForm({
  open,
  onClose,
  initialTarget,
  initialExam,
  initialMinutes,
  initialDays,
  busy,
  onSave,
}: {
  initialTarget: number | null;
  initialExam: string | null;
  initialMinutes: number | null;
  initialDays: number | null;
  busy: boolean;
  open: boolean;
  onClose: () => void;
  onSave: (fields: {
    target: string;
    exam: string;
    minutes: string;
    days: string;
  }) => Promise<void> | void;
}) {
  const [target, setTarget] = useState(initialTarget?.toString() ?? "");
  const [exam, setExam] = useState(initialExam ?? "");
  const [minutes, setMinutes] = useState(initialMinutes?.toString() ?? "");
  const [days, setDays] = useState(initialDays?.toString() ?? "");

  if (!open) return null;
  return (
    <form
      className="mt-3 flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave({ target, exam, minutes, days });
        onClose();
      }}
    >
      <Field label="Điểm mục tiêu" hint="10–990, bước 5.">
        <Input
          type="number"
          autoComplete="off"
          min={10}
          max={990}
          step={5}
          value={target}
          onChange={(event) => setTarget(event.target.value)}
          placeholder="750"
        />
      </Field>
      <Field label="Ngày thi dự kiến">
        <Input type="date" value={exam} onChange={(event) => setExam(event.target.value)} />
      </Field>
      <Field label="Phút mỗi ngày" hint="5–480. Mặc định 30′.">
        <Input
          type="number"
          autoComplete="off"
          min={5}
          max={480}
          step={5}
          value={minutes}
          onChange={(event) => setMinutes(event.target.value)}
          placeholder="30"
        />
      </Field>
      <Field label="Ngày học mỗi tuần" hint="1–7. Mặc định 7.">
        <Input
          type="number"
          autoComplete="off"
          min={1}
          max={7}
          value={days}
          onChange={(event) => setDays(event.target.value)}
          placeholder="7"
        />
      </Field>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy}>
          Lưu & dựng lại lịch
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => {
            setTarget(initialTarget?.toString() ?? "");
            setExam(initialExam ?? "");
            setMinutes(initialMinutes?.toString() ?? "");
            setDays(initialDays?.toString() ?? "");
            onClose();
          }}
        >
          Hủy
        </Button>
      </div>
    </form>
  );
}

/** §31 bản gọn: tuần từ lịch ĐANG HIỂN THỊ (group ngay client trên
 * `plan.items` — ngày đã pack sẵn ở payload, tính lại phía server là thêm
 * một nguồn có thể lệch với cái người học đang nhìn). Series + trend đến từ
 * `/evaluation` — cái đó cần câu truy vấn, không suy ra từ lịch được. */
function ProgressPanel({
  plan,
  evaluation,
  versions,
  busy,
}: {
  plan: StudyPlanPublic;
  evaluation: PlanEvaluationPublic | null;
  versions: PlanVersionPublic[];
  busy: boolean;
}) {
  const rows = useMemo(() => {
    const start = new Date(`${plan.starts_at}T12:00:00`);
    const weeks = new Map<number, { due: number; done: number; minutes: number }>();
    for (const item of plan.items) {
      if (!item.day || !isCorePlanItem(item)) continue;
      const idx = Math.max(
        0,
        Math.floor((new Date(`${item.day}T12:00:00`).getTime() - start.getTime()) / 604_800_000),
      );
      const bucket = weeks.get(idx) ?? { due: 0, done: 0, minutes: 0 };
      bucket.due += 1;
      if (item.done) {
        bucket.done += 1;
        bucket.minutes += item.est_minutes ?? 0;
      }
      weeks.set(idx, bucket);
    }
    return [...weeks.entries()]
      .filter(([, w]) => w.due > 0)
      .sort((a, b) => a[0] - b[0])
      .slice(0, 10);
  }, [plan]);
  // Phút THẬT (`elapsed_seconds` của các lượt nộp) từ /evaluation — phút ước
  // lượng của mục chỉ để đếm việc, không phải bằng chứng ngồi bàn.
  const real = new Map((evaluation?.weeks ?? []).map((w) => [w.index, w]));
  const realOf = (idx: number) => real.get(idx)?.minutes ?? null;
  const series = evaluation?.retakes ?? [];
  const stale = evaluation?.new_diagnostic && !busy;

  return (
    <Panel className="mt-4 p-4">
      <p className="text-label font-semibold uppercase text-ink-faint">Tuần &amp; tiến bộ</p>
      {series.length > 0 && (
        <p className="mt-2 flex flex-wrap items-center gap-1.5 font-data text-body tabular-nums">
          {series.map((r, i) => (
            <span key={r.attempt_id} className="inline-flex items-center gap-1.5">
              {i > 0 && (
                <span className="text-ink-faint" aria-hidden>
                  →
                </span>
              )}
              <span
                className={cx(
                  "font-semibold",
                  i === series.length - 1 ? "text-ink" : "text-ink-muted",
                )}
              >
                {r.total_scaled}
              </span>
            </span>
          ))}
          <span className="text-small font-normal text-ink-faint">
            điểm đo lại qua các bài kiểm tra trên lịch
          </span>
        </p>
      )}
      {evaluation?.trend.length ? (
        <ul className="mt-2 space-y-1 text-small">
          {evaluation.trend.slice(0, 5).map((t) => (
            <li key={t.code} className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-ink">{t.label}</span>
              <span className="font-data tabular-nums text-ink-faint">
                {t.baseline_total > 0
                  ? `${Math.round((t.baseline_correct / t.baseline_total) * 100)}%`
                  : "—"}
                {" → "}
                {t.recent_total > 0
                  ? `${Math.round((t.recent_correct / t.recent_total) * 100)}%`
                  : "chưa đo lại"}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {rows.length > 0 && (
        <ul className="mt-3 grid grid-cols-2 gap-1.5 text-small sm:grid-cols-5">
          {rows.map(([idx, w]) => (
            <li
              key={idx}
              className={cx(
                "rounded border border-rule px-2 py-1.5",
                w.done === w.due ? "border-ok/40 bg-ok-tint" : "bg-recess",
              )}
            >
              <p className="text-label font-semibold uppercase text-ink-faint">Tuần {idx + 1}</p>
              <p className="font-data tabular-nums text-ink">
                {w.done}/{w.due}
                {realOf(idx) != null ? (
                  <span className="ml-1 text-label font-normal text-ink-faint">
                    {realOf(idx)}&apos; thật
                  </span>
                ) : (
                  w.minutes > 0 && (
                    <span className="ml-1 text-label font-normal text-ink-faint">
                      ~{w.minutes}&apos;
                    </span>
                  )
                )}
              </p>
              {(() => {
                const cur = realOf(idx);
                const prev = realOf(idx - 1);
                if (cur == null || prev == null || cur === prev) return null;
                const delta = cur - prev;
                return (
                  <p className={cx("text-label", delta > 0 ? "text-ok" : "text-ink-faint")}>
                    {delta > 0 ? "+" : "−"}
                    {Math.abs(delta)}&apos; so với tuần trước
                  </p>
                );
              })()}
            </li>
          ))}
        </ul>
      )}
      {stale && (
        <p className="mt-3 text-small text-warn">
          Bạn đã có bài đo mới — kế hoạch hiện hành vẫn đang bám số cũ. Quay lại trang này khi sẵn
          sàng và bấm “Sinh lại” để dựng phiên bản mới từ kết quả mới nhất.
        </p>
      )}
      {versions.length > 1 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-small font-semibold text-ink-muted hover:text-ink">
            Phiên bản kế hoạch ({versions.length})
          </summary>
          <ul className="mt-2 space-y-1 text-small">
            {versions.map((v) => (
              <li key={v.id} className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-data font-semibold tabular-nums text-ink">v{v.version}</span>
                <span className="text-ink-muted">{v.reason ?? "Không rõ từ trước"}</span>
                <span className="text-ink-faint">
                  {new Date(v.created_at).toLocaleDateString("vi-VN")}
                </span>
                {v.is_current && <Tag tone="neutral">hiện hành</Tag>}
                <span className="text-ink-faint">· {v.item_count} mục</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Panel>
  );
}
