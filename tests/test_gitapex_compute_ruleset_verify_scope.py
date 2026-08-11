"""Unit tests for `.github/scripts/gitapex_compute_ruleset_verify_scope.py`.

Issue #1013 (task 13). This module is the local-reproducibility/pytest
counterpart `ruleset-verify.yml`'s "Resolve scan scope and source of
truth" step never had before this task: previously that step's logic
lived only as inline bash in the workflow file, with no local invocation
and no test coverage at all. Mirrors
`test_gitapex_compute_skill_audit_flags.py`'s own shape for the
analogous extraction (issue #874).

`test_output_matches_the_prior_inline_bash_behavior` is the direct parity
proof: it re-derives each of the four branches via the exact `git`
commands the replaced bash used, and asserts this module's own output
agrees, for both a `pull_request` and a non-`pull_request` event.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

import gitapex_compute_ruleset_verify_scope as scope_module  # noqa: E402


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _commit(repo: pathlib.Path, message: str = "change") -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "t@e")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    _commit(tmp_path, "initial, no ruleset file")
    return tmp_path


def _write_ruleset(repo: pathlib.Path, name: str = "main-protection") -> None:
    ruleset_dir = repo / ".github" / "rulesets"
    ruleset_dir.mkdir(parents=True, exist_ok=True)
    (ruleset_dir / "main.json").write_text(f'{{"name": "{name}"}}\n', encoding="utf-8")


# --- compute_scope: non-pull_request ----------------------------------------


def test_non_pull_request_event_resolves_full_scope_without_touching_git(tmp_path: pathlib.Path) -> None:
    # A directory that is not even a git repo -- proves this branch never
    # shells out to git at all, matching the original bash's own early exit.
    outputs = scope_module.compute_scope("schedule", "", tmp_path, tmp_path, None)
    assert outputs == {"applicable": "true", "scope": "full", "sot": scope_module.MAIN_RULESET_PATH}


def test_workflow_dispatch_event_also_resolves_full_scope(tmp_path: pathlib.Path) -> None:
    outputs = scope_module.compute_scope("workflow_dispatch", "", tmp_path, tmp_path, None)
    assert outputs["scope"] == "full"


# --- compute_scope: pull_request --------------------------------------------


def test_pull_request_missing_base_sha_raises(repo: pathlib.Path) -> None:
    with pytest.raises(scope_module.RulesetVerifyScopeError, match="--base-sha is required"):
        scope_module.compute_scope("pull_request", "", repo, repo, None)


def test_pull_request_unresolvable_base_commit_raises(repo: pathlib.Path) -> None:
    with pytest.raises(scope_module.RulesetVerifyScopeError, match="is not present"):
        scope_module.compute_scope("pull_request", "0" * 40, repo, repo, None)


def test_pull_request_base_lacking_ruleset_file_is_applicable_false(repo: pathlib.Path) -> None:
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    outputs = scope_module.compute_scope("pull_request", base_sha, repo, repo, None)
    assert outputs == {"applicable": "false"}


def test_pull_request_base_with_tree_at_ruleset_path_is_applicable_false(
    repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    # Issue #1024: a *directory* committed at .github/rulesets/main.json
    # (not a blob) must resolve the same as a genuinely missing file --
    # `git cat-file -e` returns 0 for a tree just as it does for a blob,
    # so without a blob-type check this used to report applicable=true
    # and materialize `git show`'s tree listing as the "sot" file, which
    # is not JSON at all.
    ruleset_dir = repo / ".github" / "rulesets" / "main.json"
    ruleset_dir.mkdir(parents=True)
    (ruleset_dir / "inner.json").write_text('{"oops": "not a real ruleset"}\n', encoding="utf-8")
    base_sha = _commit(repo, "main.json is a tree, not a blob")
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    outputs = scope_module.compute_scope("pull_request", base_sha, repo, runner_temp, None)
    assert outputs == {"applicable": "false"}


def test_pull_request_base_lacking_ruleset_file_writes_step_summary(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    summary_file = tmp_path / "summary.md"
    scope_module.compute_scope("pull_request", base_sha, repo, repo, summary_file)
    assert "carries no" in summary_file.read_text(encoding="utf-8")


def test_pull_request_base_lacking_ruleset_file_summary_write_is_optional(repo: pathlib.Path) -> None:
    # No step_summary_file (None) must not raise -- the CLI only passes one
    # when $GITHUB_STEP_SUMMARY is actually set.
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    scope_module.compute_scope("pull_request", base_sha, repo, repo, None)


def test_pull_request_base_with_ruleset_file_materializes_it(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    _write_ruleset(repo)
    base_sha = _commit(repo, "add ruleset")
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    outputs = scope_module.compute_scope("pull_request", base_sha, repo, runner_temp, None)
    assert outputs["applicable"] == "true"
    assert outputs["scope"] == "required-checks"
    sot_path = pathlib.Path(outputs["sot"])
    assert sot_path == runner_temp / "base_main_ruleset.json"
    assert sot_path.read_text(encoding="utf-8") == '{"name": "main-protection"}\n'


def test_pull_request_reads_the_base_ref_not_the_head_ref(repo: pathlib.Path, tmp_path: pathlib.Path) -> None:
    # The base commit is checked out at HEAD when compute_scope runs (a
    # pull_request's own checkout ref is the head ref, per the workflow's
    # `ref:` -- fetch-depth 0 is what makes the base commit reachable
    # without switching HEAD). Materialize a base ruleset, then commit a
    # DIFFERENT ruleset on top, and confirm the base ref's own content
    # (not the current working tree's) is what gets read.
    _write_ruleset(repo, name="base-version")
    base_sha = _commit(repo, "base ruleset")
    _write_ruleset(repo, name="head-version")
    _commit(repo, "head ruleset, different content")
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    outputs = scope_module.compute_scope("pull_request", base_sha, repo, runner_temp, None)
    sot_path = pathlib.Path(outputs["sot"])
    assert "base-version" in sot_path.read_text(encoding="utf-8")


# --- direct parity against the replaced inline bash -------------------------


def _bash_equivalent(repo: pathlib.Path, event_name: str, base_sha: str, runner_temp: pathlib.Path) -> dict[str, str]:
    """A literal re-implementation of the replaced bash step, run via `git`
    subprocess calls exactly as the original `run:` block did, independent
    of this module's own code -- the parity proof this test asserts
    against."""
    if event_name != "pull_request":
        return {"applicable": "true", "scope": "full", "sot": ".github/rulesets/main.json"}
    commit_check = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{base_sha}^{{commit}}"], capture_output=True, check=False
    )
    if commit_check.returncode != 0:
        raise scope_module.RulesetVerifyScopeError("base commit is not present")
    path_check = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{base_sha}:.github/rulesets/main.json"],
        capture_output=True,
        check=False,
    )
    if path_check.returncode != 0:
        return {"applicable": "false"}
    show = subprocess.run(
        ["git", "-C", str(repo), "show", f"{base_sha}:.github/rulesets/main.json"],
        capture_output=True,
        text=True,
        check=True,
    )
    sot_file = runner_temp / "base_main_ruleset.json"
    sot_file.write_text(show.stdout, encoding="utf-8")
    return {"applicable": "true", "scope": "required-checks", "sot": str(sot_file)}


@pytest.mark.parametrize("event_name", ["schedule", "workflow_dispatch"])
def test_output_matches_the_prior_inline_bash_behavior_non_pull_request(
    tmp_path: pathlib.Path, event_name: str
) -> None:
    module_result = scope_module.compute_scope(event_name, "", tmp_path, tmp_path, None)
    bash_result = _bash_equivalent(tmp_path, event_name, "", tmp_path)
    assert module_result == bash_result


def test_output_matches_the_prior_inline_bash_behavior_pull_request_with_ruleset(
    repo: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    _write_ruleset(repo)
    base_sha = _commit(repo, "add ruleset")
    module_temp = tmp_path / "module-temp"
    bash_temp = tmp_path / "bash-temp"
    module_temp.mkdir()
    bash_temp.mkdir()
    module_result = scope_module.compute_scope("pull_request", base_sha, repo, module_temp, None)
    bash_result = _bash_equivalent(repo, "pull_request", base_sha, bash_temp)
    assert module_result["applicable"] == bash_result["applicable"]
    assert module_result["scope"] == bash_result["scope"]
    assert pathlib.Path(module_result["sot"]).read_text(encoding="utf-8") == pathlib.Path(bash_result["sot"]).read_text(
        encoding="utf-8"
    )


def test_output_matches_the_prior_inline_bash_behavior_pull_request_without_ruleset(repo: pathlib.Path) -> None:
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    module_result = scope_module.compute_scope("pull_request", base_sha, repo, repo, None)
    bash_result = _bash_equivalent(repo, "pull_request", base_sha, repo)
    assert module_result == bash_result


# --- _show_at_commit's own defeat case ---------------------------------------


def test_show_at_commit_raises_when_git_show_fails(repo: pathlib.Path) -> None:
    # A defeat case for _show_at_commit's own error handling, not reachable
    # through compute_scope's own happy path: compute_scope only ever calls
    # _show_at_commit after _path_exists_at_commit has already confirmed the
    # path exists, so this direct call proves the raise-on-failure branch
    # actually fires rather than assuming `git show` can never fail once
    # `cat-file -e` would have passed.
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    with pytest.raises(scope_module.RulesetVerifyScopeError, match=r"git show .* failed"):
        scope_module._show_at_commit(repo, base_sha, "not/a/real/path.json")


# --- CLI / main() ------------------------------------------------------------


def test_main_prints_key_value_lines_for_non_pull_request(capsys: pytest.CaptureFixture[str]) -> None:
    rc = scope_module.main(["--event-name", "schedule"])
    assert rc == 0
    stdout = capsys.readouterr().out
    assert stdout == "applicable=true\nscope=full\nsot=.github/rulesets/main.json\n"


def test_main_informational_notice_goes_to_stderr_not_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    rc = scope_module.main(["--event-name", "schedule"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Comparing the live ruleset" in captured.err
    assert "Comparing the live ruleset" not in captured.out


def test_main_exits_one_with_an_error_annotation_on_unresolved_scope(
    repo: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = scope_module.main(["--event-name", "pull_request", "--base-sha", "0" * 40, "--repo-root", str(repo)])
    assert rc == 1
    assert "::error::" in capsys.readouterr().err


def test_main_defaults_runner_temp_from_environment(
    repo: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_ruleset(repo)
    base_sha = _commit(repo, "add ruleset")
    env_runner_temp = tmp_path / "env-runner-temp"
    env_runner_temp.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(env_runner_temp))
    rc = scope_module.main(["--event-name", "pull_request", "--base-sha", base_sha, "--repo-root", str(repo)])
    assert rc == 0
    stdout = capsys.readouterr().out
    assert str(env_runner_temp) in stdout
    assert (env_runner_temp / "base_main_ruleset.json").is_file()


def test_main_defaults_step_summary_file_from_environment(
    repo: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
    rc = scope_module.main(["--event-name", "pull_request", "--base-sha", base_sha, "--repo-root", str(repo)])
    assert rc == 0
    assert "carries no" in summary_file.read_text(encoding="utf-8")


def test_main_explicit_runner_temp_flag_overrides_the_environment(
    repo: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_ruleset(repo)
    base_sha = _commit(repo, "add ruleset")
    env_runner_temp = tmp_path / "env-runner-temp"
    explicit_runner_temp = tmp_path / "explicit-runner-temp"
    env_runner_temp.mkdir()
    explicit_runner_temp.mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(env_runner_temp))
    rc = scope_module.main(
        [
            "--event-name",
            "pull_request",
            "--base-sha",
            base_sha,
            "--repo-root",
            str(repo),
            "--runner-temp",
            str(explicit_runner_temp),
        ]
    )
    assert rc == 0
    stdout = capsys.readouterr().out
    assert str(explicit_runner_temp) in stdout
    assert (explicit_runner_temp / "base_main_ruleset.json").is_file()
    assert not (env_runner_temp / "base_main_ruleset.json").is_file()
