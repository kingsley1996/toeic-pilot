"use client";

import { BookOpen, FileText, Headphones, House, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { NavLink, SessionControls, activeHref, type NavItem } from "@/components/nav";
import { ButtonLink, IconButton } from "@/components/ui";
import { useSession } from "@/lib/session";

/*
 * Chỉ điều hướng của khu HỌC. Các trang quản trị có khung riêng
 * (`components/admin-shell.tsx`) và cố ý không nằm ở đây: trộn hai bộ nav lại
 * đẩy header lên sáu mục ở vai trò admin, và quan trọng hơn là xoá mất ranh
 * giới giữa "đang học" và "đang sửa nội dung người khác sẽ học".
 *
 * Icon theo khái niệm, không theo trang — bảng tra ở DESIGN-SYSTEM §8.4.
 */
/*
 * Ba mục NGANG HÀNG: một việc hôm nay, và hai kho nội dung. Không mục nào chứa
 * mục nào.
 *
 * Bộ cũ là "Learning Hub · Ôn tập · Dictation", và đó là một lỗi phân loại:
 * Ôn tập và Dictation nằm BÊN TRONG Learning Hub, nên người dùng không đoán
 * được nên bấm cái nào. Nó cũng khiến `/dashboard` — nơi đăng nhập đẩy tới và
 * là chỗ DUY NHẤT hiện số từ cần ôn — không có mặt ở đâu trong nav cả.
 *
 * `Ôn tập` và `Gõ lại từ` cố ý KHÔNG có ở đây: chúng là hai CHẾ ĐỘ của cùng một
 * hàng đợi SM-2, không phải hai nơi chốn. Đặt chúng thành mục nav là hứa hẹn hai
 * hoạt động, trong khi mở cái nào trước thì cái đó tiêu hết hàng đợi của ngày và
 * cái còn lại hiện "không còn từ nào đến hạn".
 */
const LEARN_LINKS: NavItem[] = [
  { href: "/learn", label: "Hôm nay", Icon: House },
  { href: "/learn/vocabulary", label: "Từ vựng", Icon: BookOpen },
  { href: "/learn/dictation", label: "Dictation", Icon: Headphones },
  { href: "/learn/tests", label: "Luyện thi", Icon: FileText },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
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

  /*
   * Hai khu tự dựng khung của chúng, và ở đây phải nhường hẳn chỗ.
   *
   * - **Quản trị** có nav riêng (`admin-shell.tsx`); lồng hai header vào nhau
   *   là hai hàng điều hướng chồng lên nhau.
   * - **Màn làm bài** thì mạnh hơn thế: nó cố ý KHÔNG có lối đi đâu khác. Một
   *   thanh nav mời người đang thi bấm sang "Từ vựng" giữa lúc đồng hồ đang
   *   chạy — và bài thi vẫn tính giờ ở máy chủ trong lúc họ đi. Thanh trên cùng
   *   của màn đó chỉ có hai đường ra, Nộp bài và Thoát, và đó là chủ ý.
   *
   * Bỏ khung cũng gỡ luôn hai header `sticky top-0` chồng nhau.
   */
  const bareLayout =
    pathname === "/admin" ||
    pathname.startsWith("/admin/") ||
    pathname.startsWith("/learn/attempts/");
  if (bareLayout) {
    return <>{children}</>;
  }

  const active = activeHref(LEARN_LINKS, pathname);

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header dính dùng MỘT đường kẻ ở đáy, không đổ bóng (§6.3). */}
      <header className="sticky top-0 z-20 border-b border-rule bg-ground/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4">
          {/* Đã đăng nhập thì logo về NHÀ, không về trang giới thiệu: bấm logo
              rồi rơi vào một trang bán hàng là chuyện chỉ xảy ra với người đã
              là người dùng rồi. */}
          <Link
            href={status === "authenticated" ? "/learn" : "/"}
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
