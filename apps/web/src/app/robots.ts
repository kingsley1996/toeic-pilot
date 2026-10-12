import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Trang quản trị, đăng nhập, callback OAuth và preview nội bộ:
        // crawler vào không có gì đọc, chỉ tốn crawl budget.
        disallow: ["/admin/", "/login", "/register", "/auth/", "/preview/"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
