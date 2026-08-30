"""Đồng bộ knowledge base → embed → đẩy vector lên Pinecone.

uv run python -m app.content.embed_kb [--dir <thư mục>] [--create-index]

Ba bước, mỗi bước idempotent:
1. `sync_knowledge` — upsert bảng `knowledge_chunk` từ file markdown, xoá ref
   mất nguồn (chạy lại tìm ít việc hơn).
2. Embed toàn bộ chunk qua cổng embeddings của Google (gemini-embedding-001,
   3072 chiều, đa ngôn ngữ).
3. Upsert vector lên Pinecone, id = ref, namespace "kb".

`--create-index` tạo index serverless nếu CHƯA có — bắt buộc lần đầu. Chiều
index lấy từ vector thật của lượt embed đầu, không phải hằng số: hằng số là
thứ sẽ sai lặng lẽ ngày nhà cung cấp đổi model.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

from app.content.sync_kb import DEFAULT_DIR
from app.core.database import SessionLocal
from app.models.knowledge import KnowledgeChunk
from app.services import embeddings, vector_store
from app.services.knowledge import sync_knowledge


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--create-index", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        synced = sync_knowledge(session, args.dir)
        session.commit()
        print(
            "đồng bộ file — tạo mới:",
            len(synced.created),
            "· cập nhật:",
            len(synced.updated),
            "· xoá:",
            len(synced.removed),
        )
        print("   ", synced.created or synced.updated or synced.removed or "(không đổi)")

        chunks = list(session.scalars(select(KnowledgeChunk)))
    finally:
        session.close()

    if not chunks:
        print("knowledge base trống — không có gì để embed")
        return 0

    store = vector_store.PineconeVectorStore()
    if args.create_index:
        first = embeddings.embed_texts([chunks[0].content])
        host = store.create_index(len(first[0]))
        print(f"index sẵn sàng: {host}")

    # Batching: một lượt gọi cho toàn bộ corpus nhỏ; corpus lớn thì cắt 64 —
    # đủ để một lần mạng không mang hàng nghìn văn bản, không nhỏ tới tốn lượt.
    batch_size = 64
    upserted = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embeddings.embed_texts([chunk.content for chunk in batch])
        upserted += store.upsert(
            [(chunk.ref, vector, {"title": chunk.title}) for chunk, vector in zip(batch, vectors)]
        )
    print(f"đã upsert {upserted} vector lên Pinecone (namespace 'kb')")

    # Dọn vector MẤT GỐC: file đã xoá thì hàng DB biến mất ở bước sync, nhưng
    # vector cũ vẫn nằm trên Pinecone — chiếm chỗ top-k và trả ref không còn
    # tồn tại. Không dọn thì "xoá tài liệu" chỉ xoá được một nửa.
    live_refs = {chunk.ref for chunk in chunks}
    stale = [ref for ref in store.list_ids() if ref not in live_refs]
    removed = store.delete(stale)
    print(f"đã xoá {removed} vector mất gốc: {stale}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
