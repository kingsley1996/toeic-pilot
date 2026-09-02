"use client";

import { API_ROUTES, type ReviewDueCount } from "@toeic-pilot/shared";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/**
 * Số từ đến hạn ôn, cho huy hiệu ở nav và cho lời nhắc đầu trang từ vựng.
 *
 * Đọc lại MỖI LẦN ĐỔI TRANG, không phải một lần lúc dựng: ôn xong một buổi rồi
 * rời trang mà con số vẫn đứng ở giá trị cũ thì nó nói dối, và đó là đúng lúc
 * người học nhìn nó để biết còn việc hay không. Endpoint là một lượt `COUNT`
 * nên đọc lại rẻ.
 *
 * Hỏng thì trả 0 và chỗ hiển thị tự ẩn: một con số sai còn tệ hơn không có số.
 */
export function useDueCount(): number {
  const { status, token } = useSession();
  const pathname = usePathname();
  const [due, setDue] = useState(0);

  useEffect(() => {
    // Ba trạng thái, không phải hai: `loading` chưa biết có token hay không,
    // và gọi lúc đó là một lượt 401 chắc chắn.
    if (status !== "authenticated" || !token) return;
    let cancelled = false;
    apiFetch<ReviewDueCount>(API_ROUTES.reviewDueCount, { token })
      .then((data) => {
        if (!cancelled) setDue(data.due);
      })
      .catch(() => {
        if (!cancelled) setDue(0);
      });
    return () => {
      cancelled = true;
    };
  }, [status, token, pathname]);

  // SUY RA chứ không ghi: đặt `setDue(0)` ngay trong thân effect lúc đăng xuất
  // là setState đồng bộ trong effect — lint `react-hooks/set-state-in-effect`
  // chặn, và nó chặn đúng: giá trị đó là hàm của `status`, không phải một trạng
  // thái thứ hai chạy song song và có thể lệch pha.
  return status === "authenticated" ? due : 0;
}
