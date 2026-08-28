"use client";

import { ChevronDown, LogOut, SquarePen, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";

import { activeHref, isBranchOpen } from "@/components/nav-active";
import { SoundToggle } from "@/components/sound-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, Skeleton, Tag, cx } from "@/components/ui";
import { useProgression } from "@/lib/progression";
import { useSession } from "@/lib/session";

export { activeHref, isBranchOpen };

export type NavItem = {
  href: string;
  label: string;
  Icon: LucideIcon;
  /**
   * Đường dẫn khác cũng thuộc về mục này, khi chúng KHÔNG nằm dưới `href`.
   *
   * Cần thiết từ lúc trang chủ chuyển sang `/dashboard`: `/learn/review`,
   * `/learn/typing` và `/learn/attempts` là những chế độ mở ra TỪ trang chủ
   * nhưng không còn nằm dưới đường dẫn của nó, nên quy tắc tiền tố không với
   * tới. Thiếu trường này thì mở "Ôn tập" xong cả thanh nav tắt hết đèn, và
   * người dùng mất dấu mình đang ở đâu — một lỗi im lặng, vì trang vẫn đúng.
   */
  covers?: string[];
};

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

/**
 * Menu tài khoản.
 *
 * Đóng theo BA đường, và cả ba đều cần: Escape (bàn phím), bấm ra ngoài
 * (chuột), và điều hướng. Thiếu đường thứ ba thì bấm "Hồ sơ" sẽ sang trang mới
 * với menu vẫn còn mở đè lên trên — lỗi trông như menu bị kẹt.
 *
 * Đóng-khi-điều-hướng suy ra từ `pathname` chứ không viết bằng effect, cùng thủ
 * thuật menu mobile ở `app-shell.tsx` dùng: `useEffect(() => setOpen(false),
 * [pathname])` là setState đồng bộ trong thân effect, thứ mà lint
 * `react-hooks/set-state-in-effect` chặn đúng chỗ này.
 */
function UserMenu({ showRole }: { showRole: boolean }) {
  const { user, token, logout, canEdit } = useSession();
  // Cùng khung, cùng huy hiệu như trong sidebar. Ba trang dùng thanh trên đứng
  // NGOÀI ứng dụng, nhưng người đã đăng nhập vẫn đi qua chúng — và một avatar
  // đổi hình tuỳ trang thì đọc như hai tài khoản khác nhau.
  const progression = useProgression(token);
  const pathname = usePathname();
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const open = openedAt === pathname;
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpenedAt(null);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpenedAt(null);
    }
    // `mousedown`, không phải `click`: bấm vào một nút khác phải đóng menu TRƯỚC
    // khi nút đó xử lý, nếu không menu còn nằm đè lúc trang đã đổi bên dưới.
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!user) return null;
  const name = user.profile.display_name ?? user.email;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpenedAt(open ? null : pathname)}
        className={cx(
          "flex items-center gap-2 rounded border px-1.5 py-1 transition-colors",
          open ? "border-rule-strong bg-recess" : "border-transparent hover:bg-recess",
        )}
      >
        <Avatar
          id={user.id}
          name={user.profile.display_name}
          email={user.email}
          src={user.profile.avatar_url}
          size="md"
          frame={progression?.frame}
          level={progression?.level}
        />
        <span className="hidden max-w-[10rem] truncate text-small font-semibold sm:block">
          {name}
        </span>
        <ChevronDown
          size={14}
          strokeWidth={2}
          aria-hidden
          className={cx("text-ink-faint transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        /*
         * `shadow-overlay` là MỘT trong ba ngoại lệ của luật cấm đổ bóng (§6.3):
         * lớp phủ thật cần tách khỏi nội dung bên dưới, và ở đây viền không đủ
         * vì menu nằm đè lên chữ chứ không nằm cạnh.
         */
        <div
          role="menu"
          className="shadow-overlay absolute right-0 top-[calc(100%+6px)] z-30 w-60 rounded border border-rule-strong bg-panel py-1"
        >
          <div className="border-b border-rule px-3 pb-2 pt-1.5">
            <p className="truncate text-small font-semibold">{name}</p>
            <p className="truncate text-label text-ink-faint">{user.email}</p>
            {showRole && (
              <Tag tone="action" className="mt-1.5">
                {user.role}
              </Tag>
            )}
          </div>

          <Link
            href="/profile"
            role="menuitem"
            className="flex items-center gap-2.5 px-3 py-2 text-small hover:bg-recess"
          >
            <UserRound size={15} strokeWidth={1.75} aria-hidden className="text-ink-muted" />
            Hồ sơ
          </Link>

          {/*
           * Cửa vào khu quản trị nằm TRONG menu tài khoản, không phải một nút
           * riêng trên header. Nó là thứ dùng vài lần một ngày bởi một số ít
           * người, còn header là chỗ dành cho việc học — một nút thường trực ở
           * đó lấy chỗ của điều hướng thật và nói với mọi học viên rằng có một
           * khu vực họ không vào được.
           *
           * Chỉ hiện với người thực sự mở được nó. Máy chủ vẫn chặn bằng
           * `require_role` dù giao diện có hiện hay không; đây chỉ quyết định
           * cái gì đáng vẽ ra.
           */}
          {canEdit && (
            <>
              <div className="my-1 border-t border-rule" />
              <Link
                href="/admin"
                role="menuitem"
                className="flex items-center gap-2.5 px-3 py-2 text-small hover:bg-recess"
              >
                <SquarePen size={15} strokeWidth={1.75} aria-hidden className="text-ink-muted" />
                Quản trị nội dung
              </Link>
            </>
          )}

          <div className="my-1 border-t border-rule" />

          <button
            type="button"
            role="menuitem"
            onClick={logout}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-small text-alert hover:bg-recess"
          >
            <LogOut size={15} strokeWidth={1.75} aria-hidden />
            Đăng xuất
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Danh tính, theme và lối thoát — giống nhau ở cả hai khu vực.
 *
 * `loading` dựng một khối giữ chỗ chứ không dựng nút của người chưa đăng nhập:
 * đoán sai ở đây chính là thứ từng khiến header mời "Đăng nhập" với người đã
 * đăng nhập rồi.
 */
export function SessionControls({ showRole = false }: { showRole?: boolean }) {
  const { status } = useSession();

  return (
    <div className="flex items-center gap-2">
      <SoundToggle />
      <ThemeToggle />
      {status === "loading" && <Skeleton className="h-8 w-24" />}
      {status === "authenticated" && <UserMenu showRole={showRole} />}
    </div>
  );
}
