"use client";

import {
  ArrowLeft,
  ClipboardList,
  Cpu,
  FolderTree,
  Headphones,
  Library,
  Sparkles,
  SquarePen,
  Tags,
} from "lucide-react";
import Link from "next/link";
import { Fragment } from "react";
import { usePathname } from "next/navigation";

import { NavLink, SessionControls, activeHref, type NavItem } from "@/components/nav";
import { Skeleton, Tag } from "@/components/ui";
import { useRequireSession } from "@/lib/session";

/*
 * Điều hướng của khu quản trị. Nó KHÔNG nằm trên header chính: học viên và biên
 * tập viên làm hai việc khác hẳn nhau, và trộn hai bộ nav lại vừa làm header
 * chật (sáu mục ở vai trò admin) vừa xoá mất ranh giới giữa "đang học" và "đang
 * sửa nội dung người khác sẽ học".
 */
type AdminNavItem = NavItem & { children?: NavItem[] };

const ADMIN_LINKS: AdminNavItem[] = [
  { href: "/admin", label: "Overview", Icon: SquarePen },
  { href: "/admin/vocabulary", label: "Vocabulary", Icon: Library },
  { href: "/admin/vocabulary/tree", label: "Vocabulary tree", Icon: FolderTree },
  { href: "/admin/dictation", label: "Dictation", Icon: Headphones },
  { href: "/admin/dictation/tree", label: "Content tree", Icon: FolderTree },
  { href: "/admin/tests", label: "Tests", Icon: ClipboardList },
  {
    href: "/admin/ai",
    label: "AI layer",
    Icon: Sparkles,
    // Gắn nhãn chỉ là MỘT việc của tầng AI, không phải cả tầng. Để nó ngang
    // hàng với "Tầng AI" ở menu chính sẽ ngụ ý hai khu riêng biệt, rồi mục thứ
    // hai (giải thích câu sai) và thứ ba (kế hoạch học) sẽ không biết đặt đâu.
    children: [
      { href: "/admin/ai/skill-tags", label: "Skill labels", Icon: Tags },
      { href: "/admin/ai/providers", label: "Providers", Icon: Cpu },
    ],
  },
];

// Phẳng hoá để `activeHref` thấy cả mục con. Nó sắp theo độ dài giảm dần nên
// đường dẫn con luôn thắng đường dẫn cha — không cần luật riêng.
const ALL_LINKS: NavItem[] = ADMIN_LINKS.flatMap((item) => [item, ...(item.children ?? [])]);

/**
 * Khung của khu quản trị nội dung.
 *
 * Có sidebar còn phía học viên thì không — đó là tín hiệu im lặng nói rằng bạn
 * đang ở một nơi khác, mà không cần thêm màu hay thêm kiểu chữ nào (§6.3: độ
 * nổi là viền + bậc nền, không phải trang trí).
 *
 * `useRequireSession({ canEdit: true })` chuyển hướng chứ không hiện 403: người
 * chưa từng có quyền thì không nên bị thông báo là đã bị từ chối. Máy chủ vẫn
 * chặn từng endpoint bằng `require_role`; chỗ này chỉ quyết định dựng cái gì.
 */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const { status, canEdit } = useRequireSession({ canEdit: true });
  const pathname = usePathname();
  const active = activeHref(ALL_LINKS, pathname);

  if (status !== "authenticated" || !canEdit) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-8">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="mt-6 h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-rule bg-ground/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4">
          {/* Lối ra luôn hiện. Khu quản trị là ngõ cụt nếu không có đường về. */}
          <Link
            href="/dashboard"
            className="inline-flex shrink-0 items-center gap-2 rounded px-2 py-1.5 text-small font-semibold text-ink-muted transition-colors hover:bg-recess hover:text-ink"
          >
            <ArrowLeft size={16} strokeWidth={1.75} aria-hidden />
            <span className="hidden sm:inline">Back to learning</span>
          </Link>

          <span aria-hidden className="h-5 w-px shrink-0 bg-rule" />

          <p className="flex shrink-0 items-center gap-2 font-display text-subtitle font-semibold tracking-tight">
            Content admin
            <Tag tone="action" className="hidden sm:inline-flex">
              admin
            </Tag>
          </p>

          <div className="ml-auto">
            <SessionControls />
          </div>
        </div>

        {/* Dưới lg, sidebar trở thành một hàng ngang cuộn được — vẫn là cùng một
            bộ mục, không phải một menu thứ hai phải bảo trì riêng. */}
        <nav className="flex gap-1 overflow-x-auto border-t border-rule px-4 py-2 lg:hidden">
          {ALL_LINKS.map((item) => (
            <NavLink key={item.href} {...item} active={item.href === active} />
          ))}
        </nav>
      </header>

      <div className="mx-auto flex w-full max-w-6xl flex-1 gap-0 px-0 lg:px-4">
        <aside className="hidden w-52 shrink-0 border-r border-rule py-8 pr-4 lg:block">
          <p className="mb-2 px-2.5 text-label font-semibold uppercase text-ink-faint">Content</p>
          <nav className="flex flex-col gap-0.5">
            {ADMIN_LINKS.map((item) => (
              <Fragment key={item.href}>
                <NavLink
                  href={item.href}
                  label={item.label}
                  Icon={item.Icon}
                  active={item.href === active}
                  className="justify-start"
                />
                {/* Mục con chỉ hiện khi đang ở trong khu đó. Hiện thường trực sẽ
                  làm sidebar dài ra vì những việc người dùng chưa quan tâm, và
                  mỗi tính năng AI mới lại thêm một dòng nữa. */}
                {item.children && (active === item.href || active?.startsWith(`${item.href}/`)) && (
                  <div className="ml-3 flex flex-col gap-0.5 border-l border-rule pl-2">
                    {item.children.map((child) => (
                      <NavLink
                        key={child.href}
                        {...child}
                        active={child.href === active}
                        className="justify-start"
                      />
                    ))}
                  </div>
                )}
              </Fragment>
            ))}
          </nav>
        </aside>

        <main className="min-w-0 flex-1">{children}</main>
      </div>

      <footer className="border-t border-rule py-6">
        <p className="mx-auto max-w-6xl px-4 text-small text-ink-faint">
          Content stays in draft until it is published. Audio is generated out of band.
        </p>
      </footer>
    </div>
  );
}
