"use client";

import {
  API_ROUTES,
  type TopicPublic,
  type VocabularyCollectionPublic,
  type VocabularyProgress,
} from "@toeic-pilot/shared";
import { BookOpen, Library, Layers, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import {
  Alert,
  ButtonLink,
  EmptyState,
  Meter,
  Page,
  PageHeader,
  PanelLink,
  Skeleton,
} from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useDueCount } from "@/lib/due-count";
import { useSession } from "@/lib/session";

/*
 * Trang từ vựng mở ra ở tầng TUYỂN TẬP (collection), không còn là danh sách chủ
 * đề phẳng: học viên nghĩ "học bộ TOEIC 600 từ" trước khi nghĩ "chủ đề nào".
 * Từ vựng → tuyển tập → cuốn sách → chủ đề → trang từ.
 *
 * Chủ đề chưa được xếp vào cuốn nào (collection_item_id = null) vẫn liệt kê ở
 * đây thay vì biến mất — dữ liệu cũ không mất dấu khi cây phân cấp ra đời.
 */
const TONES = ["bg-accent-us", "bg-accent-uk", "bg-accent-au", "bg-accent-ca"] as const;

function CollectionCard({
  collection,
  index,
}: {
  collection: VocabularyCollectionPublic;
  index: number;
}) {
  const tone = TONES[index % TONES.length]!;
  return (
    <PanelLink
      href={`/learn/vocabulary/collections/${collection.id}`}
      className="flex flex-col p-6"
    >
      <span aria-hidden className={`h-1 w-10 rounded ${tone}`} />
      <h2 className="mt-4 text-subtitle">{collection.name}</h2>
      {collection.description && (
        <p className="mt-1.5 text-small text-ink-muted">{collection.description}</p>
      )}
      <p className="mt-3 flex items-center gap-1.5 font-data text-small tabular-nums text-ink-faint">
        <Layers size={13} strokeWidth={2} aria-hidden />
        {collection.topic_count} chủ đề
      </p>
    </PanelLink>
  );
}

function UnfiledTopicCard({
  topic,
  index,
  progress,
}: {
  topic: TopicPublic;
  index: number;
  progress: VocabularyProgress | null;
}) {
  const tone = TONES[index % TONES.length]!;
  return (
    <PanelLink href={`/learn/vocabulary/${topic.slug}`} className="flex flex-col p-6">
      <span aria-hidden className={`h-1 w-10 rounded ${tone}`} />
      <h3 className="mt-4 text-subtitle">{topic.name}</h3>
      {topic.description && <p className="mt-1.5 text-small text-ink-muted">{topic.description}</p>}
      <p className="mt-3 font-data text-small tabular-nums text-ink-faint">
        {topic.entry_count} từ
      </p>
      {progress && progress.total > 0 && (
        <div className="mt-4">
          <Meter
            value={progress.mastered}
            max={progress.total}
            ticks={Math.min(progress.total, 8)}
          />
          <p className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-small text-ink-muted">
            <span>{progress.mastered} đã thuộc</span>
            {progress.due > 0 && (
              <span className="text-ink">
                <RotateCcw size={12} strokeWidth={2} aria-hidden className="mr-1 inline" />
                {progress.due} cần ôn
              </span>
            )}
          </p>
        </div>
      )}
    </PanelLink>
  );
}

function VocabularyLanding() {
  const { token } = useSession();
  const due = useDueCount();
  const [collections, setCollections] = useState<VocabularyCollectionPublic[] | null>(null);
  const [topics, setTopics] = useState<TopicPublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Tiến độ chỉ xin cho chủ đề CHƯA XẾP (đăng nhập mới có), map đóng dấu token để
  // đăng nhập/đăng xuất đổi đúng thứ hiện ra mà không cần xoá state trong effect.
  const [progressByTopic, setProgressByTopic] = useState<{
    token: string;
    data: Record<string, VocabularyProgress | null>;
  }>({ token: "", data: {} });

  useEffect(() => {
    apiFetch<VocabularyCollectionPublic[]>(API_ROUTES.vocabularyCollections)
      .then(setCollections)
      .catch(() => setError("Không tải được danh sách tuyển tập."));
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then(setTopics)
      .catch(() => setError("Không tải được danh sách chủ đề."));
  }, []);

  const unfiled = (topics ?? []).filter((topic) => topic.collection_item_id === null);

  useEffect(() => {
    if (!token || unfiled.length === 0) return;
    let stale = false;
    Promise.all(
      unfiled.map((topic) =>
        apiFetch<VocabularyProgress>(
          `${API_ROUTES.vocabularyProgress}?topic=${encodeURIComponent(topic.slug)}`,
          { token },
        ).catch(() => null),
      ),
    ).then((rows) => {
      if (stale) return;
      setProgressByTopic({
        token,
        data: Object.fromEntries(unfiled.map((topic, index) => [topic.slug, rows[index] ?? null])),
      });
    });
    return () => {
      stale = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, topics]);

  const progressFor = (slug: string) =>
    progressByTopic.token === token ? progressByTopic.data[slug] : null;

  return (
    <Page>
      <PageHeader
        eyebrow="Từ vựng"
        title="Tuyển tập"
        description="Chọn một tuyển tập để học từ theo cuốn sách, nghe phát âm bốn giọng và chơi minigame."
      />

      {/*
       * Việc đến hạn đứng TRƯỚC danh sách tuyển tập, vì nó là câu trả lời cho
       * "hôm nay tôi nên làm gì" — còn tuyển tập trả lời "tôi muốn học thêm gì".
       * Đặt dưới danh sách thì người học phải cuộn qua mọi cuốn sách mới thấy
       * việc đã đến hạn, và hàng đợi SM-2 chỉ có giá trị khi được làm đúng ngày.
       *
       * `useDueCount` trả 0 cho khách vãng lai, nên khối này tự vắng mặt.
       */}
      {due > 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-3 rounded border border-action bg-action-tint p-5">
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 font-semibold text-action-ink">
              <RotateCcw size={15} strokeWidth={2} aria-hidden />
              <span className="font-data tabular-nums">{due}</span> từ đến hạn ôn
            </p>
            <p className="mt-0.5 text-small text-ink-muted">Ôn đúng lúc sắp quên thì nhớ lâu.</p>
          </div>
          <ButtonLink href="/learn/review" size="sm">
            Ôn ngay
          </ButtonLink>
        </div>
      )}

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!collections && !error && (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-44" />
          ))}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {collections?.map((collection, index) => (
          <CollectionCard key={collection.id} collection={collection} index={index} />
        ))}
      </div>

      {collections?.length === 0 && (
        <EmptyState
          icon={Library}
          title="Chưa có tuyển tập nào"
          description="Nội dung đang được biên soạn. Quay lại sau nhé."
        />
      )}

      {unfiled.length > 0 && (
        <section className="mt-12">
          <h2 className="text-heading text-ink">Chủ đề khác</h2>
          <p className="mt-1 text-small text-ink-muted">
            Các chủ đề chưa được xếp vào tuyển tập nào.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {unfiled.map((topic, index) => (
              <UnfiledTopicCard
                key={topic.id}
                topic={topic}
                index={index}
                progress={token ? progressFor(topic.slug) : null}
              />
            ))}
          </div>
        </section>
      )}

      {topics && topics.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-3 rounded border border-rule bg-panel p-5">
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 font-semibold">
              <BookOpen size={15} strokeWidth={1.75} aria-hidden className="text-ink-muted" />
              Xem toàn bộ từ vựng
            </p>
            <p className="mt-0.5 text-small text-ink-muted">
              Duyệt mọi chủ đề trong một danh sách.
            </p>
          </div>
          <Link
            href="/learn/vocabulary/all"
            className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded border border-rule-strong bg-panel px-3.5 text-body font-semibold text-ink transition-colors hover:bg-recess"
          >
            Mở danh sách
          </Link>
        </div>
      )}
    </Page>
  );
}

export default function VocabularyPage() {
  return <VocabularyLanding />;
}
