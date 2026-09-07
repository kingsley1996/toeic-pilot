"""Ước lượng kết quả placement — SPEC-PLACEMENT §2–§3. Tất định, không LLM.

V1: tỉ lệ đúng từng section trên thang 100, tra bảng quy đổi của form nguồn;
dải tin cậy 95% từ sai số nhị thức. CEFR theo bảng chính chủ của ETS
(Tannenbaum & Wylie 2006) map TỪNG SECTION, trần C1 — không phát minh băng C2.
"""

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.placement import PlacementResult
from app.models.practice import LISTENING_PARTS, Attempt, AttemptItem, Question
from app.services.scoring import raw_to_scaled

VERSION = "v1"
# CI 95% cho p=0.5, n=42: 1.96·√(0.25/42) ≈ 0.151 → ±~76/495 điểm. Đặt thành
# hằng số thay vì tính mỗi lần: n cố định bởi đề cố định, và con số này là
# thứ hiện lên UI "ước lượng", nên phải nhìn được và tranh luận được.
CI_Z = 1.96


def _section_of(part: int) -> str:
    return "listening" if part in LISTENING_PARTS else "reading"


def _scaled_range(db: Session, scale_slug: str, section: str, raw: int, n: int) -> tuple[int, int]:
    """Dải quy đổi quanh `raw` theo CI 95% của tỉ lệ đúng, kẹp vào [0, 495].

    Bảng quy đổi dựng cho thang 100 câu — CI tính trên n câu của đề mini phải
    quy về thang 100 TRƯỚC khi tra, nếu không dải thấp một bậc đơn vị và nói
    một thứ khác với điểm trung tâm.
    """
    p = raw / n if n else 0.0
    half_width = CI_Z * math.sqrt(p * (1 - p) / n) if n else 0.0
    raw_low = max(0, round(raw - half_width * n))
    raw_high = min(n, round(raw + half_width * n))
    low = raw_to_scaled(db, scale_slug, section, round(raw_low / n * 100))
    high = raw_to_scaled(db, scale_slug, section, round(raw_high / n * 100))
    return low, high


# Bảng ETS — mapping TOEIC L&R ↔ CEFR theo section. Trần của TOEIC L&R là C1:
# nghiên cứu chuẩn-set của ETS không có băng C2, và phát minh ra một băng là
# nói dối có số liệu.
CEFR_BANDS: dict[str, tuple[tuple[int, int], ...]] = {
    "A1": ((60, 105), (60, 110)),
    "A2": ((110, 270), (115, 270)),
    "B1": ((275, 395), (275, 380)),
    "B2": ((400, 485), (385, 450)),
    "C1": ((490, 495), (455, 495)),
}
_LISTENING, _READING = 0, 1


def cefr_of(section: str, scaled: int) -> str:
    band_index = _LISTENING if section == "listening" else _READING
    ranges = [(level, r[band_index]) for level, r in CEFR_BANDS.items()]
    for level, (low, high) in ranges:
        if low <= scaled <= high:
            return level
    # Dưới A1 (điểm sàn của bảng ETS là 60): vẫn là A1 — băng thấp nhất là
    # nơi điểm thấp dồn về, không phải một khoảng trống để bịa "A0".
    if scaled < min(low for _, (low, _high) in ranges):
        return "A1"
    # Trên sàn mà không khớp băng nào = khe hở giữa hai băng. Không có khe nào
    # hôm nay vì mọi điểm quy đổi là bội của 5 và các băng liền nhau ở bội 5;
    # một bảng quy đổi tương lai trả 452 thì rơi vào đây, và trả về "A1" cho
    # một người đọc gần B2 là nói dối có số liệu.
    raise ValueError(f"{section} {scaled} rơi vào khe giữa hai băng CEFR")


def analyze(db: Session, attempt: Attempt) -> PlacementResult:
    """Phán quyết v1 cho một lượt làm placement đã nộp. Idempotent: gọi lại
    trên cùng một lượt trả về hàng đã có, không chấm lại.

    Hàng "pending" do `/placement/start` tạo cho lượt này được ĐIỀN VÀO CHỖ,
    không thay bằng hàng mới — nó đang giữ mốc tự khai trước bài, và hai hàng
    cho một lượt là hai phán quyết cho cùng một lượt làm.
    """
    existing = db.get(PlacementResult, attempt.id)
    if existing is not None and existing.estimator_version != "pending":
        return existing

    rows = db.execute(
        select(Question.part, AttemptItem.is_correct)
        .join(Question, Question.id == AttemptItem.question_id)
        .where(AttemptItem.attempt_id == attempt.id)
    ).all()
    totals: dict[str, list[int]] = {"listening": [0, 0], "reading": [0, 0]}
    for part, is_correct in rows:
        bucket = totals[_section_of(part)]
        bucket[0] += 1 if is_correct else 0
        bucket[1] += 1

    scale = attempt.test.score_scale_slug
    out = (
        existing
        if existing is not None
        else PlacementResult(
            attempt_id=attempt.id,
            user_id=attempt.user_id,
            estimator_version=VERSION,
            listening_scaled=0,
            reading_scaled=0,
            cefr_listening="A1",
            cefr_reading="A1",
            cefr_overall="A1",
        )
    )
    out.estimator_version = VERSION
    for section, (raw, total) in totals.items():
        if total == 0:  # pragma: no cover — đề placement luôn đủ hai section
            raise ValueError(f"placement test has no {section} questions")
        setattr(out, f"{section}_raw", raw)
        low, high = _scaled_range(db, scale, section, raw, total)
        setattr(out, f"{section}_low", low)
        setattr(out, f"{section}_high", high)
        scaled = raw_to_scaled(db, scale, section, round(raw / total * 100))
        setattr(out, f"{section}_scaled", scaled)
        setattr(out, f"cefr_{section}", cefr_of(section, scaled))
    # Tổng thể = section YẾU hơn: bảo thủ, cùng luật với việc đếm cả câu bỏ
    # trống vào mẫu số — không tặng trình độ cho phần chưa đọc/kịp nghe.
    out.cefr_overall = min(out.cefr_listening, out.cefr_reading)
    db.add(out)
    db.commit()
    db.refresh(out)
    return out
