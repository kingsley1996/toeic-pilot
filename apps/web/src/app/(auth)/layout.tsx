"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { PilotMascot, Typewriter } from "@/components/pilot-mascot";
import { cx } from "@/components/ui";

/**
 * Khung dùng chung của `/login` và `/register`.
 *
 * **Nó là một layout của nhóm route `(auth)`, không phải một component gọi từ
 * mỗi trang** — và đó là điều kiện để hiệu ứng tồn tại. Layout của nhóm route
 * KHÔNG bị dựng lại khi đi giữa hai trang trong nhóm, nên linh vật giữ nguyên
 * phần tử DOM của nó và trượt sang bên kia. Gọi từ trong mỗi trang thì mỗi lần
 * chuyển là một lần tháo ra dựng lại: ảnh biến mất rồi hiện ra ở chỗ mới, không
 * có gì để chuyển động.
 *
 * Ngoặc đơn trong tên thư mục là cú pháp nhóm route của Next: nó gom hai trang
 * lại dưới một layout mà KHÔNG thêm đoạn nào vào URL. `/login` vẫn là `/login`.
 *
 * Layout giữ nguyên cũng là thứ giữ TRẠNG THÁI của linh vật: nhịp chớp mắt
 * không bị đặt lại mỗi lần đổi trang, nên nó không chớp một cái ngay lúc vừa
 * trượt sang bên kia.
 */

/**
 * Hai nửa đổi chỗ bằng `translate-x`, không bằng `order` của flex/grid.
 *
 * `order` không chuyển động được — trình duyệt chỉ nội suy được những thuộc tính
 * có giá trị trung gian, và thứ tự sắp xếp thì không có giá trị trung gian nào.
 * Hai nửa rộng bằng nhau nên dịch đúng 100% chiều rộng của chính mình là chúng
 * hoán vị khít, và cả hai cùng chạy nên mắt đọc ra là MỘT chuyển động chứ không
 * phải hai thứ rời nhau.
 *
 * Chỉ áp từ `lg` trở lên. Ở màn hình hẹp hai nửa xếp chồng, và "trái/phải" không
 * còn nghĩa gì — dịch ngang ở đó chỉ đẩy nội dung ra khỏi màn hình.
 */
export default function AuthGroupLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const onRegister = pathname.startsWith("/register");

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:py-14 lg:min-h-[calc(100vh-11rem)]">
      {/* KHÔNG `items-center`: hai cột phải cao BẰNG NHAU, và cột cao hơn là
          cột biểu mẫu. Căn giữa thì mỗi cột cao đúng nội dung của nó, và khối
          nền của linh vật hụt hơn ô đăng nhập một đoạn — trông như hai khối rơi
          từ hai nơi khác nhau xuống cạnh nhau. Ở lưới, mặc định `stretch` cho
          cả hàng cùng chiều cao, và `h-full` bên trong nhận lại chiều cao đó. */}
      {/* `lg:gap-0`: hai khối CHẠM nhau thành một vật thể. Có khe ở giữa thì
          chúng đọc ra là hai cái hộp đặt cạnh nhau, và mắt phải tự nối lại.
          Dưới `lg` vẫn có khe, vì lúc đó chúng xếp chồng và "chạm nhau" theo
          chiều dọc lại thành một khối cao thượt không có chỗ thở. */}
      <div className="grid gap-8 lg:grid-cols-2 lg:gap-0">
        <div
          className={cx(
            "flex transition-transform duration-500 ease-out motion-reduce:transition-none",
            onRegister && "lg:translate-x-full",
          )}
        >
          {/*
           * Khung nền của linh vật: bậc nền CHÌM (`recess`) cộng chính tấm lưới
           * kỹ thuật của khung ứng dụng, không phải một ảnh nền riêng. Lưới vẽ
           * từ token `--rule` nên nó tự đổi theo sáng/tối cùng mọi đường kẻ khác;
           * một ảnh sẽ phải làm hai bản và bản tối là bản bị quên (§6.3).
           *
           * `overflow-hidden` để lưới bị cắt đúng theo bo góc 4px, nếu không nó
           * tràn ra khỏi khối và mất luôn cảm giác "một ô cửa".
           */}
          {/* Cạnh chung: bỏ viền và bo góc ở đúng bên tiếp giáp ô đăng nhập, để
                hai khối liền thành một. Bên nào là bên chung thì đổi theo trang,
                nên nó phải suy từ `onRegister` chứ không cố định được. Không bỏ
                thì chỗ tiếp giáp có hai đường viền chồng lên nhau — dày gấp đôi
                mọi đường kẻ khác trên trang, và đọc ra là lỗi. */}
          <div
            className={cx(
              "relative flex h-full w-full flex-col items-center justify-center overflow-hidden rounded border border-rule bg-recess px-6 py-8",
              onRegister ? "lg:rounded-l-none lg:border-l-0" : "lg:rounded-r-none lg:border-r-0",
            )}
          >
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0"
              style={{
                backgroundImage:
                  "repeating-linear-gradient(to right, rgb(var(--rule) / 0.5) 0 1px, transparent 1px 32px), repeating-linear-gradient(to bottom, rgb(var(--rule) / 0.5) 0 1px, transparent 1px 32px)",
              }}
            />

            <PilotMascot
              className={cx(
                "relative mx-auto h-40 w-40 transition-transform duration-500 ease-out motion-reduce:transition-none sm:h-52 sm:w-52 lg:h-60 lg:w-60",
                // Lật ngang khi sang phải để linh vật luôn NHÌN VỀ phía biểu
                // mẫu. Không lật thì sau khi đổi bên nó quay lưng vào ô nhập, và
                // cái sai đó đọc ra ngay dù không ai gọi được tên nó.
                onRegister && "-scale-x-100",
              )}
            />

            {/* Slogan: MỘT dòng, gõ ra từng chữ, và nó nói đúng cách sản phẩm
                hoạt động — ôn theo lịch quên của trí nhớ — chứ không phải một
                lời hứa về điểm số mà không ai kiểm được. Nằm trong khung nền để
                nó thuộc về linh vật, không thành một dòng chữ trôi nổi cạnh
                biểu mẫu. */}
            <Typewriter
              text="Ôn đúng lúc sắp quên."
              className="relative mt-5 text-center text-small text-ink-muted"
            />
          </div>
        </div>

        {/* `items-center` ở ĐÂY chứ không ở lưới: ô đăng nhập giữ đúng chiều
            cao nội dung của nó và nằm giữa hàng, trong khi khối nền bên kia mới
            là thứ giãn ra cho bằng. Đặt ngược lại thì biểu mẫu bị kéo cao và có
            một khoảng trống dưới đáy, trông như đang thiếu một trường nhập. */}
        <div
          className={cx(
            "flex items-center transition-transform duration-500 ease-out motion-reduce:transition-none",
            onRegister && "lg:-translate-x-full",
          )}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
