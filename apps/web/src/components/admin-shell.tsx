"use client";

import { ArrowLeft, FolderTree, Headphones, Library, SquarePen } from "lucide-react";
import Link from "next/link";
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
const ADMIN_LINKS: NavItem[] = [
  { href: "/admin", label: "Tổng quan", Icon: SquarePen },
  { href: "/admin/vocabulary", label: "Từ vựng", Icon: Library },
  { href: "/admin/dictation", label: "Câu nghe", Icon: Headphones },
  { href: "/admin/dictation/tree", label: "Cây nội dung", Icon: FolderTree },
];

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
  const active = activeHref(ADMIN_LINKS, pathname);

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
            href="/learn"
            className="inline-flex shrink-0 items-center gap-2 rounded px-2 py-1.5 text-small font-semibold text-ink-muted transition-colors hover:bg-recess hover:text-ink"
          >
            <ArrowLeft size={16} strokeWidth={1.75} aria-hidden />
            <span className="hidden sm:inline">Về khu học</span>
          </Link>

          <span aria-hidden className="h-5 w-px shrink-0 bg-rule" />

          <p className="flex shrink-0 items-center gap-2 font-display text-subtitle font-semibold tracking-tight">
            Quản trị nội dung
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
          {ADMIN_LINKS.map((item) => (
            <NavLink key={item.href} {...item} active={item.href === active} />
          ))}
        </nav>
      </header>

      <div className="mx-auto flex w-full max-w-6xl flex-1 gap-0 px-0 lg:px-4">
        <aside className="hidden w-52 shrink-0 border-r border-rule py-8 pr-4 lg:block">
          <p className="mb-2 px-2.5 text-label font-semibold uppercase text-ink-faint">Nội dung</p>
          <nav className="flex flex-col gap-0.5">
            {ADMIN_LINKS.map((item) => (
              <NavLink
                key={item.href}
                {...item}
                active={item.href === active}
                className="justify-start"
              />
            ))}
          </nav>
        </aside>

        <main className="min-w-0 flex-1">{children}</main>
      </div>

      <footer className="border-t border-rule py-6">
        <p className="mx-auto max-w-6xl px-4 text-small text-ink-faint">
          Nội dung lưu ở dạng nháp cho tới khi được xuất bản. Audio sinh ngoài luồng.
        </p>
      </footer>
    </div>
  );
}
