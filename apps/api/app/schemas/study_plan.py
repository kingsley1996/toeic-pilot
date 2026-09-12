"""Schemas kế hoạch học (SPEC-PLACEMENT §6 + SPEC-STUDY-PLANNER §34)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

# Loại mục ĐÓNG: đi qua OpenAPI thành union TypeScript, frontend thiếu một
# loại là lỗi `tsc` chứ không phải một chip không có đường dẫn (bài học `PetId`).
PlanItemKind = Literal[
    "grammar_lesson", "part_drill", "vocab_review", "dictation", "mini_test", "mock_test"
]
PlanPhase = Literal["foundation", "weakness", "integrated", "final"]
PlanFeasibility = Literal["FEASIBLE", "CHALLENGING", "HIGH_RISK"]


class StudyPlanItemPublic(BaseModel):
    position: int
    kind: PlanItemKind
    part: int
    ref_id: str | None
    # Bài học ngữ pháp cần id chủ đề để dựng đường `topic/lesson`.
    topic_id: str | None = None
    label: str
    reason: str | None
    # ĐÍCH ĐẾN do generator dựng (mig 085): drill kèm `?labels=`, board từ
    # vựng theo chủ đề, đề thi thử. None = hàng cũ — UI fallback bảng của nó.
    link: str | None = None
    # Nhãn đường ống §15 — chỉ để hiển thị/nhóm, không phải hàng đợi.
    phase: PlanPhase | None = None
    # Phút ước lượng của một buổi (§17–21). Đây là con số PACKER dùng để chia
    # ngày, nên gửi ra: UI in nó ra đúng thứ lịch đã dựa vào, không tự giữ
    # một bảng phút thứ hai có thể lệch.
    est_minutes: int = 30
    # Mục `mock_test` cần cặp slug để dựng link tới đề; `mini_test` thì link
    # thẳng /learn/placement nên không dùng hai cột này.
    test_slug: str | None = None
    collection_slug: str | None = None
    # SUY từ bản ghi học thật lúc đọc (SPEC §6) — không phải cột tick.
    done: bool
    # Mục này xong vì NGƯỜI HỌC TỰ TICK (`done_at`), không phải vì có bản ghi
    # học. UI dùng để khoá checkbox: bỏ tick một việc đã học thật là nói dối.
    manual_done: bool = False
    # Ngày SUY lúc đọc: hôm nay (giờ của người học) + hạng mục chưa xong //
    # nhịp buổi. Mục đã xong không có ngày — quá khứ của nó nằm ở chính bản
    # ghi học, không phải ở đây. NULL = chưa có ngày vì ai đó đứng trước nó
    # chưa xong.
    day: date | None = None
    # Ngày THẬT của bản ghi học làm xong mục. Ô tick trên lịch đứng ở đây,
    # không phải ở `day` — mục đã xong không còn trong hàng đợi để suy, và
    # ngày suy ra sẽ trôi theo "hôm nay" từng lần đọc.
    completed_on: date | None = None


class PlanEstimate(BaseModel):
    """Khối "bạn đang ở đâu" của header §34 — đọc từ placement_result gốc."""

    listening: int
    reading: int
    total: int
    band_low: int
    band_high: int
    cefr: str


class PlanFocus(BaseModel):
    """Một kỹ năng trong top priority — nhãn + bằng chứng thô, không điểm
    priority: người học đọc "đúng 2/6" chứ không đọc "0.21". `code`+`part` để
    chip bấm thẳng vào drill đã lọc đúng dạng câu."""

    label: str
    correct: int
    total: int
    code: str
    part: int


class PlanMockOption(BaseModel):
    """Một đề full đã publish — danh sách cho ô `mock_test` đổi đích trước khi
    nộp. id để PATCH, title để hiển thị."""

    id: str
    title: str


class StudyPlanPublic(BaseModel):
    id: str
    placement_attempt_id: str
    target_score: int | None
    exam_date: date | None
    source: str
    created_at: datetime
    items: list[StudyPlanItemPublic]
    done_count: int
    # "Hôm nay" do MÁY CHỦ tính theo timezone profile — cùng bài học với lịch
    # hoạt động: để trình duyệt tự gọi `new Date()` là lịch lệch một cột mỗi
    # khi đồng hồ máy khác múi người học, và không gì báo.
    today: date
    # Móc neo của lịch — ngày sinh kế hoạch (hoặc lần "Dời lịch" gần nhất).
    # UI in nó cạnh nút dời: người học cần biết lịch này hẹn từ đâu.
    starts_at: date
    # Hai con số lịch: phút/ngày và số TUẦN-NGÀY nghỉ được. `pace_per_day`
    # từng đứng một mình ở đây và đủ khi lịch là "3 buổi mỗi ngày, mọi ngày";
    # từ khi ngày nghỉ là dữ liệu thật, hai cột này thay nó.
    minutes_per_day: int
    study_days_per_week: int
    days_left: int | None = None
    # Header §34: estimate/gap/feasibility/top focus/why. `None` khi kế hoạch
    # không đọc được phán quyết gốc — màn hình vẫn là màn lịch, chỉ mất phần
    # giải thích, không mất cả trang vì một header.
    estimate: PlanEstimate | None = None
    gap: int | None = None
    weeks_left: int | None = None
    feasibility: PlanFeasibility | None = None
    top_focus: list[PlanFocus] = []
    why: str | None = None
    # §29: phiên bản + lý do — kế hoạch cũ không bị ghi đè, nó là một hàng
    # `is_current=False` mà /study-plan/versions đọc lại được.
    version: int = 1
    reason: str | None = None
    # Rỗng khi kế hoạch không có mục thi thử — UI chỉ vẽ select khi có cả ô
    # lẫn danh sách.
    mock_options: list[PlanMockOption] = []


class PlanVersionPublic(BaseModel):
    """Một phiên bản kế hoạch trong lịch sử (§29)."""

    id: str
    version: int
    reason: str | None
    created_at: datetime
    is_current: bool
    target_score: int | None
    exam_date: date | None
    item_count: int
    done_count: int


class PlanRetake(BaseModel):
    """Một MỐC trên chuỗi điểm: phán quyết placement (mini) hoặc lượt nộp
    đề thi thử full đã quy đổi. `kind` để UI phân biệt hai loại đo — chúng
    không phải cùng một sự kiện."""

    attempt_id: str
    created_at: datetime
    total_scaled: int
    cefr: str = ""
    kind: str = "mini"  # "mini" | "mock"
    label: str = ""


class PlanTrendRow(BaseModel):
    """§31: cùng một kỹ năng, hai lần đo — bài đầu vào và bài mới nhất."""

    code: str
    label: str
    baseline_correct: int
    baseline_total: int
    recent_correct: int
    recent_total: int


class PlanWeekStat(BaseModel):
    """§31 bản trung thực: `minutes` là GIÂY THẬT của các lượt nộp trong tuần
    (`elapsed_seconds`), không phải `est_minutes` của mục — phút ước lượng
    nằm ở lịch hiển thị, còn đây là bằng chứng người học đã ngồi bao lâu.
    Không bôi số phút ôn từ vựng: không có thời lượng từng lượt review thì
    mọi con số phút ở đó đều là bịa."""

    index: int
    minutes: int
    attempts: int
    reviews: int
    dictation: int
    grammar: int


class PlanEvaluationPublic(BaseModel):
    retakes: list[PlanRetake]
    weeks: list[PlanWeekStat] = []
    trend: list[PlanTrendRow]
    # Một phán quyết MỚI HƠN ca chốt hiện hành đã tồn tại (bấm "Đo lại" theo
    # lịch xong rồi) → UI nhắc dựng phiên bản mới, vì lời khuyên hiện hành
    # đang bám số cũ.
    new_diagnostic: bool = False
