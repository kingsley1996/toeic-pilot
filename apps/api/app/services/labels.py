"""Bộ nhãn câu hỏi TOEIC — sinh từ `planning/toeic_question_label_taxonomy.md`.

**Không sửa tay tệp này.** Nguồn sự thật là tài liệu markdown; `tests/test_labels.py`
đọc lại tài liệu đó và so với đây, nên hai bên lệch nhau là một bài test đỏ chứ
không phải một khám phá sáu tuần sau.

Bảy mặt phân loại, và mỗi câu mang **đúng một nhãn mỗi mặt** — ràng buộc đó nằm ở
khoá chính của bảng nhãn, không nằm ở quy ước.

Bốn mặt mô tả NGỮ LIỆU DÙNG CHUNG chứ không mô tả từng câu (`owner="set"`): ba câu
của cùng một hội thoại Part 3 luôn cùng Topic, vì đó là thuộc tính của đoạn hội
thoại. Treo chúng trên câu thì schema CHO PHÉP ba câu mang ba topic khác nhau và
không gì báo lỗi — cùng lý do ADR-001 §A4.3 treo audio Part 3/4 ở `question_set`.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FACETS", "LABELS", "Facet", "Label", "codes_for", "facets_for", "is_valid"]


@dataclass(frozen=True, slots=True)
class Label:
    code: str
    label_vi: str
    parts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Facet:
    key: str
    label_vi: str
    # "question" hoặc "set" — quyết định nhãn treo ở bảng nào.
    owner: str
    labels: tuple[Label, ...]


FACETS: tuple[Facet, ...] = (
    Facet(
        key="question_type",
        label_vi="Dạng câu hỏi",
        owner="question",
        labels=(
            Label("PART_1_PERSON_DESCRIPTION", "Tranh tả người", (1,)),
            Label("PART_1_PERSON_AND_OBJECT_DESCRIPTION", "Tranh tả cả người và vật", (1,)),
            Label("PART_2_WHO_QUESTION", "Câu hỏi WHO", (2,)),
            Label("PART_2_WHERE_QUESTION", "Câu hỏi WHERE", (2,)),
            Label("PART_2_WHEN_QUESTION", "Câu hỏi WHEN", (2,)),
            Label("PART_2_HOW_QUESTION", "Câu hỏi HOW", (2,)),
            Label("PART_2_WHY_QUESTION", "Câu hỏi WHY", (2,)),
            Label("PART_2_YES_NO_QUESTION", "Câu hỏi YES/NO", (2,)),
            Label("PART_2_TAG_QUESTION", "Câu hỏi đuôi", (2,)),
            Label("PART_2_CHOICE_QUESTION", "Câu hỏi lựa chọn", (2,)),
            Label("PART_2_REQUEST_OR_SUGGESTION", "Câu yêu cầu, đề nghị", (2,)),
            Label("PART_2_STATEMENT", "Câu trần thuật", (2,)),
            Label("PART_3_TOPIC_OR_PURPOSE", "Câu hỏi về chủ đề, mục đích", (3,)),
            Label("PART_3_SPEAKER_IDENTITY", "Câu hỏi về danh tính người nói", (3,)),
            Label("PART_3_CONVERSATION_DETAIL", "Câu hỏi về chi tiết cuộc hội thoại", (3,)),
            Label("PART_3_FUTURE_ACTION", "Câu hỏi về hành động tương lai", (3,)),
            Label("PART_3_GRAPH_OR_TABLE_QUESTION", "Câu hỏi kết hợp bảng biểu", (3,)),
            Label("PART_3_LOCATION", "Câu hỏi về địa điểm hội thoại", (3,)),
            Label("PART_3_REQUEST_OR_SUGGESTION", "Câu hỏi về yêu cầu, gợi ý", (3,)),
            Label("PART_4_TOPIC_OR_PURPOSE", "Câu hỏi về chủ đề, mục đích", (4,)),
            Label("PART_4_SPEAKER_OR_LOCATION", "Câu hỏi về danh tính, địa điểm", (4,)),
            Label("PART_4_DETAIL", "Câu hỏi về chi tiết", (4,)),
            Label("PART_4_FUTURE_ACTION", "Câu hỏi về hành động tương lai", (4,)),
            Label("PART_4_GRAPH_OR_TABLE_QUESTION", "Câu hỏi kết hợp bảng biểu", (4,)),
            Label("PART_4_IMPLICATION", "Câu hỏi về hàm ý câu nói", (4,)),
            Label("PART_4_REQUEST_OR_SUGGESTION", "Câu hỏi yêu cầu, gợi ý", (4,)),
            Label("PART_5_PART_OF_SPEECH", "Câu hỏi từ loại", (5,)),
            Label("PART_5_GRAMMAR", "Câu hỏi ngữ pháp", (5,)),
            Label("PART_5_VOCABULARY", "Câu hỏi từ vựng", (5,)),
            Label("PART_6_GRAMMAR", "Câu hỏi ngữ pháp", (6,)),
            Label("PART_6_VOCABULARY", "Câu hỏi từ vựng", (6,)),
            Label("PART_6_SENTENCE_INSERTION", "Câu hỏi điền câu vào đoạn văn", (6,)),
            Label("PART_7_INFORMATION_RETRIEVAL", "Câu hỏi tìm thông tin", (7,)),
            Label("PART_7_FALSE_INFORMATION", "Câu hỏi tìm chi tiết sai", (7,)),
            Label("PART_7_TOPIC_OR_PURPOSE", "Câu hỏi về chủ đề, mục đích", (7,)),
            Label("PART_7_INFERENCE", "Câu hỏi suy luận", (7,)),
            Label("PART_7_SENTENCE_INSERTION", "Câu hỏi điền câu", (7,)),
            Label(
                "PART_7_VOCABULARY_IN_CONTEXT",
                "Câu hỏi tìm từ đồng nghĩa / từ vựng trong ngữ cảnh",
                (7,),
            ),
            Label("PART_7_IMPLICATION", "Câu hỏi về hàm ý câu nói", (7,)),
        ),
    ),
    Facet(
        key="topic",
        label_vi="Chủ đề",
        owner="set",
        labels=(
            Label("PART_3_COMPANY_PERSONNEL", "Chủ đề: Company - Personnel", (3,)),
            Label("PART_3_COMPANY_EVENT_OR_PROJECT", "Chủ đề: Company - Event, Project", (3,)),
            Label("PART_3_SHOPPING_OR_SERVICE", "Chủ đề: Shopping, Service", (3,)),
            Label("PART_3_HOUSING", "Chủ đề: Housing", (3,)),
        ),
    ),
    Facet(
        key="speech_type",
        label_vi="Dạng bài nói",
        owner="set",
        labels=(
            Label("PART_4_TELEPHONE_MESSAGE", "Dạng bài: Telephone message - Tin nhắn thoại", (4,)),
            Label("PART_4_ADVERTISEMENT", "Dạng bài: Advertisement - Quảng cáo", (4,)),
            Label("PART_4_ANNOUNCEMENT", "Dạng bài: Announcement - Thông báo", (4,)),
            Label("PART_4_TALK", "Dạng bài: Talk - Bài phát biểu, diễn văn", (4,)),
            Label(
                "PART_4_MEETING_EXCERPT",
                "Dạng bài: Excerpt from a meeting - Trích dẫn từ buổi họp",
                (4,),
            ),
        ),
    ),
    Facet(
        key="grammar",
        label_vi="Điểm ngữ pháp",
        owner="question",
        labels=(
            Label("GRAMMAR_NOUN", "Danh từ", (5,)),
            Label("GRAMMAR_PRONOUN", "Đại từ", (5, 6)),
            Label("GRAMMAR_ADJECTIVE", "Tính từ", (5,)),
            Label("GRAMMAR_TENSE", "Thì", (5, 6)),
            Label("GRAMMAR_VOICE", "Thể", (5, 6)),
            Label("GRAMMAR_ADVERB", "Trạng từ", (5,)),
            Label("GRAMMAR_PARTICIPLE", "Phân từ và cấu trúc phân từ", (5,)),
            Label("GRAMMAR_PREPOSITION", "Giới từ", (5, 6)),
            Label("GRAMMAR_CONJUNCTION", "Liên từ", (5,)),
            Label("GRAMMAR_RELATIVE_CLAUSE", "Mệnh đề quan hệ", (5,)),
            Label("GRAMMAR_COMPARISON", "Cấu trúc so sánh", (5,)),
            Label("GRAMMAR_TO_INFINITIVE", "Động từ nguyên mẫu có to", (6,)),
        ),
    ),
    Facet(
        key="passage_type",
        label_vi="Dạng văn bản",
        owner="set",
        labels=(
            Label(
                "PART_6_EMAIL_OR_LETTER", "Hình thức: Thư điện tử / thư tay (Email / Letter)", (6,)
            ),
            Label("PART_6_ARTICLE_OR_REVIEW", "Hình thức: Bài báo (Article / Review)", (6,)),
            Label("PART_6_MEMO", "Hình thức: Thông báo nội bộ (Memo)", (6,)),
            Label(
                "PART_7_EMAIL_OR_LETTER", "Dạng bài: Email / Letter - Thư điện tử / Thư tay", (7,)
            ),
            Label("PART_7_FORM", "Dạng bài: Form - Đơn từ, biểu mẫu", (7,)),
            Label(
                "PART_7_ARTICLE_OR_REVIEW",
                "Dạng bài: Article / Review - Bài báo / Bài đánh giá",
                (7,),
            ),
            Label("PART_7_ADVERTISEMENT", "Dạng bài: Advertisement - Quảng cáo", (7,)),
            Label(
                "PART_7_ANNOUNCEMENT_OR_NOTICE", "Dạng bài: Announcement / Notice - Thông báo", (7,)
            ),
            Label(
                "PART_7_TEXT_MESSAGE_CHAIN", "Dạng bài: Text message chain - Chuỗi tin nhắn", (7,)
            ),
            Label("PART_7_SCHEDULE", "Dạng bài: Schedule - Lịch trình, thời gian biểu", (7,)),
        ),
    ),
    Facet(
        key="passage_structure",
        label_vi="Cấu trúc đoạn",
        owner="set",
        labels=(
            Label("PART_7_SINGLE_PASSAGE", "Cấu trúc: một đoạn", (7,)),
            Label("PART_7_MULTIPLE_PASSAGE", "Cấu trúc: nhiều đoạn", (7,)),
        ),
    ),
)

LABELS: dict[str, Label] = {label.code: label for facet in FACETS for label in facet.labels}


def is_valid(code: str) -> bool:
    return code in LABELS


def facets_for(part: int, owner: str) -> list[Facet]:
    """Các mặt phân loại áp dụng cho một part, ở một tầng sở hữu.

    Thu hẹp theo part ngay từ đây thay vì bác sau: một câu Part 5 không có mặt
    `topic`, và đưa mặt đó ra trước mặt người duyệt lẫn model chỉ tạo cơ hội sai.
    """
    return [
        facet
        for facet in FACETS
        if facet.owner == owner and any(part in label.parts for label in facet.labels)
    ]


def codes_for(facet_key: str, part: int) -> list[Label]:
    """Nhãn hợp lệ của một mặt, với một part cụ thể.

    `GRAMMAR_*` dùng chung giữa Part 5 và 6 nhưng KHÔNG trùng danh sách: Part 6
    chỉ có năm điểm ngữ pháp, Part 5 có mười một. Lọc theo part là thứ giữ đúng
    khác biệt đó.
    """
    for facet in FACETS:
        if facet.key == facet_key:
            return [label for label in facet.labels if part in label.parts]
    return []
