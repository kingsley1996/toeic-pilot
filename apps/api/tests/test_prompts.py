"""Prompt là tệp có phiên bản — kể cả metadata frontmatter."""

from app.services.llm.prompts import Prompt, load


def test_KHONG_frontmatter_thi_version_nhu_cu() -> None:
    """Đường cũ không đổi một byte version nào."""
    first = Prompt("x", "Chào {ten}")
    assert first.meta == {}
    assert first.text == "Chào {ten}"
    assert first.render(ten="bạn") == "Chào bạn"


def test_frontmatter_thanh_meta_body_thanh_text() -> None:
    prompt = Prompt("x", "---\npurpose: Chấm\ninputs: a, b\neval_suite: coach\n---\n\nChấm {a} đi.")
    assert prompt.meta == {"purpose": "Chấm", "inputs": "a, b", "eval_suite": "coach"}
    assert prompt.text == "Chấm {a} đi."
    assert prompt.render(a="bài") == "Chấm bài đi."


def test_sua_meta_KHONG_doi_version_sua_chu_thi_DOI() -> None:
    a = Prompt("x", "---\npurpose: Một\n---\n\nChấm đi.")
    b = Prompt("x", "---\nppurpose: Hai\n---\n\nChấm đi.".replace("ppurpose", "purpose"))
    c = Prompt("x", "---\npurpose: Một\n---\n\nChấm lại đi.")
    assert a.version == b.version
    assert a.version != c.version


def test_frontmatter_khong_dong_thi_NO_TO(tmp_path) -> None:
    (tmp_path / "hong.md").write_text("---\npurpose: X\n\nKhông có dòng đóng", encoding="utf-8")
    try:
        load("hong", tmp_path)
    except ValueError as exc:
        assert "đóng" in str(exc)
    else:
        raise AssertionError("phải ném ValueError")


def test_judge_coach_that_co_meta() -> None:
    """Ít nhất một prompt thật dùng frontmatter — không thì đây là code chết."""
    prompt = load("judge_coach")
    assert prompt.meta.get("eval_suite") == "coach"
    assert "{described}" in prompt.text and "{reply}" in prompt.text
