"""Nền chung của bộ eval AI — lỗi, báo cáo, nạp case, ngưỡng, report.

Không gọi model, không chạm database: mọi suite (`eval_suites.*`) dựng trên
lớp này. Đổi ở đây ảnh hưởng mọi suite, nên đổi thận trọng.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.services.llm.prompts import load

# Mọi suite eval, một chỗ duy nhất. Route admin đọc ở đây chứ không import
# `eval_ai` — module đó kéo theo `eval_suites` tức `app.content`, mà chuỗi
# import của `app/main.py` cấm điều đó (PHASE2-AUDIO §A4.1).
SUITES = ("coach", "shape", "retrieval", "planner", "exam")

# Case hỏng vì dataset viết sai KHÁC system hỏng vì sản phẩm sai. Gộp hai thứ
# thì một case viết hỏng trông như regression của model (§2.3).
FailureKind = Literal["dataset", "system", "judge", "infrastructure"]


class EvalError(RuntimeError):
    """Case hay cấu hình hỏng — lỗi của người viết eval, không phải của hệ thống."""


@dataclass(slots=True)
class CaseFailure:
    id: str
    detail: str
    kind: FailureKind = "system"
    # Mã máy đọc được để group-by về sau (vd wrong_correct_answer). `detail`
    # giữ cho người đọc; `code` cho báo cáo tổng hợp. Rỗng nghĩa là chưa phân loại.
    code: str = ""


@dataclass(slots=True)
class SuiteReport:
    name: str
    passed: int = 0
    total: int = 0
    failures: list[CaseFailure] = field(default_factory=list)
    version: str = ""
    # Dòng tóm tắt metric riêng của suite (vd recall/MRR) — in kèm, không chặn.
    summary: str = ""
    # Số máy đọc được, để so baseline (§4): {"recall": 1.0, "mrr": 0.92}.
    metrics: dict[str, float] = field(default_factory=dict)


def load_cases(path: Path, required: set[str]) -> list[dict[str, Any]]:
    """Đọc JSONL, mỗi dòng một case. Hỏng ở dòng nào thì nói đúng dòng đó."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvalError(f"không đọc được {path}: {exc}") from exc
    cases: list[dict[str, Any]] = []
    for lineno, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except ValueError as exc:
            raise EvalError(f"{path}:{lineno}: không phải JSON ({exc})") from exc
        if not isinstance(data, dict):
            raise EvalError(f"{path}:{lineno}: mỗi dòng phải là một object")
        missing = required - set(data)
        if missing:
            raise EvalError(f"{path}:{lineno}: thiếu {sorted(missing)}")
        cases.append(data)
    if not cases:
        raise EvalError(f"{path}: không có case nào")
    return cases


def _verdict(
    cid: str, expect_pass: bool, expect_subs: list[str], actual: list[str]
) -> CaseFailure | None:
    """So kết quả thật với kỳ vọng của case. `None` nghĩa là case đúng như viết."""
    if expect_pass:
        if not actual:
            return None
        return CaseFailure(cid, f"tưởng đạt mà rớt: {'; '.join(actual)}")
    if not actual:
        return CaseFailure(cid, "tưởng rớt mà đạt")
    joined = " ".join(actual)
    missing = [s for s in expect_subs if s not in joined]
    if missing:
        return CaseFailure(cid, f"rớt sai chỗ (thiếu {missing}): {joined}")
    return None


def _prompt_version(name: str) -> str:
    try:
        return load(name).version
    except Exception:  # noqa: BLE001 — mọi lý do đều thành "unknown"
        return "unknown"


def load_thresholds(path: Path) -> dict[str, float]:
    """Ngưỡng chặn theo suite — thiếu entry nghĩa là đòi 100%."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvalError(f"không đọc được {path}: {exc}") from exc
    except ValueError as exc:
        raise EvalError(f"{path}: không phải JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise EvalError(f"{path}: phải là một object")
    out: dict[str, float] = {}
    for key, value in data.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvalError(f"{path}: ngưỡng {key!r} phải là số")
        out[str(key)] = float(value)
    return out


def _git_sha() -> str:
    """SHA ngắn của HEAD — fail-soft vì eval phải chạy được cả ngoài git."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except Exception:  # noqa: BLE001 — mọi lý do đều thành "unknown"
        return "unknown"
    return out.stdout.strip() or "unknown"


def _dataset_hashes(datasets: Path) -> dict[str, str]:
    """SHA256 từng tệp dataset — report nào cũng truy được nó chấm cái gì."""
    hashes: dict[str, str] = {}
    for name in ("coach_explain", "explanation_shape", "retrieval", "planner"):
        path = datasets / f"{name}.jsonl"
        try:
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        except OSError:
            hashes[name] = "missing"
    return hashes


def _manifest_status(datasets: Path) -> tuple[str, bool]:
    """Version manifest + khớp hay không. Không khớp là warning, không phải chặn:
    dataset đang sửa dở mà chặn CI thì không ai dám thêm case."""
    try:
        manifest = json.loads((datasets / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "none", True
    if not isinstance(manifest, dict):
        return "broken", False
    pinned = manifest.get("files", {})
    current = _dataset_hashes(datasets)
    match = bool(pinned) and all(pinned.get(k) == v for k, v in current.items())
    return str(manifest.get("version", "unknown")), match


def write_manifest(datasets: Path) -> Path:
    """Ghim hash dataset hiện tại — chạy sau khi thêm/sửa case xong."""
    from datetime import date

    target = datasets / "manifest.json"
    target.write_text(
        json.dumps(
            {"version": date.today().isoformat(), "files": _dataset_hashes(datasets)},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def _report_json(
    reports: list[SuiteReport],
    *,
    against: str | None,
    suite_arg: str,
    floors: dict[str, float],
    datasets: Path,
) -> dict[str, Any]:
    """Report reproducible (§5): đọc report này là biết đã chấm cái gì,
    bằng gì, trên mã nào — không cần hỏi người chạy."""
    manifest_version, manifest_match = _manifest_status(datasets)
    return {
        "run": {
            "id": uuid.uuid4().hex[:12],
            "at": datetime.now(UTC).isoformat(),
            "git_sha": _git_sha(),
            "suite_arg": suite_arg,
            "against": against,
            "thresholds": floors,
        },
        "datasets": {
            "hashes": _dataset_hashes(datasets),
            "manifest_version": manifest_version,
            "manifest_match": manifest_match,
        },
        "suites": [
            {
                "name": r.name,
                "version": r.version,
                "summary": r.summary,
                "metrics": r.metrics,
                "passed": r.passed,
                "total": r.total,
                "failures": [{"id": f.id, "kind": f.kind, "detail": f.detail} for f in r.failures],
            }
            for r in reports
        ],
    }


def diff_against(baseline: dict[str, Any], reports: list[SuiteReport]) -> tuple[list[str], bool]:
    """So lượt chạy hiện tại với một report baseline (§4).

    Trả về (các dòng in, có_case_mới_rớt). Case rớt MỚI là regression và chặn;
    case đã hết rớt chỉ là tin tốt để đọc. Delta metric chỉ là số so sánh —
    chặn tuyệt đối vẫn do ngưỡng (--fail-under) quyết.
    """
    raw_suites = baseline.get("suites", [])
    old: dict[str, dict[str, Any]] = (
        {s["name"]: s for s in raw_suites} if isinstance(raw_suites, list) else {}
    )
    lines: list[str] = []
    new_failures = False
    for report in reports:
        prev = old.get(report.name)
        if not isinstance(prev, dict):
            lines.append(f"[{report.name}] chưa có baseline — bỏ qua so sánh")
            continue
        old_ids = {f["id"] for f in prev.get("failures", []) if isinstance(f, dict)}
        new_ids = {f.id for f in report.failures}
        fresh = sorted(new_ids - old_ids)
        fixed = sorted(old_ids - new_ids)
        if fresh:
            new_failures = True
        old_total = int(prev.get("total", 0) or 0)
        old_passed = int(prev.get("passed", 0) or 0)
        line = f"[{report.name}] {old_passed}/{old_total} → {report.passed}/{report.total}"
        old_metrics = prev.get("metrics", {})
        if isinstance(old_metrics, dict) and old_metrics and report.metrics:
            deltas = " · ".join(
                f"{k} {float(old_metrics.get(k, 0.0)):.2f}→{v:.2f}"
                for k, v in sorted(report.metrics.items())
            )
            line += f" · {deltas}"
        if not fresh and not fixed:
            line += " (không đổi)"
        lines.append(line)
        for cid in fresh:
            lines.append(f"  MỚI RỚT: {cid}")
        for cid in fixed:
            lines.append(f"  đã hết rớt: {cid}")
    return lines, new_failures


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvalError(f"không đọc được baseline {path}: {exc}") from exc
    except ValueError as exc:
        raise EvalError(f"baseline {path} không phải JSON ({exc})") from exc
    if not isinstance(data, dict) or "suites" not in data:
        raise EvalError(f"baseline {path} thiếu 'suites'")
    return data
