"""Configuration for the offline content pipeline.

Deliberately a separate settings object from `app.core.config`. The pipeline is
the only thing that ever *writes* to the object store, so its credentials have no
business sitting in the environment of a process that serves HTTP. Keeping the
two apart means a leak in the API cannot hand an attacker write access to the
audio bucket.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.content.manifest import DEFAULT_MANIFEST_PATH
from app.core.media import DEFAULT_MEDIA_ROOT

# settings.py -> content -> app -> apps/api
_API_DIR = Path(__file__).resolve().parents[2]


class ContentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_API_DIR.parents[1] / ".env", _API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    object_store_dir: Path = DEFAULT_MEDIA_ROOT
    manifest_path: Path = DEFAULT_MANIFEST_PATH

    # A deliberate manual knob, NOT the installed edge-tts version. It feeds the
    # source hash, so deriving it from the package would mean every routine
    # dependency bump invalidated the entire audio library and forced a full
    # regeneration. Bump this only when you actually want everything re-synthesised.
    tts_engine_version: str = "2"
    """Phiên bản 2 = giọng đọc chậm lại còn `tts_rate`.

    Nó nằm trong `source_hash`, nên hai clip cùng một câu nhưng khác phiên bản có
    khoá khác nhau và **không lẫn vào nhau được**. Đó là lý do phải nâng số này
    khi đổi tốc độ: không nâng thì clip mới băm ra đúng khoá của clip cũ,
    `get_or_create` thấy đã có nên bỏ qua, và việc thu lại lặng lẽ không xảy ra.

    Lưu ý một chỗ mà dòng chú thích cũ hứa hơi rộng: nâng số này KHÔNG tự làm
    kho audio cũ thành `STALE`. `media_state` cố ý đọc engine và phiên bản từ
    **chính hàng asset** chứ không từ cấu hình, vì câu hỏi ở đó là "clip này có
    đọc đúng câu này không" — và một clip đọc nhanh vẫn đọc đúng chữ. Muốn thu
    lại thật thì phải nói ra: `backfill_audio --force`.
    """

    # Tốc độ đọc, truyền thẳng cho edge-tts.
    #
    # Mặc định của edge-tts (`+0%`) là giọng đọc bản tin, và ĐO ĐƯỢC là quá
    # nhanh cho việc luyện nghe: trên 5 câu thật, bỏ khoảng lặng đầu/cuối,
    # trung vị là **188 từ/phút** và câu nhanh nhất chạm 230. Đề TOEIC thật chạy
    # khoảng 150–170.
    #
    # Đo lại ở các mức (cùng 5 câu, cùng cách đo):
    #
    #     +0%   188 wpm   (dải 177–230)   4,27 s mỗi câu
    #     -20%  151 wpm   (dải 141–185)   5,32 s
    #     -25%  142 wpm   (dải 133–173)   5,67 s
    #     -30%  132 wpm   (dải 124–162)   6,07 s
    #
    # Chọn -20% để **bằng đề thật**, không chậm hơn: luyện dưới tốc độ thi là
    # luyện một thứ sẽ không gặp, và ngày vào phòng thi mới biết.
    #
    # Đổi số này thì phải nâng `tts_engine_version` cùng lúc, nếu không clip mới
    # và clip cũ dùng chung một khoá.
    tts_rate: str = "-20%"

    # Wikimedia — the most likely source of openly-licensed photographs — returns
    # 403 to clients that do not identify themselves, and their policy asks for a
    # contact address. A default library User-Agent simply does not work.
    http_user_agent: str = (
        "ToeicPilot-content/1.0 (offline content pipeline; contact: dev@localhost)"
    )

    # Public archives rate-limit bulk downloads: Wikimedia returned 429 partway
    # through the very first three-image run. A pause between fetches costs
    # nothing in an offline pipeline and keeps us a well-behaved client.
    image_fetch_delay_seconds: float = 1.5

    # The image counterpart of tts_engine_version, and the same warning applies:
    # it feeds the source hash, so bumping it re-fetches the whole image library.
    image_transform_version: str = "1"

    tts_max_attempts: int = 4
    tts_backoff_seconds: float = 2.0

    # Reserved for the Cloudflare R2 migration (PHASE2-AUDIO A5). Unset until
    # there is a domain on Cloudflare DNS; the API runtime never reads these.
    r2_account_id: str | None = None
    r2_bucket: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None


content_settings = ContentSettings()
