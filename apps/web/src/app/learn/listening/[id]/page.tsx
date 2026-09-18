"use client";

import {
  API_ROUTES,
  type ListeningAttemptResult,
  type ListeningContentPublic,
} from "@toeic-pilot/shared";
import { CircleCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { DictationExercise } from "@/components/dictation-exercise";
import { GuestNotice } from "@/components/guest-notice";
import { ListeningPlayerView } from "@/components/listening-player";
import { Alert, EmptyState, Page, PageHeader, SkeletonList, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/** Mili-giây hiện tại. Bọc ngoài component như `timeAgo` ở admin/users: rule
 * purity cấm gọi `Date.now()` trong render (kể cả trong hàm lồng), còn helper
 * ngoài này chỉ được gọi từ handler bấm/nộp — đúng chỗ thời gian sinh ra. */
function nowMs(): number {
  return Date.now();
}

/** Một bài Listening Lab: phát lại từng segment YouTube rồi chép chính tả. */
export default function ListeningLessonPage() {
  const { token } = useRequireSession();
  const contentId = String(useParams().id);
  const [content, setContent] = useState<ListeningContentPublic | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  // Mốc tính thời gian làm từng câu — chỉ ghi trong handler chuyển câu và đọc
  // trong handler nộp bài. Không khởi tạo ở render (`Date.now()` là hàm impure)
  // và không đặt trong effect (setState đồng bộ trong effect cho thứ tính được
  // từ sự kiện bấm). Lần nộp đầu chưa chuyển câu lần nào thì mốc là lúc bấm
  // Kiểm tra — `?? Date.now()` ngay trong handler là hợp lệ.
  const segStartedAt = useRef<number | null>(null);

  const load = useCallback(
    (t: string) =>
      apiFetch<ListeningContentPublic>(API_ROUTES.listeningContent(contentId), { token: t })
        .then(setContent)
        .catch(() => setError("Không tải được bài này. Nó có thể đã bị xoá.")),
    [contentId],
  );

  useEffect(() => {
    if (token) void load(token);
  }, [token, load]);

  if (!token || (!content && !error)) {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={5} />
      </Page>
    );
  }

  const segments = content?.segments ?? [];
  const active = segments[activeIndex] ?? null;
  const next = activeIndex + 1 < segments.length ? segments[activeIndex + 1] : undefined;

  function goTo(index: number) {
    segStartedAt.current = nowMs();
    setActiveIndex(index);
  }

  /** Ghi lượt làm về attempts của segment — cũng là chỗ duy nhất đánh dấu câu
   * đã đúng (server phán, không phải trình duyệt), và tính thời gian làm. */
  async function submitSegment(segmentId: string, text: string): Promise<unknown> {
    if (!token || !content) return null;
    const result = await apiFetch<ListeningAttemptResult>(
      API_ROUTES.listeningAttempts(content.id),
      {
        method: "POST",
        token,
        body: JSON.stringify({
          segment_id: segmentId,
          answer: text,
          time_spent_seconds: Math.max(
            0,
            Math.round((nowMs() - (segStartedAt.current ?? nowMs())) / 1000),
          ),
        }),
      },
    );
    if (result.is_correct) {
      setDoneIds((current) => new Set(current).add(segmentId));
    }
    return result;
  }

  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={[{ href: "/learn/listening", label: "Listening Lab" }]} />
      {error && <Alert>{error}</Alert>}

      {content && (
        <>
          <PageHeader
            eyebrow={`YouTube · ${doneIds.size}/${segments.length} câu đã đúng`}
            title={content.title}
            description="Nghe lại từng câu rồi gõ những gì bạn nghe được."
          />

          <GuestNotice className="mb-4" />

          {segments.length === 0 && (
            <EmptyState
              title="Bài này chưa có câu nào"
              description="Transcript lúc tạo không còn segment nào hợp lệ."
            />
          )}

          {segments.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-1.5">
              {segments.map((segment, index) => {
                const done = doneIds.has(segment.id);
                const current = index === activeIndex;
                return (
                  <button
                    key={segment.id}
                    type="button"
                    onClick={() => goTo(index)}
                    aria-current={current ? "true" : undefined}
                    title={`Câu ${index + 1} · ${done ? "đã đúng" : "chưa đúng"}`}
                    className={cx(
                      "inline-flex h-8 items-center gap-1 rounded border px-2 font-data text-small transition-colors",
                      current
                        ? "border-action bg-action-tint text-action-ink"
                        : done
                          ? "border-rule bg-ok-tint text-ok"
                          : "border-rule-strong text-ink-muted hover:bg-recess",
                    )}
                  >
                    {done && <CircleCheck size={13} strokeWidth={2.5} aria-hidden />}
                    {index + 1}
                  </button>
                );
              })}
            </div>
          )}

          {active && content.external_id && (
            <div className="mb-4">
              <ListeningPlayerView
                key={active.id}
                videoId={content.external_id}
                start={active.start}
                end={active.end}
              />
            </div>
          )}

          {active && !content.external_id && (
            <div className="mb-4">
              <Alert tone="warn">Bài này thiếu ID video nên không phát được.</Alert>
            </div>
          )}

          {active && (
            <DictationExercise
              key={active.id}
              item={{
                id: active.id,
                transcript: active.text,
                word_count: active.text.split(/\s+/).length,
              }}
              submitAnswer={(text) => submitSegment(active.id, text)}
              onNext={next ? () => goTo(activeIndex + 1) : undefined}
              nextLabel="Câu tiếp theo"
            />
          )}
        </>
      )}
    </Page>
  );
}
