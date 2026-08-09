"""Parsing pasted content into draft records.

Pure functions returning parsed rows **and their problems**, never raising on the
first bad line: whoever pastes 300 words wants every complaint at once, not a
game of whack-a-mole. Nothing here writes to the database — the parse result is
shown for review first (ADR-005 §3.4).
"""

from dataclasses import dataclass, field

from app.models.vocabulary import PARTS_OF_SPEECH

# Pipe-delimited because the fields are short and a paste from a spreadsheet or a
# notes file needs no escaping rules to be readable. It breaks if a meaning
# contains "|", which is good enough for now and recorded as a known limit in
# SPEC-LEARNING-HUB.md §5.
FIELD_SEP = "|"

VOCABULARY_COLUMNS = (
    "headword",
    "part_of_speech",
    "phonetic",
    "meaning_en",
    "meaning_vi",
    "example",
    "example_vi",
)
REQUIRED_VOCABULARY_COLUMNS = ("headword", "part_of_speech", "meaning_en", "meaning_vi")


@dataclass
class ParsedVocabulary:
    line: int
    headword: str = ""
    part_of_speech: str = ""
    phonetic: str | None = None
    meaning_en: str = ""
    meaning_vi: str = ""
    example: str | None = None
    example_vi: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class ParsedDictation:
    line: int
    transcript: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _clean(value: str) -> str | None:
    value = value.strip()
    return value or None


def parse_vocabulary(raw: str) -> list[ParsedVocabulary]:
    """One entry per line: headword | pos | phonetic | en | vi | example | example_vi.

    Trailing fields may be omitted; empty ones are allowed for anything not in
    `REQUIRED_VOCABULARY_COLUMNS`.
    """
    rows: list[ParsedVocabulary] = []
    seen: dict[tuple[str, str], int] = {}

    for lineno, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(FIELD_SEP)]
        row = ParsedVocabulary(line=lineno)

        if len(parts) > len(VOCABULARY_COLUMNS):
            row.problems.append(
                f"too many fields ({len(parts)}); expected at most "
                f"{len(VOCABULARY_COLUMNS)}: {', '.join(VOCABULARY_COLUMNS)}"
            )
            rows.append(row)
            continue

        values = dict(zip(VOCABULARY_COLUMNS, parts, strict=False))
        row.headword = values.get("headword", "").strip()
        row.part_of_speech = values.get("part_of_speech", "").strip().lower()
        row.phonetic = _clean(values.get("phonetic", ""))
        row.meaning_en = values.get("meaning_en", "").strip()
        row.meaning_vi = values.get("meaning_vi", "").strip()
        row.example = _clean(values.get("example", ""))
        row.example_vi = _clean(values.get("example_vi", ""))

        for column in REQUIRED_VOCABULARY_COLUMNS:
            if not getattr(row, column):
                row.problems.append(f"{column} is required")

        if row.part_of_speech and row.part_of_speech not in PARTS_OF_SPEECH:
            row.problems.append(
                f"part_of_speech {row.part_of_speech!r} is not one of {list(PARTS_OF_SPEECH)}"
            )

        # Caught here rather than by the database, because a unique violation at
        # commit time aborts the whole batch and says nothing about which line.
        key = (row.headword.lower(), row.part_of_speech)
        if row.headword and row.part_of_speech:
            if key in seen:
                row.problems.append(f"duplicate of line {seen[key]} in this paste")
            else:
                seen[key] = lineno

        rows.append(row)
    return rows


def parse_dictation(raw: str) -> list[ParsedDictation]:
    """One sentence per line.

    No delimiter: the transcript is the whole line. Anything else would need
    escaping for a format whose only field is free text.
    """
    rows: list[ParsedDictation] = []
    seen: dict[str, int] = {}

    for lineno, line in enumerate(raw.splitlines(), start=1):
        transcript = line.strip()
        if not transcript:
            continue
        row = ParsedDictation(line=lineno, transcript=transcript)

        if len(transcript.split()) < 3:
            # Two words is not a dictation exercise; it is almost certainly a
            # stray line from the paste.
            row.problems.append("transcript is too short to be a dictation sentence")

        key = transcript.lower()
        if key in seen:
            row.problems.append(f"duplicate of line {seen[key]} in this paste")
        else:
            seen[key] = lineno

        rows.append(row)
    return rows
