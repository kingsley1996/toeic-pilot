"""Blueprint: quyết định đề sẽ là gì, TRƯỚC khi gọi mô hình.

**Vì sao tách riêng thay vì để mô hình tự quyết.** Mô hình viết câu hỏi giỏi hơn
nhiều so với thiết kế đề. Bảo nó "sinh 30 câu Part 5" thì phần lớn sẽ rơi vào
cùng vài điểm ngữ pháp dễ nhất, vì đó là vùng xác suất cao nhất — và không có gì
trong đầu ra nói cho ta biết điều đó đã xảy ra. Phân bố điểm ngữ pháp là quyết
định của người ra đề, nên nó được ghi ra thành dữ liệu và mô hình chỉ việc viết
đúng ô đã giao.

Hệ quả thứ hai, quan trọng không kém: **nhãn được quyết định trước, không gắn
sau**. `enrich_skills.py` hiện đọc câu rồi đoán nhãn; với đề tự sinh thì đảo lại
— blueprint giao nhãn, và `enrich_skills` trở thành **bước đối chiếu**: nó đoán
khác thứ đã giao nghĩa là câu viết chưa đúng dạng, chứ không phải nhãn sai.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.core.media import LOGICAL_VOICE_ACCENTS
from app.services.labels import codes_for

# Part 5 kiểm 11 điểm ngữ pháp (Part 6 chỉ 5 — hai danh sách KHÁC nhau, xem
# `labels.py`). Trọng số dưới đây theo tỉ lệ thường thấy của đề thật: từ loại và
# từ vựng chiếm phần lớn, các cấu trúc hẹp hơn xuất hiện một hai câu.
#
# Con số là điểm KHỞI ĐẦU để người ra đề sửa, không phải luật. Nó nằm trong
# blueprint đã ghi ra đĩa chính vì thế: sửa một tệp JSON dễ hơn sửa một hằng số.
PART5_MIX: tuple[tuple[str, str, int], ...] = (
    ("PART_5_PART_OF_SPEECH", "GRAMMAR_NOUN", 3),
    ("PART_5_PART_OF_SPEECH", "GRAMMAR_ADJECTIVE", 3),
    ("PART_5_PART_OF_SPEECH", "GRAMMAR_ADVERB", 3),
    ("PART_5_GRAMMAR", "GRAMMAR_TENSE", 3),
    ("PART_5_GRAMMAR", "GRAMMAR_VOICE", 2),
    ("PART_5_GRAMMAR", "GRAMMAR_PRONOUN", 2),
    ("PART_5_GRAMMAR", "GRAMMAR_PARTICIPLE", 2),
    ("PART_5_GRAMMAR", "GRAMMAR_RELATIVE_CLAUSE", 2),
    ("PART_5_GRAMMAR", "GRAMMAR_COMPARISON", 1),
    ("PART_5_GRAMMAR", "GRAMMAR_CONJUNCTION", 2),
    ("PART_5_VOCABULARY", "GRAMMAR_PREPOSITION", 3),
    ("PART_5_VOCABULARY", "", 4),
)

# Bối cảnh của câu. TOEIC lấy trọn bối cảnh công sở và thương mại, không bao giờ
# lấy đời sống riêng tư — nên danh sách này vừa là chỉ dẫn cho mô hình vừa là
# phép chống trôi: 30 câu cùng nói về "the manager" đọc ra ngay là máy viết.
BUSINESS_CONTEXTS: tuple[str, ...] = (
    "hợp đồng và đàm phán",
    "tuyển dụng và nhân sự",
    "lịch họp và lịch công tác",
    "đơn hàng và giao vận",
    "báo cáo tài chính quý",
    "bảo trì thiết bị văn phòng",
    "chiến dịch marketing",
    "dịch vụ khách hàng",
    "đào tạo nội bộ",
    "thuê và sửa chữa mặt bằng",
)


# Part 1: sáu bức ảnh, và bố cục dưới đây theo tỉ lệ thường thấy của đề thật —
# phần lớn là ảnh có người, một hai ảnh chỉ có vật.
#
# `scene` KHÔNG phải prompt vẽ ảnh. Nó là bối cảnh giao cho người viết câu, và
# ảnh sẽ được vẽ SAU, khớp với bốn câu đã viết. Chiều phụ thuộc đó là điểm khác
# quan trọng nhất giữa đề tự sinh và đề mượn ảnh (ADR-004 §4): với ảnh mượn, ta
# phải tìm được tấm mà bốn câu viết được về nó; với ảnh sinh, ta viết bốn câu
# trước rồi vẽ tấm ảnh khớp.
# Ba dạng tranh của Part 1, và `people` là thứ CHIA chúng — không phải mã nhãn.
#
# Bảng nhãn phân biệt "tả người" với "tả cả người và vật", nhưng cả hai đều có
# người, nên nó không nói được sự khác nhau mà người luyện đề thật sự gặp: một
# người / nhiều người / không có người. Dạng thứ ba là dạng dễ bỏ sót nhất, vì
# mọi cổng kiểm của pipeline làm việc ở tầng CÂU và một đề gồm sáu tấm cùng dạng
# vẫn qua sạch mọi phép đo — đúng cùng hình dạng với thiên lệch vị trí đáp án,
# thứ đã phải sửa bằng một cổng riêng ở tầng đề.
PEOPLE_SHAPES = ("one", "several", "none")

# Part 3 và 4 đều ba câu một cụm — đó là hình dạng của đề thật.
LISTENING_QUESTIONS_PER_SET = 3

# Phân bố của một đề thật: phần lớn có người, và đúng một tấm tả vật hoặc cảnh.
PART1_MIX: tuple[tuple[str, str, str], ...] = (
    ("PART_1_PERSON_DESCRIPTION", "one", "một người đang làm việc tại bàn làm việc"),
    (
        "PART_1_PERSON_AND_OBJECT_DESCRIPTION",
        "several",
        "hai đồng nghiệp đứng cạnh máy in trong văn phòng",
    ),
    ("PART_1_PERSON_DESCRIPTION", "one", "một nhân viên kho đẩy xe hàng"),
    (
        "PART_1_PERSON_AND_OBJECT_DESCRIPTION",
        "several",
        "một người bán hàng trao túi cho khách ở quầy",
    ),
    (
        "PART_1_PERSON_AND_OBJECT_DESCRIPTION",
        "several",
        "vài người ngồi họp quanh bàn có màn chiếu",
    ),
    (
        "PART_1_OBJECT_OR_SCENE_DESCRIPTION",
        "none",
        "một phòng làm việc trống với bàn ghế và thiết bị đã xếp sẵn",
    ),
)


# Part 3: mười ba cuộc hội thoại, mỗi cuộc ba câu — câu 32 tới 70 của đề thật.
#
# **Ô của Part 3 là một CUỘC HỘI THOẠI, không phải một câu.** Ba câu của cùng một
# hội thoại phải được viết cùng nhau, vì chúng hỏi về cùng một đoạn thoại và
# không được hỏi trùng nhau; viết rời từng câu thì mô hình không biết hai câu kia
# đã hỏi gì. Nó cũng khớp với schema: bản thu và nhãn chủ đề nằm ở `question_set`
# (ADR-001 §A4.3), nên một tệp dán ↔ một cụm là ánh xạ đúng.
#
# `speakers` là số người nói. Đề thật có cả hội thoại hai người lẫn ba người, và
# ba người là dạng người học hay trượt nhất vì phải theo dõi ai nói gì.
# Phần tử thứ năm là BRIEF của hình đi kèm; rỗng nghĩa là cụm không có hình.
#
# Đo ở đề mẫu chính thức của ETS: Part 3 có đúng BA hình, nằm ở ba cụm CUỐI,
# và câu hỏi về hình luôn là câu THỨ BA của cụm (câu 64, 67, 70). Rải chúng
# vào giữa đề là sai một chi tiết mà người luyện đề nhận ra ngay.
PART3_MIX: tuple[tuple[str, int, str, tuple[str, str, str], str], ...] = (
    (
        "PART_3_COMPANY_PERSONNEL",
        2,
        "hai đồng nghiệp bàn về lịch phỏng vấn ứng viên",
        ("PART_3_TOPIC_OR_PURPOSE", "PART_3_CONVERSATION_DETAIL", "PART_3_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_3_SHOPPING_OR_SERVICE",
        2,
        "khách gọi cho cửa hàng vì đơn hàng giao thiếu",
        ("PART_3_TOPIC_OR_PURPOSE", "PART_3_SPEAKER_IDENTITY", "PART_3_REQUEST_OR_SUGGESTION"),
        "",
    ),
    (
        "PART_3_COMPANY_EVENT_OR_PROJECT",
        3,
        "ba người chuẩn bị gian hàng cho hội chợ thương mại",
        ("PART_3_LOCATION", "PART_3_CONVERSATION_DETAIL", "PART_3_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_3_HOUSING",
        2,
        "người thuê hỏi ban quản lý toà nhà về việc sửa hệ thống sưởi",
        ("PART_3_TOPIC_OR_PURPOSE", "PART_3_CONVERSATION_DETAIL", "PART_3_REQUEST_OR_SUGGESTION"),
        "",
    ),
    (
        "PART_3_COMPANY_PERSONNEL",
        2,
        "trưởng phòng và nhân viên bàn về khoá đào tạo bắt buộc",
        ("PART_3_SPEAKER_IDENTITY", "PART_3_CONVERSATION_DETAIL", "PART_3_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_3_SHOPPING_OR_SERVICE",
        2,
        "khách đổi trả một chiếc máy in mua tuần trước",
        ("PART_3_TOPIC_OR_PURPOSE", "PART_3_CONVERSATION_DETAIL", "PART_3_REQUEST_OR_SUGGESTION"),
        "",
    ),
    (
        "PART_3_COMPANY_EVENT_OR_PROJECT",
        3,
        "ba người rà lại tiến độ dự án phần mềm trước hạn",
        ("PART_3_TOPIC_OR_PURPOSE", "PART_3_SPEAKER_IDENTITY", "PART_3_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_3_HOUSING",
        2,
        "hai người xem một mặt bằng văn phòng cho thuê",
        ("PART_3_LOCATION", "PART_3_CONVERSATION_DETAIL", "PART_3_REQUEST_OR_SUGGESTION"),
        "",
    ),
    (
        "PART_3_COMPANY_PERSONNEL",
        2,
        "nhân viên xin đổi ca và đồng nghiệp trả lời",
        ("PART_3_TOPIC_OR_PURPOSE", "PART_3_CONVERSATION_DETAIL", "PART_3_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_3_SHOPPING_OR_SERVICE",
        2,
        "khách hỏi về gói bảo hành mở rộng ở quầy dịch vụ",
        ("PART_3_SPEAKER_IDENTITY", "PART_3_CONVERSATION_DETAIL", "PART_3_REQUEST_OR_SUGGESTION"),
        "",
    ),
    (
        "PART_3_COMPANY_EVENT_OR_PROJECT",
        2,
        "hai người chốt gói dịch vụ cho lễ kỷ niệm công ty",
        (
            "PART_3_TOPIC_OR_PURPOSE",
            "PART_3_CONVERSATION_DETAIL",
            "PART_3_GRAPH_OR_TABLE_QUESTION",
        ),
        "table: bảng giá bốn gói dịch vụ tổ chức sự kiện, cột Package và Price",
    ),
    (
        "PART_3_COMPANY_EVENT_OR_PROJECT",
        3,
        "ba người phân công lại ca trực sau khi một đồng nghiệp nghỉ phép",
        (
            "PART_3_SPEAKER_IDENTITY",
            "PART_3_CONVERSATION_DETAIL",
            "PART_3_GRAPH_OR_TABLE_QUESTION",
        ),
        "schedule: lịch rảnh/bận của hai người qua bốn khung giờ trong ngày",
    ),
    (
        "PART_3_HOUSING",
        2,
        "hai người chọn kho hàng mới trong bốn địa điểm",
        ("PART_3_TOPIC_OR_PURPOSE", "PART_3_LOCATION", "PART_3_GRAPH_OR_TABLE_QUESTION"),
        "map: sơ đồ khu kho gồm bốn nhà kho xếp thành hai hàng",
    ),
)

# Người nói của một cuộc hội thoại dùng CÙNG MỘT accent, đổi accent giữa các cuộc.
#
# Không phải tuỳ tiện: `audio_asset.accent` giữ đúng một giá trị, nên một clip
# trộn accent phải tự khai báo (MEDIA-PIPELINE §10.2) — và quên khai báo thì một
# giọng bị chọn hộ, im lặng. Đề thật cũng đổi accent giữa các bài chứ hiếm khi
# trong một bài. Giữ cùng accent trong một cuộc thì cái bẫy đó không tồn tại.
PART3_CASTS: tuple[tuple[str, ...], ...] = (
    ("us_female_1", "us_male_1"),
    ("uk_male_1", "uk_female_1"),
    ("au_female_1", "au_male_1"),
    ("ca_male_1", "ca_female_1"),
)

# Ba người nói thì buộc phải mượn một giọng của accent khác: mỗi accent chỉ có
# hai giọng. Ghép US với CA (hoặc UK với AU) vì hai accent đó gần nhau, nên một
# nhóm ba người vẫn nghe tự nhiên.
#
# Trộn accent ở ĐÂY thì an toàn, khác với đường spec file: `_accent_of` lấy
# accent của lượt đầu và `backfill_audio` ghi rõ vì sao được phép — audio của
# câu hỏi không ai lọc theo accent, nó chỉ đi kèm đúng câu đó. Ở từ vựng thì
# ngược lại, accent là khoá tra cứu và chọn hộ là hỏng.
PART3_TRIOS: tuple[tuple[str, ...], ...] = (
    ("us_female_1", "us_male_1", "ca_male_1"),
    ("uk_male_1", "uk_female_1", "au_female_1"),
    ("ca_female_1", "ca_male_1", "us_male_1"),
    ("au_male_1", "au_female_1", "uk_female_1"),
)


# Part 4: mười bài nói, mỗi bài ba câu — câu 71 tới 100 của đề thật.
#
# Khác Part 3 ở đúng hai chỗ, và cả hai đều nằm trong dữ liệu chứ không trong mã:
# **một người nói** (đây là bài nói, không phải hội thoại), và nhãn cụm là *dạng
# bài nói* chứ không phải *chủ đề* — hai mặt phân loại khác nhau của bảng nhãn.
#
# Hai bài CUỐI có hình, và **câu hỏi về hình là câu THỨ HAI của cụm**, không phải
# câu thứ ba như Part 3. Đo ở đề mẫu ETS: câu 96 nằm trong cụm 95–97, câu 99
# trong cụm 98–100. Một chi tiết nhỏ, nhưng người luyện đề nhận ra ngay.
PART4_MIX: tuple[tuple[str, str, tuple[str, str, str], str], ...] = (
    (
        "PART_4_TELEPHONE_MESSAGE",
        "lời nhắn thoại báo đơn hàng bị chậm và đề nghị gọi lại",
        ("PART_4_TOPIC_OR_PURPOSE", "PART_4_DETAIL", "PART_4_REQUEST_OR_SUGGESTION"),
        "",
    ),
    (
        "PART_4_ANNOUNCEMENT",
        "thông báo trong toà nhà về việc bảo trì thang máy cuối tuần",
        ("PART_4_SPEAKER_OR_LOCATION", "PART_4_DETAIL", "PART_4_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_4_ADVERTISEMENT",
        "quảng cáo một chuỗi cửa hàng nội thất đang giảm giá",
        ("PART_4_TOPIC_OR_PURPOSE", "PART_4_DETAIL", "PART_4_REQUEST_OR_SUGGESTION"),
        "",
    ),
    (
        "PART_4_MEETING_EXCERPT",
        "trích buổi họp phòng kinh doanh về kết quả quý vừa rồi",
        ("PART_4_SPEAKER_OR_LOCATION", "PART_4_DETAIL", "PART_4_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_4_TALK",
        "bài phát biểu mở đầu một khoá đào tạo nhân viên mới",
        ("PART_4_TOPIC_OR_PURPOSE", "PART_4_DETAIL", "PART_4_IMPLICATION"),
        "",
    ),
    (
        "PART_4_ANNOUNCEMENT",
        "thông báo ở sân bay về việc đổi cửa lên máy bay",
        ("PART_4_SPEAKER_OR_LOCATION", "PART_4_DETAIL", "PART_4_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_4_TELEPHONE_MESSAGE",
        "lời nhắn của khách hàng hỏi về lịch lắp đặt thiết bị",
        ("PART_4_TOPIC_OR_PURPOSE", "PART_4_DETAIL", "PART_4_REQUEST_OR_SUGGESTION"),
        "",
    ),
    (
        "PART_4_TALK",
        "hướng dẫn viên giới thiệu lịch tham quan nhà máy",
        ("PART_4_SPEAKER_OR_LOCATION", "PART_4_DETAIL", "PART_4_FUTURE_ACTION"),
        "",
    ),
    (
        "PART_4_MEETING_EXCERPT",
        "trích buổi họp công bố doanh số bốn quý của công ty",
        ("PART_4_TOPIC_OR_PURPOSE", "PART_4_GRAPH_OR_TABLE_QUESTION", "PART_4_FUTURE_ACTION"),
        "chart: biểu đồ cột doanh số bốn quý, nhãn là tên quý",
    ),
    (
        "PART_4_ANNOUNCEMENT",
        "thông báo trong trung tâm thương mại chỉ đường tới một quầy",
        ("PART_4_SPEAKER_OR_LOCATION", "PART_4_GRAPH_OR_TABLE_QUESTION", "PART_4_DETAIL"),
        "map: sơ đồ tầng trệt gồm bốn quầy xếp thành hai hàng",
    ),
)

# Một bài nói, một giọng. Xoay đều bốn accent qua mười bài.
PART4_VOICES = ("us_male_1", "uk_female_1", "au_male_1", "ca_female_1")


@dataclass
class QuestionSlot:
    """Một ô trong đề: chỗ này sẽ là câu hỏi gì.

    `id` là định danh BỀN của ô, và nó là tên tệp dán. Nhờ nó, chạy lại chặng
    sinh chỉ viết những ô còn thiếu — hàng đợi là một truy vấn trên thư mục, y
    như `backfill_audio` hỏi database "cái gì còn thiếu audio".
    """

    id: str
    number: int
    question_type: str
    grammar: str
    context: str
    # Giọng đọc, chỉ Part 1–4 dùng. Khai ở blueprint chứ không để người viết câu
    # chọn: giọng là thuộc tính của ĐỀ (rải đều bốn accent), không phải của một
    # câu, và để mô hình chọn thì sáu câu sẽ cùng một giọng.
    voice: str = ""
    # Part 1: "one" / "several" / "none". Blueprint giữ nó chứ không để người
    # viết câu suy ra từ bối cảnh, vì đây là thứ phải phủ đủ trên CẢ đề — một
    # thuộc tính của đề thì phải nằm ở nơi mô tả đề.
    people: str = ""
    # Part 3 và 4: ô là một CỤM, nên nó mang ba nhãn dạng câu (một cho mỗi câu),
    # một nhãn chủ đề của cụm, và dàn giọng của cuộc hội thoại. `question_type`
    # và `voice` để rỗng ở đó — chúng là trường của một ô-một-câu.
    question_types: list[str] = field(default_factory=list)
    topic: str = ""
    voices: list[str] = field(default_factory=list)
    # Brief của hình đi kèm (Part 3/4), dạng `kind: mô tả`. Rỗng nghĩa là cụm
    # không có hình — và phần lớn cụm không có: đề thật chỉ có ba hình ở Part 3,
    # hai ở Part 4.
    #
    # `kind` nằm ngay trong brief chứ không là trường riêng, vì nó là thứ DUY
    # NHẤT người viết blueprint phải chọn cùng lúc với nội dung: một sơ đồ và
    # một bảng giá không hoán đổi cho nhau được, và tách đôi chỉ tạo ra khả năng
    # hai nửa nói hai điều khác nhau.
    graphic: str = ""


@dataclass
class PartPlan:
    part: int
    slots: list[QuestionSlot] = field(default_factory=list)


@dataclass
class Blueprint:
    slug: str
    title: str
    seed: int
    parts: list[PartPlan] = field(default_factory=list)

    def slot_count(self) -> int:
        return sum(len(part.slots) for part in self.parts)


def build_part5(slug: str, title: str, seed: int, count: int = 30) -> Blueprint:
    """Dựng blueprint cho Part 5 từ bảng trọng số.

    `seed` làm bố cục lặp lại được, KHÔNG làm câu chữ lặp lại được: mô hình không
    tất định, và giả vờ nó tất định là tự lừa mình. Cái `seed` mua về là khi hai
    người chạy cùng một blueprint, họ nói về cùng một đề — cùng phân bố ngữ pháp,
    cùng thứ tự ô — nên so sánh kết quả với nhau có nghĩa.
    """
    rng = random.Random(seed)

    picks: list[tuple[str, str]] = []
    for question_type, grammar, weight in PART5_MIX:
        picks.extend([(question_type, grammar)] * weight)
    if len(picks) < count:
        # Bảng trọng số cộng lại ít hơn số câu cần: bù bằng cách lặp lại chính
        # nó theo đúng tỉ lệ, chứ không nhét thêm một điểm ngữ pháp tuỳ ý.
        picks = (picks * (count // len(picks) + 1))[:count]
    rng.shuffle(picks)
    picks = picks[:count]

    slots = [
        QuestionSlot(
            id=f"p5-{index:02d}",
            # Số câu chuẩn của Part 5 trong đề thật: 101–130. Lưu số này ngay từ
            # blueprint chứ không suy ra lúc nạp — ADR-007 đã chốt rằng số câu là
            # thứ được LƯU, vì suy ra thì mọi tầng phải suy lại giống hệt nhau.
            number=100 + index,
            question_type=question_type,
            grammar=grammar,
            context=BUSINESS_CONTEXTS[index % len(BUSINESS_CONTEXTS)],
        )
        for index, (question_type, grammar) in enumerate(picks, start=1)
    ]
    return Blueprint(slug=slug, title=title, seed=seed, parts=[PartPlan(part=5, slots=slots)])


# Bốn giọng logic, rải vòng tròn qua các câu. Tên LOGIC (`us_female_1`), không
# phải id nhà cung cấp — chính lớp gián tiếp đó đã cứu thư viện audio khi
# Microsoft đổi tên `en-AU-WilliamNeural` (PHASE2-AUDIO §A4).
PART1_VOICES = ("us_female_1", "uk_male_1", "au_female_1", "ca_male_1")


def build_part1(slug: str, title: str, seed: int) -> Blueprint:
    """Sáu ô Part 1. Số câu chuẩn của đề thật là 1–6."""
    slots = [
        QuestionSlot(
            id=f"p1-{index:02d}",
            number=index,
            question_type=question_type,
            grammar="",
            context=scene,
            voice=PART1_VOICES[(index - 1 + seed) % len(PART1_VOICES)],
            people=people,
        )
        for index, (question_type, people, scene) in enumerate(PART1_MIX, start=1)
    ]
    return Blueprint(slug=slug, title=title, seed=seed, parts=[PartPlan(part=1, slots=slots)])


def build_part3(slug: str, title: str, seed: int) -> Blueprint:
    """Mười ba cuộc hội thoại Part 3, câu 32–70 của đề thật.

    Một ô = một cuộc hội thoại = một tệp dán = một lượt gọi. Ba câu phải được
    viết CÙNG NHAU: chúng hỏi về cùng một đoạn thoại và không được hỏi trùng
    nhau, mà viết rời thì mô hình không biết hai câu kia đã hỏi gì.
    """
    slots = []
    for index, (topic, speakers, scene, types, graphic) in enumerate(PART3_MIX):
        pool = PART3_TRIOS if speakers == 3 else PART3_CASTS
        slots.append(
            QuestionSlot(
                id=f"p3-{index + 1:02d}",
                number=32 + index * 3,
                question_type="",
                grammar="",
                context=scene,
                question_types=list(types),
                topic=topic,
                voices=list(pool[(index + seed) % len(pool)]),
                graphic=graphic,
            )
        )
    return Blueprint(slug=slug, title=title, seed=seed, parts=[PartPlan(part=3, slots=slots)])


# Câu hỏi về hình đứng ở vị trí nào trong cụm (đánh số từ 0). Đo ở đề mẫu ETS.
GRAPHIC_POSITION = {3: 2, 4: 1}


def graph_code(part: int) -> str:
    return f"PART_{part}_GRAPH_OR_TABLE_QUESTION"


def _set_slot_problems(slot: QuestionSlot, part: int, valid_types: set[str]) -> list[str]:
    """Kiểm một ô CỤM (Part 3, 4). Ba câu, một chủ đề, một dàn giọng.

    Kiểm ở đây chứ không đợi lúc dán: một mã nhãn sai chỉ lộ ra sau khi đã sinh
    xong mười ba cuộc hội thoại, và lúc đó thứ phải sửa là mười ba tệp chứ không
    phải một dòng JSON. Cùng lý do như phần kiểm nhãn của ô-một-câu.
    """
    problems: list[str] = []
    expected = LISTENING_QUESTIONS_PER_SET
    if len(slot.question_types) != expected:
        problems.append(f"{slot.id}: cụm Part {part} cần {expected} nhãn dạng câu")
    for code in slot.question_types:
        if code not in valid_types:
            problems.append(f"{slot.id}: `{code}` không phải nhãn của part {part}")
    if len(set(slot.question_types)) != len(slot.question_types):
        # Ba câu hỏi cùng một dạng về cùng một đoạn thoại thì gần như chắc chắn
        # hỏi trùng nhau — và cái trùng đó nằm ở nội dung, chỗ không cổng nào
        # bắt được.
        problems.append(f"{slot.id}: ba câu trùng dạng")

    topics = {label.code for label in codes_for("topic", part)}
    speech = {label.code for label in codes_for("speech_type", part)}
    allowed = topics | speech
    if allowed and slot.topic not in allowed:
        problems.append(f"{slot.id}: `{slot.topic}` không phải nhãn cụm của part {part}")

    # Câu hỏi về hình và sự tồn tại của hình phải đi cùng nhau, cả hai chiều.
    # Một cụm có nhãn `GRAPH_OR_TABLE` mà không có hình là một câu hỏi bảo người
    # học "nhìn vào hình" trong khi không có hình nào; ngược lại, một hình không
    # có câu nào hỏi tới nó chỉ là một tấm ảnh thừa cạnh ba câu không dùng nó.
    asks_about_graphic = graph_code(part) in slot.question_types
    if asks_about_graphic and not slot.graphic:
        problems.append(f"{slot.id}: có câu hỏi về hình nhưng cụm không có hình")
    if slot.graphic and not asks_about_graphic:
        problems.append(f"{slot.id}: có hình nhưng không câu nào hỏi tới nó")
    if slot.graphic:
        from app.content.exam.graphics import KINDS

        kind = slot.graphic.split(":")[0].strip()
        if kind not in KINDS:
            problems.append(f"{slot.id}: dạng hình `{kind}` không có — phải là một trong {KINDS}")
    # Vị trí của câu hỏi về hình KHÁC nhau giữa hai part, đo ở đề mẫu ETS:
    # Part 3 đặt nó ở câu thứ BA (câu 64, 67, 70), Part 4 ở câu thứ HAI (câu 96,
    # 99). Suy ra "luôn là câu cuối" từ Part 3 rồi áp cho Part 4 là sai đúng một
    # chi tiết mà người luyện đề nhận ra ngay.
    if slot.graphic:
        want_at = GRAPHIC_POSITION[part]
        at = [i for i, code in enumerate(slot.question_types) if code == graph_code(part)]
        if at != [want_at]:
            problems.append(
                f"{slot.id}: câu hỏi về hình của Part {part} phải là câu thứ {want_at + 1}"
            )

    # Part 4 là bài NÓI: đúng một người. Part 3 là hội thoại: hai hoặc ba.
    low, high = (1, 1) if part == 4 else (2, 3)
    if not low <= len(slot.voices) <= high:
        wanted = "đúng 1 giọng" if part == 4 else "2 hoặc 3 giọng"
        problems.append(f"{slot.id}: cụm Part {part} cần {wanted}")
    if len(set(slot.voices)) != len(slot.voices):
        # Hai lượt cùng giọng thì người nghe không tách được ai đang nói, và câu
        # hỏi "người đàn ông nói gì" mất nghĩa.
        problems.append(f"{slot.id}: hai người nói dùng chung một giọng")
    unknown = [voice for voice in slot.voices if voice not in LOGICAL_VOICE_ACCENTS]
    if unknown:
        problems.append(f"{slot.id}: giọng không có trong danh sách: {', '.join(unknown)}")
    return problems


def build_part4(slug: str, title: str, seed: int) -> Blueprint:
    """Mười bài nói Part 4, câu 71–100 của đề thật."""
    slots = [
        QuestionSlot(
            id=f"p4-{index + 1:02d}",
            number=71 + index * 3,
            question_type="",
            grammar="",
            context=scene,
            question_types=list(types),
            topic=speech_type,
            voices=[PART4_VOICES[(index + seed) % len(PART4_VOICES)]],
            graphic=graphic,
        )
        for index, (speech_type, scene, types, graphic) in enumerate(PART4_MIX)
    ]
    return Blueprint(slug=slug, title=title, seed=seed, parts=[PartPlan(part=4, slots=slots)])


def validate(blueprint: Blueprint) -> list[str]:
    """Những gì sai TRONG blueprint, trước khi nó tốn một lượt gọi nào.

    Kiểm mã nhãn ở đây chứ không đợi `enrich_skills`: một mã sai chỉ lộ ra sau
    khi đã sinh xong 30 câu, và lúc đó thứ phải sửa là 30 tệp chứ không phải một
    dòng JSON.
    """
    problems: list[str] = []
    for part in blueprint.parts:
        valid_types = {label.code for label in codes_for("question_type", part.part)}
        valid_grammar = {label.code for label in codes_for("grammar", part.part)}
        numbers: set[int] = set()
        for slot in part.slots:
            # Ô CỤM để `question_type` rỗng — ba nhãn của nó nằm ở
            # `question_types` và được kiểm riêng bên dưới.
            if part.part not in (3, 4) and slot.question_type not in valid_types:
                problems.append(
                    f"{slot.id}: `{slot.question_type}` không phải nhãn của part {part.part}"
                )
            if slot.grammar and slot.grammar not in valid_grammar:
                problems.append(
                    f"{slot.id}: `{slot.grammar}` không phải điểm ngữ pháp của part {part.part}"
                )
            if part.part in (1, 2) and not slot.voice:
                problems.append(f"{slot.id}: phần nghe cần một giọng đọc")
            if part.part in (3, 4):
                problems.extend(_set_slot_problems(slot, part.part, valid_types))
            if part.part == 1 and slot.people not in PEOPLE_SHAPES:
                problems.append(
                    f"{slot.id}: `people` phải là một trong {PEOPLE_SHAPES}, đang là "
                    f"{slot.people!r}"
                )
            if slot.number in numbers:
                problems.append(f"{slot.id}: số câu {slot.number} bị trùng")
            numbers.add(slot.number)

        # Ràng buộc ở tầng ĐỀ, không tầng câu. Sáu tấm ảnh cùng một dạng qua sạch
        # mọi phép kiểm từng câu — và người học chỉ phát hiện ra là mình chưa gặp
        # dạng tranh không có người vào lúc ngồi trong phòng thi.
        if part.part == 1:
            missing = [
                shape for shape in PEOPLE_SHAPES if shape not in {s.people for s in part.slots}
            ]
            if missing:
                problems.append(
                    f"part 1 thiếu dạng tranh: {', '.join(missing)} — "
                    f"một đề phải có đủ tranh một người, nhiều người và không người"
                )
    return problems


def merge(existing: Blueprint | None, fresh: Blueprint) -> Blueprint:
    """Ghép kế hoạch của một part vào blueprint đã có, THAY part cùng số.

    Một đề có bảy part và được dựng từng part một, nên `plan` phải cộng dồn.
    Ghi đè cả tệp thì lập kế hoạch Part 1 xoá mất kế hoạch Part 5 — và các tệp
    dán của Part 5 vẫn nằm nguyên trên đĩa, nên không có gì báo cho tới lúc
    `check` nói "0 ô" về một part đã viết xong.
    """
    if existing is None:
        return fresh
    numbers = {plan.part for plan in fresh.parts}
    kept = [plan for plan in existing.parts if plan.part not in numbers]
    return Blueprint(
        slug=fresh.slug,
        title=fresh.title,
        seed=fresh.seed,
        parts=sorted(kept + list(fresh.parts), key=lambda plan: plan.part),
    )


def save(blueprint: Blueprint, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(blueprint), ensure_ascii=False, indent=2) + "\n")


def load(path: Path) -> Blueprint:
    raw = json.loads(path.read_text())
    return Blueprint(
        slug=raw["slug"],
        title=raw["title"],
        seed=raw["seed"],
        parts=[
            PartPlan(part=part["part"], slots=[QuestionSlot(**slot) for slot in part["slots"]])
            for part in raw["parts"]
        ],
    )
