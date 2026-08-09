"use client";

import { API_ROUTES, type TopicPublic } from "@toeic-pilot/shared";
import { BookOpen, Headphones, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

import {
  Alert,
  ButtonLink,
  EmptyState,
  Page,
  PageHeader,
  PanelLink,
  SectionHeader,
  SkeletonList,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function LearnPage() {
  const { canEdit } = useSession();
  const [topics, setTopics] = useState<TopicPublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then(setTopics)
      .catch(() => setError("Không tải được danh sách chủ đề."));
  }, []);

  return (
    <Page>
      <PageHeader
        eyebrow="Learning Hub"
        title="Hôm nay học gì"
        description="Ôn lại những từ sắp quên, hoặc luyện nghe chép chính tả."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <PanelLink href="/learn/review">
          <RotateCcw size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
          <h2 className="mt-3 text-subtitle">Ôn tập từ vựng</h2>
          <p className="mt-1 text-small text-ink-muted">
            Lặp lại ngắt quãng — đến hạn trước, rồi mới đến từ mới.
          </p>
        </PanelLink>
        <PanelLink href="/learn/dictation">
          <Headphones size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
          <h2 className="mt-3 text-subtitle">Dictation</h2>
          <p className="mt-1 text-small text-ink-muted">
            Nghe, gõ lại, và đối chiếu từng từ với đáp án.
          </p>
        </PanelLink>
      </div>

      <section className="mt-12">
        <SectionHeader title="Chủ đề" />

        {error && <Alert>{error}</Alert>}
        {!topics && !error && <SkeletonList rows={3} />}

        {topics?.length === 0 && (
          <EmptyState
            icon={BookOpen}
            title="Chưa có chủ đề nào được xuất bản"
            description={
              canEdit
                ? "Bạn có quyền tạo chủ đề — vào khu quản lý nội dung để thêm."
                : "Nội dung đang được biên soạn. Quay lại sau nhé."
            }
            action={canEdit ? <ButtonLink href="/admin">Tạo chủ đề</ButtonLink> : undefined}
          />
        )}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {topics?.map((topic) => (
            <PanelLink key={topic.id} href={`/learn/vocabulary?topic=${topic.slug}`}>
              <h3>{topic.name}</h3>
              {topic.description && (
                <p className="mt-1 text-small text-ink-muted">{topic.description}</p>
              )}
            </PanelLink>
          ))}
        </div>
      </section>
    </Page>
  );
}
