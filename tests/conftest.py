"""Shared pytest fixtures/helpers for this repository's tests/ suite."""

from __future__ import annotations

import io
import pathlib
import re
import subprocess

from pydantic import BaseModel, ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Unsatisfiable(BaseModel):
    """Throwaway model with one required field, used only by
    `make_validation_error` below to manufacture a real pydantic
    `ValidationError` instance."""

    required: int


def make_validation_error() -> ValidationError:
    """A genuine `pydantic.ValidationError` instance, for monkeypatching a
    gate's own `*Args` model class to exercise its `except ValidationError`
    branch in tests. Several `.github/scripts/gitapex_gate_*.py` gates
    (issue #1062, wave 3 of #1040's batch) wrap `argparse`-guaranteed CLI
    input in a pydantic model whose fields can never actually fail
    validation from real CLI input -- their `except ValidationError` branch
    is therefore only reachable by monkeypatching the model class itself to
    raise, not by constructing genuinely invalid input."""
    try:
        _Unsatisfiable()  # type: ignore[call-arg]
    except ValidationError as error:
        return error
    raise AssertionError("expected ValidationError")


class FakeStdin:
    """Just the surface a CLI's `main()` uses: `sys.stdin.buffer.read()`.

    Shared by every test that monkeypatches `sys.stdin` to feed a script
    non-UTF-8 (or otherwise arbitrary) bytes through its
    `sys.stdin.buffer.read().decode("utf-8")` read path, so a future change
    to this mock's surface only needs to land once (same rationale as
    `assert_path_is_gitignored` below).
    """

    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


# git check-ignore -v prefixes a match with "source:linenum:pattern", then a
# tab and the matched pathname. The pattern (and, in principle, a Windows
# drive-letter source path) can itself contain colons, so a plain split on
# the first ":" can misidentify the source -- anchoring on ":<digits>:" (the
# linenum field, which is always a bare integer) instead finds the correct
# boundary regardless of what precedes or follows it.
_CHECK_IGNORE_SOURCE_RE = re.compile(r"^(.*):\d+:")


def assert_path_is_gitignored(path: pathlib.Path, description: str) -> None:
    """Assert ``path`` is ignored by this repository's own tracked
    `.gitignore` (not an ambient exclude source elsewhere on the machine).

    Shared by every `test_gitignore_*.py` drift gate so a future fix to
    the ambient-exclude-source check only needs to land once.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-v", str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{description} is no longer covered by .gitignore."
    match = _CHECK_IGNORE_SOURCE_RE.match(result.stdout)
    assert match is not None, f"could not parse 'git check-ignore -v' output for {description}: {result.stdout!r}"
    source = match.group(1)
    repo_gitignore = REPO_ROOT / ".gitignore"
    assert pathlib.Path(source).resolve() == repo_gitignore.resolve(), (
        f"{description} is ignored, but by {source!r} instead of this "
        f"repository's own {repo_gitignore} -- an ambient exclude source "
        "(global core.excludesFile, $GIT_DIR/info/exclude) is masking a "
        "possibly-removed repository rule."
    )
