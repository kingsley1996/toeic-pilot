"""Chấm một lần "gõ lại từ" — học viên nhìn nghĩa tiếng Việt và viết lại từ.

Vì sao việc chấm nằm ở SERVER chứ không ở trình duyệt, ngược với dictation:
dictation chấm ở client để phản hồi tức thì trên một câu dài, và phải trả giá
bằng hai bộ chấm luôn có nguy cơ lệch nhau (`CLAUDE.md`, mục dictation). Ở đây
đơn vị chấm là MỘT từ, một vòng request là đủ nhanh, nên không có lý do gì để
tạo ra bản sao thứ hai — và cũng không có bản sao nào để lệch.

Hệ quả quan trọng hơn: điểm SM-2 không còn do người học tự khai. Thẻ lật cũ hỏi
"bạn có nhớ không" rồi tin câu trả lời; ở đây câu trả lời được kiểm trước.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.services.srs import GRADE_EASY, GRADE_FORGOT, GRADE_GOOD, GRADE_HARD

VERDICT_CORRECT = "correct"
VERDICT_TYPO = "typo"
VERDICT_WRONG = "wrong"
# Học viên tự nói "tôi chưa biết". Tách khỏi `wrong` vì hai chuyện khác nhau:
# đoán sai là đã thử và trượt, còn cái này là chưa từng biết — và nếu không có
# nó thì cách duy nhất để đi tiếp là bịa một câu trả lời, tức là app đang dạy
# người ta đoán bừa. Điểm SM-2 vẫn là 0; chỉ có lời kể là trung thực hơn.
VERDICT_UNKNOWN = "unknown"
VERDICTS = (VERDICT_CORRECT, VERDICT_TYPO, VERDICT_WRONG, VERDICT_UNKNOWN)

# Sai đúng một ký tự thì tính là gõ nhầm, không phải không thuộc — nhưng chỉ với
# từ đủ dài. Với "aid" thì khoảng cách 1 đã đủ biến nó thành "aim" hay "air",
# những từ khác hẳn; gọi đó là gõ nhầm là chấm điểm cho một từ học viên không
# hề viết ra.
TYPO_MAX_DISTANCE = 1
TYPO_MIN_LENGTH = 4

# Giữ dấu nháy: "dont" khác "don't" và đó là một lỗi chính tả thật. Bỏ mọi thứ
# còn lại vì học viên đang viết một MỤC TỪ, không phải một câu.
_STRIP_PUNCTUATION = re.compile(r"[^\w\s']", flags=re.UNICODE)
_COLLAPSE_SPACE = re.compile(r"\s+")
_APOSTROPHES = {"’": "'", "ʼ": "'", "´": "'"}


def canonical(text: str) -> str:
    """Đưa về dạng để so sánh: thường hoá, bỏ dấu câu, gộp khoảng trắng.

    Trả về CHUỖI chứ không phải danh sách từ như `dictation.normalise`, vì mục
    từ có thể gồm nhiều từ — "on behalf of" là một mục từ — và khoảng cách sửa
    phải tính trên toàn bộ cụm, không phải từng từ rời.
    """
    text = unicodedata.normalize("NFKC", text)
    for fancy, plain in _APOSTROPHES.items():
        text = text.replace(fancy, plain)
    text = _STRIP_PUNCTUATION.sub(" ", text.lower())
    return _COLLAPSE_SPACE.sub(" ", text).strip()


def edit_distance(left: str, right: str) -> int:
    """Khoảng cách Levenshtein, quy hoạch động trên một hàng.

    Tự viết thay vì mượn `SequenceMatcher`: `SequenceMatcher` đo độ giống nhau
    chứ không đếm số phép sửa, nên nó không trả lời được câu hỏi duy nhất cần
    hỏi ở đây — "sai đúng một ký tự phải không".
    """
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,  # xoá
                    current[j - 1] + 1,  # chèn
                    previous[j - 1] + (left_char != right_char),  # thay
                )
            )
        previous = current
    return previous[-1]


@dataclass(frozen=True)
class RecallJudgement:
    verdict: str
    distance: int
    expected: str
    typed: str


def judge(typed: str, expected: str) -> RecallJudgement:
    """So bài gõ với mục từ.

    Bỏ trống được tính là SAI chứ không phải gõ nhầm, kể cả khi mục từ chỉ dài
    một ký tự: không viết gì thì không có gì để gọi là nhầm.
    """
    typed_canonical = canonical(typed)
    expected_canonical = canonical(expected)
    distance = edit_distance(typed_canonical, expected_canonical)

    if distance == 0:
        verdict = VERDICT_CORRECT
    elif (
        typed_canonical
        and distance <= TYPO_MAX_DISTANCE
        and len(expected_canonical) >= TYPO_MIN_LENGTH
    ):
        verdict = VERDICT_TYPO
    else:
        verdict = VERDICT_WRONG

    return RecallJudgement(
        verdict=verdict,
        distance=distance,
        expected=expected_canonical,
        typed=typed_canonical,
    )


def grade_for(verdict: str, *, easy: bool = False) -> int:
    """Quy kết quả khách quan thành điểm SM-2.

    `easy` là thứ DUY NHẤT người học còn tự khai, và nó chỉ có tác dụng khi bài
    gõ đã đúng — tức là chỉ được nâng điểm sau khi đã chứng minh mình viết ra
    được. Không có nó thì điểm trần là 4, và với SM-2 điểm 4 giữ nguyên hệ số
    dễ: khoảng cách ôn vẫn giãn ra (× 2.50) nhưng không thẻ nào nhẹ đi được.
    """
    if verdict == VERDICT_CORRECT:
        return GRADE_EASY if easy else GRADE_GOOD
    if verdict == VERDICT_TYPO:
        return GRADE_HARD
    return GRADE_FORGOT
