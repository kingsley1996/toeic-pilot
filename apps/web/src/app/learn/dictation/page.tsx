"use client";

import { API_ROUTES, type DictationPage, type DictationTopicPublic } from "@toeic-pilot/shared";
import { BookOpen, Headphones } from "lucide-react";
import { useEffect, useState } from "react";

import {
  Alert,
  ButtonLink,
  EmptyState,
  Page,
  PageHeader,
  PanelLink,
  SkeletonList,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession, useSession } from "@/lib/session";

/** Tầng 1: các dạng bài nghe. */
export default function DictationTopicsPage() {
  const { status } = useRequireSession();
  const { canEdit } = useSession();
  const [topics, setTopics] = useState<DictationTopicPublic[] | null>(null);
  // Chỉ cần CON SỐ, không cần danh sách — nên giữ `total` của máy chủ chứ không
  // đếm mảng đã bị cắt trang. `items.length` sẽ đứng yên ở 50 khi câu lẻ vượt
  // một trang, và nhãn "50 câu" cho 130 câu là sai mà trông hoàn toàn hợp lý.
  const [standaloneCount, setStandaloneCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DictationTopicPublic[]>(API_ROUTES.dictationTopics)
      .then(setTopics)
      .catch(() => setError("Không tải được danh sách chủ đề."));
    // Câu chưa thuộc bài nào. Lối vào này chỉ hiện khi thật sự còn câu lẻ, nên
    // nó tự biến mất khi mọi thứ đã được xếp vào bài.
    apiFetch<DictationPage>(`${API_ROUTES.dictation}?standalone=true&limit=1`)
      .then((page) => setStandaloneCount(page.total))
      .catch(() => {});
  }, []);

  if (status !== "authenticated") {
    return (
      <Page className="max-w-3xl">
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page className="max-w-3xl">
      <PageHeader
        eyebrow="Dictation"
        title="Luyện nghe chép chính tả"
        description="Chọn một dạng bài, rồi chọn phần và bài để nghe."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!topics && !error && <SkeletonList rows={3} />}

      {topics?.length === 0 && (
        <EmptyState
          icon={Headphones}
          title="Chưa có dạng bài nào được xuất bản"
          description={
            canEdit
              ? "Tạo chủ đề, phần và bài trong khu quản trị, rồi xuất bản từ dưới lên."
              : "Nội dung đang được biên soạn. Quay lại sau nhé."
          }
          action={
            canEdit ? <ButtonLink href="/admin/dictation">Vào quản trị</ButtonLink> : undefined
          }
        />
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {topics?.map((topic) => (
          <PanelLink key={topic.id} href={`/learn/dictation/topics/${topic.id}`}>
            <BookOpen size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">{topic.name}</h2>
            {topic.description && (
              <p className="mt-1 text-small text-ink-muted">{topic.description}</p>
            )}
            <p className="mt-2 font-data text-small text-ink-faint">{topic.section_count} phần</p>
          </PanelLink>
        ))}
      </div>

      {standaloneCount > 0 && (
        <PanelLink href="/learn/dictation/standalone" className="mt-3 flex items-center gap-4">
          <Headphones
            size={16}
            strokeWidth={1.75}
            className="shrink-0 text-ink-muted"
            aria-hidden
          />
          <span className="min-w-0 flex-1">
            <span className="block font-semibold">Câu lẻ</span>
            <span className="mt-0.5 block text-small text-ink-muted">
              Câu chưa được xếp vào bài nào.
            </span>
          </span>
          <span className="shrink-0 font-data text-small text-ink-faint">
            {standaloneCount} câu
          </span>
        </PanelLink>
      )}
    </Page>
  );
}
