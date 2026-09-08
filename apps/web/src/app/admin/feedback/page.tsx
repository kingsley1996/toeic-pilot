"use client";

import {
  API_ROUTES,
  type FeedbackPublic,
  type FeedbackPage,
  type FeedbackStatus,
} from "@toeic-pilot/shared";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Page, PageHeader, Panel, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Duyệt góp ý của người học.
 *
 * `require_role("admin")` ở máy chủ, `canEdit` ở đây — duyệt là trao ruby, tức
 * chạm vào nền kinh tế, cùng ranh giới với `/admin/ruby`.
 *
 * Không có nút "trao thêm": mức thưởng là một HÀNG trong `ruby_rule`, sửa ở
 * `/admin/ruby`. Một ô nhập số ở đây sẽ là đường thứ hai đặt giá, và hai đường
 * đặt giá là hai con số sẽ lệch nhau.
 */

const TABS: { value: FeedbackStatus | "all"; label: string }[] = [
  { value: "pending", label: "Chờ xử lý" },
  { value: "approved", label: "Đã duyệt" },
  { value: "rejected", label: "Đã từ chối" },
  { value: "all", label: "Tất cả" },
];

const TYPE_LABEL: Record<string, string> = {
  bug: "Lỗi",
  feature: "Đề xuất",
  content: "Sai nội dung",
  other: "Khác",
};

export default function FeedbackAdminPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [tab, setTab] = useState<FeedbackStatus | "all">("pending");
  const [rows, setRows] = useState<FeedbackPublic[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  // `fetchPage` KHÔNG chạm state — nó chỉ đi lấy dữ liệu. Ghi state nằm ở
  // `.then`, không nằm trong thân effect: `react-hooks/set-state-in-effect` cấm
  // vế sau, và cấm có lý do — viết state từ trong effect làm render dây chuyền
  // và để nó trôi khỏi thứ nó đang mô tả. Cùng khuôn với `/admin/ruby`.
  const fetchPage = useCallback(() => {
    const query = tab === "all" ? "" : `?status=${tab}`;
    return apiFetch<FeedbackPage>(`${API_ROUTES.adminFeedback}${query}`, { token: token ?? "" });
  }, [tab, token]);

  const apply = useCallback((page: FeedbackPage) => {
    setRows(page.items);
    setTotal(page.total);
    setError(null);
  }, []);

  const onFailure = useCallback((failure: unknown, fallback: string) => {
    setError(failure instanceof ApiError ? failure.message : fallback);
  }, []);

  useEffect(() => {
    if (!token) return;
    fetchPage()
      .then(apply)
      .catch((failure) => onFailure(failure, "Không tải được danh sách."));
  }, [apply, fetchPage, onFailure, token]);

  async function act(id: string, path: string, body?: unknown) {
    if (!token) return;
    setBusy(id);
    try {
      await apiFetch(path, {
        method: "POST",
        token,
        body: JSON.stringify(body ?? {}),
      });
      apply(await fetchPage());
    } catch (actError) {
      onFailure(actError, "Thao tác không thành công.");
    } finally {
      setBusy(null);
    }
  }

  if (status !== "authenticated") return null;

  return (
    <Page>
      <PageHeader title="Góp ý" description={`${total} góp ý`} />

      <div className="mt-4 flex flex-wrap gap-2">
        {TABS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setTab(option.value)}
            aria-pressed={tab === option.value}
            className={cx(
              "rounded border px-3 py-1.5 text-small font-medium transition-colors",
              tab === option.value
                ? "border-action bg-action-tint text-action-ink"
                : "border-rule bg-panel hover:border-rule-strong",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      <div className="mt-5 space-y-3">
        {rows?.length === 0 && (
          <p className="text-small text-ink-muted">Không có góp ý nào trong mục này.</p>
        )}
        {rows?.map((row) => (
          <Panel key={row.id} className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="rounded border border-rule-strong px-2 py-0.5 text-label font-semibold uppercase">
                  {TYPE_LABEL[row.type] ?? row.type}
                </span>
                <StatusChip status={row.status} />
              </div>
              <p className="text-label text-ink-faint">
                {new Date(row.created_at).toLocaleString("vi-VN")}
              </p>
            </div>

            <p className="mt-3 whitespace-pre-wrap leading-relaxed">{row.description}</p>

            {(row.image_urls?.length ?? 0) > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {row.image_urls?.map((url) => (
                  // Mở thẳng URL trong tab mới thay vì dựng lightbox: ảnh chụp
                  // màn hình thường rộng hơn khung, và trình duyệt đã có sẵn
                  // phóng to.
                  <a key={url} href={url} target="_blank" rel="noreferrer">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={url}
                      alt="Ảnh người học đính kèm"
                      className="h-32 w-32 rounded border border-rule object-cover"
                    />
                  </a>
                ))}
              </div>
            )}

            {row.admin_note && (
              <p className="mt-3 rounded border border-rule bg-recess p-2 text-small text-ink-muted">
                {row.admin_note}
              </p>
            )}

            {row.status === "pending" && (
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={busy === row.id}
                  onClick={() => void act(row.id, API_ROUTES.adminFeedbackApprove(row.id))}
                >
                  Duyệt và trao ruby
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={busy === row.id}
                  onClick={() => {
                    const note = window.prompt("Lý do từ chối (không bắt buộc):");
                    if (note === null) return;
                    void act(row.id, API_ROUTES.adminFeedbackReject(row.id), {
                      admin_note: note || null,
                    });
                  }}
                >
                  Từ chối
                </Button>
              </div>
            )}
          </Panel>
        ))}
      </div>
    </Page>
  );
}

function StatusChip({ status }: { status: FeedbackStatus }) {
  const tone =
    status === "approved"
      ? "border-ok text-ok"
      : status === "rejected"
        ? "border-alert text-alert"
        : "border-rule-strong text-ink-muted";
  const label =
    status === "approved" ? "Đã duyệt" : status === "rejected" ? "Đã từ chối" : "Chờ xử lý";
  return (
    <span className={cx("rounded border px-2 py-0.5 text-label font-semibold", tone)}>{label}</span>
  );
}
