"""Shared pytest fixtures/helpers for this repository's tests/ suite."""

from __future__ import annotations

import pathlib
import re
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

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
    assert result.returncode == 0, (
        f"{description} is no longer covered by .gitignore."
    )
    match = _CHECK_IGNORE_SOURCE_RE.match(result.stdout)
    assert match is not None, (
        f"could not parse 'git check-ignore -v' output for {description}: "
        f"{result.stdout!r}"
    )
    source = match.group(1)
    repo_gitignore = REPO_ROOT / ".gitignore"
    assert pathlib.Path(source).resolve() == repo_gitignore.resolve(), (
        f"{description} is ignored, but by {source!r} instead of this "
        f"repository's own {repo_gitignore} -- an ambient exclude source "
        "(global core.excludesFile, $GIT_DIR/info/exclude) is masking a "
        "possibly-removed repository rule."
    )
