"use client";

import { Boxes } from "lucide-react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import { Suspense } from "react";

import { EmptyState, Page, PageHeader, Skeleton } from "@/components/ui";
import { getScene } from "@/content/scenes";
import { useRequireSession } from "@/lib/session";

/*
 * Canvas 3D chỉ tồn tại ở client — `ssr: false` là BẮT BUỘC, không phải tối ưu:
 * three đọc `window` ngay lần import đầu tiên, và `webgl` không có trên server.
 * Chunk `three` (~150KB gzip) vì thế nằm riêng ở route này, không vào bundle
 * của bất kỳ trang nào khác (`SPEC-VISUAL-VOCAB-3D` §6).
 */
const SceneViewer = dynamic(
  () => import("@/components/scenes/scene-viewer").then((m) => m.SceneViewer),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[52vh] w-full" />,
  },
);

export default function ScenePage() {
  const { sceneId } = useParams<{ sceneId: string }>();
  const { token } = useRequireSession();
  const scene = getScene(sceneId);

  if (!scene) {
    return (
      <Page>
        <EmptyState
          icon={Boxes}
          title="Không có cảnh này"
          description="Đường dẫn trỏ tới một cảnh không tồn tại."
        />
      </Page>
    );
  }

  if (!token) {
    return (
      <Page>
        <PageHeader title={scene.title} />
        <Skeleton className="mt-6 h-[52vh] w-full" />
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader title={scene.title} description={scene.description} />
      <div className="mt-4">
        <Suspense>
          <SceneViewer scene={scene} token={token} />
        </Suspense>
      </div>
    </Page>
  );
}
