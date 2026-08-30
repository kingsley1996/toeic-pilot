"""Embeddings qua cổng tương thích OpenAI của Google — httpx thẳng, không SDK.

Tách khỏi `llm/` vì đây KHÔNG phải chat: không tier, không budget, không ghi
`ai_interaction` — embeddings chạy theo hai đường rất khác nhau:

- **Offline** (`app/content/embed_kb.py`): embed toàn bộ knowledge base khi
  đồng bộ. Chậm cũng được, miễn phí và idempotent theo ref.
- **Request time** (`services/knowledge.py`): embed CÂU HỎI của người học trước
  khi tra vector store. Đây là lượt gọi mạng trên đường phục vụ — hỏng thì gọi
  bên dưới phải có đường lui (rơi về lexical), không được phép 500 cả Trợ lý.

Model mặc định là `gemini-embedding-001` — 3072 chiều, đa ngôn ngữ. **Chiều là
quyết định một chiều** (ADR-001 §A6): đổi model nghĩa là tạo lại index Pinecone
và embed lại toàn bộ corpus.
"""

from __future__ import annotations

import httpx

from app.core.config import settings

__all__ = ["EmbeddingUnavailable", "embed_texts", "embed_query"]


class EmbeddingUnavailable(RuntimeError):
    """Không gọi được embeddings — tín hiệu cho nơi gọi rơi về lexical."""


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed nhiều văn bản một lượt gọi; giữ thứ tự đầu vào."""
    if not texts:
        return []
    return _request(texts)


def embed_query(text: str) -> list[float]:
    """Embed MỘT câu truy vấn lúc request time."""
    return _request([text])[0]


def _request(inputs: list[str]) -> list[list[float]]:
    key = settings.google_api_key
    if not key:
        raise EmbeddingUnavailable("chưa có GEMINI_API_KEY trong .env")
    url = settings.embeddings_base_url.rstrip("/") + "/embeddings"
    try:
        response = httpx.post(
            url,
            json={"model": settings.embeddings_model, "input": inputs},
            headers={"Authorization": f"Bearer {key}"},
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise EmbeddingUnavailable(f"không gọi được embeddings: {exc}") from exc
    if response.status_code != 200:
        raise EmbeddingUnavailable(f"embeddings trả {response.status_code}: {response.text[:300]}")
    data = response.json().get("data") or []
    if len(data) != len(inputs):
        raise EmbeddingUnavailable(f"embeddings trả {len(data)} vector cho {len(inputs)} văn bản")
    # `index` do nhà cung cấp trả về — sắp lại theo nó thay vì tin thứ tự.
    # Google trả từng mục KHÔNG có `index`, nên thiếu thì giữ nguyên thứ tự
    # phản hồi (kiểm tay 2026-08-29: thứ tự về khớp thứ tự đầu vào).
    if all("index" in item for item in data):
        data = sorted(data, key=lambda item: item["index"])
    return [item["embedding"] for item in data]
