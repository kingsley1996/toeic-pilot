import uuid

from sqlalchemy import Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import PublishableMixin, status_check


class Topic(Base, PublishableMixin):
    """A subject a learner browses by — shared between vocabulary and dictation.

    One table rather than one per feature: learners think in subjects ("travel"),
    not in product modules, and the same subject should mean the same thing on
    both sides of the Learning Hub.
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
