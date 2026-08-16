"""Request and response shapes for the content admin surface."""

from datetime import datetime

from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    position: int = 0
    # Không gửi = chủ đề "chưa xếp". Khác với TopicUpdate ở chỗ "" không có nghĩa
    # gì ở đây (PATCH mới cần phân biệt "để nguyên" / "gỡ"), nên không cần quy ước.
    collection_item_id: str | None = None


class TopicAdmin(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    position: int
    status: str
    # Đếm cả nháp: admin nhìn thấy mọi thứ, và con số này trả lời câu "xoá chủ
    # đề này thì chuyện gì xảy ra" trước khi ai đó bấm nút xoá.
    entry_count: int
    collection_item_id: str | None
    collection_item_name: str | None


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    position: int | None = None
    status: str | None = None
    # "" = gỡ chủ đề khỏi cuốn đang chứa; UUID = xếp vào cuốn đó; không gửi =
    # để nguyên (phân biệt qua exclude_unset — không thể dùng `None` vì "gỡ"
    # chính là đặt về None).
    collection_item_id: str | None = Field(default=None)


class VocabularyCollectionCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    position: int = 0


class VocabularyCollectionAdmin(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    position: int
    status: str
    item_count: int


class VocabularyCollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    position: int | None = None
    status: str | None = None


class VocabularyCollectionItemCreate(BaseModel):
    collection_id: str
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    position: int = 0


class VocabularyCollectionItemAdmin(BaseModel):
    id: str
    collection_id: str
    collection_name: str
    name: str
    description: str | None
    position: int
    status: str
    topic_count: int


class VocabularyCollectionItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    position: int | None = None
    status: str | None = None


class ParseRequest(BaseModel):
    raw_text: str


class VocabularyRow(BaseModel):
    line: int
    headword: str
    part_of_speech: str
    phonetic: str | None = None
    meaning_en: str
    meaning_vi: str
    example: str | None = None
    example_vi: str | None = None
    problems: list[str] = []


class DictationRow(BaseModel):
    line: int
    transcript: str
    problems: list[str] = []


class VocabularyParseResponse(BaseModel):
    ok_count: int
    error_count: int
    rows: list[VocabularyRow]


class DictationParseResponse(BaseModel):
    ok_count: int
    error_count: int
    rows: list[DictationRow]


class VocabularyCommit(BaseModel):
    """Rows to write, after review.

    The client sends back the (possibly edited) parse result rather than the raw
    paste, so what gets written is exactly what was on screen.
    """

    rows: list[VocabularyRow]
    topic_id: str | None = None
    difficulty: int = Field(default=3, ge=1, le=5)


class DictationCommit(BaseModel):
    rows: list[DictationRow]
    topic_id: str | None = None
    story_id: str | None = None
    """Story nhận các câu này, nếu có.

    Khi có, mỗi dòng dán vào trở thành một câu CÓ THỨ TỰ trong story — đúng thứ
    tự đã dán, nối tiếp sau những câu đã có. Đó là toàn bộ cách một bài văn được
    nhập: dán cả bài, mỗi dòng một câu.
    """
    difficulty: int = Field(default=3, ge=1, le=5)


class CommitResult(BaseModel):
    created: int
    skipped: int
    problems: list[str]


class AudioSlotState(BaseModel):
    kind: str
    accent: str
    state: str


class VocabularyAdmin(BaseModel):
    id: str
    headword: str
    part_of_speech: str
    meaning_vi: str
    status: str
    # `missing` / `stale` / `current` per required clip. Publishing is blocked
    # unless every one is `current` — a stale clip says the old text out loud.
    audio: list[AudioSlotState]
    publishable: bool


class DictationAdmin(BaseModel):
    id: str
    transcript: str
    difficulty: int
    status: str
    audio_state: str
    publishable: bool
    story_id: str | None = None
    position: int | None = None
    """Vị trí trong bài, hoặc rỗng nếu là câu lẻ.

    Hai trường luôn cùng có hoặc cùng không — CHECK
    `ck_dictation_item_story_position` ép điều đó ở tầng database.
    """


class VocabularyUpdate(BaseModel):
    headword: str | None = None
    phonetic: str | None = None
    meaning_en: str | None = None
    meaning_vi: str | None = None
    example: str | None = None
    example_vi: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)


class DictationUpdate(BaseModel):
    transcript: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    topic_id: str | None = None
    status: str | None = None
    story_id: str | None = None
    """Chuyển câu vào một bài, hoặc `""` để đưa nó ra thành câu lẻ.

    Dùng chuỗi rỗng cho "gỡ khỏi bài" chứ không dùng `null`: với PATCH, `null`
    và "không gửi trường này" là hai ý khác nhau, mà JSON thì không phân biệt
    được nếu client bỏ trống. Chuỗi rỗng nói rõ ý định.

    `position` đi kèm tự động — đặt cuối bài — vì CHECK
    `ck_dictation_item_story_position` đòi hai cột này luôn cùng có hoặc cùng
    không.
    """


# --- cây dictation ---------------------------------------------------------


class DictationTopicCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    position: int = 0


class DictationTopicAdmin(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    position: int
    status: str
    section_count: int


class DictationSectionCreate(BaseModel):
    topic_id: str
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    position: int = 0


class DictationSectionAdmin(BaseModel):
    id: str
    topic_id: str
    topic_name: str
    name: str
    description: str | None
    position: int
    status: str
    story_count: int


class DictationStoryCreate(BaseModel):
    section_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    position: int = 0
    difficulty: int = Field(default=3, ge=1, le=5)


class DictationStoryAdmin(BaseModel):
    id: str
    section_id: str
    section_name: str
    topic_name: str
    title: str
    description: str | None
    position: int
    difficulty: int
    status: str
    item_count: int
    published_item_count: int
    publishable: bool
    """Publish được chưa.

    Một story rỗng hoặc chỉ toàn câu nháp mà lên sóng là một trang trống với học
    viên — hỏng theo kiểu trông như lỗi hệ thống chứ không như nội dung chưa
    xong. Nên cổng đòi ít nhất một câu đã publish.
    """


class DictationTopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    position: int | None = None
    status: str | None = None
    """`draft` · `published` · `archived`.

    `archived` là đường lui cho nội dung đã có người học: gỡ khỏi tầm mắt học
    viên mà không xoá, nên lịch sử làm bài không mồ côi.
    """


class DictationSectionUpdate(BaseModel):
    topic_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    position: int | None = None
    status: str | None = None


class DictationStoryUpdate(BaseModel):
    section_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    position: int | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    status: str | None = None


class StoryReorder(BaseModel):
    item_ids: list[str]
    """Toàn bộ câu của story, theo thứ tự mong muốn.

    Nhận cả danh sách chứ không nhận "đổi chỗ câu A và B": gán lại 1..N trong
    một giao dịch thì không có trạng thái trung gian nào hai câu cùng mang một
    số, và không cần ràng buộc duy nhất trên `(story_id, position)` để chống lại
    chính mình.
    """


# --- đề thi (ADR-007) -------------------------------------------------------


class QuestionOptionDraft(BaseModel):
    label: str
    # `str | None`, không phải `str`. Đây là chỗ lỗi cũ bắt đầu: hình dạng
    # xem-trước không nói được "không in gì", nên trình dán phải bịa ra `""`, mà
    # `validate_question` đòi NULL — Part 1 và 2 không bao giờ ghi vào được.
    content: str | None
    is_correct: bool
    # Bản dịch tiếng Việt, từ dòng `-> …` dưới đáp án.
    content_vi: str | None = None
    # Lời ĐỌC của Part 1/2 — `content` vẫn None ở đó.
    spoken_text: str | None = None


class TurnDraft(BaseModel):
    text: str
    voice: str


class QuestionDraft(BaseModel):
    line: int
    prompt_text: str | None
    options: list[QuestionOptionDraft]
    source: str
    source_note: str | None = None
    explanation: str | None = None
    # Chỉ Part 1 và 2: lời thoại của riêng câu này.
    script: list[TurnDraft] = []
    problems: list[str]


class GroupDraft(BaseModel):
    """Một cụm đã phân tích: ngữ liệu dùng chung và các câu thuộc về nó.

    Part 5 cũng đi qua hình dạng này với đúng một câu và không ngữ liệu, nên
    đường ghi vào database chỉ có một nhánh.
    """

    line: int
    title: str | None = None
    passages: list[str]
    # Chỉ Part 3 và 4: bản thu dùng chung của cả cụm.
    script: list[TurnDraft] = []
    questions: list[QuestionDraft]
    problems: list[str]


class TestPartParseResponse(BaseModel):
    part: int
    ok_count: int
    error_count: int
    groups: list[GroupDraft]


class TestPartCommit(BaseModel):
    part: int
    groups: list[GroupDraft]


class TestCreate(BaseModel):
    slug: str
    title: str
    description: str | None = None
    collection_slug: str | None = None
    kind: str = "full"
    time_limit_seconds: int | None = None


class QuestionAdmin(BaseModel):
    id: str
    part: int
    number: int
    position: int
    prompt_text: str | None
    options: list[QuestionOptionDraft]
    source: str
    explanation: str | None
    status: str
    set_id: str | None
    audio_url: str | None
    image_url: str | None
    audio_script: list[TurnDraft] = []
    audio_attached_at: datetime | None = None
    updated_at: datetime | None = None
    # Câu được sửa SAU khi gắn audio. Không phải cổng chặn — hash của file tải
    # lên không suy ngược ra lời thoại được, nên thứ duy nhất làm được là cho
    # người soạn nhìn thấy (ADR-007 §2.7).
    audio_may_be_stale: bool = False
    # Nhãn kỹ năng KHÔNG còn ở đây. Bộ phân loại thật có sáu mặt và một câu mang
    # nhiều nhãn cùng lúc, nên nó không nhét vừa vài trường vô hướng — nó sống ở
    # `question_label` và được phục vụ qua `/admin/ai/labels`.
    # Vì sao câu này chưa xuất bản được. Rỗng nghĩa là sẵn sàng.
    #
    # Hiện ra thay vì chỉ làm mờ nút Publish: nút mờ nói "chưa được", danh sách
    # này nói "vì sao" — và không có vế thứ hai thì người soạn phải đoán.
    problems: list[str]


class TestPartSummary(BaseModel):
    part: int
    title: str
    section: str
    question_count: int
    published_count: int
    problem_count: int


class TestAdmin(BaseModel):
    id: str
    slug: str
    title: str
    description: str | None
    kind: str
    status: str
    time_limit_seconds: int | None
    collection_slug: str | None
    question_count: int
    parts: list[TestPartSummary]


class CollectionCreate(BaseModel):
    slug: str
    title: str
    description: str | None = None
    source_tag: str | None = None
    year: int | None = None


class CollectionAdmin(BaseModel):
    id: str
    slug: str
    title: str
    description: str | None
    source_tag: str | None
    year: int | None
    status: str
    test_count: int
    published_test_count: int


class TestUpdate(BaseModel):
    """Sửa phần vỏ của đề. `model_dump(exclude_unset=True)` ở nơi gọi.

    Khoá vắng mặt nghĩa là *đừng đụng tới*, khoá bằng null nghĩa là *xoá đi* —
    `collection_slug: null` là cách gỡ đề ra khỏi bộ. Gộp hai thứ đó lại thì
    lệnh gỡ trở thành lệnh không làm gì, và nó trả về 200 nên không ai biết.
    """

    title: str | None = None
    description: str | None = None
    collection_slug: str | None = None
    time_limit_seconds: int | None = None


class QuestionEdit(BaseModel):
    """Sửa một câu sau khi dán. `exclude_unset` ở nơi gọi — xem `TestUpdate`."""

    prompt_text: str | None = None
    explanation: str | None = None
    source: str | None = None
    source_note: str | None = None
    correct_label: str | None = None
    options: dict[str, str] | None = None
    # Bản dịch tiếng Việt theo nhãn đáp án. KHÁC `options` ở một chỗ: nó sửa
    # được ở MỌI part, kể cả Part 1 và 2 — ở đó bản dịch dịch LỜI ĐỌC chứ không
    # dịch chữ in, nên nó có nội dung để dịch trong khi `options` thì không.
    #
    # Chuỗi rỗng nghĩa là XOÁ bản dịch (ghi NULL), khác với vắng mặt là để nguyên.
    translations: dict[str, str] | None = None
    # Chỉ Part 1 và 2. Part 3/4 giữ lời thoại ở cụm, và endpoint từ chối thẳng
    # thay vì ghi vào một cột không ai đọc — xem `edit_question`.
    #
    # Danh sách rỗng nghĩa là XOÁ lời thoại; vắng mặt nghĩa là để nguyên. Phân
    # biệt được là nhờ `exclude_unset`, giống `TestUpdate`.
    audio_script: list[TurnDraft] | None = None


class VoiceOption(BaseModel):
    """Một giọng logic — tên ta đặt, không phải id của nhà cung cấp (A4.3)."""

    name: str
    accent: str


class ArchiveRequest(BaseModel):
    """Cất đi hay lấy lại.

    Lưu trữ chứ không xoá là lối thoát mà lời từ chối 409 chỉ tới, nên nó phải
    bấm được từ đúng chỗ người ta vừa bị từ chối (`CONTENT_STATUSES`).
    """

    archived: bool


class SetEdit(BaseModel):
    """Sửa một cụm sau khi dán — hiện là tên cụm và lời thoại.

    Lời thoại phải sửa được, nếu không sai một chữ là phải xoá cả cụm rồi dán
    lại. Nó cũng là thứ *duy nhất* bản thu tương ứng, nên trước khi có endpoint
    này, cảnh báo `audio_may_be_stale` của Part 3/4 không có gì kích hoạt được.
    """

    title: str | None = None
    audio_script: list[TurnDraft] | None = None


class PassageImageAssign(BaseModel):
    """Gắn hoặc gỡ ảnh cho MỘT ô ngữ liệu.

    `slot` là 1..3, khớp với `passage`/`passage_2`/`passage_3`. `image_id` null
    nghĩa là gỡ ảnh ra.
    """

    slot: int
    image_id: str | None = None


class PassageAdmin(BaseModel):
    slot: int
    text: str | None
    image_id: str | None
    image_url: str | None
    image_alt: str | None


class SetAdmin(BaseModel):
    id: str
    part: int
    title: str | None
    status: str
    passages: list[PassageAdmin]
    audio_url: str | None = None
    audio_script: list[TurnDraft] = []
    audio_attached_at: datetime | None = None
    updated_at: datetime | None = None
    audio_may_be_stale: bool = False


class MediaAssign(BaseModel):
    """Gắn hoặc gỡ một asset. `asset_id` null nghĩa là gỡ ra."""

    asset_id: str | None = None
