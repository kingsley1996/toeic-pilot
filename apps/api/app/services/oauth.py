"""Đăng nhập bằng Google và Apple: luồng mã uỷ quyền phía MÁY CHỦ.

**Không nhúng SDK JavaScript của bên nào.** Đây không phải sở thích: CLAUDE.md
ghi rõ việc hoãn chuyển token sang cookie httpOnly (P1-7b) đứng vững *chỉ vì*
ứng dụng này không có script bên thứ ba nào. Nhúng `accounts.google.com/gsi` hay
`appleid.cdn-apple.com` là làm lý do đó hết hiệu lực ngay lập tức, và khi đó nợ
kỹ thuật P1-7b phải trả trước — trước cả tính năng đang làm.

Luồng: `/auth/{provider}/start` → nhà cung cấp → callback về API → đổi `code`
lấy `id_token` → xác minh → tìm/liên kết/tạo tài khoản → phát token của CHÍNH
hệ thống này. Token của Google hay Apple không bao giờ đi tiếp vào ứng dụng; nó
chỉ là bằng chứng danh tính cho đúng một lần đăng nhập.
"""

from __future__ import annotations

import json
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import settings

# --- mô tả nhà cung cấp ------------------------------------------------------


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    authorize_url: str
    token_url: str
    jwks_url: str
    issuers: tuple[str, ...]
    scope: str
    # Apple trả kết quả bằng POST form (`response_mode=form_post`) vì nó gửi kèm
    # tên người dùng ở lần đầu; Google trả bằng GET. Khai ở đây để chỗ dựng URL
    # và chỗ nhận callback không thể nói khác nhau.
    form_post: bool


GOOGLE = Provider(
    id="google",
    label="Google",
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    jwks_url="https://www.googleapis.com/oauth2/v3/certs",
    issuers=("https://accounts.google.com", "accounts.google.com"),
    scope="openid email profile",
    form_post=False,
)

APPLE = Provider(
    id="apple",
    label="Apple",
    authorize_url="https://appleid.apple.com/auth/authorize",
    token_url="https://appleid.apple.com/auth/token",
    jwks_url="https://appleid.apple.com/auth/keys",
    issuers=("https://appleid.apple.com",),
    # Apple CHỈ cho xin `name email` khi `response_mode=form_post`. Xin scope mà
    # để chế độ mặc định thì Apple từ chối cả yêu cầu, không phải chỉ bỏ scope.
    scope="name email",
    form_post=True,
)

PROVIDERS: dict[str, Provider] = {GOOGLE.id: GOOGLE, APPLE.id: APPLE}


class OAuthError(Exception):
    """Luồng đăng nhập hỏng theo cách người dùng cần biết, không phải 500."""


def client_id(provider: Provider) -> str:
    return settings.google_oauth_client_id if provider is GOOGLE else settings.apple_client_id


def is_configured(provider: Provider) -> bool:
    """Nhà cung cấp có đủ thông tin để chạy hay chưa.

    Không có cờ `enabled` riêng, và đó là chủ ý: một cờ bật kèm thông tin thiếu
    cho ra một cái nút bấm vào là lỗi, mà người dùng không phân biệt được "chưa
    dựng" với "đang hỏng".
    """
    if provider is GOOGLE:
        return bool(
            settings.google_oauth_client_id
            and settings.google_oauth_client_secret.get_secret_value()
        )
    return bool(
        settings.apple_client_id
        and settings.apple_team_id
        and settings.apple_key_id
        and settings.apple_private_key.get_secret_value()
    )


def enabled_providers() -> list[Provider]:
    return [p for p in PROVIDERS.values() if is_configured(p)]


def redirect_uri(provider: Provider) -> str:
    """Phải khớp TỪNG KÝ TỰ với thứ đã khai bên nhà cung cấp, kể cả dấu `/` cuối."""
    base = settings.oauth_callback_base_url.rstrip("/")
    return f"{base}/api/v1/auth/{provider.id}/callback"


# --- client secret -----------------------------------------------------------


def client_secret(provider: Provider, now: float | None = None) -> str:
    """Bí mật client. Google có sẵn; Apple thì phải TỰ KÝ.

    Apple không phát chuỗi bí mật nào — "client secret" của nó là một JWT ký
    ES256 bằng khoá .p8, `iss` là Team ID, `sub` là Service ID, `aud` cố định là
    `https://appleid.apple.com`, hạn tối đa 6 tháng.

    Sinh MỚI cho mỗi lần đổi mã, không lưu lại: một chuỗi ký sẵn để trong `.env`
    sẽ hết hạn sau sáu tháng, và triệu chứng lúc đó là "đăng nhập Apple hỏng" mà
    không có gì trong log nói tới ngày hết hạn.
    """
    if provider is GOOGLE:
        return settings.google_oauth_client_secret.get_secret_value()

    issued = int(now if now is not None else time.time())
    return jwt.encode(
        {
            "iss": settings.apple_team_id,
            "iat": issued,
            # 180 ngày; Apple chặn ở 6 tháng. Không dùng hạn dài hơn "tối đa" chỉ
            # vì nó tiện — Apple từ chối cả token, không cắt bớt hạn.
            "exp": issued + 180 * 24 * 3600,
            "aud": "https://appleid.apple.com",
            "sub": settings.apple_client_id,
        },
        settings.apple_private_key.get_secret_value(),
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


# --- state: một lần, có hạn --------------------------------------------------

_STATE_PREFIX = "oauth:state:"
_STATE_TTL_SECONDS = 600


@dataclass(frozen=True)
class FlowState:
    provider: str
    nonce: str
    next_path: str


def start_flow(redis_client: Any, provider: Provider, next_path: str) -> tuple[str, str]:
    """Sinh (state, nonce) và cất vào Redis. Trả về cặp đó.

    `state` chống CSRF (một yêu cầu callback không bắt nguồn từ ta), `nonce`
    chống phát lại `id_token`. Hai thứ khác nhau và cần cả hai.

    **Đường này FAIL CLOSED khi Redis hỏng**, ngược hẳn với `rate_limit_anonymous`.
    Ở đó Redis hỏng mà chặn hết thì không ai đăng nhập được — một phụ thuộc mềm
    làm sập sản phẩm. Ở đây Redis là thứ DUY NHẤT chứng minh callback này thuộc
    về một lần bấm có thật; bỏ qua nó là chấp nhận state bất kỳ, tức là bỏ luôn
    lớp chống CSRF mà state sinh ra để làm.
    """
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(16)
    payload = json.dumps({"provider": provider.id, "nonce": nonce, "next": next_path})
    try:
        redis_client.setex(_STATE_PREFIX + state, _STATE_TTL_SECONDS, payload)
    except Exception as error:  # pragma: no cover - phụ thuộc hạ tầng
        raise OAuthError("Không khởi tạo được phiên đăng nhập. Thử lại sau.") from error
    return state, nonce


def take_flow(redis_client: Any, state: str) -> FlowState:
    """Đọc state và XOÁ ngay — dùng đúng một lần.

    Không xoá thì một URL callback bị ghi lại (lịch sử trình duyệt, log proxy,
    ảnh chụp màn hình) còn dùng lại được trong suốt 10 phút.
    """
    if not state:
        raise OAuthError("Thiếu tham số state.")
    try:
        raw = redis_client.getdel(_STATE_PREFIX + state)
    except Exception as error:  # pragma: no cover - phụ thuộc hạ tầng
        raise OAuthError("Không xác thực được phiên đăng nhập. Thử lại sau.") from error
    if not raw:
        raise OAuthError("Phiên đăng nhập đã hết hạn hoặc đã dùng rồi. Thử lại.")
    data = json.loads(raw)
    return FlowState(provider=data["provider"], nonce=data["nonce"], next_path=data["next"])


# --- dựng URL và đổi mã ------------------------------------------------------


def authorize_url(provider: Provider, state: str, nonce: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": client_id(provider),
        "redirect_uri": redirect_uri(provider),
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
        "nonce": nonce,
    }
    if provider.form_post:
        params["response_mode"] = "form_post"
    else:
        # Buộc Google trả về màn chọn tài khoản thay vì im lặng dùng phiên đang
        # mở: máy dùng chung là chuyện bình thường với người học.
        params["prompt"] = "select_account"
    return f"{provider.authorize_url}?{urlencode(params)}"


def exchange_code(provider: Provider, code: str) -> str:
    """Đổi mã uỷ quyền lấy `id_token` thô (chưa xác minh)."""
    data = {
        "client_id": client_id(provider),
        "client_secret": client_secret(provider),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri(provider),
    }
    try:
        response = httpx.post(provider.token_url, data=data, timeout=10.0)
    except httpx.HTTPError as error:
        raise OAuthError(f"Không liên hệ được {provider.label}.") from error
    if response.status_code != 200:
        # In nguyên phần thân của nhà cung cấp vào log là để dò được lỗi cấu hình
        # (`redirect_uri_mismatch` là lỗi phổ biến nhất), nhưng KHÔNG trả nó ra
        # cho người dùng: nó nói về khoá và URI của ta, không nói gì về họ.
        raise OAuthError(f"{provider.label} từ chối yêu cầu đăng nhập.")
    token = response.json().get("id_token")
    if not token:
        raise OAuthError(f"{provider.label} không trả về danh tính.")
    return str(token)


def _jwks(provider: Provider) -> dict[str, Any]:
    try:
        response = httpx.get(provider.jwks_url, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise OAuthError(f"Không lấy được khoá công khai của {provider.label}.") from error
    return dict(response.json())


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None
    email_verified: bool
    private_email: bool
    display_name: str | None


def verify_id_token(provider: Provider, raw_token: str, nonce: str) -> Identity:
    """Xác minh chữ ký và các claim, rồi rút ra danh tính.

    Bốn thứ đều phải kiểm và bỏ cái nào cũng mở một lỗ khác nhau: **chữ ký** (ai
    cũng ghép được một JWT), **`aud`** (token cấp cho ứng dụng KHÁC của cùng nhà
    cung cấp sẽ dùng được ở đây — lỗ kinh điển của OAuth), **`iss`**, và
    **`nonce`** (phát lại một token cũ đã chặn được).
    """
    try:
        claims = jwt.decode(
            raw_token,
            _jwks(provider),
            algorithms=["RS256", "ES256"],
            audience=client_id(provider),
            options={"verify_at_hash": False},
        )
    except JWTError as error:
        raise OAuthError(f"Danh tính {provider.label} không hợp lệ.") from error

    if claims.get("iss") not in provider.issuers:
        raise OAuthError(f"Danh tính {provider.label} không hợp lệ.")
    if claims.get("nonce") != nonce:
        raise OAuthError("Phiên đăng nhập không khớp. Thử lại.")

    subject = claims.get("sub")
    if not subject:
        raise OAuthError(f"{provider.label} không trả về định danh.")

    email = claims.get("email")
    verified = claims.get("email_verified")
    # Apple gửi chuỗi "true"/"false"; Google gửi boolean. Một phép so `is True`
    # ở đây sẽ coi mọi tài khoản Apple là chưa xác minh, và luật liên kết bên
    # dưới im lặng ngừng hoạt động.
    email_verified = verified is True or verified == "true"
    private = claims.get("is_private_email")
    private_email = private is True or private == "true"

    return Identity(
        subject=str(subject),
        email=str(email).lower() if email else None,
        email_verified=email_verified,
        private_email=private_email,
        display_name=claims.get("name") or None,
    )


# --- luật liên kết -----------------------------------------------------------


def may_link_by_email(identity: Identity) -> bool:
    """Có được phép gắn danh tính này vào một tài khoản CÙNG EMAIL đã có không?

    Chỉ khi nhà cung cấp nói email ĐÃ XÁC MINH và nó không phải địa chỉ chuyển
    tiếp ẩn. Gắn bừa theo email là một đường chiếm tài khoản có thật: ai tạo được
    một danh tính mang email của người khác sẽ vào thẳng tài khoản đó.

    Địa chỉ ẩn của Apple (`@privaterelay.appleid.com`) bị loại vì lý do khác:
    nó là địa chỉ Apple sinh riêng cho ứng dụng này, nên nó gần như không bao giờ
    trùng với email tài khoản cũ — mà nếu trùng thì đó là dấu hiệu có gì đó sai,
    không phải một cơ hội để gộp.
    """
    return bool(identity.email) and identity.email_verified and not identity.private_email


def deterministic_email(provider: Provider, subject: str) -> str:
    """Email nội bộ cho danh tính không kèm email dùng được.

    `users.email` là NOT NULL và UNIQUE, và nó là thứ hiện trên giao diện — nên
    một tài khoản không có email vẫn cần MỘT giá trị ổn định, không đụng ai. Suy
    từ `sub` nên chạy lại bao nhiêu lần cũng ra đúng chuỗi cũ.

    `.invalid` là tên miền dành riêng của RFC 2606: nó không thể tồn tại thật,
    nên không có nguy cơ trùng với hộp thư của người nào.
    """
    return f"{provider.id}-{uuid.uuid5(uuid.NAMESPACE_URL, subject).hex}@toeicpilot.invalid"
