"""Kết xuất một đề thành SQL để đẩy sang database khác.

    uv run python scripts/dump_test.py <slug> > /tmp/<slug>.sql

Chỉ ĐỌC database nguồn. Ba điều được xử lý ở đây, và bỏ sót cái nào cũng làm
lệnh INSERT ở đích nổ hoặc — tệ hơn — đi qua rồi để lại dữ liệu sai:

  * **Mọi cột trỏ sang `users` bị đặt NULL.** `created_by`, `published_by` và
    `reviewed_by` giữ uuid của tài khoản trên máy nguồn, và những uuid đó không
    tồn tại ở đích. Cả ba đều nullable, nên NULL là câu trả lời đúng: ai soạn
    nội dung này là chuyện của database nguồn.
  * **Thứ tự bảng theo chiều phụ thuộc**: asset → collection → đề → cụm → câu →
    lựa chọn → bảng nối.
  * **Asset và collection dùng `ON CONFLICT DO NOTHING`**, vì chúng dùng chung
    giữa nhiều đề và thường đã có ở đích. Hàng của chính đề thì INSERT thẳng, cố
    ý: nếu đề đã tồn tại ở đích thì lệnh phải NỔ chứ không được lặng lẽ nhân đôi
    — `practice_test_question` không có ràng buộc nào ngăn hai bản sao.

Không dùng cho một đề đã có ở đích. Ở đó việc cần làm là UPDATE tại chỗ (xem
`recast_voices`), vì `attempt_item`, `coach_conversation` và `coach_explanation`
đều trỏ vào `question.id` — xoá để nạp lại là xoá cả lịch sử của người học.
"""

import json
import sys
from typing import Any

from sqlalchemy import text

from app.core.database import SessionLocal

USER_COLUMNS = {"created_by", "published_by", "reviewed_by"}

SCOPE = """
with t as (select id from practice_test where slug = :slug),
 ptq as (select * from practice_test_question where test_id = (select id from t)),
 q as (select * from question where id in (select question_id from ptq)),
 s as (select * from question_set
        where id in (select distinct set_id from q where set_id is not null))
"""

TABLES: list[tuple[str, str, bool]] = [
    (
        "audio_asset",
        SCOPE + "select * from audio_asset where id in "
        "(select audio_asset_id from q union select audio_asset_id from s)",
        True,
    ),
    (
        "image_asset",
        SCOPE + "select * from image_asset where id in "
        "(select image_asset_id from q union select passage_image_id from s "
        " union select passage_2_image_id from s union select passage_3_image_id from s)",
        True,
    ),
    (
        "test_collection",
        "select * from test_collection where id = "
        "(select collection_id from practice_test where slug = :slug)",
        True,
    ),
    ("practice_test", "select * from practice_test where slug = :slug", False),
    ("question_set", SCOPE + "select * from s", False),
    ("question", SCOPE + "select * from q", False),
    (
        "question_option",
        SCOPE + "select * from question_option where question_id in (select id from q)",
        False,
    ),
    ("practice_test_question", SCOPE + "select * from ptq", False),
]


def literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    return "'" + str(value).replace("'", "''") + "'"


def main() -> int:
    slug = sys.argv[1]
    out = [
        f"-- {slug}: kết xuất từ database nguồn.",
        "-- Chạy trong MỘT giao dịch: hỏng giữa chừng thì không để lại nửa đề.",
        "BEGIN;",
        "",
    ]
    with SessionLocal() as session:
        for table, sql, soft in TABLES:
            rows = session.execute(text(sql), {"slug": slug}).mappings().all()
            out.append(f"-- {table}: {len(rows)} hàng")
            for row in rows:
                cols = list(row.keys())
                vals = [literal(None if c in USER_COLUMNS else row[c]) for c in cols]
                tail = " ON CONFLICT DO NOTHING" if soft else ""
                out.append(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(vals)}){tail};"
                )
            out.append("")
    out.append("COMMIT;")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
