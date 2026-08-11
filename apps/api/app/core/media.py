"""Content-addressed naming for audio assets.

Pure stdlib on purpose. Both the runtime API and the offline content pipeline
(`app.content`, which lives behind the optional `content` extra) need these
helpers, so they sit in `core` where either side can import them without
dragging in a dependency the other does not have.

See `planning/PHASE2-AUDIO.md` A4.2 and A4.3 for why the hash is built the way
it is; both invariants are easy to break and neither breaks loudly.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

# Unit separator. A printable delimiter such as "|" would let a source text
# containing that character collide with a different (text, voice) pair;
# \x1f cannot appear in the transcripts we feed to TTS.
_FIELD_SEP = "\x1f"

AUDIO_KEY_PREFIX = "audio"
IMAGE_KEY_PREFIX = "image"
# Tiền tố riêng cho avatar: media người dùng và media nội dung nằm hai nhánh
# khác nhau ngay ở đường dẫn, nên một lệnh dọn nhắm vào nhánh này không thể vô
# tình chạm vào nhánh kia.
AVATAR_KEY_PREFIX = "avatar"

# Kept as plain tuples rather than a native PostgreSQL enum: adding a value to a
# native enum needs its own migration, and Alembic downgrades across enum types
# are painful enough that a CHECK constraint is the cheaper trade.
AUDIO_SOURCES = ("tts", "scraped", "uploaded")

# Giá trị của `audio_asset.voice` cho một clip nhiều giọng. Cột đó chỉ giữ được
# một giọng, mà câu hỏi "clip này giọng nào" không có câu trả lời đơn cho một
# đoạn hội thoại — nên nó trả lời trung thực là "nhiều", và chi tiết từng lượt
# nằm ở `source_text` dưới dạng có nhãn.
MULTI_VOICE = "multi"

# BCP-47 tags for the four accents TOEIC listening requires. Free text here would
# make "en-us", "US" and "American" all look like distinct accents to a query.
AUDIO_ACCENTS = ("en-US", "en-GB", "en-AU", "en-CA")

# Tên giọng LOGIC và accent của nó. Ở `core` chứ không ở `content/tts.py`, vì
# hai phía đều cần và chỉ `core` là chỗ cả hai import được: trình dán đề chạy
# lúc có REQUEST và phải kiểm tên giọng, còn `app.content` nằm sau extra
# `content` mà ảnh production không có (A4.1).
#
# Ánh xạ sang id của nhà cung cấp (`en-US-JennyNeural`) thì KHÔNG ở đây — đó
# đúng là thứ A4.3 nói phải giữ ở phía offline, để đổi engine không làm hỏng
# hash của mọi asset đã sinh.
LOGICAL_VOICE_ACCENTS: dict[str, str] = {
    "us_female_1": "en-US",
    "us_male_1": "en-US",
    "uk_female_1": "en-GB",
    "uk_male_1": "en-GB",
    "au_female_1": "en-AU",
    "au_male_1": "en-AU",
    "ca_female_1": "en-CA",
    "ca_male_1": "en-CA",
}

# media.py -> core -> app -> apps/api
_API_DIR = Path(__file__).resolve().parents[2]

# Where generated audio lands on disk. Defined here rather than in either
# settings object because two of them need it — the API (to serve /media in
# development) and the offline pipeline (to write into) — and they must not
# be free to disagree. Each may still override it from the environment.
DEFAULT_MEDIA_ROOT = _API_DIR / "media"


def _digest(*fields: str) -> str:
    return hashlib.sha256(_FIELD_SEP.join(fields).encode("utf-8")).hexdigest()


def source_hash(text: str, voice: str, engine: str, engine_version: str) -> str:
    """Fingerprint the INPUT to a synthesis, never the resulting bytes.

    TTS is not byte-deterministic: synthesising the same sentence twice yields
    two different mp3s. Hashing the output would therefore hand back a new hash
    on every run, turning "skip what already exists" into "insert a duplicate".
    Hashing the input is what makes the pipeline resumable and `seed` idempotent.

    `voice` must be a logical voice (``us_female_1``), not a provider voice id
    (``en-US-JennyNeural``). Provider ids in the hash would invalidate every
    existing asset the day the engine changes — see A4.3.
    """
    return _digest(text, voice, engine, engine_version)


# Khoảng lặng CỘNG THÊM giữa hai lượt nói, khi không có gì nói khác đi.
#
# "Cộng thêm" là chỗ dễ hiểu nhầm nhất, nên đo thật rồi ghi lại: edge-tts tự
# chèn khoảng **1,1 giây** đệm ở mỗi ranh giới lượt (cuối lượt trước + đầu lượt
# sau). Đo bằng `silencedetect` trên clip Part 2 đã sinh: đặt `gap_ms=600` cho
# ra khoảng lặng thật ~1,74 s. Nên `gap_ms=0` KHÔNG phải là không có khoảng
# lặng — nó là ~1,1 s, vốn đã là một nhịp hội thoại tự nhiên.
#
# Ai chỉnh con số này mà chờ nó là tổng sẽ thấy nội dung nghe lê thê mà không
# hiểu vì sao, nên đừng bỏ đoạn ghi chú này đi.
#
# Nó nằm TRONG `conversation_source_hash`, nên đổi con số ở đây sẽ làm mọi đoạn
# hội thoại không tự khai `gap_ms` phải sinh lại — cùng loại với
# `tts_engine_version`.
#
# Ở `core` chứ không ở `app/content/generate.py` vì `app/services/media_state.py`
# cũng cần nó để hỏi "clip này có còn khớp lời thoại không", mà `media_state` do
# API import nên không được chạm vào `app.content` (A4.1). Cùng lý do đã dời
# `LOGICAL_VOICE_ACCENTS` sang đây.
DEFAULT_GAP_MS = 700


def script_fingerprint(turns: Sequence[tuple[str, str]] | None) -> str | None:
    """Vân tay của LỜI THOẠI, để biết bản thu đã gắn có còn ứng với nó không.

    Khác `conversation_source_hash`: cái kia băm đầu vào của một lần *tổng hợp*
    — có engine, có khoảng lặng — để trả lời "đã sinh clip này chưa". Cái này
    chỉ hỏi "chữ và giọng có đổi không", vì bản thu tải lên KHÔNG do ta sinh ra:
    `source_hash` của nó băm một id ngẫu nhiên và không suy ngược về lời thoại
    được (ADR-007 §2.7).

    Cặp mốc thời gian không thay được nó. `audio_attached_at` do đồng hồ Python
    ghi, `updated_at` do đồng hồ database ghi qua `func.now()`, nên phép so sánh
    phụ thuộc hai chiếc đồng hồ khớp nhau — lệch vài giây theo chiều xấu là mọi
    thứ báo lệch ngay khi vừa gắn. Trên SQLite `CURRENT_TIMESTAMP` lại chỉ có độ
    phân giải một giây, nên sửa xong trong cùng giây với lúc gắn thì im lặng.
    Vân tay không cần đồng hồ nào cả, và nó chỉ đổi khi thứ bản thu ứng với đổi:
    sửa một dấu phẩy trong phần giải thích không còn làm nó kêu oan.

    Không có lượt nói nào thì không có gì để đối chiếu, nên trả về None chứ
    không phải hash của chuỗi rỗng — "chưa có lời thoại" chỉ nên có một cách
    viết trong database.
    """
    if not turns:
        return None
    fields: list[str] = ["script", str(len(turns))]
    for text, voice in turns:
        fields.extend((text, voice))
    return _digest(*fields)


def conversation_source_hash(
    turns: Sequence[tuple[str, str]],
    gap_ms: int,
    engine: str,
    engine_version: str,
) -> str:
    """Fingerprint a clip made of several turns, each in its own voice.

    Same principle as `source_hash` — băm ĐẦU VÀO, không băm bytes — nhưng đầu
    vào ở đây là cả danh sách lượt nói. Ba điều phải nằm trong hash, và bỏ sót
    bất kỳ cái nào cũng hỏng im lặng:

    - **Thứ tự các lượt.** Đảo hai lượt là một đoạn hội thoại khác hẳn. Vì
      `_digest` nối các trường bằng `\x1f` theo đúng thứ tự truyền vào, thứ tự
      đã nằm trong hash — nhưng chỉ khi ta trải các lượt ra chứ không sắp xếp.
    - **`gap_ms`.** Khoảng lặng giữa các lượt là một phần của file phát ra. Đổi
      nó mà hash không đổi thì lần sinh sau sẽ "bỏ qua vì đã có", và bản thu cũ
      với nhịp cũ ở lại vĩnh viễn.
    - **Số lượt** (`len`). Không có nó, [("ab",v)] và [("a",v),("b",v)]... thực
      ra vẫn khác nhau nhờ `\x1f`, nhưng ghi số lượt vào là hàng rào rẻ tiền
      cho mọi cách trải phẳng mà ai đó sửa về sau.

    Chuỗi mở đầu `"conversation"` giữ cho một hội thoại MỘT lượt không bao giờ
    băm trùng với một clip đơn cùng text và giọng. Trùng thì hai thứ được tạo
    bằng hai đường khác nhau — một cái đi qua ffmpeg, một cái không — sẽ dùng
    chung một `storage_key`, và cái tới sau lặng lẽ thắng.
    """
    fields: list[str] = ["conversation", str(len(turns)), str(gap_ms), engine, engine_version]
    for text, voice in turns:
        fields.extend((text, voice))
    return _digest(*fields)


def image_source_hash(source_url: str, transform_version: str) -> str:
    """Fingerprint a sourced image by where it came from and how it is processed.

    Hashing the downloaded bytes would be defensible — unlike TTS, a download is
    reproducible — but we never store those bytes. The pipeline resizes and
    re-encodes first, and Pillow makes no promise that two versions produce
    identical output. Hashing the result would therefore invalidate the whole
    library on a routine dependency bump, exactly the failure A4.2 avoids for
    audio.

    `transform_version` is the deliberate manual knob, the counterpart of
    `tts_engine_version`: bump it when you actually want everything re-fetched.
    """
    return _digest(source_url, transform_version, "image")


def storage_key_for(
    source_hash_value: str, ext: str = "mp3", prefix: str = AUDIO_KEY_PREFIX
) -> str:
    """Object-store key for an asset: ``audio/ab/abcdef....mp3``.

    The two-character shard keeps a local directory listing usable once the
    library grows; it is inert on an object store, which has no directories.
    """
    if len(source_hash_value) < 2:
        raise ValueError(f"source_hash is too short to shard: {source_hash_value!r}")
    return f"{prefix}/{source_hash_value[:2]}/{source_hash_value}.{ext}"


def image_storage_key_for(source_hash_value: str, ext: str = "jpg") -> str:
    return storage_key_for(source_hash_value, ext=ext, prefix=IMAGE_KEY_PREFIX)


def avatar_storage_key_for(source_hash_value: str, ext: str = "jpg") -> str:
    return storage_key_for(source_hash_value, ext=ext, prefix=AVATAR_KEY_PREFIX)


def public_audio_url(storage_key: str, base_url: str | None = None) -> str:
    """Join the public base URL and a storage key into a playable URL.

    Serving is a string join and nothing more: the runtime never calls the
    object store to produce a URL (A2.4). `base_url` defaults to
    `settings.audio_public_base_url`; it is a parameter so the content pipeline
    and tests can point elsewhere without mutating global settings.
    """
    if base_url is None:
        # Imported lazily: settings reads .env at import time, and this module is
        # also used by offline tooling that should not need a configured app.
        from app.core.config import settings

        base_url = settings.audio_public_base_url
    return f"{base_url.rstrip('/')}/{storage_key.lstrip('/')}"


def upload_source_hash(upload_id: str, transform_version: str = "1") -> str:
    """Danh tính của một lần upload — **không** phải địa chỉ nội dung.

    Mọi `source_hash` khác trong hệ băm *đầu vào sinh ra file*: text + giọng cho
    audio, URL nguồn + phiên bản biến đổi cho ảnh lấy về. Nhờ vậy sinh lại cho
    ra đúng khoá cũ, và `media_state` phát hiện được clip đã lệch khỏi text.

    File do người tải lên không có đầu vào nào như thế. Nó không tái tạo được —
    đó chính là lý do phải upload — nên ở đây `source_hash` chỉ còn giữ vai trò
    khoá duy nhất, và nó băm một id ngẫu nhiên do phía ta sinh ra.
    """
    return _digest("upload", upload_id, transform_version)
