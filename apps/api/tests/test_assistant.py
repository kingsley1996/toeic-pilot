"""Trợ lý trang web — ngữ cảnh, lịch sử, và các cổng ở endpoint.

Cùng lớp với `test_llm_gateway.py`: phần đáng kiểm là QUYẾT ĐỊNH (cổng nào chặn,
lịch sử gửi gì, hàng nào ghi lại), không phải lượt gọi model thật.
"""

from __future__ import annotations

import uuid
from datetime import UTC

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.ai_budget import Budget
from app.models.chat import CoachConversation, CoachMessage
from app.models.practice import Attempt, PracticeTest
from app.models.user import User
from app.services.assistant import TOOL_SCHEMAS, ask
from app.services.llm.base import LLMRequest, LLMResult, ToolCall, Usage
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


def test_ask_ghi_CAP_HOI_DAP_vao_mot_cuoc_khong_neo(db_session, fake_redis) -> None:
    user = a_user(db_session)
    gw = build_gateway(db_session, fake_redis, FakeProvider(reply="trả lời giả"))
    turn = ask(db_session, gw, user=user, question="Trang này có gì?")

    assert turn.conversation.attempt_id is None
    rows = db_session.query(CoachMessage).order_by(CoachMessage.position).all()
    assert [r.role for r in rows] == ["user", "assistant"]
    assert rows[0].content == "Trang này có gì?"


def test_LICH_SU_luot_truoc_di_vao_messages_USER_khong_vao_system(db_session, fake_redis) -> None:
    """Cùng ranh giới an toàn với coach: chữ người học không được thành chỉ dẫn.

    Vòng tool đổi hình gửi: lịch sử giờ là các tin nhắn user/assistant trong
    `messages`, và luật vẫn giữ được vì system do ta viết toàn phần.
    """
    user = a_user(db_session)
    fake = FakeProvider(reply="ok")
    gw = build_gateway(db_session, fake_redis, fake)

    ask(db_session, gw, user=user, question="câu thứ nhất")
    ask(db_session, gw, user=user, question="câu thứ hai")

    assert all("câu thứ nhất" not in req.system for req, _ in fake.seen)
    second_messages = fake.seen[1][0].messages
    user_texts = [m["content"] for m in second_messages if m["role"] == "user"]
    assert any("câu thứ nhất" in c for c in user_texts)
    assert user_texts[-1] == "câu thứ hai"


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


# --- Vòng tool -------------------------------------------------------------


def script_tool_loop(req: LLMRequest) -> LLMResult:
    """Lượt 1: xin gọi công cụ; lượt 2: trả lời dựa trên kết quả công cụ."""
    if not any(m.get("role") == "tool" for m in req.messages or []):
        return LLMResult(
            text="",
            usage=Usage(prompt=10, completion=5),
            model="fake-1",
            provider="fake",
            tool_calls=(ToolCall(id="call-1", name="trang_thai_hoc_tap", arguments="{}"),),
        )
    return LLMResult(
        text="Bạn đang ở level 1.",
        usage=Usage(prompt=10, completion=5),
        model="fake-1",
        provider="fake",
    )


def test_HOI_VE_BAN_THAN_thi_GOI_CONG_CU_lay_so_that(db_session, fake_redis) -> None:
    """Số cá nhân KHÔNG nằm trong ngữ cảnh nữa — tool phải chạy thật."""
    fake = FakeProvider(reply=script_tool_loop)
    gw = build_gateway(db_session, fake_redis, fake)
    user = a_user(db_session)

    turn = ask(db_session, gw, user=user, question="tiến độ của tôi thế nào?")

    assert turn.answer.content == "Bạn đang ở level 1."
    assert len(fake.seen) == 2  # hai lượt gọi model: xin tool → trả lời
    # Lượt 2 phải mang kết quả tool dưới dạng tin nhắn role="tool"
    tool_msgs = [m for m in fake.seen[1][0].messages if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert '"level": 1' in tool_msgs[0]["content"]


def test_CAU_HOI_THUONG_khong_goi_cong_cu(db_session, fake_redis) -> None:
    """Câu không cần số cá nhân thì một lượt gọi model là đủ."""
    fake = FakeProvider(reply="Trang có khu luyện thi.")
    gw = build_gateway(db_session, fake_redis, fake)
    user = a_user(db_session)
    ask(db_session, gw, user=user, question="trang này làm được gì?")
    assert len(fake.seen) == 1


def test_tools_di_vao_PAYLOAD_dung_schema(db_session, fake_redis) -> None:
    fake = FakeProvider(reply="ok")
    gw = build_gateway(db_session, fake_redis, fake)
    ask(db_session, gw, user=a_user(db_session), question="hi")
    sent_tools = fake.seen[0][0].tools
    names = {t["function"]["name"] for t in sent_tools}
    assert names == {s["function"]["name"] for s in TOOL_SCHEMAS}


def test_CONG_CU_KHONG_TON_TAI_thi_bao_loi_cho_model(db_session, fake_redis) -> None:
    """Model gọi tên sai: trả lỗi về CHO MODEL thay vì chết cả lượt hỏi."""
    calls = {"n": 0}

    def script(req: LLMRequest) -> LLMResult:
        calls["n"] += 1
        if calls["n"] == 1:
            return LLMResult(
                text="",
                usage=Usage(prompt=1, completion=1),
                model="m",
                provider="fake",
                tool_calls=(ToolCall(id="x", name="khong_ton_tai", arguments="{}"),),
            )
        return LLMResult(
            text="đã hiểu", usage=Usage(prompt=1, completion=1), model="m", provider="fake"
        )

    provider = FakeProvider(reply=script)
    gw = build_gateway(db_session, fake_redis, provider)
    turn = ask(db_session, gw, user=a_user(db_session), question="xin chào")
    assert turn.answer.content == "đã hiểu"
    tool_msg = [m for m in provider.seen[1][0].messages if m["role"] == "tool"][0]
    assert "không có công cụ" in tool_msg["content"]


def test_LAP_CONG_CU_QUA_3_LUOT_thi_HONG_ca_luot(db_session, fake_redis) -> None:
    """Model chỉ biết xin tool mãi: hỏng TOÀN LƯỢT — câu trả lời thiếu số là
    câu bịa có lớp vỏ hoàn chỉnh, tệ hơn là lỗi."""

    def script(_: LLMRequest) -> LLMResult:
        return LLMResult(
            text="",
            usage=Usage(prompt=1, completion=1),
            model="m",
            provider="fake",
            tool_calls=(ToolCall(id="x", name="trang_thai_hoc_tap", arguments="{}"),),
        )

    gw = build_gateway(db_session, fake_redis, FakeProvider(reply=script))
    with pytest.raises(ValueError, match="3 lượt"):
        ask(db_session, gw, user=a_user(db_session), question="tiến độ?")


def test_TOOL_luot_thi_tra_DUNG_CUA_CHINH_USER(db_session, fake_redis) -> None:
    """Tool không nhận user_id — nó đọc đúng user của request, không đọc được
    của người khác; đây là phép kiểm rằng đường trả về đúng chủ."""
    from datetime import datetime

    user = a_user(db_session)
    test = PracticeTest(slug="t1", title="Đề một", status="published", kind="mini")
    db_session.add(test)
    db_session.commit()
    db_session.add(
        Attempt(
            user_id=user.id,
            test_id=test.id,
            status="submitted",
            submitted_at=datetime.now(UTC),
            total_scaled=650,
        )
    )
    db_session.commit()

    FakeProvider(reply=script_tool_loop)

    # đổi tool sang luot_thi_gan_day cho khớp câu hỏi
    def script_attempts(req: LLMRequest) -> LLMResult:
        if not any(m.get("role") == "tool" for m in req.messages or []):
            return LLMResult(
                text="",
                usage=Usage(prompt=1, completion=1),
                model="m",
                provider="fake",
                tool_calls=(ToolCall(id="c", name="luot_thi_gan_day", arguments="{}"),),
            )
        return LLMResult(
            text="653 điểm", usage=Usage(prompt=1, completion=1), model="m", provider="fake"
        )

    fake2 = FakeProvider(reply=script_attempts)
    gw = build_gateway(db_session, fake_redis, fake2)
    turn = ask(db_session, gw, user=user, question="điểm thi gần nhất của tôi?")
    attempt_msg = [m for m in fake2.seen[1][0].messages if m["role"] == "tool"][0]
    assert "650" in attempt_msg["content"]
    assert turn.answer.content == "653 điểm"


def test_CONG_CU_LOI_THI_tra_LOI_ve_model_khong_phai_500(db_session, fake_redis) -> None:
    """Tool lỗi (vd limit="abc") không chết 500 — error trả về cho model sửa."""
    calls = {"n": 0}

    def script(req: LLMRequest) -> LLMResult:
        calls["n"] += 1
        if calls["n"] == 1:
            return LLMResult(
                text="",
                usage=Usage(prompt=1, completion=1),
                model="m",
                provider="fake",
                tool_calls=(
                    ToolCall(id="x", name="luot_thi_gan_day", arguments='{"limit": "abc"}'),
                ),
            )
        return LLMResult(
            text="đã sửa lỗi, cảm ơn",
            usage=Usage(prompt=1, completion=1),
            model="m",
            provider="fake",
        )

    provider = FakeProvider(reply=script)
    gw = build_gateway(db_session, fake_redis, provider)
    turn = ask(db_session, gw, user=a_user(db_session), question="điểm thi gần nhất?")
    assert turn.answer.content == "đã sửa lỗi, cảm ơn"
    # Lượt 2 phải có tool message chứa lỗi, không phải 500
    tool_msgs = [m for m in provider.seen[1][0].messages if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert "error" in tool_msgs[0]["content"].lower()
