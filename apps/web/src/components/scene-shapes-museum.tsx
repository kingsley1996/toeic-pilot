import { useMemo } from "react";
import * as THREE from "three";

import { Box, PALETTE, Person, Signboard, paint } from "@/components/scene-shapes";

/**
 * Phòng trưng bày bảo tàng (`planning/scenes/museum-3d-scene-spec.md`).
 * Cùng khuôn ba cảnh trước: nền MỘT canvas (sàn gỗ + thảm, không lớp phủ
 * song song), shape gốc đất, mũi người +X. Không trần (nhìn từ trên xuống),
 * tường bắc là object có nhãn `gallery-wall` — tranh/spotlight/bảng treo
 * KHỚP mặt tường nam của nó (z = −11.8), dời tường là dời cả cụm.
 *
 * `Box` lấy GỐC CHÂN (`at` là đáy) — vật đặt TRÊN vật khác (tượng trên bệ,
 * hiện vật trong tủ) phải cộng đúng cao độ trong shape.
 */

export const MUSEUM_SPAN = 36;

const MUS = {
  floor: "#b99c6d",
  floorDark: "#a3865c",
  carpet: "#8e3b2f",
  carpetDark: "#752d24",
  wall: "#e6dfd0",
  wallDark: "#cfc6b2",
  marble: "#efede8",
  marbleDark: "#c9c6bd",
  brass: "#8a6f3c",
  velvet: "#8e2f3c",
  wood: "#7a5a3a",
  woodDark: "#5c422a",
  frame: "#6e5626",
  canvas: "#9db3a8",
  glass: "#9fc0d2",
  screen: "#bfe0ea",
  exitGreen: "#2e7d4f",
  dark: "#2a2e33",
  paper: "#f7f7f4",
  gold: "#d9a92e",
} as const;

/** Kính tủ trưng bày: trong suốt để thấy hiện vật bên trong (`depthWrite
    false` cho sort đúng trước vật đục sau kính). */
function GlassBox({ size, at }: { size: [number, number, number]; at: [number, number, number] }) {
  const [w, h, d] = size;
  return (
    <mesh position={[at[0], at[1] + h / 2, at[2]]} castShadow>
      <boxGeometry args={[w, h, d]} />
      <meshStandardMaterial
        color={MUS.glass}
        transparent
        opacity={0.25}
        roughness={0.1}
        depthWrite={false}
      />
    </mesh>
  );
}

function MuseumPortal() {
  // Cổng vào tân cổ điển ở nam: bậc + 2 cột + dầm ngang.
  return (
    <group>
      {[0.15, 0.3, 0.45].map((y, i) => (
        <Box
          key={y}
          size={[7 - i * 0.8, 0.15, 2.4 - i * 0.4]}
          at={[0, y, 0]}
          color={MUS.marbleDark}
        />
      ))}
      {[-2.2, 2.2].map((x) => (
        <mesh key={x} position={[x, 2.95, 0]} castShadow>
          <cylinderGeometry args={[0.35, 0.4, 5, 12]} />
          {paint(MUS.marble)}
        </mesh>
      ))}
      <Box size={[6.4, 0.8, 1.2]} at={[0, 5.45, 0]} color={MUS.marble} />
      <Box size={[6.6, 0.2, 1.3]} at={[0, 6.25, 0]} color={MUS.marbleDark} />
    </group>
  );
}

function GalleryWall() {
  // Tường bắc 18 m + phào trên + chân tường (mặt nam ở z = +0.2 local).
  return (
    <group>
      <Box size={[18, 5, 0.4]} at={[0, 0, 0]} color={MUS.wall} />
      <Box size={[18.2, 0.25, 0.5]} at={[0, 5, 0]} color={MUS.wallDark} />
      <Box size={[18.1, 0.4, 0.45]} at={[0, 0, 0]} color={MUS.wallDark} />
    </group>
  );
}

function Painting() {
  // Khung vàng + toan phong cảnh. Các lớp cách nhau ≥0.04 m — chồng khít
  // là nhấp nháy z-fighting ở góc xiên (đã dính ở 0.02).
  return (
    <group>
      <Box size={[2.4, 2.0, 0.12]} at={[0, 2.0, 0]} color={MUS.frame} />
      <Box size={[2.0, 1.6, 0.08]} at={[0, 2.0, 0.07]} color={MUS.canvas} />
      <Box size={[2.0, 0.6, 0.06]} at={[0, 1.55, 0.12]} color={PALETTE.leaf} />
    </group>
  );
}

function Mural() {
  // Bích họa phong cảnh vẽ bằng MỘT mặt canvas (trời/mặt trời/núi/sông) —
  // nhiều hộp chồng nhau là nhấp nháy z-fighting không sửa dứt được.
  const face = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 256;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#9db3a8";
    ctx.fillRect(0, 0, 512, 160);
    ctx.fillStyle = "#d9a92e";
    ctx.beginPath();
    ctx.arc(370, 70, 42, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#40566b";
    ctx.beginPath();
    ctx.moveTo(0, 170);
    ctx.lineTo(130, 60);
    ctx.lineTo(260, 170);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#5c422a";
    ctx.beginPath();
    ctx.moveTo(180, 170);
    ctx.lineTo(300, 90);
    ctx.lineTo(420, 170);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#5f8a52";
    ctx.fillRect(0, 170, 512, 40);
    ctx.fillStyle = "#9fc0d2";
    ctx.fillRect(0, 210, 512, 46);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }, []);
  return (
    <group>
      <Box size={[6, 3, 0.08]} at={[0, 1.2, 0]} color={MUS.wallDark} />
      {face && (
        <mesh position={[0, 2.7, 0.09]}>
          <planeGeometry args={[5.7, 2.7]} />
          <meshStandardMaterial map={face} roughness={0.9} />
        </mesh>
      )}
    </group>
  );
}

function Placard() {
  // Bảng thông tin cạnh tranh: nền sẫm + mặt sáng.
  return (
    <group>
      <Box size={[0.8, 0.6, 0.06]} at={[0, 1.5, 0]} color={MUS.woodDark} />
      <Box size={[0.66, 0.46, 0.04]} at={[0, 1.5, 0.03]} color={MUS.paper} />
    </group>
  );
}

function Archway() {
  // Vòm cong sang phòng bên: 2 trụ + vòng nửa vành + buồng tối sau.
  return (
    <group>
      {[-1.1, 1.1].map((x) => (
        <Box key={x} size={[0.6, 3.4, 0.6]} at={[x, 0, 0]} color={MUS.marble} />
      ))}
      <mesh position={[0, 3.4, 0]} castShadow>
        <torusGeometry args={[1.1, 0.22, 8, 14, Math.PI]} />
        {paint(MUS.marble)}
      </mesh>
      {/* hành lang có đèn sau vòm: tường sáng + quầng sáng (không để tối —
          mắt đọc thành lỗ hỏng). */}
      <Box size={[1.7, 3.3, 0.1]} at={[0, 0, -0.3]} color="#d8cbb2" />
      <mesh position={[0, 2.2, -0.24]}>
        <planeGeometry args={[1.1, 0.7]} />
        <meshBasicMaterial color="#f4e2b8" toneMapped={false} />
      </mesh>
    </group>
  );
}

function ExitDoor() {
  // Cửa thoát hiểm + biển EXIT đỏ phát sáng (chữ vẽ bằng canvas offline như
  // mặt Signboard — drei Text tải font từ CDN nên cấm trong cảnh học).
  const sign = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 96;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#a31220";
    ctx.fillRect(0, 0, 256, 96);
    ctx.fillStyle = "#ffffff";
    ctx.font = "700 56px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("EXIT", 128, 52);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }, []);
  return (
    <group>
      <Box size={[1.5, 2.6, 0.14]} at={[0, 0, 0]} color={PALETTE.concreteDark} />
      <Box size={[1.1, 0.08, 0.06]} at={[0, 1.1, 0.1]} color={PALETTE.steelDark} />
      <Box size={[1.0, 0.35, 0.08]} at={[0, 2.95, 0.02]} color={PALETTE.steelDark} />
      {sign && (
        <mesh position={[0, 2.95, 0.09]}>
          <planeGeometry args={[0.9, 0.3]} />
          <meshBasicMaterial map={sign} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

function Spotlight() {
  // Ray ngắn + 1 đầu đèn chúc xuống tranh + chùm sáng mờ.
  return (
    <group>
      <Box size={[1.6, 0.1, 0.1]} at={[0, 4.85, 0]} color={PALETTE.steelDark} />
      <Box size={[0.08, 0.4, 0.08]} at={[0, 4.45, 0.15]} color={PALETTE.steelDark} />
      <mesh position={[0, 4.25, 0.3]} rotation={[0.5, 0, 0]} castShadow>
        <cylinderGeometry args={[0.14, 0.2, 0.35, 10]} />
        {paint(MUS.dark)}
      </mesh>
      <mesh position={[0, 3.1, 0.75]} castShadow={false}>
        <coneGeometry args={[0.85, 2.2, 12, 1, true]} />
        <meshBasicMaterial color="#ffe9b8" transparent opacity={0.14} side={2} depthWrite={false} />
      </mesh>
    </group>
  );
}

function RestorationEasel() {
  // Góc phục chế đọc được ngay: bạt lót + giá vẽ với tranh NỬA SẠCH (trái
  // ố bẩn, phải lộ hình) + bàn dụng cụ (lọ màu, cọ) bên cạnh.
  return (
    <group rotation={[0, Math.PI, 0]}>
      <Box size={[2.6, 0.04, 1.8]} at={[0.3, 0, 0.3]} color={MUS.wallDark} />
      {[-0.45, 0.45].map((x) => (
        <mesh key={x} position={[x, 0.95, 0]} rotation={[0.12, 0, x > 0 ? -0.08 : 0.08]} castShadow>
          <boxGeometry args={[0.09, 2.0, 0.09]} />
          {paint(MUS.wood)}
        </mesh>
      ))}
      {/* toan: nền ố + nửa phải đã phục chế lộ trời/cây */}
      <mesh position={[0, 1.3, 0.12]} rotation={[0.12, 0, 0]} castShadow>
        <boxGeometry args={[1.3, 1.6, 0.07]} />
        {paint(MUS.floorDark)}
      </mesh>
      <mesh position={[0.33, 1.35, 0.17]} rotation={[0.12, 0, 0]}>
        <boxGeometry args={[0.6, 1.4, 0.02]} />
        {paint(MUS.canvas)}
      </mesh>
      <mesh position={[0.33, 1.05, 0.19]} rotation={[0.12, 0, 0]}>
        <boxGeometry args={[0.6, 0.45, 0.02]} />
        {paint(PALETTE.leaf)}
      </mesh>
      {/* bàn dụng cụ + lọ màu + cọ */}
      <Box size={[0.8, 0.72, 0.6]} at={[1.25, 0, 0.2]} color={MUS.woodDark} />
      {[
        [1.1, MUS.carpet],
        [1.3, MUS.gold],
        [1.5, PALETTE.doorBlue],
      ].map(([x, c]) => (
        <mesh key={x as number} position={[x as number, 0.8, 0.2]} castShadow>
          <cylinderGeometry args={[0.07, 0.07, 0.16, 10]} />
          {paint(c as string)}
        </mesh>
      ))}
      <mesh position={[1.3, 0.76, 0.45]} rotation={[0, 0, 1.2]} castShadow>
        <boxGeometry args={[0.5, 0.03, 0.03]} />
        {paint(MUS.wood)}
      </mesh>
    </group>
  );
}

function Pedestal() {
  // Def đặt lệch tây để nhãn khỏi đè tượng — thân lùi đông đúng 1.2 m
  // (mẫu stanchion), bệ world vẫn ở tâm cụm.
  return (
    <group position={[1.2, 0, 0]}>
      <Box size={[1.2, 1.1, 1.2]} at={[0, 0, 0]} color={MUS.marble} />
      <Box size={[1.34, 0.12, 1.34]} at={[0, 1.1, 0]} color={MUS.marbleDark} />
    </group>
  );
}

function Sculpture() {
  // Tượng bán thân trên mặt bệ (gốc nhóm ở y = 1.1 — shape mang cao độ).
  return (
    <group>
      <Box size={[0.5, 0.12, 0.4]} at={[0, 0, 0]} color={MUS.marbleDark} />
      <Box size={[0.44, 0.5, 0.34]} at={[0, 0.12, 0]} color={MUS.marble} />
      <mesh position={[0, 0.82, 0]} castShadow>
        <sphereGeometry args={[0.17, 12, 10]} />
        {paint(MUS.marble)}
      </mesh>
    </group>
  );
}

function Stanchion() {
  // 4 cọc đồng + dây nhung quanh bệ trung tâm. Def đặt ở cọc góc tây-nam
  // cho khỏi đè nhãn bệ lẫn làn guide, nên thân shape lùi đúng vectơ đó
  // (mẫu eaves: gốc nhóm ở đầu có nhãn, thân trải về phía còn lại) — world
  // vẫn ôm khít bệ.
  const posts: [number, number][] = [
    [-1.8, -1.8],
    [1.8, -1.8],
    [1.8, 1.8],
    [-1.8, 1.8],
  ];
  return (
    <group position={[1.8, 0, -1.8]}>
      {posts.map(([x, z]) => (
        <group key={`${x}:${z}`} position={[x, 0, z]}>
          <mesh position={[0, 0.03, 0]} castShadow>
            <cylinderGeometry args={[0.22, 0.26, 0.06, 12]} />
            {paint(MUS.brass)}
          </mesh>
          <mesh position={[0, 0.5, 0]} castShadow>
            <cylinderGeometry args={[0.05, 0.05, 0.95, 8]} />
            {paint(MUS.brass)}
          </mesh>
          <mesh position={[0, 1.0, 0]} castShadow>
            <sphereGeometry args={[0.08, 10, 8]} />
            {paint(MUS.brass)}
          </mesh>
        </group>
      ))}
      {[-1.8, 1.8].map((z) => (
        <Box key={z} size={[3.6, 0.07, 0.07]} at={[0, 0.78, z]} color={MUS.velvet} />
      ))}
      {[-1.8, 1.8].map((x) => (
        <Box key={x} size={[0.07, 0.07, 3.6]} at={[x, 0.78, 0]} color={MUS.velvet} />
      ))}
    </group>
  );
}

function DisplayCase() {
  // Tủ kính: đế gỗ + lót nhung + hộp kính + nắp.
  return (
    <group>
      <Box size={[1.4, 0.9, 1.4]} at={[0, 0, 0]} color={MUS.wood} />
      <Box size={[0.9, 0.12, 0.9]} at={[0, 0.9, 0]} color={MUS.velvet} />
      <GlassBox size={[1.2, 1.4, 1.2]} at={[0, 0.9, 0]} />
      <Box size={[1.34, 0.1, 1.34]} at={[0, 2.3, 0]} color={MUS.woodDark} />
    </group>
  );
}

function Artifact() {
  // Bình gốm TRONG tủ tây (gốc nhóm trên mặt đế y = 0.9, lót nhung dày
  // 0.12 — shape mang cao độ, def y = 0.9).
  return (
    <group>
      <Box size={[0.5, 0.08, 0.5]} at={[0, 0.12, 0]} color={MUS.velvet} />
      <mesh position={[0, 0.44, 0]} castShadow>
        <sphereGeometry args={[0.28, 14, 12]} />
        {paint(PALETTE.cardbox)}
      </mesh>
      <mesh position={[0, 0.72, 0]} castShadow>
        <cylinderGeometry args={[0.11, 0.16, 0.25, 12]} />
        {paint(PALETTE.cardbox)}
      </mesh>
    </group>
  );
}

function Guide() {
  // Hướng dẫn viên: huy hiệu + que chỉ về phía tượng.
  return (
    <group>
      <Person coat="#7a2f3f" />
      <Box size={[0.1, 0.12, 0.03]} at={[0.19, 1.25, 0.12]} color={MUS.paper} />
      <mesh position={[0.62, 1.05, -0.14]} rotation={[0, 0, -0.15]} castShadow>
        <boxGeometry args={[0.95, 0.045, 0.045]} />
        {paint(MUS.woodDark)}
      </mesh>
    </group>
  );
}

function Visitors() {
  // Nhóm khách nghe thuyết minh: ba áo khác màu.
  return (
    <group>
      <Person coat={PALETTE.doorBlue} />
      <group position={[0.85, 0, 0.35]}>
        <Person coat={PALETTE.leaf} />
      </group>
      <group position={[-0.8, 0, 0.45]}>
        <Person coat={PALETTE.cone} />
      </group>
    </group>
  );
}

function AudioGuideVisitor() {
  // Khách đeo tai nghe thuyết minh: vòng + 2 củ tai.
  return (
    <group>
      <Person coat={PALETTE.doorOrange} />
      <Box size={[0.3, 0.05, 0.38]} at={[0.06, 1.74, 0]} color={MUS.dark} />
      {[-0.19, 0.19].map((z) => (
        <Box key={z} size={[0.12, 0.14, 0.08]} at={[0.06, 1.52, z]} color={MUS.dark} />
      ))}
      <Box size={[0.16, 0.22, 0.04]} at={[0.3, 1.0, 0.2]} color={MUS.dark} />
    </group>
  );
}

function BrochureVisitor() {
  // Khách cầm tờ gấp: giấy trắng nghiêng trước ngực.
  return (
    <group>
      <Person coat="#3f6b5a" />
      <mesh position={[0.32, 1.05, 0]} rotation={[0, 0, -0.5]} castShadow>
        <boxGeometry args={[0.3, 0.02, 0.42]} />
        {paint(MUS.paper)}
      </mesh>
    </group>
  );
}

function TicketVisitor() {
  // Khách giơ vé ở cửa: thẻ cam trên tay (đi tuần ngắn vào cửa).
  return (
    <group>
      <Person coat="#8a6f3c" />
      <Box size={[0.22, 0.14, 0.03]} at={[0.42, 1.25, -0.2]} color={PALETTE.cone} />
    </group>
  );
}

function Bench() {
  return (
    <group>
      {[-0.9, 0.9].map((x) => (
        <Box key={x} size={[0.12, 0.45, 0.7]} at={[x, 0, 0]} color={MUS.woodDark} />
      ))}
      {[-0.25, 0, 0.25].map((z) => (
        <Box key={z} size={[2.2, 0.08, 0.2]} at={[0, 0.45, z]} color={MUS.wood} />
      ))}
    </group>
  );
}

function Kiosk() {
  // Trạm tra cứu: chân + màn hình nghiêng mặt về giữa phòng (−X).
  return (
    <group rotation={[0, -Math.PI / 2, 0]}>
      <Box size={[0.5, 1.1, 0.4]} at={[0, 0, 0]} color={MUS.dark} />
      <group position={[0, 1.35, 0.1]} rotation={[-0.25, 0, 0]}>
        <Box size={[0.9, 0.7, 0.08]} at={[0, 0, 0]} color={MUS.dark} />
        <mesh position={[0, 0, 0.06]}>
          <planeGeometry args={[0.76, 0.56]} />
          <meshBasicMaterial color={MUS.screen} toneMapped={false} />
        </mesh>
      </group>
    </group>
  );
}

function Turnstile() {
  // Cổng soát vé: 2 tủ + càng ngang.
  return (
    <group>
      {[-0.55, 0.55].map((x) => (
        <Box key={x} size={[0.35, 1.05, 1.2]} at={[x, 0, 0]} color={PALETTE.steel} />
      ))}
      <Box size={[0.08, 0.08, 1.1]} at={[0, 0.95, 0]} color={PALETTE.steelDark} />
      {[0.25, -0.25].map((z) => (
        <Box key={z} size={[0.75, 0.06, 0.06]} at={[0, 0.95, z]} color={PALETTE.steelDark} />
      ))}
    </group>
  );
}

function DonationBox() {
  // Hộp quyên góp trong suốt trên chân + đồng xu trong.
  return (
    <group>
      <Box size={[0.4, 1.0, 0.4]} at={[0, 0, 0]} color={MUS.woodDark} />
      <GlassBox size={[0.6, 0.55, 0.6]} at={[0, 1.0, 0]} />
      <mesh position={[0, 1.08, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.16, 0.1, 12]} />
        {paint(MUS.gold)}
      </mesh>
    </group>
  );
}

function Cloakroom() {
  // Quầy gửi áo: bàn + giá treo 3 áo.
  return (
    <group>
      <Box size={[2.4, 1.05, 0.8]} at={[0, 0, 0]} color={MUS.wood} />
      {[-1.0, 1.0].map((x) => (
        <Box key={x} size={[0.08, 2.0, 0.08]} at={[x, 0, -0.9]} color={MUS.woodDark} />
      ))}
      <Box size={[2.2, 0.07, 0.07]} at={[0, 1.95, -0.9]} color={MUS.woodDark} />
      {[
        [-0.6, "#7a2f3f"],
        [0, PALETTE.doorBlue],
        [0.6, PALETTE.leaf],
      ].map(([x, c]) => (
        <mesh key={x as number} position={[x as number, 1.5, -0.9]} castShadow>
          <sphereGeometry args={[0.26, 10, 8]} />
          {paint(c as string)}
        </mesh>
      ))}
    </group>
  );
}

function SouvenirCounter() {
  // Quầy lưu niệm: bàn + hộp quà + giá bưu thiếp.
  return (
    <group>
      <Box size={[2.4, 1.0, 0.9]} at={[0, 0, 0]} color={MUS.wood} />
      {[
        [-0.7, 0.25, MUS.velvet],
        [-0.35, 0.4, MUS.gold],
        [0.1, 0.3, PALETTE.doorBlue],
      ].map(([x, s, c], i) => (
        <Box
          key={i}
          size={[0.3, s as number, 0.3]}
          at={[x as number, 1.0, 0.1]}
          color={c as string}
        />
      ))}
      {[0.55, 0.75, 0.95].map((x) => (
        <mesh key={x} position={[x, 1.25, -0.2]} rotation={[-0.2, 0, 0]} castShadow>
          <boxGeometry args={[0.02, 0.4, 0.3]} />
          {paint(MUS.paper)}
        </mesh>
      ))}
    </group>
  );
}

function ExhibitPanel() {
  // Panô giới thiệu triển lãm ở lối vào: 2 chân SAU bảng (cách 0.12 m —
  // chân xuyên mặt bảng là nhấp nháy z-fighting) + bảng 2 mảng màu.
  return (
    <group>
      {[-0.7, 0.7].map((x) => (
        <Box key={x} size={[0.09, 1.5, 0.09]} at={[x, 0, -0.12]} color={MUS.woodDark} />
      ))}
      <Box size={[1.9, 1.35, 0.08]} at={[0, 1.55, 0]} color={MUS.wallDark} />
      <Box size={[1.7, 0.4, 0.04]} at={[0, 1.95, 0.04]} color={MUS.carpet} />
      <Box size={[1.7, 0.6, 0.04]} at={[0, 1.35, 0.04]} color={MUS.paper} />
    </group>
  );
}

export const MUSEUM_SHAPES = {
  museum: MuseumPortal,
  exhibit: ExhibitPanel,
  guide: Guide,
  visitor: Visitors,
  curator: () => <Person coat={PALETTE.wallTrim} clipboard />,
  painting: Painting,
  sculpture: Sculpture,
  pedestal: Pedestal,
  "display-case": DisplayCase,
  artifact: Artifact,
  placard: Placard,
  stanchion: Stanchion,
  "audio-guide": AudioGuideVisitor,
  brochure: BrochureVisitor,
  ticket: TicketVisitor,
  guard: () => <Person coat={MUS.dark} hat={PALETTE.doorBlue} />,
  "gallery-wall": GalleryWall,
  spotlight: Spotlight,
  bench: Bench,
  turnstile: Turnstile,
  kiosk: Kiosk,
  "donation-box": DonationBox,
  cloakroom: Cloakroom,
  souvenir: SouvenirCounter,
  restoration: RestorationEasel,
  archway: Archway,
  exit: ExitDoor,
  mural: Mural,
};

export function MuseumEnvironment({
  onBrandPick,
}: {
  onBrandPick?: (faceCenter: [number, number, number]) => void;
}) {
  return (
    <group>
      {/* sàn gỗ + thảm (canvas ở viewer? không — vẽ phẳng bằng mesh để khỏi
          thêm texture: sàn một màu + thảm một tấm, không mặt song song vì
          thảm dày 0.04 nằm trên sàn). */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[MUSEUM_SPAN, MUSEUM_SPAN]} />
        <meshStandardMaterial color={MUS.floor} roughness={0.7} />
      </mesh>
      <Box size={[2.6, 0.04, 16]} at={[0, 0, 4]} color={MUS.carpet} />
      <Box size={[2.8, 0.02, 16.2]} at={[0, 0, 4]} color={MUS.carpetDark} />
      {/* tường hông đông/tây (tường bắc là object `gallery-wall` có nhãn) */}
      {[-14, 14].map((x) => (
        <Box key={x} size={[0.4, 5, 20]} at={[x, 0, -2]} color={MUS.wall} />
      ))}
      {/* tủ tây (decor, không nhãn — nhãn `artifact` nằm trong, nhãn
          `display case` ở tủ đông) */}
      <group position={[-6, 0, -1]}>
        <DisplayCase />
      </group>
      {/* biển chào ở lề đường phía nam, ĐÔNG cổng (cách mép bậc 1.3 m,
          ngoài rào, nền sau là cỏ) — mặt quay ra đường (khách đi tới),
          không quay vào camera */}
      <group position={[5, 0, 14]} rotation={[0, 0, 0]} scale={0.35}>
        <Signboard at={[0, 0, 0]} onPick={onBrandPick} />
      </group>
    </group>
  );
}
