"""Đăng nhập bằng Google và Apple.

Bốn thứ được kiểm ở đây là bốn thứ hỏng im lặng, và không cái nào cần gọi ra
mạng thật:

  · nhà cung cấp chưa cấu hình mà vẫn lộ endpoint — người dùng bấm vào một nút
    dẫn tới lỗi, và không phân biệt được "chưa dựng" với "đang hỏng";
  · `state` dùng lại được lần thứ hai, tức là một URL callback bị ghi lại vẫn
    còn giá trị;
  · gắn danh tính vào một tài khoản cùng email mà chưa xác minh — đường chiếm
    tài khoản kinh điển;
  · tài khoản không mật khẩu lọt qua `/auth/login` hoặc `/auth/password`.
"""

import json
import uuid

from app.models.user import User
from app.services import oauth


class FakeRedis:
    """Đủ để chạy `start_flow`/`take_flow`, không hơn.

    Ba phương thức, không phải một bản mô phỏng Redis. Một fake lớn hơn sẽ trở
    thành thứ phải bảo trì, và nó trôi khỏi Redis thật mà không có gì báo.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    def getdel(self, key: str) -> str | None:
        return self.store.pop(key, None)

    # Ba phương thức dưới đây là của bộ đếm tần suất, không phải của luồng OAuth:
    # `/start` đứng sau `rate_limit_anonymous`, và nó dùng CÙNG một Redis. Thay
    # phụ thuộc mà quên chúng thì bài test đỏ ở một chỗ không liên quan gì tới
    # thứ nó đang kiểm.
    def incr(self, key: str) -> int:
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = str(value)
        return value

    def expire(self, key: str, ttl: int) -> None:
        return None

    def ttl(self, key: str) -> int:
        return 60


def _identity(**overrides) -> oauth.Identity:
    base = {
        "subject": "sub-123",
        "email": "nguoi@example.com",
        "email_verified": True,
        "private_email": False,
        "display_name": None,
    }
    base.update(overrides)
    return oauth.Identity(**base)  # type: ignore[arg-type]


def test_state_is_single_use_and_carries_the_nonce():
    """Đọc state là XOÁ nó. Không thế thì một URL callback bị ghi lại còn dùng
    được suốt thời gian sống của nó — lịch sử trình duyệt, log proxy, ảnh chụp."""
    fake = FakeRedis()
    state, nonce = oauth.start_flow(fake, oauth.GOOGLE, "/learn/vocabulary")

    flow = oauth.take_flow(fake, state)
    assert flow.provider == "google"
    assert flow.nonce == nonce
    assert flow.next_path == "/learn/vocabulary"

    try:
        oauth.take_flow(fake, state)
    except oauth.OAuthError as error:
        assert "đã dùng rồi" in str(error) or "hết hạn" in str(error)
    else:
        raise AssertionError("state phải dùng được đúng một lần")


def test_linking_by_email_needs_a_verified_public_address():
    """Ba điều kiện, và bỏ điều nào cũng mở một đường vào tài khoản người khác."""
    assert oauth.may_link_by_email(_identity()) is True
    assert oauth.may_link_by_email(_identity(email_verified=False)) is False
    assert oauth.may_link_by_email(_identity(private_email=True)) is False
    assert oauth.may_link_by_email(_identity(email=None)) is False


def test_fallback_email_is_deterministic_and_unroutable():
    """Cùng `sub` thì cùng email, và email đó không thể là hộp thư của ai.

    `.invalid` là tên miền dành riêng của RFC 2606 — nó không tồn tại được, nên
    không có nguy cơ một tài khoản nội bộ chiếm mất địa chỉ thật của người khác.
    """
    first = oauth.deterministic_email(oauth.APPLE, "sub-abc")
    assert first == oauth.deterministic_email(oauth.APPLE, "sub-abc")
    assert first != oauth.deterministic_email(oauth.APPLE, "sub-xyz")
    assert first.endswith("@toeicpilot.invalid")


def test_an_unconfigured_provider_is_absent_rather_than_broken(client, monkeypatch):
    """Chưa có khoá thì endpoint 404 và danh sách rỗng — không có nút nào để bấm.

    404 nói đúng sự thật: đường này không tồn tại ở bản triển khai này. 503 ngụ ý
    "có nhưng đang hỏng" và mời người ta thử lại một thứ sẽ không bao giờ chạy.

    **Xoá cấu hình một cách TƯỜNG MINH thay vì cho rằng nó vốn trống.** Bản đầu
    của bài này giả định máy chạy không có khoá, và nó đỏ ngay hôm đầu tiên có
    người điền khoá Google thật vào `.env` — một bài test đỏ vì môi trường của
    lập trình viên, không nói gì về mã. CI thì vẫn xanh vì CI không có khoá, nên
    lỗi này chỉ hiện ra ở máy cá nhân, đúng chỗ khó nghi ngờ nhất.
    """
    from app.core.config import settings

    secret = type(settings.cloudinary_api_secret)
    monkeypatch.setattr(settings, "google_oauth_client_id", "")
    monkeypatch.setattr(settings, "google_oauth_client_secret", secret(""))
    monkeypatch.setattr(settings, "apple_client_id", "")
    monkeypatch.setattr(settings, "apple_private_key", secret(""))

    assert client.get("/api/v1/auth/providers").json() == []
    assert client.get("/api/v1/auth/google/start", follow_redirects=False).status_code == 404
    assert client.get("/api/v1/auth/apple/callback", follow_redirects=False).status_code == 404


def test_a_configured_provider_appears_and_redirects(client, monkeypatch):
    """Điền khoá vào là nút hiện ra và `/start` chuyển hướng đúng chỗ.

    Khẳng định trên URL chứ không chỉ trên mã 307: `redirect_uri` sai một ký tự
    là lỗi phổ biến nhất của cả luồng này, và nó chỉ lộ ra ở màn hình của Google.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_oauth_client_id", "client-abc.apps.googleusercontent.com")
    monkeypatch.setattr(
        settings, "google_oauth_client_secret", type(settings.cloudinary_api_secret)("secret")
    )

    assert [p["id"] for p in client.get("/api/v1/auth/providers").json()] == ["google"]

    response = client.get("/api/v1/auth/google/start", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client-abc.apps.googleusercontent.com" in location
    assert "%2Fapi%2Fv1%2Fauth%2Fgoogle%2Fcallback" in location
    assert "state=" in location and "nonce=" in location


def test_next_must_stay_inside_this_site(client, monkeypatch):
    """`next` chỉ nhận đường dẫn nội bộ.

    Nhận URL tuyệt đối là dựng sẵn một open redirect, và nó tệ hơn bình thường ở
    đây: trang lừa đảo hiện ra NGAY SAU một lần đăng nhập thật, tức sau khi người
    dùng vừa được xác nhận rằng mọi thứ đang bình thường.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_oauth_client_id", "cid")
    monkeypatch.setattr(
        settings, "google_oauth_client_secret", type(settings.cloudinary_api_secret)("secret")
    )

    # Thay phụ thuộc qua `dependency_overrides`, KHÔNG monkeypatch tên hàm:
    # FastAPI đã giữ chính đối tượng hàm từ lúc khai `Depends(get_redis)`, nên
    # gán đè tên trong module không còn với tới nó — và bài test sẽ lặng lẽ chạy
    # với Redis thật.
    from app.core.redis_client import get_redis
    from app.main import app

    fake = FakeRedis()
    app.dependency_overrides[get_redis] = lambda: fake
    try:
        client.get("/api/v1/auth/google/start?next=https://ke-gian.example", follow_redirects=False)
    finally:
        app.dependency_overrides.pop(get_redis, None)

    # Lọc theo tiền tố: kho này còn giữ cả bộ đếm tần suất của `/start`.
    saved = json.loads(
        next(value for key, value in fake.store.items() if key.startswith("oauth:state:"))
    )
    assert saved["next"] == "/dashboard"


def test_a_passwordless_account_cannot_use_the_password_paths(client, db_session):
    """Tài khoản Google/Apple không có mật khẩu, và hai đường mật khẩu phải nói
    đúng điều đó — mỗi đường một kiểu.

    `/login` trả về thông báo CHUNG: nói "tài khoản này dùng Google" là xác nhận
    email nào có tài khoản ở đây và bằng đường nào. `/password` thì ngược lại —
    người gọi đã đăng nhập rồi, nên nói thẳng là đúng và hữu ích.
    """
    email = f"oauth-{uuid.uuid4().hex[:8]}@example.com"
    db_session.add(User(email=email, hashed_password=None))
    db_session.commit()

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "x" * 12})
    assert login.status_code == 401
    assert "Google" not in login.json()["detail"]

    # Và đường đổi mật khẩu nói rõ, vì tới đây thì danh tính đã được chứng minh.
    other = f"pw-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={"email": other, "password": "x" * 12})
    token = client.post("/api/v1/auth/login", json={"email": other, "password": "x" * 12}).json()[
        "access_token"
    ]
    user = db_session.query(User).filter(User.email == other).one()
    user.hashed_password = None
    db_session.commit()

    changed = client.post(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "x" * 12, "new_password": "y" * 12},
    )
    assert changed.status_code == 400
    assert "Google" in changed.json()["detail"]


def test_apple_client_secret_is_a_signed_jwt_with_the_right_claims():
    """Apple không phát chuỗi bí mật — nó đòi một JWT ta tự ký.

    Bốn claim đều bắt buộc và Apple từ chối cả token nếu thiếu một. Bài này ký
    bằng một khoá EC sinh tại chỗ, nên nó kiểm được hình dạng mà không cần khoá
    thật của ai.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from jose import jwt as jose_jwt

    from app.core.config import settings

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    secret_type = type(settings.cloudinary_api_secret)
    original = (settings.apple_team_id, settings.apple_key_id, settings.apple_private_key)
    settings.apple_team_id = "TEAM123456"
    settings.apple_key_id = "KEY1234567"
    settings.apple_client_id = "com.example.web"
    settings.apple_private_key = secret_type(pem)
    try:
        token = oauth.client_secret(oauth.APPLE, now=1_700_000_000)
    finally:
        settings.apple_team_id, settings.apple_key_id, settings.apple_private_key = original

    claims = jose_jwt.get_unverified_claims(token)
    assert claims["iss"] == "TEAM123456"
    assert claims["sub"] == "com.example.web"
    assert claims["aud"] == "https://appleid.apple.com"
    # Hạn tối đa Apple cho phép là 6 tháng; dài hơn thì nó từ chối cả token.
    assert claims["exp"] - claims["iat"] <= 15_777_000
    assert jose_jwt.get_unverified_header(token)["kid"] == "KEY1234567"
