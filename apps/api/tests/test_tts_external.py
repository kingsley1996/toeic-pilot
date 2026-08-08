"""Live checks against Microsoft's TTS endpoint.

Marked `external` and deselected by default — `integration` already means
"needs real PostgreSQL", and this is a different kind of dependency: a
third-party service we do not control, do not pay for, and are not entitled to
hammer. CI must never run these.

The env guard is belt-and-braces: `addopts` deselects the marker, but an explicit
`-m` on the command line replaces `addopts` entirely, and the documented
`pytest -m "not integration"` would otherwise quietly re-select these.

    TOEIC_ALLOW_EXTERNAL_TTS=1 uv run pytest -m external
"""

import os

import pytest

from app.content.settings import ContentSettings
from app.content.tts import LOGICAL_VOICES, EdgeTTSEngine

pytestmark = [
    pytest.mark.external,
    pytest.mark.skipif(
        os.environ.get("TOEIC_ALLOW_EXTERNAL_TTS") != "1",
        reason="set TOEIC_ALLOW_EXTERNAL_TTS=1 to call the live edge-tts endpoint",
    ),
]


@pytest.mark.asyncio
async def test_every_logical_voice_exists_upstream() -> None:
    """Catch a renamed or retired provider voice before a bulk run does.

    A wrong id here fails one clip at a time, halfway through generating a
    library, which is a slow and confusing way to find a typo.
    """
    import edge_tts

    available = {voice["ShortName"] for voice in await edge_tts.list_voices()}
    missing = {
        name: logical.edge
        for name, logical in LOGICAL_VOICES.items()
        if logical.edge not in available
    }
    assert not missing, f"provider voices no longer available upstream: {missing}"


def test_synthesize_returns_playable_mp3() -> None:
    from app.content.generate import probe_duration_ms

    data = EdgeTTSEngine(ContentSettings()).synthesize("The invoice is due.", "us_female_1")

    assert len(data) > 1000
    assert probe_duration_ms(data) > 0
