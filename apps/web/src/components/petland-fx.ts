import { FIRE, GLOW_ZONES, SKY, WATER, type Rect } from "@/components/petland-scene";

/*
 * Lớp hạt của khu trại: sao nhấp nháy, mặt nước lấp lánh, đốm lửa bay lên, đom
 * đóm trôi trong cỏ.
 *
 * Vì sao phải là một lớp phủ chứ không phải làm bức tranh động: bức tranh là MỘT
 * ảnh phẳng. Muốn dòng nước tự chảy thì phải cắt nó thành lớp riêng có kênh
 * trong suốt, tức phải tô mặt nạ bằng tay cho một vùng có mép răng cưa — nhiều
 * việc hơn hẳn, và kết quả vẫn là một vòng lặp vẽ. Lớp hạt cho gần hết hiệu quả
 * đó mà không đụng vào tài sản gốc.
 *
 * Mọi hiệu ứng bị nhốt trong các vùng đo từ bức tranh (`petland-scene.ts`), vì
 * một vệt sáng lấp lánh trên bãi cỏ lộ ra ngay là đồ dán thêm.
 */

/** Ngẫu nhiên trong một ô. */
function inRect(r: Rect): { x: number; y: number } {
  return { x: r.x + Math.random() * r.w, y: r.y + Math.random() * r.h };
}

function pick<T>(list: readonly T[]): T {
  return list[Math.floor(Math.random() * list.length)]!;
}

type Star = { x: number; y: number; r: number; phase: number; speed: number };
type Shimmer = {
  x: number;
  y: number;
  w: number;
  h: number;
  life: number;
  max: number;
  fx: number;
  fy: number;
  /** Lắc ngang nhẹ quanh đường trôi, để vệt không đi thẳng như thước kẻ. */
  wobble: number;
  phase: number;
  warm: boolean;
  /** Ô nước đã sinh ra nó. Vệt TRÔI, nên phải nhớ biên của mình. */
  zone: Rect;
};
type Ripple = { x: number; y: number; r: number; max: number; speed: number; zone: Rect };
type Ember = { x: number; y: number; vx: number; vy: number; life: number; max: number };
type Fly = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  phase: number;
  speed: number;
  home: Rect;
};

const STARS = 46;
/*
 * Mặt nước cần MẬT ĐỘ mới đọc ra là dòng chảy. Bản đầu có 34 vệt cao 1.4px rải
 * trên toàn bộ mặt nước, và mắt đọc chúng thành vài đốm lấp lánh rời rạc chứ
 * không thành nước đang trôi: một vệt sáng đơn lẻ là một tia loé, còn một dòng
 * chảy là nhiều vệt cùng đi một hướng, đủ dày để thành kết cấu.
 */
const SHIMMERS = 108;
const RIPPLES = 7;
const EMBERS = 30;
const FLIES = 16;

export type Fx = { draw(now: number, dt: number, ctx: CanvasRenderingContext2D): void };

export function createFx(): Fx {
  const stars: Star[] = Array.from({ length: STARS }, () => {
    const p = inRect(pick(SKY));
    return {
      ...p,
      r: 0.7 + Math.random() * 1.5,
      phase: Math.random() * Math.PI * 2,
      // Mỗi ngôi sao một nhịp riêng, cố ý lẻ nhau: nhịp đều thì cả bầu trời
      // nháy cùng lúc và trông như màn hình bị nhấp nháy chứ không như sao.
      speed: 0.5 + Math.random() * 1.3,
    };
  });

  /*
   * Chọn ô nước theo DIỆN TÍCH, không đều tay.
   *
   * `pick()` đều tay chia đúng số vệt cho mỗi ô, nên ô suối trên 58x96 nhận bằng
   * ô vũng chính 340x114 — gấp bảy lần diện tích. Kết quả là chỗ nhỏ thì sáng
   * rực còn mặt vũng lớn nhất, thứ chiếm gần hết khung hình, lại loãng nhất. Đây
   * là lý do vì sao chỉ tăng số hạt thì vũng vẫn không đậm lên.
   */
  const waterArea = WATER.map((r) => r.w * r.h);
  const waterTotal = waterArea.reduce((a, b) => a + b, 0);
  const pickWater = () => {
    let t = Math.random() * waterTotal;
    for (let i = 0; i < WATER.length; i += 1) {
      t -= waterArea[i]!;
      if (t <= 0) return WATER[i]!;
    }
    return WATER[WATER.length - 1]!;
  };

  const newShimmer = (): Shimmer => {
    const zone = pickWater();
    const max = 1.1 + Math.random() * 1.6;
    const wobble = 1.5 + Math.random() * 3;
    const h = 1 + Math.round(Math.random() * 2);
    /*
     * Chọn chiều dài TRƯỚC, rồi mới chọn chỗ đặt sao cho cả vệt lọt trong ô.
     *
     * `inRect()` cho một ĐIỂM bất kỳ trong ô, kể cả sát mép phải — và một vệt
     * dài 40px đặt ở đó thò ra ngoài 36px ngay từ khung hình đầu tiên. Phép kiểm
     * biên ở vòng vẽ không cứu được: nó chạy TRƯỚC lần vẽ, nên vệt vừa sinh ra
     * vẫn kịp được vẽ đúng một khung rồi mới bị thay. Một khung hình ở 60fps là
     * quá nhanh để thấy, nhưng có hơn trăm vệt nên lúc nào cũng có vài cái đang
     * ở đúng khoảnh khắc đó — và cái nhìn thấy là những vạch sáng nhấp nháy trên
     * bãi cỏ.
     */
    const w = Math.min(10 + Math.random() * 46, zone.w - wobble * 2 - 2);
    const x = zone.x + wobble + Math.random() * Math.max(0, zone.w - w - wobble * 2);
    const y = zone.y + Math.random() * Math.max(0, zone.h - h);
    return {
      x,
      y,
      w,
      h,
      wobble,
      life: Math.random() * max,
      max,
      // Trôi nhanh hơn gấp đôi hướng của ô: 3–15 px/giây là chậm tới mức mắt đọc
      // thành đứng yên, và một mặt nước đứng yên thì không phải dòng chảy.
      fx: zone.fx * 2.1,
      fy: zone.fy * 2.1,
      phase: Math.random() * Math.PI * 2,
      // Một phần năm mang sắc ấm: mặt vũng trong tranh đầy vệt phản chiếu màu
      // cam của đống lửa, nên vệt sáng toàn màu lạnh sẽ nằm đè lên chúng và cãi
      // nhau với chính bức tranh.
      warm: Math.random() < 0.2,
      zone,
    };
  };
  const shimmers: Shimmer[] = Array.from({ length: SHIMMERS }, newShimmer);

  /* Gợn sóng tròn: thứ duy nhất trong lớp này nói "đây là MẶT NƯỚC" chứ không
     phải một bề mặt sáng nào đó. */
  const newRipple = (): Ripple => {
    const zone = pickWater();
    // Bán kính lớn nhất bị giới hạn bởi chỗ trống quanh tâm, nếu không thì gợn
    // sóng nào cũng bị cắt ngang giữa chừng khi chạm biên và trông như bị xoá.
    const max = Math.min(14 + Math.random() * 26, zone.w / 2 - 2, zone.h / 0.72 / 2);
    const x = zone.x + max + Math.random() * Math.max(0, zone.w - max * 2);
    const y = zone.y + max * 0.36 + Math.random() * Math.max(0, zone.h - max * 0.72);
    return { x, y, r: 0, max: Math.max(6, max), speed: 9 + Math.random() * 11, zone };
  };
  const ripples: Ripple[] = Array.from({ length: RIPPLES }, () => {
    const r = newRipple();
    r.r = Math.random() * r.max;
    return r;
  });

  /*
   * Đốm lửa sinh ra ở NGỌN lửa (y ≈ 494..518), không ở vành đá dưới chân (548).
   * Bản đầu sinh ở vành đá với lực nâng nhỏ, nên cả bầy sống và chết bên trong
   * vầng sáng của chính đống lửa và không bao giờ thấy được — bản đồ chênh lệch
   * giữa hai khung hình cho thấy chúng chụm thành một cụm bé tí, trong khi nhìn
   * bằng mắt chỉ thấy "hình như không có đốm lửa nào".
   */
  const newEmber = (): Ember => {
    const max = 1.5 + Math.random() * 1.4;
    return {
      x: FIRE.x + (Math.random() - 0.5) * 34,
      y: FIRE.y - 30 - Math.random() * 24,
      vx: (Math.random() - 0.5) * 16,
      vy: -(40 + Math.random() * 42),
      life: 0,
      max,
    };
  };
  const embers: Ember[] = Array.from({ length: EMBERS }, () => {
    const e = newEmber();
    e.life = Math.random() * e.max;
    return e;
  });

  const flies: Fly[] = Array.from({ length: FLIES }, () => {
    const home = pick(GLOW_ZONES);
    const p = inRect(home);
    return {
      ...p,
      vx: (Math.random() - 0.5) * 12,
      vy: (Math.random() - 0.5) * 12,
      phase: Math.random() * Math.PI * 2,
      speed: 0.35 + Math.random() * 0.5,
      home,
    };
  });

  /** Chấm sáng có quầng. Rẻ hơn `createRadialGradient` mỗi hạt mỗi khung hình. */
  function glow(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    r: number,
    a: number,
    color: string,
  ) {
    ctx.globalAlpha = a * 0.35;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, r * 2.6, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = a;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }

  return {
    draw(now, dt, ctx) {
      const t = now / 1000;
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
      /*
       * `lighter` (cộng màu) chứ không phải vẽ đè: những hạt này đều là ÁNH SÁNG
       * — sao, phản chiếu, tàn lửa. Vẽ đè thì một chấm mờ trên nền tối lại làm
       * chỗ đó SÁNG kém hơn xung quanh, tức một vệt xám bẩn thay vì một tia sáng.
       */
      ctx.globalCompositeOperation = "lighter";

      for (const s of stars) {
        // Đỉnh nhọn, đáy bẹt: sao đứng im phần lớn thời gian rồi loé lên, chứ
        // không phập phồng đều như đèn thở.
        const w = Math.sin(t * s.speed + s.phase) * 0.5 + 0.5;
        glow(ctx, s.x, s.y, s.r, Math.pow(w, 3) * 0.85, "#dbe9ff");
      }

      for (const s of shimmers) {
        s.life += dt;
        s.x += s.fx * dt;
        s.y += s.fy * dt;
        /*
         * Sinh trong ô là chưa đủ — vệt TRÔI. Ở tốc độ này một vệt đi được gần
         * 60px trong đời nó, thừa sức ra khỏi ô và nằm lấp lánh trên bãi cỏ,
         * đúng thứ mà việc nhốt hiệu ứng vào các ô sinh ra để ngăn. Ra khỏi biên
         * thì sinh lại; hết đời cũng sinh lại.
         */
        const out =
          s.x + s.w + s.wobble > s.zone.x + s.zone.w ||
          s.x - s.wobble < s.zone.x ||
          s.y + s.h > s.zone.y + s.zone.h ||
          s.y < s.zone.y;
        if (out || s.life >= s.max) Object.assign(s, newShimmer(), { life: 0 });
        // Hiện rồi tắt trong đúng vòng đời: một vệt sáng bật/tắt đột ngột trên
        // mặt nước đọc ra là lỗi vẽ chứ không phải là sóng.
        const a = Math.sin((s.life / s.max) * Math.PI) * 0.78;
        ctx.globalAlpha = a;
        ctx.fillStyle = s.warm ? "#ffd6a2" : "#cfeaff";
        ctx.fillRect(s.x + Math.sin(t * 1.7 + s.phase) * s.wobble, s.y, s.w, s.h);
      }

      for (const r of ripples) {
        r.r += r.speed * dt;
        // Gợn sóng KHÔNG trôi, nhưng nó nở ra — nên cũng phải dừng ở biên ô.
        const spill =
          r.x - r.r < r.zone.x ||
          r.x + r.r > r.zone.x + r.zone.w ||
          r.y - r.r * 0.36 < r.zone.y ||
          r.y + r.r * 0.36 > r.zone.y + r.zone.h;
        if (spill || r.r >= r.max) Object.assign(r, newRipple());
        const k = 1 - r.r / r.max;
        ctx.globalAlpha = k * 0.4;
        ctx.strokeStyle = "#cfeaff";
        ctx.lineWidth = 1;
        ctx.beginPath();
        // Dẹt 0.36 theo chiều dọc: một vòng tròn tròn vành vạnh trên mặt nước
        // nhìn xiên đọc ra là cái đĩa dựng đứng chứ không phải gợn sóng.
        ctx.ellipse(r.x, r.y, r.r, r.r * 0.36, 0, 0, Math.PI * 2);
        ctx.stroke();
      }

      for (const e of embers) {
        e.life += dt;
        if (e.life >= e.max) Object.assign(e, newEmber());
        e.x += e.vx * dt;
        e.y += e.vy * dt;
        // Chậm dần khi lên cao: tàn lửa nguội đi thì mất lực nâng.
        e.vy += 16 * dt;
        e.vx += Math.sin(t * 2.5 + e.x) * 5 * dt;
        const k = 1 - e.life / e.max;
        glow(ctx, e.x, e.y, 0.9 + k * 1.5, k * 0.85, k > 0.55 ? "#ffd9a0" : "#ff8a3d");
      }

      for (const f of flies) {
        f.phase += dt * f.speed;
        f.x += f.vx * dt;
        f.y += f.vy * dt;
        f.vx += (Math.random() - 0.5) * 22 * dt;
        f.vy += (Math.random() - 0.5) * 22 * dt;
        // Kéo về vùng của nó thay vì kẹp cứng ở biên: kẹp thì đom đóm dồn lại
        // thành một hàng dọc theo mép ô, và cái ô vô hình đó hiện ra.
        if (f.x < f.home.x) f.vx += 30 * dt;
        if (f.x > f.home.x + f.home.w) f.vx -= 30 * dt;
        if (f.y < f.home.y) f.vy += 30 * dt;
        if (f.y > f.home.y + f.home.h) f.vy -= 30 * dt;
        f.vx *= 0.985;
        f.vy *= 0.985;
        const blink = Math.pow(Math.sin(f.phase) * 0.5 + 0.5, 4);
        glow(ctx, f.x, f.y, 1.1, blink * 0.8, "#ffe98a");
      }

      // Vầng sáng của đống lửa, dao động bằng hai hình sin lệch chu kỳ — một cái
      // thì thành nhịp thở đều, thứ mà mắt bắt được ngay.
      const flick = 0.72 + Math.sin(t * 7.3) * 0.16 + Math.sin(t * 3.1) * 0.12;
      const g = ctx.createRadialGradient(FIRE.x, FIRE.glowY, 4, FIRE.x, FIRE.glowY, 118 * flick);
      g.addColorStop(0, "rgba(255,176,84,0.36)");
      g.addColorStop(0.45, "rgba(255,128,40,0.13)");
      g.addColorStop(1, "rgba(255,110,30,0)");
      ctx.globalAlpha = 1;
      ctx.fillStyle = g;
      ctx.fillRect(FIRE.x - 130, FIRE.glowY - 130, 260, 260);

      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    },
  };
}
