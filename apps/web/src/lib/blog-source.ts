import type { BlogPostCardPage, BlogPostDetail } from "@toeic-pilot/shared";

import { API_ROUTES } from "@toeic-pilot/shared";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/*
 * Nguồn bài blog cho trang đọc công khai (SPEC-BLOG §4). Chạy ở server
 * component nên `fetch` thẳng, ISR 10 phút như trang cảnh — bài mới publish
 * hiện ở hub chậm nhất 10 phút, đổi lại không trả request API mỗi lượt xem.
 * API hỏng thì trả null và trang hiện EmptyState thay vì 500: blog là nội
 * dung phụ, không được đánh sập cả route.
 */
async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { next: { revalidate: 600 } });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function getBlogPosts(params: {
  category?: string;
  tag?: string;
  q?: string;
}): Promise<BlogPostCardPage | null> {
  const search = new URLSearchParams({ limit: "24" });
  if (params.category) search.set("category", params.category);
  if (params.tag) search.set("tag", params.tag);
  if (params.q) search.set("q", params.q);
  return getJson<BlogPostCardPage>(`${API_ROUTES.blogPosts}?${search}`);
}

export async function getBlogPost(slug: string): Promise<BlogPostDetail | null> {
  return getJson<BlogPostDetail>(API_ROUTES.blogPost(slug));
}

export async function getBlogSlugs(): Promise<string[]> {
  const page = await getJson<BlogPostCardPage>(`${API_ROUTES.blogPosts}?limit=200`);
  return page?.items.map((item) => item.slug) ?? [];
}

/** Nhãn tiếng Việt của chuyên mục — dùng chung hub + trang bài (đừng để một
 *  nơi hiện "Mẹo làm bài", một nơi hiện slug thô "meo-lam-bai"). */
export const BLOG_CATEGORY_LABEL: Record<string, string> = {
  "meo-lam-bai": "Mẹo làm bài",
  "ngu-phap": "Ngữ pháp",
  "tu-vung": "Từ vựng",
  "kinh-nghiem": "Kinh nghiệm",
  "thong-bao": "Thông báo",
};

/**
 * Bọc ảnh có `title` thành figure + caption lúc render (SPEC-BLOG: `title`
 * của ảnh thành caption). Chạy trên HTML đã sanitize — regex chỉ bắt thẻ
 * `<img ...>` nguyên vẹn, không lồng nhau nên không có chỗ cho catastrophic
 * backtracking (`[^>]*` một tầng duy nhất).
 */
export function withCaptions(html: string): string {
  return html.replace(/<img([^>]*?)\stitle="([^"]+)"([^>]*?)>/g, (_match, before, title, after) => {
    const attrs = `${before} ${after}`.replace(/\s+/g, " ").trim();
    const escaped = title.replace(/</g, "&lt;");
    return `<figure class="blog-figure"><img ${attrs} alt="${escaped}"><figcaption>${escaped}</figcaption></figure>`;
  });
}

/** Chèn CTA giữa bài sau heading thứ 2 (render-time — sửa CTA không đụng 100 bài). */
export function withMidCta(html: string, cta: string): string {
  let seen = 0;
  let index = -1;
  while (seen < 2) {
    index = html.indexOf("</h2>", index + 1);
    if (index === -1) return html;
    seen += 1;
  }
  const at = index + "</h2>".length;
  return html.slice(0, at) + cta + html.slice(at);
}

function anchorOf(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/**
 * Gắn `id` cho H2/H3 để mục lục neo được — cùng thuật toán với
 * `toc_from_doc` phía API (text thuần, lowercase, cụm không a-z0-9 thành
 * `-`). Thẻ inline (đậm/link) giữ nguyên trong output, chỉ tuốt ra lúc tính
 * id — heading Tiptap không bao giờ chứa thẻ block lồng nên `(.*?)` an toàn.
 */
export function withHeadingIds(html: string): string {
  return html.replace(/<h([23])>(.*?)<\/h\1>/g, (match, level, inner) => {
    const text = String(inner).replace(/<[^>]*>/g, "");
    const id = anchorOf(text) || "h";
    if (id === "h") return match;
    return `<h${level} id="${id}">${inner}</h${level}>`;
  });
}
