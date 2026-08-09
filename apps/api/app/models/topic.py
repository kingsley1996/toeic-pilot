import uuid

from sqlalchemy import Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import PublishableMixin, status_check


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

    def __repr__(self) -> str:
        return f"<Topic {self.slug}>"
