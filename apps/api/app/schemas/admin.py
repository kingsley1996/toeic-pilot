"""Request and response shapes for the content admin surface."""

from pydantic import BaseModel, Field


class TopicCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    position: int = 0


class TopicAdmin(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    position: int
    status: str


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
