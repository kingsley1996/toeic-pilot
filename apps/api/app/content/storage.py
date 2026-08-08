"""Object stores for generated audio.

`LocalDirStore` today; `S3ObjectStore` when there is a domain on Cloudflare DNS
and the move to R2 is worth making (PHASE2-AUDIO A5). Keys are content-addressed,
so that migration is a file copy plus an environment variable — no call site
changes.
"""

from pathlib import Path
from typing import Protocol

from app.content.settings import ContentSettings, content_settings


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def exists(self, key: str) -> bool:
        """Whether `key` already holds an object.

        The pipeline needs this, not just the manifest: the manifest is committed
        to git while the audio files are not, so a fresh clone has entries whose
        bytes are missing. Skipping on the manifest alone would leave those
        entries permanently unrenderable.
        """
        ...


class LocalDirStore:
    def __init__(self, root: Path | None = None, settings: ContentSettings | None = None) -> None:
        self._root = root if root is not None else (settings or content_settings).object_store_dir

    @property
    def root(self) -> Path:
        return self._root

    def put(self, key: str, data: bytes, content_type: str) -> None:
        # content_type is ignored here — a directory has nowhere to record it, and
        # the /media mount infers it from the extension. It stays in the signature
        # because S3ObjectStore must send it explicitly or R2 stores everything as
        # binary/octet-stream and browsers refuse to seek.
        del content_type
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename: an interrupted bulk run must not leave a truncated
        # mp3 sitting at a key the manifest already claims is complete.
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(path)

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def _path_for(self, key: str) -> Path:
        candidate = (self._root / key).resolve()
        root = self._root.resolve()
        if not candidate.is_relative_to(root):
            raise ValueError(f"storage key escapes the store root: {key!r}")
        return candidate
