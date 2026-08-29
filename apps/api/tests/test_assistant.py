"""Trợ lý trang web — ngữ cảnh, lịch sử, và các cổng ở endpoint.

Cùng lớp với `test_llm_gateway.py`: phần đáng kiểm là QUYẾT ĐỊNH (cổng nào chặn,
lịch sử gửi gì, hàng nào ghi lại), không phải lượt gọi model thật.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.ai_budget import Budget
from app.models.chat import CoachConversation, CoachMessage
from app.models.user import User
from app.services.assistant import ask, learner_context
from app.services.llm.base import LLMRequest
from app.services.llm.fake import FakeProvider
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier


def build_gateway(
    db_session: Session,
    fake_redis,
    provider: FakeProvider,
    *,
    resolve_feature=None,
    limit_micro: int = 1_000_000,
) -> Gateway:
    return Gateway(
        providers={"fake": provider},
        routes={Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")},
        budget=Budget(limit_micro=limit_micro),
        redis_client=fake_redis,  # type: ignore[arg-type]
        session_factory=sessionmaker(bind=db_session.get_bind()),
        resolve_feature=resolve_feature,
    )


def a_user(db_session: Session) -> User:
    user = User(email=f"{uuid.uuid4().hex}@example.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    return user


def test_ngu_canh_mang_SO_THAT_tu_cac_service(db_session: Session) -> None:
    """Ngữ cảnh học viên suy ra từ đúng nguồn thống kê — không bảng tổng nào."""
    user = a_user(db_session)
    ctx = learner_context(db_session, user)
    assert "level 1" in ctx
    assert "0" in ctx  # chưa thuộc từ nào, chưa nộp bài nào


def test_ask_ghi_CAP_HOI_DAP_vao_mot_cuoc_khong_neo(db_session, fake_redis) -> None:
    user = a_user(db_session)
    gw = build_gateway(db_session, fake_redis, FakeProvider(reply="trả lời giả"))
    turn = ask(db_session, gw, user=user, question="Trang này có gì?")

    assert turn.conversation.attempt_id is None
    rows = db_session.query(CoachMessage).order_by(CoachMessage.position).all()
    assert [r.role for r in rows] == ["user", "assistant"]
    assert rows[0].content == "Trang này có gì?"


def test_LICH_SU_luot_truoc_di_vao_luot_user_khong_vao_system(db_session, fake_redis) -> None:
    """Cùng ranh giới an toàn với coach: chữ người học không được thành chỉ dẫn."""
    user = a_user(db_session)
    fake = FakeProvider(reply="ok")
    gw = build_gateway(db_session, fake_redis, fake)

    ask(db_session, gw, user=user, question="câu thứ nhất")
    ask(db_session, gw, user=user, question="câu thứ hai")

    system_texts = [req.system for req, _ in fake.seen]
    assert all("câu thứ nhất" not in s for s in system_texts)
    user_turns = [req.user for req, _ in fake.seen]
    assert "câu thứ nhất" in user_turns[1]


def test_ask_MOT_NGUOI_MOT_CUOC(db_session, fake_redis) -> None:
    user = a_user(db_session)
    gw = build_gateway(db_session, fake_redis, FakeProvider())
    ask(db_session, gw, user=user, question="một")
    ask(db_session, gw, user=user, question="hai")

    conversations = db_session.query(CoachConversation).all()
    assert len(conversations) == 1
    assert db_session.query(CoachMessage).count() == 4


def test_cuoc_khong_neo_KHONG_DUOC_chay_qua_duong_coach(db_session) -> None:
    user = a_user(db_session)
    conversation = CoachConversation(user_id=user.id, attempt_id=None)
    db_session.add(conversation)
    db_session.commit()

    from app.services.chat import ask as coach_ask
    from app.services.retrieval import AnchoredRetriever

    with pytest.raises(ValueError):
        coach_ask(
            db_session,
            build_gateway(db_session, None, FakeProvider()),
            AnchoredRetriever(db_session),
            conversation=conversation,
            question="x",
        )


# --- Endpoint ---


def test_endpoint_doi_DANG_NHAP(client: TestClient) -> None:
    assert client.post("/api/v1/assistant/chat", json={"message": "hi"}).status_code == 401
    assert client.get("/api/v1/assistant/chat").status_code == 401


def test_endpoint_RONG_va_QUA_DAI_bi_422(client: TestClient, auth) -> None:
    headers = auth("learner")
    assert (
        client.post("/api/v1/assistant/chat", json={"message": "  "}, headers=headers).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/assistant/chat", json={"message": "x" * 1001}, headers=headers
        ).status_code
        == 422
    )


def test_chua_co_lich_su_thi_tra_TRANG_RONG(client: TestClient, auth) -> None:
    response = client.get("/api/v1/assistant/chat", headers=auth("learner"))
    assert response.status_code == 200
    body = response.json()
    # `Page[T]`, không phải mảng trần: cuộc trợ lý cuốn theo mãi mãi nên nó tăng
    # theo mức dùng — ca (C) của `schemas/common.py`.
    assert body["items"] == []
    assert body["total"] == 0


def test_TINH_NANG_TAT_thi_503(
    client: TestClient, auth, db_session: Session, fake_redis, monkeypatch
) -> None:
    from app.api.routes import assistant as assistant_route

    gw = build_gateway(
        db_session,
        fake_redis,
        FakeProvider(),
        resolve_feature=lambda feature: ("fake", "fake-1", False),
    )
    monkeypatch.setattr(assistant_route, "get_gateway", lambda db: gw)
    response = client.post(
        "/api/v1/assistant/chat", json={"message": "xin chào"}, headers=auth("learner")
    )
    assert response.status_code == 503


def test_HET_HAN_MUC_thi_429(
    client: TestClient, auth, db_session: Session, fake_redis, monkeypatch
) -> None:
    from app.api.routes import assistant as assistant_route

    gw = build_gateway(
        db_session,
        fake_redis,
        FakeProvider(),
        resolve_feature=lambda feature: ("fake", "fake-1", True),
        limit_micro=1,
    )
    monkeypatch.setattr(assistant_route, "get_gateway", lambda db: gw)
    # auth("learner") TẠO tài khoản ở lần gọi đầu, nên gọi nó trước khi tra id.
    headers = auth("learner")
    learner = db_session.query(User).filter_by(email="learner@example.com").first()
    assert learner is not None
    fake_redis.values[f"aibudget:{learner.id}"] = "999999"

    response = client.post("/api/v1/assistant/chat", json={"message": "xin chào"}, headers=headers)
    assert response.status_code == 429


def test_HAPPY_PATH_ghi_va_tra_TURN(
    client: TestClient, auth, db_session: Session, fake_redis, monkeypatch
) -> None:
    """Gateway thật bị thay bằng FakeProvider ở đúng seam — router không đổi."""
    from app.api.routes import assistant as assistant_route

    fake = FakeProvider(reply="Trả lời từ trợ lý.")
    gw = build_gateway(
        db_session,
        fake_redis,
        fake,
        resolve_feature=lambda feature: ("fake", "fake-1", True),
    )
    monkeypatch.setattr(assistant_route, "get_gateway", lambda db: gw)

    headers = auth("learner")
    sent = client.post(
        "/api/v1/assistant/chat", json={"message": "Trang này có gì?"}, headers=headers
    )
    assert sent.status_code == 200
    body = sent.json()
    assert body["answer"]["content"] == "Trả lời từ trợ lý."

    # Lần gọi thứ hai phải mang ngữ cảnh trang — bản hướng dẫn nằm trong system.
    assert any("TOEIC Pilot là nền tảng" in req.system for req, _ in fake.seen)

    page = client.get("/api/v1/assistant/chat", headers=headers).json()
    # MỚI NHẤT TRƯỚC: trang đầu phải là thứ vừa nói, nên thứ tự là đáp rồi hỏi.
    # Giao diện đảo lại để đọc theo mạch trò chuyện.
    assert [m["role"] for m in page["items"]] == ["assistant", "user"]
    assert page["items"][-1]["content"] == "Trang này có gì?"
    assert page["total"] == 2


def test_LLMRequest_dung_FEATURE_tro_ly(db_session, fake_redis) -> None:
    """Feature riêng để tắt trợ lý mà không tắt coach (và để sổ cái tách được)."""
    seen_features: list[str] = []

    class ProbeGateway(Gateway):
        def run(self, request: LLMRequest, **kwargs):  # noqa: ANN003
            seen_features.append(kwargs["feature"])
            return super().run(request, **kwargs)

    user = a_user(db_session)
    gw = ProbeGateway(
        providers={"fake": FakeProvider()},
        routes={Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")},
        budget=Budget(limit_micro=1_000_000),
        redis_client=fake_redis,  # type: ignore[arg-type]
        session_factory=sessionmaker(bind=db_session.get_bind()),
    )
    ask(db_session, gw, user=user, question="xin chào")
    assert seen_features == ["assistant_chat"]
