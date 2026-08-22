"use client";

import { API_ROUTES, type AuthProviderPublic } from "@toeic-pilot/shared";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

/**
 * Nút "tiếp tục với Google / Apple", chỉ hiện khi máy chủ nói nhà cung cấp đó
 * đang bật.
 *
 * **Danh sách hỏi máy chủ chứ không cứng trong mã.** Một nút cứng sẽ hiện ở mọi
 * bản triển khai, kể cả bản chưa có khoá — và người dùng bấm vào chỉ thấy lỗi,
 * không phân biệt được "chưa dựng" với "đang hỏng". Máy chủ trả mảng rỗng thì
 * cả khối này biến mất, kể cả đường kẻ "hoặc".
 *
 * **Đây là chuyển hướng cả trang, không phải `fetch`.** Luồng phải đi qua màn
 * hình của Google rồi quay về API, nên `window.location.href` mới đúng; `fetch`
 * sẽ nhận về HTML của Google và không có gì để hiển thị.
 *
 * KHÔNG nhúng SDK của Google hay Apple. CLAUDE.md ghi rõ việc hoãn chuyển token
 * sang cookie httpOnly (P1-7b) đứng vững *chỉ vì* ứng dụng không có script bên
 * thứ ba nào; thêm một cái là làm lý do đó hết hiệu lực.
 */

/* Chữ đúng theo hướng dẫn thương hiệu của từng bên: cả Google lẫn Apple đều yêu
   cầu "Continue with X" hoặc "Sign in with X", không phải một tên tự đặt. */
const LABELS: Record<string, string> = {
  google: "Tiếp tục với Google",
  apple: "Tiếp tục với Apple",
};

export function OAuthButtons({ next = "/dashboard" }: { next?: string }) {
  const [providers, setProviders] = useState<AuthProviderPublic[]>([]);

  useEffect(() => {
    let alive = true;
    apiFetch<AuthProviderPublic[]>(API_ROUTES.authProviders)
      .then((rows) => {
        if (alive) setProviders(rows);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  if (providers.length === 0) return null;

  return (
    <div className="mt-5">
      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-rule" />
        <span className="text-small text-ink-faint">hoặc</span>
        <span className="h-px flex-1 bg-rule" />
      </div>

      <div className="mt-4 grid gap-2">
        {providers.map((provider) => (
          <a
            key={provider.id}
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}${API_ROUTES.authStart(provider.id, next)}`}
            className="inline-flex h-10 items-center justify-center gap-2 rounded border border-rule-strong px-4 text-small font-semibold transition-colors hover:bg-recess"
          >
            <ProviderMark id={provider.id} />
            {LABELS[provider.id] ?? `Tiếp tục với ${provider.label}`}
          </a>
        ))}
      </div>
    </div>
  );
}

/**
 * Dấu hiệu nhận biết của nhà cung cấp, vẽ bằng SVG nội tuyến.
 *
 * Không tải logo từ CDN của họ: đó lại là một tài nguyên bên thứ ba trên trang
 * đăng nhập, và nó còn hỏng lặng lẽ khi đường mạng bị chặn. Chữ "G" và quả táo
 * ở đây là hình tối giản theo đúng màu thương hiệu.
 */
function ProviderMark({ id }: { id: string }) {
  if (id === "google") {
    return (
      <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden focusable="false">
        <path
          fill="#4285F4"
          d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
        />
        <path
          fill="#34A853"
          d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
        />
        <path
          fill="#FBBC05"
          d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
        />
        <path
          fill="#EA4335"
          d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
        />
      </svg>
    );
  }
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden focusable="false">
      <path
        fill="currentColor"
        d="M16.36 12.7c.02 2.5 2.19 3.33 2.22 3.35-.02.06-.35 1.2-1.15 2.37-.69 1.02-1.4 2.03-2.53 2.05-1.1.02-1.46-.65-2.72-.65s-1.65.63-2.7.67c-1.08.04-1.9-1.1-2.6-2.11-1.43-2.07-2.53-5.85-1.06-8.4a4.1 4.1 0 0 1 3.47-2.11c1.07-.02 2.07.72 2.72.72.65 0 1.87-.89 3.15-.76.54.02 2.05.22 3.02 1.64-.08.05-1.8 1.05-1.78 3.14M14.4 4.85c.58-.7.97-1.67.86-2.64-.83.03-1.84.55-2.44 1.25-.53.62-1 1.6-.87 2.55.93.07 1.87-.47 2.45-1.16"
      />
    </svg>
  );
}
