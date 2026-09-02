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
    # (tiếng Anh, bản dịch). Bản dịch KHÔNG tham gia chấm bài và không vào
    # `source_hash` — nó chỉ để người học biết câu mình vừa gõ nói gì.
    sentences: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Topic:
    """Một `dictation_topic` và toàn bộ unit nằm dưới nó."""

    slug: str
    name: str
    description: str
    position: int
    units: tuple[Unit, ...]


SHORT_STORY_UNITS: tuple[Unit, ...] = (
    # Unit 1 được seed bằng một đường khác từ trước khi tệp này ra đời, nên nó
    # KHÔNG có ở đây và sáu câu của nó không có bản dịch. Khai lại đúng tên và
    # tiêu đề cũ: vòng dựng khớp theo tên nên nó nhận ra story đã có, không tạo
    # thêm, và chỉ điền phần còn thiếu.
    Unit(
        name="Unit 1 — Office life",
        story_title="A Day at the Office",
        story_description="Một ngày làm việc bình thường.",
        difficulty=3,
        sentences=(
            (
                "Please submit your expense claims to the finance department.",
                "Vui lòng nộp đề nghị thanh toán chi phí cho phòng tài chính.",
            ),
            (
                "The meeting will start at nine o'clock tomorrow morning.",
                "Cuộc họp sẽ bắt đầu lúc chín giờ sáng mai.",
            ),
            (
                "The shipment has been delayed until Thursday afternoon.",
                "Lô hàng đã bị hoãn tới chiều thứ Năm.",
            ),
            (
                "The quarterly report is due before the end of the month.",
                "Báo cáo quý phải nộp trước cuối tháng.",
            ),
            (
                "All employees are required to attend the training session.",
                "Toàn thể nhân viên bắt buộc tham dự buổi tập huấn.",
            ),
            (
                "Customers can contact our support team by phone or email.",
                "Khách hàng có thể liên hệ bộ phận hỗ trợ qua điện thoại hoặc email.",
            ),
        ),
    ),
    Unit(
        name="Unit 2 — Travel and the airport",
        story_title="A Delayed Flight",
        story_description="Chuyến bay bị hoãn và một buổi chiều phải sắp xếp lại.",
        # Dễ nhất trong bốn bài: câu ngắn, từ vựng sân bay lặp lại nhiều.
        difficulty=2,
        sentences=(
            (
                "Ms. Carter arrived at the airport two hours before her flight.",
                "Bà Carter tới sân bay trước giờ bay hai tiếng.",
            ),
            (
                "The screen at the gate said her departure had been delayed.",
                "Màn hình ở cửa ra máy bay báo chuyến của bà bị hoãn.",
            ),
            (
                "She asked an agent how long the delay was expected to last.",
                "Bà hỏi nhân viên xem dự kiến hoãn bao lâu.",
            ),
            (
                "The agent explained that bad weather had grounded several planes.",
                "Nhân viên giải thích rằng thời tiết xấu khiến vài máy bay không cất cánh được.",
            ),
            (
                "Ms. Carter called her office to move the afternoon meeting.",
                "Bà Carter gọi về văn phòng để dời cuộc họp buổi chiều.",
            ),
            (
                "She found a quiet seat near the window and opened her laptop.",
                "Bà tìm một chỗ ngồi yên tĩnh cạnh cửa sổ rồi mở máy tính.",
            ),
            (
                "An announcement finally invited passengers to board through gate twelve.",
                "Cuối cùng cũng có thông báo mời hành khách lên máy bay ở cửa số mười hai.",
            ),
            (
                "The flight landed just in time for her dinner appointment.",
                "Chuyến bay hạ cánh vừa kịp cho cuộc hẹn ăn tối của bà.",
            ),
        ),
    ),
    Unit(
        name="Unit 3 — Dining out",
        story_title="Dinner with a Client",
        story_description="Một bữa tối tiếp khách, từ lúc đặt bàn đến lúc ký hoá đơn.",
        difficulty=3,
        sentences=(
            (
                "Mr. Tanaka booked a table for four at a restaurant downtown.",
                "Ông Tanaka đặt bàn bốn người ở một nhà hàng trong trung tâm.",
            ),
            (
                "He asked the waiter to seat them away from the kitchen.",
                "Ông nhờ người phục vụ xếp chỗ xa khu bếp.",
            ),
            (
                "The client arrived a few minutes late because of heavy traffic.",
                "Khách tới trễ vài phút vì đường đông.",
            ),
            (
                "They ordered the soup of the day and the grilled fish.",
                "Họ gọi món súp trong ngày và món cá nướng.",
            ),
            (
                "The waiter apologized that the dessert menu had already changed.",
                "Người phục vụ xin lỗi vì thực đơn tráng miệng đã đổi.",
            ),
            (
                "Mr. Tanaka signed the receipt and kept a copy for his expenses.",
                "Ông Tanaka ký hoá đơn và giữ một bản để thanh toán chi phí.",
            ),
            (
                "The client thanked him and promised to send the contract on Monday.",
                "Khách cảm ơn ông và hứa gửi hợp đồng vào thứ Hai.",
            ),
            (
                "They agreed to meet again once the new branch had opened.",
                "Hai bên hẹn gặp lại khi chi nhánh mới khai trương.",
            ),
        ),
    ),
    Unit(
        name="Unit 4 — Shopping and customer service",
        story_title="The Wrong Order",
        story_description="Giao thiếu hàng, gọi tổng đài, và cách chuyện được giải quyết.",
        difficulty=3,
        sentences=(
            (
                "A customer ordered two desk lamps from the company website.",
                "Một khách hàng đặt hai chiếc đèn bàn trên website công ty.",
            ),
            (
                "The package arrived on Friday with only one lamp inside.",
                "Kiện hàng tới vào thứ Sáu nhưng bên trong chỉ có một chiếc đèn.",
            ),
            (
                "She called the support line and explained what had happened.",
                "Cô gọi tổng đài hỗ trợ và trình bày sự việc.",
            ),
            (
                "The agent apologized and checked the order number in the system.",
                "Nhân viên xin lỗi rồi tra số đơn hàng trong hệ thống.",
            ),
            (
                "He confirmed that the second lamp was still in the warehouse.",
                "Anh xác nhận chiếc đèn thứ hai vẫn còn trong kho.",
            ),
            (
                "The company agreed to ship the missing item at no extra cost.",
                "Công ty đồng ý gửi món hàng còn thiếu mà không tính thêm phí.",
            ),
            (
                "She received a confirmation email within the next ten minutes.",
                "Cô nhận được email xác nhận trong vòng mười phút sau đó.",
            ),
            (
                "The replacement lamp was delivered early the following week.",
                "Chiếc đèn thay thế được giao vào đầu tuần sau.",
            ),
        ),
    ),
    Unit(
        name="Unit 5 — A job interview",
        story_title="The Second Interview",
        story_description="Vòng phỏng vấn thứ hai, và câu hỏi bao giờ đi làm được.",
        # Khó nhất: câu dài hơn, thì quá khứ hoàn thành, số liệu trong câu.
        difficulty=4,
        sentences=(
            (
                "Daniel was invited back for a second interview on Tuesday morning.",
                "Daniel được mời quay lại phỏng vấn vòng hai vào sáng thứ Ba.",
            ),
            (
                "He studied the latest annual report the night before.",
                "Tối hôm trước anh đọc kỹ báo cáo thường niên mới nhất.",
            ),
            (
                "The manager asked him to describe a project he had managed alone.",
                "Người quản lý đề nghị anh kể về một dự án anh từng tự quản lý.",
            ),
            (
                "Daniel explained how his team had cut delivery times by a third.",
                "Daniel kể nhóm của anh đã rút ngắn thời gian giao hàng một phần ba như thế nào.",
            ),
            (
                "He mentioned that he was studying for a certificate in logistics.",
                "Anh cho biết mình đang học lấy chứng chỉ về logistics.",
            ),
            (
                "The manager wanted to know when he would be available to start.",
                "Người quản lý muốn biết khi nào anh có thể bắt đầu.",
            ),
            (
                "Daniel said his current employer required four weeks of notice.",
                "Daniel nói công ty hiện tại yêu cầu báo trước bốn tuần.",
            ),
            (
                "The offer letter reached his inbox before the end of the week.",
                "Thư mời nhận việc tới hộp thư của anh trước khi hết tuần.",
            ),
        ),
    ),
    Unit(
        name="Unit 6 — Moving to a new office",
        story_title="The Move Upstairs",
        story_description="Một đội chuyển sang tầng mới, và sự cố mạng sáng thứ Hai.",
        difficulty=3,
        sentences=(
            (
                "The design team was told they would move to a new floor.",
                "Nhóm thiết kế được báo sẽ chuyển sang tầng mới.",
            ),
            (
                "Boxes and labels arrived on Monday for everyone to pack their files.",
                "Thùng và nhãn dán được đưa tới vào thứ Hai để mọi người đóng gói hồ sơ.",
            ),
            (
                "The manager asked staff to leave the monitors on the desks.",
                "Quản lý dặn nhân viên để nguyên màn hình trên bàn.",
            ),
            (
                "Movers came on Friday evening after most people had gone home.",
                "Đội chuyển đồ tới vào tối thứ Sáu, khi phần lớn mọi người đã về.",
            ),
            (
                "On Monday the team found their chairs already waiting by the window.",
                "Sáng thứ Hai cả nhóm thấy ghế của mình đã được đặt sẵn cạnh cửa sổ.",
            ),
            (
                "The network in one corner did not work for the first hour.",
                "Mạng ở một góc phòng không chạy trong tiếng đầu tiên.",
            ),
            (
                "A technician traced the fault to a cable behind the wall panel.",
                "Một kỹ thuật viên lần ra lỗi nằm ở sợi cáp sau tấm ốp tường.",
            ),
            (
                "By lunchtime the whole floor was online and the boxes were gone.",
                "Đến trưa thì cả tầng đã có mạng và thùng đồ cũng dọn xong.",
            ),
        ),
    ),
    Unit(
        name="Unit 7 — A product launch",
        story_title="Launch Day",
        story_description="Buổi ra mắt sản phẩm, từ lúc chuẩn bị tới lúc chốt đơn.",
        # Khó nhất của topic: câu dài, quá khứ hoàn thành, nhiều mệnh đề phụ.
        difficulty=4,
        sentences=(
            (
                "The marketing department had been preparing the launch since early spring.",
                "Phòng marketing đã chuẩn bị cho buổi ra mắt từ đầu mùa xuân.",
            ),
            (
                "They booked a hall downtown and invited reporters from several magazines.",
                "Họ thuê một hội trường ở trung tâm và mời phóng viên của nhiều tạp chí.",
            ),
            (
                "The samples arrived two days late because of a customs inspection.",
                "Hàng mẫu tới trễ hai ngày vì bị kiểm tra hải quan.",
            ),
            (
                "Staff worked through the evening to arrange the display tables.",
                "Nhân viên làm suốt buổi tối để sắp xếp các bàn trưng bày.",
            ),
            (
                "On the morning of the event the microphone would not switch on.",
                "Sáng hôm diễn ra sự kiện thì micro không chịu bật.",
            ),
            (
                "A technician replaced it minutes before the first guests walked in.",
                "Một kỹ thuật viên thay nó vài phút trước khi những khách đầu tiên bước vào.",
            ),
            (
                "The director opened with a short talk about how the idea began.",
                "Giám đốc mở đầu bằng một bài nói ngắn về việc ý tưởng đã ra đời thế nào.",
            ),
            (
                "By the end of the week orders had passed every earlier record.",
                "Đến cuối tuần, số đơn hàng đã vượt mọi kỷ lục trước đó.",
            ),
        ),
    ),
    Unit(
        name="Unit 8 — A visit to the clinic",
        story_title="An Appointment After Work",
        story_description="Khám bệnh sau giờ làm, và phần bảo hiểm công ty chi trả.",
        difficulty=3,
        sentences=(
            (
                "Mr. Okafor booked an appointment at the clinic near his office.",
                "Ông Okafor đặt lịch khám ở phòng khám gần văn phòng.",
            ),
            (
                "The receptionist asked him to arrive fifteen minutes before his slot.",
                "Lễ tân dặn ông tới sớm mười lăm phút so với giờ hẹn.",
            ),
            (
                "He filled in a short form about his medical history.",
                "Ông điền một tờ khai ngắn về tiền sử bệnh.",
            ),
            (
                "The doctor listened carefully and asked how long the pain had lasted.",
                "Bác sĩ nghe kỹ rồi hỏi cơn đau đã kéo dài bao lâu.",
            ),
            (
                "She recommended a blood test and some rest for the coming week.",
                "Bác sĩ đề nghị làm xét nghiệm máu và nghỉ ngơi trong tuần tới.",
            ),
            (
                "The nurse explained which counter to visit for the sample.",
                "Y tá chỉ ông tới quầy nào để lấy mẫu.",
            ),
            (
                "He was told the results would be sent by email on Thursday.",
                "Ông được báo kết quả sẽ gửi qua email vào thứ Năm.",
            ),
            (
                "His employer covered most of the cost through the company insurance plan.",
                "Công ty chi trả phần lớn chi phí qua gói bảo hiểm của công ty.",
            ),
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
            (
                "Good morning, I would like to book a meeting room for Thursday.",
                "Chào buổi sáng, tôi muốn đặt một phòng họp cho thứ Năm.",
            ),
            (
                "Certainly, how many people will be joining you?",
                "Vâng, sẽ có bao nhiêu người tham dự ạ?",
            ),
            (
                "There will be six of us, including two visitors from Osaka.",
                "Chúng tôi có sáu người, gồm hai khách từ Osaka.",
            ),
            (
                "The large room on the third floor is free until noon.",
                "Phòng lớn ở tầng ba còn trống đến trưa.",
            ),
            (
                "Could we keep it until one o'clock instead?",
                "Chúng tôi giữ phòng đến một giờ được không?",
            ),
            (
                "That should be fine, but I will have to move another booking.",
                "Chắc là được, nhưng tôi sẽ phải dời một lượt đặt khác.",
            ),
            (
                "Please let me know if that causes any trouble.",
                "Nếu có gì bất tiện thì báo tôi nhé.",
            ),
            (
                "I will send you a confirmation before the end of the day.",
                "Tôi sẽ gửi xác nhận cho anh trước khi hết ngày.",
            ),
        ),
    ),
    Unit(
        name="Unit 2 — On the phone",
        story_title="A Call from a Supplier",
        story_description="Nhà cung cấp gọi báo hàng về trễ, và hai bên thu xếp lại.",
        difficulty=3,
        sentences=(
            (
                "Good afternoon, this is Elena calling from the packaging supplier.",
                "Chào buổi chiều, tôi là Elena gọi từ nhà cung cấp bao bì.",
            ),
            (
                "I am afraid the delivery scheduled for Monday has been delayed.",
                "Rất tiếc là lô hàng dự kiến giao thứ Hai đã bị chậm.",
            ),
            (
                "May I ask how long the delay is likely to be?",
                "Cho tôi hỏi dự kiến chậm bao lâu ạ?",
            ),
            (
                "We expect the shipment to arrive by Wednesday at the latest.",
                "Chúng tôi dự kiến hàng tới chậm nhất là thứ Tư.",
            ),
            (
                "That is later than we planned, but we can work around it.",
                "Trễ hơn kế hoạch, nhưng chúng tôi vẫn xoay được.",
            ),
            (
                "I will email you the new tracking number this afternoon.",
                "Chiều nay tôi sẽ gửi email mã vận đơn mới cho anh.",
            ),
            (
                "Please copy my colleague in the warehouse on that message.",
                "Nhớ gửi kèm cho đồng nghiệp của tôi ở kho nhé.",
            ),
            (
                "Of course, and again I apologize for the inconvenience.",
                "Vâng, và một lần nữa tôi xin lỗi vì sự bất tiện này.",
            ),
        ),
    ),
    Unit(
        name="Unit 3 — Small talk at work",
        story_title="Monday Morning",
        story_description="Vài câu chào hỏi đầu tuần trước giờ họp.",
        difficulty=2,
        sentences=(
            (
                "Good morning, did you have a nice weekend?",
                "Chào buổi sáng, cuối tuần của anh vui chứ?",
            ),
            (
                "It was quiet, I spent most of it working in the garden.",
                "Cũng yên ả, tôi dành phần lớn thời gian làm vườn.",
            ),
            (
                "That sounds relaxing compared to the traffic this morning.",
                "Nghe thư giãn hơn hẳn cảnh kẹt xe sáng nay.",
            ),
            (
                "The road near the station has been closed for repairs.",
                "Con đường gần nhà ga đang bị chặn để sửa chữa.",
            ),
            (
                "I noticed that, it took me almost an hour to get here.",
                "Tôi cũng thấy vậy, mất gần một tiếng mới tới được đây.",
            ),
            (
                "There is fresh coffee in the kitchen if you need it.",
                "Trong bếp có cà phê mới pha nếu anh cần.",
            ),
            (
                "Thank you, I will get a cup before the team meeting.",
                "Cảm ơn, tôi sẽ lấy một ly trước buổi họp nhóm.",
            ),
            (
                "See you there, it starts in about ten minutes.",
                "Gặp anh ở đó nhé, khoảng mười phút nữa là bắt đầu.",
            ),
        ),
    ),
    Unit(
        name="Unit 4 — Welcoming a visitor",
        story_title="At the Reception Desk",
        story_description="Khách tới đúng hẹn, và thủ tục ở quầy lễ tân.",
        difficulty=2,
        sentences=(
            (
                "Good morning, I have an appointment with Miss Alvarez at ten.",
                "Chào buổi sáng, tôi có hẹn với cô Alvarez lúc mười giờ.",
            ),
            (
                "Welcome, could I have your name and the company you represent?",
                "Xin chào, cho tôi xin tên anh và tên công ty anh đại diện?",
            ),
            (
                "My name is Peter Lang, and I am from the auditing firm.",
                "Tôi là Peter Lang, đến từ công ty kiểm toán.",
            ),
            (
                "Thank you, please sign the visitor book and take this badge.",
                "Cảm ơn anh, mời anh ký sổ khách và nhận thẻ này.",
            ),
            (
                "Should I wait here, or go up to the fourth floor?",
                "Tôi chờ ở đây hay lên tầng bốn ạ?",
            ),
            (
                "Please take a seat, someone will come down for you shortly.",
                "Mời anh ngồi, lát nữa sẽ có người xuống đón anh.",
            ),
            (
                "Would you like a coffee or a glass of water while you wait?",
                "Trong lúc chờ anh dùng cà phê hay một ly nước nhé?",
            ),
            (
                "A glass of water would be lovely, thank you very much.",
                "Cho tôi một ly nước thì tuyệt quá, cảm ơn chị nhiều.",
            ),
        ),
    ),
    Unit(
        name="Unit 5 — Rescheduling a training session",
        story_title="Moving the Safety Training",
        story_description="Nửa đội bận hội chợ, và buổi tập huấn phải tách làm hai.",
        difficulty=3,
        sentences=(
            (
                "I am calling about the safety training booked for next Tuesday.",
                "Tôi gọi về buổi tập huấn an toàn đã đặt vào thứ Ba tuần sau.",
            ),
            (
                "Yes, I have the session down for the whole morning.",
                "Vâng, tôi có ghi buổi đó chiếm trọn buổi sáng.",
            ),
            (
                "Unfortunately half the team will be at the trade fair that day.",
                "Tiếc là hôm đó một nửa nhóm sẽ đi hội chợ thương mại.",
            ),
            (
                "Would you rather move the session or split it into two groups?",
                "Anh muốn dời buổi học hay tách thành hai nhóm?",
            ),
            (
                "Splitting it would work better, if the trainer is available twice.",
                "Tách ra thì hợp hơn, nếu giảng viên rảnh được hai lần.",
            ),
            (
                "I will check her calendar and confirm before the end of today.",
                "Tôi sẽ xem lịch của cô ấy rồi xác nhận trong hôm nay.",
            ),
            (
                "Please also let the facilities team know about the room.",
                "Nhớ báo cả bộ phận cơ sở vật chất về phòng học nữa.",
            ),
            (
                "I will copy them on the message so that nothing is missed.",
                "Tôi sẽ gửi kèm họ trong email để không sót gì.",
            ),
        ),
    ),
    Unit(
        name="Unit 6 — Ordering office supplies",
        story_title="The Empty Cupboard",
        story_description="Hết văn phòng phẩm, và một phiếu mua hàng cần chữ ký.",
        difficulty=3,
        sentences=(
            (
                "The stationery cupboard is nearly empty again on the second floor.",
                "Tủ văn phòng phẩm ở tầng hai lại gần hết rồi.",
            ),
            (
                "I noticed that too, shall I raise a purchase request?",
                "Tôi cũng thấy vậy, tôi lập phiếu đề nghị mua hàng nhé?",
            ),
            (
                "Please do, and add the printer paper we ran out of.",
                "Anh làm giúp, thêm cả giấy in mà mình đã dùng hết.",
            ),
            (
                "Does the order still need approval from the department manager?",
                "Đơn này vẫn cần trưởng phòng duyệt phải không?",
            ),
            (
                "Anything above five hundred thousand dong does, so this one will.",
                "Trên năm trăm nghìn đồng là cần, nên đơn này có.",
            ),
            (
                "I will draft it now and send it for signature this afternoon.",
                "Tôi soạn ngay bây giờ và chiều nay trình ký.",
            ),
            (
                "Ask the supplier whether delivery before Friday is still possible.",
                "Hỏi nhà cung cấp xem có giao trước thứ Sáu được không.",
            ),
            (
                "I will mention it, and I will forward whatever they reply.",
                "Tôi sẽ hỏi, và họ trả lời sao tôi chuyển tiếp vậy.",
            ),
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
            (
                "Attention shoppers, the store will be closing in thirty minutes.",
                "Kính mời quý khách chú ý, cửa hàng sẽ đóng cửa sau ba mươi phút.",
            ),
            (
                "Please bring your final purchases to the checkout counters now.",
                "Xin quý khách mang những món cuối cùng ra quầy thanh toán ngay bây giờ.",
            ),
            (
                "The customer service desk on the ground floor closes even earlier.",
                "Quầy chăm sóc khách hàng ở tầng trệt còn đóng sớm hơn.",
            ),
            (
                "Members of our loyalty program can collect double points this weekend.",
                "Cuối tuần này, thành viên chương trình khách hàng thân thiết được nhân đôi điểm.",
            ),
            (
                "The winter sale continues in the clothing section on the second floor.",
                "Đợt giảm giá mùa đông vẫn tiếp tục ở khu quần áo tầng hai.",
            ),
            (
                "Parking remains free for one hour with any purchase over fifty thousand dong.",
                "Hoá đơn trên năm mươi nghìn đồng được miễn phí gửi xe một tiếng.",
            ),
            (
                "We open again tomorrow morning at half past eight.",
                "Chúng tôi mở cửa lại vào tám giờ rưỡi sáng mai.",
            ),
            (
                "Thank you for shopping with us, and have a pleasant evening.",
                "Cảm ơn quý khách đã mua sắm, chúc quý khách một buổi tối vui vẻ.",
            ),
        ),
    ),
    Unit(
        name="Unit 2 — A voicemail message",
        story_title="A Missing Order Number",
        story_description="Tin nhắn thoại từ phòng kế toán về một hoá đơn thiếu thông tin.",
        difficulty=3,
        sentences=(
            (
                "Hello, this is Ruth calling from the accounts department on Tuesday.",
                "Xin chào, tôi là Ruth ở phòng kế toán, gọi vào thứ Ba.",
            ),
            (
                "I am sorry to have missed you, I hope this reaches you today.",
                "Rất tiếc là không gặp được anh, mong lời nhắn này tới anh trong hôm nay.",
            ),
            (
                "The invoice you sent last week is missing a purchase order number.",
                "Hoá đơn anh gửi tuần trước thiếu số đơn đặt hàng.",
            ),
            (
                "Without that number our system cannot release the payment.",
                "Thiếu số đó thì hệ thống của chúng tôi không giải ngân được.",
            ),
            (
                "Could you resend the document with the number in the subject line?",
                "Anh gửi lại chứng từ và ghi số đó ở tiêu đề email được không?",
            ),
            (
                "If it is easier, my extension is four one six.",
                "Nếu tiện hơn thì số máy lẻ của tôi là bốn một sáu.",
            ),
            (
                "I will be at my desk until about five this afternoon.",
                "Tôi ngồi ở bàn làm việc đến khoảng năm giờ chiều nay.",
            ),
            (
                "Thank you very much, and I look forward to hearing from you.",
                "Cảm ơn anh nhiều, tôi mong sớm nhận được hồi âm.",
            ),
        ),
    ),
    Unit(
        name="Unit 3 — A staff briefing",
        story_title="Three Things Before the Shift",
        story_description="Dặn dò đầu ca: khu bốc hàng, thẻ an toàn, và lịch đánh giá.",
        difficulty=4,
        sentences=(
            (
                "Good morning everyone, thank you for coming in a little earlier.",
                "Chào cả nhà, cảm ơn mọi người đã tới sớm hơn một chút.",
            ),
            (
                "There are three things to cover before the shift begins.",
                "Có ba việc cần nói trước khi vào ca.",
            ),
            (
                "First, the loading bay will be closed for repairs until Thursday.",
                "Thứ nhất, bến bốc hàng sẽ đóng để sửa chữa cho tới thứ Năm.",
            ),
            (
                "Deliveries during that time should be directed to the side entrance.",
                "Trong thời gian đó, hàng giao xin chuyển sang lối vào bên hông.",
            ),
            (
                "Second, the new safety cards must be signed by the end of the month.",
                "Thứ hai, thẻ an toàn mới phải được ký xong trước cuối tháng.",
            ),
            (
                "Anyone who has not received one should speak to their supervisor today.",
                "Ai chưa nhận được thẻ thì hôm nay gặp quản lý trực tiếp của mình.",
            ),
            (
                "Finally, the annual review meetings will start the week after next.",
                "Cuối cùng, các buổi đánh giá thường niên sẽ bắt đầu từ tuần sau nữa.",
            ),
            (
                "Your team leader will send round a sheet for choosing a time.",
                "Trưởng nhóm sẽ chuyển tới mọi người một bảng để chọn giờ.",
            ),
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
    translated: int = 0
    published: int = 0

    def as_line(self) -> str:
        return (
            f"{self.sections} unit · {self.stories} bài · {self.items} câu mới · "
            f"{self.translated} câu vừa được dịch · {self.published} hàng vừa publish"
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
        # Giữ cả HÀNG chứ không chỉ chuỗi: câu đã có vẫn có thể còn thiếu bản
        # dịch, và một seed chỉ biết "đã có thì bỏ qua" sẽ không bao giờ điền
        # được — 134 câu cũ sẽ ở lại không lời dịch mãi mãi.
        existing = {
            item.transcript: item
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
        for sentence, translation in unit.sentences:
            found = existing.get(sentence)
            if found is not None:
                # Chỉ điền khi đang trống. Ghi đè sẽ xoá mất bản dịch ai đó vừa
                # sửa tay ở màn quản trị, và xoá một cách im lặng.
                if found.transcript_vi is None:
                    found.transcript_vi = translation
                    counts.translated += 1
                continue
            highest += 1
            session.add(
                DictationItem(
                    # NULL cho tới khi backfill_audio thu xong; CHECK trên bảng
                    # là thứ chặn hàng này lọt ra cho học viên trước lúc đó.
                    audio_asset_id=None,
                    transcript=sentence,
                    transcript_vi=translation,
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
