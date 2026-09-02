"use client";

import { type ReactNode } from "react";

import { LoginForm } from "@/components/login-form";
import { Modal } from "@/components/modal";

/**
 * Hộp thoại đăng nhập, mở ngay tại chỗ người dùng vừa bấm.
 *
 * Dùng thay cho một lần chuyển sang `/login` ở những chỗ mà việc đang làm dở
 * còn ý nghĩa: bấm một đề cụ thể trong danh sách rồi bị đá sang trang đăng
 * nhập, đăng nhập xong đứng ở `/dashboard`, là mất luôn cái đề vừa chọn.
 *
 * `next` chỉ dùng cho đường Google/Apple — luồng đó bắt buộc rời trang rồi quay
 * lại, nên nó cần biết chỗ hạ cánh. Đăng nhập bằng mật khẩu không rời trang và
 * đi qua `onSuccess`.
 */
export function LoginModal({
  open,
  onClose,
  onSuccess,
  next,
  title = "Đăng nhập để xem đề",
  /* Hai câu ngắn, không phải một câu nối bằng dấu phẩy: câu đầu là tin tốt và
     phải đọc được một mình. Tên đề cố ý KHÔNG nằm ở đây — người dùng vừa bấm
     vào nó, còn nhét thêm một cái tên dài trong ngoặc kép thì dòng ghi chú
     xuống hai hàng và cái đáng nhớ nhất bị đẩy ra cuối. */
  description = (
    <>
      Đề thi thử <strong className="font-semibold text-ink">miễn phí</strong>. Cần tài khoản để lưu
      bài làm và điểm số.
    </>
  ),
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  next: string;
  title?: string;
  description?: ReactNode;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title} description={description}>
      <LoginForm next={next} onSuccess={onSuccess} />
    </Modal>
  );
}
