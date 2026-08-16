"use client";

import { API_ROUTES, type VocabularyCollectionDetail } from "@toeic-pilot/shared";
import { Library } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { Alert, EmptyState, Page, PageHeader, PanelLink, Skeleton } from "@/components/ui";
import { apiFetch } from "@/lib/api";

const TONES = ["bg-accent-us", "bg-accent-uk", "bg-accent-au", "bg-accent-ca"] as const;

function CollectionDetail() {
  const collectionId = String(useParams<{ collectionId: string }>().collectionId ?? "");
  const [detail, setDetail] = useState<VocabularyCollectionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!collectionId) return;
    let stale = false;
    apiFetch<VocabularyCollectionDetail>(API_ROUTES.vocabularyCollection(collectionId))
      .then((body) => {
        if (!stale) setDetail(body);
      })
      .catch(() => setError("Không tải được tuyển tập."));
    return () => {
      stale = true;
    };
  }, [collectionId]);

  return (
    <Page>
      <Breadcrumbs trail={[{ href: "/learn/vocabulary", label: "Từ vựng" }]} />

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

          {detail.items.length === 0 && (
            <EmptyState
              icon={Library}
              title="Chưa có cuốn sách nào"
              description="Cuốn sách đang được biên soạn. Quay lại sau nhé."
            />
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {detail.items.map((item, index) => (
              <PanelLink
                key={item.id}
                href={`/learn/vocabulary/collection-items/${item.id}`}
                className="flex flex-col p-6"
              >
                <span aria-hidden className={`h-1 w-10 rounded ${TONES[index % TONES.length]!}`} />
                <h2 className="mt-4 text-subtitle">{item.name}</h2>
                {item.description && (
                  <p className="mt-1.5 text-small text-ink-muted">{item.description}</p>
                )}
                <p className="mt-3 font-data text-small tabular-nums text-ink-faint">
                  {item.topic_count} chủ đề
                </p>
              </PanelLink>
            ))}
          </div>
        </>
      )}
    </Page>
  );
}

export default function CollectionDetailPage() {
  return <CollectionDetail />;
}
