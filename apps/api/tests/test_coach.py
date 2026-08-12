"""Coach — năm khẳng định tất định, và ngữ cảnh gửi đi.

Lớp kiểm này chạy mỗi lần và gần như miễn phí, nên nó đứng trước giám khảo LLM.
Phần lớn lỗi thật rơi vào đây: một lời giải trôi chảy nhưng nêu SAI CHỮ CÁI đáp
án là lỗi tệ nhất sản phẩm này mắc được, và nó bị bắt bằng một phép so sánh chuỗi.
"""

from sqlalchemy.orm import Session

from app.models import Question, QuestionOption
from app.models.labels import QuestionLabel
from app.services.coach import build_context, check_output, describe, parse_output

VN = "Đáp án đúng là {ok} vì động từ phải chia ở thì quá khứ đơn theo trạng ngữ yesterday."


def a_question(db_session: Session, *, part: int = 5, tag: str | None = None) -> Question:
    question = Question(
        part=part,
        difficulty=2,
        source="original",
        status="published",
        prompt_text="The report ____ by the manager yesterday.",
    )
    question.options = [
        QuestionOption(label="A", content="reviewed", is_correct=False),
        QuestionOption(label="B", content="was reviewed", is_correct=True),
        QuestionOption(label="C", content="reviewing", is_correct=False),
        QuestionOption(label="D", content="review", is_correct=False),
    ]
    db_session.add(question)
    db_session.commit()
    if tag:
        db_session.add(QuestionLabel(question_id=question.id, facet="grammar", code=tag))
        db_session.commit()
    return question


def good_body(ok: str = "B", chosen: str = "A") -> dict[str, str]:
    return {
        "chan_doan": "Bạn nhầm giữa dạng chủ động và bị động của động từ trong câu này.",
        "vi_sao_ban_chon_sai": f"Phương án {chosen} là dạng chủ động, nhưng chủ ngữ báo cáo "
        "không tự thực hiện hành động nên không dùng được ở đây.",
        "vi_sao_dap_an_dung": VN.format(ok=ok),
        "quy_tac": "Câu bị động ở thì quá khứ đơn dùng cấu trúc was hoặc were cộng phân từ hai.",
        "bay_tuong_tu": "Gặp trạng ngữ chỉ thời gian quá khứ, hãy kiểm tra xem chủ ngữ chủ động "
        "hay bị động trước khi chọn.",
    }


def ctx_for(db_session: Session, question: Question, chosen_label: str | None = "A"):
    options = {o.label: o for o in question.options}
    chosen = options[chosen_label].id if chosen_label else None
    return build_context(db_session, question, chosen)


def test_ban_dep_thi_khong_co_loi_nao(db_session):
    ctx = ctx_for(db_session, a_question(db_session, tag="GRAMMAR_VOICE"))
    assert check_output(good_body(), ctx) == []


def test_neu_SAI_CHU_CAI_dap_an_thi_bi_bat(db_session):
    """Lỗi tệ nhất sản phẩm này mắc được, và rẻ nhất để bắt."""
    ctx = ctx_for(db_session, a_question(db_session))
    problems = check_output(good_body(ok="C"), ctx)
    assert any("chữ cái đáp án đúng" in p for p in problems)


def test_khong_nhac_phuong_an_hoc_vien_da_chon_thi_bi_bat(db_session):
    ctx = ctx_for(db_session, a_question(db_session), chosen_label="C")
    problems = check_output(good_body(chosen="A"), ctx)
    assert any("phương án đã chọn" in p for p in problems)


def test_tra_loi_bang_TIENG_ANH_troi_chay_thi_bi_bat(db_session):
    """Model bị lạc hay trả lời tiếng Anh rất trôi chảy — vẫn là hỏng."""
    ctx = ctx_for(db_session, a_question(db_session))
    body = {
        k: "The answer is B because the verb must be in the passive voice here."
        for k in good_body()
    }
    problems = check_output(body, ctx)
    assert any("tiếng Việt" in p for p in problems)


def test_truong_qua_ngan_hoac_qua_dai_deu_bi_bat(db_session):
    ctx = ctx_for(db_session, a_question(db_session))
    body = good_body() | {"quy_tac": "Ngắn."}
    assert any("quy_tac" in p for p in check_output(body, ctx))


def test_giang_SAI_DIEM_NGU_PHAP_thi_bi_bat(db_session):
    """Khẳng định thứ năm — chỉ tồn tại được vì bộ nhãn là DANH SÁCH ĐÓNG.

    Đây là kiểu hỏng nguy hiểm nhất: lời giải trôi chảy, đúng ngữ pháp, và giảng
    về một điểm hoàn toàn khác điểm mà câu hỏi kiểm.
    """
    ctx = ctx_for(db_session, a_question(db_session, tag="GRAMMAR_VOICE"))
    body = good_body() | {
        "quy_tac": "Mệnh đề quan hệ dùng who cho người và which cho vật, và đó là điểm cần nhớ."
    }
    problems = check_output(body, ctx)
    assert any("GRAMMAR_RELATIVE_CLAUSE" in p for p in problems)


def test_bo_trong_la_mot_trang_thai_CO_THAT(db_session):
    """`selected_option_id = None` nghĩa là học viên không kịp làm.

    Đó là dữ liệu, không phải dữ liệu thiếu (ADR-001 §A4.5) — và nó đáng một lời
    giải riêng, nên ngữ cảnh phải nói ra.
    """
    ctx = ctx_for(db_session, a_question(db_session), chosen_label=None)
    assert ctx.chosen is None
    assert "BỎ TRỐNG" in describe(ctx)
    # Không có phương án đã chọn thì khẳng định số 2 không áp dụng.
    assert check_output(good_body(), ctx) == []


def test_ngu_canh_mang_theo_nhan_ky_nang(db_session):
    ctx = ctx_for(db_session, a_question(db_session, tag="GRAMMAR_VOICE"))
    text = describe(ctx)
    assert "GRAMMAR_VOICE" in text
    assert "Thể" in text  # tên tiếng Việt của nhãn, để model đọc được


def test_json_boc_trong_rao_van_doc_duoc(db_session):
    import json

    body, problem = parse_output("```json\n" + json.dumps(good_body()) + "\n```")
    assert problem is None
    assert body is not None and body["quy_tac"].startswith("Câu bị động")


def test_thieu_mot_truong_thi_bi_tu_choi(db_session):
    import json

    partial = {k: v for k, v in good_body().items() if k != "bay_tuong_tu"}
    body, problem = parse_output(json.dumps(partial))
    assert body is None
    assert "bay_tuong_tu" in (problem or "")


# --- endpoint: hai cổng chặn quan trọng hơn phần gọi model -----------------


def an_attempt(db_session: Session, user, question, *, submitted: bool):
    """Dựng thẳng bằng ORM chứ không qua API.

    Ba cổng chặn được kiểm ở đây đều từ chối TRƯỚC khi chạm tới model, nên một
    hàng hợp lệ là đủ — đi qua luồng API đầy đủ sẽ là nhiều giàn giáo hơn cả thứ
    đang được kiểm (`CLAUDE.md`, quy ước test).
    """
    import uuid as _uuid
    from datetime import UTC, datetime

    from app.models.practice import Attempt, AttemptItem, PracticeTest

    test = PracticeTest(slug=f"t-{_uuid.uuid4().hex[:8]}", title="Đề kiểm thử")
    db_session.add(test)
    db_session.commit()

    attempt = Attempt(
        user_id=user.id,
        test_id=test.id,
        scope="full",
        review_mode="exam",
        status="submitted" if submitted else "in_progress",
        started_at=datetime.now(UTC),
        submitted_at=datetime.now(UTC) if submitted else None,
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.add(
        AttemptItem(
            attempt_id=attempt.id,
            question_id=question.id,
            position=1,
            selected_option_id=question.options[0].id,
        )
    )
    db_session.commit()
    return attempt


def a_user(db_session: Session, email: str):
    from app.models.user import User

    user = User(email=email, hashed_password="x")
    db_session.add(user)
    db_session.commit()
    return user


def bearer(user) -> dict[str, str]:
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_dang_lam_bai_thi_KHONG_duoc_giai_thich(client, db_session):
    """Không có cổng này thì Coach là một nút gian lận.

    Đang làm bài, bấm một cái là có lời giải kèm đáp án đúng.
    """
    user = a_user(db_session, "dang-lam@example.com")
    question = a_question(db_session)
    attempt = an_attempt(db_session, user, question, submitted=False)

    response = client.post(
        f"/api/v1/attempts/{attempt.id}/items/{question.id}/coach", headers=bearer(user)
    )
    assert response.status_code == 409
    assert "Nộp bài" in response.json()["detail"]


def test_luot_cua_NGUOI_KHAC_tra_404_chu_khong_403(client, db_session):
    """403 là xác nhận lượt đó tồn tại — id thì đoán được, quyền sở hữu thì không."""
    owner = a_user(db_session, "chu-nhan@example.com")
    other = a_user(db_session, "nguoi-la@example.com")
    question = a_question(db_session)
    attempt = an_attempt(db_session, owner, question, submitted=True)

    response = client.post(
        f"/api/v1/attempts/{attempt.id}/items/{question.id}/coach", headers=bearer(other)
    )
    assert response.status_code == 404


def test_cau_khong_thuoc_luot_lam_bai_thi_404(client, db_session):
    user = a_user(db_session, "hoc-vien@example.com")
    question = a_question(db_session)
    other_question = a_question(db_session)
    attempt = an_attempt(db_session, user, question, submitted=True)

    response = client.post(
        f"/api/v1/attempts/{attempt.id}/items/{other_question.id}/coach", headers=bearer(user)
    )
    assert response.status_code == 404


def test_cau_lam_DUNG_thi_tu_choi_truoc_khi_ton_luot_goi(client, db_session):
    """Không có gì để chẩn đoán, và prompt cũng không có nghĩa.

    Chạy thật cho thấy model trả về `chan_doan` dài đúng một ký tự khi bị hỏi về
    một câu làm đúng — nó không bịa, nó chỉ không có gì để nói. Cổng kiểm sẽ bắt
    được, nhưng bắt được nghĩa là đã tốn hai lượt gọi cho một câu hỏi vô nghĩa.
    """
    user = a_user(db_session, "lam-dung@example.com")
    question = a_question(db_session)
    attempt = an_attempt(db_session, user, question, submitted=True)

    from app.models.practice import AttemptItem

    item = db_session.query(AttemptItem).filter_by(attempt_id=attempt.id).one()
    item.selected_option_id = next(o.id for o in question.options if o.is_correct)
    item.is_correct = True
    db_session.commit()

    response = client.post(
        f"/api/v1/attempts/{attempt.id}/items/{question.id}/coach", headers=bearer(user)
    )
    assert response.status_code == 409
    assert "làm đúng" in response.json()["detail"]


def test_cau_KHONG_CO_NOI_DUNG_thi_tu_choi_som(client, db_session):
    """Part 1 không in đề, phương án chỉ đọc bằng audio, và chưa có lời thoại.

    Model không thấy gì ngoài số part và chữ cái đáp án — nó nói thẳng điều đó
    rồi trượt cổng kiểm thất thường. Chặn ở đầu vào: để cổng kiểm bắt nghĩa là
    đã tốn hai lượt gọi cho một câu hỏi không có câu trả lời.
    """
    user = a_user(db_session, "khong-noi-dung@example.com")
    question = Question(part=1, difficulty=2, source="original", status="published")
    question.options = [
        QuestionOption(label=chr(65 + i), content=None, is_correct=i == 0) for i in range(4)
    ]
    db_session.add(question)
    db_session.commit()
    attempt = an_attempt(db_session, user, question, submitted=True)

    response = client.post(
        f"/api/v1/attempts/{attempt.id}/items/{question.id}/coach", headers=bearer(user)
    )
    assert response.status_code == 409
    assert "lời thoại" in response.json()["detail"]
