"""Định dạng lời giải thích, và các ví dụ trong prompt phải tự tuân theo nó.

Phép kiểm thứ hai tồn tại vì thiếu nó đã trả giá thật: ba trong bảy ví dụ trong
các tệp prompt mô tả một câu hỏi KHÁC hẳn câu hỏi in ngay trên chúng, và hai
trong số đó còn nêu sai chữ cái đáp án. Không ai đọc lại ví dụ sau khi viết,
nhưng mô hình bám theo ví dụ chặt hơn bám theo mô tả — nên một ví dụ hỏng dạy
đúng cái thói quen mà phần mô tả đang cấm.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.content.exam import explanation as X
from app.content.exam.balance import rewrite
from app.content.exam.prompts import SYSTEM as PART5_SYSTEM

PROMPTS = Path(__file__).resolve().parents[1] / "app" / "content" / "exam" / "prompts"
_OPTION = re.compile(r"^\(([A-D])\)\s*(.*)$")
_OPENING_QUOTE = re.compile(r'^"([^"]+)"')


def _examples(text: str) -> list[tuple[dict[str, str], str, str]]:
    """(lựa chọn, chữ cái đáp án, phần sau `Explanation:`) cho từng khối ví dụ."""
    found = []
    options: dict[str, str] = {}
    answer = ""
    for line in text.splitlines():
        matched = _OPTION.match(line.strip())
        if matched:
            if answer:
                options, answer = {}, ""
            options[matched.group(1)] = matched.group(2)
        elif line.startswith("Answer:"):
            answer = line.split(":", 1)[1].strip()
        elif line.startswith("Explanation:") and options:
            found.append((options, answer, line.split(":", 1)[1].strip()))
            options, answer = {}, ""
    return found


def _sources() -> list[tuple[str, str]]:
    files = [(path.stem, path.read_text()) for path in sorted(PROMPTS.glob("part*_system.md"))]
    # Part 5 dựng lời giải thích mẫu bằng template, nên đọc tệp .md sẽ chỉ thấy
    # placeholder `{EXAMPLE_EXPLANATION}` chứ không thấy ví dụ thật.
    return [*[(n, t) for n, t in files if n != "part5_system"], ("part5", PART5_SYSTEM)]


def test_every_example_explanation_in_every_prompt_matches_its_own_question() -> None:
    problems: list[str] = []
    seen = 0
    for name, text in _sources():
        for options, answer, value in _examples(text):
            seen += 1
            where = f"{name} (đáp án {answer})"
            problems += [f"{where}: {line}" for line in X.problems(value, list(options))]
            parsed = X.parse(value)
            if parsed is None:
                continue
            if answer and answer not in parsed.clauses:
                problems.append(f"{where}: không có mệnh đề cho chính đáp án")
            for label, clause in parsed.clauses.items():
                quoted = _OPENING_QUOTE.match(clause)
                if quoted and quoted.group(1).lower() not in options.get(label, "").lower():
                    problems.append(f"{where}: mệnh đề ({label}) trích lời của một lựa chọn khác")
    assert seen >= 7, f"chỉ tìm thấy {seen} ví dụ — bộ trích khối hỏng, không phải prompt sạch"
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("target", ["B", "C", "D"])
def test_balancing_moves_each_clause_with_the_option_it_describes(target: str) -> None:
    block = (
        "[QUESTION]\nWho is the woman?\n"
        "(A) An employee\n(B) A manager\n(C) A client\n(D) A receptionist\nAnswer: A\n"
        'Explanation: Người phụ nữ nói "I\'m the new employee", nên cô là nhân viên.'
        ' | (A) "An employee" — khớp câu vừa dẫn.'
        ' | (B) "A manager" — chức của người nam.'
        ' | (C) "A client" — không được nhắc đến.'
        ' | (D) "A receptionist" — không xuất hiện.\nSource: original'
    )
    out = rewrite(block, target)
    options = dict(
        _OPTION.match(line).groups()  # type: ignore[union-attr]
        for line in out.splitlines()
        if _OPTION.match(line)
    )
    parsed = X.parse(
        next(line for line in out.splitlines() if line.startswith("Explanation:")).split(":", 1)[1]
    )
    assert parsed is not None
    assert f"Answer: {target}" in out
    for label, content in options.items():
        assert parsed.clauses[label].startswith(f'"{content}"'), label
    # Câu dẫn chứng không mang nhãn nên phép cân không được đụng vào nó.
    assert parsed.evidence.startswith("Người phụ nữ nói")


def test_an_old_prose_explanation_still_balances_through_the_fallback() -> None:
    block = (
        "[QUESTION]\nQ?\n(A) first\n(B) second\n(C) third\n(D) fourth\nAnswer: A\n"
        "Explanation: Lý do nào đó, nên (A) đúng. (B) sai. (C) sai. (D) sai.\nSource: original"
    )
    out = rewrite(block, "C")
    assert X.parse("Lý do nào đó, nên (A) đúng.") is None
    assert "Answer: C" in out
    assert "nên (C) đúng" in out
