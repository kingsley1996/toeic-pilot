"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button, ButtonLink, Skeleton, cx } from "@/components/ui";
import { useSession } from "@/lib/session";

const LEARN_LINKS = [
  { href: "/learn", label: "Learning Hub" },
  { href: "/learn/review", label: "Ôn tập" },
  { href: "/learn/dictation", label: "Dictation" },
];

const ADMIN_LINKS = [
  { href: "/admin", label: "Nội dung" },
  { href: "/admin/vocabulary", label: "Từ vựng" },
  { href: "/admin/dictation", label: "Câu nghe" },
];

function NavLink({
  href,
  label,
  active,
  onClick,
}: {
  href: string;
  label: string;
  active: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cx(
        "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
        active ? "bg-brand-soft text-brand-text" : "text-text-muted hover:bg-surface-sunken",
      )}
    >
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status, user, canEdit, logout } = useSession();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  // Deepest match wins, so /learn/review does not also light up /learn.
  const links = [...LEARN_LINKS, ...(canEdit ? ADMIN_LINKS : [])];
  const activeHref = links
    .map((link) => link.href)
    .filter((href) => pathname === href || pathname.startsWith(`${href}/`))
    .sort((a, b) => b.length - a.length)[0];

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-border bg-surface/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-4 px-4">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span
              aria-hidden
              className="grid h-7 w-7 place-items-center rounded-lg bg-brand text-sm text-white"
            >
              T
            </span>
            TOEIC Pilot
          </Link>

          {status === "authenticated" && (
            <nav className="ml-2 hidden items-center gap-1 md:flex">
              {links.map((link) => (
                <NavLink key={link.href} {...link} active={link.href === activeHref} />
              ))}
            </nav>
          )}

          <div className="ml-auto flex items-center gap-2">
            {/* "loading" renders a placeholder rather than the signed-out
                buttons. Guessing wrong here is what made the old header offer
                "Log in" to people who were already signed in. */}
            {status === "loading" && <Skeleton className="h-8 w-28" />}

            {status === "anonymous" && (
              <>
                <ButtonLink href="/login" variant="ghost" size="sm">
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
                  <p className="text-xs font-medium leading-tight">{user.email}</p>
                  <p className="text-[11px] uppercase tracking-wide text-text-subtle">
                    {user.role}
                  </p>
                </div>
                <Button variant="ghost" size="sm" onClick={logout}>
                  Thoát
                </Button>
                <button
                  type="button"
                  aria-label="Menu"
                  aria-expanded={menuOpen}
                  onClick={() => setMenuOpen((open) => !open)}
                  className="rounded-lg p-2 text-text-muted hover:bg-surface-sunken md:hidden"
                >
                  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor">
                    <path strokeWidth="2" strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" />
                  </svg>
                </button>
              </>
            )}
          </div>
        </div>

        {status === "authenticated" && menuOpen && (
          <nav className="flex flex-col gap-1 border-t border-border px-4 py-3 md:hidden">
            {links.map((link) => (
              <NavLink
                key={link.href}
                {...link}
                active={link.href === activeHref}
                onClick={() => setMenuOpen(false)}
              />
            ))}
          </nav>
        )}
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border py-6">
        <p className="mx-auto max-w-5xl px-4 text-xs text-text-subtle">
          TOEIC Pilot — nội dung học do đội ngũ tự biên soạn.
        </p>
      </footer>
    </div>
  );
}
