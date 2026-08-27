"use client";

import { TILE } from "@/components/petland-map";
import { CREATURE_COLS, CREATURE_ROWS } from "@/components/petland-sprite";
import { cx } from "@/components/ui";

/**
 * Vẽ MỘT ô sinh vật bằng CSS, và cách gọi tên hạng hiếm.
 *
 * Tách khỏi màn trứng vì bộ sưu tập cần đúng những thứ này. Hai bản sao của một
 * phép cắt ô là hai chỗ để lệch số cột — và lệch số cột thì ô vẫn vẽ ra, chỉ là
 * vẽ nhầm con, nên không có gì báo (đúng lỗi mà nút thu gọn của góc thú cưng đã
 * mắc: lấy 12 cột của tấm NỀN cho tấm sinh vật 10 cột).
 *
 * `petland-ui.tsx` KHÔNG được nhập tệp này: nó phải sống sót qua việc đổi bộ
 * sprite, còn tệp này thì biết đúng chỗ ảnh nằm.
 */

const ZOOM = 2;

function tileStyle(tile: number) {
  return {
    backgroundImage: "url(/pet/creatures.png)",
    backgroundPosition: `-${(tile % CREATURE_COLS) * TILE * ZOOM}px -${Math.floor(tile / CREATURE_COLS) * TILE * ZOOM}px`,
    backgroundSize: `${CREATURE_COLS * TILE * ZOOM}px ${CREATURE_ROWS * TILE * ZOOM}px`,
    imageRendering: "pixelated" as const,
  };
}

export const TIER_LABEL: Record<string, string> = {
  common: "thường",
  uncommon: "ít gặp",
  rare: "hiếm",
  epic: "cực hiếm",
  legendary: "huyền thoại",
};

/* Hạng dùng thang bốn accent? KHÔNG — thang đó phân loại giọng đọc. Ở đây dùng
   token trạng thái, cùng tập mà `FrameTone` đã đóng lại vì cùng một lý do: một
   mã màu tự do là đường ngắn nhất tới một nhãn không đọc được ở chế độ tối. */
export const TIER_TONE: Record<string, string> = {
  common: "text-ink-muted",
  uncommon: "text-ok",
  rare: "text-action",
  epic: "text-alert",
  // Vàng ở đỉnh thang, và `--warn` là token vàng DUY NHẤT của hệ thiết kế. Thang
  // bốn accent vẫn không mượn được: nó phân loại giọng đọc, và mượn sang đây là
  // bắt một màu mang hai nghĩa.
  legendary: "text-warn",
};

/**
 * Hạng hiếm → token màu, và token màu → số cho tầng vẽ.
 *
 * Đọc từ biến CSS chứ không chép mã màu vào đây, vì hai lý do khác nhau và cả
 * hai đều quan trọng: **màu phải theo chế độ sáng/tối** (cùng một token có hai
 * giá trị, và một số cứng sẽ chìm nghỉm ở một trong hai), và **thang màu là của
 * hệ thiết kế** — một mã màu tự do là đường ngắn nhất tới một vòng sáng không
 * đọc được, đúng thứ mà `FrameTone` đã đóng tập lại để tránh.
 *
 * Cùng bốn token mà `TIER_TONE` đang dùng cho chữ, nên vòng sáng dưới chân và
 * cái nhãn trong tủ luôn nói cùng một màu về cùng một hạng.
 */
const TIER_VAR: Record<string, string> = {
  common: "--ink-muted",
  uncommon: "--ok",
  rare: "--action",
  epic: "--alert",
  legendary: "--warn",
};

/**
 * Hạng nào thì vòng sáng mạnh tới đâu, trên thang 0..1.
 *
 * Chỉ là ĐỘ MẠNH, không phải kích cỡ hay độ mờ: tầng vẽ dịch một con số này ra
 * bán kính, độ đậm và nhịp thở, vì đó là quyết định về hình ảnh và nó thuộc về
 * chỗ cầm bút. Ở đây chỉ nói "cực hiếm mạnh gấp bốn lần thường".
 *
 * Loài thường vẫn CÓ vòng, chỉ là mờ và đứng yên: bỏ hẳn thì "không có vòng"
 * đọc ra là hỏng chứ không phải là hạng thường. Khoảng cách giữa các bậc đều
 * nhau, nên năm hạng đọc được từ xa mà không cần chú thích.
 */
const TIER_GLOW: Record<string, number> = {
  common: 0.2,
  uncommon: 0.4,
  rare: 0.6,
  epic: 0.8,
  legendary: 1,
};

/** `"23 105 74"` → `0x17694a`. Token lưu ba số RGB cách nhau bằng dấu cách. */
function tokenColor(name: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const parts = raw.split(/[\s,]+/).map(Number);
  if (parts.length < 3 || parts.some((n) => !Number.isFinite(n))) return fallback;
  return (parts[0] << 16) | (parts[1] << 8) | parts[2];
}

/**
 * Màu và độ mạnh của vòng sáng dưới chân, theo hạng hiếm.
 *
 * Đọc token NGAY LÚC GỌI chứ không nhớ lại: người dùng đổi sáng/tối giữa chừng
 * là chuyện bình thường, và một giá trị nhớ từ lần dựng đầu sẽ giữ màu của chế
 * độ cũ. Người gọi chỉ gọi lại khi con thú hoặc chủ đề đổi, nên nó không nằm
 * trên đường vẽ mỗi khung hình.
 */
export function tierGlow(tier: string): { color: number; strength: number } {
  return {
    color: tokenColor(TIER_VAR[tier] ?? TIER_VAR.common, 0x9aaab5),
    strength: TIER_GLOW[tier] ?? TIER_GLOW.common,
  };
}

/**
 * Cỡ đặt bằng `style` chứ không bằng lớp Tailwind dựng từ chuỗi.
 *
 * `h-${size}` biên dịch sạch và **không sinh ra CSS nào**: Tailwind quét mã
 * nguồn bằng văn bản, nên một tên lớp chỉ tồn tại lúc chạy thì không có trong
 * tệp CSS. Cùng lớp lỗi với `-inset-[25%]` của khung avatar (CLAUDE.md), và nó
 * cũng im lặng y như thế — ô sinh vật sẽ co về 0 và không có gì báo.
 */
export function Creature({
  tile,
  size = 32,
  className,
}: {
  tile: number;
  size?: number;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cx("tile-checker relative block shrink-0 rounded", className)}
      style={{ width: size, height: size }}
    >
      <span className="absolute inset-0" style={tileStyle(tile)} />
    </span>
  );
}
