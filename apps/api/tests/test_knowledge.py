"""Knowledge base — đồng bộ file, tra lexical, và đường rơi của tra vector."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk
from app.services import embeddings
from app.services.knowledge import parse_kb_file, search_knowledge, sync_knowledge


def _write(path, ref: str, title: str, keywords: str, body: str) -> None:
    (path / f"{ref}.md").write_text(
        f"---\nref: {ref}\ntitle: {title}\nkeywords: {keywords}\n---\n\n{body}\n",
        encoding="utf-8",
    )


def seed(db_session: Session, ref: str, title: str, keywords: str, content: str) -> None:
    db_session.add(KnowledgeChunk(ref=ref, title=title, keywords=keywords, content=content))
    db_session.commit()


def test_SYNC_tao_xong_xoa_theo_FILE(db_session: Session, tmp_path) -> None:
    # sync_knowledge không tự commit — caller commit giữa các lượt như ngoài thật
    # (và autoflush=False của session test đòi đúng thế).
    _write(tmp_path, "a-doc", "Tài liệu A", "alpha", "nội dung a")
    result = sync_knowledge(db_session, tmp_path)
    db_session.commit()
    assert result.created == ["a-doc"]

    # Đổi nội dung → cập nhật; thêm file mới; bỏ file cũ → xoá khỏi bảng.
    _write(tmp_path, "a-doc", "Tài liệu A (sửa)", "alpha", "nội dung a đã đổi")
    _write(tmp_path, "b-doc", "Tài liệu B", "beta", "nội dung b")
    result = sync_knowledge(db_session, tmp_path)
    db_session.commit()
    assert result.updated == ["a-doc"] and result.created == ["b-doc"]

    (tmp_path / "a-doc.md").unlink()
    result = sync_knowledge(db_session, tmp_path)
    db_session.commit()
    assert result.removed == ["a-doc"]


def test_SYNC_file_THIEU_REF_la_LOI_RO_RANG(db_session: Session, tmp_path) -> None:
    (tmp_path / "broken.md").write_text("không có frontmatter", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.md"):
        sync_knowledge(db_session, tmp_path)


def test_SYNC_khong_tu_COMMIT(db_session: Session, tmp_path) -> None:
    """Caller quyết định commit hay rollback — dry-run của sync_kb phụ thuộc điều đó."""
    _write(tmp_path, "a-doc", "A", "alpha", "nội dung a")
    sync_knowledge(db_session, tmp_path)
    db_session.rollback()
    assert db_session.scalars(select(KnowledgeChunk)).all() == []


def test_SYNC_sua_noi_dung_thi_MOI_updated_at(db_session: Session, tmp_path) -> None:
    """`updated_at` mô tả lượt SỬA gần nhất, không phải lượt TẠO — sync chạm
    nội dung thì cột phải tiến lên, nếu không thì quản lý "mục nào cũ rồi"
    đọc nhầm toàn bộ bảng."""
    from datetime import UTC, date, datetime

    _write(tmp_path, "a-doc", "Tài liệu A", "alpha", "nội dung a")
    sync_knowledge(db_session, tmp_path)
    db_session.commit()
    chunk = db_session.scalar(select(KnowledgeChunk).where(KnowledgeChunk.ref == "a-doc"))
    chunk.updated_at = datetime(2000, 1, 1, tzinfo=UTC)
    db_session.commit()

    _write(tmp_path, "a-doc", "Tài liệu A (sửa)", "alpha", "nội dung a đã đổi")
    sync_knowledge(db_session, tmp_path)
    db_session.commit()
    chunk = db_session.scalar(select(KnowledgeChunk).where(KnowledgeChunk.ref == "a-doc"))
    # SQLite trả `func.now()` dạng naive — so sánh theo ngày tránh lệch tz
    assert chunk.updated_at.date() > date(2000, 1, 1)


def test_LEXICAL_tra_DUNG_theo_TU_KHOA(db_session: Session) -> None:
    seed(
        db_session,
        "tests-scoring",
        "Điểm luyện thi và quy đổi",
        "điểm, quy đổi, listening",
        "Nộp bài xong mới có điểm ba kỹ năng.",
    )
    seed(
        db_session,
        "dictation",
        "Nghe chép",
        "dictation, nghe chép",
        "Nghe một câu rồi gõ lại, chấm từng từ.",
    )

    results = search_knowledge(db_session, "khi nào có điểm bài thi?")
    assert [chunk.ref for _, chunk in results][0] == "tests-scoring"
    # Câu không liên quan gì: rỗng là tín hiệu đúng, không nhét nhiễu.
    assert search_knowledge(db_session, "bầu trời màu gì?") == []


def test_TRA_VECTOR_hong_thi_RO_ve_LEXICAL(db_session: Session, monkeypatch) -> None:
    """Pinecone/mất khoá/lỗi mạng là phụ thuộc mềm: lexical phải cứu được."""
    seed(db_session, "dictation", "Nghe chép", "dictation, nghe chép", "Chấm từng từ.")

    def boom(_text: str) -> list[float]:
        raise embeddings.EmbeddingUnavailable("mạng đứt")

    monkeypatch.setattr(embeddings, "embed_query", boom)
    results = search_knowledge(db_session, "nghe chép chấm thế nào?")
    assert results and results[0][1].ref == "dictation"


def test_TRA_VECTOR_thanh_cong_thi_MAP_ve_CHUNK_theo_REF(db_session: Session, monkeypatch) -> None:
    seed(db_session, "dashboard", "Trang chủ", "dashboard", "Ba việc hôm nay.")
    seed(db_session, "ruby", "Ruby", "ruby, ví", "Kiếm từ việc học.")

    from app.services import vector_store
    from app.services.vector_store import VectorMatch

    monkeypatch.setattr(embeddings, "embed_query", lambda _t: [0.1, 0.2])
    monkeypatch.setattr(
        vector_store.PineconeVectorStore,
        "query",
        lambda self, vector, top_k: [
            VectorMatch(ref="ruby", score=0.9),
            VectorMatch(ref="dashboard", score=0.5),
        ],
    )

    results = search_knowledge(db_session, "ví ruby dùng để làm gì?")
    assert [chunk.ref for _, chunk in results] == ["ruby", "dashboard"]


def test_TRA_VECTOR_ref_mat_GOC_thi_RO_ve_LEXICAL(db_session: Session, monkeypatch) -> None:
    """Vector trả ref bảng không còn (xoá file chưa embed lại) — lexical vẫn hơn rỗng."""
    seed(db_session, "dictation", "Nghe chép", "dictation, nghe chép", "Chấm từng từ.")

    from app.services import vector_store
    from app.services.vector_store import VectorMatch

    monkeypatch.setattr(embeddings, "embed_query", lambda _t: [0.1])
    monkeypatch.setattr(
        vector_store.PineconeVectorStore,
        "query",
        lambda self, vector, top_k: [VectorMatch(ref="da-xoa", score=0.9)],
    )

    results = search_knowledge(db_session, "nghe chép chấm thế nào?")
    assert [chunk.ref for _, chunk in results] == ["dictation"]


def test_PARSE_file_hong_thi_BAO_RO_FILE_NAO(tmp_path) -> None:
    broken = tmp_path / "khong-ref.md"
    broken.write_text("---\ntitle: X\n---\n\nthân\n", encoding="utf-8")
    with pytest.raises(ValueError, match="khong-ref.md"):
        parse_kb_file(broken)
