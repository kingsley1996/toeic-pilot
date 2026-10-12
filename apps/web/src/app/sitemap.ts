import type { MetadataRoute } from "next";

import { SCENES } from "@/content/scenes";
import { getBlogSlugs } from "@/lib/blog-source";
import { SITE_URL } from "@/lib/site";

/*
 * URL public duy nhất crawler đọc được nội dung: trang giới thiệu, hub scenes,
 * 12 trang cảnh (tiêu đề + mô tả SSR), hub từ vựng, bảng xếp hạng, hub blog +
 * từng bài đã xuất bản. Mọi route còn lại sau đăng nhập hoặc là trang quản trị
 * — cho vào đây chỉ làm Google index trang skeleton rỗng.
 *
 * Slug blog lấy từ API lúc build (ISR 1 giờ — bài mới publish vào sitemap
 * chậm nhất 1 giờ, chấp nhận được cho SEO). API hỏng thì sitemap thiếu blog
 * chứ không 500 cả sitemap.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  let slugs: string[] = [];
  try {
    slugs = await getBlogSlugs();
  } catch {
    slugs = [];
  }
  return [
    { url: SITE_URL, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/learn/scenes`, changeFrequency: "weekly", priority: 0.9 },
    ...SCENES.map((scene) => ({
      url: `${SITE_URL}/learn/scenes/${scene.id}`,
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
    { url: `${SITE_URL}/learn/vocabulary`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE_URL}/hall-of-fame`, changeFrequency: "daily", priority: 0.5 },
    { url: `${SITE_URL}/blog`, changeFrequency: "weekly", priority: 0.8 },
    ...slugs.map((slug) => ({
      url: `${SITE_URL}/blog/${slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
  ];
}
