"use client";

import {
  ArrowLeft,
  ClipboardList,
  Cpu,
  FolderTree,
  Frame,
  Gauge,
  Gem,
  Grid2x2,
  Headphones,
  Library,
  ListTree,
  Palette,
  PawPrint,
  Sparkles,
  SquarePen,
  Tags,
} from "lucide-react";
import Link from "next/link";

import { SidebarShell, type ShellNavItem } from "@/components/shell";
import { Skeleton, Tag } from "@/components/ui";
import { useRequireSession } from "@/lib/session";

/*
 * Điều hướng của khu quản trị. Nó KHÔNG nằm chung với bộ mục của khu học: học
 * viên và biên tập viên làm hai việc khác hẳn nhau, và trộn hai bộ lại xoá mất
 * ranh giới giữa "đang học" và "đang sửa nội dung người khác sẽ học".
 *
 * Cái KHUNG thì dùng chung (`components/shell.tsx`). Hai khung riêng là hai bản
 * sao của cùng một layout, và cái giá không lộ ra ngay: sửa khoảng cách hay
 * cách gấp trên mobile ở một bên, bên kia lệch đi mà vẫn chạy.
 */
type AdminNavItem = ShellNavItem;

const ADMIN_LINKS: AdminNavItem[] = [
  { href: "/admin", label: "Overview", Icon: SquarePen },

  /*
   * Cây của một khu là MỤC CON của khu đó, không phải một mục gốc thứ hai.
   *
   * Trước kia "Vocabulary tree" và "Content tree" đứng ngang hàng với
   * "Vocabulary" và "Dictation", cùng một biểu tượng thư mục, và cái tên thứ hai
   * còn không nói nó là cây của khu nào — trong khi màn đề thi lại gọi phần cây
   * của nó cũng là "Cây nội dung". Ba cây, hai cái trùng tên, và hai tầng khác
   * nhau nằm chung một cột.
   */
  {
    href: "/admin/vocabulary",
    label: "Vocabulary",
    Icon: Library,
    group: "Content",
    children: [{ href: "/admin/vocabulary/tree", label: "Collections & topics", Icon: ListTree }],
  },
  {
    href: "/admin/dictation",
    label: "Dictation",
    Icon: Headphones,
    group: "Content",
    children: [{ href: "/admin/dictation/tree", label: "Topics & lessons", Icon: FolderTree }],
  },
  { href: "/admin/tests", label: "Tests", Icon: ClipboardList, group: "Content" },

  { href: "/admin/appearance", label: "Appearance", Icon: Palette, group: "System" },
  {
    href: "/admin/progression",
    label: "Progression",
    Icon: Gauge,
    group: "System",
    // Màn xem trước khung avatar là một TRANG THẬT không có lối vào nào trong
    // menu: nó tồn tại chính vì không phép kiểm nào trong terminal thấy được một
    // cái khung đặt lệch, mà thứ duy nhất mở nó ra lại là gõ tay đường dẫn.
    children: [{ href: "/admin/progression/preview", label: "Frame preview", Icon: Frame }],
  },
  {
    // Bảng loài thú và bảng giá ruby đứng cạnh nhau vì chúng là HAI NỬA của
    // cùng một quyết định vận hành: cái này định giá, cái kia định thứ mua
    // được. Cả hai là `require_role("admin")`, không phải `editor`.
    href: "/admin/pet",
    label: "Petland",
    Icon: PawPrint,
    group: "System",
    /*
     * Trình vẽ bản đồ là một TRANG THẬT mà thanh bên không hề trỏ tới — đúng
     * cùng một chỗ hỏng với màn xem trước khung avatar ở trên, và cùng một hệ
     * quả: cách duy nhất mở nó ra là gõ tay đường dẫn, nên nó tồn tại mà không
     * tồn tại.
     *
     * `/admin/ruby` cố ý KHÔNG nằm dưới `/admin/pet` — hai trang này là con của
     * nhau vì cùng một quyết định vận hành, không vì đường dẫn. Đó chính là ca
     * làm lộ lỗi mở nhánh theo tiền tố; xem `isBranchOpen`.
     */
    children: [
      { href: "/admin/petland", label: "Map editor", Icon: Grid2x2 },
      { href: "/admin/ruby", label: "Ruby rates", Icon: Gem },
    ],
  },
  {
    href: "/admin/ai",
    label: "AI layer",
    Icon: Sparkles,
    group: "System",
    // Gắn nhãn chỉ là MỘT việc của tầng AI, không phải cả tầng. Để nó ngang
    // hàng với "Tầng AI" ở menu chính sẽ ngụ ý hai khu riêng biệt, rồi mục thứ
    // hai (giải thích câu sai) và thứ ba (kế hoạch học) sẽ không biết đặt đâu.
    children: [
      { href: "/admin/ai/skill-tags", label: "Skill labels", Icon: Tags },
      { href: "/admin/ai/providers", label: "Providers", Icon: Cpu },
    ],
  },
];

/**
 * Khung của khu quản trị nội dung.
 *
 * `useRequireSession({ canEdit: true })` chuyển hướng chứ không hiện 403: người
 * chưa từng có quyền thì không nên bị thông báo là đã bị từ chối. Máy chủ vẫn
 * chặn từng endpoint bằng `require_role`; chỗ này chỉ quyết định dựng cái gì.
 */
export function AdminShell({ children }: { children: React.ReactNode }) {
  const { status, canEdit } = useRequireSession({ canEdit: true });

  if (status !== "authenticated" || !canEdit) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-8">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="mt-6 h-64 w-full" />
      </div>
    );
  }

  return (
    <SidebarShell
      links={ADMIN_LINKS}
      showRole
      headerExtra={
        <>
          <span aria-hidden className="h-5 w-px shrink-0 bg-rule" />
          <p className="flex shrink-0 items-center gap-2 font-display text-subtitle font-semibold tracking-tight">
            Content admin
            <Tag tone="action" className="hidden sm:inline-flex">
              admin
            </Tag>
          </p>
        </>
      }
      /* Lối ra luôn hiện. Khu quản trị là ngõ cụt nếu không có đường về, và
         logo thì đi về trang giới thiệu chứ không về khu học. */
      sidebarTop={
        <Link
          href="/dashboard"
          className="inline-flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-small font-semibold text-ink-muted transition-colors hover:bg-recess hover:text-ink"
        >
          <ArrowLeft size={16} strokeWidth={1.75} aria-hidden />
          Back to learning
        </Link>
      }
      footer={
        <footer className="border-t border-rule py-6">
          <p className="px-4 text-small text-ink-faint">
            Content stays in draft until it is published. Audio is generated out of band.
          </p>
        </footer>
      }
    >
      {children}
    </SidebarShell>
  );
}
