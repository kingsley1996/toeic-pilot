from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel

# Tên hiển thị của từng phần. Ở backend chứ không ở frontend: nó cũng là thứ
# trình nhập nội dung và màn quản trị cần, và ba bản sao của cùng một bảng tra
# sẽ lệch nhau ở đúng lúc ai đó sửa một chỗ.
PART_TITLES: dict[int, str] = {
    1: "Photos",
    2: "Question-Response",
    3: "Conversations",
    4: "Talks",
    5: "Incomplete Sentences",
    6: "Text Completion",
    7: "Reading Comprehension",
}

LISTENING_PARTS = (1, 2, 3, 4)

# Khoảng số câu chuẩn của một đề TOEIC 200 câu.
#
# Dùng để GỢI Ý số lúc lắp đề, không phải để suy ra nó: giá trị chốt nằm ở
# `practice_test_question.number` (ADR-007 §2.6). Đề rút gọn sẽ nhảy cóc — một
# câu Part 1 rồi ba câu Part 5 cho ra 1, 101, 102, 103 — và số nhảy cóc phải là
# thứ có người nhìn thấy và đồng ý.
PART_NUMBER_RANGES: dict[int, tuple[int, int]] = {
    1: (1, 6),
    2: (7, 31),
    3: (32, 70),
    4: (71, 100),
    5: (101, 130),
    6: (131, 146),
    7: (147, 200),
}


def suggest_numbers(parts: Sequence[int]) -> list[int]:
    """Số gợi ý cho một danh sách câu hỏi, theo thứ tự xuất hiện.

    Mỗi part đếm từ đầu khoảng của nó. Vượt khoảng thì **ném lỗi** thay vì đếm
    tiếp: câu thứ 7 của Part 1 mang số 7 sẽ đè lên Part 2, và cái đè đó chỉ lộ
    ra ở một `UniqueConstraint` với thông báo không nhắc gì tới part.
    """
    used: dict[int, int] = {}
    numbers: list[int] = []
    for part in parts:
        if part not in PART_NUMBER_RANGES:
            raise ValueError(f"part {part} không hợp lệ")
        first, last = PART_NUMBER_RANGES[part]
        offset = used.get(part, 0)
        if first + offset > last:
            raise ValueError(
                f"Part {part} chỉ có {last - first + 1} chỗ ({first}-{last}), "
                f"đang cố xếp câu thứ {offset + 1}"
            )
        used[part] = offset + 1
        numbers.append(first + offset)
    return numbers


def section_of(part: int) -> str:
    return "listening" if part in LISTENING_PARTS else "reading"


class PartBreakdown(BaseModel):
    """Một dòng của bảng SECTION / PART / TYPE / QUESTIONS."""

    part: int
    section: str
    title: str
    question_count: int
    # Số câu ĐANG CÓ nội dung, không phải số câu đề thi thật sẽ có. Một part hiện
    # 0 câu là thông tin thật — nó nói rằng phần đó chưa nhập được, và giao diện
    # phải nói ra điều đó thay vì im lặng bỏ qua (Part 2 và 3 chờ §10.2).
    has_content: bool


class TestSummary(BaseModel):
    id: str
    slug: str
    title: str
    description: str | None
    kind: str
    time_limit_seconds: int | None
    question_count: int
    attempt_count: int


class TestDetail(TestSummary):
    parts: list[PartBreakdown]


class CollectionSummary(BaseModel):
    id: str
    slug: str
    title: str
    description: str | None
    source_tag: str | None
    year: int | None
    test_count: int
    attempt_count: int


class CollectionDetail(CollectionSummary):
    tests: list[TestSummary]


class AttemptStart(BaseModel):
    test_slug: str
    review_mode: str = "exam"
    # Rỗng = làm CẢ ĐỀ. Khớp với schema: `scope='full'` thì `attempt_part` rỗng,
    # nên không phải liệt kê đủ bảy part để nói "làm tất".
    parts: list[int] = []


class OptionPublic(BaseModel):
    id: str
    label: str
    # NULL ở part 1 và 2 — ETS không in đáp án của hai part đó, chỉ đọc lên.
    content: str | None
    # Hai trường dưới đây CHỈ có khi được phép lộ: chế độ Luyện tập, hoặc sau
    # khi đã nộp. Cùng luật đang áp cho `correct_option_id` và `explanation`.
    #
    # Gửi bản dịch lúc đang thi là làm hỏng chính thứ bài thi đo: một câu từ
    # vựng Part 5 chỉ cần đọc bản dịch là chọn được, và điểm số thôi so sánh
    # được với đề thật.
    content_vi: str | None = None
    # Lời đọc của Part 1/2. Lộ nó lúc đang làm bài là in đáp án của một phần
    # kiểm kỹ năng NGHE ra màn hình.
    spoken_text: str | None = None


class PassagePublic(BaseModel):
    """Một ô ngữ liệu: văn bản, ảnh, hoặc cả hai.

    Là một object chứ không phải một chuỗi, vì ngữ liệu Part 7 có thể là một
    biểu đồ — và một biểu đồ không nhét vào `list[str]` được mà không mất đúng
    những thứ đi kèm nó: chữ thay ảnh, và dòng ghi công.
    """

    text: str | None
    image_url: str | None
    # Bắt buộc khi có ảnh. Một biểu đồ không có chữ thay ảnh là một câu hỏi mà
    # người dùng máy đọc màn hình KHÔNG trả lời được — khác hẳn ảnh Part 1, nơi
    # nội dung ảnh chính là thứ không được mô tả quá kỹ.
    image_alt: str | None
    image_attribution: str | None
    image_license: str | None


class TranscriptTurn(BaseModel):
    """Một lượt nói trong lời thoại phần Nghe.

    Giữ theo LƯỢT chứ không nối thành một chuỗi: một hội thoại Part 3 có hai tới
    ba người, và "ai nói câu nào" chính là thứ phần lớn câu hỏi Part 3 hỏi tới.
    Nối phẳng là vứt đi đúng thông tin người học cần khi đọc lại.

    `speaker` là nhãn để HIỆN ("Man", "Woman 2"), suy từ tên giọng logic ở máy
    chủ. Gửi thẳng `uk_female_1` xuống là bắt giao diện học một quy ước đặt tên
    của phía offline, và quy ước đó đổi thì giao diện hỏng lặng lẽ.
    """

    speaker: str
    text: str


class QuestionPublic(BaseModel):
    """Một câu như người làm bài nhìn thấy.

    **Không có `is_correct`.** Đây là điểm khác hẳn dictation: `DictationDetail`
    cố ý gửi cả đáp án xuống trình duyệt vì chấm ở client cho phản hồi tức thì,
    và tài liệu ghi rõ điều đó chấp nhận được cho tự học nhưng **không** cho thứ
    gì được chấm điểm. Bài thi thử thì được chấm điểm, và điểm đó nằm lại trong
    lịch sử của người học — nên đáp án chỉ rời máy chủ khi bài đã nộp, hoặc khi
    người dùng tự chọn chế độ Luyện tập.
    """

    number: int
    id: str
    part: int
    prompt_text: str | None
    audio_url: str | None
    image_url: str | None
    image_alt: str | None
    # Ghi công BẮT BUỘC đi kèm ảnh, không phải trường trang trí.
    #
    # Phần lớn ảnh mở là CC-BY: được dùng *với điều kiện* ghi công. `image_asset`
    # để `license`/`attribution` NOT NULL chính vì thế, nhưng lưu lại thôi chưa
    # đủ — endpoint nào phục vụ ảnh cũng phải trả kèm, và giao diện phải hiện ra
    # (ADR-004 §4.2). Lưu mà không hiện vẫn là vi phạm giấy phép.
    image_attribution: str | None
    image_license: str | None
    # Ngữ liệu dùng chung. Lặp lại trên từng câu của cụm sẽ tốn băng thông và
    # buộc client tự khử trùng lặp, nên chỉ câu ĐẦU của cụm mang nó.
    set_id: str | None
    set_title: str | None
    passages: list[PassagePublic]
    options: list[OptionPublic]

    selected_option_id: str | None
    flagged: bool
    # Chỉ có ở chế độ Luyện tập, hoặc sau khi đã nộp.
    correct_option_id: str | None = None
    explanation: str | None = None
    # Lời thoại phần Nghe, cùng cổng với `correct_option_id` — xem `attempt.py`.
    #
    # Với Part 3 và 4 nó thuộc về CẢ CỤM chứ không một câu, nên nó chỉ về khi
    # MỌI câu của cụm đã được trả lời: lộ hội thoại sau câu đầu là lộ luôn đáp
    # án hai câu sau, và cụm mất hai phần ba giá trị của nó.
    transcript: list[TranscriptTurn] = []


class AttemptPartProgress(BaseModel):
    part: int
    title: str
    section: str
    answered: int
    total: int
    first_number: int
    last_number: int


class AttemptState(BaseModel):
    id: str
    test_slug: str
    test_title: str
    review_mode: str
    scope: str
    status: str
    time_limit_seconds: int | None
    # Còn lại bao nhiêu giây, do MÁY CHỦ tính. Trình duyệt đếm ngược cho mượt
    # nhưng không phải nguồn sự thật: đồng hồ máy khách chỉnh được, và một bài
    # thi tin vào nó là một bài thi không có giới hạn thời gian.
    remaining_seconds: int | None
    answered_count: int
    question_count: int
    # Thời gian đã dùng, cộng dồn qua các lần tạm dừng — KHÔNG suy ra từ
    # `now() - started_at`, vì lượt làm tạm dừng được và đồng hồ treo tường sẽ
    # ăn mất thời gian người học không hề ngồi trước màn hình.
    elapsed_seconds: int
    parts: list[AttemptPartProgress]
    questions: list[QuestionPublic]


class AnswerSubmit(BaseModel):
    # NULL để bỏ chọn — người làm bài đổi ý và muốn để trống là chuyện bình
    # thường, và ô trống ở cuối part 7 chính là tín hiệu "hết giờ".
    selected_option_id: str | None = None
    flagged: bool | None = None


class AttemptSummary(BaseModel):
    """Một lượt làm bài trong danh sách lịch sử.

    Cố ý KHÔNG mang danh sách câu: một trang lịch sử vài chục lượt mà mỗi lượt
    kéo theo hai trăm câu là vài megabyte cho một màn hình chỉ cần mấy con số.
    Muốn xem câu thì mở lượt đó ra.
    """

    id: str
    test_slug: str
    test_title: str
    collection_slug: str | None
    status: str
    scope: str
    review_mode: str
    started_at: datetime
    submitted_at: datetime | None
    question_count: int
    answered_count: int
    # NULL khi bài chưa nộp — số câu đúng của một bài đang làm dở là thông tin
    # không được phép có, vì nó chính là đáp án.
    correct_count: int | None
    total_scaled: int | None
    # Còn bao nhiêu giây, cho lượt đang dở. Đây là lý do khối "đang làm dở" tồn
    # tại trên trang chủ: đồng hồ chạy ở máy chủ dù người học đã đóng tab.
    remaining_seconds: int | None


class AttemptResult(BaseModel):
    id: str
    status: str
    correct_count: int
    question_count: int
    elapsed_seconds: int
    listening_raw: int | None
    reading_raw: int | None
    listening_scaled: int | None
    reading_scaled: int | None
    total_scaled: int | None
    # Vì sao không có điểm quy đổi, khi không có. `scoring.py` từ chối đoán, và
    # giao diện phải nói ra lý do thay vì hiện số 0.
    scale_note: str | None
