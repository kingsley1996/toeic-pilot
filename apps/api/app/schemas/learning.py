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
