"""Dựng blueprint: bối cảnh, bảng dữ liệu, và lệnh `plan`."""

from __future__ import annotations

import argparse
import re
import sys
from time import perf_counter

from app.content.exam import blueprint as bp
from app.content.exam import writer
from app.content.exam.blueprint import Blueprint
from app.content.exam_cli.paths import _gateway, blueprint_path
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier


# Trần đầu ra của chặng plan. Rộng vì model bắt buộc suy luận tiêu phần lớn trần
# vào phần nghĩ TRƯỚC khi in dòng đầu tiên: đo thật với glm-5.3-flash, Part 5 nghĩ
# 14 912 ký tự và Part 7 nghĩ 15 572 — ở trần 4 000 cả hai không bao giờ tới được
# dòng bối cảnh nào, và lượt plan lặng lẽ rơi về bảng cấu hình.
def _progress(message: str) -> None:
    """Một dòng trạng thái của chặng plan.

    Mỗi part là một tới hai lượt gọi dài hàng phút và trước đây không in gì cả,
    nên nó đọc ra như treo. In ở đây chứ không ở `cmd_plan` vì `full.py` có
    đường gọi riêng — đặt tại hàm sinh thì cả hai người gọi đều có.
    """
    print(message, flush=True)


PLAN_MAX_TOKENS = 16000


def generate_part1_scenes(gateway: Gateway, tier: Tier) -> list[tuple[str, str, str]]:
    """Hỏi model sinh sáu bối cảnh Part 1 khác nhau cho một đề.

    Vì sao để model quyết định chỗ này mà không phải chỗ khác: Part 1 chỉ có sáu
    ảnh, mỗi ảnh một bối cảnh, và sự ĐA DẠNG của bối cảnh là thứ quyết định đề
    có giống đề cũ hay không — đúng thứ `PART1_MIX` tĩnh không tự làm được khi
    chỉ có sáu mẫu. `build_part1` vẫn giữ vai trò gán `number`/`voice`; model chỉ
    cung cấp `(question_type, people, scene)`.

    Đầu ra phải khớp đúng định dạng từng dòng `question_type|people|mô tả` — nếu
    model làm sai thì NÉM để `cmd_plan` rơi về `PART1_MIX` thay vì lưu một đề
    thiếu câu.
    """

    from app.services.llm.base import LLMRequest

    prompt = (
        "Viết CHÍNH XÁC sáu dòng, mỗi dòng mô tả một bức ảnh cho Part 1 của đề "
        "TOEIC (phần mô tả ảnh đơn lẻ). Mỗi dòng đúng định dạng:\n"
        "question_type|people|mô tả bối cảnh bằng tiếng Việt\n\n"
        "question_type là MỘT TRONG: PART_1_PERSON_DESCRIPTION, "
        "PART_1_PERSON_AND_OBJECT_DESCRIPTION, PART_1_OBJECT_OR_SCENE_DESCRIPTION.\n"
        "people là MỘT TRONG: one, several, none.\n"
        "Sáu bối cảnh phải KHÁC NHAU rõ rệt (người, nơi chốn, vật thể khác nhau), "
        "thuộc môi trường công sở/dịch vụ, và tỉ lệ gần đề thật: phần lớn là one "
        "hoặc several, nhiều nhất một dòng none. Không thêm tiêu đề, không thêm "
        "dòng nào khác."
    )
    _progress("  part 1: đang sinh 6 bối cảnh ảnh…")
    started = perf_counter()
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=prompt,
                user="Sinh sáu bối cảnh ảnh Part 1.",
                max_tokens=PLAN_MAX_TOKENS,
            ),
            feature="exam_plan",
            tier=tier,
        ),
        tries=writer.RETRY_TRIES,
        delay=writer.RETRY_DELAY,
    )
    _progress(f"  part 1: xong 6 bối cảnh ({perf_counter() - started:.0f}s)")
    scenes: list[tuple[str, str, str]] = []
    line_pattern = re.compile(r"^(PART_1_[A-Z_]+)\|(one|several|none)\|(.+)$")
    for line in result.text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = line_pattern.match(line)
        if match is None:
            raise ValueError(f"dòng scene không đúng định dạng: {line[:60]!r}")
        scenes.append((match.group(1), match.group(2), match.group(3).strip()))
    if len(scenes) != 6:
        raise ValueError(f"cần đúng 6 bối cảnh Part 1, model trả {len(scenes)}")
    return scenes


def generate_part_scenes(gateway: Gateway, tier: Tier, part: int, hosts: list[str]) -> list[str]:
    """Hỏi model sinh bối cảnh MỚI cho các ô của một part (2–7).

    Chỉ sinh `context` — bối cảnh — KHÔNG động vào cấu trúc (loại câu, số người
    nói, graphic, passages, điểm ngữ pháp). Cấu trúc là quyết định của người ra
    đề nằm trong bảng `PART*_MIX` và được `validate` giữ; bối cảnh là chỗ model
    có thể làm phong phú mà không phá một ràng buộc nào. Cùng chia việc với
    `generate_part1_scenes` (part 1 model sinh luôn cả loại tranh, vì cấu trúc
    của nó chỉ có ba dạng cố định).

    Đầu ra mỗi dòng là một bối cảnh tiếng Việt; model làm sai số dòng thì NÉM để
    `cmd_plan` rơi về bối cảnh mặc định trong bảng.
    """
    from app.services.llm.base import LLMRequest

    count = {
        2: 25,
        3: 13,
        4: 10,
        5: 30,
        6: 4,
        7: 15,
    }[part]
    if len(hosts) != count:
        raise ValueError(f"Part {part} cần {count} ràng buộc ô, nhận {len(hosts)}")
    part_hint = {
        2: "câu hỏi–đáp ngắn (người hỏi và người đáp)",
        3: "cuộc hội thoại công sở/dịch vụ (ba câu hỏi về cùng một đoạn thoại)",
        4: "bài nói một người (thông báo, lời nhắn, quảng cáo, trích buổi họp)",
        5: "một câu hoàn chỉnh thiếu một chỗ trống",
        6: "một văn bản dài bốn đoạn, mỗi đoạn một chỗ trống",
        7: "một hoặc nhiều văn bản đọc kèm câu hỏi",
    }[part]
    prompt = (
        f"Viết CHÍNH XÁC {count} dòng, mỗi dòng là một bối cảnh {part_hint} cho "
        f"Part {part} của đề TOEIC. Bối cảnh bằng tiếng Việt, ngắn gọn, mỗi bối "
        "cảnh KHÁC NHAU rõ rệt (người, nơi chốn, tình huống khác nhau), thuộc môi "
        "trường công sở/dịch vụ. Không thêm tiêu đề, không thêm dòng nào khác.\n"
        # Nhãn cấu trúc đã chốt trong bảng `PART*_MIX`; bối cảnh sinh mù thì chọi
        # với nhãn — ô `PART_3_HOUSING` nhận bối cảnh phỏng vấn tuyển dụng. Và
        # `topic` đi vào `question_set_label`, nên thống kê theo chủ đề đếm sai
        # chứ không chỉ đọc lạ.
        f"Dòng thứ i phải HỢP với ràng buộc thứ i dưới đây:\n"
        + "".join(f"{order}. {host}\n" for order, host in enumerate(hosts, start=1))
    )
    _progress(f"  part {part}: đang sinh {count} bối cảnh…")
    started = perf_counter()
    result = with_backoff(
        lambda: gateway.run(
            # Rộng tay vì model SUY LUẬN xuất cả chuỗi suy nghĩ trước khi tới các
            # dòng bối cảnh — cùng bài học với `writer.write_slot`: trần quá hẹp
            # thì bị cắt giữa phần thinking, và cái cắt đó không hiện ra như lỗi.
            LLMRequest(
                system=prompt,
                user=f"Sinh {count} bối cảnh Part {part}.",
                max_tokens=PLAN_MAX_TOKENS,
            ),
            feature="exam_plan",
            tier=tier,
        ),
        tries=writer.RETRY_TRIES,
        delay=writer.RETRY_DELAY,
    )
    _progress(f"  part {part}: xong {count} bối cảnh ({perf_counter() - started:.0f}s)")
    scenes = [line.strip() for line in result.text.splitlines() if line.strip()]
    if len(scenes) != count:
        raise ValueError(f"cần đúng {count} bối cảnh Part {part}, model trả {len(scenes)}")
    # Model hay thêm tiền tố đánh số ("1. …", "1) …") — bỏ đi để context sạch.
    # Nó cũng hay chép NGUYÊN mã nhãn của ràng buộc vào đầu dòng
    # ("PART_7_FORM – …"), tức là hiểu danh sách ràng buộc thành một phần định
    # dạng câu trả lời. Bối cảnh đi thẳng vào lời nhắc viết đề, nên để nguyên là
    # đẩy một mã máy vào chỗ đáng lẽ chỉ có văn xuôi.
    import re as _re

    return [
        _re.sub(r"^[A-Z][A-Z0-9_]{4,}\s*[–—-]\s*", "", _re.sub(r"^\d+[.)]\s*", "", scene))
        for scene in scenes
    ]


def _override_contexts(plan: Blueprint, scenes: list[str]) -> None:
    """Thay bối cảnh cho từng ô mà KHÔNG đụng cấu trúc.

    Scene của model đi theo THỨ TỰ ô trong part; `merge` sắp lại theo `id` nên
    phải khớp đúng slot bằng cách duyệt plan đã dựng chứ không duyệt danh sách
    đầu vào."""
    slots = [slot for part_plan in plan.parts for slot in part_plan.slots]
    for slot, scene in zip(slots, scenes, strict=True):
        slot.context = scene


def _scene_hosts(plan: Blueprint) -> list[str]:
    """Ràng buộc cấu trúc của từng ô, đúng thứ tự `_override_contexts` dán vào.

    Cấu trúc đến từ bảng `PART*_MIX` và không đổi; chỉ bối cảnh là do model
    sinh. Không đưa ràng buộc xuống thì hai bên chỉ gặp nhau ở chỉ số, và một ô
    gắn nhãn `PART_3_HOUSING` nhận bối cảnh phỏng vấn tuyển dụng.
    """
    hosts: list[str] = []
    for part_plan in plan.parts:
        for slot in part_plan.slots:
            facets = [slot.topic, slot.question_type, slot.grammar]
            if part_plan.part == 7:
                facets.append(
                    ", ".join(
                        f"đoạn {order} {'là HÌNH vẽ từ dữ liệu' if spec else 'là chữ'}"
                        for order, spec in enumerate(slot.passages, start=1)
                    )
                )
            hosts.append(" / ".join(facet for facet in facets if facet) or "không ràng buộc")
    return hosts


def _graphic_hosts(plan: Blueprint) -> list[str]:
    """Bối cảnh của ô sẽ NHẬN mỗi hình, đúng thứ tự `build_part*` dán brief vào.

    Part 3/4 dán theo thứ tự ô có `graphic`, Part 7 theo thứ tự passage không
    rỗng — duyệt đúng thứ tự đó nên hai bên không lệch. Gọi SAU
    `_override_contexts`: trước đó `context` còn là bối cảnh của bảng, và nó sắp
    bị bối cảnh model dập đè.
    """
    hosts: list[str] = []
    for part_plan in plan.parts:
        for slot in part_plan.slots:
            if part_plan.part == 7:
                hosts.extend(slot.context for spec in slot.passages if spec)
            elif slot.graphic:
                hosts.append(" — ".join(filter(None, (slot.topic, slot.context))))
    return hosts


def generate_part_graphics(gateway: Gateway, tier: Tier, part: int, hosts: list[str]) -> list[str]:
    """Hỏi model sinh brief hình MỚI cho các vị trí graphic của part (3, 4, 7).

    Chỉ sinh `graphic`/`passages` — brief `kind: mô tả` — KHÔNG đụng vị trí hay
    cấu trúc (cụm nào có hình, câu hỏi về hình ở câu thứ mấy, kind nào hợp lệ).
    Vị trí là quyết định của người ra đề (đề thật: Part 3 ba hình ở ba cụm cuối,
    Part 4 hai hình, Part 7 năm passage hình rải trong bốn cụm); model chỉ làm
    nội dung hình khác nhau để hai đề không dùng đúng một bộ hình.

    Đầu ra mỗi dòng một brief `kind: mô tả`; sai số lượng hay sai kind thì NÉM để
    `cmd_plan` rơi về `PART*_GRAPHIC_POOL` theo seed.
    """
    from app.content.exam.graphics import AXIS_BRIEF, KINDS
    from app.services.llm.base import LLMRequest

    count = {3: 3, 4: 2, 7: 5}[part]
    if len(hosts) != count:
        raise ValueError(f"Part {part} cần {count} bối cảnh ô, nhận {len(hosts)}")
    kinds = ", ".join(KINDS)
    prompt = (
        f"Viết CHÍNH XÁC {count} dòng, mỗi dòng là BRIEF cho một hình ngữ liệu "
        f"của Part {part} đề TOEIC (đề tự sinh, không phải đề thi thật).\n"
        f"Mỗi dòng đúng định dạng `kind: mô tả bằng tiếng Việt`.\n"
        # Mô tả là ghi chú nội bộ nên viết tiếng Việt; NHÃN thì đi thẳng lên
        # hình người thi đọc. Không tách hai thứ đó thì brief ghi "nhãn bốn
        # mục là Phòng tập, Hồ bơi..." và người viết đề chép đúng y lời.
        f"NHƯNG mọi NHÃN sẽ xuất hiện trên hình — tiêu đề, tên hàng, tiêu đề "
        f"cột, tên ô — phải viết bằng TIẾNG ANH. Đề TOEIC là bài thi tiếng Anh.\n"
        f"kind phải là MỘT TRONG: {kinds}.\n"
        f"Brief phải nói rõ hình gì và BỐN MỤC TRÊN TRỤC ĐÁP ÁN là gì, đủ để vẽ.\n"
        f"Trục đáp án khác nhau theo từng kind — mô tả sai trục thì hình bị cổng "
        f"kiểm chặn dù nội dung hợp lý:\n{AXIS_BRIEF}\n"
        # Không có danh sách này thì lượt sinh hình mù về ô nó sắp rơi vào, và
        # người viết đề nhận hai yêu cầu không liên quan — đó là cách một hội
        # thoại kho hàng mọc ra câu về số khách bảo tàng.
        f"MỖI hình phải THUỘC VỀ đúng ô nó đi kèm. Bối cảnh {count} ô, theo đúng "
        f"thứ tự phải trả lời:\n"
        + "".join(f"{order}. {host}\n" for order, host in enumerate(hosts, start=1))
        + f"{count} hình KHÁC NHAU về kind. Không thêm tiêu đề, "
        f"không thêm dòng nào khác."
    )
    _progress(f"  part {part}: đang sinh {count} brief hình…")
    started = perf_counter()
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=prompt,
                user=f"Sinh {count} brief hình Part {part}.",
                max_tokens=PLAN_MAX_TOKENS,
            ),
            feature="exam_plan",
            tier=tier,
        ),
        tries=writer.RETRY_TRIES,
        delay=writer.RETRY_DELAY,
    )
    _progress(f"  part {part}: xong {count} brief hình ({perf_counter() - started:.0f}s)")
    briefs: list[str] = []
    for line in result.text.splitlines():
        line = line.strip()
        if not line:
            continue
        kind = line.split(":", 1)[0].strip()
        if kind not in KINDS:
            raise ValueError(f"kind hình không hợp lệ: {line[:60]!r}")
        briefs.append(line)
    if len(briefs) != count:
        raise ValueError(f"cần đúng {count} brief hình Part {part}, model trả {len(briefs)}")
    return briefs


def cmd_plan(args: argparse.Namespace) -> int:
    title = args.title or f"TOEIC Pilot — {args.slug}"
    builder = {
        1: bp.build_part1,
        2: bp.build_part2,
        3: bp.build_part3,
        4: bp.build_part4,
        5: bp.build_part5,
        6: bp.build_part6,
        7: bp.build_part7,
    }[args.part]
    path = blueprint_path(args.slug)
    existing = bp.load(path) if path.exists() else None

    # Có `--model` thì hỏi model sinh bối cảnh (+ brief hình cho part có hình);
    # hỏng thì rơi về bảng cấu hình / pool theo seed — một lượt plan không được
    # chết vì model. Cấu trúc (loại câu, vị trí hình, giọng) luôn từ bảng; model
    # chỉ sinh NỘI DUNG bối cảnh và hình.
    built = builder(args.slug, title, args.seed)
    if args.model:
        try:
            gateway = _gateway(args.model)
            if args.part == 1:
                scenes = generate_part1_scenes(gateway, Tier(args.tier))
                built = bp.build_part1(args.slug, title, args.seed, scenes)
            else:
                contexts = generate_part_scenes(
                    gateway, Tier(args.tier), args.part, _scene_hosts(built)
                )
                if args.part in (3, 4, 7):
                    # Bối cảnh model phải áp TRƯỚC: `_graphic_hosts` đọc `context`,
                    # và bản của bảng sắp bị dập đè ở dòng dưới.
                    _override_contexts(built, contexts)
                    graphics = generate_part_graphics(
                        gateway, Tier(args.tier), args.part, _graphic_hosts(built)
                    )
                    built = {
                        3: bp.build_part3,
                        4: bp.build_part4,
                        7: bp.build_part7,
                    }[args.part](args.slug, title, args.seed, graphics)
                _override_contexts(built, contexts)
            print(f"model {args.model} sinh nội dung Part {args.part}.")
        except Exception as failure:  # noqa: BLE001 — rơi về bảng là đường đúng
            print(
                f"không sinh được nội dung bằng model ({failure}) — dùng bảng cấu hình.",
                file=sys.stderr,
            )
            built = builder(args.slug, title, args.seed)

    plan = bp.merge(existing, built)
    problems = bp.validate(plan)
    if problems:
        for problem in problems:
            print(f"  ✗ {problem}", file=sys.stderr)
        return 1
    bp.save(plan, path)
    shape = ", ".join(f"part {plan_.part}: {len(plan_.slots)} ô" for plan_ in plan.parts)
    print(f"{path} — {shape}")
    return 0
