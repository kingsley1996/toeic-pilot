"""Danh mục các tính năng AI, và cách tra cấu hình của chúng.

Danh sách tính năng nằm trong MÃ chứ không trong database: nó là tập các việc
hệ thống biết làm, và thêm một tính năng luôn kèm mã mới. Để nó ở database thì
giao diện quản trị cho phép tạo một tính năng không ai xử lý — một hàng cấu hình
trỏ vào hư không, trông hoàn toàn hợp lệ.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.ai_config import AiFeatureConfig

__all__ = ["FEATURES", "AiFeature", "resolver_for"]


@dataclass(frozen=True, slots=True)
class AiFeature:
    key: str
    label_vi: str
    description_vi: str


FEATURES: tuple[AiFeature, ...] = (
    AiFeature(
        "enrich_label",
        "Gắn nhãn kỹ năng",
        "Chạy ngoài luồng, kết quả được người duyệt. Chất lượng quan trọng hơn tốc độ, "
        "nhưng chạy một lần nên model chạy tại máy là đủ.",
    ),
    AiFeature(
        "coach_explain",
        "Coach giải thích câu sai",
        "Học viên nhìn thấy trực tiếp. Kết quả được cache theo câu và phương án đã chọn, "
        "nên chi phí hội tụ về 0 và nên chọn model mạnh.",
    ),
    AiFeature(
        "coach_chat",
        "Coach hỏi đáp",
        "Không cache được — mỗi câu hỏi là mới. Đây là bề mặt chi phí không có trần tự "
        "nhiên, nên hạn mức mỗi học viên là thứ gánh chính.",
    ),
    AiFeature(
        "eval_judge",
        "Giám khảo chấm chất lượng",
        "PHẢI khác model sinh: model chấm bài của chính nó thì thiên vị bản thân, và điểm "
        "đẹp lên mà chất lượng không đổi.",
    ),
)


def resolver_for(session: Session) -> Callable[[str], tuple[str, str, bool] | None]:
    """Hàm tra cấu hình, tiêm vào `Gateway.resolve_feature`.

    Đọc database MỖI lượt gọi, không cache. Một lượt đọc hàng theo khoá chính
    không đáng kể so với vài giây gọi LLM, còn cache lại sẽ tạo ra cửa sổ mà
    giao diện đã đổi còn hệ thống thì chưa — thứ người vận hành không có cách
    nào phát hiện, vì cả hai phía đều trông đúng.
    """

    def resolve(feature: str) -> tuple[str, str, bool] | None:
        row = session.get(AiFeatureConfig, feature)
        if row is None:
            return None
        return row.provider, row.model, row.enabled

    return resolve
