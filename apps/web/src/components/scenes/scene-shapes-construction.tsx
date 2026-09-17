import { useContext, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import {
  Box,
  Cone,
  PALETTE,
  Person,
  SceneMotionContext,
  Signboard,
  Wheel,
  paint,
} from "@/components/scenes/scene-shapes";

/**
 * Công trường xây dựng — cùng khuôn `scene-shapes-urban.tsx`: shape là group
 * gốc đất (y = 0), mũi xe +X, màu riêng trong `SITE` (không chạm `PALETTE`
 * chung vì không shape nào khác cần màu đất công trường).
 *
 * Nền vẽ bằng MỘT canvas texture (bài học urban §7.1: thêm lớp phủ song song
 * là thêm một cặp mặt z-fighting). BẪY ĐƠN VỊ: `lineWidth` tính bằng mét,
 * transform tự scale — không nhân `PX_PER_M`.
 */

export const SITE_SPAN = 36;
const PPM = 64;

const SITE = {
  dirt: "#b69a6e",
  dirtDark: "#a3865c",
  gravel: "#9aa0a4",
  pad: "#c3c9cf",
  machine: "#d99a26",
  machineDark: "#8a5f14",
  hatYellow: "#e8b820",
  vest: "#e2601a",
  rust: "#8a4a2b",
  bagGray: "#cfc9bd",
  spark: "#ffd75e",
} as const;

/** World (x, z) mét → canvas: x sang phải, z+ xuống dưới (đảo dấu như urban). */
function useSitePlan() {
  return useMemo(() => {
    const size = SITE_SPAN * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const c = size / 2;
    // yaw = 0 giống đường urban: canvasX = c + x·PPM, canvasY = c − z·PPM.
    ctx.setTransform(PPM, 0, 0, -PPM, c, c);

    ctx.fillStyle = SITE.dirt;
    ctx.fillRect(-SITE_SPAN / 2, -SITE_SPAN / 2, SITE_SPAN, SITE_SPAN);

    // Mảng đất sẫm cho đỡ phẳng (ellipse cố định — không `Math.random`: texture
    // phải giống nhau giữa hai lần load, không thì preview flake).
    ctx.fillStyle = SITE.dirtDark;
    for (const [x, z, rx, rz] of [
      [-8, 4, 5, 3],
      [7, 6, 4, 2.5],
      [-2, -11, 6, 2],
      [12, -8, 3, 3],
    ] as const) {
      ctx.beginPath();
      ctx.ellipse(x, z, rx, rz, 0.4, 0, Math.PI * 2);
      ctx.fill();
    }

    // Sân sỏi dưới chân cần cẩu.
    ctx.fillStyle = SITE.gravel;
    ctx.beginPath();
    ctx.ellipse(-10, -8, 4.5, 3.5, 0, 0, Math.PI * 2);
    ctx.fill();

    // Sân bê tông quanh móng (world x −3.6..3.6, z −7..−1): rộng hơn đế móng
    // 3D một vòng để đọc thành sân.
    ctx.fillStyle = SITE.pad;
    ctx.fillRect(-3.6, -7, 7.2, 6);

    // Vệt bánh xe dọc làn xe ủi (z = 8.5) — trang trí khớp tuyến patrol.
    ctx.strokeStyle = SITE.dirtDark;
    ctx.lineWidth = 0.35;
    for (const dz of [-0.8, 0.8]) {
      ctx.beginPath();
      ctx.moveTo(-SITE_SPAN / 2, 8.5 + dz);
      ctx.lineTo(SITE_SPAN / 2, 8.5 + dz);
      ctx.stroke();
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8;
    texture.needsUpdate = true;
    return texture;
  }, []);
}

/** Hộp nghiêng quanh Z — cần cẩu, gầu xúc không dựng được bằng `Box` thẳng. */
function TiltBox({
  size,
  at,
  rotZ,
  color,
}: {
  size: [number, number, number];
  at: [number, number, number];
  rotZ: number;
  color: string;
}) {
  return (
    <mesh position={at} rotation={[0, 0, rotZ]} castShadow receiveShadow>
      <boxGeometry args={size} />
      {paint(color)}
    </mesh>
  );
}

function Crane() {
  const animated = useContext(SceneMotionContext);
  const slewRef = useRef<THREE.Group>(null);
  const trolleyRef = useRef<THREE.Group>(null);
  const t = useRef(0);
  // Hai chuyển động đặc trưng của tower crane: cụm trên quay chậm quanh thân
  // (slew, chu kỳ 24 s) + xe con chạy dọc cần (12 s). `t` đóng băng khi tắt
  // nên resume không giật. Đọc `animated` từ context: recall, vật được chọn
  // và reduced-motion đứng yên đúng như `Mover`, shape không tự bịa cờ riêng.
  useFrame((_, dt) => {
    if (!animated) return;
    t.current += dt;
    const time = t.current;
    if (slewRef.current) slewRef.current.rotation.y = Math.sin((time * Math.PI * 2) / 24) * 0.3;
    if (trolleyRef.current)
      trolleyRef.current.position.x = 3.9 + Math.sin((time * Math.PI * 2) / 12) * 1.6;
  });
  return (
    <group>
      <Box size={[2.2, 0.6, 2.2]} color={PALETTE.concrete} />
      <Box size={[0.7, 7.5, 0.7]} at={[0, 0.6, 0]} color={SITE.machine} />
      {/* cụm quay quanh trục thân (gốc ở y = 8.1, toạ độ con trừ đúng số đó) */}
      <group ref={slewRef} position={[0, 8.1, 0]}>
        <Box size={[1.2, 1.0, 1.2]} color={PALETTE.steelDark} />
        <Box size={[0.9, 0.5, 0.9]} at={[0.1, 0.25, 0]} color={PALETTE.glass} />
        {/* tháp đỉnh + hai thanh giằng xuống cần và đối cần */}
        <Box size={[0.4, 1.4, 0.4]} at={[0, 1.0, 0]} color={SITE.machine} />
        <TiltBox
          size={[6.9, 0.08, 0.08]}
          at={[3.35, 1.5, 0]}
          rotZ={-0.2}
          color={PALETTE.steelDark}
        />
        <TiltBox
          size={[3.1, 0.08, 0.08]}
          at={[-1.45, 1.5, 0]}
          rotZ={0.2}
          color={PALETTE.steelDark}
        />
        {/* cần chính +X, đối cần −X */}
        <Box size={[7.5, 0.35, 0.5]} at={[3.0, 0.8, 0]} color={SITE.machine} />
        <Box size={[2.6, 0.35, 0.5]} at={[-1.8, 0.8, 0]} color={SITE.machine} />
        <Box size={[0.8, 1.0, 0.6]} at={[-2.9, 0.1, 0]} color={PALETTE.concreteDark} />
        {/* xe con treo cáp + dầm đang cẩu, chạy x = 2.3..5.5 dưới cần.
            `Box` lấy GỐC CHÂN (`at` là đáy): tâm cáp/móc/dầm phải trừ nửa cao
            — lần trước đổi nhầm tâm nên cả chùm lơ lửng xuyên qua cần. */}
        <group ref={trolleyRef} position={[3.9, 0.6, 0]}>
          <Box size={[0.06, 2.2, 0.06]} at={[0, -2.2, 0]} color={PALETTE.steelDark} />
          <Box size={[0.3, 0.4, 0.3]} at={[0, -2.6, 0]} color={PALETTE.steelDark} />
          <Box size={[1.6, 0.25, 0.25]} at={[0, -3.0, 0]} color={PALETTE.steel} />
        </group>
      </group>
    </group>
  );
}

/**
 * Giàn giáo tựa vào KHUNG NHÀ đang xây (hai tầng cột + sàn bê tông), không
 * phải tường gạch: thang (`ladder`) cũng tựa vào mép sàn tầng một của khung
 * này — dời khung mà không dời thang là thang chọc vào không khí.
 */
function Scaffold() {
  return (
    <group>
      {/* khung nhà: 4 cột + 2 sàn, mặt sàn trước ở local z = 0 (world −9) */}
      {[-2.4, -0.8, 0.8, 2.4].map((x) => (
        <Box key={x} size={[0.4, 4.4, 0.4]} at={[x, 0, -0.9]} color={PALETTE.concrete} />
      ))}
      {[2.1, 4.15].map((y) => (
        <Box key={y} size={[5.6, 0.25, 1.8]} at={[0, y, -0.9]} color={PALETTE.concreteDark} />
      ))}
      {/* dầm ngang nóc */}
      <Box size={[5.6, 0.3, 0.3]} at={[0, 4.4, -0.9]} color={PALETTE.steelDark} />
      {/* giàn giáo mặt trước, cách mặt sàn 0.2 m */}
      {[-2.2, -0.75, 0.75, 2.2].map((x) => (
        <Box key={x} size={[0.09, 3.4, 0.09]} at={[x, 0, 0.2]} color={PALETTE.steel} />
      ))}
      {[1.1, 2.2].map((y) => (
        <Box key={y} size={[4.6, 0.09, 0.09]} at={[0, y, 0.2]} color={PALETTE.steel} />
      ))}
      <TiltBox size={[4.9, 0.08, 0.08]} at={[0, 1.65, 0.2]} rotZ={0.45} color={PALETTE.steelDark} />
      {/* hai tầng ván đứng */}
      <Box size={[4.6, 0.08, 0.7]} at={[0, 1.15, 0.2]} color={PALETTE.wood} />
      <Box size={[4.6, 0.08, 0.7]} at={[0, 2.25, 0.2]} color={PALETTE.wood} />
    </group>
  );
}

function Bulldozer() {
  return (
    <group>
      {[0.75, -0.75].map((z) => (
        <Box key={z} size={[2.4, 0.55, 0.5]} at={[0, 0, z]} color={PALETTE.tire} />
      ))}
      <Box size={[1.9, 0.7, 1.3]} at={[-0.1, 0.55, 0]} color={SITE.machine} />
      <Box size={[0.9, 0.9, 1.0]} at={[-0.5, 1.25, 0]} color={SITE.machine} />
      <Box size={[0.7, 0.45, 1.02]} at={[-0.5, 1.5, 0]} color={PALETTE.glass} />
      <Box size={[0.95, 0.1, 1.05]} at={[-0.5, 2.2, 0]} color={SITE.machineDark} />
      {/* lưỡi ủi trước mũi +X */}
      <Box size={[0.25, 0.9, 2.4]} at={[1.45, 0.15, 0]} color={PALETTE.steelDark} />
      <Box size={[0.12, 0.8, 0.12]} at={[-0.7, 1.6, 0.3]} color={PALETTE.steelDark} />
    </group>
  );
}

function Excavator() {
  return (
    <group>
      {[0.7, -0.7].map((z) => (
        <Box key={z} size={[2.2, 0.5, 0.45]} at={[0, 0, z]} color={PALETTE.tire} />
      ))}
      <Box size={[1.5, 0.35, 1.3]} at={[-0.2, 0.5, 0]} color={SITE.machineDark} />
      <Box size={[1.2, 0.8, 1.1]} at={[-0.3, 0.85, 0]} color={SITE.machine} />
      <Box size={[0.8, 0.45, 1.12]} at={[-0.3, 1.1, 0]} color={PALETTE.glass} />
      {/* cần — gầu: tư thế đang múc, gầu chạm gần đất phía +X */}
      <TiltBox size={[2.6, 0.32, 0.32]} at={[1.57, 2.03, 0]} rotZ={0.6} color={SITE.machine} />
      <TiltBox size={[1.8, 0.24, 0.24]} at={[3.13, 2.01, 0]} rotZ={-1.0} color={SITE.machineDark} />
      <Box size={[0.55, 0.7, 0.8]} at={[3.61, 0.75, 0]} color={PALETTE.steelDark} />
    </group>
  );
}

function HardHat() {
  return (
    <group>
      <Box size={[0.9, 0.9, 0.9]} color={PALETTE.wood} />
      {/* vành + vòm mũ bảo hộ phóng to đặt trên thùng */}
      <mesh position={[0, 0.92, 0]} castShadow>
        <cylinderGeometry args={[0.45, 0.45, 0.06, 16]} />
        {paint(SITE.hatYellow)}
      </mesh>
      <mesh position={[0, 0.95, 0]} castShadow>
        <sphereGeometry args={[0.32, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2]} />
        {paint(SITE.hatYellow)}
      </mesh>
      <Box size={[0.1, 0.08, 0.3]} at={[0, 1.24, 0]} color={SITE.hatYellow} />
    </group>
  );
}

function CementBags() {
  return (
    <group>
      {/* pallet gỗ */}
      {[0.5, 0, -0.5].map((z) => (
        <Box key={z} size={[1.9, 0.09, 0.18]} at={[0, 0.02, z]} color={PALETTE.woodDark} />
      ))}
      {/* 5 bao xi măng xếp 2–2–1 */}
      {[
        [-0.45, 0.18, 0],
        [0.45, 0.18, 0],
        [-0.45, 0.4, 0],
        [0.45, 0.4, 0],
        [0, 0.62, 0],
      ].map(([x, y, z], i) => (
        <Box key={i} size={[0.85, 0.2, 0.6]} at={[x, y, z]} color={SITE.bagGray} />
      ))}
    </group>
  );
}

function ConcreteMixer() {
  return (
    <group>
      {/* chân đế + bánh */}
      {[0.55, -0.55].map((z) => (
        <Box key={z} size={[0.12, 1.0, 0.12]} at={[-0.3, 0, z]} color={PALETTE.steelDark} />
      ))}
      {[0.55, -0.55].map((z) => (
        <Wheel key={z} at={[-0.75, 0.3, z]} r={0.3} />
      ))}
      {/* thùng trộn nghiêng */}
      <mesh position={[0.1, 1.35, 0]} rotation={[0, 0, 0.6]} castShadow>
        <cylinderGeometry args={[0.55, 0.7, 1.5, 14]} />
        {paint(SITE.machine)}
      </mesh>
      <mesh position={[-0.42, 0.78, 0]} rotation={[0, 0, 0.6]} castShadow>
        <cylinderGeometry args={[0.72, 0.72, 0.12, 14]} />
        {paint(SITE.machineDark)}
      </mesh>
      {/* máng xả */}
      <TiltBox size={[1.2, 0.1, 0.3]} at={[1.15, 1.0, 0]} rotZ={-0.5} color={PALETTE.steelDark} />
    </group>
  );
}

function SteelBeams() {
  const levels = [0, 0.45, 0.9];
  return (
    <group>
      {levels.map((y, i) => (
        <group key={y}>
          {/* dầm chữ I: bụng + hai cánh */}
          <Box size={[4.2, 0.28, 0.08]} at={[0, y + 0.08, 0]} color={PALETTE.steel} />
          <Box size={[4.2, 0.07, 0.3]} at={[0, y + 0.255, 0]} color={PALETTE.steel} />
          <Box size={[4.2, 0.07, 0.3]} at={[0, y - 0.095, 0]} color={PALETTE.steel} />
          {/* kê gỗ giữa các tầng, trừ tầng trên cùng */}
          {i < levels.length - 1 &&
            [-1.4, 1.4].map((x) => (
              <Box key={x} size={[0.25, 0.1, 0.5]} at={[x, y + 0.34, 0]} color={PALETTE.woodDark} />
            ))}
        </group>
      ))}
    </group>
  );
}

function Foundation() {
  return (
    <group>
      {/* đế bê tông — khít với sân vẽ trong texture (rộng hơn một vòng) */}
      <Box size={[6, 0.35, 4.5]} color={PALETTE.concrete} />
      {/* lưới thép chờ */}
      {[-2, -0.7, 0.7, 2].flatMap((x) =>
        [-1.4, 0, 1.4].map((z) => (
          <Box key={`${x}:${z}`} size={[0.05, 0.9, 0.05]} at={[x, 0.35, z]} color={SITE.rust} />
        )),
      )}
      {/* ván khuôn một cạnh */}
      <Box size={[6.2, 0.4, 0.12]} at={[0, 0, 2.31]} color={PALETTE.wood} />
    </group>
  );
}

function Ladder() {
  return (
    // Nghiêng ÂM quanh X thì đỉnh mới đổ về local −Z: dấu dương là ngả ra
    // ngoài, chân chìa vào khung. Quay quanh gốc nên chân thang (y = 0) đứng
    // yên, đỉnh (3.2 m) lùi đúng 0.7 m. Def xoay `rotationY` để hướng ngả này
    // chĩa vào mặt khung cần tựa (mặt tây: −π/2 thành +X).
    <group rotation={[-0.22, 0, 0]}>
      {/* dựng nghiêng: chân chìa ra, đỉnh tựa vào mặt khung */}
      {[-0.25, 0.25].map((x) => (
        <Box key={x} size={[0.08, 3.2, 0.08]} at={[x, 0, 0]} color={PALETTE.steel} />
      ))}
      {[0.4, 1.0, 1.6, 2.2, 2.8].map((y) => (
        <Box key={y} size={[0.58, 0.07, 0.07]} at={[0, y, 0]} color={PALETTE.steelDark} />
      ))}
    </group>
  );
}

export function Barrier() {
  return (
    <group>
      {[-1.1, 1.1].map((x) => (
        <Box key={x} size={[0.12, 1.1, 0.12]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      {[-1.1, 1.1].map((x) => (
        <Box key={x} size={[0.5, 0.08, 0.4]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      {/* lưới chắn */}
      <Box size={[2.4, 0.55, 0.05]} at={[0, 0.35, 0]} color={PALETTE.concreteDark} />
      {/* biển sọc cam–trắng trên cùng */}
      <Box size={[2.4, 0.22, 0.08]} at={[0, 0.82, 0]} color={PALETTE.paper} />
      {[0, 2, 4].map((i) => (
        <Box key={i} size={[0.4, 0.23, 0.09]} at={[-0.8 + i * 0.4, 0.82, 0]} color={PALETTE.cone} />
      ))}
    </group>
  );
}

function WeldStation() {
  return (
    <group>
      {/* máy hàn + bàn gá + tia lửa tĩnh (không point light: một cảnh một đèn chính) */}
      <Box size={[0.8, 0.7, 0.6]} at={[-0.7, 0, 0]} color={PALETTE.wallTrim} />
      <mesh position={[-0.7, 0.5, 0.31]}>
        <cylinderGeometry args={[0.09, 0.09, 0.04, 12]} />
        {paint(PALETTE.paper)}
      </mesh>
      <Box size={[1.1, 0.45, 0.65]} at={[0.7, 0, 0]} color={PALETTE.steelDark} />
      <Box size={[0.9, 0.08, 0.12]} at={[0.7, 0.49, 0]} color={PALETTE.steel} />
      <mesh position={[0.7, 0.62, 0]}>
        <sphereGeometry args={[0.09, 10, 8]} />
        <meshBasicMaterial color={SITE.spark} />
      </mesh>
      {[
        [0.85, 0.75, 0.1],
        [0.55, 0.72, -0.08],
      ].map(([x, y, z], i) => (
        <mesh key={i} position={[x, y, z]}>
          <sphereGeometry args={[0.035, 8, 6]} />
          <meshBasicMaterial color={SITE.spark} />
        </mesh>
      ))}
    </group>
  );
}

export const CONSTRUCTION_SHAPES = {
  crane: Crane,
  scaffold: Scaffold,
  bulldozer: Bulldozer,
  excavator: Excavator,
  "hard-hat": HardHat,
  cement: CementBags,
  "concrete-mixer": ConcreteMixer,
  "steel-beam": SteelBeams,
  foundation: Foundation,
  contractor: () => <Person coat={SITE.vest} hat={SITE.hatYellow} clipboard />,
  worker: () => <Person coat={PALETTE.doorBlue} hat={SITE.hatYellow} />,
  ladder: Ladder,
  barrier: Barrier,
  weld: WeldStation,
};

/**
 * Bối cảnh công trường: đất + sân + vệt bánh (một canvas), hàng rào mượn đúng
 * shape `barrier` có nhãn, cọc tiêu mượn `Cone` của kho.
 */
export function ConstructionEnvironment({
  onBrandPick,
}: {
  onBrandPick?: (faceCenter: [number, number, number]) => void;
}) {
  const plan = useSitePlan();
  return (
    <group>
      {plan && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[SITE_SPAN, SITE_SPAN]} />
          <meshStandardMaterial map={plan} roughness={0.95} />
        </mesh>
      )}
      {/* hàng rào nam (z = 12) và tây (x = −14) — rào có nhãn đứng riêng ở
          (3.5, 10.5), trước hàng rào nam nên không trùng khít. */}
      {[-12, -9.4, -6.8, -4.2, -1.6, 1, 6.2, 8.8, 11.4].map((x) => (
        <group key={x} position={[x, 0, 12]}>
          <Barrier />
        </group>
      ))}
      {[-10, -7.4, -4.8, -2.2, 0.4, 3, 5.6, 8.2].map((z) => (
        <group key={z} position={[-14, 0, z]} rotation={[0, Math.PI / 2, 0]}>
          <Barrier />
        </group>
      ))}
      {/* biển dự án đứng SAU toàn bộ vật có nhãn (sau móng/giàn giáo, z = −14),
          mặt xoay về camera đông-nam — đúng quy ước `Signboard` của kho. */}
      <Signboard at={[0, 0, -14]} rotationY={0.4} onPick={onBrandPick} />
      <Cone at={[-6, 0, 10.5]} />
      <Cone at={[6, 0, 10.5]} />
      <Cone at={[8, 0, 1.5]} />
      <Cone at={[-7, 0, -2]} />
      {/* đống cát trang trí */}
      <mesh position={[-8, 0, 8]} castShadow receiveShadow>
        <coneGeometry args={[1.6, 1.0, 12]} />
        {paint(SITE.dirtDark)}
      </mesh>
    </group>
  );
}
