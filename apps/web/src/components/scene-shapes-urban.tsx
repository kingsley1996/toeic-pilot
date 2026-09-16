import { useMemo, type ReactNode } from "react";
import * as THREE from "three";

import { Box, PALETTE, Person, Signboard, Wheel, paint } from "@/components/scene-shapes";

/**
 * Urban intersection scene
 *
 * Coordinate convention
 * ---------------------
 *
 * World:
 *   X = world horizontal
 *   Y = height
 *   Z = world depth
 *
 * Road-local:
 *   X = along the road
 *   Z = across the road
 *   Y = height
 *
 * Every road-related object should be expressed in road-local
 * coordinates whenever possible and transformed by the ARM yaw.
 */

export const GROUND_SPAN = 36;

const PX_PER_M = 64;
const GROUND_Y = 0;
const DECAL_Y = 0.025;

const ASPHALT_EDGE = "#eef1f3";

/**
 * Two roads crossing through the origin.
 *
 * ARM 0:
 *   main avenue along world X (west <-> east),
 *   bending at the west end (từ `curve`).
 *
 * ARM 1:
 *   secondary road along world Z (south <-> north),
 *   straight.
 *
 * `yaw` follows Three.js rotationY.
 *
 * Local +X points in the direction of the road.
 * Local +Z points across the road.
 */
export const ARMS = [
  {
    yaw: 0,
    half: 3.2,
    band: 3.0,
    bend: 8,
  },
  {
    yaw: -Math.PI / 2,
    half: 2.8,
    band: 3.0,
    bend: 0,
  },
] as const;

/* -------------------------------------------------------------------------- */
/* Coordinate helpers                                                         */
/* -------------------------------------------------------------------------- */

/**
 * Convert road-local coordinates into world coordinates.
 *
 * along:
 *   distance along the road
 *
 * across:
 *   distance perpendicular to the road
 *
 * y:
 *   world height
 */
export function armPoint(
  arm: number,
  along: number,
  across = 0,
  y = GROUND_Y,
): [number, number, number] {
  const { yaw } = ARMS[arm];

  const cos = Math.cos(yaw);
  const sin = Math.sin(yaw);

  return [along * cos + across * sin, y, -along * sin + across * cos];
}

/**
 * Group using the local coordinate system of a road.
 *
 * Inside this group:
 *
 *   X = along road
 *   Z = across road
 *   Y = height
 */
function ArmGroup({ arm, children }: { arm: number; children: ReactNode }) {
  return <group rotation={[0, ARMS[arm].yaw, 0]}>{children}</group>;
}

/* -------------------------------------------------------------------------- */
/* Street texture                                                             */
/* -------------------------------------------------------------------------- */

/**
 * Creates the complete ground texture:
 *
 * - concrete plaza
 * - sidewalks
 * - asphalt
 * - road edges
 * - center lines
 *
 * This texture is intentionally kept on ONE plane.
 *
 * Crosswalks, stop lines, curbs, etc. are separate geometry sitting
 * slightly above the ground to avoid z-fighting.
 */
function useStreetPlan() {
  return useMemo(() => {
    const size = GROUND_SPAN * PX_PER_M;

    const canvas = document.createElement("canvas");

    canvas.width = size;
    canvas.height = size;

    const ctx = canvas.getContext("2d");

    if (!ctx) {
      return null;
    }

    /*
     * Base plaza.
     */
    ctx.fillStyle = "#c3cbd2";
    ctx.fillRect(0, 0, size, size);

    const center = size / 2;

    for (const arm of ARMS) {
      ctx.save();

      /**
       * Canvas transform for this road.
       *
       * We explicitly build the transform instead of using
       * ctx.rotate() so that the mapping between road-local
       * coordinates and the Three.js ground plane stays predictable.
       *
       * BẪY ĐƠN VỊ: `lineWidth`/`setLineDash` tính bằng USER UNIT (mét),
       * transform tự scale ra pixel — nhân thêm `PX_PER_M` là mọi vạch nở
       * 64 lần, phủ kín canvas, nét nào vẽ sau cùng thắng hết (hỏng im lặng:
       * vẫn ra hình, chỉ sai).
       */
      const cos = Math.cos(arm.yaw);
      const sin = Math.sin(arm.yaw);

      ctx.setTransform(
        cos * PX_PER_M,
        sin * PX_PER_M,
        sin * PX_PER_M,
        -cos * PX_PER_M,
        center,
        center,
      );

      const end = GROUND_SPAN;

      const drawRoadPath = () => {
        ctx.beginPath();

        if (arm.bend > 0) {
          /*
           * Curved entry at the south-west end.
           */
          ctx.moveTo(-end, -arm.bend);

          ctx.quadraticCurveTo(-arm.bend * 2, 0, -arm.bend, 0);

          ctx.lineTo(end, 0);
        } else {
          ctx.moveTo(-end, 0);
          ctx.lineTo(end, 0);
        }
      };

      /*
       * 1. Sidewalk band.
       */
      drawRoadPath();

      ctx.strokeStyle = PALETTE.stone;
      ctx.lineWidth = arm.half * 2 + arm.band * 2;
      ctx.lineCap = "butt";
      ctx.stroke();

      /*
       * 2. Thin white road edge.
       */
      drawRoadPath();

      ctx.strokeStyle = ASPHALT_EDGE;
      ctx.lineWidth = arm.half * 2 + 0.36;
      ctx.stroke();

      /*
       * 3. Asphalt — tối đều cả hai đường (`tire`, không phải `asphalt` xám:
       * mặt đường mà sáng hơn dải lane là cả ngã tư loang lổ).
       */
      drawRoadPath();

      ctx.strokeStyle = PALETTE.tire;
      ctx.lineWidth = arm.half * 2;
      ctx.stroke();

      /*
       * 4. Broken center line.
       *
       * Leave the actual intersection area open.
       */
      const intersectionHalf = arm.half + 1.4;

      ctx.beginPath();

      if (arm.bend > 0) {
        ctx.moveTo(-arm.bend - 3, 0);

        ctx.lineTo(-intersectionHalf, 0);
      } else {
        // Đường thẳng: nửa còn lại trước đây không có vạch giữa.
        ctx.moveTo(-end, 0);

        ctx.lineTo(-intersectionHalf, 0);
      }

      ctx.moveTo(intersectionHalf, 0);

      ctx.lineTo(end, 0);

      ctx.strokeStyle = ASPHALT_EDGE;
      ctx.lineWidth = 0.17;

      ctx.setLineDash([1.9, 1.9]);

      ctx.stroke();

      ctx.setLineDash([]);

      ctx.restore();
    }

    const texture = new THREE.CanvasTexture(canvas);

    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8;
    texture.needsUpdate = true;

    return texture;
  }, []);
}

/* -------------------------------------------------------------------------- */
/* Environment                                                                */
/* -------------------------------------------------------------------------- */

/**
 * Background environment only.
 *
 * Vocabulary objects are exposed through URBAN_SHAPES and can be
 * positioned by the scene viewer.
 */
export function UrbanEnvironment() {
  const plan = useStreetPlan();

  return (
    <group>
      {/* ------------------------------------------------------------------ */}
      {/* Ground                                                              */}
      {/* ------------------------------------------------------------------ */}

      {plan && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[GROUND_SPAN, GROUND_SPAN]} />

          <meshStandardMaterial map={plan} roughness={0.92} />
        </mesh>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Crosswalks                                                          */}
      {/* ------------------------------------------------------------------ */}

      {/* arm0 +5.5 (phía đông) KHÔNG vẽ ở đây: object `crosswalk` (có nhãn từ
          vựng) đứng đúng chỗ đó rồi, vẽ thêm là hai lớp vạch chồng nhau gây
          nháy. */}
      <Crosswalk at={[-5.5, 0, 0]} yaw={0} />

      <Crosswalk at={[0, 0, -5.5]} yaw={-Math.PI / 2} />

      <Crosswalk at={[0, 0, 5.5]} yaw={-Math.PI / 2} />

      {/* ------------------------------------------------------------------ */}
      {/* Trees                                                               */}
      {/* ------------------------------------------------------------------ */}

      {[-1, 1].map((side) => (
        <Tree key={side} at={armPoint(0, -12, side * 6.2)} />
      ))}

      {/* ------------------------------------------------------------------ */}
      {/* Street lights                                                       */}
      {/* ------------------------------------------------------------------ */}

      {/* Hàng đèn mép bắc (z = 4.9): hai chiếc bối cảnh nối với chiếc có nhãn
          `lamppost` ở (5.2, 4.9) thành một hàng thẳng bên đường. Chiếc tây đứng
          ở x = -13.5: x = -9 lọt đúng vào sàn cầu vượt (x -10.4..-7.6), cột đèn
          xuyên qua nóc cầu. */}
      <group position={[-13.5, 0, 4.9]}>
        <Lamppost />
      </group>

      <group position={[10.5, 0, 4.9]}>
        <Lamppost />
      </group>
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Basic road markings                                                       */
/* -------------------------------------------------------------------------- */

function Decal({
  size,
  at,
  color = ASPHALT_EDGE,
}: {
  size: [number, number];
  at: [number, number, number];
  color?: string;
}) {
  return (
    <mesh position={at} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={size} />

      <meshStandardMaterial color={color} roughness={0.8} />
    </mesh>
  );
}

/**
 * Pedestrian crossing (zebra đúng kiểu: thanh XUÔI theo xe, người đi BỘ cắt
 * ngang qua từng thanh, từ vỉa này sang vỉa kia).
 *
 * Local X:
 *   along the road = chiều dài mỗi thanh (= bề rộng lối qua).
 *
 * Local Z:
 *   walking direction = các thanh xếp dọc theo hướng đi, lề tới lề.
 */
export function Crosswalk({ at, yaw = 0 }: { at: [number, number, number]; yaw?: number }) {
  const barLen = 2.6;
  const barWide = 0.5;
  const barGap = 0.32;
  const barCount = 8;

  const total = (barCount - 1) * (barWide + barGap);

  return (
    <group position={at} rotation={[0, yaw, 0]}>
      {Array.from({ length: barCount }, (_, index) => {
        const z = index * (barWide + barGap) - total / 2;

        return <Decal key={index} size={[barLen, barWide]} at={[0, DECAL_Y, z]} />;
      })}
    </group>
  );
}

/**
 * Lane markings on a road-local segment: solid edge lines.
 *
 * Mặt đường texture giờ đã tối đều (`tire`) nên dải tối riêng là thừa; nét
 * đứt giữa texture cũng vẽ full đường rồi, vẽ thêm là hai nhịp chồng nhau.
 * Còn lại của object là hai vạch mép trắng (±3.0) ôm một lane.
 */
export function LaneMark() {
  return (
    <group>
      <Decal size={[9.5, 0.2]} at={[0, DECAL_Y, 3.0]} />

      <Decal size={[9.5, 0.2]} at={[0, DECAL_Y, -3.0]} />
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Intersection                                                              */
/* -------------------------------------------------------------------------- */

/**
 * Intersection node: stop lines for both roads.
 *
 * All stop lines are expressed in the corresponding road-local system.
 */
export function IntersectionNode() {
  return (
    <group>
      {ARMS.map((arm, index) => (
        <ArmGroup key={index} arm={index}>
          {[-1, 1].map((direction) => (
            <Decal
              key={direction}
              size={[0.26, arm.half * 2 - 1.4]}
              at={[direction * (arm.half + 1.1), DECAL_Y, 0]}
            />
          ))}
        </ArmGroup>
      ))}
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Sidewalk / pavement / curb                                                */
/* -------------------------------------------------------------------------- */

/**
 * Sidewalk with:
 *
 * - raised pavement
 * - paving detail
 * - tree
 * - bench
 */
export function SidewalkPad() {
  return (
    <group>
      <Box size={[6, 0.18, 3]} at={[0, 0, 0]} color={PALETTE.stone} />

      {/* Paving detail — cùng màu đá, vỉa hè một màu thống nhất. Nằm sát mặt
          (0.1) chứ không lơ lửng như trước. */}
      <Box size={[6, 0.03, 0.75]} at={[0, 0.1, 0.8]} color={PALETTE.stone} />

      <Tree at={[1.7, 0.18, -0.6]} />

      {/* Ghế quay mặt RA ĐƯỜNG: cả cụm xoay nửa vòng quanh tâm ghế — lưng ghế
          chuyển sang phía trong (nam), người ngồi nhìn ra đường (bắc). */}
      <group position={[-1.7, 0, -0.9]} rotation={[0, Math.PI, 0]}>
        {/* Bench seat */}
        <Box size={[1.4, 0.09, 0.45]} at={[0, 0.6, 0.1]} color={PALETTE.wood} />

        {/* Bench back */}
        <Box size={[1.4, 0.45, 0.1]} at={[0, 0.69, -0.1]} color={PALETTE.wood} />

        {/* Bench legs */}
        {[-0.6, 0.6].map((x) => (
          <Box key={x} size={[0.1, 0.6, 0.42]} at={[x, 0.18, 0.1]} color={PALETTE.steelDark} />
        ))}
      </group>
    </group>
  );
}

/**
 * Pavement / roadside area.
 *
 * No tree or bench here so it remains semantically distinct
 * from sidewalk.
 */
export function PavementPad() {
  return (
    <group>
      <Box size={[6, 0.18, 2.8]} at={[0, 0, 0]} color={PALETTE.stone} />

      {/* Drainage channel */}
      <Box size={[6, 0.04, 0.4]} at={[0, 0.16, 1]} color={PALETTE.steelDark} />

      {/* Paving blocks */}
      {[-2.1, -1.4, -0.7, 0, 0.7, 1.4, 2.1].map((x) => (
        <Box key={x} size={[0.45, 0.05, 0.3]} at={[x, 0.19, -0.7]} color={PALETTE.concreteDark} />
      ))}

      {/* Bollards */}
      {[-2.4, -1.2, 0, 1.2, 2.4].map((x) => (
        <mesh key={x} position={[x, 0.58, 1.15]} castShadow>
          <cylinderGeometry args={[0.07, 0.1, 0.82, 8]} />

          {paint(PALETTE.steel)}
        </mesh>
      ))}
    </group>
  );
}

/**
 * Curb row.
 */
export function CurbRow() {
  return (
    <group>
      {[-2.4, -1.2, 0, 1.2, 2.4].map((x) => (
        <Box key={x} size={[1.1, 0.26, 0.45]} at={[x, 0.02, 0]} color={PALETTE.concrete} />
      ))}
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Curve                                                                      */
/* -------------------------------------------------------------------------- */

/**
 * An actual winding bend — not a wall BESIDE the road.
 *
 * The ribbon follows the EXACT quadratic the street texture paints
 * (P0/P1/P2 copied from `useStreetPlan`), so the band lands on the painted
 * bend instead of floating beside it. Same asphalt color: the seam vanishes,
 * the white edge lines do the talking.
 */
// World (x, z) — KHÔNG phải toạ độ vẽ của texture: canvas lật dọc nên vạch
// sơn cong nằm ở world +z (phía gần camera, đúng spec "foreground"). Đặt dải
// ở -z là nó thừa ra ngoài plaza (đã từng sai).
const CURVE_P0: [number, number] = [-36, 8];
const CURVE_P1: [number, number] = [-16, 0];
const CURVE_P2: [number, number] = [-8, 0];

function curvePoint(t: number): [number, number] {
  const u = 1 - t;
  return [
    u * u * CURVE_P0[0] + 2 * u * t * CURVE_P1[0] + t * t * CURVE_P2[0],
    u * u * CURVE_P0[1] + 2 * u * t * CURVE_P1[1] + t * t * CURVE_P2[1],
  ];
}

interface CurveSeg {
  at: [number, number, number];
  yaw: number;
  len: number;
}

// Children are def-local: OX/OZ must match the `curve` def position.
const CURVE_SEGS: CurveSeg[] = (() => {
  const OX = -13;
  const OZ = 5.2;
  const N = 9;
  // T0 = 0.58: đầu dải dừng ở x ≈ -16.8, không thò qua mép đất (±18).
  const T0 = 0.58;
  const T1 = 1.0;
  const segs: CurveSeg[] = [];
  for (let i = 0; i < N; i++) {
    const a = T0 + ((T1 - T0) * i) / N;
    const b = T0 + ((T1 - T0) * (i + 1)) / N;
    const [ax, ay] = curvePoint(a);
    const [bx, by] = curvePoint(b);
    const dx = bx - ax;
    const dz = by - ay;
    segs.push({
      at: [(ax + bx) / 2 - OX, 0, (ay + by) / 2 - OZ],
      yaw: Math.atan2(-dz, dx),
      len: Math.hypot(dx, dz) * 1.25,
    });
  }
  return segs;
})();

export function CurveBend() {
  return (
    <group>
      {CURVE_SEGS.map((seg, i) => (
        <group key={i} position={seg.at} rotation={[0, seg.yaw, 0]}>
          {/* Cùng màu đường (`tire`) — dải là thân vật cho hotspot, viền trắng
              texture vẽ rồi nên không vẽ chồng. */}
          <Box size={[seg.len, 0.05, 6.4]} at={[0, 0.035, 0]} color={PALETTE.tire} />
        </group>
      ))}

      {/* Single chevron facing oncoming (western) traffic, sát mép ngoài
          (ngoài mép nhựa 1 m — đứng xa hơn là thành biển lạc trên plaza). */}
      <group position={[-2.81, 0, -8.24]}>
        <Box size={[0.16, 1.4, 0.16]} at={[0, 0, 0]} color={PALETTE.steelDark} />

        <Box size={[0.1, 1.1, 1.1]} at={[0, 1.35, 0]} color={PALETTE.marking} />

        <Box size={[0.06, 0.28, 0.9]} at={[-0.07, 1.63, 0]} color={PALETTE.lampRed} />

        <Box size={[0.06, 0.28, 0.9]} at={[-0.07, 1.33, 0]} color={PALETTE.lampRed} />
      </group>
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Tree                                                                       */
/* -------------------------------------------------------------------------- */

export function Tree({ at }: { at: [number, number, number] }) {
  return (
    <group position={at}>
      {/* Trunk */}
      <mesh position={[0, 1.05, 0]} castShadow>
        <cylinderGeometry args={[0.12, 0.17, 2.1, 7]} />

        {paint(PALETTE.woodDark)}
      </mesh>

      {/* Crown */}
      <mesh position={[0, 2.45, 0]} castShadow>
        <sphereGeometry args={[0.9, 8, 6]} />

        {paint(PALETTE.leaf)}
      </mesh>
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Overpass                                                                   */
/* -------------------------------------------------------------------------- */

/**
 * Pedestrian overpass.
 *
 * The deck must CROSS the main avenue, not run along it.
 *
 * Main avenue direction:
 *   ARMS[0].yaw
 *
 * Overpass direction:
 *   ARMS[0].yaw + PI / 2
 *
 * The entire structure is built in its own local coordinates.
 */
export function Overpass() {
  const deck = 11;
  const rise = 0.78;

  return (
    <group rotation={[0, ARMS[0].yaw + Math.PI / 2, 0]}>
      {/* ------------------------------------------------------------------ */}
      {/* Main deck                                                           */}
      {/* ------------------------------------------------------------------ */}

      <Box size={[deck, 0.36, 2.8]} at={[0, 3.1, 0]} color={PALETTE.concrete} />

      {/* Deck top trim */}
      <Box size={[deck + 0.3, 0.14, 3.1]} at={[0, 3.46, 0]} color={PALETTE.wallTrim} />

      {/* ------------------------------------------------------------------ */}
      {/* Railings                                                            */}
      {/* ------------------------------------------------------------------ */}

      {[-1, 1].map((side) => (
        <Box
          key={`rail-${side}`}
          size={[deck, 1, 0.12]}
          at={[0, 3.46, side * 1.34]}
          color={PALETTE.steel}
        />
      ))}

      {/* ------------------------------------------------------------------ */}
      {/* Vertical supports                                                    */}
      {/* ------------------------------------------------------------------ */}

      {[-1, 1].map((side) => (
        <Box
          key={`support-${side}`}
          size={[0.8, 3.1, 0.8]}
          at={[side * 4, 0, 0]}
          color={PALETTE.concreteDark}
        />
      ))}

      {/* ------------------------------------------------------------------ */}
      {/* Stairs                                                              */}
      {/* ------------------------------------------------------------------ */}

      {[-1, 1].map((side) =>
        [0, 1, 2, 3].map((i) => (
          <Box
            key={`stair-${side}-${i}`}
            size={[0.7, 3.46 - i * rise, 2.8]}
            at={[side * (deck / 2 + 0.35 + i * 0.7), 0, 0]}
            color={PALETTE.concrete}
          />
        )),
      )}
    </group>
  );
}

/* Lamppost                                                                   */
/* -------------------------------------------------------------------------- */

/**
 * Double-arm street lamp.
 *
 * The lamp is symmetric around local Z, so its orientation is inherited
 * from the road group when placed beside a road.
 */
export function Lamppost() {
  return (
    <group>
      {/* Main pole */}
      <mesh position={[0, 2.2, 0]} castShadow>
        <cylinderGeometry args={[0.1, 0.17, 4.4, 8]} />

        {paint(PALETTE.steelDark)}
      </mesh>

      {/* Top cross bar */}
      <Box size={[0.14, 0.14, 3]} at={[0, 4.2, 0]} color={PALETTE.steelDark} />

      {/* Lamps */}
      {[-1, 1].map((side) => (
        <group key={side}>
          <Box size={[0.55, 0.18, 0.34]} at={[0, 4.08, side * 1.5]} color={PALETTE.steel} />

          <Box size={[0.4, 0.12, 0.2]} at={[0, 3.98, side * 1.5]} color={PALETTE.lamp} />
        </group>
      ))}

      {/* Base */}
      <Box size={[0.55, 0.14, 0.55]} at={[0, 0, 0]} color={PALETTE.steelDark} />
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Road sign                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * Round road sign.
 *
 * The face is oriented toward local +X.
 */
export function RoadSign() {
  return (
    <group>
      {/* Pole */}
      <mesh position={[0, 1.25, 0]} castShadow>
        <cylinderGeometry args={[0.07, 0.08, 2.5, 8]} />

        {paint(PALETTE.steel)}
      </mesh>

      {/* Sign face */}
      <group position={[0.06, 2.2, 0]} rotation={[0, 0, Math.PI / 2]}>
        {/* Red outer ring */}
        <mesh castShadow>
          <cylinderGeometry args={[0.64, 0.64, 0.08, 20]} />

          {paint(PALETTE.lampRed)}
        </mesh>

        {/* White inner area */}
        <mesh position={[0, 0.05, 0]}>
          <cylinderGeometry args={[0.44, 0.44, 0.05, 20]} />

          {paint(PALETTE.paper)}
        </mesh>
      </group>
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Traffic signal                                                             */
/* -------------------------------------------------------------------------- */

/**
 * Three-light traffic signal.
 *
 * Uses meshBasicMaterial for the lamps so that the lights remain
 * visually readable even when the scene lighting is weak.
 */
export function TrafficSignal() {
  const lamps = [
    [PALETTE.lampRed, 2.62],
    [PALETTE.cone, 2.16],
    [PALETTE.lampGreen, 1.7],
  ] as const;

  return (
    <group>
      {/* Pole */}
      <mesh position={[0, 1.15, 0]} castShadow>
        <cylinderGeometry args={[0.1, 0.13, 2.3, 8]} />

        {paint(PALETTE.steelDark)}
      </mesh>

      {/* Base */}
      <Box size={[0.5, 0.14, 0.5]} at={[0, 0, 0]} color={PALETTE.steelDark} />

      {/* Signal housing */}
      <Box size={[0.66, 1.8, 0.38]} at={[0, 1.5, 0]} color={PALETTE.tire} />

      {lamps.map(([color, y]) => (
        <group key={y}>
          {/* Light */}
          <mesh position={[0.2, y, 0]} rotation={[0, 0, -Math.PI / 2]}>
            <cylinderGeometry args={[0.2, 0.2, 0.06, 14]} />

            <meshBasicMaterial color={color} />
          </mesh>

          {/* Housing visor */}
          <Box size={[0.3, 0.07, 0.46]} at={[0.24, y + 0.17, 0]} color={PALETTE.tire} />
        </group>
      ))}
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Billboard                                                                  */
/* -------------------------------------------------------------------------- */

/**
 * Reuse the existing warehouse Signboard.
 */
function Billboard() {
  return (
    <group scale={0.72}>
      <Signboard at={[0, 0, 0]} />
    </group>
  );
}

/* -------------------------------------------------------------------------- */
/* Urban vocabulary shapes                                                    */
/* -------------------------------------------------------------------------- */

/**
 * Semantic vocabulary object registry.
 *
 * These names are consumed by scene-viewer.
 *
 * The environment itself is responsible for static context.
 * These shapes are the objects that can be selected / labeled
 * as vocabulary targets.
 */
export const URBAN_SHAPES = {
  overpass: Overpass,

  intersection: IntersectionNode,

  crosswalk: () => <Crosswalk at={[0, 0, 0]} />,

  sidewalk: SidewalkPad,

  pavement: PavementPad,

  curb: CurbRow,

  curve: CurveBend,

  lane: LaneMark,

  billboard: Billboard,

  signal: TrafficSignal,

  "road-sign": RoadSign,

  lamppost: () => (
    <group>
      <Lamppost />
    </group>
  ),

  pedestrian: () => <Person coat={PALETTE.wallTrim} hat={PALETTE.tire} />,
};

/* -------------------------------------------------------------------------- */
/* Background car                                                             */
/* -------------------------------------------------------------------------- */

/**
 * Simple background car.
 *
 * `car` is intentionally NOT included in URBAN_SHAPES because it is
 * environmental decoration rather than one of the target vocabulary
 * labels.
 */
export function Car() {
  return (
    <group>
      {/* Lower body */}
      <Box size={[2.2, 0.52, 1.15]} at={[0, 0.3, 0]} color={PALETTE.doorOrange} />

      {/* Cabin */}
      <Box size={[1.05, 0.44, 1.05]} at={[-0.15, 0.82, 0]} color={PALETTE.glass} />

      {/* Lower dark trim */}
      <Box size={[2.3, 0.12, 1.2]} at={[0, 0.24, 0]} color={PALETTE.steelDark} />

      {/* Head / tail light */}
      <Box size={[0.34, 0.16, 0.9]} at={[1.1, 0.6, 0]} color={PALETTE.paper} />

      {/* Wheels */}
      {[-0.68, 0.68].flatMap((x) =>
        [0.58, -0.58].map((z) => <Wheel key={`${x}:${z}`} at={[x, 0.3, z]} r={0.3} />),
      )}
    </group>
  );
}
