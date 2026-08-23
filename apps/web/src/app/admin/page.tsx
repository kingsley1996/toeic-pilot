"use client";

import { API_ROUTES, type TopicAdmin } from "@toeic-pilot/shared";
import {
  ClipboardList,
  FolderTree,
  Gauge,
  Headphones,
  Library,
  ListTree,
  Palette,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";

import { BackfillHint } from "@/components/admin-bits";
import { Page, PageHeader, PanelLink, SectionHeader, Tag } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import { useRequireSession } from "@/lib/session";

/**
 * Trang tổng quan của khu quản trị: chỉ là ngã ba đường.
 *
 * Nó từng vừa là ngã ba đường vừa là nơi tạo, sửa và xoá CHỦ ĐỀ từ vựng — tức
 * là tầng thứ ba của cây từ vựng nằm ở đây, còn hai tầng trên nằm ở
 * `/admin/vocabulary/tree`. Cây bị chẻ làm đôi qua hai màn hình, và ở màn này
 * chủ đề hiện ra như một danh sách phẳng không nói được nó thuộc cuốn sách nào.
 * Toàn bộ vòng đời của chủ đề đã chuyển về cây; ở đây chỉ còn đường đi.
 */
export default function AdminPage() {
  const { status, token } = useRequireSession({ canEdit: true });
  const [unfiled, setUnfiled] = useState<number | null>(null);

  useEffect(() => {
    if (!token) return;
    void apiFetch<TopicAdmin[]>(API_ROUTES.adminTopics, { token })
      .then((topics) => setUnfiled(topics.filter((t) => t.collection_item_id === null).length))
      .catch(() => {});
  }, [token]);

  if (status !== "authenticated") return <Page />;

  return (
    <Page>
      <PageHeader title="Tổng quan" description="Nhập hàng loạt, xem lại, rồi xuất bản." />

      <section>
        <SectionHeader title="Nội dung" />
        <div className="grid gap-4 sm:grid-cols-2">
          <PanelLink href="/admin/vocabulary">
            <Library size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Từ vựng</h2>
            <p className="mt-1 text-small text-ink-muted">
              Mỗi từ cần bốn giọng cho headword, và bốn giọng nữa nếu có câu ví dụ.
            </p>
          </PanelLink>
          <PanelLink href="/admin/dictation">
            <Headphones size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Câu nghe</h2>
            <p className="mt-1 text-small text-ink-muted">
              Transcript vừa là nguồn sinh audio vừa là đáp án chấm bài.
            </p>
          </PanelLink>
        </div>
      </section>

      {/* Ba cây cùng một hình dạng, nên chúng đứng cùng một chỗ. Trước kia hai
          trong ba nằm lẫn giữa các mục khác của menu, còn cây thứ ba thì chỉ là
          một mục bên trong trang đề thi. */}
      <section className="mt-10">
        <SectionHeader
          title="Cây nội dung"
          aside={
            unfiled !== null && unfiled > 0 ? (
              <Tag tone="warn">{unfiled} chủ đề chưa xếp</Tag>
            ) : undefined
          }
        />
        <div className="grid gap-4 sm:grid-cols-3">
          <PanelLink href="/admin/vocabulary/tree">
            <ListTree size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Cây từ vựng</h2>
            <p className="mt-1 text-small text-ink-muted">Tuyển tập → cuốn sách → chủ đề.</p>
          </PanelLink>
          <PanelLink href="/admin/dictation/tree">
            <FolderTree size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Cây bài nghe</h2>
            <p className="mt-1 text-small text-ink-muted">Chủ đề → phần → bài.</p>
          </PanelLink>
          <PanelLink href="/admin/tests">
            <ClipboardList size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Cây đề thi</h2>
            <p className="mt-1 text-small text-ink-muted">Bộ đề → đề → câu hỏi.</p>
          </PanelLink>
        </div>
      </section>

      <section className="mt-10">
        <SectionHeader title="Hệ thống" />
        <div className="grid gap-4 sm:grid-cols-3">
          <PanelLink href="/admin/appearance">
            <Palette size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Giao diện</h2>
            <p className="mt-1 text-small text-ink-muted">
              Nền sao băng, áp cho mọi người dù đã đăng nhập hay chưa.
            </p>
          </PanelLink>
          <PanelLink href="/admin/progression">
            <Gauge size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Cấp độ và huy hiệu</h2>
            <p className="mt-1 text-small text-ink-muted">
              XP, mốc cấp, nhiệm vụ hằng ngày, khung avatar — tất cả là dữ liệu.
            </p>
          </PanelLink>
          <PanelLink href="/admin/ai">
            <Sparkles size={16} strokeWidth={1.75} className="text-ink-muted" aria-hidden />
            <h2 className="mt-3 text-subtitle">Tầng AI</h2>
            <p className="mt-1 text-small text-ink-muted">
              Chi phí, độ trễ, nhà cung cấp và độ chính xác của việc gắn nhãn.
            </p>
          </PanelLink>
        </div>
      </section>

      <div className="mt-12">
        <BackfillHint />
      </div>
    </Page>
  );
}
