"""Trình dán đề thi: Part 5, 6, 7 (ADR-007 §2.3).

Không có database ở đây, đúng theo ADR-005: parse là hàm thuần, và bước xem
trước tồn tại chính vì nó chưa ghi gì.
"""

import unicodedata

import pytest

from app.services.content_import import parse_listening_part, parse_reading_part

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


# --- phần Nghe: Part 1-4 ----------------------------------------------------

PART1 = """[QUESTION]
voice: us_female_1
Look at the picture marked number one in your test book.
(A) The woman is sitting at a picnic table.
(B) The woman is reading a newspaper.
(C) The woman is loading a truck.
(D) The woman is walking along a path.
answer: A
source: original
"""


def test_part_1_and_2_put_their_text_in_the_script_not_on_screen():
    """ETS nói rõ: lời dẫn và các câu đáp của Part 1, 2 chỉ được ĐỌC LÊN.

    Nên `prompt_text` phải rỗng và `content` của đáp án phải rỗng — đó là giá
    trị ĐÚNG (ADR-001 §A2), không phải dữ liệu thiếu. Trình dán không được nới
    lỏng hơn `validate_question`, thứ sẽ từ chối một câu Part 1 có đề bài.
    """
    (group,) = parse_listening_part(PART1, 1)
    (question,) = group.questions
    assert group.ok
    # `None`, KHÔNG phải `""`. Bản đầu của test này ghim `""` và đó là lý do lỗi
    # sống sót: `validate_question` hỏi `is not None`, nên `""` đọc ra là "có in,
    # in ra số 0 ký tự" và mọi câu Part 1/2 bị từ chối ở bước ghi. Hai nửa mỗi
    # nửa xanh theo test của riêng nó, và không test nào đi qua ranh giới.
    assert question.prompt_text is None
    assert [option.content for option in question.options] == [None, None, None, None]
    # Lời dẫn + bốn câu đọc, tất cả cùng một giọng.
    assert len(question.script) == 5
    assert {turn.voice for turn in question.script} == {"us_female_1"}

    # Lời thoại phải mang CẢ NHÃN. Người thi Part 1 không đọc gì cả, nên bản thu
    # chỉ đọc bốn câu liền nhau là không có cách nào biết câu vừa nghe là (A) hay
    # (C) — cả câu hỏi trở thành không trả lời được, và không phép kiểm nào trong
    # hệ thống thấy: hàng dữ liệu vẫn đúng, `validate_question` vẫn OK, chỉ có
    # người bấm play mới biết. Đây là chỗ duy nhất nhãn đi vào được bản thu.
    spoken = [turn.text for turn in question.script[1:]]
    assert [text[:3] for text in spoken] == ["(A)", "(B)", "(C)", "(D)"]
    # …nhưng `spoken_text` trên đáp án vẫn là câu TRẦN, không nhãn: nó trả lời
    # "đáp án A nói gì", và giao diện đã in nhãn ở chỗ khác rồi.
    assert not any((option.spoken_text or "").startswith("(") for option in question.options)


def test_part_2_has_three_options_and_switches_voice_midway():
    raw = """[QUESTION]
voice: us_female_1
Where did you put the sales report?
voice: uk_male_1
(A) On your desk, next to the printer.
(B) Yes, I finished it last night.
(C) About thirty copies, I think.
answer: A
source: original
"""
    (group,) = parse_listening_part(raw, 2)
    (question,) = group.questions
    assert group.ok
    assert len(question.options) == 3
    # Câu hỏi một giọng, ba câu đáp giọng khác — đúng format Part 2.
    assert [turn.voice for turn in question.script] == [
        "us_female_1",
        "uk_male_1",
        "uk_male_1",
        "uk_male_1",
    ]


def test_a_part_3_group_pasted_without_a_script_is_accepted():
    """Part 3 và 4 gắn bản thu dùng chung ở `question_set` (ADR-001 §A4.3),
    nhưng bản thu thường gắn SAU khi dán bằng `import_media` — nên `[SCRIPT]`
    lúc dán là TUỲ CHỌN, không còn bắt buộc. Cổng chặn đầy đủ (thiếu audio thì
    không xuất bản được) nằm ở bước xuất bản với `validate_question`.
    """
    raw = """[QUESTION]
What is the woman calling about?
(A) A late delivery
(B) A billing error
(C) A product return
(D) A price change
answer: A
source: original
"""
    (group,) = parse_listening_part(raw, 3)
    assert not any("[SCRIPT]" in problem for problem in group.problems)
    assert group.ok


def test_a_script_line_without_a_voice_is_refused():
    # Giọng là một phần của bản thu, không phải chi tiết trang trí: thiếu nó thì
    # không ai biết bản thu phải nghe như thế nào.
    (group,) = parse_listening_part(PART1.replace("voice: us_female_1\n", ""), 1)
    assert not group.ok


def test_a_pasted_part_1_question_passes_the_gate_it_will_meet_at_commit() -> None:
    """Trình dán và cổng chặn phải đồng ý với nhau về "không in gì".

    Đây là test đi qua RANH GIỚI, và là thứ đã thiếu. `parse_listening_part` có
    test riêng, `validate_question` có test riêng, cả hai xanh — trong khi cái
    thứ nhất sinh ra `""` còn cái thứ hai đòi `None`, nên Part 1 chưa bao giờ
    ghi vào được. Lỗi chỉ lộ ra khi có người thật dán một câu Part 1.

    Lọc bỏ lỗi thiếu media đúng như `commit_part` làm: lúc vừa dán thì chưa ai
    gắn được audio hay ảnh.
    """
    from app.models import Question, QuestionOption
    from app.models.validators import validate_question

    (group,) = parse_listening_part(PART1, 1)
    (draft,) = group.questions
    assert group.ok

    question = Question(
        part=1,
        prompt_text=draft.prompt_text,
        source=draft.source,
        options=[
            QuestionOption(label=o.label, content=o.content, is_correct=o.is_correct)
            for o in draft.options
        ],
    )
    problems = [
        problem
        for problem in validate_question(question)
        if "audio" not in problem and "photograph" not in problem
    ]
    assert problems == []


# --- dòng dịch nghĩa `->` --------------------------------------------------


def test_dong_dich_gan_vao_dung_dap_an_ngay_tren_no() -> None:
    """Phần Đọc: mỗi `->` thuộc về đáp án đứng ngay trên."""
    groups = parse_reading_part(
        "[QUESTION]\n"
        "The report ____ yesterday.\n"
        "(A) reviewed\n"
        "-> đã xem xét\n"
        "(B) was reviewed\n"
        "-> đã được xem xét\n"
        "(C) reviewing\n"
        "(D) review\n"
        "answer: B\n"
        "source: original\n",
        part=5,
    )
    options = groups[0].questions[0].options
    assert [o.content_vi for o in options] == ["đã xem xét", "đã được xem xét", None, None]


def test_mui_ten_that_cung_duoc_nhan() -> None:
    """Người soạn hay dán `→` từ tài liệu khác — bác nó là bắt gõ lại tay."""
    groups = parse_reading_part(
        "[QUESTION]\nX ____ Y.\n(A) a\n→ chữ a\n(B) b\n(C) c\n(D) d\nanswer: A\nsource: original\n",
        part=5,
    )
    assert groups[0].questions[0].options[0].content_vi == "chữ a"


def test_dong_dich_LAC_CHO_bi_bao_loi_chu_khong_gan_tham() -> None:
    """Gắn vào đáp án gần nhất thì bản dịch hiện dưới câu khác, và không gì báo.

    Một dòng `->` trước bất kỳ đáp án nào là người soạn gõ nhầm chỗ; nói ra ngay
    rẻ hơn nhiều so với để họ phát hiện lúc học viên đọc.
    """
    with pytest.raises(ValueError, match="ngay dưới một đáp án"):
        parse_reading_part(
            "[QUESTION]\n-> dịch trước khi có đáp án\n(A) a\n(B) b\n(C) c\n(D) d\n"
            "answer: A\nsource: original\n",
            part=5,
        )


def test_part_2_giu_content_NULL_nhung_van_luu_loi_doc_va_ban_dich() -> None:
    """Bất biến của ADR-001 §A2 không được lung lay vì tính năng mới.

    Part 2 không in gì — `content` phải là None, nếu không `validate_question`
    từ chối và cả phần đó không ghi vào được. Lời đọc đi vào `spoken_text`, một
    cột mang nghĩa khác hẳn, nên chế độ Luyện tập hiện lại được mà bài thi thật
    vẫn không lộ chữ nào.
    """
    groups = parse_listening_part(
        "[QUESTION]\n"
        "Where is the nearest pharmacy?\n"
        "(A) On Fifth Street.\n"
        "-> Ở phố Năm.\n"
        "(B) Yes, I think so.\n"
        "-> Vâng, tôi nghĩ vậy.\n"
        "(C) At three o'clock.\n"
        "-> Lúc ba giờ.\n"
        "answer: A\n"
        "source: original\n",
        part=2,
    )
    options = groups[0].questions[0].options
    assert [o.content for o in options] == [None, None, None]
    assert [o.spoken_text for o in options] == [
        "On Fifth Street.",
        "Yes, I think so.",
        "At three o'clock.",
    ]
    assert options[0].content_vi == "Ở phố Năm."
    # Lời đọc vẫn phải vào lời thoại để TTS sinh audio — hai chỗ, hai mục đích.
    # Trong lời thoại nó mang thêm NHÃN, vì đề thi thật đọc nhãn lên: người thi
    # không đọc gì cả, nên không có nhãn thì không biết câu vừa nghe là câu nào.
    # `spoken_text` ở trên vẫn là câu trần — nó trả lời một câu hỏi khác.
    assert "(A) On Fifth Street." in [turn.text for turn in groups[0].questions[0].script]
