"use client";

import { API_ROUTES, type BlogPostAdmin, type BlogPostAdminPage } from "@toeic-pilot/shared";
import { Newspaper, PenLine, Send, Undo2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Button,
  ButtonLink,
  EmptyState,
  Page,
  PageHeader,
  PublishTag,
  SectionHeader,
  SkeletonList,
  Tag,
} from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/** Danh sách bài blog: nháp trước hay xuất bản trước không quan trọng — một
 *  hàng phẳng theo `updated_at`, không cây. Nút Xuất bản/Gỡ chỉ admin thấy
 *  (editor bấm cũng 403, nhưng giấu đi thì khỏi phải giải thích). */
export default function AdminBlogPage() {
  const { status, token, canPublish } = useRequireSession({ canEdit: true });
  const [posts, setPosts] = useState<BlogPostAdmin[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback((currentToken: string) => {
    void apiFetch<BlogPostAdminPage>(`${API_ROUTES.adminBlogPosts}?limit=100`, {
      token: currentToken,
    })
      .then((page) => setPosts(page.items))
      .catch(() => setError("Không tải được danh sách bài."));
  }, []);

  useEffect(() => {
    if (token) load(token);
  }, [token, load]);

  async function send(url: string) {
    if (!token) return;
    setBusy(url);
    setError(null);
    try {
      await apiFetch(url, { method: "POST", token });
      load(token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không thực hiện được.");
    } finally {
      setBusy(null);
    }
  }

  if (status !== "authenticated") {
    return (
      <Page>
        <SkeletonList rows={4} />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader title="Blog" description="Bài viết chia sẻ + kênh SEO (SPEC-BLOG)." />

      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <section className="mt-8">
        <SectionHeader
          title="Bài viết"
          aside={
            <ButtonLink href="/admin/blog/new" size="sm">
              <PenLine size={13} strokeWidth={2} aria-hidden />
              Viết bài mới
            </ButtonLink>
          }
        />

        {!posts && <SkeletonList rows={2} />}

        {posts?.length === 0 && (
          <EmptyState
            icon={Newspaper}
            title="Chưa có bài nào"
            description="Viết bài đầu tiên — blog chỉ hiện link ở nav khi đã có bài mồi."
          />
        )}

        <div className="space-y-2">
          {posts?.map((post) => (
            <div
              key={post.id}
              className="flex flex-wrap items-center gap-2 rounded border border-rule bg-panel px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <Link
                  href={`/admin/blog/${post.id}`}
                  className="block truncate font-semibold hover:text-accent"
                >
                  {post.title}
                </Link>
                <p className="truncate font-data text-small text-ink-faint">/blog/{post.slug}</p>
              </div>
              <Tag>{post.category}</Tag>
              <PublishTag status={post.status} />
              {post.status !== "published"
                ? canPublish && (
                    <Button
                      size="sm"
                      disabled={busy !== null}
                      title="Xuất bản bài này"
                      onClick={() => void send(API_ROUTES.adminBlogPostPublish(post.id))}
                    >
                      <Send size={13} strokeWidth={2} aria-hidden />
                      {busy ? "…" : "Xuất bản"}
                    </Button>
                  )
                : canPublish && (
                    <Button
                      size="sm"
                      variant="quiet"
                      disabled={busy !== null}
                      title="Gỡ khỏi trang đọc"
                      onClick={() => void send(API_ROUTES.adminBlogPostUnpublish(post.id))}
                    >
                      <Undo2 size={13} strokeWidth={2} aria-hidden />
                      Gỡ xuống
                    </Button>
                  )}
            </div>
          ))}
        </div>
      </section>
    </Page>
  );
}
