"""Dump blog_post dev thành INSERT ... ON CONFLICT (slug) DO UPDATE.

Chạy từ scripts/export-blog.sh, xuất SQL ra stdout. Mọi giá trị text/JSON
bọc dollar-quote ($blog$) để HTML/JSON chứa nháy đơn hay backslash không
phải escape gì cả.
"""

import json

import psycopg

COLS = [
    "id", "slug", "title", "excerpt", "body_json", "body_html",
    "cover_image_url", "category", "tags", "author_name", "related_part",
    "status", "published_at", "created_at", "updated_at",
]

UPDATE_COLS = [c for c in COLS if c not in ("id", "slug")]


def lit(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
        assert "$blog$" not in text
        return f"$blog${text}$blog$"
    text = str(value)
    assert "$blog$" not in text
    return f"$blog${text}$blog$"


def main():
    conn = psycopg.connect("postgresql://toeic:toeic@localhost:5432/toeic")
    rows = conn.execute(
        f"SELECT {', '.join(COLS)} FROM blog_post ORDER BY slug"  # noqa: S608
    ).fetchall()
    print(f"-- blog sync: {len(rows)} bài, upsert theo slug, user-id dev -> NULL.")
    for row in rows:
        rec = dict(zip(COLS, row, strict=True))
        rec["created_by"] = None
        rec["published_by"] = None
        cols = COLS + ["created_by", "published_by"]
        vals = ", ".join(lit(rec[c]) for c in cols)
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in UPDATE_COLS + ["created_by", "published_by"])
        print(f"INSERT INTO blog_post ({', '.join(cols)}) VALUES ({vals})")
        print(f"ON CONFLICT (slug) DO UPDATE SET {sets};")
    conn.close()


if __name__ == "__main__":
    main()
