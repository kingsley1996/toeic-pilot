"""Grading a dictation attempt.

Pure functions over strings. The database side stores the learner's text exactly
as typed and the result of this module alongside it, so an attempt can be
re-graded later under different rules — which is the whole reason normalisation
lives here rather than at the point of writing.
"""

import re
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher

# Everything that is not a letter, digit, apostrophe or whitespace. The
# apostrophe survives because "don't" and "dont" are a real spelling difference,
# while a comma is something the learner had to guess at.
_STRIP_PUNCTUATION = re.compile(r"[^\w\s']", flags=re.UNICODE)
_COLLAPSE_SPACE = re.compile(r"\s+")

# Typographic apostrophes reach us from PDFs and phone keyboards; the learner
# typing ASCII should not be marked wrong for it.
_APOSTROPHES = {"’": "'", "ʼ": "'", "´": "'"}


def normalise(text: str) -> list[str]:
    """Reduce a line to the words a dictation actually tests.

    Case and punctuation go, because listening does not tell you where a comma
    belongs or whether a word starts a sentence. Marking those wrong deducts
    points for something dictation does not measure.

    Spelling stays: a misspelling is either a mishearing or a gap in written
    English, and both are worth reporting.
    """
    text = unicodedata.normalize("NFKC", text)
    for fancy, plain in _APOSTROPHES.items():
        text = text.replace(fancy, plain)
    text = _STRIP_PUNCTUATION.sub(" ", text.lower())
    return _COLLAPSE_SPACE.sub(" ", text).strip().split()


@dataclass(frozen=True)
class WordResult:
    """One token of feedback.

    `op` is one of:
      * ``match``   — expected word, typed correctly
      * ``missing`` — expected word, absent or wrong in the submission
      * ``extra``   — word the learner typed that is not in the transcript
    """

    op: str
    word: str


@dataclass(frozen=True)
class GradeResult:
    accuracy: Decimal
    matched: int
    expected: int
    diff: list[WordResult]

    def as_json(self) -> list[dict[str, str]]:
        """Shape stored in `dictation_attempt.word_diff`, so the UI can re-render
        the highlighting without re-running the grader."""
        return [{"op": item.op, "word": item.word} for item in self.diff]


def grade(transcript: str, submitted: str) -> GradeResult:
    """Compare a submission against the answer key, word by word.

    The transcript passed here must be `dictation_item.transcript` — the answer
    key — never `audio_asset.source_text`, which is only the string that was fed
    to TTS. The two are usually identical, which is exactly the trap: editing one
    does not touch the other.
    """
    expected_words = normalise(transcript)
    submitted_words = normalise(submitted)

    diff: list[WordResult] = []
    matched = 0

    matcher = SequenceMatcher(None, expected_words, submitted_words, autojunk=False)
    for op, exp_start, exp_end, sub_start, sub_end in matcher.get_opcodes():
        if op == "equal":
            matched += exp_end - exp_start
            diff.extend(WordResult("match", word) for word in expected_words[exp_start:exp_end])
        else:
            # A replacement is reported as both halves: the word that was wanted
            # and the word that was typed. Collapsing it into one entry would hide
            # what the learner actually wrote, which is the useful half.
            diff.extend(WordResult("missing", word) for word in expected_words[exp_start:exp_end])
            diff.extend(WordResult("extra", word) for word in submitted_words[sub_start:sub_end])

    expected = len(expected_words)
    # An empty transcript scores 0 rather than dividing by zero. It should never
    # reach here — transcript is NOT NULL and validated on import — but a grader
    # that raises on bad content fails the learner, not the content.
    ratio = Decimal(matched) / Decimal(expected) * 100 if expected else Decimal(0)

    return GradeResult(
        accuracy=ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        matched=matched,
        expected=expected,
        diff=diff,
    )
