"""Kế hoạch học — `study_plan` / `study_plan_item` (SPEC-PLACEMENT §6).

Một người MỘT kế hoạch hiện hành (`is_current`) — kế hoạch mới thay kế hoạch
cũ chứ không chồng lên. Tiến độ KHÔNG nằm ở đây: nó suy từ bản ghi học thật
(`grammar_lesson_completion`, `part_session_item`), cùng nguyên tắc §4
SPEC-GRAMMAR — cột tick trên kế hoạch là thứ lệch khỏi thực tế ở lần học đầu.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StudyPlan(Base):
    __tablename__ = "study_plan"
    __table_args__ = (
        # Hai kế hoạch hiện hành của một người là hai lời khuyên mâu thuẫn
        # hiển thị cùng lúc — ràng buộc chặn ở tầng dữ liệu, không phải ở một
        # đoạn `if` ai đó phải nhớ.
        Index(
            "uq_study_plan_current",
            "user_id",
            unique=True,
            sqlite_where=text("is_current"),
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Phán quyết placement mà kế hoạch sinh từ — kế hoạch không có gốc thì
    # không giải thích được vì sao nó đề xuất cái này thay cái kia.
    placement_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attempt.id", ondelete="RESTRICT"), nullable=False
    )
    # Snapshot đầu vào (từ user_profile lúc sinh — nguồn sự thật là profile).
    target_score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="rule"
    )  # "rule" | "llm" — cột so sánh V1/V2 (SPEC §5) có sẵn từ đầu.
    # Móc neo của lịch: mọi ngày suy từ `starts_at + pack(vị trí)`, không suy
    # từ "hôm nay" — tick một mục không được kéo cả lịch trôi (xem mig 085).
    # NULL = hàng trước 085, đọc fallback về `created_at`.
    starts_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # §29: mỗi lần sinh là MỘT PHIÊN BẢN, kế hoạch cũ không bị ghi đè — nó
    # nằm lại với `is_current=False` và số phiên tăng dần theo người học.
    # `reason` do route generate suy từ diff thật (lượt đo / đầu vào đổi).
    version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


class StudyPlanItem(Base):
    """Một mục kế hoạch = một nội dung THẬT (N4: tham chiếu treo không ghi),
    HOẶC một buổi định hướng (`vocab_review`, `dictation`) — nhịp nền đã có
    module thật để dẫn tới, `ref_id` NULL, `part` 0.

    `kind` quyết định `ref_id` trỏ đâu: `grammar_lesson` → `grammar_lesson.id`,
    `part_drill` → số part (ref_id NULL). Trạng thái xong/chưa SUY ra lúc đọc
    từ bản ghi học thật, không lưu cột — NGOẠI LE duy nhất là `done_at`: tick
    tay của người học. Nhịp nền không có bản ghi học nào để suy, nên nhịp nền
    khép lại chỉ bằng tick tay. Hai nguồn giữ riêng biệt: UI hiển thị gộp nhưng
    nói rõ mục xong vì học hay vì tự tick. NGÀY CŨNG KHÔNG LƯU: lịch suy lúc
    đọc từ hạng mục chưa xong chia nhịp học — bỏ một ngày thì mọi mục phía sau
    trôi một ngày, không có "quá hạn" giả.
    """

    __tablename__ = "study_plan_item"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('grammar_lesson', 'part_drill', 'vocab_review', 'dictation',"
            " 'mini_test', 'mock_test')",
            name="ck_study_plan_item_kind",
        ),
        CheckConstraint(
            "phase IS NULL OR phase IN ('foundation', 'weakness', 'integrated', 'final')",
            name="ck_study_plan_item_phase",
        ),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_plan.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    part: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ĐÍCH ĐẾN do generator dựng (mig 085): URL tương đối inside web app —
    # board từ vựng theo chủ đề, drill kèm `?labels=`, đề thi thử. NULL = hàng
    # cũ hoặc đường do `kind` suy ra; UI fallback bảng của nó, đừng 404.
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Nhãn đường ống §15 (SPEC-STUDY-PLANNER) — nền/điểm-yếu/tổng-hợp/nước-rút.
    # CHỈ để hiển thị và nhóm; nó không đổi thứ tự: hàng đợi vẫn là `position`,
    # packing vẫn là `day` suy lúc đọc. NULL = mục cũ trước 084 (không có phase).
    phase: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Tick tay: người học khẳng định xong. NULL = chưa tự tick. Không ghi đè
    # lên bản ghi học — `routes/study_plan.py` gộp hai nguồn khi đọc.
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bộ nhãn DRILL khép theo (mig 087): phiên phải có câu ĐÚNG NHÃN, không
    # phải "bất kỳ câu nào cùng part". NULL = mục chung theo part (ý "đều
    # tay") hoặc hàng cũ.
    filter_codes: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
