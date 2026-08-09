"use client";

import { API_ROUTES, type ReviewSession } from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import { Badge, ButtonLink, Card, CardLink, Page, PageHeader, Skeleton } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

export default function DashboardPage() {
  const { status, user, token, canEdit } = useRequireSession();
  const [due, setDue] = useState<{ due: number; fresh: number } | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<ReviewSession>(API_ROUTES.reviewSession, { token })
      .then((session) => setDue({ due: session.due_count, fresh: session.new_count }))
      // A failing counter must not take the page down with it; the rest of the
      // dashboard is still useful, so it degrades to "no number" rather than
      // to an error screen.
      .catch(() => setDue({ due: 0, fresh: 0 }));
  }, [token]);

  if (status !== "authenticated" || !user) {
    return (
      <Page>
        <Skeleton className="h-9 w-64" />
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
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
        actions={<Badge tone={canEdit ? "brand" : "neutral"}>{user.role}</Badge>}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="flex flex-col justify-between p-6">
          <div>
            <p className="text-sm font-medium text-text-muted">Cần ôn hôm nay</p>
            {total === null ? (
              <Skeleton className="mt-2 h-10 w-20" />
            ) : (
              <p className="mt-1 text-4xl font-bold tabular-nums">{total}</p>
            )}
            {due && (
              <p className="mt-1 text-sm text-text-muted">
                {due.due} đến hạn · {due.fresh} từ mới
              </p>
            )}
          </div>
          <ButtonLink href="/learn/review" className="mt-5 w-fit">
            Bắt đầu ôn
          </ButtonLink>
        </Card>

        <Card className="flex flex-col justify-between p-6">
          <div>
            <p className="text-sm font-medium text-text-muted">Luyện nghe</p>
            <p className="mt-1 text-sm text-text">
              Nghe một câu, gõ lại, và xem chính xác từ nào bị sót.
            </p>
          </div>
          <ButtonLink href="/learn/dictation" variant="secondary" className="mt-5 w-fit">
            Vào dictation
          </ButtonLink>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <CardLink href="/learn">
          <h2 className="font-semibold">Learning Hub</h2>
          <p className="mt-1 text-sm text-text-muted">Duyệt từ vựng theo chủ đề.</p>
        </CardLink>

        {/* Only rendered for editors and admins. A learner is not shown a door
            they cannot open — that is the difference between a refusal and an
            interface that simply fits the person using it. */}
        {canEdit && (
          <CardLink href="/admin">
            <h2 className="font-semibold">Quản lý nội dung</h2>
            <p className="mt-1 text-sm text-text-muted">Nhập từ vựng, câu nghe, và xuất bản.</p>
          </CardLink>
        )}
      </div>
    </Page>
  );
}
