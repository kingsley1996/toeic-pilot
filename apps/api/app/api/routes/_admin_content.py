"""Những mảnh dùng chung giữa các router quản trị nội dung.

Tồn tại vì tách `admin.py` làm hai để lộ ra một helper cả hai nửa đều gọi. Cho
`admin_vocabulary` import `admin_dictation` (hay ngược lại) thì hai tệp lại dính
vào nhau và việc tách chỉ còn là đổi tên — xem `REFACTOR-LONG-FILES.md` §2.

Tiền tố `_` để nó không bị nhầm là một router: `app/main.py` gắn mọi mô-đun
route ở đây, và một tệp không có `router` nằm lẫn vào là thứ người ta phải mở ra
mới biết.
"""


def _apply(node: object, body: object, fields: tuple[str, ...]) -> None:
    """Gán những trường được gửi lên, bỏ qua những trường không gửi.

    `exclude_unset` là mấu chốt: PATCH phải phân biệt "đặt về rỗng" với "không
    đụng tới". Không có nó, mọi PATCH sẽ xoá sạch những trường client không quan
    tâm.
    """
    data = body.model_dump(exclude_unset=True)  # type: ignore[attr-defined]
    for field in fields:
        if field in data:
            setattr(node, field, data[field])
