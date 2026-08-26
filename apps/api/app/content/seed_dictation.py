"""Bốn unit đọc chép nữa cho topic "Short stories".

    uv run python -m app.content.seed_dictation

Trước script này cây đọc chép chỉ có **một** unit và sáu câu, tức là học viên
nghe hết nội dung trong một buổi và màn hình duyệt cây không bao giờ có gì để
duyệt. Bốn unit ở đây phủ những cảnh TOEIC hay hỏi nhất ngoài công sở: sân bay,
nhà hàng, chăm sóc khách hàng, phỏng vấn.

Ba điều đã cân nhắc khi viết chữ, vì cả ba đều hỏng trong im lặng:

**Mỗi story là một mạch chuyện, không phải tám câu rời.** Mô tả của topic nói
"mỗi bài một câu chuyện liền mạch", và nó không phải câu văn cho vui: giọng đọc
được chọn theo `story_id` (`voice_for_dictation`), nên tám câu của một bài về
sau sẽ do cùng một người kể. Tám câu rời rạc do cùng một giọng kể nghe như lỗi.

**Không có chữ số và không có sở hữu cách.** "Gate twelve" chứ không phải
"gate 12", vì người học không đoán được nên gõ chữ hay gõ số, và bộ chấm coi hai
cách đó là hai từ khác nhau. Sở hữu cách còn tệ hơn: "the company's report" và
"the companys report" phát âm giống hệt nhau, mà `normalise` giữ lại dấu nháy
đơn — nên câu đó trừ điểm một thứ mà nghe không thể phân biệt được.

**Câu chưa có audio thì phải là `draft`.** `audio_asset_id` là NULL lúc mới tạo
và CHECK `ck_dictation_item_published_has_audio` chặn việc publish; API cũng
không được phép sinh audio (PHASE2-AUDIO §A4.1). Nên script này tạo bản nháp
rồi dừng, và việc thu tiếng là của `backfill_audio`:

    uv run python -m app.content.backfill_audio --only dictation

**Chạy lại được, và lần sau tìm thấy ít việc hơn.** Không có bảng hàng đợi và
không có cờ "đã seed": mỗi lần chạy, script hỏi cái gì còn thiếu thì tạo, cái gì
đã đủ điều kiện thì publish. Nên trình tự bình thường là chạy nó, chạy
`backfill_audio`, rồi chạy lại nó — lần thứ hai chính là lúc nội dung lên sóng.
"""

import argparse
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.dictation import (
    DictationItem,
    DictationSection,
    DictationStory,
    DictationTopic,
)

TOPIC_SLUG = "short-stories"


@dataclass(frozen=True)
class Unit:
    """Một unit = một `dictation_section`, và ở đây mỗi unit đúng một story."""

    name: str
    story_title: str
    story_description: str
    difficulty: int
    sentences: tuple[str, ...] = field(default_factory=tuple)


UNITS: tuple[Unit, ...] = (
    Unit(
        name="Unit 2 — Travel and the airport",
        story_title="A Delayed Flight",
        story_description="Chuyến bay bị hoãn và một buổi chiều phải sắp xếp lại.",
        # Dễ nhất trong bốn bài: câu ngắn, từ vựng sân bay lặp lại nhiều.
        difficulty=2,
        sentences=(
            "Ms. Carter arrived at the airport two hours before her flight.",
            "The screen at the gate said her departure had been delayed.",
            "She asked an agent how long the delay was expected to last.",
            "The agent explained that bad weather had grounded several planes.",
            "Ms. Carter called her office to move the afternoon meeting.",
            "She found a quiet seat near the window and opened her laptop.",
            "An announcement finally invited passengers to board through gate twelve.",
            "The flight landed just in time for her dinner appointment.",
        ),
    ),
    Unit(
        name="Unit 3 — Dining out",
        story_title="Dinner with a Client",
        story_description="Một bữa tối tiếp khách, từ lúc đặt bàn đến lúc ký hoá đơn.",
        difficulty=3,
        sentences=(
            "Mr. Tanaka booked a table for four at a restaurant downtown.",
            "He asked the waiter to seat them away from the kitchen.",
            "The client arrived a few minutes late because of heavy traffic.",
            "They ordered the soup of the day and the grilled fish.",
            "The waiter apologized that the dessert menu had already changed.",
            "Mr. Tanaka signed the receipt and kept a copy for his expenses.",
            "The client thanked him and promised to send the contract on Monday.",
            "They agreed to meet again once the new branch had opened.",
        ),
    ),
    Unit(
        name="Unit 4 — Shopping and customer service",
        story_title="The Wrong Order",
        story_description="Giao thiếu hàng, gọi tổng đài, và cách chuyện được giải quyết.",
        difficulty=3,
        sentences=(
            "A customer ordered two desk lamps from the company website.",
            "The package arrived on Friday with only one lamp inside.",
            "She called the support line and explained what had happened.",
            "The agent apologized and checked the order number in the system.",
            "He confirmed that the second lamp was still in the warehouse.",
            "The company agreed to ship the missing item at no extra cost.",
            "She received a confirmation email within the next ten minutes.",
            "The replacement lamp was delivered early the following week.",
        ),
    ),
    Unit(
        name="Unit 5 — A job interview",
        story_title="The Second Interview",
        story_description="Vòng phỏng vấn thứ hai, và câu hỏi bao giờ đi làm được.",
        # Khó nhất: câu dài hơn, thì quá khứ hoàn thành, số liệu trong câu.
        difficulty=4,
        sentences=(
            "Daniel was invited back for a second interview on Tuesday morning.",
            "He studied the latest annual report the night before.",
            "The manager asked him to describe a project he had managed alone.",
            "Daniel explained how his team had cut delivery times by a third.",
            "He mentioned that he was studying for a certificate in logistics.",
            "The manager wanted to know when he would be available to start.",
            "Daniel said his current employer required four weeks of notice.",
            "The offer letter reached his inbox before the end of the week.",
        ),
    ),
)


@dataclass
class Counts:
    sections: int = 0
    stories: int = 0
    items: int = 0
    published: int = 0

    def as_line(self) -> str:
        return (
            f"{self.sections} unit · {self.stories} bài · {self.items} câu mới · "
            f"{self.published} hàng vừa publish"
        )


def _topic(session: Session) -> DictationTopic:
    """Topic đã có sẵn thì dùng lại; chưa có thì dựng, để máy trắng cũng chạy được."""
    topic = session.scalars(select(DictationTopic).where(DictationTopic.slug == TOPIC_SLUG)).first()
    if topic is None:
        topic = DictationTopic(
            slug=TOPIC_SLUG,
            name="Short stories",
            description="Truyện ngắn, mỗi bài một câu chuyện liền mạch.",
            position=0,
            status="draft",
        )
        session.add(topic)
        session.flush()
    return topic


def _next_position(taken: set[int]) -> int:
    position = 0
    while position in taken:
        position += 1
    return position


def build(session: Session, counts: Counts) -> None:
    """Tạo những gì còn thiếu. Khớp theo tên, vì tên là thứ người soạn nhìn thấy."""
    topic = _topic(session)
    sections = {
        section.name: section
        for section in session.scalars(
            select(DictationSection).where(DictationSection.topic_id == topic.id)
        )
    }
    taken = {section.position for section in sections.values()}

    for unit in UNITS:
        section = sections.get(unit.name)
        if section is None:
            section = DictationSection(
                topic_id=topic.id,
                name=unit.name,
                position=_next_position(taken),
                status="draft",
            )
            taken.add(section.position)
            session.add(section)
            session.flush()
            counts.sections += 1

        story = session.scalars(
            select(DictationStory)
            .where(DictationStory.section_id == section.id)
            .where(DictationStory.title == unit.story_title)
        ).first()
        if story is None:
            story = DictationStory(
                section_id=section.id,
                title=unit.story_title,
                description=unit.story_description,
                position=0,
                difficulty=unit.difficulty,
                status="draft",
            )
            session.add(story)
            session.flush()
            counts.stories += 1

        # Đối chiếu theo chính lời thoại chứ không theo số lượng: sửa một câu
        # trong UNITS rồi chạy lại thì câu đó được thêm vào, còn đếm số câu sẽ
        # bảo "đủ tám rồi" và bỏ qua.
        existing = {
            item.transcript
            for item in session.scalars(
                select(DictationItem).where(DictationItem.story_id == story.id)
            )
        }
        highest = max(
            (
                item.position or 0
                for item in session.scalars(
                    select(DictationItem).where(DictationItem.story_id == story.id)
                )
            ),
            default=0,
        )
        for sentence in unit.sentences:
            if sentence in existing:
                continue
            highest += 1
            session.add(
                DictationItem(
                    # NULL cho tới khi backfill_audio thu xong; CHECK trên bảng
                    # là thứ chặn hàng này lọt ra cho học viên trước lúc đó.
                    audio_asset_id=None,
                    transcript=sentence,
                    story_id=story.id,
                    position=highest,
                    difficulty=unit.difficulty,
                    status="draft",
                )
            )
            counts.items += 1


def _publish(row: DictationTopic | DictationSection | DictationStory | DictationItem) -> None:
    row.status = "published"
    row.published_at = datetime.now(UTC)


def promote(session: Session, counts: Counts) -> None:
    """Publish đúng những gì đủ điều kiện *lúc này*, từ dưới lên.

    Từ dưới lên vì mọi truy vấn phía học viên lọc `published` ở cả bốn tầng: một
    story đã publish mà câu bên trong còn nháp hiện ra là bài rỗng, và không có
    gì báo — nó trông y hệt một bài chưa soạn xong.
    """
    topic = _topic(session)
    for section in session.scalars(
        select(DictationSection).where(DictationSection.topic_id == topic.id)
    ):
        for story in session.scalars(
            select(DictationStory).where(DictationStory.section_id == section.id)
        ):
            items = list(
                session.scalars(select(DictationItem).where(DictationItem.story_id == story.id))
            )
            for item in items:
                if item.status == "draft" and item.audio_asset_id is not None:
                    _publish(item)
                    counts.published += 1
            # Một bài rỗng không được publish, và một bài còn câu chưa có tiếng
            # cũng vậy — nửa bài thì học viên nghe hết rồi tưởng đã xong.
            ready = bool(items) and all(item.status == "published" for item in items)
            if ready and story.status == "draft":
                _publish(story)
                counts.published += 1
        if section.status == "draft" and any(
            story.status == "published"
            for story in session.scalars(
                select(DictationStory).where(DictationStory.section_id == section.id)
            )
        ):
            _publish(section)
            counts.published += 1
    if topic.status == "draft" and any(
        section.status == "published"
        for section in session.scalars(
            select(DictationSection).where(DictationSection.topic_id == topic.id)
        )
    ):
        _publish(topic)
        counts.published += 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="đếm việc phải làm rồi thôi, không ghi gì"
    )
    args = parser.parse_args(argv)

    session = SessionLocal()
    counts = Counts()
    try:
        build(session, counts)
        session.flush()
        promote(session, counts)
        if args.dry_run:
            session.rollback()
            print(f"[dry-run] {counts.as_line()}")
        else:
            session.commit()
            print(counts.as_line())
        waiting = session.scalar(
            select(DictationItem)
            .where(DictationItem.audio_asset_id.is_(None))
            .where(DictationItem.status == "draft")
            .limit(1)
        )
        if waiting is not None:
            print(
                "Còn câu chưa có tiếng — chạy: "
                "uv run python -m app.content.backfill_audio --only dictation"
            )
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
