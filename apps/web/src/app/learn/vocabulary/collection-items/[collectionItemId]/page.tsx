"use client";

import { API_ROUTES, type VocabularyItemDetail } from "@toeic-pilot/shared";
import { Library } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { Alert, EmptyState, Page, PageHeader, PanelLink, Skeleton } from "@/components/ui";
import { apiFetch } from "@/lib/api";

const TONES = ["bg-accent-us", "bg-accent-uk", "bg-accent-au", "bg-accent-ca"] as const;

/*
 * Tầng cuốn sách của cây từ vựng, đi qua UUID — KHÔNG có slug: cuốn sách là tầng
 * TRUNG GIAN, không ai deep-link thẳng tới nó, nên slug chỉ kéo thêm ràng buộc
 * duy nhất-trong-phạm-vi-cha mà không đổi được gì. Đúng tiền lệ `DictationSection`.
 */
function CollectionItemDetail() {
  const itemId = String(useParams<{ collectionItemId: string }>().collectionItemId ?? "");
  const [detail, setDetail] = useState<VocabularyItemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!itemId) return;
    let stale = false;
    apiFetch<VocabularyItemDetail>(API_ROUTES.vocabularyCollectionItem(itemId))
      .then((body) => {
        if (!stale) setDetail(body);
      })
      .catch(() => setError("Không tải được cuốn sách này."));
    return () => {
      stale = true;
    };
  }, [itemId]);

  return (
    <Page>
      {detail && (
        <Breadcrumbs
          trail={[
            { href: "/learn/vocabulary", label: "Từ vựng" },
            {
              href: `/learn/vocabulary/collections/${detail.collection_id}`,
              label: detail.collection_name,
            },
          ]}
        />
      )}

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      {!detail && !error && (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 2 }, (_, index) => (
            <Skeleton key={index} className="h-40" />
          ))}
        </div>
      )}

      {detail && (
        <>
          <PageHeader title={detail.name} description={detail.description ?? undefined} />

          {detail.topics.length === 0 && (
            <EmptyState
              icon={Library}
              title="Chưa có chủ đề nào trong cuốn sách này"
              description="Quay lại sau nhé."
            />
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {detail.topics.map((topic, index) => (
              <PanelLink
                key={topic.id}
                href={`/learn/vocabulary/${topic.slug}`}
                className="flex flex-col p-6"
              >
                <span aria-hidden className={`h-1 w-10 rounded ${TONES[index % TONES.length]!}`} />
                <h2 className="mt-4 text-subtitle">{topic.name}</h2>
                {topic.description && (
                  <p className="mt-1.5 text-small text-ink-muted">{topic.description}</p>
                )}
                <p className="mt-3 font-data text-small tabular-nums text-ink-faint">
                  {topic.entry_count} từ
                </p>
              </PanelLink>
            ))}
          </div>
        </>
      )}
    </Page>
  );
}

export default function CollectionItemDetailPage() {
  return <CollectionItemDetail />;
}
