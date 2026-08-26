"use client";

import { API_ROUTES, type ProgressionPublic } from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import { useToast } from "@/lib/toast";

/**
 * Lên level là thứ DUY NHẤT trong bộ này được báo từ mọi trang, và đó là chủ ý:
 * hook này đã nằm sẵn trong sidebar lẫn thanh trên, nên nó thấy được cú lên bậc
 * dù người học đang ở `/learn/review` hay `/learn/dictation`. Huy hiệu và việc
 * hôm nay thì chỉ đọc ở trang chủ, nên chúng chỉ báo được ở đó.
 *
 * So sánh LỚN HƠN chứ không phải khác nhau, và không bao giờ báo ở lần đọc đầu:
 * chưa có số cũ thì không có gì để nói người ta vừa *lên*. Ghi số rồi im lặng.
 *
 * Cũng vì thế không dùng `announceOnce` — nó so bằng chữ ký, mà ở đây câu hỏi là
 * "có cao hơn không". `level_reached` phía máy chủ là mốc cao nhất chỉ tăng, nên
 * số này không tụt; nhưng đăng nhập bằng tài khoản khác trong cùng tab thì có,
 * và lúc đó phép so lớn-hơn lặng lẽ làm đúng việc — không ai bị chúc mừng vì
 * level của người khác.
 */
function announceLevel(level: number, show: ReturnType<typeof useToast>["show"]) {
  let previous: number | null = null;
  try {
    const raw = window.sessionStorage.getItem("toast:level");
    previous = raw === null ? null : Number(raw);
    window.sessionStorage.setItem("toast:level", String(level));
  } catch {
    return;
  }
  if (previous === null || Number.isNaN(previous) || level <= previous) return;
  show({
    tone: "ok",
    title: `Lên Level ${level}`,
    description: "Tiếp tục học để giữ streak và mở khung avatar mới.",
    href: "/profile",
    linkLabel: "Xem hồ sơ",
    dedupeKey: "level",
  });
}

/**
 * Level và khung của chính người đang đăng nhập.
 *
 * **Không nhét vào `useSession`.** Phiên trả lời "ai đang đăng nhập và họ được
 * làm gì", và nó được dựng lại mỗi khi token đổi. Level thì đổi theo hoạt động
 * học, nên gộp vào phiên là buộc một thứ thay đổi liên tục vào một thứ phải ổn
 * định — mọi trang sẽ dựng lại khi người dùng vừa ôn xong một từ.
 *
 * **Hỏng thì im lặng trả về `null`.** Avatar không khung vẫn là avatar; một khối
 * danh tính biến mất vì một con số trang trí thì không.
 *
 * Hook dùng chung cho sidebar và thanh trên. Hai bản sao của cùng một effect sẽ
 * trôi khỏi nhau ở đúng chỗ khó thấy nhất: một bên nhớ đổi khi hợp đồng đổi, bên
 * kia thì không, và cái sai chỉ hiện ở ba trang ngoài ứng dụng.
 */
export function useProgression(token: string | null): ProgressionPublic | null {
  const [progression, setProgression] = useState<ProgressionPublic | null>(null);
  const { show } = useToast();

  useEffect(() => {
    if (!token) return;
    let alive = true;
    apiFetch<ProgressionPublic>(API_ROUTES.progression, { token })
      .then((data) => {
        if (alive) setProgression(data);
        // Ngoài `alive` có chủ ý — cùng lý do đã ghi ở `daily-tasks.tsx`.
        announceLevel(data.level, show);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token, show]);

  return progression;
}
