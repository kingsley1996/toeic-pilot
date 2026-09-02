"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AuthLayout } from "@/components/auth-layout";
import { LoginForm } from "@/components/login-form";
import { safeNextPath, stripUrlParams, useLandingSearch } from "@/lib/url-once";

export default function LoginPage() {
  const router = useRouter();

  /* Lỗi của luồng Google/Apple quay về qua query `?oauth_error=`, và `?next=`
     là chỗ quay về khi người dùng bị chặn ở giữa một việc đang làm dở.

     Suy ra từ URL chứ không đưa vào state: một `setState` trong effect bị lint
     của dự án chặn, và ở đây cũng không cần — cả hai chỉ phụ thuộc vào URL lúc
     hạ cánh. Xoá tham số khỏi thanh địa chỉ ngay sau lần dựng đầu, nếu không
     thì tải lại trang là lỗi cũ hiện ra lần nữa như vừa xảy ra. */
  const search = useLandingSearch();
  const oauthError = search.get("oauth_error");
  const next = safeNextPath(search.get("next"));
  useEffect(stripUrlParams, []);

  return (
    <AuthLayout formLabel="Đăng nhập">
      <LoginForm next={next} initialError={oauthError} onSuccess={() => router.push(next)} />
    </AuthLayout>
  );
}
