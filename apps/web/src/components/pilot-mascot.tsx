"use client";

import { useEffect, useRef, useState } from "react";

import { cx } from "@/components/ui";

/**
 * Linh vật của TOEIC Pilot ở hai trang đăng nhập và đăng ký.
 *
 * Bốn khung hình, sinh trong MỘT lần từ một sheet 2×2 (`content/sources/
 * progression-art/mascot-sheet.prompt.txt`). Sinh từng khung riêng cũng được,
 * nhưng model không vẽ lại đúng một nhân vật hai lần — mỗi khung sẽ lệch một
 * chút ở mũ, khăn hoặc màu, và lúc chớp mắt thì cả con vật giật một cái.
 *
 * Ba trạng thái được dùng:
 *
 *   · `idle`  — mở mắt, đứng yên, thở nhẹ
 *   · `blink` — nhắm mắt, hiện ~150ms mỗi vài giây
 *   · `hide`  — hai tay che mắt, khi con trỏ đang ở ô mật khẩu
 *
 * Khung `cheer` (vẫy tay) tải sẵn nhưng chưa dùng: nó dành cho lúc đăng nhập
 * thành công, mà lúc đó trang đã chuyển đi rồi — nên nó sẽ chỉ có nghĩa khi nào
 * có một khoảnh khắc chờ đủ dài để nhìn thấy.
 */

const FRAMES = {
  idle: "/brand/pilot-idle.png",
  blink: "/brand/pilot-blink.png",
  hide: "/brand/pilot-hide.png",
} as const;

/** Nhịp chớp mắt. Lệch ngẫu nhiên để không thành máy đếm nhịp. */
const BLINK_EVERY_MS = 4200;
const BLINK_JITTER_MS = 2600;
const BLINK_HOLD_MS = 150;

export function PilotMascot({ className }: { className?: string }) {
  const [blinking, setBlinking] = useState(false);
  const [hiding, setHiding] = useState(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    let cancelled = false;

    /* Hẹn giờ lồng nhau chứ không `setInterval`: mỗi lần chớp cách nhau một
       khoảng KHÁC nhau, và một interval thì chỉ có đúng một chu kỳ. Mắt bắt được
       nhịp đều rất nhanh, và lúc đó nó đọc ra là một vòng lặp chứ không phải một
       sinh vật. */
    function schedule() {
      const wait = BLINK_EVERY_MS + Math.random() * BLINK_JITTER_MS;
      timers.current.push(
        setTimeout(() => {
          if (cancelled) return;
          setBlinking(true);
          timers.current.push(
            setTimeout(() => {
              if (cancelled) return;
              setBlinking(false);
              schedule();
            }, BLINK_HOLD_MS),
          );
        }, wait),
      );
    }
    schedule();

    return () => {
      cancelled = true;
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };
  }, []);

  useEffect(() => {
    /*
     * Nghe ở cấp TÀI LIỆU, không truyền prop xuống từng ô nhập.
     *
     * Linh vật sống trong layout của nhóm route, còn ô mật khẩu nằm trong từng
     * trang — hai nhánh khác nhau của cây component. Nối chúng bằng prop sẽ phải
     * dựng một context xuyên qua layout chỉ để nói "đang gõ mật khẩu", và mỗi
     * trang mới thêm sau này lại phải nhớ nối vào. Sự kiện focus thì nổi bọt lên
     * tận `document`, nên một chỗ nghe là đủ cho mọi ô mật khẩu, kể cả ô của
     * trang chưa viết.
     */
    function isPassword(target: EventTarget | null): boolean {
      return target instanceof HTMLInputElement && target.type === "password";
    }
    function onFocusIn(event: FocusEvent) {
      if (isPassword(event.target)) setHiding(true);
    }
    function onFocusOut(event: FocusEvent) {
      if (isPassword(event.target)) setHiding(false);
    }
    document.addEventListener("focusin", onFocusIn);
    document.addEventListener("focusout", onFocusOut);
    return () => {
      document.removeEventListener("focusin", onFocusIn);
      document.removeEventListener("focusout", onFocusOut);
    };
  }, []);

  // Che mắt thắng chớp mắt: đang che thì mắt đã khuất sau bàn tay rồi.
  const frame = hiding ? FRAMES.hide : blinking ? FRAMES.blink : FRAMES.idle;

  return (
    <div className={cx("relative", className)}>
      {/* Tải sẵn hai khung kia bằng cách đặt chúng vào DOM với kích thước 0.
          Không có bước này thì lần chớp mắt ĐẦU TIÊN là một khoảng trống: trình
          duyệt mới bắt đầu tải ảnh đúng lúc cần hiện nó. */}
      {[FRAMES.blink, FRAMES.hide].map((src) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={src} src={src} alt="" aria-hidden className="absolute h-0 w-0 opacity-0" />
      ))}

      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={frame}
        alt=""
        aria-hidden
        className="animate-breathe h-full w-full select-none object-contain"
      />
    </div>
  );
}

/**
 * Slogan gõ ra từng chữ.
 *
 * Ba điều kiện phải cùng đúng, và cách làm hiển nhiên hỏng ở ít nhất một:
 *
 *   · **Trình đọc màn hình phải nghe được CẢ CÂU**, không phải từng ký tự một.
 *     Một phần tử đang được cập nhật liên tục sẽ bị đọc lại hoặc đọc rời rạc,
 *     nên phần chạy chữ mang `aria-hidden` và câu đầy đủ nằm trong một `sr-only`
 *     riêng — bản dành cho máy đọc không bao giờ dở dang.
 *   · **Chiều cao không được nhảy.** Chữ mọc dần làm khối bên dưới nhích lên
 *     nhích xuống nếu câu xuống dòng; ở đây câu ngắn nên giữ một dòng, và
 *     `min-h` khoá lại phòng khi đổi câu dài hơn.
 *   · **`prefers-reduced-motion` thì hiện luôn cả câu.** Chạy chữ là chuyển
 *     động, và người tắt chuyển động không nên phải chờ mới đọc được.
 */
export function Typewriter({ text, className }: { text: string; className?: string }) {
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      /* Nhảy thẳng tới cả câu, nhưng qua một `setTimeout(0)` chứ không gọi
         `setShown` ngay trong thân effect: `react-hooks/set-state-in-effect`
         chặn lối kia, và luật đó đúng — đặt state đồng bộ trong effect làm
         render xếp tầng. Trễ một khung hình thì mắt không thấy được. */
      const jump = setTimeout(() => setShown(text.length), 0);
      return () => clearTimeout(jump);
    }
    /* Không cần đặt lại về 0: `text` là hằng ở cả hai trang, và `useState` đã
       khởi tạo bằng 0 rồi. Đặt lại ở đây chỉ để phòng một trường hợp chưa tồn
       tại, đổi lấy một lệnh setState đồng bộ trong effect. */
    const timer = setInterval(() => {
      setShown((count) => {
        if (count >= text.length) {
          clearInterval(timer);
          return count;
        }
        return count + 1;
      });
    }, 55);
    return () => clearInterval(timer);
  }, [text]);

  const done = shown >= text.length;

  return (
    <p className={cx("min-h-[1.5rem]", className)}>
      <span aria-hidden>
        {text.slice(0, shown)}
        {/* Con trỏ nhấp nháy, và nó BIẾN MẤT khi gõ xong: một con trỏ đứng nhấp
            nháy mãi bên cạnh một câu đã hoàn chỉnh là thứ kéo mắt về mình suốt
            thời gian người dùng đang gõ ô nhập bên cạnh. */}
        {!done && (
          <span
            className="animate-caret ml-0.5 inline-block w-[1px] bg-ink align-middle"
            style={{ height: "0.9em" }}
          />
        )}
      </span>
      <span className="sr-only">{text}</span>
    </p>
  );
}
