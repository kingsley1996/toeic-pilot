"use client";

import { API_ROUTES, type ReviewSession } from "@toeic-pilot/shared";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useSession } from "@/lib/session";

/** Việc học hôm nay: thẻ đến hạn (lô này + cả hàng đợi) và từ mới còn lại. */
export type ReviewPlan = {
  /** Thẻ đến hạn trong lô hôm nay — đúng bằng những gì bấm "Ôn ngay" sẽ nhận. */
  due: number;
  /** Cả hàng đợi đến hạn, không cắt theo lô. Bằng `due` khi hàng đợi ngắn. */
  dueTotal: number;
  /** Từ mới còn lại hôm nay; 0 khi nợ ôn nhiều (máy chủ tạm ngừng) hoặc đã học đủ. */
  newCount: number;
};

const EMPTY: ReviewPlan = { due: 0, dueTotal: 0, newCount: 0 };

/**
 * Việc ôn tập của hôm nay, cho huy hiệu ở nav và cho lời nhắc đầu trang từ vựng.
 *
 * Đúng bằng những gì bấm "Ôn ngay" sẽ nhận: CÙNG endpoint, cùng tham số với
 * `/learn/review`, nên huy hiệu và phiên không thể nói hai con số khác nhau.
 * Endpoint cũ (`/vocabulary-review/due-count`) đếm riêng, chỉ đếm từ đến hạn và
 * không giới hạn — lệch cả về định nghĩa lẫn trần 100 thẻ.
 *
 * Ba số chứ không một: huy hiệu cần "sắp quên bao nhiêu" (due), còn giao diện
 * cần "hôm nay học gì" (due + new) và "còn bao nhiêu nữa đang chờ" (dueTotal).
 * Trộn chúng thành một con số là gốc của huy hiệu "99+" không ai hiểu.
 *
 * Đọc lại MỖI LẦN ĐỔI TRANG, không phải một lần lúc dựng: ôn xong một buổi rồi
 * rời trang mà con số vẫn đứng ở giá trị cũ thì nó nói dối, và đó là đúng lúc
 * người học nhìn nó để biết còn việc hay không. `include_cards=false` bỏ 55 thẻ
 * kèm audio URL, nên đọc lại vẫn rẻ.
 *
 * Hỏng thì trả 0 và chỗ hiển thị tự ẩn: một con số sai còn tệ hơn không có số.
 */
export function useReviewCount(): ReviewPlan {
  const { status, token } = useSession();
  const pathname = usePathname();
  const [plan, setPlan] = useState(EMPTY);

  useEffect(() => {
    // Ba trạng thái, không phải hai: `loading` chưa biết có token hay không,
    // và gọi lúc đó là một lượt 401 chắc chắn.
    if (status !== "authenticated" || !token) return;
    let cancelled = false;
    apiFetch<ReviewSession>(`${API_ROUTES.reviewSession}?include_cards=false`, { token })
      .then((data) => {
        if (!cancelled) {
          setPlan({
            due: data.due_count,
            dueTotal: data.due_total,
            newCount: data.new_count,
          });
        }
      })
      .catch(() => {
        if (!cancelled) setPlan(EMPTY);
      });
    return () => {
      cancelled = true;
    };
  }, [status, token, pathname]);

  // SUY RA chứ không ghi: đặt `setPlan(EMPTY)` ngay trong thân effect lúc đăng
  // xuất là setState đồng bộ trong effect — lint `react-hooks/set-state-in-effect`
  // chặn, và nó chặn đúng: giá trị đó là hàm của `status`, không phải một trạng
  // thái thứ hai chạy song song và có thể lệch pha.
  return status === "authenticated" ? plan : EMPTY;
}
