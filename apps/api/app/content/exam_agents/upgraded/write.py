"""Node write: sinh/tái sinh slot bằng writer hiện có.

Writer vẫn là business logic hiện có. Graph chỉ điều phối và đưa revision
context (qua adapter từ evaluate) vào writer.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.content.exam.writer import MissingBlock, max_tokens_for, save_slot, write_slot
from app.content.exam_agents.upgraded.evaluate import _revision_prompt_adapter
from app.content.exam_agents.upgraded.findings import _content_hash, _now_iso
from app.content.exam_agents.upgraded.state import (
    DEFAULT_MAX_TOKENS,
    ArtifactVersion,
    Node,
    NodeUpdate,
    SlotState,
    _Parts,
)
from app.services.llm.gateway import Gateway
from app.services.llm.router import Tier


def _write_node(
    gateway: Gateway,
    tier: Tier,
    workdir: Path,
    parts: _Parts,
    max_tokens: int | None = DEFAULT_MAX_TOKENS,
) -> Node:
    """Generate/re-generate slot.

    Writer vẫn là business logic hiện có. Graph chỉ điều phối và đưa revision
    context vào writer.
    """

    def write(state: SlotState) -> NodeUpdate:
        from app.content.exam.writer import GRAPHIC_MARKER, split_all, split_photo
        from app.services.llm.base import LLMError, LLMQuotaExhausted

        slot = parts.slot(state["slot_id"])
        part = parts.part(state["slot_id"])

        revision = state.get("revision", 0) + 1
        plan = state.get("revision_plan")
        hint = _revision_prompt_adapter(plan)

        metrics = dict(state.get("metrics", {}))
        metrics["revisions"] = revision
        metrics["llm_calls"] = metrics.get("llm_calls", 0) + 1

        update: NodeUpdate = {
            "revision": revision,
            "part": part,
            "status": "writing",
            "blocked": False,
            "fatal": False,
            "findings": [],
            "previous_findings": state.get("findings", []),
            "fix_hint": hint,
            "metrics": metrics,
        }

        started = perf_counter()

        try:
            block = write_slot(
                gateway,
                slot,
                tier,
                part,
                fix_hint=hint,
                max_tokens=max_tokens or max_tokens_for(part, slot),
            )

        except LLMQuotaExhausted:
            # Đây là run-level failure. Không giả vờ rằng revision có thể cứu quota.
            raise

        except LLMError as failure:
            # Transport/model failure sau khi with_backoff đã thử đủ lần.
            # Không đưa vào critic loop.
            update |= {
                "draft": "",
                "blocked": True,
                "fatal": True,
                "outcome": "escalated",
                "status": "escalated",
                "findings": [
                    {
                        "code": "LLM_ERROR",
                        "severity": "error",
                        "category": "infrastructure",
                        "location": "write",
                        "message": str(failure),
                    }
                ],
                "log": [
                    f"vòng {revision}: LLM error: {failure}"
                ],
            }
            return update

        except MissingBlock as cut:
            # Đây là content-generation failure: có thể thử revision.
            update |= {
                "draft": "",
                "blocked": True,
                "fatal": False,
                "findings": [
                    {
                        "code": "MISSING_BLOCK",
                        "severity": "error",
                        "category": "structure",
                        "location": "slot",
                        "message": str(cut),
                        "suggested_fix": (
                            "Viết ngắn hơn, đi thẳng vào block và không bỏ dở "
                            "ở giữa nội dung bắt buộc."
                        ),
                    }
                ],
                "fix_hint": (
                    "Bị cắt giữa phần suy luận — viết ngắn hơn, đi thẳng vào khối."
                ),
                "log": [
                    f"vòng {revision}: {cut}"
                ],
            }
            return update

        elapsed_ms = (perf_counter() - started) * 1000
        metrics["latency_ms"] = metrics.get("latency_ms", 0.0) + elapsed_ms

        # Persist artifact immediately, giống pipeline cũ.
        photo, block = split_photo(block)

        if photo:
            photo_path = workdir / "photos" / f"{slot.id}.txt"
            photo_path.parent.mkdir(parents=True, exist_ok=True)
            photo_path.write_text(photo + "\n")

        tables, block = split_all(block, GRAPHIC_MARKER)

        for order, table in enumerate(tables, start=1):
            suffix = "" if len(tables) == 1 else f"-{order}"
            table_path = workdir / "graphics" / f"{slot.id}{suffix}.txt"
            table_path.parent.mkdir(parents=True, exist_ok=True)
            table_path.write_text(table + "\n")

        save_slot(workdir, slot, block)

        artifact: ArtifactVersion = {
            "revision": revision,
            "path": str(workdir),
            "content_hash": _content_hash(block),
            "created_at": _now_iso(),
            "status": "draft",
        }

        # GIỮ `update`: nó mang revision/metrics vừa tính. Trả literal mới ở
        # đây là vứt cả hai — revision kẹt ở 0, verdict không bao giờ tới trần
        # và graph quay vô hạn ở đúng đường chính (viết được nhưng còn lỗi).
        return {
            **update,
            "draft": block,
            "blocked": False,
            "fatal": False,
            "status": "validating",
            "outcome": "pending",
            "findings": [],
            "revision_plan": None,
            "fix_hint": None,
            "artifacts": state.get("artifacts", []) + [artifact],
            "log": [
                f"vòng {revision}: write xong ({elapsed_ms / 1000:.1f}s)"
            ],
        }

    return write
