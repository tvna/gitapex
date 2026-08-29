"""Tests for the split.md disclosure-completeness gate
(evals/scripts/gitapex_check_split_disclosure.py).

Issue #218 (Repair 1) / #1399: reproduces the real historical incident (PR
#216's own gate-record disclosure paragraph named three fixed
fixture-assertion bugs but omitted a fourth) with a real git repository --
built with `git init` and real commits under `tmp_path`, matching
tests/test_gitapex_run_base_diff.py's own convention -- so the actual
diff-scanning behavior this script exists to get right is exercised for
real, not asserted about a stub.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import gitapex_check_split_disclosure as gate
import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "evals" / "scripts" / "gitapex_check_split_disclosure.py"

_FIXTURE_TEMPLATE = """id: {name}
name: {name}
description: a fixture.
inputs:
  prompt: does this trip the check?
expected:
  output_contains:
    - "{assertion}"
"""


def _run(args: list[str], cwd: pathlib.Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(root: pathlib.Path) -> pathlib.Path:
    root.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "--initial-branch", "main"], root)
    _run(["git", "config", "user.email", "test@example.com"], root)
    _run(["git", "config", "user.name", "Test"], root)
    return root


def _write(root: pathlib.Path, rel_path: str, content: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(root: pathlib.Path, message: str) -> None:
    _run(["git", "add", "-A"], root)
    _run(["git", "commit", "-q", "-m", message], root)


def _fixture_path(name: str) -> str:
    return f"{gate.TASKS_GLOB_PREFIX}{name}"


def _write_fixture(root: pathlib.Path, name: str, assertion: str) -> None:
    _write(root, _fixture_path(name), _FIXTURE_TEMPLATE.format(name=name.removesuffix(".yaml"), assertion=assertion))


def _write_split_md(root: pathlib.Path, content: str) -> None:
    _write(root, gate.SPLIT_MD_PATH, content)


def _run_cli(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(cwd), *args],
        capture_output=True,
        check=False,
    )


# --- undisclosed_fixtures (in-process) --------------------------------------


@pytest.mark.slow
def test_disclosed_change_passes(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    _write_split_md(repo, "# split\n\n`edge.yaml`'s assertion was loosened for casing.\n")
    _commit(repo, "loosen assertion, disclose it")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == []


@pytest.mark.slow
def test_undisclosed_change_fails(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    _write_split_md(repo, "# split\n\nunrelated addition, never mentions the fixture.\n")
    _commit(repo, "loosen assertion, forget to disclose it")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == ["edge.yaml"]


@pytest.mark.slow
def test_reproduces_real_incident_three_disclosed_one_omitted(tmp_path: pathlib.Path) -> None:
    # The real PR #216 shape: four fixture-assertion bugs fixed in one
    # commit, split.md's disclosure named three and omitted the fourth
    # (edge.yaml). Only the omitted one must be reported.
    repo = _init_repo(tmp_path)
    for name in ("edge.yaml", "mechanism-fit-subagent.yaml", "portability-issue-number-citation.yaml"):
        _write_fixture(repo, name, "headline finding")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "eadline finding")
    _write_fixture(repo, "mechanism-fit-subagent.yaml", "eadline finding fixed")
    _write_fixture(repo, "portability-issue-number-citation.yaml", "eadline finding also fixed")
    _write_split_md(
        repo,
        "# split\n\n"
        "Three fixture-assertion bugs were fixed: `mechanism-fit-subagent.yaml`'s and "
        "`portability-issue-number-citation.yaml`'s casing was corrected.\n",
    )
    _commit(repo, "fix casing, disclosure omits edge.yaml")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == ["edge.yaml"]


@pytest.mark.slow
def test_fixture_change_not_touching_assertions_is_not_flagged(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write(
        repo,
        _fixture_path("edge.yaml"),
        _FIXTURE_TEMPLATE.format(name="edge", assertion="never delete production data").replace(
            "description: a fixture.", "description: a fixture, reworded."
        ),
    )
    _commit(repo, "reword description only, assertions unchanged")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == []


@pytest.mark.slow
def test_no_task_file_changes_passes_trivially(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write(repo, "README.md", "unrelated change\n")
    _commit(repo, "unrelated change")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == []


@pytest.mark.slow
def test_deleted_fixture_is_out_of_scope(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    (repo / _fixture_path("edge.yaml")).unlink()
    _commit(repo, "delete fixture")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == []


@pytest.mark.slow
def test_split_md_removed_line_does_not_rescue_disclosure(tmp_path: pathlib.Path) -> None:
    # Only *added* lines count as new disclosure narrative: a stale,
    # removed mention from an unrelated prior edit must not satisfy this
    # range's own disclosure requirement.
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n\n`edge.yaml` is a stable fixture, unrelated to this change.\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    _write_split_md(repo, "# split\n\nThe stale note above was removed; nothing new added.\n")
    _commit(repo, "loosen assertion, remove old mention, add nothing new")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == ["edge.yaml"]


@pytest.mark.slow
def test_routine_scoring_table_mention_alone_does_not_disclose(tmp_path: pathlib.Path) -> None:
    # Regression guard for the real historical shape: this repository's
    # own gate-record convention lists every fixture run in a scoring
    # table row (`` | `edge.yaml` | 1.000000 | ... | ``) regardless of
    # whether its assertions changed. A bare-name mention there must not
    # count as disclosure -- only the possessive "`edge.yaml`'s" citation
    # form split.md's own disclosure prose actually uses does. Confirmed
    # live against the real, historically undisclosed PR #216 range
    # (commit 4b9edfa39e20bc1b8a16651d1fc6e7db778c8909): a first,
    # bare-mention design reported this range clean, which this test
    # exists to prevent regressing to.
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    _write_split_md(
        repo,
        "# split\n\n"
        "| Fixture | Before | After |\n"
        "|---|---|---|\n"
        "| `edge.yaml` | 1.000000 (reused) | 1.000000 (fresh) |\n",
    )
    _commit(repo, "loosen assertion, only the routine scoring table mentions the fixture")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == ["edge.yaml"]


@pytest.mark.slow
def test_multiple_fixtures_touched_in_one_range(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "a.yaml", "one")
    _write_fixture(repo, "b.yaml", "two")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "a.yaml", "one, tightened")
    _write_fixture(repo, "b.yaml", "two, tightened")
    _write_split_md(repo, "# split\n\nOnly `a.yaml`'s assertion was tightened.\n")
    _commit(repo, "tighten both, disclose only one")

    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == ["b.yaml"]


# --- main() (in-process, for coverage of argparse/print/return-code paths --
# the subprocess-based CLI tests below prove the real entry point works
# end to end, but coverage.py cannot see inside a separate `sys.executable`
# process without extra subprocess-coverage plumbing this repository does
# not have wired for this script -- these in-process calls exercise the
# same three branches (PASS, FAIL, error) directly.) ------------------------


@pytest.mark.slow
def test_main_returns_zero_and_prints_pass_on_clean_range(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    _write_split_md(repo, "# split\n\n`edge.yaml`'s assertion was loosened.\n")
    _commit(repo, "loosen and disclose")

    exit_code = gate.main(["--base", "HEAD^", "--head", "HEAD", "--repo-root", str(repo)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


@pytest.mark.slow
def test_main_returns_one_and_prints_fail_with_fixture_name(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    _write_split_md(repo, "# split\n\nnothing relevant added.\n")
    _commit(repo, "loosen, forget to disclose")

    exit_code = gate.main(["--base", "HEAD^", "--head", "HEAD", "--repo-root", str(repo)])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "FAIL" in err
    assert "edge.yaml" in err


@pytest.mark.slow
def test_main_returns_one_and_prints_error_on_unresolvable_ref(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "README.md", "only commit\n")
    _commit(repo, "only commit")

    exit_code = gate.main(["--base", "not-a-real-ref", "--head", "HEAD", "--repo-root", str(repo)])
    assert exit_code == 1
    assert "error:" in capsys.readouterr().err


def test_main_returns_one_and_prints_error_on_leading_dash_base(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = gate.main(["--base=-oevil", "--head", "HEAD", "--repo-root", "."])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert "--base" in err


# --- CLI (subprocess, black-box) --------------------------------------------


@pytest.mark.slow
def test_cli_exits_zero_on_clean_range(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    _write_split_md(repo, "# split\n\n`edge.yaml`'s assertion was loosened.\n")
    _commit(repo, "loosen and disclose")

    result = _run_cli(["--base", "HEAD^", "--head", "HEAD"], repo)
    assert result.returncode == 0
    assert b"PASS" in result.stdout


@pytest.mark.slow
def test_cli_exits_one_and_names_fixture_on_undisclosed_range(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    _write_split_md(repo, "# split\n\nnothing relevant added.\n")
    _commit(repo, "loosen, forget to disclose")

    result = _run_cli(["--base", "HEAD^", "--head", "HEAD"], repo)
    assert result.returncode == 1
    assert b"FAIL" in result.stderr
    assert b"edge.yaml" in result.stderr


@pytest.mark.slow
def test_cli_reports_error_on_unresolvable_ref(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "README.md", "only commit\n")
    _commit(repo, "only commit")

    result = _run_cli(["--base", "not-a-real-ref", "--head", "HEAD"], repo)
    assert result.returncode == 1
    assert b"error:" in result.stderr


@pytest.mark.slow
def test_undisclosed_fixtures_raises_runtime_error_outside_a_git_repo(tmp_path: pathlib.Path) -> None:
    with pytest.raises(RuntimeError):
        gate.undisclosed_fixtures("HEAD^", "HEAD", tmp_path)


# --- _validate_revision_arg (CWE-88 argument-injection hardening) ----------
#
# Found by an adversarial security review of this file's own diff: --base/
# --head are public CLI flags concatenated into a single "base..head" git
# revision-range argument with no format check. A value starting with "-"
# in that position could be parsed by git as an option instead of a
# revision (e.g. an injected --output=<path>). Not reachable through this
# module's own CI wiring (split-disclosure-gate.yml only ever passes a
# real commit SHA), but the CLI itself has no such guarantee for a future
# caller -- these tests pin the rejection directly.


def test_validate_revision_arg_accepts_a_normal_ref() -> None:
    gate._validate_revision_arg("HEAD^", "--base")
    gate._validate_revision_arg("82732c7239ef4648ee9a398d32eb737a45640181", "--head")


def test_validate_revision_arg_rejects_empty_string() -> None:
    with pytest.raises(RuntimeError, match="--base"):
        gate._validate_revision_arg("", "--base")


def test_validate_revision_arg_rejects_leading_dash() -> None:
    with pytest.raises(RuntimeError, match="--head"):
        gate._validate_revision_arg("--output=/tmp/pwned", "--head")


@pytest.mark.slow
def test_cli_rejects_leading_dash_base_before_touching_git(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo, "README.md", "only commit\n")
    _commit(repo, "only commit")

    # "--base=..." (equals form), not "--base", "..." as two argv tokens:
    # argparse itself would otherwise treat a dash-leading value as a new,
    # unrecognized option before this module's own validation ever runs.
    result = _run_cli(["--base=-o/tmp/pwned", "--head", "HEAD"], repo)
    assert result.returncode == 1
    assert b"error:" in result.stderr
    assert b"--base" in result.stderr


# --- _run_git non-UTF-8 robustness ------------------------------------------
#
# Found by an adversarial correctness review, reproduced live: a first
# version of _run_git decoded git's stdout with text=True's strict default,
# so a non-UTF-8 byte anywhere in a diff (a fixture line, a split.md line)
# raised an uncaught UnicodeDecodeError -- neither CalledProcessError nor
# OSError, so it escaped _run_git's own "raises RuntimeError only" contract
# and crashed the CLI with a raw traceback.


@pytest.mark.slow
def test_non_utf8_byte_in_a_touched_fixture_does_not_crash(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    # A raw invalid UTF-8 byte (0x80, a lone continuation byte -- not
    # representable by encoding any Python str, so built directly as
    # bytes) inside the fixture's own assertion line. _write() writes
    # text/UTF-8, so this bypasses it deliberately.
    fixture_path = repo / _fixture_path("edge.yaml")
    original = fixture_path.read_bytes()
    updated = original.replace(b"never delete production data", b"delete production data \x80")
    fixture_path.write_bytes(updated)
    _write_split_md(repo, "# split\n\n`edge.yaml`'s assertion was loosened.\n")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-q", "-m", "loosen with a non-UTF-8 byte, disclosed"], repo)

    # Must not raise UnicodeDecodeError -- returns a real, usable result.
    assert gate.undisclosed_fixtures("HEAD^", "HEAD", repo) == []


@pytest.mark.slow
def test_cli_does_not_crash_on_non_utf8_byte_in_split_md(tmp_path: pathlib.Path) -> None:
    repo = _init_repo(tmp_path)
    _write_fixture(repo, "edge.yaml", "never delete production data")
    _write_split_md(repo, "# split\n")
    _commit(repo, "baseline")

    _write_fixture(repo, "edge.yaml", "delete production data")
    split_path = repo / gate.SPLIT_MD_PATH
    content = b"# split\n\n`edge.yaml`'s assertion was loosened " + b"\x80" + b".\n"
    split_path.write_bytes(content)
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-q", "-m", "loosen, disclose with a non-UTF-8 byte"], repo)

    result = _run_cli(["--base", "HEAD^", "--head", "HEAD"], repo)
    assert result.returncode == 0
    assert b"PASS" in result.stdout
