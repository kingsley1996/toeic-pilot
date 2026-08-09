import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Three roles, flat, no resource-level permissions. A full RBAC table set would be
# three tables and a permission layer for a problem that does not exist yet.
# The one boundary that matters: an editor writes content, an admin publishes it,
# so nobody reviews their own work.
USER_ROLES = ("learner", "editor", "admin")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('learner', 'editor', 'admin')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Defaults to the least privilege, and registration never accepts it as input:
    # a self-service signup that can choose its own role is not a role system.
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="learner")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
