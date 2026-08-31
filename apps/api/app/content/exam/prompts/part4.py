"""Part 4 — Talks."""

from __future__ import annotations

from app.content.exam.blueprint import QuestionSlot
from app.content.exam.prompts.graphic import graphic_note
from app.services.labels import LABELS

SYSTEM_PART4 = """You write TOEIC Part 4 (Talks) items for an original practice
test.

A Part 4 item is ONE short talk by a SINGLE speaker plus THREE questions about
it. The talk is heard, never printed; the questions and their four options ARE
printed in the test book.

THE TALK
- One voice throughout. No dialogue, no second speaker, no interruptions.
- 90-120 words of natural spoken business English, in the register its form
  calls for: a voice-mail message, a public announcement, a radio commercial, an
  excerpt from a meeting, or a short talk to an audience.
- It opens the way that form opens — "Hi, this is Marcus from...", "Attention,
  shoppers", "Good morning, everyone, and welcome to..." — because the first
  question is usually about who is speaking or where.
- Every fact the three questions depend on must be SAID out loud.
- No real company names, no brand names, no currency symbols (say "forty
  dollars", not "$40" — it is read aloud).

THE THREE QUESTIONS
- Each asks about something different. Do not ask twice about the same sentence.
- Four printed options each, exactly one correct.
- The three wrong options must be wrong **against what was said**: a detail that
  was corrected, an action ruled out, a time that changed, or something never
  mentioned. An option that is merely unlikely is a second correct answer.
- Options are short noun phrases or short clauses, similar length to each other.

Reply with exactly this shape and nothing else — no preamble, no fences:

[SCRIPT]
voice: VOICE_A
Attention, passengers on flight two-oh-six to Denver. The departure gate has
been changed from gate twelve to gate nineteen. Boarding will begin in about
twenty minutes. Please allow extra time to reach the new gate.

[QUESTION]
Where is the announcement being made?
(A) At an airport
(B) At a train station
(C) At a bus terminal
(D) At a ferry landing
Answer: A
Source: original

[QUESTION]
...

[QUESTION]
...

Use only the voice name given in the instruction below, on a single `voice:`
line. Every question block needs its own `Answer:` and `Source: original`."""


def prompt_for_part4(slot: QuestionSlot) -> str:
    kinds = "\n".join(
        f"  {index}. {LABELS[code].label_vi} ({code})"
        for index, code in enumerate(slot.question_types, start=1)
    )
    return (
        f"Viết một bài nói Part 4 và ba câu hỏi về nó.\n"
        f"- {LABELS[slot.topic].label_vi}\n"
        f"- Tình huống: {slot.context}\n"
        f"- MỘT người nói, giọng: {slot.voices[0]}\n"
        f"- Ba câu hỏi, theo đúng thứ tự này:\n{kinds}\n"
        f"- Mọi dữ kiện mà ba câu hỏi cần phải được NÓI RA trong bài."
        + graphic_note(slot, "Bài nói")
    )
