import { constructionScene } from "@/content/scenes/construction";
import type { SceneDef } from "@/content/scenes/types";
import { urbanScene } from "@/content/scenes/urban";
import { warehouseScene } from "@/content/scenes/warehouse";

export type {
  SceneBadge,
  SceneDef,
  SceneObjectDef,
  ShapeKey,
  Patrol,
} from "@/content/scenes/types";

export const SCENES: SceneDef[] = [warehouseScene, urbanScene, constructionScene];

export function getScene(id: string): SceneDef | undefined {
  return SCENES.find((scene) => scene.id === id);
}
