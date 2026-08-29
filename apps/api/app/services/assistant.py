"""Trợ lý AI của trang web — trả lời câu hỏi về TOEIC Pilot và tiến độ của chính người hỏi.

Khác `services/chat.py` ở NGUỒN NGỮ CẢNH, không ở đường đi. Coach neo vào một
lượt làm bài (tất định, kiểm chứng được); trợ lý neo vào hai thứ không có lượt:

1. **Bản hướng dẫn trang viết tay trong mã** (`SITE_GUIDE`). Nhỏ, tĩnh, đi qua
   review như mọi dòng code khác — một tính năng mô tả sai sẽ được sửa ở cùng
   commit với tính năng đó. Tự kỳ công một phép tìm kiếm trên một văn bản vài
   nghìn ký tự chỉ tạo ảo giác rằng hệ thống đang truy hồi.
2. **Số liệu thật của người học**, suy ra từ đúng các service thống kê mà giao
   diện đã dùng (`profile_stats`, `progression`). Không bảng tổng nào được sinh
   ra để nuôi trợ lý — cùng luật "suy ra, không lưu".

Không dùng `Retriever`/`Anchor` ở đây: điểm neo của coach là một lượt làm bài
còn của trợ lý là "không có", và dựng `Anchor(attempt_id=...)` hư không chỉ để
cho một protocol trông dùng được là nghi lễ, không phải kiến trúc. Ngày RAG tới
(ADR-003 §3.3), ngữ cảnh trang sẽ là nguồn thứ ba nối vào — và nó sẽ thay đúng
một chuỗi ở đây.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.chat import CoachConversation, CoachMessage
from app.models.practice import Attempt
from app.models.user import User
from app.services import progression
from app.services.chat import MAX_QUESTION_CHARS, history, save_turn
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.prompts import load
from app.services.llm.router import Tier
from app.services.profile import ensure_profile
from app.services.profile_stats import gather_stats

__all__ = ["FEATURE", "MAX_QUESTION_CHARS", "Answered", "ask", "learner_context"]

FEATURE = "assistant_chat"

# Bản hướng dẫn đi vào MỖI lượt gọi, nên nó phải ngắn. Đổi trang thì đổi đây —
# cùng commit, để một tính năng mới không bao giờ ở trạng thái "đã có mà trợ lý
# chưa biết".
SITE_GUIDE = """\
TOEIC Pilot là nền tảng luyện thi TOEIC. Các khu:

- `/dashboard` — trang chủ: ba việc hôm nay, tiến độ từ vựng, streak, XP, level.
- `/learn/vocabulary` — học từ vựng theo chủ đề: một bảng gồm gõ lại từ,
  flashcard và quiz; tự đánh giá mức nhớ của mình sau mỗi từ.
- `/learn/review` và `/learn/typing` — ôn tập theo lịch SM-2, chỉ từ ĐẾN HẠN
  mới xuất hiện; gõ lại từ là cách gặp lại từ bằng nhớ chính tả.
- `/learn/dictation` — nghe chép theo cây chủ đề → mục → bài; hệ thống chấm
  từng từ, một câu "hoàn thành" khi từng từ đều khớp, và tiến độ tính theo số
  câu xong chứ không theo phần trăm.
- `/learn/tests` — luyện đề: chọn đề, làm bài, NỘP BÀI rồi mới có điểm ba kỹ
  năng và xem lại từng câu. Giải thích AI cho câu sai và hộp hỏi đáp về bài chỉ
  mở SAU KHI nộp — đó là cổng chống gian lận, không phải lỗi.
- `/learn/attempts` — lịch sử các lượt làm bài đã nộp.
- `/profile` — hồ sơ (múi giờ, mục tiêu điểm, ngày thi) và thống kê học tập;
  `/profile/badges` — huy hiệu, suy ra từ lịch sử học.
- Góc thú cưng Petland — nuôi thú pixel, ruby KIẾM TỪ VIỆC HỌC và tiêu vào mở
  trứng; NPC chạm mặt giao nhiệm vụ học. Chỉ số thú không đổi kết quả học.

Luật đáng biết: XP là sổ cái ghi theo sự kiện; điểm luyện đề quy đổi từ bảng
cấu hình từng đề; mọi nội dung học viên thấy đều đã xuất bản.
"""


@dataclass(slots=True)
class Answered:
    conversation: CoachConversation
    question: CoachMessage
    answer: CoachMessage


def learner_context(db: Session, user: User) -> str:
    """Số liệu thật, cùng nguồn với những gì giao diện đang hiển thị."""
    profile = ensure_profile(db, user)
    stats = gather_stats(db, user.id, profile.timezone)
    progress = progression.level_of(db, user.id)

    lines = [
        f"Tiến độ của người học này: level {progress.level} ({progress.xp_total} XP, "
        f"còn {progress.xp_for_next} XP tới level kế).",
        f"Streak hiện tại {stats.current_streak} ngày, dài nhất {stats.longest_streak} ngày.",
        f"Từ vựng: {stats.vocabulary_mastered}/{stats.vocabulary_total} từ đã thuộc, "
        f"{stats.vocabulary_due} từ đến hạn ôn hôm nay.",
        f"Dictation: {stats.dictation_completed} câu hoàn thành qua "
        f"{stats.dictation_attempts} lần nghe chép.",
    ]

    attempts = db.scalar(
        select(func.count(Attempt.id)).where(
            Attempt.user_id == user.id, Attempt.submitted_at.is_not(None)
        )
    )
    lines.append(f"Luyện thi: đã nộp {attempts or 0} lượt làm bài.")
    if attempts:
        latest = db.scalars(
            select(Attempt)
            .where(Attempt.user_id == user.id, Attempt.submitted_at.is_not(None))
            .order_by(Attempt.submitted_at.desc())
            .limit(1)
        ).first()
        if latest and latest.total_scaled is not None:
            lines.append(
                f"Gần nhất ({latest.submitted_at:%d/%m/%Y}): {latest.total_scaled} điểm "
                f"(Listening {latest.listening_scaled}, Reading {latest.reading_scaled})."
            )
    return "\n".join(lines)


def ask(
    session: Session,
    gateway: Gateway,
    *,
    user: User,
    question: str,
    request_id: str | None = None,
) -> Answered:
    text = question.strip()
    if not text:
        raise ValueError("câu hỏi rỗng")
    text = text[:MAX_QUESTION_CHARS]

    conversation = _find(session, user)

    context = f"{SITE_GUIDE}\n---\n{learner_context(session, user)}"
    prompt = load("assistant_chat")
    past = history(session, conversation.id) if conversation else []

    # Lịch sử đi vào lượt NGƯỜI DÙNG — cùng ranh giới an toàn với coach_chat:
    # nối chữ người học vào `system` là trao quyền cho câu "bỏ qua mọi quy tắc".
    turns = "\n".join(f"{'Người học' if m.role == 'user' else 'Trợ lý'}: {m.content}" for m in past)
    user_turn = f"{turns}\nNgười học: {text}" if turns else f"Người học: {text}"

    result = gateway.run(
        LLMRequest(system=prompt.render(context=context), user=user_turn, max_tokens=500),
        feature=FEATURE,
        tier=Tier.STRONG,
        user_id=user.id,
        prompt_version=prompt.version,
        request_id=request_id,
    )

    # Tạo cuộc SAU lượt gọi, không phải trước: model hỏng thì không để lại một
    # cuộc rỗng, và cửa sổ đua hẹp lại còn đúng lúc ghi.
    conversation = conversation or _open(session, user)
    asked, answered = save_turn(session, conversation.id, text, result.text.strip())
    return Answered(conversation, asked, answered)


def _find(session: Session, user: User) -> CoachConversation | None:
    return session.scalars(
        select(CoachConversation).where(
            CoachConversation.user_id == user.id,
            CoachConversation.attempt_id.is_(None),
        )
    ).first()


def _open(session: Session, user: User) -> CoachConversation:
    """Mở cuộc trợ lý, chịu được hai request đồng thời.

    Chỉ mục duy nhất từng phần (migration 050) là thứ quyết định; khối này chỉ
    biến lần thua cuộc đua thành một lượt đọc lại thay vì một lỗi 500. Đọc-rồi-
    ghi trần trong Python không đủ — cả hai bên đều thấy "chưa có" trước khi
    bên nào kịp commit, và hậu quả là lịch sử tách đôi trong im lặng.
    """
    conversation = CoachConversation(user_id=user.id, attempt_id=None)
    session.add(conversation)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _find(session, user)
        if existing is None:  # pragma: no cover — chỉ xảy ra nếu chỉ mục biến mất
            raise
        return existing
    return conversation
