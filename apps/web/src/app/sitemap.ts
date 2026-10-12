import type { MetadataRoute } from "next";

import { SCENES } from "@/content/scenes";
import { SITE_URL } from "@/lib/site";

/*
 * URL public duy nhất crawler đọc được nội dung: trang giới thiệu, hub scenes,
 * 12 trang cảnh (tiêu đề + mô tả SSR), hub từ vựng, bảng xếp hạng. Mọi route
 * còn lại sau đăng nhập hoặc là trang quản trị — cho vào đây chỉ làm Google
 * index trang skeleton rỗng.
 */
export default function sitemap(): MetadataRoute.Sitemap {
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
  ];
}
