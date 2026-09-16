import { useMemo } from "react";
import * as THREE from "three";

import { Box, Cone, PALETTE, Person, paint } from "@/components/scene-shapes";
import { Car, Tree } from "@/components/scene-shapes-urban";

/**
 * Nhà ở ngoại ô + vườn (`planning/scenes/residential-house-garden-3d-scene-spec.md`).
 * Cùng khuôn hai cảnh trước: shape gốc đất, mũi +X, MỘT canvas nền duy nhất
 * (cỏ + lối đi + luống đất vẽ phẳng; vật 3D đè lên, không mặt song song).
 *
 * Ngôi nhà CHIA ĐÔI: thân tường + cửa sổ trơn là decor trong `ResidenceEnvironment`,
 * còn mái/ống khói/ban công… là object có nhãn đặt KHỚP toạ độ thân nhà.
 * Nhà đặt tại [-6, 0, -8], mặt trước +Z — dời nhà là dời cả cụm object.
 *
 * BẪY CAO ĐỘ (đã dính một lần ở bản đầu): object gắn TRÊN NHÀ phải mang cao độ
 * trong shape (ống khói nằm trên dốc mái, cửa chớp trên đầu hồi…), vì gốc group
 * luôn ở đất. `at` của `Box` là ĐÁY — trừ nhầm tâm là vật lơ lửng (bài học §8.1).
 */

export const RESIDENCE_SPAN = 36;
const PPM = 64;

const RES = {
  grass: "#7fae5f",
  grassDark: "#6d9c50",
  lawn: "#8cbd68",
  soil: "#7a5a3a",
  wood: "#b98a53",
  woodDark: "#8a6136",
  wallBeige: "#dcc9a3",
  roofRed: "#b0562f",
  roofDark: "#8a3f22",
  brick: "#b06a4a",
  picket: "#f2f0e8",
  petalPink: "#d96a8b",
  petalYellow: "#e8b820",
  leafDark: "#3f6b34",
  walkGray: "#c3c9cf",
} as const;

/** Gốc nhóm nhà trong world — mọi object gắn nhà tính từ điểm này. */
export const HOUSE_AT: [number, number, number] = [-6, 0, -8];

function useYardPlan() {
  return useMemo(() => {
    const size = RESIDENCE_SPAN * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const c = size / 2;
    // Cùng phép đảo như urban: canvasY = c − z·PPM.
    ctx.setTransform(PPM, 0, 0, -PPM, c, c);

    ctx.fillStyle = RES.grass;
    ctx.fillRect(-RESIDENCE_SPAN / 2, -RESIDENCE_SPAN / 2, RESIDENCE_SPAN, RESIDENCE_SPAN);

    // Mảng cỏ sẫm cho đỡ phẳng (toạ độ cố định — không random).
    ctx.fillStyle = RES.grassDark;
    for (const [x, z, rx, rz] of [
      [8, 10, 5, 2.5],
      [-12, 6, 4, 3],
      [2, -12, 6, 2],
    ] as const) {
      ctx.beginPath();
      ctx.ellipse(x, z, rx, rz, 0.3, 0, Math.PI * 2);
      ctx.fill();
    }

    // Lối đi từ cổng tới hiên (world x −4.75..−3.25, z −2.5..8) + mạch vữa.
    ctx.fillStyle = RES.walkGray;
    ctx.fillRect(-4.75, -2.5, 1.5, 10.5);
    ctx.strokeStyle = RES.grassDark;
    ctx.lineWidth = 0.08;
    for (let z = -1; z <= 8; z += 1.5) {
      ctx.beginPath();
      ctx.moveTo(-4.75, z);
      ctx.lineTo(-3.25, z);
      ctx.stroke();
    }

    // Hai luống đất vườn đông (world x 7..9.5).
    ctx.fillStyle = RES.soil;
    ctx.fillRect(7, -3.5, 2.5, 2.5);
    ctx.fillRect(7, 0, 2.5, 2.5);

    // Vệt đất dưới hố đào của cậu bé (khớp def shovel).
    ctx.fillStyle = RES.soil;
    ctx.beginPath();
    ctx.ellipse(8.5, 4.5, 1.5, 1.2, 0, 0, Math.PI * 2);
    ctx.fill();

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8;
    texture.needsUpdate = true;
    return texture;
  }, []);
}

/** Mái dốc trước/sau — hộp xoay quanh X (không dùng `TiltBox`: nó chỉ xoay Z). */
function Slope({
  size,
  at,
  rotX,
  color,
}: {
  size: [number, number, number];
  at: [number, number, number];
  rotX: number;
  color: string;
}) {
  return (
    <mesh position={at} rotation={[rotX, 0, 0]} castShadow receiveShadow>
      <boxGeometry args={size} />
      {paint(color)}
    </mesh>
  );
}

/** Tam giác đầu hồi: extrude tam giác (z, y) dày 0.3 rồi xoay mặt ra ±X. */
function GableEnd({ x, flip }: { x: number; flip?: boolean }) {
  const geo = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(-3.5, 5.5);
    s.lineTo(3.5, 5.5);
    s.lineTo(0, 7.7);
    s.closePath();
    return new THREE.ExtrudeGeometry(s, { depth: 0.3, bevelEnabled: false });
  }, []);
  // rotationY(∓π/2) đưa shape-x thành world-z, dày extrude thành world-x.
  return (
    <mesh
      geometry={geo}
      position={[x, 0, 0]}
      rotation={[0, flip ? -Math.PI / 2 : Math.PI / 2, 0]}
      castShadow
    >
      {paint(RES.wallBeige)}
    </mesh>
  );
}

function Roof() {
  return (
    <group>
      {/* hai dốc: nóc (z 0, y 7.7) → diềm (z ±4.2, y 5.5), góc atan(2.2/4.2) */}
      <Slope size={[10.4, 0.15, 4.8]} at={[0, 6.6, 2.1]} rotX={0.484} color={RES.roofRed} />
      <Slope size={[10.4, 0.15, 4.8]} at={[0, 6.6, -2.1]} rotX={-0.484} color={RES.roofRed} />
      <Box size={[10.4, 0.18, 0.5]} at={[0, 7.7, 0]} color={RES.roofDark} />
      <GableEnd x={4.8} flip />
      <GableEnd x={-4.8} />
    </group>
  );
}

function TileStack() {
  // Ngói dự trữ lợp mái: nửa ống úp chồng trên pallet.
  const pipe = (key: string, at: [number, number, number]) => (
    <mesh key={key} position={at} rotation={[0, 0, Math.PI / 2]} castShadow>
      <cylinderGeometry args={[0.18, 0.18, 0.7, 10, 1, true, 0, Math.PI]} />
      {paint(RES.roofRed)}
    </mesh>
  );
  return (
    <group>
      <Box size={[1.6, 0.12, 1.0]} at={[0, 0, 0]} color={PALETTE.woodDark} />
      {[0, 1].map((row) => [-0.5, 0, 0.5].map((x) => pipe(`${row}:${x}`, [x, 0.3 + row * 0.3, 0])))}
    </group>
  );
}

function Chimney() {
  // Chân chôn trong dốc sau (mặt dốc ở local z = −1.5 cao y ≈ 6.9).
  return (
    <group>
      <Box size={[0.8, 2.2, 0.8]} at={[0, 6.6, 0]} color={RES.brick} />
      <Box size={[1.0, 0.15, 1.0]} at={[0, 8.8, 0]} color={PALETTE.concreteDark} />
      <Box size={[0.5, 0.1, 0.5]} at={[0, 8.93, 0]} color={PALETTE.tire} />
    </group>
  );
}

function Eaves() {
  // Diềm mái mặt trước, gốc nhóm ở 1/4 tây diềm (label đứng đây, cách nhãn
  // trim 3.4 m): thân diềm trải dài che hết mặt nhà (world −12.2..0.2).
  return (
    <group>
      <Box size={[12.4, 0.25, 0.12]} at={[-6.0, 5.45, 0]} color={RES.picket} />
      <Box size={[12.4, 0.08, 0.9]} at={[-6.0, 5.32, -0.45]} color={RES.picket} />
    </group>
  );
}

function Gutter() {
  // Máng xối chữ U dọc diềm, gốc nhóm lệch đông giữa (thân trải đều hai đầu
  // che hết mặt nhà: world −11.2..−0.8).
  return (
    <group>
      <Box size={[10.4, 0.08, 0.3]} at={[-1.0, 5.15, 0]} color={PALETTE.steel} />
      <Box size={[10.4, 0.25, 0.06]} at={[-1.0, 5.25, 0.15]} color={PALETTE.steel} />
      <mesh position={[-5.9, 2.55, 0.1]} castShadow>
        <cylinderGeometry args={[0.07, 0.07, 5.1, 8]} />
        {paint(PALETTE.steelDark)}
      </mesh>
    </group>
  );
}

function Vent() {
  // Cửa chớp gác mái áp mặt đầu hồi đông (mặt tường ở local x = 4.8).
  return (
    <group>
      <Box size={[0.12, 0.9, 0.7]} at={[0.03, 6.0, 0]} color={RES.picket} />
      {[6.15, 6.35, 6.55].map((y) => (
        <Box key={y} size={[0.14, 0.08, 0.6]} at={[0.03, y, 0]} color={PALETTE.steelDark} />
      ))}
    </group>
  );
}

function Weathervane() {
  // Cột + mũi tên + đuôi cờ trên nóc (gà chỉ là 3 hộp gợi hình).
  return (
    <group>
      <Box size={[0.06, 1.0, 0.06]} at={[0, 7.7, 0]} color={PALETTE.steelDark} />
      <Box size={[0.7, 0.05, 0.05]} at={[0.1, 8.55, 0]} color={PALETTE.steelDark} />
      <Box size={[0.05, 0.25, 0.18]} at={[-0.25, 8.55, 0]} color={PALETTE.steelDark} />
      <Box size={[0.22, 0.16, 0.1]} at={[0.05, 8.78, 0]} color={PALETTE.steelDark} />
    </group>
  );
}

function Balcony() {
  // Ban công đua ra mặt trước tầng trên: sàn ở y 2.7 + lan can + cửa kính.
  return (
    <group>
      <Box size={[3, 0.2, 1.2]} at={[0, 2.7, 0]} color={PALETTE.concrete} />
      {[-1.4, -0.7, 0, 0.7, 1.4].map((x) => (
        <Box key={x} size={[0.07, 0.9, 0.07]} at={[x, 2.9, 0.55]} color={RES.picket} />
      ))}
      <Box size={[3, 0.08, 0.08]} at={[0, 3.8, 0.55]} color={RES.picket} />
      {[-1.4, 1.4].map((x) => (
        <Box key={x} size={[0.07, 0.9, 0.07]} at={[x, 2.9, -0.55]} color={RES.picket} />
      ))}
      <Box size={[0.9, 2.0, 0.12]} at={[0, 2.9, -0.44]} color={PALETTE.glass} />
    </group>
  );
}

function BayWindow() {
  // Cửa sổ lồi tầng trệt: khối đua ra + kính ba mặt + nắp.
  return (
    <group>
      <Box size={[2, 2.0, 1.1]} at={[0, 0, 0]} color={RES.wallBeige} />
      <Box size={[1.6, 1.4, 0.06]} at={[0, 0.3, 0.56]} color={PALETTE.glass} />
      <Box size={[0.06, 1.4, 0.8]} at={[-1.0, 0.3, 0.15]} color={PALETTE.glass} />
      <Box size={[0.06, 1.4, 0.8]} at={[1.0, 0.3, 0.15]} color={PALETTE.glass} />
      <Box size={[2.2, 0.15, 1.3]} at={[0, 2.0, 0]} color={RES.picket} />
    </group>
  );
}

function Deck() {
  // Sàn gỗ áp hông tây nhà: ván + bậc + lan can một phía.
  return (
    <group>
      <Box size={[3, 0.4, 4]} at={[0, 0, 0]} color={RES.wood} />
      {[-1.5, -0.5, 0.5, 1.5].map((z) => (
        <Box key={z} size={[3.02, 0.42, 0.06]} at={[0, 0, z]} color={RES.woodDark} />
      ))}
      <Box size={[1.2, 0.2, 1.0]} at={[0, 0, 2.4]} color={RES.wood} />
      {[-1.4, 1.4].map((x) => (
        <Box key={x} size={[0.08, 1.0, 0.08]} at={[x, 0.4, -1.9]} color={RES.woodDark} />
      ))}
      <Box size={[3, 0.08, 0.08]} at={[0, 1.4, -1.9]} color={RES.woodDark} />
    </group>
  );
}

function Porch() {
  // Hiên che cửa chính: 2 cột + mái nhỏ áp tường + bậc.
  return (
    <group>
      {[-1.4, 1.4].map((x) => (
        <Box key={x} size={[0.18, 3.2, 0.18]} at={[x, 0, 0]} color={RES.picket} />
      ))}
      <Box size={[3.4, 0.15, 2.2]} at={[0, 3.2, -0.8]} color={RES.roofRed} />
      <Box size={[2.2, 0.18, 1.0]} at={[0, 0, 1.2]} color={PALETTE.concrete} />
    </group>
  );
}

function Doorway() {
  // Khung + cánh cửa chính + tay nắm, áp mặt tường trước.
  return (
    <group>
      {[-0.65, 0.65].map((x) => (
        <Box key={x} size={[0.15, 2.3, 0.2]} at={[x, 0, 0]} color={RES.picket} />
      ))}
      <Box size={[1.45, 0.15, 0.2]} at={[0, 2.3, 0]} color={RES.picket} />
      <Box size={[1.15, 2.2, 0.1]} at={[0, 0, -0.02]} color={RES.woodDark} />
      <Box size={[0.8, 0.7, 0.04]} at={[0, 1.2, 0.04]} color={RES.wood} />
      <Box size={[0.8, 0.7, 0.04]} at={[0, 0.25, 0.04]} color={RES.wood} />
      <mesh position={[0.4, 1.1, 0.08]}>
        <sphereGeometry args={[0.05, 8, 6]} />
        {paint(PALETTE.steelDark)}
      </mesh>
    </group>
  );
}

function Pane() {
  // Cửa sổ chia ô kính (mullion) tầng trên, áp mặt tường trước.
  return (
    <group>
      <Box size={[1.5, 1.6, 0.1]} at={[0, 3.5, -0.1]} color={RES.picket} />
      <Box size={[1.3, 1.4, 0.12]} at={[0, 3.5, -0.1]} color={PALETTE.glass} />
      <Box size={[1.3, 0.07, 0.14]} at={[0, 3.5, -0.1]} color={RES.picket} />
      <Box size={[0.07, 1.4, 0.14]} at={[0, 3.5, -0.1]} color={RES.picket} />
    </group>
  );
}

function Trim() {
  // Viền trang trí đầu hồi tây: nẹp theo dốc mái + nẹp góc đứng.
  // Gốc nhóm ở world [-11.2, 0, -8] = local nhà [-5.2, 0, 0].
  return (
    <group>
      <mesh position={[0.55, 6.6, 2.0]} rotation={[0.484, 0, 0]}>
        <boxGeometry args={[0.14, 0.18, 4.8]} />
        {paint(RES.picket)}
      </mesh>
      <mesh position={[0.55, 6.6, -2.0]} rotation={[-0.484, 0, 0]}>
        <boxGeometry args={[0.14, 0.18, 4.8]} />
        {paint(RES.picket)}
      </mesh>
      {[-3.45, 3.45].map((z) => (
        <Box key={z} size={[0.14, 5.5, 0.14]} at={[0.65, 0, z]} color={RES.picket} />
      ))}
    </group>
  );
}

function Mailbox() {
  return (
    <group>
      <Box size={[0.12, 1.1, 0.12]} at={[0, 0, 0]} color={RES.woodDark} />
      <Box size={[0.5, 0.3, 0.3]} at={[0, 1.1, 0]} color={PALETTE.wallTrim} />
      <Box size={[0.06, 0.35, 0.06]} at={[0.2, 1.25, 0.12]} color={PALETTE.cone} />
    </group>
  );
}

function MowerUnit() {
  // Máy cắt cỏ đẩy tay, mũi +X (đi cùng người đẩy trong một `Mover`).
  return (
    <group>
      <Box size={[0.7, 0.35, 0.45]} at={[0, 0.25, 0]} color={PALETTE.cone} />
      <Box size={[0.3, 0.25, 0.3]} at={[-0.1, 0.6, 0]} color={PALETTE.steelDark} />
      <mesh position={[-0.55, 0.7, 0]} rotation={[0, 0, -0.7]}>
        <boxGeometry args={[0.08, 1.1, 0.08]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      {[
        [0.22, 0.24],
        [0.22, -0.24],
        [-0.22, 0.24],
        [-0.22, -0.24],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.14, z]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.14, 0.14, 0.08, 10]} />
          {paint(PALETTE.tire)}
        </mesh>
      ))}
    </group>
  );
}

function Weeds() {
  // Cỏ dại: chùm nón lá sẫm trên bãi (máy cắt chạy ngang qua).
  const tufts: [number, number][] = [
    [0, 0],
    [0.7, 0.3],
    [-0.6, 0.4],
    [0.3, -0.5],
    [-0.4, -0.4],
    [0.9, -0.3],
  ];
  return (
    <group>
      {tufts.map(([x, z], i) => (
        <group key={i} position={[x, 0, z]}>
          {[0, 1, 2].map((k) => (
            <mesh
              key={k}
              position={[(k - 1) * 0.09, 0.18, (((k * 7 + i * 3) % 3) - 1) * 0.05]}
              rotation={[(k - 1) * 0.15, 0, (k - 1) * 0.2]}
              castShadow
            >
              <coneGeometry args={[0.07, 0.4, 6]} />
              {paint(RES.leafDark)}
            </mesh>
          ))}
        </group>
      ))}
    </group>
  );
}

function ShovelBoy() {
  // Cậu bé đào hố: người + xẻng cắm đống đất + miệng hố tối màu.
  return (
    <group>
      <Person coat={PALETTE.doorBlue} />
      {/* cán nghiêng +0.73 quanh Z: +Y → (−sinθ, cosθ) nên đầu trên về −X
          (tay người), đầu dưới về +X (hố đào). Dấu ÂM lần trước làm ngược lại:
          cán chổng ra ngoài, lưỡi rời. Tính hai đầu bằng ma trận, không đoán. */}
      <mesh position={[0.75, 0.55, 0.15]} rotation={[0, 0, 0.73]}>
        <boxGeometry args={[0.07, 1.2, 0.07]} />
        {paint(RES.woodDark)}
      </mesh>
      {/* lưỡi ôm đầu dưới cán (1.15, 0.10), miệng hố ngay dưới lưỡi */}
      <Box size={[0.22, 0.3, 0.04]} at={[1.15, 0, 0.15]} color={PALETTE.steelDark} />
      <mesh position={[1.15, 0.02, 0.18]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.32, 14]} />
        <meshStandardMaterial color={PALETTE.tire} roughness={1} />
      </mesh>
      <mesh position={[1.6, 0, 0.3]} receiveShadow>
        <coneGeometry args={[0.55, 0.5, 10]} />
        {paint(RES.soil)}
      </mesh>
    </group>
  );
}

function Flowerpots() {
  // Cặp chậu hoa hai bên cửa: chậu + đất + thân + hoa.
  const pot = (x: number, blossom: string) => (
    <group key={x} position={[x, 0, 0]}>
      <mesh position={[0, 0.25, 0]} castShadow>
        <cylinderGeometry args={[0.28, 0.2, 0.5, 10]} />
        {paint(RES.roofRed)}
      </mesh>
      <Box size={[0.08, 0.5, 0.08]} at={[0, 0.5, 0]} color={RES.leafDark} />
      <mesh position={[0, 0.85, 0]} castShadow>
        <sphereGeometry args={[0.16, 10, 8]} />
        {paint(blossom)}
      </mesh>
      {[-0.15, 0.15].map((dx) => (
        <mesh key={dx} position={[dx, 0.68, 0]} castShadow>
          <sphereGeometry args={[0.1, 8, 6]} />
          {paint(blossom)}
        </mesh>
      ))}
    </group>
  );
  return (
    <group>
      {pot(-0.8, RES.petalPink)}
      {pot(0.8, RES.petalYellow)}
    </group>
  );
}

function Shrubs() {
  // Ba bụi cây tròn áp tường trước.
  return (
    <group>
      {[
        [-1.1, 0.45, 0],
        [0, 0.6, 0.1],
        [1.1, 0.5, 0],
      ].map(([x, r, z], i) => (
        <mesh key={i} position={[x, r * 0.9, z]} castShadow>
          <sphereGeometry args={[r, 10, 8]} />
          {paint(i === 1 ? PALETTE.leaf : RES.leafDark)}
        </mesh>
      ))}
    </group>
  );
}

function HedgeRow() {
  // Hàng rào cây được cắt phẳng + người tỉa một đầu (tĩnh).
  return (
    <group>
      {[-1.8, -0.6, 0.6, 1.8].map((z) => (
        <Box key={z} size={[0.9, 1.0, 1.1]} at={[0, 0, z]} color={PALETTE.leaf} />
      ))}
      {/* mặt cắt phẳng của bụi cây đã đủ đọc "được tỉa" — thanh ngang đè
          lên trên chỉ giống xà nhà. Kéo tỉa đặt vào tay người. */}
      <group position={[0, 0, 3.1]} rotation={[0, Math.PI / 2, 0]}>
        <Person coat={PALETTE.wallTrim} hat={PALETTE.cone} />
      </group>
      <Box size={[0.4, 0.06, 0.12]} at={[0.15, 1.0, 2.55]} color={PALETTE.steelDark} />
    </group>
  );
}

function PicketFence() {
  // Đoạn rào cọc trắng 2.4 m — rào có nhãn + bản decor mượn lại.
  return (
    <group>
      {[-1.1, 1.1].map((x) => (
        <Box key={x} size={[0.14, 1.0, 0.14]} at={[x, 0, 0]} color={RES.picket} />
      ))}
      {[0.35, 0.7].map((y) => (
        <Box key={y} size={[2.4, 0.08, 0.06]} at={[0, y, 0]} color={RES.picket} />
      ))}
      {[-1.0, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1.0].map((x) => (
        <Box key={x} size={[0.12, 0.9, 0.05]} at={[x, 0, 0]} color={RES.picket} />
      ))}
    </group>
  );
}

function Driveway() {
  // Lối xe bê tông ra cổng hông (tấm mỏng trên cỏ, đáy chìm nên không fight).
  return (
    <group>
      <Box size={[3, 0.08, 10]} at={[0, 0, 0]} color={RES.walkGray} />
      {[-2.5, 2.5].map((z) => (
        <Box key={z} size={[3.02, 0.02, 0.08]} at={[0, 0.08, z]} color={PALETTE.concreteDark} />
      ))}
    </group>
  );
}

function YardPanel() {
  // Thảm cỏ đốn (bãi máy cắt chạy): tấm + viền đá.
  return (
    <group>
      <Box size={[12, 0.06, 4.5]} at={[0, 0, 0]} color={RES.lawn} />
      {[
        [0, 2.28, 12.2, 0.24],
        [0, -2.28, 12.2, 0.24],
        [6.05, 0, 0.24, 4.8],
        [-6.05, 0, 0.24, 4.8],
      ].map(([x, z, w, d], i) => (
        <Box key={i} size={[w, 0.12, d]} at={[x, 0, z]} color={PALETTE.stone} />
      ))}
    </group>
  );
}

export const RESIDENCE_SHAPES = {
  roof: Roof,
  tile: TileStack,
  chimney: Chimney,
  eaves: Eaves,
  gutter: Gutter,
  vent: Vent,
  weathervane: Weathervane,
  balcony: Balcony,
  "bay-window": BayWindow,
  deck: Deck,
  porch: Porch,
  doorway: Doorway,
  pane: Pane,
  trim: Trim,
  mailbox: Mailbox,
  mower: () => (
    // Người đẩy sau máy (mũi +X): `Mover` xoay cả cụm theo vận tốc, chân người
    // tự quẫy nhờ `Person` đo chuyển động thế giới (không cần prop).
    <group>
      <MowerUnit />
      <group position={[-0.95, 0, 0]}>
        <Person coat={PALETTE.doorBlue} hat={PALETTE.cone} />
      </group>
    </group>
  ),
  weed: Weeds,
  shovel: ShovelBoy,
  flowerpot: Flowerpots,
  shrub: Shrubs,
  hedge: HedgeRow,
  fence: PicketFence,
  driveway: Driveway,
  yard: YardPanel,
};

/** Thân nhà trơn (decor): tường + cửa sổ không nhãn — mái/cửa/ban công là object. */
function HouseBody() {
  const [hx, , hz] = HOUSE_AT;
  return (
    <group>
      <Box size={[9, 5.5, 7]} at={[hx, 0, hz]} color={RES.wallBeige} />
      {/* dải móng sẫm chân tường */}
      <Box size={[9.1, 0.4, 7.1]} at={[hx, 0, hz]} color={PALETTE.concreteDark} />
      {/* cửa sổ trơn mặt sau (mặt trước dành cho object có nhãn) */}
      {[
        [-2, 3.6, -3.55, 1.2],
        [2, 1.4, -3.55, 1.4],
      ].map(([x, y, z, w]) => (
        <group key={`${x}:${y}`} position={[hx + x, y, hz + z]}>
          <Box size={[w, 1.3, 0.1]} at={[0, 0, 0]} color={RES.picket} />
          <Box size={[w - 0.2, 1.1, 0.12]} at={[0, 0, 0]} color={PALETTE.glass} />
        </group>
      ))}
      {/* cửa sổ tròn gác mái mặt tây (decor, vent thật ở đầu đông) */}
      <mesh position={[hx - 4.56, 6.3, hz]} rotation={[0, -Math.PI / 2, 0]}>
        <circleGeometry args={[0.35, 14]} />
        <meshStandardMaterial color={PALETTE.glass} roughness={0.4} />
      </mesh>
    </group>
  );
}

/** Nhà hàng xóm decor (không nhãn): khối + mái chóp + cửa. */
function NeighborHouse({
  at,
  yaw,
  wall,
  roof,
}: {
  at: [number, number, number];
  yaw: number;
  wall: string;
  roof: string;
}) {
  return (
    <group position={at} rotation={[0, yaw, 0]}>
      <Box size={[6, 3.6, 5]} color={wall} />
      <mesh position={[0, 4.5, 0]} rotation={[0, Math.PI / 4, 0]} castShadow>
        <coneGeometry args={[4.6, 1.8, 4]} />
        {paint(roof)}
      </mesh>
      <Box size={[1.0, 2.0, 0.12]} at={[0, 0, 2.5]} color={RES.woodDark} />
      <Box size={[1.2, 1.0, 0.12]} at={[-1.8, 1.6, 2.5]} color={PALETTE.glass} />
      <Box size={[1.2, 1.0, 0.12]} at={[1.8, 1.6, 2.5]} color={PALETTE.glass} />
    </group>
  );
}

export function ResidenceEnvironment() {
  const plan = useYardPlan();
  return (
    <group>
      {plan && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[RESIDENCE_SPAN, RESIDENCE_SPAN]} />
          <meshStandardMaterial map={plan} roughness={0.95} />
        </mesh>
      )}
      <HouseBody />
      <NeighborHouse at={[-16, 0, -2]} yaw={0.2} wall="#d8cfae" roof={RES.roofDark} />
      {/* nhà đông lùi ra x = 16: rào hông đông (x = 10.5) cần 1 m cách tường */}
      <NeighborHouse at={[16, 0, -6]} yaw={-0.15} wall="#cfd8d3" roof="#40566b" />
      <Tree at={[-8, 0, 12.5]} />
      <Tree at={[11, 0, -11]} />
      {/* xe đỗ đầu bắc lối xe — giữa lối là nhãn driveway, đỗ đè là nuốt pill */}
      <group position={[4.5, 0.08, 2.5]} rotation={[0, Math.PI / 2, 0]}>
        <Car />
      </group>
      {/* rào bọc QUANH lô đất (tây −14, đông 10.5, bắc −13, nam 8): cổng đi bộ
          ở lối đi (x −4.75..−3.25), đoạn có nhãn ở x = 0. Hông tránh nhà hàng
          xóm hai bên — rào đâm tường là xuyên tường. */}
      {[-14, -11.4, -8.8, -6.2, 4.2, 6.8, 9.4].map((x) => (
        <group key={x} position={[x, 0, 8]}>
          <PicketFence />
        </group>
      ))}
      {[-14, -11.4, -8.8, -6.2, -3.6, -1, 1.6, 4.2, 6.8, 9.4].map((x) => (
        <group key={x} position={[x, 0, -13]}>
          <PicketFence />
        </group>
      ))}
      {[-10.4, -7.8, -5.2, -2.6, 0, 2.6, 5.2].map((z) => (
        <group key={z} position={[-14, 0, z]} rotation={[0, Math.PI / 2, 0]}>
          <PicketFence />
        </group>
      ))}
      {[-10.4, -7.8, -5.2, -2.6, 0, 2.6, 5.2].map((z) => (
        <group key={z} position={[10.5, 0, z]} rotation={[0, Math.PI / 2, 0]}>
          <PicketFence />
        </group>
      ))}
      <Cone at={[-8, 0, 8.8]} />
    </group>
  );
}
