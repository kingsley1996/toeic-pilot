"""Wizard tương tác cho pipeline sinh đề — giao diện CLI thay cho chạy lẻ từng lệnh.

    uv run python -m app.content.generate_exam interact [--slug tp-form-03]

Một vòng menu trên một đề: dựng blueprint, sinh, kiểm, loại ô hỏng, vẽ hình,
cân đáp án, nạp vào database — mỗi bước đều là chính lệnh `generate_exam` mà
người ta từng phải chạy tay, chỉ là được điều khiển bằng phím mũi tên thay vì
nhớ cú pháp. TUI mỏng (questionary), mọi logic vẫn nằm ở `generate_exam.py` —
wizard này KHÔNG nhân bản một luật nào.

Hàng đợi vẫn là một TRUY VẤN trên thư mục, y như khi chạy tay: chọn một hành
động nhiều lần thì lần sau tìm thấy ít việc hơn, và thoát giữa chừng không mất
gì vì mọi hiện vật đã nằm trên đĩa.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import questionary

from app.content.generate_exam import DEFAULT_ROOT, blueprint_path

__all__ = ["run_interactive"]


@dataclass
class State:
    """Trạng thái của wizard — nhỏ, đủ để menu hiện người ta đang ở đâu."""

    slug: str = ""
    model: str = ""
    plan_done: bool = False
    wrote: int = 0
    blocked: int = 0
    flagged: int = 0
    loaded: bool = False


def _known_slugs() -> list[str]:
    return sorted(p.name for p in DEFAULT_ROOT.iterdir() if blueprint_path(p.name).exists())


def _blueprint_summary(state: State) -> str:
    plan_path = blueprint_path(state.slug)
    if not plan_path.exists():
        return "chưa có blueprint"
    import json

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    parts = plan.get("parts", [])
    shape = ", ".join(f"P{p['part']}:{len(p.get('slots', []))}" for p in parts) or "(trống)"
    return f"{plan.get('title', state.slug)} — {shape}"


def _menu(state: State) -> str:
    """Một màn menu. Trả về tên hành động người dùng chọn."""
    title = state.slug or "(chưa chọn đề)"
    summary = _blueprint_summary(state)
    model = state.model or "(mặc định theo LLM_TIER_CHEAP)"
    choices = [
        questionary.Choice(title="Chọn / tạo đề khác", value="pick"),
        questionary.Choice(title=f"Chọn model — hiện: {model}", value="model"),
        questionary.Choice(title="Dựng blueprint (plan)", value="plan"),
        questionary.Choice(title="Sinh văn bản (write)", value="write"),
        questionary.Choice(title="Kiểm tra (check)", value="check"),
        questionary.Choice(title="Loại ô hỏng (prune)", value="prune"),
        questionary.Choice(title="Cân đáp án (balance)", value="balance"),
        questionary.Choice(title="Vẽ hình ngữ liệu (graphic)", value="graphic"),
        questionary.Choice(title="Vẽ ảnh Part 1 (photo)", value="photo"),
        questionary.Choice(title="Kiểm / đẩy media (media)", value="media"),
        questionary.Choice(title="Nạp vào database (load)", value="load"),
        questionary.Choice(title="Chạy hết các bước còn thiếu", value="run_all"),
        questionary.Choice(title="Thoát", value="quit"),
    ]
    return (
        questionary.select(
            f"Đề: {title} · {summary}",
            choices=choices,
            instruction="↑↓ chọn · Enter xác nhận · Ctrl-C thoát",
        ).ask()
        or "quit"
    )


def _pick_slug(state: State) -> None:
    slugs = _known_slugs()
    choice = questionary.select(
        "Chọn đề (hoặc tạo mới)",
        choices=[
            *[questionary.Choice(title=s, value=s) for s in slugs],
            questionary.Choice(title="＋ Tạo blueprint mới", value="__new__"),
            questionary.Choice(title="← Quay lại", value="__back__"),
        ],
    ).ask()
    if choice is None or choice == "__back__":
        return
    if choice == "__new__":
        state.slug = questionary.text("Slug của đề (vd `tp-form-07`):").ask() or ""
        if state.slug:
            _run_plan(state)
        return
    state.slug = choice


def _run_plan(state: State) -> None:
    part = questionary.select(
        "Dựng blueprint cho part nào?",
        choices=[
            questionary.Choice(title="Part 1 — Photographs (6 câu)", value=1),
            questionary.Choice(title="Part 2 — Question-Response (25 câu)", value=2),
            questionary.Choice(title="Part 3 — Conversations (13 cụm)", value=3),
            questionary.Choice(title="Part 4 — Talks (10 cụm)", value=4),
            questionary.Choice(title="Part 5 — Incomplete Sentences (30 câu)", value=5),
            questionary.Choice(title="Part 6 — Text Completion (4 cụm)", value=6),
            questionary.Choice(title="Part 7 — Reading (15 cụm)", value=7),
        ],
    ).ask()
    if part is None:
        return
    seed = questionary.text("Seed (chạy lại ra cùng bố cục):", default="20260822").ask()
    from argparse import Namespace

    from app.content.generate_exam import cmd_plan

    code = cmd_plan(
        Namespace(slug=state.slug, title=None, seed=int(seed or 0), part=part, model=state.model)
    )
    state.plan_done = code == 0


def _run_write(state: State) -> None:
    if not state.slug:
        _pick_slug(state)
        return
    from argparse import Namespace

    from app.content.generate_exam import cmd_write

    limit_text = questionary.text(
        "Giới hạn số ô (0 = tất cả):", default="0", instruction="thử 2–3 ô trước"
    ).ask()
    limit = int((limit_text or "0").strip() or 0)
    code = cmd_write(
        Namespace(slug=state.slug, limit=limit, tier="t1", max_tokens=6000, model=state.model)
    )
    if code == 3:  # LLMQuotaExhausted — hạn mức ngày, chờ chứ không cày tiếp
        print("\nHết hạn mức LLM trong ngày. Chạy lại sau khi có lại hạn mức.\n")
        return
    if code == 0:
        print("\nĐã sinh xong. Chạy `check` để xem còn ô nào chặn không.\n")


def _run_check(state: State) -> None:
    if not state.slug:
        _pick_slug(state)
        return
    from argparse import Namespace

    from app.content.generate_exam import cmd_check

    verify = questionary.confirm("Đối chiếu đáp án bằng LLM (tốn lượt gọi)?", default=False).ask()
    code = cmd_check(
        Namespace(slug=state.slug, verify=bool(verify), part=None, tier="t1", model=state.model)
    )
    if code in (1, 3):
        print("\nCòn ô chặn (hoặc hết hạn mức). Dùng `prune` để loại rồi `write` lại.\n")
        state.blocked = 1
    else:
        state.blocked = 0


def _run_prune(state: State) -> None:
    if not state.slug:
        _pick_slug(state)
        return
    from argparse import Namespace

    from app.content.generate_exam import cmd_prune

    ambiguity = questionary.confirm(
        "Loại cả câu có hơn một phương án điền được (cần LLM, nhiễu)?", default=False
    ).ask()
    dry = questionary.confirm("Chạy thử (không xoá)?", default=True).ask()
    code = cmd_prune(
        Namespace(
            slug=state.slug,
            part=None,
            dry_run=bool(dry),
            ambiguity=bool(ambiguity),
            tier="t1",
            model=state.model,
        )
    )
    _ = code


def _run_simple(state: State, name: str) -> None:
    """plan/balance/graphic/photo/media — các lệnh chỉ cần slug và vài cờ nhỏ."""
    if not state.slug:
        _pick_slug(state)
        return
    from argparse import Namespace

    from app.content import generate_exam as ge

    if name == "balance":
        ge.cmd_balance(Namespace(slug=state.slug, part=None))
    elif name == "graphic":
        ge.cmd_graphic(Namespace(slug=state.slug))
    elif name == "photo":
        ge.cmd_photo(Namespace(slug=state.slug, limit=0, aspect="4:3", seed=0, greyscale=True))
    elif name == "media":
        push = questionary.confirm("Đẩy media còn thiếu lên nhà cung cấp?", default=False).ask()
        ge.cmd_media(Namespace(slug=state.slug, part=None, push=bool(push)))


def _token() -> str:
    """Token editor từ biến môi trường, hoặc hỏi."""
    env = os.environ.get("TOEIC_EDITOR_TOKEN")
    if env:
        return env
    return (
        questionary.text(
            "Token tài khoản editor:", instruction="đặt TOEIC_EDITOR_TOKEN để khỏi gõ"
        ).ask()
        or ""
    )


def _run_load(state: State) -> None:
    if not state.slug:
        _pick_slug(state)
        return
    from argparse import Namespace

    from app.content.generate_exam import cmd_load

    token = _token()
    if not token:
        print("Cần token editor để nạp. Bỏ qua.\n")
        return
    api = (
        questionary.text("URL API:", default="http://localhost:8000").ask()
        or "http://localhost:8000"
    )
    code = cmd_load(Namespace(slug=state.slug, token=token, api=api, part=None, slot=None))
    state.loaded = code == 0


def _run_all(state: State) -> None:
    """Chạy tuần tự các bước còn thiếu, dừng khi gặp chỗ cần người quyết."""
    if not state.slug:
        _pick_slug(state)
        if not state.slug:
            return
    if not blueprint_path(state.slug).exists():
        print("Chưa có blueprint — dựng Part 5 trước (lát đầu của kế hoạch).")
        _run_plan(state)
    if not state.plan_done:
        return
    if not state.model:
        _pick_model(state)

    from argparse import Namespace

    from app.content.generate_exam import cmd_check, cmd_write

    code = cmd_write(
        Namespace(slug=state.slug, limit=0, tier="t1", max_tokens=6000, model=state.model)
    )
    if code == 3:
        print("Hết hạn mức LLM. Dừng — chạy lại sau.")
        return
    code = cmd_check(
        Namespace(slug=state.slug, verify=False, part=None, tier="t1", model=state.model)
    )
    if code in (1, 3):
        print("Còn ô chặn — dùng `prune` + `write` trong menu để sửa trước khi nạp.\n")
        return
    state.blocked = 0

    ge = __import__(
        "app.content.generate_exam",
        fromlist=["cmd_balance", "cmd_graphic", "cmd_photo", "cmd_media"],
    )
    ge.cmd_balance(Namespace(slug=state.slug, part=None))
    if questionary.confirm("Chạy `media` (kiểm + đẩy)?", default=True).ask():
        ge.cmd_media(Namespace(slug=state.slug, part=None, push=True))
    if questionary.confirm("Nạp vào database (cần token editor)?", default=True).ask():
        _run_load(state)


def _pick_model(state: State) -> None:
    """Chọn model để viết/kiểm. Liệt kê `known_models()` — những model có giá."""
    from app.services.llm.pricing import known_models

    choices = [
        questionary.Choice(title="(mặc định theo LLM_TIER_CHEAP)", value=""),
        *[
            questionary.Choice(title=f"{provider}/{model}", value=f"{provider}/{model}")
            for provider, model in known_models()
        ],
        questionary.Choice(title="← Quay lại", value="__back__"),
    ]
    choice = questionary.select("Chọn model cho các bước sinh/kiểm", choices=choices).ask()
    if choice is None or choice == "__back__":
        return
    state.model = choice
    print(f"Đã chọn model: {choice or '(mặc định)'}\n")


def run_interactive(slug: str | None = None) -> int:
    """Vòng lặp chính. Trả về mã thoát cho `main()` của generate_exam."""
    state = State(slug=slug or "")
    if slug and blueprint_path(slug).exists():
        state.plan_done = True

    while True:
        try:
            action = _menu(state)
        except KeyboardInterrupt:
            print("\nTạm biệt — hiện vật vẫn trên đĩa, chạy lại tiếp tục từ đây.")
            return 0
        if action == "quit":
            return 0
        if action == "pick":
            _pick_slug(state)
        elif action == "model":
            _pick_model(state)
        elif action == "plan":
            _run_plan(state)
        elif action == "write":
            _run_write(state)
        elif action == "check":
            _run_check(state)
        elif action == "prune":
            _run_prune(state)
        elif action in ("balance", "graphic", "photo", "media"):
            _run_simple(state, action)
        elif action == "load":
            _run_load(state)
        elif action == "run_all":
            _run_all(state)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_interactive())
