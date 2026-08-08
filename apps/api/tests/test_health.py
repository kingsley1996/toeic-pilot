from unittest.mock import MagicMock, patch

import redis
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.logging import REQUEST_ID_HEADER


def _redis_ok():
    client = MagicMock()
    client.ping.return_value = True
    return patch("app.api.routes.health.get_redis", return_value=client)


def _redis_down():
    client = MagicMock()
    client.ping.side_effect = redis.ConnectionError("connection refused")
    return patch("app.api.routes.health.get_redis", return_value=client)


# --- liveness -------------------------------------------------------------


def test_health_is_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_does_not_depend_on_the_database(client: TestClient, db_session):
    """Liveness must stay green while Postgres is down, otherwise the
    orchestrator restarts a perfectly healthy process during a DB outage."""
    with patch.object(db_session, "execute", side_effect=OperationalError("x", {}, Exception())):
        assert client.get("/health").status_code == 200


# --- readiness ------------------------------------------------------------


def test_ready_reports_both_dependencies(client: TestClient):
    with _redis_ok():
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"database": "ok", "redis": "ok"}


def test_ready_returns_503_when_database_is_down(client: TestClient, db_session):
    """P1-6 regression: /ready used to return a hardcoded 'ready' forever, so a
    load balancer would keep routing to an instance that cannot serve anything."""
    with (
        patch.object(db_session, "execute", side_effect=OperationalError("x", {}, Exception())),
        _redis_ok(),
    ):
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["database"] == "unavailable"


def test_ready_stays_200_when_only_redis_is_down(client: TestClient):
    """Redis is a soft dependency — degrade, don't remove the instance."""
    with _redis_down():
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"] == {"database": "ok", "redis": "degraded"}


# --- request correlation (P1-9) -------------------------------------------


def test_response_carries_a_request_id(client: TestClient):
    response = client.get("/health")
    assert response.headers.get(REQUEST_ID_HEADER)


def test_request_id_is_unique_per_request(client: TestClient):
    a = client.get("/health").headers[REQUEST_ID_HEADER]
    b = client.get("/health").headers[REQUEST_ID_HEADER]
    assert a != b


def test_incoming_request_id_is_propagated(client: TestClient):
    response = client.get("/health", headers={REQUEST_ID_HEADER: "trace-from-gateway"})
    assert response.headers[REQUEST_ID_HEADER] == "trace-from-gateway"


def test_incoming_request_id_is_truncated(client: TestClient):
    response = client.get("/health", headers={REQUEST_ID_HEADER: "x" * 500})
    assert len(response.headers[REQUEST_ID_HEADER]) == 64
