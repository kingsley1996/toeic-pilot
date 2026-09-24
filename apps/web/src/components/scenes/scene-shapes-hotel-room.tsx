import { useMemo } from "react";
import * as THREE from "three";

import { Box, PALETTE, paint, useSignFace } from "@/components/scenes/scene-shapes";

/**
 * Phòng khách sạn (topic `hotel`, 18 từ: 15 nhập mới qua pipeline + 3 nối từ
 * housing/travel — balcony, curtain, baggage). Làm lại từ sảnh thất bại: sảnh
 * ép từ trừu tượng (reservation, vacancy...) khó hình dung; phòng toàn đồ vật
 * cụ thể, nhìn là biết. Quy ước indoor như mọi cảnh: `Box` gốc chân, chữ
 * canvas offline, mặt phủ cách nhau ≥ 0.02.
 *
 * Bố cục: phòng ngủ tây (giường dọc Z đầu bắc) + phòng tắm kính đông-nam +
 * ban công ngoài tường bắc. Gối nằm TRÊN giường như grill/chef cùng X tách
 * đứng — probe quyết định có giữ được không.
 */

const HR = {
  floorWood: "#b08a5a",
  floorDark: "#96754c",
  wallCream: "#ece5d8",
  woodDark: "#6e4f2e",
  woodGold: "#a8814a",
  sheetWhite: "#f2f3f4",
  blanketBlue: "#3b6ea5",
  pillowWhite: "#f7f5ef",
  tubWhite: "#eef1f3",
  steelChrome: "#aab2b9",
  waterBlue: "#7fb3c8",
  glassBlue: "#9fc0d2",
  tvBlack: "#1d2530",
  screenGlow: "#2e4a5a",
  plantGreen: "#5f8a52",
} as const;

/** Giường đôi dọc Z đầu bắc: khung + chân + đầu giường + nệm + ga. */
function BedFrame() {
  return (
    <group>
      {/* 4 chân + khung (đáy khung ngồi trên chân, không lơ lửng) */}
      {[-1.45, 1.45].map((x) =>
        [-1.95, 1.95].map((z) => (
          <Box key={`${x}${z}`} size={[0.15, 0.15, 0.15]} at={[x, 0, z]} color={HR.woodDark} />
        )),
      )}
      <Box size={[3.2, 0.35, 4.2]} at={[0, 0.15, 0]} color={HR.woodDark} />
      {/* đầu giường cao tựa bắc (−Z), chân chạm đất */}
      <Box size={[3.2, 1.3, 0.18]} at={[0, 0, -2.05]} color={HR.woodDark} />
      {/* nệm + ga phủ (mặt nào cũng lút 0.005, không đồng phẳng) */}
      <Box size={[3.0, 0.3, 4.0]} at={[0, 0.495, 0]} color={HR.sheetWhite} />
      <Box size={[3.02, 0.08, 2.2]} at={[0, 0.79, 0.9]} color={HR.blanketBlue} />
    </group>
  );
}

/** Cặp gối TRÊN nệm gần đầu giường (world z ≈ −4.6, đáy lút vào nệm). */
function PillowPair() {
  return (
    <group>
      {[-0.8, 0.8].map((x) => (
        <group key={x} position={[x, 0.79, 0]}>
          <Box size={[0.9, 0.22, 0.6]} at={[-0.45, 0, -0.3]} color={HR.pillowWhite} />
          {/* viền gối lồi 4 mặt */}
          <Box size={[0.94, 0.06, 0.64]} at={[-0.47, 0.08, -0.32]} color={HR.sheetWhite} />
        </group>
      ))}
    </group>
  );
}

/** Băng ghế cuối giường + chăn gấp 3 lớp + chân. */
function BlanketBench() {
  return (
    <group>
      {[-1.0, 1.0].map((x) =>
        [-0.25, 0.25].map((z) => (
          <Box key={`${x}${z}`} size={[0.1, 0.1, 0.1]} at={[x, 0, z]} color={HR.woodDark} />
        )),
      )}
      <Box size={[2.4, 0.35, 0.7]} at={[0, 0.1, 0]} color={HR.woodDark} />
      {/* chăn gấp 3 lớp so le, lớp nào cũng lút vào lớp dưới */}
      <Box size={[1.8, 0.12, 0.6]} at={[0, 0.445, 0]} color={HR.blanketBlue} />
      <Box size={[1.7, 0.12, 0.55]} at={[0.03, 0.56, 0]} color={HR.sheetWhite} />
      <Box size={[1.6, 0.12, 0.5]} at={[-0.03, 0.67, 0]} color={HR.blanketBlue} />
    </group>
  );
}

/** Tủ đầu giường + đồng hồ báo thức mặt đứng (thân xoay trục Z, mặt +Z). */
function AlarmClock() {
  return (
    <group>
      <Box size={[0.9, 0.55, 0.7]} at={[0, 0, 0]} color={HR.woodDark} />
      <Box size={[1.0, 0.05, 0.8]} at={[0, 0.545, 0]} color={HR.sheetWhite} />
      {/* đế đồng hồ: đáy lút mặt tủ, đỉnh lút thân */}
      <Box size={[0.2, 0.22, 0.12]} at={[0, 0.59, 0.1]} color={PALETTE.steelDark} />
      {/* thân đứng (xoay X 90° cho trục ra +Z), mặt + kim nổi dần ra trước */}
      <mesh position={[0, 0.85, 0.1]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.16, 0.1, 14]} />
        {paint(HR.sheetWhite)}
      </mesh>
      <mesh position={[0, 0.85, 0.17]}>
        <circleGeometry args={[0.13, 14]} />
        <meshBasicMaterial color={HR.tvBlack} toneMapped={false} />
      </mesh>
      {/* kim giờ + kim phút */}
      <Box size={[0.02, 0.07, 0.01]} at={[0, 0.86, 0.19]} color={HR.sheetWhite} />
      <Box size={[0.05, 0.02, 0.01]} at={[0.01, 0.85, 0.19]} color={HR.sheetWhite} />
      {/* 2 chuông trên đỉnh */}
      {[-0.1, 0.1].map((x) => (
        <mesh key={x} position={[x, 1.04, 0.1]}>
          <sphereGeometry args={[0.05, 8, 6]} />
          {paint(HR.steelChrome)}
        </mesh>
      ))}
    </group>
  );
}

/** TV lớn đối diện giường: màn NGỒI TRỰC TIẾP lên tủ (kiểu TV đặt trên tủ
 *  khách sạn — không chân, không cổ, không khe hở thì không có gì để lơ
 *  lửng/trượt/lệch). Màn thụt đều 0.1 mỗi bên so với tủ nên trước sau đều
 *  cân. Xoay π ngoài def giữ trục thẳng. */
function TvSet() {
  return (
    <group>
      <Box size={[2.0, 0.55, 0.8]} at={[0, 0, 0]} color={HR.woodDark} />
      {/* remote (đáy lút 0.01) */}
      <Box size={[0.08, 0.03, 0.25]} at={[0.7, 0.54, 0.2]} color={PALETTE.steelDark} />
      {/* màn ngồi lút 0.005 vào mặt tủ */}
      <Box size={[1.8, 1.3, 0.12]} at={[0, 0.545, 0]} color={HR.tvBlack} />
      <mesh position={[0, 1.195, 0.08]}>
        <planeGeometry args={[1.68, 1.18]} />
        <meshBasicMaterial color={HR.screenGlow} toneMapped={false} />
      </mesh>
    </group>
  );
}

/** Điều hòa treo tường: thân + cánh gió mở + đèn. */
function AirconWall() {
  return (
    <group>
      <Box size={[1.6, 0.45, 0.3]} at={[0, 2.3, 0]} color={HR.sheetWhite} />
      {/* cánh gió mở chĩa xuống */}
      <group position={[0, 2.3, 0.14]} rotation={[0.7, 0, 0]}>
        <Box size={[1.4, 0.04, 0.35]} at={[0, -0.17, 0]} color={HR.steelChrome} />
      </group>
      {/* vệt gió: 3 đường mờ dưới cánh */}
      {[-0.4, 0, 0.4].map((x) => (
        <mesh key={x} position={[x, 1.95, 0.3]}>
          <planeGeometry args={[0.08, 0.4]} />
          <meshBasicMaterial color={HR.waterBlue} transparent opacity={0.5} toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[0.6, 2.32, 0.16]}>
        <sphereGeometry args={[0.03, 8, 6]} />
        <meshBasicMaterial color={PALETTE.lampGreen} toneMapped={false} />
      </mesh>
    </group>
  );
}

/** Tủ quần áo 2 cánh + tay nắm. */
function ClosetWardrobe() {
  return (
    <group>
      <Box size={[2.4, 2.2, 0.9]} at={[0, 0, 0]} color={HR.woodDark} />
      <Box size={[0.04, 2.0, 0.06]} at={[0, 0.05, 0.45]} color={PALETTE.steelDark} />
      {[-0.2, 0.2].map((x) => (
        <mesh key={x} position={[x, 1.2, 0.48]}>
          <sphereGeometry args={[0.045, 8, 6]} />
          {paint(HR.steelChrome)}
        </mesh>
      ))}
      {/* nóc tủ (đáy lút thân) */}
      <Box size={[2.5, 0.08, 1.0]} at={[0, 2.19, 0]} color={HR.woodDark} />
    </group>
  );
}

/** Giá treo di động + 3 móc áo có đồ. */
function HangerRack() {
  return (
    <group>
      {[-0.7, 0.7].map((x) => (
        <Box key={x} size={[0.08, 1.6, 0.5]} at={[x, 0, 0]} color={HR.steelChrome} />
      ))}
      <mesh position={[0, 1.62, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.04, 0.04, 1.5, 8]} />
        {paint(HR.steelChrome)}
      </mesh>
      {/* 3 móc áo: tam giác + áo choàng (màu literal theo ghế, không hằng
          lạ — hằng không tồn tại là tsc kêu) */}
      {[-0.45, 0, 0.45].map((x, i) => (
        <group key={x}>
          <Box size={[0.04, 0.12, 0.04]} at={[x, 1.62, 0]} color={PALETTE.steelDark} />
          <Box size={[0.4, 0.04, 0.04]} at={[x, 1.5, 0]} color={PALETTE.steelDark} />
          <Box
            size={[0.34, 0.55, 0.22]}
            at={[x, 0.95, 0]}
            color={[HR.blanketBlue, HR_RED, HR.sheetWhite][i]}
          />
        </group>
      ))}
    </group>
  );
}

const HR_RED = "#a83c3c";

/** Két sắt trên kệ thấp + bàn phím + tay xoay. */
function SafeBox() {
  return (
    <group>
      <Box size={[0.9, 0.4, 0.6]} at={[0, 0, 0]} color={HR.woodDark} />
      <Box size={[0.7, 0.55, 0.5]} at={[0, 0.395, 0]} color={PALETTE.steelDark} />
      {/* cửa két + tay xoay + phím (mặt nào cũng lút, không đồng phẳng) */}
      <Box size={[0.6, 0.45, 0.04]} at={[0, 0.45, 0.26]} color={PALETTE.steel} />
      <mesh position={[-0.15, 0.45, 0.29]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.05, 0.05, 0.05, 10]} />
        {paint(PALETTE.tire)}
      </mesh>
      {[
        [0.1, 0.55],
        [0.18, 0.55],
        [0.1, 0.47],
        [0.18, 0.47],
      ].map(([x, y], i) => (
        <mesh key={i} position={[x, y, 0.28]}>
          <boxGeometry args={[0.05, 0.05, 0.02]} />
          <meshBasicMaterial color={PALETTE.lampGreen} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

/** Chữ lên biển nhỏ: canvas offline (file phòng không có helper riêng nên
 *  viết tại chỗ, 1 hàm dùng 1 lần — khỏi dựng hạ tầng textPanel thứ hai). */
function hotelPanel(
  lines: { text: string; size: number; color: string; bold?: boolean }[],
  w = 512,
  h = 128,
  bg = "#1d2530",
) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);
  ctx.textBaseline = "middle";
  ctx.fillStyle = lines[0].color;
  ctx.font = `700 ${lines[0].size}px system-ui, sans-serif`;
  ctx.fillText(lines[0].text, 28, h / 2);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

/** Tủ lạnh mini LỚN: hốc mở lộ chai + cửa kính MỞ + biển MINIBAR.
 *  Bản cửa kính dán trước thùng đặc: chai chìm trong thân, nhìn xuyên kính
 *  chỉ thấy mặt thùng đen — sai mà vẫn ra hình. */
function MinibarFridge() {
  const face = useMemo(
    () => hotelPanel([{ text: "MINIBAR", size: 72, color: "#ffffff", bold: true }]),
    [],
  );
  return (
    <group>
      {/* vỏ hốc: lưng + 2 hông + nóc + đáy (mặt trước mở) */}
      <Box size={[1.4, 1.1, 0.1]} at={[0, 0, -0.3]} color={HR.tvBlack} />
      {[-0.65, 0.65].map((x) => (
        <Box key={x} size={[0.1, 1.1, 0.7]} at={[x, 0, 0]} color={HR.tvBlack} />
      ))}
      <Box size={[1.4, 0.1, 0.7]} at={[0, 1.05, 0]} color={HR.tvBlack} />
      <Box size={[1.4, 0.1, 0.7]} at={[0, 0, 0]} color={HR.tvBlack} />
      {/* 3 chai trong hốc, đáy lút đáy hốc */}
      {[-0.32, 0, 0.32].map((x) => (
        <mesh key={x} position={[x, 0.295, 0.08]} castShadow>
          <cylinderGeometry args={[0.09, 0.09, 0.4, 8]} />
          {paint([HR.waterBlue, HR_RED, HR.sheetWhite][Math.abs(Math.round(x * 3)) % 3])}
        </mesh>
      ))}
      {/* đèn hốc */}
      <mesh position={[0, 1.0, 0.1]}>
        <boxGeometry args={[1.0, 0.04, 0.04]} />
        <meshBasicMaterial color={HR.sheetWhite} toneMapped={false} />
      </mesh>
      {/* cửa kính MỞ (bản lề cạnh phải, xoay ra 63°) */}
      <group position={[0.7, 0, 0.35]} rotation={[0, 1.1, 0]}>
        <mesh position={[0, 0.55, 0.32]} raycast={() => null}>
          <boxGeometry args={[0.02, 1.0, 0.6]} />
          <meshStandardMaterial color={HR.glassBlue} transparent opacity={0.35} />
        </mesh>
      </group>
      {/* nắp trắng + biển tên mặt trước */}
      <Box size={[1.45, 0.1, 0.75]} at={[0, 1.15, 0]} color={HR.sheetWhite} />
      <Box size={[1.2, 0.2, 0.04]} at={[0, 1.1, 0.38]} color={HR.tvBlack} />
      {face && (
        <mesh position={[0, 1.1, 0.42]}>
          <planeGeometry args={[1.1, 0.16]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Khay trà: bàn nhỏ + ấm + 2 tách + hộp trà. */
function KettleTray() {
  return (
    <group>
      <Box size={[1.2, 0.5, 0.7]} at={[0, 0, 0]} color={HR.woodDark} />
      <Box size={[1.3, 0.05, 0.8]} at={[0, 0.5, 0]} color={HR.sheetWhite} />
      {/* ấm: thân ngồi lút vào khay + vòi + quai gắn thân */}
      <mesh position={[-0.25, 0.68, 0]} castShadow>
        <cylinderGeometry args={[0.13, 0.16, 0.28, 10]} />
        {paint(HR.steelChrome)}
      </mesh>
      <Box size={[0.16, 0.04, 0.05]} at={[-0.05, 0.78, 0]} color={HR.steelChrome} />
      <Box size={[0.04, 0.16, 0.05]} at={[-0.42, 0.75, 0]} color={HR.steelChrome} />
      {/* 2 tách (đáy lút khay) */}
      {[-0.05, 0.2].map((x) => (
        <mesh key={x} position={[x, 0.59, 0.15]} castShadow>
          <cylinderGeometry args={[0.06, 0.045, 0.09, 8]} />
          {paint(HR.sheetWhite)}
        </mesh>
      ))}
      <Box size={[0.25, 0.18, 0.15]} at={[0.35, 0.545, -0.15]} color={HR_RED} />
    </group>
  );
}

/** Giá treo khăn + 2 khăn vắt. */
function TowelRack() {
  return (
    <group>
      {[-0.5, 0.5].map((x) => (
        <Box key={x} size={[0.07, 1.3, 0.07]} at={[x, 0, 0]} color={HR.steelChrome} />
      ))}
      <mesh position={[0, 1.32, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.035, 0.035, 1.1, 8]} />
        {paint(HR.steelChrome)}
      </mesh>
      {/* khăn vắt qua thanh: đỉnh lút vào thanh, 2 mảnh trước-sau */}
      {[-0.25, 0.25].map((x, i) => (
        <group key={x}>
          <Box
            size={[0.34, 0.62, 0.05]}
            at={[x, 1.0, 0.05]}
            color={i === 0 ? HR.sheetWhite : HR.waterBlue}
          />
          <Box
            size={[0.34, 0.5, 0.05]}
            at={[x, 1.06, -0.05]}
            color={i === 0 ? HR.sheetWhite : HR.waterBlue}
          />
        </group>
      ))}
    </group>
  );
}

/** Bồn tắm RỖNG giữa: vành 4 cạnh + mặt nước thấp dưới miệng. Bản cũ lót
 *  đặc cả lòng bồn (nhìn như khối xanh đặc) — sai mà vẫn ra hình. */
function BathtubTub() {
  return (
    <group>
      {/* đáy bồn */}
      <Box size={[2.2, 0.45, 1.2]} at={[0, 0.1, 0]} color={HR.tubWhite} />
      {/* vành 4 cạnh lên 0.75 */}
      {[0.525, -0.525].map((z) => (
        <Box key={z} size={[2.2, 0.2, 0.15]} at={[0, 0.545, z]} color={HR.tubWhite} />
      ))}
      {[-1.025, 1.025].map((x) => (
        <Box key={x} size={[0.15, 0.2, 0.9]} at={[x, 0.545, 0]} color={HR.tubWhite} />
      ))}
      {/* mặt nước thấp dưới miệng 0.17 */}
      <mesh position={[0, 0.58, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.9, 0.9]} />
        <meshStandardMaterial color={HR.waterBlue} />
      </mesh>
      {/* vòi + 2 núm trên vành tây */}
      <mesh position={[-0.9, 0.8, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.05, 0.05, 0.3, 8]} />
        {paint(HR.steelChrome)}
      </mesh>
      <Box size={[0.05, 0.2, 0.12]} at={[-1.0, 0.65, 0]} color={HR.steelChrome} />
      {[-0.25, 0.25].map((z) => (
        <mesh key={z} position={[-1.0, 0.78, z]}>
          <sphereGeometry args={[0.045, 8, 6]} />
          {paint(HR.steelChrome)}
        </mesh>
      ))}
    </group>
  );
}

/** Buồng sen: khay + cột + bát sen + tay nắm. */
function ShowerStall() {
  return (
    <group>
      <Box size={[1.0, 0.12, 1.0]} at={[0, 0, 0]} color={HR.tubWhite} />
      {/* cột sen áp góc (chân lút khay) */}
      <Box size={[0.08, 2.0, 0.08]} at={[-0.4, 0.11, -0.4]} color={HR.steelChrome} />
      {/* bát sen nghiêng + tia nước chạm bát */}
      <group position={[-0.25, 2.05, -0.25]} rotation={[0.5, 0, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.14, 0.05, 0.1, 10]} />
          {paint(HR.steelChrome)}
        </mesh>
      </group>
      <mesh position={[-0.25, 1.7, -0.12]}>
        <planeGeometry args={[0.2, 0.7]} />
        <meshBasicMaterial color={HR.waterBlue} transparent opacity={0.4} toneMapped={false} />
      </mesh>
      {/* tay vịn nối từ cột (tay lơ lửng giữa không là hỏng im lặng) */}
      <Box size={[0.05, 0.05, 0.8]} at={[-0.4, 1.0, 0]} color={HR.steelChrome} />
    </group>
  );
}

/** Cửa ban công: vách kính trượt KHUNG NHÔM MẢNH ngay giữa cửa mở tường bắc
 *  (nhìn xuyên ra lan can + trời) + tay nắm dọc + bàn cây ngoài ban công.
 *  Bản khung gỗ dày đặc thanh là một rừng gậy khó hiểu — vách kính hiện đại
 *  chỉ cần ray + đố biên + đố giữa. */
function BalconyDoor() {
  return (
    <group>
      {/* ray trên/dưới + 2 ĐỐ BIÊN GỖ ăn vào mép cửa tường (không phải nhôm
          mảnh tàng hình — vách phải thấy chỗ bám vào tường) */}
      <Box size={[2.8, 0.1, 0.14]} at={[0, 2.45, 0]} color={PALETTE.steelDark} />
      <Box size={[2.8, 0.06, 0.18]} at={[0, 0.03, 0]} color={PALETTE.steelDark} />
      {[-1.36, 1.36].map((x) => (
        <Box key={x} size={[0.16, 2.6, 0.2]} at={[x, 0, -0.02]} color={HR.woodDark} />
      ))}
      {/* 2 tấm kính trượt chồng giữa (trong, nhìn xuyên ra ngoài) */}
      {[
        { x: -0.33, z: -0.04 },
        { x: 0.33, z: 0.06 },
      ].map((p, i) => (
        <group key={i}>
          <mesh position={[p.x, 0.1, p.z]} raycast={() => null}>
            <boxGeometry args={[1.32, 2.35, 0.03]} />
            <meshStandardMaterial color={HR.glassBlue} transparent opacity={0.15} />
          </mesh>
          {/* đố giữa 2 tấm */}
          <Box
            size={[0.07, 2.35, 0.07]}
            at={[p.x + (i === 0 ? 0.62 : -0.62), 0.1, p.z]}
            color={PALETTE.steelDark}
          />
          {/* tay nắm dọc */}
          <Box
            size={[0.05, 0.5, 0.05]}
            at={[p.x + (i === 0 ? 0.45 : -0.45), 1.0, p.z + 0.08]}
            color={PALETTE.steelDark}
          />
        </group>
      ))}
      {/* ngoài ban công: lan can TRẮNG mép sân + 2 tay HỒI nối vào tường
          (lan can cụt 2 đầu giữa sân là sai) + bàn tròn + chậu cây */}
      {[-1.6, -0.5, 0.5, 1.6].map((x) => (
        <Box key={x} size={[0.08, 1.0, 0.08]} at={[x, -0.015, -3.5]} color={HR.sheetWhite} />
      ))}
      <Box size={[3.4, 0.08, 0.08]} at={[0, 0.95, -3.5]} color={HR.sheetWhite} />
      {/* tay hồi 2 bên: từ đầu lan can đâm vào mặt tường (đầu sau lút tường) */}
      {[-1.7, 1.7].map((x) => (
        <group key={x}>
          <Box size={[0.08, 0.08, 3.5]} at={[x, 0.95, -1.75]} color={HR.sheetWhite} />
          <Box size={[0.08, 1.0, 0.08]} at={[x, -0.015, -1.75]} color={HR.sheetWhite} />
        </group>
      ))}
      <mesh position={[1.9, 0.45, -3.2]} castShadow>
        <cylinderGeometry args={[0.4, 0.4, 0.05, 12]} />
        {paint(HR.woodDark)}
      </mesh>
      <Box size={[0.08, 0.45, 0.08]} at={[1.9, -0.01, -3.2]} color={PALETTE.steelDark} />
      <group position={[-1.9, 0, -3.4]}>
        <mesh position={[0, 0.19, 0]} castShadow>
          <cylinderGeometry args={[0.22, 0.17, 0.4, 10]} />
          {paint(HR.tubWhite)}
        </mesh>
        <mesh position={[0, 0.7, 0]} castShadow>
          <coneGeometry args={[0.32, 0.65, 8]} />
          {paint(HR.plantGreen)}
        </mesh>
      </group>
    </group>
  );
}

/** Cặp rèm 2 bên cửa ban công: thanh + vải gấp sóng. */
function CurtainPair() {
  return (
    <group>
      <mesh position={[0, 2.55, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.04, 0.04, 3.6, 8]} />
        {paint(HR.woodGold)}
      </mesh>
      {[-1.35, 1.35].map((x) => (
        <group key={x}>
          {/* 3 nếp gấp so le đọc ra vải rèm — chân chạm đất, đỉnh lút thanh */}
          {[-0.12, 0, 0.12].map((dz, i) => (
            <Box
              key={i}
              size={[0.5, 2.55, 0.09]}
              at={[x, 0, dz * (i % 2 === 0 ? 1 : 0.4)]}
              color={HR.blanketBlue}
            />
          ))}
          {/* dây buộc giữa */}
          <Box size={[0.56, 0.08, 0.3]} at={[x, 1.0, 0]} color={HR.woodGold} />
        </group>
      ))}
    </group>
  );
}

/** Giá hành lý: 4 chân đứng chắc (chân X chéo cũ mỏng manh) + mặt giá +
 *  2 vali đáy lút. */
function BaggageRack() {
  return (
    <group>
      {[-0.5, 0.5].map((x) =>
        [-0.3, 0.3].map((z) => (
          <Box key={`${x}${z}`} size={[0.06, 0.48, 0.06]} at={[x, 0, z]} color={HR.woodDark} />
        )),
      )}
      <Box size={[1.1, 0.06, 0.7]} at={[0, 0.475, 0]} color={HR.woodDark} />
      {/* 2 vali đứng trên giá (đáy lút mặt giá) + quai lút nóc vali */}
      <Box size={[0.45, 0.62, 0.25]} at={[-0.25, 0.53, 0]} color={HR_RED} />
      <Box size={[0.45, 0.55, 0.25]} at={[0.28, 0.53, 0]} color={HR.blanketBlue} />
      <Box size={[0.14, 0.05, 0.05]} at={[-0.25, 1.14, 0]} color={PALETTE.steelDark} />
      <Box size={[0.14, 0.05, 0.05]} at={[0.28, 1.07, 0]} color={PALETTE.steelDark} />
    </group>
  );
}

/** Logo dán tường bắc (mặt +Z về camera) — lệch đông cho khỏi điều hòa. */
function BrandPlateNorth({ onPick }: { onPick?: (c: [number, number, number]) => void }) {
  const face = useSignFace();
  if (!onPick) return null;
  return (
    <group
      position={[2.5, 0, -8.83]}
      onClick={(e) => {
        e.stopPropagation();
        onPick([2.5, 2.0, -8.5]);
      }}
    >
      <Box size={[3.7, 1.9, 0.08]} at={[0, 1.05, 0]} color={PALETTE.wallTrim} />
      {face && (
        <mesh position={[0, 2.0, 0.06]}>
          <planeGeometry args={[3.6, 1.8]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Tủ vách ngăn (decor): kệ gỗ thoáng tách khu giường với giữa phòng.
 *  Dài 6 m (z −5..1), cách giường 3.4 m — ngăn thật mà vẫn thoáng.
 *  Cao 1.8 — camera home cao nhìn qua được, không che giường (tia tới giường
 *  qua x này còn cao 4.5). Kệ hở + sách/lọ 2 đầu để không thành bức tường. */
function PartitionShelf({ at }: { at: [number, number, number] }) {
  return (
    <group position={at}>
      {[-3, 3].map((z) => (
        <Box key={z} size={[0.4, 1.8, 0.12]} at={[0, 0, z]} color={HR.woodDark} />
      ))}
      {[0.5, 1.0, 1.5].map((y) => (
        <Box key={y} size={[0.36, 0.06, 6.0]} at={[0, y, 0]} color={HR.woodDark} />
      ))}
      {/* sách đứng kệ giữa 2 cụm + lọ cây 2 đầu */}
      {[-1.6, -1.4, -1.2, 1.2, 1.4, 1.6].map((z, i) => (
        <Box
          key={z}
          size={[0.2, 0.32, 0.12]}
          at={[0, 1.025, z]}
          color={[HR.blanketBlue, HR_RED, HR.woodGold][i % 3]}
        />
      ))}
      {[-2.4, 2.4].map((z) => (
        <group key={z}>
          <mesh position={[0, 1.65, z]} castShadow>
            <cylinderGeometry args={[0.09, 0.12, 0.25, 8]} />
            {paint(HR.sheetWhite)}
          </mesh>
          <mesh position={[0, 1.94, z]} castShadow>
            <coneGeometry args={[0.18, 0.35, 8]} />
            {paint(HR.plantGreen)}
          </mesh>
        </group>
      ))}
    </group>
  );
}

export function HotelRoomEnvironment({
  onBrandPick,
}: {
  onBrandPick?: (c: [number, number, number]) => void;
}) {
  const floor = useMemo(() => {
    // Sàn gỗ sọc deterministic (không random).
    const PPM = 32;
    const W = 26 * PPM;
    const H = 20 * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = HR.floorWood;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = HR.floorDark;
    for (let i = 0; i < 20; i += 2) ctx.fillRect(0, i * PPM, W, PPM);
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
          <planeGeometry args={[26, 20]} />
          <meshStandardMaterial map={floor} roughness={0.9} />
        </mesh>
      )}
      {/* sân ban công ngoài: chạm khít mép sàn trong, không chồng mặt */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[-3, -0.01, -11]}
        receiveShadow
        raycast={() => null}
      >
        <planeGeometry args={[7, 4]} />
        <meshStandardMaterial color={PALETTE.concrete} roughness={0.95} />
      </mesh>
      {/* tường bắc CÓ cửa mở ra ban công (x −4.4..−1.6): 2 đoạn + đà ngang
          trên. Không đục lỗ thì kính trong cũng chỉ nhìn vào tường đặc. */}
      <Box size={[8.6, 3.4, 0.3]} at={[-8.7, 0, -9]} color={HR.wallCream} />
      <Box size={[14.6, 3.4, 0.3]} at={[5.7, 0, -9]} color={HR.wallCream} />
      <Box size={[2.8, 0.8, 0.3]} at={[-3, 2.6, -9]} color={HR.wallCream} />
      <Box size={[0.3, 3.4, 18]} at={[-13, 0, 0]} color={HR.wallCream} />
      <Box size={[0.3, 3.4, 18]} at={[13, 0, 0]} color={HR.wallCream} />
      {/* mặt nam: tường lửng 2 đoạn chừa cửa giữa (x ±2.5) */}
      {[-7.75, 7.75].map((x) => (
        <group key={x}>
          <Box size={[10.5, 1.1, 0.2]} at={[x, 0, 9]} color={HR.wallCream} />
          <Box size={[10.5, 0.08, 0.26]} at={[x, 1.1, 9]} color={HR.woodDark} />
        </group>
      ))}
      {/* vách kính phòng tắm đông-nam (tây + nam buồng), tắt raycast */}
      <mesh position={[7.5, 1.1, 5.75]} raycast={() => null}>
        <boxGeometry args={[0.04, 2.2, 5.5]} />
        <meshStandardMaterial color={HR.glassBlue} transparent opacity={0.28} />
      </mesh>
      <mesh position={[9.75, 1.1, 8.5]} raycast={() => null}>
        <boxGeometry args={[4.5, 2.2, 0.04]} />
        <meshStandardMaterial color={HR.glassBlue} transparent opacity={0.28} />
      </mesh>
      {[7.5, 12].map((x) =>
        [3, 8.5].map((z) => (
          <Box key={`${x}${z}`} size={[0.12, 2.3, 0.12]} at={[x, 0, z]} color={HR.steelChrome} />
        )),
      )}
      <BrandPlateNorth onPick={onBrandPick} />
      {/* tủ vách ngăn tách khu giường (x −0.2..0.2, z −5..1) */}
      <PartitionShelf at={[0, 0, -2]} />
    </group>
  );
}

/** Thảm trải sàn tây-nam: 3 lớp nổi dần (lớp nào cũng lút 0.005, lồi 0.025). */
function RugMat() {
  return (
    <group>
      <Box size={[4, 0.04, 3]} at={[0, 0, 0]} color={HR.blanketBlue} />
      <Box size={[3.4, 0.03, 2.4]} at={[0, 0.035, 0]} color={HR.sheetWhite} />
      <Box size={[2.6, 0.03, 1.6]} at={[0, 0.06, 0]} color={HR_RED} />
    </group>
  );
}

/** Ghế sofa DÀI mặt +Z (xoay ngoài): 4 chân + bệ + 2 nệm + lưng + 2 gối
 *  tựa + 2 tay. Bản đơn cũ không ra dáng sofa phòng khách sạn. */
function SofaChair() {
  return (
    <group>
      {[-0.95, 0.95].map((x) =>
        [-0.35, 0.35].map((z) => (
          <Box key={`${x}${z}`} size={[0.09, 0.35, 0.09]} at={[x, 0, z]} color={HR.woodDark} />
        )),
      )}
      <Box size={[2.2, 0.2, 0.9]} at={[0, 0.345, 0]} color={HR.blanketBlue} />
      {/* 2 nệm ngồi (đáy lút bệ) */}
      {[-0.53, 0.53].map((x) => (
        <Box key={x} size={[1.0, 0.15, 0.8]} at={[x, 0.54, 0]} color={HR.sheetWhite} />
      ))}
      {/* lưng + 2 gối tựa nghiêng vào lưng */}
      <Box size={[2.2, 0.75, 0.2]} at={[0, 0.55, -0.37]} color={HR.blanketBlue} />
      {[-0.53, 0.53].map((x) => (
        <group key={x} position={[x, 0.68, -0.24]} rotation={[-0.18, 0, 0]}>
          <Box size={[0.9, 0.45, 0.15]} at={[0, 0.22, 0]} color={HR.sheetWhite} />
        </group>
      ))}
      {/* 2 tay vịn (đáy lút bệ) */}
      {[-1.01, 1.01].map((x) => (
        <Box key={x} size={[0.18, 0.4, 0.9]} at={[x, 0.54, 0]} color={HR.blanketBlue} />
      ))}
    </group>
  );
}

export const HOTEL_ROOM_SHAPES = {
  "bed-frame": BedFrame,
  "pillow-pair": PillowPair,
  "blanket-bench": BlanketBench,
  "alarm-clock": AlarmClock,
  "tv-set": TvSet,
  "aircon-wall": AirconWall,
  "closet-wardrobe": ClosetWardrobe,
  "hanger-rack": HangerRack,
  "safe-box": SafeBox,
  "minibar-fridge": MinibarFridge,
  "kettle-tray": KettleTray,
  "towel-rack": TowelRack,
  "bathtub-tub": BathtubTub,
  "shower-stall": ShowerStall,
  "balcony-door": BalconyDoor,
  "curtain-pair": CurtainPair,
  "baggage-rack": BaggageRack,
  "rug-mat": RugMat,
  "sofa-chair": SofaChair,
};
