"""Lát B — luồng gắn nhãn theo mặt, kiểm bằng provider giả.

Bài đáng giá nhất là bài từ chối một mã hợp lệ-nhưng-sai-part. Một mã bịa còn dễ
thấy; `GRAMMAR_NOUN` cho một câu Part 6 thì tồn tại thật, đúng mặt, đúng kiểu —
và vẫn sai, vì Part 6 chỉ kiểm năm điểm ngữ pháp. Nhận vào thì `GROUP BY` mọc
thêm một nhóm cho thứ đề thi không kiểm ở phần đó.
"""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.content.enrich_skills import _describe, classify
from app.core.ai_budget import Budget
from app.models import Question, QuestionOption, QuestionSet
from app.services.labels import FACETS
from app.services.llm.fake import FakeProvider
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier

ROUTES = {Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")}


def facet(key: str):
    return next(f for f in FACETS if f.key == key)


def gateway_with(db_session: Session, fake_redis, provider: FakeProvider) -> Gateway:
    return Gateway(
        providers={"fake": provider},
        routes=ROUTES,
        budget=Budget(limit_micro=10_000_000),
        redis_client=fake_redis,  # type: ignore[arg-type]
        session_factory=sessionmaker(bind=db_session.get_bind()),
    )


def test_ma_hop_le_thi_nhan_duoc_ngay_lan_dau(db_session, fake_redis):
    provider = FakeProvider(reply='{"code": "PART_5_GRAMMAR", "ly_do": "câu bị động"}')
    outcome = classify(
        gateway_with(db_session, fake_redis, provider), facet("question_type"), 5, "…", Tier.STRONG
    )
    assert outcome.code == "PART_5_GRAMMAR"
    assert outcome.attempts == 1


def test_json_boc_trong_rao_ba_dau_huyen_van_doc_duoc(db_session, fake_redis):
    """Model hay bọc JSON trong rào dù prompt bảo đừng — bóc ra, đừng coi là hỏng."""
    provider = FakeProvider(reply='```json\n{"code": "PART_5_VOCABULARY", "ly_do": "x"}\n```')
    outcome = classify(
        gateway_with(db_session, fake_redis, provider), facet("question_type"), 5, "…", Tier.STRONG
    )
    assert outcome.code == "PART_5_VOCABULARY"


def test_ma_BIA_bi_tu_choi(db_session, fake_redis):
    provider = FakeProvider(reply='{"code": "PART_5_GRAMMARS", "ly_do": "x"}')
    outcome = classify(
        gateway_with(db_session, fake_redis, provider), facet("question_type"), 5, "…", Tier.STRONG
    )
    assert outcome.code is None
    assert outcome.attempts == 2


def test_ma_co_that_nhung_SAI_PART_bi_tu_choi(db_session, fake_redis):
    """`GRAMMAR_NOUN` có ở Part 5 và KHÔNG có ở Part 6.

    Kiểu sai im lặng nhất trong cả lát này: mã tồn tại, đúng mặt, chỉ sai part.
    """
    provider = FakeProvider(reply='{"code": "GRAMMAR_NOUN", "ly_do": "danh từ"}')
    outcome = classify(
        gateway_with(db_session, fake_redis, provider), facet("grammar"), 6, "…", Tier.STRONG
    )
    assert outcome.code is None
    assert "không hợp lệ" in outcome.reason


def test_thuc_don_chi_liet_ke_ma_hop_le_voi_part_do(db_session, fake_redis):
    """Thu hẹp NGAY TRONG PROMPT thay vì bác sau.

    Đưa một lựa chọn không thể đúng ra trước mặt model chỉ tạo cơ hội sai — và
    tốn thêm một lượt gọi để sửa.
    """
    provider = FakeProvider(reply='{"code": "GRAMMAR_TENSE", "ly_do": "x"}')
    classify(gateway_with(db_session, fake_redis, provider), facet("grammar"), 6, "…", Tier.STRONG)
    ((sent, _model),) = provider.seen
    assert "GRAMMAR_NOUN" not in sent.system  # chỉ có ở Part 5
    assert "GRAMMAR_TENSE" in sent.system


def test_moi_luot_goi_HTTP_la_mot_hang_so_cai_ke_ca_luot_hong(db_session, fake_redis):
    from app.models.ai import AiInteraction

    replies = iter(["hỏng", '{"code": "PART_5_GRAMMAR", "ly_do": "x"}'])
    provider = FakeProvider(reply=lambda _req: next(replies))
    classify(
        gateway_with(db_session, fake_redis, provider), facet("question_type"), 5, "…", Tier.STRONG
    )
    rows = db_session.query(AiInteraction).all()
    assert len(rows) == 2
    assert all((r.prompt_version or "").startswith("label_facet@") for r in rows)


def test_het_han_muc_NGAY_khong_bi_thu_lai(db_session, fake_redis):
    """Hai loại 429, và gộp chúng lại là một lỗi tốn kém."""
    from app.services.llm.base import LLMQuotaExhausted

    calls = 0

    def counting(_req: object) -> str:
        nonlocal calls
        calls += 1
        raise LLMQuotaExhausted("hết hạn mức ngày")

    provider = FakeProvider(reply=counting)
    with pytest.raises(LLMQuotaExhausted):
        classify(
            gateway_with(db_session, fake_redis, provider),
            facet("question_type"),
            5,
            "…",
            Tier.STRONG,
        )
    assert calls == 1


def test_part_1_noi_ro_la_KHONG_IN_de_bai(db_session):
    """Part 1 không in đề — sự thật của đề thi, không phải dữ liệu thiếu."""
    question = Question(part=1, difficulty=2, source="original", status="draft", prompt_text=None)
    question.options = [
        QuestionOption(label=chr(65 + i), content=None, is_correct=i == 0) for i in range(4)
    ]
    db_session.add(question)
    db_session.commit()
    assert "chỉ đọc bằng audio" in _describe(question)


def test_cau_part_7_duoc_kem_doan_van_cua_nhom(db_session):
    """Ngữ cảnh dùng chung nằm ở `question_set`, không ở câu hỏi."""
    group = QuestionSet(part=7, title="Thông báo", passage="The elevator will be out of service.")
    question = Question(
        part=7,
        difficulty=2,
        source="original",
        status="draft",
        prompt_text="What is suggested?",
        question_set=group,
        position=1,
    )
    question.options = [
        QuestionOption(label=chr(65 + i), content=f"x{i}", is_correct=i == 0) for i in range(4)
    ]
    db_session.add(group)
    db_session.commit()
    described = _describe(question)
    assert "elevator will be out of service" in described
    assert "Thông báo" in described
