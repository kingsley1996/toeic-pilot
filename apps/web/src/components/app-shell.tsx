"use client";

import { BookOpen, Headphones, Library, LogOut, Menu, RotateCcw, SquarePen, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { ButtonLink, IconButton, Skeleton, cx } from "@/components/ui";
import { useSession } from "@/lib/session";

/*
 * Icon theo khái niệm, không theo trang. Một khái niệm dùng MỘT icon trong toàn
 * app (DESIGN-SYSTEM §8.4) — bảng này và bảng ở tài liệu phải khớp nhau.
 */
const LEARN_LINKS = [
  { href: "/learn", label: "Learning Hub", Icon: BookOpen },
  { href: "/learn/review", label: "Ôn tập", Icon: RotateCcw },
  { href: "/learn/dictation", label: "Dictation", Icon: Headphones },
];

const ADMIN_LINKS = [
  { href: "/admin", label: "Nội dung", Icon: SquarePen },
  { href: "/admin/vocabulary", label: "Từ vựng", Icon: Library },
  { href: "/admin/dictation", label: "Câu nghe", Icon: Headphones },
];

function NavLink({
  href,
  label,
  Icon,
  active,
  onClick,
}: {
  href: string;
  label: string;
  Icon: typeof BookOpen;
  active: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cx(
        "inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded px-2.5 py-1.5 text-small font-semibold transition-colors",
        active ? "bg-action-tint text-action-ink" : "text-ink-muted hover:bg-recess hover:text-ink",
      )}
    >
      <Icon size={16} strokeWidth={1.75} aria-hidden />
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status, user, canEdit, logout } = useSession();
  const pathname = usePathname();
  /*
   * Menu mobile được đóng dấu bằng đường dẫn mà nó được mở ra trên đó, nên điều
   * hướng làm nó tự đóng THEO SUY DIỄN — không cần effect.
   *
   * Cách hiển nhiên là `useEffect(() => setMenuOpen(false), [pathname])`, nhưng
   * đó là setState đồng bộ trong thân effect: một lượt render dây chuyền, và
   * lint `react-hooks/set-state-in-effect` chặn đúng chỗ này. Cách dưới đây còn
   * đúng cho MỌI kiểu điều hướng, kể cả bấm logo hay quay lại bằng nút back —
   * chứ không chỉ cho những link có gắn onClick.
   */
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const menuOpen = openedAt === pathname;
  const setMenuOpen = (open: boolean) => setOpenedAt(open ? pathname : null);

  // Khớp sâu nhất thắng, để /learn/review không đồng thời làm sáng /learn.
  const links = [...LEARN_LINKS, ...(canEdit ? ADMIN_LINKS : [])];
  const activeHref = links
    .map((link) => link.href)
    .filter((href) => pathname === href || pathname.startsWith(`${href}/`))
    .sort((a, b) => b.length - a.length)[0];

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
            <nav className="ml-1 hidden items-center gap-0.5 lg:flex">
              {links.map((link) => (
                <NavLink key={link.href} {...link} active={link.href === activeHref} />
              ))}
            </nav>
          )}

          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />

            {/* "loading" dựng một khối giữ chỗ chứ không dựng nút của người chưa
                đăng nhập. Đoán sai ở đây chính là thứ từng khiến header mời
                "Đăng nhập" với người đã đăng nhập rồi. */}
            {status === "loading" && <Skeleton className="h-8 w-24" />}

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

            {status === "authenticated" && user && (
              <>
                <div className="hidden text-right sm:block">
                  <p className="text-small font-semibold leading-tight">{user.email}</p>
                  <p className="font-data text-label uppercase leading-tight text-ink-faint">
                    {user.role}
                  </p>
                </div>
                <IconButton icon={LogOut} aria-label="Thoát" onClick={logout} />
                <IconButton
                  icon={menuOpen ? X : Menu}
                  aria-label={menuOpen ? "Đóng menu" : "Mở menu"}
                  aria-expanded={menuOpen}
                  onClick={() => setMenuOpen(!menuOpen)}
                  className="lg:hidden"
                />
              </>
            )}
          </div>
        </div>

        {status === "authenticated" && menuOpen && (
          <nav className="flex flex-col gap-0.5 border-t border-rule bg-panel px-4 py-3 lg:hidden">
            {links.map((link) => (
              <NavLink key={link.href} {...link} active={link.href === activeHref} />
            ))}
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
