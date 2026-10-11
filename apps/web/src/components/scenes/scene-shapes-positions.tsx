import { useMemo } from "react";
import * as THREE from "three";

import { Box, PALETTE, paint, useSignFace } from "@/components/scenes/scene-shapes";

/**
 * Phòng đọc (topic `positions`, 14 từ). Mỗi shape là một TIỂU CẢNH diễn đúng
 * một quan hệ vị trí (bàn + sách cho `on`, ghế dài + thùng cho `under`...),
 * hotspot mang tên giới từ — trò Part 1 "A [noun] is [prep] the [noun]".
 *
 * Quy ước indoor như mọi cảnh: `Box` gốc chân, chữ canvas offline, mặt phủ
 * cách nhau ≥ 0.02, đồ trên mặt đáy lút 0.005. Ghế mặc định mặt +Z (về phía
 * nam/phía camera); muốn hướng khác thì xoay/bố trí ngay trong shape, không
 * đặt `rotationY` ở def cho đỡ lừa người sau (phòng tĩnh, không patrol).
 */

const PR = {
  floorWood: "#b08a5a",
  floorDark: "#96754c",
  wallWarm: "#e8e2d4",
  woodDark: "#6e4f2e",
  woodGold: "#a8814a",
  fabricBlue: "#3b6ea5",
  fabricRed: "#a8502f",
  fabricGreen: "#5f8a52",
  cushionCream: "#f2ede0",
  paperWhite: "#f7f5ef",
  steelDark: "#3f464d",
  plantGreen: "#5f8a52",
  potTerra: "#b0623a",
  glassBlue: "#9fc0d2",
  tvBlack: "#1d2530",
  screenGlow: "#2e4a5a",
  bookRed: "#a83232",
  bookBlue: "#2f5f8f",
  bookGreen: "#3f7a4e",
  bookGold: "#c09a3f",
} as const;

/* --- Đồ dùng chung (không vào registry, chỉ tiểu cảnh dưới dùng) --- */

/** Chậu cây: chậu + đất + tán lá nón, đỉnh 0.9. */
function PlantPot() {
  return (
    <group>
      <mesh position={[0, 0.175, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.2, 0.35, 10]} />
        {paint(PR.potTerra)}
      </mesh>
      <mesh position={[0, 0.625, 0]} castShadow>
        <coneGeometry args={[0.28, 0.55, 8]} />
        {paint(PR.plantGreen)}
      </mesh>
    </group>
  );
}

/** Ghế ăn mặt +Z (lưng ở −Z): chân 0.45 + mặt 0.52 + trụ lưng tới 1.0. */
function DiningChair() {
  return (
    <group>
      {[-0.19, 0.19].map((x) =>
        [-0.19, 0.19].map((z) => (
          <Box key={`${x}${z}`} size={[0.07, 0.46, 0.07]} at={[x, 0, z]} color={PR.woodDark} />
        )),
      )}
      <Box size={[0.45, 0.07, 0.45]} at={[0, 0.45, 0]} color={PR.woodGold} />
      {[-0.19, 0.19].map((x) => (
        <Box key={x} size={[0.06, 0.48, 0.06]} at={[x, 0.515, -0.19]} color={PR.woodDark} />
      ))}
      <Box size={[0.44, 0.3, 0.05]} at={[0, 0.62, -0.19]} color={PR.woodGold} />
    </group>
  );
}

/** Ghế bành mặt +Z: đế + nệm + lưng tới 1.0 + 2 tay. Mọi mặt hông đều thụt
 *  vào trong mép đế (mặt nào trùng mép đế là nhấp nháy ở xa — §10.6). */
function Armchair() {
  return (
    <group>
      <Box size={[0.9, 0.35, 0.8]} at={[0, 0, 0]} color={PR.fabricBlue} />
      <Box size={[0.68, 0.15, 0.6]} at={[-0.09, 0.345, 0.05]} color={PR.cushionCream} />
      <Box size={[0.88, 0.65, 0.18]} at={[0, 0.345, -0.295]} color={PR.fabricBlue} />
      {[-0.37, 0.37].map((x) => (
        <Box key={x} size={[0.15, 0.3, 0.8]} at={[x, 0.345, 0]} color={PR.fabricBlue} />
      ))}
    </group>
  );
}

/** Ghế đôi mặt +Z, rộng 2 m, lưng tới 1.0. */
function Loveseat() {
  return (
    <group>
      {[-0.9, 0.9].map((x) =>
        [-0.35, 0.35].map((z) => (
          <Box key={`${x}${z}`} size={[0.09, 0.3, 0.09]} at={[x, 0, z]} color={PR.woodDark} />
        )),
      )}
      <Box size={[2.0, 0.2, 0.9]} at={[0, 0.295, 0]} color={PR.fabricGreen} />
      {[-0.48, 0.48].map((x) => (
        <Box key={x} size={[0.9, 0.13, 0.8]} at={[x, 0.49, 0]} color={PR.cushionCream} />
      ))}
      <Box size={[1.98, 0.6, 0.18]} at={[0, 0.4, -0.35]} color={PR.fabricGreen} />
      {[-0.905, 0.905].map((x) => (
        <Box key={x} size={[0.18, 0.35, 0.9]} at={[x, 0.4, 0]} color={PR.fabricGreen} />
      ))}
    </group>
  );
}

/** Thùng gỗ 0.4–0.7, nắp lút 0.005 vào thân. */
function Crate({ s = 0.6 }: { s?: number }) {
  return (
    <group>
      <Box size={[s, s - 0.06, s]} at={[0, 0, 0]} color={PALETTE.cardbox} />
      <Box size={[s + 0.02, 0.06, s + 0.02]} at={[0, s - 0.065, 0]} color={PR.woodGold} />
    </group>
  );
}

/** Cửa sổ áp tường (mặt tường ở local z = 0, nhìn về +Z): khung 1.1..2.5. */
function WallWindow() {
  return (
    <group position={[0, 0, 0.055]}>
      {/* khung ngoài + kính + song chia 4 (mặt nào cũng lồi ≥ 0.02) */}
      <Box size={[1.9, 0.1, 0.1]} at={[0, 1.05, 0]} color={PR.cushionCream} />
      <Box size={[1.9, 0.1, 0.1]} at={[0, 2.4, 0]} color={PR.cushionCream} />
      {[-0.9, 0.9].map((x) => (
        <Box key={x} size={[0.1, 1.45, 0.1]} at={[x, 1.05, 0]} color={PR.cushionCream} />
      ))}
      <mesh position={[0, 1.74, 0.02]} raycast={() => null}>
        <planeGeometry args={[1.7, 1.28]} />
        <meshStandardMaterial color={PR.glassBlue} transparent opacity={0.28} />
      </mesh>
      <Box size={[0.06, 1.28, 0.04]} at={[0, 1.1, 0.04]} color={PR.cushionCream} />
      <Box size={[1.7, 0.06, 0.04]} at={[0, 1.71, 0.04]} color={PR.cushionCream} />
      {/* bậu cửa lồi ra đỡ (cắm vào khung, không chạm khít) */}
      <Box size={[2.1, 0.1, 0.25]} at={[0, 0.97, 0.08]} color={PR.woodGold} />
    </group>
  );
}

/** Cửa đi áp tường (khung tới 2.5). `facing`: −X cho tường đông, −Z cho tường nam. */
function WallDoor({ facing }: { facing: "-x" | "-z" }) {
  const inner = (
    <group>
      {[-0.71, 0.71].map((x) => (
        <Box key={x} size={[0.12, 2.4, 0.14]} at={[x, 0, 0]} color={PR.woodDark} />
      ))}
      <Box size={[1.5, 0.12, 0.14]} at={[0, 2.38, 0]} color={PR.woodDark} />
      {/* cánh khép: lưng lút vào tường, mặt trước lộ */}
      <Box size={[1.3, 2.32, 0.1]} at={[0, 0.02, 0]} color={PR.fabricRed} />
      <Box size={[1.0, 0.9, 0.03]} at={[0, 1.25, 0.05]} color={PR.woodGold} />
      <Box size={[1.0, 0.7, 0.03]} at={[0, 0.25, 0.05]} color={PR.woodGold} />
      <mesh position={[0.45, 1.05, 0.08]}>
        <sphereGeometry args={[0.05, 8, 6]} />
        {paint(PR.steelDark)}
      </mesh>
    </group>
  );
  // Cửa dựng theo mặt +Z rồi xoay ra hướng tường: −X là yaw −π/2? Tính hai
  // đầu: yaw −π/2 đưa +Z thành (−1, 0, 0)? (sin(−π/2), 0, cos(−π/2)) = (−1,0,0) ✓.
  return <group rotation={[0, facing === "-x" ? -Math.PI / 2 : Math.PI, 0]}>{inner}</group>;
}

/* --- 14 tiểu cảnh (registry) --- */

/** `on`: chồng sách TRÊN bàn phụ (đỉnh 0.71). */
function BookOnTable() {
  return (
    <group>
      {[-0.3, 0.3].map((x) =>
        [-0.3, 0.3].map((z) => (
          <Box key={`${x}${z}`} size={[0.07, 0.5, 0.07]} at={[x, 0, z]} color={PR.woodDark} />
        )),
      )}
      <Box size={[0.7, 0.06, 0.7]} at={[0, 0.49, 0]} color={PR.woodGold} />
      <Box size={[0.35, 0.08, 0.25]} at={[0, 0.545, 0]} color={PR.bookRed} />
      <Box size={[0.3, 0.08, 0.22]} at={[0.02, 0.62, 0]} color={PR.bookBlue} />
    </group>
  );
}

/** `under`: thùng 0.4 lút dưới gầm ghế dài (mặt ghế 0.55). */
function CrateUnderBench() {
  return (
    <group>
      {[-0.7, 0.7].map((x) =>
        [-0.18, 0.18].map((z) => (
          <Box key={`${x}${z}`} size={[0.08, 0.46, 0.08]} at={[x, 0, z]} color={PR.woodDark} />
        )),
      )}
      <Box size={[1.6, 0.1, 0.5]} at={[0, 0.45, 0]} color={PR.woodGold} />
      <group position={[-0.35, 0, 0]}>
        <Crate s={0.4} />
      </group>
    </group>
  );
}

/** `above`: sofa mặt +X (lưng tựa tây) + tranh treo TRÊN tường (tới 2.5). */
function PaintingAboveSofa() {
  return (
    <group>
      {/* sofa xoay sẵn mặt +X: lưng ở −X */}
      <group rotation={[0, Math.PI / 2, 0]}>
        <Loveseat />
      </group>
      {/* tranh áp tường tây (mặt tường local x = −2.35): khung + mặt lồi dần.
          Mảng đồi chỉ được nằm trong mặt canvas (±0.77) — lố ra là tràn khung. */}
      <group position={[-2.32, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <Box size={[1.62, 0.08, 0.07]} at={[0, 1.5, 0]} color={PR.woodDark} />
        <Box size={[1.62, 0.08, 0.07]} at={[0, 2.42, 0]} color={PR.woodDark} />
        {[-0.81, 0.81].map((x) => (
          <Box key={x} size={[0.08, 1.0, 0.07]} at={[x, 1.5, 0]} color={PR.woodDark} />
        ))}
        <mesh position={[0, 2.0, 0.06]}>
          <planeGeometry args={[1.54, 0.92]} />
          <meshStandardMaterial color={PR.cushionCream} roughness={0.9} />
        </mesh>
        {/* mảng "tranh" trừu tượng deterministic: đồi + mặt trời */}
        <mesh position={[-0.2, 1.84, 0.085]}>
          <planeGeometry args={[1.0, 0.35]} />
          <meshStandardMaterial color={PR.fabricGreen} roughness={0.9} />
        </mesh>
        <mesh position={[0.4, 2.19, 0.085]}>
          <circleGeometry args={[0.14, 12]} />
          <meshBasicMaterial color={PR.bookGold} toneMapped={false} />
        </mesh>
      </group>
    </group>
  );
}

/** `below`: kệ sách gắn DƯỚI cửa sổ tường bắc (cửa lút vào tường,
 *  đỡ kệ cắm vào thân kệ — mặt nào chạm khít là nhấp nháy ở xa). */
function ShelfBelowWindow() {
  return (
    <group>
      <group position={[0, 0, -0.64]}>
        <WallWindow />
      </group>
      {/* kệ + 2 đỡ + 5 sách đứng (đáy lút mặt kệ) */}
      <Box size={[1.6, 0.07, 0.35]} at={[0, 0.78, -0.45]} color={PR.woodGold} />
      {[-0.6, 0.6].map((x) => (
        <Box key={x} size={[0.08, 0.26, 0.3]} at={[x, 0.53, -0.48]} color={PR.steelDark} />
      ))}
      {[-0.5, -0.28, -0.06, 0.16, 0.38].map((x, i) => (
        <Box
          key={x}
          size={[0.16, 0.32, 0.22]}
          at={[x, 0.845, -0.45]}
          color={[PR.bookRed, PR.bookBlue, PR.bookGreen, PR.bookGold, PR.bookRed][i]}
        />
      ))}
    </group>
  );
}

/** `beside`: chậu cây đặt CẠNH ghế đôi (đỉnh ghế 1.0). */
function PlantBesideChair() {
  return (
    <group>
      <Loveseat />
      <group position={[1.7, 0, 0.2]}>
        <PlantPot />
      </group>
    </group>
  );
}

/** `between`: cây Ở GIỮA hai ghế bành (đỉnh ghế 1.0). */
function PlantBetweenChairs() {
  return (
    <group>
      <group position={[-1.15, 0, 0]}>
        <Armchair />
      </group>
      <group position={[1.15, 0, 0]}>
        <Armchair />
      </group>
      <group position={[0, 0, 0.1]}>
        <PlantPot />
      </group>
    </group>
  );
}

/** `behind`: tủ đứng SAU bàn làm việc (nóc tủ 1.1). */
function CabinetBehindDesk() {
  return (
    <group>
      {/* bàn phía nam */}
      <group position={[0, 0, 1.3]}>
        <Box size={[0.06, 0.71, 0.8]} at={[-0.77, 0, 0]} color={PR.woodDark} />
        <Box size={[0.06, 0.71, 0.8]} at={[0.77, 0, 0]} color={PR.woodDark} />
        <Box size={[1.6, 0.08, 0.8]} at={[0, 0.7, 0]} color={PR.woodGold} />
        <Box size={[0.5, 0.26, 0.6]} at={[-0.45, 0.445, 0]} color={PR.woodDark} />
        <Box size={[0.35, 0.06, 0.25]} at={[0.3, 0.775, 0]} color={PR.bookBlue} />
        <mesh position={[0.55, 0.835, 0.15]} castShadow>
          <cylinderGeometry args={[0.05, 0.04, 0.12, 10]} />
          {paint(PR.fabricRed)}
        </mesh>
      </group>
      {/* tủ phía bắc */}
      <group position={[0, 0, -0.8]}>
        <Box size={[1.4, 1.1, 0.5]} at={[0, 0, 0]} color={PR.woodDark} />
        <Box size={[0.03, 0.9, 0.03]} at={[0, 0.08, 0.25]} color={PR.steelDark} />
        {[-0.35, 0.35].map((x) => (
          <mesh key={x} position={[x, 0.55, 0.27]}>
            <sphereGeometry args={[0.035, 8, 6]} />
            {paint(PR.steelDark)}
          </mesh>
        ))}
      </group>
    </group>
  );
}

/** `in front of`: thảm chùi TRƯỚC cửa đông (khung tới 2.5). */
function MatInFrontOfDoor() {
  return (
    <group>
      <group position={[2.6, 0, 0]}>
        <WallDoor facing="-x" />
      </group>
      {/* thảm chùi: 2 lớp nổi dần như thảm hotel */}
      <Box size={[0.9, 0.04, 1.3]} at={[1.2, 0, 0]} color={PR.fabricRed} />
      <Box size={[0.7, 0.03, 1.0]} at={[1.2, 0.035, 0]} color={PR.cushionCream} />
    </group>
  );
}

/** `across from`: sofa nhìn nam, TV ĐỐI DIỆN qua khoảng trống (đỉnh 1.45). */
function SofaAcrossFromTv() {
  return (
    <group>
      <group position={[0, 0, -1.2]}>
        <Loveseat />
      </group>
      <group position={[0, 0, 1.4]}>
        <Box size={[1.8, 0.5, 0.45]} at={[0, 0, 0]} color={PR.woodDark} />
        {/* màn lút 0.005 vào mặt kệ, mặt hình lồi tiếp 0.05 */}
        <Box size={[1.5, 0.95, 0.08]} at={[0, 0.495, 0]} color={PR.tvBlack} />
        <mesh position={[0, 0.97, -0.045]} rotation={[0, Math.PI, 0]}>
          <planeGeometry args={[1.38, 0.83]} />
          <meshBasicMaterial color={PR.screenGlow} toneMapped={false} />
        </mesh>
      </group>
    </group>
  );
}

/** `against`: giá sách cao DỰA tường bắc (nóc 2.2). */
function ShelfAgainstWall() {
  const bookColors = [PR.bookRed, PR.bookBlue, PR.bookGreen, PR.bookGold];
  return (
    <group>
      {[-0.87, 0.87].map((x) => (
        <Box key={x} size={[0.06, 2.2, 0.4]} at={[x, 0, -0.42]} color={PR.woodDark} />
      ))}
      <Box size={[1.78, 0.06, 0.4]} at={[0, 2.14, -0.42]} color={PR.woodDark} />
      <Box size={[1.78, 2.2, 0.04]} at={[0, 0, -0.6]} color={PR.woodDark} />
      {[0.5, 1.05, 1.6].map((y) => (
        <Box key={y} size={[1.68, 0.05, 0.36]} at={[0, y, -0.42]} color={PR.woodGold} />
      ))}
      {/* 3 tầng sách đứng, đáy lút mặt đợt */}
      {[0.545, 1.095, 1.645].map((y, r) =>
        [-0.6, -0.38, -0.16, 0.06, 0.28, 0.5].map((x, i) => (
          <Box
            key={`${r}${x}`}
            size={[0.16, 0.3, 0.24]}
            at={[x, y, -0.42]}
            color={bookColors[(i + r) % 4]}
          />
        )),
      )}
    </group>
  );
}

/** `around`: 4 ghế xếp XUNG QUANH bàn tròn (lưng ghế đỉnh 1.0). */
function ChairsAroundTable() {
  return (
    <group>
      {/* bàn tròn: chân + đế + mặt 0.72 */}
      <mesh position={[0, 0.33, 0]} castShadow>
        <cylinderGeometry args={[0.08, 0.08, 0.66, 10]} />
        {paint(PR.woodDark)}
      </mesh>
      <mesh position={[0, 0.025, 0]} castShadow>
        <cylinderGeometry args={[0.3, 0.34, 0.05, 12]} />
        {paint(PR.woodDark)}
      </mesh>
      <mesh position={[0, 0.685, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.85, 0.85, 0.06, 20]} />
        {paint(PR.woodGold)}
      </mesh>
      {/* ghế 4 hướng nhìn vào tâm: yaw từ hướng cần quay (§7.8) */}
      <group position={[0, 0, -1.55]}>
        <DiningChair />
      </group>
      <group position={[0, 0, 1.55]} rotation={[0, Math.PI, 0]}>
        <DiningChair />
      </group>
      <group position={[1.55, 0, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <DiningChair />
      </group>
      <group position={[-1.55, 0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <DiningChair />
      </group>
    </group>
  );
}

/** `on top of`: 3 thùng xếp CHỒNG lên nhau (nóc 1.79). */
function CratesOnTopOfEachOther() {
  return (
    <group>
      <Crate s={0.7} />
      <group position={[0.04, 0.69, -0.02]}>
        <Crate s={0.6} />
      </group>
      <group position={[-0.03, 1.28, 0.03]}>
        <Crate s={0.5} />
      </group>
    </group>
  );
}

/** `near`: giá treo áo đặt GẦN cửa nam (khung tới 2.5). */
function StandNearDoor() {
  return (
    <group>
      <group position={[-1.2, 0, 1.0]}>
        <WallDoor facing="-z" />
      </group>
      {/* giá treo: đế + trụ tới 1.8 + 4 móc + núm */}
      <group position={[1.5, 0, 0.4]}>
        <mesh position={[0, 0.025, 0]} castShadow>
          <cylinderGeometry args={[0.25, 0.28, 0.05, 12]} />
          {paint(PR.woodDark)}
        </mesh>
        <mesh position={[0, 0.9, 0]} castShadow>
          <cylinderGeometry args={[0.04, 0.04, 1.8, 8]} />
          {paint(PR.woodDark)}
        </mesh>
        {[0, Math.PI / 2, Math.PI, -Math.PI / 2].map((a) => (
          <group key={a} rotation={[0, a, 0]}>
            <Box size={[0.3, 0.05, 0.05]} at={[0.17, 1.58, 0]} color={PR.woodDark} />
          </group>
        ))}
        <mesh position={[0, 1.83, 0]}>
          <sphereGeometry args={[0.06, 8, 6]} />
          {paint(PR.woodGold)}
        </mesh>
      </group>
    </group>
  );
}

/** `in the middle of`: thảm tròn + bàn thấp Ở GIỮA khoảng trống (mặt 0.4). */
function RugInMiddleOfRoom() {
  return (
    <group>
      <mesh position={[0, 0.02, 0]} receiveShadow>
        <cylinderGeometry args={[1.3, 1.3, 0.04, 24]} />
        {paint(PR.fabricBlue)}
      </mesh>
      <mesh position={[0, 0.0475, 0]} receiveShadow>
        <cylinderGeometry args={[0.85, 0.85, 0.025, 24]} />
        {paint(PR.cushionCream)}
      </mesh>
      {/* bàn thấp giữa thảm */}
      <mesh position={[0, 0.2, 0]} castShadow>
        <cylinderGeometry args={[0.06, 0.06, 0.33, 10]} />
        {paint(PR.woodDark)}
      </mesh>
      <mesh position={[0, 0.35, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.55, 0.55, 0.05, 16]} />
        {paint(PR.woodGold)}
      </mesh>
      {/* tách trà trên bàn (đáy lút mặt bàn) */}
      <mesh position={[0.2, 0.43, 0.1]} castShadow>
        <cylinderGeometry args={[0.05, 0.04, 0.07, 10]} />
        {paint(PR.cushionCream)}
      </mesh>
    </group>
  );
}

/** Biển thương hiệu dán tường bắc đầu đông — mẫu tấm nhỏ indoor của hotel
 *  (Signboard 9.6 m không lọt phòng 3.4 m). Sau lưng thùng chồng, mặt +Z. */
function BrandPlateEast({ onPick }: { onPick?: (c: [number, number, number]) => void }) {
  const face = useSignFace();
  if (!onPick) return null;
  return (
    <group
      position={[10.9, 0, -8.82]}
      onClick={(e) => {
        e.stopPropagation();
        onPick([10.9, 2.25, -8.5]);
      }}
    >
      <Box size={[3.4, 1.7, 0.08]} at={[0, 1.4, 0]} color={PALETTE.wallTrim} />
      {face && (
        <mesh position={[0, 2.25, 0.065]}>
          <planeGeometry args={[3.3, 1.6]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

export function PositionsRoomEnvironment({
  onBrandPick,
}: {
  onBrandPick?: (c: [number, number, number]) => void;
}) {
  const floor = useMemo(() => {
    // Sàn gỗ sọc deterministic (không random — §8.7).
    const PPM = 32;
    const W = 26 * PPM;
    const H = 18 * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = PR.floorWood;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = PR.floorDark;
    for (let i = 0; i < 18; i += 2) ctx.fillRect(0, i * PPM, W, PPM);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    return tex;
  }, []);
  return (
    <group>
      {floor && (
        <mesh
          rotation={[-Math.PI / 2, 0, 0]}
          position={[0, 0, 0]}
          receiveShadow
          raycast={() => null}
        >
          <planeGeometry args={[26, 18]} />
          <meshStandardMaterial map={floor} roughness={0.9} />
        </mesh>
      )}
      {/* 4 tường khép kín (giao nhau khối, không đồng phẳng). Mặt nam là
          tường lửng 2 đoạn + cổng cửa full-height ôm khít khung cửa nam
          (mẫu hotel): tường nam đặc 3.4 m là che mất dải objects z 5.5..8.8
          (beside/adjacent/across-tv/near) khỏi home camera. */}
      <Box size={[26.6, 3.4, 0.3]} at={[0, 0, -9]} color={PR.wallWarm} />
      <Box size={[0.3, 3.4, 18.6]} at={[-13, 0, 0]} color={PR.wallWarm} />
      <Box size={[0.3, 3.4, 18.6]} at={[13, 0, 0]} color={PR.wallWarm} />
      <Box size={[2.0, 3.4, 0.3]} at={[-6.7, 0, 9]} color={PR.wallWarm} />
      {[
        [-10.35, 5.3],
        [3.65, 18.7],
      ].map(([x, w]) => (
        <group key={x}>
          <Box size={[w, 1.1, 0.2]} at={[x, 0, 9]} color={PR.wallWarm} />
          <Box size={[w, 0.08, 0.26]} at={[x, 1.1, 9]} color={PR.woodDark} />
        </group>
      ))}
      {/* nẹp chân tường cho đỡ trơ (đoạn nam chừa cổng cửa) */}
      <Box size={[26, 0.12, 0.06]} at={[0, 0, -8.82]} color={PR.woodDark} />
      <Box size={[5.3, 0.12, 0.06]} at={[-10.35, 0, 8.87]} color={PR.woodDark} />
      <Box size={[18.7, 0.12, 0.06]} at={[3.65, 0, 8.87]} color={PR.woodDark} />
      <BrandPlateEast onPick={onBrandPick} />
    </group>
  );
}

export const POSITIONS_SHAPES = {
  "pos-book-on-table": BookOnTable,
  "pos-crate-under-bench": CrateUnderBench,
  "pos-painting-above-sofa": PaintingAboveSofa,
  "pos-shelf-below-window": ShelfBelowWindow,
  "pos-plant-beside-chair": PlantBesideChair,
  "pos-plant-between-chairs": PlantBetweenChairs,
  "pos-cabinet-behind-desk": CabinetBehindDesk,
  "pos-mat-in-front-of-door": MatInFrontOfDoor,
  "pos-sofa-across-from-tv": SofaAcrossFromTv,
  "pos-shelf-against-wall": ShelfAgainstWall,
  "pos-chairs-around-table": ChairsAroundTable,
  "pos-crates-on-top-of-each-other": CratesOnTopOfEachOther,
  "pos-stand-near-door": StandNearDoor,
  "pos-rug-in-middle-of-room": RugInMiddleOfRoom,
  "pos-chair-next-to-table": ChairNextToTable,
  "pos-slippers-under-bed": SlippersUnderBed,
  "pos-chairs-opposite": ChairsOpposite,
  "pos-cabinet-adjacent-desk": CabinetAdjacentDesk,
  "pos-books-along-shelf": BooksAlongShelf,
  "pos-chairs-alongside-table": ChairsAlongsideTable,
  "pos-chair-facing-bookcase": ChairFacingBookcase,
  "pos-stairs-upstairs": StairsUpstairs,
  "pos-vase-inside-cabinet": VaseInsideCabinet,
  "pos-flowerbed-outside-fence": FlowerbedOutsideFence,
};

/* --- Đợt 2: 10 từ khó/hay gặp (giữ nguyên mọi quy ước đợt 1) --- */

/** `next to`: ghế đặt NGAY CẠNH bàn phụ (mặt ghế, đỉnh 1.0). */
function ChairNextToTable() {
  return (
    <group>
      {[-0.3, 0.3].map((x) =>
        [-0.3, 0.3].map((z) => (
          <Box key={`${x}${z}`} size={[0.07, 0.5, 0.07]} at={[x, 0, z]} color={PR.woodDark} />
        )),
      )}
      <Box size={[0.7, 0.06, 0.7]} at={[0, 0.49, 0]} color={PR.woodGold} />
      {/* ghế quay mặt vào bàn (yaw −π/2 đưa +Z thành −X — §7.8 tính hai đầu) */}
      <group position={[0.85, 0, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <DiningChair />
      </group>
    </group>
  );
}

/** `underneath`: dép lê lút dưới gầm giường (nệm đỉnh 0.62, gối 0.77). */
function SlippersUnderBed() {
  return (
    <group>
      {[-0.7, 0.7].map((x) =>
        [-1.0, 1.0].map((z) => (
          <Box key={`${x}${z}`} size={[0.1, 0.11, 0.1]} at={[x, 0, z]} color={PR.woodDark} />
        )),
      )}
      <Box size={[1.6, 0.3, 2.2]} at={[0, 0.1, 0]} color={PR.woodDark} />
      <Box size={[1.5, 0.22, 2.0]} at={[0, 0.395, 0]} color={PR.cushionCream} />
      {/* đầu giường cao phía bắc + gối lút vào nệm */}
      <Box size={[1.56, 1.0, 0.12]} at={[0, 0, -1.04]} color={PR.woodDark} />
      <Box size={[0.6, 0.15, 0.4]} at={[-0.35, 0.61, -0.7]} color={PR.paperWhite} />
      <Box size={[0.6, 0.15, 0.4]} at={[0.35, 0.61, -0.7]} color={PR.paperWhite} />
      {/* dép thò nửa ra ngoài gầm (nhìn từ nam là thấy ngay) */}
      {[-0.18, 0.18].map((x) => (
        <Box key={x} size={[0.13, 0.08, 0.32]} at={[x, 0, 1.06]} color={PR.fabricRed} />
      ))}
    </group>
  );
}

/** `opposite`: hai ghế bành ĐỐI DIỆN nhau (quay mặt vào nhau). */
function ChairsOpposite() {
  return (
    <group>
      <group position={[0, 0, -1.0]}>
        <Armchair />
      </group>
      <group position={[0, 0, 1.0]} rotation={[0, Math.PI, 0]}>
        <Armchair />
      </group>
      {/* thảm tròn mỏng ở giữa (decor phẳng, không nhãn) */}
      <mesh position={[0, 0.02, 0]} receiveShadow>
        <cylinderGeometry args={[0.9, 0.9, 0.04, 20]} />
        {paint(PR.fabricRed)}
      </mesh>
    </group>
  );
}

/** `adjacent to`: tủ SÁT CẠNH bàn (chạm nhau, khe hở 0 — khác `behind`). */
function CabinetAdjacentDesk() {
  return (
    <group>
      <group position={[-0.55, 0, 0]}>
        <Box size={[0.06, 0.71, 0.8]} at={[-0.77, 0, 0]} color={PR.woodDark} />
        <Box size={[0.06, 0.71, 0.8]} at={[0.77, 0, 0]} color={PR.woodDark} />
        <Box size={[1.6, 0.08, 0.8]} at={[0, 0.7, 0]} color={PR.woodGold} />
        <Box size={[0.35, 0.06, 0.25]} at={[-0.3, 0.775, 0]} color={PR.bookGreen} />
        <mesh position={[0.4, 0.835, 0.1]} castShadow>
          <cylinderGeometry args={[0.05, 0.04, 0.12, 10]} />
          {paint(PR.fabricBlue)}
        </mesh>
      </group>
      {/* tủ chạm mép bàn: tâm tủ = mép đông bàn + nửa rộng tủ */}
      <group position={[0.75, 0, 0]}>
        <Box size={[1.0, 1.1, 0.5]} at={[0, 0, 0]} color={PR.woodDark} />
        <Box size={[0.03, 0.9, 0.03]} at={[0, 0.08, 0.25]} color={PR.steelDark} />
        {[-0.25, 0.25].map((x) => (
          <mesh key={x} position={[x, 0.55, 0.27]}>
            <sphereGeometry args={[0.035, 8, 6]} />
            {paint(PR.steelDark)}
          </mesh>
        ))}
      </group>
    </group>
  );
}

/** `along`: sách xếp DỌC kệ thấp (đỉnh sách 0.875). */
function BooksAlongShelf() {
  const bookColors = [PR.bookRed, PR.bookBlue, PR.bookGreen, PR.bookGold];
  return (
    <group>
      {[-1.17, 1.17].map((x) => (
        <Box key={x} size={[0.06, 0.6, 0.4]} at={[x, 0, 0]} color={PR.woodDark} />
      ))}
      <Box size={[2.34, 0.06, 0.4]} at={[0, 0.54, 0]} color={PR.woodGold} />
      <Box size={[2.34, 0.08, 0.4]} at={[0, 0, 0]} color={PR.woodDark} />
      {/* 10 gáy sách dọc kệ + lọ cây chặn đầu */}
      {Array.from({ length: 10 }, (_, i) => (
        <Box
          key={i}
          size={[0.16, 0.3, 0.24]}
          at={[-0.85 + i * 0.18, 0.595, 0]}
          color={bookColors[i % 4]}
        />
      ))}
      <mesh position={[1.0, 0.68, 0]} castShadow>
        <cylinderGeometry args={[0.07, 0.09, 0.2, 8]} />
        {paint(PR.paperWhite)}
      </mesh>
      <mesh position={[1.0, 0.83, 0]} castShadow>
        <coneGeometry args={[0.13, 0.25, 8]} />
        {paint(PR.plantGreen)}
      </mesh>
    </group>
  );
}

/** `alongside`: hai ghế DỌC MỘT BÊN bàn dài (cùng nhìn vào bàn). */
function ChairsAlongsideTable() {
  return (
    <group>
      {[-1.0, 1.0].map((x) =>
        [-0.28, 0.28].map((z) => (
          <Box key={`${x}${z}`} size={[0.08, 0.69, 0.08]} at={[x, 0, z]} color={PR.woodDark} />
        )),
      )}
      <Box size={[2.2, 0.08, 0.7]} at={[0, 0.68, 0]} color={PR.woodGold} />
      {[-0.55, 0.55].map((x) => (
        <group key={x} position={[x, 0, 0.85]} rotation={[0, Math.PI, 0]}>
          <DiningChair />
        </group>
      ))}
    </group>
  );
}

/** `facing`: ghế bành HƯỚNG MẶT về tủ sách thấp (cách 1 m). */
function ChairFacingBookcase() {
  const bookColors = [PR.bookBlue, PR.bookGold, PR.bookRed, PR.bookGreen];
  return (
    <group>
      {/* yaw π/2 đưa +Z thành +X: ghế nhìn đông về tủ */}
      <group rotation={[0, Math.PI / 2, 0]}>
        <Armchair />
      </group>
      <group position={[1.6, 0, 0]}>
        {[-0.57, 0.57].map((x) => (
          <Box key={x} size={[0.06, 1.0, 0.35]} at={[x, 0, 0]} color={PR.woodDark} />
        ))}
        <Box size={[1.14, 0.06, 0.35]} at={[0, 0.94, 0]} color={PR.woodDark} />
        <Box size={[1.08, 0.05, 0.32]} at={[0, 0.45, 0]} color={PR.woodGold} />
        {[0.0, 0.495].map((y, r) =>
          [-0.36, -0.18, 0, 0.18, 0.36].map((x, i) => (
            <Box
              key={`${r}${x}`}
              size={[0.14, 0.26, 0.22]}
              at={[x, y, 0]}
              color={bookColors[(i + r) % 4]}
            />
          )),
        )}
      </group>
    </group>
  );
}

/** `upstairs`: cầu thang 6 bậc lên tầng (đỉnh lan can 2.84). */
function StairsUpstairs() {
  return (
    <group>
      {/* 6 khối đặc leo dần về đông: bậc i mặt trên ở 0.3·(i+1) */}
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Box
          key={i}
          size={[0.5, 0.3 * (i + 1), 1.2]}
          at={[-1.5 + i * 0.5, 0, 0]}
          color={i % 2 ? PR.floorWood : PR.floorDark}
        />
      ))}
      {/* chiếu nghỉ trên cùng (mép khít bậc cuối, không chồng mặt) */}
      <Box size={[0.6, 1.8, 1.2]} at={[1.55, 0, 0]} color={PR.floorWood} />
      {/* lan can nam: 3 trụ lút vào mặt bậc + thanh chéo qua 2 đầu mút
          (0.1, 1.3) → (3.1, 2.8): dài 3.35, góc atan2(1.5, 3.0) = 0.464 */}
      {[
        [0.1, 0.295],
        [1.6, 1.195],
        [3.1, 1.795],
      ].map(([x, base], i) => (
        <Box key={i} size={[0.08, 1.0, 0.08]} at={[x - 1.6, base, 0.56]} color={PR.woodDark} />
      ))}
      <mesh position={[0.0, 2.05, 0.56]} rotation={[0, 0, 0.464]} castShadow>
        <boxGeometry args={[3.35, 0.08, 0.08]} />
        {paint(PR.woodDark)}
      </mesh>
    </group>
  );
}

/** `inside`: bình đứng BÊN TRONG tủ mở cửa (cánh mở vuông góc). */
function VaseInsideCabinet() {
  return (
    <group>
      <Box size={[1.14, 0.06, 0.5]} at={[0, 1.04, 0]} color={PR.woodDark} />
      <Box size={[1.14, 0.06, 0.5]} at={[0, 0, 0]} color={PR.woodDark} />
      {[-0.57, 0.57].map((x) => (
        <Box key={x} size={[0.06, 1.1, 0.5]} at={[x, 0, 0]} color={PR.woodDark} />
      ))}
      <Box size={[1.14, 1.1, 0.04]} at={[0, 0, -0.23]} color={PR.woodDark} />
      <Box size={[1.08, 0.05, 0.44]} at={[0, 0.5, 0]} color={PR.woodGold} />
      {/* bình trên đợt giữa: thân + cổ + miệng */}
      <mesh position={[0.15, 0.68, 0]} castShadow>
        <cylinderGeometry args={[0.11, 0.13, 0.3, 12]} />
        {paint(PR.fabricBlue)}
      </mesh>
      <mesh position={[0.15, 0.88, 0]} castShadow>
        <cylinderGeometry args={[0.05, 0.07, 0.12, 10]} />
        {paint(PR.fabricBlue)}
      </mesh>
      {/* cánh phải mở ra trước: bản lề mép đông, xoay +108° đưa cánh từ
          −X ra +Z (tính hai đầu: (−cosθ, sinθ) với θ = 1.89) */}
      <group position={[0.57, 0, 0.25]} rotation={[0, 1.89, 0]}>
        <Box size={[0.54, 1.0, 0.05]} at={[-0.27, 0.05, 0]} color={PR.woodGold} />
        <mesh position={[-0.27, 0.55, 0.04]}>
          <sphereGeometry args={[0.035, 8, 6]} />
          {paint(PR.steelDark)}
        </mesh>
      </group>
    </group>
  );
}

/** `outside`: luống hoa trồng BÊN NGOÀI hàng rào trắng (đỉnh cọc 1.0). */
function FlowerbedOutsideFence() {
  return (
    <group>
      {/* hàng rào dọc X: 2 thanh + 7 cọc + 2 trụ */}
      {[0.35, 0.7].map((y) => (
        <Box key={y} size={[2.6, 0.08, 0.05]} at={[0, y, 0]} color={PR.paperWhite} />
      ))}
      {[-1.2, -0.8, -0.4, 0, 0.4, 0.8, 1.2].map((x) => (
        <Box key={x} size={[0.09, 0.9, 0.04]} at={[x, 0, 0.02]} color={PR.paperWhite} />
      ))}
      {[-1.32, 1.32].map((x) => (
        <Box key={x} size={[0.12, 1.0, 0.12]} at={[x, 0, 0]} color={PR.paperWhite} />
      ))}
      {/* luống đất + 5 khóm hoa phía ngoài (local +Z) */}
      <Box size={[2.4, 0.15, 0.5]} at={[0, 0, 0.75]} color={PR.woodDark} />
      {[-0.9, -0.45, 0, 0.45, 0.9].map((x, i) => (
        <group key={x} position={[x, 0.15, 0.75]}>
          <mesh position={[0, 0.145, 0]} castShadow>
            <cylinderGeometry args={[0.02, 0.02, 0.3, 6]} />
            {paint(PR.plantGreen)}
          </mesh>
          <mesh position={[0, 0.34, 0]} castShadow>
            <sphereGeometry args={[0.08, 8, 6]} />
            {paint([PR.fabricRed, PR.bookGold, PR.cushionCream][i % 3])}
          </mesh>
        </group>
      ))}
    </group>
  );
}
