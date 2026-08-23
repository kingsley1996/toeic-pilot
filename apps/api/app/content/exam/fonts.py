"""Tìm một font có thật trên máy để vẽ hình ngữ liệu.

`ImageFont.load_default()` cho ra chữ bitmap cỡ 10px không phóng to được, và một
bảng giá vẽ bằng nó thì không đọc nổi — tức là hỏng đúng thứ tấm hình tồn tại để
làm. Nên phải đi tìm một font thật, và **không có thì báo lỗi** thay vì vẽ ra
một tấm hình vô dụng rồi để người ta phát hiện lúc nhìn.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

# Ứng viên theo thứ tự ưu tiên, macOS trước rồi Linux — cùng thứ tự với chỗ
# pipeline thật sự chạy (máy soạn nội dung, rồi image worker).
_CANDIDATES = (
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
    ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Helvetica.ttc"),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
)


@lru_cache(maxsize=8)
def load_font(size: int, bold: bool = False) -> Any:
    from PIL import ImageFont

    for regular, heavy in _CANDIDATES:
        path = Path(heavy if bold else regular)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError(
        "Không tìm thấy font TrueType nào để vẽ hình ngữ liệu. "
        f"Đã thử: {', '.join(regular for regular, _ in _CANDIDATES)}"
    )
