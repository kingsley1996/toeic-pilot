"use client";

import { Player } from "@remotion/player";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { FPS } from "@/remotion/mocks";

/**
 * Khung phát cho ba ô minh hoạ của trang giới thiệu.
 *
 * **Player chỉ tồn tại khi ô nằm trong khung nhìn.** Ba cảnh chạy vòng cùng lúc
 * trên một trang dài là ba vòng lặp đốt pin cho thứ người dùng không nhìn, và
 * trên máy yếu nó làm chính lượt cuộn bị giật. Gắn/tháo hẳn player, không dùng
 * `PlayerRef.play()`/`pause()`: lượt `play()` qua ref không khởi động lại được
 * cảnh đã dừng ở đây, nên cảnh thứ hai và thứ ba đứng im mãi ở khung 0. Cách này
 * còn được thêm một tính chất tốt hơn — cuộn tới thì cảnh chạy LẠI TỪ ĐẦU, thay
 * vì bắt người xem nhảy vào giữa vòng lặp.
 *
 * **Tôn trọng `prefers-reduced-motion`.** Ai bật giảm chuyển động thì cảnh đứng
 * ở khung đầu và hiện thanh điều khiển — chuyển động ở đây là NỘI DUNG (nó cho
 * xem cơ chế), nên bỏ hẳn là bỏ mất thông tin; đúng cách là để họ tự quyết.
 *
 * Đã hydrate chưa và có xin giảm chuyển động không đều là **trạng thái bên ngoài
 * React**, nên đọc bằng `useSyncExternalStore` chứ không phải `useEffect` +
 * `setState` — viết state từ effect làm render dây chuyền và để nó lệch pha với
 * thứ nó mô tả, đúng cái bẫy `lib/session.tsx` đã tránh. `inView` thì khác: nó
 * được đặt từ callback của observer, không phải từ thân effect.
 */

const noop = () => () => {};

let query: MediaQueryList | null = null;
const motionQuery = () => {
  if (query === null) query = window.matchMedia("(prefers-reduced-motion: reduce)");
  return query;
};

function subscribeMotion(onChange: () => void) {
  const q = motionQuery();
  q.addEventListener("change", onChange);
  return () => q.removeEventListener("change", onChange);
}

export function MockPlayer({
  component,
  durationInFrames,
  width,
  height,
}: {
  component: React.ComponentType;
  durationInFrames: number;
  width: number;
  height: number;
}) {
  const mounted = useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
  const calm = useSyncExternalStore(
    subscribeMotion,
    () => motionQuery().matches,
    () => false,
  );

  const box = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = box.current;
    if (el === null) return;
    const io = new IntersectionObserver(([entry]) => setInView(entry?.isIntersecting ?? false), {
      threshold: 0.3,
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    // Khung giữ chỗ có cùng tỉ lệ với cảnh, nên bố cục không nhảy lúc player
    // được gắn vào hay tháo ra.
    <div ref={box} style={{ aspectRatio: `${width} / ${height}` }}>
      {mounted && (calm || inView) && (
        <Player
          component={component}
          durationInFrames={durationInFrames}
          fps={FPS}
          compositionWidth={width}
          compositionHeight={height}
          style={{ width: "100%", height: "100%" }}
          autoPlay={!calm}
          loop
          /* Cảnh không có tiếng, nhưng vẫn phải khai: trình duyệt chặn autoPlay
             khi chưa tắt tiếng, Remotion tự tắt hộ rồi cảnh báo. Prop đúng là
             `initiallyMuted`, không phải `muted` như thông báo gợi ý — `muted`
             không tồn tại trên `<Player>`. */
          initiallyMuted
          /* Thanh điều khiển chỉ hiện khi người dùng xin giảm chuyển động, vì
             lúc đó nó là lối vào duy nhất. */
          controls={calm}
          spaceKeyToPlayOrPause={false}
        />
      )}
    </div>
  );
}
