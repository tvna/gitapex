from __future__ import annotations

import os
import shutil
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
    # A directory with no flake.nix makes gitapex_provision_class_b.py fail fast,
    # and the same fake directory (no apm.yml either) then makes the
    # prek-install step's own apm.yml guard (issue #749) skip it too --
    # the hook itself must still exit 0 (never block session start)
    # through both.
    fake_project = tmp_path / "not-a-real-checkout"
    fake_project.mkdir()
    result = _run(
        {
            "CLAUDE_CODE_REMOTE": "true",
            "CLAUDE_PROJECT_DIR": str(fake_project),
        }
    )
    assert result.returncode == 0
    assert "not a gitapex checkout" in result.stderr


def test_installs_the_prek_hook_for_a_real_checkout() -> None:
    # Issue #749: this ephemeral-web session-start path is the third
    # place (alongside CONTRIBUTING.md's manual step and flake.nix's
    # devShell shellHook) prek's hook install must reach -- exercised
    # here against this repository's own real checkout (REPO_ROOT has a
    # real .git/ and, by the time this test runs, a real
    # .pre-commit-config.yaml), not a fake project dir.
    result = _run({"CLAUDE_CODE_REMOTE": "true", "CLAUDE_PROJECT_DIR": str(REPO_ROOT)})
    assert result.returncode == 0
    pre_commit_hook = REPO_ROOT / ".git" / "hooks" / "pre-commit"
    assert pre_commit_hook.exists()
    assert "prek" in pre_commit_hook.read_text(encoding="utf-8")


def test_skips_prek_install_without_apm_yml_even_with_a_real_git_repo(tmp_path: Path) -> None:
    # Issue #749's defense-in-depth guard: an apm.yml presence check,
    # mirroring gitapex_provision_class_b.py's own run_apm_install check ("refusing
    # to run apm install outside a gitapex checkout"). A directory that IS
    # a real git repository (unlike the fake-project test above, which
    # fails for the unrelated reason of not being a git repo at all) but
    # has no apm.yml must still skip the prek-install step -- proving the
    # guard fires on its own specific condition, not accidentally via
    # `prek install` itself failing for some other reason.
    other_repo = tmp_path / "some-other-checkout"
    other_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(other_repo), check=True)
    result = _run({"CLAUDE_CODE_REMOTE": "true", "CLAUDE_PROJECT_DIR": str(other_repo)})
    assert result.returncode == 0
    assert "not a gitapex checkout" in result.stderr
    assert not (other_repo / ".git" / "hooks" / "pre-commit").exists()


def test_exits_zero_and_warns_when_uv_not_on_path() -> None:
    # Simulate a session-start environment with no `uv` on PATH (e.g. a
    # container image that skipped it) -- the hook must still exit 0 and
    # explain why the pre-commit hook was not installed, not crash. PATH
    # is trimmed to only the directories holding the binaries this
    # script itself needs to even run (bash, to exec it; python3, so
    # provisioning still runs) -- `uv`'s own directory is deliberately
    # excluded so `command -v uv` genuinely finds nothing, without
    # otherwise breaking the subprocess launch itself.
    required = ("bash", "python3", "sh", "test", "echo")
    dirs = []
    for tool in required:
        found = shutil.which(tool)
        assert found is not None, f"{tool} must be resolvable for this test to be meaningful"
        tool_dir = str(Path(found).parent)
        if tool_dir not in dirs:
            dirs.append(tool_dir)
    result = _run(
        {
            "CLAUDE_CODE_REMOTE": "true",
            "CLAUDE_PROJECT_DIR": str(REPO_ROOT),
            "PATH": os.pathsep.join(dirs),
        }
    )
    assert result.returncode == 0
    assert "uv not found" in result.stderr
