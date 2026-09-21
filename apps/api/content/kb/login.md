---
ref: login
title: Đăng nhập và tài khoản
keywords: đăng nhập, login, đăng ký, register, google, apple, mật khẩu, tài khoản, đăng xuất, quên mật khẩu
source: content/kb/login.md
doc_type: guide
topic: account
language: vi
content_version: 2
---

Tạo tài khoản tại `/register` bằng email + mật khẩu, hoặc bấm nút Google / Apple tại `/login` để đăng nhập qua nhà cung cấp (tài khoản kiểu này không có mật khẩu riêng của trang; muốn đặt mật khẩu thì vào hồ sơ làm lần đầu). Mỗi lần gửi form đăng nhập/đăng ký có một bước kiểm chống bot chạy ngầm, nên chậm hơn bình thường khoảng nửa giây là cố ý.

Đổi mật khẩu (tài khoản email) sẽ làm TẤT CẢ phiên đăng nhập khác hết hiệu lực — chỉ giữ lại phiên bạn đang dùng. Đăng xuất thu hồi token của phiên đó; dùng máy tính dùng chung thì nhớ đăng xuất.

Mật khẩu tối đa 72 byte (chữ tiếng Việt có dấu tính theo byte nên đừng đặt quá dài). Quên mật khẩu hiện chưa có đường tự phục vụ — liên hệ người vận hành để được đặt lại.
