"""Nguồn ngữ cảnh cho Coach hỏi đáp — và chỗ RAG sẽ cắm vào.

Hôm nay chỉ có một bản cài đặt: `AnchoredRetriever`, lấy ngữ cảnh **tất định**
từ chính câu hỏi và lượt làm bài mà cuộc trò chuyện đang neo vào. Ngày có ngữ
liệu (ngưỡng ở `ADR-003` §3.3), thêm một bản thứ hai đọc `knowledge_chunk` bằng
vector, và **không dòng nào ở endpoint, prompt hay giao diện phải đổi**.

Ba điều làm cái seam này thật chứ không phải trang trí:

- **`query` có mặt trong chữ ký ngay từ đầu, dù hôm nay không ai dùng.** Bản
  neo trả về ngữ cảnh của điểm neo bất kể người học hỏi gì; bản RAG sẽ dùng
  `query` để tìm. Thêm tham số đó về sau là đổi chữ ký ở mọi nơi gọi — thứ luôn
  bị hoãn, rồi thành một hàm `fetch_rag` thứ hai chạy song song.
- **`Snippet` mang `source` và `ref`.** Không có chúng thì prompt nhận về một
  đống văn bản không nguồn gốc, và câu trả lời không trích dẫn lại được — mà
  trích dẫn là thứ phân biệt RAG với việc nhồi ngữ cảnh.
- **Ghép được.** `ChainedRetriever` cho phép chạy neo VÀ vector cùng lúc khi
  RAG tới, thay vì phải chọn một.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.labels import QuestionLabel
from app.models.practice import Attempt, AttemptItem, Question
from app.services.labels import LABELS

__all__ = ["Anchor", "AnchoredRetriever", "ChainedRetriever", "Retriever", "Snippet"]


@dataclass(frozen=True, slots=True)
class Anchor:
    """Cuộc trò chuyện neo vào đâu.

    `question_id` có thể `None`: người học hỏi về cả lượt làm bài chứ không về
    một câu cụ thể. Đó là hai câu hỏi khác nhau và ngữ cảnh cũng khác.
    """

    attempt_id: uuid.UUID
    question_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class Snippet:
    # "question" | "attempt" | "knowledge_chunk" — nguồn, để câu trả lời trích
    # dẫn lại được và để đo retrieval tách khỏi đo sinh văn.
    source: str
    ref: str
    text: str


class Retriever(Protocol):
    def fetch(self, *, query: str, anchor: Anchor, limit: int = 8) -> list[Snippet]: ...


class AnchoredRetriever:
    """Ngữ cảnh TẤT ĐỊNH từ điểm neo — không tìm kiếm, không xếp hạng.

    Cố ý bỏ qua `query`: hôm nay mọi câu hỏi về một câu đều nhận cùng một ngữ
    cảnh, và đó là điều đúng khi chưa có ngữ liệu. Bịa ra một phép tìm kiếm trên
    một câu hỏi duy nhất chỉ tạo ảo giác rằng hệ thống đang truy hồi.
    """

    def fetch(self, *, query: str, anchor: Anchor, limit: int = 8) -> list[Snippet]:
        del query, limit  # xem docstring
        out: list[Snippet] = []
        if anchor.question_id is not None:
            question = self._session.scalars(
                select(Question)
                .where(Question.id == anchor.question_id)
                .options(selectinload(Question.options))
            ).first()
            if question is not None:
                out.append(Snippet("question", str(question.id), _describe_question(question)))
                labels = self._session.execute(
                    select(QuestionLabel.facet, QuestionLabel.code).where(
                        QuestionLabel.question_id == question.id
                    )
                ).all()
                if labels:
                    named = ", ".join(
                        f"{facet}: {code}"
                        + (f" ({LABELS[code].label_vi})" if code in LABELS else "")
                        for facet, code in labels
                    )
                    out.append(Snippet("question", f"{question.id}#labels", f"Nhãn — {named}"))

        summary = self._attempt_summary(anchor.attempt_id)
        if summary:
            out.append(Snippet("attempt", str(anchor.attempt_id), summary))
        return out

    def __init__(self, session: Session) -> None:
        self._session = session

    def _attempt_summary(self, attempt_id: uuid.UUID) -> str | None:
        attempt = self._session.get(Attempt, attempt_id)
        if attempt is None:
            return None
        rows = self._session.execute(
            select(AttemptItem.is_correct, Question.part)
            .join(Question, Question.id == AttemptItem.question_id)
            .where(AttemptItem.attempt_id == attempt_id)
        ).all()
        if not rows:
            return None
        wrong: dict[int, int] = {}
        for is_correct, part in rows:
            if is_correct is False:
                wrong[int(part)] = wrong.get(int(part), 0) + 1
        if not wrong:
            return f"Lượt làm bài này có {len(rows)} câu và không câu nào sai."
        detail = ", ".join(f"Part {p}: {n} câu" for p, n in sorted(wrong.items()))
        return f"Lượt làm bài này có {len(rows)} câu, làm sai {sum(wrong.values())} câu — {detail}."


class ChainedRetriever:
    """Chạy nhiều nguồn và nối kết quả, giữ nguyên thứ tự đã khai báo.

    Tồn tại từ bây giờ để ngày RAG tới không phải chọn giữa neo và vector: ngữ
    cảnh của chính câu hỏi luôn đáng tin hơn một đoạn tìm được, nên nó đứng
    trước và bản vector nối vào sau.
    """

    def __init__(self, *sources: Retriever) -> None:
        self._sources = sources

    def fetch(self, *, query: str, anchor: Anchor, limit: int = 8) -> list[Snippet]:
        out: list[Snippet] = []
        for source in self._sources:
            out.extend(source.fetch(query=query, anchor=anchor, limit=limit))
            if len(out) >= limit:
                break
        return out[:limit]


def _describe_question(question: Question) -> str:
    lines = [f"Câu hỏi Part {question.part}."]
    if question.prompt_text:
        lines.append(f"Đề bài: {question.prompt_text}")
    else:
        lines.append("Đề bài: không in ra, phần này chỉ đọc bằng audio.")
    for option in sorted(question.options, key=lambda o: o.label):
        mark = " ← đáp án đúng" if option.is_correct else ""
        lines.append(f"  {option.label}. {option.content or '(chỉ đọc bằng audio)'}{mark}")
    if question.explanation:
        lines.append(f"Giải thích: {question.explanation}")
    return "\n".join(lines)
