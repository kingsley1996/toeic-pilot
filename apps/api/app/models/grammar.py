"""Ngữ pháp TOEIC — `planning/docs/SPEC-GRAMMAR.md` §4.

Hai tầng, không phải bốn như dictation: một bài ngữ pháp không phải một đơn vị
audio, nên không có lý do tồn tại cho tầng giữa.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import PublishableMixin, status_check


class GrammarTopic(Base, PublishableMixin):
    """Một chủ đề — thường LÀ một mã nhãn của taxonomy, nhưng không bắt buộc.

    `code` là khoá ngoại LOGIC tới facet `grammar` trong `services/labels.py`,
    được admin endpoint kiểm bằng đúng hàm mà `enrich_skills` dùng, không phải
    một danh sách chép tay. UNIQUE: hai chủ đề cùng một mã là hai chỗ phải sửa
    khi taxonomy đổi — và chủ đề nào cũng tự xưng là "Giới từ".

    NULL hợp lệ và có chủ đích: giáo trình ngữ pháp có những bài nền tảng
    ("Kiến thức cơ bản", "Câu điều kiện") nằm ngoài 12 mã của taxonomy. Không
    mã = không có "luyện tập theo nhãn" và không có cổng ngưỡng 12 câu — bài
    practice của nó vẫn gắn câu tay bình thường, và cổng publish của nó đòi
    ít nhất một bài đã publish thay vì một con số trong kho.
    """

    __tablename__ = "grammar_topic"
    __table_args__ = (status_check("grammar_topic"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str | None] = mapped_column(String(48), unique=True, nullable=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # `cascade="all, delete-orphan"` như dictation_section: mặc định ORM sẽ gán
    # NULL vào `topic_id` trước khi xoá, mà cột NOT NULL — xoá topic sẽ hỏng.
    lessons: Mapped[list["GrammarLesson"]] = relationship(
        back_populates="topic",
        order_by="GrammarLesson.position",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<GrammarTopic {self.code}>"


class GrammarLesson(Base, PublishableMixin):
    """Một bài học: `theory` có lý thuyết markdown trong `body` và Hoàn thành là
    nút bấm; `practice` không có body, câu lấy từ bảng nối, và hoàn thành SUY RA
    từ `grammar_attempt` — đúng toàn bộ câu là xong, không có nút để bấm bừa.

    `body` rỗng bị cổng publish chặn ở endpoint với lesson theory — một trang
    chỉ có khoảng trắng vẫn "có body" theo database và là một trang trống với
    người học.
    """

    __tablename__ = "grammar_lesson"
    __table_args__ = (
        status_check("grammar_lesson"),
        CheckConstraint("kind IN ('theory', 'practice')", name="ck_grammar_lesson_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("grammar_topic.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="theory")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    topic: Mapped[GrammarTopic] = relationship(back_populates="lessons")
    questions: Mapped[list["GrammarLessonQuestion"]] = relationship(
        back_populates="lesson",
        order_by="GrammarLessonQuestion.position",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<GrammarLesson {self.slug}>"


class GrammarLessonQuestion(Base):
    """Bài tập CỦA MỘT BÀI HỌC — rút từ bảng nối này, KHÔNG phải từ nhãn.

    Nhãn thô hơn bài học: ba bài trong cùng chủ đề "Thì" mà rút theo nhãn thì
    người học gặp lại y một bộ câu ở mỗi bài, và mọi thứ trông hoàn toàn bình
    thường (`SPEC-GRAMMAR.md` §8, lỗi hỏng im lặng số một).
    """

    __tablename__ = "grammar_lesson_question"
    __table_args__ = (CheckConstraint("position >= 1", name="ck_grammar_lesson_question_position"),)

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("grammar_lesson.id", ondelete="CASCADE"), primary_key=True
    )
    # CASCADE, khác `grammar_attempt`: hàng nối không mang lịch sử ai, xoá bài
    # học thì quan hệ "câu này thuộc bài nào" chết theo là đúng.
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    lesson: Mapped[GrammarLesson] = relationship(back_populates="questions")


class GrammarLessonCompletion(Base):
    """Dấu "người học đã học xong bài".

    Đây là hàng DUY NHẤT trong module không suy ra được từ bảng khác: sự kiện là
    cái nút "Hoàn thành" được bấm, và không lịch sử nào khác kể được chuyện đó
    (G4 chưa có bài tập theo bài). Tiến độ vẫn suy ra — từ chính những hàng này;
    cái được lưu là biến cố, không phải bộ đếm.
    """

    __tablename__ = "grammar_lesson_completion"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("grammar_lesson.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GrammarAttempt(Base):
    """Lượt làm bài. Tiến độ SUY RA từ bảng này, không có bảng tiến độ song song
    — cùng luật với `StoryProgress`: bảng ghi kèm lịch sử sẽ lệch ngay lần đầu
    có ai xoá một lượt, và không gì phát hiện.
    """

    __tablename__ = "grammar_attempt"
    __table_args__ = (Index("ix_grammar_attempt_user_question", "user_id", "question_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # RESTRICT: lịch sử của người học không được mồ côi theo một câu hỏi.
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="RESTRICT"), nullable=False
    )
    # SET NULL, và đó là chỗ dễ chọn sai: màn sửa đề của admin xoá-and-tạo lại
    # toàn bộ options mỗi lần lưu, nên RESTRICT ở đây biến mỗi lần sửa một câu
    # đã có người trả lời thành lỗi 500. Mất "chọn đáp án nào" còn hơn mất cả
    # lượt làm; `is_correct` đã lưu nên lịch sử vẫn chấm được.
    option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_option.id", ondelete="SET NULL"), nullable=True
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
