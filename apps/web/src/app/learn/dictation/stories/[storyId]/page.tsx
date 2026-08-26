"use client";

import { API_ROUTES, type DictationStoryDetail } from "@toeic-pilot/shared";
import { CircleCheck, CircleDashed } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { DictationExercise } from "@/components/dictation-exercise";
import { DictationNextUp } from "@/components/dictation-next";
import { StoryProgressBar } from "@/components/story-progress";
import { Alert, EmptyState, Page, PageHeader, Panel, SkeletonList, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/** Tầng 4: một bài văn, làm tuần tự từng câu. */
export default function DictationStoryPage() {
  const { status, token } = useRequireSession();
  const storyId = String(useParams().storyId);
  const [story, setStory] = useState<DictationStoryDetail | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (t: string) =>
      apiFetch<DictationStoryDetail>(API_ROUTES.dictationStory(storyId), { token: t })
        .then((data) => {
          setStory(data);
          // Mở đúng câu đầu tiên CHƯA làm — đó là câu trả lời cho "hôm qua tôi
          // dừng ở đâu". Làm dở hôm nay, mai vào là tiếp đúng chỗ đó.
          setActiveId((current) => {
            if (current) return current;
            const next = data.items.find((item) => !item.completed);
            return next?.id ?? data.items[0]?.id ?? null;
          });
        })
        .catch(() => setError("Không tải được bài này.")),
    [storyId],
  );

  useEffect(() => {
    if (token) void load(token);
  }, [token, load]);

  if (status !== "authenticated" || (!story && !error)) {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={5} />
      </Page>
    );
  }

  const active = story?.items.find((item) => item.id === activeId) ?? null;
  const activeIndex = story?.items.findIndex((item) => item.id === activeId) ?? -1;
  const next = story && activeIndex >= 0 ? story.items[activeIndex + 1] : undefined;

  return (
    <Page className="max-w-3xl">
      {error && <Alert>{error}</Alert>}

      {story && (
        <>
          <Breadcrumbs
            trail={[
              { href: "/learn/dictation", label: "Dictation" },
              { href: `/learn/dictation/topics/${story.topic_id}`, label: story.topic_name },
              { href: `/learn/dictation/sections/${story.section_id}`, label: story.section_name },
            ]}
          />
          <PageHeader eyebrow="Bài nghe" title={story.title} description={story.description} />

          <Panel className="mb-4 p-4">
            <StoryProgressBar progress={story.progress} />
          </Panel>

          {story.items.length === 0 && (
            <EmptyState
              icon={CircleDashed}
              title="Bài này chưa có câu nào"
              description="Nội dung đang được biên soạn."
            />
          )}

          {/* Dải câu: vừa là điều hướng vừa là bản đồ tiến độ. Câu đã làm mang
              dấu tích, câu đang làm được tô — nhìn một cái là biết còn bao xa. */}
          {story.items.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-1.5">
              {story.items.map((item, index) => {
                const done = item.completed;
                const current = item.id === activeId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveId(item.id)}
                    aria-current={current ? "true" : undefined}
                    title={`Câu ${index + 1} · ${done ? "đã xong" : "chưa xong"}`}
                    className={cx(
                      "inline-flex h-8 items-center gap-1 rounded border px-2 font-data text-small transition-colors",
                      current
                        ? "border-action bg-action-tint text-action-ink"
                        : done
                          ? "border-rule bg-ok-tint text-ok"
                          : "border-rule-strong text-ink-muted hover:bg-recess",
                    )}
                  >
                    {done && <CircleCheck size={12} strokeWidth={2} aria-hidden />}
                    {index + 1}
                  </button>
                );
              })}
            </div>
          )}

          {/* Khối đi tiếp nằm TRÊN bài tập chứ không dưới, và chỉ hiện khi cả
              bài đã xong: lúc đó phần dưới không còn việc gì để làm, còn lối đi
              tiếp thì phải nằm trong tầm mắt chứ không nằm sau một lần cuộn.
              `story.progress` được `load()` làm mới sau mỗi lượt chấm, nên nó
              xuất hiện ngay khi câu cuối vừa đúng. */}
          {story.progress.total_items > 0 &&
            story.progress.completed_items >= story.progress.total_items && (
              <DictationNextUp
                token={token}
                topicId={story.topic_id}
                sectionId={story.section_id}
                storyId={story.id}
              />
            )}

          {active && (
            <>
              <p className="mb-2 text-small text-ink-muted">
                Câu {activeIndex + 1}/{story.items.length} · {active.word_count} từ · nghe lại bao
                nhiêu lần cũng được
              </p>
              <DictationExercise
                // `key` chứ không phải effect reset — xem chú thích ở component.
                key={active.id}
                item={active}
                onGraded={() => token && void load(token)}
                onNext={next ? () => setActiveId(next.id) : undefined}
                footer={
                  next ? undefined : (
                    <p className="text-small text-ink-muted">Đây là câu cuối của bài.</p>
                  )
                }
              />
            </>
          )}
        </>
      )}
    </Page>
  );
}
