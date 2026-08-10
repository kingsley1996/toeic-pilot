from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from tests.test_storage import png

TICKET = "/api/v1/admin/media/images/ticket"
CONFIRM = "/api/v1/admin/media/images/confirm"

LICENCE = {
    "source_url": "https://example.com/photo",
    "license": "CC-BY-4.0",
    "attribution": "Ảnh: Nguyễn Văn A",
}


def headers_for(db_session: Session, role: str) -> dict[str, str]:
    user = User(email=f"{role}@example.com", hashed_password="x", role=role)
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture(autouse=True)
def local_media(tmp_path: Path):
    original_root, original_driver = settings.media_root, settings.image_storage_driver
    settings.media_root = tmp_path
    settings.image_storage_driver = "local"
    yield
    settings.media_root, settings.image_storage_driver = original_root, original_driver


def test_a_learner_cannot_ask_for_an_upload_ticket(client: TestClient, db_session: Session):
    """Vé upload là quyền tiêu tiền, nên nó là quyền của editor.

    Mọi endpoint admin đều có một test kiểu này (ADR-005): kiểm tra quyền là thứ
    dễ quên nhất khi thêm route mới, và quên thì không có gì báo.
    """
    learner = headers_for(db_session, "learner")
    assert client.post(TICKET, json={}, headers=learner).status_code == 403
    assert client.post(TICKET, json={}).status_code == 401


def test_the_upload_round_trip(client: TestClient, db_session: Session):
    """Bốn bước của ADR-006 §2.3, chạy qua driver local.

    Driver local giữ đúng hình dạng multipart của Cloudinary, nên đường đi được
    kiểm ở đây là đường đi frontend sẽ dùng thật.
    """
    editor = headers_for(db_session, "editor")

    ticket = client.post(TICKET, json={"ext": "png"}, headers=editor).json()
    # Khoá do PHÍA TA sinh: nếu client đặt được khoá thì một vé hợp lệ ghi đè
    # được lên đường dẫn của người khác.
    assert ticket["storage_key"].startswith("image/")
    assert "svg" not in ticket["allowed_formats"]

    upload = client.post(
        ticket["upload_url"],
        data=ticket["fields"],
        files={"file": ("photo.png", png(1200, 800), "image/png")},
    )
    assert upload.status_code == 200

    confirmed = client.post(
        CONFIRM, json={"storage_key": ticket["storage_key"], **LICENCE}, headers=editor
    )
    assert confirmed.status_code == 201
    body = confirmed.json()
    assert body["source"] == "uploaded"
    # Kích thước đọc từ file, không phải do client khai.
    assert (body["width"], body["height"]) == (1200, 800)

    # Gọi lại bước 4 là chuyện bình thường — mạng chập chờn, bấm hai lần. Thao
    # tác đã thành công rồi nên 409 chỉ khiến người ta upload lại.
    again = client.post(
        CONFIRM, json={"storage_key": ticket["storage_key"], **LICENCE}, headers=editor
    )
    assert again.json()["id"] == body["id"]


def test_confirm_refuses_a_key_with_no_file_behind_it(client: TestClient, db_session: Session):
    """Bước xác minh của §2.3.

    Không có nó, endpoint này là một đường ghi hàng asset tuỳ ý vào database: ai
    cũng gọi được với một `storage_key` bịa ra. Chính bước này bắt được lỗi
    `folder` khi chạy lên Cloudinary thật.
    """
    editor = headers_for(db_session, "editor")
    response = client.post(
        CONFIRM, json={"storage_key": "image/nothing-here.png", **LICENCE}, headers=editor
    )
    assert response.status_code == 400


def test_licence_fields_are_required(client: TestClient, db_session: Session):
    """Ba cột bản quyền là NOT NULL — bỏ trống phải là 422, không phải hàng thiếu."""
    editor = headers_for(db_session, "editor")
    payload = {"storage_key": "image/x.png", **LICENCE}
    del payload["attribution"]
    assert client.post(CONFIRM, json=payload, headers=editor).status_code == 422


def test_a_forged_ticket_cannot_write(client: TestClient, db_session: Session):
    editor = headers_for(db_session, "editor")
    ticket = client.post(TICKET, json={}, headers=editor).json()
    response = client.post(
        ticket["upload_url"],
        data={**ticket["fields"], "signature": "0" * 64},
        files={"file": ("x.png", png(8, 8), "image/png")},
    )
    assert response.status_code == 403


def test_the_ticket_endpoint_is_rate_limited(client: TestClient, db_session: Session):
    """Hạn mức là thứ đứng giữa một tài khoản và hoá đơn Cloudinary (P1-8)."""
    from app.api.routes.media import TICKET_QUOTA

    editor = headers_for(db_session, "editor")
    for _ in range(TICKET_QUOTA.limit):
        client.post(TICKET, json={}, headers=editor)
    over = client.post(TICKET, json={}, headers=editor)

    assert over.status_code == 429
    assert over.headers["Retry-After"]
