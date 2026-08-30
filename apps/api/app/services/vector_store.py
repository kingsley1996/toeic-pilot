"""Vector store Pinecone — httpx thẳng, không SDK (ADR-003 §3.1).

Phụ trách đúng ba việc: tìm host của index, upsert vector, tra vector. Mọi thứ
khác (tạo index, xoá index, quản lý collection) là việc vận hành — có lệnh
trong `app/content/embed_kb.py` nhưng không nằm ở đường phục vụ request.

Postgres giữ NỘI DUNG (`knowledge_chunk`), Pinecone giữ VECTOR — hai nguồn
nối với nhau bằng `ref` làm id. Postgres mất thì files trong git trả lại được;
Pinecone mất thì `embed_kb` đẩy lại; một bên lệch bên kia thì phép tra lai ở
`services/knowledge.py` vẫn chạy (rơi về lexical). Không bên nào là "bản gốc
duy nhất" — đó là chủ ý, và là lý do không có cột vector trong Postgres.

Lỗi ở đây KHÔNG bao giờ nổ lên request: nơi gọi nhận `VectorStoreUnavailable`
và rơi về lexical. Vector store là phụ thuộc mềm của Trợ lý — cùng hạng với
Redis ở `rate_limit_anonymous`, ngược với `ai_budget`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

__all__ = ["VectorStoreUnavailable", "PineconeVectorStore", "VectorMatch"]

logger = logging.getLogger(__name__)

_API_VERSION = "2025-04"
_API_BASE = "https://api.pinecone.io"


class VectorStoreUnavailable(RuntimeError):
    """Không gọi được Pinecone hoặc index chưa tồn tại."""


@dataclass(frozen=True, slots=True)
class VectorMatch:
    ref: str
    score: float


class PineconeVectorStore:
    name = "pinecone"

    def __init__(self, *, index_name: str | None = None, api_key: str | None = None) -> None:
        self._index_name = index_name or settings.pinecone_index_name
        self._key = api_key or settings.pinecone_api_key or ""
        self._host: str | None = None

    def _headers(self) -> dict[str, str]:
        return {
            "Api-Key": self._key,
            "X-Pinecone-API-Version": _API_VERSION,
            "Content-Type": "application/json",
        }

    def _resolve_host(self) -> str:
        """Host của index chỉ biết được qua describe — cache trong tiến trình.

        Host đổi thì tiến trình phải restart để thấy, và đó là đúng: host đổi
        nghĩa là index đã bị dựng lại, tức là toàn bộ vector cũng phải embed lại.
        """
        if self._host:
            return self._host
        if not self._key:
            raise VectorStoreUnavailable("chưa có PINECONE_API_KEY trong .env")
        try:
            response = httpx.get(
                f"{_API_BASE}/indexes/{self._index_name}",
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise VectorStoreUnavailable(f"không gọi được Pinecone: {exc}") from exc
        if response.status_code == 404:
            raise VectorStoreUnavailable(
                f"index {self._index_name!r} chưa tồn tại — chạy embed_kb --create-index"
            )
        if response.status_code != 200:
            raise VectorStoreUnavailable(
                f"describe index trả {response.status_code}: {response.text[:200]}"
            )
        host = response.json().get("host")
        if not host:
            raise VectorStoreUnavailable("describe index không trả host")
        self._host = host
        return host

    def upsert(self, items: list[tuple[str, list[float], dict[str, str]]]) -> int:
        """(ref, vector, metadata) → upsert vào namespace "kb"; trả số vector."""
        if not items:
            return 0
        host = self._resolve_host()
        try:
            response = httpx.post(
                f"https://{host}/vectors/upsert",
                headers=self._headers(),
                timeout=60.0,
                json={
                    "namespace": "kb",
                    "vectors": [
                        {"id": ref, "values": vector, "metadata": metadata}
                        for ref, vector, metadata in items
                    ],
                },
            )
        except httpx.HTTPError as exc:
            raise VectorStoreUnavailable(f"không upsert được vào Pinecone: {exc}") from exc
        if response.status_code != 200:
            raise VectorStoreUnavailable(
                f"upsert trả {response.status_code}: {response.text[:300]}"
            )
        return int(response.json().get("upsertedCount", len(items)))

    def list_ids(self) -> list[str]:
        """Toàn bộ id trong namespace "kb" — dùng để tìm vector mất gốc."""
        host = self._resolve_host()
        out: list[str] = []
        token: str | None = None
        while True:
            params: dict[str, str | int] = {"namespace": "kb", "limit": 100}
            if token:
                params["paginationToken"] = token
            try:
                response = httpx.get(
                    f"https://{host}/vectors/list",
                    headers=self._headers(),
                    timeout=30.0,
                    params=params,
                )
            except httpx.HTTPError as exc:
                raise VectorStoreUnavailable(f"không liệt kê được vector: {exc}") from exc
            if response.status_code != 200:
                raise VectorStoreUnavailable(
                    f"list trả {response.status_code}: {response.text[:300]}"
                )
            body = response.json()
            out.extend(str(v["id"]) for v in body.get("vectors") or [])
            token = body.get("pagination", {}).get("next")
            if not token:
                return out

    def delete(self, refs: list[str]) -> int:
        """Xoá vector theo id — dọn những ref không còn nguồn trong bảng."""
        if not refs:
            return 0
        host = self._resolve_host()
        try:
            response = httpx.post(
                f"https://{host}/vectors/delete",
                headers=self._headers(),
                timeout=30.0,
                json={"namespace": "kb", "ids": refs},
            )
        except httpx.HTTPError as exc:
            raise VectorStoreUnavailable(f"không xoá được vector: {exc}") from exc
        if response.status_code != 200:
            raise VectorStoreUnavailable(
                f"delete trả {response.status_code}: {response.text[:300]}"
            )
        return len(refs)

    def query(self, vector: list[float], *, top_k: int = 4) -> list[VectorMatch]:
        host = self._resolve_host()
        try:
            response = httpx.post(
                f"https://{host}/query",
                headers=self._headers(),
                timeout=30.0,
                json={"namespace": "kb", "vector": vector, "topK": top_k, "includeMetadata": False},
            )
        except httpx.HTTPError as exc:
            raise VectorStoreUnavailable(f"không query được Pinecone: {exc}") from exc
        if response.status_code != 200:
            raise VectorStoreUnavailable(f"query trả {response.status_code}: {response.text[:300]}")
        return [
            VectorMatch(ref=str(hit["id"]), score=float(hit["score"]))
            for hit in response.json().get("matches") or []
        ]

    def create_index(self, dimension: int) -> str:
        """Tạo index serverless nếu CHƯA có; trả host. Việc vận hành, không
        nằm trên đường request — idempotent để lệnh `--create-index` gọi thoải mái."""
        if not self._key:
            raise VectorStoreUnavailable("chưa có PINECONE_API_KEY trong .env")
        try:
            response = httpx.get(
                f"{_API_BASE}/indexes/{self._index_name}", headers=self._headers(), timeout=30.0
            )
            if response.status_code == 200:
                host = response.json().get("host") or ""
                if host:
                    self._host = host
                    return host
            body = {
                "name": self._index_name,
                "dimension": dimension,
                "metric": "cosine",
                "spec": {"serverless": {"cloud": "aws", "region": "us-east-1"}},
            }
            created = httpx.post(
                f"{_API_BASE}/indexes", headers=self._headers(), timeout=60.0, json=body
            )
        except httpx.HTTPError as exc:
            raise VectorStoreUnavailable(f"không gọi được Pinecone: {exc}") from exc
        if created.status_code not in (200, 201):
            raise VectorStoreUnavailable(
                f"tạo index trả {created.status_code}: {created.text[:300]}"
            )
        # Serverless index sẵn sàng sau chục giây tới một phút; lệnh embed sẽ
        # tự retry qua VectorStoreUnavailable của describe nếu chưa xong.
        host = str(created.json().get("host") or "")
        if host:
            self._host = host
        return host
