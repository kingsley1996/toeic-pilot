"""Màn hình theo dõi hệ thống không được in bí mật ra.

Nó hiện tên nhà cung cấp cho từng phụ thuộc, mà tên ấy lấy từ chuỗi kết nối —
nơi Postgres và Redis đều mang mật khẩu. Bản đầu tiên cắt sai và trả nguyên
`user:password@host`; hàng dữ liệu vẫn hợp lệ, màn hình vẫn dựng, chỉ có mật
khẩu production nằm trên một trang làm ra để đưa người khác xem.
"""

import pytest

from app.api.routes.admin_system import _host


@pytest.mark.parametrize(
    ("url", "secret"),
    [
        (
            "postgresql+psycopg://postgres.abcdefgh:s3cr3tp4ss@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres",
            "s3cr3tp4ss",
        ),
        ("rediss://default:AY1tokenvalue@vital-raven-208868.upstash.io:6379", "AY1tokenvalue"),
        ("postgresql+psycopg://toeic:toeic@postgres:5432/toeic", "toeic:toeic"),
    ],
)
def test_host_never_carries_the_credential(url: str, secret: str) -> None:
    host = _host(url)
    assert secret not in host
    assert "@" not in host


def test_host_keeps_enough_to_recognise_the_provider() -> None:
    assert _host("rediss://default:x@vital-raven-208868.upstash.io:6379") == (
        "vital-raven-208868.upstash.io:6379"
    )
    assert _host("redis://redis:6379/0") == "redis:6379"
