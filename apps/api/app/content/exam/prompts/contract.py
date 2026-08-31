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
