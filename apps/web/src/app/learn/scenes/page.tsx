import { Page, PageHeader } from "@/components/ui";
import { SceneCard } from "@/components/scene-card";
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
        title="Visual Toeic Vocabulary"
        eyebrow="Từ vựng"
        description="Học từ vựng trong một bối cảnh 3D trực quan: xoay cảnh để khám phá, chạm vào đồ vật để tìm từ, nghe phát âm và ghi nhớ ngay trong ngữ cảnh. Sau đó, từ vựng tự động quay về hàng đợi SM-2 quen thuộc để ôn tập đúng lúc."
      />
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {SCENES.map((scene) => (
          <SceneCard key={scene.id} scene={scene} />
        ))}
      </div>
    </Page>
  );
}
