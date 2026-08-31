"""Đổi dàn giọng của một đề đã dán sang dàn narrator của đề thật.

Chỉ kiểm bộ LẬP ánh xạ — nó thuần tuý và là chỗ duy nhất có thể sai im lặng.
Phần đọc/ghi database là một vòng lặp không có quyết định nào trong đó.
"""

from collections import Counter
from pathlib import Path

from app.content.recast_voices import plan_slot, read_paste
from app.core.media import TOEIC_NARRATORS, voice_gender

CAST = set(TOEIC_NARRATORS.values())


def test_a_same_accent_conversation_becomes_two_countries() -> None:
    """Hình dạng sai phổ biến nhất của đề cũ: cả cuộc hội thoại một accent."""
    plan = plan_slot("p3", ["au_female_1", "au_male_1"], Counter())

    after = list(plan.mapping.values())
    assert set(after) <= CAST
    assert len(set(after)) == 2
    assert len({voice.split("_")[0] for voice in after}) == 2


def test_gender_is_never_flipped() -> None:
    """Part 3 và 4 hỏi thẳng "What does the *man* say?".

    Lật giới tính một lượt là làm câu hỏi sai đáp án, và không phép kiểm nào
    trong hệ thống thấy điều đó — chỉ người bấm play mới biết.
    """
    voices = ["us_male_1", "ca_female_1", "uk_male_1", "au_female_1"]
    for before, after in plan_slot("x", voices, Counter()).mapping.items():
        assert voice_gender(before) == voice_gender(after)


def test_a_voice_already_in_the_cast_is_left_alone() -> None:
    plan = plan_slot("p1", ["us_female_1"], Counter())
    assert plan.mapping == {"us_female_1": "us_female_1"}
    assert not plan.changed


def test_more_speakers_of_one_gender_than_narrators_is_reported_not_guessed() -> None:
    """Dàn chỉ có hai nữ. Ba người nói nữ trong một ô thì không có lời giải.

    Đoán bừa ở đây nghĩa là hai người nói dùng chung một giọng, và người nghe
    mất khả năng tách ai đang nói — hỏng nặng hơn hẳn việc dừng lại và nói ra.
    """
    plan = plan_slot("p3", ["us_female_1", "uk_female_1", "au_female_1"], Counter())
    assert plan.problem


def test_the_least_used_accent_wins_so_a_paper_evens_out() -> None:
    """Chọn tham lam theo accent đang ít lượt nhất, nên cả đề tự tiến về 25%."""
    used = Counter({"ca_male_1": 40, "au_male_1": 0})
    plan = plan_slot("p2", ["uk_male_1"], used)
    assert plan.mapping["uk_male_1"] == "au_male_1"


def test_a_bracket_line_closes_the_spoken_region(tmp_path: Path) -> None:
    """`[QUESTION]` kết thúc lời thoại; câu hỏi và lựa chọn sau nó không được đọc.

    Không đóng vùng thì phần câu hỏi bị tính là lời thoại, và tệp Part 3/4 nào
    cũng trượt khỏi bảng tra nối tệp với hàng database — đo được 23/54 tệp trượt
    trước khi có dòng đó, và cái trượt là im lặng: tệp chỉ đơn giản không được
    sửa.
    """
    path = tmp_path / "p3-01.txt"
    path.write_text(
        "[SCRIPT]\n"
        "voice: us_female_1\n"
        "Do you have a moment?\n"
        "voice: ca_male_1\n"
        "Of course.\n"
        "\n"
        "[QUESTION]\n"
        "What does the man agree to do?\n"
        "(A) Review a budget\n"
        "Answer: A\n"
    )
    order, texts = read_paste(path)
    assert order == ["us_female_1", "ca_male_1"]
    assert texts == ["Do you have a moment?", "Of course."]
