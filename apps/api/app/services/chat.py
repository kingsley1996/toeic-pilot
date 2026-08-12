"""Coach hỏi đáp — neo vào ngữ cảnh, và chừa sẵn chỗ cho RAG.

Hai điều quyết định giá của tính năng này:

- **Không cache được.** Mỗi câu hỏi là mới, nên khác hẳn `coach_explain` nơi chi
  phí hội tụ về 0. Trần thật sự là hạn mức chi tiêu (fail closed) cộng cửa sổ
  lịch sử ở đây.
- **Lịch sử có CỬA SỔ, không gửi hết.** Gửi toàn bộ nghĩa là tin nhắn thứ hai
  mươi đắt gấp nhiều lần tin nhắn đầu, và chi phí một cuộc trò chuyện tăng theo
  bình phương độ dài. Cắt ở `HISTORY_TURNS` lượt gần nhất giữ chi phí mỗi tin
  nhắn gần như không đổi — đổi lại trợ giảng "quên" phần đầu, và đó là đánh đổi
  đúng cho một cuộc hỏi đáp quanh một câu hỏi.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat import CoachConversation, CoachMessage
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.router import Tier
from app.services.retrieval import Anchor, Retriever

__all__ = ["FEATURE", "MAX_QUESTION_CHARS", "Answered", "ask"]

FEATURE = "coach_chat"

# Sáu lượt qua lại. Đủ để hỏi tiếp một hai câu quanh cùng một chỗ chưa hiểu, và
# ngắn đủ để chi phí mỗi tin nhắn không trôi đi.
HISTORY_TURNS = 6

# Trần độ dài câu hỏi. Không phải để chống lạm dụng — `rate_limit` lo việc đó —
# mà vì một "câu hỏi" dài năm nghìn ký tự không phải câu hỏi: đó là ai đó dán
# nguyên một bài đọc vào, và nó biến một lượt gọi rẻ thành một lượt đắt.
MAX_QUESTION_CHARS = 1000


@dataclass(slots=True)
class Answered:
    conversation: CoachConversation
    question: CoachMessage
    answer: CoachMessage


def history(session: Session, conversation_id: uuid.UUID) -> list[CoachMessage]:
    """`HISTORY_TURNS * 2` tin nhắn gần nhất, trả về theo thứ tự trò chuyện.

    Sắp theo `position` chứ KHÔNG theo `created_at`: `func.now()` trả thời điểm
    của giao dịch, nên cặp hỏi–đáp ghi cùng một lượt không phân biệt được.

    Lấy mới-nhất-trước rồi đảo lại: `ORDER BY position DESC LIMIT n` dùng được
    index, còn lấy hết rồi cắt ở Python thì đọc cả cuộc trò chuyện mỗi lượt.
    """
    rows = list(
        session.scalars(
            select(CoachMessage)
            .where(CoachMessage.conversation_id == conversation_id)
            .order_by(CoachMessage.position.desc())
            .limit(HISTORY_TURNS * 2)
        )
    )
    return list(reversed(rows))


def ask(
    session: Session,
    gateway: Gateway,
    retriever: Retriever,
    *,
    conversation: CoachConversation,
    question: str,
    request_id: str | None = None,
) -> Answered:
    text = question.strip()
    if not text:
        raise ValueError("câu hỏi rỗng")
    text = text[:MAX_QUESTION_CHARS]

    anchor = Anchor(attempt_id=conversation.attempt_id, question_id=conversation.question_id)
    snippets = retriever.fetch(query=text, anchor=anchor)
    context = "\n\n".join(f"[{s.source}:{s.ref}]\n{s.text}" for s in snippets) or "(không có)"

    prompt = load("coach_chat")
    past = history(session, conversation.id)

    # Lịch sử đi vào lượt NGƯỜI DÙNG, không vào lời nhắc hệ thống. Nối nó vào
    # `system` sẽ khiến chữ người học từng gõ trở thành một phần chỉ dẫn cho
    # model — đúng con đường mà một câu "bỏ qua mọi quy tắc phía trên" cần để có
    # hiệu lực. Đây là ranh giới an toàn, không phải cách sắp xếp cho gọn.
    turns = "\n".join(
        f"{'Người học' if m.role == 'user' else 'Trợ giảng'}: {m.content}" for m in past
    )
    user_turn = f"{turns}\nNgười học: {text}" if turns else f"Người học: {text}"

    result = gateway.run(
        LLMRequest(system=prompt.render(context=context), user=user_turn, max_tokens=500),
        feature=FEATURE,
        tier=Tier.STRONG,
        user_id=conversation.user_id,
        prompt_version=prompt.version,
        request_id=request_id,
    )

    nxt = int(
        session.scalar(
            select(func.coalesce(func.max(CoachMessage.position), 0)).where(
                CoachMessage.conversation_id == conversation.id
            )
        )
        or 0
    )
    asked = CoachMessage(
        conversation_id=conversation.id, position=nxt + 1, role="user", content=text
    )
    answered = CoachMessage(
        conversation_id=conversation.id,
        position=nxt + 2,
        role="assistant",
        content=result.text.strip(),
    )
    session.add_all([asked, answered])
    session.commit()
    return Answered(conversation, asked, answered)
