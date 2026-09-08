"""Lắp đề placement từ một đề full có sẵn — SPEC-PLACEMENT §1 path A.

    uv run python -m app.content.make_placement                # tạo/cập nhật draft
    uv run python -m app.content.make_placement --publish      # duyệt + xuất bản

    uv run python -m app.content.make_placement --preview     # chỉ xem, không ghi

Định mức 84 câu (§0 của spec): P1 6, P2 12, P3 12, P4 12, P5 20, P6 8, P7 14.
Cắt lệch phần dư chấp nhận được; cắt cụm thì không — một nửa cuộc hội thoại
không phải một câu hỏi trắc nghiệm độc lập.

**Chọn theo DẠNG CÂU, không theo vị trí.** Bản đầu lấy phần đầu của mỗi part, và
đề TOEIC xếp từ dễ đến khó trong từng part, nên đề placement là đầu của bảy part
cộng lại: 0 câu biểu đồ, 0 câu hàm ý, 0 câu điền câu — trong khi kho có đủ cả ba.
`PRIORITY` liệt kê những dạng khó phải có mặt và `EASY` liệt kê hai dạng dễ nhất
của mỗi part để cụm đặc chúng bị lấy sau. Đo và lập luận ở
`SPEC-EXAM-DIFFICULTY` §4.

Số câu (`number`) đánh tuần tự 1..N theo part — đề mini không nhảy cóc kiểu
đề 200 câu, và số nhảy cóc phải là thứ có người nhìn thấy và đồng ý (ADR-007
§2.6); người duyệt thấy số liền mạch trong bảng duyệt.
"""

import argparse
from collections import Counter
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.labels import QuestionLabel
from app.models.practice import PracticeTest, PracticeTestQuestion, Question

SOURCE_SLUG = "tp-test-09"
PLACEMENT_SLUG = "tp-placement-01"
TITLE = "Bài test đầu vào"
DESCRIPTION = (
    "84 câu rút từ đề mẫu, ~40 phút. Kết quả cho biết trình độ hiện tại "
    "(ước lượng) và những kỹ năng cần luyện — làm một lần mỗi tuần."
)
KIND = "placement"
TOTAL_QUESTIONS = 84
# 40 phút, không phải 50: đề 84 câu ở tốc độ thật còn dư trên 15 phút khi chặn
# 50 — nói dối về thời lượng là làm người học nghỉ tay giữa bài. Bài 50 phút
# từng là chuẩn trước khi có dữ liệu lượt làm thật.
TIME_LIMIT_SECONDS = 40 * 60


def _source_test(db: Session, slug: str = SOURCE_SLUG) -> PracticeTest:
    test = db.scalar(select(PracticeTest).where(PracticeTest.slug == slug))
    if test is None:
        raise SystemExit(f"không có đề nguồn {slug}")
    return test


def _source_questions(db: Session, test: PracticeTest) -> list[Question]:
    rows = db.execute(
        select(PracticeTestQuestion.position, Question)
        .join(Question, Question.id == PracticeTestQuestion.question_id)
        .where(PracticeTestQuestion.test_id == test.id)
        .order_by(PracticeTestQuestion.position)
    ).all()
    return [q for _, q in rows]


def _labels_of(db: Session, facet: str, ids: list[UUID]) -> dict[UUID, list[str]]:
    """question_id -> các mã nhãn của một facet. `question` không có
    relationship tới nhãn; truy vấn bảng nối một lần cho cả đề nguồn."""
    rows = db.execute(
        select(QuestionLabel.question_id, QuestionLabel.code).where(
            QuestionLabel.question_id.in_(ids), QuestionLabel.facet == facet
        )
    ).all()
    out: dict[UUID, list[str]] = {}
    for qid, code in rows:
        out.setdefault(qid, []).append(code)
    return out


# Định mức theo DẠNG CÂU, cho những part chọn được từng câu một.
#
# Bộ chọn cũ lấy **phần đầu** của mỗi part, và đề TOEIC xếp từ dễ đến khó trong
# từng part — nên đề placement là đầu của bảy part cộng lại. Đo trên `tp-test-09`:
# câu biểu đồ Part 3 nằm ở 64–70 còn bộ chọn lấy 32–43, Part 4 là 85–99 và bộ
# chọn lấy 71–82. Không giao nhau chút nào.
#
# Nhưng vị trí KHÔNG phải thứ để sửa theo. Đề nguồn do chính pipeline này sinh
# ra, và blueprint xáo Part 2 và Part 5 theo seed — ở đó vị trí không mang tín
# hiệu độ khó nào. Thứ mang tín hiệu là **dạng câu**, và nó có nhãn.
PLACEMENT_MIX: dict[int, dict[str, int]] = {
    # Mười dạng câu hỏi, mỗi dạng ít nhất một câu. Trục độ khó thật của Part 2 —
    # đáp án đúng trả lời gián tiếp hay không — KHÔNG có nhãn, nên bộ chọn không
    # thấy nó; xem `SPEC-EXAM-DIFFICULTY` §2.1.
    2: {
        "PART_2_WHERE_QUESTION": 2,
        "PART_2_REQUEST_OR_SUGGESTION": 2,
        "PART_2_WHO_QUESTION": 1,
        "PART_2_WHEN_QUESTION": 1,
        "PART_2_HOW_QUESTION": 1,
        "PART_2_WHY_QUESTION": 1,
        "PART_2_YES_NO_QUESTION": 1,
        "PART_2_TAG_QUESTION": 1,
        "PART_2_CHOICE_QUESTION": 1,
        "PART_2_STATEMENT": 1,
    },
    # Từ vựng là dạng khó nhất của Part 5 — nó không có quy tắc để suy ra. Bộ
    # chọn cũ phủ theo nhãn `grammar` và ra 2/20 câu từ vựng, mỏng hơn cả tỉ lệ
    # của chính kho (7/30 trong đề nguồn).
    5: {
        "PART_5_GRAMMAR": 8,
        "PART_5_PART_OF_SPEECH": 6,
        "PART_5_VOCABULARY": 6,
    },
}

# Dạng câu mà đề placement PHẢI có ít nhất một câu, dù nó nằm ở cụm nào trong
# part. Đây là những dạng khó nhất, và đúng những dạng mà bộ chọn cũ lấy trọn 0.
PRIORITY: dict[int, tuple[str, ...]] = {
    3: ("PART_3_GRAPH_OR_TABLE_QUESTION", "PART_3_IMPLICATION"),
    4: ("PART_4_GRAPH_OR_TABLE_QUESTION", "PART_4_IMPLICATION"),
    7: ("PART_7_SENTENCE_INSERTION", "PART_7_IMPLICATION", "PART_7_VOCABULARY_IN_CONTEXT"),
}

# Hai dạng dễ nhất của mỗi part nghe/đọc dài. Cụm nào đặc hai dạng này thì lấy
# sau cùng — đây là thứ thay cho "lấy cụm đầu tiên".
EASY: dict[int, tuple[str, ...]] = {
    3: ("PART_3_TOPIC_OR_PURPOSE", "PART_3_CONVERSATION_DETAIL"),
    4: ("PART_4_TOPIC_OR_PURPOSE", "PART_4_DETAIL"),
    7: ("PART_7_INFORMATION_RETRIEVAL", "PART_7_TOPIC_OR_PURPOSE"),
}


def _pick_to_mix(
    questions: list[Question],
    labels: dict[UUID, list[str]],
    grammar_labels: dict[UUID, list[str]],
    mix: dict[str, int],
    n: int,
) -> list[Question]:
    """Lấy đúng định mức từng dạng câu; phần dư bù bằng dạng còn nhiều nhất.

    Trong cùng một dạng, ưu tiên câu mang một mã `grammar` chưa ai lấy — đó là
    tính chất §0.4 của spec ("mỗi kỹ năng chính có 2–4 câu") mà bộ chọn cũ đạt
    được bằng cách phủ theo nhãn `grammar`, và nó không được mất đi khi định mức
    chuyển sang `question_type`.
    """
    by_code: dict[str, list[Question]] = {}
    for q in questions:
        for code in labels.get(q.id, []):
            by_code.setdefault(code, []).append(q)

    picked: set[UUID] = set()
    out: list[Question] = []
    seen_grammar: set[str] = set()

    def take(code: str) -> bool:
        pool = [q for q in by_code.get(code, []) if q.id not in picked]
        if not pool:
            return False
        fresh = [q for q in pool if set(grammar_labels.get(q.id, [])) - seen_grammar]
        chosen = (fresh or pool)[0]
        picked.add(chosen.id)
        seen_grammar.update(grammar_labels.get(chosen.id, []))
        out.append(chosen)
        return True

    for code, want in mix.items():
        for _ in range(want):
            if len(out) >= n:
                break
            take(code)
    # Định mức không đủ (kho thiếu một dạng) thì bù bằng dạng còn nhiều nhất,
    # chứ không bỏ trống: 84 câu là con số cả §0 của spec dựa vào.
    while len(out) < n:
        remaining = Counter(
            {c: len([q for q in qs if q.id not in picked]) for c, qs in by_code.items()}
        )
        code, left = remaining.most_common(1)[0] if remaining else ("", 0)
        if left <= 0 or not take(code):
            break
    _cover_grammar(out, questions, labels, grammar_labels)
    return out


def _cover_grammar(
    out: list[Question],
    questions: list[Question],
    labels: dict[UUID, list[str]],
    grammar_labels: dict[UUID, list[str]],
) -> None:
    """Kéo về đủ mọi mã `grammar` bằng cách ĐỔI CHỖ, không thêm câu.

    §0.4 của spec chọn 20 câu Part 5 chính vì "mỗi nhãn `grammar` hiện diện ít
    nhất một câu" — breakdown kỹ năng đứng trên đó. Định mức mới xếp theo
    `question_type`, nên một mã ngữ pháp hiếm có thể rơi ra ngoài; ở đề nguồn
    hôm nay đúng một mã rơi (`GRAMMAR_TO_INFINITIVE`).

    Đổi trong CÙNG một `question_type`, và chỉ đổi một câu mà mọi mã ngữ pháp
    của nó đã có ở câu khác — nên định mức dạng câu không đổi và không mã nào
    mất đi để mã khác vào.
    """

    def type_of(q: Question) -> str:
        codes = labels.get(q.id, [])
        return codes[0] if codes else ""

    for _ in range(len(questions)):
        chosen_ids = {q.id for q in out}
        covered = Counter(code for q in out for code in grammar_labels.get(q.id, []))
        wanted = {
            code for q in questions for code in grammar_labels.get(q.id, []) if code not in covered
        }
        if not wanted:
            return
        swap = next(
            (
                (incoming, outgoing)
                for incoming in questions
                if incoming.id not in chosen_ids
                and wanted & set(grammar_labels.get(incoming.id, []))
                for outgoing in out
                if type_of(outgoing) == type_of(incoming)
                and all(covered[code] > 1 for code in grammar_labels.get(outgoing.id, []))
            ),
            None,
        )
        if swap is None:
            return
        incoming, outgoing = swap
        out[out.index(outgoing)] = incoming


def _cover_grammar_by_set(
    chosen: list[Question],
    part6: list[Question],
    grammar_labels: dict[UUID, list[str]],
) -> None:
    """Đổi một cụm Part 6 lấy một cụm khác, nếu nó kéo về một mã ngữ pháp đang thiếu.

    Part 6 lấy 2 trong 4 cụm, và mã ngữ pháp nào nằm ở hai cụm kia thì rơi ra
    ngoài. Điều đó không vô hại: planner đọc kỹ năng yếu theo mã `GRAMMAR_*`, nên
    một mã vắng mặt trong đề nghĩa là người yếu điểm ngữ pháp ấy không bao giờ bị
    phát hiện. Bộ chọn cũ phủ đủ 12 mã, nhưng do may chứ không do luật.

    Đổi cả CỤM và chỉ đổi cụm cùng kích thước, nên tổng 84 câu không đổi. Việc
    này chạy sau cùng, khi đã biết Part 5 phủ được những mã nào.
    """
    groups = _sets_of(part6)
    for _ in range(len(groups)):
        chosen_ids = {q.id for q in chosen}
        covered = {code for q in chosen for code in grammar_labels.get(q.id, [])}
        missing = {code for q in part6 for code in grammar_labels.get(q.id, [])} - covered
        if not missing:
            return
        inside = [g for g in groups if all(q.id in chosen_ids for q in g)]
        outside = [g for g in groups if not any(q.id in chosen_ids for q in g)]
        swap = next(
            (
                (incoming, outgoing)
                for incoming in outside
                if missing & {c for q in incoming for c in grammar_labels.get(q.id, [])}
                for outgoing in inside
                if len(outgoing) == len(incoming)
                # Không đánh đổi một mã lấy một mã: cụm bị bỏ chỉ được mang
                # những mã còn xuất hiện ở chỗ khác trong đề.
                and not {
                    c
                    for q in outgoing
                    for c in grammar_labels.get(q.id, [])
                    if not any(
                        c in grammar_labels.get(other.id, [])
                        for other in chosen
                        if other not in outgoing
                    )
                }
            ),
            None,
        )
        if swap is None:
            return
        incoming, outgoing = swap
        start = chosen.index(outgoing[0])
        for question in outgoing:
            chosen.remove(question)
        chosen[start:start] = incoming


def _sets_of(questions: list[Question]) -> list[list[Question]]:
    by_set: dict[UUID, list[Question]] = {}
    for q in questions:
        if q.set_id is not None:
            by_set.setdefault(q.set_id, []).append(q)
    return list(by_set.values())


def _pick_sets(
    questions: list[Question],
    labels: dict[UUID, list[str]],
    part: int,
    n: int,
) -> list[Question]:
    """Cụm NGUYÊN, ưu tiên cụm mang dạng câu khó — không phải cụm đứng đầu.

    Cắt lệch phần dư chấp nhận được; cắt cụm thì không — một nửa cuộc hội thoại
    không phải một câu hỏi trắc nghiệm độc lập. Nên định mức từng dạng ở đây là
    thứ *hướng tới*, không phải thứ đạt đúng: đơn vị chọn là cụm.

    Hai chặng, và thứ tự giữa chúng là toàn bộ điểm của hàm này:

    1. mỗi mã trong `PRIORITY` lấy MỘT cụm chứa nó, cụm nhỏ nhất để còn chỗ;
    2. phần còn lại xếp theo tỉ lệ câu DỄ tăng dần.

    Đảo thứ tự thì chặng 2 ăn hết định mức trước và cụm có biểu đồ không bao giờ
    tới lượt — đúng cái đã xảy ra với bộ chọn cũ, chỉ khác lý do.
    """
    groups = _sets_of(questions)
    easy = set(EASY.get(part, ()))

    def codes_of(group: list[Question]) -> set[str]:
        return {code for q in group for code in labels.get(q.id, [])}

    def easy_ratio(group: list[Question]) -> float:
        hits = sum(1 for q in group for code in labels.get(q.id, []) if code in easy)
        return hits / len(group)

    out: list[Question] = []
    used: set[int] = set()

    for wanted in PRIORITY.get(part, ()):
        pool = [
            (i, g)
            for i, g in enumerate(groups)
            if i not in used and wanted in codes_of(g) and len(out) + len(g) <= n
        ]
        if not pool:
            continue
        index, group = min(pool, key=lambda pair: len(pair[1]))
        used.add(index)
        out.extend(group)

    rest = [(i, g) for i, g in enumerate(groups) if i not in used]
    for index in _fill_exactly(rest, n - len(out), easy_ratio):
        out.extend(groups[index])
    return out


def _fill_exactly(
    rest: list[tuple[int, list[Question]]],
    need: int,
    easy_ratio: Callable[[list[Question]], float],
) -> list[int]:
    """Chọn tập cụm cộng lại ĐÚNG `need` câu, ít câu dễ nhất.

    Lấy tham lam theo tỉ lệ câu dễ thì thường hụt vài câu: cụm Part 7 dài 2 tới
    5 câu, và "lấy tiếp nếu còn vừa" dừng ở 13/14 rồi không có cụm 1 câu nào để
    bù. Một câu thiếu làm cả lượt dựng đổ ở phép kiểm tổng — đúng như nó nên,
    nhưng thứ cần sửa là phép chọn chứ không phải phép kiểm.

    Quy hoạch động trên số câu, y như xếp balo: `best[k]` là tập cụm rẻ nhất
    cộng lại đúng `k` câu. Kho có mười lăm cụm và `need` không quá 14, nên nó
    tức thời. Không có tổ hợp nào khớp đúng thì lấy tổng lớn nhất còn dưới —
    phép kiểm 84 câu ở `select_questions` mới là chỗ nói ra điều đó.
    """
    best: dict[int, tuple[float, list[int]]] = {0: (0.0, [])}
    for index, group in sorted(rest, key=lambda pair: easy_ratio(pair[1])):
        cost = easy_ratio(group)
        for size in sorted(best, reverse=True):
            total = size + len(group)
            if total > need:
                continue
            score = best[size][0] + cost
            if total not in best or score < best[total][0]:
                best[total] = (score, [*best[size][1], index])
    return best[max(best)][1]


def _pick_part(
    part: int,
    questions: list[Question],
    type_labels: dict[UUID, list[str]],
    grammar_labels: dict[UUID, list[str]],
) -> list[Question]:
    # Part 1 của đề nguồn có đúng sáu câu, tức lấy hết — không có gì để chọn.
    if part == 1:
        return questions[:6]
    if part in PLACEMENT_MIX:
        quota = 12 if part == 2 else 20
        return _pick_to_mix(questions, type_labels, grammar_labels, PLACEMENT_MIX[part], quota)
    quota = {3: 12, 4: 12, 6: 8, 7: 14}[part]
    return _pick_sets(questions, type_labels, part, quota)


def select_questions(
    db: Session, source_slug: str = SOURCE_SLUG
) -> tuple[PracticeTest, list[Question], dict[UUID, list[str]], dict[UUID, list[str]]]:
    """Chọn 84 câu. KHÔNG ghi gì — `--preview` gọi đúng hàm này."""
    source_test = _source_test(db, source_slug)
    source = _source_questions(db, source_test)
    ids = [q.id for q in source]
    type_labels = _labels_of(db, "question_type", ids)
    grammar_labels = _labels_of(db, "grammar", ids)
    chosen: list[Question] = []
    for part in range(1, 8):
        part_qs = [q for q in source if q.part == part]
        chosen.extend(_pick_part(part, part_qs, type_labels, grammar_labels))
    _cover_grammar_by_set(chosen, [q for q in source if q.part == 6], grammar_labels)

    # Định mức 84 câu là cả lập luận §0 của spec (84 → dải ±~75 điểm). Thiếu
    # câu thì bộ chọn thoát êm — một đề 79 câu xuất bản được, và con số ±75 in
    # trên màn kết quả lặng lẽ sai.
    if len(chosen) != TOTAL_QUESTIONS:
        per_part = Counter(q.part for q in chosen)
        raise SystemExit(
            f"lắp ra {len(chosen)} câu, cần {TOTAL_QUESTIONS} — "
            f"đề nguồn {SOURCE_SLUG} thiếu nhãn hoặc thiếu câu: {dict(sorted(per_part.items()))}"
        )
    return source_test, chosen, type_labels, grammar_labels


def describe(
    chosen: list[Question],
    type_labels: dict[UUID, list[str]],
    grammar_labels: dict[UUID, list[str]],
) -> None:
    """In phân bố dạng câu để NGƯỜI DUYỆT nhìn thấy trước khi xuất bản.

    Con số duy nhất từng in ra là tổng số câu mỗi part, mà tổng ấy giống hệt
    nhau dù đề gồm toàn câu tìm-thông-tin hay toàn câu suy luận.
    """
    for part in range(1, 8):
        part_qs = [q for q in chosen if q.part == part]
        counts = Counter(code for q in part_qs for code in type_labels.get(q.id, []))
        print(f"  part {part}: {len(part_qs)} câu")
        for code, n in counts.most_common():
            mark = " ←" if code in PRIORITY.get(part, ()) else ""
            print(f"      {n:>2}  {code}{mark}")
        missing = [c for c in PRIORITY.get(part, ()) if c not in counts]
        if missing:
            # Cảnh báo, không chặn: kho có thể chưa có dạng đó câu nào —
            # `PART_3_IMPLICATION` là mã mới, đề nguồn cũ không có câu nào.
            print(f"      THIẾU dạng khó: {', '.join(missing)}")
    grammar_codes = {code for q in chosen for code in grammar_labels.get(q.id, [])}
    print(f"  nhãn grammar: {len(grammar_codes)} mã")


def build(
    db: Session, publish: bool, slug: str = PLACEMENT_SLUG, source_slug: str = SOURCE_SLUG
) -> None:
    source_test, chosen, type_labels, grammar_labels = select_questions(db, source_slug)

    existing = db.scalar(select(PracticeTest).where(PracticeTest.slug == slug))
    if existing is not None and existing.status == "published":
        raise SystemExit("đề placement đã published — dựng lại là đổi đề dưới chân người học")
    if existing is None:
        existing = PracticeTest(
            slug=slug,
            title=TITLE,
            description=DESCRIPTION,
            kind=KIND,
            time_limit_seconds=TIME_LIMIT_SECONDS,
            # Bảng quy đổi của ĐỀ NGUỒN, không phải `"default"` ghi cứng. Cả lý
            # do chọn path A (spec §1) là "có neo: câu lấy từ form có sẵn
            # `score_conversion` nên quy đổi dựa trên đường cong thật". Hôm nay
            # cả hai đang là `default` nên ghi cứng không lệch — ngày ai đó gắn
            # bảng riêng cho đề nguồn thì placement vẫn quy đổi bằng bảng cũ.
            score_scale_slug=source_test.score_scale_slug,
            is_placement=True,
        )
        db.add(existing)
        db.flush()
    existing.title = TITLE
    existing.description = DESCRIPTION
    existing.is_placement = True
    for row in db.scalars(
        select(PracticeTestQuestion).where(PracticeTestQuestion.test_id == existing.id)
    ):
        db.delete(row)
    for number, question in enumerate(chosen, start=1):
        db.add(
            PracticeTestQuestion(
                test_id=existing.id, question_id=question.id, position=number, number=number
            )
        )
    if publish:
        # KHÔNG lưu trữ các đề cũ nữa. `_placement_test()` giờ rút ngẫu nhiên
        # trong nhóm đang published, nên xuất bản một đề là THÊM vào nhóm chứ
        # không thay chỗ. Muốn bỏ một đề khỏi nhóm thì lưu trữ nó ở
        # `/admin/placement` — một quyết định vận hành, không phải hệ quả kèm
        # theo của việc dựng đề mới.
        existing.status = "published"
    db.commit()

    print(f"{slug}: {len(chosen)} câu ({'published' if publish else 'draft'})")
    describe(chosen, type_labels, grammar_labels)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        default=PLACEMENT_SLUG,
        help="slug đề placement. Đề đã published KHÔNG dựng lại được — đổi đề dưới "
        "chân người học; dùng slug mới, `--publish` sẽ tự lưu trữ đề cũ.",
    )
    parser.add_argument(
        # Nguồn là thứ đổi theo từng lượt dựng, không phải một hằng số của công
        # cụ: mỗi đề mới sinh ra là một nguồn mới có thể lấy. Mặc định giữ đề cũ
        # để lệnh không đổi nghĩa với người đang gõ nó theo thói quen.
        "--source",
        default=SOURCE_SLUG,
        help=f"slug đề nguồn để rút câu (mặc định {SOURCE_SLUG})",
    )
    parser.add_argument("--publish", action="store_true", help="xuất bản sau khi lắp")
    parser.add_argument(
        "--preview", action="store_true", help="chỉ in phân bố dạng câu, không ghi gì"
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.preview:
            _source, chosen, type_labels, grammar_labels = select_questions(db, args.source)
            print(f"{args.slug} ← {args.source}: {len(chosen)} câu (preview, chưa ghi)")
            describe(chosen, type_labels, grammar_labels)
            return
        build(db, publish=args.publish, slug=args.slug, source_slug=args.source)


if __name__ == "__main__":
    main()
