"use client";

import {
  API_ROUTES,
  type ListeningAdminPage,
  type ListeningCaptionsPublic,
  type ListeningContentPublic,
} from "@toeic-pilot/shared";
import { useCallback, useEffect, useRef, useState } from "react";

import { DestructiveButton } from "@/components/destructive-button";
import { GuestNotice } from "@/components/guest-notice";
import { ListeningPlayerView } from "@/components/listening-player";
import { TiktokPlayerView } from "@/components/tiktok-player";
import { VideoPlayerView } from "@/components/video-player";
import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  Input,
  Page,
  PageHeader,
  Pager,
  Panel,
  Select,
  SkeletonList,
  Tag,
  Textarea,
  cx,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { resolveTikTokUrl, resolveYouTubeUrl } from "@/lib/listening-source";
import { useRequireSession } from "@/lib/session";

// Khớp `DEFAULT_LIMIT` ở `app/schemas/common.py`.
const PAGE_SIZE = 50;

type SourceKind = "youtube" | "tiktok";

/** Mili-giây hiện tại. Chỉ gọi trong handler (purity rule cấm trong render) —
 * cùng mẹo `nowMs` của trang học listening. */
function nowMs(): number {
  return Date.now();
}

function detectSource(url: string): { kind: SourceKind; canonical: string } | null {
  const yt = resolveYouTubeUrl(url);
  if (yt.ok) return { kind: "youtube", canonical: yt.source.url };
  // Link rút gọn TikTok (vm/vt) không trích được ID ở client — vẫn nhận để
  // backend resolve, preview phụ đề sẽ báo rõ nếu không lấy được.
  const tt = resolveTikTokUrl(url);
  if (tt.ok) return { kind: "tiktok", canonical: tt.source.url };
  return null;
}

export default function AdminListeningPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [url, setUrl] = useState("");
  const [source, setSource] = useState<{ kind: SourceKind; canonical: string } | null>(null);
  const [title, setTitle] = useState("");
  const [format, setFormat] = useState<"srt" | "vtt">("vtt");
  const [transcript, setTranscript] = useState("");
  const [captionNote, setCaptionNote] = useState<string | null>(null);
  const [items, setItems] = useState<ListeningAdminPage["items"] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [forceId, setForceId] = useState<string | null>(null);
  // Sửa thủ công khi transcript lệch video: video + transcript cạnh nhau để
  // vừa nghe vừa sửa. `id` null = câu mới (backend chèn), câu vắng mặt = xoá.
  type EditRow = { key: string; id: string | null; start: string; end: string; text: string };
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editSegs, setEditSegs] = useState<EditRow[]>([]);
  const [editSource, setEditSource] = useState<{
    source_type: string;
    source_url: string;
    external_id: string | null;
    media_url: string | null;
  } | null>(null);
  // Câu đang nghe thử trong player (đổi là seek + phát, theo `ListeningPlayerView`).
  const [preview, setPreview] = useState({ start: 0, end: 0 });
  const [replaySeq, setReplaySeq] = useState(0);
  const newKey = useRef(0);
  // Câu video đang phát tới (follow theo timeline) — highlight + cuộn tới,
  // độc lập với `preview` (câu bấm nghe thử). Không seek/play theo.
  const [followKey, setFollowKey] = useState<string | null>(null);
  const rowRefs = useRef(new Map<string, HTMLDivElement>());
  // Cửa sổ settle sau mỗi lần bấm Nghe: seek đang bay, tick đọc giờ cũ mà
  // tính là follow là highlight nhảy về câu cũ (cùng mẹo trang học).
  const settleUntilRef = useRef(0);
  const [editBusy, setEditBusy] = useState(false);
  const [editForceAttempts, setEditForceAttempts] = useState<number | null>(null);
  // Mốc dừng cho player = cuối mọi câu hợp lệ, tăng dần.
  const previewStops = editSegs
    .map((seg) => Number(seg.end))
    .filter((n) => Number.isFinite(n))
    .sort((a, b) => a - b);

  const refresh = useCallback(
    (t: string, at = offset) => {
      apiFetch<ListeningAdminPage>(`${API_ROUTES.adminListeningContents}?offset=${at}`, {
        token: t,
      })
        .then((page) => {
          setItems(page.items);
          setTotal(page.total);
        })
        .catch(() => setError("Không tải được thư viện."));
    },
    [offset],
  );

  useEffect(() => {
    if (token) refresh(token);
  }, [token, refresh]);

  /* Cuộn list câu tới câu video đang phát tới. Trước early-return dưới: hook
   * sau `return` có điều kiện là lỗi luật lẫn lỗi React. */
  useEffect(() => {
    if (followKey) rowRefs.current.get(followKey)?.scrollIntoView({ block: "nearest" });
  }, [followKey]);

  if (status === "loading" || !token) {
    return (
      <Page className="max-w-4xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  function checkUrl() {
    const found = detectSource(url);
    setSource(found);
    setCaptionNote(null);
    if (!found) setError("Link chưa đúng — cần link video YouTube hoặc TikTok.");
    else setError(null);
  }

  /** Lấy phụ đề tự động (YouTube + TikTok; TikTok chậm hơn và không phải
   * video nào cũng có sub — thiếu thì dán tay vào ô dưới). */
  async function fetchCaptions() {
    if (!token || !source) return;
    setCaptionNote(null);
    setError(null);
    setBusy(true);
    try {
      const data = await apiFetch<ListeningCaptionsPublic>(API_ROUTES.listeningCaptions, {
        method: "POST",
        token,
        body: JSON.stringify({ url: source.canonical }),
      });
      setTranscript(data.raw);
      if (data.title?.trim() && !title.trim()) setTitle(data.title.trim());
      setCaptionNote(
        `Đã lấy phụ đề (${data.language}, ${data.segment_count} câu). Kiểm tra lại trước khi xuất bản.`,
      );
    } catch (err) {
      if (err instanceof ApiError) {
        const code = (err.detail as { code?: unknown } | undefined)?.code;
        setCaptionNote(
          code === "UNSUPPORTED_SOURCE"
            ? "Nguồn này chưa tự lấy phụ đề được — dán SRT/VTT vào ô dưới."
            : err.message,
        );
      } else {
        setCaptionNote("Không lấy được phụ đề lúc này — dán tay vào ô dưới.");
      }
    } finally {
      setBusy(false);
    }
  }

  /** Tạo bài riêng rồi xuất bản luôn (có quyền) hoặc để chờ duyệt. Ba endpoint
   * learner có sẵn nối tiếp nhau — không có đường ghi riêng cho admin. */
  async function createAndPublish() {
    if (!token || !source) return;
    setNotice(null);
    setError(null);
    setBusy(true);
    try {
      const created = await apiFetch<{ id: string }>(API_ROUTES.listeningContents, {
        method: "POST",
        token,
        body: JSON.stringify({
          source: { type: source.kind, url: source.canonical },
          title: title.trim(),
          transcript: { format, raw: transcript },
        }),
      });
      if (canPublish) {
        await apiFetch(API_ROUTES.adminListeningContent(created.id), {
          method: "PATCH",
          token,
          body: JSON.stringify({ is_public: true }),
        });
        setNotice("Đã xuất bản vào thư viện.");
      } else {
        setNotice("Đã tạo bản riêng (chỉ bạn thấy) — admin sẽ tạo bản public riêng cho thư viện.");
      }
      setUrl("");
      setSource(null);
      setTitle("");
      setTranscript("");
      setCaptionNote(null);
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được bài.");
    } finally {
      setBusy(false);
    }
  }

  /** Mở trình sửa: tải chi tiết public rồi đổ vào form từng câu. */
  async function startEdit(id: string) {
    if (!token) return;
    setError(null);
    setNotice(null);
    setEditForceAttempts(null);
    setEditBusy(true);
    try {
      const detail = await apiFetch<ListeningContentPublic>(API_ROUTES.listeningContent(id), {
        token,
      });
      setEditingId(id);
      setEditTitle(detail.title);
      setEditSource({
        source_type: detail.source_type,
        source_url: detail.source_url,
        external_id: detail.external_id,
        media_url: detail.media_url ?? null,
      });
      setEditSegs(
        detail.segments.map((seg) => ({
          key: seg.id,
          id: seg.id,
          start: String(seg.start),
          end: String(seg.end),
          text: seg.text,
        })),
      );
      const first = detail.segments[0];
      if (first) {
        setPreview({ start: first.start, end: first.end });
        setFollowKey(first.id);
      } else {
        setFollowKey(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tải được bài.");
    } finally {
      setEditBusy(false);
    }
  }

  /** Thêm câu mới vào cuối (mốc nối tiếp câu cuối để dễ căn giờ). */
  function addEditRow() {
    newKey.current += 1;
    const lasts = editSegs.map((seg) => Number(seg.end)).filter((n) => Number.isFinite(n));
    const start = lasts.length > 0 ? Math.max(...lasts) : 0;
    setEditSegs((rows) => [
      ...rows,
      {
        key: `new-${newKey.current}`,
        id: null,
        start: String(start),
        end: String(start + 2),
        text: "",
      },
    ]);
  }

  /** Nghe thử một câu: đổi mốc là player seek + phát (bấm trùng thì phát lại).
   * Mở cửa sổ settle để tick giờ cũ trong lúc seek không lôi highlight đi. */
  function previewRow(seg: EditRow) {
    const start = Number(seg.start);
    const end = Number(seg.end);
    if (!Number.isFinite(start) || !Number.isFinite(end)) return;
    settleUntilRef.current = nowMs() + 1200;
    setFollowKey(seg.key);
    setPreview((prev) => {
      if (prev.start === start && prev.end === end) setReplaySeq((n) => n + 1);
      return { start, end };
    });
  }

  /** Video tới đâu thì highlight tới đó: tìm câu chứa mốc giờ trên transcript
   * đang sửa (giờ đọc từ input nên sửa giờ là follow bám theo ngay). Ngoài
   * khoảng thì đứng yên câu cũ. Chỉ highlight + cuộn, không seek/play. */
  function handleTime(playedSeconds: number) {
    if (nowMs() < settleUntilRef.current) return;
    const found = editSegs.find((seg) => {
      const start = Number(seg.start);
      const end = Number(seg.end);
      return (
        Number.isFinite(start) &&
        Number.isFinite(end) &&
        playedSeconds >= start &&
        playedSeconds < end
      );
    });
    if (found && found.key !== followKey) setFollowKey(found.key);
  }

  /** Lưu toàn bộ transcript (full-replace: câu mới không id, câu vắng = xoá).
   * 409 nghĩa là đã có người học — hỏi lại rồi gửi kèm ?force=true. */
  async function saveEdit(force: boolean) {
    if (!token || !editingId) return;
    setError(null);
    if (editSegs.length === 0) {
      setError("Bài cần ít nhất một câu — muốn dọn thì dùng nút Xoá.");
      return;
    }
    const segments = [];
    for (const seg of editSegs) {
      const start = Number(seg.start);
      const end = Number(seg.end);
      if (!Number.isFinite(start) || !Number.isFinite(end) || !seg.text.trim()) {
        setError("Mỗi câu cần start/end là số và text khác rỗng.");
        return;
      }
      segments.push(
        seg.id === null
          ? { text: seg.text.trim(), start, end }
          : { id: seg.id, text: seg.text.trim(), start, end },
      );
    }
    setEditBusy(true);
    try {
      await apiFetch(
        `${API_ROUTES.adminListeningContent(editingId)}${force ? "?force=true" : ""}`,
        {
          method: "PUT",
          token,
          body: JSON.stringify({ title: editTitle.trim(), segments }),
        },
      );
      setNotice(force ? "Đã lưu (giữ lịch sử học cũ)." : "Đã lưu sửa đổi.");
      setEditingId(null);
      setEditSegs([]);
      setEditSource(null);
      setFollowKey(null);
      rowRefs.current.clear();
      setEditForceAttempts(null);
      refresh(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const row = items?.find((c) => c.id === editingId);
        setEditForceAttempts(row?.attempt_count ?? 0);
      } else {
        setError(err instanceof ApiError ? err.message : "Không lưu được.");
      }
    } finally {
      setEditBusy(false);
    }
  }

  async function unpublish(id: string) {
    if (!token) return;
    setError(null);
    try {
      await apiFetch(API_ROUTES.adminListeningContent(id), {
        method: "PATCH",
        token,
        body: JSON.stringify({ is_public: false }),
      });
      setNotice("Đã gỡ khỏi thư viện (lịch sử học giữ nguyên).");
      refresh(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không gỡ được.");
    }
  }

  async function remove(id: string, force: boolean) {
    if (!token) return;
    setError(null);
    setForceId(null);
    try {
      await apiFetch(`${API_ROUTES.adminListeningContent(id)}${force ? "?force=true" : ""}`, {
        method: "DELETE",
        token,
      });
      setNotice(force ? "Đã xoá kèm lịch sử học." : "Đã xoá bài.");
      refresh(token);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Có người đã học — không xoá im lặng, hỏi lại cho rõ.
        setForceId(id);
      } else {
        setError(err instanceof ApiError ? err.message : "Không xoá được.");
      }
    }
  }

  return (
    <Page className="max-w-4xl">
      <PageHeader
        eyebrow="Quản trị"
        title="Thư viện Listening"
        description="Thêm bài từ link video, duyệt xuất bản, gỡ hoặc xoá. Chỉ bài public hiện ở đây — bài riêng của user không bao giờ lọt vào."
      />

      <GuestNotice className="mb-4" />

      {notice && (
        <div className="mb-4">
          <Alert tone="ok">{notice}</Alert>
        </div>
      )}
      {error && (
        <div className="mb-4">
          <Alert tone="alert">{error}</Alert>
        </div>
      )}

      <Panel className="mb-6 space-y-3 p-5">
        <h2 className="text-subtitle">Thêm từ link video</h2>
        <div className="flex flex-wrap gap-2">
          <Input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=… hoặc link TikTok"
            inputMode="url"
            aria-label="Link video"
            className="min-w-0 flex-1"
          />
          <Button size="sm" variant="secondary" onClick={checkUrl}>
            Kiểm tra link
          </Button>
        </div>
        {source && (
          <div className="space-y-3">
            <p className="flex flex-wrap items-center gap-2 text-small text-ink-muted">
              <Tag tone="action">{source.kind === "youtube" ? "YouTube" : "TikTok"}</Tag>
              <span className="break-all font-data">{source.canonical}</span>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => void fetchCaptions()}
              >
                Lấy phụ đề
              </Button>
            </p>
            {captionNote && <p className="text-small text-ink-muted">{captionNote}</p>}
            <label className="block">
              <span className="mb-1.5 block text-label font-semibold uppercase text-ink-muted">
                Tên bài học
              </span>
              <Input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={512}
                aria-label="Tên bài học"
              />
            </label>
            <div className="flex items-center gap-2">
              <Select
                value={format}
                onChange={(event) => setFormat(event.target.value as "srt" | "vtt")}
                aria-label="Định dạng phụ đề"
              >
                <option value="vtt">VTT</option>
                <option value="srt">SRT</option>
              </Select>
            </div>
            <Textarea
              value={transcript}
              onChange={(event) => setTranscript(event.target.value)}
              rows={8}
              aria-label="Phụ đề có timestamp"
              className="font-data"
            />
            <Button
              onClick={() => void createAndPublish()}
              disabled={busy || !title.trim() || !transcript.trim()}
            >
              {canPublish ? "Tạo + xuất bản" : "Tạo bản riêng"}
            </Button>
          </div>
        )}
      </Panel>

      {editingId && (
        <Panel className="mb-6 space-y-3 p-5">
          <h2 className="text-subtitle">Sửa bài ({editSegs.length} câu)</h2>
          <label className="block">
            <span className="mb-1.5 block text-label font-semibold uppercase text-ink-muted">
              Tên bài học
            </span>
            <Input
              value={editTitle}
              onChange={(event) => setEditTitle(event.target.value)}
              maxLength={512}
              aria-label="Tên bài học"
            />
          </label>
          {/* Video trái, form câu phải (mobile xếp chồng, video dính trên để
            vừa nghe vừa sửa). Câu video đang phát tới thì highlight + cuộn
            tới — cùng cách trang học bám playback. Player dùng chung
            (không `key` theo câu: remount là dựng lại iframe). */}
          <div className="grid items-start gap-4 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <div className="sticky top-0 z-10 bg-panel pb-1">
                {editSource?.media_url ? (
                  <VideoPlayerView
                    videoUrl={editSource.media_url}
                    sourceUrl={editSource.source_url}
                    title={editTitle}
                    start={preview.start}
                    end={preview.end}
                    stops={previewStops}
                    startLabel="Nghe"
                    onAdvance={() => {}}
                    onTimeUpdate={handleTime}
                    replaySignal={replaySeq}
                  />
                ) : editSource?.source_type === "tiktok" && editSource.external_id ? (
                  /* TikTok embed không seek/báo giờ được — chỉ mở để đối chiếu
                    toàn video khi sửa, không có Nghe-từng-câu như YouTube. */
                  <TiktokPlayerView
                    videoId={editSource.external_id}
                    sourceUrl={editSource.source_url}
                  />
                ) : editSource?.source_type === "youtube" && editSource.external_id ? (
                  <ListeningPlayerView
                    videoId={editSource.external_id}
                    start={preview.start}
                    end={preview.end}
                    stops={previewStops}
                    startLabel="Nghe"
                    onAdvance={() => {}}
                    onTimeUpdate={handleTime}
                    replaySignal={replaySeq}
                  />
                ) : (
                  editSource && (
                    <p className="text-small text-ink-muted">
                      Nguồn video gốc:{" "}
                      <a
                        href={editSource.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-action-ink underline"
                      >
                        Mở để đối chiếu
                      </a>
                    </p>
                  )
                )}
              </div>
            </div>
            <div className="space-y-2 lg:col-span-3">
              {editSegs.map((seg, i) => (
                <div
                  key={seg.key}
                  ref={(node) => {
                    if (node) rowRefs.current.set(seg.key, node);
                    else rowRefs.current.delete(seg.key);
                  }}
                  aria-current={seg.key === followKey ? "true" : undefined}
                  className={cx(
                    "flex flex-wrap items-center gap-2 rounded border px-2 py-1.5",
                    seg.key === followKey && "border-action bg-action-tint",
                  )}
                >
                  <span className="w-8 shrink-0 font-data text-small text-ink-muted">#{i + 1}</span>
                  <Input
                    value={seg.start}
                    onChange={(event) =>
                      setEditSegs((rows) =>
                        rows.map((r) =>
                          r.key === seg.key ? { ...r, start: event.target.value } : r,
                        ),
                      )
                    }
                    inputMode="decimal"
                    aria-label={`Câu ${i + 1} bắt đầu (giây)`}
                    className="w-24 font-data"
                  />
                  <Input
                    value={seg.end}
                    onChange={(event) =>
                      setEditSegs((rows) =>
                        rows.map((r) =>
                          r.key === seg.key ? { ...r, end: event.target.value } : r,
                        ),
                      )
                    }
                    inputMode="decimal"
                    aria-label={`Câu ${i + 1} kết thúc (giây)`}
                    className="w-24 font-data"
                  />
                  <Input
                    value={seg.text}
                    onChange={(event) =>
                      setEditSegs((rows) =>
                        rows.map((r) =>
                          r.key === seg.key ? { ...r, text: event.target.value } : r,
                        ),
                      )
                    }
                    aria-label={`Câu ${i + 1} nội dung`}
                    className="min-w-0 flex-1"
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={editBusy}
                    title="Nghe thử câu này"
                    onClick={() => previewRow(seg)}
                  >
                    Nghe
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={editBusy || editSegs.length <= 1}
                    title={editSegs.length <= 1 ? "Bài cần ít nhất một câu" : "Xoá câu này"}
                    onClick={() => setEditSegs((rows) => rows.filter((r) => r.key !== seg.key))}
                  >
                    Xoá
                  </Button>
                </div>
              ))}
              <Button size="sm" variant="secondary" disabled={editBusy} onClick={addEditRow}>
                Thêm câu
              </Button>
            </div>
          </div>
          {editForceAttempts !== null && (
            <p className="text-small text-ink-muted">
              Bài đã có {editForceAttempts} lượt học — lưu sẽ đổi đáp án của lịch sử cũ.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {editForceAttempts === null ? (
              <Button size="sm" disabled={editBusy} onClick={() => void saveEdit(false)}>
                Lưu
              </Button>
            ) : (
              <Button size="sm" disabled={editBusy} onClick={() => void saveEdit(true)}>
                Lưu kèm {editForceAttempts} lượt học
              </Button>
            )}
            <Button
              size="sm"
              variant="secondary"
              disabled={editBusy}
              onClick={() => {
                setEditingId(null);
                setEditSegs([]);
                setEditSource(null);
                setFollowKey(null);
                rowRefs.current.clear();
                setEditForceAttempts(null);
              }}
            >
              Huỷ
            </Button>
          </div>
        </Panel>
      )}

      <h2 className="mb-2 text-subtitle">Bài đang public ({total})</h2>
      {items === null ? (
        <SkeletonList rows={3} />
      ) : items.length === 0 ? (
        <EmptyState title="Thư viện trống" description="Thêm bài đầu tiên từ link video ở trên." />
      ) : (
        <div className="space-y-2">
          {items.map((content) => (
            <Panel key={content.id} className="flex flex-wrap items-center gap-3 p-4">
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{content.title}</span>
                <span className="mt-0.5 block text-small text-ink-muted">
                  <Tag tone="neutral">{content.source_type}</Tag>{" "}
                  <span className="font-data">
                    {content.segment_count} câu · {content.attempt_count} lượt học ·{" "}
                    {content.owner_email}
                  </span>
                </span>
              </span>
              <ButtonLink href={`/learn/listening/${content.id}`} variant="secondary" size="sm">
                Mở
              </ButtonLink>
              <Button
                size="sm"
                variant="secondary"
                disabled={!canPublish || editBusy}
                title={canPublish ? "Sửa tên + từng câu" : "Cần quyền admin"}
                onClick={() => void startEdit(content.id)}
              >
                Sửa
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={!canPublish}
                title={canPublish ? "Gỡ khỏi thư viện (giữ lịch sử)" : "Cần quyền admin"}
                onClick={() => void unpublish(content.id)}
              >
                Gỡ
              </Button>
              <DestructiveButton
                label="Xoá"
                confirmLabel="Xoá thật?"
                disabled={!canPublish}
                title={canPublish ? undefined : "Cần quyền admin"}
                onConfirm={() => void remove(content.id, false)}
              />
              {forceId === content.id && (
                <Button size="sm" variant="secondary" onClick={() => void remove(content.id, true)}>
                  Xoá kèm {content.attempt_count} lượt học
                </Button>
              )}
            </Panel>
          ))}
        </div>
      )}
      <div className="mt-4">
        <Pager total={total} limit={PAGE_SIZE} offset={offset} onOffset={setOffset} />
      </div>
    </Page>
  );
}
