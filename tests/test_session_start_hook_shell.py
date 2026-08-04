from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"


def _run(env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_REMOTE", None)
    env.pop("CLAUDE_ENV_FILE", None)
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=15, env=env, cwd=str(REPO_ROOT)
    )


def test_script_exists_and_is_executable() -> None:
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & stat.S_IXUSR


def test_exits_zero_and_noop_when_not_remote() -> None:
    result = _run({"CLAUDE_PROJECT_DIR": str(REPO_ROOT)})
    assert result.returncode == 0


def test_exits_zero_even_when_python3_reports_failure(tmp_path: Path) -> None:
    # A directory with no flake.nix makes provision_class_b.py fail fast --
    # the hook itself must still exit 0 (never block session start).
    fake_project = tmp_path / "not-a-real-checkout"
    fake_project.mkdir()
    result = _run(
        {
            "CLAUDE_CODE_REMOTE": "true",
            "CLAUDE_PROJECT_DIR": str(fake_project),
        }
    )
    assert result.returncode == 0
