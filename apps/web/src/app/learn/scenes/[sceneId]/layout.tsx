import type { Metadata } from "next";
import type { ReactNode } from "react";

import { getScene } from "@/content/scenes";

/*
 * Trang cảnh là client component (canvas 3D) nên không export metadata được —
 * layout server bọc ngoài này lo title/description riêng cho từng cảnh, để
 * crawler thấy 12 trang khác nhau thay vì 12 bản sao "TOEIC Pilot".
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ sceneId: string }>;
}): Promise<Metadata> {
  const { sceneId } = await params;
  const scene = getScene(sceneId);
  if (!scene) return { title: "Không có cảnh này" };
  const count = scene.objects.length;
  return {
    title: `${scene.title} — Từ Vựng TOEIC Theo Ngữ Cảnh`,
    description: `${scene.description} Học ${count} từ vựng TOEIC trong bối cảnh ${scene.title.toLowerCase()} với phát âm và ôn tập SM-2.`,
    alternates: { canonical: `/learn/scenes/${scene.id}` },
    openGraph: {
      title: `${scene.title} — Từ Vựng TOEIC Theo Ngữ Cảnh`,
      description: scene.description,
      images: [{ url: `/scenes/${scene.id}.webp`, width: 1280, height: 576 }],
    },
  };
}

export default function SceneLayout({ children }: { children: ReactNode }) {
  return children;
}
