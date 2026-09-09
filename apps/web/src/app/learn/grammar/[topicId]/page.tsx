"use client";

import { API_ROUTES, type GrammarTopicDetail } from "@toeic-pilot/shared";
import { BookOpen, Check, Lock, PenLine } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { LoginModal } from "@/components/login-modal";
import { Alert, EmptyState, Page, PageHeader, PanelLink, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/**
 * Tầng 2: các bài học trong một chủ đề.
 *
 * Chặn ở CẢ HAI đầu (khuôn trang đề chi tiết): trang danh sách bắt lần bấm, còn
 * đây bắt người gõ thẳng URL hay mở lại dấu trang — khách vào là thấy cổng đăng
 * nhập ngay tại chỗ, kèm nút đóng để quay lại.
 */
export default function GrammarTopicPage() {
  const { status, token } = useSession();
  const topicId = String(useParams().topicId);
  const [topic, setTopic] = useState<GrammarTopicDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    apiFetch<GrammarTopicDetail>(API_ROUTES.grammarTopic(topicId), { token: token ?? undefined })
      .then(setTopic)
      .catch(() => setError("Không tải được chủ đề này."));
    // `token` trong deps: đăng nhập xong từ hộp thoại là fetch lại có token.
  }, [topicId, token]);

  if (status === "anonymous") {
    return (
      <Page className="max-w-3xl">
        <Breadcrumbs trail={[{ href: "/learn/grammar", label: "Ngữ pháp" }]} />
        <div className="mt-4">
          <EmptyState
            icon={Lock}
            title="Đăng nhập để học ngữ pháp"
            description={
              <>
                Học ngữ pháp <strong className="font-semibold text-ink">miễn phí</strong>. Đăng nhập
                để lưu tiến độ bài học và có trải nghiệm học tập trọn vẹn hơn.
              </>
            }
          />
        </div>
        <LoginModal
          open={!dismissed}
          onClose={() => setDismissed(true)}
          onSuccess={() => setDismissed(true)}
          next={`/learn/grammar/${topicId}`}
          title="Đăng nhập để học ngữ pháp"
        />
      </Page>
    );
  }

  if (status === "loading" || (!topic && !error)) {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={[{ href: "/learn/grammar", label: "Ngữ pháp" }]} />

      {error && <Alert>{error}</Alert>}

      {topic && (
        <>
          <PageHeader eyebrow="Chủ đề" title={topic.title} description={topic.summary} />

          {topic.lessons.length === 0 && (
            <EmptyState
              icon={BookOpen}
              title="Chủ đề này chưa có bài nào"
              description="Lý thuyết đang được soạn."
            />
          )}

          <div className="space-y-2">
            {topic.lessons.map((lesson) => {
              const LessonIcon = lesson.kind === "practice" ? PenLine : BookOpen;
              return (
                <PanelLink
                  key={lesson.id}
                  href={`/learn/grammar/${topic.id}/${lesson.id}`}
                  className="flex items-center gap-4"
                >
                  <LessonIcon
                    size={16}
                    strokeWidth={1.75}
                    className="shrink-0 text-ink-muted"
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1 block font-semibold">{lesson.title}</span>
                  {lesson.completed && (
                    <Check size={14} strokeWidth={2} className="shrink-0 text-ok" aria-hidden />
                  )}
                </PanelLink>
              );
            })}
          </div>
        </>
      )}
    </Page>
  );
}
