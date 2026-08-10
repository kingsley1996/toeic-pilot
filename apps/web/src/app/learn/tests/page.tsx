"use client";

import { API_ROUTES, type CollectionSummary } from "@toeic-pilot/shared";
import { BookOpen, ChevronRight, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState, Page, PageHeader, PanelLink, Skeleton, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";

/*
 * Danh sách bộ đề — màn đầu của khu luyện thi.
 *
 * KHÔNG dùng `useRequireSession`: đây là trang công khai. Người chưa có tài
 * khoản phải xem được có những đề gì trước khi quyết định đăng ký; bắt đăng nhập
 * để *nhìn* sẽ chặn đúng nhóm người mà trang này tồn tại để thuyết phục. Bắt
 * đầu làm bài mới cần tài khoản, vì lúc đó mới có gì để lưu.
 */

export default function TestCollectionsPage() {
  const [collections, setCollections] = useState<CollectionSummary[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<CollectionSummary[]>(API_ROUTES.testCollections)
      .then((rows) => {
        if (!cancelled) setCollections(rows);
      })
      .catch(() => {
        if (!cancelled) setCollections([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Page>
      <PageHeader
        eyebrow="Luyện thi"
        title="Đề thi thử TOEIC"
        description="Đề đầy đủ bảy phần Nghe và Đọc, chấm điểm tự động và quy đổi theo thang của từng đề."
      />

      {collections === null ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-36 w-full" />
        </div>
      ) : collections.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="Chưa có bộ đề nào"
          description="Nội dung đang được biên soạn. Quay lại sau nhé."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {collections.map((collection) => (
            <PanelLink
              key={collection.id}
              href={`/learn/tests/${collection.slug}`}
              className="flex flex-col p-5"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-subtitle leading-tight">{collection.title}</h2>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {collection.source_tag && <Tag>{collection.source_tag}</Tag>}
                    {collection.year !== null && <Tag>{collection.year}</Tag>}
                  </div>
                </div>
                <BookOpen
                  size={20}
                  strokeWidth={1.75}
                  aria-hidden
                  className="mt-0.5 shrink-0 text-ink-faint"
                />
              </div>

              {collection.description && (
                <p className="mt-3 line-clamp-2 text-small text-ink-muted">
                  {collection.description}
                </p>
              )}

              <div className="mt-4 flex items-center gap-4 text-small text-ink-muted">
                <span className="inline-flex items-center gap-1.5">
                  <BookOpen size={14} strokeWidth={1.75} aria-hidden />
                  <span className="font-data tabular-nums">{collection.test_count}</span> đề
                </span>
                {/* Số lượt làm ĐẾM từ bảng attempt, không phải một bộ đếm lưu
                    sẵn — cùng luật với tiến độ dictation và thống kê hồ sơ. */}
                <span className="inline-flex items-center gap-1.5">
                  <Users size={14} strokeWidth={1.75} aria-hidden />
                  <span className="font-data tabular-nums">{collection.attempt_count}</span> lượt
                  làm
                </span>
              </div>

              <span className="mt-4 inline-flex items-center gap-1 text-small font-semibold text-action-ink">
                Vào luyện
                <ChevronRight size={14} strokeWidth={2} aria-hidden />
              </span>
            </PanelLink>
          ))}
        </div>
      )}
    </Page>
  );
}
