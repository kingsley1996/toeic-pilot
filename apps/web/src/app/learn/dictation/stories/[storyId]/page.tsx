"use client";

import { API_ROUTES, type DictationStoryDetail } from "@toeic-pilot/shared";
import { ArrowLeft, CircleCheck, CircleDashed } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { DictationExercise } from "@/components/dictation-exercise";
import { DictationNextUp } from "@/components/dictation-next";
import { StoryProgressBar } from "@/components/story-progress";
import { Alert, EmptyState, Page, SkeletonList, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { GuestNotice } from "@/components/guest-notice";
import { useSession } from "@/lib/session";

/** Tầng 4: một bài văn, làm tuần tự từng câu. */
export default function DictationStoryPage() {
  const { status, token } = useSession();
  const storyId = String(useParams().storyId);
  const router = useRouter();
  const [story, setStory] = useState<DictationStoryDetail | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  // Đích "Đi tiếp" của bài đã xong, để Enter ở câu cuối đi được luôn thay vì
  // chấm lại câu vừa đúng.
  const [nextHref, setNextHref] = useState<{ storyId: string; href: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rememberNext = useCallback(
    (href: string | null) => setNextHref(href ? { storyId, href } : null),
    [storyId],
  );

  const load = useCallback(
    (t?: string) =>
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
    // Chờ phiên phân giải xong rồi mới gọi: gọi lúc `loading` là gọi KHÔNG kèm
    // token, và người đã đăng nhập sẽ thấy một bài không có câu nào được đánh
    // dấu đã xong.
    if (status !== "loading") void load(token ?? undefined);
  }, [token, status, load]);

  if (status === "loading" || (!story && !error)) {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={5} />
      </Page>
    );
  }

  const active = story?.items.find((item) => item.id === activeId) ?? null;
  const activeIndex = story?.items.findIndex((item) => item.id === activeId) ?? -1;
  const next = story && activeIndex >= 0 ? story.items[activeIndex + 1] : undefined;
  // Chỉ dùng đích của CHÍNH bài này: đổi bài mà state cũ còn sót lại thì Enter
  // sẽ nhảy về bài trước.
  const continueHref = nextHref && story && nextHref.storyId === story.id ? nextHref.href : null;

  return (
    <Page className="py-4 sm:py-6">
      {error && <Alert>{error}</Alert>}

      {story && (
        // Chế độ luyện: thanh trên gom tiêu đề + tiến độ + dải câu, phần gõ
        // chiếm phần còn lại và tự căn giữa. Trang chủ đề/section vẫn giữ
        // PageHeader đầy đủ; ở đây người học đang gõ, không đang đọc giới thiệu.
        <div className="mx-auto flex min-h-[calc(100dvh-16rem)] w-full max-w-5xl flex-col">
          <div className="flex items-center gap-2">
            <Link
              href={`/learn/dictation/sections/${story.section_id}`}
              aria-label={`Quay lại ${story.section_name}`}
              title={`Quay lại ${story.section_name}`}
              className="grid h-8 w-8 shrink-0 place-items-center rounded border border-rule-strong text-ink-muted transition-colors hover:bg-recess hover:text-ink"
            >
              <ArrowLeft size={16} strokeWidth={2} aria-hidden />
            </Link>
            <h1 className="min-w-0 truncate text-subtitle font-semibold">{story.title}</h1>
            <StoryProgressBar progress={story.progress} className="ml-auto w-36 shrink-0" />
          </div>

          <GuestNotice className="mt-3" />

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
            <div className="mb-3 mt-3 flex flex-wrap gap-1.5">
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
              <div className="mb-3">
                <DictationNextUp
                  token={token}
                  topicId={story.topic_id}
                  sectionId={story.section_id}
                  storyId={story.id}
                  onResolved={rememberNext}
                />
              </div>
            )}

          {active && (
            <>
              <p className="mb-1 mt-1 text-small text-ink-muted">
                Câu {activeIndex + 1}/{story.items.length} · {active.word_count} từ · nghe lại bao
                nhiêu lần cũng được
              </p>
              <div className="flex flex-1 flex-col justify-center">
                <DictationExercise
                  // `key` chứ không phải effect reset — xem chú thích ở component.
                  key={active.id}
                  item={active}
                  onGraded={() => token && void load(token)}
                  onNext={
                    next
                      ? () => setActiveId(next.id)
                      : continueHref
                        ? () => router.push(continueHref)
                        : undefined
                  }
                  nextLabel={next ? "Câu tiếp theo" : "Đi tiếp"}
                  footer={
                    next || continueHref ? undefined : (
                      <p className="text-small text-ink-muted">Đây là câu cuối của bài.</p>
                    )
                  }
                />
              </div>
            </>
          )}
        </div>
      )}
    </Page>
  );
}
