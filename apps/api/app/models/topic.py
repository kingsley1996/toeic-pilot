import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import PublishableMixin, status_check

if TYPE_CHECKING:
    from app.models.vocabulary import VocabularyCollectionItem


class Topic(Base, PublishableMixin):
    """A subject a learner browses vocabulary by.

    It was designed to be shared with dictation, on the reasoning that learners
    think in subjects ("travel") rather than in product modules. Dictation has
    since grown its own tree (`DictationTopic` → section → story) because the two
    classify along different axes: vocabulary groups by *subject*, dictation by
    *kind of listening* ("short stories", "conversation"). Sharing one table put
    "Short stories" in the vocabulary subject filter, where it means nothing.

    `dictation_item.topic_id` still points here and is still honoured, so
    sentences that predate the tree keep working.
    """

    __tablename__ = "topic"
    __table_args__ = (status_check("topic"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Cuốn sách (collection_item) chứa chủ đề này trong cây
    # collection → collection_item → topic. NULL = chủ đề tồn tại trước cây hoặc
    # chưa được xếp; màn admin liệt kê riêng để không ai mất dấu.
    collection_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vocabulary_collection_item.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Ghi chú vòng: `vocabulary.py` import module này, nên quan hệ ngược khai
    # báo bằng string và resolve qua registry — import ngược lại sẽ vòng vo.
    collection_item: Mapped["VocabularyCollectionItem | None"] = relationship(
        back_populates="topics"
    )

    def __repr__(self) -> str:
        return f"<Topic {self.slug}>"
