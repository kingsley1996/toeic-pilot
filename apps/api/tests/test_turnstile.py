"""Cổng chống bot Cloudflare Turnstile (ADR-015).

Bốn thứ được ghim ở đây, và cả bốn đều hỏng im lặng:

  · **chưa cấu hình thì phải trơ hoàn toàn** — nếu không, mọi máy dev và mọi
    lần chạy CI đều mất luôn đường đăng nhập, mà không lỗi nào nói vì sao;
  · **cấu hình một nửa thì không được khởi động** — chỉ có site key thì trang vẽ
    ô kiểm còn máy chủ không kiểm gì cả, tức là *trông như* đã được bảo vệ;
  · **Cloudflare chối thì chặn**, kể cả khi mọi thứ khác của request đều hợp lệ;
  · **không hỏi được Cloudflare thì cho qua** — cái này ngược với trực giác nên
    càng phải có bài, xem `turnstile.verify`.

Không bài nào gọi ra mạng thật. Một bài kiểm bảo mật mà phải có Internet mới
chạy được thì sẽ bị bỏ qua đúng vào ngày người ta cần nó nhất.
"""

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings, settings
from app.services import turnstile


def _turn_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "turnstile_site_key", "0x4AAAAAAA-site")
    monkeypatch.setattr(settings, "turnstile_secret_key", SecretStr("0x4AAAAAAA-secret"))


def _answer(monkeypatch, payload: dict, status_code: int = 200) -> list[dict]:
    """Thay `httpx.post` bằng một câu trả lời dựng sẵn, và giữ lại thứ đã gửi đi."""
    sent: list[dict] = []

    def fake_post(url: str, data: dict, timeout: float) -> httpx.Response:
        sent.append({"url": url, "data": data})
        return httpx.Response(status_code, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    return sent


def test_an_unconfigured_turnstile_lets_everything_through(client, monkeypatch):
    """Thiếu khoá thì tính năng TẮT, không phải hỏng.

    Đây là đường chạy của mọi máy dev và của cả bộ e2e, nên nó phải là đường
    được kiểm chứ không phải đường được cho là hiển nhiên.
    """
    monkeypatch.setattr(settings, "turnstile_site_key", "")
    monkeypatch.setattr(settings, "turnstile_secret_key", SecretStr(""))

    assert client.get("/api/v1/auth/turnstile").status_code == 204

    created = client.post(
        "/api/v1/auth/register",
        json={"email": "no-gate@example.com", "password": "mat-khau-du-dai-123"},
    )
    assert created.status_code == 201, created.text


def test_half_configured_turnstile_refuses_to_start(monkeypatch):
    """Chỉ có site key = trang vẽ ô kiểm, máy chủ không kiểm.

    Nó phải nổ lúc khởi động, vì kiểu hỏng này KHÔNG có triệu chứng: mọi request
    thành công, ô kiểm hiện ra, và hàng rào thì không tồn tại.
    """
    monkeypatch.setenv("TURNSTILE_SITE_KEY", "0x4AAAAAAA-site")
    monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="TURNSTILE_SECRET_KEY"):
        Settings(_env_file=None)

    monkeypatch.delenv("TURNSTILE_SITE_KEY")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "0x4AAAAAAA-secret")
    with pytest.raises(ValueError, match="TURNSTILE_SITE_KEY"):
        Settings(_env_file=None)


def test_the_site_key_is_served_so_the_two_sides_cannot_drift(client, monkeypatch):
    _turn_on(monkeypatch)
    body = client.get("/api/v1/auth/turnstile")
    assert body.status_code == 200
    assert body.json() == {"site_key": "0x4AAAAAAA-site"}


def test_a_rejected_token_blocks_the_request(client, monkeypatch):
    _turn_on(monkeypatch)
    _answer(monkeypatch, {"success": False, "error-codes": ["invalid-input-response"]})

    refused = client.post(
        "/api/v1/auth/register",
        json={"email": "bot@example.com", "password": "mat-khau-du-dai-123"},
        headers={turnstile.TOKEN_HEADER: "a-token-cloudflare-does-not-like"},
    )
    assert refused.status_code == 403


def test_a_missing_token_blocks_the_request(client, monkeypatch):
    """Không gửi header thì bị chặn — nếu không, né cổng chỉ là việc bỏ trống nó."""
    _turn_on(monkeypatch)
    called = _answer(monkeypatch, {"success": True})

    refused = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "mat-khau-du-dai-123"},
    )
    assert refused.status_code == 403
    # Và không tốn một vòng mạng nào để nói ra điều đó.
    assert called == []


def test_a_good_token_gets_through_and_carries_the_client_address(client, monkeypatch):
    _turn_on(monkeypatch)
    sent = _answer(monkeypatch, {"success": True})

    created = client.post(
        "/api/v1/auth/register",
        json={"email": "human@example.com", "password": "mat-khau-du-dai-123"},
        headers={turnstile.TOKEN_HEADER: "a-token-cloudflare-likes"},
    )
    assert created.status_code == 201, created.text
    assert sent[0]["url"] == turnstile.VERIFY_URL
    assert sent[0]["data"]["response"] == "a-token-cloudflare-likes"
    # `remoteip` là tuỳ chọn với Cloudflare nhưng là thứ giúp họ chấm điểm rủi
    # ro; bỏ nó đi thì cổng vẫn "chạy" và vẫn yếu đi, không dấu hiệu nào.
    assert sent[0]["data"]["remoteip"]


def test_an_unreachable_cloudflare_does_not_lock_everyone_out(client, monkeypatch):
    """Hỏng thì MỞ — và đây là chỗ dễ bị "sửa" ngược nhất trong cả tệp.

    Đóng lại nghe an toàn hơn, nhưng nó biến một sự cố phía Cloudflare thành một
    sự cố *của ta*: không ai đăng nhập được nữa. Cho qua thì hàng rào tụt về
    đúng mức của ngày hôm qua — rate limit theo IP vẫn chạy — chứ không tụt về
    không. Cùng lựa chọn mà `rate_limit_anonymous` đã ghi ra khi Redis chết.
    """
    _turn_on(monkeypatch)

    def explode(url: str, data: dict, timeout: float) -> httpx.Response:
        raise httpx.ConnectTimeout("cloudflare is having a day")

    monkeypatch.setattr(httpx, "post", explode)

    created = client.post(
        "/api/v1/auth/register",
        json={"email": "outage@example.com", "password": "mat-khau-du-dai-123"},
        headers={turnstile.TOKEN_HEADER: "a-token-nobody-can-check"},
    )
    assert created.status_code == 201, created.text


def test_an_overlong_token_never_leaves_the_process(client, monkeypatch):
    """Header rác không được biến thành một request đi ra ngoài mạng."""
    _turn_on(monkeypatch)
    called = _answer(monkeypatch, {"success": True})

    refused = client.post(
        "/api/v1/auth/register",
        json={"email": "flood@example.com", "password": "mat-khau-du-dai-123"},
        headers={turnstile.TOKEN_HEADER: "x" * (turnstile.MAX_TOKEN_LENGTH + 1)},
    )
    assert refused.status_code == 403
    assert called == []
