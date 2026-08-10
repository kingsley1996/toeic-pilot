"""Chấm bài gõ lại từ.

Điều đáng canh không phải là "đúng thì đúng", mà là ranh giới giữa gõ nhầm và
không thuộc: đặt sai chỗ thì hoặc học viên bị phạt vì trượt phím, hoặc được
cộng điểm cho một từ họ chưa từng viết ra.
"""

import pytest

from app.services.recall import (
    TYPO_MIN_LENGTH,
    VERDICT_CORRECT,
    VERDICT_TYPO,
    VERDICT_WRONG,
    canonical,
    edit_distance,
    grade_for,
    judge,
)
from app.services.srs import GRADE_EASY, GRADE_FORGOT, GRADE_GOOD, GRADE_HARD


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("reimburse", "reimburse"),
        ("  Reimburse  ", "reimburse"),
        ("REIMBURSE", "reimburse"),
        ("reimburse.", "reimburse"),
        # Mục từ nhiều chữ là chuyện bình thường: "on behalf of" là MỘT mục từ.
        ("on behalf of", "on behalf of"),
        ("On  behalf   of", "on behalf of"),
    ],
)
def test_case_spacing_and_punctuation_do_not_make_an_answer_wrong(
    typed: str, expected: str
) -> None:
    assert judge(typed, expected).verdict == VERDICT_CORRECT


def test_a_curly_apostrophe_still_counts_as_correct() -> None:
    """Bàn phím điện thoại tự đổi dấu nháy; đó không phải lỗi của người học."""
    assert judge("don’t", "don't").verdict == VERDICT_CORRECT


def test_a_missing_apostrophe_is_a_real_spelling_mistake() -> None:
    """Nhưng bỏ hẳn dấu nháy thì là sai chính tả — một ký tự, nên là gõ nhầm."""
    assert judge("dont", "don't").verdict == VERDICT_TYPO


def test_one_wrong_character_in_a_long_word_is_a_typo() -> None:
    assert judge("reimburze", "reimburse").verdict == VERDICT_TYPO
    assert judge("reimburs", "reimburse").verdict == VERDICT_TYPO


def test_two_wrong_characters_is_not_a_typo() -> None:
    assert judge("reimbrze", "reimburse").verdict == VERDICT_WRONG


def test_one_character_off_in_a_short_word_is_wrong_not_a_typo() -> None:
    """Với từ ngắn, khoảng cách 1 đã là một từ khác hẳn.

    "aim" cách "aid" đúng một ký tự nhưng không ai gọi đó là trượt phím; chấm
    nó là gõ nhầm tức là cho điểm một từ học viên không hề viết ra.
    """
    short = "aid"
    assert len(short) < TYPO_MIN_LENGTH
    assert judge("aim", short).verdict == VERDICT_WRONG


def test_an_empty_answer_is_wrong_never_a_typo() -> None:
    """Không viết gì thì không có gì để gọi là nhầm — kể cả với mục từ 1 ký tự."""
    assert judge("", "a").verdict == VERDICT_WRONG
    assert judge("   ", "reimburse").verdict == VERDICT_WRONG


def test_a_completely_different_word_is_wrong() -> None:
    assert judge("invoice", "reimburse").verdict == VERDICT_WRONG


@pytest.mark.parametrize(
    ("left", "right", "distance"),
    [("", "", 0), ("abc", "abc", 0), ("abc", "abd", 1), ("abc", "ab", 1), ("", "abc", 3)],
)
def test_edit_distance_counts_single_edits(left: str, right: str, distance: int) -> None:
    assert edit_distance(left, right) == distance
    assert edit_distance(right, left) == distance, "khoảng cách phải đối xứng"


def test_canonical_is_idempotent() -> None:
    once = canonical("  On BEHALF, of  ")
    assert canonical(once) == once


# --- điểm SM-2 suy ra ------------------------------------------------------


def test_grades_follow_the_verdict() -> None:
    assert grade_for(VERDICT_CORRECT) == GRADE_GOOD
    assert grade_for(VERDICT_TYPO) == GRADE_HARD
    assert grade_for(VERDICT_WRONG) == GRADE_FORGOT


def test_easy_only_applies_to_a_correct_answer() -> None:
    """Nói "dễ" trong lúc viết sai không nâng được điểm.

    Đây là toàn bộ lý do endpoint này tồn tại: thẻ lật tin lời người học, còn ở
    đây lời khai chỉ được xét SAU khi máy đã xác nhận là viết đúng.
    """
    assert grade_for(VERDICT_CORRECT, easy=True) == GRADE_EASY
    assert grade_for(VERDICT_TYPO, easy=True) == GRADE_HARD
    assert grade_for(VERDICT_WRONG, easy=True) == GRADE_FORGOT
