/**
 * Bối cảnh của góc thú cưng: khu trại đêm trong `public/landscape/petland-2.jpg`.
 *
 * Tách khỏi component vì đây là DỮ LIỆU đo từ chính bức tranh, không phải logic.
 * `scripts/check-petland-fit.mjs` đọc file này để kiểm; để lẫn vào component thì
 * phép kiểm phải phân tích JSX chỉ để lấy vài con số.
 */

/** Kích thước thật của bức tranh. Mọi toạ độ dưới đây nằm trong hệ này. */
export const WORLD_W = 1360;
export const WORLD_H = 768;

/**
 * Một điểm neo trên đường đi.
 *
 * `y` là nơi BÀN CHÂN chạm đất, không phải tâm con thú. `scale` là cỡ con thú ở
 * đó — nó phải NHỎ DẦN khi đi về phía sau, vì bức tranh vẽ theo phối cảnh xiên:
 * một con thú giữ nguyên cỡ khi đi lên cầu sẽ trông như đang phình to.
 */
export type Anchor = { x: number; y: number; scale: number; label?: string };

/*
 * Đường đi, đo bằng cách phủ lưới toạ độ lên bức tranh rồi đọc từng mốc.
 *
 * Đây là kỹ thuật "walk path" của game phiêu lưu trỏ-và-bấm, và nó thay cho thứ
 * hiển nhiên hơn — một mặt đất phẳng ở `y` cố định. Mặt đất phẳng không dùng
 * được ở đây: khu trại nằm thấp bên trái, mặt cầu cao hơn nó 230px và ở xa hơn,
 * còn bờ bên kia lại thấp xuống về phía máng nước. Cho con thú đi ngang theo một
 * đường `y` cố định là cho nó lội qua suối ở nửa quãng đường.
 *
 * Vị trí con thú là MỘT số — quãng đường đã đi dọc đường này — nên "sang trái"
 * và "sang phải" vẫn là hai phím, còn `y` và `scale` suy ra từ đó.
 */
export const PATH: Anchor[] = [
  { x: 250, y: 716, scale: 0.9, label: "lối vào trại" },
  { x: 352, y: 688, scale: 0.86, label: "lửa trại" },
  { x: 470, y: 638, scale: 0.79, label: "chỗ ngồi" },
  { x: 548, y: 584, scale: 0.71 },
  { x: 596, y: 534, scale: 0.65, label: "bờ suối" },
  // Cầu là hình THANG, không phải một đường ngang: dốc lên từ 502 tới mặt phẳng
  // quanh 487 rồi hạ nhẹ về 483 ở đầu bên kia. Đo ở bản phóng 3x — nhìn ảnh cỡ
  // thật thì tay vịn, mặt cầu và gầm cầu chỉ cách nhau vài pixel.
  { x: 632, y: 502, scale: 0.61, label: "đầu cầu" },
  { x: 706, y: 490, scale: 0.59 },
  { x: 812, y: 488, scale: 0.58, label: "giữa cầu" },
  { x: 916, y: 486, scale: 0.58 },
  { x: 988, y: 494, scale: 0.6, label: "bờ bên kia" },
  // Dừng BÊN CẠNH máng nước chứ không ở giữa nó: thùng gỗ chiếm x 1045..1300 và
  // chân chạm cỏ ở y 575, nên đặt tiếp vào trong đó thì bàn chân rơi vào lòng máng.
  { x: 1032, y: 548, scale: 0.66, label: "máng nước" },
];

/** Độ dài từng đoạn và tổng, tính một lần. */
const SEGMENTS = PATH.slice(1).map((p, i) => {
  const q = PATH[i]!;
  return Math.hypot(p.x - q.x, p.y - q.y);
});
export const PATH_LENGTH = SEGMENTS.reduce((a, b) => a + b, 0);

/**
 * Vị trí, cỡ và tên chỗ đứng tại quãng đường `d` (px, từ 0 tới `PATH_LENGTH`).
 *
 * Nội suy tuyến tính giữa hai điểm neo. Nội suy trơn (Catmull-Rom) sẽ cho đường
 * cong đẹp hơn nhưng có thể VƯỢT RA NGOÀI các điểm neo ở chỗ gấp khúc — tức con
 * thú lượn ra khỏi mặt đất đã đo, đúng thứ đường đi này sinh ra để ngăn.
 */
export function pointAt(d: number): { x: number; y: number; scale: number; label: string } {
  const clamped = Math.max(0, Math.min(PATH_LENGTH, d));
  let left = clamped;
  for (let i = 0; i < SEGMENTS.length; i += 1) {
    const len = SEGMENTS[i]!;
    if (left <= len || i === SEGMENTS.length - 1) {
      const a = PATH[i]!;
      const b = PATH[i + 1]!;
      const t = len === 0 ? 0 : Math.min(1, left / len);
      return {
        x: a.x + (b.x - a.x) * t,
        y: a.y + (b.y - a.y) * t,
        scale: a.scale + (b.scale - a.scale) * t,
        // Nhãn của điểm neo GẦN hơn: "đang ở lửa trại" chỉ đúng khi thực sự ở đó.
        label: (t < 0.5 ? a.label : b.label) ?? "",
      };
    }
    left -= len;
  }
  const last = PATH[PATH.length - 1]!;
  return { ...last, label: last.label ?? "" };
}

/** Quãng đường ứng với một điểm neo, để tự đi dạo tới đúng các mốc có tên. */
export function distanceOfAnchor(index: number): number {
  return SEGMENTS.slice(0, index).reduce((a, b) => a + b, 0);
}

/** Các mốc có tên — đích của những chuyến tự đi dạo. */
export const LANDMARKS = PATH.map((p, i) => ({ ...p, at: distanceOfAnchor(i) })).filter(
  (p): p is Anchor & { at: number; label: string } => Boolean(p.label),
);

/* ─────────────────────────────────────────────────────────────────────────────
 * Vùng cho lớp hạt (`petland-fx.ts`).
 *
 * Bức tranh là một ảnh PHẲNG, nên không thể làm cho chính nó chuyển động: dòng
 * nước, đốm lửa và ngôi sao đều là một lớp hạt vẽ ĐÈ lên. Muốn lớp đó không lộ
 * ra là giả thì mỗi hiệu ứng phải bị nhốt vào đúng chỗ của nó — sao chỉ ở trời,
 * lấp lánh chỉ ở mặt nước — và "đúng chỗ" ở đây là toạ độ đo từ bức tranh, y
 * như `PATH`. Kiểm bằng `check-petland-fit.mjs --debug`, vốn vẽ các vùng này ra.
 */

export type Rect = { x: number; y: number; w: number; h: number };

/** Trời, để đặt sao. Tránh tán cây hai bên và dãy đồi. */
export const SKY: Rect[] = [
  { x: 380, y: 15, w: 600, h: 155 },
  { x: 600, y: 170, w: 380, h: 88 },
];

/**
 * Mặt nước. Các ô cố ý nằm LỌT HẲN trong lòng nước chứ không phủ kín nó: một
 * vệt sáng thiếu ở mép bờ thì không ai nhận ra, còn một vệt sáng lấp lánh trên
 * bãi cỏ thì nhận ra ngay.
 *
 * `fx`/`fy` là hướng trôi, theo dòng chảy vẽ trong tranh: suối chảy từ đồi bên
 * phải xuống dưới-TRÁI, nên `fx` âm ở cả bốn ô.
 *
 * Ô [3] là ô tốn công nhất và đáng nhớ vì sao. Hai lần đặt đầu tiên đạt 73% rồi
 * 87% "đúng chất liệu" — dưới ngưỡng 90% của `check-petland-fit.mjs` — vì khúc
 * suối đó có đá tối ở bờ trái và cỏ ăn vào từ bên phải, cả hai đều không nhìn ra
 * ở cỡ thật. Chỉ khi phóng 6x mới thấy mảng nước sạch thật sự chỉ rộng 52x26.
 * Đừng nới ô này ra cho "đầy đặn hơn": phần nới thêm là bờ, không phải nước.
 */
export const WATER: Array<Rect & { fx: number; fy: number }> = [
  { x: 838, y: 446, w: 56, h: 34, fx: -6, fy: 12 },
  { x: 820, y: 496, w: 170, h: 32, fx: -5, fy: 10 },
  { x: 742, y: 498, w: 64, h: 52, fx: -7, fy: 13 },
  { x: 674, y: 566, w: 52, h: 26, fx: -6, fy: 14 },
];

/** Đống lửa: gốc phát đốm, và tâm của vầng sáng ấm. */
export const FIRE = { x: 370, y: 640, glowY: 598 };

/** Cỏ và tán cây, để đom đóm bay. Trong tranh đã có đom đóm vẽ sẵn, nên những
 *  con biết bay chỉ là phần tiếp nối chứ không phải một ý tưởng mới. */
export const GLOW_ZONES: Rect[] = [
  { x: 60, y: 596, w: 210, h: 150 },
  { x: 620, y: 596, w: 300, h: 140 },
  { x: 1040, y: 600, w: 260, h: 130 },
  { x: 34, y: 128, w: 176, h: 206 },
  { x: 1150, y: 150, w: 190, h: 240 },
];
