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
      {/* Mobile: xếp dọc, chữ dòng đầu và nút chiếm trọn hàng — `flex-1` trên
          một hàng ngang hẹp ép đoạn văn co lại thành dọc chữ một-từ-một-dòng. */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4 sm:gap-y-2">
        <p className="text-small sm:min-w-48 sm:flex-1">
          <span className="font-semibold">Bạn chưa đăng nhập — tiến độ sẽ không được lưu.</span>{" "}
          <span className="text-ink-muted">
            Bài nghe vẫn chấm bình thường, nhưng tải lại trang là mất hết.
          </span>
        </p>
        <div className="flex items-center gap-2 max-sm:[&>a]:flex-1">
          <ButtonLink href="/login" variant="secondary" size="sm" className="max-sm:justify-center">
            <LogIn size={14} strokeWidth={2} aria-hidden />
            Đăng nhập
          </ButtonLink>
          <ButtonLink href="/register" size="sm" className="max-sm:justify-center">
            Tạo tài khoản
          </ButtonLink>
        </div>
      </div>
    </div>
  );
}
