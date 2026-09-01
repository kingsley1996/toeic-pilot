"""Hình dạng của một đề: dạng câu nào, bối cảnh nào, cảnh nào, ai nói.

Tách khỏi `blueprint.py` vì đây là **nội dung người ra đề chỉnh**, còn bên kia là
**mã dựng và kiểm đề**. Để chung thì sửa một bối cảnh công sở phải mở cùng tệp
với thuật toán rải giọng, và ngược lại — `REFACTOR-LONG-FILES.md` §3.

Ranh giới đặt ở "ai chỉnh", không ở "có phải hằng số không": `PEOPLE_SHAPES`,
`QUESTIONS_PER_SET` và `GRAPHIC_POSITION` ở lại `blueprint.py`, vì chúng là
những điều BẤT BIẾN của định dạng đề mà `validate` cưỡng chế, không phải lựa
chọn ai đó chỉnh cho một đề khác đi.
"""

from app.core.media import TOEIC_NARRATORS

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


# --- Chọn giọng -----------------------------------------------------------
#
# Đề thật có bốn narrator, giới tính gắn cứng vào quốc tịch (`TOEIC_NARRATORS`),
# nên một hội thoại hai người — một nam một nữ — LUÔN là hai quốc tịch khác
# nhau. Lý do đầy đủ ở PHASE2-AUDIO §A4.6.
NARRATOR_WOMEN = (TOEIC_NARRATORS["en-US"], TOEIC_NARRATORS["en-GB"])


NARRATOR_MEN = (TOEIC_NARRATORS["en-CA"], TOEIC_NARRATORS["en-AU"])


NARRATORS = (*NARRATOR_WOMEN, *NARRATOR_MEN)


# Part 2: người hỏi và người đáp, khác giới nên khác quốc tịch. Cả hai chiều —
# người hỏi là nữ ở tám cặp đầu, là nam ở tám cặp sau.
PART2_PAIRS: tuple[tuple[str, str], ...] = tuple(
    [(woman, man) for woman in NARRATOR_WOMEN for man in NARRATOR_MEN]
    + [(man, woman) for woman in NARRATOR_WOMEN for man in NARRATOR_MEN]
)


# Part 3, hội thoại hai người: một nữ một nam.
PART3_CASTS: tuple[tuple[str, ...], ...] = tuple(
    (woman, man) for woman in NARRATOR_WOMEN for man in NARRATOR_MEN
)


# Part 3, hội thoại ba người: hai nữ một nam, hoặc một nữ hai nam.
PART3_TRIOS: tuple[tuple[str, ...], ...] = tuple(
    [(*NARRATOR_WOMEN, man) for man in NARRATOR_MEN]
    + [(woman, *NARRATOR_MEN) for woman in NARRATOR_WOMEN]
)


# Phân bố của một đề thật: phần lớn có người, và đúng một tấm tả vật hoặc cảnh.
# 18 mẫu — nhiều hơn 6 câu của một đề, để `build_part1` shuffle và lấy 6 theo
# seed: hai đề khác seed thì Part 1 khác nhau, không lặp lại đúng bộ ảnh cũ.
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
    ("PART_1_PERSON_DESCRIPTION", "one", "một đầu bếp đang trang trí một món ăn"),
    (
        "PART_1_PERSON_AND_OBJECT_DESCRIPTION",
        "several",
        "hai công nhân lắp ráp một món đồ nội thất trong cửa hàng",
    ),
    ("PART_1_PERSON_DESCRIPTION", "one", "một người phụ nữ đang xách vali bước qua sảnh"),
    (
        "PART_1_PERSON_AND_OBJECT_DESCRIPTION",
        "several",
        "một nhóm hành khách xếp hàng trước quầy làm thủ tục ở sân bay",
    ),
    (
        "PART_1_OBJECT_OR_SCENE_DESCRIPTION",
        "none",
        "một thư viện yên tĩnh với các kệ sách và bàn đọc",
    ),
    ("PART_1_PERSON_DESCRIPTION", "one", "một người đàn ông đang lau cửa kính toà nhà"),
    (
        "PART_1_PERSON_AND_OBJECT_DESCRIPTION",
        "several",
        "hai nhân viên lễ tân đang trò chuyện cạnh bàn lễ tân",
    ),
    (
        "PART_1_OBJECT_OR_SCENE_DESCRIPTION",
        "none",
        "một quán cà phê vắng khách với những chiếc bàn và ghế gỗ",
    ),
    (
        "PART_1_PERSON_DESCRIPTION",
        "one",
        "một người thợ sửa chữa đang kiểm tra ống nước dưới bồn rửa",
    ),
    (
        "PART_1_PERSON_AND_OBJECT_DESCRIPTION",
        "several",
        "một nhóm sinh viên đang đứng quanh một bảng thông báo",
    ),
    ("PART_1_PERSON_DESCRIPTION", "one", "một người giao hàng đang ôm một thùng các-tông"),
    (
        "PART_1_OBJECT_OR_SCENE_DESCRIPTION",
        "none",
        "một bãi đỗ xe trống với vài chiếc xe đậu rải rác",
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


# Brief hình cho BA cụm cuối Part 3. Mỗi mục một brief `kind: mô tả` — model hay
# chọn, và `build_part3` chọn theo seed khi không dùng model. Đủ nhiều để hai đề
# khác seed có bộ hình khác nhau; `graphics.py` là nơi quyết định kind nào vẽ được.
PART3_GRAPHIC_POOL: tuple[str, ...] = (
    "table: bảng giá bốn gói dịch vụ tổ chức sự kiện, cột Package và Price",
    "schedule: lịch rảnh/bận của hai người qua bốn khung giờ trong ngày",
    "map: sơ đồ khu kho gồm bốn nhà kho xếp thành hai hàng",
    "chart: biểu đồ cột doanh số bốn quý, nhãn là tên quý",
    "survey: phiếu khảo sát bốn mục mức độ hài lòng đã đánh dấu",
    "form: phiếu đặt phòng họp bốn suất đã điền",
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


# Brief hình cho HAI cụm cuối Part 4 (câu 96 và 99). Cùng luật với pool Part 3.
PART4_GRAPHIC_POOL: tuple[str, ...] = (
    "chart: biểu đồ cột doanh số bốn quý, nhãn là tên quý",
    "map: sơ đồ tầng trệt gồm bốn quầy xếp thành hai hàng",
    "table: bảng giá bốn gói hội viên, cột Gói và Phí",
    # Trục của `schedule` là columns[1:], nên bảng hai cột cho trục MỘT mục
    # trong khi câu hỏi cần bốn — bản cũ ("cột Ngày và Giờ") không ô nào viết nổi.
    "schedule: lịch bảo trì ba thiết bị qua bốn ngày, cột đầu là tên thiết bị, "
    'bốn cột "Monday", "Tuesday", "Wednesday", "Thursday"',
    "survey: phiếu khảo sát bốn câu hỏi về dịch vụ đã đánh dấu",
    "form: phiếu đăng ký bốn buổi đào tạo đã điền",
)


# Part 2: hai mươi lăm câu hỏi–đáp, câu 7 tới 31 của đề thật.
#
# Không in gì cả, và chỉ có **ba** lựa chọn — hai điều đó chi phối mọi chặng sau.
# Trọng số theo tỉ lệ thường thấy: câu hỏi WH chiếm phần lớn, câu đuôi và câu
# lựa chọn ít hơn, và luôn có vài câu trần thuật (thứ người học hay trượt nhất
# vì không có từ để hỏi mà bám vào).
PART2_MIX: tuple[tuple[str, int], ...] = (
    ("PART_2_WHERE_QUESTION", 3),
    ("PART_2_WHEN_QUESTION", 3),
    ("PART_2_HOW_QUESTION", 3),
    ("PART_2_YES_NO_QUESTION", 3),
    ("PART_2_REQUEST_OR_SUGGESTION", 3),
    ("PART_2_WHO_QUESTION", 2),
    ("PART_2_WHY_QUESTION", 2),
    ("PART_2_TAG_QUESTION", 2),
    ("PART_2_CHOICE_QUESTION", 2),
    ("PART_2_STATEMENT", 2),
)


# Part 6: bốn văn bản, mỗi văn bản bốn chỗ trống — câu 131 tới 146.
#
# **Câu CUỐI của mỗi văn bản là câu ĐIỀN CÂU**, bốn lựa chọn là bốn câu hoàn
# chỉnh chứ không phải bốn từ (câu 134 của đề mẫu). Vị trí cố định, đúng như câu
# hỏi về hình của Part 3/4 — và cùng lý do phải ghi thành ràng buộc: mô hình để
# tự do sẽ rải nó lung tung hoặc bỏ hẳn, và mỗi câu riêng lẻ vẫn hợp lệ.
#
# Part 6 chỉ kiểm **năm** điểm ngữ pháp, không phải mười một như Part 5 — hai
# danh sách khác nhau trong `labels.py`, và dùng nhầm là một mã hợp lệ nhưng sai
# part.
PART6_MIX: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "PART_6_EMAIL_OR_LETTER",
        "thư báo khách hàng về vé xem biểu diễn cả mùa vừa mua",
        (
            ("PART_6_GRAMMAR", "GRAMMAR_TENSE"),
            ("PART_6_VOCABULARY", ""),
            ("PART_6_GRAMMAR", "GRAMMAR_PRONOUN"),
            ("PART_6_SENTENCE_INSERTION", ""),
        ),
    ),
    (
        "PART_6_EMAIL_OR_LETTER",
        "email trả lời khách hỏi về dịch vụ bảo trì thiết bị văn phòng",
        (
            ("PART_6_VOCABULARY", ""),
            ("PART_6_GRAMMAR", "GRAMMAR_PREPOSITION"),
            ("PART_6_GRAMMAR", "GRAMMAR_VOICE"),
            ("PART_6_SENTENCE_INSERTION", ""),
        ),
    ),
    (
        "PART_6_MEMO",
        "thông báo nội bộ về việc chuyển sang hệ thống chấm công mới",
        (
            ("PART_6_GRAMMAR", "GRAMMAR_TO_INFINITIVE"),
            ("PART_6_VOCABULARY", ""),
            ("PART_6_GRAMMAR", "GRAMMAR_TENSE"),
            ("PART_6_SENTENCE_INSERTION", ""),
        ),
    ),
    (
        "PART_6_ARTICLE_OR_REVIEW",
        "bài báo ngắn về một chuỗi cửa hàng vừa mở chi nhánh mới",
        (
            ("PART_6_VOCABULARY", ""),
            ("PART_6_GRAMMAR", "GRAMMAR_PRONOUN"),
            ("PART_6_SENTENCE_INSERTION", ""),
            ("PART_6_GRAMMAR", "GRAMMAR_VOICE"),
        ),
    ),
)


# Part 7: mười chín cụm, câu 147 tới 200. Ba nhóm, và số câu mỗi cụm KHÁC nhau —
# 2 tới 5 — nên số câu nằm ở chính cái ô chứ không tra theo part.
#
# Mỗi mục: (dạng ngữ liệu, bối cảnh, các dạng câu hỏi, các ngữ liệu).
# "Các ngữ liệu" là danh sách song song với số đoạn: chuỗi rỗng nghĩa là đoạn
# CHỮ, còn `kind: mô tả` nghĩa là đoạn đó được VẼ từ dữ liệu (§28).
PART7_SETS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    # --- mười cụm một ngữ liệu, câu 147–175
    (
        "PART_7_TEXT_MESSAGE_CHAIN",
        "hai đồng nghiệp nhắn tin về việc đổi vé máy bay",
        ("PART_7_INFORMATION_RETRIEVAL", "PART_7_IMPLICATION"),
        ("",),
    ),
    (
        "PART_7_ADVERTISEMENT",
        "quảng cáo dịch vụ dọn văn phòng theo tháng",
        ("PART_7_TOPIC_OR_PURPOSE", "PART_7_INFORMATION_RETRIEVAL"),
        ("",),
    ),
    (
        "PART_7_ANNOUNCEMENT_OR_NOTICE",
        "thông báo đóng bãi xe để sửa chữa",
        ("PART_7_TOPIC_OR_PURPOSE", "PART_7_INFERENCE"),
        ("",),
    ),
    (
        "PART_7_ADVERTISEMENT",
        "quảng cáo tuyển dụng vị trí điều phối kho",
        ("PART_7_INFORMATION_RETRIEVAL", "PART_7_FALSE_INFORMATION", "PART_7_INFERENCE"),
        ("",),
    ),
    (
        "PART_7_EMAIL_OR_LETTER",
        "thư cảm ơn khách hàng lâu năm kèm ưu đãi",
        ("PART_7_TOPIC_OR_PURPOSE", "PART_7_INFORMATION_RETRIEVAL"),
        ("",),
    ),
    (
        "PART_7_ARTICLE_OR_REVIEW",
        "bài đánh giá một quán ăn mới mở gần khu văn phòng",
        ("PART_7_TOPIC_OR_PURPOSE", "PART_7_INFERENCE", "PART_7_INFORMATION_RETRIEVAL"),
        ("",),
    ),
    (
        "PART_7_ARTICLE_OR_REVIEW",
        "bài báo ngắn về việc một công ty mở rộng nhà máy",
        ("PART_7_INFORMATION_RETRIEVAL", "PART_7_INFERENCE", "PART_7_VOCABULARY_IN_CONTEXT"),
        ("",),
    ),
    (
        "PART_7_EMAIL_OR_LETTER",
        "email trả lời khách về đơn hàng bị thiếu hoá đơn",
        (
            "PART_7_TOPIC_OR_PURPOSE",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_INFERENCE",
            "PART_7_SENTENCE_INSERTION",
        ),
        ("",),
    ),
    (
        "PART_7_ARTICLE_OR_REVIEW",
        "bài báo về một hội chợ việc làm sắp tổ chức",
        (
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_INFERENCE",
            "PART_7_FALSE_INFORMATION",
            "PART_7_SENTENCE_INSERTION",
        ),
        ("",),
    ),
    (
        "PART_7_TEXT_MESSAGE_CHAIN",
        "ba người trao đổi nhóm về việc đặt phòng họp",
        (
            "PART_7_TOPIC_OR_PURPOSE",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_IMPLICATION",
            "PART_7_INFERENCE",
        ),
        ("",),
    ),
    # --- hai cụm hai ngữ liệu, câu 176–185
    (
        "PART_7_EMAIL_OR_LETTER",
        "email đặt chỗ hội thảo và lịch các phiên",
        (
            "PART_7_TOPIC_OR_PURPOSE",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_INFERENCE",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_VOCABULARY_IN_CONTEXT",
        ),
        ("", "schedule: lịch bốn phiên hội thảo trong ngày"),
    ),
    (
        "PART_7_ANNOUNCEMENT_OR_NOTICE",
        "thông cáo ra mắt sản phẩm và thư phản hồi của đại lý",
        (
            "PART_7_TOPIC_OR_PURPOSE",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_INFERENCE",
            "PART_7_FALSE_INFORMATION",
            "PART_7_INFERENCE",
        ),
        ("", ""),
    ),
    # --- ba cụm ba ngữ liệu, câu 186–200
    (
        "PART_7_FORM",
        "email xác nhận đặt phòng, thư phàn nàn, và phiếu khảo sát đã điền",
        (
            "PART_7_TOPIC_OR_PURPOSE",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_FALSE_INFORMATION",
            "PART_7_INFERENCE",
            "PART_7_INFERENCE",
        ),
        ("", "", "survey: phiếu khảo sát bốn mục đã đánh dấu"),
    ),
    (
        "PART_7_SCHEDULE",
        "thông báo nội bộ, email hỏi lại, và lịch buổi đào tạo",
        (
            "PART_7_TOPIC_OR_PURPOSE",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_INFERENCE",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_VOCABULARY_IN_CONTEXT",
        ),
        ("", "", "schedule: lịch bốn buổi đào tạo trong tháng"),
    ),
    (
        "PART_7_FORM",
        "thư mời hội viên, bảng giá vé, và phiếu đặt vé đã điền",
        (
            "PART_7_INFERENCE",
            "PART_7_FALSE_INFORMATION",
            "PART_7_VOCABULARY_IN_CONTEXT",
            "PART_7_INFORMATION_RETRIEVAL",
            "PART_7_INFORMATION_RETRIEVAL",
        ),
        ("", "table: bảng giá vé bốn suất diễn", "form: phiếu đặt vé đã điền"),
    ),
)


# Brief hình cho các PASSAGE HÌNH Part 7. Năm passage hình rải trong bốn cụm:
# p7-11 (1), p7-13 (1), p7-14 (1), p7-15 (2). Pool đủ nhiều để `sample` chọn 5
# mục không trùng.
# Nhãn ghi bằng TIẾNG ANH vì chúng được in thẳng lên hình người thi đọc; phần
# mô tả quanh chúng là ghi chú nội bộ nên vẫn tiếng Việt. Khác pool Part 3/4 ở
# chỗ KHÔNG cần nêu trục đáp án: hình Part 7 là NGỮ LIỆU, câu hỏi hỏi về nội
# dung chứ không bắt chọn giữa bốn hàng (§28).
PART7_GRAPHIC_POOL: tuple[str, ...] = (
    'schedule: lịch bốn phiên hội thảo trong ngày, cột "Session", "Time", "Room"',
    'survey: phiếu khảo sát dịch vụ, cột "Aspect", "Rating", "Comment"',
    'schedule: lịch bốn buổi đào tạo trong tháng, cột "Course", "Date", "Trainer"',
    'table: bảng giá vé bốn suất diễn, cột "Performance", "Time", "Price"',
    'form: phiếu đặt vé đã điền, các mục "Passenger", "Route", "Date", "Seat"',
    'chart: biểu đồ cột kết quả khảo sát bốn quý, nhãn "Q1", "Q2", "Q3", "Q4"',
    'schedule: lịch hẹn bốn khách hàng trong tuần, cột "Client", "Day", "Time"',
    'table: bảng giá bốn gói phần mềm, cột "Plan" và "Fee"',
    'map: sơ đồ bốn khu vực hội chợ, mỗi ô "Zone A".."Zone D" kèm tên gian hàng',
    'form: phiếu đăng ký hội thảo đã điền, các mục "Name", "Company", "Session", "Meal"',
)
