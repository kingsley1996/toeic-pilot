/**
 * Origin công khai của web — dùng cho canonical, sitemap, robots, OG.
 * Vercel không set `NEXT_PUBLIC_SITE_URL` thì rơi về domain prod đã biết,
 * chứ không rơi về localhost (build trên Vercel mà canonical localhost là
 * thảm họa SEO âm thầm).
 */
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://toeic-pilot-web.vercel.app";
