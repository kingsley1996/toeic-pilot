"use client";

import {
  LogIn,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  SquarePen,
  UserPlus,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import { API_ROUTES, type BackdropPublic } from "@toeic-pilot/shared";

import { NavLink, SessionControls, type NavItem } from "@/components/nav";
import { activeHref, isBranchOpen } from "@/components/nav-active";
import { SoundToggle } from "@/components/sound-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, ButtonLink, IconButton, Skeleton, Tag, cx } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useProgression } from "@/lib/progression";
import {
  getSidebarState,
  serverSidebarState,
  setSidebarState,
  subscribeToSidebar,
} from "@/lib/sidebar";
import { useSession } from "@/lib/session";

/**
 * Khung có sidebar, dùng chung cho CẢ khu học lẫn khu quản trị.
 *
 * Hai khu từng có hai khung riêng, và cái giá của việc đó không lộ ra ngay: mỗi
 * lần sửa khoảng cách, chiều rộng cột hay cách gấp trên mobile là phải nhớ sửa
 * ở hai chỗ, và chỗ bị quên thì vẫn chạy — chỉ lệch đi vài pixel mà không ai
 * báo. Bộ MỤC thì vẫn riêng (`links` là tham số): học viên và biên tập viên làm
 * hai việc khác hẳn nhau, trộn hai bộ nav lại sẽ xoá mất ranh giới giữa "đang
 * học" và "đang sửa nội dung người khác sẽ học".
 *
 * Cùng MỘT `SidebarContent` được dựng hai lần — một lần trong cột trái từ `lg`
 * trở lên, một lần trong ngăn kéo dưới `lg`. Đây là chỗ dễ sinh ra "menu thứ
 * hai" phải bảo trì riêng, và menu thứ hai luôn là menu bị quên khi thêm mục.
 */

export type ShellNavItem = NavItem & {
  children?: NavItem[];
  /**
   * Tiêu đề nhóm in RA TRÊN mục này, khi nó khác nhóm của mục ngay trước.
   *
   * Khu quản trị có bảy mục gốc làm ba việc không liên quan nhau — soạn nội
   * dung, chỉnh giao diện, xem tầng AI — và xếp cả bảy vào một cột phẳng thì
   * người đọc phải tự đoán ranh giới. Bên khu học không mục nào có `group`, nên
   * ở đó không có tiêu đề nào được in ra.
   */
  group?: string;
};

/*
 * Nền động, đo bằng SỐ Ô lưới chứ không bằng pixel hay phần trăm: lưới là bội
 * số của 32px kể từ gốc khung cố định, nên chỉ số ô mới đảm bảo tia và đốm nằm
 * đúng trên đường kẻ ở mọi kích thước màn hình. Phần trăm sẽ trôi lệch khỏi
 * lưới ngay khi đổi chiều rộng cửa sổ, và một vệt sáng trôi CẠNH lưới thì mắt
 * đọc ra là sai ngay.
 */
const GRID_CELL = 32;

/*
 * Bảng vị trí CỐ ĐỊNH; cấu hình quản trị chỉ chọn lấy bao nhiêu phần tử đầu.
 *
 * Vị trí không lưu trong database, và đó là chủ ý: một toạ độ lưu sẵn phải hợp
 * lệ với mọi kích thước màn hình, mà lúc lưu thì không có màn hình nào để kiểm.
 * Ở đây thứ tự đã được chọn sao cho phần tử đầu nằm bên trái — màn hình hẹp
 * vẫn thấy — rồi mới lan dần sang phải.
 *
 * `col`/`row` là góc trên-trái, `size` là cạnh hình vuông, tính bằng ô. Chu
 * kỳ lẻ nhau và lệch pha, nên các tia không bao giờ rơi vào một nhịp đều đặn —
 * nền mà mắt bắt được nhịp là nền đã hỏng.
 */
const METEORS = [
  // Điểm xuất phát tính bằng ô lưới, và ô ÂM là hợp lệ: sao băng phải bắt đầu
  // ngoài khung rồi mới lao vào, nếu không nó "hiện ra" giữa trời.
  //
  // Cùng một góc cho tất cả — mưa sao băng thật toả ra từ một hướng, và mỗi vệt
  // một góc trông như nhiễu chứ không như một hiện tượng. Chu kỳ lẻ nhau để các
  // vệt không rơi thành nhịp đều đặn; `delay` rải chúng ra trong một vòng.
  { left: -8, top: 1, duration: 11, delay: 0 },
  { left: 14, top: -10, duration: 17, delay: 5 },
  { left: -12, top: 12, duration: 14, delay: 9 },
  { left: 30, top: -14, duration: 21, delay: 3 },
  { left: 6, top: -18, duration: 19, delay: 13 },
  { left: 22, top: 6, duration: 25, delay: 17 },
] as const;

const METEOR_ANGLE = "34deg";
const METEOR_TRAVEL = "150vmax";

/*
 * Đốm sáng ở giao điểm lưới. Mỗi đốm chỉ loé một nhịp ngắn trong cả chu kỳ, và
 * đỉnh sáng đặt SỚM (6% chu kỳ) chứ không muộn: đặt muộn thì lần loé ĐẦU TIÊN
 * bị lùi gần trọn một chu kỳ, và đo thật thì hai trong năm đốm chưa hề sáng sau
 * 20 giây mở trang.
 */
const TWINKLES = [
  { col: 7, row: 5, duration: 9, delay: 1 },
  { col: 14, row: 11, duration: 13, delay: 5 },
  { col: 21, row: 4, duration: 11, delay: 3 },
  { col: 31, row: 16, duration: 17, delay: 8 },
  { col: 37, row: 8, duration: 15, delay: 12 },
  { col: 4, row: 18, duration: 10, delay: 6 },
  { col: 25, row: 21, duration: 14, delay: 2 },
  { col: 11, row: 2, duration: 12, delay: 9 },
  { col: 33, row: 25, duration: 16, delay: 4 },
  { col: 18, row: 27, duration: 18, delay: 11 },
  { col: 29, row: 6, duration: 19, delay: 7 },
  { col: 2, row: 12, duration: 21, delay: 14 },
] as const;

/*
 * Giá trị rơi về khi chưa đọc được cấu hình. Phải KHỚP `BACKDROP_DEFAULTS` phía
 * máy chủ — hai bộ mặc định lệch nhau nghĩa là trang nhấp nháy đổi hình một lần
 * ngay sau khi tải xong, mà không có gì báo.
 */
const BACKDROP_FALLBACK: BackdropPublic = {
  spark_count: 2,
  twinkle_count: 5,
  color: "action",
  speed_percent: 100,
  enabled: true,
};

/**
 * Chu kỳ sau khi áp hệ số tốc độ.
 *
 * Chia chứ không nhân: `speed_percent` là TỐC ĐỘ, nên số càng lớn thì chu kỳ
 * càng ngắn. Làm ngược lại thì thanh chỉnh "nhanh hơn" cho ra hiệu ứng chậm
 * hơn — một lỗi không ai báo vì nó vẫn chạy, chỉ sai chiều.
 */
function scaled(seconds: number, speedPercent: number): string {
  return `${((seconds * 100) / speedPercent).toFixed(2)}s`;
}

/**
 * Nền lưới + tia sáng + đốm lấp lánh, dựng một lần cho mỗi khung.
 *
 * `aria-hidden` và `pointer-events-none`: nó không mang thông tin và không được
 * chắn cú bấm nào. Màn làm bài KHÔNG có nền này — nó dùng `bareLayout` nên
 * không đi qua đây, và đó là chủ ý: một vệt sáng chuyển động sau lưng người
 * đang tính giờ làm bài là thứ duy nhất trong app cạnh tranh trực tiếp với sự
 * tập trung.
 *
 * Cấu hình đọc từ endpoint CÔNG KHAI, nên khách xem trang giới thiệu cũng thấy
 * đúng thứ quản trị viên vừa đặt. Hỏng thì rơi về mặc định chứ không mất nền.
 */
function GridBackdrop() {
  const [config, setConfig] = useState<BackdropPublic>(BACKDROP_FALLBACK);
  useEffect(() => {
    apiFetch<BackdropPublic>(API_ROUTES.backdrop)
      .then(setConfig)
      .catch(() => {});
  }, []);

  // Lưới tĩnh vẫn ở lại khi tắt hiệu ứng: `enabled=false` tắt phần CHUYỂN ĐỘNG,
  // không tắt nền.
  const meteors = config.enabled ? METEORS.slice(0, config.spark_count) : [];
  const twinkles = config.enabled ? TWINKLES.slice(0, config.twinkle_count) : [];

  return (
    <div
      aria-hidden
      className="grid-backdrop"
      style={{ "--spark-color": `var(--${config.color})` } as React.CSSProperties}
    >
      {meteors.map((meteor) => (
        <span
          key={`${meteor.left}-${meteor.top}`}
          className="grid-meteor"
          style={
            {
              left: `${meteor.left * GRID_CELL}px`,
              top: `${meteor.top * GRID_CELL}px`,
              "--meteor-angle": METEOR_ANGLE,
              "--meteor-travel": METEOR_TRAVEL,
              "--meteor-duration": scaled(meteor.duration, config.speed_percent),
              "--meteor-delay": scaled(meteor.delay, config.speed_percent),
            } as React.CSSProperties
          }
        >
          <span className="grid-meteor-body" />
        </span>
      ))}

      {twinkles.map((dot) => (
        <span
          key={`t-${dot.col}-${dot.row}`}
          className="grid-twinkle"
          style={
            {
              left: `${dot.col * GRID_CELL}px`,
              top: `${dot.row * GRID_CELL}px`,
              "--twinkle-duration": scaled(dot.duration, config.speed_percent),
              "--twinkle-delay": scaled(dot.delay, config.speed_percent),
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}

/**
 * Nút thu gọn sidebar, chỉ có từ `lg` trở lên.
 *
 * Dưới `lg` sidebar đã là ngăn kéo phủ toàn màn — thu gọn nó thành dải icon là
 * một trạng thái thứ ba không giải quyết vấn đề nào.
 *
 * Bề rộng KHÔNG do state này quyết định: nó do `data-sidebar` trên `<html>`, đặt
 * xong trước khi trang vẽ. Ở đây chỉ cần biết mình đang là mũi tên nào, và một
 * frame sai của một icon 16px thì không ai thấy — một cột 240px co lại thì có.
 * `undefined` ở lần dựng đầu là "chưa đọc được localStorage", cùng ba-trạng-thái
 * như `ThemeToggle`.
 */
function SidebarToggle() {
  const state = useSyncExternalStore(subscribeToSidebar, getSidebarState, serverSidebarState);
  const collapsed = state === "collapsed";

  return (
    <IconButton
      icon={collapsed ? PanelLeftOpen : PanelLeftClose}
      aria-label={collapsed ? "Mở rộng thanh bên" : "Thu gọn thanh bên"}
      aria-expanded={state === undefined ? undefined : !collapsed}
      onClick={() => setSidebarState(collapsed ? "expanded" : "collapsed")}
      className="hidden lg:grid"
    />
  );
}

/** Phẳng hoá để `activeHref` thấy cả mục con; nó tự ưu tiên khớp sâu nhất. */
function flatten(links: ShellNavItem[]): NavItem[] {
  return links.flatMap((item) => [item, ...(item.children ?? [])]);
}

/**
 * Danh tính + lối thoát, đặt ở ĐÁY sidebar chứ không nằm trong menu xổ ở header.
 *
 * Ở đây chúng là hai dòng nhìn thấy được thay vì hai mục giấu sau một cú bấm.
 * Sidebar có sẵn chiều cao để làm thế, còn header thì không — đó là lý do bản
 * cũ phải gói chúng vào dropdown ngay từ đầu.
 *
 * Ba trạng thái phiên, không phải hai: `loading` dựng khối giữ chỗ chứ KHÔNG
 * dựng nút của người chưa đăng nhập. Đoán sai ở đây chính là thứ từng khiến
 * header mời "Đăng nhập" với người đã đăng nhập rồi.
 */
function AccountBlock({ showRole }: { showRole: boolean }) {
  const { status, user, token, canEdit, logout } = useSession();
  const pathname = usePathname();
  // Level và khung — xem `lib/progression.ts` để biết vì sao nó không nằm trong
  // phiên đăng nhập.
  const progression = useProgression(token);
  // Đang ở trong khu quản trị rồi thì lối vào nó là một dòng trỏ về chính chỗ
  // đang đứng. Đường ra là "Back to learning" trên đầu sidebar, không phải đây.
  const inAdmin = pathname === "/admin" || pathname.startsWith("/admin/");

  if (status === "loading") {
    return (
      <div className="shrink-0 border-t border-rule px-2 py-3">
        <Skeleton className="h-9 w-full" />
      </div>
    );
  }

  if (status === "anonymous" || !user) {
    return (
      <div className="flex shrink-0 flex-col gap-2 border-t border-rule px-2 py-3">
        {/* Cả hai lối vào đều sống sót qua lúc thu gọn, chỉ rụng mất chữ: bỏ một
            cái đi là quyết định hộ người dùng rằng họ định làm gì. */}
        <ButtonLink href="/login" variant="secondary" size="sm" className="rail:px-0">
          <LogIn size={14} strokeWidth={2} aria-hidden className="hidden rail:block" />
          <span className="rail:sr-only">Đăng nhập</span>
        </ButtonLink>
        <ButtonLink href="/register" size="sm" className="rail:px-0">
          <UserPlus size={14} strokeWidth={2} aria-hidden className="hidden rail:block" />
          <span className="rail:sr-only">Tạo tài khoản</span>
        </ButtonLink>
      </div>
    );
  }

  // Dòng email chỉ hiện khi có tên hiển thị RIÊNG. `display_name` là nullable và
  // phần lớn tài khoản chưa đặt, nên `name ?? email` rồi in cả hai dòng cho ra
  // cùng một chuỗi hai lần — trông như lỗi dữ liệu chứ không như một khối danh
  // tính. Menu xổ cũ giấu chuyện này vì nó chỉ mở ra khi được bấm.
  const displayName = user.profile.display_name;

  return (
    <div className="shrink-0 border-t border-rule px-2 py-2">
      <Link
        href="/profile"
        className="flex items-center gap-2.5 rounded px-2 py-2 transition-colors hover:bg-recess rail:justify-center rail:px-0"
        title={displayName ?? user.email}
      >
        {/* `md` chứ không `sm`: huy hiệu level cần chỗ để đọc được, và ở 28px
            nó chiếm gần một phần ba ô. Đây là avatar THƯỜNG TRỰC của người dùng,
            nên nếu chỉ một cỡ được mang huy hiệu thì phải là cỡ này. */}
        <Avatar
          id={user.id}
          name={displayName}
          email={user.email}
          src={user.profile.avatar_url}
          size="md"
          frame={progression?.frame}
          level={progression?.level}
        />
        <span className="min-w-0 flex-1 rail:sr-only">
          <span className="block truncate text-small font-semibold">
            {displayName ?? user.email}
          </span>
          {displayName && (
            <span className="block truncate text-label text-ink-faint">{user.email}</span>
          )}
        </span>
      </Link>

      {showRole && user.role !== "learner" && (
        <div className="px-2 pb-1 rail:hidden">
          <Tag tone="action">{user.role}</Tag>
        </div>
      )}

      {/*
       * Cửa vào khu quản trị nằm trong khối TÀI KHOẢN, không phải trong bộ mục
       * học. Nó là thứ dùng vài lần một ngày bởi một số ít người, còn bộ mục
       * trên kia là chỗ dành cho việc học — một mục thường trực ở đó lấy chỗ của
       * điều hướng thật và nói với mọi học viên rằng có một khu vực họ không vào
       * được. Chỉ hiện với người thực sự mở được nó; máy chủ vẫn chặn bằng
       * `require_role` dù giao diện có hiện hay không.
       */}
      {canEdit && !inAdmin && (
        <Link
          href="/admin"
          title="Quản trị nội dung"
          className="flex items-center gap-2.5 rounded px-2.5 py-2 text-small font-semibold text-ink-muted transition-colors hover:bg-recess hover:text-ink rail:justify-center rail:px-0"
        >
          <SquarePen size={16} strokeWidth={1.75} aria-hidden />
          <span className="rail:sr-only">Quản trị nội dung</span>
        </Link>
      )}

      <button
        type="button"
        onClick={logout}
        title="Đăng xuất"
        className="flex w-full items-center gap-2.5 rounded px-2.5 py-2 text-left text-small font-semibold text-alert transition-colors hover:bg-recess rail:justify-center rail:px-0"
      >
        <LogOut size={16} strokeWidth={1.75} aria-hidden />
        <span className="rail:sr-only">Đăng xuất</span>
      </button>
    </div>
  );
}

function SidebarContent({
  links,
  active,
  sectionLabel,
  sidebarTop,
  showRole,
}: {
  links: ShellNavItem[];
  active: string | undefined;
  sectionLabel?: string;
  sidebarTop?: React.ReactNode;
  showRole: boolean;
}) {
  return (
    <div className="flex h-full flex-col">
      {sidebarTop && <div className="border-b border-rule px-2 py-2">{sidebarTop}</div>}

      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
        {sectionLabel && (
          <p className="mb-2 px-2.5 text-label font-semibold uppercase text-ink-faint rail:sr-only">
            {sectionLabel}
          </p>
        )}
        <nav className="flex flex-col gap-1">
          {links.map((item, index) => (
            <div key={item.href} className="contents">
              {item.group && item.group !== links[index - 1]?.group && (
                /* Thu gọn thì chữ không còn chỗ, nhưng RANH GIỚI nhóm thì vẫn
                   phải thấy: bảy icon xếp liền một cột là bảy việc không liên
                   quan trông như một danh sách. Cái `<p>` co lại thành một
                   đường kẻ, và tên nhóm đi tiếp tới trình đọc màn hình. */
                <p
                  className={cx(
                    "px-2.5 text-label font-semibold uppercase text-ink-faint",
                    index === 0 ? "mb-1" : "mb-1 mt-4",
                    "rail:mx-2 rail:h-px rail:bg-rule rail:px-0",
                    index === 0 && "rail:hidden",
                  )}
                >
                  <span className="rail:sr-only">{item.group}</span>
                </p>
              )}
              {/* Spread, không liệt kê từng prop: bản liệt kê chép ba trường và
                  im lặng đánh rơi mọi trường thêm sau này. `badge` được thêm vào
                  `NavItem` và không bao giờ tới nơi vì đúng chỗ này — kiểu vẫn
                  đúng, trang vẫn chạy, huy hiệu chỉ đơn giản là không hiện. */}
              <NavLink
                {...item}
                title={item.label}
                active={item.href === active}
                className="justify-start"
              />
              {/* Mục con chỉ hiện khi đang ở trong khu đó. Hiện thường trực sẽ
                  làm sidebar dài ra vì những việc người dùng chưa quan tâm, và
                  mỗi tính năng mới lại thêm một dòng nữa. */}
              {item.children && isBranchOpen(item, active) && (
                /* Thụt lề bằng viền trái không sống nổi trong một dải 64px —
                   icon con lệch khỏi cột icon cha, và cái lệch đó đọc ra là hỏng
                   chứ không phải là phân cấp. Thu gọn thì bỏ thụt lề; mục con
                   vốn chỉ hiện khi đang ở trong khu đó nên ngữ cảnh không mất. */
                <div className="ml-3 flex flex-col gap-1 border-l border-rule pl-2 rail:ml-0 rail:border-l-0 rail:pl-0">
                  {item.children.map((child) => (
                    <NavLink
                      key={child.href}
                      {...child}
                      title={child.label}
                      active={child.href === active}
                      className="justify-start"
                    />
                  ))}
                </div>
              )}
            </div>
          ))}
        </nav>
      </div>

      <AccountBlock showRole={showRole} />
    </div>
  );
}

export function SidebarShell({
  links,
  sectionLabel,
  headerExtra,
  sidebarTop,
  showRole = false,
  footer,
  children,
}: {
  links: ShellNavItem[];
  sectionLabel?: string;
  /** Dựng trong header, ngay sau logo. */
  headerExtra?: React.ReactNode;
  /** Dựng trên đầu sidebar, phía trên bộ mục. */
  sidebarTop?: React.ReactNode;
  showRole?: boolean;
  footer?: React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const active = activeHref(flatten(links), pathname);

  /*
   * Ngăn kéo mobile được đóng dấu bằng đường dẫn mà nó được mở ra trên đó, nên
   * điều hướng làm nó tự đóng THEO SUY DIỄN — không cần effect. Cách hiển nhiên
   * là `useEffect(() => setOpen(false), [pathname])`, nhưng đó là setState đồng
   * bộ trong thân effect, thứ mà lint `react-hooks/set-state-in-effect` chặn
   * đúng chỗ này. Cách dưới đây còn đúng cho MỌI kiểu điều hướng, kể cả bấm
   * logo hay quay lại bằng nút back.
   */
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const menuOpen = openedAt === pathname;

  return (
    <div className="flex min-h-screen flex-col">
      <GridBackdrop />
      {/* Header mỏng: logo, chỗ cắm riêng của từng khu, đổi sáng/tối. Danh tính
          và đăng xuất KHÔNG ở đây — chúng nằm dưới đáy sidebar. */}
      <header className="sticky top-0 z-30 border-b border-rule bg-ground/85 backdrop-blur">
        <div className="flex h-16 items-center gap-3 px-4">
          <IconButton
            icon={menuOpen ? X : Menu}
            aria-label={menuOpen ? "Đóng menu" : "Mở menu"}
            aria-expanded={menuOpen}
            onClick={() => setOpenedAt(menuOpen ? null : pathname)}
            className="lg:hidden"
          />
          {/* Cùng vị trí với hamburger, và hai cái loại trừ nhau theo breakpoint:
              một khung chỉ có đúng một nút điều khiển sidebar, luôn ở một chỗ. */}
          <SidebarToggle />

          {/* Logo LUÔN về trang giới thiệu, kể cả khi đã đăng nhập: quy ước
              chung của web là logo = gốc của site. Đường về nhà không mất — nó
              là mục đầu tiên của sidebar. */}
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

          {headerExtra}

          <div className="ml-auto flex items-center gap-2">
            <SoundToggle />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <div className="flex flex-1">
        {/*
         * Cột trái ĐỨNG YÊN khi nội dung cuộn: `sticky` dưới header cao 4rem, và
         * tự cuộn bên trong khi bộ mục dài hơn màn hình. Dùng `dvh` chứ không
         * `vh` vì trên trình duyệt di động `vh` tính cả phần thanh địa chỉ tự
         * ẩn, nên khối tài khoản ở đáy bị đẩy khuất khỏi màn hình.
         */}
        <aside
          /* Mốc của biến thể `rail:` — xem `tailwind.config.ts`. Không có nó,
             `data-sidebar` trên `<html>` sẽ thu gọn cả nav ngang của trang giới
             thiệu lẫn ngăn kéo mobile, hai chỗ dùng chung component này. */
          data-rail
          className="sticky top-16 hidden h-[calc(100dvh-4rem)] w-60 shrink-0 border-r border-rule transition-[width] duration-enter motion-reduce:transition-none lg:block rail:w-16"
        >
          <SidebarContent
            links={links}
            active={active}
            sectionLabel={sectionLabel}
            sidebarTop={sidebarTop}
            showRole={showRole}
          />
        </aside>

        <main className="min-w-0 flex-1">{children}</main>
      </div>

      {/* Dưới `lg`, sidebar thành ngăn kéo phủ toàn màn — CÙNG một component,
          không phải một menu thứ hai. */}
      {menuOpen && (
        <div className="fixed inset-0 top-16 z-20 bg-ground lg:hidden">
          <SidebarContent
            links={links}
            active={active}
            sectionLabel={sectionLabel}
            sidebarTop={sidebarTop}
            showRole={showRole}
          />
        </div>
      )}

      {footer}
    </div>
  );
}

/**
 * Khung chỉ có thanh trên, dùng cho trang giới thiệu và hai trang xác thực.
 *
 * Ba trang này KHÔNG có sidebar, và lý do giống nhau: chúng không nằm trong ứng
 * dụng. Trang giới thiệu nói chuyện với người chưa có tài khoản, còn `/login` và
 * `/register` là cánh cửa vào — dựng một cột điều hướng đầy mục cho người chưa
 * bước qua cửa là mời họ bấm vào những nơi sẽ đá họ ngược về đây.
 *
 * Chọn theo ĐƯỜNG DẪN chứ không theo trạng thái phiên: trạng thái chỉ phân giải
 * được sau khi JS chạy, nên chọn theo nó sẽ dựng một khung rồi đổi sang khung
 * kia ngay trước mắt người dùng.
 */
export function TopBarShell({
  links,
  sectionLabel,
  children,
  footer,
}: {
  links: NavItem[];
  sectionLabel?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const pathname = usePathname();
  const { status } = useSession();
  const active = activeHref(links, pathname);

  /*
   * Cùng cách đóng dấu bằng đường dẫn như `SidebarShell` — xem chú thích dài ở
   * đó về lý do không dùng effect.
   *
   * Bộ mục ở đây KHÔNG phụ thuộc phiên: `app-shell` chỉ đưa xuống ba kho nội
   * dung, và cả ba đều xem được khi chưa đăng nhập. Trước đây nav bị chặn sau
   * `status === "authenticated"`, nên khách vãng lai đứng ở trang giới thiệu
   * không có lối nào vào phần học. Không còn ba trạng thái để lo ở chỗ này, và
   * cũng không còn cú nháy khi phiên phân giải xong.
   */
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const menuOpen = openedAt === pathname;
  const hasNav = links.length > 0;

  return (
    <div className="flex min-h-screen flex-col">
      <GridBackdrop />
      {/* `z-30` chứ không `z-20`: ngăn kéo ở `z-20` và đứng sau trong DOM, nên
          header ngang cơ sẽ bị chính nó phủ mất — cùng nút vừa dùng để mở. */}
      <header className="sticky top-0 z-30 border-b border-rule bg-ground/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4">
          {hasNav && (
            <IconButton
              icon={menuOpen ? X : Menu}
              aria-label={menuOpen ? "Đóng menu" : "Mở menu"}
              aria-expanded={menuOpen}
              onClick={() => setOpenedAt(menuOpen ? null : pathname)}
              className="md:hidden"
            />
          )}

          <Link
            href="/"
            className="flex shrink-0 items-center gap-2 font-display text-subtitle font-semibold tracking-tight"
          >
            <span
              aria-hidden
              className="grid h-7 w-7 place-items-center rounded bg-action font-data text-small text-on-action"
            >
              T
            </span>
            <span className="hidden sm:inline">TOEIC Pilot</span>
          </Link>

          {hasNav && (
            <nav className="ml-1 hidden items-center gap-0.5 md:flex">
              {links.map((link) => (
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

            {/* Menu tài khoản vẫn ở đây, KHÔNG chỉ ở sidebar. Ba trang này không
                có sidebar, nên bỏ nó đi là người đã đăng nhập đứng ở trang giới
                thiệu không còn lối nào để xem hồ sơ hay đăng xuất — họ phải vào
                lại ứng dụng trước đã. */}
            <SessionControls />
          </div>
        </div>
      </header>

      {/*
       * Dưới `md`, nav ngang biến mất — và trước đây KHÔNG có gì thay nó, nên
       * người đã đăng nhập đứng ở ba trang này trên điện thoại không còn lối
       * vào bất cứ phần nào của ứng dụng.
       *
       * Dùng lại `SidebarContent`, không viết một menu thứ hai: thêm một mục vào
       * `LEARN_LINKS` phải hiện ra ở cả hai khung mà không ai phải nhớ.
       */}
      {hasNav && menuOpen && (
        <div className="fixed inset-0 top-16 z-20 bg-ground md:hidden">
          <SidebarContent
            links={links}
            active={active}
            sectionLabel={sectionLabel}
            showRole={false}
          />
        </div>
      )}

      <main className="flex-1">{children}</main>
      {footer}
    </div>
  );
}
