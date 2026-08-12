"""Issue #1052 (refs #1047, #1049): flag a stale "standard library
only"/"stdlib-only" claim, or a bare `python3 <file>.py` invocation
example, left behind after a diff adds a real third-party import to a
`.github/scripts/*.py` or `evals/scripts/*.py` file. See
`.github/scripts/gitapex_gate_stdlib_only_claim_drift.py`'s own module
docstring for the two incidents (issue #1040 waves 1 and 2) this gate
exists to prevent from recurring a third time.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_stdlib_only_claim_drift as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _diff(rel_path: str, added_lines: list[str]) -> str:
    """Build a minimal unified diff adding `added_lines` to `rel_path`,
    matching the shape `git diff -U0` produces (enough for this gate's own
    parser, which only reads the `+++ b/<path>` header and post-`@@` `+`
    lines)."""
    header = (
        f"diff --git a/{rel_path} b/{rel_path}\nindex 0000000..1111111 100644\n--- a/{rel_path}\n+++ b/{rel_path}\n"
    )
    hunk = f"@@ -0,0 +1,{len(added_lines)} @@\n"
    body = "".join(f"+{line}\n" for line in added_lines)
    return header + hunk + body


def _write(root: pathlib.Path, rel_path: str, content: str) -> pathlib.Path:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --- parse_diff_added_third_party_imports ---


def test_third_party_import_addition_is_detected() -> None:
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic", ""])
    assert gate.parse_diff_added_third_party_imports(diff_text) == {".github/scripts/gitapex_gate_foo.py"}


def test_from_import_form_is_detected() -> None:
    diff_text = _diff("evals/scripts/gitapex_foo.py", ["from pydantic import BaseModel"])
    assert gate.parse_diff_added_third_party_imports(diff_text) == {"evals/scripts/gitapex_foo.py"}


def test_stdlib_import_is_not_flagged() -> None:
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import json", "import pathlib"])
    assert gate.parse_diff_added_third_party_imports(diff_text) == set()


def test_indented_import_is_not_top_level() -> None:
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["if True:", "    import pydantic"])
    assert gate.parse_diff_added_third_party_imports(diff_text) == set()


def test_file_outside_scope_is_ignored() -> None:
    diff_text = _diff("skills/foo/scripts/gitapex_bar.py", ["import pydantic"])
    assert gate.parse_diff_added_third_party_imports(diff_text) == set()


def test_empty_diff_yields_empty_set() -> None:
    assert gate.parse_diff_added_third_party_imports("") == set()


def test_added_line_colliding_with_a_file_header_does_not_hide_a_later_import() -> None:
    # Adversarial-review finding (issue #1052's own PR): an added line
    # whose own content starts with "++ " is diff-prefixed to "+++ ...",
    # identical to a real `+++ b/<path>` file header. Without gating the
    # header check on `not in_hunk`, this line was misread as a second
    # file header mid-hunk, silently dropping every real added line after
    # it in the same hunk -- including the import a few lines later.
    diff_text = _diff(
        ".github/scripts/gitapex_gate_foo.py",
        [
            "# unified diff hunk header example:",
            "++ b/faketrap.py",
            "import pydantic",
        ],
    )
    assert gate.parse_diff_added_third_party_imports(diff_text) == {".github/scripts/gitapex_gate_foo.py"}


# --- has_stale_claim: the two real defect shapes, and the two real false
# positives found and fixed while measuring this gate against this
# repository's own already-corrected text (defeat-test-disclosure) ---


def test_stale_phrase_is_flagged() -> None:
    text = "Standard library only, so the calling workflow needs no dependency install."
    assert gate.has_stale_claim(text, "gitapex_gate_foo.py") is True


def test_bare_invocation_example_is_flagged() -> None:
    text = "Usage::\n\n    python3 gitapex_gate_foo.py\n"
    assert gate.has_stale_claim(text, "gitapex_gate_foo.py") is True


def test_uv_wrapped_invocation_example_is_not_flagged() -> None:
    text = "Usage::\n\n    uv run --frozen python3 gitapex_gate_foo.py\n"
    assert gate.has_stale_claim(text, "gitapex_gate_foo.py") is False


def test_clean_text_is_not_flagged() -> None:
    text = "This gate's own production invocation runs under uv run."
    assert gate.has_stale_claim(text, "gitapex_gate_foo.py") is False


def test_accurate_disclosure_with_nearby_uv_run_mention_is_not_flagged() -> None:
    # Real defeat case found while measuring this gate against
    # gitapex_compute_skill_audit_flags.py's own post-fix text (commit
    # 080a050): "my own code is standard library only, but ... uv run"
    # legitimately still contains the phrase.
    text = (
        "This module's own code is standard library only, but issue #1040 gave "
        "one of the three helper scripts it imports a real pydantic import -- so "
        "a dependency install is now required transitively. skill-audit-gate.yml's "
        "own invocation already runs this module under uv run, so that path is "
        "unaffected."
    )
    assert gate.has_stale_claim(text, "gitapex_compute_skill_audit_flags.py") is False


def test_boilerplate_usage_block_does_not_suppress_a_genuinely_stale_claim() -> None:
    # Adversarial-review finding (issue #1052's own PR): nearly every
    # .github/scripts/*.py docstring shows an indented `Usage:: uv run
    # --frozen python3 <file>.py` example regardless of whether the file
    # needs a third-party dependency. A bare "is uv run mentioned
    # anywhere nearby" check would suppress a genuinely stale,
    # uncorrected claim sitting near that routine boilerplate -- exactly
    # the flagship PR #1044 defect shape. The fix excludes indented
    # (Usage::-example) lines from the proximity search; only an
    # unindented, prose "uv run" mention -- a real corrective disclosure
    # -- suppresses.
    text = (
        "Standard library only, so the calling workflow needs no dependency install.\n\n"
        "Usage::\n\n"
        "    uv run --frozen python3 gitapex_gate_foo.py\n"
    )
    assert gate.has_stale_claim(text, "gitapex_gate_foo.py") is True


def test_negated_stale_phrase_is_not_flagged() -> None:
    # Real defeat case found while measuring this gate against
    # plugin-root-brace-notation-gate.yml's own post-fix text (commit
    # 3881c57): "no longer stdlib-only" is the accurate, corrected claim,
    # not a stale one -- the "uv run" mention is 39 lines away in that real
    # file, well outside any reasonable proximity window, so the negation
    # guard (not the proximity guard) is what must catch this case.
    text = "issue #1040 added a real pydantic import, so it is no longer stdlib-only, but still runs unconditionally"
    assert gate.has_stale_claim(text, "gitapex_gate_foo.py") is False


def test_far_away_uv_run_mention_does_not_suppress_a_real_stale_claim() -> None:
    # Adversarial: a decoy "uv run" mention thousands of characters away
    # (well outside the proximity window, and with no negation cue nearby)
    # must not suppress a genuinely stale, un-negated claim.
    text = "Standard library only, so the calling workflow needs no dependency install." + (" " * 1000) + "uv run"
    assert gate.has_stale_claim(text, "gitapex_gate_foo.py") is True


# --- find_stale_claims: the three text sources, end to end ---


def test_source_a_own_file_content_is_checked(tmp_path: pathlib.Path) -> None:
    _write(
        tmp_path,
        ".github/scripts/gitapex_gate_foo.py",
        '"""Standard library only."""\n\nimport pydantic\n',
    )
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    findings = gate.find_stale_claims(diff_text, tmp_path)
    assert len(findings) == 1
    assert findings[0].source == "the changed file's own content"


def test_source_b_direct_importer_is_checked(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Clean."""\n\nimport pydantic\n')
    _write(
        tmp_path,
        ".github/scripts/gitapex_caller.py",
        '"""Standard library only, calls gitapex_gate_foo."""\n\nimport gitapex_gate_foo\n',
    )
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    findings = gate.find_stale_claims(diff_text, tmp_path)
    assert len(findings) == 1
    assert findings[0].source == "a direct importer"
    assert "gitapex_caller.py" in findings[0].location


def test_source_b_ignores_the_changed_file_importing_itself(tmp_path: pathlib.Path) -> None:
    # find_direct_importers must exclude the changed file itself even if
    # its own content happens to match the "imports itself" regex shape
    # (it never does in real code, but the exclusion is what prevents
    # double-counting the source-(a) finding as a spurious source-(b) one).
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Clean."""\n\nimport pydantic\n')
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    findings = gate.find_stale_claims(diff_text, tmp_path)
    assert findings == []


def test_source_c_referencing_workflow_is_checked_even_when_not_adjacent_to_run_step(
    tmp_path: pathlib.Path,
) -> None:
    # Real regression shape (issue #1049): the stale claim was in a
    # top-of-file rationale comment, not adjacent to the run: step that
    # names the file.
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Clean."""\n\nimport pydantic\n')
    _write(
        tmp_path,
        ".github/workflows/foo-gate.yml",
        "# The scan is stdlib-only Python, so it costs a few seconds.\n"
        "name: Foo gate\n"
        "jobs:\n"
        "  foo:\n"
        "    steps:\n"
        "      - run: uv run --frozen python3 .github/scripts/gitapex_gate_foo.py\n",
    )
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    findings = gate.find_stale_claims(diff_text, tmp_path)
    assert len(findings) == 1
    assert findings[0].source == "a referencing workflow file"


def test_unrelated_workflow_not_referencing_the_file_is_not_flagged(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Clean."""\n\nimport pydantic\n')
    _write(
        tmp_path,
        ".github/workflows/unrelated.yml",
        "# Some other gate is stdlib-only.\nname: Unrelated\njobs:\n  a:\n    steps:\n      - run: echo hi\n",
    )
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    findings = gate.find_stale_claims(diff_text, tmp_path)
    assert findings == []


def test_no_findings_when_no_file_gains_a_third_party_import(tmp_path: pathlib.Path) -> None:
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import json"])
    assert gate.find_stale_claims(diff_text, tmp_path) == []


def test_empty_diff_is_a_legitimate_pass_not_an_error(tmp_path: pathlib.Path) -> None:
    assert gate.find_stale_claims("", tmp_path) == []


# --- fail-closed on malformed/unreadable input (dimension 15) ---


def test_unreadable_own_file_raises_scan_error(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    trap = tmp_path / ".github" / "scripts" / "gitapex_gate_foo.py"
    trap.mkdir()  # a directory named like the file -- read_text() raises OSError
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    with pytest.raises(gate.ScanError):
        gate.find_stale_claims(diff_text, tmp_path)


def test_unreadable_importer_raises_scan_error(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Clean."""\n\nimport pydantic\n')
    (tmp_path / ".github" / "scripts" / "gitapex_caller.py").mkdir()
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    with pytest.raises(gate.ScanError):
        gate.find_stale_claims(diff_text, tmp_path)


# --- CLI ---


def test_main_returns_zero_and_prints_ok_on_clean_diff(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    diff_file = tmp_path / "diff.txt"
    diff_file.write_text(_diff(".github/scripts/gitapex_gate_foo.py", ["import json"]), encoding="utf-8")
    rc = gate.main(["--diff", str(diff_file), "--root", str(tmp_path)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_main_returns_one_and_prints_findings_on_stale_claim(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Standard library only."""\n\nimport pydantic\n')
    diff_file = tmp_path / "diff.txt"
    diff_file.write_text(_diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"]), encoding="utf-8")
    rc = gate.main(["--diff", str(diff_file), "--root", str(tmp_path)])
    assert rc == 1
    out = capsys.readouterr().err + capsys.readouterr().out
    assert "gitapex_gate_foo.py" in out


def test_main_returns_two_on_missing_root(tmp_path: pathlib.Path) -> None:
    rc = gate.main(["--root", str(tmp_path / "does-not-exist")])
    assert rc == 2


def test_main_returns_two_on_unreadable_diff_file(tmp_path: pathlib.Path) -> None:
    bad_diff = tmp_path / "bad.diff"
    bad_diff.write_bytes(b"\xff\xfe\x00bad")
    rc = gate.main(["--diff", str(bad_diff)])
    assert rc == 2


def test_main_returns_two_when_scan_error_is_raised(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "scripts" / "gitapex_gate_foo.py").mkdir()
    diff_file = tmp_path / "diff.txt"
    diff_file.write_text(_diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"]), encoding="utf-8")
    rc = gate.main(["--diff", str(diff_file), "--root", str(tmp_path)])
    assert rc == 2


# --- live proof against this repository's own real tree: after this gate
# lands, its own real files must stay clean (the actual regression
# backstop -- deliberately reads the real tree, not a fixture) ---


def test_this_repositorys_own_current_state_has_no_stale_claims() -> None:
    assert gate.find_stale_claims("", REPO_ROOT) == []
