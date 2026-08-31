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
from app.models import Attempt, PracticeTest, QuestionSet, User

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


def test_the_history_never_reveals_correct_counts_while_a_test_is_in_progress(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """`correct_count` phải là NULL cho bài chưa nộp.

    Nó không chỉ là số liệu thiếu — với bài đang làm dở, "đúng mấy câu" CHÍNH LÀ
    đáp án: mở danh sách ở tab khác, đổi một lựa chọn, tải lại và xem con số
    nhích lên là dò được từng câu.
    """
    published_test(client, auth("admin"))
    learner = auth("learner")
    assert start(client, learner).status_code == 201

    page = client.get("/api/v1/attempts", headers=learner).json()
    (row,) = page["items"]

    assert row["status"] == "in_progress"
    assert row["correct_count"] is None
    assert row["question_count"] == 1


def test_the_history_shows_only_your_own_attempts(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    published_test(client, auth("admin"))
    assert start(client, auth("learner")).status_code == 201

    stranger = User(email="khac@example.com", hashed_password="x", role="learner")
    db_session.add(stranger)
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(str(stranger.id))}"}

    assert client.get("/api/v1/attempts", headers=headers).json()["items"] == []


def test_listing_does_not_finalise_an_expired_attempt(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Danh sách CHỈ đọc.

    `GET /{id}` chốt bài quá giờ, và đúng — mở nó ra thì phải chấm. Nhưng làm
    thế trong danh sách nghĩa là một lần mở trang lịch sử ghi hàng chục hàng vào
    database, và một GET không nên có tác dụng phụ ở quy mô đó.
    """
    published_test(client, auth("admin"))
    learner = auth("learner")
    start(client, learner)

    test = db_session.scalars(select(PracticeTest)).one()
    test.time_limit_seconds = 1
    attempt = db_session.scalars(select(Attempt)).one()
    attempt.elapsed_seconds = 9999
    db_session.commit()

    page = client.get("/api/v1/attempts", headers=learner).json()
    (row,) = page["items"]

    assert row["remaining_seconds"] == 0
    assert row["status"] == "in_progress"
    db_session.refresh(attempt)
    assert attempt.status == "in_progress"


def test_the_history_pages_without_dropping_or_repeating_a_row(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Lật trang phải phủ đúng mỗi hàng một lần.

    Điều kiện là thứ tự TOÀN PHẦN. `started_at DESC` một mình không đủ: hai lượt
    mở trong cùng một giây có thứ tự tương đối không xác định, nên với
    LIMIT/OFFSET một lượt hiện ở cả hai trang còn một lượt biến mất — im lặng,
    không lỗi nào được ném ra. Khoá phụ `id` là thứ khép kín nó.
    """
    published_test(client, auth("admin"))
    learner = auth("learner")
    for _ in range(5):
        assert start(client, learner).status_code == 201

    first = client.get("/api/v1/attempts?limit=2&offset=0", headers=learner).json()
    second = client.get("/api/v1/attempts?limit=2&offset=2", headers=learner).json()
    third = client.get("/api/v1/attempts?limit=2&offset=4", headers=learner).json()

    assert first["total"] == 5
    assert [len(page["items"]) for page in (first, second, third)] == [2, 2, 1]

    seen = [row["id"] for page in (first, second, third) for row in page["items"]]
    assert len(set(seen)) == 5


def test_ban_dich_KHONG_lo_khi_dang_thi(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Chế độ Luyện thi: `content_vi` và `spoken_text` phải là None cho tới khi nộp.

    Gửi bản dịch lúc đang làm bài là làm hỏng chính thứ bài thi đo — một câu từ
    vựng Part 5 chỉ cần đọc bản dịch là chọn được, còn Part 1/2 thì lời đọc
    chính là đáp án của một phần kiểm kỹ năng NGHE.
    """
    from app.models.practice import QuestionOption

    published_test(client, auth("admin"))
    option = db_session.query(QuestionOption).first()
    assert option is not None
    option.content_vi = "bản dịch bí mật"
    option.spoken_text = "spoken secret"
    db_session.commit()

    started = start(client, auth("learner")).json()
    served = started["questions"][0]["options"]
    assert all(o["content_vi"] is None for o in served)
    assert all(o["spoken_text"] is None for o in served)


PASTE_PART_5 = """[QUESTION]
The board approved the ____ budget for the next quarter.
(A) annual
-> thường niên
(B) annually
-> hằng năm
(C) annualize
-> quy đổi theo năm
(D) annuity
-> khoản niên kim
answer: A
source: original

[QUESTION]
She finished the report ____ than her colleagues.
(A) fast
-> nhanh
(B) faster
-> nhanh hơn
(C) fastest
-> nhanh nhất
(D) fastly
-> (không phải từ có thật)
answer: B
source: original
"""


def test_luyen_tap_chi_lo_dap_an_cua_cau_da_tra_loi(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Chế độ Luyện tập lộ theo TỪNG CÂU, không phải cả lượt làm.

    Lộ cả lượt ngay từ đầu là hỏng đúng thứ bài tập đo: với Part 1 và 2 thì
    "lộ" nghĩa là gửi kèm nguyên văn lời đọc, nên người học đọc được bốn câu
    trả lời trước khi bấm nghe. Với Part 5 thì bản dịch nói thẳng đáp án.

    Gác ở máy chủ chứ không ở giao diện — giấu bằng CSS vẫn để nguyên văn nằm
    trong payload.
    """
    admin = auth("admin")
    client.post(
        "/api/v1/admin/tests",
        json={"slug": "luyentap", "title": "Đề luyện tập", "kind": "mini"},
        headers=admin,
    )
    add_part(client, admin, "luyentap", 5, PASTE_PART_5)
    for question in client.get("/api/v1/admin/tests/luyentap/questions", headers=admin).json():
        assert (
            client.post(
                f"/api/v1/admin/questions/{question['id']}/publish", headers=admin
            ).status_code
            == 200
        )
    assert client.post("/api/v1/admin/tests/luyentap/publish", headers=admin).status_code == 200

    learner = auth("learner")
    state = client.post(
        "/api/v1/attempts",
        json={"test_slug": "luyentap", "parts": [], "review_mode": "practice"},
        headers=learner,
    ).json()
    assert len(state["questions"]) == 2

    # Chưa trả lời câu nào: không câu nào được lộ, kể cả ở chế độ Luyện tập.
    for question in state["questions"]:
        assert question["correct_option_id"] is None
        assert all(o["content_vi"] is None for o in question["options"])

    answered, untouched = state["questions"]
    after = client.patch(
        f"/api/v1/attempts/{state['id']}/questions/{answered['id']}",
        json={"selected_option_id": answered["options"][0]["id"]},
        headers=learner,
    ).json()

    now_answered = next(q for q in after["questions"] if q["id"] == answered["id"])
    now_untouched = next(q for q in after["questions"] if q["id"] == untouched["id"])

    assert now_answered["correct_option_id"] is not None
    assert any(o["content_vi"] for o in now_answered["options"])
    # Câu bên cạnh vẫn kín: lộ theo câu, không theo lượt làm.
    assert now_untouched["correct_option_id"] is None
    assert all(o["content_vi"] is None for o in now_untouched["options"])

    # Nộp bài thì lộ hết — không còn gì để đo nữa.
    client.post(f"/api/v1/attempts/{state['id']}/submit", headers=learner)
    submitted = client.get(f"/api/v1/attempts/{state['id']}", headers=learner).json()
    for question in submitted["questions"]:
        assert question["correct_option_id"] is not None
        assert any(o["content_vi"] for o in question["options"])


PART1_NO_PHOTO = """[QUESTION]
voice: us_female_1
(A) The man is typing on a keyboard.
(B) The man is holding a telephone.
(C) Two people are in the office.
(D) The desk is covered with papers.
answer: A
source: original
"""


def test_publishing_all_questions_skips_the_ones_that_fail_the_gate_and_names_them(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Nút "xuất bản tất cả" đi qua ĐÚNG cổng của `publish_question`.

    Một endpoint hàng loạt nới lỏng luật là cách chắc chắn nhất để một câu thiếu
    bản thu đi ra ngoài — và nội dung đó trông hoàn toàn bình thường cho tới khi
    có người học bấm play.

    Nó làm được tới đâu làm tới đó rồi NÊU TÊN phần còn lại. Từ chối cả lô vì
    một câu hỏng thì người biên tập phải tự đi tìm câu đó; và chỉ trả về con số
    thành công thì phần thiếu chỉ lộ ra ở lần bấm "Xuất bản đề" kế tiếp, dưới
    dạng một con số không kèm lý do.
    """
    headers = auth("admin")
    slug = "bulk"
    client.post(
        "/api/v1/admin/tests",
        json={"slug": slug, "title": "Đề thử", "kind": "mini"},
        headers=headers,
    )
    add_part(client, headers, slug, 5, PART5)
    # Câu Part 1 dán được nhưng KHÔNG xuất bản được: nó còn thiếu ảnh và bản thu.
    add_part(client, headers, slug, 1, PART1_NO_PHOTO)

    response = client.post(f"/api/v1/admin/tests/{slug}/questions/publish", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["published_count"] == 1
    assert [item["number"] for item in body["skipped"]] == [1]
    assert body["skipped"][0]["reason"]

    rows = client.get(f"/api/v1/admin/tests/{slug}/questions", headers=headers).json()
    by_number = {row["number"]: row["status"] for row in rows}
    assert by_number[1] == "draft"
    assert by_number[101] == "published"

    # Và cổng ở tầng đề vẫn chặn, nên câu nháp kia không lọt ra đâu cả.
    assert client.post(f"/api/v1/admin/tests/{slug}/publish", headers=headers).status_code == 409


PART2_ONE = """[QUESTION]
voice: us_female_1
Where did you put the quarterly sales report?
voice: uk_male_1
(A) On your desk, next to the printer.
(B) Yes, I finished it last night.
(C) About thirty copies, I think.
answer: A
source: original
"""


def test_scoring_reads_the_verdicts_finalise_just_wrote(db_session: Session) -> None:
    """Chấm điểm phải đọc được những câu vừa chấm đúng trong CÙNG giao dịch.

    `_finalise` gán `is_correct` lên các đối tượng trong BỘ NHỚ, rồi `count_raw`
    đếm bằng một câu SELECT. Session chạy `autoflush=False`, nên câu SELECT đó
    đọc lại hàng CŨ và đếm ra 0 — mọi lượt làm cả đề trả về "Nghe 5 · Đọc 5 ·
    Tổng 10" bất kể trả lời đúng bao nhiêu. Đo được trên đề 200 câu thật: 120
    câu đúng nằm trong `attempt_item`, còn `listening_raw` bằng 0.

    Lỗi ngủ yên tới ngày có một đề ĐỦ: trước đó `score_attempt` luôn từ chối vì
    `test.kind != "full"`, và ngoại lệ bị nuốt theo đúng thiết kế — nên đường
    quy đổi chưa từng chạy tới chỗ hỏng.

    Bài này dựng thẳng bằng ORM thay vì đi qua HTTP: một câu phần Nghe **không
    xuất bản được nếu chưa có bản thu**, nên đường HTTP đòi phải bịa ra một
    `audio_asset` — giàn giáo lớn hơn thứ nó bảo vệ, và nó kiểm cổng xuất bản
    chứ không kiểm phép đẩy xuống DB.
    """
    from app.api.routes.attempt import _finalise
    from app.models import AttemptItem, PracticeTestQuestion, Question
    from app.models.practice import QuestionOption

    test = PracticeTest(slug="cham-diem", title="Đề chấm điểm", kind="full", status="published")
    db_session.add(test)
    db_session.flush()

    user = User(email="cham-diem@example.com", hashed_password="x", role="learner")
    db_session.add(user)
    db_session.flush()

    attempt = Attempt(user_id=user.id, test_id=test.id, scope="full", status="in_progress")
    db_session.add(attempt)
    db_session.flush()

    for position, (number, part) in enumerate(((7, 2), (101, 5)), start=1):
        question = Question(part=part, difficulty=3, source="original", status="published")
        db_session.add(question)
        db_session.flush()
        right = QuestionOption(question_id=question.id, label="A", content="x", is_correct=True)
        wrong = QuestionOption(question_id=question.id, label="B", content="y", is_correct=False)
        db_session.add_all([right, wrong])
        db_session.add(
            PracticeTestQuestion(
                test_id=test.id, question_id=question.id, position=number, number=number
            )
        )
        db_session.flush()
        db_session.add(
            AttemptItem(
                attempt_id=attempt.id,
                question_id=question.id,
                position=position,
                selected_option_id=right.id,
            )
        )
    db_session.flush()
    db_session.refresh(attempt)

    _finalise(db_session, attempt, "submitted")

    # Một câu Nghe và một câu Đọc, cả hai trả lời đúng.
    assert attempt.listening_raw == 1
    assert attempt.reading_raw == 1


def test_a_full_form_gets_the_exam_s_own_time_limit(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """Đề ĐẦY ĐỦ mặc định 120 phút; đề rút gọn thì không.

    TOEIC Listening & Reading là 45 phút Nghe + 75 phút Đọc — định nghĩa của kỳ
    thi, không phải tuỳ chọn. Bỏ trống thì người học vào phòng thi thử mà không
    có đồng hồ, và cái thiếu đó KHÔNG báo lỗi ở đâu: giao diện lặng lẽ hiện
    "Không giới hạn giờ", đọc ra như một lựa chọn của người soạn chứ không như
    một ô bị bỏ trống. Đề 200 câu đầu tiên nạp bằng pipeline đã đúng như thế.
    """
    headers = auth("admin")
    full = client.post(
        "/api/v1/admin/tests",
        json={"slug": "de-day-du", "title": "Đề đầy đủ", "kind": "full"},
        headers=headers,
    )
    assert full.status_code == 201, full.text
    assert full.json()["time_limit_seconds"] == 120 * 60

    mini = client.post(
        "/api/v1/admin/tests",
        json={"slug": "de-rut-gon", "title": "Đề rút gọn", "kind": "mini"},
        headers=headers,
    )
    assert mini.json()["time_limit_seconds"] is None

    # Người soạn nhập gì thì theo cái đó, kể cả trên một đề đầy đủ.
    chosen = client.post(
        "/api/v1/admin/tests",
        json={
            "slug": "de-tu-chon",
            "title": "Đề tự chọn giờ",
            "kind": "full",
            "time_limit_seconds": 3600,
        },
        headers=headers,
    )
    assert chosen.json()["time_limit_seconds"] == 3600


PASTE_PART_3_TWO = """[SCRIPT] Hỏi lịch giao hàng
voice: us_female_1
Hi, I'm calling about the chairs we ordered last Monday.
voice: us_male_1
Let me check. They shipped yesterday and arrive on Friday.

[QUESTION]
What is the woman calling about?
(A) An order she placed
(B) A billing error
(C) A product return
(D) A price change
answer: A
source: original

[QUESTION]
When will the order arrive?
(A) On Monday
(B) On Tuesday
(C) On Friday
(D) On Sunday
answer: C
source: original

[QUESTION]
What will the man most likely do next?
(A) Check the shipping record
(B) Cancel the whole order
(C) Issue a refund notice
(D) Visit the warehouse
answer: A
source: original
"""


def _attach_set_audio(client: TestClient, admin: dict[str, str], db_session, slug: str) -> None:
    """Gắn một bản thu cho cụm, vì cổng publish của Part 3 đòi có audio.

    Đúng ra nó phải đòi: xuất bản một câu nghe chưa có bản thu là đưa ra một câu
    không ai trả lời được. Test này cần đi qua cổng đó chứ không vòng qua nó.
    """
    from app.models.audio import AudioAsset

    clip = AudioAsset(
        storage_key=f"audio/xx/{slug}.mp3",
        source_hash=slug.ljust(64, "0")[:64],
        voice="us_female_1",
        accent="en-US",
        engine="uploaded",
        engine_version="-",
        duration_ms=9000,
        size_bytes=100,
    )
    db_session.add(clip)
    db_session.commit()
    for group in client.get(f"/api/v1/admin/tests/{slug}/sets", headers=admin).json():
        client.post(
            f"/api/v1/admin/question-sets/{group['id']}/audio",
            json={"asset_id": str(clip.id)},
            headers=admin,
        )


def test_practice_hands_over_the_transcript_before_any_answer(
    client: TestClient, auth, db_session
) -> None:
    """Luyện tập cho xem lời thoại ngay, không đợi chọn đáp án.

    Đây là một đánh đổi của sản phẩm chứ không phải của mã, và nó ngược với luật
    cũ: lời thoại từng đi chung cổng lộ đáp án, và với cụm Part 3/4 thì phải trả
    lời hết cụm mới về. Người luyện tự quyết khi nào nhìn.

    Phép kiểm đi cùng nó là `test_exam_mode_never_sends_a_transcript`: chỗ ranh
    giới thật sự nằm ở đó, và nếu luật này bị nới sang cả Luyện thi thì bài thi
    mất nghĩa.
    """
    admin = auth("admin")
    client.post(
        "/api/v1/admin/tests",
        json={"slug": "nghe-luyen", "title": "Nghe", "kind": "mini"},
        headers=admin,
    )
    add_part(client, admin, "nghe-luyen", 3, PASTE_PART_3_TWO)
    _attach_set_audio(client, admin, db_session, "nghe-luyen")
    for question in client.get("/api/v1/admin/tests/nghe-luyen/questions", headers=admin).json():
        published = client.post(f"/api/v1/admin/questions/{question['id']}/publish", headers=admin)
        assert published.status_code == 200, published.text
    opened = client.post("/api/v1/admin/tests/nghe-luyen/publish", headers=admin)
    assert opened.status_code == 200, opened.text

    learner = auth("learner")
    started = client.post(
        "/api/v1/attempts",
        json={"test_slug": "nghe-luyen", "parts": [], "review_mode": "practice"},
        headers=learner,
    )
    assert started.status_code == 201, started.text
    state = started.json()
    first, second, _third = state["questions"]

    # Chưa bấm gì cả mà lời thoại đã có — và đáp án thì CHƯA.
    lead = next(q for q in state["questions"] if q["id"] == first["id"])
    assert [t["speaker"] for t in lead["transcript"]] == ["Woman", "Man"]
    assert "chairs we ordered" in lead["transcript"][0]["text"]
    assert lead["correct_option_id"] is None, "lời thoại mở ra không kéo theo đáp án"

    # Vẫn chỉ đi kèm câu ĐẦU của cụm: ba câu mang ba bản sao là ba lần cùng một
    # đoạn văn trên đường truyền, và client sẽ phải tự khử trùng lặp.
    tail = next(q for q in state["questions"] if q["id"] == second["id"])
    assert tail["transcript"] == []


def test_exam_mode_never_sends_a_transcript(client: TestClient, auth, db_session) -> None:
    """Chế độ Luyện thi không lộ gì cả, kể cả sau khi đã trả lời."""
    admin = auth("admin")
    client.post(
        "/api/v1/admin/tests",
        json={"slug": "nghe-thi", "title": "Nghe", "kind": "mini"},
        headers=admin,
    )
    add_part(client, admin, "nghe-thi", 3, PASTE_PART_3_TWO)
    _attach_set_audio(client, admin, db_session, "nghe-thi")
    for question in client.get("/api/v1/admin/tests/nghe-thi/questions", headers=admin).json():
        client.post(f"/api/v1/admin/questions/{question['id']}/publish", headers=admin)
    client.post("/api/v1/admin/tests/nghe-thi/publish", headers=admin)

    learner = auth("learner")
    state = client.post(
        "/api/v1/attempts",
        json={"test_slug": "nghe-thi", "parts": [], "review_mode": "exam"},
        headers=learner,
    ).json()
    for question in state["questions"]:
        client.patch(
            f"/api/v1/attempts/{state['id']}/questions/{question['id']}",
            json={"selected_option_id": question["options"][0]["id"]},
            headers=learner,
        )
    answered = client.get(f"/api/v1/attempts/{state['id']}", headers=learner).json()
    assert all(q["transcript"] == [] for q in answered["questions"])

    # Nộp rồi thì lộ — không còn gì để đo.
    client.post(f"/api/v1/attempts/{state['id']}/submit", headers=learner)
    submitted = client.get(f"/api/v1/attempts/{state['id']}", headers=learner).json()
    lead = submitted["questions"][0]
    assert lead["transcript"], "nộp xong phải có lời thoại để xem lại"
