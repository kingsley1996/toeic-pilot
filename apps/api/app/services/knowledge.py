"""Knowledge base của TOEIC Pilot — đồng bộ từ file, và phép tra cho Trợ lý.

Nội dung là NỘI DUNG nên nằm trong git (`apps/api/content/kb/*.md`, frontmatter
`ref`/`title`/`keywords`); bảng `knowledge_chunk` là bản đã tính sẵn cho
retrieval — cùng quan hệ "nguồn ↔ hàng" với manifest audio.

Phép tra hôm nay là LEXICAL trong Python: trùng token giữa câu hỏi với
(title×3, keywords×4, content×1), cộng một lượt so sánh bỏ dấu để câu hỏi gõ
thiếu dấu vẫn khớp. Cố ý như vậy chứ không phải thiếu hiểu biết:

- `ponytail:` trần thật của phép tra này là một corpus vài chục–vài trăm chunk
  do NGƯỜI viết, khi đó signal (từ khoá, tiêu đề) có kiểm soát. Corpus vượt
  trần hoặc là nội dung máy sinh → thêm cột `embedding vector(1024)` (quyết
  định đã ghi ở ADR-003) cộng một lớp scoring vector; mọi nơi gọi ở đây chỉ
  đổi thân hàm `search`, không đổi chữ ký.
- Không dùng Postgres FTS: tiếng Việt không có từ điển stem sẵn, còn phép tra
  trong Python chạy được Y HẾT trên SQLite của bộ test — một bản cài, hai nơi
  chứng minh.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk
from app.services.vector_store import VectorMatch

logger = logging.getLogger(__name__)

__all__ = ["Synced", "parse_kb_file", "search_knowledge", "sync_knowledge"]

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _strip_diacritics(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )


def _tokens(text: str) -> set[str]:
    """Token hóa thô: chữ/số, chữ thường, ở CẢ HAI dạng có và không dấu."""
    words = set(re.findall(r"[^\W_]+", text.lower(), re.UNICODE))
    return words | {_strip_diacritics(w) for w in words}


def parse_kb_file(path: Path) -> dict[str, str]:
    """Đọc frontmatter `ref`/`title`/`keywords` + thân; thiếu ref là file hỏng."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        raise ValueError(f"{path.name}: thiếu frontmatter ---")
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    if not meta.get("ref"):
        raise ValueError(f"{path.name}: thiếu ref trong frontmatter")
    meta.setdefault("title", path.stem)
    meta.setdefault("keywords", "")
    meta["content"] = text[match.end() :].strip()
    return meta


@dataclass(slots=True)
class Synced:
    updated: list[str]
    created: list[str]
    removed: list[str]


def sync_knowledge(db: Session, directory: Path) -> Synced:
    """Đồng bộ bảng từ thư mục markdown: upsert theo `ref`, xoá ref mất nguồn.

    KHÔNG commit — caller quyết định: đường thật commit, dry-run của `sync_kb`
    rollback. Tự commit ở đây là thứ từng biến dry-run thành một lượt ghi thật.
    """
    files = {
        meta["ref"]: meta for meta in (parse_kb_file(p) for p in sorted(directory.glob("*.md")))
    }
    existing = {chunk.ref: chunk for chunk in db.scalars(select(KnowledgeChunk))}
    synced = Synced(updated=[], created=[], removed=[])

    for ref, meta in files.items():
        row = existing.get(ref)
        if row is None:
            db.add(
                KnowledgeChunk(
                    ref=ref, title=meta["title"], keywords=meta["keywords"], content=meta["content"]
                )
            )
            synced.created.append(ref)
        elif (row.title, row.keywords, row.content) != (
            meta["title"],
            meta["keywords"],
            meta["content"],
        ):
            row.title, row.keywords, row.content = meta["title"], meta["keywords"], meta["content"]
            synced.updated.append(ref)

    for ref in set(existing) - set(files):
        db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.ref == ref))
        synced.removed.append(ref)

    return synced


def search_knowledge(
    db: Session, query: str, *, limit: int = 4, min_score: float = 0.25
) -> list[tuple[float, KnowledgeChunk]]:
    """Tra các chunk khớp câu hỏi, mạnh nhất trước; dưới ngưỡng là không có.

    Hai đường, và cả hai đều phải sống được một mình:

    - **Vector** (Pinecone + embeddings Google) — chính, khi hai khoá đều có.
      Semantic matching là thứ lexical không có: "thang điểm" khớp "quy đổi
      điểm số" dù không một token nào trùng.
    - **Lexical** (Python, bên dưới) — phương dự phòng. Mất khoá, nhà cung cấp
      sập, index chưa dựng: log warning và rơi xuống đây. Trợ lý trả lời được
      bằng cách nào đó là quan trọng hơn trả lời bằng cách đẹp nhất.

    Ngưỡng `min_score` chỉ áp cho đường lexical — score của Pinecone là phép
    so sánh vector, không cùng một thang.
    """
    vector_matches = _search_vector(query, limit)
    if vector_matches is not None:
        refs = [m.ref for m in vector_matches]
        by_ref = {
            chunk.ref: chunk
            for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.ref.in_(refs)))
        }
        mapped = [(m.score, by_ref[m.ref]) for m in vector_matches if m.ref in by_ref][:limit]
        if mapped:
            return mapped
        # Vector trả ref nhưng bảng không còn (xoá file mà chưa embed lại, hay
        # index trống): lexical vẫn hơn trả rỗng.
    return _search_lexical(db, query, limit, min_score)


def _search_vector(query: str, limit: int) -> list[VectorMatch] | None:
    """Vector path, hoặc `None` khi đường này không đi được — không bao giờ raise."""
    try:
        # Import trong hàm: hai module này đọc settings và gọi mạng; giữ chúng
        # xa đường import để module knowledge vẫn nhập được không cần khoá.
        from app.services import embeddings, vector_store

        vector = embeddings.embed_query(query)
    except Exception as exc:  # noqa: BLE001 — mọi lý do không embed được đều là "rơi về lexical"
        logger.warning("kb_vector_embed_unavailable", extra={"reason": str(exc)[:200]})
        return None
    try:
        matches = vector_store.PineconeVectorStore().query(vector, top_k=limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("kb_vector_query_unavailable", extra={"reason": str(exc)[:200]})
        return None
    return matches


def _search_lexical(
    db: Session, query: str, limit: int, min_score: float
) -> list[tuple[float, KnowledgeChunk]]:
    q_tokens = _tokens(query)
    if not q_tokens:
        return []
    scored: list[tuple[float, KnowledgeChunk]] = []
    for chunk in db.scalars(select(KnowledgeChunk)):
        pool: dict[str, int] = {}
        for token in _tokens(chunk.title):
            pool[token] = max(pool.get(token, 0), 3)
        for token in _tokens(chunk.keywords):
            pool[token] = max(pool.get(token, 0), 4)
        for token in _tokens(chunk.content):
            pool.setdefault(token, 1)
        score = sum(pool.get(t, 0) for t in q_tokens) / (len(q_tokens) * 4)
        if score >= min_score:
            scored.append((score, chunk))
    scored.sort(key=lambda pair: (-pair[0], pair[1].ref))
    return scored[:limit]
