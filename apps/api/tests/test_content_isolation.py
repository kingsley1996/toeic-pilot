"""Guard the boundary between the API runtime and the offline content pipeline.

The production image is built with `uv sync --frozen --no-dev` and without the
`content` or `agents` extras, so it has no edge-tts, no mutagen and no langgraph.
If anything reachable from `app.main` ever imports `app.content`, the image stops
booting — and it does so at container start, not at build time, which is a slow
and expensive way to find out.

The `docker` CI job catches this too, by booting the image. This test catches it
in under a second, on the developer's machine, before the push.
"""

import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]

PROBE = """
import sys

import app.main  # noqa: F401

leaked = sorted(m for m in sys.modules if m == "app.content" or m.startswith("app.content."))
print(",".join(leaked))
"""


def test_app_main_does_not_import_the_content_pipeline() -> None:
    # A subprocess, not an assertion over the current sys.modules: this same test
    # session imports app.content elsewhere, so an in-process check would report a
    # leak that does not exist.
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = [name for name in result.stdout.strip().split(",") if name]
    assert not leaked, (
        f"app.main pulls in {leaked}. The production image has none of the "
        f"content or agents extras — no edge-tts, no mutagen, no langgraph — so "
        f"this breaks container startup. Move the shared code into app/core/ "
        f"instead."
    )
