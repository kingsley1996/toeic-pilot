"""Cache-Control của middleware allowlist: endpoint nào có/không header.

Ba tính chất ghim ở đây, cả ba đều hỏng im lặng nếu mất:

- thuần public có `public` (trình duyệt giữ, qua lại không tốn RTT);
- lẫn user-data có `private` + `Vary: Authorization` (máy dùng chung + đổi
  acc không thấy số người trước);
- endpoint user và mọi non-GET KHÔNG có header (allowlist, không blocklist).
"""

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_pure_content_is_publicly_cacheable(client: TestClient) -> None:
    response = client.get("/api/v1/practice/parts")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=60, stale-while-revalidate=300"
    assert "vary" not in response.headers


def test_mixed_content_varies_by_authorization(client: TestClient) -> None:
    response = client.get("/api/v1/grammar-topics")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=60"
    assert response.headers["vary"] == "Authorization"


def test_user_endpoints_and_writes_have_no_cache_header(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    me = client.get("/api/v1/auth/me", headers=auth("learner"))
    assert me.status_code == 200
    assert "cache-control" not in me.headers

    denied = client.post("/api/v1/auth/login", json={"email": "x@y.z", "password": "sai"})
    assert "cache-control" not in denied.headers


def test_user_scoped_lookalikes_are_not_matched(
    client: TestClient, auth: Callable[[str], dict[str, str]]
) -> None:
    """`/vocabulary/<uuid>` chỉ khớp đúng UUID — `/vocabulary-progress`,
    `/vocabulary-review/...`, `/vocabulary-topic-...` là endpoint user, dính
    `public` ở đây là lộ dữ liệu người học vào cache. Dùng token thật để các
    endpoint trả 200 (guard thật, không phải 401)."""
    headers = auth("learner")
    for path in (
        "/api/v1/vocabulary-progress",
        "/api/v1/vocabulary-review/session",
        "/api/v1/vocabulary-topic-progress?item=00000000-0000-0000-0000-000000000000",
    ):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, path
        assert "cache-control" not in response.headers, path
