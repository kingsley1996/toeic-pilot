"use client";

import { API_ROUTES, type DictationTopicDetail } from "@toeic-pilot/shared";
import { Layers } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { Alert, EmptyState, Page, PageHeader, PanelLink, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { GuestNotice } from "@/components/guest-notice";
import { useSession } from "@/lib/session";

/** Tầng 2: các phần trong một dạng bài. */
export default function DictationTopicPage() {
  const { status } = useSession();
  const topicId = String(useParams().topicId);
  const [topic, setTopic] = useState<DictationTopicDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DictationTopicDetail>(API_ROUTES.dictationTopic(topicId))
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
      <Breadcrumbs trail={[{ href: "/learn/dictation", label: "Dictation" }]} />

      {error && <Alert>{error}</Alert>}

      {topic && (
        <>
          <PageHeader eyebrow="Dạng bài" title={topic.name} description={topic.description} />

          <GuestNotice className="mb-4" />

          {topic.sections.length === 0 && (
            <EmptyState
              icon={Layers}
              title="Chủ đề này chưa có phần nào"
              description="Nội dung đang được biên soạn."
            />
          )}

          <div className="space-y-2">
            {topic.sections.map((section) => (
              <PanelLink
                key={section.id}
                href={`/learn/dictation/sections/${section.id}`}
                className="flex items-center gap-4"
              >
                <Layers
                  size={16}
                  strokeWidth={1.75}
                  className="shrink-0 text-ink-muted"
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{section.name}</span>
                  {section.description && (
                    <span className="mt-0.5 block text-small text-ink-muted">
                      {section.description}
                    </span>
                  )}
                </span>
                <span className="shrink-0 font-data text-small text-ink-faint">
                  {section.story_count} bài
                </span>
              </PanelLink>
            ))}
          </div>
        </>
      )}
    </Page>
  );
}
