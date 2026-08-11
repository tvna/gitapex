from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"

pytestmark = pytest.mark.slow


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


def test_skips_self_plugin_registration_without_apm_yml_even_with_a_real_git_repo(
    tmp_path: Path,
) -> None:
    # Issue #773's own apm.yml guard, same rationale as issue #749's
    # pre-existing prek-install guard just above it in the script:
    # registering a marketplace named "gitapex" only makes sense inside an
    # actual gitapex checkout.
    other_repo = tmp_path / "some-other-checkout"
    other_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(other_repo), check=True)
    result = _run({"CLAUDE_CODE_REMOTE": "true", "CLAUDE_PROJECT_DIR": str(other_repo)})
    assert result.returncode == 0
    assert "skipping gitapex's own plugin registration (not a gitapex checkout)" in result.stderr


def test_exits_zero_and_warns_when_claude_cli_not_on_path() -> None:
    # Issue #773: a session-start environment with no `claude` binary on
    # PATH (e.g. a bare CI runner, unlike this repository's own Claude
    # Code sessions where `claude` is always present) must still exit 0
    # and explain why self-plugin registration was skipped, not crash --
    # same shape as test_exits_zero_and_warns_when_uv_not_on_path above,
    # for the sibling `command -v claude` guard.
    required = ("bash", "python3", "sh", "test", "echo", "git")
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
    assert "claude CLI not found on PATH; skipping gitapex's own plugin registration" in result.stderr


def _init_bare_origin_with_commit(origin_dir: Path, branch: str) -> None:
    subprocess.run(["git", "init", "-q", "--bare", "--initial-branch", branch, str(origin_dir)], check=True)
    seed_dir = origin_dir.parent / f"{origin_dir.name}-seed"
    subprocess.run(["git", "clone", "-q", str(origin_dir), str(seed_dir)], check=True)
    (seed_dir / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(seed_dir), check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "seed"],
        cwd=str(seed_dir),
        check=True,
    )
    subprocess.run(["git", "push", "-q", "origin", branch], cwd=str(seed_dir), check=True)


def _clone_work_repo(origin_dir: Path, work_dir: Path) -> None:
    subprocess.run(["git", "clone", "-q", str(origin_dir), str(work_dir)], check=True)


def _assert_no_fetch_happened(work_dir: Path) -> None:
    # A fresh `git clone` never writes FETCH_HEAD on its own (verified
    # against this environment's git); a skip path that fetched anyway
    # despite its own warning would still leave the warning text present,
    # so asserting the warning alone cannot catch that regression -- only
    # checking the actual repository state can.
    assert not (work_dir / ".git" / "FETCH_HEAD").exists()


def test_fetches_the_configured_default_branch_from_origin(tmp_path: Path) -> None:
    # Issue #1033: .gitapex/default-branch.json's own presence is the gate
    # for this step (see the script's own comment for why the branch name
    # lives there and not in .gitapex/ssot.json). A local file:// origin,
    # not the real GitHub remote, keeps this deterministic and offline-safe
    # rather than depending on live network access to github.com.
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    _init_bare_origin_with_commit(origin_dir, "release")
    _clone_work_repo(origin_dir, work_dir)
    (work_dir / ".gitapex").mkdir()
    (work_dir / ".gitapex" / "default-branch.json").write_text('{"default_branch": "release"}\n', encoding="utf-8")

    # Advance the origin past what work_dir cloned, so a real fetch is the
    # only way work_dir's remote-tracking ref could move.
    seed_dir = tmp_path / "origin.git-seed"
    (seed_dir / "README.md").write_text("seed\nmore\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(seed_dir), check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "advance"],
        cwd=str(seed_dir),
        check=True,
    )
    subprocess.run(["git", "push", "-q", "origin", "release"], cwd=str(seed_dir), check=True)
    advanced_sha = subprocess.run(
        ["git", "rev-parse", "release"], cwd=str(seed_dir), check=True, capture_output=True, text=True
    ).stdout.strip()

    result = _run({"CLAUDE_CODE_REMOTE": "true", "CLAUDE_PROJECT_DIR": str(work_dir)})

    assert result.returncode == 0
    fetch_head_sha = subprocess.run(
        ["git", "rev-parse", "FETCH_HEAD"], cwd=str(work_dir), check=True, capture_output=True, text=True
    ).stdout.strip()
    assert fetch_head_sha == advanced_sha


def test_skips_fetch_and_warns_when_default_branch_config_is_missing(tmp_path: Path) -> None:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    _init_bare_origin_with_commit(origin_dir, "main")
    _clone_work_repo(origin_dir, work_dir)

    result = _run({"CLAUDE_CODE_REMOTE": "true", "CLAUDE_PROJECT_DIR": str(work_dir)})

    assert result.returncode == 0
    assert "default-branch.json not found; skipping default-branch fetch" in result.stderr
    _assert_no_fetch_happened(work_dir)


def test_skips_fetch_and_warns_when_default_branch_value_is_empty(tmp_path: Path) -> None:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    _init_bare_origin_with_commit(origin_dir, "main")
    _clone_work_repo(origin_dir, work_dir)
    (work_dir / ".gitapex").mkdir()
    (work_dir / ".gitapex" / "default-branch.json").write_text('{"default_branch": ""}\n', encoding="utf-8")

    result = _run({"CLAUDE_CODE_REMOTE": "true", "CLAUDE_PROJECT_DIR": str(work_dir)})

    assert result.returncode == 0
    assert "default_branch is missing/empty; skipping fetch" in result.stderr
    _assert_no_fetch_happened(work_dir)


@pytest.mark.parametrize(
    "malformed_branch",
    [
        "release:refs/heads/unrelated",  # refspec-shaped -- must not update an unintended local ref
        "@{-1}",  # indirect syntax -- git check-ref-format --branch resolves this to a commit-ish
        "topic..invalid",  # rejected outright by git check-ref-format
    ],
)
def test_skips_fetch_and_warns_when_default_branch_is_not_an_exact_branch_name(
    tmp_path: Path, malformed_branch: str
) -> None:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    _init_bare_origin_with_commit(origin_dir, "main")
    _clone_work_repo(origin_dir, work_dir)
    (work_dir / ".gitapex").mkdir()
    (work_dir / ".gitapex" / "default-branch.json").write_text(
        json.dumps({"default_branch": malformed_branch}), encoding="utf-8"
    )

    result = _run({"CLAUDE_CODE_REMOTE": "true", "CLAUDE_PROJECT_DIR": str(work_dir)})

    assert result.returncode == 0
    assert "is not a valid exact branch name; skipping fetch" in result.stderr
    _assert_no_fetch_happened(work_dir)
    # The refspec case's own attack: a `git fetch origin
    # "release:refs/heads/unrelated"` would silently create refs/heads/unrelated.
    assert not (work_dir / ".git" / "refs" / "heads" / "unrelated").exists()


def test_exits_zero_and_warns_when_origin_is_unreachable(tmp_path: Path) -> None:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    _init_bare_origin_with_commit(origin_dir, "main")
    _clone_work_repo(origin_dir, work_dir)
    (work_dir / ".gitapex").mkdir()
    (work_dir / ".gitapex" / "default-branch.json").write_text('{"default_branch": "main"}\n', encoding="utf-8")
    # Point origin at a path with no git repository at all, so the fetch
    # fails fast (no such repository) rather than hanging -- proving the
    # fail-soft path still holds now that the fetch is wrapped in
    # GIT_TERMINAL_PROMPT=0 / timeout.
    subprocess.run(
        ["git", "-C", str(work_dir), "remote", "set-url", "origin", str(tmp_path / "does-not-exist.git")],
        check=True,
    )

    result = _run({"CLAUDE_CODE_REMOTE": "true", "CLAUDE_PROJECT_DIR": str(work_dir)})

    # Deliberately not asserting FETCH_HEAD's absence here: a fetch that
    # fails still touches/creates an (empty) FETCH_HEAD as part of git's
    # own fetch machinery -- that check only distinguishes "never
    # attempted" (the skip-path tests above) from "attempted", not
    # "attempted and failed" from "attempted and succeeded".
    assert result.returncode == 0
    assert "could not fetch default branch 'main' from origin this session (non-fatal)" in result.stderr


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
