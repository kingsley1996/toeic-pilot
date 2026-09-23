import { useMemo } from "react";
import * as THREE from "three";

import { Box, PALETTE, Person, Signboard, paint } from "@/components/scenes/scene-shapes";
import { Tree } from "@/components/scenes/scene-shapes-urban";

/**
 * Công viên (topic `park`).
 * Cùng khuôn residence: shape gốc đất, MỘT canvas nền duy nhất (cỏ + mảng cỏ
 * sẫm + vệt đất vẽ phẳng; vật 3D đè lên, không mặt song song), cây decor mượn
 * `Tree` của urban. `bench`/`lamppost`/`hedge` dùng lại shape có sẵn nên không
 * vẽ ở đây — registry cuối file chỉ chứa 20 shape mới.
 *
 * Nước là đĩa đặc opacity 0.85 (không phải kính 0.28 của office — nước phải đọc
 * ra sâu). Mọi tấm phẳng nổi trên cỏ đều là Box mỏng đáy chìm (học Driveway),
 * không dùng plane chồng plane.
 */

export const PARK_SPAN = 36;
const PPM = 64;

const PK = {
  grass: "#7fae5f",
  grassDark: "#6d9c50",
  lawnLight: "#93c56e",
  soil: "#8a6844",
  sand: "#e6d199",
  water: "#4f9db8",
  waterDeep: "#3a7d99",
  wood: "#a97c4c",
  woodDark: "#7c5a34",
  stone: "#b9bfc6",
  stoneDark: "#8d949c",
  walkGray: "#c9ced3",
  petalRed: "#d95f5f",
  petalPink: "#e08bb0",
  petalYellow: "#e8b820",
  petalWhite: "#f4f1e6",
  leafDark: "#3f6b34",
  gateGreen: "#2e6b46",
  blanketRed: "#c0392b",
  balloonBlue: "#3b7dd8",
  balloonOrange: "#e67e22",
  balloonGreen: "#2e9d5b",
  balloonPurple: "#8e5bd6",
} as const;

function useParkPlan() {
  return useMemo(() => {
    const size = PARK_SPAN * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    const c = size / 2;
    // Cùng phép đảo như urban/residence: canvasY = c − z·PPM.
    ctx.setTransform(PPM, 0, 0, -PPM, c, c);

    ctx.fillStyle = PK.grass;
    ctx.fillRect(-PARK_SPAN / 2, -PARK_SPAN / 2, PARK_SPAN, PARK_SPAN);

    // Mảng cỏ sẫm cho đỡ phẳng (toạ độ cố định — không random, §8.7).
    ctx.fillStyle = PK.grassDark;
    for (const [x, z, rx, rz] of [
      [-13, 8, 4, 2.5],
      [13, -8, 4, 3],
      [-2, -14, 6, 2],
      [6, 12, 5, 2],
    ] as const) {
      ctx.beginPath();
      ctx.ellipse(x, z, rx, rz, 0.4, 0, Math.PI * 2);
      ctx.fill();
    }

    // Vệt đất dưới hố cát (khớp def sandbox [11.5, 8.5]) và dưới thảm picnic
    // (khớp def picnic [−5, 7.5]) — vẽ phẳng, vật 3D đè lên.
    ctx.fillStyle = PK.soil;
    ctx.beginPath();
    ctx.ellipse(11.5, 8.5, 2.2, 1.8, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(-5, 7.5, 2.6, 2.0, 0, 0, Math.PI * 2);
    ctx.fill();

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8;
    texture.needsUpdate = true;
    return texture;
  }, []);
}

/** Mặt nước đặc: đĩa cylinder mỏng, vành đá torus đè lên mép. */
function WaterDisc({ r, squash = 1 }: { r: number; squash?: number }) {
  return (
    <group>
      {/* đĩa nước dẹt theo Z giống vành — thiếu scale này là mặt tròn nằm
          trong vành bầu dục, lệch mép hai đầu (đã dính ở lake) */}
      <mesh position={[0, 0.05, 0]} scale={[1, 1, squash]} receiveShadow>
        <cylinderGeometry args={[r, r, 0.1, 28]} />
        <meshStandardMaterial color={PK.water} transparent opacity={0.85} flatShading />
      </mesh>
      {/* torus sống trong mặt XY — xoay X mới nằm xuống thành vành ao */}
      <mesh
        position={[0, 0.1, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        scale={[1, squash, 1]}
        castShadow
      >
        <torusGeometry args={[r, 0.22, 8, 28]} />
        {paint(PK.stone)}
      </mesh>
    </group>
  );
}

/** Đài phun nước: bể tròn + cột + hai đĩa + tia nước cone đặc. */
function Fountain() {
  return (
    <group>
      <mesh position={[0, 0.25, 0]} receiveShadow castShadow>
        <cylinderGeometry args={[2.2, 2.4, 0.5, 20]} />
        {paint(PK.stone)}
      </mesh>
      <mesh position={[0, 0.52, 0]}>
        <cylinderGeometry args={[1.9, 1.9, 0.06, 20]} />
        <meshStandardMaterial color={PK.water} transparent opacity={0.85} flatShading />
      </mesh>
      <mesh position={[0, 1.0, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.3, 1.6, 10]} />
        {paint(PK.stoneDark)}
      </mesh>
      <mesh position={[0, 1.85, 0]} castShadow>
        <cylinderGeometry args={[0.9, 0.7, 0.18, 12]} />
        {paint(PK.stone)}
      </mesh>
      {/* cột trên CHẠM đĩa (đĩa đỉnh 1.94): đáy 1.9 lút vào đĩa */}
      <mesh position={[0, 2.35, 0]} castShadow>
        <cylinderGeometry args={[0.12, 0.16, 0.9, 8]} />
        {paint(PK.stoneDark)}
      </mesh>
      {/* tia nước: cone đặc đọc ra "đang phun" mà không cần animation */}
      <mesh position={[0, 3.3, 0]}>
        <coneGeometry args={[0.5, 1.4, 10]} />
        <meshStandardMaterial color={PK.water} transparent opacity={0.7} flatShading />
      </mesh>
    </group>
  );
}

/** Ao nhỏ phía đông — lá sen nổi +0.03 trên mặt nước (quy tắc 0.02, §10.6). */
function Pond() {
  return (
    <group>
      <WaterDisc r={2.4} squash={0.75} />
      {[
        [-0.8, 0.3, 0.35],
        [0.6, -0.5, 0.28],
        [1.1, 0.5, 0.22],
      ].map(([x, z, r], i) => (
        <mesh key={i} position={[x, 0.13, z]}>
          <cylinderGeometry args={[r, r, 0.03, 10]} />
          {paint(PK.leafDark)}
        </mesh>
      ))}
      <mesh position={[0.6, 0.25, -0.5]} castShadow>
        <sphereGeometry args={[0.12, 8, 6]} />
        {paint(PK.petalPink)}
      </mesh>
    </group>
  );
}

/**
 * Cầu vòm qua ao theo trục X: năm ván dốc dần lên đỉnh + lan can theo dốc.
 * Nhịp 6 m (x ±3) vắt qua ao bầu dục (rx 2.4) nên hai trụ đá đứng TRÊN BỜ
 * (x ±2.9), không chôn giữa nước như bản bậc thang cũ. Góc nghiêng tính sẵn:
 * ván ngoài atan(0.33/1.16) ≈ 0.28, ván trong atan(0.2/1.16) ≈ 0.17
 * (rotation.z dương đưa đầu +X lên — §8.9: viết số rồi mới đặt mesh).
 */
const BRIDGE_PLANKS: { x: number; y: number; tilt: number }[] = [
  { x: -2.32, y: 0.92, tilt: 0.28 },
  { x: -1.16, y: 1.25, tilt: 0.17 },
  { x: 0, y: 1.45, tilt: 0 },
  { x: 1.16, y: 1.25, tilt: -0.17 },
  { x: 2.32, y: 0.92, tilt: -0.28 },
];
/** Tay vịn nối đỉnh các cột lan can: [tâm x, tâm y, nghiêng, dài]. */
const BRIDGE_RAILS: [number, number, number, number][] = [
  [-1.74, 1.915, 0.28, 1.3],
  [-0.58, 2.18, 0.17, 1.25],
  [0.58, 2.18, -0.17, 1.25],
  [1.74, 1.915, -0.28, 1.3],
];

function Bridge() {
  return (
    <group>
      {/* trụ đá hai đầu trên bờ, mép ván ngoài gác lên đỉnh trụ (y 1.0) */}
      {[-2.9, 2.9].map((x) => (
        <Box key={x} size={[0.4, 1.0, 1.5]} at={[x, 0, 0]} color={PK.stoneDark} />
      ))}
      {BRIDGE_PLANKS.map((p) => (
        <mesh key={p.x} position={[p.x, p.y, 0]} rotation={[0, 0, p.tilt]} castShadow>
          <boxGeometry args={[1.35, 0.16, 1.6]} />
          {paint(PK.wood)}
        </mesh>
      ))}
      {/* cột lan can đứng trên mặt ván (đáy = mặt ván + 0.08), cao 0.75 */}
      {BRIDGE_PLANKS.map((p) =>
        [-0.7, 0.7].map((z) => (
          <Box
            key={`${p.x}${z}`}
            size={[0.1, 0.75, 0.1]}
            at={[p.x, p.y + 0.08, z]}
            color={PK.woodDark}
          />
        )),
      )}
      {[-0.7, 0.7].map((z) => (
        <group key={z}>
          {BRIDGE_RAILS.map(([x, y, tilt, len], i) => (
            <mesh key={i} position={[x, y, z]} rotation={[0, 0, tilt]} castShadow>
              <boxGeometry args={[len, 0.09, 0.09]} />
              {paint(PK.woodDark)}
            </mesh>
          ))}
        </group>
      ))}
    </group>
  );
}

/** Hồ lớn phía bắc + bến gỗ + thuyền decor (không nhãn). */
function Lake() {
  return (
    <group>
      <WaterDisc r={4.2} squash={0.6} />
      {/* bến gỗ chìa ra từ mép nam */}
      <Box size={[1.4, 0.15, 2.6]} at={[0, 0.15, 2.6]} color={PK.wood} />
      {[-0.6, 0.6].map((x) => (
        <Box key={x} size={[0.18, 0.5, 0.18]} at={[x, 0, 3.4]} color={PK.woodDark} />
      ))}
      {/* thuyền: đáy + hai thành + ghế */}
      <group position={[-1.6, 0, 0.6]} rotation={[0, 0.5, 0]}>
        <Box size={[1.6, 0.3, 0.7]} at={[0, 0.1, 0]} color={PK.woodDark} />
        <Box size={[1.6, 0.35, 0.1]} at={[0, 0.35, 0.3]} color={PK.wood} />
        <Box size={[1.6, 0.35, 0.1]} at={[0, 0.35, -0.3]} color={PK.wood} />
        <Box size={[0.3, 0.1, 0.6]} at={[0.2, 0.4, 0]} color={PK.wood} />
      </group>
    </group>
  );
}

/** Chòi nghỉ: sàn tròn + 6 cột + mái cone + ghế vòng decor. */
function Gazebo() {
  return (
    <group>
      <mesh position={[0, 0.15, 0]} receiveShadow castShadow>
        <cylinderGeometry args={[2.2, 2.2, 0.3, 12]} />
        {paint(PK.wood)}
      </mesh>
      {Array.from({ length: 6 }, (_, i) => {
        const a = (i / 6) * Math.PI * 2;
        return (
          <Box
            key={i}
            size={[0.18, 2.4, 0.18]}
            at={[Math.cos(a) * 1.9, 0.3, Math.sin(a) * 1.9]}
            color={PK.woodDark}
          />
        );
      })}
      {/* mái NGỒI trên đầu cột (đỉnh cột 2.7): đáy mái 2.7 */}
      <mesh position={[0, 3.5, 0]} castShadow>
        <coneGeometry args={[2.7, 1.6, 6]} />
        {paint(PK.gateGreen)}
      </mesh>
      <mesh position={[0, 4.32, 0]}>
        <sphereGeometry args={[0.12, 8, 6]} />
        {paint(PK.woodDark)}
      </mesh>
      {/* ghế vòng quanh cột giữa */}
      <mesh position={[0, 0.65, 0]}>
        <cylinderGeometry args={[0.9, 0.9, 0.12, 10]} />
        {paint(PK.woodDark)}
      </mesh>
      <mesh position={[0, 0.45, 0]}>
        <cylinderGeometry args={[0.25, 0.3, 0.4, 8]} />
        {paint(PK.stoneDark)}
      </mesh>
    </group>
  );
}

/** Tượng đá trên bệ hai tầng — thân trừu tượng, không tạc mặt. */
function Statue() {
  return (
    <group>
      <Box size={[1.4, 0.4, 1.4]} at={[0, 0, 0]} color={PK.stoneDark} />
      <Box size={[1.0, 0.5, 1.0]} at={[0, 0.4, 0]} color={PK.stone} />
      <Box size={[0.5, 1.1, 0.4]} at={[0, 0.9, 0]} color={PK.stone} />
      <Box size={[0.7, 0.5, 0.3]} at={[0, 1.9, 0]} color={PK.stone} />
      <mesh position={[0, 2.45, 0]} castShadow>
        <sphereGeometry args={[0.22, 10, 8]} />
        {paint(PK.stone)}
      </mesh>
      {/* tay dang: hai box ngang đối xứng */}
      {[-1, 1].map((s) => (
        <Box key={s} size={[0.5, 0.16, 0.16]} at={[s * 0.45, 2.0, 0]} color={PK.stone} />
      ))}
    </group>
  );
}

/** Khung xích đu chữ A + xà + hai ghế treo xích. */
function Swing() {
  return (
    <group>
      {[-1.6, 1.6].map((x) => (
        <group key={x}>
          {[-1, 1].map((s) => (
            <mesh key={s} position={[x + s * 0.45, 1.4, 0]} rotation={[0, 0, s * -0.3]} castShadow>
              <cylinderGeometry args={[0.09, 0.09, 3.0, 8]} />
              {paint(PK.gateGreen)}
            </mesh>
          ))}
        </group>
      ))}
      <mesh position={[0, 2.75, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.09, 0.09, 3.6, 8]} />
        {paint(PK.gateGreen)}
      </mesh>
      {[-0.8, 0.8].map((x) => (
        <group key={x}>
          {[-0.25, 0.25].map((z) => (
            <mesh key={z} position={[x, 1.75, z]} castShadow>
              <cylinderGeometry args={[0.025, 0.025, 1.9, 6]} />
              {paint(PK.stoneDark)}
            </mesh>
          ))}
          <Box size={[0.55, 0.08, 0.5]} at={[x, 0.75, 0]} color={PK.wood} />
        </group>
      ))}
    </group>
  );
}

/** Bập bênh: đế + trụ + ván NGANG (không nghiêng — dấu nghiêng phải tính, §8.9). */
function Seesaw() {
  return (
    <group>
      <Box size={[0.8, 0.25, 0.8]} at={[0, 0, 0]} color={PK.stoneDark} />
      <Box size={[0.25, 0.7, 0.25]} at={[0, 0.25, 0]} color={PK.gateGreen} />
      <Box size={[3.2, 0.14, 0.4]} at={[0, 0.95, 0]} color={PK.wood} />
      {[-1.3, 1.3].map((x) => (
        <group key={x}>
          {/* ghế NGỒI trên ván (đỉnh ván 1.09), không chìm trong ván */}
          <Box size={[0.4, 0.08, 0.35]} at={[x, 1.09, 0]} color={PK.woodDark} />
          <mesh position={[x, 1.35, 0]} castShadow>
            <cylinderGeometry args={[0.03, 0.03, 0.5, 6]} />
            {paint(PK.stoneDark)}
          </mesh>
          <Box size={[0.3, 0.05, 0.05]} at={[x, 1.6, 0]} color={PK.stoneDark} />
        </group>
      ))}
    </group>
  );
}

/** Hố cát: khung gỗ + cát + xô và xẻng decor. */
function Sandbox() {
  return (
    <group>
      {[-1.1, 1.1].map((z) => (
        <Box key={z} size={[2.6, 0.3, 0.18]} at={[0, 0, z]} color={PK.wood} />
      ))}
      {[-1.2, 1.2].map((x) => (
        <Box key={x} size={[0.18, 0.3, 2.4]} at={[x, 0, 0]} color={PK.wood} />
      ))}
      <Box size={[2.3, 0.22, 2.0]} at={[0, 0, 0]} color={PK.sand} />
      {/* lâu đài cát decor */}
      <mesh position={[-0.5, 0.35, 0.3]} castShadow>
        <cylinderGeometry args={[0.18, 0.24, 0.35, 8]} />
        {paint(PK.sand)}
      </mesh>
      <mesh position={[0.4, 0.3, -0.4]} castShadow>
        <cylinderGeometry args={[0.16, 0.16, 0.28, 10]} />
        {paint(PK.petalRed)}
      </mesh>
    </group>
  );
}

/** Diều bay đứng yên trên đầu + dây thẳng xuống cuộn dây (né tính góc chéo). */
function Kite() {
  return (
    <group>
      {/* dây dọc từ cuộn lên diều */}
      <mesh position={[0, 2.6, 0]}>
        <cylinderGeometry args={[0.015, 0.015, 5.0, 6]} />
        <meshStandardMaterial color={PALETTE.paper} />
      </mesh>
      {/* diều thoi: hai cone úp nhau */}
      <mesh position={[0, 5.3, 0]} rotation={[0, 0, Math.PI]} castShadow>
        <coneGeometry args={[0.55, 0.9, 4]} />
        {paint(PK.petalRed)}
      </mesh>
      <mesh position={[0, 4.55, 0]} castShadow>
        <coneGeometry args={[0.55, 0.7, 4]} />
        {paint(PK.petalYellow)}
      </mesh>
      {/* đuôi ba nơ */}
      {[3.9, 3.4, 2.9].map((y) => (
        <Box key={y} size={[0.22, 0.14, 0.04]} at={[0, y, 0]} color={PK.balloonBlue} />
      ))}
      {/* cuộn dây dưới đất */}
      <mesh position={[0, 0.15, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.16, 0.14, 10]} />
        {paint(PK.woodDark)}
      </mesh>
    </group>
  );
}

/** Võng giữa hai cọc + gối — vải ba đoạn nông, không tính cong. */
function Hammock() {
  return (
    <group>
      {[-2.2, 2.2].map((x) => (
        <group key={x}>
          <mesh position={[x, 0.7, 0]} castShadow>
            <cylinderGeometry args={[0.09, 0.11, 1.5, 8]} />
            {paint(PK.woodDark)}
          </mesh>
          <mesh position={[x, 1.45, 0]}>
            <sphereGeometry args={[0.11, 8, 6]} />
            {paint(PK.woodDark)}
          </mesh>
        </group>
      ))}
      <Box size={[1.4, 0.08, 0.8]} at={[-1.45, 1.05, 0]} color={PK.blanketRed} />
      <Box size={[1.4, 0.08, 0.8]} at={[1.45, 1.05, 0]} color={PK.blanketRed} />
      <Box size={[1.6, 0.06, 0.8]} at={[0, 0.85, 0]} color={PK.petalWhite} />
      <Box size={[0.4, 0.12, 0.5]} at={[-0.9, 0.92, 0]} color={PK.balloonBlue} />
    </group>
  );
}

/** Cổng chính: hai trụ + xà + bảng PARK canvas + hai cánh mở. */
function useGateBoard() {
  return useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 160;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#2e6b46";
    ctx.fillRect(0, 0, 512, 160);
    ctx.strokeStyle = "#f4f1e6";
    ctx.lineWidth = 8;
    ctx.strokeRect(10, 10, 492, 140);
    ctx.fillStyle = "#f4f1e6";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "700 84px system-ui, sans-serif";
    ctx.fillText("PARK", 256, 84);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    return tex;
  }, []);
}

function Gate() {
  const board = useGateBoard();
  return (
    <group>
      {[-2.6, 2.6].map((x) => (
        <group key={x}>
          <Box size={[0.7, 3.2, 0.7]} at={[x, 0, 0]} color={PK.stone} />
          <Box size={[0.9, 0.25, 0.9]} at={[x, 0, 0]} color={PK.stoneDark} />
          <mesh position={[x, 3.5, 0]} castShadow>
            <sphereGeometry args={[0.3, 10, 8]} />
            {paint(PK.stoneDark)}
          </mesh>
        </group>
      ))}
      <Box size={[6.4, 0.4, 0.5]} at={[0, 3.1, 0]} color={PK.gateGreen} />
      {board && (
        <mesh position={[0, 2.2, 0.28]}>
          <planeGeometry args={[3.4, 1.05]} />
          <meshBasicMaterial map={board} toneMapped={false} />
        </mesh>
      )}
      <Box size={[3.4, 1.05, 0.08]} at={[0, 2.2, 0.2]} color={PK.gateGreen} />
      {/* bảng TREO vào xà bằng 2 thanh (đỉnh bảng 2.725, đáy xà 3.1) —
          không thanh là bảng lơ lửng giữa hai trụ */}
      {[-1.2, 1.2].map((x) => (
        <Box key={x} size={[0.06, 0.4, 0.06]} at={[x, 2.7, 0.2]} color={PK.stoneDark} />
      ))}
      {/* hai cánh cổng mở vào trong (gốc khít trụ, yaw đối xứng) */}
      <group position={[-2.15, 0, 0]} rotation={[0, 0.6, 0]}>
        <Box size={[2.0, 1.4, 0.08]} at={[-1.0, 0.2, 0]} color={PK.stoneDark} />
      </group>
      <group position={[2.15, 0, 0]} rotation={[0, -0.6, 0]}>
        <Box size={[2.0, 1.4, 0.08]} at={[1.0, 0.2, 0]} color={PK.stoneDark} />
      </group>
    </group>
  );
}

/** Lối đi: tấm mỏng đáy chìm + mạch vữa nổi 0.02 (quy tắc flicker, §10.6). */
function Path() {
  return (
    <group>
      <Box size={[2.2, 0.08, 12]} at={[0, 0, 0]} color={PK.walkGray} />
      {Array.from({ length: 7 }, (_, i) => (
        <Box key={i} size={[2.22, 0.02, 0.07]} at={[0, 0.08, -5 + i * 1.7]} color={PK.stoneDark} />
      ))}
    </group>
  );
}

/** Bãi cỏ: thảm sáng + viền đá bốn cạnh. */
function Lawn() {
  return (
    <group>
      <Box size={[7, 0.07, 5]} at={[0, 0, 0]} color={PK.lawnLight} />
      {[-2.55, 2.55].map((z) => (
        <Box key={z} size={[7.3, 0.12, 0.25]} at={[0, 0, z]} color={PK.stone} />
      ))}
      {[-3.6, 3.6].map((x) => (
        <Box key={x} size={[0.25, 0.12, 5.3]} at={[x, 0, 0]} color={PK.stone} />
      ))}
    </group>
  );
}

/** Luống hoa dài + tám hoa (thân + đầu) + viền gạch. */
function Flowerbed() {
  const flowers: { x: number; z: number; color: string }[] = [
    { x: -1.4, z: 0.3, color: PK.petalRed },
    { x: -1.0, z: -0.4, color: PK.petalYellow },
    { x: -0.6, z: 0.4, color: PK.petalPink },
    { x: -0.2, z: -0.3, color: PK.petalWhite },
    { x: 0.2, z: 0.35, color: PK.petalRed },
    { x: 0.6, z: -0.35, color: PK.petalPink },
    { x: 1.0, z: 0.3, color: PK.petalYellow },
    { x: 1.4, z: -0.3, color: PK.petalRed },
  ];
  return (
    <group>
      <Box size={[3.6, 0.3, 1.4]} at={[0, 0, 0]} color={PK.soil} />
      {[-0.75, 0.75].map((z) => (
        <Box key={z} size={[3.7, 0.32, 0.12]} at={[0, 0, z]} color={PK.petalRed} />
      ))}
      {flowers.map((f, i) => (
        <group key={i} position={[f.x, 0.3, f.z]}>
          <mesh position={[0, 0.25, 0]} castShadow>
            <cylinderGeometry args={[0.03, 0.03, 0.5, 6]} />
            {paint(PK.leafDark)}
          </mesh>
          <mesh position={[0, 0.55, 0]} castShadow>
            <sphereGeometry args={[0.11, 8, 6]} />
            {paint(f.color)}
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Đèn đá: đế + thân có ô sáng + mái + chóp. */
function Lantern() {
  return (
    <group>
      <Box size={[0.6, 0.25, 0.6]} at={[0, 0, 0]} color={PK.stoneDark} />
      {/* thân TIẾP đế (đỉnh đế 0.25), không lơ lửng */}
      <mesh position={[0, 0.55, 0]} castShadow>
        <cylinderGeometry args={[0.18, 0.22, 0.6, 6]} />
        {paint(PK.stone)}
      </mesh>
      <Box size={[0.5, 0.4, 0.5]} at={[0, 0.9, 0]} color={PK.stone} />
      <Box size={[0.3, 0.24, 0.52]} at={[0, 0.9, 0]} color={PK.petalYellow} />
      <mesh position={[0, 1.3, 0]} castShadow>
        <coneGeometry args={[0.5, 0.35, 4]} />
        {paint(PK.stoneDark)}
      </mesh>
      <mesh position={[0, 1.55, 0]}>
        <sphereGeometry args={[0.09, 8, 6]} />
        {paint(PK.stoneDark)}
      </mesh>
    </group>
  );
}

/** Người ngồi bệt mặt +X: đùi duỗi, cẳng chống, lưng thẳng — decor tĩnh. */
function SeatedPerson({ coat, pants = PALETTE.steelDark }: { coat: string; pants?: string }) {
  return (
    <group>
      {[-0.12, 0.12].map((z) => (
        <group key={z}>
          <Box size={[0.42, 0.14, 0.16]} at={[0.3, 0.05, z]} color={pants} />
          <Box size={[0.14, 0.28, 0.16]} at={[0.48, 0, z]} color={pants} />
          <Box size={[0.12, 0.42, 0.14]} at={[0.02, 0.25, z > 0 ? 0.27 : -0.27]} color={coat} />
        </group>
      ))}
      <Box size={[0.34, 0.22, 0.4]} at={[0, 0.05, 0]} color={pants} />
      <Box size={[0.34, 0.55, 0.4]} at={[0, 0.27, 0]} color={coat} />
      <Box size={[0.26, 0.26, 0.26]} at={[0.02, 0.82, 0]} color={PALETTE.skin} />
      {/* mắt nhìn +X + tóc đỉnh/gáy (đầu trơn là mặt đơ — đã dính) */}
      {[-0.07, 0.07].map((z) => (
        <Box key={z} size={[0.05, 0.06, 0.06]} at={[0.14, 0.85, z]} color={PALETTE.tire} />
      ))}
      <Box size={[0.3, 0.08, 0.3]} at={[0.02, 1.08, 0]} color={PALETTE.tire} />
      <Box size={[0.1, 0.3, 0.28]} at={[-0.14, 0.9, 0]} color={PALETTE.tire} />
    </group>
  );
}

/** Buổi dã ngoại: thảm + giỏ + đĩa bánh + hai người ngồi + một người đang dọn. */
function Picnic() {
  return (
    <group>
      {/* thảm TIẾP cỏ (không lơ lửng 0.02); đồ trên thảm tiếp mặt thảm 0.06 */}
      <Box size={[2.4, 0.06, 1.8]} at={[0, 0, 0]} color={PK.blanketRed} />
      <Box size={[2.4, 0.06, 0.3]} at={[0, 0.02, 0.4]} color={PK.petalWhite} />
      <Box size={[0.5, 0.35, 0.35]} at={[-0.5, 0.06, -0.2]} color={PK.wood} />
      {/* quai nửa TRÊN đứng (arc π mặc định đã là nửa trên) */}
      <mesh position={[-0.5, 0.35, -0.2]} castShadow>
        <torusGeometry args={[0.18, 0.035, 6, 12, Math.PI]} />
        {paint(PK.woodDark)}
      </mesh>
      <mesh position={[0.4, 0.085, 0.2]} castShadow>
        <cylinderGeometry args={[0.22, 0.22, 0.05, 12]} />
        {paint(PK.petalWhite)}
      </mesh>
      <mesh position={[0.4, 0.2, 0.2]}>
        <sphereGeometry args={[0.09, 8, 6]} />
        {paint(PK.petalRed)}
      </mesh>
      <mesh position={[0.55, 0.2, 0.05]}>
        <sphereGeometry args={[0.09, 8, 6]} />
        {paint(PK.petalYellow)}
      </mesh>
      <group position={[1.9, 0, 0.9]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={PK.balloonGreen} />
        {/* tóc người dọn (mũi +X nên gáy −X) — không tóc là hói từ xa */}
        <Box size={[0.14, 0.9, 0.4]} at={[-0.18, 1.0, 0]} color={PALETTE.tire} />
        <Box size={[0.44, 0.14, 0.44]} at={[0.06, 1.66, 0]} color={PALETTE.tire} />
      </group>
      {/* hai người ngồi quây quanh đồ ăn, mặt vào giữa thảm (mông tiếp thảm) */}
      <group position={[0.75, 0, -0.55]} rotation={[0, Math.PI, 0]}>
        <SeatedPerson coat={PK.balloonBlue} />
      </group>
      <group position={[-1.0, 0, 0.6]}>
        <SeatedPerson coat={PK.petalYellow} pants={PK.woodDark} />
      </group>
    </group>
  );
}

/** Đồng hồ mặt trời: đế + đĩa + kim đứng hơi nghiêng (đỉnh lệch tính sẵn). */
function Sundial() {
  return (
    <group>
      <Box size={[0.7, 0.5, 0.7]} at={[0, 0, 0]} color={PK.stoneDark} />
      {/* đĩa TIẾP đế (đỉnh đế 0.5); vạch giờ tiếp mặt đĩa 0.6 */}
      <mesh position={[0, 0.55, 0]} castShadow>
        <cylinderGeometry args={[0.55, 0.55, 0.1, 16]} />
        {paint(PK.stone)}
      </mesh>
      {/* kim: đáy ở đĩa (y 0.6), cao 0.7, nghiêng 0.2 rad về +X —
          đỉnh ở x ≈ 0.07 + sin(0.2)·0.35 ≈ 0.14, y ≈ 0.95 + cos(0.2)·0.35 ≈ 1.29 */}
      <mesh position={[0.07, 0.95, 0]} rotation={[0, 0, -0.2]} castShadow>
        <boxGeometry args={[0.06, 0.7, 0.3]} />
        {paint(PK.stoneDark)}
      </mesh>
      {[-0.35, 0.35].map((x) => (
        <Box key={x} size={[0.05, 0.02, 0.9]} at={[x, 0.6, 0]} color={PK.stoneDark} />
      ))}
    </group>
  );
}

/** Bồn tắm chim: chân + chậu + nước + hai chim decor. */
function Birdbath() {
  return (
    <group>
      {/* chân TIẾP đất; chậu TIẾP chân (đỉnh chân 0.8) */}
      <mesh position={[0, 0.4, 0]} castShadow>
        <cylinderGeometry args={[0.14, 0.2, 0.8, 8]} />
        {paint(PK.stone)}
      </mesh>
      <mesh position={[0, 0.925, 0]} castShadow>
        <cylinderGeometry args={[0.55, 0.4, 0.25, 12]} />
        {paint(PK.stone)}
      </mesh>
      <mesh position={[0, 1.06, 0]}>
        <cylinderGeometry args={[0.45, 0.45, 0.04, 12]} />
        <meshStandardMaterial color={PK.water} transparent opacity={0.85} flatShading />
      </mesh>
      {/* chim ĐỨNG trong chậu (mặt nước 1.08), không lơ lửng trên */}
      {[
        [0.15, 1.17, 0.1],
        [-0.2, 1.14, -0.15],
      ].map(([x, y, z], i) => (
        <group key={i} position={[x, y, z]}>
          <mesh castShadow>
            <sphereGeometry args={[0.09, 8, 6]} />
            {paint(PK.stoneDark)}
          </mesh>
          <mesh position={[0.08, 0.08, 0]} castShadow>
            <sphereGeometry args={[0.055, 8, 6]} />
            {paint(PK.stoneDark)}
          </mesh>
          <mesh position={[0.15, 0.08, 0]} rotation={[0, 0, -Math.PI / 2]}>
            <coneGeometry args={[0.025, 0.07, 6]} />
            {paint(PK.petalYellow)}
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Người bán bóng: Person + tay giơ + năm bóng dây (patrol đi dọc lối). */
function Balloon() {
  const balloons: { dx: number; dz: number; h: number; color: string }[] = [
    { dx: 0.1, dz: 0, h: 3.1, color: PK.balloonBlue },
    { dx: -0.3, dz: 0.2, h: 2.9, color: PK.petalRed },
    { dx: 0.4, dz: -0.15, h: 2.9, color: PK.petalYellow },
    { dx: -0.1, dz: -0.3, h: 3.2, color: PK.balloonGreen },
    { dx: 0.3, dz: 0.3, h: 3.0, color: PK.balloonPurple },
  ];
  return (
    <group>
      <Person coat={PK.petalRed} hat={PK.woodDark} />
      {/* tay phải giơ lên giữ chùm dây */}
      <group position={[0, 1.36, -0.26]} rotation={[0, 0, 2.6]}>
        <Box size={[0.12, 0.55, 0.14]} at={[0, -0.55, 0]} color={PK.petalRed} />
      </group>
      {balloons.map((b, i) => (
        <group key={i}>
          <mesh position={[0.35, 2.2, -0.26]}>
            <cylinderGeometry args={[0.012, 0.012, b.h - 1.9, 6]} />
            <meshStandardMaterial color={PALETTE.paper} />
          </mesh>
          <mesh position={[b.dx + 0.3, b.h, b.dz - 0.26]} castShadow>
            <sphereGeometry args={[0.28, 12, 10]} />
            {paint(b.color)}
          </mesh>
          <mesh position={[b.dx + 0.3, b.h - 0.32, b.dz - 0.26]}>
            <coneGeometry args={[0.05, 0.1, 6]} />
            {paint(b.color)}
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Đoạn rào sắt decor 4 m — cổng nam chừa trống cho `gate`. */
function ParkFence() {
  return (
    <group>
      {[-2, 2].map((x) => (
        <Box key={x} size={[0.12, 1.1, 0.12]} at={[x, 0, 0]} color={PK.stoneDark} />
      ))}
      {[0.5, 0.9].map((y) => (
        <Box key={y} size={[4, 0.07, 0.07]} at={[0, y, 0]} color={PK.stoneDark} />
      ))}
      {[-1.5, -1, -0.5, 0, 0.5, 1, 1.5].map((x) => (
        <Box key={x} size={[0.06, 0.9, 0.06]} at={[x, 0.05, 0]} color={PK.stoneDark} />
      ))}
    </group>
  );
}

export function ParkEnvironment({
  onBrandPick,
}: {
  onBrandPick?: (c: [number, number, number]) => void;
}) {
  const ground = useParkPlan();
  // Rào ba mặt: bắc + đông + tây; mặt nam chỉ hai đoạn ngoài cổng (cổng ở x ±3).
  const fenceX: number[] = [-14, -10, -6, 6, 10, 14];
  return (
    <group>
      {ground && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
          <planeGeometry args={[PARK_SPAN, PARK_SPAN]} />
          <meshStandardMaterial map={ground} />
        </mesh>
      )}
      {/* rào bắc */}
      {[-16, -12, -8, -4, 0, 4, 8, 12, 16].map((x) => (
        <group key={`n${x}`} position={[x, 0, -16]}>
          <ParkFence />
        </group>
      ))}
      {/* rào đông/tây xoay 90° */}
      {[-12, -8, -4, 0, 4, 8, 12].map((z) => (
        <group key={`w${z}`} position={[-16, 0, z]} rotation={[0, Math.PI / 2, 0]}>
          <ParkFence />
        </group>
      ))}
      {[-12, -8, -4, 0, 4, 8, 12].map((z) => (
        <group key={`e${z}`} position={[16, 0, z]} rotation={[0, Math.PI / 2, 0]}>
          <ParkFence />
        </group>
      ))}
      {/* rào nam chừa cổng */}
      {fenceX.map((x) => (
        <group key={`s${x}`} position={[x, 0, 14]}>
          <ParkFence />
        </group>
      ))}
      {/* cây decor rải quanh, né cụm object (tính theo def park.ts).
          Cây [-7, -12] cũ đâm thân qua vành đá hồ (vành tới x −7.2) nên dời
          ra ngoài tầm vành + tán (4.2 + 0.9). */}
      {[
        [-13, -11],
        [-14, 6],
        [-8, -12.5],
        [13, -11],
        [14, 2],
        [6, -12],
        [-13, 11],
        [13, 11],
      ].map(([x, z], i) => (
        <Tree key={i} at={[x, 0, z]} />
      ))}
      {/* biển sau lưng (bắc), mặt +Z quay về camera nam — yaw π là quay
          lưng vào nhà (đã dính một lần, preview đen thui) */}
      <Signboard at={[11, 0, -13]} onPick={onBrandPick} />
    </group>
  );
}

export const PARK_SHAPES = {
  fountain: Fountain,
  pond: Pond,
  bridge: Bridge,
  gazebo: Gazebo,
  statue: Statue,
  swing: Swing,
  picnic: Picnic,
  flowerbed: Flowerbed,
  lantern: Lantern,
  gate: Gate,
  path: Path,
  lawn: Lawn,
  lake: Lake,
  balloon: Balloon,
  sundial: Sundial,
  birdbath: Birdbath,
  seesaw: Seesaw,
  sandbox: Sandbox,
  kite: Kite,
  hammock: Hammock,
};
