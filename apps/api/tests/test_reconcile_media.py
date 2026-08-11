"""Đối chiếu media mồ côi.

Thứ đáng kiểm ở đây là **danh sách nguồn tham chiếu**. Bỏ sót một cột khoá ngoại
không làm lệnh đổ — nó báo nhầm một tài sản đang được dùng là rác, và bước sau
là `--delete-rows` xoá hàng đó đi.
"""

from sqlalchemy.orm import Session

from app.content.reconcile_media import collect
from app.models import ImageAsset, Question, QuestionSet
from tests.test_domain_model import make_audio


def make_image(session: Session, marker: str) -> ImageAsset:
    asset = ImageAsset(
        storage_key=f"image/{marker}/{marker}.jpg",
        source_hash=marker * 32,
        mime_type="image/jpeg",
        size_bytes=10,
        width=10,
        height=10,
        source="uploaded",
        source_url="https://example.com",
        license="CC0",
        attribution="Ai đó",
    )
    session.add(asset)
    session.commit()
    return asset


def test_an_image_in_the_second_passage_slot_is_not_reported_as_orphaned(
    db_session: Session,
) -> None:
    """Cụm Part 7 có BA ô ngữ liệu, không phải một.

    Chỉ quét `passage_image_id` sẽ coi ảnh của ô 2 và ô 3 là rác — tức là ảnh
    của mọi bài đọc nhiều đoạn.
    """
    used = [make_image(db_session, chr(ord("a") + i)) for i in range(3)]
    stimulus = QuestionSet(part=7, status="draft")
    stimulus.passage_image_id = used[0].id
    stimulus.passage_2_image_id = used[1].id
    stimulus.passage_3_image_id = used[2].id
    db_session.add(stimulus)
    db_session.commit()

    assert collect(db_session).dangling_image == []


def test_audio_on_a_question_set_counts_as_referenced(db_session: Session) -> None:
    """Part 3/4 treo bản thu ở CỤM, không ở câu."""
    clip = make_audio(db_session, marker="z")
    stimulus = QuestionSet(part=3, status="draft", audio_asset_id=clip.id)
    db_session.add(stimulus)
    db_session.commit()

    assert collect(db_session).dangling_audio == []


def test_an_asset_nobody_points_at_is_reported(db_session: Session) -> None:
    orphan = make_audio(db_session, marker="y")

    report = collect(db_session)

    assert [a.id for a in report.dangling_audio] == [orphan.id]


def test_detaching_an_image_leaves_it_orphaned(db_session: Session) -> None:
    """Gỡ ảnh chỉ tháo liên kết — đó là lý do lệnh này tồn tại."""
    picture = make_image(db_session, "d")
    question = Question(part=1, source="original", status="draft", image_asset_id=picture.id)
    db_session.add(question)
    db_session.commit()
    assert collect(db_session).dangling_image == []

    question.image_asset_id = None
    db_session.commit()

    assert [a.id for a in collect(db_session).dangling_image] == [picture.id]
