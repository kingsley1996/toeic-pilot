import { useFrame } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { Box, PALETTE, Person, Wheel, paint, useSignFace } from "@/components/scenes/scene-shapes";

/**
 * Nhà hàng (topic `restaurant`, 21 từ lấy sẵn trong kho — không nhập mới).
 * Indoor thứ hai sau office nên mượn toàn bộ quy ước của nó: shape gốc đất,
 * đồ nhỏ tự mang bàn (bấm vào bàn vẫn ăn như kiện dispatch mang pallet),
 * chữ vẽ canvas offline, kính decor một mức 0.28 + tắt raycast.
 *
 * Phân biệt các món ăn bằng đạo cụ, không bằng màu chung chung: khai vị là
 * đĩa salad đầy, tráng miệng là bánh kem dâu, đồ uống là bình + ly, khăn là
 * hình chóp gấp, đồ dùng là khay dao-nĩa-thìa, rót thêm là bình quai, trang
 * trí là đĩa trắng + lá thơm (một-to-ít như revise một tờ).
 */

const RS = {
  tablecloth: "#f3ede0",
  tableclothRed: "#b8443c",
  chairWood: "#7c5a34",
  plateWhite: "#f7f5ef",
  saladGreen: "#4d8a3f",
  tomatoRed: "#d94f3d",
  cakePink: "#e8a0a8",
  berryRed: "#b8283c",
  juiceOrange: "#e8932e",
  meatBrown: "#8a5a33",
  charcoal: "#2e3236",
  emberRed: "#e2572e",
  traySteel: "#aab2b9",
  paperBag: "#cfa46f",
  moneyGreen: "#4d8a5f",
  bookRed: "#a83c3c",
  bookBlue: "#3b6ea5",
  bookGreen: "#3f7d4f",
  floorWood: "#b08a5a",
  floorDark: "#96754c",
  wallCream: "#e6ddcb",
} as const;

function foodCanvas(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void) {
  // Helper thuần như `officeCanvas`: mỗi shape gọi trong `useMemo` của nó.
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  draw(ctx);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

/** Bàn ăn chung: mặt tròn + khăn phủ + chân + 4 ghế (ghế nào thừa thì món
 *  nhỏ dùng bản không ghế). Nến giữa bàn để bàn tiệc đọc ra "đang dùng". */
function DiningTable({ chairs = 4, candle = true }: { chairs?: number; candle?: boolean }) {
  return (
    <group>
      <mesh position={[0, 0.74, 0]} receiveShadow castShadow>
        <cylinderGeometry args={[0.8, 0.8, 0.06, 18]} />
        {paint(RS.tablecloth)}
      </mesh>
      <mesh position={[0, 0.68, 0]}>
        <cylinderGeometry args={[0.82, 0.85, 0.1, 18]} />
        {paint(RS.tableclothRed)}
      </mesh>
      <mesh position={[0, 0.36, 0]} castShadow>
        <cylinderGeometry args={[0.09, 0.12, 0.72, 10]} />
        {paint(RS.chairWood)}
      </mesh>
      <mesh position={[0, 0.05, 0]}>
        <cylinderGeometry args={[0.35, 0.4, 0.08, 12]} />
        {paint(RS.chairWood)}
      </mesh>
      {Array.from({ length: chairs }, (_, i) => {
        const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
        const x = Math.cos(a) * 1.25;
        const z = Math.sin(a) * 1.25;
        // Lưng ghế ở local −Z nên mặt ghế nhìn về local +Z: muốn nhìn vào
        // tâm bàn thì rotation = −a−π/2 (đặt +π/2 là cả 4 ghế quay ra ngoài).
        return (
          <group key={i} position={[x, 0, z]} rotation={[0, -a - Math.PI / 2, 0]}>
            <Box size={[0.42, 0.06, 0.42]} at={[0, 0.45, 0]} color={RS.chairWood} />
            <Box size={[0.42, 0.5, 0.06]} at={[0, 0.48, -0.2]} color={RS.chairWood} />
            <Box size={[0.06, 0.45, 0.06]} at={[0, 0, 0]} color={PALETTE.steelDark} />
          </group>
        );
      })}
      {candle && (
        <group>
          <mesh position={[0, 0.85, 0]} castShadow>
            <cylinderGeometry args={[0.09, 0.11, 0.12, 10]} />
            {paint(RS.traySteel)}
          </mesh>
          <mesh position={[0, 0.95, 0]} castShadow>
            <cylinderGeometry args={[0.025, 0.025, 0.14, 8]} />
            {paint(RS.plateWhite)}
          </mesh>
          <mesh position={[0, 1.04, 0]}>
            <sphereGeometry args={[0.03, 8, 6]} />
            <meshBasicMaterial color={RS.juiceOrange} toneMapped={false} />
          </mesh>
        </group>
      )}
    </group>
  );
}

/** Người ngồi ghế ăn mặt +X: mông ở mặt ghế 0.48, chân gập dưới bàn. */
function DiningSeated({ coat }: { coat: string }) {
  return (
    <group>
      <Box size={[0.34, 0.2, 0.38]} at={[0, 0.48, 0]} color={PALETTE.steelDark} />
      <Box size={[0.34, 0.55, 0.4]} at={[-0.05, 0.68, 0]} color={coat} />
      {/* đùi ngang ra trước + cẳng xuống — gầm bàn che nên không cần bàn chân */}
      <Box size={[0.4, 0.14, 0.36]} at={[0.2, 0.5, 0]} color={PALETTE.steelDark} />
      <Box size={[0.12, 0.42, 0.32]} at={[0.35, 0.08, 0]} color={PALETTE.steelDark} />
      <group position={[-0.02, 1.22, 0]}>
        <Box size={[0.26, 0.26, 0.26]} at={[0, 0, 0]} color={PALETTE.skin} />
      </group>
    </group>
  );
}

/** Ghế ăn nhỏ cho bàn món: mặt + lưng + trụ (mặt ghế 0.48 khớp mông
 *  `DiningSeated`). Mặt ghế nhìn về local +Z như ghế bàn tròn. */
function SmallChair() {
  return (
    <group>
      <Box size={[0.42, 0.06, 0.42]} at={[0, 0.45, 0]} color={RS.chairWood} />
      <Box size={[0.42, 0.5, 0.06]} at={[0, 0.48, -0.2]} color={RS.chairWood} />
      <Box size={[0.06, 0.45, 0.06]} at={[0, 0, 0]} color={PALETTE.steelDark} />
    </group>
  );
}

/** Bảng menu trên kệ đỡ cạnh cửa: 2 chân + khay đỡ + bảng nghiêng, mặt
 *  canvas +Z quay về khách bước vào (không làm chữ A hai mặt — mặt sau
 *  quay vào tường là vô nghĩa, mặt trước phải ra ngoài). */
function useMenuFace() {
  return useMemo(
    () =>
      foodCanvas(256, 340, (ctx) => {
        ctx.fillStyle = RS.chairWood;
        ctx.fillRect(0, 0, 256, 340);
        ctx.fillStyle = RS.tablecloth;
        ctx.fillRect(14, 14, 228, 312);
        ctx.fillStyle = RS.bookRed;
        ctx.fillRect(14, 14, 228, 64);
        ctx.fillStyle = RS.tablecloth;
        ctx.font = "700 40px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("MENU", 128, 60);
        ctx.fillStyle = PALETTE.steelDark;
        for (const y of [110, 150, 190, 230]) {
          ctx.fillRect(34, y, 150, 12);
          ctx.fillStyle = RS.juiceOrange;
          ctx.fillRect(192, y - 2, 30, 16);
          ctx.fillStyle = PALETTE.steelDark;
        }
        ctx.fillStyle = RS.bookRed;
        ctx.fillRect(34, 262, 100, 30);
      }),
    [],
  );
}

function MenuBoard() {
  const face = useMenuFace();
  return (
    <group>
      {/* kệ đỡ: 2 chân + khay đỡ ngang */}
      {[-0.4, 0.4].map((x) => (
        <Box key={x} size={[0.08, 1.0, 0.08]} at={[x, 0, 0]} color={RS.chairWood} />
      ))}
      <Box size={[1.0, 0.06, 0.3]} at={[0, 0.95, 0.05]} color={RS.chairWood} />
      {/* bảng nghiêng tựa trên kệ (đỉnh y ≈ 2.25), mặt canvas +Z ra cửa.
          `Box` lấy gốc CHÂN theo y còn mesh trần lấy tâm — `at` 0.6 là đáy
          0.6 (tâm 1.25), lệch mặt (tâm 0.6) cả thân bảng (họ §8.1, đã dính).
          Mặt nổi 0.03 trước thân (quy tắc 0.02, §10.6). */}
      <group position={[0, 1.0, 0]} rotation={[-0.18, 0, 0]}>
        <Box size={[1.0, 1.3, 0.06]} at={[0, -0.05, 0]} color={RS.chairWood} />
        {face && (
          <mesh position={[0, 0.6, 0.1]}>
            <planeGeometry args={[0.9, 1.15]} />
            <meshBasicMaterial map={face} toneMapped={false} />
          </mesh>
        )}
      </group>
    </group>
  );
}

/** Bục đón khách: bục cao + sổ đặt + nữ tiếp đón đứng sau, mặt +Z ra
 *  cửa (mũi Person +X nên yaw −π/2 mới nhìn về khách — để mặc định là
 *  quay ngang). Tóc gáy + đỉnh + búi như lễ tân office. */
function HostStand() {
  return (
    <group>
      <Box size={[0.7, 1.1, 0.5]} at={[0, 0, 0]} color={RS.chairWood} />
      <Box size={[0.8, 0.06, 0.6]} at={[0, 1.1, 0]} color={PALETTE.steelDark} />
      {/* sổ LÚN 5mm vào mặt bục (đáy 1.155 dưới mặt 1.16) — đáy đồng phẳng
          với mặt mới là flicker */}
      <Box size={[0.4, 0.04, 0.3]} at={[0, 1.155, 0]} color={PALETTE.paper} />
      <group position={[0, 0, -0.65]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={RS.bookRed} />
        <Box size={[0.14, 0.9, 0.4]} at={[-0.18, 1.0, 0]} color={PALETTE.tire} />
        <Box size={[0.44, 0.14, 0.44]} at={[0.06, 1.66, 0]} color={PALETTE.tire} />
        <mesh position={[-0.16, 1.84, 0]} castShadow>
          <sphereGeometry args={[0.11, 10, 8]} />
          {paint(PALETTE.tire)}
        </mesh>
      </group>
    </group>
  );
}

/** Bàn tiệc chính giữa phòng: bàn tròn + nến + 2 thực khách ngồi đối
 *  nhau (không món — món nằm ở các bàn nhỏ riêng cho khỏi lẫn). */
function TableSet() {
  return (
    <group>
      <DiningTable />
      {/* ngồi ĐÚNG ghế 3π/4 và 7π/4 (ghế ở bán kính 1.25): mặt vào tâm bàn.
          rotation tính như ghế — người mũi +X: θ = atan2(−dz, dx). */}
      <group position={[-0.884, 0, 0.884]} rotation={[0, Math.PI / 4, 0]}>
        <DiningSeated coat={RS.moneyGreen} />
      </group>
      <group position={[0.884, 0, -0.884]} rotation={[0, (-3 * Math.PI) / 4, 0]}>
        <DiningSeated coat={PALETTE.doorOrange} />
      </group>
    </group>
  );
}

/** Bàn vuông 2 ghế + bảng RESERVED dựng trên mặt bàn. */
function useReservedFace() {
  return useMemo(
    () =>
      foodCanvas(256, 128, (ctx) => {
        ctx.fillStyle = RS.bookRed;
        ctx.fillRect(0, 0, 256, 128);
        ctx.strokeStyle = RS.tablecloth;
        ctx.lineWidth = 6;
        ctx.strokeRect(8, 8, 240, 112);
        ctx.fillStyle = RS.tablecloth;
        ctx.font = "700 44px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("RESERVED", 128, 80);
      }),
    [],
  );
}

function ReserveTable() {
  const face = useReservedFace();
  return (
    <group>
      <Box size={[1.2, 0.07, 1.2]} at={[0, 0.73, 0]} color={RS.tablecloth} />
      {[
        [-0.5, -0.5],
        [0.5, -0.5],
        [-0.5, 0.5],
        [0.5, 0.5],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.07, 0.73, 0.07]} at={[x, 0, z]} color={RS.chairWood} />
      ))}
      {[-0.9, 0.9].map((x) => (
        <group key={x} position={[x, 0, 0.9]} rotation={[0, Math.PI, 0]}>
          <Box size={[0.42, 0.06, 0.42]} at={[0, 0.45, 0]} color={RS.chairWood} />
          <Box size={[0.42, 0.5, 0.06]} at={[0, 0.48, -0.2]} color={RS.chairWood} />
        </group>
      ))}
      {/* bảng dựng: chân + mặt canvas hai mặt */}
      <Box size={[0.5, 0.04, 0.3]} at={[0, 0.77, 0]} color={RS.chairWood} />
      {face && (
        <mesh position={[0, 1.05, 0]}>
          <planeGeometry args={[0.55, 0.28]} />
          <meshBasicMaterial map={face} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
      )}
      <Box size={[0.06, 0.28, 0.06]} at={[0, 0.77, 0]} color={RS.chairWood} />
    </group>
  );
}

/** Hai thực khách đối mặt qua bàn tròn + 2 đĩa đang ăn dở. Ngồi ĐÚNG
 *  2 ghế của bàn (bán kính 1.25, góc π/4 và 5π/4) — đặt giữa hai ghế là
 *  ngồi lên không khí (đã dính một lần). */
function DinerSet() {
  return (
    <group>
      <DiningTable chairs={2} />
      <group position={[-0.884, 0, -0.884]} rotation={[0, -Math.PI / 4, 0]}>
        <DiningSeated coat={PALETTE.doorBlue} />
      </group>
      <group position={[0.884, 0, 0.884]} rotation={[0, (3 * Math.PI) / 4, 0]}>
        <DiningSeated coat={RS.bookGreen} />
      </group>
      {[-0.3, 0.3].map((z) => (
        <group key={z}>
          <mesh position={[0, 0.79, z]} receiveShadow>
            <cylinderGeometry args={[0.22, 0.18, 0.04, 14]} />
            {paint(RS.plateWhite)}
          </mesh>
          <mesh position={[0.05, 0.83, z]} castShadow>
            <sphereGeometry args={[0.07, 8, 6]} />
            {paint(RS.meatBrown)}
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Đĩa salad khai vị trên bàn nhỏ + 2 ghế + 1 thực khách (ghế tây). */
function AppetizerPlate() {
  return (
    <group>
      <Box size={[1.0, 0.07, 1.0]} at={[0, 0.73, 0]} color={RS.tablecloth} />
      {[
        [-0.4, -0.4],
        [0.4, -0.4],
        [-0.4, 0.4],
        [0.4, 0.4],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.07, 0.73, 0.07]} at={[x, 0, z]} color={RS.chairWood} />
      ))}
      {/* ghế đông (trống, mặt −X vào bàn) + ghế tây có khách (mặt +X) */}
      <group position={[0.85, 0, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <SmallChair />
      </group>
      <group position={[-0.85, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <SmallChair />
      </group>
      <group position={[-0.85, 0, 0]}>
        <DiningSeated coat={RS.saladGreen} />
      </group>
      <mesh position={[0, 0.79, 0]} receiveShadow>
        <cylinderGeometry args={[0.3, 0.24, 0.05, 16]} />
        {paint(RS.plateWhite)}
      </mesh>
      {/* salad đầy đĩa: 5 lá + 3 cà chua — đầy mới là khai vị, ít là garnish */}
      {[
        [-0.1, 0.05],
        [0.08, -0.08],
        [-0.02, -0.12],
        [0.12, 0.1],
        [-0.12, -0.05],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.85, z]} castShadow>
          <sphereGeometry args={[0.07, 8, 6]} />
          {paint(RS.saladGreen)}
        </mesh>
      ))}
      {[
        [0, 0],
        [-0.14, 0.1],
        [0.1, -0.12],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.9, z]} castShadow>
          <sphereGeometry args={[0.045, 8, 6]} />
          {paint(RS.tomatoRed)}
        </mesh>
      ))}
    </group>
  );
}

/** Bánh kem dâu trên đĩa cao (chân đĩa cho khác đĩa bẹt khai vị)
 *  + 2 ghế + 1 thực khách (ghế đông, mặt −X vào bàn). */
function DessertPlate() {
  return (
    <group>
      <Box size={[1.0, 0.07, 1.0]} at={[0, 0.73, 0]} color={RS.tablecloth} />
      {[
        [-0.4, -0.4],
        [0.4, -0.4],
        [-0.4, 0.4],
        [0.4, 0.4],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.07, 0.73, 0.07]} at={[x, 0, z]} color={RS.chairWood} />
      ))}
      <group position={[-0.85, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <SmallChair />
      </group>
      <group position={[0.85, 0, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <SmallChair />
      </group>
      <group position={[0.85, 0, 0]} rotation={[0, Math.PI, 0]}>
        <DiningSeated coat={RS.berryRed} />
      </group>
      <mesh position={[0, 0.82, 0]} castShadow>
        <cylinderGeometry args={[0.05, 0.09, 0.1, 10]} />
        {paint(RS.traySteel)}
      </mesh>
      <mesh position={[0, 0.9, 0]} receiveShadow>
        <cylinderGeometry args={[0.26, 0.26, 0.03, 16]} />
        {paint(RS.plateWhite)}
      </mesh>
      <mesh position={[0, 1.0, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.18, 0.14, 14]} />
        {paint(RS.cakePink)}
      </mesh>
      <mesh position={[0, 1.1, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.05, 0.05, 12]} />
        {paint(RS.plateWhite)}
      </mesh>
      <mesh position={[0.06, 1.15, 0.04]} castShadow>
        <sphereGeometry args={[0.04, 8, 6]} />
        {paint(RS.berryRed)}
      </mesh>
      <mesh position={[-0.07, 1.15, -0.03]} castShadow>
        <sphereGeometry args={[0.04, 8, 6]} />
        {paint(RS.berryRed)}
      </mesh>
    </group>
  );
}

/** Bình nước quả + 2 ly thủy tinh (kính 0.6 cho thấy nước cam bên trong). */
function BeverageSet() {
  return (
    <group>
      <Box size={[1.0, 0.07, 1.0]} at={[0, 0.73, 0]} color={RS.tablecloth} />
      {[
        [-0.4, -0.4],
        [0.4, -0.4],
        [-0.4, 0.4],
        [0.4, 0.4],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.07, 0.73, 0.07]} at={[x, 0, z]} color={RS.chairWood} />
      ))}
      {/* bình: thân + cổ + nước cam thấy qua kính */}
      <mesh position={[-0.15, 0.95, 0]} castShadow>
        <cylinderGeometry args={[0.13, 0.16, 0.35, 12]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.6} flatShading />
      </mesh>
      <mesh position={[-0.15, 0.92, 0]}>
        <cylinderGeometry args={[0.11, 0.14, 0.25, 12]} />
        <meshStandardMaterial color={RS.juiceOrange} flatShading />
      </mesh>
      <mesh position={[-0.15, 1.16, 0]} castShadow>
        <cylinderGeometry args={[0.06, 0.09, 0.08, 10]} />
        {paint(RS.traySteel)}
      </mesh>
      {[0.15, 0.32].map((x) => (
        <group key={x}>
          <mesh position={[x, 0.86, 0.1]} castShadow>
            <cylinderGeometry args={[0.055, 0.045, 0.16, 10]} />
            <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.6} flatShading />
          </mesh>
          <mesh position={[x, 0.83, 0.1]}>
            <cylinderGeometry args={[0.045, 0.04, 0.08, 10]} />
            <meshStandardMaterial color={RS.juiceOrange} flatShading />
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Khăn ăn gấp chóp trên đĩa trống — hình chóp mới là "đã gấp", vải phẳng
 *  là chưa dọn. */
function NapkinSet() {
  return (
    <group>
      <Box size={[1.0, 0.07, 1.0]} at={[0, 0.73, 0]} color={RS.tablecloth} />
      {[
        [-0.4, -0.4],
        [0.4, -0.4],
        [-0.4, 0.4],
        [0.4, 0.4],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.07, 0.73, 0.07]} at={[x, 0, z]} color={RS.chairWood} />
      ))}
      <mesh position={[-0.2, 0.79, 0]} receiveShadow>
        <cylinderGeometry args={[0.22, 0.18, 0.04, 14]} />
        {paint(RS.plateWhite)}
      </mesh>
      <mesh position={[-0.2, 0.92, 0]} castShadow>
        <coneGeometry args={[0.11, 0.22, 4]} />
        {paint(RS.tableclothRed)}
      </mesh>
      <mesh position={[0.25, 0.79, 0]} receiveShadow>
        <cylinderGeometry args={[0.22, 0.18, 0.04, 14]} />
        {paint(RS.plateWhite)}
      </mesh>
      <mesh position={[0.25, 0.92, 0]} castShadow>
        <coneGeometry args={[0.11, 0.22, 4]} />
        {paint(RS.tablecloth)}
      </mesh>
    </group>
  );
}

/** Khay dao-nĩa-thìa: cán thẳng + đầu phân biệt (nĩa 3 răng mini). */
function UtensilSet() {
  return (
    <group>
      <Box size={[1.0, 0.07, 1.0]} at={[0, 0.73, 0]} color={RS.tablecloth} />
      {[
        [-0.4, -0.4],
        [0.4, -0.4],
        [-0.4, 0.4],
        [0.4, 0.4],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.07, 0.73, 0.07]} at={[x, 0, z]} color={RS.chairWood} />
      ))}
      <Box size={[0.7, 0.08, 0.4]} at={[0, 0.8, 0]} color={RS.chairWood} />
      {/* dao/nĩa/thìa NẰM TRÊN mặt khay (đỉnh khay 0.88) — để 0.85 là chôn
          cả bộ trong khay, nhìn từ trên chỉ thấy khay trống (đã dính). */}
      {/* dao: cán + lưỡi */}
      <Box size={[0.25, 0.02, 0.05]} at={[-0.2, 0.885, -0.1]} color={PALETTE.steelDark} />
      <Box size={[0.2, 0.015, 0.06]} at={[-0.2, 0.885, 0.08]} color={RS.traySteel} />
      {/* nĩa: cán + 3 răng */}
      <Box size={[0.25, 0.02, 0.04]} at={[0.1, 0.885, -0.08]} color={PALETTE.steelDark} />
      {[-0.03, 0, 0.03].map((dz) => (
        <Box
          key={dz}
          size={[0.12, 0.015, 0.025]}
          at={[0.1, 0.885, 0.1 + dz]}
          color={RS.traySteel}
        />
      ))}
      {/* thìa: cán + đầu bầu dục */}
      <Box size={[0.22, 0.02, 0.04]} at={[-0.05, 0.885, 0.18]} color={RS.traySteel} />
      <mesh position={[-0.05, 0.905, 0.32]} castShadow>
        <sphereGeometry args={[0.045, 8, 6]} />
        {paint(RS.traySteel)}
      </mesh>
    </group>
  );
}

/** Bình rót thêm + 2 ly rỗng chờ — "refill" đọc ra từ bình nghiêng rót. */
function RefillPitcher() {
  return (
    <group>
      <Box size={[1.0, 0.07, 1.0]} at={[0, 0.73, 0]} color={RS.tablecloth} />
      {[
        [-0.4, -0.4],
        [0.4, -0.4],
        [-0.4, 0.4],
        [0.4, 0.4],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.07, 0.73, 0.07]} at={[x, 0, z]} color={RS.chairWood} />
      ))}
      {/* bình quai: thân + quai torus nửa + miệng */}
      <mesh position={[-0.1, 0.98, 0]} castShadow>
        <cylinderGeometry args={[0.14, 0.17, 0.4, 12]} />
        {paint(RS.plateWhite)}
      </mesh>
      <mesh position={[-0.1, 1.0, -0.14]} rotation={[0, 0, 0]} castShadow>
        <torusGeometry args={[0.12, 0.025, 6, 12, Math.PI]} />
        {paint(RS.plateWhite)}
      </mesh>
      <mesh position={[-0.1, 1.2, 0]} castShadow>
        <cylinderGeometry args={[0.09, 0.12, 0.06, 12]} />
        {paint(RS.plateWhite)}
      </mesh>
      {[0.2, 0.35].map((x) => (
        <mesh key={x} position={[x, 0.84, 0.15]} castShadow>
          <cylinderGeometry args={[0.055, 0.045, 0.14, 10]} />
          <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.6} flatShading />
        </mesh>
      ))}
    </group>
  );
}

/** Đĩa trắng + vài lá thơm + củ cải — ít mới là trang trí (ngược appetizer). */
function GarnishPlate() {
  return (
    <group>
      <Box size={[1.0, 0.07, 1.0]} at={[0, 0.73, 0]} color={PALETTE.steel} />
      {[
        [-0.4, -0.4],
        [0.4, -0.4],
        [-0.4, 0.4],
        [0.4, 0.4],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.07, 0.73, 0.07]} at={[x, 0, z]} color={RS.chairWood} />
      ))}
      {/* bàn inox cho khác bàn gỗ khu ăn — đây là bàn bếp */}
      <mesh position={[0, 0.79, 0]} receiveShadow>
        <cylinderGeometry args={[0.3, 0.3, 0.03, 16]} />
        {paint(RS.plateWhite)}
      </mesh>
      {[
        [0.08, 0.05],
        [-0.06, -0.08],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.83, z]} castShadow>
          <sphereGeometry args={[0.05, 8, 6]} />
          {paint(RS.saladGreen)}
        </mesh>
      ))}
      <mesh position={[-0.1, 0.84, 0.08]} castShadow>
        <sphereGeometry args={[0.05, 8, 6]} />
        {paint(RS.tomatoRed)}
      </mesh>
      {/* bình xịt dầu decor cạnh đĩa */}
      <mesh position={[0.3, 0.9, -0.2]} castShadow>
        <cylinderGeometry args={[0.05, 0.05, 0.2, 8]} />
        {paint(RS.juiceOrange)}
      </mesh>
    </group>
  );
}

/** Quầy buffet dài: chân + mặt + 3 khay inox có nắp + chồng đĩa + nồi
 *  súp + rổ bánh mì đầu đông (quầy 4.4 m mới đủ chỗ — số khớp def). */
function BuffetCounter() {
  return (
    <group>
      <Box size={[4.4, 0.85, 1.0]} at={[0, 0, 0]} color={RS.chairWood} />
      <Box size={[4.5, 0.06, 1.1]} at={[0, 0.85, 0]} color={PALETTE.steelDark} />
      {[
        { x: -1.2, food: RS.meatBrown },
        { x: -0.2, food: RS.saladGreen },
        { x: 0.8, food: RS.juiceOrange },
      ].map(({ x, food }) => (
        <group key={x}>
          <Box size={[0.9, 0.18, 0.7]} at={[x, 0.88, 0]} color={RS.traySteel} />
          {/* nắp mở nửa sau, món VUN QUA miệng khay mới thấy từ xa —
              thấp trong khay là nắp che hết (đã dính một lần) */}
          <Box size={[0.9, 0.1, 0.35]} at={[x, 1.05, -0.17]} color={RS.traySteel} />
          <Box size={[0.7, 0.14, 0.5]} at={[x, 1.0, 0.05]} color={food} />
        </group>
      ))}
      {/* chồng đĩa đầu tây quầy: đĩa đầu LÚN 5mm vào mặt quầy (đáy 0.875
          dưới mặt 0.88) — đáy đồng phẳng với mặt mới là flicker, khe 0.025
          mới tách đĩa (quy tắc 0.02, §10.6) */}
      {[0, 1, 2, 3, 4].map((i) => (
        <mesh key={i} position={[-1.9, 0.89 + i * 0.055, 0]}>
          <cylinderGeometry args={[0.2, 0.2, 0.03, 14]} />
          {paint(RS.plateWhite)}
        </mesh>
      ))}
      {/* hàng ly tráng miệng mép trước quầy (dải z 0.35..0.5 còn trống) */}
      {[-1.0, -0.5, 0, 0.5, 1.0].map((x, i) => (
        <group key={x}>
          <mesh position={[x, 0.92, 0.43]} castShadow>
            <cylinderGeometry args={[0.06, 0.05, 0.08, 8]} />
            {paint(RS.plateWhite)}
          </mesh>
          <mesh position={[x, 0.98, 0.43]} castShadow>
            <sphereGeometry args={[0.035, 8, 6]} />
            {paint(i % 2 ? RS.berryRed : RS.cakePink)}
          </mesh>
        </group>
      ))}
      {/* nồi súp đầu đông: thân + mặt súp + muôi gác */}
      <mesh position={[1.5, 1.0, 0.1]} castShadow>
        <cylinderGeometry args={[0.17, 0.19, 0.22, 12]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      <mesh position={[1.5, 1.1, 0.1]}>
        <cylinderGeometry args={[0.14, 0.14, 0.03, 12]} />
        <meshStandardMaterial color={RS.juiceOrange} flatShading />
      </mesh>
      <group position={[1.5, 1.15, -0.1]} rotation={[0, 0, 1.1]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.02, 0.02, 0.3, 6]} />
          {paint(RS.traySteel)}
        </mesh>
      </group>
      {/* rổ bánh mì: khay + 3 ổ dài */}
      <Box size={[0.45, 0.1, 0.3]} at={[1.95, 0.93, -0.15]} color={RS.paperBag} />
      {[-0.08, 0, 0.08].map((dz) => (
        <mesh
          key={dz}
          position={[1.95, 1.02, -0.15 + dz]}
          rotation={[0, 0, Math.PI / 2]}
          castShadow
        >
          <cylinderGeometry args={[0.045, 0.045, 0.35, 8]} />
          {paint(RS.meatBrown)}
        </mesh>
      ))}
    </group>
  );
}

/** Bếp nướng: thân đen + vỉ + than đỏ + 3 miếng thịt + kẹp gác. */
function GrillStove() {
  return (
    <group>
      <Box size={[1.2, 0.7, 0.8]} at={[0, 0, 0]} color={RS.charcoal} />
      <Box size={[1.1, 0.08, 0.7]} at={[0, 0.7, 0]} color={PALETTE.steelDark} />
      {/* than đỏ dưới vỉ */}
      {[0.25, 0, -0.25].map((x) => (
        <mesh key={x} position={[x, 0.76, 0]}>
          <sphereGeometry args={[0.09, 8, 6]} />
          <meshBasicMaterial color={RS.emberRed} toneMapped={false} />
        </mesh>
      ))}
      {/* vỉ: 5 thanh song song */}
      {[-0.28, -0.14, 0, 0.14, 0.28].map((z) => (
        <Box key={z} size={[1.05, 0.03, 0.04]} at={[0, 0.85, z]} color={PALETTE.steelDark} />
      ))}
      {[-0.3, 0.05, 0.35].map((x, i) => (
        <Box key={i} size={[0.22, 0.07, 0.3]} at={[x, 0.88, 0]} color={RS.meatBrown} />
      ))}
      {/* kẹp GÁC TRÊN thịt (đỉnh thịt 0.95), không chìm trong thịt */}
      <group position={[0.3, 0.96, 0.2]} rotation={[0, 0.4, Math.PI / 2]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.02, 0.02, 0.5, 6]} />
          {paint(RS.traySteel)}
        </mesh>
      </group>
      {/* chụp hút mùi: 2 trụ đỡ từ thân bếp (lửng là lơ lửng — đã dính) +
          ống khói flush đỉnh tường 3.0, không chọc lên trời */}
      {[-0.6, 0.6].map((x) => (
        <Box key={x} size={[0.08, 1.5, 0.08]} at={[x, 0.68, 0]} color={PALETTE.steelDark} />
      ))}
      <Box size={[1.3, 0.5, 0.9]} at={[0, 2.2, 0]} color={RS.traySteel} />
      <Box size={[0.3, 0.35, 0.3]} at={[0, 2.65, 0]} color={RS.traySteel} />
    </group>
  );
}

/** Đầu bếp: Person + mũ cao + tạp dề + chảo trên tay. */
function ChefFigure() {
  return (
    <group>
      <Person coat={RS.plateWhite} hat={RS.plateWhite} />
      {/* mũ cao hơn mũ thường: trụ trắng trên vành */}
      <mesh position={[0.06, 1.85, 0]} castShadow>
        <cylinderGeometry args={[0.13, 0.13, 0.22, 10]} />
        {paint(RS.plateWhite)}
      </mesh>
      {/* tạp dề trước ngực */}
      <Box size={[0.05, 0.5, 0.34]} at={[0.2, 1.0, 0]} color={RS.plateWhite} />
      {/* chảo tay phải: cán + lòng */}
      <group position={[0, 1.36, -0.14]} rotation={[0, 0, 1.2]}>
        <Box size={[0.1, 0.4, 0.12]} at={[0, -0.4, 0]} color={RS.plateWhite} />
      </group>
      <mesh position={[0.42, 0.95, -0.14]} castShadow>
        <cylinderGeometry args={[0.16, 0.13, 0.07, 12]} />
        {paint(RS.charcoal)}
      </mesh>
    </group>
  );
}

/** Hai thùng nguyên liệu: rau xanh + cà rốt cam. */
function IngredientCrate() {
  return (
    <group>
      {[-0.45, 0.45].map((x, ci) => (
        <group key={x}>
          <Box size={[0.8, 0.35, 0.6]} at={[x, 0, 0]} color={RS.paperBag} />
          {[-0.25, 0, 0.25].map((dx) =>
            ci === 0 ? (
              <mesh key={dx} position={[x + dx, 0.42, 0]} castShadow>
                <sphereGeometry args={[0.12, 8, 6]} />
                {paint(RS.saladGreen)}
              </mesh>
            ) : (
              <mesh key={dx} position={[x + dx, 0.42, 0]} rotation={[0, 0, 0.3]} castShadow>
                <coneGeometry args={[0.07, 0.25, 8]} />
                {paint(RS.juiceOrange)}
              </mesh>
            ),
          )}
        </group>
      ))}
    </group>
  );
}

/**
 * Người đẩy xe mặt +X: chân quẫy theo chuyển động như `Person` (tự đo
 * world-shift, không prop) nhưng KHÔNG có tay bên — chỉ hai tay trước nắm
 * tay cầm. Dùng `Person` + gắn thêm tay là 4 tay (đã dính một lần).
 */
function PushingStaff({ coat, hat }: { coat: string; hat?: string }) {
  const body = useRef<THREE.Group>(null);
  const legBack = useRef<THREE.Group>(null);
  const legFront = useRef<THREE.Group>(null);
  const t = useRef(0);
  const here = useRef(new THREE.Vector3());
  const there = useRef(new THREE.Vector3());

  useFrame((_, dt) => {
    const g = body.current;
    if (!g) return;
    g.getWorldPosition(here.current);
    const moved = there.current.distanceTo(here.current);
    there.current.copy(here.current);
    if (moved < 0.002) return;
    t.current += dt * 3.2;
    const s = Math.sin(t.current);
    if (legBack.current) legBack.current.rotation.z = s * 0.45;
    if (legFront.current) legFront.current.rotation.z = -s * 0.45;
    g.position.y = Math.abs(Math.sin(t.current)) * 0.035;
  });

  return (
    <group ref={body}>
      <group ref={legBack} position={[0, 0.82, -0.11]}>
        <Box size={[0.16, 0.72, 0.2]} at={[0, -0.72, 0]} color={PALETTE.steelDark} />
        <Box size={[0.26, 0.1, 0.22]} at={[0.04, -0.82, 0]} color={PALETTE.tire} />
      </group>
      <group ref={legFront} position={[0, 0.82, 0.11]}>
        <Box size={[0.16, 0.72, 0.2]} at={[0, -0.72, 0]} color={PALETTE.steelDark} />
        <Box size={[0.26, 0.1, 0.22]} at={[0.04, -0.82, 0]} color={PALETTE.tire} />
      </group>
      <Box size={[0.36, 0.62, 0.44]} at={[0, 0.82, 0]} color={coat} />
      {/* hai tay trước vươn tới tay cầm (không tay bên) */}
      {[-0.15, 0.15].map((z) => (
        <Box key={z} size={[0.5, 0.1, 0.12]} at={[0.28, 1.1, z]} color={coat} />
      ))}
      <group position={[0.06, 1.44, 0]} rotation={[0, 0, -0.08]}>
        <Box size={[0.28, 0.28, 0.28]} at={[0, 0, 0]} color={PALETTE.skin} />
        {[-0.07, 0.07].map((z) => (
          <Box key={z} size={[0.05, 0.06, 0.06]} at={[0.13, 0.15, z]} color={PALETTE.tire} />
        ))}
        {hat && (
          <>
            <Box size={[0.32, 0.09, 0.32]} at={[0, 0.26, 0]} color={hat} />
            <Box size={[0.14, 0.04, 0.3]} at={[0.19, 0.27, 0]} color={hat} />
          </>
        )}
      </group>
    </group>
  );
}

/** Xe đẩy phục vụ tiệc: 3 tầng + khay phủ khăn + bánh xe (mượn `Wheel`)
 *  + nhân viên đẩy sau tay cầm (mặt −X vào xe). */
function CateringCart() {
  return (
    <group>
      <group position={[1.05, 0, 0]} rotation={[0, Math.PI, 0]}>
        <PushingStaff coat={RS.plateWhite} hat={PALETTE.cone} />
      </group>
      {[0.35, 0.7, 1.05].map((y) => (
        <Box key={y} size={[1.1, 0.05, 0.7]} at={[0, y, 0]} color={RS.traySteel} />
      ))}
      {[
        [-0.5, -0.3],
        [0.5, -0.3],
        [-0.5, 0.3],
        [0.5, 0.3],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.05, 1.05, 0.05]} at={[x, 0, z]} color={PALETTE.steelDark} />
      ))}
      {/* khay phủ khăn NGỒI trên kệ (đỉnh kệ 1.1) + tay đẩy NỐI trụ —
          lơ lửng/luplơ là hỏng im lặng ở vật nhỏ */}
      <Box size={[0.8, 0.12, 0.55]} at={[-0.05, 1.1, 0]} color={RS.tablecloth} />
      <mesh position={[-0.05, 1.22, 0]} castShadow>
        <sphereGeometry args={[0.12, 10, 8]} />
        {paint(RS.tablecloth)}
      </mesh>
      <Box size={[0.05, 0.05, 0.6]} at={[0.54, 1.0, 0]} color={PALETTE.steelDark} />
      {[
        [-0.4, -0.3],
        [0.4, -0.3],
        [-0.4, 0.3],
        [0.4, 0.3],
      ].map(([x, z]) => (
        <Wheel key={`${x}:${z}`} at={[x, 0.14, z]} r={0.14} />
      ))}
      {/* đĩa tầng giữa */}
      <mesh position={[0, 0.74, 0]}>
        <cylinderGeometry args={[0.24, 0.24, 0.04, 14]} />
        {paint(RS.plateWhite)}
      </mesh>
    </group>
  );
}

/** Bồi bàn bưng khay: Person + tay trái giơ khay + 2 ly trên khay.
 *  Tay xoay −2.6 đưa đầu tay tới (−0.284, 1.83) nên khay ĐẶT ĐÚNG đó —
 *  để khay 2.05 là lơ lửng trên đầu tay 0.2 (đã dính một lần). */
function WaiterFigure() {
  return (
    <group>
      <Person coat={PALETTE.tire} />
      {/* tay trái giơ lên đỡ khay (gương tay phải của Balloon: −Z giơ là +2.6) */}
      <group position={[0, 1.36, 0.26]} rotation={[0, 0, -2.6]}>
        <Box size={[0.12, 0.55, 0.14]} at={[0, -0.55, 0]} color={PALETTE.tire} />
      </group>
      <mesh position={[-0.28, 1.86, 0.26]} receiveShadow>
        <cylinderGeometry args={[0.3, 0.3, 0.04, 14]} />
        {paint(RS.traySteel)}
      </mesh>
      {[-0.1, 0.1].map((dz) => (
        <mesh key={dz} position={[-0.28, 1.97, 0.26 + dz]} castShadow>
          <cylinderGeometry args={[0.05, 0.04, 0.12, 8]} />
          <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.6} flatShading />
        </mesh>
      ))}
    </group>
  );
}

/** Túi giấy mang về + hộp xốp trên quầy thu ngân (quầy là decor chung)
 *  + nhân viên đứng sau quầy trao hàng (mặt +Z ra khách). */
function TakeoutBag() {
  return (
    <group>
      <group position={[0.1, 0, -0.85]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={RS.plateWhite} hat={RS.plateWhite} />
      </group>
      {/* túi giấy: thân (đáy lút mặt quầy) + miệng gấp NGẬM mép túi
          (đỉnh thân 1.5) + quai nửa trên đứng (arc π mặc định đã là nửa
          trên — xoay π/2 là thành nửa bên, đã dính) */}
      <Box size={[0.4, 0.5, 0.3]} at={[0, 1.0, 0]} color={RS.paperBag} />
      <Box size={[0.42, 0.08, 0.32]} at={[0, 1.46, 0]} color={PALETTE.cardbox} />
      <mesh position={[0, 1.5, 0]} castShadow>
        <torusGeometry args={[0.1, 0.02, 6, 10, Math.PI]} />
        {paint(PALETTE.cardbox)}
      </mesh>
      {/* hộp xốp trắng cạnh túi + nắp NGỒI đỉnh hộp (đỉnh 1.18) */}
      <Box size={[0.35, 0.18, 0.25]} at={[0.45, 1.0, 0.1]} color={RS.plateWhite} />
      <Box size={[0.37, 0.04, 0.27]} at={[0.45, 1.18, 0.1]} color={RS.plateWhite} />
    </group>
  );
}

/** Chữ $ TIP dán trước hũ — không chữ thì lọ kính chỉ đọc ra "lọ". */
function useTipFace() {
  return useMemo(
    () =>
      foodCanvas(128, 80, (ctx) => {
        ctx.fillStyle = RS.plateWhite;
        ctx.fillRect(0, 0, 128, 80);
        ctx.fillStyle = RS.moneyGreen;
        ctx.font = "700 52px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("$ TIP", 64, 58);
      }),
    [],
  );
}

/** Hũ tiền boa: lọ kính thấy tiền giấy xanh + khe bỏ tiền trên nắp. */
function GratuityJar() {
  const tip = useTipFace();
  return (
    <group>
      {/* lọ TIẾP mặt quầy (đỉnh quầy 1.01): đáy lút 0.0x, không lơ lửng */}
      <mesh position={[0, 1.17, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.16, 0.32, 12]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.6} flatShading />
      </mesh>
      {/* tiền trong lọ: 3 tờ xanh dựng */}
      {[-0.05, 0, 0.05].map((dx, i) => (
        <Box key={i} size={[0.02, 0.18, 0.12]} at={[dx, 1.12, 0]} color={RS.moneyGreen} />
      ))}
      <mesh position={[0, 1.35, 0]} castShadow>
        <cylinderGeometry args={[0.17, 0.17, 0.04, 12]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      {/* chữ $ TIP canvas dán trước lọ (nổi 0.02 trước mặt lọ) */}
      {tip && (
        <mesh position={[0, 1.2, 0.185]}>
          <planeGeometry args={[0.2, 0.125]} />
          <meshBasicMaterial map={tip} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Kệ sách công thức: khung 3 đợt + sách đứng TRÊN mặt đợt (đỉnh đợt).
 *  Sách cao chạm khít đáy đợt trên là flicker — sách ngắn hơn khe 0.04;
 *  đợt trên cùng không có sách đội nóc (đã dính: sách đâm qua đợt 1.7). */
function RecipeShelf() {
  const rows: { top: number; h: number; colors: string[] }[] = [
    { top: 0.41, h: 0.38, colors: [RS.bookRed, RS.bookBlue, RS.bookGreen, RS.moneyGreen] },
    { top: 0.91, h: 0.38, colors: [RS.bookBlue, RS.bookRed, RS.bookGreen] },
    { top: 1.41, h: 0.26, colors: [RS.bookGreen, RS.moneyGreen, RS.bookRed, RS.bookBlue] },
  ];
  return (
    <group>
      {[-0.7, 0.7].map((x) => (
        <Box key={x} size={[0.08, 1.7, 0.4]} at={[x, 0, 0]} color={RS.chairWood} />
      ))}
      {[0.35, 0.85, 1.35].map((y) => (
        <Box key={y} size={[1.5, 0.06, 0.42]} at={[0, y, 0]} color={RS.chairWood} />
      ))}
      {rows.map((row, ri) =>
        row.colors.map((c, i) => (
          <Box
            key={`${ri}:${i}`}
            size={[0.12, row.h - (i % 2) * 0.06, 0.3]}
            at={[-0.55 + i * 0.28, row.top, 0]}
            color={c}
          />
        )),
      )}
    </group>
  );
}

export function RestaurantEnvironment({
  onBrandPick,
}: {
  onBrandPick?: (c: [number, number, number]) => void;
}) {
  const floor = useMemo(() => {
    // Sàn gỗ sọc deterministic (không random — texture phải giống mỗi lần load).
    const PPM = 32;
    const size = 30 * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = RS.floorWood;
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = RS.floorDark;
    for (let i = 0; i < 30; i += 2) ctx.fillRect(0, i * PPM, size, PPM);
    ctx.strokeStyle = RS.chairWood;
    ctx.lineWidth = 2;
    for (let i = 0; i <= 30; i += 5) {
      ctx.beginPath();
      ctx.moveTo(0, i * PPM);
      ctx.lineTo(size, i * PPM);
      ctx.stroke();
    }
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    return tex;
  }, []);
  return (
    <group>
      {floor && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[30, 30]} />
          <meshStandardMaterial map={floor} roughness={0.9} />
        </mesh>
      )}
      {/* tường bắc (z = −10) + tường tây/đông đặc — mặt nam mở cho camera */}
      <Box size={[26, 3.0, 0.3]} at={[0, 0, -10]} color={RS.wallCream} />
      <Box size={[0.3, 3.0, 18]} at={[-13, 0, -1]} color={RS.wallCream} />
      <Box size={[0.3, 3.0, 18]} at={[13, 0, -1]} color={RS.wallCream} />
      {/* mặt nam: tường lửng nối liền tường tây–đông, chừa lối vào giữa
          (x ±2.2). Tường cao 1.1 — camera trên cao nhìn qua được, không như
          khung cửa 2.6 m cũ che cả host/menu. */}
      {[-7.6, 7.6].map((x) => (
        <group key={x}>
          <Box size={[10.8, 1.1, 0.2]} at={[x, 0, 8]} color={RS.wallCream} />
          <Box size={[10.8, 0.08, 0.26]} at={[x, 1.1, 8]} color={RS.chairWood} />
        </group>
      ))}
      {/* cửa sổ Trung Hoa TRÊN 2 bờ tường lửng: khung + song dọc + ô tròn
          nguyệt động giữa mỗi đoạn, cao tới y 3.0 (bằng tường hai bên).
          Vòng torus sống sẵn trong mặt XY nên đứng tường hướng nam là đúng
          chiều luôn (ngược vụ vành ao park phải xoay nằm — §11.1). Nan thưa
          để thân host/menu đọc được qua khe (nhãn DOM nằm trên canvas nên
          e2e không bắt được kiểu che này, chỉ mắt xem mới thấy). */}
      {[-7.6, 7.6].map((cx) => (
        <group key={cx}>
          {/* bậu dưới ngồi lút vào mũ tường + mũ trên flush đỉnh tường 3.0.
              `Box` lấy gốc CHÂN theo y: `at` là ĐÁY — mọi con số dưới là đáy,
              đỉnh = đáy + cao (bản trước đặt đáy 2.025 cho song cao 1.75 là
              đỉnh chọc lên 3.775, vượt tường — họ §8.1). */}
          <Box size={[10.8, 0.12, 0.16]} at={[cx, 1.15, 8]} color={RS.chairWood} />
          <Box size={[10.8, 0.12, 0.16]} at={[cx, 2.88, 8]} color={RS.chairWood} />
          {/* thanh giữa CHẺ ĐÔI chừa ô tròn, tâm đúng y 2.0 */}
          {[-2.975, 2.975].map((dx) => (
            <Box key={dx} size={[4.85, 0.08, 0.12]} at={[cx + dx, 1.96, 8]} color={RS.chairWood} />
          ))}
          <Box size={[1.1, 0.1, 0.16]} at={[cx, 1.95, 8]} color={RS.chairWood} />
          {/* song dọc 1.24..2.9: chân lút bậu, đỉnh lút mũ (cách 1.35,
              bỏ cây giữa nhường ô tròn) */}
          {[-5.4, -4.05, -2.7, -1.35, 1.35, 2.7, 4.05, 5.4].map((dx) => (
            <Box key={dx} size={[0.09, 1.66, 0.09]} at={[cx + dx, 1.24, 8]} color={RS.chairWood} />
          ))}
          {/* ô tròn nguyệt động + thanh đứng trong (hai đầu lút vào vành) */}
          <mesh position={[cx, 2.0, 8]} castShadow>
            <torusGeometry args={[0.5, 0.08, 8, 24]} />
            {paint(RS.chairWood)}
          </mesh>
          <Box size={[0.07, 0.9, 0.07]} at={[cx, 1.55, 8]} color={RS.chairWood} />
        </group>
      ))}
      {/* lối vào: hai trụ cây lùn + thảm đỏ giữa hai tường lửng */}
      {[-2.2, 2.2].map((x) => (
        <group key={x}>
          <Box size={[0.5, 1.0, 0.5]} at={[x, 0, 8]} color={RS.chairWood} />
          <mesh position={[x, 1.15, 8]} castShadow>
            <sphereGeometry args={[0.3, 10, 8]} />
            {paint(PALETTE.leaf)}
          </mesh>
        </group>
      ))}
      <Box size={[3.4, 0.04, 2.2]} at={[0, 0, 8]} color={RS.tableclothRed} />
      {/* quầy thu ngân decor tây-bắc: takeout/gratuity đặt khớp hai đầu */}
      <Box size={[4.4, 0.95, 0.9]} at={[-10, 0, -6]} color={RS.chairWood} />
      <Box size={[4.5, 0.06, 1.0]} at={[-10, 0.95, -6]} color={PALETTE.steelDark} />
      {/* logo thương hiệu tường bắc giữa (mẫu LogoPlate office, không chân) */}
      <BrandPlate onPick={onBrandPick} />
      {/* chậu cây 2 góc + đèn đứng cạnh cửa */}
      <PlantPot at={[-12, 0, 6.5]} />
      <PlantPot at={[12, 0, 6.5]} />
      <PlantPot at={[-12, 0, -8.5]} />
    </group>
  );
}

/** Logo dán tường như office (trong nhà không dựng biển cột). */
function BrandPlate({ onPick }: { onPick?: (c: [number, number, number]) => void }) {
  const face = useSignFace();
  const ref = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  if (!onPick) return null;
  return (
    <group
      ref={ref}
      position={[0, 0, -9.83]}
      onClick={(e) => {
        e.stopPropagation();
        if (!ref.current) return;
        const v = new THREE.Vector3(0, 2.0, 0).applyMatrix4(ref.current.matrixWorld);
        onPick([v.x, v.y, v.z]);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={() => setHovered(false)}
    >
      <Box size={[3.7, 1.9, 0.08]} at={[0, 1.05, 0]} color={PALETTE.wallTrim} />
      {face && (
        <mesh position={[0, 2.0, hovered ? 0.07 : 0.06]}>
          <planeGeometry args={[3.6, 1.8]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Chậu cây decor góc phòng. */
function PlantPot({ at }: { at: [number, number, number] }) {
  return (
    <group position={at}>
      <mesh position={[0, 0.2, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.17, 0.4, 10]} />
        {paint(RS.bookRed)}
      </mesh>
      {[
        [0, 0.75, 0, 0.35, 0.7],
        [0.18, 0.6, 0.1, 0.25, 0.5],
        [-0.18, 0.62, -0.08, 0.25, 0.55],
      ].map(([x, y, z, r, h], i) => (
        <mesh key={i} position={[x, y, z]} castShadow>
          <coneGeometry args={[r, h, 8]} />
          {paint(PALETTE.leaf)}
        </mesh>
      ))}
    </group>
  );
}

export const RESTAURANT_SHAPES = {
  "menu-board": MenuBoard,
  "host-stand": HostStand,
  "table-set": TableSet,
  "reserve-table": ReserveTable,
  "diner-set": DinerSet,
  "appetizer-plate": AppetizerPlate,
  "dessert-plate": DessertPlate,
  "beverage-set": BeverageSet,
  "napkin-set": NapkinSet,
  "utensil-set": UtensilSet,
  "refill-pitcher": RefillPitcher,
  "garnish-plate": GarnishPlate,
  "buffet-counter": BuffetCounter,
  "grill-stove": GrillStove,
  "chef-figure": ChefFigure,
  "ingredient-crate": IngredientCrate,
  "catering-cart": CateringCart,
  "waiter-figure": WaiterFigure,
  "takeout-bag": TakeoutBag,
  "gratuity-jar": GratuityJar,
  "recipe-shelf": RecipeShelf,
};
