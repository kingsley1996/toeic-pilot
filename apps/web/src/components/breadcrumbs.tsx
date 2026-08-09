import { ChevronRight } from "lucide-react";
import Link from "next/link";

/**
 * Đường quay lui trong cây dictation.
 *
 * Cây bốn tầng mà không có đường lui thì mỗi trang là một ngõ cụt: nút back của
 * trình duyệt vẫn chạy, nhưng người dùng không thấy mình đang ở đâu trong cây,
 * và không nhảy được lên tầng giữa mà phải bấm back nhiều lần.
 */
export function Breadcrumbs({ trail }: { trail: Array<{ href: string; label: string }> }) {
  return (
    <nav aria-label="Đường dẫn" className="mb-4 flex flex-wrap items-center gap-1 text-small">
      {trail.map((crumb, index) => (
        <span key={crumb.href} className="flex items-center gap-1">
          {index > 0 && (
            <ChevronRight size={14} strokeWidth={1.75} className="text-ink-faint" aria-hidden />
          )}
          <Link
            href={crumb.href}
            className="rounded px-1 py-0.5 text-ink-muted transition-colors hover:bg-recess hover:text-ink"
          >
            {crumb.label}
          </Link>
        </span>
      ))}
    </nav>
  );
}
