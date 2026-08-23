"""Cân lại vị trí đáp án trên toàn ĐỀ.

**Vì sao cần.** Mô hình có thiên lệch vị trí rất mạnh và không tự biết: một lượt
chạy thật với `nemotron-3-ultra-550b` cho **29 trên 30 câu có đáp án là (A)** —
người chọn bừa A được 97%. Không phép kiểm từng câu nào bắt được chuyện đó, vì
mỗi câu riêng lẻ hoàn toàn hợp lệ; nó là tính chất của cả đề.

**Vì sao sửa được mà không phải sinh lại.** Hoán vị bốn lựa chọn là phép biến đổi
ĐỊNH DẠNG: cùng bốn phương án, cùng một phương án đúng, chỉ khác thứ tự in ra.
Nó không giấu đi lỗi nào — khác hẳn với việc tự đổi một đáp án sai thành đúng,
thứ sẽ che mất đúng tín hiệu mà cổng kiểm sinh ra để bắt.

**Vì sao gán đích thay vì xáo ngẫu nhiên.** Xáo ngẫu nhiên 30 câu vẫn có thể ra
một đề lệch; gán vòng tròn A→B→C→D thì phân bố đúng bằng nhau theo định nghĩa.
Nó cũng khiến bước này **chạy lại được**: "đưa đáp án đúng về chữ X" là một đích
cố định, nên chạy lần thứ hai không xê dịch gì.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.content.exam.blueprint import LISTENING_QUESTIONS_PER_SET, Blueprint
from app.content.exam.writer import paste_path

LETTERS = "ABCD"
_OPTION = re.compile(r"^\(([A-D])\)\s*(.*)$")
# `MULTILINE` là bắt buộc: `balance` quét cả khối chứ không từng dòng, và không
# có cờ này thì `^` chỉ khớp đầu chuỗi — phép đếm trả về 0 cho mọi thứ trong khi
# việc hoán vị vẫn chạy đúng. Một con số 0 im lặng cạnh một thao tác thành công.
_ANSWER = re.compile(r"^Answer:\s*([A-D])\s*$", re.IGNORECASE | re.MULTILINE)


def split_questions(block: str) -> list[tuple[int, int]]:
    """Khoảng dòng của từng khối `[QUESTION]`. Part 3/4 có ba khối trong một tệp.

    Cân theo cả tệp là sai ở đó: `rewrite` quét toàn khối, gặp bốn lựa chọn của
    câu đầu và dòng `Answer:` của câu cuối, rồi đổi chỗ hai thứ thuộc hai câu
    khác nhau — một phép hoán vị vẫn "thành công" và làm hỏng hai câu cùng lúc.
    """
    lines = block.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == "[QUESTION]"]
    if not starts:
        return []
    bounds = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        bounds.append((start, end))
    return bounds


def rewrite_all(block: str, targets: list[str]) -> str:
    """Cân từng khối câu hỏi trong một tệp, mỗi khối một chữ cái đích."""
    lines = block.splitlines()
    bounds = split_questions(block)
    if not bounds:
        return block
    out = lines[: bounds[0][0]]
    for (start, end), target in zip(bounds, targets, strict=False):
        out.extend(rewrite("\n".join(lines[start:end]), target).splitlines())
    return "\n".join(out)


def rewrite(block: str, target: str) -> str:
    """Đưa đáp án đúng về chữ `target`, giữ nguyên mọi thứ khác.

    Hoán vị bằng cách ĐỔI CHỖ đúng hai lựa chọn, không xáo cả bốn: giữ nguyên
    thứ tự tương đối của ba phương án còn lại, nên một cặp đối lập được cố ý đặt
    cạnh nhau vẫn nằm cạnh nhau.
    """
    lines = block.splitlines()
    options: dict[str, tuple[int, str]] = {}
    answer_line = -1
    answer = ""

    for index, line in enumerate(lines):
        stripped = line.strip()
        matched = _OPTION.match(stripped)
        if matched:
            options[matched.group(1)] = (index, matched.group(2))
            continue
        found = _ANSWER.match(stripped)
        if found:
            answer_line, answer = index, found.group(1).upper()

    if answer not in options or target not in options or answer == target:
        return block

    # Đổi NỘI DUNG của hai dòng, giữ nguyên nhãn — nhãn phải luôn theo thứ tự
    # A, B, C, D từ trên xuống, vì `_OPTION_LINE` của parser đọc nhãn từ chính
    # dòng đó và giao diện in ra theo thứ tự xuất hiện.
    answer_index, answer_text = options[answer]
    target_index, target_text = options[target]
    lines[answer_index] = f"({answer}) {target_text}"
    lines[target_index] = f"({target}) {answer_text}"
    lines[answer_line] = f"Answer: {target}"
    return "\n".join(lines)


def plan_targets(count: int, seed: int) -> list[str]:
    """Chữ cái đích cho từng câu, chia đều và xoay theo `seed`.

    Xoay để hai đề khác nhau không cùng bắt đầu bằng A — một người làm nhiều đề
    sẽ nhận ra khuôn "câu 101 luôn là A" nhanh hơn ta tưởng.
    """
    offset = seed % len(LETTERS)
    return [LETTERS[(index + offset) % len(LETTERS)] for index in range(count)]


def balance(blueprint: Blueprint, workdir: Path, only: int | None = None) -> dict[str, int]:
    """Ghi lại các tệp dán sao cho đáp án rải đều. Trả về phân bố sau khi cân.

    Gán đích TRONG TỪNG PART, không trên danh sách gộp. Hai lý do, và lý do thứ
    hai là thứ hỏng im lặng: mỗi part được nạp riêng và phải tự cân, còn nếu gán
    trên danh sách gộp thì thêm một part mới sẽ dịch đích của MỌI part đã cân
    trước đó — các tệp dán bị viết lại và không còn khớp với những gì đã nằm
    trong database.

    Part 2 có ba lựa chọn nên nó không dùng được bảng bốn chữ này; khi tới lượt
    nó, chỗ cần sửa là `LETTERS`, không phải hàm này.
    """
    tally = dict.fromkeys(LETTERS, 0)
    for part in blueprint.parts:
        if only is not None and part.part != only:
            continue
        ordered = sorted(part.slots, key=lambda item: item.number)
        # Part 3/4 có BA câu trong một ô, nên số đích phải đếm theo CÂU chứ không
        # theo ô — đếm theo ô thì mỗi cụm chỉ nhận một chữ cái và ba câu của nó
        # cùng đáp án, thứ đọc ra ngay là máy làm.
        per_slot = LISTENING_QUESTIONS_PER_SET if part.part in (3, 4) else 1
        targets = plan_targets(len(ordered) * per_slot, blueprint.seed)
        for index, slot in enumerate(ordered):
            path = paste_path(workdir, slot)
            if not path.exists():
                continue
            share = targets[index * per_slot : (index + 1) * per_slot]
            updated = rewrite_all(path.read_text(), share)
            path.write_text(updated.rstrip() + "\n")
            for found in _ANSWER.finditer(updated):
                tally[found.group(1).upper()] += 1
    return tally
