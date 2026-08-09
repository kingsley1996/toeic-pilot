"use client";

import { API_ROUTES, type UserPublic, type UserRegister } from "@toeic-pilot/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button, Field, FieldError, Input, Panel, Spinner } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    const form = new FormData(event.currentTarget);
    const body: UserRegister = {
      email: String(form.get("email")),
      password: String(form.get("password")),
    };

    try {
      await apiFetch<UserPublic>(API_ROUTES.register, {
        method: "POST",
        body: JSON.stringify(body),
      });
      router.push("/login");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Không tạo được tài khoản.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm px-4 py-12 sm:py-20">
      <p className="text-label font-semibold uppercase text-action-ink">Tài khoản</p>
      <h1 className="mt-1.5">Tạo tài khoản</h1>
      <p className="mt-2 text-ink-muted">Miễn phí. Bắt đầu học được ngay.</p>

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
          {/*
           * Giới hạn của bcrypt tính theo BYTE chứ không theo ký tự, và chữ có
           * dấu tốn 3 byte mỗi ký tự — nên một mật khẩu tiếng Việt 24 ký tự đã
           * chạm trần 72 byte. Máy chủ trả 422 chứ không cắt bớt âm thầm; nói
           * trước ở đây rẻ hơn là để người dùng gặp lỗi rồi mới đoán.
           */}
          <Field
            label="Mật khẩu"
            hint="Ít nhất 8 ký tự. Mật khẩu có dấu tiếng Việt tốn nhiều chỗ hơn, tối đa khoảng 24 ký tự."
          >
            <Input
              name="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
            />
          </Field>

          {error && <FieldError>{error}</FieldError>}

          <Button type="submit" size="lg" disabled={loading} className="w-full">
            {loading && <Spinner />}
            {loading ? "Đang tạo…" : "Tạo tài khoản"}
          </Button>
        </form>
      </Panel>

      <p className="mt-5 text-small text-ink-muted">
        Đã có tài khoản?{" "}
        <Link
          href="/login"
          className="font-semibold text-action-ink underline-offset-2 hover:underline"
        >
          Đăng nhập
        </Link>
      </p>
    </div>
  );
}
