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


@dataclass(frozen=True)
class Unit:
    """Một unit = một `dictation_section`, và ở đây mỗi unit đúng một story."""

    name: str
    story_title: str
    story_description: str
    difficulty: int
    sentences: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Topic:
    """Một `dictation_topic` và toàn bộ unit nằm dưới nó."""

    slug: str
    name: str
    description: str
    position: int
    units: tuple[Unit, ...]


SHORT_STORY_UNITS: tuple[Unit, ...] = (
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
    Unit(
        name="Unit 6 — Moving to a new office",
        story_title="The Move Upstairs",
        story_description="Một đội chuyển sang tầng mới, và sự cố mạng sáng thứ Hai.",
        difficulty=3,
        sentences=(
            "The design team was told they would move to a new floor.",
            "Boxes and labels arrived on Monday for everyone to pack their files.",
            "The manager asked staff to leave the monitors on the desks.",
            "Movers came on Friday evening after most people had gone home.",
            "On Monday the team found their chairs already waiting by the window.",
            "The network in one corner did not work for the first hour.",
            "A technician traced the fault to a cable behind the wall panel.",
            "By lunchtime the whole floor was online and the boxes were gone.",
        ),
    ),
    Unit(
        name="Unit 7 — A product launch",
        story_title="Launch Day",
        story_description="Buổi ra mắt sản phẩm, từ lúc chuẩn bị tới lúc chốt đơn.",
        # Khó nhất của topic: câu dài, quá khứ hoàn thành, nhiều mệnh đề phụ.
        difficulty=4,
        sentences=(
            "The marketing department had been preparing the launch since early spring.",
            "They booked a hall downtown and invited reporters from several magazines.",
            "The samples arrived two days late because of a customs inspection.",
            "Staff worked through the evening to arrange the display tables.",
            "On the morning of the event the microphone would not switch on.",
            "A technician replaced it minutes before the first guests walked in.",
            "The director opened with a short talk about how the idea began.",
            "By the end of the week orders had passed every earlier record.",
        ),
    ),
    Unit(
        name="Unit 8 — A visit to the clinic",
        story_title="An Appointment After Work",
        story_description="Khám bệnh sau giờ làm, và phần bảo hiểm công ty chi trả.",
        difficulty=3,
        sentences=(
            "Mr. Okafor booked an appointment at the clinic near his office.",
            "The receptionist asked him to arrive fifteen minutes before his slot.",
            "He filled in a short form about his medical history.",
            "The doctor listened carefully and asked how long the pain had lasted.",
            "She recommended a blood test and some rest for the coming week.",
            "The nurse explained which counter to visit for the sample.",
            "He was told the results would be sent by email on Thursday.",
            "His employer covered most of the cost through the company insurance plan.",
        ),
    ),
)


CONVERSATION_UNITS: tuple[Unit, ...] = (
    Unit(
        name="Unit 1 — Making an appointment",
        story_title="Booking a Meeting Room",
        story_description="Đặt phòng họp qua quầy lễ tân, có một chỗ phải đổi lịch.",
        difficulty=2,
        sentences=(
            "Good morning, I would like to book a meeting room for Thursday.",
            "Certainly, how many people will be joining you?",
            "There will be six of us, including two visitors from Osaka.",
            "The large room on the third floor is free until noon.",
            "Could we keep it until one o'clock instead?",
            "That should be fine, but I will have to move another booking.",
            "Please let me know if that causes any trouble.",
            "I will send you a confirmation before the end of the day.",
        ),
    ),
    Unit(
        name="Unit 2 — On the phone",
        story_title="A Call from a Supplier",
        story_description="Nhà cung cấp gọi báo hàng về trễ, và hai bên thu xếp lại.",
        difficulty=3,
        sentences=(
            "Good afternoon, this is Elena calling from the packaging supplier.",
            "I am afraid the delivery scheduled for Monday has been delayed.",
            "May I ask how long the delay is likely to be?",
            "We expect the shipment to arrive by Wednesday at the latest.",
            "That is later than we planned, but we can work around it.",
            "I will email you the new tracking number this afternoon.",
            "Please copy my colleague in the warehouse on that message.",
            "Of course, and again I apologize for the inconvenience.",
        ),
    ),
    Unit(
        name="Unit 3 — Small talk at work",
        story_title="Monday Morning",
        story_description="Vài câu chào hỏi đầu tuần trước giờ họp.",
        difficulty=2,
        sentences=(
            "Good morning, did you have a nice weekend?",
            "It was quiet, I spent most of it working in the garden.",
            "That sounds relaxing compared to the traffic this morning.",
            "The road near the station has been closed for repairs.",
            "I noticed that, it took me almost an hour to get here.",
            "There is fresh coffee in the kitchen if you need it.",
            "Thank you, I will get a cup before the team meeting.",
            "See you there, it starts in about ten minutes.",
        ),
    ),
    Unit(
        name="Unit 4 — Welcoming a visitor",
        story_title="At the Reception Desk",
        story_description="Khách tới đúng hẹn, và thủ tục ở quầy lễ tân.",
        difficulty=2,
        sentences=(
            "Good morning, I have an appointment with Miss Alvarez at ten.",
            "Welcome, could I have your name and the company you represent?",
            "My name is Peter Lang, and I am from the auditing firm.",
            "Thank you, please sign the visitor book and take this badge.",
            "Should I wait here, or go up to the fourth floor?",
            "Please take a seat, someone will come down for you shortly.",
            "Would you like a coffee or a glass of water while you wait?",
            "A glass of water would be lovely, thank you very much.",
        ),
    ),
    Unit(
        name="Unit 5 — Rescheduling a training session",
        story_title="Moving the Safety Training",
        story_description="Nửa đội bận hội chợ, và buổi tập huấn phải tách làm hai.",
        difficulty=3,
        sentences=(
            "I am calling about the safety training booked for next Tuesday.",
            "Yes, I have the session down for the whole morning.",
            "Unfortunately half the team will be at the trade fair that day.",
            "Would you rather move the session or split it into two groups?",
            "Splitting it would work better, if the trainer is available twice.",
            "I will check her calendar and confirm before the end of today.",
            "Please also let the facilities team know about the room.",
            "I will copy them on the message so that nothing is missed.",
        ),
    ),
    Unit(
        name="Unit 6 — Ordering office supplies",
        story_title="The Empty Cupboard",
        story_description="Hết văn phòng phẩm, và một phiếu mua hàng cần chữ ký.",
        difficulty=3,
        sentences=(
            "The stationery cupboard is nearly empty again on the second floor.",
            "I noticed that too, shall I raise a purchase request?",
            "Please do, and add the printer paper we ran out of.",
            "Does the order still need approval from the department manager?",
            "Anything above five hundred thousand dong does, so this one will.",
            "I will draft it now and send it for signature this afternoon.",
            "Ask the supplier whether delivery before Friday is still possible.",
            "I will mention it, and I will forward whatever they reply.",
        ),
    ),
)


# Thông báo và tin nhắn: đúng dạng Part 4 — một người nói, không có người đáp.
# Tách thành topic riêng vì giọng đọc chọn theo story, và một bản tin phát thanh
# đọc bằng giọng kể chuyện thì nghe sai ngay từ câu đầu.
ANNOUNCEMENT_UNITS: tuple[Unit, ...] = (
    Unit(
        name="Unit 1 — A store announcement",
        story_title="Closing Time",
        story_description="Thông báo trong siêu thị trước giờ đóng cửa.",
        difficulty=2,
        sentences=(
            "Attention shoppers, the store will be closing in thirty minutes.",
            "Please bring your final purchases to the checkout counters now.",
            "The customer service desk on the ground floor closes even earlier.",
            "Members of our loyalty program can collect double points this weekend.",
            "The winter sale continues in the clothing section on the second floor.",
            "Parking remains free for one hour with any purchase over fifty thousand dong.",
            "We open again tomorrow morning at half past eight.",
            "Thank you for shopping with us, and have a pleasant evening.",
        ),
    ),
    Unit(
        name="Unit 2 — A voicemail message",
        story_title="A Missing Order Number",
        story_description="Tin nhắn thoại từ phòng kế toán về một hoá đơn thiếu thông tin.",
        difficulty=3,
        sentences=(
            "Hello, this is Ruth calling from the accounts department on Tuesday.",
            "I am sorry to have missed you, I hope this reaches you today.",
            "The invoice you sent last week is missing a purchase order number.",
            "Without that number our system cannot release the payment.",
            "Could you resend the document with the number in the subject line?",
            "If it is easier, my extension is four one six.",
            "I will be at my desk until about five this afternoon.",
            "Thank you very much, and I look forward to hearing from you.",
        ),
    ),
    Unit(
        name="Unit 3 — A staff briefing",
        story_title="Three Things Before the Shift",
        story_description="Dặn dò đầu ca: khu bốc hàng, thẻ an toàn, và lịch đánh giá.",
        difficulty=4,
        sentences=(
            "Good morning everyone, thank you for coming in a little earlier.",
            "There are three things to cover before the shift begins.",
            "First, the loading bay will be closed for repairs until Thursday.",
            "Deliveries during that time should be directed to the side entrance.",
            "Second, the new safety cards must be signed by the end of the month.",
            "Anyone who has not received one should speak to their supervisor today.",
            "Finally, the annual review meetings will start the week after next.",
            "Your team leader will send round a sheet for choosing a time.",
        ),
    ),
)

TOPICS: tuple[Topic, ...] = (
    Topic(
        slug="short-stories",
        name="Short stories",
        description="Truyện ngắn, mỗi bài một câu chuyện liền mạch.",
        position=0,
        units=SHORT_STORY_UNITS,
    ),
    Topic(
        slug="conversations",
        name="Conversations",
        description="Hội thoại ngắn nơi làm việc, mỗi bài một cuộc trao đổi.",
        position=1,
        units=CONVERSATION_UNITS,
    ),
    Topic(
        slug="announcements",
        name="Announcements",
        description="Thông báo và tin nhắn, mỗi bài một người nói từ đầu đến cuối.",
        position=2,
        units=ANNOUNCEMENT_UNITS,
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


def _topic(session: Session, spec: Topic) -> DictationTopic:
    """Topic đã có sẵn thì dùng lại; chưa có thì dựng, để máy trắng cũng chạy được.

    Khớp theo `slug` chứ không theo tên: tên hiển thị là thứ người soạn sửa được
    trong màn quản trị, và đổi tên một chủ đề đang có nội dung không được biến nó
    thành một chủ đề thứ hai rỗng không.
    """
    topic = session.scalars(select(DictationTopic).where(DictationTopic.slug == spec.slug)).first()
    if topic is None:
        topic = DictationTopic(
            slug=spec.slug,
            name=spec.name,
            description=spec.description,
            position=spec.position,
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
    """Tạo những gì còn thiếu, cho từng chủ đề một."""
    for spec in TOPICS:
        _build_topic(session, spec, counts)


def _build_topic(session: Session, spec: Topic, counts: Counts) -> None:
    """Khớp unit theo TÊN, vì tên là thứ người soạn nhìn thấy và gõ lại."""
    topic = _topic(session, spec)
    sections = {
        section.name: section
        for section in session.scalars(
            select(DictationSection).where(DictationSection.topic_id == topic.id)
        )
    }
    taken = {section.position for section in sections.values()}

    for unit in spec.units:
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
    for spec in TOPICS:
        _promote_topic(session, spec, counts)


def _promote_topic(session: Session, spec: Topic, counts: Counts) -> None:
    topic = _topic(session, spec)
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
