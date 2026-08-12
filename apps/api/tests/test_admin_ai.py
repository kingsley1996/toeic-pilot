"""Khu quản trị tầng AI: duyệt nhãn theo mặt phân loại, và thống kê.

Bài quan trọng nhất là bài giữ `proposed_code` sau khi người sửa. Mất nó thì KPI
độ đúng không còn tính được, mà mất một cách im lặng — mọi thứ vẫn chạy, chỉ là
con số "máy đúng bao nhiêu phần trăm" trở thành 100% mãi mãi.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import Question, QuestionOption, QuestionSet
from app.models.labels import QuestionLabel
from app.models.user import User

LABELS = "/api/v1/admin/ai/labels"


@pytest.fixture()
def auth(db_session: Session) -> Callable[[str], dict[str, str]]:
    cache: dict[str, dict[str, str]] = {}

    def make(role: str) -> dict[str, str]:
        if role not in cache:
            user = User(email=f"{role}@example.com", hashed_password="x", role=role)
            db_session.add(user)
            db_session.commit()
            cache[role] = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
        return cache[role]

    return make


def a_question(db_session: Session, part: int = 5, proposed: str | None = None) -> Question:
    # Part 3, 4, 6, 7 BẮT BUỘC thuộc một nhóm — `ck_question_set_required`, và
    # đó là luật thật của đề thi (ADR-001 §A4.2), không phải chi tiết của test.
    group = None
    if part in (3, 4, 6, 7):
        group = QuestionSet(part=part, title=f"Nhóm part {part}")
        db_session.add(group)
        db_session.commit()
    question = Question(
        part=part,
        difficulty=2,
        source="original",
        status="draft",
        prompt_text="The report ____.",
        set_id=group.id if group else None,
        position=1 if group else None,
    )
    question.options = [
        QuestionOption(label=chr(65 + i), content=f"x{i}", is_correct=i == 0) for i in range(4)
    ]
    db_session.add(question)
    db_session.commit()
    if proposed:
        db_session.add(
            QuestionLabel(
                question_id=question.id,
                facet="question_type",
                code=proposed,
                proposed_code=proposed,
            )
        )
        db_session.commit()
    return question


def test_sua_nhan_KHONG_lam_mat_nhan_may_de_xuat(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    question = a_question(db_session, proposed="PART_5_GRAMMAR")

    response = client.patch(
        f"{LABELS}/{question.id}",
        json={"facet": "question_type", "code": "PART_5_VOCABULARY"},
        headers=auth("admin"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "PART_5_VOCABULARY"
    # Giữ nguyên. Cột duy nhất nói được "người đã phải SỬA" chứ không chỉ "đã xem".
    assert body["proposed_code"] == "PART_5_GRAMMAR"
    # Người kiểm lấy từ PHIÊN, không từ body.
    assert body["reviewed_by"] == "admin@example.com"


def test_ma_khong_hop_le_voi_PART_nay_bi_tu_choi(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """`GRAMMAR_NOUN` có thật, nhưng chỉ ở Part 5 — không có ở Part 6.

    Đây là kiểu sai im lặng nhất: mã tồn tại, đúng mặt, chỉ sai part. Nhận vào
    thì thống kê mọc thêm một nhóm cho thứ đề thi không kiểm ở phần đó.
    """
    question = a_question(db_session, part=6)
    response = client.patch(
        f"{LABELS}/{question.id}",
        json={"facet": "grammar", "code": "GRAMMAR_NOUN"},
        headers=auth("admin"),
    )
    assert response.status_code == 422
    assert "Part 6" in response.json()["detail"]


def test_ma_dung_nhung_SAI_MAT_bi_tu_choi(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Ghi một mã `grammar` vào mặt `question_type` sẽ ĐÈ nhãn của mặt kia.

    Khoá chính là `(question_id, facet)`, nên một mã sai mặt không tạo hàng mới
    mà ghi đè hàng đang có — mất nhãn cũ, không lỗi nào.
    """
    question = a_question(db_session)
    response = client.patch(
        f"{LABELS}/{question.id}",
        json={"facet": "question_type", "code": "GRAMMAR_TENSE"},
        headers=auth("admin"),
    )
    assert response.status_code == 422
    assert "không thuộc mặt" in response.json()["detail"]


def test_nhan_cua_NGU_LIEU_CHUNG_ghi_mot_lan_cho_ca_nhom(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Chủ đề Part 3 là thuộc tính của hội thoại, không của từng câu."""
    group = QuestionSet(part=3, title="Đặt phòng")
    db_session.add(group)
    db_session.commit()

    response = client.patch(
        f"/api/v1/admin/ai/set-labels/{group.id}",
        json={"facet": "topic", "code": "PART_3_HOUSING"},
        headers=auth("admin"),
    )
    assert response.status_code == 200
    assert response.json()["code"] == "PART_3_HOUSING"


def test_mat_cua_SET_khong_ghi_duoc_vao_cau(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    question = a_question(db_session, part=3)
    response = client.patch(
        f"{LABELS}/{question.id}",
        json={"facet": "topic", "code": "PART_3_HOUSING"},
        headers=auth("admin"),
    )
    assert response.status_code == 422
    assert "thuộc về set" in response.json()["detail"]


def test_thong_ke_tinh_do_dung_theo_TUNG_MAT(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Một con số gộp che mất chuyện máy đoán tốt mặt này mà tệ mặt kia."""
    keeps = a_question(db_session, proposed="PART_5_GRAMMAR")
    corrects = a_question(db_session, proposed="PART_5_GRAMMAR")
    client.patch(
        f"{LABELS}/{keeps.id}",
        json={"facet": "question_type", "code": "PART_5_GRAMMAR"},
        headers=auth("admin"),
    )
    client.patch(
        f"{LABELS}/{corrects.id}",
        json={"facet": "question_type", "code": "PART_5_VOCABULARY"},
        headers=auth("admin"),
    )

    stats = client.get("/api/v1/admin/ai/stats", headers=auth("admin")).json()
    by_facet = {row["facet"]: row for row in stats["facets"]}
    assert by_facet["question_type"]["reviewed"] == 2
    assert by_facet["question_type"]["agreeing"] == 1


def test_chuong_cua_tra_202_chu_khong_phai_200(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """202 là lời hứa đúng: đã nhận yêu cầu, chưa hứa nhãn đã có."""
    response = client.post("/api/v1/admin/ai/skill-tags/requests", headers=auth("admin"))
    assert response.status_code == 202


def test_chi_chon_duoc_model_CO_GIA(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """`cost_usd` ném lỗi với model lạ chứ không ghi 0 — hành vi đúng, nhưng nó
    phải hỏng ở chỗ CHỌN chứ không ở chỗ CHẠY.

    Không có phép kiểm này thì một lần gõ nhầm tên model làm mọi lượt gọi của
    tính năng đó hỏng, và thông báo lỗi nói về bảng giá chứ không nói về ô vừa
    bấm lưu.
    """
    response = client.put(
        "/api/v1/admin/ai/features/coach_explain",
        json={"provider": "ollama", "model": "model-khong-ton-tai", "enabled": True},
        headers=auth("admin"),
    )
    assert response.status_code == 422
    assert "bảng giá" in response.json()["detail"]


def test_tinh_nang_khong_co_trong_ma_thi_404(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Danh sách tính năng nằm trong MÃ, không trong database.

    Để nó ở database thì giao diện cho phép tạo một tính năng không ai xử lý —
    một hàng cấu hình trỏ vào hư không, trông hoàn toàn hợp lệ.
    """
    response = client.put(
        "/api/v1/admin/ai/features/tinh_nang_bia",
        json={"provider": "ollama", "model": "gemma3:latest", "enabled": True},
        headers=auth("admin"),
    )
    assert response.status_code == 404


def test_chua_cau_hinh_thi_bao_la_CHUA_CAU_HINH_chu_khong_bo_trong(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Ô trống đọc như "chưa dùng được", trong khi tính năng vẫn đang chạy bằng
    cấu hình từ biến môi trường."""
    rows = client.get("/api/v1/admin/ai/features", headers=auth("admin")).json()
    coach = next(r for r in rows if r["key"] == "coach_explain")
    assert coach["configured"] is False
    assert coach["provider"] is None
    assert coach["enabled"] is True


def test_tat_mot_tinh_nang_thi_gateway_TU_CHOI_va_ghi_so(db_session: Session, fake_redis) -> None:
    """Tắt có chủ ý khác hẳn nhà cung cấp hỏng: thử lại bao nhiêu lần cũng thế.

    Và lượt bị chặn vẫn phải thành một hàng trong sổ — bỏ nó thì không ai biết
    một tính năng đã tắt bao lâu và chặn bao nhiêu lượt, mà câu đó luôn được hỏi
    ngay sau khi có người phàn nàn.
    """
    import pytest
    from sqlalchemy.orm import sessionmaker

    from app.core.ai_budget import Budget
    from app.models.ai import AiInteraction
    from app.services.llm.base import FeatureDisabled, LLMRequest
    from app.services.llm.fake import FakeProvider
    from app.services.llm.gateway import Gateway
    from app.services.llm.router import Tier

    gateway = Gateway(
        providers={"fake": FakeProvider()},
        routes={Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")},
        budget=Budget(limit_micro=10_000_000),
        redis_client=fake_redis,  # type: ignore[arg-type]
        session_factory=sessionmaker(bind=db_session.get_bind()),
        resolve_feature=lambda _f: ("fake", "fake-1", False),
    )
    with pytest.raises(FeatureDisabled):
        gateway.run(LLMRequest(system="s", user="u"), feature="coach_explain", tier=Tier.CHEAP)

    (row,) = db_session.query(AiInteraction).all()
    assert row.status == "refused"
    assert "đang tắt" in (row.error or "")
