"""Tests for the betterleaks-allowlist-no-removal gate
(.github/scripts/gitapex_gate_betterleaks_allowlist_no_removal.py).

Issue #1427, retrospective #1308 repair 3. PR #1305's own fix-up commit
replaced a renamed fixture's old-path allowlist entries instead of adding
the new-path entries alongside them, directly against .betterleaks.toml's
own documented "never replace, only add" rule -- CI's betterleaks
full-history scan caught it only as four confusing false-positive "leak"
reports. This gate diffs the allowlist itself, structurally, before that
detour is ever needed.

The pure comparison functions (extract_allowlist_paths, waiver_bodies,
find_unwaived_removals) are tested directly on TOML text, no git involved.
The git-integration functions (show_file_at_ref, resolve_merge_base,
check, main) are tested against real repos built with `git init` under
tmp_path, matching test_gitapex_gate_behind_base.py's own real-git-over-mock
convention.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_gate_betterleaks_allowlist_no_removal as gate
import pytest
import yaml
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_has_no_trigger_path_filter,
)

BASE_TOML = """\
[extend]
useDefault = true

[allowlist]
description = \"\"\"fixtures\"\"\"
paths = [
  '''^evals/one\\.yaml$''',
  '''^evals/two\\.yaml$''',
]
"""

# --- extract_allowlist_paths ---------------------------------------------


def test_extract_allowlist_paths_returns_the_paths_array() -> None:
    assert gate.extract_allowlist_paths(BASE_TOML) == [
        r"^evals/one\.yaml$",
        r"^evals/two\.yaml$",
    ]


def test_extract_allowlist_paths_treats_missing_allowlist_table_as_empty() -> None:
    assert gate.extract_allowlist_paths("[extend]\nuseDefault = true\n") == []


def test_extract_allowlist_paths_treats_missing_paths_key_as_empty() -> None:
    assert gate.extract_allowlist_paths("[allowlist]\ndescription = 'x'\n") == []


def test_extract_allowlist_paths_treats_empty_text_as_empty() -> None:
    assert gate.extract_allowlist_paths("") == []


def test_extract_allowlist_paths_raises_on_invalid_toml() -> None:
    with pytest.raises(gate.GateError, match=r"cannot parse \.betterleaks\.toml as TOML"):
        gate.extract_allowlist_paths("[allowlist\npaths = [")


def test_extract_allowlist_paths_raises_when_paths_is_not_an_array() -> None:
    with pytest.raises(gate.GateError, match=r"\[allowlist\]\.paths must be an array"):
        gate.extract_allowlist_paths("[allowlist]\npaths = 'not-a-list'\n")


def test_extract_allowlist_paths_fails_closed_on_a_recursion_error() -> None:
    """Defeat test (adversarial security review): `tomllib.loads` raises a
    bare `RecursionError`, not `TOMLDecodeError`, for a document nested
    deeply enough to blow the interpreter's own recursion limit -- an
    uncaught `except tomllib.TOMLDecodeError` alone would let this crash
    with an unhandled traceback (Python's default exit 1), colliding with
    this gate's own documented exit-1 "unwaived removal found" meaning.
    Must instead raise GateError (exit 2), the same fail-closed path every
    other malformed-input case here takes."""
    deeply_nested = "x = " + "[" * 3000 + "]" * 3000
    with pytest.raises(gate.GateError, match=r"cannot parse \.betterleaks\.toml as TOML"):
        gate.extract_allowlist_paths(deeply_nested)


# --- waiver_bodies / find_unwaived_removals --------------------------------


def test_waiver_bodies_finds_a_waived_comment() -> None:
    text = "# betterleaks-allowlist-no-removal: WAIVED: fixture retired, see issue #999\n"
    assert gate.waiver_bodies(text) == ["fixture retired, see issue #999"]


def test_waiver_bodies_is_case_insensitive() -> None:
    text = "# BETTERLEAKS-ALLOWLIST-NO-REMOVAL: waived: retired\n"
    assert gate.waiver_bodies(text) == ["retired"]


def test_waiver_bodies_returns_empty_for_no_comment() -> None:
    assert gate.waiver_bodies(BASE_TOML) == []


def test_waiver_bodies_requires_a_non_empty_reason() -> None:
    text = "# betterleaks-allowlist-no-removal: WAIVED:\n"
    assert gate.waiver_bodies(text) == []


def test_find_unwaived_removals_is_empty_when_nothing_removed() -> None:
    assert gate.find_unwaived_removals(BASE_TOML, BASE_TOML) == []


def test_find_unwaived_removals_is_empty_when_only_additions() -> None:
    head = BASE_TOML.replace(
        "  '''^evals/two\\.yaml$''',\n",
        "  '''^evals/two\\.yaml$''',\n  '''^evals/three\\.yaml$''',\n",
    )
    assert gate.find_unwaived_removals(BASE_TOML, head) == []


def test_find_unwaived_removals_flags_a_removed_entry() -> None:
    head = BASE_TOML.replace("  '''^evals/two\\.yaml$''',\n", "")
    assert gate.find_unwaived_removals(BASE_TOML, head) == [r"^evals/two\.yaml$"]


def test_find_unwaived_removals_respects_a_waiver_quoting_the_entry_verbatim() -> None:
    head = BASE_TOML.replace("  '''^evals/two\\.yaml$''',\n", "")
    head += (
        "\n# betterleaks-allowlist-no-removal: WAIVED: retired, was "
        r"'''^evals/two\.yaml$'''" + "\n"
    )
    assert gate.find_unwaived_removals(BASE_TOML, head) == []


def test_find_unwaived_removals_ignores_a_waiver_that_names_a_different_entry() -> None:
    head = BASE_TOML.replace("  '''^evals/two\\.yaml$''',\n", "")
    head += "\n# betterleaks-allowlist-no-removal: WAIVED: retired '''^evals/other\\.yaml$'''\n"
    assert gate.find_unwaived_removals(BASE_TOML, head) == [r"^evals/two\.yaml$"]


def test_find_unwaived_removals_flags_deleting_the_whole_allowlist_block() -> None:
    head = "[extend]\nuseDefault = true\n"
    assert gate.find_unwaived_removals(BASE_TOML, head) == [
        r"^evals/one\.yaml$",
        r"^evals/two\.yaml$",
    ]


# --- git integration -------------------------------------------------------


def _run(args: list[str], cwd: pathlib.Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: pathlib.Path, *, branch: str = "main") -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "--initial-branch", branch], root)
    _run(["git", "config", "user.email", "test@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    return root


def _write_toml(root: pathlib.Path, text: str, message: str) -> None:
    (root / ".betterleaks.toml").write_text(text, encoding="utf-8")
    _run(["git", "add", "--", ".betterleaks.toml"], root)
    _run(["git", "commit", "-q", "-m", message], root)


def _synced_head(tmp_path: pathlib.Path, *, initial_toml: str = BASE_TOML) -> tuple[pathlib.Path, pathlib.Path]:
    origin = _init_repo(tmp_path / "origin")
    _write_toml(origin, initial_toml, "initial")

    head = _init_repo(tmp_path / "head")
    _run(["git", "remote", "add", "origin", str(origin)], head)
    _run(["git", "fetch", "-q", "origin", "main"], head)
    _run(["git", "checkout", "-q", "-b", "main", "origin/main"], head)
    return origin, head


@pytest.mark.slow
def test_show_file_at_ref_returns_committed_content(tmp_path: pathlib.Path) -> None:
    _origin, head = _synced_head(tmp_path)
    text = gate.show_file_at_ref(head, "HEAD", ".betterleaks.toml")
    assert text == BASE_TOML


@pytest.mark.slow
def test_show_file_at_ref_returns_empty_string_for_a_missing_path(tmp_path: pathlib.Path) -> None:
    _origin, head = _synced_head(tmp_path)
    assert gate.show_file_at_ref(head, "HEAD", "does-not-exist.toml") == ""


def test_show_file_at_ref_fails_closed_on_a_real_git_failure_not_a_missing_path(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defeat test (dimension 15, fail-closed on malformed/incomplete input):
    a `git show` failure that is NOT the fixed missing-path stderr shape
    (a corrupted object, a transient I/O error) must raise GateError, not
    silently read as an empty allowlist -- which would otherwise let a
    real base-side removal go undetected because the comparison saw a
    fabricated "nothing was ever there" base state. Regression test for
    the pre-fix behavior, which treated every nonzero `git show` exit as
    "path absent" regardless of stderr."""

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="fatal: loose object abcd1234 is corrupt"
        )

    monkeypatch.setattr(gate._gitapex_base_ref, "run_git", lambda *a, **k: _fake_run())
    with pytest.raises(gate.GateError, match=r"git show .* failed"):
        gate.show_file_at_ref(tmp_path, "HEAD", ".betterleaks.toml")


@pytest.mark.slow
def test_resolve_merge_base_returns_the_common_ancestor(tmp_path: pathlib.Path) -> None:
    origin, head = _synced_head(tmp_path)
    base_sha = subprocess.run(
        ["git", "-C", str(origin), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    _write_toml(head, BASE_TOML + "\n# local edit\n", "local edit")
    merge_base = gate.resolve_merge_base(head, "refs/remotes/origin/main")
    assert merge_base == base_sha


def test_resolve_merge_base_fails_closed_when_the_merge_base_call_itself_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defeat test: `require_common_ancestor` finding a common ancestor does
    not guarantee the later `git merge-base` call in this function also
    succeeds (a race, a corrupt object appearing between the two calls) --
    a nonzero exit here must raise GateError, not silently return garbage
    stdout as though it were a real SHA."""

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="fatal: not a valid object name")

    monkeypatch.setattr(gate._gitapex_base_ref, "run_git", lambda *a, **k: _fake_run())
    with pytest.raises(gate.GateError, match=r"git merge-base .* failed"):
        gate.resolve_merge_base(tmp_path, "refs/remotes/origin/main")


@pytest.mark.slow
def test_check_local_plane_fetches_and_reports_an_unwaived_removal(tmp_path: pathlib.Path) -> None:
    _origin, head = _synced_head(tmp_path)
    removed_toml = BASE_TOML.replace("  '''^evals/two\\.yaml$''',\n", "")
    _write_toml(head, removed_toml, "drop an entry")
    assert gate.check(head) == [r"^evals/two\.yaml$"]


@pytest.mark.slow
def test_check_local_plane_passes_when_removal_is_waived(tmp_path: pathlib.Path) -> None:
    _origin, head = _synced_head(tmp_path)
    removed_toml = BASE_TOML.replace("  '''^evals/two\\.yaml$''',\n", "")
    removed_toml += "\n# betterleaks-allowlist-no-removal: WAIVED: retired '''^evals/two\\.yaml$'''\n"
    _write_toml(head, removed_toml, "drop an entry, waived")
    assert gate.check(head) == []


@pytest.mark.slow
def test_check_local_plane_passes_on_addition_only(tmp_path: pathlib.Path) -> None:
    _origin, head = _synced_head(tmp_path)
    added_toml = BASE_TOML.replace(
        "  '''^evals/two\\.yaml$''',\n",
        "  '''^evals/two\\.yaml$''',\n  '''^evals/three\\.yaml$''',\n",
    )
    _write_toml(head, added_toml, "add an entry")
    assert gate.check(head) == []


@pytest.mark.slow
def test_check_ci_plane_uses_the_given_merge_base_without_fetching(tmp_path: pathlib.Path) -> None:
    origin, head = _synced_head(tmp_path)
    base_sha = subprocess.run(
        ["git", "-C", str(origin), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    removed_toml = BASE_TOML.replace("  '''^evals/two\\.yaml$''',\n", "")
    _write_toml(head, removed_toml, "drop an entry")
    # No `origin` fetch is possible: point the remote at a nonexistent path,
    # then prove `check` still succeeds when a merge_base is supplied
    # directly -- the ci plane never needs to reach the network.
    _run(["git", "remote", "set-url", "origin", str(tmp_path / "does-not-exist")], head)
    assert gate.check(head, merge_base=base_sha) == [r"^evals/two\.yaml$"]


def test_check_local_plane_fails_closed_on_unreachable_remote(tmp_path: pathlib.Path) -> None:
    head = _init_repo(tmp_path / "head")
    _write_toml(head, BASE_TOML, "initial")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)
    with pytest.raises(gate.GateError, match="git fetch"):
        gate.check(head)


# --- CLI: main --------------------------------------------------------------


@pytest.mark.slow
def test_main_returns_zero_when_nothing_removed(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    _origin, head = _synced_head(tmp_path)
    assert gate.main(["--root", str(head)]) == 0
    assert "OK:" in capsys.readouterr().out


@pytest.mark.slow
def test_main_returns_one_and_lists_the_removed_entries(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _origin, head = _synced_head(tmp_path)
    removed_toml = BASE_TOML.replace("  '''^evals/two\\.yaml$''',\n", "")
    _write_toml(head, removed_toml, "drop an entry")
    assert gate.main(["--root", str(head)]) == 1
    stderr = capsys.readouterr().err
    assert "FAIL" in stderr
    assert r"^evals/two\.yaml$" in stderr
    assert "#1427" in stderr
    assert "WAIVED" in stderr


@pytest.mark.slow
def test_main_returns_two_and_names_the_fetch_failure_distinctly(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    head = _init_repo(tmp_path / "head")
    _write_toml(head, BASE_TOML, "initial")
    _run(["git", "remote", "add", "origin", str(tmp_path / "does-not-exist")], head)
    assert gate.main(["--root", str(head)]) == 2
    stderr = capsys.readouterr().err
    assert "error:" in stderr
    assert "git fetch" in stderr
    assert "FAIL" not in stderr


@pytest.mark.slow
def test_main_accepts_a_pre_resolved_merge_base_and_skips_fetching(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    origin, head = _synced_head(tmp_path)
    base_sha = subprocess.run(
        ["git", "-C", str(origin), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    _run(["git", "remote", "set-url", "origin", str(tmp_path / "does-not-exist")], head)
    assert gate.main(["--root", str(head), "--merge-base", base_sha]) == 0


def test_main_returns_two_on_a_root_that_does_not_exist(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "does-not-exist"
    assert gate.main(["--root", str(missing)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_returns_two_on_a_root_that_is_a_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    a_file = tmp_path / "not-a-directory"
    a_file.write_text("x", encoding="utf-8")
    assert gate.main(["--root", str(a_file)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


# --- GateBetterleaksAllowlistNoRemovalArgs validation -----------------------


def test_args_reject_a_root_that_does_not_exist(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateBetterleaksAllowlistNoRemovalArgs(root=tmp_path / "does-not-exist", merge_base=None)


# --- CI workflow drift gates -------------------------------------------
#
# .github/workflows/betterleaks-allowlist-no-removal-gate.yml's own pointer
# comments name these three tests -- an invariant's own drift gate ships
# with the invariant, matching detection-logic-property-coverage-gate.yml's
# own identically-named precedent (issue #1178).

_WORKFLOW_NAME = "betterleaks-allowlist-no-removal-gate.yml"


def _run_scripts(workflow_name: str) -> list[str]:
    """Every `run:` step body in `.github/workflows/<workflow_name>`, parsed
    from YAML rather than matched as text -- this workflow's own pointer
    comments contain the literal substrings (`fetch-depth: '0'`,
    `$merge_base`) a whole-file text check would be satisfied by even with
    the real invariant deleted, the exact defeat case
    `conftest.assert_workflow_feeds_merge_base_to`'s own docstring names."""
    path = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows" / workflow_name
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [step["run"] for job in parsed["jobs"].values() for step in job["steps"] if "run" in step]


def test_the_workflow_has_no_paths_filter() -> None:
    """Drift gate mirroring detection-logic-property-coverage-gate.yml's own
    identical reasoning: a `paths:` filter under `pull_request:` would leave
    this required check `Pending` forever for a PR that does not happen to
    touch a matched path, rather than skipped."""
    assert_workflow_has_no_trigger_path_filter(_WORKFLOW_NAME)


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    """Drift gate: this gate's own CI step reads `.betterleaks.toml`'s
    content at the merge-base commit via `git show`, which requires that
    commit's tree to be present locally (`fetch-depth: '0'`) and the
    checked-out working tree to be the PR's own head (`ref: <head sha>`),
    not whatever `main` happens to be at the moment the job runs."""
    assert_workflow_checkout_pins_head_sha_with_full_history(_WORKFLOW_NAME)


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    """Drift gate: the workflow resolves `$merge_base` from `$BASE_SHA`/
    `$HEAD_SHA` and feeds exactly that value to the gate script's
    `--merge-base` flag -- never `$BASE_SHA` directly -- so a change that
    landed on `main` after this PR forked is never misattributed to this
    PR as a removal. `assert_workflow_feeds_merge_base_to` (this
    repository's shared drift-test helper for gates whose CI producer is a
    raw `git <command>` line) does not fit this gate's own shape: the
    value is fed to a `uv run python3 ...` invocation, not to a further
    `git` subcommand, so this is a bespoke check for the same invariant.
    `$BASE_SHA` legitimately appears elsewhere in the step (the
    `git merge-base` call itself, and the failure message naming both
    SHAs) -- only the line(s) invoking the gate script are checked for it.

    The real workflow's own invocation wraps across two lines with a `\\`
    continuation (the script-path line, then a separate `--merge-base
    "$merge_base"` line) -- checked as two distinct line classes below,
    not one combined "any of these lines" pool: a decoy line elsewhere in
    the matched set (e.g. a comment quoting `"$merge_base"` in prose) must
    not let a real regression on the `--merge-base` flag's own line pass
    unnoticed, the exact gap an earlier revision of this test had (an
    adversarial-review finding, issue #1427)."""
    scripts = _run_scripts(_WORKFLOW_NAME)
    combined = "\n".join(scripts)
    assert 'merge_base=$(git merge-base "$BASE_SHA" "$HEAD_SHA")' in combined, combined
    all_lines = [line for script in scripts for line in script.split("\n")]
    script_path_lines = [line for line in all_lines if "gitapex_gate_betterleaks" in line]
    merge_base_flag_lines = [line for line in all_lines if "--merge-base" in line]
    assert script_path_lines, combined
    assert merge_base_flag_lines, combined
    for line in merge_base_flag_lines:
        assert '"$merge_base"' in line, line
    for line in script_path_lines + merge_base_flag_lines:
        assert "$BASE_SHA" not in line, line
