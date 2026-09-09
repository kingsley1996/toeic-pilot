"use client";

import type { PartTacticsAdmin } from "@toeic-pilot/shared";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { MarkdownLite } from "@/components/markdown-lite";
import { VideoBlock, type VideoState } from "@/components/video-block";
import { Alert, Button, Field, Page, PageHeader, SkeletonList, Textarea } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

const VALID_PARTS = new Set([1, 2, 3, 4, 5, 6, 7]);

/**
 * Soạn chiến thuật MỘT part: body markdown + video chiến thuật. Cùng triết lý
 * với `LessonForm` của grammar — sửa THẲNG trong DB, đừng đòi deploy để đổi một
 * chữ; markdown trong `apps/web/content/parts/` chỉ còn là hạt giống lần đầu,
 * chạy sync sau khi sửa tay ở đây là GHI ĐÈ nội dung.
 */
export default function EditPartTacticsPage() {
  const rawPart = Number(useParams().part);
  const part = VALID_PARTS.has(rawPart) ? rawPart : null;
  const { status, token } = useRequireSession({ canEdit: true });
  const [loaded, setLoaded] = useState(false);
  const [body, setBody] = useState("");
  const [video, setVideo] = useState<VideoState>({ url: null, duration: null });
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (part === null || !token) return;
    apiFetch<PartTacticsAdmin>(`/api/v1/admin/parts/${part}/tactics`, { token })
      .then((row) => {
        setBody(row.body);
        setVideo({ url: row.video_url ?? null, duration: row.video_duration_s ?? null });
        setLoaded(true);
      })
      .catch(() => setFailure("Không tải được trang chiến thuật này."));
  }, [part, token]);

  if (!part) {
    return (
      <Page className="max-w-3xl">
        <Alert>Không có phần này — bài thi TOEIC có bảy phần, từ 1 đến 7.</Alert>
      </Page>
    );
  }

  if (status !== "authenticated" || !loaded) {
    return (
      <Page className="max-w-5xl">
        <SkeletonList rows={6} />
      </Page>
    );
  }

  async function save() {
    if (!token) return;
    setSaving(true);
    setFailure(null);
    setSaved(false);
    try {
      const row = await apiFetch<PartTacticsAdmin>(`/api/v1/admin/parts/${part}/tactics`, {
        method: "PUT",
        token,
        body: JSON.stringify({ body }),
      });
      setVideo({ url: row.video_url ?? null, duration: row.video_duration_s ?? null });
      setSaved(true);
    } catch (err) {
      setFailure(err instanceof ApiError ? err.message : "Không lưu được.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Page className="max-w-5xl">
      <Link
        href="/admin/parts"
        className="mb-3 inline-flex items-center gap-1.5 text-small text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={13} strokeWidth={2} aria-hidden />
        Quay lại chiến thuật bảy part
      </Link>

      <PageHeader eyebrow="Chiến thuật" title={`Part ${part}`} />

      {failure && (
        <div className="mb-4">
          <Alert>{failure}</Alert>
        </div>
      )}
      {saved && !failure && (
        <div className="mb-4">
          <Alert tone="ok">Đã lưu.</Alert>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Field label="Markdown">
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="h-[calc(100dvh-24rem)] min-h-[22rem] font-data text-small"
            spellCheck={false}
          />
        </Field>
        <Field label="Xem trước">
          <div className="h-[calc(100dvh-24rem)] min-h-[22rem] overflow-y-auto rounded border border-rule-strong bg-panel p-4">
            <MarkdownLite text={body} className="text-lesson" />
          </div>
        </Field>
      </div>

      <VideoBlock
        token={token}
        scope={{ kind: "part", part }}
        videoUrl={video.url}
        duration={video.duration}
        onChanged={setVideo}
        hint="Tùy chọn — mp4/webm/mov, tối đa 300 MB. Người học thấy player trên khối chiến thuật."
      />

      <div className="sticky bottom-0 -mx-4 mt-6 flex items-center justify-end gap-2 border-t border-rule bg-ground/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <span className="flex-1 text-small text-ink-faint">
          Chạy lại <code className="font-data">scripts/sync-parts.sh</code> sẽ ghi đè nội dung này.
        </span>
        <Button disabled={saving} onClick={() => void save()}>
          {saving ? "Đang lưu…" : "Lưu"}
        </Button>
      </div>
    </Page>
  );
}
