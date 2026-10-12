"""Sanitize + trích xuất từ HTML/JSON của bài blog.

`body_html` ra trang public đọc không cần đăng nhập, nên dù người viết là
staff thì HTML vẫn qua allowlist `nh3` trước khi cất. Cái gì editor không sinh
(thẻ H1, script, style, iframe, form) thì rớt ở đây, không cần tin client.
"""

import re
from typing import Any

import nh3

ALLOWED_TAGS = {
    "p",
    "h2",
    "h3",
    "h4",
    "strong",
    "em",
    "u",
    "s",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "hr",
    "br",
    "figure",
    "figcaption",
}

ALLOWED_ATTRIBUTES = {
    # `rel` do `link_rel` dưới đây quản — nh3 từ chối đưa nó vào allowlist.
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
}


def sanitize_body_html(html: str) -> str:
    """Lọc HTML qua allowlist. Link ngoài luôn có `rel` chống tabnabbing."""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer",
    )


def _walk_text(node: object, out: list[str]) -> None:
    if isinstance(node, dict):
        text = node.get("text")
        if isinstance(text, str):
            out.append(text)
        content = node.get("content")
        if isinstance(content, list):
            for child in content:
                _walk_text(child, out)
    elif isinstance(node, list):
        for child in node:
            _walk_text(child, out)


def doc_text(doc: dict[str, Any]) -> str:
    """Toàn bộ chữ trong tài liệu Tiptap (đếm độ dài, tính phút đọc)."""
    out: list[str] = []
    _walk_text(doc.get("content", []), out)
    return "".join(out)


def is_tiptap_doc(doc: object) -> bool:
    return (
        isinstance(doc, dict) and doc.get("type") == "doc" and isinstance(doc.get("content"), list)
    )


def toc_from_doc(doc: dict[str, Any]) -> list[dict[str, str | int]]:
    """Mục lục từ H2/H3. Không lưu cột riêng — rút lúc đọc, chục dòng."""
    toc: list[dict[str, str | int]] = []
    for node in doc.get("content", []):
        if not isinstance(node, dict) or node.get("type") != "heading":
            continue
        level = node.get("attrs", {}).get("level", 2)
        if level not in (2, 3):
            continue
        parts: list[str] = []
        _walk_text(node.get("content", []), parts)
        text = "".join(parts).strip()
        if not text:
            continue
        anchor = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or f"h{len(toc)}"
        toc.append({"level": level, "text": text, "id": anchor})
    return toc


def reading_minutes(text: str) -> int:
    return max(1, -(-len(text.split()) // 200))
