"""Bộ eval AI — cổng hồi quy chạy offline, không mạng, không khoá."""

from pathlib import Path

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.content.eval_ai import (
    CaseFailure,
    EvalError,
    SuiteReport,
    _mean_or_none,
    diff_against,
    eval_planner,
    eval_retrieval,
    load_cases,
    main,
)
from app.content.eval_suites.coach import eval_coach, judge_coach
from app.content.eval_suites.shape import eval_shape
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
    assert CaseFailure(id="x", detail="y").kind == "system"


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
    # Fake chặn non-JSON ngay ở provider (có schema) nên thành lỗi gọi —
    # hạ tầng, không phải judge chấm sai.
    gw = _judge_gateway("không rõ")
    report = judge_coach([_judge_case(True)], gw)
    assert report.passed == 0 and "JSON" in report.failures[0].detail
    assert report.failures[0].kind == "infrastructure"


def test_PARSE_JUDGE_khong_json_thi_NONE() -> None:
    from app.content.eval_suites.coach import _parse_judge

    verdict, _ = _parse_judge("không rõ")
    assert verdict is None
    verdict, _ = _parse_judge('{"dat": "yes"}')
    assert verdict is None


def test_COACH_case_hong_thi_kind_dataset() -> None:
    report = eval_coach([{"id": "thieu", "reply": {}}])
    assert report.failures[0].kind == "dataset"


def test_RETRIEVAL_doi_nhieu_ref_hon_limit_thi_case_hong(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "---\nref: diem\ntitle: Điểm thi\nkeywords: điểm\n---\n\nCó điểm.\n",
        encoding="utf-8",
    )
    report = eval_retrieval(
        [{"id": "q", "query": "điểm", "relevant_refs": ["a", "b", "c", "d", "e"]}],
        tmp_path,
    )
    assert report.passed == 0
    assert report.failures[0].kind == "dataset"
    assert "top-4" in report.failures[0].detail


def test_MEAN_khong_so_lieu_thi_NA_chu_khong_100() -> None:
    assert _mean_or_none([]) is None
    assert _mean_or_none([1.0, 0.5]) == 0.75


def test_NOREDIS_cham_vao_thi_LO() -> None:
    from app.content.eval_ai import _NoRedis

    try:
        _NoRedis().incrby("x", 1)
    except Exception as exc:  # noqa: BLE001 — test cố ý chạm
        assert "offline" in str(exc)
    else:
        raise AssertionError("phải ném lỗi")


def test_JUDGE_schema_khai_day_du_kieu_va_cam_field_la() -> None:
    from app.services.llm.fake import FakeProvider as Fake

    provider = Fake(reply='{"dat": true, "ly_do": "đạt"}')
    assert judge_coach([_judge_case(True)], _judge_gateway_with(provider)).passed == 1
    seen_schema = provider.seen[0][0].schema
    assert seen_schema is not None
    assert seen_schema["properties"] == {"dat": {"type": "boolean"}, "ly_do": {"type": "string"}}
    assert seen_schema["additionalProperties"] is False


def _judge_gateway_with(provider) -> Gateway:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.tables["ai_interaction"].create(engine)
    return Gateway(
        providers={"fake": provider},
        routes={Tier.CHEAP: ("fake", "fake-1"), Tier.STRONG: ("fake", "fake-1")},
        budget=Budget(limit_micro=1_000_000_000),
        redis_client=redis.Redis(),
        session_factory=lambda: Session(engine),
    )


def test_BASELINE_case_moi_rot_thi_chan() -> None:
    baseline = {
        "suites": [
            {"name": "coach", "passed": 10, "total": 10, "failures": [], "metrics": {}},
            {
                "name": "retrieval",
                "passed": 16,
                "total": 16,
                "failures": [],
                "metrics": {"recall": 1.0, "mrr": 0.92},
            },
        ]
    }
    current = [
        SuiteReport(
            name="coach", passed=9, total=10, failures=[CaseFailure("c1", "sai", "system")]
        ),
        SuiteReport(
            name="retrieval",
            passed=16,
            total=16,
            metrics={"recall": 1.0, "mrr": 0.85},
        ),
    ]
    lines, has_new = diff_against(baseline, current)
    assert has_new is True
    assert any("MỚI RỚT: c1" in line for line in lines)
    assert any("mrr 0.92→0.85" in line for line in lines)

    same, has_new = diff_against(
        baseline,
        [
            SuiteReport(name="coach", passed=10, total=10),
            SuiteReport(name="retrieval", passed=16, total=16),
        ],
    )
    assert has_new is False


def test_BASELINE_thieu_file_thi_BAO_dung(tmp_path: Path, capsys) -> None:
    assert main(["--suite", "coach", "--baseline", str(tmp_path / "khong-co.json")]) == 2
    assert "eval hỏng" in capsys.readouterr().err


def test_CODES_ma_hoa_dung_loai_loi() -> None:
    coach = eval_coach(
        [
            {
                "id": "sai-chu-cai",
                "question": {
                    "part": 5,
                    "prompt_text": "Q?",
                    "options": [
                        {"label": "A", "content": "x"},
                        {"label": "B", "content": "y"},
                    ],
                    "correct": "B",
                },
                "labels": {},
                "chosen": "A",
                "expect_pass": True,
                "reply": {
                    "chan_doan": "Bạn nhầm chủ động với bị động ở câu này.",
                    "vi_sao_ban_chon_sai": "Phương án A chủ động nên nghĩa vô lý.",
                    "vi_sao_dap_an_dung": "Đáp án đúng là C vì hợp nghĩa nhất.",
                    "quy_tac": "Đọc kỹ đề trước khi chọn đáp án.",
                    "bay_tuong_tu": "Câu khó thì đọc lại đề rồi mới chốt.",
                },
            }
        ]
    )
    assert coach.failures[0].code == "wrong_correct_answer"
    assert coach.failures[0].kind == "system"

    shape = eval_shape(
        [
            {
                "id": "trong",
                "labels": ["A"],
                "text": "  ",
                "expect_pass": False,
                "expect_problem": "rỗng",
            }
        ]
    )
    assert shape.failures == []
    shape = eval_shape([{"id": "trong", "labels": ["A"], "text": "  ", "expect_pass": True}])
    assert shape.failures[0].code == "empty_output"


def test_JUDGE_confusion_va_dem_thu_lai() -> None:
    from app.services.llm.base import LLMError

    calls = [0]

    def flaky(request):
        calls[0] += 1
        if calls[0] == 1:
            raise LLMError("502 quá tải")
        ok = "AAA" in request.system
        return '{"dat": true, "ly_do": "đạt"}' if ok else '{"dat": false, "ly_do": "sai"}'

    from app.services.llm.fake import FakeProvider as Fake

    provider = Fake(reply=flaky)
    cases = [_judge_case(True), _judge_case(False)]
    cases[0]["question"]["prompt_text"] = "AAA"
    report = judge_coach(cases, _judge_gateway_with(provider))
    assert (report.passed, report.total) == (2, 2)
    assert report.metrics["agreement"] == 1.0
    assert report.metrics["judge_precision"] == 1.0
    assert "TP1" in report.summary and "TN1" in report.summary
    assert "thử lại 1 lượt" in report.summary


def test_RETRIEVAL_vector_thieu_keys_thi_BAO_TO(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(
        "---\nref: diem\ntitle: Điểm thi\nkeywords: điểm\n---\n\nCó điểm.\n",
        encoding="utf-8",
    )
    try:
        eval_retrieval(
            [{"id": "q", "query": "điểm", "relevant_refs": ["diem"]}], tmp_path, "vector"
        )
    except EvalError as exc:
        assert "vector" in str(exc)
    else:
        raise AssertionError("phải ném EvalError khi thiếu keys")


def test_MANIFEST_ghim_va_phat_hien_lech(tmp_path: Path) -> None:
    from app.content.eval_ai import _manifest_status, write_manifest

    (tmp_path / "coach_explain.jsonl").write_text('{"id": "x"}\n', encoding="utf-8")
    for name in ("explanation_shape", "retrieval", "planner"):
        (tmp_path / f"{name}.jsonl").write_text("", encoding="utf-8")
    target = write_manifest(tmp_path)
    assert target.name == "manifest.json"
    version, match = _manifest_status(tmp_path)
    assert match is True and version != "none"
    (tmp_path / "coach_explain.jsonl").write_text('{"id": "y"}\n', encoding="utf-8")
    _, match = _manifest_status(tmp_path)
    assert match is False


def test_REPORT_json_co_kind_code_metadata(tmp_path: Path, capsys) -> None:
    import json

    out = tmp_path / "r.json"
    assert main(["--suite", "shape", "--report", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["run"]["git_sha"]
    assert set(data["datasets"]["hashes"]) == {
        "coach_explain",
        "explanation_shape",
        "retrieval",
        "planner",
    }
    assert data["suites"][0]["metrics"] == {}
