"""Trợ lý AI cho học viên: hỏi đáp về trang web và tiến độ của chính mình.

Hai điểm khác `routes/coach.py`, và cả hai đến từ việc trợ lý KHÔNG neo vào lượt
làm bài:

- **Không có cổng "nộp bài xong mới hỏi".** Cổng đó tồn tại vì ngữ cảnh của
  coach là chính lượt làm bài — cho hỏi khi chưa nộp là cho phép xin đáp án.
  Trợ lý không nhìn thấy lượt nào, nên không có gì để gian lận.
- **Một người MỘT cuộc hội thoại cuốn theo.** Coach tách theo từng bài và từng
  câu vì ngữ cảnh tách theo đó; trợ lý nói về cùng một trang web, nên tách mạch
  chỉ làm mất lịch sử khi người học quay lại.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_gateway
from app.core.ai_budget import BudgetExceeded, BudgetUnavailable
from app.core.database import get_db
from app.core.rate_limit import Quota, rate_limit
from app.models.chat import CoachConversation, CoachMessage
from app.models.user import User
from app.schemas.assistant import AssistantAsk
from app.schemas.coach import ChatMessagePublic, ChatTurn
from app.schemas.common import DEFAULT_LIMIT, MAX_LIMIT, Page, count_rows, page_of
from app.services.assistant import MAX_QUESTION_CHARS, ask
from app.services.llm.base import FeatureDisabled, LLMError

router = APIRouter(prefix="/assistant", tags=["assistant"])

# Như CHAT_QUOTA của coach: trần thật sự nằm ở hạn mức chi tiêu, bộ này chỉ
# chặn vòng lặp tự động.
ASSISTANT_QUOTA = Quota(limit=40, window_seconds=3600)


@router.post(
    "/chat",
    response_model=ChatTurn,
    dependencies=[Depends(rate_limit("assistant-chat", ASSISTANT_QUOTA, fail_open=False))],
)
def chat(
    body: AssistantAsk,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatTurn:
    message = body.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Câu hỏi đang trống."
        )
    if len(message) > MAX_QUESTION_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Câu hỏi dài quá {MAX_QUESTION_CHARS} ký tự.",
        )

    try:
        turn = ask(
            db,
            get_gateway(db),
            user=user,
            question=message,
            request_id=request.headers.get("x-request-id"),
        )
    except FeatureDisabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Trợ lý đang tạm tắt."
        ) from None
    except BudgetExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn đã dùng hết hạn mức AI trong ngày. Thử lại vào ngày mai.",
        ) from None
    except (BudgetUnavailable, LLMError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trợ lý tạm thời không phản hồi. Thử lại sau ít phút.",
        ) from None

    return ChatTurn(
        conversation_id=turn.conversation.id,
        question=ChatMessagePublic(id=turn.question.id, role="user", content=turn.question.content),
        answer=ChatMessagePublic(id=turn.answer.id, role="assistant", content=turn.answer.content),
    )


@router.get("/chat", response_model=Page[ChatMessagePublic])
def chat_history(
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[ChatMessagePublic]:
    """Có phân trang, và đây là chỗ lý lẽ của coach KHÔNG chuyển sang được.

    `coach.py::chat_history` trả mảng trần vì một cuộc coach bị chặn bởi chính
    lượt làm bài nó neo vào — vài câu hỏi rồi hết. Trợ lý bỏ đúng cái neo ấy để
    có một cuộc cuốn theo mãi mãi, nên nó rơi vào ca (C) "tăng theo mức dùng"
    của `schemas/common.py`, nơi luật là `Page[T]`.

    Sắp GIẢM DẦN theo `position`: trang đầu là những gì vừa nói, thứ người ta mở
    lại để đọc. Sắp tăng dần thì trang đầu là cuộc trò chuyện của tháng trước và
    người dùng phải lật tới cuối mới thấy câu mình vừa hỏi.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    conversation = db.scalars(
        select(CoachConversation).where(
            CoachConversation.user_id == user.id,
            CoachConversation.attempt_id.is_(None),
        )
    ).first()
    if conversation is None:
        return page_of([], 0, limit, offset)

    query = select(CoachMessage).where(CoachMessage.conversation_id == conversation.id)
    rows = db.scalars(
        query.order_by(CoachMessage.position.desc()).limit(limit).offset(offset)
    ).all()
    return page_of(
        [ChatMessagePublic(id=r.id, role=r.role, content=r.content) for r in rows],
        count_rows(db, query),
        limit,
        offset,
    )
