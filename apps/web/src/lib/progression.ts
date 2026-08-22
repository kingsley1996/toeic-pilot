"use client";

import { API_ROUTES, type ProgressionPublic } from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

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

  useEffect(() => {
    if (!token) return;
    let alive = true;
    apiFetch<ProgressionPublic>(API_ROUTES.progression, { token })
      .then((data) => {
        if (alive) setProgression(data);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [token]);

  return progression;
}
