import { useContext, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import {
  Box,
  PALETTE,
  Person,
  SceneMotionContext,
  paint,
  useSignFace,
} from "@/components/scenes/scene-shapes";

/**
 * Sảnh sân bay (topic `airport`, 23 từ: 13 nhập mới + 10 nối từ
 * travel/park/business). Indoor lớn nhất từ trước tới nay nên mượn toàn bộ
 * quy ước restaurant/office: shape gốc đất, `Box` lấy gốc chân, chữ vẽ canvas
 * offline, tường bắc thấp cho camera trên cao nhìn qua ra đường băng.
 *
 * Bố cục: check-in tây → bảng thông tin giữa-nam → sảnh chờ giữa →
 * an ninh/hải quan đông → cửa ra máy bay + đường băng bắc. Khoang mẫu
 * (ghế + ngăn trên + tiếp viên) ở đông-bắc như khu trưng bày hãng bay.
 */

const AP = {
  floor: "#aeb9c2",
  floorLine: "#8d99a3",
  wallWhite: "#eef1f3",
  counterBlue: "#2f6f8f",
  counterTop: "#dfe5e9",
  beltBlack: "#2a2e33",
  beltFrame: "#6e7780",
  boardDark: "#1d2530",
  screenGreen: "#2e7d4f",
  screenAmber: "#c07d10",
  screenRed: "#a31220",
  seatBlue: "#3b6ea5",
  seatDark: "#2c537d",
  caseRed: "#b8443c",
  caseGreen: "#3f7d4f",
  caseNavy: "#2f4a6f",
  poleGrey: "#7c868f",
  glassBlue: "#9fc0d2",
  goldAmber: "#e8932e",
} as const;

/** Chữ lên màn hình/biển: canvas offline, không tải font mạng. */
function textPanel(
  lines: { text: string; size: number; color: string; bold?: boolean }[],
  w = 512,
  h = 256,
  bg: string = AP.boardDark,
  // Lề trái chữ: text sát mép canvas (x nhỏ) thì góc nhìn chéo mép backing
  // che mất ký tự đầu ("FLIGHT" → "LIGHT") — sai mà vẫn ra hình.
  x0 = 28,
) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);
  ctx.textBaseline = "middle";
  const step = h / (lines.length + 1);
  lines.forEach((l, i) => {
    ctx.fillStyle = l.color;
    ctx.font = `${l.bold ? "700" : "400"} ${l.size}px system-ui, sans-serif`;
    ctx.fillText(l.text, x0, step * (i + 1));
  });
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

/** Vali: thân + quai + 2 bánh. Gốc chân. */
function Suitcase({
  at,
  color,
  small = false,
}: {
  at: [number, number, number];
  color: string;
  small?: boolean;
}) {
  const w = small ? 0.36 : 0.5;
  const h = small ? 0.55 : 0.72;
  const d = small ? 0.22 : 0.28;
  return (
    <group position={at}>
      <Box size={[w, h, d]} at={[0, 0.06, 0]} color={color} />
      {/* nẹp giữa */}
      <Box size={[0.06, h, d + 0.02]} at={[0, 0.06, 0]} color={PALETTE.steelDark} />
      <Box size={[0.16, 0.05, 0.05]} at={[0, h + 0.06, 0]} color={PALETTE.steelDark} />
      {[-w / 4, w / 4].map((x) => (
        <mesh key={x} position={[x, 0.04, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.045, 0.045, 0.05, 10]} />
          {paint(PALETTE.tire)}
        </mesh>
      ))}
    </group>
  );
}

/** Quầy làm thủ tục dài 6 m: mặt quầy + 3 màn hình + cân băng trước. */
function CheckInCounter() {
  return (
    <group>
      <Box size={[6, 1.05, 0.9]} at={[0, 0, 0]} color={AP.counterBlue} />
      <Box size={[6.1, 0.07, 1.0]} at={[0, 1.05, 0]} color={AP.counterTop} />
      {/* 3 màn hình hãng bay trên cột sau quầy */}
      {[-2, 0, 2].map((x) => (
        <group key={x}>
          <Box size={[0.08, 0.75, 0.08]} at={[x, 1.05, -0.35]} color={AP.poleGrey} />
          <Box size={[1.1, 0.6, 0.08]} at={[x, 1.8, -0.35]} color={AP.boardDark} />
        </group>
      ))}
      {/* cân băng trước quầy */}
      <Box size={[2.4, 0.12, 0.8]} at={[-1.2, 0.35, 0.95]} color={AP.beltFrame} />
      <Box size={[2.3, 0.04, 0.7]} at={[-1.2, 0.47, 0.95]} color={AP.beltBlack} />
      {[-2.2, -0.2].map((x) => (
        <Box key={x} size={[0.08, 0.35, 0.7]} at={[x, 0, 0.95]} color={AP.beltFrame} />
      ))}
      {/* 2 nhân viên trực sau quầy (decor §7.9: không nhãn, không vào bảng
          từ): mặt về phía khách (+Z), đứng lọt giữa quầy và tường màn hình */}
      <group position={[-1.8, 0, -1.0]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={AP.counterBlue} clipboard hair="#2e2620" />
      </group>
      <group position={[1.4, 0, -1.0]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={AP.seatDark} hair="#5a4632" />
      </group>
    </group>
  );
}

/** Nhân viên bán vé sau quầy: người + bảng tên trên bục. */
function TicketAgent() {
  return (
    <group>
      <Person coat={AP.counterBlue} hair="#2e2620" />
      <Box size={[0.5, 0.9, 0.3]} at={[0.55, 0, 0.3]} color={AP.counterTop} />
      <Box size={[0.4, 0.25, 0.02]} at={[0.55, 0.9, 0.47]} color={PALETTE.paper} />
    </group>
  );
}

/** Băng chuyền hành lý dài 5 m: khung + băng đen + 2 vali trượt khi animated. */
function ConveyorBelt() {
  const animated = useContext(SceneMotionContext);
  return (
    <group>
      <Box size={[5, 0.75, 1.0]} at={[0, 0, 0]} color={AP.beltFrame} />
      <Box size={[4.9, 0.08, 0.9]} at={[0, 0.75, 0]} color={AP.beltBlack} />
      {[-2.2, -0.7, 0.7, 2.2].map((x) => (
        <Box key={x} size={[0.12, 0.75, 0.9]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      <SlidingCase offset={0} color={AP.caseRed} animated={animated} />
      <SlidingCase offset={2.4} color={AP.caseNavy} animated={animated} />
    </group>
  );
}

/** Vali con trượt dọc băng (x −2..2), đứng yên khi recall/reduced-motion. */
function SlidingCase({
  offset,
  color,
  animated,
}: {
  offset: number;
  color: string;
  animated: boolean;
}) {
  const caseRef = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const g = caseRef.current;
    if (!animated || !g) return;
    const t = clock.elapsedTime * 0.45 + offset;
    // Đi một chiều rồi vòng lại đầu (vali qua máy soi xong quay về).
    // Biên −2.2..2.2: thân vali (rộng 0.5) không bao giờ thò qua đầu băng.
    g.position.x = -2.2 + (((t % 4.4) + 4.4) % 4.4);
  });
  return (
    <group ref={caseRef} position={[0, 0.83, 0]}>
      <Box size={[0.5, 0.5, 0.6]} at={[-0.25, 0, -0.3]} color={color} />
    </group>
  );
}

/** Xe đẩy + 3 vali chồng — hành lý ký gửi chờ làm thủ tục. */
function LuggageCart() {
  return (
    <group>
      <Box size={[1.1, 0.08, 0.7]} at={[0, 0.35, 0]} color={AP.beltFrame} />
      {[-0.45, 0.45].map((x) =>
        [-0.28, 0.28].map((z) => (
          <mesh key={`${x}${z}`} position={[x, 0.14, z]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.09, 0.09, 0.06, 10]} />
            {paint(PALETTE.tire)}
          </mesh>
        )),
      )}
      <Box size={[0.06, 0.9, 0.7]} at={[-0.52, 0.35, 0]} color={AP.beltFrame} />
      <Suitcase at={[-0.2, 0.43, 0]} color={AP.caseRed} />
      <Suitcase at={[0.1, 0.43, -0.05]} color={AP.caseGreen} />
      {/* đáy lút 0.01 vào nóc vali dưới (1.15), không đồng phẳng */}
      <group position={[0, 1.14, 0]} rotation={[0, 0.25, 0]}>
        <Box size={[0.5, 0.5, 0.6]} at={[-0.25, 0, -0.3]} color={AP.caseNavy} />
      </group>
    </group>
  );
}

/** Vali xách tay trên bục cân cạnh quầy. */
function CarryOn() {
  return (
    <group>
      <Box size={[0.9, 0.4, 0.7]} at={[0, 0, 0]} color={AP.counterBlue} />
      <Box size={[0.8, 0.04, 0.6]} at={[0, 0.395, 0]} color={AP.counterTop} />
      <Suitcase at={[0, 0.44, 0]} color={AP.caseGreen} small />
    </group>
  );
}

/** Bảng lật tổng treo 2 cột giữa sảnh: 3 dòng chuyến bay. */
function DepartureBoard() {
  const face = useMemo(
    () =>
      textPanel(
        [
          { text: "VN 205  HA NOI    08:40  BOARDING", size: 44, color: "#f2f3f4", bold: true },
          { text: "VN 318  DA NANG   09:15  DELAYED", size: 44, color: AP.goldAmber, bold: true },
          { text: "VN 442  SAI GON   09:50  CANCELLED", size: 44, color: "#e2601a", bold: true },
        ],
        1024,
        384,
      ),
    [],
  );
  return (
    <group>
      {[-2.2, 2.2].map((x) => (
        <Box key={x} size={[0.18, 3.2, 0.18]} at={[x, 0, 0]} color={PALETTE.steelDark} />
      ))}
      <Box size={[5.2, 2.0, 0.18]} at={[0, 1.35, 0]} color={AP.boardDark} />
      {face && (
        <mesh position={[0, 2.35, 0.12]}>
          <planeGeometry args={[5.0, 1.85]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Kiosk màn hình đứng: khung + chân + mặt chữ. Màu phân biệt 3 trạng thái. */
function StatusScreen({ title, sub, color }: { title: string; sub: string; color: string }) {
  const face = useMemo(
    () =>
      textPanel(
        [
          { text: title, size: 64, color: "#ffffff", bold: true },
          { text: sub, size: 40, color: "#f2f3f4" },
        ],
        512,
        320,
        AP.boardDark,
      ),
    [title, sub],
  );
  return (
    <group>
      <Box size={[0.5, 0.5, 0.4]} at={[0, 0, 0]} color={PALETTE.steelDark} />
      <Box size={[0.14, 1.1, 0.14]} at={[0, 0.5, 0]} color={PALETTE.steelDark} />
      <Box size={[1.5, 1.0, 0.12]} at={[0, 1.6, 0]} color={color} />
      {face && (
        <mesh position={[0, 2.1, 0.09]}>
          <planeGeometry args={[1.4, 0.9]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

function DepartureScreen() {
  return <StatusScreen title="DEPARTURES" sub="08:40  VN205" color={AP.screenGreen} />;
}
function DelayScreen() {
  return <StatusScreen title="DELAYED" sub="+45 MIN  VN318" color={AP.screenAmber} />;
}
function CancelScreen() {
  return <StatusScreen title="CANCELLED" sub="VN442  SEE DESK" color={AP.screenRed} />;
}

/** Cột loa thông báo: dầm ngang + 2 loa kèn chĩa ngang hai hướng + vòng
 *  sóng đồng tâm TRƯỚC miệng loa. Bản cũ loa tí hon, vòng đặt cạnh thân đọc
 *  ra quai xách — sai mà vẫn ra hình. */
function AnnouncePole() {
  return (
    <group>
      <Box size={[0.16, 2.6, 0.16]} at={[0, 0, 0]} color={AP.poleGrey} />
      <Box size={[0.12, 0.12, 1.5]} at={[0, 2.5, 0]} color={AP.poleGrey} />
      {[1, -1].map((s) => (
        <group key={s}>
          {/* cổ loa + miệng kèn hướng ±Z */}
          <mesh position={[0, 2.45, s * 0.55]} rotation={[Math.PI / 2, 0, 0]} castShadow>
            <cylinderGeometry args={[0.07, 0.07, 0.3, 8]} />
            {paint(PALETTE.steelDark)}
          </mesh>
          <mesh
            position={[0, 2.45, s * 0.85]}
            rotation={[s > 0 ? -Math.PI / 2 : Math.PI / 2, 0, 0]}
            castShadow
          >
            <coneGeometry args={[0.22, 0.35, 10]} />
            {paint(AP.counterTop)}
          </mesh>
          {/* sóng âm: 2 vành tròn trước miệng, to dần theo khoảng cách */}
          {[1.15, 1.45].map((z, i) => (
            <mesh key={i} position={[0, 2.45, s * z]}>
              <torusGeometry args={[0.16 + i * 0.14, 0.02, 6, 18]} />
              <meshBasicMaterial color={AP.counterBlue} toneMapped={false} />
            </mesh>
          ))}
        </group>
      ))}
    </group>
  );
}

/** Khách ngồi ghế chờ (mặt +Z, xoay ngoài khi đặt): mông ở mặt ghế 0.52,
 *  chân gập, có tóc. Không tay (nhỏ, xa camera — mẫu DiningSeated). */
function SeatedGuest({ coat, hair }: { coat: string; hair: string }) {
  return (
    <group>
      <Box size={[0.38, 0.18, 0.4]} at={[0, 0.56, 0]} color={PALETTE.steelDark} />
      <Box size={[0.36, 0.5, 0.34]} at={[0, 0.74, -0.02]} color={coat} />
      <Box size={[0.26, 0.26, 0.26]} at={[0, 1.24, 0.02]} color={PALETTE.skin} />
      {/* đầu spans 1.24..1.50 (`Box` lấy gốc chân): mái ngồi TRÊN 1.50,
          đặt thấp hơn là chìm trong đầu — đúng lỗi Person cũ */}
      <Box size={[0.28, 0.1, 0.28]} at={[0, 1.495, 0.02]} color={hair} />
      <Box size={[0.28, 0.22, 0.06]} at={[0, 1.24, -0.12]} color={hair} />
      {/* mắt mặt +Z (hướng ngồi): lồi 0.03 khỏi mặt */}
      {[-0.07, 0.07].map((x) => (
        <Box key={x} size={[0.06, 0.06, 0.05]} at={[x, 1.32, 0.13]} color={PALETTE.tire} />
      ))}
      <Box size={[0.36, 0.14, 0.42]} at={[0, 0.56, 0.3]} color={PALETTE.steelDark} />
      <Box size={[0.32, 0.5, 0.14]} at={[0, 0, 0.48]} color={PALETTE.steelDark} />
    </group>
  );
}

/** Sảnh chờ: 2 dãy 4 ghế đối lưng + bàn thấp giữa. */
function DepartureLounge() {
  return (
    <group>
      {[-1.35, 1.35].map((z, zi) => (
        <group key={zi}>
          {[-1.5, -0.5, 0.5, 1.5].map((x) => (
            <group key={x} position={[x, 0, z]} rotation={[0, z > 0 ? Math.PI : 0, 0]}>
              <Box size={[0.55, 0.07, 0.55]} at={[0, 0.45, 0]} color={AP.seatBlue} />
              <Box size={[0.55, 0.55, 0.07]} at={[0, 0.45, -0.26]} color={AP.seatDark} />
              <Box size={[0.07, 0.45, 0.07]} at={[0, 0, 0]} color={PALETTE.steelDark} />
            </group>
          ))}
        </group>
      ))}
      <Box size={[1.2, 0.35, 0.5]} at={[0, 0, 0]} color={AP.counterTop} />
      {/* 4 khách ngồi so le 2 dãy (không ngồi kín — kín là giả) */}
      {[
        [-1.5, 1.35, Math.PI, AP.caseNavy, "#2e2620"],
        [0.5, 1.35, Math.PI, AP.caseGreen, "#5a4632"],
        [-0.5, -1.35, 0, AP.screenRed, "#2e2620"],
        [1.5, -1.35, 0, AP.seatDark, "#8a8a8a"],
      ].map(([x, z, r, c, h], i) => (
        <group key={i} position={[x as number, 0, z as number]} rotation={[0, r as number, 0]}>
          <SeatedGuest coat={c as string} hair={h as string} />
        </group>
      ))}
      {/* phòng kính riêng: 3 vách U mở hướng đông (ra cửa), trụ góc + đà
          nóc, không trần (mẫu phòng họp kính office). Kính tắt raycast nên
          bấm xuyên tới ghế. Ghế ngoài cùng cách vách 0.6 m. */}
      <mesh position={[-2.4, 1.1, 0]} raycast={() => null}>
        <boxGeometry args={[0.04, 2.2, 4.6]} />
        <meshStandardMaterial color={AP.glassBlue} transparent opacity={0.28} />
      </mesh>
      {[-2.3, 2.3].map((z) => (
        <mesh key={z} position={[0, 1.1, z]} raycast={() => null}>
          <boxGeometry args={[4.8, 2.2, 0.04]} />
          <meshStandardMaterial color={AP.glassBlue} transparent opacity={0.28} />
        </mesh>
      ))}
      {[-2.4, 2.4].map((x) =>
        [-2.3, 2.3].map((z) => (
          <Box key={`${x}${z}`} size={[0.12, 2.3, 0.12]} at={[x, 0, z]} color={AP.poleGrey} />
        )),
      )}
      <Box size={[0.14, 0.18, 4.7]} at={[-2.4, 2.2, 0]} color={AP.poleGrey} />
      {[-2.3, 2.3].map((z) => (
        <Box key={z} size={[4.9, 0.18, 0.14]} at={[0, 2.2, z]} color={AP.poleGrey} />
      ))}
    </group>
  );
}

/** Góc nối chuyến: biển TRANSFER + 3 ghế + chậu cây. */
function LayoverCorner() {
  const face = useMemo(
    () =>
      textPanel(
        [{ text: "TRANSFER", size: 72, color: "#ffffff", bold: true }],
        512,
        160,
        AP.counterBlue,
      ),
    [],
  );
  return (
    <group>
      <Box size={[0.14, 2.2, 0.14]} at={[-1, 0, 0]} color={AP.poleGrey} />
      <Box size={[0.14, 2.2, 0.14]} at={[1, 0, 0]} color={AP.poleGrey} />
      <Box size={[2.4, 0.7, 0.1]} at={[0, 1.5, 0]} color={AP.counterBlue} />
      {face && (
        <mesh position={[0, 1.85, 0.08]}>
          <planeGeometry args={[2.3, 0.6]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
      {[-0.7, 0, 0.7].map((x) => (
        <group key={x} position={[x, 0, 0.9]}>
          <Box size={[0.55, 0.07, 0.55]} at={[0, 0.45, 0]} color={AP.seatBlue} />
          <Box size={[0.55, 0.55, 0.07]} at={[0, 0.45, -0.26]} color={AP.seatDark} />
          <Box size={[0.07, 0.45, 0.07]} at={[0, 0, 0]} color={PALETTE.steelDark} />
        </group>
      ))}
      {/* 2 khách ngồi 2 ghế đầu, ghế giữa bỏ trống */}
      {[-0.7, 0.7].map((x, i) => (
        <group key={x} position={[x, 0, 0.9]}>
          <SeatedGuest
            coat={i === 0 ? AP.caseNavy : AP.screenRed}
            hair={i === 0 ? "#5a4632" : "#2e2620"}
          />
        </group>
      ))}
    </group>
  );
}

/** Quầy thông tin: quầy chữ nhật + bảng lịch trình nghiêng trên mặt quầy.
 *  Bản trụ tròn cũ đọc ra thùng phi, biển quay lưng về phía khách — sai mà
 *  vẫn ra hình. Cột biển INFO xanh đã bỏ theo yêu cầu (bảng lịch trình đủ
 *  nhận diện quầy). */
function InfoDesk() {
  const sheet = useMemo(
    () =>
      textPanel(
        [
          { text: "FLIGHT  VN 205", size: 44, color: AP.boardDark, bold: true },
          { text: "08:40 SGN-HAN", size: 44, color: AP.boardDark },
          { text: "GATE 12  SEAT 14A", size: 44, color: AP.boardDark },
        ],
        512,
        320,
        PALETTE.paper,
        56,
      ),
    [],
  );
  return (
    <group>
      <Box size={[2.0, 1.05, 0.8]} at={[0, 0, 0]} color={AP.counterBlue} />
      <Box size={[2.1, 0.07, 0.9]} at={[0, 1.05, 0]} color={AP.counterTop} />
      {/* bảng lịch trình lệch tây: mũi tên nhãn ở x = 0 đâm giữa bảng là
          che mất dòng chữ — lệch ra cho mũi tên trượt qua mép */}
      <group position={[-0.55, 1.12, 0.1]} rotation={[-0.35, 0, 0]}>
        <Box size={[0.8, 0.62, 0.04]} at={[0, 0.31, -0.02]} color={AP.counterTop} />
        {sheet && (
          <mesh position={[0, 0.31, 0.03]}>
            <planeGeometry args={[0.72, 0.56]} />
            <meshBasicMaterial map={sheet} toneMapped={false} />
          </mesh>
        )}
        <Box size={[0.7, 0.4, 0.04]} at={[0, 0.05, -0.28]} color={AP.poleGrey} />
      </group>
    </group>
  );
}

/** Cổng soát vé: bục + máy quét + 2 barrier + TẤM VÉ LỚN trên giá.
 *  Bản cũ chỉ có bục đen với màn hình tí hon — không có gì đọc ra "vé". */
function BoardingPodium() {
  const card = useMemo(
    () =>
      textPanel(
        [
          { text: "BOARDING PASS", size: 56, color: AP.counterBlue, bold: true },
          { text: "VN 205   GATE 12", size: 48, color: AP.boardDark, bold: true },
          { text: "SEAT 14A   08:40", size: 48, color: AP.boardDark },
        ],
        512,
        320,
        PALETTE.paper,
        56,
      ),
    [],
  );
  // Vạch barcode deterministic (không random — texture phải giống mỗi lần).
  const bars = [0.05, 0.02, 0.04, 0.02, 0.06, 0.03, 0.02, 0.05, 0.03, 0.04, 0.02, 0.06];
  let bx = -0.42;
  const barXs: number[] = bars.map((w) => {
    const x = bx + w / 2;
    bx += w + 0.025;
    return x;
  });
  return (
    <group>
      <Box size={[0.7, 1.1, 0.5]} at={[0, 0, 0]} color={AP.counterBlue} />
      <Box size={[0.5, 0.3, 0.4]} at={[0, 1.095, 0]} color={PALETTE.steelDark} />
      <Box size={[0.3, 0.02, 0.2]} at={[0, 1.395, 0.05]} color={AP.screenGreen} />
      {[-1.2, 1.2].map((x) => (
        <group key={x}>
          <Box size={[0.08, 0.95, 0.08]} at={[x, 0, 0.9]} color={PALETTE.steelDark} />
          <Box size={[0.08, 0.95, 0.08]} at={[x, 0, -0.9]} color={PALETTE.steelDark} />
          <Box size={[0.05, 0.05, 1.8]} at={[x, 0.9, 0]} color={AP.counterBlue} />
        </group>
      ))}
      {/* giá vé TRƯỚC-ĐÔNG bục (mặt về nam, hướng camera bay tới): bản cũ
          đặt lệch tây nên flyTo xong vé ra ngoài khung — sai mà vẫn ra hình */}
      {[-0.45, 0.45].map((dx) => (
        <Box key={dx} size={[0.08, 1.1, 0.08]} at={[1.1 + dx, 0, 1.3]} color={AP.poleGrey} />
      ))}
      <group position={[1.1, 1.1, 1.3]} rotation={[-0.3, 0, 0]}>
        <Box size={[1.15, 0.72, 0.05]} at={[0, 0.36, 0]} color={AP.counterTop} />
        {card && (
          <mesh position={[0, 0.46, 0.045]}>
            <planeGeometry args={[1.05, 0.44]} />
            <meshBasicMaterial map={card} toneMapped={false} />
          </mesh>
        )}
        {/* dải barcode trắng dưới vùng chữ + vạch 3D nổi (mặt nào cũng
            cách nhau ≥ 0.02, không đồng phẳng) */}
        <mesh position={[0, 0.13, 0.045]}>
          <planeGeometry args={[1.0, 0.18]} />
          <meshBasicMaterial color={PALETTE.paper} toneMapped={false} />
        </mesh>
        {barXs.map((x, i) => (
          <Box key={i} size={[bars[i], 0.12, 0.02]} at={[x, 0.13, 0.075]} color={AP.boardDark} />
        ))}
      </group>
    </group>
  );
}

/** Khung soi an ninh: 2 trụ + đà + băng khay + 2 khay xám. */
function SecurityFrame() {
  return (
    <group>
      <Box size={[0.25, 2.2, 1.2]} at={[-0.9, 0, 0]} color={AP.beltFrame} />
      <Box size={[0.25, 2.2, 1.2]} at={[0.9, 0, 0]} color={AP.beltFrame} />
      <Box size={[2.05, 0.5, 1.2]} at={[0, 2.2, 0]} color={AP.counterBlue} />
      <Box size={[4.2, 0.55, 0.9]} at={[0, 0, 1.35]} color={AP.beltFrame} />
      <Box size={[4.1, 0.06, 0.8]} at={[0, 0.55, 1.35]} color={AP.beltBlack} />
      {[-1.2, 0.2].map((x) => (
        <Box key={x} size={[0.9, 0.12, 0.65]} at={[x, 0.605, 1.35]} color={AP.floorLine} />
      ))}
    </group>
  );
}

/** Buồng kiểm hộ chiếu: vách kính 3 mặt (tắt raycast) + bàn + nhân viên. */
function PassportBooth() {
  return (
    <group>
      <Box size={[2.2, 0.06, 1.6]} at={[0, 0, 0]} color={AP.counterTop} />
      <Box size={[2.2, 1.0, 0.5]} at={[0, 0, -0.55]} color={AP.counterBlue} />
      <Box size={[2.2, 0.06, 1.7]} at={[0, 2.35, 0]} color={AP.counterBlue} />
      {[-1.07, 1.07].map((x) => (
        <Box key={x} size={[0.08, 2.35, 0.08]} at={[x, 0, -0.8]} color={AP.poleGrey} />
      ))}
      {[-1.07, 1.07].map((x) => (
        <mesh key={x} position={[x, 1.2, 0]} raycast={() => null}>
          <boxGeometry args={[0.04, 2.3, 1.6]} />
          <meshStandardMaterial color={AP.glassBlue} transparent opacity={0.28} />
        </mesh>
      ))}
      <mesh position={[0, 1.2, -0.8]} raycast={() => null}>
        <boxGeometry args={[2.2, 2.3, 0.04]} />
        <meshStandardMaterial color={AP.glassBlue} transparent opacity={0.28} />
      </mesh>
      {/* nhân viên mặt về phía khách (+Z): mũi Person là +X nên yaw −π/2,
          quay π là nhìn vào tường tây */}
      <group position={[0, 0, -0.1]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={PALETTE.steelDark} hat={PALETTE.steelDark} hair="#8a8a8a" />
      </group>
    </group>
  );
}

/** Bục + cuốn hộ chiếu mở (2 bìa xanh + trang trắng). */
function PassportStand() {
  return (
    <group>
      <Box size={[0.7, 1.0, 0.5]} at={[0, 0, 0]} color={AP.counterTop} />
      <group position={[0, 1.0, 0]} rotation={[-0.35, 0, 0]}>
        <Box size={[0.34, 0.02, 0.46]} at={[-0.17, 0.05, 0]} color={AP.seatDark} />
        <Box size={[0.34, 0.02, 0.46]} at={[0.17, 0.05, 0]} color={AP.seatDark} />
        <Box size={[0.3, 0.025, 0.42]} at={[-0.17, 0.06, 0]} color={PALETTE.paper} />
        <Box size={[0.3, 0.025, 0.42]} at={[0.17, 0.06, 0]} color={PALETTE.paper} />
      </group>
    </group>
  );
}

/** Quầy hải quan: quầy + biển DECLARE + đèn 2 làn xanh/đỏ. */
function CustomsCounter() {
  const face = useMemo(
    () =>
      textPanel(
        [{ text: "DECLARE", size: 72, color: "#ffffff", bold: true }],
        512,
        160,
        AP.screenRed,
      ),
    [],
  );
  return (
    <group>
      <Box size={[3.4, 1.05, 0.9]} at={[0, 0, 0]} color={AP.counterBlue} />
      <Box size={[3.5, 0.07, 1.0]} at={[0, 1.05, 0]} color={AP.counterTop} />
      <Box size={[0.12, 1.9, 0.12]} at={[-1.5, 1.05, 0]} color={AP.poleGrey} />
      <Box size={[1.9, 0.6, 0.08]} at={[-0.6, 2.0, 0]} color={AP.screenRed} />
      {face && (
        <mesh position={[-0.6, 2.0, 0.07]}>
          <planeGeometry args={[1.8, 0.55]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
      {/* đèn 2 làn: xanh qua / đỏ kiểm */}
      {[
        [0.9, AP.screenGreen],
        [1.4, AP.screenRed],
      ].map(([x, c], i) => (
        <group key={i}>
          <Box size={[0.08, 0.9, 0.08]} at={[x as number, 1.05, 0]} color={AP.poleGrey} />
          <mesh position={[x as number, 2.05, 0]}>
            <sphereGeometry args={[0.09, 10, 8]} />
            <meshBasicMaterial color={c as string} toneMapped={false} />
          </mesh>
        </group>
      ))}
      <group position={[0.3, 0, 0.7]} rotation={[0, -Math.PI / 2, 0]}>
        <Person coat={AP.screenGreen} hair="#2e2620" />
      </group>
    </group>
  );
}

/** Cửa ra máy bay: khung kính đôi + biển GATE 12 + cọc xếp hàng. */
function GateDoor() {
  const face = useMemo(
    () =>
      textPanel(
        [{ text: "GATE 12", size: 80, color: "#ffffff", bold: true }],
        512,
        160,
        AP.counterBlue,
      ),
    [],
  );
  return (
    <group>
      {[-1.3, 1.3].map((x) => (
        <Box key={x} size={[0.18, 2.6, 0.3]} at={[x, 0, 0]} color={AP.poleGrey} />
      ))}
      <Box size={[2.8, 0.25, 0.3]} at={[0, 2.6, 0]} color={AP.poleGrey} />
      <Box size={[1.6, 0.55, 0.08]} at={[0, 2.85, 0]} color={AP.counterBlue} />
      {face && (
        <mesh position={[0, 2.85, 0.07]}>
          <planeGeometry args={[1.5, 0.48]} />
          <meshBasicMaterial map={face} toneMapped={false} />
        </mesh>
      )}
      {[-0.6, 0.6].map((x) => (
        <mesh key={x} position={[x, 1.3, 0]} raycast={() => null}>
          <boxGeometry args={[1.1, 2.6, 0.05]} />
          <meshStandardMaterial color={AP.glassBlue} transparent opacity={0.28} />
        </mesh>
      ))}
      {/* 4 cọc dây xếp hàng trước cửa */}
      {[-2.2, -0.75, 0.75, 2.2].map((x) => (
        <group key={x}>
          <Box size={[0.07, 0.9, 0.07]} at={[x, 0, 1.6]} color={PALETTE.steelDark} />
          <mesh position={[x, 0.92, 1.6]}>
            <sphereGeometry args={[0.06, 8, 6]} />
            {paint(PALETTE.steelDark)}
          </mesh>
        </group>
      ))}
      {[-1.48, 0, 1.48].map((x) => (
        <Box key={x} size={[1.4, 0.05, 0.05]} at={[x, 0.78, 1.6]} color={AP.screenRed} />
      ))}
    </group>
  );
}

/** Dải đường băng ngoài trời: mặt băng + vạch giữa + đèn mép.
 *  Mesh của CHÍNH object giữ raycast để bấm vào thân băng cũng ăn (bản cũ
 *  tắt hết nên chỉ còn pill bé để bấm — khó bấm mà vẫn ra hình). Chỉ tường
 *  kính/sân/máy bay decor mới tắt. */
function RunwayStrip() {
  return (
    <group>
      <mesh position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[14, 4]} />
        <meshStandardMaterial color={PALETTE.asphalt} />
      </mesh>
      {[-5, -3, -1, 1, 3, 5].map((x) => (
        <mesh key={x} position={[x, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[1.2, 0.25]} />
          <meshStandardMaterial color={PALETTE.marking} />
        </mesh>
      ))}
      {[-6.5, 6.5].map((x) =>
        [-1.7, 1.7].map((z) => (
          <mesh key={`${x}${z}`} position={[x, 0.12, z]}>
            <sphereGeometry args={[0.09, 8, 6]} />
            <meshBasicMaterial color={AP.goldAmber} toneMapped={false} />
          </mesh>
        )),
      )}
    </group>
  );
}

/** Cụm 3 ghế mẫu khoang máy bay: ghế + tay vịn + lưng. */
function AisleSeat() {
  return (
    <group>
      {[-1.1, 0, 1.1].map((x) => (
        <group key={x} position={[x, 0, 0]}>
          <Box size={[0.55, 0.08, 0.55]} at={[0, 0.45, 0]} color={AP.seatBlue} />
          <Box size={[0.55, 0.6, 0.1]} at={[0, 0.45, -0.25]} color={AP.seatDark} />
          <Box size={[0.08, 0.25, 0.5]} at={[0.3, 0.55, 0]} color={AP.seatDark} />
          <Box size={[0.07, 0.45, 0.07]} at={[0, 0, 0]} color={PALETTE.steelDark} />
        </group>
      ))}
      {/* thảm lối đi + mũi tên chỉ lối */}
      <mesh position={[0, 0.03, 1.1]} rotation={[-Math.PI / 2, 0, 0]} raycast={() => null}>
        <planeGeometry args={[3.4, 0.8]} />
        <meshStandardMaterial color={AP.floorLine} />
      </mesh>
    </group>
  );
}

/** Ngăn hành lý trên cao: tủ dài + cửa mở + túi trong. */
function OverheadBin() {
  return (
    <group>
      {/* 2 cột đỡ tủ */}
      {[-1.5, 1.5].map((x) => (
        <Box key={x} size={[0.1, 2.1, 0.5]} at={[x, 0, 0]} color={AP.counterTop} />
      ))}
      <Box size={[3.3, 0.55, 0.6]} at={[0, 2.1, 0]} color={AP.counterTop} />
      {/* cửa ngăn mở: bản lề ở mép trên-trước, cánh ngửa ra 48° — đặt slab
          chìm trong thân là mất cửa im lặng (mặt chìm không ai thấy) */}
      <group position={[-0.5, 2.62, 0.3]} rotation={[-0.85, 0, 0]}>
        <Box size={[1.4, 0.5, 0.05]} at={[0, -0.25, 0]} color={AP.counterBlue} />
      </group>
      <Box size={[0.8, 0.35, 0.45]} at={[0.6, 2.1, 0]} color={AP.caseRed} />
      <Box size={[0.5, 0.3, 0.4]} at={[-0.5, 2.08, 0]} color={AP.caseNavy} />
    </group>
  );
}

/** Tiếp viên + xe đẩy phục vụ, mặt +X (hướng đi do `Mover` quyết định khi
 *  patrol — xoay tay ở đây là cộng dồn thành đi lùi, họ §7.6). */
function FlightAttendant() {
  return (
    <group>
      <Person coat={AP.screenRed} hair="#5a4632" />
      {/* khăn quàng: dải đỏ trước ngực */}
      <Box size={[0.1, 0.3, 0.05]} at={[0.2, 1.15, 0]} color={PALETTE.paper} />
      <group position={[0.75, 0, 0.2]}>
        <Box size={[0.7, 0.7, 0.45]} at={[0, 0.35, 0]} color={AP.counterTop} />
        <Box size={[0.7, 0.08, 0.45]} at={[0, 1.05, 0]} color={AP.counterBlue} />
        {[-0.25, 0.25].map((x) =>
          [-0.15, 0.15].map((z) => (
            <mesh key={`${x}${z}`} position={[x, 0.07, z]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.06, 0.06, 0.05, 8]} />
              {paint(PALETTE.tire)}
            </mesh>
          )),
        )}
      </group>
    </group>
  );
}

/** Logo dán tường tây (mặt +X về phía camera đông-nam). */
function BrandPlateWest({ onPick }: { onPick?: (c: [number, number, number]) => void }) {
  const face = useSignFace();
  if (!onPick) return null;
  return (
    <group
      position={[-15.82, 0, -2]}
      rotation={[0, Math.PI / 2, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onPick([-15.5, 2.0, -2]);
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

/** Máy bay decor đậu ngoài sân: thân + mũi + đuôi + cánh + động cơ + hàng
 *  cửa sổ rời + kính lái + càng đáp có chân. Dải kính dán liền cũ rẻ tiền,
 *  4 bánh lơ lửng không càng — sai mà vẫn ra hình. */
function ParkedPlane() {
  const winXs = [-2.1, -1.4, -0.7, 0, 0.7, 1.4, 2.1];
  return (
    <group position={[9, 0, -21]} rotation={[0, -0.35, 0]}>
      <mesh position={[0, 2.2, 0]} rotation={[0, 0, Math.PI / 2]} castShadow raycast={() => null}>
        <cylinderGeometry args={[1.1, 1.1, 7, 12]} />
        {paint(PALETTE.vanWhite)}
      </mesh>
      <mesh
        position={[3.8, 2.2, 0]}
        rotation={[0, 0, -Math.PI / 2]}
        castShadow
        raycast={() => null}
      >
        <coneGeometry args={[1.1, 1.6, 12]} />
        {paint(PALETTE.vanWhite)}
      </mesh>
      {/* sọc livery xanh mảnh dưới hàng cửa sổ */}
      <Box size={[6.6, 0.16, 2.22]} at={[0.2, 2.0, 0]} color={AP.counterBlue} />
      {/* cửa sổ rời 2 bên (không phải dải dán liền) */}
      {winXs.map((x) =>
        [-1.05, 1.05].map((z) => (
          <Box key={`${x}${z}`} size={[0.34, 0.3, 0.06]} at={[x, 2.55, z]} color={AP.boardDark} />
        )),
      )}
      {/* kính lái ôm mũi */}
      {[-0.45, 0.45].map((z) => (
        <group key={z} position={[3.75, 2.55, z]} rotation={[0, z > 0 ? -0.45 : 0.45, 0]}>
          <Box size={[0.45, 0.32, 0.08]} at={[0, 0, 0]} color={AP.boardDark} />
        </group>
      ))}
      {/* đuôi đứng + băng trắng + cánh ngang đuôi */}
      <Box size={[0.25, 2.2, 1.4]} at={[-3.6, 2.6, 0]} color={AP.counterBlue} />
      <Box size={[0.3, 0.45, 1.42]} at={[-3.6, 3.3, 0]} color={PALETTE.paper} />
      <Box size={[1.1, 0.1, 3.0]} at={[-3.3, 2.5, 0]} color={PALETTE.vanWhite} />
      {/* cánh chính */}
      <Box size={[1.6, 0.14, 4.6]} at={[0.3, 2.0, 0]} color={AP.counterBlue} />
      {/* 2 động cơ treo dưới cánh + cửa hút gió tối */}
      {[-1.5, 1.5].map((z) => (
        <group key={z}>
          <Box size={[0.5, 0.5, 0.12]} at={[0.3, 1.75, z]} color={AP.counterBlue} />
          <mesh position={[0.3, 1.45, z]} rotation={[0, 0, Math.PI / 2]} castShadow>
            <cylinderGeometry args={[0.32, 0.32, 1.4, 10]} />
            {paint(PALETTE.vanWhite)}
          </mesh>
          <mesh position={[1.0, 1.45, z]} rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[0.26, 0.26, 0.08, 10]} />
            {paint(AP.boardDark)}
          </mesh>
        </group>
      ))}
      {/* vây lưng trên nóc */}
      <Box size={[0.3, 0.4, 0.06]} at={[-0.5, 3.3, 0]} color={AP.counterBlue} />
      {/* càng đáp CÓ chân: trụ + bánh chạm đất */}
      {[-1.2, 1.2].map((z) =>
        [1.4, -1.6].map((x) => (
          <group key={`${x}${z}`}>
            <Box size={[0.1, 0.55, 0.1]} at={[x, 0.55, z]} color={PALETTE.steelDark} />
            <mesh position={[x, 0.35, z]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.35, 0.35, 0.2, 10]} />
              {paint(PALETTE.tire)}
            </mesh>
          </group>
        )),
      )}
      <Box size={[0.08, 0.9, 0.08]} at={[2.9, 0.2, 0]} color={PALETTE.steelDark} />
      <mesh position={[2.9, 0.22, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.22, 0.22, 0.14, 10]} />
        {paint(PALETTE.tire)}
      </mesh>
    </group>
  );
}

/** Hai hành khách decor đi lại 2 làn ngược pha (không nhãn, không vào bảng
 *  từ). Decor trong environment nằm NGOÀI `SceneObject` nên không có cờ
 *  `animated` riêng: tự đóng băng khi prefers-reduced-motion để preview
 *  deterministic (chế độ plain cũng reduce). Recall vẫn đi — dot đáp án là
 *  DOM nằm trên canvas nên người đi qua không che được.
 *  Không pill nên e2e elementFromPoint không thấy họ: làn đi đâu cũng được,
 *  miễn mắt thấy thoáng (cách vật tĩnh ~1 m). */
export function TerminalTravelers() {
  return (
    <group>
      <WalkingGuest
        base={[-3, -6.4]}
        axis="x"
        range={2}
        phase={0}
        speed={0.55}
        coat={AP.caseNavy}
        hair="#2e2620"
      />
      <WalkingGuest
        base={[2.0, 5.25]}
        axis="z"
        range={1.25}
        phase={Math.PI}
        speed={0.45}
        coat={AP.caseGreen}
        hair="#8a8a8a"
      />
    </group>
  );
}

function WalkingGuest({
  base,
  axis,
  range,
  phase,
  speed,
  coat,
  hair,
}: {
  base: [number, number];
  axis: "x" | "z";
  range: number;
  phase: number;
  speed: number;
  coat: string;
  hair: string;
}) {
  const guestRef = useRef<THREE.Group>(null);
  const tRef = useRef(0);
  const [still] = useState(
    () =>
      typeof window !== "undefined" &&
      !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );
  useFrame((_, dt) => {
    const g = guestRef.current;
    if (!g || still) return;
    tRef.current += dt * speed;
    const s = Math.sin(tRef.current + phase);
    const fwd = Math.cos(tRef.current + phase) >= 0;
    if (axis === "x") {
      g.position.x = base[0] + s * range;
      g.position.z = base[1];
      // Mặt theo hướng đi, tới đầu làn quay lại (không đi lùi).
      g.rotation.y = fwd ? 0 : Math.PI;
    } else {
      g.position.x = base[0];
      g.position.z = base[1] + s * range;
      g.rotation.y = fwd ? -Math.PI / 2 : Math.PI / 2;
    }
  });
  return (
    <group ref={guestRef} position={[base[0], 0, base[1]]}>
      <Person coat={coat} hair={hair} />
    </group>
  );
}

export function AirportEnvironment({
  onBrandPick,
}: {
  onBrandPick?: (c: [number, number, number]) => void;
}) {
  const floor = useMemo(() => {
    // Sàn sảnh xám xanh + đường kẻ deterministic.
    const PPM = 32;
    const W = 36 * PPM;
    const H = 24 * PPM;
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = AP.floor;
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = AP.floorLine;
    ctx.lineWidth = 2;
    for (let i = 0; i <= 36; i += 3) {
      ctx.beginPath();
      ctx.moveTo(i * PPM, 0);
      ctx.lineTo(i * PPM, H);
      ctx.stroke();
    }
    for (let i = 0; i <= 24; i += 3) {
      ctx.beginPath();
      ctx.moveTo(0, i * PPM);
      ctx.lineTo(W, i * PPM);
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
        <mesh
          rotation={[-Math.PI / 2, 0, 0]}
          position={[0, 0, -1]}
          receiveShadow
          raycast={() => null}
        >
          <planeGeometry args={[36, 24]} />
          <meshStandardMaterial map={floor} roughness={0.9} />
        </mesh>
      )}
      {/* sân đỗ ngoài: chạm khít mép sàn trong (z = −13), không chồng mặt */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.01, -19.5]}
        receiveShadow
        raycast={() => null}
      >
        <planeGeometry args={[44, 13]} />
        <meshStandardMaterial color={PALETTE.concrete} roughness={0.95} />
      </mesh>
      {/* tường tây + đông đặc cao 3.4 */}
      <Box size={[0.3, 3.4, 24]} at={[-16, 0, -1]} color={AP.wallWhite} />
      <Box size={[0.3, 3.4, 24]} at={[16, 0, -1]} color={AP.wallWhite} />
      {/* tường bắc THẤP (1.1 m) + cột kính: camera trên cao nhìn qua ra băng */}
      <Box size={[32.3, 1.1, 0.25]} at={[0, 0, -12]} color={AP.wallWhite} />
      {[-12, -6, 0, 6, 12].map((x) => (
        <Box key={x} size={[0.18, 2.3, 0.18]} at={[x, 1.1, -12]} color={AP.poleGrey} />
      ))}
      <Box size={[32.3, 0.18, 0.2]} at={[0, 3.25, -12]} color={AP.poleGrey} />
      {/* chân kính lút 0.05 vào mũ tường (1.1), không khe hở, không đồng phẳng */}
      <mesh position={[0, 2.125, -12]} raycast={() => null}>
        <boxGeometry args={[32, 2.15, 0.04]} />
        <meshStandardMaterial color={AP.glassBlue} transparent opacity={0.28} />
      </mesh>
      {/* mặt nam mở: tường lửng 2 đoạn chạm tường tây–đông, chừa cửa giữa
          (x ±3.5). Đoạn ngắn là hở góc nhìn ra trời — xấu mà vẫn ra hình. */}
      {[-9.75, 9.75].map((x) => (
        <group key={x}>
          <Box size={[12.5, 1.1, 0.2]} at={[x, 0, 10]} color={AP.wallWhite} />
          <Box size={[12.5, 0.08, 0.26]} at={[x, 1.1, 10]} color={AP.counterBlue} />
        </group>
      ))}
      {/* thảm cửa + 2 chậu cây */}
      <Box size={[5, 0.04, 2]} at={[0, 0, 10]} color={AP.counterBlue} />
      {[-3.2, 3.2].map((x) => (
        <group key={x} position={[x, 0, 10]}>
          <mesh position={[0, 0.2, 0]} castShadow>
            <cylinderGeometry args={[0.22, 0.17, 0.4, 10]} />
            {paint(AP.caseRed)}
          </mesh>
          <mesh position={[0, 0.7, 0]} castShadow>
            <coneGeometry args={[0.32, 0.65, 8]} />
            {paint(PALETTE.leaf)}
          </mesh>
        </group>
      ))}
      <BrandPlateWest onPick={onBrandPick} />
      <ParkedPlane />
      <TerminalTravelers />
    </group>
  );
}

export const AIRPORT_SHAPES = {
  "checkin-counter": CheckInCounter,
  "ticket-agent": TicketAgent,
  "conveyor-belt": ConveyorBelt,
  "luggage-cart": LuggageCart,
  "carry-on": CarryOn,
  "departure-board": DepartureBoard,
  "departure-screen": DepartureScreen,
  "delay-screen": DelayScreen,
  "cancel-screen": CancelScreen,
  "announce-pole": AnnouncePole,
  "departure-lounge": DepartureLounge,
  "layover-corner": LayoverCorner,
  "info-desk": InfoDesk,
  "boarding-podium": BoardingPodium,
  "security-frame": SecurityFrame,
  "passport-booth": PassportBooth,
  "passport-stand": PassportStand,
  "customs-counter": CustomsCounter,
  "gate-door": GateDoor,
  "runway-strip": RunwayStrip,
  "overhead-bin": OverheadBin,
  "aisle-seat": AisleSeat,
  "flight-attendant": FlightAttendant,
};
