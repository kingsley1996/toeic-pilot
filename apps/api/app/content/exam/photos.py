"""Chặng ảnh của Part 1: biến phần mô tả thành một prompt vẽ được.

**Chiều phụ thuộc ở đây ngược với ADR-004**, và đó là cả ý tưởng (kế hoạch §8).
Với ảnh đi mượn ta phải TÌM một tấm mà bốn câu mô tả viết được về nó, nên cần
người quyết định. Với ảnh sinh, bốn câu được viết trước và tấm ảnh được vẽ để
khớp với chúng — cái khó biến mất, nhưng đổi lại tấm ảnh phải đúng tới từng chi
tiết mà bốn câu đó dựa vào.

Vì thế phần mô tả do người viết đề sinh ra chứa rất nhiều câu PHỦ ĐỊNH: "No
telephone is visible", "No other people are visible". Chúng cần thiết cho chặng
kiểm — đó là thứ làm ba câu nhiễu sai một cách kiểm chứng được — nhưng là chất
độc cho một prompt vẽ: mô hình khuếch tán không có phủ định, nên "no telephone"
đọc ra gần như "telephone". Tách chúng ra và đẩy sang `Avoid:` là việc duy nhất
module này làm, và nó là việc phải làm.
"""

from __future__ import annotations

import re
from pathlib import Path

# Câu khẳng định sự VẮNG MẶT. Bắt theo khuôn câu chứ không theo từ khoá "no",
# vì "no" cũng xuất hiện giữa câu khẳng định ("a sign with no text on it").
_ABSENCE = re.compile(
    r"^\s*(no|none of|there (is|are) no|neither)\b|\bare not visible\b|\bis not visible\b",
    re.IGNORECASE,
)

# Hướng ảnh, không phải nội dung ảnh. Tách riêng để khi đổi phong cách toàn bộ
# Part 1 thì sửa một chỗ, chứ không sửa sáu tệp mô tả.
STYLE = (
    "A realistic black and white photograph, monochrome, documentary style, "
    "eye-level camera, natural indoor lighting, strong tonal separation between "
    "subject and background, sharp focus, full scene visible, "
    "ordinary workplace setting."
)

# Những thứ luôn phải tránh ở ảnh Part 1, bất kể cảnh là gì. Chữ và logo đứng
# đầu danh sách vì đề thi thật không bao giờ có chúng — và một tấm ảnh có chữ
# biến câu hỏi nghe thành câu hỏi đọc.
ALWAYS_AVOID = (
    "colour, saturated colours, sepia, colour tint, "
    "text, letters, words, signage, logos, brand names, watermark, "
    "illustration, cartoon, 3d render, collage, split screen, "
    "distorted hands, extra limbs, extra people"
)


def split_sentences(description: str) -> list[str]:
    """Cắt tới mức MỆNH ĐỀ, không chỉ tới câu.

    Câu phủ định thường nấp trong nửa sau của một câu ghép — "Both are standing;
    no chair or desk is visible" — nên cắt theo dấu chấm thôi là cả câu đó bị xếp
    vào vế khẳng định, và cái ghế bị cấm lại được vẽ ra.
    """
    text = " ".join(description.split())
    parts: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for clause in re.split(r";\s*|,\s+and\s+", sentence):
            cleaned = clause.strip(" ,")
            if cleaned:
                parts.append(cleaned)
    return parts


def photo_prompt(description: str) -> tuple[str, str]:
    """(prompt vẽ, chuỗi `Avoid`). Câu phủ định chuyển hết sang vế thứ hai."""
    present: list[str] = []
    absent: list[str] = []
    for sentence in split_sentences(description):
        (absent if _ABSENCE.search(sentence) else present).append(sentence)

    # Bỏ chữ phủ định ở vế `Avoid`: chỗ đó liệt kê thứ KHÔNG được xuất hiện, nên
    # để nguyên "No telephone is visible" là phủ định hai lần.
    stripped = [
        re.sub(
            r"^\s*(there\s+(is|are)\s+)?(no|none\s+of)\s+",
            "",
            re.sub(r"\s*(is|are)\s+(not\s+)?visible\b", "", part, flags=re.IGNORECASE),
            flags=re.IGNORECASE,
        ).strip(" .,")
        for part in absent
    ]
    # Một mệnh đề phủ định có thể liệt kê nhiều thứ, mỗi thứ mang chữ "no" của
    # riêng nó ("no whiteboard, no graph, no door"). Bóc từng mục một, nếu không
    # thì `Avoid:` chứa chính chữ phủ định mà nó tồn tại để thay thế.
    items = [
        re.sub(r"^\s*(no|and\s+no)\s+", "", item, flags=re.IGNORECASE).strip(" .,")
        for part in stripped
        for item in part.split(",")
    ]
    avoid = ", ".join(item for item in items if item)
    # Nối lại bằng ", " chứ không bằng khoảng trắng: cắt tới mệnh đề đã bỏ mất
    # dấu phẩy, và dán liền hai mệnh đề tạo ra những câu đọc không ra ("the
    # printer the woman is on the right side").
    body = ", ".join(present).replace("., ", ". ")
    return f"{STYLE} {body}", ", ".join(filter(None, (avoid, ALWAYS_AVOID)))


def to_greyscale(path: Path) -> None:
    """Chuyển tấm ảnh về đen trắng, ghi đè tại chỗ.

    Đề TOEIC thật in đen trắng, nên một tấm ảnh màu đặt người học vào một bài
    khác với bài họ sẽ gặp — màu là một manh mối mà phòng thi không cho ("chiếc
    áo vàng", "cái hộp đỏ").

    Làm CẢ HAI: prompt xin ảnh đơn sắc, và bước này ép về đơn sắc. Chỉ xin thì
    mô hình vẫn trả ảnh màu ở một số lượt, và cái sai đó chỉ lộ ra khi có người
    nhìn — đúng loại lỗi mà một phép biến đổi tất định xoá sạch. Chỉ ép mà không
    xin thì mô hình bố cục theo màu, và bản khử màu của một cảnh hợp lý về màu
    có thể mất hết tương phản giữa chủ thể và nền.

    Ghi lại thành RGB chứ không giữ chế độ "L": một ảnh một kênh vẫn đúng về mặt
    hiển thị, nhưng mọi thứ phía sau (probe kích thước, Cloudinary, trình duyệt)
    đều làm việc với ảnh ba kênh, và một định dạng khác thường ở giữa đường ống
    là chỗ hỏng lặng lẽ ở đúng một khâu nào đó.
    """
    from PIL import Image, ImageOps

    with Image.open(path) as opened:
        grey = ImageOps.grayscale(opened.convert("RGB")).convert("RGB")
        grey.save(path)
