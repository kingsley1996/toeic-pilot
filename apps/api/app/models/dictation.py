import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.audio import AudioAsset
from app.models.mixins import PublishableMixin, difficulty_check, status_check

# JSONB on PostgreSQL, plain JSON on the SQLite used by the test fixture.
_JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class DictationItem(Base, PublishableMixin):
    __tablename__ = "dictation_item"
    __table_args__ = (
        # A published item must have audio. Expressible as a CHECK because the
        # link is a single column, unlike vocabulary, where "has all four accents"
        # spans rows in another table and only the publish endpoint can enforce it.
        CheckConstraint(
            "status <> 'published' OR audio_asset_id IS NOT NULL",
            name="ck_dictation_item_published_has_audio",
        ),
        # Thuộc về một story thì phải có thứ tự trong story đó, và ngược lại.
        # Nếu tách rời, một câu có thể nằm trong story mà không biết đứng thứ
        # mấy — nghĩa là thứ tự phát cho học viên trở thành ngẫu nhiên theo cách
        # database trả hàng, tức là im lặng và không tái lập được.
        CheckConstraint(
            "(story_id IS NULL) = (position IS NULL)",
            name="ck_dictation_item_story_position",
        ),
        difficulty_check("dictation_item"),
        status_check("dictation_item"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable because a draft exists before its audio does: the editor writes the
    # transcript, the offline worker synthesises it later. The CHECK above is what
    # stops that intermediate state from reaching a learner.
    audio_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audio_asset.id", ondelete="RESTRICT"), nullable=True
    )
    # THE ANSWER KEY. `audio_asset.source_text` is the string that was fed to TTS
    # and exists only so an asset can be re-derived; the two are usually
    # identical, which is exactly the trap. Editing one does not touch the other,
    # and grading against the wrong one marks a learner down over a comma in a
    # copy nobody meant to grade against.
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    # Bản dịch tiếng Việt, CHỈ để đọc hiểu. Nó không tham gia chấm bài và
    # KHÔNG được vào `source_hash` — hash là `sha256(text|voice|engine|version)`
    # và cổng publish so nó để phát hiện clip cũ, nên kéo bản dịch vào đó sẽ
    # biến mỗi lần sửa một chữ tiếng Việt thành một lệnh thu lại toàn bộ.
    #
    # Nullable: câu chưa dịch vẫn học được bình thường, chỉ là khối lời thoại
    # hiện mỗi tiếng Anh.
    transcript_vi: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("topic.id", ondelete="SET NULL"), nullable=True
    )
    # Nullable vì các câu có trước cây phân cấp vẫn phải sống tiếp. Một câu chưa
    # gán story không hỏng, nó chỉ chưa xuất hiện trong luồng duyệt của học viên
    # — và màn admin liệt kê chúng riêng để không ai mất dấu.
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dictation_story.id", ondelete="SET NULL"), nullable=True, index=True
    )
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)

    # Same purpose as VocabularyAudio.asset: the publish gate compares a hash
    # recomputed from the current transcript against the asset's stored one.
    asset: Mapped["AudioAsset | None"] = relationship()
    story: Mapped["DictationStory | None"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<DictationItem {self.transcript[:40]!r}>"


class DictationAttempt(Base):
    __tablename__ = "dictation_attempt"
    __table_args__ = (
        CheckConstraint("accuracy BETWEEN 0 AND 100", name="ck_dictation_attempt_accuracy"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dictation_item.id", ondelete="RESTRICT"), nullable=False
    )
    # Stored exactly as typed. Normalisation belongs to the grader, and the
    # grader will change; keeping only the normalised form would make it
    # impossible to ever re-grade an old attempt under new rules.
    submitted_text: Mapped[str] = mapped_column(Text, nullable=False)
    accuracy: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    # Khớp đáp án từng từ, không thiếu không thừa. Tiến độ đếm cột NÀY chứ không
    # đếm `accuracy = 100`: gõ đủ câu rồi gõ thêm vẫn cho accuracy 100, nên dùng
    # accuracy để đánh dấu hoàn thành sẽ tính cả những bài rõ ràng chưa xong.
    #
    # Lưu chứ không suy ra trong SQL, vì suy ra cần chuẩn hoá văn bản — thứ chỉ
    # bộ chấm biết làm. `submitted_text` vẫn giữ nguyên văn, nên nếu sau này đổi
    # định nghĩa "đúng" thì cột này tính lại được từ đầu.
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    # Word-level comparison, so the UI can re-render the highlighting without
    # re-running the grader.
    word_diff: Mapped[Any | None] = mapped_column(_JSON_TYPE, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DictationTopic(Base, PublishableMixin):
    """Tầng trên cùng của cây dictation: Short stories · Conversation · TOEIC Listening.

    Bảng riêng chứ không dùng chung `topic` với từ vựng, dù `topic` được thiết kế
    để dùng chung. Lý do là hai bên phân loại theo hai trục khác nhau: từ vựng
    gom theo *chủ đề* ("du lịch", "văn phòng"), còn dictation gom theo *dạng bài
    nghe* ("truyện ngắn", "hội thoại"). Nhét chung một bảng thì "Short stories"
    sẽ hiện ra trong bộ lọc chủ đề của từ vựng, nơi nó vô nghĩa.
    """

    __tablename__ = "dictation_topic"
    __table_args__ = (status_check("dictation_topic"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # `cascade="all, delete-orphan"` chứ không chỉ dựa vào ON DELETE CASCADE của
    # database: mặc định ORM sẽ cố gán NULL vào `section.topic_id` trước khi xoá,
    # mà cột đó NOT NULL — nên xoá một topic sẽ hỏng. Để ORM tự xoá con cũng
    # khiến hành vi giống nhau trên PostgreSQL và trên SQLite của test, nơi khoá
    # ngoại mặc định không được thực thi.
    sections: Mapped[list["DictationSection"]] = relationship(
        back_populates="topic",
        order_by="DictationSection.position",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DictationTopic {self.slug}>"


class DictationSection(Base, PublishableMixin):
    """Tầng giữa. Admin tự đặt tên lúc tạo — "Unit 1", "Level A", "Tuần 3", tuỳ họ.

    Không có slug: không ai deep-link tới một section, nên URL dùng UUID. Thêm
    slug ở đây sẽ kéo theo ràng buộc duy nhất-trong-phạm-vi-cha, tức một thứ nữa
    có thể đặt sai mà chẳng đổi lại được gì.
    """

    __tablename__ = "dictation_section"
    __table_args__ = (status_check("dictation_section"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # CASCADE: xoá một topic thì cả nhánh dưới nó đi theo. Khác với nội dung
    # trỏ tới người dùng (SET NULL) — ở đó mất quy kết còn hơn mất bài học.
    topic_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dictation_topic.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    topic: Mapped["DictationTopic"] = relationship(back_populates="sections")
    stories: Mapped[list["DictationStory"]] = relationship(
        back_populates="section",
        order_by="DictationStory.position",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DictationSection {self.name!r}>"


class DictationStory(Base, PublishableMixin):
    """Một bài văn liền mạch, chia thành 15-20 câu CÓ THỨ TỰ.

    Thứ tự là điểm khác biệt so với một cái rổ gom câu: học viên làm tuần tự, bỏ
    dở hôm nay mai vào làm tiếp, và điểm của cả story mới có nghĩa. Thứ tự nằm ở
    `dictation_item.position`, không phải ở đây.

    Tiến độ **không** có bảng riêng: nó suy ra được từ `dictation_attempt`. Một
    bảng tiến độ ghi song song sẽ lệch khỏi lịch sử làm bài ngay lần đầu có ai
    xoá một lượt làm, và không có gì phát hiện.
    """

    __tablename__ = "dictation_story"
    __table_args__ = (
        difficulty_check("dictation_story"),
        status_check("dictation_story"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dictation_section.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)

    section: Mapped["DictationSection"] = relationship(back_populates="stories")
    # KHÔNG cascade: xoá một bài phải giữ lại các câu trong nó. `passive_deletes`
    # giữ cho ORM không tự gán NULL vào `story_id` — nó sẽ để nguyên `position`
    # và vi phạm CHECK `ck_dictation_item_story_position`. Endpoint xoá gỡ cả hai
    # cột một cách tường minh trước (`_detach_items`).
    items: Mapped[list["DictationItem"]] = relationship(
        back_populates="story",
        order_by="DictationItem.position",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<DictationStory {self.title!r}>"
