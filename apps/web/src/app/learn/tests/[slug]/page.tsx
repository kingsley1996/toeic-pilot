"use client";

import { API_ROUTES, type CollectionDetail } from "@toeic-pilot/shared";
import { ArrowLeft, Clock, FileText, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ButtonLink, EmptyState, Page, Panel, SectionHeader, Skeleton, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";

export default function CollectionPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const [collection, setCollection] = useState<CollectionDetail | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    apiFetch<CollectionDetail>(API_ROUTES.testCollection(slug))
      .then((data) => {
        if (!cancelled) setCollection(data);
      })
      .catch(() => {
        if (!cancelled) setMissing(true);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (missing) {
    return (
      <Page>
        <EmptyState
          icon={FileText}
          title="Không có bộ đề này"
          description="Có thể nó đã được gỡ, hoặc đường dẫn bị gõ sai."
          action={<ButtonLink href="/learn/tests">Về danh sách bộ đề</ButtonLink>}
        />
      </Page>
    );
  }

  if (collection === null) {
    return (
      <Page>
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-6 h-28 w-full" />
        <Skeleton className="mt-4 h-64 w-full" />
      </Page>
    );
  }

  return (
    <Page>
      <Link
        href="/learn/tests"
        className="inline-flex items-center gap-1.5 text-small font-semibold text-ink-muted hover:text-ink"
      >
        <ArrowLeft size={14} strokeWidth={2} aria-hidden />
        Bộ đề thi
      </Link>

      {/* Bậc nền chìm, không phải card nổi có gradient như bản tham khảo:
          §6.3 nói độ nổi là viền + bậc nền, và một dải màu chuyển sắc là đúng
          thứ hệ này đã bỏ đi có chủ ý. */}
      <section className="mt-4 rounded border border-rule bg-recess p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-2">
          {collection.source_tag && <Tag>{collection.source_tag}</Tag>}
          {collection.year !== null && <Tag>{collection.year}</Tag>}
        </div>
        <h1 className="mt-2">{collection.title}</h1>
        {collection.description && (
          <p className="mt-2 max-w-2xl text-ink-muted">{collection.description}</p>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-4 text-small text-ink-muted">
          <span>
            <span className="font-data tabular-nums text-ink">{collection.test_count}</span> đề
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Users size={14} strokeWidth={1.75} aria-hidden />
            <span className="font-data tabular-nums text-ink">{collection.attempt_count}</span> lượt
            làm
          </span>
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader title="Danh sách đề" />
        {collection.tests.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="Bộ đề này chưa có đề nào"
            description="Đề sẽ xuất hiện ở đây khi được xuất bản."
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {collection.tests.map((test) => (
              <Panel key={test.id} className="flex flex-wrap items-center gap-4 p-4">
                <div className="min-w-[12rem] flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <p className="font-semibold">{test.title}</p>
                    {/* Mọi đề hiện đều miễn phí — không có trường nào trong
                        `practice_test` phân biệt trả phí, nên đây là nhãn tĩnh.
                        Ngày có đề trả phí thì phải thêm cột rồi đọc từ đó, chứ
                        không được để nhãn này nói dối. */}
                    <Tag tone="ok">Miễn phí</Tag>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-small text-ink-muted">
                    <span className="inline-flex items-center gap-1.5">
                      <FileText size={13} strokeWidth={1.75} aria-hidden />
                      <span className="font-data tabular-nums">{test.question_count}</span> câu
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Users size={13} strokeWidth={1.75} aria-hidden />
                      <span className="font-data tabular-nums">{test.attempt_count}</span> lượt
                    </span>
                    {test.time_limit_seconds !== null && (
                      <span className="inline-flex items-center gap-1.5">
                        <Clock size={13} strokeWidth={1.75} aria-hidden />
                        <span className="font-data tabular-nums">
                          {Math.round(test.time_limit_seconds / 60)}
                        </span>{" "}
                        phút
                      </span>
                    )}
                  </div>
                </div>
                <ButtonLink
                  href={`/learn/tests/${slug}/${test.slug}`}
                  variant="secondary"
                  size="sm"
                >
                  Xem chi tiết
                </ButtonLink>
              </Panel>
            ))}
          </div>
        )}
      </section>
    </Page>
  );
}
