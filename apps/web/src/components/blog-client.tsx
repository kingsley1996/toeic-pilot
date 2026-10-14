"use client";

import { Check, Link2, ListTree, Share2 } from "lucide-react";
import { useEffect, useState } from "react";

import type { TocEntry } from "@toeic-pilot/shared";

/** Nút chia sẻ bài: native share nếu có, không thì copy link (không SDK ngoài). */
export function BlogShare({ title, url }: { title: string; url: string }) {
  const [copied, setCopied] = useState(false);

  async function share() {
    if (typeof navigator !== "undefined" && "share" in navigator) {
      try {
        await navigator.share({ title, url });
        return;
      } catch {
        // Người dùng hủy dialog share — không phải lỗi, im lặng bỏ qua.
      }
    }
    await copy();
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard bị chặn (iframe/quyền) — nút vẫn hiện, không nổ trang.
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => void share()}
        className="inline-flex items-center gap-1.5 rounded border border-rule-strong px-3 py-1.5 text-small font-semibold hover:bg-recess"
      >
        {copied ? <Check size={14} aria-hidden /> : <Share2 size={14} aria-hidden />}
        {copied ? "Đã copy link" : "Chia sẻ"}
      </button>
      <button
        type="button"
        onClick={() => void copy()}
        title="Copy link bài viết"
        aria-label="Copy link bài viết"
        className="rounded border border-rule-strong p-2 text-ink-muted hover:bg-recess"
      >
        <Link2 size={14} aria-hidden />
      </button>
    </div>
  );
}

/** Thanh tiến độ đọc — décor thuần túy, không logic. */
export function ReadingProgress() {
  const [ratio, setRatio] = useState(0);

  useEffect(() => {
    function onScroll() {
      const total = document.documentElement.scrollHeight - window.innerHeight;
      setRatio(total > 0 ? Math.min(1, window.scrollY / total) : 0);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="fixed inset-x-0 top-0 z-40 h-0.5 bg-transparent" aria-hidden>
      <div className="h-full bg-action" style={{ width: `${Math.round(ratio * 100)}%` }} />
    </div>
  );
}

/**
 * Mục lục bài viết: bấm là cuộn MƯỢT tới heading, không nhảy cục.
 *
 * `<a href="#id">` thuần của trình duyệt nhảy ngay lập tức — đọc bài dài mà
 * khung hình teleport thì mất mạch. `scroll-behavior: smooth` toàn cục thì
 * vạ lây cả app (cuộn code cũng mượt theo), nên gắn hành vi vào đúng cú bấm
 * ở đây. Tôn trọng giảm chuyển động của hệ điều hành.
 */
export function BlogToc({ toc }: { toc: TocEntry[] }) {
  function go(event: React.MouseEvent, id: string) {
    event.preventDefault();
    const el = document.getElementById(id);
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    window.history.replaceState(null, "", `#${id}`);
  }

  return (
    <nav className="sticky top-4 rounded border border-rule bg-panel p-4" aria-label="Mục lục">
      <p className="mb-2 flex items-center gap-1.5 text-small font-bold">
        <ListTree size={14} aria-hidden /> Mục lục
      </p>
      <ul className="space-y-1.5">
        {toc.map((entry) => (
          <li key={entry.id} className={entry.level === 3 ? "pl-4" : ""}>
            <a
              href={`#${entry.id}`}
              onClick={(e) => go(e, entry.id)}
              className="text-small text-ink-muted hover:text-ink"
            >
              {entry.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
