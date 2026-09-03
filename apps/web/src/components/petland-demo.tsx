"use client";

/**
 * Góc thú cưng, chạy thật trên trang giới thiệu.
 *
 * Diễn đúng hai việc người học thật sự làm ở đó: con thú đi lang thang, **gặp
 * NPC và làm bài để lấy ruby** (ADR-012), rồi được cho ăn và ba chỉ số dâng lên
 * (ADR-013).
 *
 * **Không dùng Remotion, và đó là lần sửa thứ ba của cùng một lỗi.** Cảnh này
 * từng chạy qua `<Player>` ở 30 rồi 60 khung/giây, và cả hai lần vẫn giật. Lý do
 * nằm ở mô hình: Player dựng lại CẢ CÂY React mỗi khung — ở đây là bản đồ, hai
 * con thú, thẻ nhiệm vụ và cả `PetHud` với bốn cái nút — chỉ để dịch một phần tử
 * đi vài pixel. Petland thật thì không làm thế: Pixi ghi thẳng toạ độ vào sprite
 * trong vòng `requestAnimationFrame`, không có render nào của React ở giữa.
 *
 * Nên ở đây cũng vậy. Một vòng `requestAnimationFrame` ghi `transform` THẲNG vào
 * DOM qua ref, không đi qua state. React chỉ được đánh thức khoảng tám lần mỗi
 * giây, cho những thứ đổi chậm: chú thích, thẻ nhiệm vụ, ba thanh chỉ số. Chuyển
 * động mượt ở nhịp màn hình, còn giao diện thì rẻ.
 *
 * **Dùng lại chính mã của trò chơi.** `wanderStep` chọn ô kế tiếp, `conditionOf`
 * đọc tình trạng từ ba chỉ số, và bảng dưới đáy là `PetHud` thật — nên nút "Đi
 * dạo" tự mờ đi lúc con thú đói mà không dòng nào ở đây nói tới chuyện đó. Ba
 * tệp ấy đều bị `check-petland-layers.mjs` cấm nhập `pixi.js`.
 *
 * **Bản đồ vẽ MỘT LẦN.** Hơn bốn trăm lượt `drawImage`; làm lại mỗi khung cho
 * một hình không đổi là cách chắc chắn nhất để đốt CPU khách ở trang đầu tiên họ
 * thấy. Vòng rAF chỉ chạy khi ô nằm trong khung nhìn, và không chạy chút nào nếu
 * người dùng xin giảm chuyển động.
 */

import { useEffect, useRef, useState } from "react";

import { isWalkable, TILE, wanderStep, type MapData, type Tile } from "@/components/petland-map";
import { conditionOf } from "@/components/petland-pet";
import { Creature, usePetlandMapCanvas } from "@/components/petland-preview";
import { PetHud } from "@/components/petland-ui";
import { PixelIcon } from "@/components/pixel-icon";
import { cx } from "@/components/ui";
import { landing } from "@/content/landing";

const T = landing.pet.scene;

const SCALE = 2;
const CELL = TILE * SCALE;
const MAP_W = 18;
const MAP_H = 13;

const RESIDENT = 169; // Mèo
const NPC_TILE = 117; // Cú
const HOME: Tile = { x: 6, y: 6 };
const NPC: Tile = { x: 12, y: 5 };

/* Mọi mốc tính bằng MILI GIÂY, không bằng khung hình: vòng rAF chạy ở nhịp màn
   hình, và một máy 120Hz không được xem cảnh này nhanh gấp đôi. */
const STEP_MS = 420; // một ô
const PAUSE_MS = 150; // đứng nghỉ giữa hai bước
const CYCLE_MS = STEP_MS + PAUSE_MS;
const WANDER_STEPS = 3; // lang thang trước khi NPC hiện ra
const QUEST_MS = 6200;
const FEED_MS = 3800;

/** PRNG có hạt giống: cùng một lượt xem cho ra cùng một đường đi. */
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Một bước tiến về phía NPC: ưu tiên trục lệch nhiều hơn, né ô không đi được. */
function stepToward(map: MapData, from: Tile, target: Tile): Tile {
  const dx = Math.sign(target.x - from.x);
  const dy = Math.sign(target.y - from.y);
  const tries: Tile[] =
    Math.abs(target.x - from.x) >= Math.abs(target.y - from.y)
      ? [
          { x: from.x + dx, y: from.y },
          { x: from.x, y: from.y + dy },
        ]
      : [
          { x: from.x, y: from.y + dy },
          { x: from.x + dx, y: from.y },
        ];
  return tries.find((next) => isWalkable(map, next.x, next.y)) ?? from;
}

const adjacent = (a: Tile, b: Tile) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y) <= 1;

/**
 * Đường đi: lang thang quanh nhà, rồi tiến thẳng tới NPC.
 *
 * Dừng ngay khi đứng cạnh NPC — thẻ nhiệm vụ mở lúc CHẠM MẶT, không theo đồng
 * hồ, vì NPC chỉ mở nhiệm vụ khi người học đang ở đó (ADR-012 §1).
 */
function buildPath(map: MapData): Tile[] {
  const rand = mulberry32(20260904);
  const path: Tile[] = [HOME];
  for (let step = 0; step < WANDER_STEPS; step += 1) {
    const here = path[path.length - 1];
    path.push(wanderStep(map, here, HOME, 3, rand) ?? here);
  }
  for (let guard = 0; guard < 24; guard += 1) {
    const here = path[path.length - 1];
    if (adjacent(here, NPC)) break;
    const next = stepToward(map, here, NPC);
    if (next === here) break;
    path.push(next);
  }
  return path;
}

type Phase = "walk" | "quest" | "feed";

export function PetlandDemo() {
  const { canvas, map } = usePetlandMapCanvas();
  const pet = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<Phase>("walk");
  /** 0 → 1 trong nhịp nhiệm vụ và nhịp cho ăn, để React vẽ phần đổi chậm. */
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (map === null) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const path = buildPath(map);
    const walkMs = (path.length - 1) * CYCLE_MS;
    const loopMs = walkMs + QUEST_MS + FEED_MS;

    let raf = 0;
    let started = 0;
    let lastPhase: Phase = "walk";
    let lastTick = -1;

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      /* `started = 0` là dấu "vừa được bật lại": mốc thời gian đặt lại ở khung
         kế tiếp, nên cuộn ra rồi cuộn về sẽ xem lại TỪ ĐẦU thay vì rơi vào giữa
         vòng — cùng tính chất mà `MockPlayer` có được nhờ gắn/tháo hẳn player. */
      if (started === 0) started = now;
      const at = (now - started) % loopMs;

      /* Vị trí: ghi THẲNG vào DOM. Đây là toàn bộ lý do cảnh này không đi qua
         Remotion — không có render nào của React trên đường đi này. */
      const walking = at < walkMs;
      const step = walking ? Math.floor(at / CYCLE_MS) : path.length - 2;
      const local = walking ? at % CYCLE_MS : CYCLE_MS;
      const from = path[Math.max(0, Math.min(step, path.length - 1))];
      const to = path[Math.max(0, Math.min(step + 1, path.length - 1))];
      const t = Math.min(1, local / STEP_MS);
      const x = from.x + (to.x - from.x) * t;
      const y = from.y + (to.y - from.y) * t;
      const hop = t > 0 && t < 1 ? Math.abs(Math.sin(t * Math.PI)) * 1.5 * SCALE : 0;
      const facing = to.x < from.x ? -1 : 1;
      const breathe = 1 + Math.sin(now / 700) * 0.03;
      const node = pet.current;
      if (node !== null) {
        node.style.transform = `translate3d(${x * CELL}px, ${y * CELL - hop}px, 0) scaleX(${facing}) scaleY(${breathe})`;
      }

      /* Phần đổi chậm: đánh thức React khoảng tám lần mỗi giây, không hơn. */
      const next: Phase = walking ? "walk" : at < walkMs + QUEST_MS ? "quest" : "feed";
      const span = next === "quest" ? QUEST_MS : FEED_MS;
      const done = next === "walk" ? 0 : (at - walkMs - (next === "feed" ? QUEST_MS : 0)) / span;
      const tick = Math.floor(done * 50);
      if (next !== lastPhase || tick !== lastTick) {
        lastPhase = next;
        lastTick = tick;
        setPhase(next);
        setProgress(done);
      }
    };

    /* Chỉ chạy khi ô NẰM TRONG khung nhìn. Một vòng rAF quay đều cho thứ không
       ai nhìn là pin và CPU đổ đi, và trên máy yếu nó làm chính lượt cuộn giật —
       cùng lý do `MockPlayer` gắn/tháo player theo `IntersectionObserver`. */
    const io = new IntersectionObserver(
      ([entry]) => {
        const visible = entry?.isIntersecting ?? false;
        if (visible && raf === 0) {
          started = 0;
          raf = requestAnimationFrame(frame);
        } else if (!visible && raf !== 0) {
          cancelAnimationFrame(raf);
          raf = 0;
        }
      },
      { threshold: 0.3 },
    );
    const node = box.current;
    if (node !== null) io.observe(node);

    return () => {
      io.disconnect();
      if (raf !== 0) cancelAnimationFrame(raf);
    };
  }, [map]);

  /* Ba chỉ số: đói cho tới lúc được cho ăn, rồi dâng lên. `conditionOf` là hàm
     thật của trò chơi, nên chữ "Đang đói" và cái nút "Đi dạo" bị mờ đều tự đến. */
  const fed = phase === "feed" ? Math.min(1, progress * 2.2) : 0;
  const needs = {
    fullness: 0.14 + 0.78 * fed,
    energy: 0.72,
    mood: 0.52 + 0.3 * fed,
  };
  const condition = conditionOf(needs);

  const typed =
    phase === "quest" ? Math.floor(Math.max(0, progress - 0.2) * 2.6 * T.questAnswer.length) : 0;
  const solved = phase === "quest" && progress > 0.66;
  const rewarded = phase === "quest" && progress > 0.74;
  const caption = phase === "walk" ? T.encounter : phase === "quest" ? null : T.feeding;

  return (
    <div style={{ background: "rgb(var(--panel))" }}>
      {/* `overflow: hidden` là chốt: mọi thứ đè lên bản đồ đều tính theo ô, và
          một ô ngoài lưới phải bị cắt ở mép bản đồ chứ không tràn ra vỏ máy. */}
      <div
        ref={box}
        style={{
          position: "relative",
          width: MAP_W * CELL,
          height: MAP_H * CELL,
          maxWidth: "100%",
          overflow: "hidden",
        }}
      >
        <canvas
          ref={canvas}
          style={{ width: "100%", height: "100%", imageRendering: "pixelated", display: "block" }}
          role="img"
          aria-label="Bản đồ Petland: khu nhà, bãi cỏ và con suối mà con thú đi lại trên đó"
        />

        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            transform: `translate3d(${NPC.x * CELL}px, ${NPC.y * CELL}px, 0)`,
          }}
        >
          <Creature tile={NPC_TILE} size={CELL} />
        </div>

        {phase === "walk" && (
          <div
            aria-hidden
            className="grid place-items-center rounded"
            style={{
              position: "absolute",
              left: NPC.x * CELL + CELL * 0.3,
              top: NPC.y * CELL - CELL * 0.85,
              width: 16,
              height: 20,
              background: "#ffd447",
              color: "#1b1e26",
              font: "800 13px/1 ui-sans-serif, system-ui, sans-serif",
            }}
          >
            !
          </div>
        )}

        {/* Con thú: `transform` do vòng rAF ghi vào, React không đụng tới. */}
        <div
          ref={pet}
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            transform: `translate3d(${HOME.x * CELL}px, ${HOME.y * CELL}px, 0)`,
            transformOrigin: "bottom center",
            willChange: "transform",
          }}
        >
          <Creature tile={RESIDENT} size={CELL} />
        </div>

        {phase === "feed" &&
          [0, 1, 2].map((i) => {
            const age = Math.min(1, Math.max(0, progress * 3 - i * 0.22));
            if (age <= 0 || age >= 1) return null;
            return (
              <span
                key={i}
                aria-hidden
                style={{
                  position: "absolute",
                  left: NPC.x * CELL - CELL + (i - 1) * 12,
                  top: NPC.y * CELL - age * 34,
                  opacity: 1 - age,
                }}
              >
                <PixelIcon name={i === 1 ? "heart" : "bone"} scale={2} />
              </span>
            );
          })}

        {/* Thẻ nhiệm vụ, dựng theo `petland-quest.tsx`: tên con vật + đồng hồ
            đếm ngược, đề bài, ô gõ, nút Trả lời. Bài tập nằm NGAY TRONG thẻ —
            một cú chuyển trang cho xung động hai mươi giây thì xung động ấy
            chết giữa đường (ADR-012 §3). */}
        {phase === "quest" && (
          <div
            className="rounded border border-rule-strong bg-panel p-3"
            style={{ position: "absolute", left: 10, top: 10, width: 208 }}
          >
            <span className="text-small font-semibold text-warn">
              {T.questName}
              <span className="ml-2 font-data font-normal tabular-nums text-ink-muted">
                {T.questTimer}
              </span>
            </span>
            <p className="mt-1 text-small text-ink-muted">{T.questLead}</p>

            <div className="mt-2 rounded border border-rule-strong p-2">
              <p className="text-body text-ink">{T.questPrompt}</p>
              <p className="font-data text-label text-ink-faint">{T.questPos}</p>
              <div className="mt-2 w-full rounded border border-rule-strong px-2 py-1 text-small">
                {typed === 0 ? (
                  <span className="text-ink-faint">{T.questPlaceholder}</span>
                ) : (
                  <span className="text-ink">{T.questAnswer.slice(0, typed)}</span>
                )}
              </div>
              {/* `flex-wrap` chứ không phải một hàng cứng: nhãn nút dài ra khi
                  chấm xong ("Trả lời" → "✓ Chính xác") và phần thưởng hiện
                  thêm bên cạnh, nên hai thẻ ép nhau tràn khỏi thẻ. Cho phần
                  thưởng rơi xuống dòng dưới thì không bao giờ vỡ. */}
              <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1.5">
                <span
                  className={cx(
                    "inline-flex h-7 shrink-0 items-center whitespace-nowrap rounded border px-2 text-small font-semibold",
                    solved ? "border-ok bg-ok-tint text-ok" : "border-rule-strong text-ink-muted",
                  )}
                >
                  {solved ? `✓ ${T.questCorrect}` : T.questSubmit}
                </span>
                {rewarded && (
                  <span className="font-data text-small font-semibold tabular-nums text-warn">
                    {T.questReward}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {caption !== null && (
          <div
            className="rounded"
            style={{
              position: "absolute",
              left: 10,
              bottom: 10,
              padding: "5px 9px",
              background: "rgb(17 20 26 / 0.86)",
              color: "#fff",
              font: "600 12px/1.2 ui-sans-serif, system-ui, sans-serif",
            }}
          >
            {caption}
          </div>
        )}
      </div>

      {/* Bảng chỉ số THẬT, không phải bản vẽ lại: tám ô mỗi thanh, màu cảnh báo
          và từ tình trạng đều do mã đang chạy trong sản phẩm quyết định. */}
      <div className="border-t border-rule">
        <PetHud
          needs={needs}
          condition={condition}
          asleep={false}
          busy={phase === "feed" && progress < 0.2}
          onAction={() => {}}
        />
      </div>
    </div>
  );
}
