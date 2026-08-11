"""Hình dạng chung cho các endpoint trả danh sách có phân trang.

**Chỉ dùng cho danh sách PHÌNH được.** Danh sách có trần nằm sẵn trong miền
nghiệp vụ — tám giọng logic, hai trăm câu của một đề TOEIC, bảy part — vẫn trả
mảng trần. Bọc chúng lại chỉ để "cho nhất quán" là bắt frontend xử lý một tình
huống không xảy ra được, và làm mọi nơi gọi khó đọc hơn để đổi lấy không gì.

Ba nhóm, và mỗi endpoint mới thuộc đúng một nhóm:

  A. Có trần trong miền   -> mảng trần. `/voices`, `/tests/{slug}/questions`.
  B. Phình theo nội dung  -> `Page[T]`. `/admin/vocabulary`, `/admin/tests`.
  C. Phình theo sử dụng   -> `Page[T]`. `/attempts`.

Chỗ dễ xếp nhầm nhất là các bảng phân loại. Chủ đề từ vựng là nhóm A — biên tập
viên tự tay dựng, và số lượng dừng ở vài chục. `dictation_section` thì KHÔNG,
dù trông y hệt: số phần là chủ đề **nhân** số phần mỗi chủ đề, nên nó phình theo
nội dung. Câu hỏi phân nhóm không phải "trông có giống danh mục không" mà là
"cái gì đặt ra trần cho nó".

`limit`/`offset` chứ không phải con trỏ: con trỏ ổn định hơn khi có hàng chèn
vào giữa lúc đang lật trang, nhưng ở đây không có danh sách nào nhiều người ghi
đồng thời — màn quản trị là biên tập viên xem nội dung của chính họ, lịch sử làm
bài là của riêng một người. Điều kiện để xem lại: khi một danh sách trở thành
luồng nhiều người ghi cùng lúc.
"""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

# Cùng con số đã dùng sẵn ở `/learning/vocabulary` và `/attempts`. Đặt tên để
# ba chỗ không trôi khỏi nhau.
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page[T](BaseModel):
    """Một trang kết quả, kèm tổng số để giao diện biết còn gì phía sau.

    `total` là điều mảng trần không nói được, và thiếu nó thì màn hình chỉ có
    hai lựa chọn tệ: im lặng cắt cụt ở 50 hàng, hoặc tải hết. Cái đầu là thứ
    `/learn/vocabulary` đang làm — lấy 50 từ rồi bỏ phần còn lại mà không ai
    biết là còn.
    """

    items: list[T]
    total: int
    limit: int
    offset: int


def count_rows(db: Session, query: Select[Any]) -> int:
    """Đếm tổng số hàng của một truy vấn, bỏ qua sắp xếp và phân trang.

    `order_by` phải gỡ ra: đếm không cần thứ tự, và Postgres từ chối `ORDER BY`
    trên một cột không nằm trong `GROUP BY` của truy vấn con.
    """
    counted = query.order_by(None).limit(None).offset(None).subquery()
    return db.scalar(select(func.count()).select_from(counted)) or 0


def page_of[T](items: Sequence[T], total: int, limit: int, offset: int) -> Page[T]:
    return Page[T](items=list(items), total=total, limit=limit, offset=offset)
