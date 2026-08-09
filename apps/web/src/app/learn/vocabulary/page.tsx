"use client";

import {
  API_ROUTES,
  type TopicPublic,
  type VocabularyDetail,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AccentRow } from "@/components/audio-button";
import {
  Alert,
  Badge,
  ButtonLink,
  Card,
  EmptyState,
  Page,
  PageHeader,
  SkeletonList,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

function VocabularyBrowser() {
  const topicSlug = useSearchParams().get("topic");
  const { canEdit } = useSession();
  const [topics, setTopics] = useState<TopicPublic[]>([]);
  // Stamped with the topic it belongs to, so switching topic makes the previous
  // list stale by derivation. Clearing it from the effect instead would be a
  // synchronous setState in an effect body — a cascading render, and a moment
  // where the old topic's words are shown under the new topic's heading.
  const [loaded, setLoaded] = useState<{
    topic: string | null;
    words: VocabularySummary[];
  } | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<VocabularyDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then(setTopics)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const query = topicSlug ? `?topic=${encodeURIComponent(topicSlug)}` : "";
    apiFetch<VocabularySummary[]>(`${API_ROUTES.vocabulary}${query}`)
      .then((list) => setLoaded({ topic: topicSlug, words: list }))
      .catch(() => setError("Không tải được danh sách từ."));
  }, [topicSlug]);

  const words = loaded?.topic === topicSlug ? loaded.words : null;

  function toggle(id: string) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    setDetail(null);
    apiFetch<VocabularyDetail>(API_ROUTES.vocabularyDetail(id))
      .then(setDetail)
      .catch(() => setError("Không tải được chi tiết từ này."));
  }

  const activeTopic = topics.find((topic) => topic.slug === topicSlug);

  return (
    <Page>
      <PageHeader
        eyebrow="Từ vựng"
        title={activeTopic ? activeTopic.name : "Tất cả từ vựng"}
        description={
          activeTopic?.description ?? "Bấm vào một từ để xem nghĩa, ví dụ và phát âm bốn giọng."
        }
      />

      {/* The filter lives on the page rather than only in the URL: arriving here
          from a bookmark used to leave no way to change topic or get back to the
          full list. */}
      {topics.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          <ButtonLink
            href="/learn/vocabulary"
            size="sm"
            variant={topicSlug ? "secondary" : "primary"}
          >
            Tất cả
          </ButtonLink>
          {topics.map((topic) => (
            <ButtonLink
              key={topic.id}
              href={`/learn/vocabulary?topic=${topic.slug}`}
              size="sm"
              variant={topic.slug === topicSlug ? "primary" : "secondary"}
            >
              {topic.name}
            </ButtonLink>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!words && <SkeletonList rows={5} />}

      {words?.length === 0 && (
        <EmptyState
          icon="🗂️"
          title={activeTopic ? `Chủ đề ${activeTopic.name} chưa có từ nào` : "Chưa có từ nào"}
          description={
            canEdit
              ? "Từ mới phải có đủ audio bốn giọng trước khi xuất bản được."
              : "Nội dung đang được biên soạn."
          }
          action={canEdit ? <ButtonLink href="/admin/vocabulary">Thêm từ</ButtonLink> : undefined}
        />
      )}

      <div className="space-y-2">
        {words?.map((word) => {
          const open = openId === word.id;
          return (
            <Card key={word.id} className={cx("overflow-hidden", open && "border-brand")}>
              <button
                type="button"
                onClick={() => toggle(word.id)}
                aria-expanded={open}
                className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-surface-sunken"
              >
                <div className="min-w-0 flex-1">
                  <span className="font-semibold">{word.headword}</span>
                  {word.phonetic && (
                    <span className="ml-2 font-mono text-sm text-text-subtle">{word.phonetic}</span>
                  )}
                </div>
                <span className="hidden truncate text-sm text-text-muted sm:block">
                  {word.meaning_vi}
                </span>
                <Badge>{word.part_of_speech}</Badge>
                <span
                  aria-hidden
                  className={cx("text-text-subtle transition-transform", open && "rotate-180")}
                >
                  ▾
                </span>
              </button>

              {open && (
                <div className="animate-rise border-t border-border bg-surface-sunken px-5 py-4">
                  {!detail ? (
                    <SkeletonList rows={1} />
                  ) : (
                    <>
                      <p className="font-medium sm:hidden">{detail.meaning_vi}</p>
                      <p className="text-sm text-text-muted">{detail.meaning_en}</p>
                      <AccentRow clips={detail.headword_audio} className="mt-3" />
                      {detail.example && (
                        <div className="mt-4 rounded-lg border border-border bg-surface p-4">
                          <p className="italic">{detail.example}</p>
                          {detail.example_vi && (
                            <p className="mt-1 text-sm text-text-muted">{detail.example_vi}</p>
                          )}
                          <AccentRow clips={detail.example_audio} className="mt-3" />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </Page>
  );
}

export default function VocabularyPage() {
  // useSearchParams opts the route out of static rendering unless it sits inside
  // a Suspense boundary; without this the build warns and the page ships as a
  // dynamic route for no reason.
  return (
    <Suspense
      fallback={
        <Page>
          <SkeletonList rows={5} />
        </Page>
      }
    >
      <VocabularyBrowser />
    </Suspense>
  );
}
