"""Chặng sinh văn bản: một ô một lượt gọi, ghi thẳng ra tệp dán.

**Mô hình xuất ra ĐỊNH DẠNG DÁN**, không phải JSON rồi mình dựng lại. Đó là
quyết định kiến trúc chính của cả pipeline: định dạng dán đã có parser thật
(`content_import.py`) và bộ luật thật (`validators.py`) đứng sau, nên bản sinh
phải qua đúng cái cổng mà bản người dán phải qua. Nhận JSON rồi tự lắp câu là
dựng đường vào thứ hai, và mọi luật ở cổng kia phải được nhớ lại lần nữa ở đây —
chỗ nào quên thì hỏng im lặng.

**Một ô một lượt gọi.** Cùng lý do `enrich_skills` gọi một facet một lượt: gộp
thì ít lượt hơn nhưng mô hình trượt một chỗ là hỏng cả mẻ, phải chạy lại toàn bộ
thay vì chạy lại đúng ô hỏng, và ngữ cảnh rộng ra làm nó lệch khỏi điểm ngữ pháp
đã giao.

**Ghi xuống đĩa NGAY sau mỗi ô**, không gom cuối lượt: 30 ô là nhiều phút, và
một lần Ctrl-C không được phép vứt sạch.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.content.exam.blueprint import Blueprint, QuestionSlot
from app.services.labels import LABELS
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier

# Hợp đồng định dạng, gửi kèm mọi lượt gọi. Viết ra tường minh chứ không tả bằng
# lời: mô hình bám theo ví dụ chặt hơn nhiều so với bám theo mô tả.
# Dòng giải thích của ví dụ, ghép từ nhiều mảnh để NGUỒN ngắn dưới 100 cột mà
# chuỗi gửi đi vẫn nằm trên MỘT dòng. Ngắt dòng thật ở đây sẽ dạy mô hình ngắt
# dòng theo, và parser coi dòng lạ sau các đáp án là lỗi — một lựa chọn định
# dạng của tệp nguồn sẽ đi thẳng vào đầu ra của mô hình.
EXAMPLE_EXPLANATION = (
    'Explanation: Sau "must be" cần phân từ hai của thể bị động. '
    '(B) là V-ing, không đi sau "be" theo nghĩa bị động; '
    '(C) là danh từ; (D) là tính từ nghĩa "phục tùng", không liên quan.'
)

SYSTEM = f"""You write TOEIC Part 5 (Incomplete Sentences) questions for an original practice test.

THE ONE RULE THAT DECIDES WHETHER AN ITEM IS USABLE
Exactly one option can complete the sentence. Apply this test before you answer:
read the sentence four times, once with each option in the blank. If a competent
speaker of business English would accept two of them, the item is broken — throw
it away and write a different one. Near-synonyms are the usual way this goes
wrong: "verify / confirm / validate" all fit "------- the references", so that is
not an item, it is four right answers.

Each wrong option must fail for a reason you can state in one short clause:
- wrong part of speech for that slot,
- wrong collocation with the noun or verb next to the blank,
- wrong tense, voice, or number given the rest of the sentence,
- a real word that means something unrelated in this context.
"Slightly less natural" is NOT a reason. If that is the best you can say about a
distractor, replace it.

Other rules:
- One English sentence with exactly one blank, written as seven hyphens: -------
- Exactly FOUR options labelled (A) (B) (C) (D).
- Setting is always work, business or office life — never private life.
- Neutral register. No humour, no real brand names.
- Never copy a sentence from any real exam. Write new material.
- Sentence and options in ENGLISH. Explanation in Vietnamese.
- The explanation names the reason EACH wrong option is wrong, not just why the
  right one is right.

Reply with exactly this block and nothing else — no preamble, no code fences:

[QUESTION]
All maintenance requests must be ------- through the facilities portal by Friday.
(A) submitted
(B) submitting
(C) submission
(D) submissive
Answer: A
{EXAMPLE_EXPLANATION}
Source: original

Note the shape of the answer line: a single letter, nothing else."""


PHOTO_MARKER = "[PHOTO]"

# Cả pipeline sinh đề kiên nhẫn hơn mặc định của `with_backoff`. Đo được trên
# model miễn phí của tokenrouter: **ba lượt 503 liên tiếp rồi lượt thứ tư trả
# 200** — tức là `tries=4` mặc định bỏ cuộc đúng một lượt trước khi thành công.
# Một chặng chạy ngoài luồng hàng chục phút thì đợi thêm hai phút là rẻ; bỏ cuộc
# thì ô đó về hàng đợi và người chạy phải tự chạy lại.
RETRY_TRIES = 7
RETRY_DELAY = 6.0

SYSTEM_PART1 = f"""You write TOEIC Part 1 (Photographs) items for an original practice test.

A Part 1 item is a photograph plus four spoken statements. Nothing is printed in
the test book — the four statements are heard, not read. Exactly one statement is
a true description of the photograph.

THE RULE THAT DECIDES WHETHER AN ITEM IS USABLE
The three wrong statements must be **verifiably false about the photograph**, not
merely unlikely. Each one fails in one of these ways:
- right object, wrong action ("The man is repairing the copier" when he is using it),
- right action, wrong object ("She is holding a folder" when it is a mug),
- an object or person that is simply not in the photograph,
- a plural/singular mismatch ("The workers are..." when there is one person).
A statement that *might* be true depending on how you look at the photo is not a
distractor — it is a second right answer. Rewrite it.

Write the four statements FIRST, then describe the photograph that makes exactly
one of them true. The description will be used to create the photograph, so it
must fix every detail the four statements depend on: how many people, what each
is doing, what objects are visible and where.

Other rules:
- Present continuous is the normal tense for Part 1; a few statements may use
  "There is / There are" or the passive.
- Each statement is one short sentence, 6–12 words, similar length to the others.
- Setting is always work, business or public life. No brand names, no text in the
  photograph.
- Never copy from any real exam.

Reply with exactly these two blocks and nothing else — no preamble, no fences:

{PHOTO_MARKER}
A photograph of an office worker seated at a desk, typing on a laptop with both
hands. A closed notebook and a white mug sit to the right of the laptop. No other
people are visible.

[QUESTION]
voice: VOICE_ID
(A) The man is typing on a laptop.
(B) The man is pouring coffee into a mug.
(C) Two colleagues are sharing a desk.
(D) The notebook is lying open on the desk.
Answer: A
Source: original

`voice:` must be copied exactly from the instruction below."""


# Số người trong ảnh đổi cả bộ mẫu câu, không chỉ đổi nội dung. Không nói ra thì
# mô hình viết "The man is ..." cho một tấm ảnh không có ai — và câu đó sai theo
# một kiểu người học không học được gì từ nó.
_PEOPLE_BRIEF = {
    "one": (
        "Trong ảnh có ĐÚNG MỘT người. Mẫu câu chính là thì hiện tại tiếp diễn "
        "với người đó làm chủ ngữ."
    ),
    "several": (
        "Trong ảnh có TỪ HAI NGƯỜI TRỞ LÊN. Dùng cả chủ ngữ số nhiều "
        '("The workers are...") lẫn chủ ngữ chỉ một người trong nhóm.'
    ),
    "none": (
        "Trong ảnh KHÔNG CÓ NGƯỜI NÀO — chỉ đồ vật hoặc quang cảnh. Vì thế "
        'KHÔNG câu nào được có người làm chủ ngữ. Dùng "There is / There are", '
        'thể bị động trạng thái ("Some chairs have been arranged in rows"), '
        "hoặc hiện tại tiếp diễn với chủ ngữ là đồ vật "
        '("Some boxes are sitting on the floor"). Một câu nhiễu tốt ở dạng này '
        "là câu nhắc tới một người không hề có trong ảnh."
    ),
}


def prompt_for_part1(slot: QuestionSlot) -> str:
    kind = LABELS[slot.question_type].label_vi
    return (
        f"Viết một câu hỏi Part 1.\n"
        f"- Dạng ảnh: {kind}\n"
        f"- {_PEOPLE_BRIEF[slot.people]}\n"
        f"- Bối cảnh: {slot.context}\n"
        # Đưa NGUYÊN dòng cần in ra, không mô tả nó. Bản cũ viết
        # "- Dòng `voice:` phải ghi đúng: ca_male_1" và mô hình nhỏ chép luôn cả
        # dấu ngoặc ngược vào đầu ra — `\`voice:\` ca_male_1` — thứ parser từ chối.
        # Hỏng ba lần liên tiếp y hệt nhau với gemma3, tức là lỗi của prompt chứ
        # không phải của mô hình.
        f"- Dòng đầu tiên sau [QUESTION] phải là chính xác:\nvoice: {slot.voice}\n"
        f"- Ba câu sai phải SAI KIỂM CHỨNG ĐƯỢC so với tấm ảnh sẽ vẽ, "
        f"không phải chỉ 'ít khả năng'."
    )


def split_photo(block: str) -> tuple[str, str]:
    """Tách phần mô tả ảnh khỏi phần dán.

    Hai hiện vật riêng vì parser TỪ CHỐI dòng lạ sau các đáp án: nhét mô tả ảnh
    vào cùng tệp dán là làm cả khối không đọc được. Tách ở đây cũng đúng về mặt
    vòng đời — mô tả ảnh phục vụ chặng vẽ, tệp dán phục vụ chặng nạp, và hai
    chặng đó chạy lại độc lập với nhau.
    """
    if PHOTO_MARKER not in block:
        return "", block
    _, _, rest = block.partition(PHOTO_MARKER)
    photo, marker, paste = rest.partition("[QUESTION]")
    return photo.strip(), (marker + paste).strip()


def prompt_for(slot: QuestionSlot) -> str:
    grammar = LABELS[slot.grammar].label_vi if slot.grammar else "từ vựng thương mại"
    kind = LABELS[slot.question_type].label_vi
    lines = [
        "Viết một câu hỏi Part 5.",
        f"- Dạng câu: {kind}",
        f"- Điểm kiểm tra: {grammar}",
        f"- Bối cảnh: {slot.context}",
    ]
    if not slot.grammar:
        # Câu TỪ VỰNG là chỗ lỗi "hai đáp án cùng đúng" xảy ra nhiều nhất, vì
        # cách viết dễ nhất là lấy bốn từ gần nghĩa. Nói thẳng đường đi đúng thay
        # vì chỉ cấm đường sai: bốn từ cùng đăng ký ngôn ngữ nhưng KHÁC trường
        # nghĩa, và chỉ một từ hợp với danh từ/động từ đứng cạnh chỗ trống.
        lines.append(
            "- Bốn lựa chọn phải là bốn từ KHÁC TRƯỜNG NGHĨA, không phải bốn từ gần nghĩa. "
            "Ba từ sai phải sai vì không đi được với từ đứng cạnh chỗ trống, "
            "không phải vì 'kém tự nhiên hơn'."
        )
    else:
        lines.append(
            "- Ba lựa chọn sai phải sai vì đúng điểm kiểm tra đó (sai từ loại, sai thì, "
            "sai thể, sai dạng), không phải sai vu vơ."
        )
    lines.append(
        "- Bốn lựa chọn dài xấp xỉ nhau: lựa chọn dài hơn hẳn là một manh mối rò rỉ đáp án."
    )
    return "\n".join(lines)


def paste_path(workdir: Path, slot: QuestionSlot) -> Path:
    return workdir / "paste" / f"{slot.id}.txt"


# Chỗ trống viết bằng gạch DƯỚI, hoặc bằng số gạch ngang khác bảy. Cả hai đều là
# sai lệch định dạng, không phải sai nội dung — chỗ trống ở đâu thì vẫn ở đó.
_BLANK_VARIANTS = re.compile(r"_{3,}|-{3,}")
BLANK = "-------"


def clean(text: str) -> str:
    """Gỡ rào ``` và mọi thứ trước `[QUESTION]`.

    Mô hình nhỏ hay thêm một câu dẫn ("Chắc chắn rồi, đây là…") dù prompt đã cấm.
    Cắt ở đây rẻ hơn nhiều so với để parser từ chối cả khối — và nó không che
    giấu gì: phần bị cắt luôn nằm TRƯỚC mốc, tức là không phải nội dung câu hỏi.
    """
    body = text.strip()
    if "```" in body:
        parts = [chunk for chunk in body.split("```") if "[QUESTION]" in chunk]
        body = parts[0] if parts else body.replace("```", "")
    # Mốc phải đứng ĐẦU DÒNG, và lấy lần xuất hiện CUỐI CÙNG.
    #
    # Cả hai điều kiện đều học được từ một lượt chạy thật: model suy luận trích
    # dẫn chính cái mốc này trong lúc tự nhủ ("Format must be [QUESTION] ..."),
    # nên `find` bắt được nó ở giữa đoạn suy nghĩ và giữ lại toàn bộ phần suy
    # nghĩ như thể đó là câu hỏi. Khối thật luôn là khối cuối.
    lines_all = body.splitlines()
    starts = [index for index, line in enumerate(lines_all) if line.strip() == "[QUESTION]"]
    if starts:
        # Giữ khối [PHOTO] nếu nó đứng NGAY TRƯỚC khối câu hỏi cuối cùng: Part 1
        # cần cả hai, và cắt sạch phần đầu sẽ vứt mất mô tả ảnh — thứ chỉ phát
        # hiện được ở chặng vẽ, tức là sau khi đã trả tiền cho lượt gọi.
        photo_starts = [
            index
            for index, line in enumerate(lines_all[: starts[-1]])
            if line.strip() == PHOTO_MARKER
        ]
        begin = photo_starts[-1] if photo_starts else starts[-1]
        body = "\n".join(lines_all[begin:]).strip()

    # Chuẩn hoá chỗ trống. Sửa ĐỊNH DẠNG thì được, sửa nội dung thì không: một
    # chuỗi gạch dưới và bảy gạch ngang nói cùng một điều ở cùng một chỗ, nên
    # quy về một dạng không giấu đi lỗi nào. Ngược lại, tự sửa một đáp án sai
    # thành đúng sẽ che mất đúng tín hiệu mà cổng kiểm sinh ra để bắt.
    #
    # Đo được: mô hình ĐANG dùng viết `_______` ở khoảng 1 trên 15 câu, và bắt
    # sinh lại chỉ để đổi ký tự là trả tiền cho một lượt gọi mà không đổi gì.
    lines = body.splitlines()
    if lines and lines[0].strip() == "[QUESTION]" and len(lines) > 1:
        lines[1] = _BLANK_VARIANTS.sub(BLANK, lines[1])
    return "\n".join(lines)


class MissingBlock(RuntimeError):
    """Đầu ra không chứa `[QUESTION]` — không có gì để lưu."""


def write_slot(gateway: Gateway, slot: QuestionSlot, tier: Tier, part: int = 5) -> str:
    # Qua `with_backoff`: nhà cung cấp lớn trả 503 "high demand" khá thường, và
    # không lùi thì vòng lặp đốt sạch 30 ô trong vài giây, mỗi ô hỏng một lần vì
    # cùng một cơn quá tải kéo dài vài chục giây. Đo được với Gemini: một lượt
    # chạy 30 ô ra 0 tệp.
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=SYSTEM_PART1 if part == 1 else SYSTEM,
                user=prompt_for_part1(slot) if part == 1 else prompt_for(slot),
                # Rộng tay, vì model SUY LUẬN xuất cả chuỗi suy nghĩ trước khi tới
                # khối cần lấy. Đo được: `nemotron-3-ultra` cụt giữa phần suy nghĩ ở
                # 600 token, và cái cụt đó không hiện ra như một lỗi — nó hiện ra
                # như một ô đã ghi xong với nội dung là đoạn model đang tự nhủ.
                max_tokens=6000,
                # Nhiệt độ KHÁC 0, và đây là chỗ duy nhất trong dự án cố ý như thế.
                # Mọi lượt gọi khác (gắn nhãn, chấm) muốn cùng đầu vào ra cùng đầu
                # ra. Ở đây thì ngược lại: 30 câu ở nhiệt độ 0 sẽ trôi về cùng một
                # khuôn câu, và cái giống nhau đó đọc ra ngay là máy viết.
                temperature=0.8,
            ),
            feature="exam_write",
            tier=tier,
        ),
        tries=RETRY_TRIES,
        delay=RETRY_DELAY,
    )
    block = clean(result.text)
    lines = [line.strip() for line in block.splitlines()]
    # Với Part 1, khối bắt đầu bằng [PHOTO]; với các part khác là [QUESTION].
    header_ok = lines and lines[0] in ("[QUESTION]", PHOTO_MARKER)
    # Ba dấu hiệu của một khối HOÀN CHỈNH, không phải một khối bị cắt giữa chừng.
    # Chỉ hỏi "có mốc không" là không đủ: đầu ra bị cắt vẫn có mốc, và nó được
    # lưu như một ô đã xong.
    complete = (
        header_ok
        and any(line.startswith("(D)") for line in lines)
        and any(line.lower().startswith("answer:") for line in lines)
    )
    if not complete:
        # NÉM chứ không lưu. Lưu một đầu ra không có mốc nghĩa là ô đó coi như
        # xong — hàng đợi là một truy vấn trên thư mục, nên lần chạy sau sẽ bỏ
        # qua nó, và thứ rác kia nằm lại tới tận chặng kiểm. Ném thì ô vẫn thiếu
        # tệp, và chạy lại lệnh là tự nó thử lại.
        raise MissingBlock(
            f"đầu ra không phải một khối hoàn chỉnh ({len(result.text)} ký tự) — "
            f"thường là bị cắt giữa phần suy luận"
        )
    return block


def pending(blueprint: Blueprint, workdir: Path) -> list[QuestionSlot]:
    """Ô nào còn thiếu tệp dán.

    Hàng đợi là một TRUY VẤN trên thư mục, không phải một bảng job — cùng luật
    với `backfill_audio` hỏi database "cái gì còn thiếu audio". Chạy lại lệnh là
    tìm thấy ít việc hơn, và đó là toàn bộ cơ chế phục hồi.
    """
    return [
        slot
        for part in blueprint.parts
        for slot in part.slots
        if not paste_path(workdir, slot).exists()
    ]


def save_slot(workdir: Path, slot: QuestionSlot, block: str) -> Path:
    path = paste_path(workdir, slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(block.rstrip() + "\n")
    return path
