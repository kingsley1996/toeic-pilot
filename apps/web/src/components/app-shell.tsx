"use client";

import {
  BookOpen,
  Boxes,
  Dumbbell,
  FileText,
  GraduationCap,
  Headphones,
  House,
  Map,
  Newspaper,
  Sparkles,
} from "lucide-react";
import { usePathname } from "next/navigation";
import dynamic from "next/dynamic";

import { type NavItem } from "@/components/nav";
import { FeedbackDock } from "@/components/feedback-dock";
import { PetlandCard } from "@/components/petland/petland-card";
import { SidebarShell, TopBarShell } from "@/components/shell";
import { SiteFooter } from "@/components/site-footer";
import { useReviewCount } from "@/lib/review-count";
import { useSession } from "@/lib/session";

/*
 * Bảng thú cưng là khối TSX lớn nhất của app (kèm dữ liệu bản đồ + bestiary),
 * nhưng nó chỉ hiện khi có người mở nó — còn khi đóng thì bản thân component
 * dựng ra `null`. Tải lười nó ra khỏi bundle của MỌI trang có sidebar: thẻ nhỏ
 * ở sidebar (`PetlandCard`) vẫn nhập tĩnh vì nó hiện luôn.
 */
const PetLand = dynamic(() => import("@/components/petland/petland").then((m) => m.PetLand), {
  ssr: false,
});

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
/*
 * Ba KHO NỘI DUNG, hiện với mọi người kể cả khách vãng lai.
 *
 * Cả ba trang này đã công khai từ trước — `/learn/tests` có hẳn chú thích nói đó
 * là chủ ý, `/learn/vocabulary` dùng `useSession` chứ không phải
 * `useRequireSession`, và `/learn/dictation` vừa được mở. Nên bày chúng ra
 * không phải là mời người ta bấm vào chỗ sẽ đá họ ngược lại: mỗi mục ở đây dẫn
 * tới một trang khách xem được thật.
 */
const CONTENT_LINKS: NavItem[] = [
  { href: "/learn/vocabulary", label: "Từ vựng", Icon: BookOpen },
  // Cảnh 3D từng núp dưới `covers` của Từ vựng; nay là lối vào trực tiếp nên
  // đứng riêng — giữ `covers` là hoà depth với mục này và đèn sáng nhầm chỗ.
  { href: "/learn/scenes", label: "Visual Words", Icon: Boxes },
  { href: "/learn/dictation", label: "Dictation", Icon: Headphones },
  { href: "/learn/grammar", label: "Ngữ pháp", Icon: GraduationCap },
  { href: "/learn/parts", label: "Luyện theo part", Icon: Dumbbell },
  { href: "/learn/tests", label: "Luyện giải đề", Icon: FileText },
];

/*
 * Hai mục CHỈ có nghĩa khi đã đăng nhập, nên chúng chỉ hiện ở sidebar sau khi
 * đăng nhập — không bao giờ ở thanh trên của trang giới thiệu.
 *
 * "Hôm nay" là việc của một người cụ thể và "Trợ lý AI" cần một tài khoản để
 * nói chuyện. Bày chúng cho khách là hứa hai nơi chốn rồi đá họ về `/login` —
 * đúng cái mà bộ mục cũ đã tránh, và lý do đó vẫn còn nguyên với hai mục này.
 */
const TODAY_LINK: NavItem = {
  // `covers`: các chế độ mở ra từ trang chủ nhưng không nằm dưới `/dashboard`.
  // Không khai báo thì mở "Ôn tập" xong cả sidebar tắt đèn.
  href: "/dashboard",
  label: "Hôm nay",
  Icon: House,
  covers: ["/learn/review", "/learn/typing", "/learn/attempts"],
};
const PLAN_LINK: NavItem = {
  // Kế hoạch + màn setup placement là cùng một câu hỏi ("học gì bây giờ?"),
  // nên `/learn/placement` nằm dưới mục này chứ không tạo mục thứ hai.
  href: "/learn/plan",
  label: "Kế hoạch học",
  Icon: Map,
  covers: ["/learn/placement"],
};
const ASSISTANT_LINK: NavItem = {
  href: "/learn/assistant",
  label: "Trợ lý AI",
  Icon: Sparkles,
};

/*
 * Ba trang dùng thanh trên thay vì sidebar, và cả ba vì cùng một lý do: chúng
 * đứng NGOÀI ứng dụng. Trang giới thiệu nói chuyện với người chưa có tài khoản;
 * `/login` và `/register` là cánh cửa vào. Dựng một cột điều hướng đầy mục cho
 * người chưa bước qua cửa là mời họ bấm vào những nơi sẽ đá họ ngược về đây.
 *
 * Blog (`isBlogRoute` dưới đây) đi cùng khung này vì lý do riêng, xem chú thích
 * ở đó — không gộp vào `TOP_BAR_ROUTES` vì nó là tiền tố động (`/blog/[slug]`).
 *
 * Danh sách theo ĐƯỜNG DẪN chứ không theo trạng thái phiên. Trạng thái chỉ phân
 * giải được sau khi JS chạy (localStorage không tồn tại lúc render ở máy chủ),
 * nên chọn khung theo nó sẽ dựng một khung rồi đổi sang khung kia ngay trước
 * mắt người dùng — đúng cái bẫy ba-trạng-thái đã ghi trong CLAUDE.md, lần này
 * hiện ra thành một cú nhảy layout thay vì một cái nút sai.
 */
const TOP_BAR_ROUTES = new Set(["/", "/login", "/register"]);

/*
 * Blog là khu RIÊNG BIỆT, không sidebar như các mục học tập.
 *
 * Người đọc blog (kể cả từ Google) không phải lúc nào cũng là học viên đang
 * học dở — dựng sidebar "Học" cạnh bài viết là mời họ đi lạc khỏi bài, còn
 * bareLayout thì mất luôn đường về. Thanh trên + footer là vừa: đọc xong bài
 * vẫn thấy đường vào test đầu vào/luyện part (funnel của SPEC-BLOG §6), và
 * khung này đã tồn tại nên không thêm loại layout thứ tư.
 */
const isBlogRoute = (pathname: string) => pathname === "/blog" || pathname.startsWith("/blog/");

/*
 * Blog trong menu "Thêm" của thanh trên — nhưng KHÔNG trong CONTENT_LINKS.
 *
 * CONTENT_LINKS nuôi cả sidebar ("Hôm nay", "Kế hoạch", ...): nhét Blog vào đó
 * là nó hiện ở sidebar, đúng thứ quyết định tách blog thành khu riêng đã loại.
 * Nối riêng ở `more` dưới đây thì chỉ thanh trên có Blog, sidebar không biết.
 */
const BLOG_LINK: NavItem = { href: "/blog", label: "Blog", Icon: Newspaper };

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const review = useReviewCount();
  const { status } = useSession();
  const signedIn = status === "authenticated";
  // Huy hiệu đếm THẺ ĐẾN HẠN, không cộng từ mới: đến hạn là việc có hạn chót
  // (sắp quên), còn từ mới là lời mời. Cộng cả hai thì huy hiệu đứng ở 10–20
  // mãi vì từ mới chưa học vẫn còn đó, và người vắng mặt tuần thấy "99+" mà
  // không biết đó là nợ cũ hay việc hôm nay.
  //
  // "100+" khi lô đầy mà hàng đợi còn dài: nói đúng "còn hơn 100 thẻ", thay vì
  // "99+" (trần hiển thị cũ) vốn chỉ là quy ước của con số, không của hàng đợi.
  const badge =
    review.due > 0 ? (review.dueTotal > review.due ? `${review.due}+` : review.due) : undefined;
  // Gắn huy hiệu vào đúng mục từ vựng. Ghép theo `href`, không theo chỉ số:
  // thêm hay đổi thứ tự mục thì huy hiệu vẫn bám đúng chỗ.
  const withBadge = (list: NavItem[]): NavItem[] =>
    list.map((link) => (link.href === "/learn/vocabulary" ? { ...link, badge } : link));

  // Thanh trên của trang giới thiệu: LUÔN đúng ba kho nội dung, không phụ thuộc
  // phiên. Sidebar thì thêm các mục của tài khoản khi đã đăng nhập, giữ nguyên
  // thứ tự cũ — "Hôm nay" mở đầu, kế hoạch học cạnh nó (cả hai là "học gì bây
  // giờ" của một người cụ thể), rồi các kho nội dung, "Trợ lý AI" khép lại.
  const topBarLinks = withBadge(CONTENT_LINKS);
  const sidebarLinks = withBadge(
    signedIn ? [TODAY_LINK, PLAN_LINK, ...CONTENT_LINKS, ASSISTANT_LINK] : CONTENT_LINKS,
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

  if (TOP_BAR_ROUTES.has(pathname) || isBlogRoute(pathname)) {
    return (
      <TopBarShell
        links={topBarLinks}
        // Nav ngang: hai mục chính thẳng hàng, phần còn lại gộp vào "Thêm"
        // (yêu cầu bố cục 2026-09-07). Ngăn kéo mobile vẫn hiện phẳng cả bộ
        // — `TopBarShell` tự lọc, đây chỉ là NGUỒN.
        more={[
          ...topBarLinks.filter((l) => ["/learn/grammar", "/learn/parts"].includes(l.href)),
          BLOG_LINK,
        ]}
        sectionLabel="Học"
        footer={<SiteFooter links={topBarLinks} />}
      >
        {children}
      </TopBarShell>
    );
  }

  return (
    <SidebarShell links={sidebarLinks} sectionLabel="Học" sidebarBottom={<PetlandCard />}>
      {children}
      {/* Bảng thú cưng: đóng thì không dựng gì, mở thì do thẻ ở sidebar gọi.
          Chỉ ở khung có sidebar — ba trang thanh trên đứng NGOÀI ứng dụng, còn
          khu quản trị và màn làm bài đi qua nhánh `bareLayout` phía trên. */}
      <PetLand />
      {/* Nút góp ý: cùng phạm vi với `PetLand`, và cùng lý do. Khu quản trị đã
          có đường riêng để xem góp ý, còn người đang thi thì không nên được mời
          làm gì khác — cả hai đi qua nhánh `bareLayout` phía trên nên không
          nhận nút này. Ba trang thanh trên là trang giới thiệu, chưa đăng nhập,
          mà `feedback.user_id` là NOT NULL. */}
      <FeedbackDock />
    </SidebarShell>
  );
}
