"use client";

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
  description = "Đề thi thử miễn phí, nhưng cần tài khoản để lưu bài làm và điểm số.",
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
  next: string;
  title?: string;
  description?: string;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title} description={description}>
      <LoginForm next={next} onSuccess={onSuccess} />
    </Modal>
  );
}
