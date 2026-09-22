"""Chạy eval AI từ giao diện: xem suite, xếp lượt, đọc báo cáo.

Ranh giới kiến trúc của cả tệp này: route KHÔNG import `app.content`
(PHASE2-AUDIO §A4.1) — endpoint chỉ đọc file tĩnh và ghi hàng đợi; worker
(cùng ảnh với worker TTS) mới là thứ chạy suite. Bài đầu ghim đúng chỗ đó.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.user import User

EVAL = "/api/v1/admin/ai/eval"


def _auth(db_session: Session) -> dict[str, str]:
    admin = User(email="eval-admin@example.com", hashed_password="x", role="admin")
    db_session.add(admin)
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(str(admin.id))}"}


def test_route_KHONG_import_app_content() -> None:
    """Mọi import trong `admin_ai` phải sống được trong ảnh prod (không extra
    `content`). Đụng `app.content` là `test_content_isolation` đỏ — bài này nói
    trước bằng lời của route eval."""
    import app.api.routes.admin_ai as route_mod

    assert not route_mod.__name__.startswith("app.content")
    assert "app.content" not in str(getattr(route_mod, "__file__", ""))


def test_overview_liet_ke_dung_5_suite(client: TestClient, db_session: Session) -> None:
    from app.content.eval_core import SUITES

    body = client.get(f"{EVAL}/overview", headers=_auth(db_session)).json()
    assert {s["name"] for s in body["suites"]} == set(SUITES)
    assert all(s["cases"] > 0 and s["threshold"] > 0 for s in body["suites"])
    assert isinstance(body["manifest_match"], bool)


def test_queue_tu_choi_suite_la_va_judge_thieu_model(
    client: TestClient, db_session: Session
) -> None:
    headers = _auth(db_session)
    assert (
        client.post(f"{EVAL}/runs", json={"suite": "khong-co"}, headers=headers).status_code == 422
    )
    assert client.post(f"{EVAL}/runs", json={"suite": "judge"}, headers=headers).status_code == 400
    same = {"suite": "judge", "judge_model": "a/m", "gen_model": "a/m"}
    assert client.post(f"{EVAL}/runs", json=same, headers=headers).status_code == 400


def test_queue_va_doc_luot_chay(client: TestClient, db_session: Session) -> None:
    headers = _auth(db_session)
    created = client.post(f"{EVAL}/runs", json={"suite": "coach"}, headers=headers)
    assert created.status_code == 202
    assert created.json()["status"] == "queued"

    listed = client.get(f"{EVAL}/runs", headers=headers).json()
    assert any(row["id"] == created.json()["id"] for row in listed)

    detail = client.get(f"{EVAL}/runs/{created.json()['id']}", headers=headers).json()
    assert detail["suite"] == "coach" and detail["report"] is None

    assert (
        client.get(f"{EVAL}/runs/00000000-0000-0000-0000-000000000000", headers=headers).status_code
        == 404
    )


def test_worker_chay_luot_queued_thanh_done(db_session: Session) -> None:
    """Worker dùng được: hàng queued → done + report, không cần Redis chạy."""
    from sqlalchemy.orm import sessionmaker

    from app.content.eval_worker import process_one
    from app.models.eval_run import EvalRun

    db_session.add(EvalRun(suite="coach", status="queued"))
    db_session.commit()
    factory = sessionmaker(bind=db_session.get_bind())

    assert process_one(factory) is not None

    row = db_session.query(EvalRun).order_by(EvalRun.created_at.desc()).first()
    assert row.status == "done"
    assert row.report["suites"][0]["name"] == "coach"
    assert row.finished_at is not None


def test_worker_khong_viec_thi_thoi(db_session: Session) -> None:
    from sqlalchemy.orm import sessionmaker

    from app.content.eval_worker import process_one

    assert process_one(sessionmaker(bind=db_session.get_bind())) is None


def test_worker_judge_trung_model_thi_error_chu_khong_goi(db_session: Session) -> None:
    """Từ chối trùng model xảy ra TRƯỚC mọi lượt gọi — worker kiểm params
    trước khi dựng gateway, nên không tốn một xu."""
    from sqlalchemy.orm import sessionmaker

    from app.content.eval_worker import process_one
    from app.models.eval_run import EvalRun

    db_session.add(
        EvalRun(
            suite="judge",
            status="queued",
            params={"judge_model": "a/m", "gen_model": "a/m"},
        )
    )
    db_session.commit()
    assert process_one(sessionmaker(bind=db_session.get_bind())) is not None
    row = db_session.query(EvalRun).order_by(EvalRun.created_at.desc()).first()
    assert row.status == "error" and "trùng" in (row.error or "")
