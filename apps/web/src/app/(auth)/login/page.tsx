"use client";

import { API_ROUTES, type TokenResponse, type UserLogin } from "@toeic-pilot/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { AuthLayout } from "@/components/auth-layout";
import { OAuthButtons } from "@/components/oauth-buttons";
import { Button, Field, FieldError, Input, Spinner } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { stripUrlParams, useLandingSearch } from "@/lib/url-once";
import { setAccessToken } from "@/lib/auth-storage";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  /* Lỗi của luồng Google/Apple quay về qua query `?oauth_error=`.

     Suy ra từ URL chứ không đưa vào state: một `setState` trong effect bị lint
     của dự án chặn, và ở đây cũng không cần — thông báo này chỉ phụ thuộc vào
     URL lúc hạ cánh. Xoá tham số khỏi thanh địa chỉ ngay sau lần dựng đầu, nếu
     không thì tải lại trang là lỗi cũ hiện ra lần nữa như vừa xảy ra. */
  const oauthError = useLandingSearch().get("oauth_error");
  useEffect(stripUrlParams, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    const form = new FormData(event.currentTarget);
    const body: UserLogin = {
      email: String(form.get("email")),
      password: String(form.get("password")),
    };

    try {
      const token = await apiFetch<TokenResponse>(API_ROUTES.login, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setAccessToken(token.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đăng nhập được.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout formLabel="Đăng nhập">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Email">
          <Input
            name="email"
            type="email"
            required
            autoComplete="email"
            placeholder="ban@vidu.com"
          />
        </Field>
        <Field label="Mật khẩu">
          <Input
            name="password"
            type="password"
            required
            minLength={8}
            autoComplete="current-password"
          />
        </Field>

        {/* Lỗi không bao giờ chỉ là màu: có icon, có viền, có chữ. */}
        {(error ?? oauthError) && <FieldError>{error ?? oauthError}</FieldError>}

        <Button type="submit" size="lg" disabled={loading} className="w-full">
          {loading && <Spinner />}
          {loading ? "Đang đăng nhập…" : "Đăng nhập"}
        </Button>
      </form>

      <OAuthButtons />

      <p className="mt-6 border-t border-rule pt-4 text-small text-ink-muted">
        Chưa có tài khoản?{" "}
        <Link
          href="/register"
          className="font-semibold text-action-ink underline-offset-2 hover:underline"
        >
          Tạo tài khoản
        </Link>
      </p>
    </AuthLayout>
  );
}
