"""Bộ chọn đề placement — `app/content/make_placement.py`.

Không bài nào chạm database thật: thứ đáng ghim là **phép chọn**, và nó là hàm
thuần trên một danh sách câu cùng bảng nhãn.

Bài học đứng sau tệp này: bản đầu lấy **phần đầu** của mỗi part, mà đề TOEIC xếp
từ dễ đến khó trong từng part — nên đề placement là đầu của bảy part cộng lại, và
không có phép kiểm nào thấy điều đó. Số câu vẫn đúng 84, mọi câu vẫn hợp lệ.
"""

import uuid
from dataclasses import dataclass, field

from app.content.make_placement import _fill_exactly, _pick_part


@dataclass
class FakeQuestion:
    part: int
    set_id: uuid.UUID | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


def _conversations(part: int, specs: list[tuple[str, ...]]) -> tuple[list, dict]:
    """Mỗi spec là một cụm; mỗi phần tử là mã dạng câu của một câu trong cụm."""
    questions: list[FakeQuestion] = []
    labels: dict[uuid.UUID, list[str]] = {}
    for spec in specs:
        set_id = uuid.uuid4()
        for code in spec:
            question = FakeQuestion(part=part, set_id=set_id)
            questions.append(question)
            labels[question.id] = [code]
    return questions, labels


def test_a_hard_set_is_taken_even_when_it_stands_last() -> None:
    """Cụm có biểu đồ nằm CUỐI Part 3 của mọi đề thật — đó là chỗ đề để nó.

    Bộ chọn cũ lấy bốn cụm đầu và dừng, nên trên `tp-test-09` nó lấy câu 32–43
    trong khi ba câu biểu đồ nằm ở 64–70. Không giao nhau chút nào, và đề vẫn ra
    đủ 12 câu Part 3 nên không có gì để báo.
    """
    easy = ("PART_3_TOPIC_OR_PURPOSE", "PART_3_CONVERSATION_DETAIL", "PART_3_FUTURE_ACTION")
    hard = (
        "PART_3_SPEAKER_IDENTITY",
        "PART_3_CONVERSATION_DETAIL",
        "PART_3_GRAPH_OR_TABLE_QUESTION",
    )
    questions, labels = _conversations(3, [easy, easy, easy, easy, easy, hard])

    picked = _pick_part(3, questions, labels, {})
    codes = [labels[q.id][0] for q in picked]
    assert len(picked) == 12
    assert "PART_3_GRAPH_OR_TABLE_QUESTION" in codes


def test_whole_sets_only_never_half_a_conversation() -> None:
    """Nửa cuộc hội thoại không phải một câu hỏi trắc nghiệm độc lập."""
    easy = ("PART_3_TOPIC_OR_PURPOSE", "PART_3_CONVERSATION_DETAIL", "PART_3_FUTURE_ACTION")
    questions, labels = _conversations(3, [easy] * 6)

    picked = _pick_part(3, questions, labels, {})
    by_set: dict[uuid.UUID, int] = {}
    for question in picked:
        by_set[question.set_id] = by_set.get(question.set_id, 0) + 1
    assert set(by_set.values()) == {3}


def test_the_easiest_sets_are_taken_last() -> None:
    """Cụm đặc hai dạng dễ nhất phải xếp sau, và đó là thứ thay cho "cụm đầu"."""
    easy = ("PART_7_INFORMATION_RETRIEVAL", "PART_7_TOPIC_OR_PURPOSE")
    mixed = ("PART_7_INFERENCE", "PART_7_FALSE_INFORMATION")
    # Sáu cụm dễ đứng TRƯỚC, ba cụm khó đứng sau — nếu vị trí còn quyết định
    # thì bộ chọn lấy bảy cụm đầu và chỉ vớ được một cụm khó.
    questions, labels = _conversations(7, [easy] * 6 + [mixed] * 3)

    picked = _pick_part(7, questions, labels, {})
    codes = [labels[q.id][0] for q in picked]
    assert len(picked) == 14
    assert codes.count("PART_7_INFERENCE") == 3


def test_part5_reaches_its_vocabulary_quota() -> None:
    """Từ vựng là dạng khó nhất của Part 5 — nó không có quy tắc để suy ra.

    Bộ chọn cũ phủ theo nhãn `grammar` và ra 2/20 câu từ vựng, mỏng hơn cả tỉ lệ
    của chính kho.
    """
    questions: list[FakeQuestion] = []
    labels: dict[uuid.UUID, list[str]] = {}
    for code, count in (
        ("PART_5_GRAMMAR", 14),
        ("PART_5_PART_OF_SPEECH", 9),
        ("PART_5_VOCABULARY", 7),
    ):
        for _ in range(count):
            question = FakeQuestion(part=5)
            questions.append(question)
            labels[question.id] = [code]

    picked = _pick_part(5, questions, labels, {})
    codes = [labels[q.id][0] for q in picked]
    assert len(picked) == 20
    assert codes.count("PART_5_VOCABULARY") == 6


def test_the_fill_lands_on_the_quota_exactly_not_one_short() -> None:
    """Cụm Part 7 dài 2 tới 5 câu, nên "lấy tiếp nếu còn vừa" dừng ở 13/14.

    Một câu thiếu làm cả lượt dựng đổ ở phép kiểm 84 — đúng như nó nên, nhưng
    thứ phải sửa là phép chọn.
    """
    # Lấy theo thứ tự thì 5+5+3 = 13 rồi tắc: 4 và 2 đều làm vượt. Tổ hợp đúng
    # là 5+5+4, và chỉ phép tìm trên MỌI tổ hợp mới thấy nó.
    groups = [(i, [FakeQuestion(part=7)] * size) for i, size in enumerate((5, 5, 3, 4, 2))]
    chosen = _fill_exactly(groups, 14, lambda group: 0.0)
    assert sum(len(groups[i][1]) for i in chosen) == 14
