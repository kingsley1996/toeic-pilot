"use client";

import type { GrammarLessonAdmin, PartTacticsAdmin } from "@toeic-pilot/shared";
import { useRef, useState } from "react";

import { Alert, Button, Panel } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import {
  messageFor,
  videoDurationSeconds,
  uploadGrammarVideo,
  uploadPartVideo,
} from "@/lib/upload";

type VideoAdmin = Pick<GrammarLessonAdmin | PartTacticsAdmin, "video_url" | "video_duration_s">;

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export type VideoState = { url: string | null; duration: number | null };

/**
 * Khối "Video bài giảng/chiến thuật" dùng chung cho màn soạn grammar lesson và
 * màn soạn chiến thuật part (SPEC-GRAMMAR-VIDEO §4): xin vé → PUT thẳng object
 * store → confirm gắn khoá. Chỉ hàng ĐÃ có id/part mới gắn video được.
 */
export function VideoBlock({
  token,
  scope,
  videoUrl,
  duration,
  onChanged,
  hint,
}: {
  token: string | null;
  /** `grammar` gắn theo lessonId; `part` gắn theo part 1–7. */
  scope: { kind: "grammar"; lessonId: string } | { kind: "part"; part: number };
  videoUrl: string | null;
  duration: number | null;
  onChanged: (next: VideoState) => void;
  hint: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const confirmPath = (storageKey: string, durationS: number | null) => ({
    method: "PUT",
    token: token ?? undefined,
    body: JSON.stringify({ storage_key: storageKey, duration_s: durationS }),
  });

  async function pick(file: File) {
    if (!token || busy) return;
    setBusy(true);
    setFailure(null);
    try {
      const durationS = await videoDurationSeconds(file);
      const storageKey =
        scope.kind === "grammar"
          ? await uploadGrammarVideo(scope.lessonId, file, token)
          : await uploadPartVideo(scope.part, file, token);
      const updated = await apiFetch<VideoAdmin>(
        scope.kind === "grammar"
          ? `/api/v1/admin/grammar/lessons/${scope.lessonId}/video`
          : `/api/v1/admin/parts/${scope.part}/tactics/video`,
        confirmPath(storageKey, durationS),
      );
      onChanged({ url: updated.video_url ?? null, duration: updated.video_duration_s ?? null });
    } catch (err) {
      setFailure(messageFor(err, "Không tải được video."));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!token || busy) return;
    setBusy(true);
    setFailure(null);
    try {
      const updated = await apiFetch<VideoAdmin>(
        scope.kind === "grammar"
          ? `/api/v1/admin/grammar/lessons/${scope.lessonId}/video`
          : `/api/v1/admin/parts/${scope.part}/tactics/video`,
        { method: "DELETE", token: token ?? undefined },
      );
      onChanged({ url: updated.video_url ?? null, duration: updated.video_duration_s ?? null });
    } catch (err) {
      setFailure(messageFor(err, "Không gỡ được video."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="mt-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-small font-semibold">
          {scope.kind === "grammar" ? "Video bài giảng" : "Video chiến thuật"}
        </p>
        <span className="flex-1" />
        {videoUrl && duration !== null && (
          <span className="text-small text-ink-muted" title="Thời lượng (do trình duyệt đọc)">
            {formatDuration(duration)}
          </span>
        )}
        {videoUrl && (
          <Button size="sm" variant="quiet" disabled={busy} onClick={() => void remove()}>
            Xoá
          </Button>
        )}
        <input
          ref={input}
          type="file"
          accept="video/mp4,video/webm,video/quicktime"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void pick(file);
            // Cho phép chọn LẠI cùng một file: không xoá giá trị thì `change`
            // không bắn lần thứ hai, và nút trông như hỏng.
            event.target.value = "";
          }}
        />
        <Button
          size="sm"
          variant="secondary"
          disabled={busy}
          onClick={() => input.current?.click()}
        >
          {busy ? "Đang tải lên…" : videoUrl ? "Thay thế" : "Tải video lên"}
        </Button>
      </div>
      {failure && (
        <div className="mt-2">
          <Alert>{failure}</Alert>
        </div>
      )}
      {videoUrl && (
        <video controls preload="metadata" src={videoUrl} className="mt-3 w-full rounded" />
      )}
      {!videoUrl && !busy && <p className="mt-2 text-small text-ink-muted">{hint}</p>}
    </Panel>
  );
}
