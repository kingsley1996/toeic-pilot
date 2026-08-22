"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { Alert, Page, Skeleton } from "@/components/ui";
import { setAccessToken } from "@/lib/auth-storage";
import { stripUrlParams, useLandingHash } from "@/lib/url-once";

/**
 * Điểm hạ cánh sau khi đăng nhập bằng Google hoặc Apple.
 *
 * Máy chủ trả token trong **fragment** của URL (`#token=…`), không phải query.
 * Query đi vào log máy chủ, vào header `Referer` của mọi tài nguyên trên trang
 * đích, và nằm đọc được trong lịch sử trình duyệt. Fragment không rời khỏi
 * trình duyệt bao giờ.
 *
 * Trang này **xoá fragment ngay sau khi đọc** bằng `replaceState`: để nguyên thì
 * token còn nằm trong thanh địa chỉ, trong lịch sử, và trong mọi ảnh chụp màn
 * hình người dùng gửi cho bộ phận hỗ trợ.
 *
 * Cả đoạn này biến mất vào ngày token chuyển sang cookie httpOnly (P1-7b).
 */
export default function OAuthCallbackPage() {
  const router = useRouter();
  // Đọc một lần lúc hạ cánh. Không `setState` trong effect: trạng thái duy nhất
  // ở đây là "có token hay không", và nó suy được thẳng từ URL.
  const params = useLandingHash();
  const token = params.get("token");
  const next = params.get("next") ?? "/dashboard";

  useEffect(() => {
    if (!token) return;
    setAccessToken(token);
    // Xoá fragment TRƯỚC khi điều hướng, và thay chỗ thay vì đẩy một mục lịch
    // sử mới: bấm Back sau đó không được quay lại một URL còn mang token.
    stripUrlParams();
    // `replace`, không `push` — trang này không phải nơi ai muốn quay lại.
    router.replace(next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
  }, [router, token, next]);

  return (
    <Page>
      {token ? (
        <>
          <Skeleton className="h-9 w-64" />
          <Skeleton className="mt-6 h-40" />
        </>
      ) : (
        <Alert>Không nhận được phiên đăng nhập. Thử lại từ trang đăng nhập.</Alert>
      )}
    </Page>
  );
}
