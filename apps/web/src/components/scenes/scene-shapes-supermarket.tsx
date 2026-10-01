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
const GOODS = [
  "#c0392b",
  "#e67e22",
  "#e8b93c",
  "#5f8a52",
  "#3b6ea5",
  "#8a5a33",
  "#f7f7f4",
] as const;
const goodsColor = (i: number, j: number) => GOODS[(i * 5 + j * 3) % GOODS.length];

/** Một mặt kệ dài 8 m: 4 tầng, mỗi tầng 10 hộp cùng cỡ (0.6 × 0.35 × 0.4).
 *  Hộp ngồi lút 0.005 trên mặt tầng (mặt ở tầng+0.05). */
function ShelfGoods({ facing = 1 }: { facing?: 1 | -1 }) {
  const boxes: Array<{ x: number; y: number; c: string }> = [];
  for (let tier = 0; tier < 4; tier++)
    for (let i = 0; i < 10; i++)
      boxes.push({ x: -3.3 + i * 0.73, y: 0.395 + tier * 0.42, c: goodsColor(i, tier) });
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
      {/* lưng + hồi lút 0.005 vào chân đế (đỉnh đế 0.12) */}
      <Box size={[8, 2.0, 0.1]} at={[0, 0.115, 0]} color={PALETTE.concrete} />
      {[-3.9, 3.9].map((x) => (
        <Box key={x} size={[0.12, 2.0, 1.2]} at={[x, 0.115, 0]} color={PALETTE.steel} />
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

/** Cửa kính trượt: khung + 2 cánh kính trong + thảm + biển treo trên đầu.
 *  IN biển xanh, EXIT biển lục — hai cửa cùng shape là không phân biệt nổi.
 *  Biển trên đỉnh khung (tâm y 3.05): nhãn ôm nóc biển, không mũi tên. */
function DoorWithSign({ text, bg }: { text: string; bg: string }) {
  const face = useMemo(
    () =>
      marketCanvas(256, 96, (ctx) => {
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, 256, 96);
        ctx.fillStyle = "#f7f7f4";
        ctx.font = "bold 56px sans-serif";
        ctx.fillText(text, 24, 66);
      }),
    [text, bg],
  );
  return (
    <group>
      {/* cột DÀY hơn dải tường ngang (0.34 vs 0.3): cùng độ dày là mặt hông
          cột trùng mặt hông dải đúng đoạn giao nhau → flicker. Lồi 0.02 mỗi
          bên đọc như gờ trụ, có chủ ý. */}
      {[-1.1, 1.1].map((x) => (
        <Box key={x} size={[0.18, 3.3, 0.34]} at={[x, 0, 0]} color={PALETTE.wallTrim} />
      ))}
      <Box size={[2.4, 0.25, 0.3]} at={[0, 2.7, 0]} color={PALETTE.wallTrim} />
      <Box size={[1.3, 0.5, 0.08]} at={[0, 3.05, 0]} color={PALETTE.wallTrim} />
      {/* chữ nổi 0.04 trên mặt biển (mặt ở 0.04) */}
      {face && (
        <mesh position={[0, 3.05, 0.08]}>
          <planeGeometry args={[1.2, 0.42]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
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
function EntryDoor() {
  return <DoorWithSign text="IN" bg="#1d5c96" />;
}
function ExitDoor() {
  return <DoorWithSign text="EXIT" bg="#1d7a3a" />;
}

/** Chồng 3 giỏ xách tay lồng nhau (hộp mở thu dần). */
function BasketStack() {
  return (
    <group>
      {[0, 1, 2].map((i) => (
        <group key={i} position={[0, i * 0.28, 0]}>
          <Box
            size={[0.62 - i * 0.06, 0.05, 0.42 - i * 0.05]}
            at={[0, 0, 0]}
            color={PALETTE.cone}
          />
          <Box
            size={[0.62 - i * 0.06, 0.3, 0.04]}
            at={[0, 0.05, 0.19 - i * 0.025]}
            color={PALETTE.cone}
          />
          <Box
            size={[0.62 - i * 0.06, 0.3, 0.04]}
            at={[0, 0.05, -0.19 + i * 0.025]}
            color={PALETTE.cone}
          />
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
      {/* chữ nổi 0.04 trên mặt bảng (mặt ở 0.04) */}
      {face && (
        <mesh position={[0, 1.2, 0.08]}>
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
      {/* chân lút 0.05 vào xà (đỉnh chân chạm đỉnh xà là trùng mặt) */}
      {[-1.4, 1.4].map((x) => (
        <Box key={x} size={[0.14, 2.62, 0.14]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      <Box size={[2.94, 0.14, 0.14]} at={[0, 2.63, 0]} color={PALETTE.steelDark} />
      <Box size={[0.7, 0.7, 0.08]} at={[0, 2.15, 0]} color={PALETTE.brandBlue} />
      {/* số hở xà 0.06 (đỉnh biển 2.5, đáy xà 2.56), chữ nổi 0.05 */}
      {face && (
        <mesh position={[0, 2.15, 0.09]}>
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
            {/* chân lút 0.01 vào khung đáy (đỉnh khung 0.61) */}
            <Box size={[0.05, 0.5, 0.05]} at={[x, 0.04, z]} color={PALETTE.steelDark} />
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
      {/* cột lút vào bục; thẻ ôm tâm cột cho khỏi lơ lửng, chữ nổi 0.04 */}
      <Box size={[0.1, 0.6, 0.1]} at={[0, 0.49, -0.4]} color={PALETTE.steelDark} />
      <Box size={[1.1, 0.7, 0.06]} at={[0, 0.75, -0.38]} color={PALETTE.paper} />
      {face && (
        <mesh position={[0, 0.75, -0.31]}>
          <planeGeometry args={[1.0, 0.62]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Sạp rau: bàn gỗ + 3 thùng + đống củ quả CỠ ĐỌC ĐƯỢC (cầu r 0.2 —
 *  r 0.16 nhìn xa chỉ là gợn, mắt kiểm cận produce). */
function ProduceStand() {
  const piles = [
    { at: [-0.9, 0.75, 0] as [number, number, number], c: PALETTE.cone },
    { at: [0, 0.75, 0] as [number, number, number], c: PALETTE.leaf },
    { at: [0.9, 0.75, 0] as [number, number, number], c: "#a31220" },
  ];
  return (
    <group>
      <Box size={[3.0, 0.7, 1.6]} at={[0, 0, 0]} color={PALETTE.wood} />
      {/* thùng lút 0.005 vào mặt bàn (mặt ở 0.7) */}
      {[-1.05, 0, 1.05].map((x) => (
        <Box key={x} size={[0.9, 0.35, 1.3]} at={[x, 0.695, 0]} color={PALETTE.woodDark} />
      ))}
      {piles.map((p, k) => (
        <group key={k} position={p.at}>
          {[-0.28, 0, 0.28].map((dx) =>
            [-0.32, 0.32].map((dz) => (
              <mesh key={`${dx}${dz}`} position={[dx, 0.36, dz]} castShadow>
                <sphereGeometry args={[0.2, 10, 8]} />
                {paint(p.c)}
              </mesh>
            )),
          )}
          <mesh position={[0, 0.62, 0]} castShadow>
            <sphereGeometry args={[0.2, 10, 8]} />
            {paint(p.c)}
          </mesh>
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
      {/* mặt + cột lút vào nhau (không chạm đúng số) */}
      <Box size={[0.55, 0.06, 0.55]} at={[0, 0.895, 0]} color={PALETTE.steel} />
      <Box size={[0.08, 0.55, 0.08]} at={[0, 0.955, -0.2]} color={PALETTE.steelDark} />
      {/* mặt số tròn quay về +Z: trụ mặc định trục Y nên xoay X π/2 (§10.4) */}
      <mesh position={[0, 1.45, -0.14]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.22, 0.08, 20]} />
        {paint(PALETTE.paper)}
      </mesh>
      {/* kim nổi 0.025 trước mặt số (mặt ở −0.10) */}
      <Box size={[0.03, 0.16, 0.02]} at={[0.05, 1.45, -0.065]} color="#a31220" />
    </group>
  );
}

/** Khay ăn thử: chân cao + mâm + 6 chén nhỏ. */
function SampleStand() {
  return (
    <group>
      <Box size={[0.12, 1.1, 0.12]} at={[0, 0, 0]} color={PALETTE.steelDark} />
      {/* mâm lút vào đầu cột; chén chìm vào mâm cho khỏi bay */}
      <Box size={[0.7, 0.05, 0.7]} at={[0, 1.095, 0]} color={PALETTE.steel} />
      {[-0.2, 0, 0.2].map((x) =>
        [-0.2, 0.2].map((z) => (
          <mesh key={`${x}${z}`} position={[x, 1.16, z]} castShadow>
            <cylinderGeometry args={[0.07, 0.05, 0.09, 12]} />
            {paint(PALETTE.paper)}
          </mesh>
        )),
      )}
    </group>
  );
}

/** Tủ sữa mở: VỎ RỖNG mặt +X (lưng/đáy/nóc/2 hông) + 3 kệ thò ra + hộp
 *  sữa đầy màu NGỒI HẲN NGOÀI thân.
 *  Bản cũ chôn kệ+hộp trong khối đặc: mặt trước hộp trùng khít mặt trước
 *  thân (cùng x = 0.3) nên flicker diện rộng. Vỏ rỗng thì không còn mặt
 *  nào để trùng. Cao 1.7 m, mặt mở sẵn +X nên khỏi yaw. */
const MILK = ["#f7f7f4", "#3b6ea5", "#f7f7f4", "#a31220", "#f7f7f4"] as const;
function DairyCooler() {
  return (
    <group>
      {/* vỏ: đáy + lưng + nóc + 2 hông (chân lút nhau, đỉnh hông chìm
          dưới nóc cho khỏi trùng mặt) */}
      <Box size={[0.8, 0.12, 2.4]} at={[-0.2, 0, 0]} color={PALETTE.concreteDark} />
      <Box size={[0.12, 1.58, 2.4]} at={[-0.54, 0.115, 0]} color={PALETTE.concreteDark} />
      <Box size={[0.8, 0.1, 2.4]} at={[-0.2, 1.6, 0]} color={PALETTE.concreteDark} />
      {[-1.14, 1.14].map((z) => (
        <Box key={z} size={[0.8, 1.68, 0.12]} at={[-0.2, 0, z]} color={PALETTE.concreteDark} />
      ))}
      {/* 3 kệ thò ra khỏi mặt mở (đuôi lút vào lưng) + hộp ngồi lút 0.005 */}
      {[0.42, 0.8, 1.18].map((y, tier) => (
        <group key={y}>
          <Box size={[0.75, 0.05, 2.1]} at={[-0.2, y, 0]} color={PALETTE.concrete} />
          {[-0.8, -0.4, 0, 0.4, 0.8].map((z, i) => (
            <Box
              key={z}
              size={[0.3, 0.32, 0.32]}
              at={[-0.12, y + 0.205, z]}
              color={MILK[(tier + i) % MILK.length]}
            />
          ))}
        </group>
      ))}
    </group>
  );
}

/** Tủ đông ĐỨNG cửa kính: khoang RỖNG thật (không khối lót đặc — đồ chôn
 *  trong khối lót là vô hình từ mọi góc), lưng + hông + nóc + đáy, ruột
 *  sương (lưng-trong + sàn-trong), 3 kệ đồ đông đầy màu, 2 cánh kính trong
 *  0.28 + đố. Mọi khe ≥0.03, mọi đế lút 0.005.
 *  Cao 2.1 m, mặt mở sẵn +X nên khỏi yaw. */
const FROST = ["#a31220", "#3b6ea5", "#5f8a52", "#f7f7f4", "#e8b93c"] as const;
function ChestFreezer() {
  return (
    <group>
      {/* vỏ: đáy + lưng + 2 hông + nóc */}
      <Box size={[1.2, 0.12, 2.4]} at={[0, 0, 0]} color={PALETTE.concrete} />
      <Box size={[0.1, 1.98, 2.4]} at={[-0.55, 0.115, 0]} color={PALETTE.concrete} />
      {[-1.15, 1.15].map((z) => (
        <Box key={z} size={[1.2, 1.98, 0.1]} at={[0, 0.115, z]} color={PALETTE.concrete} />
      ))}
      <Box size={[1.2, 0.1, 2.4]} at={[0, 2.0, 0]} color={PALETTE.concrete} />
      {/* ruột sương: lưng-trong lút 0.01 vào lưng + sàn-trong lút vào đáy */}
      <Box size={[0.04, 1.8, 2.2]} at={[-0.49, 0.14, 0]} color="#e8f1f5" />
      <Box size={[1.0, 0.06, 2.2]} at={[-0.04, 0.115, 0]} color="#e8f1f5" />
      {/* 3 kệ (đuôi lút vào lưng cho có chỗ bám) + đồ đông ngồi lút 0.005 */}
      {[0.6, 1.1, 1.6].map((y, tier) => (
        <group key={y}>
          <Box size={[1.0, 0.05, 2.0]} at={[-0.09, y, 0]} color={PALETTE.steel} />
          {[-0.75, -0.25, 0.25, 0.75].map((z, i) => (
            <Box
              key={z}
              size={[0.55, 0.4, 0.32]}
              at={[-0.09, y + 0.22, z]}
              color={FROST[(tier * 4 + i) % FROST.length]}
            />
          ))}
        </group>
      ))}
      {/* 2 cánh kính trong (0.28 cho xuyên) + đố — kính hở mép tường 0.04 */}
      <mesh position={[0.64, 1.05, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[2.0, 1.8]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.28} />
      </mesh>
      {[0.64, 0.64, 0.64].map((x, i) => (
        <Box
          key={i}
          size={[0.08, 1.8, 0.1]}
          at={[x, 1.05, [-1.0, 0, 1.0][i]]}
          color={PALETTE.steelDark}
        />
      ))}
    </group>
  );
}

/** Quầy bánh: tủ + kệ 2 tầng sau + ổ TO (trụ nằm r 0.14, cầu r 0.17) xen
 *  hai vàng — ổ cũ r 0.11 lẫn màu gỗ, cận cảnh mới thấy. Thêm hàng trên
 *  mặt quầy cho người đứng gần cũng đọc được. */
const LOAF_A = "#e0aa5e";
const LOAF_B = "#c97f3a";
function BakeryCounter() {
  return (
    <group>
      <Box size={[2.6, 0.9, 1.0]} at={[0, 0, 0]} color={PALETTE.wood} />
      {/* mặt quầy + chân kệ lút vào nhau */}
      <Box size={[2.6, 0.06, 1.1]} at={[0, 0.895, 0]} color={PALETTE.woodDark} />
      {/* hàng trên mặt quầy */}
      {[-0.8, 0, 0.8].map((x, i) => (
        <mesh key={x} position={[x, 1.06, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.14, 0.14, 0.5, 12]} />
          {paint(i % 2 ? LOAF_B : LOAF_A)}
        </mesh>
      ))}
      {[0.4, 0.9].map((dz) => (
        <Box key={dz} size={[0.08, 0.8, 0.08]} at={[-1.2, 0.955, dz]} color={PALETTE.woodDark} />
      ))}
      {[0.4, 0.9].map((dz) => (
        <Box key={dz} size={[0.08, 0.8, 0.08]} at={[1.2, 0.955, dz]} color={PALETTE.woodDark} />
      ))}
      {[1.25, 1.65].map((y) => (
        <Box key={y} size={[2.5, 0.05, 1.0]} at={[0, y, 0.65]} color={PALETTE.woodDark} />
      ))}
      {[-1.0, -0.5, 0, 0.5, 1.0].map((x, i) => (
        <group key={x}>
          <mesh position={[x, 1.41, 0.65]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[0.14, 0.14, 0.4, 12]} />
            {paint(i % 2 ? LOAF_B : LOAF_A)}
          </mesh>
          <mesh position={[x, 1.84, 0.65]} castShadow>
            <sphereGeometry args={[0.17, 10, 8]} />
            {paint(i % 2 ? LOAF_A : LOAF_B)}
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Quầy đồ nguội: TỦ RỖNG mặt trước (đế + 2 hông + lưng tối + nóc) + khay
 *  màu trên kệ trong + kính trước + bảng menu treo trên 2 cột.
 *  Bản cũ là khối đặc: kính dán trên mặt đặc + khay chôn trong khối nên cả
 *  hai vô hình (mắt kiểm cận deli). */
const TRAY = ["#a31220", "#5f8a52", "#e8b93c", "#e2601a"] as const;
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
      {/* thân tủ rỗng mặt trước: đế + 2 hông + lưng tối + nóc (chân lút nhau) */}
      <Box size={[2.6, 0.15, 1.0]} at={[0, 0, 0]} color={PALETTE.concrete} />
      {[-1.25, 1.25].map((x) => (
        <Box key={x} size={[0.1, 0.75, 1.0]} at={[x, 0.145, 0]} color={PALETTE.concrete} />
      ))}
      <Box size={[2.6, 0.75, 0.1]} at={[0, 0.145, -0.45]} color={PALETTE.steelDark} />
      <Box size={[2.6, 0.08, 1.05]} at={[0, 0.86, 0]} color={PALETTE.concrete} />
      {/* kệ trong + 4 khay màu (đáy lút vào kệ) */}
      <Box size={[2.4, 0.04, 0.7]} at={[0, 0.4, 0]} color={PALETTE.steel} />
      {[-0.9, -0.3, 0.3, 0.9].map((x, i) => (
        <Box key={x} size={[0.45, 0.12, 0.4]} at={[x, 0.475, 0]} color={TRAY[i % TRAY.length]} />
      ))}
      {/* kính trước hở hông 0.06, hở nóc 0.035 */}
      <mesh position={[0, 0.5, 0.56]} castShadow>
        <planeGeometry args={[2.5, 0.7]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.28} />
      </mesh>
      {[-1.2, 1.2].map((x) => (
        <Box key={x} size={[0.08, 1.8, 0.08]} at={[x, 0.9, -0.3]} color={PALETTE.steelDark} />
      ))}
      <Box size={[2.6, 0.7, 0.06]} at={[0, 1.45, -0.3]} color={PALETTE.wallTrim} />
      {/* mặt bảng trước ở −0.27: chữ nổi 0.035, dưới 0.02 là flicker (§10.6) */}
      {menu && (
        <mesh position={[0, 1.45, -0.235]}>
          <planeGeometry args={[2.4, 0.6]} />
          <meshBasicMaterial map={menu} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Một shape 3 làn (một nhãn): băng chuyền + cổng quét + màn hình mỗi làn.
 *  Thân SÁNG trên đế tối — nguyên khối xám đọc như bê tông (mắt kiểm cận). */
function CheckoutLane() {
  return (
    <group>
      {[-2.4, 0, 2.4].map((x) => (
        <group key={x} position={[x, 0, 0]}>
          {/* thân + đế (đế lòi 0.02 bốn phía) + băng lút vào thân */}
          <Box size={[1.8, 0.9, 0.9]} at={[0, 0, 0]} color={PALETTE.concrete} />
          <Box size={[1.84, 0.12, 0.94]} at={[0, 0, 0]} color={PALETTE.concreteDark} />
          <Box size={[1.8, 0.06, 0.7]} at={[0, 0.895, 0]} color={PALETTE.tire} />
          {/* trụ quét + xà lút vào nhau; trụ màn lút vào băng */}
          {[-0.7, 0.7].map((sx) => (
            <Box
              key={sx}
              size={[0.08, 0.5, 0.08]}
              at={[sx, 0.955, -0.2]}
              color={PALETTE.steelDark}
            />
          ))}
          <Box size={[1.5, 0.08, 0.08]} at={[0, 1.41, -0.2]} color={PALETTE.steelDark} />
          <Box size={[0.08, 0.7, 0.08]} at={[0.6, 0.955, 0.25]} color={PALETTE.steelDark} />
          <Box size={[0.4, 0.3, 0.06]} at={[0.6, 1.5, 0.25]} color={PALETTE.brandBlue} />
        </group>
      ))}
    </group>
  );
}

/** Giấy in trên quầy: tờ TO (0.4 × 0.55) + 4 dòng đậm — ngồi trên mặt
 *  băng (đỉnh 0.925), dòng nổi 0.025 trên mặt giấy. */
function ReceiptSlip() {
  return (
    <group>
      <Box size={[0.4, 0.02, 0.55]} at={[0, 0.925, 0]} color="#ffffff" />
      {[0, 1, 2, 3].map((i) => (
        <Box
          key={i}
          size={[0.3 - i * 0.04, 0.005, 0.03]}
          at={[0, 1.0, -0.18 + i * 0.1]}
          color={PALETTE.steelDark}
        />
      ))}
    </group>
  );
}

/** Hộp ngũ cốc dựng: thân + nhãn trắng + vạch đen. Ngồi trên mặt băng
 *  (đỉnh 0.925), không chìm. */
function BarcodeBox() {
  return (
    <group>
      <Box size={[0.4, 0.5, 0.15]} at={[0, 0.925, 0]} color={PALETTE.cone} />
      <Box size={[0.3, 0.3, 0.02]} at={[0, 1.075, 0.09]} color={PALETTE.paper} />
      {/* vạch nổi 0.025 trên nhãn — dưới 0.02 là flicker (§10.6) */}
      {[0, 1, 2, 3, 4].map((i) => (
        <Box
          key={i}
          size={[0.025, 0.22, 0.005]}
          at={[-0.1 + i * 0.05, 1.075, 0.125]}
          color={PALETTE.tire}
        />
      ))}
    </group>
  );
}

/** Chồng 3 túi giấy lồng nhau trên quầy (đáy ngồi trên mặt băng 0.925). */
function PaperBags() {
  return (
    <group>
      {[0, 1, 2].map((i) => (
        <group key={i} position={[0, i * 0.2, 0]}>
          <Box
            size={[0.5 - i * 0.05, 0.04, 0.35 - i * 0.04]}
            at={[0, 0.925, 0]}
            color={PALETTE.cardbox}
          />
          <Box
            size={[0.5 - i * 0.05, 0.22, 0.03]}
            at={[0, 0.96, 0.16 - i * 0.02]}
            color={PALETTE.cardbox}
          />
          <Box
            size={[0.5 - i * 0.05, 0.22, 0.03]}
            at={[0, 0.96, -0.16 + i * 0.02]}
            color={PALETTE.cardbox}
          />
        </group>
      ))}
    </group>
  );
}

/** Tháp khuyến mãi: pallet + kim tự tháp hộp 3-2-1 + biển PROMO chữ trắng.
 *  Biển đỏ trơn không chữ đọc như cờ hiệu — thêm chữ là rõ chuyện ngay. */
function PromoTower() {
  const face = useMemo(
    () =>
      marketCanvas(256, 128, (ctx) => {
        ctx.fillStyle = "#a31220";
        ctx.fillRect(0, 0, 256, 128);
        ctx.fillStyle = "#f7f7f4";
        ctx.font = "bold 60px sans-serif";
        ctx.fillText("PROMO", 36, 84);
      }),
    [],
  );
  return (
    <group>
      <Box size={[1.6, 0.12, 1.6]} at={[0, 0, 0]} color={PALETTE.woodDark} />
      {/* tầng chồng tầng: đáy lút 0.005 vào đỉnh tầng dưới */}
      {[-0.5, 0.5].map((x) =>
        [-0.5, 0.5].map((z) => (
          <Box
            key={`${x}${z}`}
            size={[0.55, 0.55, 0.55]}
            at={[x, 0.115, z]}
            color={PALETTE.cardbox}
          />
        )),
      )}
      <Box size={[0.55, 0.55, 0.55]} at={[-0.28, 0.665, 0]} color={PALETTE.cone} />
      <Box size={[0.55, 0.55, 0.55]} at={[0.28, 0.665, 0]} color={PALETTE.cone} />
      <Box size={[0.55, 0.5, 0.55]} at={[0, 1.21, 0]} color={PALETTE.paper} />
      <Box size={[0.08, 0.5, 0.08]} at={[0, 1.5, -0.2]} color={PALETTE.steelDark} />
      <Box size={[0.9, 0.5, 0.06]} at={[0, 1.85, -0.2]} color={PALETTE.lampRed} />
      {/* mặt biển trước ở −0.17: chữ nổi 0.035, dưới 0.02 là flicker */}
      {face && (
        <mesh position={[0, 1.85, -0.135]}>
          <planeGeometry args={[0.82, 0.42]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Biển chữ A dựng THẲNG, không xoay: 2 chân + 1 bảng đỏ + mặt % trắng
 *  nổi 0.05. Bản nghiêng cũ tính pháp tuyến bằng tay — đúng một góc nhìn
 *  thì ôm, đổi góc là lơ lửng/flicker. Thẳng thì mọi góc đều ôm. */
function CouponStand() {
  const face = useMemo(
    () =>
      marketCanvas(180, 240, (ctx) => {
        ctx.fillStyle = "#f7f7f4";
        ctx.fillRect(0, 0, 180, 240);
        ctx.fillStyle = "#a31220";
        ctx.font = "bold 150px sans-serif";
        ctx.fillText("%", 40, 195);
      }),
    [],
  );
  return (
    <group>
      {[-0.42, 0.42].map((x) => (
        <Box key={x} size={[0.12, 1.7, 0.12]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      <Box size={[1.02, 1.3, 0.08]} at={[0, 0.35, 0]} color={PALETTE.lampRed} />
      {face && (
        <mesh position={[0, 1.0, 0.09]}>
          <planeGeometry args={[0.9, 1.2]} />
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
      {/* khối lút vào đỉnh cột; chữ nổi 0.04 */}
      <Box size={[0.9, 0.65, 0.9]} at={[0, 1.795, 0]} color={PALETTE.cone} />
      {face && (
        <mesh position={[0, 2.12, 0.49]}>
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
      {/* chữ nổi 0.045 trên mặt biển (mặt ở −0.27) */}
      {face && (
        <mesh position={[0, 1.65, -0.225]}>
          <planeGeometry args={[1.9, 0.42]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
      <group position={[1.5, 0, 0.3]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={PALETTE.leaf} hair={PALETTE.tire} />
      </group>
    </group>
  );
}

export const SUPERMARKET_SHAPES = {
  "entry-door": EntryDoor,
  "exit-door": ExitDoor,
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
      position={[0, 0, -10.78]}
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
      {/* chữ nổi 0.03 trên mặt biển (mặt ở 0.04) */}
      {face && (
        <mesh position={[0, 2.2, 0.07]}>
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
      {/* trụ mặt tiền DÀY hơn dải ngang (0.34 vs 0.3) + đâm lút vào dải:
          cùng độ dày là mặt hông trùng nhau đúng đoạn giao → flicker */}
      {[-13.5, -10, -3.5, 0, 3.5, 10, 13.5].map((x) => (
        <Box key={x} size={[0.6, 3.3, 0.34]} at={[x, 0, 10]} color={PALETTE.wall} />
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
