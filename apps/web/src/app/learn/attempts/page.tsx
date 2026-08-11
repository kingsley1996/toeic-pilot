"use client";

import { API_ROUTES, type AttemptPage, type AttemptSummary } from "@toeic-pilot/shared";
import { ClipboardList, Clock } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ButtonLink, EmptyState, Page, PageHeader, Skeleton, Tag, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { clock } from "@/lib/attempt";
import { useRequireSession } from "@/lib/session";

/*
 * Lịch sử làm bài.
 *
 * Màn riêng chứ không nhét vào hồ sơ: đây là danh sách CÓ HÀNH ĐỘNG — tiếp tục
 * bài dở, xem lại bài đã chấm — còn `/profile` trả lời "tôi đã học được gì" bằng
 * thống kê. Trộn hai loại đó lại thì trang hồ sơ dài ra mà không ai tìm thấy nút
 * mình cần.
 *
 * Bài đang dở đứng riêng ở trên cùng, không xếp lẫn theo thời gian. Đồng hồ của
 * chúng vẫn chạy ở máy chủ dù người học đã đóng tab, nên chúng là việc cần làm
 * ngay chứ không phải lịch sử.
 */

type Filter = "all" | "in_progress" | "done";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "Tất cả" },
  { value: "in_progress", label: "Đang làm dở" },
  { value: "done", label: "Đã nộp" },
];

export default function AttemptHistoryPage() {
  const { status, token } = useRequireSession();
  const [rows, setRows] = useState<AttemptSummary[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    apiFetch<AttemptPage>(API_ROUTES.attempts, { token })
      .then((data) => {
        if (!cancelled) setRows(data.items);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (status !== "authenticated" || rows === null) {
    return (
      <Page>
        <Skeleton className="h-8 w-52" />
        <Skeleton className="mt-6 h-24 w-full" />
        <Skeleton className="mt-3 h-24 w-full" />
      </Page>
    );
  }

  const unfinished = rows.filter((row) => row.status === "in_progress");
  const shown =
    filter === "all"
      ? rows
      : rows.filter((row) =>
          filter === "in_progress" ? row.status === "in_progress" : row.status !== "in_progress",
        );

  return (
    <Page>
      <PageHeader
        eyebrow="Luyện thi"
        title="Lịch sử làm bài"
        description="Bài đang dở vẫn chạy đồng hồ ở máy chủ — mở lại để làm tiếp trước khi hết giờ."
      />

      {rows.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="Bạn chưa làm đề nào"
          description="Chọn một bộ đề rồi bắt đầu — mỗi lượt làm sẽ được lưu lại ở đây."
          action={<ButtonLink href="/learn/tests">Xem bộ đề</ButtonLink>}
        />
      ) : (
        <>
          {unfinished.length > 0 && filter === "all" && (
            <p className="mt-6 text-small text-warn">
              Bạn có <span className="font-data tabular-nums">{unfinished.length}</span> bài đang
              làm dở.
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-1.5">
            {FILTERS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setFilter(option.value)}
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

          <div className="mt-4 space-y-3">
            {shown.map((row) => (
              <AttemptRow key={row.id} row={row} />
            ))}
            {shown.length === 0 && (
              <p className="text-small text-ink-muted">Không có lượt nào ở mục này.</p>
            )}
          </div>
        </>
      )}
    </Page>
  );
}

function AttemptRow({ row }: { row: AttemptSummary }) {
  const running = row.status === "in_progress";
  // Hết giờ nhưng chưa chốt: danh sách chỉ đọc, việc chấm để lần mở bài lo. Nói
  // ra ở đây để người học không tưởng mình còn kịp làm tiếp.
  const expired = running && row.remaining_seconds === 0;

  return (
    <Link
      href={`/learn/attempts/${row.id}`}
      className="block rounded border border-rule-strong bg-panel p-4 hover:border-action"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">{row.test_title}</p>
          <p className="mt-0.5 text-small text-ink-muted">
            {new Date(row.started_at).toLocaleString("vi-VN")}
            {row.scope !== "full" && " · một phần"}
            {row.review_mode === "practice" && " · luyện tập"}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {running ? (
            expired ? (
              <Tag tone="alert">Đã quá giờ</Tag>
            ) : (
              <Tag tone="warn">
                <Clock size={12} strokeWidth={2} aria-hidden />
                Còn{" "}
                {row.remaining_seconds === null ? "không giới hạn" : clock(row.remaining_seconds)}
              </Tag>
            )
          ) : (
            <Tag tone="ok">Đã nộp</Tag>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-small">
        {running ? (
          <span className="text-ink-muted">
            Đã trả lời{" "}
            <span className="font-data tabular-nums text-ink">
              {row.answered_count}/{row.question_count}
            </span>
          </span>
        ) : (
          <>
            <span className="text-ink-muted">
              Đúng{" "}
              <span className="font-data tabular-nums text-ink">
                {row.correct_count}/{row.question_count}
              </span>
            </span>
            {row.total_scaled !== null && (
              <span className="text-ink-muted">
                Điểm quy đổi{" "}
                <span className="font-data tabular-nums text-action-ink">{row.total_scaled}</span>
              </span>
            )}
          </>
        )}
        <span className="ml-auto font-semibold text-action-ink">
          {running ? "Làm tiếp" : "Xem kết quả"}
        </span>
      </div>
    </Link>
  );
}
