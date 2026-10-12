import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SeoWordList } from "@/components/seo-word-list";
import { getScene } from "@/content/scenes";
import { getSeoWords } from "@/lib/seo-content";

/*
 * Trang cảnh là client component (canvas 3D) nên không export metadata được —
 * layout server bọc ngoài này lo title/description riêng cho từng cảnh, để
 * crawler thấy 12 trang khác nhau thay vì 12 bản sao "TOEIC Pilot".
 *
 * ISR 10 phút: khối từ vựng fetch từ API lúc render — nếu build/deploy đúng lúc
 * API free-tier đang ngủ thì bản tĩnh đầu thiếu section, 10 phút sau tự render
 * lại có đủ. Không `force-dynamic`: mỗi lượt xem trả 25 request API là phí.
 */
export const revalidate = 600;
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

export default async function SceneLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ sceneId: string }>;
}) {
  // Khối SEO SSR dưới canvas: crawler đọc được từ + nghĩa + ví dụ mà không cần
  // WebGL. API hỏng thì bỏ qua — trang tương tác phía trên không phụ thuộc nó.
  const { sceneId } = await params;
  const scene = getScene(sceneId);
  const words = scene ? await getSeoWords(scene.topicSlug) : null;
  return (
    <>
      {children}
      {scene && words ? <SeoWordList words={words} sceneTitle={scene.title} /> : null}
    </>
  );
}
