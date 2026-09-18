"""resolve_source: paste URL YouTube thành source chuẩn, còn lại từ chối đúng mã."""

import pytest

from app.services.listening_source import (
    INVALID_URL,
    UNSUPPORTED_SOURCE,
    SourceError,
    resolve_source,
)

_VIDEO = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={_VIDEO}",
        f"https://youtube.com/watch?v={_VIDEO}&t=42s&list=PLxyz",
        f"http://m.youtube.com/watch?v={_VIDEO}",
        f"https://music.youtube.com/watch?v={_VIDEO}",
        f"https://youtu.be/{_VIDEO}",
        f"youtu.be/{_VIDEO}",
        f"https://www.youtube.com/embed/{_VIDEO}",
        f"https://www.youtube.com/shorts/{_VIDEO}",
        f"https://www.youtube.com/live/{_VIDEO}",
        f"  https://youtu.be/{_VIDEO}?si=abc  ",
    ],
)
def test_youtube_shapes_resolve_to_canonical(url: str) -> None:
    source = resolve_source(url)
    assert source.type == "youtube"
    assert source.external_id == _VIDEO
    assert source.url == f"https://www.youtube.com/watch?v={_VIDEO}"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/watch?v=toolongvideoid123",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/playlist?list=PLxyz",
        "https://www.youtube.com/embed",
        "https://youtu.be/",
        "https://www.youtube.com/@somechannel",
        "",
        "   ",
        "not a url at all!!!",
    ],
)
def test_malformed_youtube_is_invalid_not_unsupported(url: str) -> None:
    with pytest.raises(SourceError) as exc_info:
        resolve_source(url)
    assert exc_info.value.code == INVALID_URL


@pytest.mark.parametrize(
    "url",
    [
        "https://www.tiktok.com/@user/video/7345678901234567890",
        "https://vm.tiktok.com/ZM123abc/",
        "https://vimeo.com/123456789",
        "https://example.com/video.mp4",
    ],
)
def test_non_youtube_is_unsupported(url: str) -> None:
    with pytest.raises(SourceError) as exc_info:
        resolve_source(url)
    assert exc_info.value.code == UNSUPPORTED_SOURCE
