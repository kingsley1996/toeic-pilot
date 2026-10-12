import type { Metadata } from "next";

import { ListTree, Newspaper } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { BlogShare, ReadingProgress } from "@/components/blog-client";
import { Breadcrumbs } from "@/components/breadcrumbs";
import { Page, Tag } from "@/components/ui";
import { getBlogPost, withCaptions, withHeadingIds, withMidCta } from "@/lib/blog-source";
import { SITE_URL } from "@/lib/site";

export const revalidate = 600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = await getBlogPost(slug);
  if (!post) return { title: "Không có bài này" };
  const url = `/blog/${post.slug}`;
  return {
    title: post.title,
    description: post.excerpt,
    alternates: { canonical: url },
    openGraph: {
      title: post.title,
      description: post.excerpt,
      url,
      type: "article",
      publishedTime: post.published_at ?? undefined,
      ...(post.cover_image_url ? { images: [{ url: post.cover_image_url }] } : {}),
    },
  };
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default async function BlogPostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await getBlogPost(slug);
  if (!post) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.excerpt,
    ...(post.cover_image_url ? { image: post.cover_image_url } : {}),
    datePublished: post.published_at,
    author: { "@type": "Organization", name: post.author_name },
  };

  const midCta = `<aside class="blog-cta"><p><strong>Chưa biết mình đang ở đâu?</strong> Làm test đầu vào 84 câu — miễn phí, có điểm ước tính ngay.</p><p><a href="/learn/placement">Test đầu vào miễn phí →</a></p></aside>`;
  const body = withMidCta(withHeadingIds(withCaptions(post.body_html)), midCta);
  const learnHref = post.related_part ? `/learn/parts/${post.related_part}` : "/learn/placement";

  return (
    <Page className="max-w-6xl">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <ReadingProgress />

      <Breadcrumbs
        trail={[
          { href: "/blog", label: "Blog" },
          { href: `/blog/${post.slug}`, label: post.title },
        ]}
      />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <article>
          <p className="mb-2 flex flex-wrap items-center gap-2 text-label text-ink-faint">
            <Tag>{post.category}</Tag>
            <span>
              {formatDate(post.published_at)} · {post.reading_minutes} phút đọc · {post.author_name}
            </span>
          </p>
          <h1 className="text-title font-bold leading-tight">{post.title}</h1>
          <p className="mt-2 text-subtitle text-ink-muted">{post.excerpt}</p>

          <div className="mt-4">
            <BlogShare title={post.title} url={`${SITE_URL}/blog/${post.slug}`} />
          </div>

          {post.cover_image_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={post.cover_image_url}
              alt=""
              className="mt-6 aspect-[16/9] w-full rounded object-cover"
            />
          )}

          {/* HTML đã qua allowlist ở server lúc cất bài — render thẳng. */}
          <div className="article-blog" dangerouslySetInnerHTML={{ __html: body }} />

          <div className="mt-8 flex flex-wrap gap-2">
            {post.tags.map((tag) => (
              <Link
                key={tag}
                href={`/blog?tag=${encodeURIComponent(tag)}`}
                className="rounded-full border border-rule-strong px-2.5 py-0.5 text-label text-ink-muted hover:bg-recess"
              >
                #{tag}
              </Link>
            ))}
          </div>

          <aside className="blog-cta mt-8">
            <p>
              <strong>Học tiếp:</strong>{" "}
              {post.related_part
                ? `bài này nhắc tới Part ${post.related_part} — vào luyện ngay.`
                : "làm test đầu vào để biết mình đang ở đâu."}
            </p>
            <p>
              <Link href={learnHref}>
                {post.related_part
                  ? `Luyện Part ${post.related_part} →`
                  : "Test đầu vào miễn phí →"}
              </Link>
            </p>
          </aside>

          {post.related.length > 0 && (
            <section className="mt-8" aria-label="Bài liên quan">
              <h2 className="mb-3 flex items-center gap-2 text-subtitle font-bold">
                <Newspaper size={16} aria-hidden /> Đọc tiếp
              </h2>
              <div className="grid gap-3 sm:grid-cols-3">
                {post.related.map((rel) => (
                  <Link
                    key={rel.slug}
                    href={`/blog/${rel.slug}`}
                    className="rounded border border-rule bg-panel p-3 hover:border-rule-strong"
                  >
                    <p className="text-small font-semibold leading-snug">{rel.title}</p>
                    <p className="mt-1 text-label text-ink-faint">{rel.reading_minutes} phút đọc</p>
                  </Link>
                ))}
              </div>
            </section>
          )}
        </article>

        {post.toc.length > 0 && (
          <aside className="hidden lg:block" aria-label="Mục lục">
            <nav className="sticky top-4 rounded border border-rule bg-panel p-4">
              <p className="mb-2 flex items-center gap-1.5 text-small font-bold">
                <ListTree size={14} aria-hidden /> Mục lục
              </p>
              <ul className="space-y-1.5">
                {post.toc.map((entry) => (
                  <li key={entry.id} className={entry.level === 3 ? "pl-4" : ""}>
                    <a href={`#${entry.id}`} className="text-small text-ink-muted hover:text-ink">
                      {entry.text}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
          </aside>
        )}
      </div>
    </Page>
  );
}
