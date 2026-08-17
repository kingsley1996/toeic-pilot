"use client";

import { API_ROUTES, type TokenResponse, type UserLogin } from "@toeic-pilot/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button, Field, FieldError, Input, Panel, Spinner } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { setAccessToken } from "@/lib/auth-storage";

export default function LoginPage() {
  const router = useRouter();
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
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không đăng nhập được.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm px-4 py-12 sm:py-20">
      <p className="text-label font-semibold uppercase text-action-ink">Tài khoản</p>
      <h1 className="mt-1.5">Đăng nhập</h1>
      <p className="mt-2 text-ink-muted">Tiếp tục phiên ôn tập của bạn.</p>

      <Panel className="mt-7 p-5">
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
          {error && <FieldError>{error}</FieldError>}

          <Button type="submit" size="lg" disabled={loading} className="w-full">
            {loading && <Spinner />}
            {loading ? "Đang đăng nhập…" : "Đăng nhập"}
          </Button>
        </form>
      </Panel>

      <p className="mt-5 text-small text-ink-muted">
        Chưa có tài khoản?{" "}
        <Link
          href="/register"
          className="font-semibold text-action-ink underline-offset-2 hover:underline"
        >
          Tạo tài khoản
        </Link>
      </p>
    </div>
  );
}
