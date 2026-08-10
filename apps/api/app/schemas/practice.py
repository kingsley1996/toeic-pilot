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
    passages: list[str]
    options: list[OptionPublic]

    selected_option_id: str | None
    flagged: bool
    # Chỉ có ở chế độ Luyện tập, hoặc sau khi đã nộp.
    correct_option_id: str | None = None
    explanation: str | None = None


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
    parts: list[AttemptPartProgress]
    questions: list[QuestionPublic]


class AnswerSubmit(BaseModel):
    # NULL để bỏ chọn — người làm bài đổi ý và muốn để trống là chuyện bình
    # thường, và ô trống ở cuối part 7 chính là tín hiệu "hết giờ".
    selected_option_id: str | None = None
    flagged: bool | None = None


class AttemptResult(BaseModel):
    id: str
    status: str
    correct_count: int
    question_count: int
    listening_raw: int | None
    reading_raw: int | None
    listening_scaled: int | None
    reading_scaled: int | None
    total_scaled: int | None
    # Vì sao không có điểm quy đổi, khi không có. `scoring.py` từ chối đoán, và
    # giao diện phải nói ra lý do thay vì hiện số 0.
    scale_note: str | None
