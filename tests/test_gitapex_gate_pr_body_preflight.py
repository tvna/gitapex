"""Tests for the consolidated local PR-body preflight
(.github/scripts/gitapex_gate_pr_body_preflight.py, issue #1725).

Two different gate scripts -- skill-audit-disclosure (#1707) and
provenance-disclosure (#1711) -- were each tripped by the same root
cause: no single local command ran every PR-body-affecting gate together
before a create_pull_request/update_pull_request call. This suite proves
the consolidated command actually catches both original defect shapes,
not just that its own aggregation logic works in the abstract.

Sub-checks that need no git state (ascii-only, provenance-marker-scan,
provenance-disclosure) are exercised against the real sibling scripts --
issue #1711's own reconstruction in particular needs the real
gate_provenance_disclosure.py behavior, not a stand-in. The one sub-check
that needs a real git repository and this checkout's own pydantic-backed
gitapex_compute_skill_audit_flags module (skill-audit-disclosure) is
instead exercised against a small stand-in script asserting the exact
argv contract this module promises it -- test_gitapex_gate_skill_audit_
disclosure.py already covers that real gate's own git/pydantic behavior
directly, so re-deriving it here would just be a slower, duplicate copy.
"""

from __future__ import annotations

import pathlib
import subprocess

import gitapex_gate_pr_body_preflight as preflight
import pytest
from conftest import init_git_repo, run_git

_CLEAN_BODY = "Clean PR body.\n\nCloses #1725\n"

# Issue #1711's own reconstruction: a paragraph combining a limitation
# cue ("no access to") and a tool-fingerprint cue ("a dispatch tool") in
# the same paragraph, the exact shape that false-triggered provenance-
# disclosure in CI after the local pre-push pass had not included it.
_1711_BODY = (
    "Execution log bullet: skill-audit-disclosure found the body missing "
    "its required section, because no access to a registered skill "
    "invocation was available for a dispatch tool at the time.\n"
)


# --- CheckResult.status ---


def test_check_result_status_reflects_passed_and_skipped() -> None:
    assert preflight.CheckResult("a", True, False, "").status == "PASS"
    assert preflight.CheckResult("a", False, False, "").status == "FAIL"
    assert preflight.CheckResult("a", False, True, "skipped").status == "SKIPPED"
    # skipped takes priority over passed when (implausibly) both are set,
    # matching the property's own if-skipped-first branch order.
    assert preflight.CheckResult("a", True, True, "skipped").status == "SKIPPED"


# --- _run ---


def test_run_executes_argv_with_no_shell_and_captures_output() -> None:
    completed = preflight._run(("python3", "-c", "print('hello')"))
    assert completed.returncode == 0
    assert completed.stdout.strip() == "hello"


def test_run_pipes_stdin_text_through_when_given() -> None:
    completed = preflight._run(("python3", "-c", "import sys; print(sys.stdin.read().strip())"), stdin_text="piped")
    assert completed.stdout.strip() == "piped"


def test_run_default_timeout_tracks_a_monkeypatched_subprocess_timeout_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a plain ``timeout: float = SUBPROCESS_TIMEOUT_SECONDS``
    default-argument value would freeze that module global's value at
    _run's own function-definition time, silently breaking every test
    (and every real call) that relies on monkeypatching
    SUBPROCESS_TIMEOUT_SECONDS to change _run's own effective timeout --
    found by an independent adversarial review of this issue's own
    implementation, live-confirmed via _run.__defaults__ staying stale
    after such a monkeypatch. _run's own None-sentinel timeout parameter
    must read SUBPROCESS_TIMEOUT_SECONDS fresh at call time instead."""
    monkeypatch.setattr(preflight, "SUBPROCESS_TIMEOUT_SECONDS", 0.1)
    with pytest.raises(subprocess.TimeoutExpired):
        preflight._run(("python3", "-c", "import time; time.sleep(5)"))


def test_run_explicit_timeout_overrides_subprocess_timeout_seconds() -> None:
    completed = preflight._run(("python3", "-c", "print('hello')"), timeout=30)
    assert completed.returncode == 0


# --- _temp_text_file ---


def test_temp_text_file_yields_a_path_holding_the_given_text() -> None:
    with preflight._temp_text_file("gitapex-test-", "hello world\n") as path:
        assert path.is_file()
        assert path.read_text(encoding="utf-8") == "hello world\n"
        assert path.name.startswith("gitapex-test-")
    # Unlinked on normal exit -- the whole point of factoring this out of
    # main()'s own body-file handling and check_provenance_disclosure's own
    # diff-added-file handling.
    assert not path.exists()


def test_temp_text_file_is_unlinked_even_when_the_with_block_raises() -> None:
    with pytest.raises(ValueError, match="boom"), preflight._temp_text_file("gitapex-test-", "x") as path:
        captured_path = path
        raise ValueError("boom")
    assert not captured_path.exists()


# --- _isolated ---


def test_error_result_formats_a_timeout_distinctly_from_other_errors() -> None:
    timeout_result = preflight._error_result("a", subprocess.TimeoutExpired(cmd=["x"], timeout=1))
    assert timeout_result.name == "a"
    assert not timeout_result.passed
    assert "timed out" in timeout_result.output

    other_result = preflight._error_result("b", ValueError("bad value"))
    assert other_result.name == "b"
    assert not other_result.passed
    assert "timed out" not in other_result.output
    assert "bad value" in other_result.output


def test_isolated_returns_the_wrapped_check_result_on_success() -> None:
    result = preflight._isolated("a", lambda: preflight.CheckResult("a", True, False, ""))
    assert result.passed


def test_isolated_converts_a_prbodypreflighterror_into_a_failing_result() -> None:
    def _boom() -> preflight.CheckResult:
        raise preflight.PrBodyPreflightError("sibling script missing")

    result = preflight._isolated("some-check", _boom)
    assert result.name == "some-check"
    assert not result.passed
    assert not result.skipped
    assert "sibling script missing" in result.output


def test_isolated_converts_a_timeout_into_a_failing_result() -> None:
    def _boom() -> preflight.CheckResult:
        raise subprocess.TimeoutExpired(cmd=["python3"], timeout=1)

    result = preflight._isolated("some-check", _boom)
    assert result.name == "some-check"
    assert not result.passed
    assert "timed out" in result.output


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("[Errno 2] No such file or directory: 'git'"),
        ValueError("bad argv"),
        subprocess.SubprocessError("generic subprocess failure"),
    ],
    ids=["FileNotFoundError-is-an-OSError", "ValueError", "SubprocessError"],
)
def test_isolated_converts_the_wider_exception_scope_into_a_failing_result(error: Exception) -> None:
    """_isolated's own _ISOLATED_EXCEPTIONS scope widened to match
    gitapex_gate_local_preflight.py's own run_check (OSError, ValueError,
    subprocess.SubprocessError, in addition to this module's own
    PrBodyPreflightError/TimeoutExpired) -- reconstructs the concrete
    scenario an independent adversarial review of this issue's own
    implementation named: build_diff_added_corpus's bare `git diff`
    subprocess call raising an uncaught FileNotFoundError if git itself
    were ever missing from PATH, which the original narrower scope let
    crash this whole aggregate run past every other sub-check's own
    result."""

    def _boom() -> preflight.CheckResult:
        raise error

    result = preflight._isolated("some-check", _boom)
    assert result.name == "some-check"
    assert not result.passed
    assert not result.skipped
    assert str(error) in result.output


def test_build_diff_added_corpus_filenotfounderror_is_isolated_not_a_crash(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end reconstruction of the scenario above through the real
    call chain: git itself unresolvable (not merely a sibling script) must
    still surface as a failing provenance-disclosure result via
    run_all_checks's own diff_added_corpus_error path, never an uncaught
    exception out of run_all_checks."""
    repo = init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "init"], repo)
    run_git(["git", "tag", "BASE"], repo)

    monkeypatch.setattr(preflight, "REPO_ROOT", repo)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path-dir"))
    (tmp_path / "empty-path-dir").mkdir()

    body_path = tmp_path / "body.txt"
    body_path.write_text(_CLEAN_BODY, encoding="utf-8")
    results = preflight.run_all_checks(
        body_path, _CLEAN_BODY, ("BASE", "HEAD"), frozenset({"skill-audit-disclosure", "provenance-marker-scan"})
    )
    by_name = {result.name: result for result in results}
    assert not by_name["provenance-disclosure"].passed
    assert "No such file or directory" in by_name["provenance-disclosure"].output


# --- run_all_checks ---


def test_run_all_checks_runs_all_four_sub_checks_without_check_diff(tmp_path: pathlib.Path) -> None:
    body_path = tmp_path / "body.txt"
    body_path.write_text(_CLEAN_BODY, encoding="utf-8")
    results = preflight.run_all_checks(body_path, _CLEAN_BODY, None)
    names = {result.name for result in results}
    assert names == {"skill-audit-disclosure", "provenance-disclosure", "ascii-only", "provenance-marker-scan"}
    skill_audit_result = next(r for r in results if r.name == "skill-audit-disclosure")
    assert skill_audit_result.skipped
    assert all(result.passed for result in results if not result.skipped)


# --- check_ascii_only ---


def test_check_ascii_only_passes_clean_text() -> None:
    result = preflight.check_ascii_only(_CLEAN_BODY)
    assert result.passed
    assert not result.skipped


def test_check_ascii_only_flags_non_ascii() -> None:
    result = preflight.check_ascii_only("PR body with an em dash — here.\n")
    assert not result.passed
    assert "non-ASCII" in result.output


def test_check_ascii_only_allows_bare_tabs() -> None:
    result = preflight.check_ascii_only("col1\tcol2\n")
    assert result.passed


# --- format_report ---


def test_format_report_all_passed() -> None:
    results = [preflight.CheckResult("a", True, False, ""), preflight.CheckResult("b", True, False, "")]
    report = preflight.format_report(results)
    assert "PASS  a" in report
    assert "PASS  b" in report
    assert "all 2 run check(s) passed." in report


def test_format_report_with_failure_and_skip() -> None:
    results = [
        preflight.CheckResult("a", False, False, "FAIL: bad"),
        preflight.CheckResult("b", True, False, ""),
        preflight.CheckResult("c", False, True, "skipped reason"),
    ]
    report = preflight.format_report(results)
    assert "FAIL  a" in report
    assert "PASS  b" in report
    assert "SKIPPED  c" in report
    assert "1 of 3 check(s) FAILED: a" in report
    assert "skipped reason" in report


# --- check_provenance_marker_scan (real sibling script) ---


def test_check_provenance_marker_scan_passes_clean_body(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    result = preflight.check_provenance_marker_scan(body)
    assert result.passed
    assert not result.skipped


def test_check_provenance_marker_scan_flags_session_url(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(
        "Generated by claude-example-model during session https://claude.ai/code/session_01Example\n",
        encoding="utf-8",
    )
    result = preflight.check_provenance_marker_scan(body)
    assert not result.passed


def test_check_provenance_marker_scan_raises_when_sibling_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    monkeypatch.setattr(preflight, "PROVENANCE_MARKER_SCAN", tmp_path / "does-not-exist.py")
    try:
        preflight.check_provenance_marker_scan(body)
        raise AssertionError("expected PrBodyPreflightError")
    except preflight.PrBodyPreflightError:
        pass


# --- check_provenance_disclosure (real sibling script, issue #1711) ---


def test_check_provenance_disclosure_passes_clean_body(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    result = preflight.check_provenance_disclosure(body, None)
    assert result.passed
    assert not result.skipped


def test_check_provenance_disclosure_reconstructs_1711_false_positive(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_1711_BODY, encoding="utf-8")
    result = preflight.check_provenance_disclosure(body, None)
    assert not result.passed
    assert "paragraph" in result.output.lower()


def test_check_provenance_disclosure_grades_diff_added_corpus_too(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    corpus = "no access to a registered skill invocation for a dispatch tool\n"
    result = preflight.check_provenance_disclosure(body, corpus)
    assert not result.passed


def test_check_provenance_disclosure_raises_when_sibling_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    monkeypatch.setattr(preflight, "PROVENANCE_DISCLOSURE", tmp_path / "does-not-exist.py")
    try:
        preflight.check_provenance_disclosure(body, None)
        raise AssertionError("expected PrBodyPreflightError")
    except preflight.PrBodyPreflightError:
        pass


# --- check_skill_audit_disclosure ---


def test_check_skill_audit_disclosure_skipped_without_check_diff(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    result = preflight.check_skill_audit_disclosure(body, None)
    assert result.skipped
    assert not result.passed


_STAND_IN_SKILL_AUDIT_GATE = """\
import sys
args = sys.argv[1:]
assert args[0] == '--check-diff'
assert args[1] == 'BASE'
assert args[2] == 'HEAD'
assert args[3] == '--body-file'
body = open(args[4]).read()
if 'RAN,' in body:
    print('FAIL: disclosure line malformed', file=sys.stderr)
    sys.exit(1)
print('PASS')
sys.exit(0)
"""


def test_check_skill_audit_disclosure_reconstructs_1707_regex_break(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #1707: a stray comma right after "RAN" broke the real gate's
    own regex. This stand-in asserts the exact argv contract
    check_skill_audit_disclosure promises (--check-diff BASE HEAD
    --body-file PATH) and reproduces that comma-sensitive shape, so the
    test proves this module's own argv wiring surfaces a FAIL exactly
    the way the original defect would have -- and that a corrected body
    passes once fixed."""
    dummy = tmp_path / "dummy_skill_audit_gate.py"
    dummy.write_text(_STAND_IN_SKILL_AUDIT_GATE, encoding="utf-8")
    monkeypatch.setattr(preflight, "SKILL_AUDIT_DISCLOSURE", dummy)

    body_fail = tmp_path / "body_fail.txt"
    body_fail.write_text("deterministic-gate-quality: RAN, iteratively\n", encoding="utf-8")
    result = preflight.check_skill_audit_disclosure(body_fail, ("BASE", "HEAD"))
    assert not result.passed
    assert not result.skipped

    body_pass = tmp_path / "body_pass.txt"
    body_pass.write_text("deterministic-gate-quality: RAN\n", encoding="utf-8")
    result = preflight.check_skill_audit_disclosure(body_pass, ("BASE", "HEAD"))
    assert result.passed


def test_check_skill_audit_disclosure_raises_when_sibling_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    monkeypatch.setattr(preflight, "SKILL_AUDIT_DISCLOSURE", tmp_path / "does-not-exist.py")
    try:
        preflight.check_skill_audit_disclosure(body, ("BASE", "HEAD"))
        raise AssertionError("expected PrBodyPreflightError")
    except preflight.PrBodyPreflightError:
        pass


# --- _registry_required_packages / _missing_packages_report (issue #1725 review finding 1) ---


def test_registry_required_packages_empty_on_unreadable_registry(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(preflight, "SSOT_PATH", tmp_path / "does-not-exist.json")
    assert preflight._registry_required_packages("skill-audit-disclosure") == []


def test_registry_required_packages_empty_on_invalid_utf8_registry(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_registry = tmp_path / "ssot.json"
    bad_registry.write_bytes(b"\xff\xfe not valid utf-8")
    monkeypatch.setattr(preflight, "SSOT_PATH", bad_registry)
    assert preflight._registry_required_packages("skill-audit-disclosure") == []


def test_registry_required_packages_empty_when_registry_not_a_dict(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad_registry = tmp_path / "ssot.json"
    bad_registry.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(preflight, "SSOT_PATH", bad_registry)
    assert preflight._registry_required_packages("skill-audit-disclosure") == []


def test_registry_required_packages_empty_for_unknown_gate_id() -> None:
    assert preflight._registry_required_packages("no-such-gate-id") == []


def test_registry_required_packages_finds_skill_audit_disclosure_pydantic() -> None:
    """Confirms the real, live .gitapex/ssot.json still declares
    skill-audit-disclosure's own pydantic precondition -- the exact fact
    check_skill_audit_disclosure's own precondition probe depends on."""
    assert "pydantic" in preflight._registry_required_packages("skill-audit-disclosure")


def test_missing_packages_report_none_when_gate_declares_no_packages() -> None:
    assert preflight._missing_packages_report("no-such-gate-id") is None


def test_missing_packages_report_none_when_checker_script_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(preflight, "PYTHON_PRECONDITION_CHECKER", tmp_path / "does-not-exist.py")
    assert preflight._missing_packages_report("skill-audit-disclosure") is None


def test_missing_packages_report_flags_a_genuinely_missing_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "_registry_required_packages", lambda gate_id: ["this-package-does-not-exist"])
    report = preflight._missing_packages_report("skill-audit-disclosure")
    assert report is not None
    assert "not importable" in report
    assert "uv sync" in report


def test_missing_packages_report_treats_a_flag_shaped_package_name_as_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defeat test for the "--" argv separator fix (issue #1725 review
    finding): a registry-declared package name that happens to look like
    an argparse flag (e.g. "--help") must still reach
    gitapex_check_python_precondition.py as inert positional data, not be
    read as option syntax for that script's own CLI. Without the "--"
    separator this module's own _run call now adds, "--help" would trigger
    that script's own --help handling instead of a module-import probe --
    exiting 0 with usage text, not JSON -- which _missing_packages_report
    would misread as "every required package is importable," silently
    losing the deny this scenario should produce. Mirrors
    hooks/test_gitapex_check_pr_skill_audit_disclosure_shell.py's own
    test_tier1_precondition_treats_a_flag_shaped_package_name_as_data for
    the sibling hook's identical call site."""
    monkeypatch.setattr(preflight, "_registry_required_packages", lambda gate_id: ["--help"])
    report = preflight._missing_packages_report("skill-audit-disclosure")
    assert report is not None, "a flag-shaped package name must still be reported missing, not silently skipped"
    assert "--help" in report
    assert "uv sync" in report


def test_check_skill_audit_disclosure_reports_missing_dependency_instead_of_running(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """check_skill_audit_disclosure's own precondition probe short-circuits
    before invoking the real gate script at all when a required package is
    missing -- confirmed by pointing SKILL_AUDIT_DISCLOSURE at a script
    that would fail the test if actually executed."""
    poison_script = tmp_path / "should_not_run.py"
    poison_script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "SKILL_AUDIT_DISCLOSURE", poison_script)
    monkeypatch.setattr(preflight, "_registry_required_packages", lambda gate_id: ["this-package-does-not-exist"])

    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    result = preflight.check_skill_audit_disclosure(body, ("BASE", "HEAD"))
    assert not result.passed
    assert not result.skipped
    assert "not importable" in result.output


# --- run_all_checks: --skip (issue #1725 review finding 2) ---


def test_run_all_checks_honors_skip(tmp_path: pathlib.Path) -> None:
    body_path = tmp_path / "body.txt"
    body_path.write_text(_CLEAN_BODY, encoding="utf-8")
    results = preflight.run_all_checks(body_path, _CLEAN_BODY, None, frozenset({"skill-audit-disclosure"}))
    names = {result.name for result in results}
    assert names == {"provenance-disclosure", "ascii-only", "provenance-marker-scan"}


def test_run_all_checks_skipping_everything_returns_no_results(tmp_path: pathlib.Path) -> None:
    body_path = tmp_path / "body.txt"
    body_path.write_text(_CLEAN_BODY, encoding="utf-8")
    results = preflight.run_all_checks(body_path, _CLEAN_BODY, None, frozenset(preflight.SUB_CHECK_NAMES))
    assert results == []


def test_run_all_checks_skip_provenance_disclosure_avoids_diff_added_corpus_computation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When provenance-disclosure is skipped, build_diff_added_corpus is
    never called even with --check-diff supplied -- confirmed by making it
    raise if invoked."""

    def _boom(base_ref: str, head_ref: str) -> str:
        raise AssertionError("build_diff_added_corpus should not have been called")

    monkeypatch.setattr(preflight, "build_diff_added_corpus", _boom)
    body_path = tmp_path / "body.txt"
    body_path.write_text(_CLEAN_BODY, encoding="utf-8")
    results = preflight.run_all_checks(
        body_path, _CLEAN_BODY, ("BASE", "HEAD"), frozenset({"skill-audit-disclosure", "provenance-disclosure"})
    )
    names = {result.name for result in results}
    assert names == {"ascii-only", "provenance-marker-scan"}


def test_main_skip_flag_excludes_named_sub_check(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = preflight.main(["--body", str(body), "--skip", "skill-audit-disclosure"])
    assert exit_code == 0
    assert "skill-audit-disclosure" not in capsys.readouterr().out


def test_main_skip_rejects_unknown_check_name(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    with pytest.raises(SystemExit):
        preflight.main(["--body", str(body), "--skip", "not-a-real-check"])


# --- build_diff_added_corpus ---


def test_build_diff_added_corpus_extracts_added_paragraph(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_git_repo(tmp_path / "repo")
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    (docs_dir / "note.md").write_text("first version\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "base"], repo)
    run_git(["git", "tag", "base"], repo)

    (docs_dir / "note.md").write_text("first version\n\nsecond paragraph added\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "head"], repo)

    monkeypatch.setattr(preflight, "REPO_ROOT", repo)
    corpus = preflight.build_diff_added_corpus("base", "HEAD")
    assert "second paragraph added" in corpus


def test_build_diff_added_corpus_raises_on_bad_ref(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "init"], repo)

    monkeypatch.setattr(preflight, "REPO_ROOT", repo)
    try:
        preflight.build_diff_added_corpus("does-not-exist", "HEAD")
        raise AssertionError("expected PrBodyPreflightError")
    except preflight.PrBodyPreflightError:
        pass


def test_build_diff_added_corpus_raises_when_sibling_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "init"], repo)
    run_git(["git", "tag", "base"], repo)

    monkeypatch.setattr(preflight, "REPO_ROOT", repo)
    monkeypatch.setattr(preflight, "EXTRACT_DIFF_ADDED_LINES", tmp_path / "does-not-exist.py")
    try:
        preflight.build_diff_added_corpus("base", "HEAD")
        raise AssertionError("expected PrBodyPreflightError")
    except preflight.PrBodyPreflightError:
        pass


def test_build_diff_added_corpus_raises_when_extract_script_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "base"], repo)
    run_git(["git", "tag", "base"], repo)
    (repo / "README.md").write_text("hello\nmore\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "head"], repo)

    broken_extractor = tmp_path / "broken_extract.py"
    broken_extractor.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")

    monkeypatch.setattr(preflight, "REPO_ROOT", repo)
    monkeypatch.setattr(preflight, "EXTRACT_DIFF_ADDED_LINES", broken_extractor)
    try:
        preflight.build_diff_added_corpus("base", "HEAD")
        raise AssertionError("expected PrBodyPreflightError")
    except preflight.PrBodyPreflightError:
        pass


# --- run_all_checks / main (end to end) ---


def test_main_exits_zero_on_clean_body(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    assert preflight.main(["--body", str(body)]) == 0


def test_main_exits_nonzero_reconstructing_1711(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_1711_BODY, encoding="utf-8")
    assert preflight.main(["--body", str(body)]) == 1


def test_main_accepts_body_file_alias(tmp_path: pathlib.Path) -> None:
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    assert preflight.main(["--body-file", str(body)]) == 0


def test_main_errors_on_missing_body_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = preflight.main(["--body", str(tmp_path / "does-not-exist.txt")])
    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_main_errors_on_invalid_utf8_body_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    body = tmp_path / "body.txt"
    body.write_bytes(b"\xff\xfe not valid utf-8")
    exit_code = preflight.main(["--body", str(body)])
    assert exit_code == 1
    assert "not valid UTF-8" in capsys.readouterr().err


def test_main_with_check_diff_runs_the_diff_dependent_sub_checks(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercises main()'s own --check-diff branch end to end (argv parsing
    through run_all_checks's own build_diff_added_corpus call and
    check_skill_audit_disclosure's own --check-diff invocation), against a
    scratch git repo and a stand-in skill-audit-disclosure gate -- the same
    argv-contract stand-in test_check_skill_audit_disclosure_reconstructs_
    1707_regex_break uses, reused here so this end-to-end path needs no
    real git history from this checkout or its pydantic-backed flag module."""
    repo = init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "base"], repo)
    run_git(["git", "tag", "BASE"], repo)
    (repo / "README.md").write_text("hello\nmore\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "head"], repo)

    dummy = tmp_path / "dummy_skill_audit_gate.py"
    dummy.write_text(_STAND_IN_SKILL_AUDIT_GATE, encoding="utf-8")
    monkeypatch.setattr(preflight, "REPO_ROOT", repo)
    monkeypatch.setattr(preflight, "SKILL_AUDIT_DISCLOSURE", dummy)

    body = tmp_path / "body.txt"
    body.write_text("deterministic-gate-quality: RAN\n", encoding="utf-8")
    assert preflight.main(["--body", str(body), "--check-diff", "BASE", "HEAD"]) == 0


def test_main_isolates_a_sub_check_that_cannot_run_from_the_rest(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sub-check that cannot run at all (here, a missing skill-audit-
    disclosure sibling script under --check-diff) is reported as a FAIL for
    that sub-check alone and exits 1 -- the other three sub-checks still
    run and are reported too, not silently lost. Before _isolated existed,
    this exact scenario raised PrBodyPreflightError straight out of
    run_all_checks, aborting every other sub-check's own result -- found by
    an independent adversarial review of this issue's own implementation,
    reconstructed here as a defeat test against that regression."""
    repo = init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "init"], repo)
    run_git(["git", "tag", "base"], repo)

    monkeypatch.setattr(preflight, "REPO_ROOT", repo)
    monkeypatch.setattr(preflight, "SKILL_AUDIT_DISCLOSURE", tmp_path / "does-not-exist.py")

    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = preflight.main(["--body", str(body), "--check-diff", "base", "HEAD"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "FAIL  skill-audit-disclosure" in out
    assert "sibling script not found" in out
    # The other three sub-checks still ran and reported PASS -- the whole
    # point of this isolation.
    assert "PASS  provenance-disclosure" in out
    assert "PASS  ascii-only" in out
    assert "PASS  provenance-marker-scan" in out


def test_main_isolates_a_sub_check_that_times_out_from_the_rest(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A sub-check whose own subprocess hangs past SUBPROCESS_TIMEOUT_SECONDS
    is reported as a FAIL for that sub-check alone -- the other three still
    run and are reported, via run_all_checks's own _isolated wrapper."""
    slow_script = tmp_path / "slow_provenance_scan.py"
    slow_script.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "PROVENANCE_MARKER_SCAN", slow_script)
    monkeypatch.setattr(preflight, "SUBPROCESS_TIMEOUT_SECONDS", 0.1)

    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = preflight.main(["--body", str(body)])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "FAIL  provenance-marker-scan" in out
    assert "timed out" in out
    assert "PASS  provenance-disclosure" in out
    assert "PASS  ascii-only" in out


def test_run_all_checks_isolates_build_diff_added_corpus_failure_from_the_rest(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When build_diff_added_corpus itself raises (here, its own
    diff-added-lines sibling script is missing), only provenance-
    disclosure is reported as failed (via the diff_added_corpus_error path,
    the same isolation _isolated applies to every other sub-check) --
    skill-audit-disclosure, ascii-only, and provenance-marker-scan still
    run, on the same --check-diff ref pair."""
    repo = init_git_repo(tmp_path / "repo")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "base"], repo)
    run_git(["git", "tag", "BASE"], repo)
    (repo / "README.md").write_text("hello\nmore\n", encoding="utf-8")
    run_git(["git", "add", "-A"], repo)
    run_git(["git", "commit", "-q", "-m", "head"], repo)

    dummy = tmp_path / "dummy_skill_audit_gate.py"
    dummy.write_text(_STAND_IN_SKILL_AUDIT_GATE, encoding="utf-8")
    monkeypatch.setattr(preflight, "REPO_ROOT", repo)
    monkeypatch.setattr(preflight, "SKILL_AUDIT_DISCLOSURE", dummy)
    monkeypatch.setattr(preflight, "EXTRACT_DIFF_ADDED_LINES", tmp_path / "does-not-exist.py")

    body_text = "deterministic-gate-quality: RAN\n"
    body_path = tmp_path / "body.txt"
    body_path.write_text(body_text, encoding="utf-8")
    results = preflight.run_all_checks(body_path, body_text, ("BASE", "HEAD"))
    by_name = {result.name: result for result in results}
    assert not by_name["provenance-disclosure"].passed
    assert "error:" in by_name["provenance-disclosure"].output
    assert by_name["ascii-only"].passed
    assert by_name["provenance-marker-scan"].passed
    assert by_name["skill-audit-disclosure"].passed


def test_run_all_checks_reports_a_timed_out_diff_added_corpus_build(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_diff_added_corpus's own subprocess.TimeoutExpired is caught
    the same way its PrBodyPreflightError sibling case already is (see
    test_run_all_checks_isolates_build_diff_added_corpus_failure_from_the_rest)
    -- reported as a failing provenance-disclosure result via _isolated's
    own diff_added_corpus_error path, not raised out of run_all_checks."""

    def _timed_out(base_ref: str, head_ref: str) -> str:
        raise subprocess.TimeoutExpired(cmd=["git", "diff"], timeout=1)

    monkeypatch.setattr(preflight, "build_diff_added_corpus", _timed_out)
    body_path = tmp_path / "body.txt"
    body_path.write_text(_CLEAN_BODY, encoding="utf-8")
    results = preflight.run_all_checks(body_path, _CLEAN_BODY, ("BASE", "HEAD"), frozenset({"skill-audit-disclosure"}))
    by_name = {result.name: result for result in results}
    assert not by_name["provenance-disclosure"].passed
    assert "timed out" in by_name["provenance-disclosure"].output
    assert by_name["ascii-only"].passed


# --- main(): the outer try/except backstop (run_all_checks itself no longer
# raises in normal operation -- see _isolated -- but this defensive path
# stays in place for a future sub-check added without going through it) ---


def test_main_backstop_reports_prbodypreflighterror_from_run_all_checks(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(*args: object, **kwargs: object) -> list[preflight.CheckResult]:
        raise preflight.PrBodyPreflightError("simulated: a future sub-check bypassed _isolated")

    monkeypatch.setattr(preflight, "run_all_checks", _boom)
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = preflight.main(["--body", str(body)])
    assert exit_code == 1
    assert "error: simulated" in capsys.readouterr().err


def test_main_backstop_reports_timeoutexpired_from_run_all_checks(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(*args: object, **kwargs: object) -> list[preflight.CheckResult]:
        raise subprocess.TimeoutExpired(cmd=["python3"], timeout=1)

    monkeypatch.setattr(preflight, "run_all_checks", _boom)
    body = tmp_path / "body.txt"
    body.write_text(_CLEAN_BODY, encoding="utf-8")
    exit_code = preflight.main(["--body", str(body)])
    assert exit_code == 1
    assert "timed out" in capsys.readouterr().err
