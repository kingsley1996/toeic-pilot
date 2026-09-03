"""Định dạng lời giải thích: một câu dẫn chứng, rồi mỗi lựa chọn một mệnh đề.

    Explanation: <dẫn chứng, KHÔNG gọi tên nhãn> | (A) … | (B) … | (C) … | (D) …

**Vì sao cần định dạng thay vì văn xuôi tự do.** `balance` hoán vị hai lựa chọn
*sau* khi mô hình đã viết xong lời giải thích, nên mọi tham chiếu tới nhãn trong
đó phải đi theo. Với văn xuôi, cách duy nhất là tìm-thay `(A)` bằng regex, và nó
chỉ đúng với đúng một cách viết: "đáp án B", "phương án đầu tiên", hay một `(A)`
nằm trong câu trích tiếng Anh đều lọt qua. Thứ còn lại là lời giải thích sai đúng
MỘT chữ cái — trích dẫn vẫn có thật, bẫy vẫn đúng chỗ, nên không cổng nào thấy;
chỉ người học đọc mới thấy nó đang nói về một phương án khác.

Khoá mệnh đề theo nhãn thì phép cân trở thành đổi chỗ hai *payload*, đúng thao
tác đã làm với chính các lựa chọn. Không còn regex nào chạy trên prose thì không
còn chỗ để sai. Câu dẫn chứng cấm gọi tên nhãn vì nó **không** di chuyển.

Định dạng còn khiến ba kiểu ăn gian đo được thành lỗi *cấu trúc* chứ không phải
lỗi chất lượng: thiếu mệnh đề cho một lựa chọn là đếm hụt, gộp ba câu nhiễu vào
một câu "các phương án khác đều sai" là đếm hụt, và gắn tên bẫy lên đáp án đúng
nằm lộ trong mệnh đề của chính nó. Đếm thì chính xác; đọc prose thì không.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

SEPARATOR = " | "
_CLAUSE_MIN_CHARS = 10
# Tách tại `|` ĐỨNG NGAY TRƯỚC một nhãn, không tại mọi `|`.
#
# Bảng biểu của Part 7 dùng `|` ngăn cột, và lời giải thích trích chúng nguyên
# văn — `biểu đồ cho "Sales | 12", "IT | 8"` bị cắt thành ba đoạn rác nếu tách
# theo mọi dấu. Đổi sang một ký tự khác chỉ dời chỗ va chạm; ràng buộc "dấu phân
# cách luôn đứng trước một nhãn" là tính chất của chính định dạng nên không có
# nội dung nào giả được nó. Khoảng trắng để lỏng vì đó là thứ mô hình gõ.
_SPLIT = re.compile(r"\s*\|\s*(?=\([A-D]\))")
_CLAUSE = re.compile(r"^\(([A-D])\)\s*(.*)$", re.DOTALL)
_LABEL = re.compile(r"\(([A-D])\)")
# Chữ cái TRẦN — `Đáp án B vì …`. Phép cân chỉ đổi dạng có ngoặc, nên dạng này
# đứng yên trong khi đáp án đã dời đi. Đo được 2 ca trên 124 câu của tp-test-09;
# lần đếm đầu tôi báo 0 vì regex đếm thiếu cờ bỏ qua hoa thường.
_BARE_LABEL = re.compile(r"(?:đáp án|phương án|lựa chọn)\s+([A-D])\b", re.IGNORECASE)


@dataclass(frozen=True)
class Explanation:
    """Dẫn chứng cố định, cộng một mệnh đề cho mỗi nhãn, giữ thứ tự A→D."""

    evidence: str
    clauses: dict[str, str]

    def render(self) -> str:
        return SEPARATOR.join([self.evidence, *(f"({k}) {v}" for k, v in self.clauses.items())])

    def swap(self, first: str, second: str) -> Explanation:
        """Đổi chỗ nội dung hai mệnh đề, giữ nguyên vị trí nhãn.

        Nhãn phải ở nguyên chỗ vì giao diện in mệnh đề cạnh lựa chọn cùng nhãn;
        thứ di chuyển là *mô tả*, đi theo đúng nội dung mà nó mô tả.
        """
        if first not in self.clauses or second not in self.clauses:
            return self
        moved = dict(self.clauses)
        moved[first], moved[second] = self.clauses[second], self.clauses[first]
        return replace(self, clauses=moved)


def parse(value: str) -> Explanation | None:
    """Đọc phần sau `Explanation:`. `None` nghĩa là không theo định dạng.

    `None` không phải lỗi ở đây: hàng trăm câu Part 5 đã có lời giải thích viết
    theo lối cũ, và người gọi phải chạy được với cả hai. Chỗ báo là cổng kiểm.
    """
    segments = [part for part in (raw.strip() for raw in _SPLIT.split(value.strip())) if part]
    if len(segments) < 2:
        return None

    clauses: dict[str, str] = {}
    for segment in segments[1:]:
        matched = _CLAUSE.match(segment)
        if matched is None or matched.group(1) in clauses:
            return None
        clauses[matched.group(1)] = matched.group(2).strip()

    if list(clauses) != sorted(clauses):
        return None
    return Explanation(evidence=segments[0], clauses=clauses)


def problems(value: str, labels: Sequence[str]) -> list[str]:
    """Chỗ lời giải thích lệch định dạng. `labels` là nhãn thật của câu hỏi."""
    parsed = parse(value)
    if parsed is None:
        return ["lời giải thích chưa theo định dạng `dẫn chứng | (A) … | (B) …`"]

    found: list[str] = []
    if _LABEL.search(parsed.evidence) or _BARE_LABEL.search(parsed.evidence):
        found.append("câu dẫn chứng gọi tên nhãn — nó không di chuyển khi cân đáp án")
    for label, clause in parsed.clauses.items():
        bare = _BARE_LABEL.search(clause)
        if bare and bare.group(1).upper() != label:
            found.append(f"mệnh đề ({label}) gọi tên ({bare.group(1).upper()}) bằng chữ cái trần")
    # Mệnh đề rỗng hoặc cụt lủn. Nó xuất hiện khi bản gốc gộp nhãn — `(B) và
    # (D) không phải nhóm có phí cao nhất` cắt ra thành `(B) và.` — và không
    # phép đếm nào thấy, vì đủ bốn nhãn và nhãn nào cũng có chữ.
    thin = sorted(
        label
        for label, clause in parsed.clauses.items()
        if len(clause.strip(" .\"'")) < _CLAUSE_MIN_CHARS
    )
    if thin:
        found.append(f"mệnh đề ({'/'.join(thin)}) rỗng hoặc quá ngắn để nói được điều gì")
    missing = sorted(set(labels) - set(parsed.clauses))
    extra = sorted(set(parsed.clauses) - set(labels))
    if missing:
        found.append(f"thiếu mệnh đề cho ({'/'.join(missing)})")
    if extra:
        found.append(f"có mệnh đề cho nhãn không tồn tại ({'/'.join(extra)})")
    return found
