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
            if slot.question_type not in valid_types:
                problems.append(
                    f"{slot.id}: `{slot.question_type}` không phải nhãn của part {part.part}"
                )
            if slot.grammar and slot.grammar not in valid_grammar:
                problems.append(
                    f"{slot.id}: `{slot.grammar}` không phải điểm ngữ pháp của part {part.part}"
                )
            if part.part in (1, 2, 3, 4) and not slot.voice:
                problems.append(f"{slot.id}: phần nghe cần một giọng đọc")
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
