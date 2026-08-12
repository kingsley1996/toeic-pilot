"""Coach cho học viên: giải thích một câu vừa làm sai.

Hai cổng chặn ở đây quan trọng hơn phần gọi model:

- **Chỉ giải thích sau khi lượt làm bài đã NỘP.** Không có cổng này thì Coach
  trở thành nút gian lận: đang làm bài, bấm một cái là có lời giải kèm đáp án.
- **Chỉ chủ nhân của lượt làm bài.** Lượt của người khác không được xem, kể cả
  khi biết id — id là thứ đoán được, quyền sở hữu thì không.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.ai_budget import BudgetExceeded, BudgetUnavailable
from app.core.database import SessionLocal, get_db
from app.core.rate_limit import Quota, rate_limit
from app.core.redis_client import get_redis
from app.models.coach import CoachExplanation, CoachFeedback
from app.models.practice import Attempt, AttemptItem, Question
from app.models.user import User
from app.schemas.coach import CoachExplanationPublic, CoachFeedbackWrite
from app.services.ai_features import resolver_for
from app.services.coach import CoachUnavailable, NothingToExplain, explain
from app.services.llm.base import FeatureDisabled, LLMError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attempts", tags=["coach"])

# Rộng tay: một học viên xem lại một đề 200 câu có thể muốn giải thích cho vài
# chục câu trong một buổi. Trần thật sự nằm ở hạn mức CHI TIÊU, không ở đây —
# bộ này chỉ chặn một vòng lặp tự động.
COACH_QUOTA = Quota(limit=120, window_seconds=3600)


def _owned_submitted_attempt(db: Session, attempt_id: uuid.UUID, user: User) -> Attempt:
    attempt = db.get(Attempt, attempt_id)
    # 404 chứ không 403 cho lượt của người khác: nói "bạn không được xem" là xác
    # nhận lượt đó tồn tại.
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có lượt này")
    if attempt.submitted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nộp bài xong mới xem được giải thích.",
        )
    return attempt


@router.post(
    "/{attempt_id}/items/{question_id}/coach",
    response_model=CoachExplanationPublic,
    dependencies=[Depends(rate_limit("coach", COACH_QUOTA, fail_open=False))],
)
def explain_question(
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoachExplanationPublic:
    attempt = _owned_submitted_attempt(db, attempt_id, user)

    item = db.scalars(
        select(AttemptItem).where(
            AttemptItem.attempt_id == attempt.id, AttemptItem.question_id == question_id
        )
    ).first()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Câu này không có trong lượt làm bài"
        )

    # Câu làm ĐÚNG thì không có gì để chẩn đoán, và prompt cũng không có nghĩa:
    # trường `vi_sao_ban_chon_sai` nói về một lựa chọn không sai. Chạy thử cho
    # thấy model trả về `chan_doan` dài đúng MỘT ký tự — nó không bịa, nó chỉ
    # không có gì để nói. Chặn ở đây thay vì để cổng kiểm bắt, vì cổng kiểm bắt
    # nghĩa là đã tốn hai lượt gọi model cho một câu hỏi vô nghĩa.
    #
    # Giao diện đã chỉ hiện nút cho câu sai, nhưng giao diện không phải cổng —
    # endpoint nhận được id nào cũng phải tự bảo vệ.
    if item.is_correct:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Câu này bạn làm đúng rồi — không có gì để giải thích.",
        )

    question = db.scalars(
        select(Question).where(Question.id == question_id).options(selectinload(Question.options))
    ).first()
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có câu hỏi này")

    from app.core.ai_budget import Budget
    from app.core.config import settings
    from app.services.llm.gateway import Gateway
    from app.services.llm.ollama import OllamaProvider
    from app.services.llm.openrouter import OpenRouterProvider
    from app.services.llm.router import Tier

    providers: dict[str, object] = {"ollama": OllamaProvider(settings.ollama_base_url)}
    if settings.openrouter_api_key:
        providers["openrouter"] = OpenRouterProvider(settings.openrouter_api_key)

    gateway = Gateway(
        providers=providers,  # type: ignore[arg-type]
        routes={
            Tier.CHEAP: _split(settings.llm_tier_cheap),
            Tier.STRONG: _split(settings.llm_tier_strong),
        },
        budget=Budget(limit_micro=settings.ai_daily_budget_micro_usd),
        redis_client=get_redis(),
        session_factory=SessionLocal,
        resolve_feature=resolver_for(db),
    )

    try:
        result = explain(
            db,
            gateway,
            question=question,
            selected_option_id=item.selected_option_id,
            user_id=user.id,
            request_id=request.headers.get("x-request-id"),
        )
    except FeatureDisabled:
        # 503, và nói thật. Một tính năng tắt mà giao diện im lặng là một tính
        # năng hỏng — người dùng bấm mãi và không hiểu vì sao không có gì.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Coach đang tạm tắt.",
        ) from None
    except BudgetExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn đã dùng hết hạn mức AI trong ngày. Thử lại vào ngày mai.",
        ) from None
    except BudgetUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tạm thời chưa kiểm được hạn mức. Thử lại sau ít phút.",
        ) from None
    except NothingToExplain as exc:
        # 409, không phải 503: đây không phải sự cố tạm thời mà là câu hỏi thiếu
        # nội dung. Trả 503 sẽ mời người dùng thử lại một thứ không bao giờ khác đi.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except CoachUnavailable as exc:
        # GHI LẠI VÌ SAO. Một 503 mất hai mươi giây mà không để lại dấu vết là
        # một sự cố không chẩn đoán được ở production: người dùng báo "không có
        # gì hiện ra", và log chỉ có đúng con số 503.
        logger.warning(
            "coach_gate_failed",
            extra={"question_id": str(question_id), "problems": str(exc)},
        )
        # Cố ý KHÔNG trả một lời giải không đạt. Năm khẳng định là một cổng, và
        # một lời giải nêu sai chữ cái đáp án là một bài học sai.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chưa tạo được lời giải đạt yêu cầu cho câu này.",
        ) from None
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trợ giảng tạm thời không phản hồi. Thử lại sau ít phút.",
        ) from None

    return _public(db, result.explanation, user)


@router.post(
    "/{attempt_id}/items/{question_id}/coach/feedback",
    response_model=CoachExplanationPublic,
)
def rate_explanation(
    attempt_id: uuid.UUID,
    question_id: uuid.UUID,
    body: CoachFeedbackWrite,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CoachExplanationPublic:
    """Một người một phiếu — khoá chính `(explanation_id, user_id)` lo việc đó.

    Không có ràng buộc ấy thì một người bấm mười lần làm lệch đúng con số duy
    nhất đo được chất lượng.
    """
    _owned_submitted_attempt(db, attempt_id, user)
    row = db.get(CoachExplanation, body.explanation_id)
    if row is None or row.question_id != question_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có lời giải này")

    existing = db.get(CoachFeedback, (row.id, user.id))
    if existing is None:
        db.add(CoachFeedback(explanation_id=row.id, user_id=user.id, helpful=body.helpful))
    else:
        existing.helpful = body.helpful
    db.commit()
    return _public(db, row, user)


def _public(db: Session, row: CoachExplanation, user: User) -> CoachExplanationPublic:
    mine = db.get(CoachFeedback, (row.id, user.id))
    return CoachExplanationPublic(
        id=row.id,
        body=row.body,
        helpful=mine.helpful if mine else None,
    )


def _split(value: str) -> tuple[str, str]:
    provider, _, model = value.partition("/")
    return provider, model
