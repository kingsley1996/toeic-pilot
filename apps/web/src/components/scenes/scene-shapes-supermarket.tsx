import { useMemo } from "react";
import * as THREE from "three";

import { Box, PALETTE, Person, Wheel, paint, useSignFace } from "@/components/scenes/scene-shapes";

/**
 * Siêu thị — cùng khuôn `scene-shapes-office.tsx`: shape là group gốc đất
 * (y = 0), `Box` lấy gốc chân, màu tái dùng `PALETTE` chung.
 *
 * Quy ước đọc để 24 từ khỏi lẫn nhau:
 * - 3 dãy kệ: chỉ dãy giữa có nhãn, hai dãy bên là decor trong environment.
 * - Đồ trên mặt quầy tự mang quầy của nó (receipt/barcode/bag nằm trên làn
 *   checkout) — tách bằng cao độ + vị trí x, không bằng khoảng cách xa.
 * - Biển chữ đều là canvas offline: số aisle (xanh), % coupon (đỏ), SALE
 *   (cam), $5 endcap (vàng), menu deli (dòng), danh sách (dòng + ô tick).
 */

function marketCanvas(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void) {
  // Helper thuần, không phải hook: mỗi shape gọi trong `useMemo` của nó.
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  draw(ctx);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

/** Gạch sàn 1 m — lưới kẻ deterministic, không chữ, không random. */
function useTileFloor() {
  return useMemo(() => {
    const PPM = 32;
    const size = 32 * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#d7dce0";
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "#bcc3c9";
    ctx.lineWidth = 2;
    for (let i = 0; i <= 32; i++) {
      ctx.beginPath();
      ctx.moveTo(i * PPM, 0);
      ctx.lineTo(i * PPM, size);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i * PPM);
      ctx.lineTo(size, i * PPM);
      ctx.stroke();
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8;
    return texture;
  }, []);
}

// Hàng trên kệ: màu chọn bằng công thức chỉ số, KHÔNG random — hai lần load
// phải ra một ảnh (quy tắc deterministic §8.7).
const GOODS = ["#c0392b", "#e67e22", "#e8b93c", "#5f8a52", "#3b6ea5", "#8a5a33", "#f7f7f4"] as const;
const goodsColor = (i: number, j: number) => GOODS[(i * 5 + j * 3) % GOODS.length];

/** Một mặt kệ dài 8 m: 4 tầng, mỗi tầng 10 hộp cùng cỡ (0.6 × 0.35 × 0.4). */
function ShelfGoods({ facing = 1 }: { facing?: 1 | -1 }) {
  const boxes: Array<{ x: number; y: number; c: string }> = [];
  for (let tier = 0; tier < 4; tier++)
    for (let i = 0; i < 10; i++)
      boxes.push({ x: -3.3 + i * 0.73, y: 0.35 + tier * 0.42, c: goodsColor(i, tier) });
  return (
    <group>
      {boxes.map((b, k) => (
        <Box key={k} size={[0.6, 0.35, 0.4]} at={[b.x, b.y, facing * 0.32]} color={b.c} />
      ))}
    </group>
  );
}

/** Kệ gondola hai mặt: lưng giữa + chân đế + 4 tầng mỗi bên. Dài 8 m, cao 2 m. */
function GondolaShelf() {
  return (
    <group>
      <Box size={[8, 0.12, 1.2]} at={[0, 0, 0]} color={PALETTE.steelDark} />
      <Box size={[8, 2.0, 0.1]} at={[0, 0.12, 0]} color={PALETTE.concrete} />
      {[-3.9, 3.9].map((x) => (
        <Box key={x} size={[0.12, 2.0, 1.2]} at={[x, 0.12, 0]} color={PALETTE.steel} />
      ))}
      {[0.35, 0.77, 1.19, 1.61].map((y) => (
        <group key={y}>
          <Box size={[7.8, 0.05, 0.55]} at={[0, y, 0.32]} color={PALETTE.stone} />
          <Box size={[7.8, 0.05, 0.55]} at={[0, y, -0.32]} color={PALETTE.stone} />
        </group>
      ))}
      <ShelfGoods facing={1} />
      <ShelfGoods facing={-1} />
    </group>
  );
}

/** Cửa kính trượt: khung + 2 cánh kính trong + thảm. Cao 2.7 m. */
function EntryDoor() {
  return (
    <group>
      {[-1.1, 1.1].map((x) => (
        <Box key={x} size={[0.18, 2.7, 0.3]} at={[x, 0, 0]} color={PALETTE.wallTrim} />
      ))}
      <Box size={[2.4, 0.25, 0.3]} at={[0, 2.7, 0]} color={PALETTE.wallTrim} />
      {[-0.52, 0.52].map((x) => (
        <mesh key={x} position={[x, 1.45, 0]}>
          <planeGeometry args={[0.95, 2.3]} />
          <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.28} />
        </mesh>
      ))}
      <Box size={[2.2, 0.03, 1.2]} at={[0, 0, 0.8]} color={PALETTE.asphalt} />
    </group>
  );
}

/** Chồng 3 giỏ xách tay lồng nhau (hộp mở thu dần). */
function BasketStack() {
  return (
    <group>
      {[0, 1, 2].map((i) => (
        <group key={i} position={[0, i * 0.28, 0]}>
          <Box size={[0.62 - i * 0.06, 0.05, 0.42 - i * 0.05]} at={[0, 0, 0]} color={PALETTE.cone} />
          <Box size={[0.62 - i * 0.06, 0.3, 0.04]} at={[0, 0.05, 0.19 - i * 0.025]} color={PALETTE.cone} />
          <Box size={[0.62 - i * 0.06, 0.3, 0.04]} at={[0, 0.05, -0.19 + i * 0.025]} color={PALETTE.cone} />
        </group>
      ))}
    </group>
  );
}

/** Bảng danh sách mua sắm: 2 chân + bảng + giấy dòng + ô tick. */
function ListBoard() {
  const face = useMemo(
    () =>
      marketCanvas(256, 320, (ctx) => {
        ctx.fillStyle = "#f7f7f4";
        ctx.fillRect(0, 0, 256, 320);
        ctx.fillStyle = "#40566b";
        ctx.fillRect(0, 0, 256, 52);
        ctx.fillStyle = "#f7f7f4";
        ctx.font = "bold 26px sans-serif";
        ctx.fillText("LIST", 18, 36);
        for (let i = 0; i < 6; i++) {
          const y = 90 + i * 36;
          ctx.strokeStyle = "#40566b";
          ctx.lineWidth = 3;
          ctx.strokeRect(18, y - 18, 22, 22);
          ctx.fillStyle = "#9aa4ad";
          ctx.fillRect(52, y - 10, 170 - i * 18, 8);
        }
      }),
    [],
  );
  return (
    <group>
      {[-0.7, 0.7].map((x) => (
        <Box key={x} size={[0.1, 1.75, 0.1]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      <Box size={[1.7, 1.3, 0.08]} at={[0, 0.55, 0]} color={PALETTE.wallTrim} />
      {face && (
        <mesh position={[0, 1.2, 0.05]}>
          <planeGeometry args={[1.55, 1.15]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Cổng biển số lối đi: 2 chân + xà + biển treo số 5. Cao 2.6 m. */
function AisleSign() {
  const face = useMemo(
    () =>
      marketCanvas(128, 128, (ctx) => {
        ctx.fillStyle = "#13395f";
        ctx.fillRect(0, 0, 128, 128);
        ctx.fillStyle = "#f7f7f4";
        ctx.font = "bold 84px sans-serif";
        ctx.fillText("5", 38, 96);
      }),
    [],
  );
  return (
    <group>
      {[-1.4, 1.4].map((x) => (
        <Box key={x} size={[0.14, 2.7, 0.14]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      <Box size={[2.94, 0.14, 0.14]} at={[0, 2.63, 0]} color={PALETTE.steelDark} />
      <Box size={[0.7, 0.7, 0.08]} at={[0, 2.2, 0]} color={PALETTE.brandBlue} />
      {face && (
        <mesh position={[0, 2.2, 0.05]}>
          <planeGeometry args={[0.62, 0.62]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Xe đẩy có người đẩy sau (cùng group nên đi cùng nhau khi patrol). */
function ShopCart() {
  return (
    <group>
      {/* giỏ trên: khung đáy + 4 thành nan (3 thanh mỗi thành) */}
      <Box size={[1.0, 0.06, 0.6]} at={[0, 0.55, 0]} color={PALETTE.steel} />
      {[0.62, 0.78, 0.94].map((y) => (
        <group key={y}>
          <Box size={[1.0, 0.04, 0.04]} at={[0, y, 0.28]} color={PALETTE.steel} />
          <Box size={[1.0, 0.04, 0.04]} at={[0, y, -0.28]} color={PALETTE.steel} />
        </group>
      ))}
      <Box size={[0.04, 0.45, 0.6]} at={[-0.48, 0.6, 0]} color={PALETTE.steel} />
      {/* tay đẩy + khung chân + 4 bánh */}
      <Box size={[0.05, 0.05, 0.6]} at={[-0.62, 1.0, 0]} color={PALETTE.tire} />
      {[-0.45, 0.45].map((x) =>
        [-0.22, 0.22].map((z) => (
          <group key={`${x}${z}`}>
            <Box size={[0.05, 0.5, 0.05]} at={[x, 0.05, z]} color={PALETTE.steelDark} />
            <Wheel at={[x, 0, z]} r={0.09} />
          </group>
        )),
      )}
      {/* vài món đã mua trong giỏ */}
      <Box size={[0.3, 0.25, 0.3]} at={[0.2, 0.58, 0]} color={PALETTE.cardbox} />
      <Box size={[0.2, 0.3, 0.2]} at={[-0.25, 0.58, 0.05]} color={PALETTE.leaf} />
      {/* người đẩy sau xe (mũi +X, cùng hướng xe) */}
      <group position={[-1.05, 0, 0]}>
        <Person coat={PALETTE.doorOrange} hair={PALETTE.tire} />
      </group>
    </group>
  );
}

/** Đầu cap cuối kệ: bục + thẻ giá vàng "$5" cỡ lớn. */
function EndcapTag() {
  const face = useMemo(
    () =>
      marketCanvas(256, 160, (ctx) => {
        ctx.fillStyle = "#e8b93c";
        ctx.fillRect(0, 0, 256, 160);
        ctx.fillStyle = "#a31220";
        ctx.font = "bold 92px sans-serif";
        ctx.fillText("$5", 62, 118);
      }),
    [],
  );
  return (
    <group>
      <Box size={[1.4, 0.5, 1.0]} at={[0, 0, 0]} color={PALETTE.cardbox} />
      <Box size={[0.1, 0.6, 0.1]} at={[0, 0.5, -0.4]} color={PALETTE.steelDark} />
      <Box size={[1.1, 0.7, 0.06]} at={[0, 0.75, -0.38]} color={PALETTE.paper} />
      {face && (
        <mesh position={[0, 1.1, -0.34]}>
          <planeGeometry args={[1.0, 0.62]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Sạp rau: bàn gỗ + 3 thùng + đống củ quả (cầu dẹt xếp lưới cố định). */
function ProduceStand() {
  const piles = [
    { at: [-0.9, 0.75, 0] as [number, number, number], c: PALETTE.cone },
    { at: [0, 0.75, 0] as [number, number, number], c: PALETTE.leaf },
    { at: [0.9, 0.75, 0] as [number, number, number], c: "#a31220" },
  ];
  return (
    <group>
      <Box size={[3.0, 0.7, 1.6]} at={[0, 0, 0]} color={PALETTE.wood} />
      {[-1.05, 0, 1.05].map((x) => (
        <Box key={x} size={[0.9, 0.35, 1.3]} at={[x, 0.7, 0]} color={PALETTE.woodDark} />
      ))}
      {piles.map((p, k) => (
        <group key={k} position={p.at}>
          {[-0.25, 0, 0.25].map((dx) =>
            [-0.3, 0.3].map((dz) => (
              <mesh key={`${dx}${dz}`} position={[dx, 0.32, dz]} castShadow>
                <sphereGeometry args={[0.16, 10, 8]} />
                {paint(p.c)}
              </mesh>
            )),
          )}
        </group>
      ))}
    </group>
  );
}

/** Cân bàn: chân + mặt + cột + mặt số (trụ xoay X π/2 cho mặt về camera). */
function ProduceScale() {
  return (
    <group>
      <Box size={[0.5, 0.9, 0.5]} at={[0, 0, 0]} color={PALETTE.steelDark} />
      <Box size={[0.55, 0.06, 0.55]} at={[0, 0.9, 0]} color={PALETTE.steel} />
      <Box size={[0.08, 0.55, 0.08]} at={[0, 0.96, -0.2]} color={PALETTE.steelDark} />
      {/* mặt số tròn quay về +Z: trụ mặc định trục Y nên xoay X π/2 (§10.4) */}
      <mesh position={[0, 1.45, -0.14]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.22, 0.08, 20]} />
        {paint(PALETTE.paper)}
      </mesh>
      <Box size={[0.03, 0.16, 0.02]} at={[0.05, 1.45, -0.09]} color="#a31220" />
    </group>
  );
}

/** Khay ăn thử: chân cao + mâm + 6 chén nhỏ. */
function SampleStand() {
  return (
    <group>
      <Box size={[0.12, 1.1, 0.12]} at={[0, 0, 0]} color={PALETTE.steelDark} />
      <Box size={[0.7, 0.05, 0.7]} at={[0, 1.1, 0]} color={PALETTE.steel} />
      {[-0.2, 0, 0.2].map((x) =>
        [-0.2, 0.2].map((z) => (
          <mesh key={`${x}${z}`} position={[x, 1.18, z]} castShadow>
            <cylinderGeometry args={[0.07, 0.05, 0.09, 12]} />
            {paint(PALETTE.paper)}
          </mesh>
        )),
      )}
    </group>
  );
}

/** Tủ sữa mở: thân + 3 tầng + hộp sữa trắng xếp lưới.
 *  Dài 2.4 (world X sau yaw): lưng lút tường 0.1, mặt trước hở dãy kệ decor
 *  phía đông 0.6 — dài hơn là đâm cả hai. */
function DairyCooler() {
  return (
    <group>
      <Box size={[0.8, 1.7, 2.4]} at={[-0.1, 0, 0]} color={PALETTE.vanWhite} />
      {[0.45, 0.9, 1.35].map((y) => (
        <group key={y}>
          <Box size={[0.6, 0.04, 2.2]} at={[0.15, y, 0]} color={PALETTE.concrete} />
          {[-0.8, -0.4, 0, 0.4, 0.8].map((z) => (
            <Box key={z} size={[0.3, 0.32, 0.32]} at={[0.15, y + 0.04, z]} color={PALETTE.paper} />
          ))}
        </group>
      ))}
    </group>
  );
}

/** Tủ đông nắp kính: thân + mặt kính trượt một mức 0.28 (§10.5) + tay nắm. */
function ChestFreezer() {
  return (
    <group>
      <Box size={[1.1, 1.0, 2.6]} at={[0, 0, 0]} color={PALETTE.vanWhite} />
      <mesh position={[0, 1.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.0, 2.5]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.28} />
      </mesh>
      <Box size={[1.14, 0.08, 0.1]} at={[0, 1.0, 1.2]} color={PALETTE.steel} />
      <Box size={[1.14, 0.08, 0.1]} at={[0, 1.0, -1.2]} color={PALETTE.steel} />
    </group>
  );
}

/** Quầy bánh: tủ + kệ 2 tầng sau + ổ bánh (trụ nằm + cầu). */
function BakeryCounter() {
  return (
    <group>
      <Box size={[2.6, 0.9, 1.0]} at={[0, 0, 0]} color={PALETTE.wood} />
      <Box size={[2.6, 0.06, 1.1]} at={[0, 0.9, 0]} color={PALETTE.woodDark} />
      {[0.4, 0.9].map((dz) => (
        <Box key={dz} size={[0.08, 0.8, 0.08]} at={[-1.2, 0.96, dz]} color={PALETTE.woodDark} />
      ))}
      {[0.4, 0.9].map((dz) => (
        <Box key={dz} size={[0.08, 0.8, 0.08]} at={[1.2, 0.96, dz]} color={PALETTE.woodDark} />
      ))}
      {[1.25, 1.65].map((y) => (
        <Box key={y} size={[2.5, 0.05, 1.0]} at={[0, y, 0.65]} color={PALETTE.wood} />
      ))}
      {[-0.8, 0, 0.8].map((x) => (
        <group key={x}>
          <mesh position={[x, 1.38, 0.65]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[0.11, 0.11, 0.5, 12]} />
            {paint("#c98d4e")}
          </mesh>
          <mesh position={[x, 1.78, 0.65]} castShadow>
            <sphereGeometry args={[0.14, 10, 8]} />
            {paint("#dba964")}
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Quầy đồ nguội: tủ + mặt kính trước + bảng menu treo trên 2 cột. */
function DeliCounter() {
  const menu = useMemo(
    () =>
      marketCanvas(256, 128, (ctx) => {
        ctx.fillStyle = "#23404f";
        ctx.fillRect(0, 0, 256, 128);
        ctx.fillStyle = "#f7f7f4";
        ctx.font = "bold 24px sans-serif";
        ctx.fillText("MENU", 14, 32);
        ctx.fillStyle = "#9fc0d2";
        for (let i = 0; i < 3; i++) ctx.fillRect(14, 50 + i * 24, 200 - i * 40, 8);
      }),
    [],
  );
  return (
    <group>
      <Box size={[2.6, 0.9, 1.0]} at={[0, 0, 0]} color={PALETTE.concrete} />
      <mesh position={[0, 0.55, 0.52]} castShadow>
        <planeGeometry args={[2.5, 0.7]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.28} />
      </mesh>
      {[-1.2, 1.2].map((x) => (
        <Box key={x} size={[0.08, 1.8, 0.08]} at={[x, 0.9, -0.3]} color={PALETTE.steelDark} />
      ))}
      <Box size={[2.6, 0.7, 0.06]} at={[0, 1.45, -0.3]} color={PALETTE.wallTrim} />
      {menu && (
        <mesh position={[0, 1.45, -0.26]}>
          <planeGeometry args={[2.4, 0.6]} />
          <meshBasicMaterial map={menu} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Một shape 3 làn (một nhãn): băng chuyền + cổng quét + màn hình mỗi làn. */
function CheckoutLane() {
  return (
    <group>
      {[-2.4, 0, 2.4].map((x) => (
        <group key={x} position={[x, 0, 0]}>
          <Box size={[1.8, 0.9, 0.9]} at={[0, 0, 0]} color={PALETTE.concreteDark} />
          <Box size={[1.8, 0.06, 0.7]} at={[0, 0.9, 0]} color={PALETTE.tire} />
          {[-0.7, 0.7].map((sx) => (
            <Box key={sx} size={[0.08, 0.5, 0.08]} at={[sx, 0.96, -0.2]} color={PALETTE.steelDark} />
          ))}
          <Box size={[1.5, 0.08, 0.08]} at={[0, 1.42, -0.2]} color={PALETTE.steelDark} />
          <Box size={[0.08, 0.7, 0.08]} at={[0.6, 0.96, 0.25]} color={PALETTE.steelDark} />
          <Box size={[0.4, 0.3, 0.06]} at={[0.6, 1.5, 0.25]} color={PALETTE.brandBlue} />
        </group>
      ))}
    </group>
  );
}

/** Giấy in trên quầy: tờ mỏng + 4 dòng chữ (nổi 0.02 chống flicker §10.6). */
function ReceiptSlip() {
  return (
    <group>
      <Box size={[0.3, 0.015, 0.45]} at={[0, 0.9, 0]} color={PALETTE.paper} />
      {[0, 1, 2, 3].map((i) => (
        <Box key={i} size={[0.22 - i * 0.03, 0.005, 0.025]} at={[0, 0.92, -0.14 + i * 0.08]} color={PALETTE.steel} />
      ))}
    </group>
  );
}

/** Hộp ngũ cốc dựng: thân + nhãn trắng + vạch đen. */
function BarcodeBox() {
  return (
    <group>
      <Box size={[0.4, 0.5, 0.15]} at={[0, 0.9, 0]} color={PALETTE.cone} />
      <Box size={[0.3, 0.3, 0.02]} at={[0, 1.05, 0.09]} color={PALETTE.paper} />
      {[0, 1, 2, 3, 4].map((i) => (
        <Box key={i} size={[0.025, 0.22, 0.005]} at={[-0.1 + i * 0.05, 1.05, 0.105]} color={PALETTE.tire} />
      ))}
    </group>
  );
}

/** Chồng 3 túi giấy lồng nhau trên quầy. */
function PaperBags() {
  return (
    <group>
      {[0, 1, 2].map((i) => (
        <group key={i} position={[0, i * 0.2, 0]}>
          <Box size={[0.5 - i * 0.05, 0.04, 0.35 - i * 0.04]} at={[0, 0.9, 0]} color={PALETTE.cardbox} />
          <Box size={[0.5 - i * 0.05, 0.22, 0.03]} at={[0, 0.94, 0.16 - i * 0.02]} color={PALETTE.cardbox} />
          <Box size={[0.5 - i * 0.05, 0.22, 0.03]} at={[0, 0.94, -0.16 + i * 0.02]} color={PALETTE.cardbox} />
        </group>
      ))}
    </group>
  );
}

/** Tháp khuyến mãi: pallet + kim tự tháp hộp 3-2-1 + biển trên đỉnh. */
function PromoTower() {
  return (
    <group>
      <Box size={[1.6, 0.12, 1.6]} at={[0, 0, 0]} color={PALETTE.woodDark} />
      {[-0.5, 0.5].map((x) =>
        [-0.5, 0.5].map((z) => (
          <Box key={`${x}${z}`} size={[0.55, 0.55, 0.55]} at={[x, 0.12, z]} color={PALETTE.cardbox} />
        )),
      )}
      <Box size={[0.55, 0.55, 0.55]} at={[-0.28, 0.67, 0]} color={PALETTE.cone} />
      <Box size={[0.55, 0.55, 0.55]} at={[0.28, 0.67, 0]} color={PALETTE.cone} />
      <Box size={[0.55, 0.5, 0.55]} at={[0, 1.22, 0]} color={PALETTE.paper} />
      <Box size={[0.08, 0.5, 0.08]} at={[0, 1.5, -0.2]} color={PALETTE.steelDark} />
      <Box size={[0.9, 0.5, 0.06]} at={[0, 1.85, -0.2]} color={PALETTE.lampRed} />
    </group>
  );
}

/** Biển chữ A mặt đỏ chữ % trắng. */
function CouponStand() {
  const face = useMemo(
    () =>
      marketCanvas(160, 200, (ctx) => {
        ctx.fillStyle = "#a31220";
        ctx.fillRect(0, 0, 160, 200);
        ctx.fillStyle = "#f7f7f4";
        ctx.font = "bold 120px sans-serif";
        ctx.fillText("%", 30, 150);
      }),
    [],
  );
  return (
    <group>
      {/* hai cánh nghiêng: rotation.x ±0.22 — dấu tính như thang (§8.2):
          cánh trước ngả đỉnh về +Z là dương */}
      <group rotation={[0.22, 0, 0]}>
        <Box size={[0.9, 1.6, 0.06]} at={[0, 0.75, 0.17]} color={PALETTE.paper} />
      </group>
      <group rotation={[-0.22, 0, 0]}>
        <Box size={[0.9, 1.6, 0.06]} at={[0, 0.75, -0.17]} color={PALETTE.concrete} />
      </group>
      {face && (
        <mesh position={[0, 0.95, 0.36]} rotation={[0.22, 0, 0]}>
          <planeGeometry args={[0.8, 1.0]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Cột biển cam SALE 4 mặt. */
function DiscountTotem() {
  const face = useMemo(
    () =>
      marketCanvas(256, 128, (ctx) => {
        ctx.fillStyle = "#e2601a";
        ctx.fillRect(0, 0, 256, 128);
        ctx.fillStyle = "#f7f7f4";
        ctx.font = "bold 64px sans-serif";
        ctx.fillText("SALE", 52, 88);
      }),
    [],
  );
  return (
    <group>
      <Box size={[0.5, 1.8, 0.5]} at={[0, 0, 0]} color={PALETTE.steelDark} />
      <Box size={[0.9, 0.65, 0.9]} at={[0, 1.8, 0]} color={PALETTE.cone} />
      {face && (
        <mesh position={[0, 2.12, 0.46]}>
          <planeGeometry args={[0.8, 0.4]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Quầy dịch vụ KH: bàn + biển SERVICE trên 2 cột + nhân viên. */
function ServiceDesk() {
  const face = useMemo(
    () =>
      marketCanvas(256, 96, (ctx) => {
        ctx.fillStyle = "#23404f";
        ctx.fillRect(0, 0, 256, 96);
        ctx.fillStyle = "#f7f7f4";
        ctx.font = "bold 44px sans-serif";
        ctx.fillText("SERVICE", 34, 64);
      }),
    [],
  );
  return (
    <group>
      <Box size={[2.0, 0.9, 0.8]} at={[0, 0, 0.3]} color={PALETTE.brandBlue} />
      {[-0.9, 0.9].map((x) => (
        <Box key={x} size={[0.08, 1.9, 0.08]} at={[x, 0, -0.3]} color={PALETTE.steelDark} />
      ))}
      <Box size={[2.0, 0.5, 0.06]} at={[0, 1.65, -0.3]} color={PALETTE.wallTrim} />
      {face && (
        <mesh position={[0, 1.65, -0.26]}>
          <planeGeometry args={[1.9, 0.42]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
      <group position={[-0.5, 0, -0.5]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={PALETTE.leaf} hair={PALETTE.tire} />
      </group>
    </group>
  );
}

export const SUPERMARKET_SHAPES = {
  "entry-door": EntryDoor,
  "basket-stack": BasketStack,
  "list-board": ListBoard,
  "gondola-shelf": GondolaShelf,
  "aisle-sign": AisleSign,
  "shop-cart": ShopCart,
  "endcap-tag": EndcapTag,
  "produce-stand": ProduceStand,
  "produce-scale": ProduceScale,
  "sample-stand": SampleStand,
  "dairy-cooler": DairyCooler,
  "chest-freezer": ChestFreezer,
  "bakery-counter": BakeryCounter,
  "deli-counter": DeliCounter,
  "checkout-lane": CheckoutLane,
  cashier: () => (
    <group rotation={[0, -Math.PI / 2, 0]}>
      <Person coat={PALETTE.brandBlue} hair={PALETTE.tire} />
    </group>
  ),
  "receipt-slip": ReceiptSlip,
  "barcode-box": BarcodeBox,
  "paper-bags": PaperBags,
  "promo-tower": PromoTower,
  "coupon-stand": CouponStand,
  "discount-totem": DiscountTotem,
  "service-desk": ServiceDesk,
};

/** Logo thương hiệu dán tường bắc sau quầy thu ngân (mẫu LogoPlate office:
 *  trong nhà không dựng biển cột). */
function MarketLogo({ onPick }: { onPick: (faceCenter: [number, number, number]) => void }) {
  const face = useSignFace();
  return (
    <group
      position={[0, 0, -10.8]}
      onClick={(e) => {
        e.stopPropagation();
        onPick([0, 2.2, -10.7]);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        document.body.style.cursor = "";
      }}
    >
      <Box size={[3.7, 1.9, 0.08]} at={[0, 1.25, 0]} color={PALETTE.wallTrim} />
      {face && (
        <mesh position={[0, 2.2, 0.06]}>
          <planeGeometry args={[3.6, 1.8]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

export function SupermarketEnvironment({
  onBrandPick,
}: {
  onBrandPick: (faceCenter: [number, number, number]) => void;
}) {
  const floor = useTileFloor();
  return (
    <group>
      {floor && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[30, 24]} />
          <meshStandardMaterial map={floor} roughness={0.95} />
        </mesh>
      )}
      {/* tường bắc đặc kín 4 m (z = −11) — để hở dải giữa là camera trên cao
          nhìn xuyên ra trời, đọc như tường thủng */}
      <Box size={[30, 4.0, 0.3]} at={[0, 0, -11]} color={PALETTE.wall} />
      {/* tường tây/đông đặc (cao 4 m, lưng tủ sữa/tủ đông lút 0.15) */}
      <Box size={[0.3, 4.0, 22]} at={[-14, 0, 0]} color={PALETTE.wall} />
      <Box size={[0.3, 4.0, 22]} at={[14, 0, 0]} color={PALETTE.wall} />
      {/* mặt kính nam: trụ + dải kính, chừa 2 ô cửa (x −7..−5, 5..7) cho
          entry-door/exit-door vẽ khung riêng */}
      {[-13.5, -10, -3.5, 0, 3.5, 10, 13.5].map((x) => (
        <Box key={x} size={[0.6, 3.2, 0.3]} at={[x, 0, 10]} color={PALETTE.wall} />
      ))}
      <Box size={[28, 0.8, 0.3]} at={[0, 3.2, 10]} color={PALETTE.wall} />
      {[
        [-8.75, 2.5],
        [-1.75, 3.5],
        [1.75, 3.5],
        [8.75, 2.5],
        [11.75, 2.5],
        [-11.75, 2.5],
      ].map(([x, w]) => (
        <mesh key={x} position={[x, 1.6, 10]}>
          <planeGeometry args={[w, 3.2]} />
          <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.28} />
        </mesh>
      ))}
      {/* hai dãy kệ decor (không nhãn): tây dời nam cho hở tủ sữa
          (z −2.4..−1.6), đông dời bắc cho thoáng produce */}
      <group position={[-8, 0, 3]}>
        <GondolaShelf />
      </group>
      <group position={[3, 0, -3]}>
        <GondolaShelf />
      </group>
      <MarketLogo onPick={onBrandPick} />
    </group>
  );
}
