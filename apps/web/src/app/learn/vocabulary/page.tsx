"use client";

import { API_ROUTES, type TopicPublic, type VocabularyProgress } from "@toeic-pilot/shared";
import { BookOpen, Library, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Alert, EmptyState, Meter, Page, PageHeader, PanelLink, Skeleton } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/*
 * Trang từ vựng là một lưới CHỦ ĐỀ, không còn là cuốn từ điển phẳng.
 *
 * Danh sách từ chuyển xuống trang riêng `/learn/vocabulary/[slug]`: một chủ đề
 * 300 từ không phải thứ để đọc một mạch, nó là thứ để CHỌN rồi vào. Lưới card
 * trả lời câu hỏi "mình đang ở đâu với từng chủ đề" — mỗi card mang con số và,
 * khi đã đăng nhập, một thanh tiến độ thay cho lời hứa suông.
 */
const TOPIC_TONES = ["bg-accent-us", "bg-accent-uk", "bg-accent-au", "bg-accent-ca"] as const;

function TopicCard({
  topic,
  index,
  progress,
}: {
  topic: TopicPublic;
  index: number;
  progress: VocabularyProgress | null;
}) {
  const tone = TOPIC_TONES[index % TOPIC_TONES.length]!;
  return (
    <PanelLink href={`/learn/vocabulary/${topic.slug}`} className="flex flex-col p-6">
      <span aria-hidden className={`h-1 w-10 rounded ${tone}`} />
      <h2 className="mt-4 text-subtitle">{topic.name}</h2>
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

function VocabularyTopics() {
  const { token } = useSession();
  const [topics, setTopics] = useState<TopicPublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Tiến độ theo chủ đề, chỉ xin khi đã đăng nhập — endpoint có auth. Map đóng dấu
  // token: đăng nhập/đăng xuất phải đổi đúng thứ hiện ra mà không cần xoá state
  // trong effect.
  const [progressByTopic, setProgressByTopic] = useState<{
    token: string;
    data: Record<string, VocabularyProgress | null>;
  }>({ token: "", data: {} });

  useEffect(() => {
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then(setTopics)
      .catch(() => setError("Không tải được danh sách chủ đề."));
  }, []);

  useEffect(() => {
    if (!token || !topics) return;
    let stale = false;
    Promise.all(
      topics.map((topic) =>
        apiFetch<VocabularyProgress>(
          `${API_ROUTES.vocabularyProgress}?topic=${encodeURIComponent(topic.slug)}`,
          { token },
        ).catch(() => null),
      ),
    ).then((rows) => {
      if (stale) return;
      setProgressByTopic({
        token,
        data: Object.fromEntries(topics.map((topic, index) => [topic.slug, rows[index] ?? null])),
      });
    });
    return () => {
      stale = true;
    };
  }, [token, topics]);

  const progressFor = (slug: string) =>
    progressByTopic.token === token ? progressByTopic.data[slug] : null;

  return (
    <Page>
      <PageHeader
        eyebrow="Từ vựng"
        title="Chủ đề"
        description="Chọn một chủ đề để học từ, nghe phát âm bốn giọng và chơi minigame."
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!topics && !error && (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-44" />
          ))}
        </div>
      )}

      {topics?.length === 0 && (
        <EmptyState
          icon={Library}
          title="Chưa có chủ đề nào"
          description="Nội dung đang được biên soạn. Quay lại sau nhé."
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {topics?.map((topic, index) => (
          <TopicCard
            key={topic.id}
            topic={topic}
            index={index}
            progress={token ? progressFor(topic.slug) : null}
          />
        ))}
      </div>

      {topics && topics.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-3 rounded border border-rule bg-panel p-5">
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 font-semibold">
              <BookOpen size={15} strokeWidth={1.75} aria-hidden className="text-ink-muted" />
              Xem toàn bộ từ vựng
            </p>
            <p className="mt-0.5 text-small text-ink-muted">
              Duyệt cả {topics.length} chủ đề trong một danh sách.
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
  return <VocabularyTopics />;
}
