import { Suspense, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { Box, PALETTE, Person, paint, useSignFace } from "@/components/scene-shapes";

/**
 * Văn phòng mở — cùng khuôn `scene-shapes-construction.tsx`: shape là group
 * gốc đất (y = 0), mũi người +X, màu tái dùng `PALETTE` chung (đồ văn phòng
 * không cần bảng màu riêng như đất công trường).
 *
 * Quy ước đọc để 21 từ khỏi lẫn nhau:
 * - 4 bảng tường phân biệt bằng cấu trúc canvas: danh bạ (dòng tên),
 *   phân ca (lưới giờ), lịch (lưới tháng + khoanh đỏ), đánh giá
 *   (checkbox + ✓ đỏ). Canvas offline như mặt biển `Signboard`.
 * - 3 cụm người phân biệt bằng đạo cụ + hướng mặt + tĩnh/động: interview
 *   đối mặt qua bàn (tĩnh), collaborate cùng nhìn bảng (tĩnh), personnel
 *   đi thành hàng (động, idiom tour museum).
 * - Đồ nhỏ (điện thoại, giấy sửa, máy tính) tự mang theo bàn của nó như
 *   kiện `dispatch-crates` mang pallet — bàn decor rời là bấm vào bàn
 *   không ăn mà vật thì quá bé để bấm.
 */

const PAPER_BLUE = "#bcd3e0";

function officeCanvas(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void) {
  // Helper thuần, không phải hook: mỗi shape gọi trong `useMemo` của nó.
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

/** Bàn làm việc chung: mặt + 4 chân + ghế. Màn hình là tuỳ chọn vì bàn
 *  giấy sửa cần mặt thoáng. */
function DeskBase({ w = 1.6, monitor = true }: { w?: number; monitor?: boolean }) {
  return (
    <group>
      <Box size={[w, 0.07, 0.8]} at={[0, 0.73, 0]} color={PALETTE.concrete} />
      {[
        [-w / 2 + 0.05, -0.34],
        [w / 2 - 0.05, -0.34],
        [-w / 2 + 0.05, 0.34],
        [w / 2 - 0.05, 0.34],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.06, 0.73, 0.06]} at={[x, 0, z]} color={PALETTE.steelDark} />
      ))}
      {/* ghế: mặt + lưng + trụ + đế */}
      <Box size={[0.45, 0.07, 0.45]} at={[0, 0.45, 0.78]} color={PALETTE.wallTrim} />
      <Box size={[0.45, 0.55, 0.07]} at={[0, 0.52, 0.98]} color={PALETTE.wallTrim} />
      <Box size={[0.06, 0.45, 0.06]} at={[0, 0, 0.78]} color={PALETTE.steelDark} />
      <mesh position={[0, 0.03, 0.78]} castShadow>
        <cylinderGeometry args={[0.26, 0.26, 0.05, 12]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      {monitor && (
        <>
          <Box size={[0.08, 0.32, 0.08]} at={[0, 0.8, -0.15]} color={PALETTE.steelDark} />
          <Box size={[0.7, 0.45, 0.05]} at={[0, 1.0, -0.15]} color={PALETTE.steelDark} />
          {/* mặt sáng lồi 0.025 trước thân — 0.005 là depth đấu nhau ở xa,
              màn hình "chết" như đã thấy trên preview */}
          <mesh position={[0, 1.0, -0.10]}>
            <planeGeometry args={[0.62, 0.37]} />
            <meshBasicMaterial color="#bfe3ef" toneMapped={false} />
          </mesh>
          <Box size={[0.5, 0.03, 0.2]} at={[0, 0.8, 0.18]} color={PALETTE.concreteDark} />
        </>
      )}
    </group>
  );
}

/** Điện thoại bàn `extension` — đế + ống nghe gác + cụm phím 3×3 + màn hình. */
function ExtensionPhone() {
  return (
    <group>
      <DeskBase />
      <Box size={[0.28, 0.06, 0.2]} at={[-0.5, 0.8, 0.1]} color={PALETTE.steelDark} />
      <Box size={[0.26, 0.05, 0.07]} at={[-0.5, 0.88, 0.02]} color={PALETTE.tire} />
      {[-0.06, 0, 0.06].flatMap((dx) =>
        [-0.04, 0, 0.04].map((dz) => (
          <Box
            key={`${dx}:${dz}`}
            size={[0.04, 0.02, 0.04]}
            at={[-0.5 + dx, 0.86, 0.12 + dz]}
            color={PALETTE.paper}
          />
        )),
      )}
      <Box size={[0.16, 0.02, 0.05]} at={[-0.5, 0.86, 0.0]} color={PALETTE.glass} />
    </group>
  );
}

/** Tờ trình sửa `revise` — 1 tờ duy nhất + vạch sửa đỏ + bút đỏ khổ lớn
 *  gác chéo. Khác `memo` (nhiều note ghim bảng tường) ở một-to-nằm. */
function ReviseSet() {
  return (
    <group>
      <DeskBase monitor={false} />
      <Box size={[0.5, 0.02, 0.65]} at={[0.1, 0.8, 0]} color={PALETTE.paper} />
      {[0.12, 0.0, -0.12].map((dz) => (
        <Box key={dz} size={[0.3, 0.005, 0.03]} at={[0.05, 0.822, dz]} color={PALETTE.concreteDark} />
      ))}
      {/* 2 vạch sửa đỏ đè lên dòng chữ */}
      {[0.06, -0.06].map((dz) => (
        <Box key={dz} size={[0.2, 0.006, 0.025]} at={[0.12, 0.825, dz]} color={PALETTE.lampRed} />
      ))}
      {/* bút đỏ nằm chéo qua tờ giấy */}
      <group position={[0.1, 0.85, 0]} rotation={[0, 0.5, Math.PI / 2]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.025, 0.025, 0.4, 8]} />
          {paint(PALETTE.lampRed)}
        </mesh>
        <mesh position={[0, 0.24, 0]} castShadow>
          <coneGeometry args={[0.025, 0.08, 8]} />
          {paint(PALETTE.tire)}
        </mesh>
      </group>
    </group>
  );
}

/** Phiếu lương `PAY SLIP` vẽ canvas offline: đầu xanh chữ trắng + dòng
 *  + tổng đỏ. Không có chữ thì máy tính + phong bì chỉ đọc ra "đồ văn
 *  phòng", người học không nối được tới lương. */
function usePaySlip() {
  return useMemo(
    () =>
      officeCanvas(256, 192, (ctx) => {
        ctx.fillStyle = PALETTE.paper;
        ctx.fillRect(0, 0, 256, 192);
        ctx.fillStyle = PALETTE.brandBlue;
        ctx.fillRect(0, 0, 256, 48);
        ctx.fillStyle = PALETTE.paper;
        ctx.font = "700 30px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("PAY SLIP", 128, 34);
        ctx.fillStyle = PALETTE.concreteDark;
        for (const y of [70, 96, 122]) ctx.fillRect(20, y, 190, 10);
        ctx.fillStyle = PALETTE.lampRed;
        ctx.fillRect(20, 146, 120, 26);
        ctx.fillStyle = PALETTE.paper;
        ctx.fillRect(30, 153, 80, 12);
      }),
    [],
  );
}

/** Góc tính lương `payroll` — bàn phụ + máy tính phím vuông + phong bì
 *  lương dấu đỏ + phiếu PAY SLIP dựng lều. Bàn nhỏ + đồ tiền + chữ thì
 *  khác hẳn bàn làm việc. */
function PayrollSet() {
  const slip = usePaySlip();
  return (
    <group>
      <Box size={[1.3, 0.06, 0.6]} at={[0, 0.7, 0]} color={PALETTE.wood} />
      {[
        [-0.6, -0.25],
        [0.6, -0.25],
        [-0.6, 0.25],
        [0.6, 0.25],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.06, 0.7, 0.06]} at={[x, 0, z]} color={PALETTE.woodDark} />
      ))}
      {/* máy tính: thân nằm trên mặt bàn (0.76), phím + màn hình trên thân (0.81) */}
      <Box size={[0.28, 0.05, 0.4]} at={[-0.44, 0.76, 0]} color={PALETTE.steelDark} />
      <Box size={[0.2, 0.02, 0.08]} at={[-0.44, 0.81, -0.13]} color={PALETTE.glass} />
      {[0, 1, 2].flatMap((r) =>
        [0, 1, 2].map((c) => (
          <Box
            key={`${r}:${c}`}
            size={[0.05, 0.02, 0.05]}
            at={[-0.51 + c * 0.075, 0.81, -0.02 + r * 0.08]}
            color={PALETTE.paper}
          />
        )),
      )}
      {/* phong bì lương + dấu đỏ */}
      <Box size={[0.32, 0.02, 0.22]} at={[-0.04, 0.76, 0]} color={PALETTE.paper} />
      <Box size={[0.1, 0.02, 0.1]} at={[0.0, 0.78, 0]} color={PALETTE.lampRed} />
      {/* phiếu dựng lều ngửa về camera để đọc được chữ từ trên cao */}
      {slip && (
        <mesh position={[0.38, 0.9, -0.05]} rotation={[-0.35, 0, 0]}>
          <planeGeometry args={[0.4, 0.3]} />
          <meshBasicMaterial map={slip} toneMapped={false} side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  );
}

/** Tủ hồ sơ `cabinet` — thân + 3 ngăn lồi 0.02 + tay nắm (học offset nóc kho). */
function FilingCabinet() {
  return (
    <group>
      <Box size={[0.9, 1.4, 0.6]} color={PALETTE.steel} />
      {[0.25, 0.68, 1.11].map((y) => (
        <group key={y}>
          <Box size={[0.8, 0.36, 0.03]} at={[0, y - 0.18, 0.3]} color={PALETTE.concrete} />
          <Box size={[0.3, 0.04, 0.05]} at={[0, y - 0.05, 0.32]} color={PALETTE.steelDark} />
        </group>
      ))}
      <Box size={[0.94, 0.05, 0.64]} at={[0, 1.4, 0]} color={PALETTE.steelDark} />
    </group>
  );
}

/** Kệ văn phòng phẩm `stationery` — khung + 2 tầng: hộp màu, cốc bút, xấp giấy. */
function StationeryShelf() {
  return (
    <group>
      {[
        [-0.66, -0.21],
        [0.66, -0.21],
        [-0.66, 0.21],
        [0.66, 0.21],
      ].map(([x, z]) => (
        <Box key={`${x}:${z}`} size={[0.06, 1.4, 0.06]} at={[x, 0, z]} color={PALETTE.woodDark} />
      ))}
      {[0.5, 1.05].map((y) => (
        <Box key={y} size={[1.4, 0.06, 0.5]} at={[0, y, 0]} color={PALETTE.wood} />
      ))}
      <Box size={[0.3, 0.28, 0.4]} at={[-0.4, 0.56, 0]} color={PALETTE.doorOrange} />
      <Box size={[0.3, 0.28, 0.4]} at={[0.0, 0.56, 0]} color={PALETTE.brandBlue} />
      <Box size={[0.32, 0.2, 0.42]} at={[0.4, 1.11, 0]} color={PALETTE.leaf} />
      {/* cốc bút: 2 ống + bút thò đầu */}
      {[-0.35, -0.1].map((x, i) => (
        <group key={x}>
          <mesh position={[x, 1.2, 0]} castShadow>
            <cylinderGeometry args={[0.07, 0.06, 0.16, 10]} />
            {paint(i === 0 ? PALETTE.lampRed : PALETTE.steelDark)}
          </mesh>
          <mesh position={[x + 0.02, 1.32, 0]} castShadow>
            <cylinderGeometry args={[0.012, 0.012, 0.14, 6]} />
            {paint(PALETTE.tire)}
          </mesh>
        </group>
      ))}
      <Box size={[0.4, 0.1, 0.3]} at={[0.35, 0.56, 0]} color={PALETTE.paper} />
    </group>
  );
}

/** Bảng ghim `memo` — khung gỗ + 6 note màu + đinh. Không canvas: giấy màu
 *  đã đọc ra "tin dán", khác `revise` 1 tờ trên bàn. Bảng chiếm y 1.0..2.1. */
function MemoBoard() {
  const notes: Array<{ at: [number, number, number]; color: string }> = [
    { at: [-0.6, 1.53, 0.05], color: PALETTE.paper },
    { at: [-0.2, 1.58, 0.05], color: "#f2c94c" },
    { at: [0.2, 1.51, 0.05], color: PALETTE.paper },
    { at: [0.6, 1.57, 0.05], color: PALETTE.leaf },
    { at: [-0.4, 1.13, 0.05], color: PALETTE.doorOrange },
    { at: [0.3, 1.11, 0.05], color: PAPER_BLUE },
  ];
  return (
    <group>
      <Box size={[1.8, 1.1, 0.07]} at={[0, 1.0, 0]} color={PALETTE.woodDark} />
      <Box size={[1.66, 0.96, 0.02]} at={[0, 1.07, 0.03]} color="#c9a876" />
      {notes.map((n, i) => (
        /* giấy trước phông 0.0175 — dưới 0.01 là xa nhấp nháy */
        <group key={i} position={[n.at[0], n.at[1], 0.065]}>
          <Box size={[0.3, 0.34, 0.015]} color={n.color} />
          <mesh position={[0, 0.14, 0.012]}>
            <sphereGeometry args={[0.025, 8, 6]} />
            {paint(PALETTE.lampRed)}
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Khung treo tường chung cho 4 bảng canvas: khung + mặt vẽ. `at` là TÂM
 *  mặt bảng (khác `Box` lấy gốc chân) để def tính nhãn theo tâm cho tiện.
 *  `easel` dựng thêm 2 chân sau để bảng đứng độc lập giữa phòng (lịch hẹn
 *  không còn chỗ trên tường bắc mà vẫn phải tách khỏi evaluation). */
function WallBoard({
  size,
  at,
  face,
  easel = false,
}: {
  size: [number, number];
  at: [number, number, number];
  face: THREE.Texture | null;
  easel?: boolean;
}) {
  const [w, h] = size;
  const [cx, cy, cz] = at;
  return (
    <group>
      {/* `Box` lấy tâm theo x/z, gốc chân theo y: khung tâm (cx, cy),
          chân = cy − nửa cao; mặt vẽ trước khung 0.02 cho khỏi đấu depth */}
      <Box
        size={[w + 0.1, h + 0.1, 0.06]}
        at={[cx, cy - (h + 0.1) / 2, cz - 0.05]}
        color={PALETTE.steelDark}
      />
      {face && (
        <mesh position={[cx, cy, cz]}>
          <planeGeometry args={[w, h]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
      {easel &&
        [-0.35, 0.35].map((dx) => (
          /* chân sau cách lưng khung 0.03 — dính vào mới đấu depth */
          <Box
            key={dx}
            size={[0.08, 1.1, 0.08]}
            at={[cx + dx, 0, cz - 0.15]}
            color={PALETTE.steelDark}
          />
        ))}
    </group>
  );
}

/** Danh bạ `directory` — 6 dòng tên + số (vạch như `ClipboardSheet`). */
function DirectoryBoard() {
  const face = useMemo(
    () =>
      officeCanvas(384, 256, (ctx) => {
        ctx.fillStyle = PALETTE.paper;
        ctx.fillRect(0, 0, 384, 256);
        for (let i = 0; i < 6; i++) {
          const y = 26 + i * 38;
          ctx.fillStyle = PALETTE.wallTrim;
          ctx.fillRect(20, y, 150, 14);
          ctx.fillStyle = PALETTE.concreteDark;
          ctx.fillRect(230, y, 120, 14);
        }
      }),
    [],
  );
  return <WallBoard size={[1.8, 1.2]} at={[0, 1.6, 0]} face={face} />;
}

/** Bảng phân ca `shift` — lưới 3 ca × 5 ngày + ô đã xếp kín (đặc), ô trống (rỗng). */
function ShiftBoard() {
  const face = useMemo(
    () =>
      officeCanvas(384, 256, (ctx) => {
        ctx.fillStyle = PALETTE.paper;
        ctx.fillRect(0, 0, 384, 256);
        ctx.strokeStyle = PALETTE.steelDark;
        ctx.lineWidth = 3;
        for (let r = 0; r <= 3; r++) {
          ctx.beginPath();
          ctx.moveTo(90, 20 + r * 72);
          ctx.lineTo(368, 20 + r * 72);
          ctx.stroke();
        }
        for (let c = 0; c <= 5; c++) {
          ctx.beginPath();
          ctx.moveTo(90 + c * 55.6, 20);
          ctx.lineTo(90 + c * 55.6, 236);
          ctx.stroke();
        }
        // ca sáng full, ca chiều 3/5, ca đêm 1/5 — đọc ra "lịch xếp người"
        ctx.fillStyle = PALETTE.brandBlue;
        for (let c = 0; c < 5; c++) ctx.fillRect(94 + c * 55.6, 24, 47, 64);
        for (let c = 0; c < 3; c++) ctx.fillRect(94 + c * 55.6, 96, 47, 64);
        ctx.fillRect(94, 168, 47, 64);
        ctx.fillStyle = PALETTE.lampRed;
        ctx.font = "700 26px system-ui, sans-serif";
        ctx.fillText("S", 40, 70);
        ctx.fillText("C", 40, 142);
        ctx.fillText("Đ", 40, 214);
      }),
    [],
  );
  return <WallBoard size={[1.6, 1.1]} at={[0, 1.6, 0]} face={face} />;
}

/** Lịch hẹn `appointment` — lưới tháng + 1 ô khoanh đỏ ("ngày có hẹn"). */
function AppointmentCalendar() {
  const face = useMemo(
    () =>
      officeCanvas(256, 288, (ctx) => {
        ctx.fillStyle = PALETTE.paper;
        ctx.fillRect(0, 0, 256, 288);
        ctx.fillStyle = PALETTE.lampRed;
        ctx.fillRect(0, 0, 256, 44);
        ctx.fillStyle = PALETTE.paper;
        ctx.font = "700 26px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("THÁNG 9", 128, 31);
        ctx.strokeStyle = PALETTE.concreteDark;
        ctx.lineWidth = 2;
        for (let r = 0; r <= 4; r++) {
          ctx.beginPath();
          ctx.moveTo(16, 56 + r * 56);
          ctx.lineTo(240, 56 + r * 56);
          ctx.stroke();
        }
        for (let c = 0; c <= 6; c++) {
          ctx.beginPath();
          ctx.moveTo(16 + c * 32, 56);
          ctx.lineTo(16 + c * 32, 280);
          ctx.stroke();
        }
        // ô hẹn: cột 3, hàng 2
        ctx.strokeStyle = PALETTE.lampRed;
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.arc(16 + 3.5 * 32, 56 + 1.5 * 56, 15, 0, Math.PI * 2);
        ctx.stroke();
      }),
    [],
  );
  return (
    <group>
      {/* đứng giá chữ A giữa phòng: tường bắc hết chỗ mà nhãn lịch dính
          vào evaluation thì hỏng cả hai (giá thay kẹp treo tường) */}
      <WallBoard size={[0.9, 1.05]} at={[0, 1.6, 0]} face={face} easel />
    </group>
  );
}

/** Bảng đánh giá `evaluation` — giấy lớn + 4 hàng checkbox, 3 ✓ 1 ☐ + ✓ đỏ to. */
function EvaluationBoard() {
  const face = useMemo(
    () =>
      officeCanvas(288, 320, (ctx) => {
        ctx.fillStyle = PALETTE.paper;
        ctx.fillRect(0, 0, 288, 320);
        ctx.fillStyle = PALETTE.wallTrim;
        ctx.fillRect(24, 20, 200, 20);
        for (let i = 0; i < 4; i++) {
          const y = 70 + i * 56;
          ctx.strokeStyle = PALETTE.steelDark;
          ctx.lineWidth = 4;
          ctx.strokeRect(24, y, 28, 28);
          ctx.fillStyle = PALETTE.concreteDark;
          ctx.fillRect(66, y + 8, 150, 12);
        }
        // 3 dấu ✓, 1 ô trống
        ctx.strokeStyle = PALETTE.leaf;
        ctx.lineWidth = 7;
        for (const y of [70, 126, 182]) {
          ctx.beginPath();
          ctx.moveTo(28, y + 14);
          ctx.lineTo(36, y + 22);
          ctx.lineTo(50, y + 4);
          ctx.stroke();
        }
        ctx.strokeStyle = PALETTE.lampRed;
        ctx.lineWidth = 12;
        ctx.beginPath();
        ctx.moveTo(210, 250);
        ctx.lineTo(232, 276);
        ctx.lineTo(272, 220);
        ctx.stroke();
      }),
    [],
  );
  return <WallBoard size={[1.2, 1.35]} at={[0, 1.55, 0]} face={face} />;
}

/** Đồng hồ `punctual` — kim hình học chỉ 8 giờ đúng ("đúng giờ vào ca"):
 *  kim giờ xoay −120° quanh Z (8h là xuôi chiều kim đồng hồ 120° kể từ
 *  12h), kim phút chỉ 12h. Mặt r 0.42, vành r 0.48. */
function PunctualClock() {
  return (
    <group>
      {/* cylinder trục Y phải xoay X π/2 mới quay mặt +Z — để nguyên là mặt
          đồng hồ nằm ngửa (đã từng úp sai hướng mà vẫn ra hình). */}
      <mesh position={[0, 2.7, 0.02]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.48, 0.48, 0.07, 24]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      <mesh position={[0, 2.7, 0.06]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.42, 0.42, 0.02, 24]} />
        {paint(PALETTE.paper)}
      </mesh>
      {/* vạch 12-3-6-9: nửa chìm trong mặt (không chạm khít, không lơ lửng) */}
      {[
        [0, 0.34],
        [0.34, 0],
        [0, -0.34],
        [-0.34, 0],
      ].map(([x, y], i) => (
        <Box key={i} size={[0.05, 0.09, 0.02]} at={[x, 2.7 + y - 0.045, 0.075]} color={PALETTE.steelDark} />
      ))}
      <group position={[0, 2.7, 0.09]} rotation={[0, 0, (-2 * Math.PI) / 3]}>
        <Box size={[0.05, 0.24, 0.015]} at={[0, 0.1, 0]} color={PALETTE.tire} />
      </group>
      {/* kim phút chỉ 12h, đầu kim chạm vành trong (không thò ra ngoài mặt) */}
      <mesh position={[0, 2.96, 0.0975]}>
        <boxGeometry args={[0.04, 0.28, 0.015]} />
        {paint(PALETTE.tire)}
      </mesh>
      <mesh position={[0, 2.7, 0.105]}>
        <sphereGeometry args={[0.035, 10, 8]} />
        {paint(PALETTE.lampRed)}
      </mesh>
    </group>
  );
}

/** Thẻ nhân viên `badge` phóng to trên stand — thẻ cứng + ảnh + vạch tên +
 *  kẹp + dây đeo chữ V. Học idiom `hard-hat` (vật đội/đeo phóng to đặt bệ). */
function BadgeStand() {
  return (
    <group>
      <mesh position={[0, 0.55, 0]} castShadow>
        <cylinderGeometry args={[0.05, 0.07, 1.1, 8]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      <mesh position={[0, 0.03, 0]} castShadow>
        <cylinderGeometry args={[0.2, 0.24, 0.06, 10]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      {/* dây đeo */}
      <Box size={[0.05, 0.4, 0.02]} at={[-0.09, 1.75, 0]} color={PALETTE.lampRed} />
      <group position={[0.09, 1.75, 0]} rotation={[0, 0, 0.45]}>
        <Box size={[0.05, 0.4, 0.02]} color={PALETTE.lampRed} />
      </group>
      <Box size={[0.12, 0.08, 0.04]} at={[0, 1.56, 0]} color={PALETTE.steel} />
      {/* thẻ + chi tiết lồi 0.02 trước mặt — 0.0025 là xa nhấp nháy */}
      <Box size={[0.44, 0.58, 0.03]} at={[0, 1.22, 0]} color={PALETTE.paper} />
      <Box size={[0.38, 0.1, 0.035]} at={[0, 1.44, 0.02]} color={PALETTE.brandBlue} />
      <Box size={[0.14, 0.16, 0.035]} at={[-0.1, 1.2, 0.02]} color={PALETTE.glass} />
      <Box size={[0.16, 0.05, 0.035]} at={[0.09, 1.24, 0.02]} color={PALETTE.concreteDark} />
      <Box size={[0.16, 0.05, 0.035]} at={[0.09, 1.16, 0.02]} color={PALETTE.concreteDark} />
      <Box size={[0.3, 0.04, 0.035]} at={[0, 1.02, 0.02]} color={PALETTE.lampRed} />
    </group>
  );
}

/** Máy chấm công `attendance` — chân đế + thân máy + khe quẹt + thẻ cắm nửa
 *  chừng + đèn xanh. "Cái máy", khác `badge` là "cái thẻ". */
function AttendanceRecorder() {
  return (
    <group>
      <Box size={[0.5, 1.0, 0.4]} color={PALETTE.steel} />
      <Box size={[0.55, 0.42, 0.32]} at={[0, 1.0, 0]} color={PALETTE.wallTrim} />
      {/* nắp lồi 0.02 mỗi mặt cho khỏi đấu depth với thân */}
      <Box size={[0.59, 0.05, 0.36]} at={[0, 1.42, 0]} color={PALETTE.steelDark} />
      <Box size={[0.3, 0.05, 0.03]} at={[0, 1.12, 0.17]} color={PALETTE.tire} />
      {/* thẻ cắm nửa chừng: thò ra ngoài mặt máy, y ngang khe */}
      <Box size={[0.2, 0.16, 0.02]} at={[-0.1, 1.1, 0.22]} color={PALETTE.paper} />
      <mesh position={[0.18, 1.28, 0.17]}>
        <sphereGeometry args={[0.035, 10, 8]} />
        <meshBasicMaterial color={PALETTE.lampGreen} />
      </mesh>
    </group>
  );
}

/** Loa thông báo `notify` — giá treo + hộp + loa kèn chĩa xuống. Treo cao
 *  2.9 m, khác điện thoại bàn ở cao độ + hướng phát. */
function NotifySpeaker() {
  return (
    <group>
      <Box size={[0.1, 0.9, 0.1]} at={[0, 2.2, 0]} color={PALETTE.steelDark} />
      <Box size={[0.36, 0.26, 0.26]} at={[0, 2.85, 0]} color={PALETTE.steelDark} />
      {/* loa kèn chĩa xuống-trước: +Y xoay 2.2 rad thành (−0.59, +0.81)
          theo y/z nên miệng loe hướng xuống phòng */}
      <group position={[0, 2.72, 0.12]} rotation={[2.2, 0, 0]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.2, 0.07, 0.32, 12]} />
          {paint(PALETTE.concrete)}
        </mesh>
      </group>
    </group>
  );
}

/** Quầy lễ tân `reception` — quầy dài + mặt đá + chuông gọi + xấp brochure.
 *  Vách logo thương hiệu nằm ở environment (decor có `onPick` riêng). */
function ReceptionDesk() {
  return (
    <group>
      <Box size={[2.6, 1.0, 0.7]} color={PALETTE.wood} />
      <Box size={[2.8, 0.06, 0.85]} at={[0, 1.0, 0]} color={PALETTE.concrete} />
      <Box size={[2.2, 0.6, 0.03]} at={[0, 0.35, 0.36]} color={PALETTE.woodDark} />
      {/* chuông gọi */}
      <mesh position={[-0.8, 1.06, 0.1]} castShadow>
        <sphereGeometry args={[0.06, 10, 8, 0, Math.PI * 2, 0, Math.PI / 2]} />
        {paint(PALETTE.steel)}
      </mesh>
      <Box size={[0.12, 0.02, 0.12]} at={[-0.8, 1.03, 0.1]} color={PALETTE.steelDark} />
      {/* xấp brochure nằm trên mặt đá (1.06), không lún vào */}
      <Box size={[0.35, 0.1, 0.25]} at={[0.7, 1.06, 0]} color={PALETTE.paper} />
      <Box size={[0.35, 0.02, 0.25]} at={[0.7, 1.16, 0]} color={PALETTE.brandBlue} />
    </group>
  );
}

/** Phỏng vấn `interview` — bàn tròn + 2 ghế + 2 người đối mặt + folder.
 *  Verb thành tiểu cảnh như `weld` ở construction. */
function InterviewSet() {
  return (
    <group>
      <mesh position={[0, 0.72, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.45, 0.45, 0.05, 16]} />
        {paint(PALETTE.wood)}
      </mesh>
      <mesh position={[0, 0.36, 0]} castShadow>
        <cylinderGeometry args={[0.05, 0.07, 0.7, 8]} />
        {paint(PALETTE.steelDark)}
      </mesh>
      {/* ghế để NGOÀI người (±1.15) — để cùng chỗ là chân người xuyên
          qua mặt ghế. Người đứng giữa bàn và ghế như vừa đứng lên. */}
      {[-1.15, 1.15].map((x) => (
        <group key={x}>
          <Box size={[0.42, 0.07, 0.42]} at={[x, 0.45, 0]} color={PALETTE.wallTrim} />
          <Box
            size={[0.42, 0.5, 0.07]}
            at={[x + (x > 0 ? 0.2 : -0.2), 0.52, 0]}
            color={PALETTE.wallTrim}
          />
        </group>
      ))}
      <group position={[-0.85, 0, 0]}>
        <Person coat={PALETTE.brandBlue} clipboard />
      </group>
      <group position={[0.85, 0, 0]} rotation={[0, Math.PI, 0]}>
        <Person coat={PALETTE.steel} />
      </group>
      <Box size={[0.3, 0.03, 0.22]} at={[0, 0.75, 0.1]} color={PALETTE.paper} />
    </group>
  );
}

/** Cộng tác `collaborate` — bảng trắng vẽ biểu đồ + 2 người cùng phía, một
 *  người cầm gậy chỉ. Khác interview ở không bàn + cùng nhìn một hướng. */
function CollaborateSet() {
  const face = useMemo(
    () =>
      officeCanvas(384, 224, (ctx) => {
        ctx.fillStyle = "#fdfefe";
        ctx.fillRect(0, 0, 384, 224);
        // trục + đường tăng
        ctx.strokeStyle = PALETTE.steelDark;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(40, 190);
        ctx.lineTo(360, 190);
        ctx.moveTo(40, 190);
        ctx.lineTo(40, 20);
        ctx.stroke();
        ctx.strokeStyle = PALETTE.brandBlue;
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(50, 170);
        ctx.lineTo(140, 140);
        ctx.lineTo(220, 150);
        ctx.lineTo(330, 60);
        ctx.stroke();
        ctx.strokeStyle = PALETTE.lampRed;
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(220, 150);
        ctx.lineTo(330, 60);
        ctx.stroke();
      }),
    [],
  );
  return (
    <group>
      {[-0.85, 0.85].map((x) => (
        <Box key={x} size={[0.08, 1.9, 0.08]} at={[x, 0, -0.35]} color={PALETTE.steelDark} />
      ))}
      {/* bảng chân y 0.7 (0.7..1.85, trong trụ) — để 1.25 là lơ lửng trên trụ */}
      <Box size={[1.9, 1.15, 0.06]} at={[0, 0.7, -0.35]} color={PALETTE.steel} />
      {face && (
        /* mặt vẽ trước thân 0.03 — 0.01 là xa cũng nhấp nháy (đúng bệnh vừa dính) */
        <mesh position={[0, 1.275, -0.29]}>
          <planeGeometry args={[1.78, 1.03]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
      {/* khay bút chìm 0.02 vào chân bảng: giao nhau thì không đấu depth,
          chạm khít mặt mới đấu */}
      <Box size={[1.9, 0.06, 0.12]} at={[0, 0.66, -0.3]} color={PALETTE.steelDark} />
      {/* 2 người cùng quay mặt −Z vào bảng */}
      <group position={[-0.4, 0, 0.45]} rotation={[0, Math.PI / 2, 0]}>
        <Person coat={PALETTE.doorBlue} />
      </group>
      <group position={[0.45, 0, 0.5]} rotation={[0, Math.PI / 2, 0]}>
        <Person coat={PALETTE.leaf} />
      </group>
      {/* gậy chỉ dài 0.5: đầu chạm đúng mặt bảng, dài nữa là xuyên qua */}
      <group position={[-0.4, 1.3, 0.1]} rotation={[-1.1, 0, 0]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.015, 0.015, 0.5, 6]} />
          {paint(PALETTE.woodDark)}
        </mesh>
      </group>
    </group>
  );
}

/** Đội ngũ `personnel` — 3 người đi thành hàng, cùng patrol ở def (idiom
 *  tour museum: cùng nhịp là giữ đội hình). Một object, một nhãn. */
function PersonnelTeam() {
  return (
    <group>
      <group position={[-0.75, 0, 0]}>
        <Person coat={PALETTE.doorBlue} />
      </group>
      <group position={[0, 0, 0.15]}>
        <Person coat={PALETTE.wallTrim} clipboard />
      </group>
      <group position={[0.75, 0, 0]}>
        <Person coat={PALETTE.leaf} />
      </group>
    </group>
  );
}

export const OFFICE_SHAPES = {  supervisor: () => <Person coat={PALETTE.wallTrim} clipboard />,
  intern: () => (
    <group>
      <Person coat={PALETTE.doorOrange} />
      {/* chồng hồ sơ ôm trước ngực — đi cùng người vì cùng group shape */}
      <Box size={[0.36, 0.12, 0.3]} at={[0.34, 1.0, 0]} color={PALETTE.cardbox} />
      <Box size={[0.36, 0.12, 0.3]} at={[0.34, 1.12, 0]} color={PALETTE.paper} />
    </group>
  ),
  candidate: () => (
    <group>
      <Person coat={PALETTE.leaf} />
      <Box size={[0.08, 0.4, 0.3]} at={[0, 1.05, -0.32]} color={PALETTE.brandBlue} />
    </group>
  ),
  interview: InterviewSet,
  "personnel-team": PersonnelTeam,
  collaborate: CollaborateSet,
  "reception-desk": ReceptionDesk,
  "directory-board": DirectoryBoard,
  "badge-stand": BadgeStand,
  "appointment-calendar": AppointmentCalendar,
  "punctual-clock": PunctualClock,
  "office-cabinet": FilingCabinet,
  "stationery-shelf": StationeryShelf,
  "extension-phone": ExtensionPhone,
  "payroll-set": PayrollSet,
  "shift-board": ShiftBoard,
  "memo-board": MemoBoard,
  "attendance-recorder": AttendanceRecorder,
  "revise-set": ReviseSet,
  "evaluation-board": EvaluationBoard,
  "notify-speaker": NotifySpeaker,
};

/** Kính decor dùng chung: trong như dải kính tường bắc, và KHÔNG nhận
 *  raycast — kính trước vật có nhãn mà nuốt click là hỏng im lặng
 *  (cùng luật mũi tên nhãn ở viewer). */
function GlassPane({
  size,
  at,
  opacity = 0.28,
}: {
  size: [number, number, number];
  at: [number, number, number];
  opacity?: number;
}) {
  return (
    <mesh position={[at[0], at[1] + size[1] / 2, at[2]]} raycast={() => null}>
      <boxGeometry args={size} />
      <meshStandardMaterial color={PALETTE.glass} transparent opacity={opacity} />
    </mesh>
  );
}

/**
 * Cửa kính lối vào phía nam — khung + 1 cánh cố định + 1 cánh trượt mở
 * (lệch trước 0.45 là đọc ra "đang mở"). Decor, không gắn từ: máy
 * `attendance` đứng cạnh mới là từ vựng.
 */
function GlassEntrance({ at }: { at: [number, number, number] }) {
  return (
    <group position={at}>
      {/* trụ + đà + ngưỡng (toạ độ TÂM theo x/z như `Box`) */}
      {[-2.0, 2.0].map((x) => (
        <Box key={x} size={[0.2, 2.5, 0.2]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      {/* đà lút 0.06 vào đầu trụ: chạm khít mặt mới đấu depth */}
      <Box size={[4.2, 0.3, 0.25]} at={[0, 2.44, 0]} color={PALETTE.steelDark} />
      <Box size={[3.8, 0.04, 0.34]} at={[0, 0, 0]} color={PALETTE.steel} />
      {/* cánh cố định (tây) + cánh trượt mở (lệch trước 0.45 là đọc ra "đang mở") */}
      <GlassPane size={[1.7, 2.4, 0.05]} at={[-0.95, 0.05, 0]} />
      <GlassPane size={[1.7, 2.4, 0.05]} at={[-0.05, 0.05, 0.45]} />
      {/* tay nắm cánh mở */}
      <Box size={[0.05, 0.5, 0.05]} at={[-0.5, 1.0, 0.5]} color={PALETTE.steelDark} />
    </group>
  );
}

/**
 * Phòng họp kính bao cụm interview — 3 vách kính U (mở hướng nam làm lối
 * vào) + trụ góc + đà nóc, không trần. Kính trong nên bàn ghế bên trong
 * vẫn đọc được từ camera đầu; nhãn interview treo trên nóc kính (2.9 m).
 */
function MeetingGlassRoom({ at }: { at: [number, number, number] }) {
  return (
    <group position={at}>
      {/* U kính mở hướng nam (tâm x/z như `Box`, chân y) */}
      <GlassPane size={[3.6, 2.2, 0.06]} at={[0, 0, -1.6]} />
      <GlassPane size={[0.06, 2.2, 3.6]} at={[-1.8, 0, 0.2]} />
      <GlassPane size={[0.06, 2.2, 3.6]} at={[1.8, 0, 0.2]} />
      {[
        [-1.8, -1.6],
        [1.8, -1.6],
        [-1.8, 2.0],
        [1.8, 2.0],
      ].map(([x, z]) => (
        /* trụ cao lút vào đà (2.26 > nóc kính 2.2): chạm khít mặt mới đấu */
        <Box key={`${x}:${z}`} size={[0.12, 2.26, 0.12]} at={[x, 0, z]} color={PALETTE.steelDark} />
      ))}
      <Box size={[3.84, 0.12, 0.12]} at={[0, 2.14, -1.6]} color={PALETTE.steelDark} />
      <Box size={[0.12, 0.12, 3.84]} at={[-1.8, 2.14, 0.2]} color={PALETTE.steelDark} />
      <Box size={[0.12, 0.12, 3.84]} at={[1.8, 2.14, 0.2]} color={PALETTE.steelDark} />
    </group>
  );
}
/**
 * Mặt kính phía nam kín từ mép tường tây tới mép đất phía đông — văn phòng
 * nhìn từ ngoài vào như khối kính một mặt, không còn hở/trống phía camera.
 * Cửa vào (`GlassEntrance` ở x 1..5) nằm giữa mặt này: đà ngang CHIA ĐÔI
 * né đúng khoảng cửa để khỏi chập hai đà vào nhau (giao nhau còn được,
 * trùng khít mới flicker — nhưng hai đà song sinh thì nhìn vẫn rối).
 */
function GlassFacade() {
  const panelsWest = [
    [-13, -9],
    [-9, -5],
    [-5, -1],
    [-1, 1],
  ];
  const panelsEast = [
    [5, 9],
    [9, 13],
  ];
  return (
    <group position={[0, 0, 8]}>
      {/* panel hẹp hơn khoảng trụ 0.2 (hở 0.1 mỗi bên) — khít vào trụ là đấu depth */}
      {[...panelsWest, ...panelsEast].map(([x0, x1]) => (
        <GlassPane key={`${x0}:${x1}`} size={[x1 - x0 - 0.2, 2.4, 0.05]} at={[(x0 + x1) / 2, 0.05, 0]} />
      ))}
      {[-13, -9, -5, -1, 1, 5, 9, 13].map((x) => (
        <Box key={x} size={[0.15, 2.5, 0.15]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      {/* đà ngang hai đoạn (chừa khoảng cửa) lút 0.06 vào đầu trụ;
          ngưỡng cũng chia đôi để khỏi chập với ngưỡng cửa */}
      <Box size={[14.2, 0.3, 0.2]} at={[-6.1, 2.44, 0]} color={PALETTE.steelDark} />
      <Box size={[8.2, 0.3, 0.2]} at={[9.1, 2.44, 0]} color={PALETTE.steelDark} />
      <Box size={[14.2, 0.04, 0.3]} at={[-6.1, 0, 0]} color={PALETTE.steel} />
      <Box size={[8.2, 0.04, 0.3]} at={[9.1, 0, 0]} color={PALETTE.steel} />
    </group>
  );
}
/**
 * Nền văn phòng mở (`office-floor`): sàn thảm lưới 1 m, tường bắc 3 m có
 * dải kính, tường tây đặc, mặt kính phía nam kín hai mép, cửa kính lối vào
 * + phòng họp kính. Phía đông mở để camera nhìn vào. Không trần — camera
 * nhìn từ trên cao nên trần chỉ che mất vật.
 *
 * Vách ngăn cubicle là decor NHƯNG toạ độ của nó ràng buộc với object
 * (bàn phải nằm trong ô): con số chốt ở đây, file `office.ts` chỉ việc
 * đặt bàn vào đúng ô đã vẽ (tiền lệ cặp `CURVE_SEGS`-def ở urban §7.10):
 * - Ô 1: x −10.75..−8, z −3.5..0 → bàn extension ở (−9.4, −2.2).
 * - Ô 2: x −8..−5.25, z −3.5..0 → bàn revise ở (−6.6, −2.2).
 */

/** Sàn thảm: lưới 1 m vẽ thẳng bằng pixel (không `Math.random` — texture
 *  phải giống nhau giữa hai lần load, không thì preview flake). */
function useCarpet() {
  return useMemo(() => {
    const PPM = 32;
    const size = 30 * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#aeb6bd";
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "#9aa2a9";
    ctx.lineWidth = 2;
    for (let i = 0; i <= 30; i++) {
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

/** Vách ngăn cubicle cao 1.4 m — camera nhìn qua được, người ngồi thì khuất. */
function Partition({ at, along }: { at: [number, number, number]; along: "x" | "z" }) {
  const len = along === "x" ? 5.5 : 3.5;
  const size: [number, number, number] = along === "x" ? [len, 1.4, 0.12] : [0.12, 1.4, len];
  return (
    <group position={at}>
      <Box size={size} color={PALETTE.concrete} />
      <Box
        size={along === "x" ? [len, 0.08, 0.16] : [0.16, 0.08, len]}
        at={[0, 1.4, 0]}
        color={PALETTE.wallTrim}
      />
    </group>
  );
}

/** Nữ lễ tân đứng sau quầy — decor, không nhãn. `Person` + tóc dày đọc được
 *  từ xa (rộng hơn đầu 0.08 mỗi bên — bản cũ chỉ hơn 0.03 nên ở xa như hói),
 *  áo trắng; quầy cao 1 m che chân nên khỏi cần váy. Đứng lệch đông quầy
 *  cho khỏi chui dưới nhãn `reception` (nhãn treo đúng giữa quầy theo trục
 *  logo). Tóc căn theo tâm đầu (x = 0.06, không phải 0). */
function Receptionist({ at }: { at: [number, number, number] }) {
  return (
    <group position={at} rotation={[0, -Math.PI / 2, 0]}>
      <Person coat={PALETTE.paper} />
      {/* tóc: gáy dài tới lưng + đỉnh phủ qua trán đầu + 2 lọn + búi
          (mũi người +X nên gáy ở −X).
          CHÚ Ý: `Box` lấy gốc CHÂN theo y — đầu `Person` cao tới 1.72
          (nhóm ở 1.44 + hộp 0.28, không phải tâm 1.44!), tóc phải phủ QUA
          con số đó; lần trước tính nhầm tâm nên da đầu thò lên trên tóc. */}
      <Box size={[0.14, 0.9, 0.4]} at={[-0.18, 1.0, 0]} color={PALETTE.tire} />
      <Box size={[0.44, 0.14, 0.44]} at={[0.06, 1.66, 0]} color={PALETTE.tire} />
      {[-0.17, 0.17].map((z) => (
        <Box key={z} size={[0.1, 0.4, 0.09]} at={[-0.08, 1.32, z]} color={PALETTE.tire} />
      ))}
      <mesh position={[-0.16, 1.84, 0]} castShadow>
        <sphereGeometry args={[0.11, 10, 8]} />
        {paint(PALETTE.tire)}
      </mesh>
    </group>
  );
}

/** Máy nước nóng lạnh decor góc đông gần cửa. */
function WaterCooler({ at }: { at: [number, number, number] }) {
  return (
    <group position={at}>
      <Box size={[0.45, 0.9, 0.45]} color={PALETTE.paper} />
      <Box size={[0.3, 0.12, 0.3]} at={[0, 0.9, 0]} color={PALETTE.steelDark} />
      <mesh position={[0, 1.25, 0]} castShadow>
        <cylinderGeometry args={[0.17, 0.17, 0.5, 12]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.6} />
      </mesh>
      <Box size={[0.1, 0.08, 0.05]} at={[0, 0.6, 0.24]} color={PALETTE.lampRed} />
      <Box size={[0.1, 0.08, 0.05]} at={[0, 0.6, -0.24]} color={PALETTE.brandBlue} />
    </group>
  );
}

/** Chậu cây decor — 3 nón lá trên chậu, cùng họ low-poly cả cảnh. */
function Plant({ at }: { at: [number, number, number] }) {
  return (
    <group position={at}>
      <mesh position={[0, 0.2, 0]} castShadow>
        <cylinderGeometry args={[0.22, 0.17, 0.4, 10]} />
        {paint("#a8573c")}
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

/**
 * Logo thương hiệu dán tường bắc sau quầy lễ tân — cùng mặt vẽ `useSignFace`
 * của `Signboard` nhưng không chân (trong nhà không dựng biển cột). Bấm mở
 * Panel giới thiệu như biển ngoài trời (§9.6): tâm mặt qua `matrixWorld`
 * nên đúng cả khi group lồng nhau.
 */
function LogoPlate({ onPick }: { onPick: (faceCenter: [number, number, number]) => void }) {
  const face = useSignFace();
  const ref = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState(false);
  return (
    <group
      ref={ref}
      position={[2, 0, -9.83]}
      onClick={(e) => {
        if (!ref.current) return;
        e.stopPropagation();
        const v = new THREE.Vector3(0, 2.0, 0).applyMatrix4(ref.current.matrixWorld);
        onPick([v.x, v.y, v.z]);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={() => setHovered(false)}
      onPointerEnter={() => {
        document.body.style.cursor = "pointer";
      }}
      onPointerLeave={() => {
        document.body.style.cursor = "";
      }}
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

export function OfficeEnvironment({
  onBrandPick,
}: {
  onBrandPick: (faceCenter: [number, number, number]) => void;
}) {
  const carpet = useCarpet();
  return (
    <group>
      {carpet && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[30, 30]} />
          <meshStandardMaterial map={carpet} roughness={0.95} />
        </mesh>
      )}
      {/* tường bắc (z = −10): chân đặc 1.6 m + dải kính 1 m + diềm 0.4 m.
          `Box` lấy tâm theo x/z: tường dài 26 phải đặt tâm x = 0. */}
      <Box size={[26, 1.6, 0.3]} at={[0, 0, -10]} color={PALETTE.wall} />
      <Box size={[26, 0.4, 0.3]} at={[0, 2.6, -10]} color={PALETTE.wall} />
      {[-11.5, -8.25, -5, -1.75, 1.5, 4.75, 8, 11.25].map((x) => (
        <Box key={x} size={[0.25, 1.0, 0.3]} at={[x, 1.6, -10]} color={PALETTE.wall} />
      ))}
      <mesh position={[0, 2.1, -10]}>
        <planeGeometry args={[25, 1.0]} />
        <meshStandardMaterial color={PALETTE.glass} transparent opacity={0.3} />
      </mesh>
      {/* tường tây đặc (x = −13, z −10..8 → tâm z = −1) — bảng phân ca treo ở đây */}
      <Box size={[0.3, 3.0, 18]} at={[-13, 0, -1]} color={PALETTE.wall} />
      {/* tường đông đặc đối xứng (x = 13) — khép kín văn phòng với mặt kính
          nam; góc đông-bắc gặp tường bắc, góc đông-nam gặp đầu facade */}
      <Box size={[0.3, 3.0, 18]} at={[13, 0, -1]} color={PALETTE.wall} />
      {/* phòng payroll riêng góc đông-nam: tường bắc + tường tây, hướng nam
          mở ra cửa kính (vào từ phía entrance), phía đông mượn tường nhà.
          Cao 2.4 (phòng riêng, khác vách cubicle 1.4) nhưng không trần nên
          camera trên cao vẫn thấy bàn. Không tường nam để bàn không bị che. */}
      <Box size={[3.85, 2.4, 0.15]} at={[10.925, 0, 3]} color={PALETTE.wall} />
      <Box size={[0.15, 2.4, 3.5]} at={[9, 0, 4.75]} color={PALETTE.wall} />
      {/* 2 ô cubicle mở hướng nam */}
      <Partition at={[-8, 0, -3.5]} along="x" />
      <Partition at={[-10.75, 0, -1.75]} along="z" />
      <Partition at={[-8, 0, -1.75]} along="z" />
      <Partition at={[-5.25, 0, -1.75]} along="z" />
      {/* cửa kính lối vào phía nam + phòng họp kính bao cụm interview
          (cùng toạ độ cụm interview trong `office.ts`) + mặt kính kín
          hai mép nam */}
      <GlassEntrance at={[3, 0, 8]} />
      <GlassFacade />
      <MeetingGlassRoom at={[4.2, 0, 0.3]} />
      {/* lễ tân sau quầy đầu đông (quầy x 0.6..3.4 trong `office.ts`):
          giữa quầy là đúng trục logo nhưng chui dưới nhãn reception */}
      <Receptionist at={[3.1, 0, -8.2]} />
      <Suspense fallback={null}>
        <LogoPlate onPick={onBrandPick} />
      </Suspense>
      <WaterCooler at={[12, 0, -8]} />
      <Plant at={[-12, 0, 6]} />
      <Plant at={[12.4, 0, 3]} />
      <Plant at={[-4, 0, -8.6]} />
    </group>
  );
}
