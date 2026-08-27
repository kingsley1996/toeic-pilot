import { cx } from "@/components/ui";

/*
 * Biểu tượng pixel, vẽ bằng lưới ký tự ngay trong mã nguồn.
 *
 * Vì sao không phải tệp ảnh: một biểu tượng 12x12 là khoảng 40 byte dưới dạng
 * lưới ký tự, và sửa nó là sửa một dòng chữ chứ không phải mở trình vẽ, xuất
 * lại, rồi nhớ commit tệp mới. Bộ này cũng KHÔNG dính gì tới mascot hay bối
 * cảnh — đổi cả hai thứ đó thì các biểu tượng vẫn đúng.
 *
 * Vì sao SVG chứ không phải canvas: canvas không tồn tại lúc dựng ở máy chủ, nên
 * sẽ có một khoảnh khắc ô trống trước khi JS chạy. SVG dựng được ở cả hai phía,
 * và các hình chữ nhật nằm đúng toạ độ nguyên nên mép vẫn sắc.
 */

const T = "."; // trong suốt

type IconDef = {
  palette: Record<string, string>;
  rows: string[];
};

/*
 * Bảng màu chọn để đọc được trên CẢ nền sáng lẫn nền tối — biểu tượng là NỘI
 * DUNG chứ không phải chữ, nên nó không lấy màu theo token của giao diện; một
 * khúc xương đổi màu theo chủ đề thì không còn là khúc xương.
 */
const ICONS = {
  /** Cho ăn. Khúc xương đọc ra ngay ở 12px, và chỉ cần hai màu. */
  bone: {
    palette: { o: "#7a6440", W: "#f4ecd8" },
    rows: [
      ".oo.....oo..",
      "oWWo...oWWo.",
      "oWWWoooWWWo.",
      "oWWWWWWWWWo.",
      "oWWWoooWWWo.",
      "oWWo...oWWo.",
      ".oo.....oo..",
    ],
  },
  /** Chọc. Bàn tay chìa một ngón. */
  hand: {
    palette: { o: "#6b4a2f", S: "#f0c9a4" },
    rows: [
      ".....oo.....",
      "....oSSo....",
      "....oSSo....",
      "....oSSo....",
      "..oooSSo....",
      ".oSSSSSSo...",
      ".oSSSSSSo...",
      ".oSSSSSSo...",
      ".oSSSSSSo...",
      "..oooooo....",
    ],
  },
  /** Đi dạo. Dấu chân: ba ngón và một đệm thịt. */
  paw: {
    palette: { o: "#4a3a2a", P: "#c9a06a" },
    rows: [
      ".oo.oo.oo...",
      "oPPoPPoPPo..",
      "oPPoPPoPPo..",
      ".oo.oo.oo...",
      "............",
      "..oooooo....",
      ".oPPPPPPo...",
      ".oPPPPPPo...",
      ".oPPPPPPo...",
      "..oooooo....",
    ],
  },
  /** Cho ngủ. */
  moon: {
    palette: { o: "#3d4a72", M: "#dfe6ff" },
    rows: [
      "....oooo....",
      "...oMMMMo...",
      "..oMMMoo....",
      "..oMMo......",
      "..oMMo......",
      "..oMMo......",
      "..oMMMoo....",
      "...oMMMMo...",
      "....oooo....",
    ],
  },
  /** Đánh thức. */
  sun: {
    palette: { o: "#8a5a12", S: "#ffd66b", s: "#ffb02e" },
    rows: [
      ".....ss.....",
      ".s..oooo..s.",
      "..soSSSSos..",
      "...oSSSSo...",
      "...oSSSSo...",
      "..soSSSSos..",
      ".s..oooo..s.",
      ".....ss.....",
    ],
  },
  /** Phản hồi khi được chơi cùng. */
  heart: {
    palette: { o: "#8c1f34", H: "#ff5d73" },
    rows: [".oo..oo.", "oHHooHHo", "oHHHHHHo", "oHHHHHHo", ".oHHHHo.", "..oHHo..", "...oo..."],
  },
  /** Phản hồi khi ăn xong. */
  spark: {
    palette: { o: "#a87a12", S: "#ffe58a" },
    rows: ["...o...", "...o...", "..oSo..", "ooSSSoo", "..oSo..", "...o...", "...o..."],
  },
  /** Miếng ăn rơi ra lúc nhai. */
  crumb: {
    palette: { o: "#7a6440", C: "#e8d5a8" },
    rows: [".oo.", "oCCo", "oCCo", ".oo."],
  },
  /**
   * Quả trứng, cho khoảnh khắc trước khi biết nở ra con gì.
   *
   * Vẽ ở đây chứ không lấy từ tấm ghép: ba gói ô không có quả trứng nào, và cái
   * cần ở đây là một hình đứng một mình trên nền bảng — cùng loại việc mà bộ
   * biểu tượng này ra đời để làm.
   */
  egg: {
    palette: { o: "#6b5a3a", E: "#f6ecd2", s: "#e0d0aa" },
    rows: ["..oo..", ".oEEo.", "oEEEEo", "oEEEEo", "oEsEEo", "oEssEo", ".oEEo.", "..oo.."],
  },
  /** Con thú đang ngủ. Ba chữ Z chồng lên nhau, to dần. */
  zzz: {
    palette: { o: "#3d4a72", Z: "#dfe6ff" },
    rows: ["....ooo.", "....oZo.", "...oZoo.", "..ooZo..", "ooZZo...", "oZZo....", "oooo...."],
  },
} satisfies Record<string, IconDef>;

export type PixelIconName = keyof typeof ICONS;

/** Gộp các ô cùng màu liền nhau trên một hàng thành MỘT hình chữ nhật. */
function runs(def: IconDef): Array<{ x: number; y: number; w: number; fill: string }> {
  const out: Array<{ x: number; y: number; w: number; fill: string }> = [];
  def.rows.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const ch = row[x]!;
      let end = x;
      while (end < row.length && row[end] === ch) end += 1;
      if (ch !== T) {
        const fill = def.palette[ch];
        if (!fill) throw new Error(`ký tự "${ch}" không có trong bảng màu`);
        out.push({ x, y, w: end - x, fill });
      }
      x = end;
    }
  });
  return out;
}

/* Dựng một lần lúc nạp module: các lưới là hằng số, nên tính lại ở mỗi lần
   render là công việc lặp đi lặp lại cho ra đúng một kết quả. */
const SHAPES = Object.fromEntries(
  Object.entries(ICONS).map(([k, def]) => [
    k,
    { w: Math.max(...def.rows.map((r) => r.length)), h: def.rows.length, rects: runs(def) },
  ]),
) as Record<PixelIconName, { w: number; h: number; rects: ReturnType<typeof runs> }>;

/**
 * @param scale Số pixel màn hình cho mỗi ô của lưới. Số NGUYÊN, nếu không thì
 *   mép các ô rơi vào giữa pixel và cả hình bị nhoè — đúng thứ phong cách pixel
 *   không chịu được.
 */
export function PixelIcon({
  name,
  scale = 2,
  className,
}: {
  name: PixelIconName;
  scale?: number;
  className?: string;
}) {
  const s = SHAPES[name];
  const k = Math.max(1, Math.round(scale));
  return (
    <svg
      aria-hidden
      focusable="false"
      width={s.w * k}
      height={s.h * k}
      viewBox={`0 0 ${s.w} ${s.h}`}
      shapeRendering="crispEdges"
      className={cx("shrink-0", className)}
    >
      {s.rects.map((r) => (
        <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width={r.w} height={1} fill={r.fill} />
      ))}
    </svg>
  );
}
