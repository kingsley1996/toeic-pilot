"use client";

import { LogIn } from "lucide-react";

import { ButtonLink } from "@/components/ui";
import { useSession } from "@/lib/session";

/**
 * Nhắc khách vãng lai rằng họ làm bài được nhưng không lưu được gì.
 *
 * Ba trạng thái phiên, không phải hai. `loading` KHÔNG hiện gì: localStorage
 * chưa tồn tại lúc máy chủ dựng trang, nên đoán ở đó sẽ nháy một dòng "bạn chưa
 * đăng nhập" vào mặt người đã đăng nhập rồi — đúng cái lỗi mà header từng mắc
 * và `.claude/rules/frontend.md` ghi lại.
 *
 * Nó nói ra HẬU QUẢ chứ không chỉ nói trạng thái. "Bạn chưa đăng nhập" là một
 * sự thật vô dụng; thứ người học cần biết là gõ xong rồi tải lại trang thì mất
 * hết. Và nó là `warn` chứ không phải `alert`: chưa có gì hỏng, chỉ là một điều
 * cần biết trước khi bỏ công ra.
 */
export function GuestNotice({ className }: { className?: string }) {
  const { status } = useSession();
  if (status !== "anonymous") return null;

  return (
    <div
      className={`rounded border border-warn bg-warn-tint px-4 py-3 ${className ?? ""}`}
      role="status"
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p className="flex-1 text-small">
          <span className="font-semibold">Bạn chưa đăng nhập — tiến độ sẽ không được lưu.</span>{" "}
          <span className="text-ink-muted">
            Bài nghe vẫn chấm bình thường, nhưng tải lại trang là mất hết.
          </span>
        </p>
        <div className="flex shrink-0 items-center gap-2">
          <ButtonLink href="/login" variant="secondary" size="sm">
            <LogIn size={14} strokeWidth={2} aria-hidden />
            Đăng nhập
          </ButtonLink>
          <ButtonLink href="/register" size="sm">
            Tạo tài khoản
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
