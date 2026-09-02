"use client";

import { API_ROUTES, type TokenResponse, type UserLogin } from "@toeic-pilot/shared";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { OAuthButtons } from "@/components/oauth-buttons";
import { Button, Field, FieldError, Input, Spinner } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { setAccessToken } from "@/lib/auth-storage";

/**
 * Ô đăng nhập, dùng chung cho trang `/login` và hộp thoại chặn ở khu luyện thi.
 *
 * `onSuccess` chứ không phải một lần `router.push` cứng, vì hai chỗ gọi muốn
 * hai thứ khác nhau: trang thì đi tiếp, hộp thoại thì **ở nguyên chỗ cũ**. Cái
 * sau chạy được là nhờ token ghi vào `auth-storage` được `SessionProvider` theo
 * dõi qua `useSyncExternalStore` — cả ứng dụng thấy mình đã đăng nhập ngay,
 * không cần tải lại trang.
 */
export function LoginForm({
  next = "/dashboard",
  initialError,
  onSuccess,
}: {
  next?: string;
  initialError?: string | null;
  onSuccess: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      // Không mở khoá nút lại ở nhánh thành công: `onSuccess` đóng hộp thoại
      // hoặc chuyển trang, và bật lại chỉ kịp nháy một nút bấm được lên màn.
      onSuccess();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đăng nhập được.");
      setLoading(false);
    }
  }

  const registerHref =
    next === "/dashboard" ? "/register" : `/register?next=${encodeURIComponent(next)}`;

  return (
    <>
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
        {(error ?? initialError) && <FieldError>{error ?? initialError}</FieldError>}

        <Button type="submit" size="lg" disabled={loading} className="w-full">
          {loading && <Spinner />}
          {loading ? "Đang đăng nhập…" : "Đăng nhập"}
        </Button>
      </form>

      <OAuthButtons next={next} />

      <p className="mt-6 border-t border-rule pt-4 text-small text-ink-muted">
        Chưa có tài khoản?{" "}
        <Link
          href={registerHref}
          className="font-semibold text-action-ink underline-offset-2 hover:underline"
        >
          Tạo tài khoản
        </Link>
      </p>
    </>
  );
}
