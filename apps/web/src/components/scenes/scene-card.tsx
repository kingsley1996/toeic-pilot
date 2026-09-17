import { PanelLink, Tag } from "@/components/ui";
import type { SceneBadge, SceneDef } from "@/content/scenes";

/**
 * Chữ của `SceneBadge`. "Thử nghiệm" là tone `warn` chứ không phải trung tính:
 * nó nói cảnh này chưa qua mắt người duyệt, tức có thể còn lỗi — không phải
 * trang trí cho vui.
 */
export const SCENE_BADGES: Record<SceneBadge, { label: string; tone: "action" | "warn" }> = {
  new: { label: "Mới", tone: "action" },
  beta: { label: "Thử nghiệm", tone: "warn" },
};

/**
 * Card một cảnh 3D — dùng chung cho section "Visual Word" ở trang từ vựng và
 * hub `/learn/scenes`, để hai nơi không trôi thành hai kiểu card khác nhau.
 */
export function SceneCard({ scene }: { scene: SceneDef }) {
  return (
    <PanelLink
      key={scene.id}
      href={`/learn/scenes/${scene.id}`}
      className="group flex flex-col overflow-hidden p-0"
    >
      {/* Ảnh là ảnh CHỤP thật của cảnh (canvas 3D), không phải hình minh hoạ
          vẽ tay — vẽ tay thì nó sẽ nói dối về cách cảnh trông ra sao.
          Regenerate: SCENE_PREVIEWS=1 pnpm exec playwright test
          e2e/scene-previews.spec.ts. `<img>` thường vì đây là tệp tĩnh
          trong `public/` (cùng lý do với brand.tsx). */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/scenes/${scene.id}.png`}
        alt=""
        aria-hidden
        width={1980}
        height={892}
        className="aspect-[3/2] w-full border-b border-rule bg-recess object-cover transition-transform duration-300 group-hover:scale-105"
      />
      <div className="flex flex-1 flex-col p-3">
        <span className="flex flex-wrap items-center gap-1.5">
          <span aria-hidden className="h-1 w-8 rounded bg-action" />
          {(scene.badges ?? []).map((badge) => (
            <Tag key={badge} tone={SCENE_BADGES[badge].tone}>
              {SCENE_BADGES[badge].label}
            </Tag>
          ))}
        </span>
        <h3 className="mt-2.5 text-body font-semibold leading-snug">{scene.title}</h3>
        <p className="mt-1 line-clamp-2 text-small text-ink-muted">{scene.description}</p>
        <p className="mt-auto pt-2.5 font-data text-small tabular-nums text-ink-faint">
          {scene.objects.length} từ
        </p>
      </div>
    </PanelLink>
  );
}
