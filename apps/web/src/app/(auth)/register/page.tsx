"use client";

import {
  API_ROUTES,
  type TokenResponse,
  type UserPublic,
  type UserRegister,
} from "@toeic-pilot/shared";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { AuthLayout } from "@/components/auth-layout";
import { OAuthButtons } from "@/components/oauth-buttons";
import { TurnstileUnavailable, turnstileHeader, useTurnstile } from "@/components/turnstile";
import { Button, Field, FieldError, Input, Spinner } from "@/components/ui";
import { ApiError, apiFetch } from "@/lib/api";
import { setAccessToken } from "@/lib/auth-storage";
import { safeNextPath, stripUrlParams, useLandingSearch } from "@/lib/url-once";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const gate = useTurnstile();

  // `?next=` là chỗ quay về khi người dùng tới đây từ một hộp thoại chặn giữa
  // chừng. Đọc một lần lúc hạ cánh rồi xoá khỏi thanh địa chỉ, cùng luật với
  // trang đăng nhập.
  const next = safeNextPath(useLandingSearch().get("next"));
  useEffect(stripUrlParams, []);

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
        headers: turnstileHeader(await gate.take()),
        body: JSON.stringify(body),
      });
      /*
       * Đăng nhập luôn bằng chính thông tin vừa nhập. Trước đây trang này đẩy
       * thẳng sang `/login`, nên người dùng phải gõ lại đúng email và mật khẩu
       * họ vừa đặt xong ba giây trước — trong khi ngay phía trên có dòng "Miễn
       * phí. Bắt đầu học được ngay."
       *
       * `register` trả về `UserPublic` chứ không trả token, nên phải gọi thêm
       * một lượt. Đổi nó thành trả token thì sạch hơn nhưng là đổi hợp đồng đã
       * có test; một request nữa ở đây rẻ hơn nhiều.
       *
       * Nếu bước đăng nhập hỏng thì tài khoản VẪN đã tạo xong, nên rơi về
       * `/login` là đúng — người dùng đăng nhập tay và không mất gì.
       */
      try {
        /* Token thứ HAI, và nó bắt buộc phải là một cái mới: Cloudflare chỉ
           nhận mỗi token đúng một lần, còn một lần bấm "Tạo tài khoản" ở đây lại
           gọi hai endpoint. `take()` tự làm mới, nên chỗ này chỉ cần gọi lại. */
        const token = await apiFetch<TokenResponse>(API_ROUTES.login, {
          method: "POST",
          headers: turnstileHeader(await gate.take()),
          body: JSON.stringify(body),
        });
        setAccessToken(token.access_token);
        router.push(next);
      } catch {
        router.push(`/login?next=${encodeURIComponent(next)}`);
      }
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof TurnstileUnavailable
          ? err.message
          : "Không tạo được tài khoản.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout formLabel="Tạo tài khoản">
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

        {gate.widget}

        {error && <FieldError>{error}</FieldError>}

        <Button type="submit" size="lg" disabled={loading} className="w-full">
          {loading && <Spinner />}
          {loading ? "Đang tạo…" : "Tạo tài khoản"}
        </Button>
      </form>

      {/* Cùng bộ nút với trang đăng nhập: với nhà cung cấp bên ngoài thì "đăng
          ký" và "đăng nhập" là CÙNG một thao tác — lần đầu tạo tài khoản, lần
          sau vào lại. Dựng hai đường riêng chỉ tạo ra hai cách gọi tên cho một
          việc, và người dùng phải đoán mình đang ở đường nào. */}
      <OAuthButtons next={next} />

      <p className="mt-6 border-t border-rule pt-4 text-small text-ink-muted">
        Đã có tài khoản?{" "}
        <Link
          href={next === "/dashboard" ? "/login" : `/login?next=${encodeURIComponent(next)}`}
          className="font-semibold text-action-ink underline-offset-2 hover:underline"
        >
          Đăng nhập
        </Link>
      </p>
    </AuthLayout>
  );
}
