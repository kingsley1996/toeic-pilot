/**
 * Đồng hồ RIÊNG của thế giới Petland, và bầu trời đổi màu theo nó.
 *
 * **Suy ra từ đồng hồ thật, không lưu ở đâu cả.** Cùng luật với nhu cầu con thú
 * và chuỗi ngày học: một bộ đếm chạy song song sẽ lệch khỏi thời gian thật ngay
 * lần đầu có người đóng tab, và không có gì phát hiện ra. Ở đây còn rẻ hơn thế —
 * giờ trong thế giới là một phép chia lấy dư trên `Date.now()`, nên hai máy khác
 * nhau mở cùng lúc thấy cùng một buổi.
 *
 * **Mốc gốc tính theo UTC, không theo múi giờ người dùng.** Petland là MỘT nơi
 * chốn, nên trời tối ở đó là tối với tất cả mọi người — người ở Hà Nội và người
 * ở Berlin cùng nhìn vào một buổi hoàng hôn. Lấy theo múi giờ máy thì "đêm ở
 * Petland" thành một câu không nói được với ai khác.
 *
 * **Một ngày ở đây dài một giờ thật.** Đây là con số quan trọng nhất tệp này, và
 * nó là một đánh đổi giữa hai cái hỏng ngược nhau:
 *
 *   · Chạy theo giờ thật (một ngày = một ngày) thì người chỉ học buổi chiều sẽ
 *     KHÔNG BAO GIỜ thấy đêm. Một tính năng mà phần lớn người dùng không bao giờ
 *     nhìn thấy thì coi như không có.
 *   · Chạy quá nhanh (một ngày = mười phút) thì bầu trời nhấp nháy trong lúc
 *     người ta đang học, và góc thú cưng chuyển từ "có gì đó đang sống ở đây"
 *     sang "có gì đó đang nháy ở đây".
 *
 * Một giờ nghĩa là một buổi học mười phút thấy trời dịch đi rõ ràng, và qua vài
 * ngày thì thấy đủ cả chu kỳ.
 *
 * Không React, không Pixi, không đường dẫn ảnh: một hàm thuần trên một con số.
 * Nhờ vậy nó kiểm được mà không cần trình duyệt, và ngày máy chủ cần biết ở
 * Petland đang là mấy giờ (kẻ xâm nhập ra vào ban đêm chẳng hạn) thì nó chép
 * sang Python được nguyên xi — lúc đó nhớ luật đã ghi cho `dictation.ts`: hai
 * bản phải là bản dịch từng bước của nhau, và lệch nhau là hỏng im lặng.
 */

/** Một ngày ở Petland dài bao nhiêu mili giây thật. */
export const WORLD_DAY_MS = 60 * 60 * 1000;

export type WorldPhase = "dawn" | "day" | "dusk" | "night";

export type WorldTime = {
  /** 0..1 trong một ngày. 0 là nửa đêm. */
  t: number;
  /** Giờ và phút trong thế giới, để in ra cho người đọc. */
  hours: number;
  minutes: number;
  phase: WorldPhase;
  /** Lớp phủ bầu trời: màu và độ đậm. `alpha === 0` nghĩa là giữa trưa. */
  sky: { color: number; alpha: number };
};

/**
 * Các mốc màu trời trong ngày, và bảng này LÀ thiết kế của tính năng.
 *
 * Giữa hai mốc thì nội suy tuyến tính, nên bầu trời không bao giờ nhảy bậc —
 * một cú nhảy màu đọc ra là lỗi vẽ chứ không phải hoàng hôn.
 *
 * Ba điều về mấy con số này:
 *
 *   · **Giữa trưa `alpha` bằng 0**, tức là không phủ gì cả. Phủ một lớp mỏng cho
 *     "ấm hơn" nghe hay nhưng nó làm mọi ô pixel lệch màu suốt cả ngày, mà bảng
 *     màu của Kenney vốn đã được chọn để đứng cạnh nhau.
 *   · **Đêm dừng ở 0,55**, không phải 0,8: dưới ngưỡng đó thì không nhìn ra con
 *     thú đang đứng đâu, mà con thú mới là thứ người ta mở bảng này để xem. Trời
 *     tối là bối cảnh, không phải màn che.
 *   · **Bình minh và hoàng hôn ngả CAM, đêm ngả XANH TÍM.** Cùng một màu tối cho
 *     cả ba thì chỉ còn "sáng dần rồi tối dần", mất hẳn hai khoảnh khắc mà người
 *     ta thật sự nhận ra là lúc nào trong ngày.
 */
const STOPS: ReadonlyArray<{ at: number; color: number; alpha: number }> = [
  { at: 0.0, color: 0x1b2a5e, alpha: 0.55 }, // nửa đêm
  { at: 0.18, color: 0x2c3a6b, alpha: 0.5 }, // gần sáng
  { at: 0.24, color: 0xd9743a, alpha: 0.32 }, // bình minh
  { at: 0.32, color: 0xffc98a, alpha: 0.1 }, // nắng sớm
  { at: 0.42, color: 0xffffff, alpha: 0.0 }, // giữa trưa
  { at: 0.66, color: 0xffffff, alpha: 0.0 },
  { at: 0.74, color: 0xffb066, alpha: 0.16 }, // xế chiều
  { at: 0.8, color: 0xe0662e, alpha: 0.36 }, // hoàng hôn
  { at: 0.88, color: 0x2c3a6b, alpha: 0.5 }, // chạng vạng
  { at: 1.0, color: 0x1b2a5e, alpha: 0.55 }, // vòng lại nửa đêm
];

function lerpColor(from: number, to: number, k: number): number {
  const r = Math.round(((from >> 16) & 255) + (((to >> 16) & 255) - ((from >> 16) & 255)) * k);
  const g = Math.round(((from >> 8) & 255) + (((to >> 8) & 255) - ((from >> 8) & 255)) * k);
  const b = Math.round((from & 255) + ((to & 255) - (from & 255)) * k);
  return (r << 16) | (g << 8) | b;
}

function phaseOf(t: number): WorldPhase {
  if (t < 0.22 || t >= 0.86) return "night";
  if (t < 0.34) return "dawn";
  if (t < 0.72) return "day";
  return "dusk";
}

/**
 * Thời gian ở Petland tại một mốc đồng hồ thật.
 *
 * `now` là tham số chứ không đọc thẳng `Date.now()`, cùng lý do `srs.review`
 * nhận `now`: một hàm phụ thuộc đồng hồ thì không bài kiểm nào nói được gì về nó.
 */
export function worldTime(now: number): WorldTime {
  const t = (now % WORLD_DAY_MS) / WORLD_DAY_MS;
  const total = t * 24 * 60;
  let index = 0;
  while (index < STOPS.length - 2 && t >= STOPS[index + 1].at) index += 1;
  const from = STOPS[index];
  const to = STOPS[index + 1];
  const span = to.at - from.at;
  const k = span > 0 ? (t - from.at) / span : 0;
  return {
    t,
    hours: Math.floor(total / 60),
    minutes: Math.floor(total % 60),
    phase: phaseOf(t),
    sky: {
      color: lerpColor(from.color, to.color, k),
      alpha: from.alpha + (to.alpha - from.alpha) * k,
    },
  };
}

/** `06:24` — hai chữ số, để con số không nhảy bề ngang mỗi phút. */
export function worldClockLabel(time: WorldTime): string {
  return `${String(time.hours).padStart(2, "0")}:${String(time.minutes).padStart(2, "0")}`;
}

export const PHASE_LABEL: Record<WorldPhase, string> = {
  dawn: "bình minh",
  day: "ban ngày",
  dusk: "hoàng hôn",
  night: "ban đêm",
};
