"""Suite retrieval — đo tìm kiếm trên knowledge base thật."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.content.eval_core import CaseFailure, EvalError, SuiteReport
from app.services import embeddings
from app.services.embeddings import EmbeddingUnavailable
from app.services.knowledge import search_knowledge, sync_knowledge

# Top-K của suite retrieval — case đòi nhiều ref hơn số này là case viết hỏng
# (§2.1), không phải retriever hỏng. Đổi số này thì đổi cả dataset.
RETRIEVAL_LIMIT = 4


def _offline_embed(text: str) -> list[float]:
    """Ép đường lexical: suite này đo lexical, vector thuộc về P1."""
    del text
    raise EmbeddingUnavailable("eval offline — chỉ đo lexical")


class _NoRedis:
    """Redis giả cho eval offline — chạm vào là lỗi TO, không phải treo.

    `llm_select` không truyền user_id nên budget không bao giờ chạm Redis ở
    suite planner. Dùng client thật ở đây sẽ lặng lẽ KẾT NỐI được ở máy có
    Redis chạy (như CI) và hỏng ở máy không có — đúng loại test chập chờn theo
    môi trường (§11).
    """

    def __getattr__(self, name: str) -> Any:
        raise EvalError(f"eval offline gọi Redis.{name} — đường này phải chạy không Redis")


def _mean_or_none(xs: list[float]) -> float | None:
    """Trung bình, hoặc None khi không có quan sát nào — không có số liệu
    KHÁC đạt điểm tuyệt đối (§2.2)."""
    return sum(xs) / len(xs) if xs else None


def eval_retrieval(cases: list[dict[str, Any]], kb_dir: Path, mode: str = "lexical") -> SuiteReport:
    """Đồng bộ KB thật vào SQLite memory rồi đo Recall — top-4 phải chứa mọi ref.

    Kèm MRR trung bình để so cấu hình retrieval với nhau (lexical vs vector,
    P1.2): cổng chặn vẫn là recall từng case, MRR chỉ là số so sánh.

    - `lexical` (mặc định): ép đường lexical, offline hoàn toàn — cổng CI.
    - `vector`: đường production thật (vector trước, lexical fallback). Cần keys;
      probe hỏng là EvalError TO — không bao giờ lặng lẽ đo lexical rồi báo là vector.
    """
    if not kb_dir.is_dir():
        raise EvalError(f"không thấy thư mục KB {kb_dir}")
    if mode not in ("lexical", "vector"):
        raise EvalError(f"mode retrieval lạ: {mode!r}")
    if mode == "vector":
        # Probe một lượt embed: keys thiếu/index chết thì DỪNG ở đây. Đo tiếp
        # là rơi về lexical mà báo cáo vẫn ghi "vector" — đúng thứ §9 cấm.
        try:
            embeddings.embed_query("kiểm tra kết nối")
        except Exception as exc:  # noqa: BLE001 — mọi lý do đều thành EvalError rõ ràng
            raise EvalError(f"mode vector cần embeddings chạy được ({exc})") from exc
    engine = create_engine("sqlite:///:memory:")
    from app.core.database import Base

    Base.metadata.tables["knowledge_chunk"].create(engine)
    previous = embeddings.embed_query
    if mode == "lexical":
        embeddings.embed_query = _offline_embed
    try:
        with Session(engine) as session:
            synced = sync_knowledge(session, kb_dir)
            session.commit()
            version = f"{len(synced.created)} mục · {mode}"
            report = SuiteReport(name="retrieval", version=version)
            recalls: list[float] = []
            rrs: list[float] = []
            for case in cases:
                cid = str(case.get("id", "?"))
                report.total += 1
                rows = search_knowledge(session, str(case.get("query", "")), limit=RETRIEVAL_LIMIT)
                got = [chunk.ref for _, chunk in rows]
                raw_want = case.get("relevant_refs", [])
                if not isinstance(raw_want, list) or not raw_want:
                    report.failures.append(
                        CaseFailure(cid, "relevant_refs phải là mảng", "dataset", "invalid_dataset")
                    )
                    continue
                want = [str(r) for r in raw_want]
                if len(want) > RETRIEVAL_LIMIT:
                    report.failures.append(
                        CaseFailure(
                            cid,
                            f"đòi {len(want)} ref trong top-{RETRIEVAL_LIMIT} — case viết hỏng",
                            "dataset",
                            "too_many_refs",
                        )
                    )
                    continue
                ranks = [got.index(r) for r in want if r in got]
                recalls.append(len(ranks) / len(want))
                rrs.append(1 / (min(ranks) + 1) if ranks else 0.0)
                missing = [r for r in want if r not in got]
                if not missing:
                    report.passed += 1
                else:
                    report.failures.append(
                        CaseFailure(
                            cid, f"thiếu {missing}, top-4 là {got}", "system", "missing_refs"
                        )
                    )
            recall = _mean_or_none(recalls)
            mrr = _mean_or_none(rrs)
            if recall is None or mrr is None:
                report.summary = "recall n/a · MRR n/a"
            else:
                report.summary = f"recall {recall:.2f} · MRR {mrr:.2f}"
                report.metrics = {"recall": recall, "mrr": mrr}
    finally:
        embeddings.embed_query = previous
        engine.dispose()
    return report
