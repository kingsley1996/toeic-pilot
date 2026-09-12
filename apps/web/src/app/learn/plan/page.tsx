"use client";

import {
  API_ROUTES,
  type PlacementGate,
  type StudyPlanItemPublic,
  type StudyPlanPublic,
  type UserProfilePublic,
} from "@toeic-pilot/shared";
import { Calendar, Pencil } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

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

  // Mục tiêu/ngày thi SỬA được ngay trên màn này — nhưng nguồn sự thật vẫn là
  // `user_profile` (SPEC-PLACEMENT: một nguồn cho cả form placement lẫn profile),
  // nên đây chỉ là một cửa nữa ghi vào ô đó, không phải cột thứ hai.
  useEffect(() => {
    if (!token) return;
    apiFetch<UserProfilePublic>(API_ROUTES.profile, { token })
      .then(setProfile)
      .catch(() => setProfile(null));
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
          apiFetch<PlacementGate>(API_ROUTES.placementGate, { token })
            .then(setGate)
            .catch(() => setGate(null));
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

  async function saveTargets(fields: {
    target: string;
    exam: string;
    minutes: string;
    days: string;
  }) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
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
            <Button disabled={busy} onClick={() => void generate(gate?.latest_attempt_id ?? null)}>
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
              Mục tiêu và ngày thi lấy từ hồ sơ của bạn. Chưa nhập thì kế hoạch vẫn dựng được — chỉ
              là nó chưa biết bạn có bao nhiêu ngày.
            </Alert>
          </div>
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
        {detailsOpen && plan.why && <p className="mt-3 text-small text-ink-muted">{plan.why}</p>}
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

/** §10: ba nhãn feasibility, không lời hứa nào. Màu theo tone đã có, chữ
 * Việt để "FEASIBLE" không lọt vào mặt người học như một HTTP code. */
function FeasibilityTag({ value }: { value: "FEASIBLE" | "CHALLENGING" | "HIGH_RISK" }) {
  const [tone, label] =
    value === "FEASIBLE"
      ? (["ok", "Khả thi với nhịp này"] as const)
      : value === "CHALLENGING"
        ? (["warn", "Hơi sát — cần đều đặn"] as const)
        : (["alert", "Rủi ro cao so với lịch hiện tại"] as const);
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
