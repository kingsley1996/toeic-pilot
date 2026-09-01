"""Prompt là TỆP CÓ PHIÊN BẢN, không phải chuỗi ký tự nằm trong mã.

Ba thứ đến từ việc này và không thứ nào có được nếu prompt là một literal:

- đổi prompt trở thành một diff xem lại được, chứ không phải một dòng lẫn trong
  một commit sửa mười thứ khác
- `ai_interaction.prompt_version` ghi được **bản nào đã tạo ra câu trả lời nào**
  — không có nó thì một câu trả lời tệ trong log không truy được về nguyên nhân
- cổng hồi quy của bộ eval có cái để so: "tỉ lệ đạt tụt kể từ bản nào"

Phiên bản là **hash của chính nội dung**, không phải một số người tự tăng. Số tự
tăng thì có ngày ai đó sửa prompt mà quên tăng, và từ đó hai nội dung khác nhau
mang cùng một nhãn — hỏng đúng thứ mà cột này sinh ra để làm.
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path

__all__ = ["Prompt", "load"]

_DIR = Path(__file__).parent


class Prompt:
    __slots__ = ("name", "text", "version")

    def __init__(self, name: str, text: str) -> None:
        self.name = name
        self.text = text
        self.version = f"{name}@{hashlib.sha256(text.encode()).hexdigest()[:12]}"

    def render(self, **values: object) -> str:
        """Thay chỗ trống bằng `str.format`, và NỔ nếu thiếu một chỗ.

        `format` ném `KeyError` khi thiếu biến — giữ nguyên hành vi đó thay vì
        điền chuỗi rỗng. Một prompt gửi đi với chỗ trống chưa điền vẫn sinh ra
        câu trả lời trôi chảy, nên lỗi này không tự lộ ra ở đầu ra bao giờ.
        """
        return self.text.format(**values)


@cache
def load(name: str, directory: Path = _DIR) -> Prompt:
    """Nạp một prompt. `directory` mặc định là sổ đăng ký RUNTIME ở cạnh tệp này.

    Có tham số thư mục vì có hai sổ đăng ký, và chúng cố ý tách nhau
    (`PROMPT-SYSTEM.md` §0): ở đây là prompt trả lời người học trong một request,
    còn `app/content/exam/prompts/` là prompt của đường sinh đề ngoài luồng. Gộp
    một chỗ thì ranh giới ấy — cái quyết định prompt nào ghi `prompt_version` vào
    `ai_interaction` — thành vô hình.

    Dùng chung lớp `Prompt` thì cả hai được cùng một thứ: phiên bản là hash của
    nội dung, nên không ai sửa prompt mà quên tăng số.
    """
    path = directory / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Không có prompt {name!r} tại {path}")
    return Prompt(name, path.read_text(encoding="utf-8").strip())
