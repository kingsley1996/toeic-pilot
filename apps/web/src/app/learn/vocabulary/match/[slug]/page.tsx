"use client";

import {
  API_ROUTES,
  type TopicPublic,
  type VocabularyPage as VocabularyListPage,
  type VocabularySummary,
} from "@toeic-pilot/shared";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { Alert, ButtonLink, EmptyState, Page, PageHeader, Skeleton } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

import { MIN_WORDS, MatchGame } from "../../_games";

export default function MatchPage() {
  const rawSlug = String(useParams<{ slug: string }>().slug ?? "");
  const topicSlug = rawSlug === "all" ? null : rawSlug;
  const { token } = useSession();

  const [topics, setTopics] = useState<TopicPublic[] | null>(null);
  const [pool, setPool] = useState<VocabularySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<TopicPublic[]>(API_ROUTES.topics)
      .then(setTopics)
      .catch(() => {});
    const parts = [topicSlug ? `topic=${encodeURIComponent(topicSlug)}` : "", "limit=200"];
    apiFetch<VocabularyListPage>(`${API_ROUTES.vocabulary}?${parts.filter(Boolean).join("&")}`)
      .then((page) => setPool(page.items))
      .catch(() => setError("Không tải được từ vựng."));
  }, [topicSlug]);

  const topicName = useMemo(() => {
    if (!topicSlug) return "Tất cả từ vựng";
    return topics?.find((topic) => topic.slug === topicSlug)?.name ?? topicSlug;
  }, [topicSlug, topics]);

  return (
    <Page className="max-w-2xl">
      <Breadcrumbs
        trail={[
          { href: "/learn/vocabulary", label: "Từ vựng" },
          { href: `/learn/vocabulary/${rawSlug}`, label: topicName },
          { href: "", label: "Ghép từ" },
        ]}
      />
      <PageHeader
        eyebrow="Minigame"
        title="Ghép từ với nghĩa"
        description={`${topicName} — lật bàn cờ 4x4: mỗi từ có một ô và nghĩa của nó nằm ở ô khác. Ghép đúng thì cặp biến mất.`}
      />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {!pool && !error && <Skeleton className="h-56" />}

      {pool && pool.length < MIN_WORDS.match ? (
        <EmptyState
          title="Chưa đủ từ để chơi"
          description={`Cần ít nhất ${MIN_WORDS.match} từ, hiện có ${pool.length}.`}
          action={
            <ButtonLink href={`/learn/vocabulary/${rawSlug}`} variant="secondary">
              Về danh sách từ
            </ButtonLink>
          }
        />
      ) : (
        pool && (
          <MatchGame
            key={rawSlug}
            pool={pool}
            token={token}
            backHref={`/learn/vocabulary/${rawSlug}`}
          />
        )
      )}
    </Page>
  );
}
