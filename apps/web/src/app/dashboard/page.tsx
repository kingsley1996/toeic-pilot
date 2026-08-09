"use client";

import { API_ROUTES, type ReviewSession } from "@toeic-pilot/shared";
import { BookOpen, Headphones, RotateCcw, SquarePen } from "lucide-react";
import { useEffect, useState } from "react";

import { ButtonLink, Page, PageHeader, Panel, PanelLink, Skeleton, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

export default function DashboardPage() {
  const { status, user, token, canEdit } = useRequireSession();
  const [due, setDue] = useState<{ due: number; fresh: number } | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<ReviewSession>(API_ROUTES.reviewSession, { token })
      .then((session) => setDue({ due: session.due_count, fresh: session.new_count }))
      // Một bộ đếm hỏng không được kéo cả trang xuống theo: phần còn lại vẫn
      // dùng được, nên nó xuống cấp thành "không có số" chứ không thành màn lỗi.
      .catch(() => setDue({ due: 0, fresh: 0 }));
  }, [token]);

  if (status !== "authenticated" || !user) {
    return (
      <Page>
        <Skeleton className="h-9 w-64" />
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      </Page>
    );
  }

  const total = due ? due.due + due.fresh : null;

  return (
    <Page>
      <PageHeader
        eyebrow="Bảng điều khiển"
        title={`Chào ${user.email.split("@")[0]}`}
        description="Bắt đầu bằng phiên ôn tập hôm nay, hoặc luyện nghe chép chính tả."
        actions={<Tag tone={canEdit ? "action" : "neutral"}>{user.role}</Tag>}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        {/* Mặt đọc: con số là thứ đầu tiên mắt chạm vào, và nó dùng font data
            với chữ số thẳng cột nên không nhảy khi cập nhật. */}
        <Panel className="flex flex-col justify-between p-5">
          <div>
            <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-ink-faint">
              <RotateCcw size={12} strokeWidth={2} aria-hidden />
              Cần ôn hôm nay
            </p>
            {total === null ? (
              <Skeleton className="mt-2 h-12 w-24" />
            ) : (
              <p className="mt-1.5 font-data text-readout leading-none text-ink">{total}</p>
            )}
            {due && (
              <p className="mt-3 font-data text-small text-ink-muted">
                {due.due} đến hạn · {due.fresh} từ mới
              </p>
            )}
          </div>
          <ButtonLink href="/learn/review" className="mt-5 w-fit">
            Bắt đầu ôn
          </ButtonLink>
        </Panel>

        <Panel className="flex flex-col justify-between p-5">
          <div>
            <p className="flex items-center gap-1.5 text-label font-semibold uppercase text-ink-faint">
              <Headphones size={12} strokeWidth={2} aria-hidden />
              Luyện nghe
            </p>
            <p className="mt-2 text-ink">Nghe một câu, gõ lại, và xem chính xác từ nào bị sót.</p>
          </div>
          <ButtonLink href="/learn/dictation" variant="secondary" className="mt-5 w-fit">
            Vào dictation
          </ButtonLink>
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <PanelLink href="/learn">
          <BookOpen size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
          <h2 className="mt-3 text-subtitle">Learning Hub</h2>
          <p className="mt-1 text-small text-ink-muted">Duyệt từ vựng theo chủ đề.</p>
        </PanelLink>

        {/* Chỉ dựng cho editor và admin. Học viên không được chỉ vào một cánh
            cửa họ không mở được — đó là khác biệt giữa một lời từ chối và một
            giao diện vừa vặn với người đang dùng nó. */}
        {canEdit && (
          <PanelLink href="/admin">
            <SquarePen size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Quản lý nội dung</h2>
            <p className="mt-1 text-small text-ink-muted">Nhập từ vựng, câu nghe, và xuất bản.</p>
          </PanelLink>
        )}
      </div>
    </Page>
  );
}
