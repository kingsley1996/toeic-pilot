import { redirect } from "next/navigation";

/**
 * `/learn` đã chuyển sang `/dashboard`.
 *
 * Route được GIỮ LẠI chứ không xoá: đây là nơi đăng nhập đẩy tới suốt nhiều
 * sprint, nên nó nằm trong lịch sử trình duyệt và trong bookmark của người đang
 * dùng. Xoá thẳng thì họ nhận một trang 404 cho một địa chỉ vẫn đúng ngày hôm
 * trước. Đúng cái lý do `/dashboard` từng được giữ lại khi hướng chuyển ngược
 * lại — chỉ là lần này mũi tên quay đầu.
 *
 * Chỉ mỗi `/learn` chuyển hướng; các trang con (`/learn/vocabulary`,
 * `/learn/dictation`, `/learn/tests`, `/learn/review`, `/learn/typing`,
 * `/learn/attempts`) giữ nguyên đường dẫn. `/learn` là một bảng điều khiển nên
 * tên `dashboard` mô tả đúng nó; các trang con thật sự là nơi học, nên
 * `/learn/...` mới là tên đúng của chúng.
 *
 * Chuyển hướng ở SERVER chứ không phải bằng `useEffect` + `router.replace`:
 * cách kia phải dựng xong một trang rỗng, chạy JS, rồi mới chuyển — người dùng
 * nhìn thấy một nhịp trắng ở giữa.
 */
export default function LearnRedirect() {
  redirect("/dashboard");
}
