"""Bộ eval AI — cổng hồi quy chạy offline, không mạng, không khoá."""

from pathlib import Path

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.content.eval_ai import (
    CaseFailure,
    EvalError,
    eval_coach,
    eval_planner,
    eval_retrieval,
    eval_shape,
    judge_coach,
    load_cases,
    main,
)
from app.core.ai_budget import Budget
from app.core.database import Base
from app.services.llm.fake import FakeProvider
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier


def _write(path: Path, name: str, lines: list[str]) -> Path:
    target = path / name
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def test_COACH_dat_rot_dung_nhu_case_viet(tmp_path: Path) -> None:
    reply = {
        "chan_doan": "Bạn nhầm giữa chủ động và bị động ở câu này, vì chủ ngữ là sự vật.",
        "vi_sao_ban_chon_sai": "Phương án A là dạng chủ động nên câu đọc thành báo cáo tự xem xét.",
        "vi_sao_dap_an_dung": "Đáp án đúng là B vì yesterday đòi quá khứ đơn và nghĩa đòi bị động.",
        "quy_tac": "Bị động quá khứ đơn dùng was hoặc were cộng dạng quá khứ phân từ.",
        "bay_tuong_tu": "Chủ ngữ là sự vật thì kiểm tra bị động trước khi chốt đáp án.",
    }
    base = {
        "question": {
            "part": 5,
            "prompt_text": "The report ____ yesterday.",
            "options": [
                {"label": "A", "content": "reviewed"},
                {"label": "B", "content": "was reviewed"},
            ],
            "correct": "B",
        },
        "labels": {},
        "reply": reply,
    }
    good = {"id": "dat", "chosen": "A", "expect_pass": True, **base}
    bad = {"id": "rot", "chosen": "A", "expect_pass": False, "expect_problems": [], **base}
    report = eval_coach([good, bad])
    assert (report.passed, report.total) == (1, 2)
    assert [f.id for f in report.failures] == ["rot"]
    assert "tưởng rớt mà đạt" in report.failures[0].detail


def test_COACH_case_hong_thi_BAO_dung_case(tmp_path: Path) -> None:
    report = eval_coach([{"id": "thieu", "reply": {}}])
    assert report.total == 1 and report.passed == 0
    assert "question" in report.failures[0].detail


def test_SHAPE_dem_chu_khong_cai(tmp_path: Path) -> None:
    report = eval_shape(
        [
            {
                "id": "du",
                "labels": ["A", "B"],
                "text": "Căn cứ chung. | (A) Đúng chỗ này. | (B) Sai chỗ kia.",
                "expect_pass": True,
            },
            {
                "id": "thieu",
                "labels": ["A", "B"],
                "text": "Căn cứ chung. | (A) Đúng chỗ này.",
                "expect_pass": False,
                "expect_problem": "3",
            },
        ]
    )
    assert (report.passed, report.total) == (2, 2)


def test_RETRIEVAL_lexical_tren_KB_that(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "---\nref: diem\ntitle: Điểm thi\nkeywords: điểm, quy đổi\n---\n\nNộp bài mới có điểm.\n",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text(
        "---\nref: chep\ntitle: Nghe chép\nkeywords: dictation, nghe chép\n---\n\nChấm từng từ.\n",
        encoding="utf-8",
    )
    report = eval_retrieval(
        [
            {"id": "q1", "query": "quy đổi điểm", "relevant_refs": ["diem"]},
            {"id": "q2", "query": "nghe chép chấm", "relevant_refs": ["chep"]},
        ],
        tmp_path,
    )
    assert (report.passed, report.total) == (2, 2)


def test_JUDGE_trung_model_sinh_thi_TU_CHOI(capsys) -> None:
    assert main(["--judge", "x/m", "--gen-model", "x/m"]) == 2
    assert "trùng model sinh" in capsys.readouterr().err


def test_JUDGE_thieu_gen_model_thi_BAO_thieu(capsys) -> None:
    assert main(["--judge", "x/m"]) == 2
    assert "--gen-model" in capsys.readouterr().err


def test_SUITE_la_thi_BAO_dung_ten(capsys) -> None:
    assert main(["--suite", "coach", "--datasets", "/khong/co"]) == 2
    assert "eval hỏng" in capsys.readouterr().err


def test_LOAD_case_thieu_khoa_thi_BAO_dong(tmp_path: Path) -> None:
    target = _write(tmp_path, "c.jsonl", ['{"id": "x"}'])
    try:
        load_cases(target, {"id", "reply"})
    except EvalError as exc:
        assert "1" in str(exc) and "reply" in str(exc)
    else:
        raise AssertionError("phải ném EvalError")


def test_CASE_FAILURE_la_dataclass() -> None:
    assert CaseFailure(id="x", detail="y").detail == "y"


def _plan_case(**over: object) -> dict:
    base: dict = {
        "id": "p",
        "budget": 4,
        "seed_topics": [
            {"code": "GRAMMAR_VOICE", "title": "Thể bị động"},
            {"code": "GRAMMAR_TENSE", "title": "Thì hiện tại"},
        ],
        "weak": [["GRAMMAR_VOICE", 1, 4], ["GRAMMAR_TENSE", 0, 3]],
        "reply": {"items": [{"id": "g1", "reason": "Ôn."}]},
        "expected": [{"kind": "grammar_lesson", "part": 5, "label": "Ôn Thể bị động"}],
    }
    base.update(over)
    return base


def test_PLANNER_chon_dung_ung_vien() -> None:
    report = eval_planner([_plan_case()])
    assert (report.passed, report.total) == (1, 1)


def test_PLANNER_id_la_thi_LOC_giu_dung() -> None:
    reply = {"items": [{"id": "g1", "reason": "Ôn."}, {"id": "g9", "reason": "Bịa."}]}
    assert eval_planner([_plan_case(reply=reply)]).passed == 1


def test_PLANNER_json_hong_thi_NONE() -> None:
    case = _plan_case(reply="không phải json", expect_none=True)
    case.pop("expected")
    assert eval_planner([case]).passed == 1


def test_PLANNER_thieu_ung_vien_thi_KHONG_goi_model() -> None:
    case = _plan_case(weak=[], expect_none=True, expect_no_call=True)
    case.pop("expected")
    assert eval_planner([case]).passed == 1


def test_PLANNER_chu_de_draft_thi_KHONG_thanh_ung_vien() -> None:
    case = _plan_case(
        seed_topics=[{"code": "GRAMMAR_VOICE", "title": "Thể bị động", "status": "draft"}],
        expect_none=True,
        expect_no_call=True,
    )
    case.pop("expected")
    assert eval_planner([case]).passed == 1


def _judge_gateway(reply: str) -> Gateway:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.tables["ai_interaction"].create(engine)
    return Gateway(
        providers={"fake": FakeProvider(reply=reply)},
        routes={Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")},
        budget=Budget(limit_micro=1_000_000_000),
        redis_client=redis.Redis(),
        session_factory=lambda: Session(engine),
    )


def _judge_case(expect_pass: bool) -> dict:
    return {
        "id": "j",
        "question": {
            "part": 5,
            "prompt_text": "The report ____ yesterday.",
            "options": [
                {"label": "A", "content": "reviewed"},
                {"label": "B", "content": "was reviewed"},
            ],
            "correct": "B",
        },
        "labels": {},
        "chosen": "A",
        "expect_pass": expect_pass,
        "reply": {"dat": "placeholder"},
    }


def test_JUDGE_dong_y_thi_dat() -> None:
    gw = _judge_gateway('{"dat": true, "ly_do": "đạt"}')
    assert judge_coach([_judge_case(True)], gw).passed == 1
    gw = _judge_gateway('{"dat": false, "ly_do": "sai chữ cái"}')
    assert judge_coach([_judge_case(False)], gw).passed == 1


def test_JUDGE_bat_dong_thi_BAO() -> None:
    gw = _judge_gateway('{"dat": true, "ly_do": "đạt"}')
    report = judge_coach([_judge_case(False)], gw)
    assert report.passed == 0 and "bất đồng" in report.failures[0].detail


def test_JUDGE_khong_json_thi_BAO() -> None:
    gw = _judge_gateway("không rõ")
    report = judge_coach([_judge_case(True)], gw)
    assert report.passed == 0 and "JSON" in report.failures[0].detail
