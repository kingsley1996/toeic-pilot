import { Boxes } from "lucide-react";

import { Page, PageHeader, PanelLink } from "@/components/ui";
import { SCENES } from "@/content/scenes";

/*
 * Danh sách cảnh là RSC thuần: nội dung nằm trong repo (`SPEC-VISUAL-VOCAB-3D`
 * §2.1), không có fetch nào để mà ba trạng thái. Khách xem được danh sách;
 * cửa đăng nhập nằm ở trang cảnh — cùng khuôn `frontend.md`: nơi SM-2 ghi điểm
 * mới là nơi tài khoản có nghĩa.
 */
export default function ScenesIndex() {
  return (
    <Page>
      <PageHeader
        title="Cảnh từ vựng 3D"
        description="Học từ trong một bối cảnh thật: xoay cảnh, chạm vào vật, nghe và nhớ. Điểm quay về đúng hàng đợi SM-2 quen thuộc."
      />
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {SCENES.map((scene) => (
          <PanelLink
            key={scene.id}
            href={`/learn/scenes/${scene.id}`}
            className="flex flex-col p-6"
          >
            <span
              aria-hidden
              className="flex h-10 w-10 items-center justify-center rounded border border-rule bg-recess"
            >
              <Boxes size={18} strokeWidth={1.75} className="text-ink-faint" />
            </span>
            <h2 className="mt-3 text-subtitle">{scene.title}</h2>
            <p className="mt-1 text-small text-ink-muted">{scene.description}</p>
            <p className="mt-auto pt-3 font-data text-small tabular-nums text-ink-faint">
              {scene.objects.length} từ
            </p>
          </PanelLink>
        ))}
      </div>
    </Page>
  );
}
