"""Collocation: parse/validate import, commit, PATCH sau commit (lát C1).

Luật dễ hỏng im lặng nhất được kiểm: commit luôn `draft`; WARNING không chặn
commit (§9); entry gap-NULL vẫn hợp lệ nhưng discovery phải lọc published (§16).
"""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.models import VocabularyEntry

PASTE = "\n".join(  # noqa: E501 — dữ liệu dán, mỗi dòng là một hàng thật
    [
        "submit a report | submit | submit | VERB_NOUN | nộp báo cáo | Please submit the report by Friday. | Vui lòng nộp báo cáo trước thứ Sáu. | make,do,take",  # noqa: E501
        "interested in | interest | in | ADJ_PREP | quan tâm đến | She is interested in the position. | Cô ấy quan tâm đến vị trí này. | to,on,about",  # noqa: E501
        "in accordance with | accordance | | PREP_PHRASE | theo đúng | The work was completed in accordance with the agreement. | Công việc được hoàn thành theo đúng thỏa thuận. |",  # noqa: E501
    ]
)


def _parse(client: TestClient, auth: Callable[[str], dict[str, str]], raw: str) -> dict:
    return client.post(
        "/api/v1/admin/collocations/parse", json={"raw_text": raw}, headers=auth("editor")
    ).json()


def _commit(client: TestClient, auth: Callable[[str], dict[str, str]], rows: list) -> dict:
    return client.post(
        "/api/v1/admin/collocations", json={"rows": rows}, headers=auth("editor")
    ).json()


def test_parse_reports_every_rule_once(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    bad = (
        "submit a report | | submit | VERB_NOUN | nghĩa | ex | vi | make\n"
        "overlook | overlook | overlook | VERB_NOUN | nghĩa | ex | vi |\n"
        "submit a report | submit | entire | VERB_NOUN | nghĩa | ex | vi |\n"
        "submit a report | submit | submit | FOO_BAR | nghĩa | ex | vi |\n"
        "submit a report | submit | submit | VERB_NOUN | nghĩa | ex | vi | make,make\n"
        "submit a report | submit | submit | VERB_NOUN | nghĩa | ex | vi | submit\n"
        "submit a report | submit | submit | VERB_NOUN | nghĩa | ex | vi | a,b,c,d\n"
    )
    body = _parse(client, auth, bad)
    assert body["ok_count"] == 0 and body["error_count"] == 7
    texts = [p for row in body["rows"] for p in row["problems"]]
    assert any("base_word is required" in t for t in texts)
    assert any("entire headword" in t for t in texts)
    assert any("does not appear in headword" in t for t in texts)
    assert any("is not one of" in t for t in texts)
    assert any("duplicate distractors" in t for t in texts)
    assert any("must not equal gap_word" in t for t in texts)
    assert any("at most 3" in t for t in texts)


def test_parse_warns_when_a_distractor_forms_another_pasted_collocation(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    paste = (
        "submit a report | submit | submit | VERB_NOUN | nộp báo cáo | ex | vi | write,take\n"
        "write a report | write | write | VERB_NOUN | viết báo cáo | ex | vi | make\n"
    )
    body = _parse(client, auth, paste)
    first = body["rows"][0]
    assert any("WARNING" in w and "write" in w for w in first["warnings"])
    # WARNING không phải ERROR: hàng vẫn ok, commit được.
    assert body["ok_count"] == 2


def test_parse_gap_is_matched_by_token_not_substring(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    # "in" là gap: không được khớp trong "interested".
    body = _parse(
        client,
        auth,
        "interested in | interest | on | ADJ_PREP | quan tâm đến | ex | vi | to\n",
    )
    assert body["error_count"] == 1
    assert "does not appear in headword" in body["rows"][0]["problems"][0]


def test_commit_creates_phrase_entry_with_detail(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    body = _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    assert body["created"] == 3 and body["skipped"] == 0

    entry = db_session.query(VocabularyEntry).filter_by(headword="submit a report").one()
    assert entry.part_of_speech == "phrase" and entry.status == "draft"
    assert entry.collocation is not None
    assert entry.collocation.base_word == "submit"
    assert entry.collocation.gap_word == "submit"
    assert entry.collocation.pattern == "VERB_NOUN"
    assert entry.collocation.distractors == ["make", "do", "take"]

    gapless = db_session.query(VocabularyEntry).filter_by(headword="in accordance with").one()
    assert gapless.collocation is not None and gapless.collocation.gap_word is None


def test_commit_skips_rows_that_still_have_problems(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    rows = _parse(client, auth, PASTE)["rows"]
    rows[0]["problems"] = ["stale problem from an older parse"]
    body = _commit(client, auth, rows)
    assert body["created"] == 2 and body["skipped"] == 1


def test_patch_updates_detail_after_commit(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    entry = db_session.query(VocabularyEntry).filter_by(headword="submit a report").one()

    patched = client.patch(
        f"/api/v1/admin/vocabulary/{entry.id}/collocation",
        json={"pattern": "VERB_PREP", "distractors": ["drop", "file"]},
        headers=auth("editor"),
    )
    assert patched.status_code == 200
    db_session.refresh(entry.collocation)
    assert entry.collocation.pattern == "VERB_PREP"
    assert entry.collocation.base_word == "submit"  # field không gửi thì giữ nguyên
    assert entry.collocation.distractors == ["drop", "file"]


def test_patch_rejects_a_distractor_that_equals_the_gap(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    entry = db_session.query(VocabularyEntry).filter_by(headword="submit a report").one()

    bad = client.patch(
        f"/api/v1/admin/vocabulary/{entry.id}/collocation",
        json={"distractors": ["submit", "make"]},
        headers=auth("editor"),
    )
    assert bad.status_code == 422


def test_patch_clears_the_gap_with_an_empty_string(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    entry = db_session.query(VocabularyEntry).filter_by(headword="submit a report").one()

    cleared = client.patch(
        f"/api/v1/admin/vocabulary/{entry.id}/collocation",
        json={"gap_word": ""},
        headers=auth("editor"),
    )
    assert cleared.status_code == 200
    db_session.refresh(entry.collocation)
    assert entry.collocation.gap_word is None


def test_discovery_follows_the_published_rule(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Draft bị loại; lọc theo base_word; gap-NULL vẫn hiện ở discovery (§16)."""
    _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    db_session.execute(
        sa_update(VocabularyEntry)
        .where(VocabularyEntry.headword.in_(["submit a report", "interested in"]))
        .values(status="published")
    )
    db_session.commit()

    listed = client.get("/api/v1/vocabulary-collocations").json()
    assert {item["headword"] for item in listed["items"]} == {"submit a report", "interested in"}

    listed = client.get("/api/v1/vocabulary-collocations?base_word=submit").json()
    assert [item["headword"] for item in listed["items"]] == ["submit a report"]
    assert listed["items"][0]["pattern"] == "VERB_NOUN"
    assert listed["items"][0]["baseWord"] == "submit"


def test_detail_carries_the_collocation_block(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    db_session.execute(
        sa_update(VocabularyEntry)
        .where(VocabularyEntry.headword == "submit a report")
        .values(status="published")
    )
    db_session.commit()
    entry = db_session.query(VocabularyEntry).filter_by(headword="submit a report").one()

    detail = client.get(f"/api/v1/vocabulary/{entry.id}").json()
    assert detail["collocation"] == {"baseWord": "submit", "pattern": "VERB_NOUN"}


def test_quiz_pool_excludes_gap_null_entries(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    """Eligibility §18: `collocation=1` chỉ trả entry published + gap NOT NULL."""
    _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    db_session.execute(
        sa_update(VocabularyEntry)
        .where(VocabularyEntry.headword.in_(["submit a report", "interested in"]))
        .values(status="published")
    )
    db_session.commit()

    pool = client.get("/api/v1/vocabulary?collocation=1&limit=50").json()
    headwords = {item["headword"] for item in pool["items"]}
    # "in accordance with" (gap-NULL) bị loại; chỉ hai entry published có gap.
    assert headwords == {"submit a report", "interested in"}
    for item in pool["items"]:
        choices = item["collocation"]["choices"]
        assert item["collocation"]["gapWord"] in choices
        assert len(choices) >= 2


def test_quiz_answer_is_graded_against_gap_not_headword(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    db_session.execute(
        sa_update(VocabularyEntry)
        .where(VocabularyEntry.headword == "submit a report")
        .values(status="published")
    )
    db_session.commit()
    entry = db_session.query(VocabularyEntry).filter_by(headword="submit a report").one()
    answer_url = f"/api/v1/vocabulary/{entry.id}/collocation-answer"

    right = client.post(answer_url, json={"answer": " SUBMIT "})
    assert right.status_code == 200 and right.json() == {"correct": True, "expected": "submit"}

    wrong = client.post(answer_url, json={"answer": "make"})
    assert wrong.json() == {"correct": False, "expected": "submit"}

    # So với headword là SAI — "submit a report" không được chấp nhận (§19).
    headword = client.post(answer_url, json={"answer": "submit a report"})
    assert headword.json() == {"correct": False, "expected": "submit"}


def test_quiz_answer_404_for_gap_null_entry(
    client: TestClient, db_session: Session, auth: Callable[[str], dict[str, str]]
) -> None:
    _commit(client, auth, _parse(client, auth, PASTE)["rows"])
    db_session.execute(
        sa_update(VocabularyEntry)
        .where(VocabularyEntry.headword == "in accordance with")
        .values(status="published")
    )
    db_session.commit()
    entry = db_session.query(VocabularyEntry).filter_by(headword="in accordance with").one()

    answer = client.post(f"/api/v1/vocabulary/{entry.id}/collocation-answer", json={"answer": "x"})
    assert answer.status_code == 404
