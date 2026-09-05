"""Response and request shapes for the Learning Hub.

IDs and timestamps are strings, matching `app/schemas/auth.py`: the generated
TypeScript then gets `string` for both, which is what the frontend wants anyway
since JSON has neither a UUID nor a date type.
"""

import uuid

from pydantic import BaseModel, Field, model_validator

from app.services.srs import GRADES


class TopicPublic(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    position: int
    # Số từ đã xuất bản trong chủ đề. Trang chủ đề của học viên là một lưới
    # card và con số này là câu trả lời cho "vào đây có gì để học" — một chủ đề
    # 0 từ phải nói thẳng điều đó thay vì mở ra một trang trống.
    entry_count: int
    # Cuốn sách chứa chủ đề này (collection → collection_item → topic).
    # NULL = chủ đề chưa được xếp vào cuốn nào; màn từ vựng liệt kê chúng riêng.
    collection_item_id: str | None = None


class VocabularyCollectionItemPublic(BaseModel):
    id: str
    name: str
    description: str | None
    position: int
    topic_count: int


class VocabularyCollectionPublic(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    position: int
    topic_count: int


class VocabularyCollectionDetail(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    position: int
    items: list[VocabularyCollectionItemPublic]


class VocabularyItemDetail(BaseModel):
    id: str
    name: str
    description: str | None
    position: int
    topics: list[TopicPublic]
    # Cha của tầng này — cần cho breadcrumb "Từ vựng → <tuyển tập> → <cuốn sách>".
    collection_id: str
    collection_name: str


class AudioClip(BaseModel):
    accent: str
    url: str
    duration_ms: int


class VocabularySummary(BaseModel):
    id: str
    headword: str
    part_of_speech: str
    phonetic: str | None
    meaning_vi: str


class VocabularyDetail(VocabularySummary):
    meaning_en: str
    example: str | None
    example_vi: str | None
    cefr_level: str | None
    difficulty: int
    # Four accents each, keyed by kind. Empty when the pipeline has not caught up
    # yet — but a published entry always has them, because publishing is blocked
    # until every clip exists and matches the text.
    headword_audio: list[AudioClip]
    example_audio: list[AudioClip]


class VocabularyMastery(BaseModel):
    """Trạng thái của một học viên trên MỘT từ."""

    entry_id: str
    # `new` / `learning` / `mastered` — suy ra từ `interval_days`, xem
    # `srs.mastery`. Không có cột nào lưu giá trị này.
    mastery: str
    # Tách khỏi `mastery` vì hai chuyện khác nhau: một từ đã thuộc vẫn đến hạn
    # ôn lại, và một từ đang học thì chưa chắc đến hạn hôm nay.
    is_due: bool


class VocabularyProgress(BaseModel):
    """Tiến độ từ vựng của học viên, theo chủ đề hoặc trên toàn bộ.

    Suy ra từ `vocabulary_review_state` chứ không đọc bảng tiến độ nào — cùng lý
    do đã ghi ở [`StoryProgress`]: một bảng ghi song song sẽ lệch khỏi lịch sử ôn
    tập mà không có gì phát hiện ra.

    Đây là endpoint RIÊNG, có auth, chứ không phải thêm cột vào `GET /vocabulary`
    vốn là endpoint công khai. Nhét trạng thái người dùng vào đó thì với khách
    chưa đăng nhập, mọi từ sẽ mang giá trị `new` — một lời nói dối, chứ không
    phải "chưa có dữ liệu".
    """

    total: int
    new: int
    learning: int
    mastered: int
    due: int
    entries: list[VocabularyMastery]


class VocabularyTopicProgress(BaseModel):
    """Tiến độ của MỘT chủ đề, gọn tới mức đủ cho danh sách chủ đề.

    Tách khỏi [`VocabularyProgress`] vì nó trả lời một câu hỏi khác: kia là "chủ
    đề đang mở đi tới đâu" và kèm trạng thái từng từ, còn đây là "trong mười bốn
    chủ đề của cuốn sách, cái nào đã xong". Gọi endpoint kia mười bốn lần cũng ra
    câu trả lời, kèm mười bốn danh sách từ mà không ai vẽ ra.

    Cùng cặp trường `total`/`new` với [`VocabularyProgress`] chứ không phải một
    trường `done` tính sẵn: thanh tiến độ trên trang đó đọc `total - new`, và một
    định nghĩa "xong" thứ hai tính ở máy chủ sẽ lệch khỏi thanh ấy vào đúng ngày
    một trong hai bên đổi.
    """

    slug: str
    total: int
    new: int


class TopicSessionSubmit(BaseModel):
    """Lưu lại bàn cờ của một chủ đề cho học viên.

    `entry_ids` là THỨ TỰ HỌC của ván (không phải tập hợp), `position` là chỉ
    số của từ đang học trong danh sách đó — bằng `len(entry_ids)` khi đã chấm
    xong cả ván. Hai invariant này được kiểm ở đây để không bao giờ lọt một bàn
    cờ trỏ ra ngoài mảng vào DB.
    """

    entry_ids: list[uuid.UUID]
    position: int = Field(ge=0)

    @model_validator(mode="after")
    def _position_within_board(self) -> "TopicSessionSubmit":
        if self.position > len(self.entry_ids):
            raise ValueError("position must not exceed the number of entries")
        return self


class TopicSession(TopicSessionSubmit):
    """Bàn cờ đã lưu, trả lại cho client nối tiếp ván đang dở.

    `done` suy ra từ `position` so với chiều dài mảng — không lưu thành cột, vì
    một giá trị lưu song song sẽ lệch khỏi cặp (entry_ids, position) ngay lần ghi
    đầu tiên quên cập nhật cả hai.
    """

    done: bool


class TopicSessionSummary(BaseModel):
    """Một ván đang lưu, kèm đủ ngữ cảnh để dựng lối "học tiếp" mà không phải
    gọi thêm hai endpoint nữa.

    KHÔNG trả `entry_ids`. Danh sách đó dài bằng cả chủ đề (40–50 id) và chỉ có
    ích cho màn đang học; nhét nó vào một danh sách để hiện một dòng "còn 12/42
    từ" là gửi vài nghìn ký tự cho một con số.

    `collection_item_*` là NULL được: `topic.collection_item_id` nullable, nên
    một chủ đề chưa xếp vào cuốn sách nào vẫn có ván học hợp lệ. Phía đọc phải
    rơi về tên chủ đề, không được coi cuốn sách là chắc chắn có.
    """

    topic_id: uuid.UUID
    topic_slug: str
    topic_name: str
    collection_item_id: uuid.UUID | None
    collection_item_name: str | None
    total: int
    position: int
    done: bool


class ReviewCard(VocabularyDetail):
    """A card in a review session.

    `is_new` drives the daily new-card cap: without knowing which cards are new,
    the session cannot enforce a limit, and an uncapped queue of new words builds
    a review debt the learner meets a fortnight later.
    """

    is_new: bool


class ReviewSession(BaseModel):
    due_count: int
    new_count: int
    cards: list[ReviewCard]


class ReviewDueCount(BaseModel):
    """Chỉ một con số, và đó là toàn bộ lý do nó tồn tại.

    Huy hiệu trên thanh điều hướng cần con số này ở MỌI trang. Hai endpoint sẵn
    có đều trả về nó nhưng kèm theo quá nhiều thứ khác: `/vocabulary-progress`
    gửi kèm một hàng cho mỗi từ đã xuất bản, `/profile/stats` gửi kèm lịch 365
    ngày. Gọi một trong hai ở mỗi lần đổi trang là trả giá lớn cho một con số.

    **Và `ReviewSession.due_count` không dùng được**: nó đếm số thẻ TRONG LÔ,
    mà lô bị chặn bởi `limit`. Người có 150 từ đến hạn sẽ thấy 100 — sai một
    cách im lặng, vì con số vẫn hợp lý.
    """

    due: int


class ReviewSubmit(BaseModel):
    # 0 forgot · 3 hard · 4 good · 5 easy · 6 mastered. SM-2's 1 and 2 are
    # rejected: the button UI cannot produce them, so accepting them would record
    # something the learner never clicked.
    grade: int = Field(description=f"One of {list(GRADES)}")


class PetReward(BaseModel):
    """Con thú vừa nhận được gì từ lượt học này.

    Máy chủ nói ra, giao diện không tự tính. Trần XP ngày và mức trần 1.0 của
    tinh thần đều có thể cắt bớt, nên một lượt "đáng" 8 XP có thể chỉ ghi được 2
    — và cái toast phải nói đúng con số đã ghi.

    `null` ở nơi dùng nghĩa là lượt này không cấp gì (đã kịch trần, hoặc người
    học chưa từng mở góc thú cưng).
    """

    xp: int
    # Chuỗi chứ không phải float, cùng lý do `ease_factor` là chuỗi: ba chỉ số
    # lưu `Numeric(4,3)` và đọc ra là `Decimal`; đi qua float là thêm một lần
    # làm tròn ở mỗi biên.
    mood: str
    ruby: int = 0


class ReviewResult(BaseModel):
    entry_id: str
    grade: int
    interval_days: int
    repetitions: int
    lapses: int
    ease_factor: str
    due_at: str
    pet: PetReward | None = None


class RecallSubmit(BaseModel):
    """Một lần gõ lại từ."""

    typed: str = Field(description="Nguyên văn học viên gõ, không chuẩn hoá trước")
    # Thứ DUY NHẤT người học còn tự khai — và chỉ có tác dụng khi bài gõ đã
    # đúng. Nói "dễ" trong lúc viết sai không nâng được điểm: server kiểm trước
    # rồi mới xét cờ này.
    easy: bool = False
    # "Tôi chưa biết" — bỏ qua việc chấm và ghi thẳng điểm 0. Không có nó thì
    # người học buộc phải bịa một câu trả lời để đi tiếp.
    give_up: bool = False


class RecallCheckSubmit(BaseModel):
    """Một lần gõ NHỜ CHẤM, chưa ghi điểm.

    Khác `RecallSubmit` ở chỗ KHÔNG có `easy`: điểm SM-2 ở đây là năm nút
    học viên tự chọn SAU khi thấy kết quả, không phải hai trạng thái easy/không.
    """

    typed: str = Field(description="Nguyên văn học viên gõ, không chuẩn hoá trước")
    give_up: bool = False


class RecallCheck(BaseModel):
    """Kết quả chấm gõ-đúng/sai, KHÔNG ghi lượt ôn nào.

    Phục vụ luồng học theo chủ đề: máy chấm xong, học viên nhìn câu trả lời
    thật rồi mới tự chấm mức độ nhớ bằng năm nút chuẩn. Ghi điểm ở đây sẽ làm
    từ đó bị tính hai lần trong cùng một lượt.
    """

    verdict: str
    expected: str
    typed: str


class RecallResult(ReviewResult):
    """Kết quả chấm + lượt ôn đã ghi.

    Kế thừa `ReviewResult` vì một lần gõ lại CHÍNH LÀ một lượt ôn: nó chạy qua
    đúng SM-2 đó và ghi đúng `vocabulary_review_log` đó. Khác biệt duy nhất là
    điểm do máy suy ra thay vì do người học tự bấm.
    """

    # `correct` / `typo` / `wrong` / `unknown` — `unknown` là học viên tự nói
    # chưa biết, khác với đoán sai.
    verdict: str
    # Dạng đã chuẩn hoá của mục từ, trả về để giao diện đối chiếu từng ký tự.
    expected: str
    typed: str


class DictationSummary(BaseModel):
    id: str
    difficulty: int
    topic_id: str | None
    # Word count rather than the transcript: sending the answer to the browser
    # before the learner types would make the exercise pointless.
    word_count: int


class DictationDetail(DictationSummary):
    audio_url: str
    duration_ms: int
    # Bản dịch đi CÙNG lời thoại, không đi riêng: nó nằm trong cùng một khối
    # trên giao diện, nên tách ra thành một lượt gọi nữa chỉ để lộ ra sau.
    # `None` = câu chưa dịch, và khối đó chỉ hiện tiếng Anh.
    transcript_vi: str | None = None
    transcript: str
    """The answer key, sent to the browser on purpose.

    Grading runs on the client so feedback is instant, which means the answer is
    readable in the network tab before the learner types. That is a deliberate
    trade for a self-study tool: the only person the shortcut cheats is the
    learner. It is **not** acceptable for anything scored competitively — if
    dictation ever becomes part of a graded test, this field has to go and the
    grading has to move back behind the API.
    """


class DictationSubmit(BaseModel):
    submitted_text: str


class WordDiff(BaseModel):
    op: str
    word: str


class DictationResult(BaseModel):
    attempt_id: str
    accuracy: str
    matched: int
    expected: int
    transcript: str
    diff: list[WordDiff]
    pet: PetReward | None = None
    is_complete: bool
    """Đã gõ đúng từng từ, không thiếu không thừa.

    `accuracy` vẫn được trả về và vẫn được lưu — nó là lịch sử, và bỏ đi thì
    không tính lại được. Nhưng giao diện không hiện nó nữa: câu trả lời người
    học cần là "đúng chưa", không phải "được bao nhiêu phần trăm".
    """


# --- cây dictation: topic -> section -> story -> item ---------------------


class StoryProgress(BaseModel):
    """Tiến độ của một học viên trên một story: đã làm đúng bao nhiêu câu.

    Suy ra từ `dictation_attempt` chứ không đọc từ bảng tiến độ nào: một bảng ghi
    song song sẽ lệch khỏi lịch sử làm bài mà không có gì phát hiện.

    Không còn điểm trung bình. Dictation đo được đúng một chuyện một cách đáng
    tin — nghe ra hay chưa — và một con số như "89%" không nói cho người học biết
    nên đi tiếp hay nghe lại. "3/6 câu đã xong" thì nói được.
    """

    total_items: int
    completed_items: int


class DictationTopicPublic(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    section_count: int


class DictationSectionPublic(BaseModel):
    id: str
    name: str
    description: str | None
    story_count: int


class DictationTopicDetail(DictationTopicPublic):
    sections: list[DictationSectionPublic]


class DictationStorySummary(BaseModel):
    id: str
    title: str
    description: str | None
    difficulty: int
    progress: StoryProgress


class DictationSectionDetail(DictationSectionPublic):
    topic_id: str
    topic_name: str
    stories: list[DictationStorySummary]


class StoryItem(BaseModel):
    """Một câu trong story, kèm việc học viên đã làm đúng nó hay chưa."""

    id: str
    position: int
    word_count: int
    audio_url: str
    duration_ms: int
    transcript: str
    transcript_vi: str | None = None
    completed: bool


class DictationStoryDetail(BaseModel):
    id: str
    title: str
    description: str | None
    difficulty: int
    section_id: str
    section_name: str
    topic_id: str
    topic_name: str
    items: list[StoryItem]
    progress: StoryProgress


# --- G3: luyện tập cuối chủ đề ----------------------------------------------


class GrammarPracticeOption(BaseModel):
    id: str
    label: str
    content: str | None


class GrammarPracticeQuestion(BaseModel):
    """Một câu rút theo nhãn. Không `is_correct` — đáp án chỉ rời máy chủ khi nộp."""

    id: str
    part: int
    prompt_text: str | None
    options: list[GrammarPracticeOption]
    completed: bool
    """Đã từng trả lời đúng ít nhất một lần — suy từ `grammar_attempt`."""


class GrammarPracticeSubmit(BaseModel):
    question_id: str
    option_id: str


class GrammarPracticeResult(BaseModel):
    is_correct: bool
    correct_option_id: str
    explanation: str | None


# --- ngữ pháp (SPEC-GRAMMAR G2) ---------------------------------------------


class GrammarTopicPublic(BaseModel):
    id: str
    code: str | None
    """Null với bài nền tảng ngoài taxonomy — UI phải ẩn lối "Luyện tập" theo
    nhãn khi thấy null, đừng để người học bấm vào một màn 404."""

    slug: str
    title: str
    summary: str | None
    lesson_count: int
    completed_lesson_count: int = 0
    """Số bài người học đã bấm Hoàn thành — 0 khi vô danh. Chủ đề được tính là
    hoàn thành khi hai con số này bằng nhau và lớn hơn 0."""


class GrammarLessonSummary(BaseModel):
    id: str
    slug: str
    title: str
    kind: str
    position: int
    completed: bool


class GrammarTopicDetail(GrammarTopicPublic):
    lessons: list[GrammarLessonSummary]


class GrammarNextTopic(BaseModel):
    """Chủ đề kế tiếp CÓ ít nhất một bài đã publish — đích đến của bài cuối topic."""

    topic_id: str
    topic_title: str
    lesson_id: str
    lesson_title: str


class GrammarLessonDetail(BaseModel):
    id: str
    topic_id: str
    topic_title: str
    slug: str
    title: str
    kind: str
    body: str
    """Rỗng với practice — nội dung của nó là `questions`."""

    questions: list[GrammarPracticeQuestion] = []
    """Chỉ dựng cho lesson `practice`: câu từ bảng nối, `completed` từng câu suy
    từ `grammar_attempt`. Lesson theory luôn rỗng."""

    completed: bool = False
    """Dấu tay "Hoàn thành" — cả hai loại lesson, người học tự bấm."""

    next_lesson: GrammarLessonSummary | None = None
    """Bài kế theo `position` trong cùng chủ đề — thanh sticky cần nó để không
    phải tải cả cây chủ đề chỉ để biết đi đâu tiếp."""

    next_topic: GrammarNextTopic | None = None
    """Chủ đề kế (theo `position`) có bài đã publish, kèm bài đầu của nó — tính
    vô điều kiện để sidebar hiện đường đi còn lại ở MỌI bài, không chỉ bài cuối.
    Rỗng khi không còn chủ đề nào phía trước có nội dung."""
