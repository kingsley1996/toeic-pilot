"use client";

import { API_ROUTES, type ReviewDueCount } from "@toeic-pilot/shared";
import { BookOpen, FileText, Headphones, House, Sparkles } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { type NavItem } from "@/components/nav";
import { PetLand } from "@/components/petland";
import { SidebarShell, TopBarShell } from "@/components/shell";
import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

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

/**
 * Số từ đến hạn, cho huy hiệu ở mục "Từ vựng".
 *
 * Đọc lại MỖI LẦN ĐỔI TRANG, không phải một lần lúc dựng khung: ôn xong một
 * buổi rồi rời trang mà huy hiệu vẫn đứng ở con số cũ thì nó nói dối, và đó là
 * đúng lúc người học nhìn nó để biết còn việc hay không. Endpoint là một lượt
 * `COUNT` nên đọc lại rẻ.
 *
 * Hỏng thì trả 0 và huy hiệu tự ẩn: một con số sai còn tệ hơn không có số.
 */
function useDueCount(): number {
  const { status, token } = useSession();
  const pathname = usePathname();
  const [due, setDue] = useState(0);

  useEffect(() => {
    // Ba trạng thái, không phải hai: `loading` chưa biết có token hay không,
    // và gọi lúc đó là một lượt 401 chắc chắn.
    if (status !== "authenticated" || !token) return;
    let cancelled = false;
    apiFetch<ReviewDueCount>(API_ROUTES.reviewDueCount, { token })
      .then((data) => {
        if (!cancelled) setDue(data.due);
      })
      .catch(() => {
        if (!cancelled) setDue(0);
      });
    return () => {
      cancelled = true;
    };
  }, [status, token, pathname]);

  // SUY RA chứ không ghi: đặt `setDue(0)` ngay trong thân effect lúc đăng xuất
  // là setState đồng bộ trong effect — lint `react-hooks/set-state-in-effect`
  // chặn, và nó chặn đúng: giá trị đó là hàm của `status`, không phải một trạng
  // thái thứ hai chạy song song và có thể lệch pha.
  return status === "authenticated" ? due : 0;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const due = useDueCount();
  // Gắn huy hiệu vào đúng mục từ vựng. Ghép theo `href`, không theo chỉ số:
  // thêm hay đổi thứ tự mục thì huy hiệu vẫn bám đúng chỗ.
  const links: NavItem[] = LEARN_LINKS.map((link) =>
    link.href === "/learn/vocabulary" ? { ...link, badge: due } : link,
  );

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
      <TopBarShell links={links} sectionLabel="Học" footer={Footer}>
        {children}
      </TopBarShell>
    );
  }

  return (
    <SidebarShell links={links} sectionLabel="Học">
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
