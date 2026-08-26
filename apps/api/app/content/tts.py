"""Text-to-speech engines for the offline content pipeline.

`TTSEngine` exists to keep the pipeline free of any one vendor's API, not to
pretend engines are interchangeable. They are not: switching engines changes how
the voices sound, so content generated before and after a switch will not match.
See PHASE2-AUDIO A3 — the real protection against edge-tts breaking is that
generation happens offline, so an outage blocks new content rather than existing
content.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Protocol

from app.content.settings import ContentSettings, content_settings
from app.core.media import LOGICAL_VOICE_ACCENTS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LogicalVoice:
    """A voice named in our terms, mapped to each provider's id separately.

    The logical name is what gets stored and hashed. Provider ids stay on this
    side of the boundary so that swapping engines does not invalidate the hash of
    every asset ever generated.
    """

    accent: str
    edge: str


# TOEIC listening uses four accents (US / UK / AU / CA), so a single voice is
# never enough — the domain schema needs a join table, not an FK column.
# Id của nhà cung cấp, khoá theo tên giọng logic. Danh sách tên và accent nằm ở
# `app/core/media.py` vì phía runtime cũng cần; chỉ phần ánh xạ sang edge-tts ở
# lại đây, đúng như A4.3 yêu cầu.
_EDGE_IDS: dict[str, str] = {
    "us_female_1": "en-US-JennyNeural",
    "us_male_1": "en-US-GuyNeural",
    "uk_female_1": "en-GB-SoniaNeural",
    "uk_male_1": "en-GB-RyanNeural",
    "au_female_1": "en-AU-NatashaNeural",
    "au_male_1": "en-AU-WilliamMultilingualNeural",
    "ca_female_1": "en-CA-ClaraNeural",
    "ca_male_1": "en-CA-LiamNeural",
}

LOGICAL_VOICES: dict[str, LogicalVoice] = {
    name: LogicalVoice(accent=accent, edge=_EDGE_IDS[name])
    for name, accent in LOGICAL_VOICE_ACCENTS.items()
}


def accent_for(voice: str) -> str:
    try:
        return LOGICAL_VOICES[voice].accent
    except KeyError:
        raise ValueError(
            f"unknown logical voice {voice!r}; known voices: {sorted(LOGICAL_VOICES)}"
        ) from None


class TTSEngine(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def synthesize(self, text: str, voice: str) -> bytes:
        """Render `text` in the logical `voice` and return mp3 bytes."""
        ...


class EdgeTTSEngine:
    """edge-tts, Microsoft's Read Aloud endpoint reached through an unofficial client.

    Two failure modes worth expecting: per-IP rate limiting during a bulk run, and
    the periodic 403 storm when Microsoft rotates the `Sec-MS-GEC` signing token
    and every installed copy of the library breaks at once until upstream patches.
    Retry with backoff handles the first. Nothing handles the second except
    waiting — which is survivable only because already-generated audio is on disk.
    """

    def __init__(self, settings: ContentSettings | None = None) -> None:
        self._settings = settings or content_settings

    @property
    def name(self) -> str:
        return "edge-tts"

    @property
    def version(self) -> str:
        return self._settings.tts_engine_version

    def synthesize(self, text: str, voice: str) -> bytes:
        provider_voice = LOGICAL_VOICES[voice].edge if voice in LOGICAL_VOICES else None
        if provider_voice is None:
            raise ValueError(
                f"unknown logical voice {voice!r}; known voices: {sorted(LOGICAL_VOICES)}"
            )

        last_error: Exception | None = None
        for attempt in range(1, self._settings.tts_max_attempts + 1):
            try:
                return asyncio.run(self._stream(text, provider_voice, self._settings.tts_rate))
            except Exception as exc:  # edge-tts surfaces a wide range of failures
                last_error = exc
                if attempt == self._settings.tts_max_attempts:
                    break
                delay = self._settings.tts_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "tts_attempt_failed",
                    extra={"attempt": attempt, "voice": voice, "retry_in": delay},
                )
                time.sleep(delay)

        raise RuntimeError(
            f"edge-tts failed after {self._settings.tts_max_attempts} attempts for "
            f"voice {voice!r}. A burst of 403s usually means Microsoft rotated the "
            f"signing token; upgrading edge-tts is the fix. Already-generated audio "
            f"is unaffected."
        ) from last_error

    @staticmethod
    async def _stream(text: str, provider_voice: str, rate: str) -> bytes:
        import edge_tts

        chunks: list[bytes] = []
        # `rate` đi kèm mọi lần tổng hợp. Không truyền thì edge-tts đọc ở giọng
        # bản tin — đo được là 188 từ/phút, nhanh hơn đề TOEIC thật; lý do đầy đủ
        # ở `ContentSettings.tts_rate`.
        async for chunk in edge_tts.Communicate(text, provider_voice, rate=rate).stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        if not chunks:
            raise RuntimeError("edge-tts returned no audio data")
        return b"".join(chunks)
