"use client";

import { API_ROUTES, type ReviewSession } from "@toeic-pilot/shared";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/**
 * Số thẻ của phiên ôn hôm nay (đến hạn + từ mới còn lại), cho huy hiệu ở nav
 * và cho lời nhắc đầu trang từ vựng.
 *
 * Đúng bằng những gì bấm "Ôn ngay" sẽ nhận: CÙNG endpoint, cùng tham số với
 * `/learn/review`, nên huy hiệu và phiên không thể nói hai con số khác nhau.
 * Endpoint cũ (`/vocabulary-review/due-count`) đếm riêng, chỉ đếm từ đến hạn và
 * không giới hạn — lệch cả về định nghĩa lẫn trần 100 thẻ.
 *
 * Đọc lại MỖI LẦN ĐỔI TRANG, không phải một lần lúc dựng: ôn xong một buổi rồi
 * rời trang mà con số vẫn đứng ở giá trị cũ thì nó nói dối, và đó là đúng lúc
 * người học nhìn nó để biết còn việc hay không. `include_cards=false` bỏ 55 thẻ
 * kèm audio URL, nên đọc lại vẫn rẻ.
 *
 * Hỏng thì trả 0 và chỗ hiển thị tự ẩn: một con số sai còn tệ hơn không có số.
 */
export function useReviewCount(): number {
  const { status, token } = useSession();
  const pathname = usePathname();
  const [count, setCount] = useState(0);

  useEffect(() => {
    // Ba trạng thái, không phải hai: `loading` chưa biết có token hay không,
    // và gọi lúc đó là một lượt 401 chắc chắn.
    if (status !== "authenticated" || !token) return;
    let cancelled = false;
    apiFetch<ReviewSession>(`${API_ROUTES.reviewSession}?include_cards=false`, { token })
      .then((data) => {
        if (!cancelled) setCount(data.due_count + data.new_count);
      })
      .catch(() => {
        if (!cancelled) setCount(0);
      });
    return () => {
      cancelled = true;
    };
  }, [status, token, pathname]);

  // SUY RA chứ không ghi: đặt `setCount(0)` ngay trong thân effect lúc đăng xuất
  // là setState đồng bộ trong effect — lint `react-hooks/set-state-in-effect`
  // chặn, và nó chặn đúng: giá trị đó là hàm của `status`, không phải một trạng
  // thái thứ hai chạy song song và có thể lệch pha.
  return status === "authenticated" ? count : 0;
}
