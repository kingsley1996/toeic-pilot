"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { IconButton, Skeleton, Tag, cx } from "@/components/ui";
import { useSession } from "@/lib/session";

export type NavItem = { href: string; label: string; Icon: LucideIcon };

/**
 * Một mục điều hướng, dùng chung cho cả header học viên lẫn sidebar quản trị.
 *
 * `whitespace-nowrap` không phải chi tiết thẩm mỹ: tài khoản có quyền biên tập
 * nhìn thấy nhiều mục hơn, và flex sẽ bóp chúng xuống thành hai dòng giữa chữ
 * ("Learning / Hub") — lỗi chỉ lộ ra ở đúng vai trò đó.
 */
export function NavLink({
  href,
  label,
  Icon,
  active,
  onClick,
  className,
}: NavItem & { active: boolean; onClick?: () => void; className?: string }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cx(
        "inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded px-2.5 py-1.5 text-small font-semibold transition-colors",
        active ? "bg-action-tint text-action-ink" : "text-ink-muted hover:bg-recess hover:text-ink",
        className,
      )}
    >
      <Icon size={16} strokeWidth={1.75} aria-hidden />
      {label}
    </Link>
  );
}

/** Khớp sâu nhất thắng, để `/learn/review` không đồng thời làm sáng `/learn`. */
export function activeHref(items: NavItem[], pathname: string): string | undefined {
  return items
    .map((item) => item.href)
    .filter((href) => pathname === href || pathname.startsWith(`${href}/`))
    .sort((a, b) => b.length - a.length)[0];
}

/**
 * Danh tính, theme và lối thoát — giống nhau ở cả hai khu vực.
 *
 * `loading` dựng một khối giữ chỗ chứ không dựng nút của người chưa đăng nhập:
 * đoán sai ở đây chính là thứ từng khiến header mời "Đăng nhập" với người đã
 * đăng nhập rồi.
 */
export function SessionControls({ showRole = false }: { showRole?: boolean }) {
  const { status, user, logout } = useSession();

  return (
    <div className="flex items-center gap-2">
      <ThemeToggle />
      {status === "loading" && <Skeleton className="h-8 w-24" />}
      {status === "authenticated" && user && (
        <>
          <div className="hidden text-right sm:block">
            <p className="text-small font-semibold leading-tight">{user.email}</p>
            {showRole ? (
              <Tag tone="action" className="mt-0.5">
                {user.role}
              </Tag>
            ) : (
              <p className="font-data text-label uppercase leading-tight text-ink-faint">
                {user.role}
              </p>
            )}
          </div>
          <IconButton icon={LogOut} aria-label="Thoát" onClick={logout} />
        </>
      )}
    </div>
  );
}
