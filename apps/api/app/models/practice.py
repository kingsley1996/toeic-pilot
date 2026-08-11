"""TOEIC Practice: questions, tests, and what a learner did with them.

The shape here follows the exam rather than any tidier abstraction, because the
exam is what has to be rendered. Two facts drive almost every decision in this
module (ADR-001 A2):

  * Parts 3, 4, 6 and 7 hang several questions off one shared stimulus — an
    audio conversation, a talk, a passage. Parts 1, 2 and 5 do not.
  * Part 2 has three options and prints neither the prompt nor the options; the
    learner only hears them. Every other part has four printed options.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import PublishableMixin, difficulty_check, status_check

# Parts whose questions hang off a shared stimulus. Listed here rather than
# inlined so the CHECK constraint and any future validator cannot disagree.
GROUPED_PARTS = (3, 4, 6, 7)

LISTENING_PARTS = (1, 2, 3, 4)
READING_PARTS = (5, 6, 7)

QUESTION_SOURCES = ("original", "generated", "licensed")
TEST_KINDS = ("full", "mini")
ATTEMPT_MODES = ("full_test", "part_practice")

# Parts whose options exist only in the audio. ETS prints neither the four
# statements of part 1 nor the three responses of part 2; part 1's test book
# shows the photograph alone. So `prompt_text` and `question_option.content` are
# NULL for both — the correct value, not missing data.
UNPRINTED_PARTS = (1, 2)

# Part 2 is the one part with three options rather than four.
PART_2_OPTION_COUNT = 3
DEFAULT_OPTION_COUNT = 4


class QuestionSet(Base, PublishableMixin):
    """A stimulus shared by several questions (parts 3, 4, 6, 7)."""

    __tablename__ = "question_set"
    __table_args__ = (
        CheckConstraint("part BETWEEN 1 AND 7", name="ck_question_set_part"),
        status_check("question_set"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    # Parts 3 and 4: one recording, several questions. Parts 1 and 2 put their
    # audio on the question instead, because there it really is one per question.
    audio_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audio_asset.id", ondelete="RESTRICT"), nullable=True
    )
    # Parts 6 and 7. Three separate columns rather than an array because part 7
    # tops out at three passages and their order carries meaning — an email, its
    # reply, then a schedule. An array loses that; a child table adds a join for
    # a limit that is hard-coded at three anyway.
    passage: Mapped[str | None] = mapped_column(Text, nullable=True)
    passage_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    passage_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Một ảnh cho MỖI ô ngữ liệu, không phải một ảnh cho cả cụm.
    #
    # Lý do lấy thẳng từ lập luận ba cột ở trên: thứ tự mang nghĩa. Một cột ảnh
    # dùng chung sẽ không diễn đạt được "ngữ liệu 1 là biểu đồ, ngữ liệu 2 là
    # email" — mà đó đúng là hình dạng bài đọc đôi hay gặp nhất.
    #
    # Phần lớn ngữ liệu KHÔNG cần ảnh, và không nên có: bảng giá, lịch trình,
    # mẫu đơn đều viết thành văn bản được, và bản văn bản đọc được bằng máy đọc
    # màn hình, phóng to được, tìm được. Ảnh dành cho chỗ quan hệ không gian
    # mang nghĩa — biểu đồ, sơ đồ mặt bằng, bản đồ.
    # Lời thoại của bản thu, dạng [{"text": ..., "voice": ...}] theo thứ tự nói.
    #
    # Part 1 và 2 **không in gì cả** — ETS chỉ đọc lên — nên `prompt_text` và
    # `question_option.content` đều phải NULL. Thứ biên tập viên gõ vào chính là
    # lời thoại, và trước cột này nó không có chỗ nào để ở.
    #
    # JSON lượt nói chứ không phải một khối văn bản: nó ghi được ai nói câu nào,
    # thứ người soát bản thu cần, và là đúng hình dạng `conversation_source_hash`
    # sẽ đọc khi đường TTS được làm (ADR-007 §2.1, §2.7b).
    #
    # `JSON` với biến thể `JSONB` cho Postgres: production dùng JSONB (nhị phân,
    # đánh chỉ mục được), còn test chạy trên SQLite — nơi `JSONB` không tồn tại
    # và mọi bảng sẽ không tạo được.
    audio_script: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    # Thời điểm gắn audio, để màn quản trị đặt cạnh `updated_at` mà cảnh báo.
    #
    # Cần cột riêng chứ không so với `audio_asset.created_at`: gắn một bản thu
    # cũ vào câu vừa sửa sẽ báo lệch oan, mà cảnh báo oan là cách nhanh nhất dạy
    # người ta bấm bỏ qua mọi cảnh báo (ADR-007 §2.7).
    audio_attached_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Vân tay của lời thoại TẠI LÚC GẮN bản thu. So nó với vân tay hiện tại là
    # cách duy nhất biết bản thu còn ứng với lời thoại hay không — xem
    # `script_fingerprint`, phần nói vì sao cặp mốc thời gian không làm được.
    audio_script_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    passage_image_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("image_asset.id", ondelete="RESTRICT"), nullable=True
    )
    passage_2_image_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("image_asset.id", ondelete="RESTRICT"), nullable=True
    )
    passage_3_image_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("image_asset.id", ondelete="RESTRICT"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="question_set", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<QuestionSet part={self.part} {self.title or self.id}>"


class Question(Base, PublishableMixin):
    __tablename__ = "question"
    __table_args__ = (
        CheckConstraint("part BETWEEN 1 AND 7", name="ck_question_part"),
        # Parts 3, 4, 6 and 7 are meaningless without their stimulus. Enforcing it
        # here catches malformed content when it is seeded, rather than when a
        # learner opens a conversation question with no conversation attached.
        CheckConstraint(
            "part NOT IN (3, 4, 6, 7) OR set_id IS NOT NULL",
            name="ck_question_set_required",
        ),
        CheckConstraint(
            "source IN ('original', 'generated', 'licensed')",
            name="ck_question_source",
        ),
        difficulty_check("question"),
        status_check("question"),
        Index("ix_question_part_status", "part", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_set.id", ondelete="CASCADE"), nullable=True, index=True
    )
    position: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # NULL for part 2, where nothing is printed. That is the correct value, not
    # missing data.
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Parts 1 and 2 only; parts 3 and 4 carry their audio on the set.
    audio_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audio_asset.id", ondelete="RESTRICT"), nullable=True
    )
    # Part 1 photographs (ADR-004). An FK rather than a URL string: a bare URL
    # has nowhere to record the licence and attribution that CC-BY requires, and
    # it invites hotlinking someone else's server.
    # Lời thoại của bản thu, dạng [{"text": ..., "voice": ...}] theo thứ tự nói.
    #
    # Part 1 và 2 **không in gì cả** — ETS chỉ đọc lên — nên `prompt_text` và
    # `question_option.content` đều phải NULL. Thứ biên tập viên gõ vào chính là
    # lời thoại, và trước cột này nó không có chỗ nào để ở.
    #
    # JSON lượt nói chứ không phải một khối văn bản: nó ghi được ai nói câu nào,
    # thứ người soát bản thu cần, và là đúng hình dạng `conversation_source_hash`
    # sẽ đọc khi đường TTS được làm (ADR-007 §2.1, §2.7b).
    #
    # `JSON` với biến thể `JSONB` cho Postgres: production dùng JSONB (nhị phân,
    # đánh chỉ mục được), còn test chạy trên SQLite — nơi `JSONB` không tồn tại
    # và mọi bảng sẽ không tạo được.
    audio_script: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    # Thời điểm gắn audio, để màn quản trị đặt cạnh `updated_at` mà cảnh báo.
    #
    # Cần cột riêng chứ không so với `audio_asset.created_at`: gắn một bản thu
    # cũ vào câu vừa sửa sẽ báo lệch oan, mà cảnh báo oan là cách nhanh nhất dạy
    # người ta bấm bỏ qua mọi cảnh báo (ADR-007 §2.7).
    audio_attached_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Vân tay của lời thoại TẠI LÚC GẮN bản thu. So nó với vân tay hiện tại là
    # cách duy nhất biết bản thu còn ứng với lời thoại hay không — xem
    # `script_fingerprint`, phần nói vì sao cặp mốc thời gian không làm được.
    audio_script_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("image_asset.id", ondelete="RESTRICT"), nullable=True
    )
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    # What the question tests ("inference", "verb-tense"). This is the raw
    # material for telling a learner *what* they are weak at rather than only
    # which part they score badly on.
    skill_tag: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # NOT NULL on purpose. Real TOEIC material is ETS copyright, and that is a
    # legal exposure rather than a technical one. Requiring provenance forces the
    # question to be answered while someone still knows the answer; backfilling
    # it later means auditing thousands of rows nobody remembers adding.
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    question_set: Mapped["QuestionSet | None"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )

    @property
    def is_listening(self) -> bool:
        return self.part in LISTENING_PARTS

    def __repr__(self) -> str:
        return f"<Question part={self.part} {self.id}>"


class QuestionOption(Base):
    __tablename__ = "question_option"
    __table_args__ = (
        UniqueConstraint("question_id", "label", name="uq_question_option_label"),
        CheckConstraint("label IN ('A', 'B', 'C', 'D')", name="ck_question_option_label"),
        # At most one correct answer. "At least one" cannot be expressed as a
        # declarative constraint on this table — see ADR-001 B4; it is checked
        # when content is seeded and has its own test.
        Index(
            "uq_question_option_single_correct",
            "question_id",
            unique=True,
            postgresql_where=text("is_correct"),
            sqlite_where=text("is_correct"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(1), nullable=False)
    # NULL for part 2: the options exist only in the audio.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped["Question"] = relationship(back_populates="options")

    def __repr__(self) -> str:
        return f"<QuestionOption {self.label}{'*' if self.is_correct else ''}>"


class TestCollection(Base, PublishableMixin):
    """Một "bộ đề" — nhóm các đề phát hành cùng nhau.

    Có bảng riêng thay vì hai cột chuỗi trên `practice_test`, vì gom nhóm bằng
    chuỗi nghĩa là gõ sai một ký tự sẽ sinh ra một bộ đề mới mà không ai định
    tạo, và không có gì phát hiện ra ngoài việc danh sách bỗng dài thêm một mục.
    """

    __tablename__ = "test_collection"
    __table_args__ = (
        status_check("test_collection"),
        CheckConstraint(
            "year IS NULL OR year BETWEEN 2000 AND 2100", name="ck_test_collection_year"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Nhãn hiển thị của nơi phát hành. KHÔNG phải `question.source` — cột kia
    # trả lời câu hỏi bản quyền theo từng câu và không được lẫn với nhãn này.
    source_tag: Mapped[str | None] = mapped_column(String(32), nullable=True)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    tests: Mapped[list["PracticeTest"]] = relationship(
        back_populates="collection", order_by="PracticeTest.position"
    )

    def __repr__(self) -> str:
        return f"<TestCollection {self.slug}>"


class PracticeTest(Base, PublishableMixin):
    __tablename__ = "practice_test"
    __table_args__ = (
        CheckConstraint("kind IN ('full', 'mini')", name="ck_practice_test_kind"),
        status_check("practice_test"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Nullable: một đề lẻ phải tồn tại được mà không cần bịa ra một bộ đề chỉ có
    # một phần tử.
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_collection.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    collection: Mapped["TestCollection | None"] = relationship(back_populates="tests")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="full")
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Which raw-to-scaled curve this form uses. Real TOEIC forms differ, so the
    # scale belongs to the test rather than to the application.
    score_scale_slug: Mapped[str] = mapped_column(
        ForeignKey("score_scale.slug", ondelete="RESTRICT"),
        nullable=False,
        server_default="default",
    )

    def __repr__(self) -> str:
        return f"<PracticeTest {self.slug}>"


class PracticeTestQuestion(Base):
    """Ordering of questions within a test.

    A join table rather than an FK on `question`, for two reasons: a good
    question should be reusable across tests, and "Practice by Part" draws
    questions that belong to no test at all.
    """

    __tablename__ = "practice_test_question"
    __table_args__ = (
        UniqueConstraint("test_id", "position", name="uq_practice_test_question_position"),
        UniqueConstraint("test_id", "number", name="uq_practice_test_question_number"),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_test.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Số câu chính thức, TÁCH khỏi `position`.
    #
    # `position` là thứ tự trình bày; `number` là con số người học nhìn thấy và
    # nói ra — "câu 32 là Part 3". Với đề đầy đủ hai thứ trùng nhau, nên trông
    # như thừa; với đề rút gọn thì không: một đề mini gồm một câu Part 1 và ba
    # câu Part 5 có position 1–4 nhưng number 1, 101, 102, 103.
    #
    # Lưu chứ không suy ra, vì số nhảy cóc phải là thứ có người nhìn thấy và
    # đồng ý — không phải thứ một hàm tính ra sau lưng (ADR-007 §2.6).
    number: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class Attempt(Base):
    """One sitting: a full mock test, or an ad-hoc run of questions from one part."""

    __tablename__ = "attempt"
    __table_args__ = (
        CheckConstraint("scope IN ('full', 'partial')", name="ck_attempt_scope"),
        CheckConstraint("review_mode IN ('exam', 'practice')", name="ck_attempt_review_mode"),
        CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired', 'abandoned')",
            name="ck_attempt_status",
        ),
        # Nộp rồi thì phải có mốc nộp, và ngược lại. Hai cột nói cùng một chuyện
        # nên chúng không được phép nói khác nhau.
        CheckConstraint(
            "(status IN ('submitted', 'expired')) = (submitted_at IS NOT NULL)",
            name="ck_attempt_submitted_consistent",
        ),
        Index("ix_attempt_user_started", "user_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # LUÔN thuộc một đề. Mô hình cũ tách "làm cả đề" khỏi "luyện một part" và
    # bắt phải chọn một trong hai, nên nó cấm đúng tổ hợp mà giao diện cho phép:
    # một đề, một TẬP part. Luyện theo part giờ là `scope='partial'`, và vì thế
    # vẫn giữ được liên kết tới đề — thứ mô hình cũ đánh mất.
    test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_test.id", ondelete="RESTRICT"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="full")
    # Trục THỨ HAI, không phải cách gọi khác của `scope`: phạm vi trả lời "làm
    # phần nào", cái này trả lời "có được xem đáp án khi đang làm không".
    review_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="exam")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")
    # Thời gian đã dùng, cộng dồn qua các lần tạm dừng. KHÔNG suy ra từ
    # `now() - started_at`: lượt làm tạm dừng được, nên đồng hồ treo tường sẽ ăn
    # mất thời gian người học không hề ngồi trước màn hình.
    elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parts: Mapped[list["AttemptPart"]] = relationship(
        cascade="all, delete-orphan", back_populates="attempt"
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    listening_raw: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reading_raw: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Stored, never recomputed on read. TOEIC conversion tables differ per form
    # and will be corrected over time; deriving the scaled score at display time
    # would silently rewrite a learner's past results every time we touch the
    # table, and their progress chart would move on its own.
    listening_scaled: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    reading_scaled: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    total_scaled: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    items: Mapped[list["AttemptItem"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )
    test: Mapped["PracticeTest"] = relationship()

    def __repr__(self) -> str:
        return f"<Attempt {self.scope}/{self.review_mode} user={self.user_id}>"


class AttemptItem(Base):
    """A question as served to a learner, plus what they did with it.

    One table for both, because an unanswered question is data. Fifteen blanks at
    the end of part 7 means the learner ran out of time — one of the strongest
    signals the study planner has. Splitting "served" from "answered" would turn
    that signal into the absence of a row.
    """

    __tablename__ = "attempt_item"
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_item_question"),
        UniqueConstraint("attempt_id", "position", name="uq_attempt_item_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attempt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # NULL means left blank — see the class docstring.
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_option.id", ondelete="RESTRICT"), nullable=True
    )
    # Derivable from the selected option, but stored anyway: content can be
    # corrected after a learner has sat the test, and a past result must keep the
    # verdict it had at the time. Same reasoning as the scaled scores above.
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # "Đánh dấu" để quay lại. Nằm ở đây chứ không ở bảng riêng: nó chỉ có nghĩa
    # trong phạm vi một lượt làm và biến mất cùng lượt làm đó.
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_spent_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt: Mapped["Attempt"] = relationship(back_populates="items")


class AttemptPart(Base):
    """Các part người học đã chọn cho lượt làm này.

    Bảng riêng thay vì một cột mảng: đây là quan hệ một-nhiều thật, và một cột
    mảng sẽ không có ràng buộc nào ngăn số 9 lọt vào.

    `scope='full'` thì bảng này RỖNG, không phải chứa đủ bảy hàng. Liệt kê đủ
    bảy nghĩa là một đề rút gọn sau này (chỉ có part 5-7) sẽ trông giống hệt một
    lượt làm cả đề, và hai thứ đó không giống nhau.
    """

    __tablename__ = "attempt_part"
    __table_args__ = (CheckConstraint("part BETWEEN 1 AND 7", name="ck_attempt_part_range"),)

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attempt.id", ondelete="CASCADE"), primary_key=True
    )
    part: Mapped[int] = mapped_column(SmallInteger, primary_key=True)

    attempt: Mapped["Attempt"] = relationship(back_populates="parts")
