"""Một đề demo để dựng và kiểm giao diện thi thử.

    uv run python -m app.content.seed_demo_test

Đề **rút gọn** (`kind='mini'`, 24 câu) chứ không phải 200 câu. Viết tay 200 câu
có nghĩa là việc soạn nội dung nhiều tuần, và mục đích ở đây là cho giao diện
một hình dạng dữ liệu THẬT để chạy lên — đủ cả bảy part, đủ các dạng cấu trúc
khác nhau: câu đứng một mình, cụm dùng chung audio, cụm dùng chung đoạn văn, và
bài nhiều đoạn.

Hai điều không được lơi lỏng kể cả với dữ liệu demo:

**`source='original'`.** Mọi câu ở đây do chúng ta tự viết theo *định dạng* của
đề thi — định dạng thì không thuộc bản quyền ai, văn bản cụ thể thì có. Không
dòng nào được sao chép từ đề ETS, và cột này là nơi câu trả lời đó được ghi lại
theo từng câu.

**Năm trong bảy part.** `validate_question` đòi audio ở cả bốn part nghe — part
1 và 2 mỗi câu một clip, part 3 và 4 một clip cho cả cụm — và part 1 đòi thêm
ảnh. Không có audio thì những part đó **không lưu được thành câu hỏi hợp lệ**,
chứ không phải lưu được mà im tiếng. Đó là §10.2 hiện ra bằng dữ liệu.

Bốn part nghe không cùng mức độ chặn:

- **Part 1 và 4 đã có**, sinh bằng đường ống hiện có: cả hai chỉ cần MỘT giọng
  (part 1 đọc bốn câu mô tả, part 4 là một bài nói của một người). Spec ở
  `content/sources/demo_test_listening.jsonl`; ảnh part 1 lấy từ thư viện ảnh
  CC đã có sẵn.
- **Part 2 và 3 thì chưa.** Part 2 cần câu hỏi một giọng và ba đáp án giọng khác
  trong cùng MỘT file; part 3 cần hội thoại 2-3 người. `SpecItem` là
  `(text, voice)` — một text, một giọng, một file — nên không diễn đạt được.
  Đây là §10.2, và không nhà cung cấp lưu trữ hay giao diện nào gỡ được nó.

Seed **bỏ qua** part 1/4 nếu chưa tìm thấy audio, thay vì hỏng: chạy được trên
một máy chưa chạy `generate` quan trọng hơn là ép mọi máy phải có đủ media.
"""

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.audio import AudioAsset
from app.models.image import ImageAsset
from app.models.practice import (
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionOption,
    QuestionSet,
    TestCollection,
)
from app.models.validators import validate_question

COLLECTION_SLUG = "demo-2026"
TEST_SLUG = "demo-2026-test-1"

# Nhãn phần: dùng chung với giao diện, nên tên hiển thị chỉ có một nguồn.
PART_TITLES = {
    1: "Photos",
    2: "Question-Response",
    3: "Conversations",
    4: "Talks",
    5: "Incomplete Sentences",
    6: "Text Completion",
    7: "Reading Comprehension",
}


def _audio(session: Session, starts_with: str) -> AudioAsset | None:
    """Tìm clip đã sinh sẵn theo phần đầu của chính văn bản đã đọc.

    Tra bằng `source_text` chứ không ghi cứng `storage_key`: khoá là hash của
    (văn bản | giọng | engine | phiên bản engine), nên sửa một chữ trong spec là
    khoá đổi hoàn toàn — và một khoá ghi cứng sẽ trỏ vào hư không mà không báo.
    """
    return (
        session.query(AudioAsset)
        .filter(AudioAsset.source_text.like(f"{starts_with}%"))
        .order_by(AudioAsset.created_at)
        .first()
    )


def _question(
    part: int,
    *,
    prompt: str | None,
    options: list[tuple[str, str | None]],
    correct: str,
    explanation: str | None = None,
) -> Question:
    question = Question(
        part=part,
        prompt_text=prompt,
        explanation=explanation,
        difficulty=3,
        # Không bao giờ để mặc định ở bất kỳ đâu trong code hay giao diện: đây là
        # cột duy nhất mà một giá trị sai gây hậu quả pháp lý.
        source="original",
        source_note="Viết cho đề demo, không sao chép từ đề thi thật.",
        status="published",
    )
    question.options = [
        QuestionOption(label=label, content=content, is_correct=(label == correct))
        for label, content in options
    ]
    return question


def build(session: Session) -> PracticeTest:
    collection = TestCollection(
        slug=COLLECTION_SLUG,
        title="Bộ đề demo 2026",
        description="Đề rút gọn dùng để dựng và kiểm giao diện. Không phải đề thi thật.",
        source_tag="demo",
        year=2026,
        position=0,
        status="published",
    )
    test = PracticeTest(
        slug=TEST_SLUG,
        title="Demo 2026 - Test 1",
        description=(
            "Đề rút gọn 5/7 phần. Part 2 và 3 chờ audio nhiều giọng (MEDIA-PIPELINE §10.2)."
        ),
        kind="mini",
        time_limit_seconds=45 * 60,
        collection=collection,
        position=0,
        status="published",
    )
    session.add(test)

    ordered: list[Question] = []

    # --- Part 1: ảnh + audio một giọng ---------------------------------------
    #
    # Part 2 và 3 KHÔNG có ở đây và sẽ không có cho tới khi §10.2 được gỡ: chúng
    # cần nhiều giọng trong cùng một file. Chèn chúng vào mà bỏ qua kiểm tra sẽ
    # tạo ra dữ liệu demo dạy sai về hình dạng dữ liệu thật, và giao diện dựng
    # trên đó sẽ trông như đã xong trong khi phần khó nhất còn nguyên.
    photos = _audio(session, "Look at the picture marked number one")
    photo_image = session.query(ImageAsset).order_by(ImageAsset.created_at).first()
    if photos is not None and photo_image is not None:
        question = _question(
            1, prompt=None, options=[(label, None) for label in "ABCD"], correct="A"
        )
        question.audio_asset_id = photos.id
        question.image_asset_id = photo_image.id
        ordered.append(question)

    # --- Part 4: một bài nói, một giọng, dùng chung cho ba câu ----------------
    talk_audio = _audio(session, "Questions three through five")
    if talk_audio is not None:
        talk = QuestionSet(
            part=4,
            title="Thông báo bảo trì toà nhà",
            audio_asset_id=talk_audio.id,
            status="published",
        )
        session.add(talk)
        for index, (prompt, options, correct) in enumerate(
            [
                (
                    "Where is the announcement most likely being made?",
                    ["In an apartment building", "At an airport", "In a factory", "At a hotel"],
                    "A",
                ),
                (
                    "When will the work begin?",
                    ["On Monday", "On Wednesday", "On Friday", "On Saturday"],
                    "B",
                ),
                (
                    "What are listeners asked to do?",
                    ["Use another entrance", "Work from home", "Arrive earlier", "Park elsewhere"],
                    "A",
                ),
            ]
        ):
            question = _question(
                4, prompt=prompt, options=list(zip("ABCD", options)), correct=correct
            )
            question.question_set = talk
            question.position = index + 1
            ordered.append(question)

    # --- Part 5: câu đơn, không cụm ------------------------------------------
    for prompt, options, correct in [
        (
            "The new invoices ------- to the accounting department yesterday.",
            ["send", "were sent", "sending", "have sent"],
            "B",
        ),
        (
            "Ms. Tran will review the contract ------- she returns from Hanoi.",
            ["as soon as", "in spite of", "because of", "rather than"],
            "A",
        ),
        (
            "The workshop was ------- attended than the organisers had expected.",
            ["well", "better", "best", "the best"],
            "B",
        ),
        (
            "All visitors must present a valid ------- at the reception desk.",
            ["identify", "identified", "identification", "identifiable"],
            "C",
        ),
    ]:
        ordered.append(
            _question(5, prompt=prompt, options=list(zip("ABCD", options)), correct=correct)
        )

    # --- Part 6: một đoạn văn có bốn chỗ trống -------------------------------
    notice = QuestionSet(
        part=6,
        title="Thông báo gửi khách hàng",
        passage=(
            "Thank you for choosing Lam Vien Stationery. Because of a supplier delay, a few "
            "items in your order will arrive later than planned. ---(1)--- We expect the "
            "remaining items to ship by Friday.\n\n"
            "If you would prefer not to wait, you may cancel the ---(2)--- items at no charge. "
            "---(3)--- our customer service team on 1900 6868 and we will process the request "
            "the same day.\n\n"
            "We ---(4)--- the inconvenience and thank you for your patience."
        ),
        status="published",
    )
    session.add(notice)
    for index, (options, correct) in enumerate(
        [
            (
                [
                    "The rest of your order has already been dispatched.",
                    "Our shop will be closed next week.",
                    "Please return the damaged goods to us.",
                    "We no longer sell that product.",
                ],
                "A",
            ),
            (["delay", "delayed", "delaying", "delays"], "B"),
            (["Contact", "Contacts", "Contacted", "Contacting"], "A"),
            (["regret", "regrets", "regretting", "have regretted"], "A"),
        ]
    ):
        question = _question(
            6,
            prompt=f"Chỗ trống ({index + 1})",
            options=list(zip("ABCD", options)),
            correct=correct,
        )
        question.question_set = notice
        question.position = index + 1
        ordered.append(question)

    # --- Part 7: một bài hai đoạn (email + bảng giá) -------------------------
    double = QuestionSet(
        part=7,
        title="Email và bảng giá",
        passage=(
            "To: hoa.nguyen@example.com\nFrom: sales@lamvien.example\nSubject: Quotation for "
            "your March order\n\n"
            "Dear Ms. Nguyen,\n\nThank you for your enquiry. Our current rates are attached "
            "below. Orders above 500 units qualify for the bulk rate, and delivery within Ho "
            "Chi Minh City is free for those orders.\n\n"
            "The quotation is valid until 31 March.\n\nBest regards,\nTran Minh, Sales"
        ),
        passage_2=(
            "PRICE LIST — March\n\n"
            "A4 paper (per ream)      standard 62,000 VND    bulk 54,000 VND\n"
            "Ballpoint pens (box)     standard 45,000 VND    bulk 39,000 VND\n"
            "Delivery inside HCMC     30,000 VND             free on bulk orders"
        ),
        status="published",
    )
    session.add(double)
    for index, (prompt, options, correct) in enumerate(
        [
            (
                "What is the purpose of the e-mail?",
                [
                    "To confirm a delivery",
                    "To provide prices",
                    "To apologise for a delay",
                    "To announce a new product",
                ],
                "B",
            ),
            (
                "By what date must Ms. Nguyen place her order to receive these rates?",
                ["1 March", "15 March", "31 March", "1 April"],
                "C",
            ),
            (
                "Ms. Nguyen orders 600 reams of A4 paper for delivery in Ho Chi Minh City. "
                "How much will she pay for delivery?",
                ["Nothing", "30,000 VND", "39,000 VND", "54,000 VND"],
                "A",
            ),
            (
                "What is indicated about ballpoint pens?",
                [
                    "They are out of stock",
                    "They are sold by the box",
                    "They are delivered separately",
                    "They are on sale until April",
                ],
                "B",
            ),
            (
                "What is suggested about orders below 500 units?",
                [
                    "They cannot be delivered",
                    "They are charged for delivery",
                    "They take longer to arrive",
                    "They must be paid in advance",
                ],
                "B",
            ),
        ]
    ):
        question = _question(7, prompt=prompt, options=list(zip("ABCD", options)), correct=correct)
        question.question_set = double
        question.position = index + 1
        ordered.append(question)

    # Kiểm từng câu bằng chính bộ luật mà trình nhập nội dung dùng. Dữ liệu demo
    # đi vòng qua kiểm tra là dữ liệu demo dạy sai về hình dạng dữ liệu thật.
    for question in ordered:
        problems = validate_question(question)
        if problems:
            raise ValueError(f"part {question.part}: {problems}")

    session.add_all(ordered)
    session.flush()
    for position, question in enumerate(ordered, start=1):
        session.add(
            PracticeTestQuestion(test_id=test.id, question_id=question.id, position=position)
        )
    return test


def main() -> None:
    session = SessionLocal()
    try:
        existing = session.query(PracticeTest).filter(PracticeTest.slug == TEST_SLUG).one_or_none()
        if existing is not None:
            print(f"Đã có {TEST_SLUG}; không làm gì.")
            return
        test = build(session)
        session.commit()
        count = (
            session.query(PracticeTestQuestion)
            .filter(PracticeTestQuestion.test_id == test.id)
            .count()
        )
        print(f"Đã tạo {test.slug} với {count} câu, thuộc bộ đề {COLLECTION_SLUG}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
