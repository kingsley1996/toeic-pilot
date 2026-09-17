import { createContext, useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { useTexture } from "@react-three/drei";

/**
 * Vật trong cảnh dựng bằng three primitives, không bằng `.glb`
 * (`SPEC-VISUAL-VOCAB-3D.md` §2.2). Mỗi shape là một `Group` gốc toạ độ
 * nằm trên mặt đất (y = 0), cao dần lên +Y. Khi một shape xấu đến mức người
 * học nhận ra, thay đúng key đó bằng GLB — scene không đổi.
 *
 * Bảng màu 3D là bảng RIÊNG, không phải token CSS: `meshStandardMaterial`
 * không đọc `var()`, và cố bắc cầu hai hệ chỉ để đổi màu nền trời là tự
 * dựng hạ tầng cho một hằng số.
 */
export const PALETTE = {
  concrete: "#c8ced4",
  concreteDark: "#9aa4ad",
  asphalt: "#565e66",
  wall: "#e3e6e9",
  wallTrim: "#40566b",
  doorBlue: "#3b6ea5",
  doorOrange: "#c2620f",
  steel: "#6e7780",
  steelDark: "#3f464d",
  tire: "#2a2e33",
  wood: "#b98a53",
  woodDark: "#93683a",
  cardbox: "#cfa46f",
  paper: "#f7f7f4",
  vanWhite: "#f2f3f4",
  brandBlue: "#2f6f8f",
  board: "#8a5a33",
  cone: "#e2601a",
  skin: "#c08a58",
  /** Mái kho phụ — đỏ gạch để khác mái chính (xanh đá), nhìn là biết hai nhà. */
  roofRed: "#a8502f",
  // đô thị: sơn kẻ đường, bê tông vỉa hè, kính, đèn
  marking: "#eef1f3",
  stone: "#b0b9c1",
  glass: "#9fc0d2",
  lamp: "#f4e2b8",
  lampRed: "#a31220",
  lampGreen: "#2e7d4f",
  leaf: "#5f8a52",
} as const;

/** `flatShading` là chữ ký của cả khu vườn — low-poly đọc ra low-poly. */
export function paint(color: string) {
  return <meshStandardMaterial color={color} flatShading />;
}

/**
 * Shape có biết cảnh đang cho chuyển động không. `SceneObject` trong viewer
 * cung cấp đúng cờ `animated` mà `Mover` dùng — shape đọc để tự tắt animation
 * nội bộ trong recall/reduced-motion mà không cần khoan prop qua registry
 * (`Record<ShapeKey, FC>` không mang prop, đổi nó là đụng mọi shape).
 * Mặc định `true`: shape nào cũng render trong `SceneObject` nên provider
 * luôn có mặt; thiếu thì animation chạy như cũ chứ không chết im.
 */
export const SceneMotionContext = createContext(true);

export function Box({
  size,
  at = [0, 0, 0],
  color,
}: {
  size: [number, number, number];
  at?: [number, number, number];
  color: string;
}) {
  const [w, h, d] = size;
  return (
    <mesh position={[at[0], at[1] + h / 2, at[2]]} castShadow receiveShadow>
      <boxGeometry args={[w, h, d]} />
      {paint(color)}
    </mesh>
  );
}

export function Wheel({ at, r = 0.28 }: { at: [number, number, number]; r?: number }) {
  return (
    <mesh position={at} rotation={[Math.PI / 2, 0, 0]} castShadow>
      <cylinderGeometry args={[r, r, 0.16, 14]} />
      {paint(PALETTE.tire)}
    </mesh>
  );
}

export function Warehouse({ depot = false, roof }: { depot?: boolean; roof?: string }) {
  const w = depot ? 3.4 : 7.4;
  const h = depot ? 2.1 : 3.3;
  const d = depot ? 2.8 : 5.2;
  return (
    <group>
      <Box size={[w, h, d]} color={PALETTE.wall} />
      {/* dải viền mái — hai mảng tường phẳng cùng màu sẽ đọc thành khối giấy.
          Mũ 0.37 thay vì 0.35: mặt trên của nó phải cao hơn nóc tường một chút,
          hai mặt phẳng trùng khít thì depth-buffer đấu nhau và nóc nhấp nháy. */}
      <Box size={[w + 0.15, 0.37, d + 0.15]} at={[0, h - 0.35, 0]} color={roof ?? PALETTE.wallTrim} />
      {/* cửa lớn hướng +Z */}
      <Box size={[w * 0.28, h * 0.62, 0.12]} at={[-w * 0.2, 0, d / 2]} color={PALETTE.doorBlue} />
      <Box size={[w * 0.16, h * 0.5, 0.12]} at={[w * 0.16, 0, d / 2]} color={PALETTE.steelDark} />
      {depot && <Box size={[1.1, 0.5, 0.3]} at={[0, h, -0.4]} color={PALETTE.wallTrim} />}
    </group>
  );
}

function LoadingBay() {
  return (
    <group>
      {/* vệt sơn bến trên nền */}
      <mesh position={[0, 0.01, 0.7]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[2.6, 1.8]} />
        <meshStandardMaterial color={PALETTE.asphalt} />
      </mesh>
      {[-0.9, 0.9].map((x) => (
        <mesh key={x} position={[x, 0.02, 0.7]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.16, 1.8]} />
          <meshStandardMaterial color={PALETTE.doorOrange} />
        </mesh>
      ))}
      {/* tường đoạn + cửa cuốn */}
      <Box size={[2.6, 2.3, 0.5]} color={PALETTE.wall} />
      <Box size={[1.6, 1.7, 0.12]} at={[0, 0, 0.25]} color={PALETTE.steel} />
      {/* nẹp hẹp hơn cửa cuốn một chút: đúng 1.6 thì mặt bên của nó trùng khít
          mặt bên cửa cuốn và nhấp nháy ở mép */}
      {[0.35, 0.8, 1.25].map((y) => (
        <Box key={y} size={[1.54, 0.12, 0.14]} at={[0, y, 0.32]} color={PALETTE.steelDark} />
      ))}
      {/* đà trên cửa: lùi vào trong tường 0.03 ở mặt -Z, cùng lý do như dải mui xe */}
      <Box size={[2.75, 0.22, 0.7]} at={[0, 2.3, 0.13]} color={PALETTE.doorOrange} />
    </group>
  );
}

function Forklift() {
  return (
    <group>
      <Box size={[1.3, 0.75, 0.95]} color={PALETTE.doorOrange} />
      <Box size={[0.75, 0.85, 0.8]} at={[-0.55, 0.75, 0]} color={PALETTE.concreteDark} />
      {/* gọng nâng */}
      <Box size={[0.09, 1.6, 0.09]} at={[0.75, 0, -0.32]} color={PALETTE.steelDark} />
      <Box size={[0.09, 1.6, 0.09]} at={[0.75, 0, 0.32]} color={PALETTE.steelDark} />
      <Box size={[0.5, 0.06, 0.75]} at={[1.0, 0.06, 0]} color={PALETTE.steel} />
      <Wheel at={[-0.45, 0.28, 0.52]} r={0.28} />
      <Wheel at={[-0.45, 0.28, -0.52]} r={0.28} />
      <Wheel at={[0.5, 0.22, 0.52]} r={0.22} />
      <Wheel at={[0.5, 0.22, -0.52]} r={0.22} />
    </group>
  );
}

function CourierVan() {
  return (
    <group>
      <Box size={[1.9, 0.55, 1.05]} at={[0.15, 0.35, 0]} color={PALETTE.vanWhite} />
      <Box size={[0.9, 0.7, 1.0]} at={[0.68, 0.62, 0]} color={PALETTE.brandBlue} />
      <Box size={[0.35, 0.3, 0.9]} at={[0.82, 1.1, 0]} color={PALETTE.concrete} />
      {/* dải màu trên mui: cao hơn nóc thân xe 0.02 và lùi vào hậu 0.06 —
          đúng mặt -X với thân xe thì cạnh sau cũng nhấp nháy như nóc */}
      <Box size={[1.44, 0.2, 1.02]} at={[-0.02, 0.72, 0]} color={PALETTE.brandBlue} />
      <Wheel at={[0.62, 0.28, 0.52]} />
      <Wheel at={[0.62, 0.28, -0.52]} />
      <Wheel at={[-0.58, 0.28, 0.52]} />
      <Wheel at={[-0.58, 0.28, -0.52]} />
    </group>
  );
}

/** Ván gỗ pallet, gốc tại mặt đất. */
function PalletDeck() {
  const slats = [-0.42, 0, 0.42];
  return (
    <group>
      {slats.map((z) => (
        <Box key={`t${z}`} size={[1.1, 0.06, 0.22]} at={[0, 0.14, z]} color={PALETTE.wood} />
      ))}
      {[-0.4, 0, 0.4].map((x) => (
        <Box key={`l${x}`} size={[0.14, 0.14, 0.9]} at={[x, 0, 0]} color={PALETTE.woodDark} />
      ))}
      <Box size={[1.1, 0.05, 0.9]} at={[0, 0, 0]} color={PALETTE.woodDark} />
    </group>
  );
}

function ConsignmentCrate() {
  return (
    <group>
      <PalletDeck />
      <Box size={[0.95, 0.85, 0.8]} at={[0, 0.2, 0]} color={PALETTE.cardbox} />
      {/* đai + nhãn vận đơn ở mặt +Z */}
      <Box size={[0.98, 0.08, 0.83]} at={[0, 0.62, 0]} color={PALETTE.woodDark} />
      <Box size={[0.08, 0.88, 0.83]} at={[0.2, 0.2, 0]} color={PALETTE.woodDark} />
      <Box size={[0.45, 0.3, 0.02]} at={[-0.15, 0.55, 0.41]} color={PALETTE.paper} />
      <Box size={[0.35, 0.03, 0.02]} at={[-0.15, 0.62, 0.43]} color={PALETTE.tire} />
      <Box size={[0.25, 0.03, 0.02]} at={[-0.2, 0.56, 0.43]} color={PALETTE.tire} />
    </group>
  );
}

/** Chồng hàng `cargo`: khác thùng lẻ `consignment-crate` ở chỗ cao hai tầng
 *  + một kiện nhỏ trên cùng — đọc ra "hàng chuyên chở" chứ không phải một lô. */
function CargoStack() {
  return (
    <group>
      <PalletDeck />
      {[
        [-0.5, 0.2],
        [0.5, 0.2],
        [-0.5, 1.0],
        [0.5, 1.0],
      ].map(([x, y], i) => (
        <Box key={i} size={[0.95, 0.8, 0.8]} at={[x, y, 0]} color={PALETTE.cardbox} />
      ))}
      {/* đai ngang tầng dưới + nhãn giấy tầng trên */}
      <Box size={[1.98, 0.08, 0.83]} at={[0, 0.55, 0]} color={PALETTE.woodDark} />
      <Box size={[0.45, 0.3, 0.02]} at={[0.5, 1.35, 0.41]} color={PALETTE.paper} />
      <Box size={[0.7, 0.5, 0.6]} at={[-0.1, 1.8, 0]} color={PALETTE.wood} />
    </group>
  );
}

/** Xe tải `freight` — mũi +X: cabin cam + thùng trắng gân xanh, khác xe
 *  `courier-van` nhỏ trắng-xanh ở cabin thấp và thùng dài gấp rưỡi. Đỗ trên
 *  đường là cố ý (xe đỗ lề), còn container cũ nửa nằm nửa ngoài đường nên
 *  đọc như đặt nhầm — vì thế không dùng container cho từ này. */
function FreightTruck() {
  return (
    <group>
      <Box size={[4.4, 0.3, 1.1]} at={[-0.1, 0.55, 0]} color={PALETTE.steelDark} />
      {/* thùng hàng + gân + cửa hậu −X. Gân thấp hơn nóc 0.03: cao bằng
          nhau là hai mặt trùng khít, nóc nhấp nháy (cùng họ với dải viền
          mái `Warehouse`). */}
      <Box size={[3.0, 2.0, 2.0]} at={[-0.9, 0.85, 0]} color={PALETTE.paper} />
      {[-1.9, -1.3, -0.7, -0.1, 0.5].map((x) => (
        <Box key={x} size={[0.1, 1.94, 2.06]} at={[x, 0.88, 0]} color={PALETTE.brandBlue} />
      ))}
      <Box size={[0.08, 1.8, 0.9]} at={[-2.42, 0.95, -0.48]} color={PALETTE.steelDark} />
      <Box size={[0.08, 1.8, 0.9]} at={[-2.42, 0.95, 0.48]} color={PALETTE.steelDark} />
      {/* cabin: thân thấp + nóc lồi 0.02 mỗi mặt + kính trước lồi 0.03 —
          song song mà cách nhau có 0.01 thì nhìn xiên vẫn nhấp nháy */}
      <Box size={[1.2, 1.1, 1.9]} at={[1.7, 0.7, 0]} color={PALETTE.doorOrange} />
      <Box size={[1.0, 0.7, 1.94]} at={[1.7, 1.5, 0]} color={PALETTE.doorOrange} />
      <Box size={[0.1, 0.6, 1.7]} at={[2.28, 1.5, 0]} color={PALETTE.glass} />
      {[1.7, -0.5, -1.6].flatMap((x) =>
        [0.95, -0.95].map((z) => <Wheel key={`${x}:${z}`} at={[x, 0.4, z]} r={0.4} />),
      )}
    </group>
  );
}

/** Kệ công nghiệp cho động từ `store` — trụ xanh + dầm cam + kiện trên
 *  pallet từng tầng, khác hẳn kệ gỗ gia đình ở khung sắt màu và hàng hoá
 *  xếp theo pallet. Cao 2.8 m. */
function StorageRack() {
  return (
    <group>
      {[
        [-1.26, -0.5],
        [1.26, -0.5],
        [-1.26, 0.5],
        [1.26, 0.5],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.12, 2.8, 0.12]} at={[x, 0, z]} color={PALETTE.brandBlue} />
      ))}
      {/* dầm cam hai tầng, trước + sau */}
      {[1.0, 2.0].map((y) =>
        [-0.5, 0.5].map((z) => (
          <Box key={`${y}:${z}`} size={[2.6, 0.14, 0.1]} at={[0, y, z]} color={PALETTE.doorOrange} />
        )),
      )}
      {/* tầng trệt: hai thùng đặt thẳng nền */}
      <Box size={[0.9, 0.7, 0.8]} at={[-0.6, 0, 0]} color={PALETTE.cardbox} />
      <Box size={[0.9, 0.7, 0.8]} at={[0.6, 0, 0]} color={PALETTE.cardbox} />
      {/* hai tầng trên: pallet + kiện */}
      {[1.07, 2.07].map((y, i) => (
        <group key={y}>
          <Box size={[2.4, 0.08, 0.9]} at={[0, y, 0]} color={PALETTE.woodDark} />
          <Box
            size={[0.95, 0.62, 0.8]}
            at={[-0.6, y + 0.08, 0]}
            color={i === 0 ? PALETTE.cardbox : PALETTE.wood}
          />
          <Box
            size={[0.95, 0.62, 0.8]}
            at={[0.6, y + 0.08, 0]}
            color={i === 0 ? PALETTE.wood : PALETTE.cardbox}
          />
        </group>
      ))}
      {/* nhãn giấy tầng trệt */}
      <Box size={[0.4, 0.28, 0.02]} at={[-0.6, 0.35, 0.41]} color={PALETTE.paper} />
    </group>
  );
}

/** Phiếu giao hàng khổ lớn dán trên kiện — `dispatch note` là tờ giấy đi
 *  cùng hàng, nên giấy phải là nhân vật chính (bản bàn kiểm tra trước để
 *  giấy lọt thỏm giữa đồ đạc, nhìn ra cái bàn). Vẽ bằng canvas offline như
 *  mặt biển `Signboard`, không tải font mạng. */
function useDispatchSlip() {
  return useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 192;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = PALETTE.paper;
    ctx.fillRect(0, 0, 256, 192);
    ctx.strokeStyle = PALETTE.concreteDark;
    ctx.lineWidth = 6;
    ctx.strokeRect(3, 3, 250, 186);
    // đầu phiếu + 3 dòng chữ (vạch như `ClipboardSheet`)
    ctx.fillStyle = PALETTE.concreteDark;
    ctx.fillRect(20, 20, 150, 18);
    ctx.fillStyle = PALETTE.steel;
    for (const y of [60, 86, 112]) ctx.fillRect(20, y, 216, 10);
    // con dấu đỏ góc dưới
    ctx.strokeStyle = PALETTE.lampRed;
    ctx.lineWidth = 5;
    ctx.strokeRect(168, 128, 68, 44);
    ctx.fillStyle = PALETTE.lampRed;
    ctx.fillRect(178, 142, 48, 8);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    return tex;
  }, []);
}

function DispatchCrates() {
  const slip = useDispatchSlip();
  return (
    <group>
      <PalletDeck />
      <Box size={[0.9, 0.7, 0.75]} at={[-0.5, 0.2, 0]} color={PALETTE.cardbox} />
      <Box size={[0.9, 0.7, 0.75]} at={[0.5, 0.2, 0]} color={PALETTE.cardbox} />
      <Box size={[0.7, 0.45, 0.6]} at={[0.4, 0.9, 0]} color={PALETTE.wood} />
      {slip && (
        <mesh position={[-0.5, 0.55, 0.39]}>
          <planeGeometry args={[0.6, 0.45]} />
          <meshBasicMaterial map={slip} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Tem `FRAGILE` vẽ bằng canvas offline: chữ đỏ + pictogram ly nứt (vẽ
 *  bằng nét 2D, không tải ảnh mạng). Không có chữ thì đai đỏ chỉ là "thùng
 *  đẹp", người học không đọc ra dễ vỡ. */
function useFragileMark() {
  return useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 192;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = PALETTE.paper;
    ctx.fillRect(0, 0, 256, 192);
    ctx.strokeStyle = PALETTE.lampRed;
    ctx.lineWidth = 12;
    ctx.strokeRect(6, 6, 244, 180);
    ctx.fillStyle = PALETTE.lampRed;
    ctx.font = "700 44px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("FRAGILE", 128, 56);
    // ly rượu: bầu (cung) + cuống + đế, nét xám
    ctx.strokeStyle = PALETTE.steelDark;
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(128, 108, 26, Math.PI, 0);
    ctx.moveTo(102, 108);
    ctx.lineTo(102, 96);
    ctx.moveTo(154, 108);
    ctx.lineTo(154, 96);
    ctx.moveTo(128, 134);
    ctx.lineTo(128, 162);
    ctx.moveTo(106, 162);
    ctx.lineTo(150, 162);
    ctx.stroke();
    // vết nứt đỏ chéo qua bầu ly
    ctx.strokeStyle = PALETTE.lampRed;
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(112, 88);
    ctx.lineTo(122, 102);
    ctx.lineTo(116, 112);
    ctx.lineTo(128, 124);
    ctx.stroke();
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    return tex;
  }, []);
}

/** Thùng `fragile` — một kiện trên pallet thấp, đai đỏ + tem chữ/biểu tượng
 *  mặt +Z để khác hẳn thùng `consignment` (đai gỗ + nhãn nhỏ). */
function FragileBox() {
  const mark = useFragileMark();
  return (
    <group>
      <PalletDeck />
      <Box size={[0.9, 0.7, 0.75]} at={[0, 0.2, 0]} color={PALETTE.cardbox} />
      {/* đai đỏ chữ thập */}
      <Box size={[0.92, 0.12, 0.77]} at={[0, 0.5, 0]} color={PALETTE.lampRed} />
      <Box size={[0.12, 0.72, 0.77]} at={[0, 0.2, 0]} color={PALETTE.lampRed} />
      {mark && (
        <mesh position={[-0.25, 0.52, 0.39]}>
          <planeGeometry args={[0.36, 0.27]} />
          <meshBasicMaterial map={mark} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}
export function ClipboardSheet({
  at,
  rotation,
}: {
  at: [number, number, number];
  rotation?: [number, number, number];
}) {
  return (
    <group position={at} rotation={rotation}>
      <Box size={[0.85, 1.1, 0.05]} color={PALETTE.board} />
      <Box size={[0.7, 0.9, 0.02]} at={[0, -0.04, 0.03]} color={PALETTE.paper} />
      {/* "số" in thành vạch, barcode thành cụm vạch dày */}
      {[0.2, 0.06, -0.08].map((y) => (
        <Box key={y} size={[0.5, 0.045, 0.01]} at={[-0.05, y, 0.06]} color={PALETTE.concreteDark} />
      ))}
      {[-0.22, -0.16, -0.11, -0.03, 0.04].map((x, i) => (
        <Box
          key={x}
          size={[0.03 + i * 0.008, 0.16, 0.01]}
          at={[x, -0.3, 0.06]}
          color={PALETTE.tire}
        />
      ))}
      <mesh position={[0, 0.55, 0.06]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.045, 0.045, 0.3, 10]} />
        {paint(PALETTE.steel)}
      </mesh>
    </group>
  );
}

/** Kẹp hồ sơ dựng đứng trên cọc — người học phải đọc ra "phiếu theo dõi lô hàng". */
function Clipboard() {
  return (
    <group>
      <mesh position={[0, 0.6, 0]} castShadow>
        <cylinderGeometry args={[0.05, 0.05, 1.2, 8]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      <ClipboardSheet at={[0, 1.45, 0]} rotation={[-0.18, 0, 0]} />
    </group>
  );
}

/** Vật trang trí không bấm được — cần để cảnh đọc ra "khu kho" trước khi học. */
export function Cone({ at }: { at: [number, number, number] }) {
  return (
    <group position={at}>
      <Box size={[0.4, 0.05, 0.4]} color={PALETTE.steelDark} />
      <mesh position={[0, 0.35, 0]} castShadow>
        <coneGeometry args={[0.18, 0.65, 10]} />
        {paint(PALETTE.cone)}
      </mesh>
      <mesh position={[0, 0.41, 0]}>
        <coneGeometry args={[0.115, 0.14, 10]} />
        {paint(PALETTE.paper)}
      </mesh>
    </group>
  );
}

/**
 * Hình người low-poly, mũi quay về +X theo ước lệ của cả khu vườn (`Mover` đổi
 * hướng theo vận tốc nên không được đặt `rotationY` cho vật biết đi). Một định
 * nghĩa duy nhất cho nhân viên kho và người đi bộ — hai bản chép của cùng một
 * cái thân là hai chỗ phải sửa cùng lúc khi đổi tỉ lệ.
 */
export function Person({
  coat = PALETTE.doorBlue,
  hat,
  clipboard = false,
}: {
  coat?: string;
  hat?: string;
  clipboard?: boolean;
}) {
  const body = useRef<THREE.Group>(null);
  const legBack = useRef<THREE.Group>(null);
  const legFront = useRef<THREE.Group>(null);
  const armFree = useRef<THREE.Group>(null);
  const t = useRef(0);
  const here = useRef(new THREE.Vector3());
  const there = useRef(new THREE.Vector3());

  // Tự đo xem mình có đang bị `Mover` đẩy đi không thay vì nhận prop: shape đi
  // bộ nào cũng dùng được qua registry, và không có ai quên truyền cờ.
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
    if (armFree.current) armFree.current.rotation.z = -s * 0.3;
    g.position.y = Math.abs(Math.sin(t.current)) * 0.035;
  });

  return (
    <group ref={body}>
      {/* chân quay quanh khớp hông; mũi chân hướng +X */}
      <group ref={legBack} position={[0, 0.82, -0.11]}>
        <Box size={[0.16, 0.72, 0.2]} at={[0, -0.72, 0]} color={PALETTE.steelDark} />
        <Box size={[0.26, 0.1, 0.22]} at={[0.04, -0.82, 0]} color={PALETTE.tire} />
      </group>
      <group ref={legFront} position={[0, 0.82, 0.11]}>
        <Box size={[0.16, 0.72, 0.2]} at={[0, -0.72, 0]} color={PALETTE.steelDark} />
        <Box size={[0.26, 0.1, 0.22]} at={[0.04, -0.82, 0]} color={PALETTE.tire} />
      </group>
      <Box size={[0.36, 0.62, 0.44]} at={[0, 0.82, 0]} color={coat} />
      <group ref={armFree} position={[0, 1.36, 0.26]}>
        <Box size={[0.12, 0.5, 0.14]} at={[0, -0.5, 0]} color={coat} />
      </group>
      {clipboard ? (
        <>
          {/* Tay ôm phiếu: xoay +Z mới đưa ra TRƯỚC (góc âm là quặt ra sau). */}
          <group position={[0, 1.36, -0.14]} rotation={[0, 0, 1.0]}>
            <Box size={[0.12, 0.46, 0.14]} at={[0, -0.46, 0]} color={coat} />
          </group>
          {/* Phiếu nằm GIỮA ngực (z = 0) và ngửa lên: lệch z ra là nó văng sang
              một bên người, yaw +π/2 mới là mặt phiếu quay về +X. */}
          <group position={[0.2, 1.15, 0]} rotation={[0, Math.PI / 2, 0]}>
            <group rotation={[-1.05, 0, 0]} scale={0.42}>
              <ClipboardSheet at={[0, -0.55, 0]} />
            </group>
          </group>
        </>
      ) : (
        <group position={[0, 1.36, -0.26]}>
          <Box size={[0.12, 0.5, 0.14]} at={[0, -0.5, 0]} color={coat} />
        </group>
      )}
      {/* Đầu quay mũi về +X: cúp mặt bằng rotation.z âm. Cúi bằng trục X thì
          thành nhìn sang bên. Có phiếu thì mắt nhìn xuống phiếu. */}
      <group position={[0.06, 1.44, 0]} rotation={[0, 0, clipboard ? -0.7 : -0.08]}>
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

/** Nhân viên kho: người + mũ bảo hộ + bảng kiểm kê ôm trước ngực. */
export function Worker() {
  return <Person hat={PALETTE.cone} clipboard />;
}

/**
 * Mặt biển vẽ bằng canvas 2D rồi dán lên plane. `drei` có `Text` nhưng nó tải
 * font từ CDN — một cảnh học không được phép chờ mạng để hiện chữ. Canvas thì
 * dùng đúng font hệ thống đang chạy trên trang, và sai cỡ nào cũng chỉ hỏng ở
 * chỗ nó đứng, không hỏng cả cảnh.
 */
export function useSignFace() {
  const mark = useTexture("/brand/mark.png");
  return useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 512;
    const ctx = canvas.getContext("2d");
    const img = mark.image as HTMLImageElement;
    if (!ctx || !img) return null;
    ctx.fillStyle = PALETTE.paper;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 60, 168, 176, 176);
    ctx.textBaseline = "middle";
    ctx.fillStyle = PALETTE.wallTrim;
    ctx.font = "700 132px system-ui, sans-serif";
    ctx.fillText("TOEIC PILOT", 276, 200);
    ctx.fillStyle = PALETTE.steel;
    ctx.font = "400 62px system-ui, sans-serif";
    ctx.fillText("Ôn đúng lúc sắp quên.", 280, 312);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    return tex;
  }, [mark]);
}

/**
 * Biển hiệu đứng SAU toàn bộ vật có nhãn, cao hơn nóc kho để nhìn thấy từ mọi
 * góc. Đặt trước vật có nhãn là che mất từ cần học — đẹp đến đâu cũng vô nghĩa.
 */
export function Signboard({
  at,
  rotationY = 0,
  onPick,
}: {
  at: [number, number, number];
  rotationY?: number;
  /** Bấm biển gọi ra ngoài (viewer mở bảng giới thiệu). Không truyền thì biển
      là vật tĩnh — `billboard` ở urban không truyền nên vẫn mở thẻ từ vựng. */
  onPick?: (faceCenter: [number, number, number]) => void;
}) {
  const face = useSignFace();
  const ref = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);

  useEffect(() => {
    if (!hovered || !onPick) return;
    document.body.style.cursor = "pointer";
    return () => {
      document.body.style.cursor = "";
    };
  }, [hovered, onPick]);

  return (
    <group
      ref={ref}
      position={at}
      rotation={[0, rotationY, 0]}
      onClick={(e) => {
        if (!onPick || !ref.current) return;
        e.stopPropagation();
        // Tâm mặt biển ra world để viewer bay tới — qua `matrixWorld` nên đúng
        // cả khi biển nằm trong group lồng/scale (residence thu 0.72).
        const v = new THREE.Vector3(0, 6.5, 0).applyMatrix4(ref.current.matrixWorld);
        onPick([v.x, v.y, v.z]);
      }}
      onPointerOver={(e) => {
        if (!onPick) return;
        e.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={() => setHovered(false)}
    >
      {[-3.4, 3.4].map((x) => (
        <Box key={x} size={[0.34, 4.2, 0.34]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      <Box size={[9.6, 4.6, 0.22]} at={[0, 4.2, 0]} color={PALETTE.wallTrim} />
      {face && (
        <mesh position={[0, 6.5, 0.12]}>
          <planeGeometry args={[9.0, 4.5]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/**
 * Phần kho. `scene-shapes-urban.tsx` góp phần còn lại và `scene-viewer` gộp
 * thành `Record<ShapeKey, FC>` — gộp ở đó nên thiếu shape nào là `tsc` kêu,
 * thêm key vào `ShapeKey` mà quên vẽ hình không im lặng được.
 */
export const WAREHOUSE_SHAPES = {
  warehouse: () => <Warehouse />,
  depot: () => <Warehouse depot />,
  "loading-bay": LoadingBay,
  forklift: Forklift,
  "courier-van": CourierVan,
  pallet: () => <PalletDeck />,
  "consignment-crate": ConsignmentCrate,
  clipboard: Clipboard,
  "warehouse-manager": Worker,
  "cargo-stack": CargoStack,
  "freight-truck": FreightTruck,
  "storage-rack": StorageRack,
  "dispatch-note": DispatchCrates,
  "fragile-box": FragileBox,
};
