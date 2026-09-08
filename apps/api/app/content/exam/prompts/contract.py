"""Hợp đồng định dạng: các MỐC mà prompt hứa xuất ra và parser tin là có.

Nằm ở đây chứ không ở `writer` vì nó là điều khoản của hợp đồng — cả bên hứa
lẫn bên tin đều nhập từ một chỗ."""

from __future__ import annotations

from app.services.content_import import SCRIPT_MARKER as CONTENT_SCRIPT_MARKER
from app.services.content_import import SET_MARKER as CONTENT_SET_MARKER

PHOTO_MARKER = "[PHOTO]"
# Mốc lời thoại dùng chung của Part 3/4. Cùng chuỗi mà `content_import` nhận,
# nhập từ đó chứ không viết lại: hai hằng số cho một giao thức là hai thứ trôi
# khỏi nhau, và cái trôi chỉ lộ ra ở chặng nạp.
SCRIPT_MARKER = CONTENT_SCRIPT_MARKER
GRAPHIC_MARKER = "[GRAPHIC]"
PASSAGE_MARKER = CONTENT_SET_MARKER

BLANK = "-------"

# Nửa còn lại của hợp đồng: các MỐC ở trên nói khối bắt đầu ở đâu, dòng này nói
# khối kết thúc bằng gì. Ở prompt của TỪNG Ô chứ không chỉ trong ví dụ cuối
# system prompt — đo được: `mimo-v2.5` viết trọn ba câu Part 7 mà không có dòng
# `Source:` nào, `gpt-oss-120b` cũng vậy ở Part 3. Cả hai system prompt đều có
# dòng ấy, nhưng chỉ nằm trong ví dụ ở cuối một prompt dài trăm dòng.
BLOCK_TAIL = (
    "\n- MỖI khối [QUESTION] kết thúc bằng ba dòng RIÊNG của nó, đúng thứ tự này:"
    "\n    Answer: <chữ cái>"
    "\n    Explanation: <bằng chứng> | (A) … | (B) … | (C) … | (D) …"
    "\n    Source: original"
    "\n  Một khối thiếu `Source: original` bị TỪ CHỐI ở chặng nạp, dù nội dung đúng"
    " hết. Viết một dòng cho cả ô là thiếu — mỗi khối một dòng."
)
