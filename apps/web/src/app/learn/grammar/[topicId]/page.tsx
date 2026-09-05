"use client";

import { API_ROUTES, type GrammarTopicDetail } from "@toeic-pilot/shared";
import { BookOpen, Check, PenLine } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { GuestNotice } from "@/components/guest-notice";
import { Alert, EmptyState, Page, PageHeader, PanelLink, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/** Tầng 2: các bài học trong một chủ đề. */
export default function GrammarTopicPage() {
  const { status } = useSession();
  const topicId = String(useParams().topicId);
  const [topic, setTopic] = useState<GrammarTopicDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<GrammarTopicDetail>(API_ROUTES.grammarTopic(topicId))
      .then(setTopic)
      .catch(() => setError("Không tải được chủ đề này."));
  }, [topicId]);

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

          <GuestNotice className="mb-4" />

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
