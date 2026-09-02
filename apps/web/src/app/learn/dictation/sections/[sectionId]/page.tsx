"use client";

import { API_ROUTES, type DictationSectionDetail } from "@toeic-pilot/shared";
import { FileText } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { StoryProgressBar } from "@/components/story-progress";
import { Alert, EmptyState, Page, PageHeader, PanelLink, SkeletonList, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { GuestNotice } from "@/components/guest-notice";
import { useSession } from "@/lib/session";

/** Tầng 3: các bài trong một phần, kèm tiến độ của chính học viên. */
export default function DictationSectionPage() {
  // `useSession`, KHÔNG `useRequireSession`: cây đọc chép mở cho cả khách
  // vãng lai. Đăng nhập chỉ thêm cột tiến độ — endpoint đã nhận token tuỳ chọn.
  const { status, token } = useSession();
  const sectionId = String(useParams().sectionId);
  const [section, setSection] = useState<DictationSectionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Chờ phiên phân giải xong rồi mới gọi: gọi lúc `loading` là gọi KHÔNG
    // kèm token, và người đã đăng nhập sẽ thấy một cây không có tiến độ.
    if (status === "loading") return;
    apiFetch<DictationSectionDetail>(API_ROUTES.dictationSection(sectionId), {
      token: token ?? undefined,
    })
      .then(setSection)
      .catch(() => setError("Không tải được phần này."));
  }, [sectionId, token, status]);

  if (status === "loading" || (!section && !error)) {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page className="max-w-3xl">
      {error && <Alert>{error}</Alert>}

      {section && (
        <>
          <Breadcrumbs
            trail={[
              { href: "/learn/dictation", label: "Dictation" },
              { href: `/learn/dictation/topics/${section.topic_id}`, label: section.topic_name },
            ]}
          />
          <PageHeader eyebrow="Phần" title={section.name} description={section.description} />

          <GuestNotice className="mb-4" />

          {section.stories.length === 0 && (
            <EmptyState
              icon={FileText}
              title="Phần này chưa có bài nào"
              description="Nội dung đang được biên soạn."
            />
          )}

          <div className="space-y-2">
            {section.stories.map((story) => (
              <PanelLink
                key={story.id}
                href={`/learn/dictation/stories/${story.id}`}
                className="flex flex-wrap items-center gap-4"
              >
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{story.title}</span>
                    <Tag>độ khó {story.difficulty}</Tag>
                  </span>
                  {story.description && (
                    <span className="mt-0.5 block text-small text-ink-muted">
                      {story.description}
                    </span>
                  )}
                </span>
                {/* Tiến độ nằm ngay trên thẻ bài: câu hỏi đầu tiên khi quay lại
                    là "hôm qua mình dừng ở đâu", và trả lời nó ở đây rẻ hơn bắt
                    người ta mở từng bài ra xem. */}
                <StoryProgressBar progress={story.progress} className="w-full sm:w-56" />
              </PanelLink>
            ))}
          </div>
        </>
      )}
    </Page>
  );
}
