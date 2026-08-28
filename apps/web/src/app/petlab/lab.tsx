"use client";

import { useEffect, useRef } from "react";

import {
  findPath,
  nearestWalkable,
  parseMap,
  type MapData,
  type Tile,
} from "@/components/petland-map";
import { STEP_SECONDS } from "@/components/petland-pet";
import { createStage, type Stage } from "@/components/petland-render";

export default function Lab() {
  const host = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let stage: Stage | null = null;
    let raf = 0;
    let alive = true;

    let map: MapData | null = null;
    let tile: Tile = { x: 0, y: 0 };
    let from: Tile = tile;
    let progress = 0;
    let facing: "left" | "right" = "right";
    let queue: Tile[] = [];
    let last = performance.now();

    const onClick = (event: MouseEvent) => {
      if (!stage || !map) return;
      const target = stage.tileAt(event.clientX, event.clientY);
      if (target) queue = findPath(map, tile, target);
    };

    void fetch("/pet/map.json")
      .then((res) => res.json())
      .then((raw) => {
        const parsed = parseMap(raw);
        if (!parsed || !alive) return null;
        map = parsed;
        tile = nearestWalkable(parsed, { x: 3, y: 8 });
        from = tile;
        return createStage(el, parsed, { zoom: 2, viewW: 14, viewH: 8 });
      })
      .then((made) => {
        if (!made) return;
        if (!alive) {
          made.destroy();
          return;
        }
        stage = made;
        el.addEventListener("click", onClick);

        const loop = (now: number) => {
          const dt = Math.min(0.1, (now - last) / 1000);
          last = now;
          if (queue.length > 0) {
            progress += dt / STEP_SECONDS;
            while (progress >= 1 && queue.length > 0) {
              progress -= 1;
              from = tile;
              const next = queue.shift() as Tile;
              facing = next.x < tile.x ? "left" : next.x > tile.x ? "right" : facing;
              tile = next;
            }
            if (queue.length === 0) progress = 0;
          }
          made.draw({
            tile,
            from,
            progress: queue.length ? progress : 0,
            facing,
            species: 169,
            clock: now / 1000,
            // Bàn thử không có nút hành động nào, nên không có tư thế nào để
            // diễn. `null` là "đứng bình thường", không phải "chưa biết".
            action: null,
            sleeping: false,
            encounters: [],
            fight: null,
            reduced: false,
            // Không có hạng nào ở đây: bàn thử vẽ một con cố định để soi bước
            // chân, không để soi độ hiếm.
            glow: { color: 0x9aaab5, strength: 0 },
            // Bàn thử luôn giữa trưa: nó tồn tại để soi bước chân, và một bầu
            // trời đang tối dần làm mọi lần so sánh khác nhau một chút.
            sky: { color: 0xffffff, alpha: 0 },
          });
          raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);
      })
      .catch(() => {});

    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      el.removeEventListener("click", onClick);
      stage?.destroy();
    };
  }, []);

  return <div ref={host} className="inline-block rounded border border-rule-strong" />;
}
