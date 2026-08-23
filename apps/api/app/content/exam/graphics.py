"""Hình đi kèm của Part 3 và 4: VẼ RA TỪ DỮ LIỆU, không sinh bằng mô hình ảnh.

**Vì sao khác hẳn ảnh Part 1.** Ảnh Part 1 là ảnh chụp và luật đầu tiên của nó
là *không có chữ nào trong ảnh*. Hình Part 3/4 ngược hoàn toàn: nó là một tài
liệu và **toàn bộ giá trị nằm ở chữ đọc được**. Mô hình khuếch tán vẽ chữ không
đáng tin, nên đường của Part 1 không dùng lại được ở đây.

Vẽ từ dữ liệu mua về ba thứ, và thứ ba là thứ bắt buộc:

1. **Chữ luôn đọc được**, vì nó được đặt chứ không được đoán.
2. **Vẽ lại cho ra đúng tấm cũ**, nên sửa một ô rồi vẽ lại là thao tác rẻ.
3. **Chữ thay ảnh sinh ra từ CÙNG dữ liệu.** `assign_passage_image` trả 409 cho
   hình ngữ liệu không có `alt_text`, và nó đúng: hình đó *là* nội dung người
   học phải đọc. Hình do mô hình vẽ thì phải có người nhìn rồi mô tả lại bằng
   tay — và mô tả tay trôi khỏi hình ngay lần sửa đầu tiên.

## Bốn dạng, vì đề thật có bốn dạng

Đếm trên đề mẫu chính thức của ETS: câu 64 là **bảng** giá, câu 67 là **lưới
lịch** có ô trống, câu 70 là **sơ đồ** bốn cửa hàng, câu 96 là bảng danh sách,
câu 99 là hình có **đánh dấu bộ phận**. Nói cách khác bảng chỉ chiếm hai trên
năm — làm mỗi bảng là bỏ mất phần lớn dạng câu người học sẽ gặp.

Điều thật sự phân biệt bốn dạng không phải cách vẽ, mà là **trục đáp án**: bốn
lựa chọn của câu "Look at the graphic" lấy từ đâu.

| dạng | trục đáp án | ví dụ trên đề mẫu |
|---|---|---|
| `table` | tên HÀNG | câu 64: bốn loại sổ |
| `schedule` | tiêu đề CỘT | câu 67: bốn khung giờ |
| `chart` | nhãn CỘT BIỂU ĐỒ | biểu đồ doanh số theo quý |
| `map` | nhãn Ô trên sơ đồ | câu 70: bốn cửa hàng |

`schedule` khác `table` ở một chỗ dễ bỏ qua và là toàn bộ điểm của nó: **ô được
phép TRỐNG**. Câu hỏi "hai người sẽ họp lúc mấy giờ" trả lời được chính nhờ tìm
cột mà cả hai hàng đều trống. Một renderer đòi mọi hàng đủ cột sẽ từ chối đúng
dạng câu đó.

Dạng thứ năm — hình có đánh dấu bộ phận (câu 99) — **chưa làm**: nó cần một tấm
ảnh thật rồi phủ dấu A–D lên, tức là ghép đường Part 1 với đường này. Ghi ra đây
thay vì lặng lẽ bỏ qua.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

WIDTH = 760
PADDING = 28
ROW_HEIGHT = 46
HEADER_HEIGHT = 52
TITLE_HEIGHT = 54

INK = (17, 17, 17)
RULE = (140, 140, 140)
HEADER_BG = (232, 232, 232)
CELL_BG = (246, 246, 246)
BAR = (72, 72, 72)
PAPER = (255, 255, 255)

KINDS = ("table", "schedule", "chart", "map")


@dataclass
class Graphic:
    """Một hình ngữ liệu, ở dạng dữ liệu chứ không dạng ảnh."""

    kind: str
    title: str
    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def problems(self) -> list[str]:
        out: list[str] = []
        if self.kind not in KINDS:
            out.append(f"dạng hình phải là một trong {KINDS}, đang là {self.kind!r}")
            return out
        if not self.title.strip():
            out.append("hình thiếu dòng tiêu đề — dòng ngay sau `kind:` là tên của hình")
        if not self.rows:
            out.append("hình không có hàng nào")
            return out

        if self.kind == "chart":
            # Biểu đồ là (nhãn, số). Không đọc được số thì không vẽ được cột, và
            # một cột cao bằng 0 trông như dữ liệu thật.
            for index, row in enumerate(self.rows):
                if len(row) != 2 or _number(row[1]) is None:
                    out.append(f"hàng {index + 1} của biểu đồ phải là `nhãn | số`")
        elif self.kind == "map":
            if not all(row for row in self.rows):
                out.append("sơ đồ có hàng rỗng")
        else:
            if len(self.columns) < 2:
                out.append("hình cần ít nhất hai cột")
            # `schedule` CHO PHÉP ô trống — đó là toàn bộ điểm của nó — nhưng
            # không cho phép hàng NGẮN hơn, vì lúc đó không biết ô nào trống.
            wrong = [i for i, row in enumerate(self.rows) if len(row) != len(self.columns)]
            if wrong:
                out.append(f"hàng {', '.join(str(i + 1) for i in wrong)} lệch số cột")

        # Lưới lịch đếm theo NGƯỜI, không theo lựa chọn: đề mẫu có đúng hai
        # người (Zahra và Sammy) và bốn khung giờ. Áp luật 3–6 hàng của bảng
        # vào đó là từ chối đúng hình dạng của đề thật.
        limits = {"schedule": (2, 4), "table": (3, 6), "chart": (3, 6)}
        if self.kind in limits:
            low, high = limits[self.kind]
            if not low <= len(self.rows) <= high:
                out.append(f"hình dạng {self.kind} cần {low}–{high} hàng, đang có {len(self.rows)}")
        if len(self.answer_axis()) != 4:
            out.append(
                f"trục đáp án của dạng {self.kind} phải có đúng 4 mục, "
                f"đang có {len(self.answer_axis())}"
            )
        return out

    def answer_axis(self) -> list[str]:
        """Bốn thứ mà bốn lựa chọn của câu hỏi về hình phải lấy từ đó.

        Đây là chỗ bốn dạng thật sự khác nhau. Lấy sai trục thì câu hỏi vẫn hợp
        lệ về mọi mặt và vẫn có đúng một đáp án — nó chỉ không còn hỏi về tấm
        hình nữa.
        """
        if self.kind == "schedule":
            # Cột đầu là tên người/hàng, không phải một lựa chọn.
            return self.columns[1:]
        if self.kind == "map":
            return [cell.split(":")[0].strip() for row in self.rows for cell in row]
        return [row[0] for row in self.rows if row]

    def alt_text(self) -> str:
        """Chữ thay ảnh, sinh từ chính dữ liệu vừa vẽ.

        Đọc thành câu chứ không thành CSV: người dùng máy đọc màn hình nghe tuần
        tự, và một chuỗi dấu phẩy không nói được ô nào thuộc cột nào. Với sơ đồ
        thì phải nói cả VỊ TRÍ, vì quan hệ trái/phải chính là thứ câu hỏi dùng.
        """
        lines = [f"{self.title}."]
        if self.kind == "chart":
            lines.append("Biểu đồ cột.")
            lines += [f"{row[0]}: {row[1]}." for row in self.rows]
        elif self.kind == "map":
            lines.append(f"Sơ đồ {len(self.rows)} hàng.")
            for index, row in enumerate(self.rows, start=1):
                places = ", ".join(
                    f"{position} từ trái là {cell}"
                    for position, cell in zip(("thứ nhất", "thứ hai", "thứ ba", "thứ tư"), row)
                )
                lines.append(f"Hàng {index}: {places}.")
        else:
            for row in self.rows:
                pairs = ", ".join(
                    f"{column}: {value or 'trống'}"
                    for column, value in zip(self.columns, row, strict=False)
                )
                lines.append(f"{pairs}.")
        return " ".join(lines)


_SPLIT = re.compile(r"\t+|\s*\|\s*")
_KIND_LINE = re.compile(r"^kind\s*:\s*(\w+)\s*$", re.IGNORECASE)


def _number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:[.,]\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else None


def parse_graphic(text: str) -> Graphic:
    """Đọc khối `[GRAPHIC]` mà mô hình viết ra.

    Dòng `kind:` chọn dạng; dòng kế là tiêu đề; rồi tiêu đề cột (trừ `chart` và
    `map`, vốn không có); còn lại là các hàng. Ô ngăn nhau bằng `|` hoặc tab.

    **Không bỏ ô rỗng.** Bản đầu lọc `if cell.strip()` và thế là mọi lưới lịch
    mất sạch ô trống — đúng thứ làm nên câu hỏi "họ họp lúc mấy giờ".
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    kind = "table"
    if lines:
        matched = _KIND_LINE.match(lines[0])
        if matched:
            kind = matched.group(1).lower()
            lines = lines[1:]
    if not lines:
        return Graphic(kind=kind, title="")

    title = lines[0].lstrip("#").strip()
    # Tiêu đề KHÔNG được là một hàng dữ liệu. Mô hình quên dòng tiêu đề khá
    # thường, và khi đó hàng tiêu đề cột bị đọc thành tiêu đề — cả bảng trôi lên
    # một dòng và triệu chứng lộ ra ở tận chỗ khác ("cần 2–4 hàng, đang có 1"),
    # tức là lời từ chối chỉ vào hậu quả chứ không vào nguyên nhân.
    if "|" in title or "\t" in title:
        return Graphic(kind=kind, title="")
    # Bỏ đúng dấu `|` MỞ ĐẦU (kiểu markdown), giữ nguyên dấu cuối.
    #
    # `strip("|")` ăn mất dấu cuối, và cùng với nó là ô TRỐNG cuối hàng — nên
    # `Zahra | Busy | | Team meeting |` đọc ra bốn ô thay vì năm, và mọi lưới
    # lịch đều báo "lệch số cột". Ô trống cuối hàng chính là khung giờ người đó
    # rảnh, tức là thứ câu hỏi đang tìm.
    cells = [[cell.strip() for cell in _SPLIT.split(line.removeprefix("|"))] for line in lines[1:]]
    cells = [row for row in cells if not all(set(cell) <= set("-:") and cell for cell in row)]
    if not cells:
        return Graphic(kind=kind, title=title)
    if kind in ("chart", "map"):
        return Graphic(kind=kind, title=title, rows=cells)
    return Graphic(kind=kind, title=title, columns=cells[0], rows=cells[1:])


# Cỡ chữ nhỏ nhất còn đọc được ở kích thước hiển thị của đề. Dưới mức này thì
# thu nhỏ không còn cứu được gì, và chữ bị cắt đúng hơn là chữ không đọc nổi.
MIN_FONT = 13


def _fit(draw, text: str, room: int, size: int, bold: bool):  # type: ignore[no-untyped-def]
    """Chữ và font vừa đúng bề ngang `room`.

    Bảng lịch có năm cột, và một ô như "Budget meeting" tràn ra ngoài mép giấy ở
    cỡ chữ mặc định — tấm hình vẫn "vẽ xong", chỉ là mất chữ. PIL không có vùng
    cắt, nên phải tự đo: thu cỡ chữ dần, và chỉ khi chạm sàn mới cắt bớt chữ.
    """
    from app.content.exam.fonts import load_font

    for candidate in range(size, MIN_FONT - 1, -1):
        font = load_font(candidate, bold=bold)
        if draw.textlength(text, font=font) <= room:
            return text, font
    font = load_font(MIN_FONT, bold=bold)
    trimmed = text
    while trimmed and draw.textlength(trimmed + "…", font=font) > room:
        trimmed = trimmed[:-1]
    return (trimmed + "…") if trimmed != text else text, font


def render(graphic: Graphic, path: Path) -> None:
    """Vẽ ra PNG đen trắng, cùng tông với ảnh Part 1."""
    from PIL import Image, ImageDraw

    from app.content.exam.fonts import load_font

    body = load_font(20)
    title_font = load_font(24, bold=True)

    # Khổ giấy theo SỐ CỘT. Năm cột trên khổ 760 chỉ còn ~120px mỗi ô, hẹp hơn
    # phần lớn nhãn thật; nới khổ rẻ hơn nhiều so với thu chữ xuống mức khó đọc.
    width = WIDTH if len(graphic.columns) <= 4 else WIDTH + 180

    if graphic.kind == "chart":
        height = TITLE_HEIGHT + ROW_HEIGHT * len(graphic.rows) + PADDING * 2 + 10
    elif graphic.kind == "map":
        height = TITLE_HEIGHT + 96 * len(graphic.rows) + PADDING * 2
    else:
        height = TITLE_HEIGHT + HEADER_HEIGHT + ROW_HEIGHT * len(graphic.rows) + PADDING * 2

    canvas = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.text((PADDING, PADDING), graphic.title, font=title_font, fill=INK)
    top = PADDING + TITLE_HEIGHT

    if graphic.kind == "chart":
        values = [(_number(row[1]) or 0.0) for row in graphic.rows]
        widest = max(values) or 1.0
        label_width = 190
        track = width - PADDING * 2 - label_width - 90
        y = top
        for row, size in zip(graphic.rows, values, strict=True):
            draw.text((PADDING, y + 12), row[0], font=body, fill=INK)
            length = int(track * size / widest)
            draw.rectangle(
                [PADDING + label_width, y + 10, PADDING + label_width + length, y + 34], fill=BAR
            )
            draw.text((PADDING + label_width + length + 10, y + 12), row[1], font=body, fill=INK)
            y += ROW_HEIGHT
        draw.line([PADDING + label_width, top, PADDING + label_width, y], fill=RULE, width=2)
    elif graphic.kind == "map":
        y = top
        for row in graphic.rows:
            columns = max(1, len(row))
            box = (WIDTH - PADDING * 2 - 12 * (columns - 1)) // columns
            for index, cell in enumerate(row):
                x = PADDING + index * (box + 12)
                draw.rectangle([x, y, x + box, y + 76], fill=CELL_BG, outline=RULE, width=2)
                text, font = _fit(draw, cell, box - 28, 20, True)
                draw.text((x + 14, y + 28), text, font=font, fill=INK)
            y += 96
    else:
        columns = max(1, len(graphic.columns))
        usable = width - PADDING * 2
        # Cột đầu rộng gấp rưỡi: nó giữ tên của hàng, phần dài nhất của bảng.
        weights = [1.5] + [1.0] * (columns - 1)
        total = sum(weights)
        edges = [PADDING]
        for weight in weights:
            edges.append(edges[-1] + int(usable * weight / total))

        draw.rectangle([PADDING, top, edges[-1], top + HEADER_HEIGHT], fill=HEADER_BG)
        for index, column in enumerate(graphic.columns):
            room = edges[index + 1] - edges[index] - 24
            text, font = _fit(draw, column, room, 20, True)
            draw.text((edges[index] + 12, top + 15), text, font=font, fill=INK)

        y = top + HEADER_HEIGHT
        for row in graphic.rows:
            for index, value in enumerate(row[:columns]):
                if value:
                    room = edges[index + 1] - edges[index] - 24
                    text, font = _fit(draw, value, room, 20, False)
                    draw.text((edges[index] + 12, y + 13), text, font=font, fill=INK)
            y += ROW_HEIGHT
            draw.line([PADDING, y, edges[-1], y], fill=RULE, width=1)

        draw.rectangle([PADDING, top, edges[-1], y], outline=RULE, width=2)
        draw.line(
            [PADDING, top + HEADER_HEIGHT, edges[-1], top + HEADER_HEIGHT], fill=RULE, width=2
        )
        for edge in edges[1:-1]:
            draw.line([edge, top, edge, y], fill=RULE, width=1)

    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
