"""Every command we tell someone to run must actually run.

This exists because it already went wrong: eighteen places — error messages, admin
UI copy, module docstrings, planning docs — told the reader to run
`python -m app.content.backfill_audio`, which fails with `command not found` on a
machine that has not installed a system Python. The project uses `uv`, and
`CLAUDE.md` says so in bold, but nothing checked.

That class of mistake is invisible to every other gate: the code is correct, the
tests pass, the types check. Only a person following the instructions finds out.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

SEARCH_ROOTS = (
    REPO_ROOT / "apps" / "api" / "app",
    REPO_ROOT / "apps" / "web" / "src",
    REPO_ROOT / "planning",
)
SUFFIXES = {".py", ".ts", ".tsx", ".md"}

# A bare `python -m app.…` not already prefixed with `uv run`.
BARE_PYTHON = re.compile(r"(?<!uv run )\bpython -m app\.")


def source_files() -> list[Path]:
    return [
        path
        for root in SEARCH_ROOTS
        if root.is_dir()
        for path in root.rglob("*")
        if path.suffix in SUFFIXES and path.is_file() and "__pycache__" not in path.parts
    ]


def test_no_documented_command_omits_uv_run() -> None:
    offenders: list[str] = []
    for path in source_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if BARE_PYTHON.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()[:80]}")

    assert not offenders, (
        "These tell the reader to run a bare `python`, which this project does not "
        "provide — every entry point goes through `uv run`:\n  " + "\n  ".join(offenders)
    )


def test_the_check_would_catch_a_regression() -> None:
    # Guards the guard: a regex that matched nothing would make the test above
    # pass forever without proving anything.
    assert BARE_PYTHON.search("run python -m app.content.seed")
    assert not BARE_PYTHON.search("uv run python -m app.content.seed")
