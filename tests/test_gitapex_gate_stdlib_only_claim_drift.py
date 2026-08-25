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


def test_removed_line_colliding_with_a_source_header_does_not_hide_a_later_import() -> None:
    # Issue #1316: the symmetric case of the "++ "/"+++ " finding directly
    # above, never applied to this file's own `--- ` check. A *removed*
    # line whose own original content starts with "-- " is diff-prefixed
    # to "--- ...", identical to a real `--- a/<path>` source header.
    # Gating this check on `not in_hunk` (rather than raising or
    # unconditionally clearing `in_hunk` on it, the way `diff --git `/`@@`
    # are handled) lets it fall through to the normal `-`-prefixed removal
    # handling instead of being misread as a header -- so the real added
    # import two lines later is still correctly detected.
    #
    # An earlier version of this fix instead treated `--- ` exactly like
    # `diff --git `/`@@` (an unconditional boundary raising `ScanError`
    # when `in_hunk`), which closed the misattribution risk but
    # reintroduced a live false positive: an ordinary, correctly-declared
    # diff removing a real source line that happens to start with "-- "
    # (13 such lines exist today under this gate's own scope, e.g.
    # gitapex_scan_ruleset_drift.py's own line 6) aborted the whole scan
    # instead of being graded normally -- found by a dispatched
    # refactor/simplify review before landing.
    diff_text = (
        "diff --git a/.github/scripts/gitapex_gate_foo.py b/.github/scripts/gitapex_gate_foo.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/.github/scripts/gitapex_gate_foo.py\n"
        "+++ b/.github/scripts/gitapex_gate_foo.py\n"
        "@@ -1,3 +1,3 @@\n"
        " import os\n"
        "--- old comment marker\n"
        "+import pydantic\n"
        " import sys\n"
    )
    assert gate.parse_diff_added_third_party_imports(diff_text) == {".github/scripts/gitapex_gate_foo.py"}


def test_removing_a_real_source_line_starting_with_double_dash_is_graded_normally() -> None:
    # Real defeat case found live by a dispatched refactor/simplify review:
    # .github/scripts/gitapex_scan_ruleset_drift.py's own line 6 starts
    # "-- and differ only in..." -- an ordinary docstring line, not a diff
    # header. Removing it (diff-prefixed to "--- and differ only in...")
    # must not abort the whole scan; the diff's own real added import must
    # still be detected.
    diff_text = (
        "diff --git a/.github/scripts/gitapex_scan_ruleset_drift.py b/.github/scripts/gitapex_scan_ruleset_drift.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/.github/scripts/gitapex_scan_ruleset_drift.py\n"
        "+++ b/.github/scripts/gitapex_scan_ruleset_drift.py\n"
        "@@ -1,2 +1,2 @@\n"
        " import os\n"
        "-- and differ only in how much of the ruleset they look at\n"
        "+import pydantic\n"
    )
    assert gate.parse_diff_added_third_party_imports(diff_text) == {".github/scripts/gitapex_scan_ruleset_drift.py"}


def test_an_over_declared_hunk_before_the_next_diff_git_line_raises_scan_error() -> None:
    # An over-declared hunk (its own header claims more post-image lines
    # than its real body has) whose incompleteness is discovered at the
    # next file's own `diff --git ` line, not only at end of input.
    diff_text = (
        "diff --git a/.github/scripts/gitapex_gate_a.py b/.github/scripts/gitapex_gate_a.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/.github/scripts/gitapex_gate_a.py\n"
        "+++ b/.github/scripts/gitapex_gate_a.py\n"
        "@@ -1,1 +1,3 @@\n"
        " import os\n"
        "diff --git a/.github/scripts/gitapex_gate_b.py b/.github/scripts/gitapex_gate_b.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/.github/scripts/gitapex_gate_b.py\n"
        "+++ b/.github/scripts/gitapex_gate_b.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+import pydantic\n"
    )
    with pytest.raises(gate.ScanError, match="declared more pre-/post-image"):
        gate.parse_diff_added_third_party_imports(diff_text)


def test_an_unparseable_hunk_header_raises_scan_error() -> None:
    # Issue #1316: `_HUNK_RE` (the declared-count tracker's own regex)
    # fails to match a malformed `@@ ... @@` line -- fails closed rather
    # than silently treating it as a hunk carrying no declared counts.
    diff_text = (
        "diff --git a/.github/scripts/gitapex_gate_foo.py b/.github/scripts/gitapex_gate_foo.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/.github/scripts/gitapex_gate_foo.py\n"
        "+++ b/.github/scripts/gitapex_gate_foo.py\n"
        "@@ malformed hunk header @@\n"
        "+import pydantic\n"
    )
    with pytest.raises(gate.ScanError, match="unparseable hunk header"):
        gate.parse_diff_added_third_party_imports(diff_text)


def test_current_path_is_reset_at_a_new_diff_git_line() -> None:
    # Real defeat case found live by a dispatched adversarial review: a
    # file adding only a stdlib import, followed by an out-of-scope file
    # (notes.txt) adding a real third-party import, must not leak the
    # first file's own path forward -- `current_path` has to be cleared
    # at every `diff --git ` line, not only updated by the next `+++ `.
    diff_text = (
        "diff --git a/.github/scripts/gitapex_gate_a.py b/.github/scripts/gitapex_gate_a.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/.github/scripts/gitapex_gate_a.py\n"
        "+++ b/.github/scripts/gitapex_gate_a.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+import sys\n"
        "diff --git a/notes.txt b/notes.txt\n"
        "index 0000000..1111111 100644\n"
        "--- a/notes.txt\n"
        "+++ b/notes.txt\n"
        "@@ -0,0 +1,1 @@\n"
        "+import requests\n"
    )
    assert gate.parse_diff_added_third_party_imports(diff_text) == set()


def test_a_post_image_header_with_no_source_header_before_it_raises_scan_error() -> None:
    # Real defeat case found live by a dispatched adversarial review: a
    # `+++ b/<path>` header with no preceding `--- ` was accepted as
    # genuine, letting a hand-fed patch misattribute a real added import
    # to an attacker-named path the diff's own real headers never
    # legitimately introduced. Mirrors
    # gitapex_gate_detection_logic_property_coverage.py's own identical
    # fail-closed check.
    diff_text = (
        "diff --git a/.github/scripts/gitapex_gate_victim.py b/.github/scripts/gitapex_gate_victim.py\n"
        "index 0000000..1111111 100644\n"
        "+++ b/.github/scripts/gitapex_gate_victim.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+import pydantic\n"
    )
    with pytest.raises(gate.ScanError, match="no `--- ` source header"):
        gate.parse_diff_added_third_party_imports(diff_text)


def test_an_under_declared_hunk_still_records_its_real_added_import() -> None:
    # Real defeat case found live by a dispatched adversarial review: an
    # earlier revision's `if not in_hunk: continue` early-exit silently
    # dropped a real added import whenever a hunk's own declared
    # post-image count under-stated its real body (a zero/zero declared
    # hunk with a real "+" line still following) -- exactly the silent
    # miss this issue exists to close. `current_path is not None` alone
    # (no `in_hunk` gate) must still catch it, matching
    # gitapex_gate_detection_logic_property_coverage.py's own
    # unconditional recording.
    diff_text = (
        "diff --git a/.github/scripts/gitapex_gate_c.py b/.github/scripts/gitapex_gate_c.py\n"
        "index 0000000..1111111 100644\n"
        "--- a/.github/scripts/gitapex_gate_c.py\n"
        "+++ b/.github/scripts/gitapex_gate_c.py\n"
        "@@ -0,0 +0,0 @@\n"
        "+import requests\n"
    )
    assert gate.parse_diff_added_third_party_imports(diff_text) == {".github/scripts/gitapex_gate_c.py"}


def test_multi_file_diff_with_correctly_declared_hunks_attributes_each_import_to_its_own_file() -> None:
    # Issue #1316: the actual regression a bare, uncounted `not in_hunk`
    # guard on the `--- `/`diff --git ` check introduced -- an ordinary,
    # correctly-declared multi-file diff left `in_hunk` never clearing at
    # the second file's own real `+++ ` header, so its added import
    # misattributed to the first file's path instead of its own. Found
    # live by this issue's own differential-oracle property test
    # (tests/test_gitapex_gate_stdlib_only_claim_drift_properties.py)
    # before landing; this is the fixed regression's own direct proof.
    diff_text = _diff(".github/scripts/gitapex_gate_a.py", ["import pydantic"]) + _diff(
        ".github/scripts/gitapex_gate_b.py", ["import pydantic"]
    )
    assert gate.parse_diff_added_third_party_imports(diff_text) == {
        ".github/scripts/gitapex_gate_a.py",
        ".github/scripts/gitapex_gate_b.py",
    }


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
    # its own content happens to match the "imports itself" regex shape --
    # otherwise the source-(a) finding below would be double-counted as a
    # spurious second, source-(b) finding pointing at the same file.
    _write(
        tmp_path,
        ".github/scripts/gitapex_gate_foo.py",
        '"""Standard library only."""\n\nimport pydantic\nimport gitapex_gate_foo\n',
    )
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    findings = gate.find_stale_claims(diff_text, tmp_path)
    assert len(findings) == 1
    assert findings[0].source == "the changed file's own content"


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


def test_a_clean_importer_alongside_a_non_importing_script_is_not_flagged(tmp_path: pathlib.Path) -> None:
    # Exercises find_direct_importers' own loop continuing past both a
    # non-importing candidate (the `if import_re.search(...)` false
    # branch) and a clean importer (find_stale_claims' own importer-loop
    # false branch) without appending either.
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Clean."""\n\nimport pydantic\n')
    _write(tmp_path, ".github/scripts/gitapex_unrelated.py", '"""Does not import gitapex_gate_foo at all."""\n')
    _write(
        tmp_path, ".github/scripts/gitapex_clean_caller.py", '"""Clean, no stale claim."""\n\nimport gitapex_gate_foo\n'
    )
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    assert gate.find_stale_claims(diff_text, tmp_path) == []


def test_a_clean_referencing_workflow_is_not_flagged(tmp_path: pathlib.Path) -> None:
    # Exercises find_stale_claims' own workflow-loop false branch: the
    # workflow references the changed file (so it's a real candidate)
    # but carries no stale claim.
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Clean."""\n\nimport pydantic\n')
    _write(
        tmp_path,
        ".github/workflows/foo-gate.yml",
        "name: Foo gate\njobs:\n  foo:\n    steps:\n      - run: uv run --frozen python3 .github/scripts/gitapex_gate_foo.py\n",
    )
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    assert gate.find_stale_claims(diff_text, tmp_path) == []


def test_diff_header_without_a_b_prefix_is_used_as_is(tmp_path: pathlib.Path) -> None:
    # git supports --no-prefix, producing "+++ path" instead of
    # "+++ b/path"; the path must still resolve correctly.
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Standard library only."""\n\nimport pydantic\n')
    rel_path = ".github/scripts/gitapex_gate_foo.py"
    diff_text = (
        f"diff --git a/{rel_path} b/{rel_path}\nindex 0000000..1111111 100644\n--- {rel_path}\n+++ {rel_path}\n"
        "@@ -0,0 +1,1 @@\n+import pydantic\n"
    )
    findings = gate.find_stale_claims(diff_text, tmp_path)
    assert len(findings) == 1
    assert findings[0].changed_file == rel_path


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


def test_unreadable_referencing_workflow_raises_scan_error(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Clean."""\n\nimport pydantic\n')
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "trap.yml").mkdir()
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import pydantic"])
    with pytest.raises(gate.ScanError):
        gate.find_stale_claims(diff_text, tmp_path)


# --- comma-separated imports (code review found: `import os, pydantic` only
# captured "os", silently missing "pydantic") ---


def test_comma_separated_import_detects_every_named_module(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Standard library only."""\n\nimport os, pydantic\n')
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import os, pydantic"])
    findings = gate.find_stale_claims(diff_text, tmp_path)
    assert len(findings) == 1
    assert findings[0].source == "the changed file's own content"


def test_comma_separated_import_of_only_stdlib_modules_is_not_flagged(tmp_path: pathlib.Path) -> None:
    _write(tmp_path, ".github/scripts/gitapex_gate_foo.py", '"""Standard library only."""\n\nimport os, sys, json\n')
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import os, sys, json"])
    assert gate.find_stale_claims(diff_text, tmp_path) == []


def test_doubled_comma_is_invalid_syntax_and_names_no_modules() -> None:
    # A doubled comma ("import os,,pydantic") is not valid Python; ast.parse
    # raises SyntaxError, and _imported_root_modules treats that the same
    # as any other line that names no import at all -- an empty list, never
    # a bogus module name derived from the malformed text.
    assert gate._imported_root_modules("import os,,pydantic") == []


# --- adversarial-review findings: ast.parse replacing the old hand-rolled
# comma/whitespace tokenizer (issue #1052's own PR, second review round) ---


def test_trailing_comment_comma_is_not_parsed_as_a_second_import() -> None:
    # Real defeat case: the old regex/split tokenizer captured the whole
    # rest of the line including a trailing "#" comment, so a comma inside
    # unrelated comment prose was misread as a second imported alias.
    assert gate._imported_root_modules("import os  # noqa: E501, F401") == ["os"]


def test_semicolon_chained_import_statement_is_parsed_as_two_real_imports() -> None:
    # Real defeat case: the old tokenizer left a stray ";" attached to the
    # first name ("os;") instead of recognizing two separate statements.
    assert gate._imported_root_modules("import os; import sys") == ["os", "sys"]


def test_backslash_continuation_names_no_modules_rather_than_a_stray_backslash() -> None:
    # Real defeat case: a line-continued "import os, \\" (continuing onto a
    # second physical line the diff parser never sees) left a bare "\\"
    # parsed as if it were a module name under the old tokenizer.
    assert gate._imported_root_modules("import os, \\") == []


def test_invalid_import_syntax_names_no_modules() -> None:
    # Real defeat case: 'import "os";' is not valid Python (import expects
    # a name, not a string literal); the old regex still captured the
    # quoted text as a bogus "module name" and would have flagged a file
    # for an import that was never syntactically valid in the first place.
    assert gate._imported_root_modules('import "os";') == []


def test_comment_comma_does_not_cause_a_false_positive_end_to_end(tmp_path: pathlib.Path) -> None:
    _write(
        tmp_path,
        ".github/scripts/gitapex_gate_foo.py",
        '"""Standard library only."""\n\nimport os  # note: os, urllib3 unrelated\n',
    )
    diff_text = _diff(".github/scripts/gitapex_gate_foo.py", ["import os  # note: os, urllib3 unrelated"])
    assert gate.find_stale_claims(diff_text, tmp_path) == []


def test_malformed_diff_text_containing_a_bare_marker_substring_still_raises_scan_error(
    tmp_path: pathlib.Path,
) -> None:
    # Real defeat case: the malformed-diff guard originally checked whether
    # any marker occurred ANYWHERE in the text, so ordinary prose merely
    # mentioning "---" or "@@" mid-sentence satisfied it without being a
    # diff at all. The fix anchors each marker to the start of some line.
    prose = "This PR looks fine --- go ahead and merge (cc @@release-bot)\n"
    with pytest.raises(gate.ScanError):
        gate.find_stale_claims(prose, tmp_path)


def test_crlf_diff_still_detects_an_added_third_party_import(tmp_path: pathlib.Path) -> None:
    # Real defeat case: a CRLF-encoded diff (git's local plane under
    # core.autocrlf, or a re-saved --diff file) left a trailing "\r"
    # attached to the "+++ b/<path>" header's path, which then failed
    # _TARGET_DIR_RE's own $-anchored match and silently dropped the file.
    rel_path = ".github/scripts/gitapex_gate_foo.py"
    _write(tmp_path, rel_path, '"""Standard library only."""\n\nimport pydantic\n')
    lf_diff = _diff(rel_path, ["import pydantic"])
    crlf_diff = lf_diff.replace("\n", "\r\n")
    findings = gate.find_stale_claims(crlf_diff, tmp_path)
    assert len(findings) == 1
    assert findings[0].source == "the changed file's own content"


# --- CLI ---


def test_main_reads_diff_from_stdin_when_no_diff_flag_given(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    diff_bytes = _diff(".github/scripts/gitapex_gate_foo.py", ["import json"]).encode("utf-8")
    monkeypatch.setattr("sys.stdin.buffer.read", lambda: diff_bytes)
    rc = gate.main(["--root", str(tmp_path)])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_main_returns_two_on_undecodable_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin.buffer.read", lambda: b"\xff\xfe\x00bad")
    assert gate.main([]) == 2


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


def test_main_returns_two_on_malformed_non_diff_text(tmp_path: pathlib.Path) -> None:
    # code review found: find_stale_claims' own docstring promised exit
    # code 2 for a malformed diff, but nothing enforced it until the
    # _DIFF_STRUCTURE_MARKERS check was added -- this is the CLI-level
    # proof that the promise now holds.
    diff_file = tmp_path / "not-a-diff.txt"
    diff_file.write_text("this is not a unified diff at all\njust some prose\n", encoding="utf-8")
    rc = gate.main(["--diff", str(diff_file), "--root", str(tmp_path)])
    assert rc == 2


def test_find_stale_claims_raises_on_malformed_non_diff_text(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.ScanError):
        gate.find_stale_claims("this is not a unified diff at all\njust some prose\n", tmp_path)


# --- live proof against this repository's own real tree: after this gate
# lands, its own real files must stay clean (the actual regression
# backstop -- deliberately reads the real tree, not a fixture) ---


def test_this_repositorys_own_current_state_has_no_stale_claims() -> None:
    # A real, non-empty diff -- reconstructed as if the whole file were
    # newly added -- against an actual pydantic-importing file already in
    # this tree (issue #1040 wave 1), so this test genuinely exercises all
    # three text sources against real repo content instead of trivially
    # passing on an empty diff that has nothing to check.
    rel_path = ".github/scripts/gitapex_gate_hidden_characters.py"
    real_file = REPO_ROOT / rel_path
    diff_text = _diff(rel_path, real_file.read_text(encoding="utf-8").splitlines())
    assert gate.find_stale_claims(diff_text, REPO_ROOT) == []
