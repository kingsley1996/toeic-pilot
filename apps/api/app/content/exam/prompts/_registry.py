"""Sổ đăng ký prompt của đường SINH ĐỀ — tách khỏi sổ runtime, cố ý.

Hai sổ, cùng một lớp `Prompt`, hai thư mục (`PROMPT-SYSTEM.md` §0). Sổ runtime ở
`app/services/llm/prompts/` phục vụ người học trong một request; sổ này chạy
ngoài luồng trên máy soạn nội dung. Gộp một chỗ thì ranh giới quyết định prompt
nào ghi `prompt_version` vào `ai_interaction` trở thành vô hình.

Dùng chung lớp `Prompt` thì cả hai được cùng một thứ: **phiên bản là hash của
chính nội dung**, nên không có đường nào sửa prompt mà quên tăng số.

Đặt ở tệp riêng chứ không ở `__init__` vì `__init__` import các `partN`, còn các
`partN` cần hàm này — để chung là vòng import.
"""

from __future__ import annotations

from pathlib import Path

from app.services.llm.prompts import Prompt, load

_DIR = Path(__file__).parent


def exam_prompt(name: str) -> Prompt:
    """Prompt sinh đề tên `name`, đọc từ `<name>.md` cạnh tệp này."""
    return load(name, _DIR)
