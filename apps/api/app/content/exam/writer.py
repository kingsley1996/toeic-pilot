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

from app.content.exam.blueprint import (
    QUESTIONS_PER_SET,
    Blueprint,
    QuestionSlot,
)
from app.content.exam.prompts import (
    _PROMPT_FOR,
    BLANK,
    GRAPHIC_MARKER,
    GRAPHIC_RULES_TEMPLATE,
    PASSAGE_MARKER,
    PHOTO_MARKER,
    SCRIPT_MARKER,
    _system_for,
    graphic_rules,
    prompt_for,
    prompt_for_part1,
    prompt_for_part2,
    prompt_for_part3,
    prompt_for_part4,
    prompt_for_part6,
    prompt_for_part7,
)

# Tái xuất hợp đồng định dạng: `check`, `authoring` và `graph` vốn lấy các mốc
# qua `writer`, và bắt chúng đổi sang `prompts` chỉ vì tệp được tách là một diff
# không mua được gì. `__all__` cũng là thứ nói cho ruff biết đây là tái xuất cố
# ý chứ không phải import bỏ quên.
__all__ = [
    "BLANK",
    "DEFAULT_MAX_TOKENS",
    "GRAPHIC_MARKER",
    "GRAPHIC_RULES_TEMPLATE",
    "PASSAGE_MARKER",
    "PHOTO_MARKER",
    "RETRY_DELAY",
    "RETRY_TRIES",
    "SCRIPT_MARKER",
    "MissingBlock",
    "clean",
    "graphic_rules",
    "paste_path",
    "pending",
    "prompt_for",
    "prompt_for_part1",
    "prompt_for_part2",
    "prompt_for_part3",
    "prompt_for_part4",
    "prompt_for_part6",
    "prompt_for_part7",
    "save_slot",
    "split_all",
    "split_marked",
    "split_photo",
    "write_slot",
]
from app.services.llm.base import LLMRequest
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier

# Cả pipeline sinh đề kiên nhẫn hơn mặc định của `with_backoff`. Đo được trên
# model miễn phí của tokenrouter: **ba lượt 503 liên tiếp rồi lượt thứ tư trả
# 200** — tức là `tries=4` mặc định bỏ cuộc đúng một lượt trước khi thành công.
# Một chặng chạy ngoài luồng hàng chục phút thì đợi thêm hai phút là rẻ; bỏ cuộc
# thì ô đó về hàng đợi và người chạy phải tự chạy lại.
RETRY_TRIES = 7
RETRY_DELAY = 6.0


def split_all(block: str, marker: str) -> tuple[list[str], str]:
    """Tách MỌI khối mang `marker`, theo thứ tự. Trả (các khối, phần còn lại).

    Một cụm Part 7 có thể mang HAI hình (bảng giá và phiếu đặt hàng của đề mẫu),
    nên bản chỉ lấy khối cuối làm mất tấm thứ nhất — và mất im lặng, vì tệp dán
    vẫn hợp lệ và chỉ thiếu một ngữ liệu mà không ai đếm.
    """
    taken: list[str] = []
    rest = block
    while True:
        one, rest = split_marked(rest, marker)
        if not one:
            return list(reversed(taken)), rest
        taken.append(one)


def split_marked(block: str, marker: str) -> tuple[str, str]:
    """Tách khối mang `marker` ra khỏi phần dán. Trả (phần tách, phần còn lại).

    Cùng lý do như `split_photo`: parser TỪ CHỐI dòng lạ, nên mô tả ảnh và dữ
    liệu bảng phải rời khỏi tệp dán. Nó cũng đúng về vòng đời — hai hiện vật đó
    phục vụ chặng vẽ, tệp dán phục vụ chặng nạp, và hai chặng chạy lại độc lập.
    """
    lines = block.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == marker]
    if not starts:
        return "", block
    begin = starts[-1]
    # Khối kết thúc ở mốc tiếp theo bất kỳ ([SCRIPT], [QUESTION], [PHOTO]).
    end = next(
        (
            index
            for index in range(begin + 1, len(lines))
            if lines[index].strip().startswith("[") and lines[index].strip().endswith("]")
        ),
        len(lines),
    )
    taken = "\n".join(lines[begin + 1 : end]).strip()
    rest = "\n".join(lines[:begin] + lines[end:]).strip()
    return taken, rest


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


def paste_path(workdir: Path, slot: QuestionSlot) -> Path:
    return workdir / "paste" / f"{slot.id}.txt"


# Chỗ trống viết bằng gạch DƯỚI, hoặc bằng số gạch ngang khác bảy. Cả hai đều là
# sai lệch định dạng, không phải sai nội dung — chỗ trống ở đâu thì vẫn ở đó.
_BLANK_VARIANTS = re.compile(r"_{3,}|-{3,}")


def clean(text: str, expect_markers: int = 1) -> str:
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
    # Part 3 và 4 mở đầu bằng `[SCRIPT]` và mang BA khối câu hỏi, nên "lấy khối
    # cuối" là sai ở đó: nó vứt mất lời thoại và hai câu đầu. Có `[SCRIPT]` đầu
    # dòng thì cắt từ đó và giữ trọn phần còn lại.
    # Part 6/7 mở đầu bằng `[PASSAGE]`, Part 3/4 bằng `[SCRIPT]` — cùng vai trò
    # "ngữ liệu dùng chung", hai mốc khác nhau vì một bên đọc lên, một bên in ra.
    script_starts = [
        index
        for index, line in enumerate(lines_all)
        if line.strip() in (SCRIPT_MARKER, PASSAGE_MARKER)
    ]
    if script_starts:
        # Giữ khối [GRAPHIC] nếu nó đứng TRƯỚC lời thoại — mô hình đặt bảng lên
        # đầu vì prompt bảo thế, và cắt sạch phần trước [SCRIPT] sẽ vứt mất nó.
        # Mất bảng thì chỉ lộ ra ở chặng vẽ, tức là sau khi đã trả tiền gọi.
        graphic_starts = [
            index
            for index, line in enumerate(lines_all[: script_starts[-1]])
            if line.strip() == GRAPHIC_MARKER
        ]
        # Lấy mốc thứ `expect_markers` TỪ CUỐI LÊN, không phải mốc cuối.
        #
        # Luật "lấy mốc cuối" dựng cho `[SCRIPT]`, nơi mỗi cụm chỉ có đúng một —
        # nên cuối cũng là đầu, và nó chặn được model suy luận trích lại chính
        # cái mốc trong lúc tự nhủ. Part 7 có tới BA `[PASSAGE]`, và luật đó cắt
        # mất hai ngữ liệu đầu: đầu ra còn lại vẫn là một cụm hợp lệ, chỉ thiếu
        # tài liệu — rồi câu hỏi "mục đích của tài liệu THỨ NHẤT là gì" hỏi về
        # một thứ không còn ở đó.
        take = min(expect_markers, len(script_starts))
        begin = graphic_starts[-1] if graphic_starts else script_starts[-take]
        return "\n".join(lines_all[begin:]).strip()

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


# Trần đầu ra mặc định của chặng viết. Không phải hằng số cứng, vì nó bị kéo
# theo hai hướng ngược nhau và cả hai đều đo được:
#
#   · model SUY LUẬN cần rộng — `qwen3.8-max` nghĩ 22 000 ký tự về một ô lịch
#     Part 3 rồi mới trả lời, và ở 6 000 nó không bao giờ tới được câu trả lời;
#   · hạn mức TPM của nhà cung cấp lại tính `max_tokens` vào ngân sách phút —
#     gói miễn phí của Groq là 8 000 TPM, nên đặt 12 000 làm MỌI yêu cầu bị từ
#     chối 413 trước khi kịp gửi đi.
#
# Nên nó là tham số của lượt chạy, giống như việc chọn nhà cung cấp.
DEFAULT_MAX_TOKENS = 6000

# Trần theo HÌNH DẠNG của ô, không theo lượt chạy — `--max-tokens` là một con số
# cho cả trăm ô có độ khó rất khác nhau.
#
# Nội dung sinh ra rất ngắn (đo trên tp-form-08: 64 tới 401 token), nên gần như
# TOÀN BỘ trần là phần suy luận, và nó tỉ lệ với độ khó chứ không với độ dài đầu
# ra. Đo được với glm-5.3-flash: ô không hình dùng trung bình 2 096 token và
# nhiều nhất 7 739; ô có hình dùng 8 506 ở trần 25 000, còn `p3-11` bị cắt ở
# trần 12 000.
#
# Trần rộng KHÔNG miễn phí: model nở phần suy luận cho vừa ngân sách được cấp.
# Cùng một ô có hình, trần 40 000 mất 322 giây còn trần 25 000 chỉ mất 225 — và
# cửa sổ đọc đi theo trần, nên trần rộng cũng làm một ô HỎNG hỏng chậm hơn.
_MAX_TOKENS_BY_PART = {1: 10000, 2: 10000, 3: 14000, 4: 14000, 5: 12000, 6: 16000, 7: 20000}
GRAPHIC_MAX_TOKENS = 24000

# Trần phản hồi của NHÀ CUNG CẤP, đo chứ không tra tài liệu: ba lượt ngắt kết nối
# ở 340 154, 340 144 và 340 465 ms — lệch 0,3 giây trên 340. Nó cắt bất kể cửa sổ
# đọc của ta rộng bao nhiêu, nên mọi lượt gọi phải sinh XONG trước nó. Ở nhịp
# ~38 token/giây đo được, 340 giây là khoảng 13 000 token.
PROVIDER_CEILING_TOKENS = 13000

# Part 7 là part duy nhất chạm trần đó, và ranh giới trùng khít với hình dạng ô:
# mười ô MỘT ngữ liệu (`p7-01`…`p7-10`) đạt hết, còn `p7-11` — hai ngữ liệu, năm
# câu — ngắt kết nối cả hai lần thử. Nội dung thật của nó chỉ ~700 token; phần
# vượt trần là suy luận, nên hạ trần cắt đúng thứ đang thừa.
PART7_MAX_TOKENS = 10000


def max_tokens_for(part: int, slot: QuestionSlot) -> int:
    """Trần đầu ra hợp lý cho ô này. `--max-tokens` truyền tay vẫn thắng."""
    if part == 7:
        return PART7_MAX_TOKENS
    if slot.graphic or any(slot.passages):
        return GRAPHIC_MAX_TOKENS
    return _MAX_TOKENS_BY_PART.get(part, DEFAULT_MAX_TOKENS)


def write_slot(
    gateway: Gateway,
    slot: QuestionSlot,
    tier: Tier,
    part: int = 5,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    fix_hint: str | None = None,
) -> str:
    # Qua `with_backoff`: nhà cung cấp lớn trả 503 "high demand" khá thường, và
    # không lùi thì vòng lặp đốt sạch 30 ô trong vài giây, mỗi ô hỏng một lần vì
    # cùng một cơn quá tải kéo dài vài chục giây. Đo được với Gemini: một lượt
    # chạy 30 ô ra 0 tệp.
    user_prompt = _PROMPT_FOR.get(part, prompt_for)(slot)
    if fix_hint:
        # Lượt viết lại trong vòng agent: lời phê của critic gắn vào prompt.
        # Không có nó thì "viết lại" chỉ là sinh lại mù — ô hỏng cùng kiểu.
        user_prompt = f"{user_prompt}\n\nLƯU Ý SỬA từ lượt trước: {fix_hint}"
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=_system_for(part, slot),
                user=user_prompt,
                # Rộng tay, vì model SUY LUẬN xuất cả chuỗi suy nghĩ trước khi tới
                # khối cần lấy. Đo được: `nemotron-3-ultra` cụt giữa phần suy nghĩ ở
                # 600 token, và cái cụt đó không hiện ra như một lỗi — nó hiện ra
                # như một ô đã ghi xong với nội dung là đoạn model đang tự nhủ.
                max_tokens=max_tokens,
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
    block = clean(result.text, max(1, len(slot.passages)))
    lines = [line.strip() for line in block.splitlines()]
    # Part 1 mở đầu bằng [PHOTO], Part 3/4 bằng [SCRIPT], còn lại là [QUESTION].
    header_ok = bool(lines) and lines[0] in (
        "[QUESTION]",
        PHOTO_MARKER,
        SCRIPT_MARKER,
        PASSAGE_MARKER,
        GRAPHIC_MARKER,
    )
    # Ba dấu hiệu của một khối HOÀN CHỈNH, không phải một khối bị cắt giữa chừng.
    # Chỉ hỏi "có mốc không" là không đủ: đầu ra bị cắt vẫn có mốc, và nó được
    # lưu như một ô đã xong.
    # Part 3/4 phải có ĐỦ BA câu, và đây là chỗ duy nhất đếm được rẻ. Thiếu một
    # câu thì parser vẫn đọc ra một cụm hợp lệ hai câu, `commit_part` vẫn ghi, và
    # đề lặng lẽ ngắn đi một câu ở đúng chỗ không ai đếm.
    # Part 7 không có số cố định cho cả part — lấy từ chính cái ô.
    wanted = len(slot.question_types) if part == 7 else QUESTIONS_PER_SET.get(part, 1)
    # Part 2 có BA lựa chọn, nên `(D)` là dấu hiệu sai ở đó — đòi nó thì mọi ô
    # Part 2 đều bị ném đi dù viết đúng.
    final = "(C)" if part == 2 else "(D)"
    complete = (
        header_ok
        and sum(1 for line in lines if line == "[QUESTION]") >= wanted
        and sum(1 for line in lines if line.startswith(final)) >= wanted
        and sum(1 for line in lines if line.lower().startswith("answer:")) >= wanted
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
