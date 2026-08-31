"""Các lệnh của `generate_exam`, tách theo nhóm việc.

`generate_exam.py` từng là một tệp 988 dòng gom mười ba lệnh con. Phần lõi vốn
đã nằm ở `app/content/exam/*` (blueprint, writer, check, balance, loader), nên
tệp kia chỉ còn là lớp CLI — nhưng một lớp CLI dài gần nghìn dòng thì việc tìm
một lệnh đã là một lượt đọc.

Chia theo VIỆC người dùng đang làm, không theo tầng kỹ thuật:

- `paths`     — thư mục làm việc và gateway; mọi nhóm đều cần
- `plan`      — dựng blueprint, sinh bối cảnh và bảng dữ liệu
- `authoring` — viết, kiểm, cắt bỏ, cân vị trí đáp án
- `media`     — ảnh Part 1, hình ngữ liệu Part 3/4, tải lên và gắn vào đề
- `load`      — nạp vào database qua API admin, và wizard

`generate_exam.py` giữ nguyên vai trò cửa trước: argparse và `main()`. Đường
gọi tài liệu ghi (`uv run python -m app.content.generate_exam <lệnh>`) không
đổi.
"""
