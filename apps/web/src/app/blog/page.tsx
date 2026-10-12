import type { Metadata } from "next";

import type { BlogPostCard } from "@toeic-pilot/shared";
import Link from "next/link";

import { EmptyState, Page, PageHeader, Tag } from "@/components/ui";
import { getBlogPosts } from "@/lib/blog-source";

export const revalidate = 600;

export const metadata: Metadata = {
  title: "Blog luyện thi TOEIC — Mẹo, ngữ pháp, từ vựng",
  description:
    "Bài viết chia sẻ kinh nghiệm luyện thi TOEIC: mẹo làm từng part, ngữ pháp hay ra thi, từ vựng theo chủ đề.",
  alternates: { canonical: "/blog" },
};

const CATEGORIES = [
  { slug: "", label: "Tất cả" },
  { slug: "meo-lam-bai", label: "Mẹo làm bài" },
  { slug: "ngu-phap", label: "Ngữ pháp" },
  { slug: "tu-vung", label: "Từ vựng" },
  { slug: "kinh-nghiem", label: "Kinh nghiệm" },
  { slug: "thong-bao", label: "Thông báo" },
] as const;

const CATEGORY_LABEL: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.slug, c.label]),
);

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function BlogCard({ post }: { post: BlogPostCard }) {
  return (
    <Link
      href={`/blog/${post.slug}`}
      className="group flex flex-col overflow-hidden rounded border border-rule bg-panel hover:border-rule-strong"
    >
      {post.cover_image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={post.cover_image_url}
          alt=""
          loading="lazy"
          className="aspect-[16/9] w-full object-cover"
        />
      ) : (
        <div className="flex aspect-[16/9] w-full items-center justify-center bg-recess p-4 text-center text-small font-semibold text-ink-faint">
          {post.title}
        </div>
      )}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-center gap-2">
          <Tag>{CATEGORY_LABEL[post.category] ?? post.category}</Tag>
          <span className="text-label text-ink-faint">
            {formatDate(post.published_at)} · {post.reading_minutes} phút đọc
          </span>
        </div>
        <h2 className="font-semibold leading-snug group-hover:text-accent">{post.title}</h2>
        <p className="line-clamp-2 text-small text-ink-muted">{post.excerpt}</p>
      </div>
    </Link>
  );
}

export default async function BlogHubPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; tag?: string; q?: string }>;
}) {
  const params = await searchParams;
  const category = params.category ?? "";
  const page = await getBlogPosts({
    category: category || undefined,
    tag: params.tag,
    q: params.q,
  });

  return (
    <Page className="max-w-6xl">
      <PageHeader
        title="Blog TOEIC"
        description="Mẹo làm bài, ngữ pháp, từ vựng — viết bởi đội ngũ ToeicPilot."
      />

      <nav className="mb-6 flex flex-wrap gap-2" aria-label="Chuyên mục">
        {CATEGORIES.map((c) => {
          const active = category === c.slug;
          return (
            <Link
              key={c.slug}
              href={c.slug ? `/blog?category=${c.slug}` : "/blog"}
              aria-current={active ? "page" : undefined}
              className={`rounded-full border px-3 py-1 text-small font-semibold ${
                active
                  ? "border-ink bg-ink text-ground"
                  : "border-rule-strong text-ink-muted hover:bg-recess"
              }`}
            >
              {c.label}
            </Link>
          );
        })}
      </nav>

      {!page && (
        <EmptyState
          title="Chưa tải được bài viết"
          description="Máy chủ nội dung đang bận — quay lại sau ít phút."
        />
      )}

      {page && page.total === 0 && (
        <EmptyState title="Chưa có bài nào" description="Chuyên mục này đang được viết." />
      )}

      {page && page.total > 0 && (
        <>
          <p className="mb-4 text-small text-ink-muted">
            <span className="font-data">{page.total}</span> bài viết
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {page.items.map((post) => (
              <BlogCard key={post.slug} post={post} />
            ))}
          </div>
        </>
      )}
    </Page>
  );
}
