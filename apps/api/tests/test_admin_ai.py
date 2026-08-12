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
