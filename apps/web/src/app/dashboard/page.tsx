import { redirect } from "next/navigation";

/**
 * `/dashboard` đã gộp vào `/learn`.
 *
 * Route được GIỮ LẠI chứ không xoá: đây là nơi đăng nhập đẩy tới suốt thời gian
 * qua, nên nó nằm trong lịch sử trình duyệt và trong bookmark của người đang
 * dùng. Xoá thẳng thì họ nhận một trang 404 cho một địa chỉ vẫn đúng ngày hôm
 * trước.
 *
 * Chuyển hướng ở SERVER chứ không phải bằng `useEffect` + `router.replace`:
 * cách kia phải dựng xong một trang rỗng, chạy JS, rồi mới chuyển — người dùng
 * nhìn thấy một nhịp trắng ở giữa.
 */
export default function DashboardRedirect() {
  redirect("/learn");
}
