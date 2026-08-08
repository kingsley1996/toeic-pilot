"""Content rules the database cannot enforce.

Three invariants in ADR-001 B4 are real but not expressible as declarative
constraints on a single table:

  * a question must have **at least** one correct option (the partial unique
    index only rules out more than one),
  * the option count depends on the part (three for part 2, four elsewhere),
  * `question.part` must match `question_set.part` — no composite FK can require
    this while `set_id` stays nullable.

Written as pure functions returning a list of problems rather than raising on the
first: whoever imports content wants every problem in one pass, not a game of
whack-a-mole through a thousand rows.

Recording them here rather than leaving them as prose is the point. "There is a
CHECK constraint" reads as "this is safe", and for these three it is not.
"""

from app.models.practice import (
    DEFAULT_OPTION_COUNT,
    GROUPED_PARTS,
    PART_2_OPTION_COUNT,
    UNPRINTED_PARTS,
    Question,
)

_LABELS = "ABCD"


def expected_option_count(part: int) -> int:
    """Part 2 offers three responses; every other part offers four."""
    return PART_2_OPTION_COUNT if part == 2 else DEFAULT_OPTION_COUNT


def validate_question(question: Question) -> list[str]:
    """Check one question and its options. An empty list means it is well formed."""
    problems: list[str] = []
    part = question.part
    options = list(question.options)

    if part < 1 or part > 7:
        problems.append(f"part must be between 1 and 7, got {part}")
        return problems

    # --- options ---------------------------------------------------------
    expected = expected_option_count(part)
    if len(options) != expected:
        problems.append(f"part {part} needs exactly {expected} options, got {len(options)}")

    labels = [option.label for option in options]
    if len(set(labels)) != len(labels):
        problems.append(f"duplicate option labels: {sorted(labels)}")
    expected_labels = set(_LABELS[:expected])
    if options and set(labels) != expected_labels:
        problems.append(f"option labels must be {sorted(expected_labels)}, got {sorted(labels)}")

    correct = [option.label for option in options if option.is_correct]
    if not correct:
        # The gap the partial unique index leaves open: a question with no
        # correct answer inserts cleanly and can never be answered correctly.
        problems.append("no option is marked correct")
    elif len(correct) > 1:
        problems.append(f"more than one option marked correct: {sorted(correct)}")

    # --- the shared stimulus ---------------------------------------------
    if part in GROUPED_PARTS:
        if question.set_id is None and question.question_set is None:
            problems.append(f"part {part} questions must belong to a question_set")
        elif question.question_set is not None and question.question_set.part != part:
            problems.append(
                f"question is part {part} but its set is part {question.question_set.part}"
            )

    # --- media, which lives at a different level per part (ADR-001 A4.3) ---
    if part in (1, 2) and question.audio_asset_id is None:
        problems.append(f"part {part} questions need their own audio")
    if part in (3, 4):
        stimulus = question.question_set
        if stimulus is not None and stimulus.audio_asset_id is None:
            problems.append(f"part {part} needs audio on its question_set")
    if part == 1 and question.image_asset_id is None:
        problems.append("part 1 questions need a photograph")

    # --- parts 1 and 2 print nothing --------------------------------------
    # ETS is explicit about both: "The statements will not be printed in your
    # test book and will be spoken only one time" (part 1), and the same wording
    # for the three responses in part 2. Part 1's test book shows the photograph
    # and nothing else; part 2's shows nothing at all.
    if part in UNPRINTED_PARTS:
        if question.prompt_text is not None:
            problems.append(f"part {part} prints no prompt; prompt_text must be null")
        printed = [option.label for option in options if option.content is not None]
        if printed:
            problems.append(f"part {part} prints no options, but {sorted(printed)} have content")
    elif question.prompt_text is None:
        problems.append(f"part {part} questions need prompt_text")

    return problems
