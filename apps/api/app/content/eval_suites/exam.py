"""Suite exam — replay cổng kiểm trên paste golden, không gọi model.

Mỗi case: dựng blueprint thật (builders của pipeline), dán paste ghi sẵn vào
workdir riêng, chạy đúng `check_blueprint` mà lệnh `check` và node `check` của
đồ thị chạy (tầng miễn phí, `gateway=None`). Đổi parser/luật kiểm mà hành vi
đổi thì case đỏ — hồi quy cho `exam/check.py` mà không tốn một lượt gọi nào.

Cố ý KHÔNG dùng chung workdir giữa các case: phép dò trùng là chuyện giữa các
ô, nên hai case trong một workdir sẽ dính nhau mà không liên quan gì tới luật
đang đo. Mỗi case một thư mục tạm, một ô, một kết luận.
"""

from __future__ import annotations

import hashlib
import inspect
import tempfile
from pathlib import Path
from typing import Any

from app.content.eval_core import CaseFailure, EvalError, SuiteReport
from app.content.exam import blueprint as bp
from app.content.exam.blueprint import Blueprint, PartPlan
from app.content.exam.check import check_blueprint
from app.content.exam.writer import save_slot


def _check_version() -> str:
    """Version của suite = hash chính `check.py` — đổi luật kiểm thì version
    đổi, và report nào cũng truy được nó chấm bằng bản luật nào."""
    source = Path(inspect.getsourcefile(check_blueprint) or "")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    return f"exam_check@{digest}"


def _question_count(paste: str) -> int:
    return sum(1 for line in paste.splitlines() if line.strip() == "[QUESTION]")


def _passage_count(paste: str) -> int:
    return sum(1 for line in paste.splitlines() if line.strip() == "[PASSAGE]")


def _blueprint_for(
    part: int, want_questions: int, want_passages: int, seed: int = 7
) -> tuple[Blueprint, Any]:
    """Một part, một ô KHỚP paste: đủ số câu, không hàm ý, không hình, chữ thuần.

    Khớp số câu với `len(slot.question_types)` vì cổng đếm theo đó
    (`parse_group(..., len(slot.question_types), ...)`). Đây là dựng khung,
    không phải chấm hộ: cùng việc pipeline làm khi giao ô cho người viết.
    """
    builders: dict[int, Any] = {
        1: bp.build_part1,
        2: bp.build_part2,
        5: lambda slug, title, seed: bp.build_part5(slug, title, seed, count=3),
        3: bp.build_part3,
        4: bp.build_part4,
        6: bp.build_part6,
        7: bp.build_part7,
    }
    if part not in builders:
        raise EvalError(f"part lạ: {part}")
    plan = builders[part]("eval", "E", seed=seed)
    for slot in plan.parts[0].slots:
        types = slot.question_types or []
        if part in (3, 4, 6, 7):
            if len(types) != want_questions:
                continue
            if slot.graphic or any("IMPLICATION" in t for t in types):
                continue
            if part == 7:
                # Paste thuần chữ chỉ khớp ô thuần chữ: spec nào không rỗng là
                # một đoạn VẼ, và cổng đòi tệp hình của nó ("cần 1 hình, có 0").
                specs = slot.passages or []
                if any(specs) or len(specs) != want_passages:
                    continue
        return plan, slot
    raise EvalError(f"không tìm được ô part {part} {want_questions} câu (không hàm ý, không hình)")


def _paste_for(part: int, slot: Any, paste: str) -> str:
    """Khớp giọng Part 1 với ô đã chọn — như test chuẩn đang làm."""
    if part == 1 and slot.voice:
        lines = paste.splitlines()
        return "\n".join(
            (f"voice: {slot.voice}" if line.startswith("voice:") else line) for line in lines
        )
    return paste


def eval_exam(cases: list[dict[str, Any]]) -> SuiteReport:
    report = SuiteReport(name="exam", version=_check_version())
    for case in cases:
        cid = str(case.get("id", "?"))
        report.total += 1
        try:
            part = int(case.get("part", 0))
            paste = str(case.get("paste", ""))
            seed = case.get("seed", 7)
            _, slot = _blueprint_for(
                part, _question_count(paste), _passage_count(paste), int(seed) if seed else 7
            )
            plan = Blueprint(
                slug="eval", title="E", seed=7, parts=[PartPlan(part=part, slots=[slot])]
            )
            paste = _paste_for(part, slot, str(case.get("paste", "")))
            with tempfile.TemporaryDirectory(prefix="eval-exam-") as tmp:
                workdir = Path(tmp)
                save_slot(workdir, slot, paste)
                photo = case.get("photo")
                if photo:
                    photos = workdir / "photos"
                    photos.mkdir(exist_ok=True)
                    (photos / f"{slot.id}.txt").write_text(
                        str(photo).strip() + "\n", encoding="utf-8"
                    )
                reports = check_blueprint(plan, workdir, gateway=None, quiet=True)
                mine = [r for r in reports if r.slot_id == slot.id]
                if not mine:
                    report.failures.append(
                        CaseFailure(cid, "check không đọc được ô này", "dataset")
                    )
                    continue
                problems = [p for r in mine for p in r.problems]
        except (EvalError, ValueError, KeyError) as exc:
            report.failures.append(CaseFailure(cid, f"case dựng hỏng: {exc}", "dataset"))
            continue
        if bool(case.get("expect_blocked", False)) != bool(problems):
            state = "tưởng qua mà chặn" if problems else "tưởng chặn mà qua"
            report.failures.append(
                CaseFailure(cid, f"{state}: {'; '.join(problems) or 'sạch'}", "system")
            )
            continue
        subs = [str(s) for s in case.get("expect_problems", []) or []]
        joined = " ".join(problems)
        missing = [s for s in subs if s not in joined]
        if missing:
            report.failures.append(
                CaseFailure(cid, f"thiếu vấn đề chờ đợi {missing}: {joined}", "system")
            )
        else:
            report.passed += 1
    return report
