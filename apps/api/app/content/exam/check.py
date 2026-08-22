"""Chặng kiểm: chạy TRƯỚC khi tốn một giây audio hay một tấm ảnh nào.

Ba tầng, và tầng đầu là tầng quan trọng nhất về mặt kiến trúc.

**Tầng cú pháp gọi thẳng parser thật**, không viết bản kiểm riêng. Một bản kiểm
riêng sẽ trôi khỏi parser, và ngày nó trôi thì pipeline báo "hợp lệ" cho đúng
thứ mà `POST /parts/parse` sẽ từ chối — người chạy nhận được hai câu trả lời trái
ngược từ hai chỗ, và không chỗ nào sai rõ ràng.

**Tầng ngữ nghĩa** bắt những gì parser không thể biết: đáp án có thật sự đúng
không, nhiễu có sai một cách hợp lý không, 30 câu có lặp lại nhau không.

**Tầng đối chiếu đáp án dùng một lượt gọi KHÁC, với bốn lựa chọn đã xáo thứ tự.**
Không xáo thì mô hình có xu hướng chọn lại đúng vị trí nó vừa đặt đáp án, và phép
kiểm thành một nghi thức luôn xanh.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app.content.exam.blueprint import Blueprint, QuestionSlot
from app.content.exam.writer import RETRY_DELAY, RETRY_TRIES, paste_path
from app.services.content_import import (
    ParsedOption,
    ParsedQuestion,
    parse_listening_part,
    parse_reading_part,
)
from app.services.llm.base import LLMQuotaExhausted, LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier

# Đáp án dài hơn hẳn phần còn lại là một manh mối rò rỉ: người làm bài đoán được
# mà không cần đọc câu. Ngưỡng đặt theo tỉ lệ chứ không theo số ký tự tuyệt đối,
# vì một câu từ vựng và một câu chia động từ có độ dài rất khác nhau.
LENGTH_TELL_RATIO = 1.8
# …nhưng chỉ khi lựa chọn dài nhất đủ dài để tỉ lệ có nghĩa. Câu ngữ pháp có
# lựa chọn là những từ hai ba chữ cái (`by` / `until`), và ở cỡ đó "dài gấp đôi"
# là sáu ký tự so với ba — không ai đoán được đáp án từ chuyện đó. Đo được: hai
# cờ đầu tiên của lượt chạy thật đều thuộc loại này, tức là ngưỡng tỉ lệ đơn
# thuần sinh ra báo động giả nhanh hơn sinh ra tín hiệu.
LENGTH_TELL_MIN_CHARS = 12

VERIFY_SYSTEM_PART1 = """Bạn nghe bốn câu mô tả một tấm ảnh TOEIC Part 1. Bạn
được đọc phần mô tả tấm ảnh đó. Chỉ trả về đúng MỘT chữ cái in hoa — câu mô tả
ĐÚNG tấm ảnh: A, B, C hoặc D. Không giải thích, không thêm gì khác."""

AMBIGUITY_SYSTEM_PART1 = """Bạn kiểm một câu hỏi TOEIC Part 1.

Bạn được đọc phần mô tả tấm ảnh và bốn câu mô tả. Trả về chữ cái của MỌI câu
mô tả ĐÚNG tấm ảnh — đúng theo nghĩa kiểm chứng được từ phần mô tả, không phải
"có thể đúng nếu nhìn góc khác".

Chỉ trả về các chữ cái, viết liền, không giải thích. Ví dụ: `B` hoặc `AB`."""

VERIFY_SYSTEM = """Bạn làm một câu hỏi TOEIC Part 5. Chỉ trả về đúng MỘT chữ cái
in hoa: A, B, C hoặc D. Không giải thích, không thêm gì khác."""

AMBIGUITY_SYSTEM = """Bạn kiểm một câu hỏi TOEIC Part 5.

Đọc câu bốn lần, mỗi lần thay một lựa chọn vào chỗ trống -------. Trả về chữ cái
của MỌI lựa chọn mà câu kết quả vừa đúng ngữ pháp vừa tự nhiên với người dùng
tiếng Anh thương mại.

Chỉ trả về các chữ cái, viết liền, không giải thích. Ví dụ: `B` hoặc `AB`."""


@dataclass
class SlotReport:
    slot_id: str
    number: int
    problems: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    # Các chữ cái mà người chấm nói là điền được. Ghi lại cho MỌI câu, kể cả câu
    # đạt: phân bố của cả cột này là thứ duy nhất phát hiện được người chấm đang
    # trả lời phản xạ — nhìn riêng những câu bị cờ thì không thấy gì.
    workable: str | None = None

    @property
    def blocked(self) -> bool:
        """Có `problems` là KHÔNG nạp được; `flags` chỉ là chỗ người cần nhìn."""
        return bool(self.problems)


def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).lower()
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def parse_one(block: str, part: int = 5) -> tuple[ParsedQuestion | None, list[str]]:
    """Đọc một khối bằng parser THẬT. Trả (câu, vấn đề)."""
    try:
        groups = (
            parse_listening_part(block, part)
            if part in (1, 2, 3, 4)
            else parse_reading_part(block, part)
        )
    except ValueError as error:
        return None, [str(error)]
    questions = [question for group in groups for question in group.questions]
    if len(questions) != 1:
        return None, [f"khối phải chứa đúng một câu, đọc được {len(questions)}"]
    question = questions[0]
    return question, list(question.problems)


def option_text(option: ParsedOption) -> str:
    """Chữ của một lựa chọn, dù nó được IN hay được NÓI.

    Part 1 và 2 không in gì, nên `content` là NULL ở đó và chữ nằm ở
    `spoken_text`. Đọc thẳng `content` là mọi phép kiểm ngữ nghĩa của phần Nghe
    so bốn chuỗi rỗng với nhau — và chúng đều "đạt".
    """
    return ((option.content or option.spoken_text) or "").strip()


def check_shape(question: ParsedQuestion, part: int = 5) -> list[str]:
    """Những luật của một part mà parser không tự nói ra."""
    problems: list[str] = []
    if part == 1:
        # Part 1 KHÔNG in gì cả — bốn câu là lời nói, `prompt_text` phải là NULL.
        # Parser đã cưỡng chế điều đó, nên ở đây chỉ còn luật riêng của pipeline:
        # bốn câu nói phải có thật, vì `spoken_text` rỗng thì clip sẽ im lặng và
        # không gì báo cho tới lúc có người bấm play.
        empty = [o.label for o in question.options if not (o.spoken_text or "").strip()]
        if empty:
            problems.append(f"câu nói rỗng ở lựa chọn {', '.join(empty)}")
        if question.source != "original":
            problems.append(f"`Source` phải là `original`, đang là {question.source!r}")
        return problems
    if question.prompt_text and "-------" not in question.prompt_text:
        # Chỗ trống là hình dạng của Part 5. Không có nó thì câu vẫn hợp lệ với
        # parser nhưng không phải một câu Part 5, và cái sai đó chỉ lộ ra khi có
        # người học đọc.
        problems.append("thiếu chỗ trống `-------` trong đề bài")
    if question.source != "original":
        problems.append(f"`Source` phải là `original`, đang là {question.source!r}")
    return problems


def check_options(question: ParsedQuestion) -> list[str]:
    flags: list[str] = []
    contents = [option_text(option) for option in question.options]
    if len(set(_normalise(text) for text in contents)) != len(contents):
        flags.append("có hai lựa chọn trùng nhau sau khi chuẩn hoá")

    lengths = [len(text) for text in contents if text]
    if lengths:
        longest, rest = max(lengths), sorted(lengths)[:-1]
        average = sum(rest) / len(rest) if rest else longest
        if longest >= LENGTH_TELL_MIN_CHARS and average and longest > average * LENGTH_TELL_RATIO:
            flags.append(f"một lựa chọn dài bất thường ({longest} vs trung bình {average:.0f})")
    return flags


def verify_answer(
    gateway: Gateway,
    question: ParsedQuestion,
    tier: Tier,
    seed: int,
    part: int = 5,
    context: str = "",
) -> str | None:
    """Hỏi lại mô hình với bốn lựa chọn ĐÃ XÁO. Trả về cờ nếu lệch, `None` nếu khớp.

    Đây là phép kiểm đắt nhất của chặng này (một lượt gọi mỗi câu) và cũng là
    phép duy nhất chạm tới thứ quan trọng nhất — đáp án có đúng không. Hai mô
    hình cùng dòng vẫn có thể sai giống nhau, nên nó GẮN CỜ cho người xem chứ
    không tự sửa và không tự loại.
    """
    labelled = [(option.label, option_text(option)) for option in question.options]
    truth = next(
        (
            label
            for label, option in zip([o.label for o in question.options], question.options)
            if option.is_correct
        ),
        None,
    )
    if truth is None:
        return "không tìm thấy đáp án đúng để đối chiếu"

    order = list(labelled)
    random.Random(seed).shuffle(order)
    letters = "ABCD"[: len(order)]
    shuffled = "\n".join(f"({letters[i]}) {text}" for i, (_, text) in enumerate(order))
    expected = letters[[label for label, _ in order].index(truth)]

    stem = context.strip() if part == 1 else (question.prompt_text or "")
    # `max_tokens` rộng dù câu trả lời chỉ có một chữ cái: model SUY LUẬN xuất
    # chuỗi suy nghĩ trước, và cắt ở 4 token thì nó trả về rỗng — một lỗi đọc ra
    # như "không trả về chữ cái hợp lệ", tức là đổ lỗi cho câu hỏi thay vì cho
    # giới hạn của chính ta.
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=VERIFY_SYSTEM_PART1 if part == 1 else VERIFY_SYSTEM,
                user=f"{stem}\n{shuffled}",
                max_tokens=1500,
                temperature=0.0,
            ),
            feature="exam_verify",
            tier=tier,
        ),
        tries=RETRY_TRIES,
        delay=RETRY_DELAY,
    )
    picked = result.text.strip().upper()[:1]
    if picked not in letters:
        return f"lượt đối chiếu không trả về chữ cái hợp lệ ({result.text.strip()[:20]!r})"
    if picked != expected:
        original = order[letters.index(picked)][0]
        return f"đối chiếu chọn ({original}), đề ghi đáp án ({truth})"
    return None


def count_workable_options(
    gateway: Gateway,
    question: ParsedQuestion,
    tier: Tier,
    part: int = 5,
    context: str = "",
) -> tuple[int, str]:
    """Hỏi thẳng: có bao nhiêu phương án điền được? Trả (số lượng, các chữ cái).

    Đây là phép kiểm cho ĐÚNG lỗi nội dung trội nhất — câu có hơn một đáp án
    dùng được — và nó là thứ mà mọi phép kiểm khác trong tệp này đều mù: bốn
    phương án đồng nghĩa không trùng chuỗi, không lệch độ dài, và vẫn là bốn
    đáp án đúng.

    Suy gián tiếp từ chuyện người chấm bất đồng thì KHÔNG tách được "đáp án ghi
    sai" với "hai đáp án cùng đúng" — hai lỗi cần hai cách xử lý khác nhau. Hỏi
    thẳng thì tách được.

    Trả về `0` khi không đọc được câu trả lời: một con số không đọc được không
    được phép trở thành "đạt".
    """
    letters = "".join(f"({option.label}) {option_text(option)}\n" for option in question.options)
    stem = context.strip() if part == 1 else (question.prompt_text or "")
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=AMBIGUITY_SYSTEM_PART1 if part == 1 else AMBIGUITY_SYSTEM,
                user=f"{stem}\n{letters}",
                max_tokens=1500,
                temperature=0.0,
            ),
            feature="exam_ambiguity",
            tier=tier,
        ),
        tries=RETRY_TRIES,
        delay=RETRY_DELAY,
    )
    found = "".join(sorted({ch for ch in result.text.upper() if ch in "ABCD"}))
    return len(found), found


def check_blueprint(
    blueprint: Blueprint,
    workdir: Path,
    gateway: Gateway | None = None,
    tier: Tier = Tier.CHEAP,
    ambiguity: bool = False,
    only: int | None = None,
) -> list[SlotReport]:
    """Kiểm mọi ô đã có tệp dán. `gateway=None` thì bỏ mọi tầng cần gọi model.

    `ambiguity=True` bật phép kiểm "có mấy phương án điền được". Nó là phép kiểm
    ĐÚNG lỗi trội nhất, nhưng cũng là phép nhiễu nhất: người chấm yếu sẽ gật đầu
    với những phương án mà người bản ngữ loại ngay. Nên nó ghi thành CỜ chứ không
    chặn nạp, và chỉ lệnh `prune` mới quyết định dựa vào nó.
    """
    reports: list[SlotReport] = []
    seen: dict[str, str] = {}

    slots: list[tuple[int, QuestionSlot]] = [
        (part.part, slot)
        for part in blueprint.parts
        for slot in part.slots
        if only is None or part.part == only
    ]
    for part_number, slot in slots:
        report = SlotReport(slot_id=slot.id, number=slot.number)
        path = paste_path(workdir, slot)
        if not path.exists():
            report.problems.append("chưa có tệp dán")
            reports.append(report)
            continue

        question, problems = parse_one(path.read_text(), part_number)
        # Mô tả ảnh là hiện vật RIÊNG (writer.split_photo), nên chặng kiểm phải
        # đi lấy nó. Không có nó thì mọi phép kiểm ngữ nghĩa của Part 1 đang so
        # bốn câu mô tả với hư không — và chúng đều "đạt".
        context = ""
        if part_number == 1:
            photo = workdir / "photos" / f"{slot.id}.txt"
            if photo.exists():
                context = photo.read_text().strip()
            else:
                # CỜ chứ không chặn: tệp dán vẫn nạp được, mô tả ảnh chỉ phục vụ
                # chặng vẽ. Nhưng nó chặn hai phép kiểm ngữ nghĩa bên dưới —
                # chọn một trong bốn câu mà không biết tấm ảnh có gì thì vẫn trả
                # về một chữ cái, nên phép kiểm sẽ TRÔNG như đang chạy.
                report.flags.append("thiếu mô tả ảnh (`photos/<slot>.txt`) — chưa đối chiếu được")
        report.problems.extend(problems)
        if question is None:
            reports.append(report)
            continue

        report.problems.extend(check_shape(question, part_number))
        report.flags.extend(check_options(question))

        # Part 1 không in đề bài, nên khoá chống trùng phải lấy từ chính bốn câu
        # nói. Lấy `prompt_text` ở đó là mọi ô cùng khoá rỗng, và phép chống
        # trùng tắt lặng lẽ đúng vào part dễ lặp nhất.
        key = _normalise(question.prompt_text or " ".join(option_text(o) for o in question.options))
        if key and key in seen:
            # Trùng câu trong CÙNG một đề. Mô hình lặp lại chính nó nhiều hơn
            # người ta tưởng, và hai câu giống nhau trong một đề là thứ người học
            # nhận ra ngay còn máy thì không.
            report.problems.append(f"đề bài trùng với {seen[key]}")
        elif key:
            seen[key] = slot.id

        blind = part_number == 1 and not context
        if gateway is not None and not blind:
            # Một lượt gọi hỏng KHÔNG được dừng cả chặng kiểm. Chặng này chạy
            # hàng chục phút trên cả đề, và để một lỗi 503 nhất thời vứt hết kết
            # quả của những ô đã kiểm là cách chắc chắn nhất khiến không ai chạy
            # nó. Ghi thành cờ: ô đó "chưa đối chiếu được" — nhìn thấy được, và
            # chạy lại được.
            try:
                flag = verify_answer(
                    gateway, question, tier, blueprint.seed + slot.number, part_number, context
                )
            except LLMQuotaExhausted:
                # Hạn mức NGÀY không tự hết sau vài giây, nên đi tiếp chỉ sinh ra
                # đúng dòng cờ đó cho mọi ô còn lại — và dòng nói đúng nguyên nhân
                # bị chôn dưới ba mươi dòng giống hệt. Dừng hẳn, giữ lại những ô
                # đã kiểm. Cùng cách xử lý mà `write` đã dùng.
                raise
            except Exception as failure:  # noqa: BLE001
                flag = f"không đối chiếu được đáp án: {failure}"
            if flag:
                report.flags.append(flag)
            if ambiguity:
                try:
                    count, found = count_workable_options(
                        gateway, question, tier, part_number, context
                    )
                except LLMQuotaExhausted:
                    raise
                except Exception as failure:  # noqa: BLE001
                    # `count = 1` để phép kiểm này KHÔNG gắn thêm cờ "nhiều phương
                    # án" từ một con số chưa từng được đo. Cờ nói đúng chuyện đã
                    # xảy ra nằm ngay dưới.
                    count, found = 1, None
                    report.flags.append(f"không đếm được phương án điền được: {failure}")
                report.workable = found
                if count != 1:
                    report.flags.append(
                        f"có {count} phương án điền được ({found or 'không đọc được'}) — "
                        f"một câu chỉ được có đúng một"
                    )

        reports.append(report)
    return reports


# Ngưỡng lệch của phân bố đáp án trên cả đề. Đều tuyệt đối là 25%; cho phép trôi
# tới 40% vì 30 câu là mẫu nhỏ, nhưng quá đó thì không còn là ngẫu nhiên.
ANSWER_SKEW_LIMIT = 0.40


def check_answer_spread(reports_dir: Path, blueprint: Blueprint) -> list[str]:
    """Phân bố đáp án trên TOÀN đề — lỗi ở tầng đề, không tầng câu.

    Đo được trên một lượt chạy thật: 29/30 câu có đáp án là (A), tức người chọn
    bừa A được 97%. Mỗi câu riêng lẻ hoàn toàn hợp lệ, nên không phép kiểm từng
    câu nào thấy được — đây là chỗ duy nhất nó lộ ra.
    """
    from app.content.exam.writer import paste_path

    tally: dict[str, int] = {}
    total = 0
    for part in blueprint.parts:
        for slot in part.slots:
            path = paste_path(reports_dir, slot)
            if not path.exists():
                continue
            question, _ = parse_one(path.read_text(), part.part)
            if question is None:
                continue
            correct = next((o.label for o in question.options if o.is_correct), None)
            if correct:
                tally[correct] = tally.get(correct, 0) + 1
                total += 1

    if total < 8:
        # Mẫu quá nhỏ để nói gì về phân bố. Im lặng ở đây đúng hơn là báo động
        # trên bốn câu đầu tiên của một lượt sinh còn dở.
        return []
    problems = []
    for letter, count in sorted(tally.items()):
        if count / total > ANSWER_SKEW_LIMIT:
            problems.append(
                f"đáp án lệch: ({letter}) chiếm {count}/{total} = {count / total * 100:.0f}% "
                f"— chọn bừa cũng đúng chừng đó. Chạy `balance` trước khi nạp."
            )
    return problems
