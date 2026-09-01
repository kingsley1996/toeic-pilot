"use client";

import { BookOpen, FileText, Headphones, House, Sparkles } from "lucide-react";
import { usePathname } from "next/navigation";

import { type NavItem } from "@/components/nav";
import { PetLand } from "@/components/petland";
import { SidebarShell, TopBarShell } from "@/components/shell";

/*
 * Chỉ điều hướng của khu HỌC. Các trang quản trị có bộ mục riêng
 * (`components/admin-shell.tsx`) và cố ý không nằm ở đây: trộn hai bộ nav lại
 * xoá mất ranh giới giữa "đang học" và "đang sửa nội dung người khác sẽ học".
 * Cái CHUNG giữa hai khu là cái KHUNG (`components/shell.tsx`), không phải bộ
 * mục.
 *
 * Icon theo khái niệm, không theo trang — bảng tra ở DESIGN-SYSTEM §8.4.
 */
/*
 * Bốn mục NGANG HÀNG: một việc hôm nay, và ba kho nội dung. Không mục nào chứa
 * mục nào.
 *
 * Bộ cũ là "Learning Hub · Ôn tập · Dictation", và đó là một lỗi phân loại:
 * Ôn tập và Dictation nằm BÊN TRONG Learning Hub, nên người dùng không đoán
 * được nên bấm cái nào.
 *
 * `Ôn tập` và `Gõ lại từ` cố ý KHÔNG có ở đây: chúng là hai CHẾ ĐỘ của cùng một
 * hàng đợi SM-2, không phải hai nơi chốn. Đặt chúng thành mục nav là hứa hẹn hai
 * hoạt động, trong khi mở cái nào trước thì cái đó tiêu hết hàng đợi của ngày và
 * cái còn lại hiện "không còn từ nào đến hạn".
 */
const LEARN_LINKS: NavItem[] = [
  // `covers`: ba chế độ mở ra từ trang chủ nhưng không nằm dưới `/dashboard`.
  // Không khai báo thì mở "Ôn tập" xong cả sidebar tắt đèn.
  {
    href: "/dashboard",
    label: "Hôm nay",
    Icon: House,
    covers: ["/learn/review", "/learn/typing", "/learn/attempts"],
  },
  { href: "/learn/vocabulary", label: "Từ vựng", Icon: BookOpen },
  { href: "/learn/dictation", label: "Dictation", Icon: Headphones },
  { href: "/learn/tests", label: "Luyện thi", Icon: FileText },
  { href: "/learn/assistant", label: "Trợ lý AI", Icon: Sparkles },
];

/*
 * Ba trang dùng thanh trên thay vì sidebar, và cả ba vì cùng một lý do: chúng
 * đứng NGOÀI ứng dụng. Trang giới thiệu nói chuyện với người chưa có tài khoản;
 * `/login` và `/register` là cánh cửa vào. Dựng một cột điều hướng đầy mục cho
 * người chưa bước qua cửa là mời họ bấm vào những nơi sẽ đá họ ngược về đây.
 *
 * Danh sách theo ĐƯỜNG DẪN chứ không theo trạng thái phiên. Trạng thái chỉ phân
 * giải được sau khi JS chạy (localStorage không tồn tại lúc render ở máy chủ),
 * nên chọn khung theo nó sẽ dựng một khung rồi đổi sang khung kia ngay trước
 * mắt người dùng — đúng cái bẫy ba-trạng-thái đã ghi trong CLAUDE.md, lần này
 * hiện ra thành một cú nhảy layout thay vì một cái nút sai.
 */
const TOP_BAR_ROUTES = new Set(["/", "/login", "/register"]);

const Footer = (
  <footer className="border-t border-rule py-6">
    <p className="mx-auto max-w-5xl px-4 text-small text-ink-faint">
      TOEIC Pilot — nội dung học do đội ngũ tự biên soạn.
    </p>
  </footer>
);

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  /*
   * Hai khu tự dựng khung của chúng, và ở đây phải nhường hẳn chỗ.
   *
   * - **Quản trị** có `admin-shell.tsx`, vốn cũng dựng `SidebarShell` nhưng với
   *   bộ mục của nó; lồng hai khung vào nhau là hai cột điều hướng cạnh nhau.
   * - **Màn làm bài** thì mạnh hơn thế: nó cố ý KHÔNG có lối đi đâu khác. Một
   *   cột nav mời người đang thi bấm sang "Từ vựng" giữa lúc đồng hồ đang chạy —
   *   và bài thi vẫn tính giờ ở máy chủ trong lúc họ đi. Thanh trên cùng của màn
   *   đó chỉ có hai đường ra, Nộp bài và Thoát, và đó là chủ ý.
   */
  const bareLayout =
    pathname === "/admin" ||
    pathname.startsWith("/admin/") ||
    pathname.startsWith("/learn/attempts/");
  if (bareLayout) {
    return <>{children}</>;
  }

  if (TOP_BAR_ROUTES.has(pathname)) {
    return (
      <TopBarShell links={LEARN_LINKS} sectionLabel="Học" footer={Footer}>
        {children}
      </TopBarShell>
    );
  }

  return (
    <SidebarShell links={LEARN_LINKS} sectionLabel="Học">
      {children}
      {/*
       * Chỉ ở khung có sidebar. Ba trang thanh trên đứng NGOÀI ứng dụng, còn khu
       * quản trị và màn làm bài đi qua nhánh `bareLayout` phía trên — và màn làm
       * bài là chỗ quan trọng nhất phải vắng mặt: một con thú nhảy nhót cạnh
       * người đang tính giờ làm bài là thứ cạnh tranh trực tiếp với sự tập trung.
       */}
      <PetLand />
    </SidebarShell>
  );
}
