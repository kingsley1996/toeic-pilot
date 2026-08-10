"""Trình dán đề thi: Part 5, 6, 7 (ADR-007 §2.3).

Không có database ở đây, đúng theo ADR-005: parse là hàm thuần, và bước xem
trước tồn tại chính vì nó chưa ghi gì.
"""

import unicodedata

import pytest

from app.services.content_import import parse_reading_part

# --- đề thi: Part 5, 6, 7 (ADR-007) -----------------------------------------

PART5 = """[QUESTION]
The board approved the ____ budget for the next quarter.
(A) annual
(B) annually
(C) annualize
(D) annuity
answer: A
source: original
explanation: Cần một tính từ bổ nghĩa cho "budget".
"""


def test_part_7_keeps_several_passages_under_one_group():
    """Bài đọc đôi của Part 7 là MỘT cụm, không phải hai.

    Luật: [NGỮ LIỆU] mở cụm mới chỉ khi cụm hiện tại đã có câu hỏi. Hiểu sai
    chỗ này thì một bài đọc đôi thành hai cụm mỗi cụm một nửa ngữ liệu, và câu
    hỏi mất đúng đoạn văn nó cần để trả lời.
    """
    raw = """[PASSAGE] Email và bảng giá
Thank you for your enquiry.

[PASSAGE]
PRICE LIST - March

[QUESTION]
What is the purpose of the e-mail?
(A) To confirm a delivery
(B) To provide prices
(C) To apologise
(D) To announce a product
answer: B
source: original
"""
    (group,) = parse_reading_part(raw, 7)
    assert len(group.passages) == 2
    assert len(group.questions) == 1
    assert group.title == "Email và bảng giá"
    assert group.ok


def test_part_5_never_groups_questions():
    raw = PART5 + PART5.replace("The board", "The committee")
    groups = parse_reading_part(raw, 5)
    assert [len(group.questions) for group in groups] == [1, 1]
    assert all(not group.passages for group in groups)


def test_source_has_no_default_and_the_paste_is_refused_without_it():
    """`question.source` không được default ở bất kỳ tầng nào (ADR-007 §2.5).

    Trả lời sai câu "nội dung này ở đâu ra" là rủi ro pháp lý, và một giá trị
    mặc định là cách chắc chắn nhất để không ai từng trả lời nó.
    """
    (group,) = parse_reading_part(PART5.replace("source: original\n", ""), 5)
    (question,) = group.questions
    assert not question.ok
    assert any("source:" in problem for problem in question.problems)


def test_every_problem_is_reported_at_once():
    # Người dán 30 câu muốn biết hết một lượt, không phải đập chuột từng con.
    (group,) = parse_reading_part(
        PART5.replace("answer: A", "answer: E").replace("source: original\n", ""), 5
    )
    (question,) = group.questions
    assert len(question.problems) == 2


def test_the_marker_survives_how_a_human_actually_types_it():
    """Mốc chính thức là ASCII, nhưng dạng cũ vẫn phải chạy.

    Vì sao có test này dù `[QUESTION]` không thể phân rã: nó ghi lại cách hỏng
    đã xảy ra thật. macOS trả chữ Â ở dạng phân rã, nên `"[CÂU]"` dán từ một số
    ứng dụng dài 6 ký tự chứ không phải 5 — hai chuỗi hiện lên **giống hệt
    nhau**. Người dán 10 câu nhận về màn hình trống.

    Đó cũng chính là lý do định dạng chuyển sang ASCII: vá thì hết một ca, đổi
    bảng chữ cái thì hết cả lớp lỗi.
    """
    body = PART5[len("[QUESTION]") :]
    variants = (
        "[QUESTION]",
        "[question]",
        "  [Question]  ",
        "[CÂU]",
        unicodedata.normalize("NFD", "[CÂU]"),
        "[CAU]",
    )
    for marker in variants:
        (group,) = parse_reading_part(marker + body, 5)
        assert group.ok, marker


def test_a_paste_that_matches_nothing_is_refused_not_reported_as_valid():
    """Im lặng là lỗi nặng hơn cả nguyên nhân gây ra nó.

    Bản đầu trả về 0 cụm và 0 lỗi, nên giao diện báo "hợp lệ" cho một thứ nó
    không đọc được dòng nào — và người dùng đi tìm lỗi ở phía mình.
    """
    with pytest.raises(ValueError, match="Không nhận ra dòng nào"):
        parse_reading_part("The board approved the budget.\n(A) annual\n", 5)


def test_part_6_is_one_passage_with_blanks_not_a_multi_passage_set():
    """Part 6 và Part 7 là hai format khác nhau, không phải hai biến thể.

    Part 6 (Text Completion) là **một** đoạn văn có các chỗ trống, mỗi chỗ trống
    là một câu hỏi — không có bài hai đoạn và không có ảnh. Part 7 mới có bài
    một/hai/ba đoạn. Cho Part 6 nhận nhiều đoạn là mở đường cho một cụm không
    tồn tại trong đề thật, và người soạn chỉ phát hiện khi so với đề mẫu.
    """
    two = """[PASSAGE] Đoạn 1
First text.

[PASSAGE] Đoạn 2
Second text.

[QUESTION]
(131)
(A) a
(B) b
(C) c
(D) d
answer: A
source: original
"""
    (six,) = parse_reading_part(two, 6)
    assert any("tối đa 1 đoạn văn" in problem for problem in six.problems)

    (seven,) = parse_reading_part(two, 7)
    assert seven.ok
