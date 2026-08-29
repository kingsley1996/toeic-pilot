import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

__all__ = ["CHAT_ROLES", "CoachConversation", "CoachMessage"]

CHAT_ROLES = ("user", "assistant")


class CoachConversation(Base):
    """Một cuộc hỏi đáp, NEO vào một lượt làm bài và (tuỳ chọn) một câu hỏi.

    Điểm neo không phải siêu dữ liệu — nó là **nguồn ngữ cảnh**. Một cuộc trò
    chuyện không neo vào đâu cả là một chatbot bọc API, đúng thứ `PLAN.md` nói
    không làm, và cũng là thứ không kiểm chứng được câu trả lời dựa vào đâu.

    `question_id` nullable vì hai câu hỏi khác nhau: "giải thích câu này" và
    "tôi yếu phần nào trong bài vừa rồi".

    `attempt_id` nullable cho TRỢ LÝ TRANG WEB (`services/assistant.py`): nó hỏi
    về chính trang web và tiến độ của người hỏi, nên nguồn ngữ cảnh là bản hướng
    dẫn viết tay cộng số liệu thật — không phải lượt làm bài. `NULL` là dấu hiệu
    phân loại, không thêm cột `kind`; `ask()` ở `services/chat.py` chỉ nhận cuộc
    neo vào lượt, và điều đó được kiểm thay vì tin.
    """

    __tablename__ = "coach_conversation"
    __table_args__ = (
        # "Mỗi người một cuộc trợ lý" ép ở tầng database, không phải bằng một
        # phép đọc-rồi-ghi trong Python. TỪNG PHẦN vì cuộc của coach neo vào
        # lượt làm bài và một người có nhiều lượt.
        Index(
            "uq_coach_conversation_assistant",
            "user_id",
            unique=True,
            postgresql_where=text("attempt_id IS NULL"),
            sqlite_where=text("attempt_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("attempt.id", ondelete="CASCADE"), nullable=True
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("question.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CoachMessage(Base):
    """Một lượt trong cuộc trò chuyện.

    Lưu lại vì ba lý do, và lý do thứ ba là lý do kỹ thuật:

    - người học tải lại trang mà không mất mạch
    - có dữ liệu thật để làm bộ eval sau này
    - **lịch sử là đầu vào của lượt gọi tiếp theo**, nên nó phải nằm ở đâu đó
      đáng tin hơn trạng thái của một tab trình duyệt

    Chỉ hai vai trò. Lời nhắc hệ thống KHÔNG lưu ở đây: nó được dựng lại mỗi lần
    từ prompt có phiên bản cộng ngữ cảnh vừa truy hồi, nên lưu nó vừa thừa vừa
    tạo ra hai nguồn sự thật cho cùng một thứ.
    """

    __tablename__ = "coach_message"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_coach_message_role"),
        # Thứ tự trong cuộc trò chuyện KHÔNG suy ra được từ `created_at`:
        # `func.now()` của Postgres trả thời điểm của GIAO DỊCH, nên cặp hỏi–đáp
        # ghi cùng một lượt mang đúng một dấu thời gian và thứ tự giữa chúng là
        # tuỳ ý — trợ giảng có thể hiện trước câu hỏi. Khoá duy nhất khiến một
        # lần ghi trùng vị trí hỏng TO thay vì sắp sai lặng lẽ.
        UniqueConstraint("conversation_id", "position", name="uq_coach_message_position"),
        # Câu hỏi hay hỏi nhất là "lấy N lượt gần nhất của cuộc này".
        Index("ix_coach_message_conversation_position", "conversation_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("coach_conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
