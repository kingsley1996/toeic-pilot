"use client";

import { Check, Link2, Share2 } from "lucide-react";
import { useEffect, useState } from "react";

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
