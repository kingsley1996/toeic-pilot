"use client";

import { BookOpen, Headphones, Menu, RotateCcw, SquarePen, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { NavLink, SessionControls, activeHref, type NavItem } from "@/components/nav";
import { ButtonLink, IconButton, cx } from "@/components/ui";
import { useSession } from "@/lib/session";

/*
 * Chỉ điều hướng của khu HỌC. Các trang quản trị có khung riêng
 * (`components/admin-shell.tsx`) và cố ý không nằm ở đây: trộn hai bộ nav lại
 * đẩy header lên sáu mục ở vai trò admin, và quan trọng hơn là xoá mất ranh
 * giới giữa "đang học" và "đang sửa nội dung người khác sẽ học".
 *
 * Icon theo khái niệm, không theo trang — bảng tra ở DESIGN-SYSTEM §8.4.
 */
const LEARN_LINKS: NavItem[] = [
  { href: "/learn", label: "Learning Hub", Icon: BookOpen },
  { href: "/learn/review", label: "Ôn tập", Icon: RotateCcw },
  { href: "/learn/dictation", label: "Dictation", Icon: Headphones },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status, canEdit } = useSession();
  const pathname = usePathname();

  /*
   * Menu mobile được đóng dấu bằng đường dẫn mà nó được mở ra trên đó, nên điều
   * hướng làm nó tự đóng THEO SUY DIỄN — không cần effect.
   *
   * Cách hiển nhiên là `useEffect(() => setMenuOpen(false), [pathname])`, nhưng
   * đó là setState đồng bộ trong thân effect: một lượt render dây chuyền, và
   * lint `react-hooks/set-state-in-effect` chặn đúng chỗ này. Cách dưới đây còn
   * đúng cho MỌI kiểu điều hướng, kể cả bấm logo hay quay lại bằng nút back.
   */
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const menuOpen = openedAt === pathname;
  const setMenuOpen = (open: boolean) => setOpenedAt(open ? pathname : null);

  // Khu quản trị tự dựng khung của nó. Không lồng hai header vào nhau.
  if (pathname === "/admin" || pathname.startsWith("/admin/")) {
    return <>{children}</>;
  }

  const active = activeHref(LEARN_LINKS, pathname);

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header dính dùng MỘT đường kẻ ở đáy, không đổ bóng (§6.3). */}
      <header className="sticky top-0 z-20 border-b border-rule bg-ground/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4">
          <Link
            href="/"
            className="flex shrink-0 items-center gap-2 font-display text-subtitle font-semibold tracking-tight"
          >
            {/* Dấu vuông, không phải tròn: bo góc 4px là ngôn ngữ của cả hệ. */}
            <span
              aria-hidden
              className="grid h-7 w-7 place-items-center rounded bg-action font-data text-small text-on-action"
            >
              T
            </span>
            <span className="hidden sm:inline">TOEIC Pilot</span>
          </Link>

          {status === "authenticated" && (
            <nav className="ml-1 hidden items-center gap-0.5 md:flex">
              {LEARN_LINKS.map((link) => (
                <NavLink key={link.href} {...link} active={link.href === active} />
              ))}
            </nav>
          )}

          <div className="ml-auto flex items-center gap-2">
            {/*
             * MỘT cánh cửa vào khu quản trị, không phải ba mục nav. Chỉ hiện với
             * người thực sự mở được nó — học viên không được chỉ vào một cánh
             * cửa họ không mở được.
             */}
            {status === "authenticated" && canEdit && (
              <ButtonLink
                href="/admin"
                variant="secondary"
                size="sm"
                className="hidden sm:inline-flex"
              >
                <SquarePen size={14} strokeWidth={2} aria-hidden />
                Quản trị
              </ButtonLink>
            )}

            {status === "anonymous" && (
              <>
                <ButtonLink href="/login" variant="quiet" size="sm">
                  Đăng nhập
                </ButtonLink>
                <ButtonLink href="/register" size="sm">
                  Tạo tài khoản
                </ButtonLink>
              </>
            )}

            <SessionControls />

            {status === "authenticated" && (
              <IconButton
                icon={menuOpen ? X : Menu}
                aria-label={menuOpen ? "Đóng menu" : "Mở menu"}
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen(!menuOpen)}
                className="md:hidden"
              />
            )}
          </div>
        </div>

        {status === "authenticated" && menuOpen && (
          <nav className="flex flex-col gap-0.5 border-t border-rule bg-panel px-4 py-3 md:hidden">
            {LEARN_LINKS.map((link) => (
              <NavLink key={link.href} {...link} active={link.href === active} />
            ))}
            {canEdit && (
              <NavLink
                href="/admin"
                label="Quản trị nội dung"
                Icon={SquarePen}
                active={false}
                className={cx("mt-1 border-t border-rule pt-3")}
              />
            )}
          </nav>
        )}
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-rule py-6">
        <p className="mx-auto max-w-5xl px-4 text-small text-ink-faint">
          TOEIC Pilot — nội dung học do đội ngũ tự biên soạn.
        </p>
      </footer>
    </div>
  );
}
