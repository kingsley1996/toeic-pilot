"use client";

import { API_ROUTES, type PartSessionSummary } from "@toeic-pilot/shared";
import { History } from "lucide-react";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "@/components/breadcrumbs";
import { ButtonLink, EmptyState, Page, PageHeader, PanelLink, SkeletonList } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";
import { getPartMeta } from "@/lib/parts";

/** Lịch sử phiên luyện — cùng vai với `/learn/attempts` của khu đề thi. */
export default function PartSessionsPage() {
  const { token } = useRequireSession();
  const [rows, setRows] = useState<PartSessionSummary[] | null>(null);

  useEffect(() => {
    if (!token) return;
    apiFetch<PartSessionSummary[]>(API_ROUTES.partSessions, { token })
      .then(setRows)
      .catch(() => setRows([]));
  }, [token]);

  return (
    <Page className="max-w-3xl">
      <Breadcrumbs trail={[{ href: "/learn/parts", label: "Luyện theo phần" }]} />
      <PageHeader eyebrow="Luyện theo phần" title="Phiên đã luyện" />

      {!rows && <SkeletonList rows={3} />}

      {rows?.length === 0 && (
        <EmptyState
          icon={History}
          title="Chưa có phiên nào"
          description="Vào một part và bấm Luyện ngay để bắt đầu phiên đầu tiên."
        />
      )}

      <div className="space-y-2">
        {rows?.map((r) => {
          const meta = getPartMeta(r.part);
          const date = new Date(r.created_at).toLocaleDateString("vi-VN", {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          });
          return (
            <PanelLink key={r.id} href={`/learn/parts/sessions/${r.id}`}>
              <div className="flex items-center gap-3">
                <span className="min-w-0 flex-1">
                  <span className="font-semibold">
                    Part {r.part} · {meta?.title ?? ""}
                  </span>
                  <span className="block text-small text-ink-muted">
                    {r.label_titles.join(", ") || "Tất cả"} · {date}
                  </span>
                </span>
                <span className="font-data text-small tabular-nums text-ink-muted">
                  {r.finished_at ? (
                    <>
                      đúng {r.correct}/{r.total}
                    </>
                  ) : (
                    <>
                      đang làm {r.answered}/{r.total}
                    </>
                  )}
                </span>
              </div>
            </PanelLink>
          );
        })}
      </div>

      {rows && rows.length > 0 && (
        <div className="mt-6">
          <ButtonLink variant="quiet" href="/learn/parts">
            Luyện tiếp
          </ButtonLink>
        </div>
      )}
    </Page>
  );
}
