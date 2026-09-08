"use client";

import { API_ROUTES, type TestAdmin } from "@toeic-pilot/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Page, PageHeader, Panel, cx } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Nhóm đề đầu vào.
 *
 * Người học bắt đầu bài test đầu vào thì máy chủ **rút ngẫu nhiên** một đề
 * trong nhóm đang bật. Bật thêm một đề là thêm vào nhóm, không phải thay chỗ —
 * khác hẳn hành vi cũ, nơi đúng một đề được published mỗi thời điểm.
 *
 * Đổi lại điều gì: hai người làm hai đề khác nhau mà điểm vẫn đặt cạnh nhau
 * được, vì điểm scaled quy đổi bằng `score_conversion` của chính đề đã làm. Đề
 * nào vào nhóm mà thiếu bảng quy đổi đúng thì đó mới là chỗ hỏng.
 *
 * Không có nút xoá ở đây. Lượt làm cũ trỏ vào đề, và màn xem lại phải đọc được
 * — nên đường rút một đề ra khỏi nhóm là LƯU TRỮ, không phải xoá.
 */

type Envelope = { items: TestAdmin[]; total: number };

export default function PlacementAdminPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [rows, setRows] = useState<TestAdmin[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const fetchRows = useCallback(
    () =>
      apiFetch<Envelope>(`${API_ROUTES.adminTests}?kind=placement&limit=100`, {
        token: token ?? "",
      }),
    [token],
  );

  // `setState` trong `.then`, không trong thân effect — `react-hooks/set-state-in-effect`.
  const apply = useCallback((page: Envelope) => {
    setRows(page.items);
    setError(null);
  }, []);

  useEffect(() => {
    if (!token) return;
    fetchRows()
      .then(apply)
      .catch((failure) =>
        setError(failure instanceof ApiError ? failure.message : "Không tải được danh sách."),
      );
  }, [apply, fetchRows, token]);

  async function toggle(row: TestAdmin) {
    if (!token) return;
    const path =
      row.status === "published"
        ? API_ROUTES.adminTestArchive(row.slug)
        : API_ROUTES.adminTestPublish(row.slug);
    setBusy(row.slug);
    try {
      await apiFetch(path, { method: "POST", token });
      apply(await fetchRows());
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Không đổi được trạng thái.");
    } finally {
      setBusy(null);
    }
  }

  if (status !== "authenticated") return null;

  const live = rows?.filter((row) => row.status === "published") ?? [];

  return (
    <Page>
      <PageHeader
        title="Đề đầu vào"
        description="Người học bắt đầu bài test đầu vào sẽ được rút ngẫu nhiên một đề trong nhóm đang bật."
      />

      <div className="mt-4">
        {live.length === 0 ? (
          // Nhóm rỗng KHÔNG phải một trạng thái yên lặng: `/placement/start`
          // trả 404 và người học mới không vào được đâu cả.
          <Alert tone="alert">
            Không có đề nào đang bật. Người học mới sẽ không bắt đầu được bài test đầu vào.
          </Alert>
        ) : (
          <Alert tone="info">
            {live.length === 1
              ? "Đang có 1 đề trong nhóm — mọi người học sẽ làm cùng một đề."
              : `Đang có ${live.length} đề trong nhóm, mỗi lượt bắt đầu rút ngẫu nhiên một đề.`}
          </Alert>
        )}
      </div>

      {error && (
        <div className="mt-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      <div className="mt-5 space-y-3">
        {rows?.length === 0 && (
          <p className="text-small text-ink-muted">
            Chưa có đề đầu vào nào. Dựng bằng{" "}
            <code className="text-label">make_placement --source &lt;slug đề nguồn&gt;</code>.
          </p>
        )}
        {rows?.map((row) => (
          <Panel key={row.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Link href={`/admin/tests/${row.slug}`} className="font-semibold hover:underline">
                  {row.title}
                </Link>
                <span
                  className={cx(
                    "rounded border px-2 py-0.5 text-label font-semibold",
                    row.status === "published"
                      ? "border-ok text-ok"
                      : "border-rule-strong text-ink-muted",
                  )}
                >
                  {row.status === "published" ? "Trong nhóm" : "Đã rút ra"}
                </span>
              </div>
              <p className="mt-1 text-small text-ink-muted">
                {row.slug} · {row.question_count} câu
                {row.time_limit_seconds ? ` · ${Math.round(row.time_limit_seconds / 60)} phút` : ""}
              </p>
            </div>

            <Button
              size="sm"
              variant={row.status === "published" ? "destructive" : "primary"}
              disabled={busy === row.slug}
              onClick={() => void toggle(row)}
            >
              {row.status === "published" ? "Rút khỏi nhóm" : "Đưa vào nhóm"}
            </Button>
          </Panel>
        ))}
      </div>
    </Page>
  );
}
