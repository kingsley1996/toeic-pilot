"""Sinh một đề TOEIC — bốn chặng, chạy riêng từng chặng.

    uv run python -m app.content.generate_exam plan  --slug tp-form-03
    uv run python -m app.content.generate_exam write --slug tp-form-03 [--limit 3]
    uv run python -m app.content.generate_exam check --slug tp-form-03 [--verify]
    uv run python -m app.content.generate_exam load  --slug tp-form-03 --token <editor token>

Chạy NGOÀI LUỒNG, trong image worker: `app.content` không bao giờ được import từ
`app/main.py`, và ảnh production build không có extra `content`.

Mỗi chặng đọc và ghi tệp dưới `content/generated/<slug>/`, nên chạy lại chặng sau
không phải trả tiền lại cho chặng trước. Một lượt sinh cả đề tốn hàng chục phút
và SẼ đứt — hết quota, mất mạng, máy ngủ.

Mười ba lệnh con nằm ở `app/content/exam_cli/`, chia theo việc: `plan`,
`authoring`, `media`, `load`. Tệp này giữ đúng một vai — argparse và `main()` —
để đường gọi tài liệu ghi không đổi khi các lệnh dời chỗ.
"""

from __future__ import annotations

import argparse

from app.content.exam import writer
from app.content.exam_cli.authoring import (
    cmd_balance,
    cmd_check,
    cmd_prompt,
    cmd_prune,
    cmd_write,
)
from app.content.exam_cli.load import cmd_interact, cmd_load
from app.content.exam_cli.media import cmd_attach_images, cmd_graphic, cmd_media, cmd_photo
from app.content.exam_cli.paths import DEFAULT_ROOT, blueprint_path, workdir_for
from app.content.exam_cli.plan import cmd_plan
from app.content.settings import content_settings
from app.services.llm.router import Tier

# Các lệnh được xuất lại có chủ ý: `generate_exam` là CỬA TRƯỚC của nhóm lệnh
# này, và `exam_wizard` gọi chúng qua chính module này (`ge.cmd_photo`). Không
# xuất thì mỗi nơi gọi phải biết lệnh nằm ở module con nào — đúng thứ việc tách
# tệp không được phép bắt người dùng gánh.
__all__ = [
    "DEFAULT_ROOT",
    "blueprint_path",
    "cmd_attach_images",
    "cmd_balance",
    "cmd_check",
    "cmd_prompt",
    "cmd_graphic",
    "cmd_interact",
    "cmd_load",
    "cmd_media",
    "cmd_photo",
    "cmd_plan",
    "cmd_prune",
    "cmd_write",
    "main",
    "workdir_for",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sinh một đề TOEIC.")
    parser.add_argument("--tier", default=Tier.CHEAP.value, choices=[tier.value for tier in Tier])
    sub = parser.add_subparsers(dest="command", required=True)

    plan_cmd = sub.add_parser("plan", help="dựng blueprint")
    plan_cmd.add_argument("--slug", required=True)
    plan_cmd.add_argument("--title")
    plan_cmd.add_argument("--seed", type=int, default=20260822)
    plan_cmd.add_argument("--part", type=int, default=5, choices=(1, 2, 3, 4, 5, 6, 7))
    plan_cmd.add_argument(
        "--model",
        default=None,
        help="provider/model cho Part 1 (vd `bai/glm-5.3-flash`) — sinh 6 bối cảnh; "
        "bỏ trống thì dùng PART1_MIX",
    )
    plan_cmd.set_defaults(func=cmd_plan)

    write_cmd = sub.add_parser("write", help="sinh tệp dán cho các ô còn thiếu")
    write_cmd.add_argument("--slug", required=True)
    write_cmd.add_argument("--limit", type=int, default=0)
    write_cmd.add_argument(
        "--max-tokens",
        type=int,
        default=writer.DEFAULT_MAX_TOKENS,
        help="trần đầu ra mỗi lượt gọi; model suy luận cần rộng, hạn mức TPM lại cần hẹp",
    )
    write_cmd.add_argument(
        "--model",
        default=None,
        help="provider/model (vd `bai/gpt-5.6-sol`). Xem known_models() hoặc wizard interact",
    )
    write_cmd.set_defaults(func=cmd_write)

    balance_cmd = sub.add_parser("balance", help="cân lại vị trí đáp án trên cả đề")
    balance_cmd.add_argument("--slug", required=True)
    balance_cmd.add_argument("--part", type=int, default=None, help="chỉ cân một part")
    balance_cmd.set_defaults(func=cmd_balance)

    photo_cmd = sub.add_parser("photo", help="vẽ ảnh Part 1 từ phần mô tả")
    photo_cmd.add_argument("--slug", required=True)
    photo_cmd.add_argument("--limit", type=int, default=0)
    photo_cmd.add_argument("--aspect", default="4:3")
    # Vẽ lại một tấm bị loại cần một seed KHÁC. Không có cờ này thì xoá tệp rồi
    # chạy lại cho ra đúng tấm ảnh vừa bị loại — hàng đợi làm đúng việc của nó,
    # và người chạy tưởng lệnh hỏng.
    photo_cmd.add_argument("--seed", type=int, default=0)
    # Đen trắng là MẶC ĐỊNH vì đề thi thật in đen trắng; màu là một manh mối mà
    # phòng thi không cho. Cờ tắt tồn tại để xem bản màu khi soi bố cục.
    photo_cmd.add_argument("--no-greyscale", dest="greyscale", action="store_false")
    photo_cmd.set_defaults(greyscale=True)
    photo_cmd.set_defaults(func=cmd_photo)

    media_cmd = sub.add_parser("media", help="media của đề đã lên nhà cung cấp chưa")
    media_cmd.add_argument("--slug", required=True)
    media_cmd.add_argument("--part", type=int, default=None)
    media_cmd.add_argument("--push", action="store_true", help="đẩy nốt phần còn thiếu")
    media_cmd.set_defaults(func=cmd_media)

    graphic_cmd = sub.add_parser("graphic", help="vẽ hình ngữ liệu Part 3/4 từ dữ liệu bảng")
    graphic_cmd.add_argument("--slug", required=True)
    graphic_cmd.set_defaults(func=cmd_graphic)

    attach_cmd = sub.add_parser("attach-images", help="gắn ảnh tự sinh vào đề đã nạp")
    attach_cmd.add_argument("--slug", required=True)
    attach_cmd.add_argument("--part", type=int, choices=(1, 3, 4, 7), default=None)
    attach_cmd.add_argument(
        "--commit", action="store_true", help="ghi vào DB (mặc định: chỉ in bảng khớp)"
    )
    attach_cmd.add_argument("--source-url", default=None)
    attach_cmd.add_argument("--license", default=None)
    attach_cmd.add_argument("--attribution", default=None)
    attach_cmd.add_argument("--alt-text", default=None)
    attach_cmd.add_argument("--overwrite", action="store_true")
    attach_cmd.set_defaults(func=cmd_attach_images)

    prompt_cmd = sub.add_parser("prompt", help="in prompt sẽ gửi đi cho một ô")
    prompt_cmd.add_argument("--slug", required=True)
    prompt_cmd.add_argument("--slot", required=True, help="id của ô, vd `p4-09`")
    prompt_cmd.set_defaults(func=cmd_prompt)

    check_cmd = sub.add_parser("check", help="kiểm tệp dán")
    check_cmd.add_argument("--slug", required=True)
    check_cmd.add_argument("--verify", action="store_true", help="đối chiếu đáp án bằng LLM")
    check_cmd.add_argument("--part", type=int, default=None, help="chỉ kiểm một part")
    check_cmd.add_argument(
        "--model",
        default=None,
        help="provider/model (vd `bai/gpt-5.6-sol`). Xem known_models() hoặc wizard interact",
    )
    check_cmd.set_defaults(func=cmd_check)

    prune_cmd = sub.add_parser("prune", help="xoá tệp dán của những ô không đạt")
    prune_cmd.add_argument("--slug", required=True)
    prune_cmd.add_argument("--part", type=int, default=None, help="chỉ loại trong một part")
    prune_cmd.add_argument("--dry-run", action="store_true")
    prune_cmd.add_argument(
        "--ambiguity", action="store_true", help="loại cả câu có hơn một phương án điền được"
    )
    prune_cmd.add_argument(
        "--model",
        default=None,
        help="provider/model (vd `bai/gpt-5.6-sol`). Xem known_models() hoặc wizard interact",
    )
    prune_cmd.set_defaults(func=cmd_prune)

    load_cmd = sub.add_parser("load", help="nạp vào database qua đường dán")
    load_cmd.add_argument("--slug", required=True)
    load_cmd.add_argument("--token", required=True, help="token của một tài khoản editor")
    load_cmd.add_argument("--api", default="http://localhost:8000")
    load_cmd.add_argument("--part", type=int, default=None, help="chỉ nạp một part")
    load_cmd.add_argument(
        "--slot", default=None, help="chỉ nạp một ô (vd `p2-01`), lấp vào số câu còn trống"
    )
    load_cmd.set_defaults(func=cmd_load)

    interact_cmd = sub.add_parser(
        "interact",
        help="wizard tương tác: điều khiển cả pipeline bằng menu",
    )
    interact_cmd.add_argument(
        "--slug", default=None, help="đề muốn làm; bỏ trống thì chọn lúc chạy"
    )
    interact_cmd.set_defaults(func=cmd_interact)

    args = parser.parse_args(argv)
    _ = content_settings  # giữ cùng khuôn khởi động với các lệnh content khác
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
