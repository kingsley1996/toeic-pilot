"""Dựng blueprint: bối cảnh, bảng dữ liệu, và lệnh `plan`."""

from __future__ import annotations

import argparse
import re
import sys

from app.content.exam import blueprint as bp
from app.content.exam import writer
from app.content.exam.blueprint import Blueprint
from app.content.exam_cli.paths import _gateway, blueprint_path
from app.services.llm.gateway import Gateway
from app.services.llm.retry import with_backoff
from app.services.llm.router import Tier


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
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(system=prompt, user="Sinh sáu bối cảnh ảnh Part 1.", max_tokens=4000),
            feature="exam_plan",
            tier=tier,
        ),
        tries=writer.RETRY_TRIES,
        delay=writer.RETRY_DELAY,
    )
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


def generate_part_scenes(gateway: Gateway, tier: Tier, part: int) -> list[str]:
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
        "trường công sở/dịch vụ. Không thêm tiêu đề, không thêm dòng nào khác."
    )
    result = with_backoff(
        lambda: gateway.run(
            # Rộng tay vì model SUY LUẬN xuất cả chuỗi suy nghĩ trước khi tới các
            # dòng bối cảnh — cùng bài học với `writer.write_slot`: trần quá hẹp
            # thì bị cắt giữa phần thinking, và cái cắt đó không hiện ra như lỗi.
            LLMRequest(system=prompt, user=f"Sinh {count} bối cảnh Part {part}.", max_tokens=4000),
            feature="exam_plan",
            tier=tier,
        ),
        tries=writer.RETRY_TRIES,
        delay=writer.RETRY_DELAY,
    )
    scenes = [line.strip() for line in result.text.splitlines() if line.strip()]
    if len(scenes) != count:
        raise ValueError(f"cần đúng {count} bối cảnh Part {part}, model trả {len(scenes)}")
    # Model hay thêm tiền tố đánh số ("1. …", "1) …") — bỏ đi để context sạch.
    import re as _re

    return [_re.sub(r"^\d+[.)]\s*", "", scene) for scene in scenes]


def _override_contexts(plan: Blueprint, scenes: list[str]) -> None:
    """Thay bối cảnh cho từng ô mà KHÔNG đụng cấu trúc.

    Scene của model đi theo THỨ TỰ ô trong part; `merge` sắp lại theo `id` nên
    phải khớp đúng slot bằng cách duyệt plan đã dựng chứ không duyệt danh sách
    đầu vào."""
    slots = [slot for part_plan in plan.parts for slot in part_plan.slots]
    for slot, scene in zip(slots, scenes, strict=True):
        slot.context = scene


def generate_part_graphics(gateway: Gateway, tier: Tier, part: int) -> list[str]:
    """Hỏi model sinh brief hình MỚI cho các vị trí graphic của part (3, 4, 7).

    Chỉ sinh `graphic`/`passages` — brief `kind: mô tả` — KHÔNG đụng vị trí hay
    cấu trúc (cụm nào có hình, câu hỏi về hình ở câu thứ mấy, kind nào hợp lệ).
    Vị trí là quyết định của người ra đề (đề thật: Part 3 ba hình ở ba cụm cuối,
    Part 4 hai hình, Part 7 năm passage hình rải trong bốn cụm); model chỉ làm
    nội dung hình khác nhau để hai đề không dùng đúng một bộ hình.

    Đầu ra mỗi dòng một brief `kind: mô tả`; sai số lượng hay sai kind thì NÉM để
    `cmd_plan` rơi về `PART*_GRAPHIC_POOL` theo seed.
    """
    from app.content.exam.graphics import KINDS
    from app.services.llm.base import LLMRequest

    count = {3: 3, 4: 2, 7: 5}[part]
    kinds = ", ".join(KINDS)
    prompt = (
        f"Viết CHÍNH XÁC {count} dòng, mỗi dòng là BRIEF cho một hình ngữ liệu "
        f"của Part {part} đề TOEIC (đề tự sinh, không phải đề thi thật).\n"
        f"Mỗi dòng đúng định dạng `kind: mô tả bằng tiếng Việt`.\n"
        f"kind phải là MỘT TRONG: {kinds}.\n"
        f"Brief phải nói rõ hình gì, bốn mục/nhãn là gì (vd `table: bảng giá bốn "
        f"gói hội viên, cột Gói và Phí`), đủ để vẽ. {count} hình KHÁC NHAU rõ "
        f"rệt về kind lẫn nội dung. Không thêm tiêu đề, không thêm dòng nào khác."
    )
    result = with_backoff(
        lambda: gateway.run(
            LLMRequest(
                system=prompt,
                user=f"Sinh {count} brief hình Part {part}.",
                max_tokens=4000,
            ),
            feature="exam_plan",
            tier=tier,
        ),
        tries=writer.RETRY_TRIES,
        delay=writer.RETRY_DELAY,
    )
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
                contexts = generate_part_scenes(gateway, Tier(args.tier), args.part)
                if args.part in (3, 4, 7):
                    graphics = generate_part_graphics(gateway, Tier(args.tier), args.part)
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
