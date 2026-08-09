"use client";

import {
  API_ROUTES,
  type TopicPublic,
  type VocabularyDetail,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import { ChevronDown, Library } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { AccentRow } from "@/components/audio-button";
import {
  Alert,
  ButtonLink,
  EmptyState,
  Page,
  PageHeader,
  Panel,
  SkeletonList,
  Tag,
  cx,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

function VocabularyBrowser() {
  const topicSlug = useSearchParams().get("topic");
  const { canEdit } = useSession();
  const [topics, setTopics] = useState<TopicPublic[]>([]);
  // Đóng dấu chủ đề mà nó thuộc về, nên đổi chủ đề là danh sách cũ tự trở nên
  // lỗi thời theo suy diễn. Xoá nó từ trong effect sẽ là một setState đồng bộ
  // trong thân effect — một lượt render dây chuyền, và một khoảnh khắc mà từ
  // của chủ đề cũ hiện dưới tiêu đề của chủ đề mới.
  const [loaded, setLoaded] = useState<{ topic: string | null; words: VocabularySummary[] } | null>(
    null,
  );
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

      {/* Bộ lọc nằm trên trang chứ không chỉ ở URL: đến đây từ một bookmark thì
          trước đây không còn cách nào đổi chủ đề hay quay về danh sách đầy đủ. */}
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
          icon={Library}
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
            <Panel key={word.id} className={cx("overflow-hidden", open && "border-rule-strong")}>
              <button
                type="button"
                onClick={() => toggle(word.id)}
                aria-expanded={open}
                className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-recess"
              >
                <div className="min-w-0 flex-1">
                  <span className="font-semibold">{word.headword}</span>
                  {word.phonetic && (
                    <span className="ml-2 font-data text-small text-ink-faint">
                      {word.phonetic}
                    </span>
                  )}
                </div>
                <span className="hidden truncate text-small text-ink-muted sm:block">
                  {word.meaning_vi}
                </span>
                <Tag>{word.part_of_speech}</Tag>
                <ChevronDown
                  size={16}
                  strokeWidth={1.75}
                  aria-hidden
                  className={cx(
                    "shrink-0 text-ink-faint transition-transform",
                    open && "rotate-180",
                  )}
                />
              </button>

              {open && (
                <div className="animate-settle border-t border-rule bg-recess px-4 py-4">
                  {!detail ? (
                    <SkeletonList rows={1} />
                  ) : (
                    <>
                      <p className="font-semibold sm:hidden">{detail.meaning_vi}</p>
                      <p className="text-small text-ink-muted">{detail.meaning_en}</p>
                      {/* `showMissing` để giọng chưa có clip vẫn hiện ở dạng vô
                          hiệu hoá — người học cần biết nó tồn tại nhưng chưa
                          được thu, chứ không tưởng app chỉ có ba giọng. */}
                      <AccentRow clips={detail.headword_audio} showMissing className="mt-3" />
                      {detail.example && (
                        <div className="mt-4 rounded border border-rule bg-panel p-4">
                          <p className="italic">{detail.example}</p>
                          {detail.example_vi && (
                            <p className="mt-1 text-small text-ink-muted">{detail.example_vi}</p>
                          )}
                          <AccentRow clips={detail.example_audio} className="mt-3" />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </Panel>
          );
        })}
      </div>
    </Page>
  );
}

export default function VocabularyPage() {
  // useSearchParams đẩy route ra khỏi render tĩnh trừ khi nó nằm trong một
  // Suspense boundary; không có cái này thì build cảnh báo và trang bị ship
  // dưới dạng dynamic route mà chẳng để làm gì.
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
