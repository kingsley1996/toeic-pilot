"use client";

import { API_ROUTES, type PlacementBuildOut, type TestAdmin } from "@toeic-pilot/shared";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Field, Input, Page, PageHeader, Panel, Select, cx } from "@/components/ui";
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
  const [sources, setSources] = useState<TestAdmin[] | null>(null);
  const [sourceSlug, setSourceSlug] = useState("");
  const [slug, setSlug] = useState("");
  const [buildInfo, setBuildInfo] = useState<PlacementBuildOut | null>(null);
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
    // Đề nguồn: mọi đề KHÔNG phải placement. Số câu hiển thị để thấy ngay đề
    // thiếu nội dung, còn trạng thái là cổng thật: đề nguồn phải published
    // trước thì đề placement mới được đưa vào nhóm (cổng publish chặn).
    apiFetch<Envelope>(`${API_ROUTES.adminTests}?limit=100`, { token })
      .then((page) => setSources(page.items.filter((item) => item.kind !== "placement")))
      .catch(() => setSources([]));
  }, [apply, fetchRows, token]);

  // Gợi ý số kế tiếp từ slug đang có — người soạn vẫn sửa được.
  const suggested =
    rows && rows.length > 0
      ? `tp-placement-${String(
          rows.reduce(
            (max, row) => Math.max(max, Number(/tp-placement-(\d+)/.exec(row.slug)?.[1] ?? 0)),
            0,
          ) + 1,
        ).padStart(2, "0")}`
      : "tp-placement-01";
  const chosen = sources?.find((item) => item.slug === sourceSlug);

  async function build() {
    if (!token || !sourceSlug) return;
    setBusy("build");
    setBuildInfo(null);
    try {
      const info = await apiFetch<PlacementBuildOut>(
        API_ROUTES.adminTestPlacementBuild(sourceSlug),
        { method: "POST", token, body: JSON.stringify({ slug: slug || suggested }) },
      );
      setBuildInfo(info);
      setSlug("");
      apply(await fetchRows());
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "Không dựng được đề.");
    } finally {
      setBusy(null);
    }
  }

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

      <Panel className="mt-5 space-y-4 p-4">
        <div>
          <h2 className="font-semibold">Dựng đề placement mới</h2>
          <p className="text-small text-ink-muted">
            Rút 84 câu theo dạng câu từ một đề full có sẵn, ghi dưới dạng nháp. Đề nguồn phải
            published trước khi đề placement được đưa vào nhóm.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Đề nguồn">
            <Select
              value={sourceSlug}
              onChange={(event) => {
                setSourceSlug(event.target.value);
                setBuildInfo(null);
              }}
            >
              <option value="">— chọn đề nguồn —</option>
              {sources?.map((item) => (
                <option key={item.id} value={item.slug}>
                  {item.slug} · {item.question_count} câu ·{" "}
                  {item.status === "published" ? "published" : "draft"}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Slug đề mới" hint={`Để trống sẽ dùng ${suggested}.`}>
            <Input
              value={slug || suggested}
              onChange={(event) => setSlug(event.target.value)}
              placeholder={suggested}
            />
          </Field>
        </div>
        {chosen && chosen.status !== "published" && (
          <Alert tone="alert">
            Đề nguồn đang ở trạng thái {chosen.status}. Hãy published đề nguồn trước — đề placement
            chứa câu của nó, và cổng xuất bản sẽ chặn khi còn câu nháp.
          </Alert>
        )}
        <div>
          <Button size="sm" disabled={!sourceSlug || busy === "build"} onClick={() => void build()}>
            {busy === "build" ? "Đang dựng…" : "Dựng nháp"}
          </Button>
        </div>
        {buildInfo && (
          <>
            <Alert tone="info">
              Đã tạo {buildInfo.slug} — {buildInfo.question_count} câu,{" "}
              {buildInfo.grammar_code_count} mã ngữ pháp, trạng thái nháp.
            </Alert>
            <div className="text-small">
              {buildInfo.parts.map((part) => (
                <p key={part.part}>
                  Part {part.part}: {part.count} câu
                  {part.missing_priority.length > 0 && (
                    <span className="text-ink-muted">
                      {" "}
                      — thiếu dạng khó: {part.missing_priority.join(", ")}
                    </span>
                  )}
                </p>
              ))}
            </div>
          </>
        )}
      </Panel>

      <div className="mt-5 space-y-3">
        {rows?.length === 0 && (
          <p className="text-small text-ink-muted">Chưa có đề đầu vào nào — dựng ở khung trên.</p>
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
                {row.source_slug ? ` · nguồn: ${row.source_slug}` : ""}
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
