"""Response and request shapes for the Learning Hub.

IDs and timestamps are strings, matching `app/schemas/auth.py`: the generated
TypeScript then gets `string` for both, which is what the frontend wants anyway
since JSON has neither a UUID nor a date type.
"""

from pydantic import BaseModel, Field

from app.services.srs import GRADES


class TopicPublic(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    position: int


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


class ReviewSubmit(BaseModel):
    # 0 forgot · 3 hard · 4 good · 5 easy. SM-2's 1 and 2 are rejected: the
    # four-button UI cannot produce them, so accepting them would record
    # something the learner never clicked.
    grade: int = Field(description=f"One of {list(GRADES)}")


class ReviewResult(BaseModel):
    entry_id: str
    grade: int
    interval_days: int
    repetitions: int
    lapses: int
    ease_factor: str
    due_at: str


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
