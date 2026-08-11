"""Lượt làm bài: những gì tới được tay người học, và những gì không.

Trọng tâm ở đây là **bộ lọc `published`**, không phải phép chấm điểm (đã có
`test_scoring.py`). Nội dung chưa duyệt lọt ra ngoài là kiểu hỏng im lặng: nó
trông hoàn toàn bình thường với người học, nên không ai báo lại.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import PracticeTest, QuestionSet, User

# Part 7: một ngữ liệu dùng chung sinh ra `question_set`, đúng thứ cần để kiểm
# bộ lọc hai tầng. Không cần audio hay ảnh nên nó xuất bản được ngay.
PASTE = """[PASSAGE] Thông báo
The lobby entrance will be closed from Wednesday for maintenance.

[QUESTION]
What is the notice mainly about?
(A) A change of address
(B) Building maintenance
(C) A new tenant
(D) A rent increase
answer: B
source: original
explanation: Đoạn văn nói về việc đóng cửa sảnh để bảo trì.
"""


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


PART5 = """[QUESTION]
The board approved the ____ budget for the next quarter.
(A) annual
(B) annually
(C) annualize
(D) annuity
answer: A
source: original
explanation: Cần một tính từ bổ nghĩa cho "budget".
"""


def add_part(client: TestClient, headers: dict[str, str], slug: str, part: int, raw: str) -> None:
    parsed = client.post(
        f"/api/v1/admin/tests/{slug}/parts/{part}/parse",
        json={"raw_text": raw},
        headers=headers,
    ).json()
    assert parsed["error_count"] == 0, parsed
    client.post(
        f"/api/v1/admin/tests/{slug}/parts",
        json={"part": part, "groups": parsed["groups"]},
        headers=headers,
    )


def published_test(client: TestClient, headers: dict[str, str], slug: str = "sat") -> None:
    """Một đề đã xuất bản, có đúng một cụm Part 7 và một câu trong đó."""
    client.post(
        "/api/v1/admin/tests",
        json={"slug": slug, "title": "Đề thử", "kind": "mini"},
        headers=headers,
    )
    add_part(client, headers, slug, 7, PASTE)
    for question in client.get(f"/api/v1/admin/tests/{slug}/questions", headers=headers).json():
        assert (
            client.post(
                f"/api/v1/admin/questions/{question['id']}/publish", headers=headers
            ).status_code
            == 200
        )
    assert client.post(f"/api/v1/admin/tests/{slug}/publish", headers=headers).status_code == 200


def start(client: TestClient, headers: dict[str, str], slug: str = "sat"):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/attempts",
        json={"test_slug": slug, "parts": [], "review_mode": "exam"},
        headers=headers,
    )


def test_a_learner_can_start_an_attempt_on_a_published_test(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    published_test(client, auth("admin"))

    response = start(client, auth("learner"))

    assert response.status_code == 201
    assert len(response.json()["questions"]) == 1


def test_a_published_question_under_a_draft_set_stays_out(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Lọc `published` ở CẢ HAI tầng: câu, và cụm mà câu thuộc về.

    Lọc mỗi câu là một chỗ hở im lặng — câu đã xuất bản nằm dưới cụm còn nháp sẽ
    mang theo cả ngữ liệu lẫn bản thu của cụm đó ra ngoài, vì `_passages` đọc
    thẳng từ `question_set`. Người học thấy một bài đọc chưa ai duyệt, và nó
    trông hoàn toàn bình thường.

    Cùng hình dạng với lỗ rò cây dictation, và đó là lý do cây ấy lọc `published`
    ở cả bốn tầng.
    """
    published_test(client, auth("admin"))

    # Chỉ hạ CỤM xuống nháp; câu vẫn `published`.
    stimulus = db_session.scalars(select(QuestionSet)).one()
    stimulus.status = "draft"
    db_session.commit()

    response = start(client, auth("learner"))

    assert response.status_code == 400
    assert "Không có câu hỏi nào" in response.json()["detail"]


def test_a_standalone_question_survives_the_set_filter(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """`question.set_id` là NULL ở Part 1, 2 và 5 — câu đứng riêng, không cụm.

    Dùng `join` thường thay vì `outerjoin` sẽ lặng lẽ loại sạch ba part đó khỏi
    mọi lượt làm bài: hỏng nặng hơn hẳn lỗ rò nó định vá, và im lặng y như thế.

    Một đề có cả hai loại là phép kiểm hai chiều: câu Part 5 phải ĐI QUA, câu
    Part 7 dưới cụm nháp phải BỊ CHẶN.
    """
    headers = auth("admin")
    published_test(client, headers)
    add_part(client, headers, "sat", 5, PART5)
    for question in client.get("/api/v1/admin/tests/sat/questions", headers=headers).json():
        client.post(f"/api/v1/admin/questions/{question['id']}/publish", headers=headers)

    stimulus = db_session.scalars(select(QuestionSet)).one()
    stimulus.status = "draft"
    db_session.commit()

    response = start(client, auth("learner"))

    assert response.status_code == 201
    (served,) = response.json()["questions"]
    assert served["part"] == 5


def test_a_draft_test_is_not_startable(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    published_test(client, auth("admin"))
    test = db_session.scalars(select(PracticeTest)).one()
    test.status = "draft"
    db_session.commit()

    assert start(client, auth("learner")).status_code == 404
