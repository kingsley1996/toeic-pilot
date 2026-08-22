"use client";

import {
  ArrowLeft,
  ClipboardList,
  Cpu,
  FolderTree,
  Gauge,
  Headphones,
  Library,
  Palette,
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
  { href: "/admin/vocabulary", label: "Vocabulary", Icon: Library },
  { href: "/admin/vocabulary/tree", label: "Vocabulary tree", Icon: FolderTree },
  { href: "/admin/dictation", label: "Dictation", Icon: Headphones },
  { href: "/admin/dictation/tree", label: "Content tree", Icon: FolderTree },
  { href: "/admin/tests", label: "Tests", Icon: ClipboardList },
  { href: "/admin/appearance", label: "Appearance", Icon: Palette },
  { href: "/admin/progression", label: "Progression", Icon: Gauge },
  {
    href: "/admin/ai",
    label: "AI layer",
    Icon: Sparkles,
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
      sectionLabel="Content"
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
