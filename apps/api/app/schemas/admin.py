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
