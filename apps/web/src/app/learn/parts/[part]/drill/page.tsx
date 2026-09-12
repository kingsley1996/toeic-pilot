"use client";

import { API_ROUTES, type PartSessionDetail, type PartSummary } from "@toeic-pilot/shared";
import { History, Lock } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { LoginModal } from "@/components/login-modal";
import { Button, EmptyState, Page, PageHeader, Panel, Select, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";
import { getPartMeta } from "@/lib/parts";

/**
 * Màn bắt đầu phiên luyện — CHỌN rồi mới VÀO, như vào đề thi.
 *
 * Checkbox nhãn theo đúng khuôn "Chọn phần muốn làm" của `tests/[slug]/[test]`:
 * không chọn = làm TẤT CẢ, nhiều nhãn là hợp câu. Không chọn số câu: một phiên
 * lấy toàn bộ kho, thứ người học chỉnh là đồng hồ.
 */

// 5..135 phút, mỗi bước 5 — 135 là trần của đề thi TOEIC cả hai kỹ năng.
const MINUTES = Array.from({ length: 27 }, (_, i) => (i + 1) * 5);

/* `?labels=` từ mục kế hoạch ("Luyện Part 7 — Câu hỏi suy luận") mở màn hình
   này với đúng dạng câu đã chọn sẵn — lời khuyên chỉ tới tay người học khi nó
   còn lại MỘT cú bấm. useSearchParams đòi Suspense, khuôn như /learn/plan. */
export default function PartDrillSetupPage() {
  return (
    <Suspense
      fallback={
        <Page className="max-w-3xl">
          <SkeletonList rows={3} />
        </Page>
      }
    >
      <WithPreselectedLabels />
    </Suspense>
  );
}

function WithPreselectedLabels() {
  const search = useSearchParams();
  return <DrillSetup initialLabels={(search.get("labels") ?? "").split(",").filter(Boolean)} />;
}

function DrillSetup({ initialLabels }: { initialLabels: string[] }) {
  const meta = getPartMeta(String(useParams().part));
  const router = useRouter();
  const { status, token } = useSession();
  const [summary, setSummary] = useState<PartSummary | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set(initialLabels));
  const [minutes, setMinutes] = useState<number | null>(null);
  const [gated, setGated] = useState(false);
  // Hộp đăng nhập cho khách gõ thẳng URL — đóng được để quay về hub.
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!meta) return;
    apiFetch<PartSummary[]>(API_ROUTES.practiceParts)
      .then((all) => setSummary(all.find((p) => String(p.part) === String(meta.part)) ?? null))
      .catch(() => setError("Không tải được dữ liệu phần này."));
  }, [meta]);

  if (!meta) {
    return (
      <Page className="max-w-3xl">
        <PageHeader
          title="Không có phần này"
          description="Bài thi TOEIC có bảy phần, từ 1 đến 7."
        />
      </Page>
    );
  }

  // Chặn đầu URL (khuôn trang đề chi tiết): bấm nút đã có hộp đăng nhập riêng,
  // còn đây là bắt người gõ thẳng hay mở lại dấu trang.
  if (status === "anonymous") {
    return (
      <Page className="max-w-3xl">
        <div className="mt-4">
          <EmptyState
            icon={Lock}
            title="Đăng nhập để luyện"
            description={
              <>
                Luyện theo part <strong className="font-semibold text-ink">miễn phí</strong>. Đăng
                nhập để lưu tiến độ và có trải nghiệm học tập tốt hơn.
              </>
            }
          />
        </div>
        <LoginModal
          open={!dismissed}
          onClose={() => setDismissed(true)}
          onSuccess={() => setDismissed(true)}
          next={`/learn/parts/${meta.part}/drill`}
          title="Đăng nhập để luyện"
        />
      </Page>
    );
  }

  const labels = summary?.labels ?? [];
  const isAll = chosen.size === 0 || chosen.size === labels.length;
  const selectedCount = isAll
    ? (summary?.question_count ?? 0)
    : labels.filter((l) => chosen.has(l.code)).reduce((sum, l) => sum + l.count, 0);

  function toggle(code: string) {
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  async function start() {
    if (!token) {
      setGated(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const sess = await apiFetch<PartSessionDetail>(API_ROUTES.partCreateSession(meta!.part), {
        method: "POST",
        token,
        body: JSON.stringify({
          labels: isAll ? [] : [...chosen],
          time_limit_minutes: minutes,
        }),
      });
      router.push(`/learn/parts/sessions/${sess.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tạo được phiên.");
      setBusy(false);
    }
  }

  return (
    <Page className="max-w-3xl">
      <div className="flex items-center justify-between gap-4">
        <Breadcrumbs
          trail={[
            { href: "/learn/parts", label: "Luyện theo phần" },
            { href: `/learn/parts/${meta.part}`, label: `Part ${meta.part}` },
          ]}
        />
        <Link
          href="/learn/parts/sessions"
          className="inline-flex shrink-0 items-center gap-1.5 text-small font-semibold text-ink-muted hover:text-ink"
        >
          <History size={13} strokeWidth={2} aria-hidden />
          Lịch sử luyện tập
        </Link>
      </div>
      <PageHeader
        eyebrow={`Part ${meta.part} · ${meta.title}`}
        title="Bắt đầu phiên luyện"
        description="Chọn nhãn muốn luyện (hoặc tất cả) và thời gian. Phiên được lưu và xem lại được."
      />

      {!summary && !error && <SkeletonList rows={3} />}

      {summary && (
        <>
          <section className="mt-6">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-label font-semibold uppercase text-ink-faint">
                Chọn nhãn muốn luyện
              </h2>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setChosen(new Set(labels.map((l) => l.code)))}
                  disabled={labels.length === 0}
                  className="text-small font-semibold text-ink-muted hover:text-ink disabled:opacity-50"
                >
                  Chọn tất cả
                </button>
                <button
                  type="button"
                  onClick={() => setChosen(new Set())}
                  className="text-small font-semibold text-ink-muted hover:text-ink"
                >
                  Bỏ chọn
                </button>
              </div>
            </div>
            <Panel className="mt-2 p-4">
              {labels.length === 0 ? (
                <p className="text-small text-ink-muted">
                  Phần này chưa có câu hỏi nào được gắn nhãn.
                </p>
              ) : (
                <div className="max-h-72 space-y-1.5 overflow-y-auto">
                  {labels.map((l) => (
                    <label
                      key={l.code}
                      className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 hover:bg-recess"
                    >
                      <input
                        type="checkbox"
                        checked={chosen.has(l.code)}
                        onChange={() => toggle(l.code)}
                        className="h-4 w-4 rounded border-rule-strong accent-action"
                      />
                      <span className="min-w-0 flex-1 truncate text-small font-semibold">
                        {l.title}
                      </span>
                      <span className="font-data text-small text-ink-faint">({l.count})</span>
                    </label>
                  ))}
                </div>
              )}

              <div className="mt-3 rounded border border-rule bg-recess px-3 py-2 text-small">
                {isAll ? (
                  <>
                    Toàn bộ <span className="font-data tabular-nums">{labels.length}</span> nhãn —{" "}
                    <span className="font-data tabular-nums">{summary.question_count}</span> câu
                  </>
                ) : (
                  <>
                    Đã chọn <span className="font-data tabular-nums">{chosen.size}</span> nhãn —{" "}
                    <span className="font-data tabular-nums">{selectedCount}</span> câu (có thể
                    trùng nhau giữa các nhãn)
                  </>
                )}
              </div>
            </Panel>
          </section>

          <section className="mt-6">
            <h2 className="text-label font-semibold uppercase text-ink-faint">Thời gian làm bài</h2>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <Select
                aria-label="Thời gian làm bài"
                value={minutes === null ? "" : String(minutes)}
                onChange={(e) => setMinutes(e.target.value ? Number(e.target.value) : null)}
                className="w-auto"
              >
                <option value="">Không giới hạn</option>
                {MINUTES.map((m) => (
                  <option key={m} value={m}>
                    {m} phút
                  </option>
                ))}
              </Select>
              <span className="text-small text-ink-muted">
                Hết giờ là nộp — câu chưa trả lời tính là sai.
              </span>
            </div>
          </section>

          {error && <p className="mt-3 text-small text-alert">{error}</p>}

          <div className="mt-6">
            <Button
              size="lg"
              className="w-full"
              disabled={busy || summary.question_count === 0}
              onClick={() => void start()}
            >
              {busy ? "Đang tạo phiên…" : "Bắt đầu làm bài"}
            </Button>
          </div>
        </>
      )}

      {gated && (
        <LoginModal
          open
          onClose={() => setGated(false)}
          onSuccess={() => void start()}
          next={`/learn/parts/${meta.part}/drill`}
          title="Đăng nhập để luyện theo part"
          description={
            <>
              Luyện theo part <strong className="font-semibold text-ink">miễn phí</strong>. Đăng
              nhập để lưu tiến độ và có trải nghiệm học tập tốt hơn.
            </>
          }
        />
      )}
    </Page>
  );
}
