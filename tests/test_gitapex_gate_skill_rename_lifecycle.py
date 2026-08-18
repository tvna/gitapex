"""Tests for the skill-rename lifecycle gate
(.github/scripts/gitapex_gate_skill_rename_lifecycle.py).

Refs #285 (repair 2): a skill directory removed in this PR must be
recorded as some surviving skill's spec.lifecycle.renamedFrom -- this
gate grades the removed-name list the calling workflow's git-ls-tree diff
hands it, deterministically catching what a reviewer bot caught by hand on
PR #282. Revised after a /code-review finding that the original
git-diff-name-status -M design silently skipped a rename bundled with a
substantial content rewrite (below git's ~50% default similarity
threshold for rename detection) -- this version instead compares
directory listings, which is unaffected by how much content changed.
"""

from __future__ import annotations

import pathlib
import re

import gitapex_gate_skill_rename_lifecycle as gate
import pytest
import yaml
from conftest import FakeStdin as _FakeStdin
from conftest import make_validation_error

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _write_sidecar(tmp_path, new_name, *, renamed_from=None, under_wrong_key=False):
    skill_dir = tmp_path / "skills" / new_name
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    if under_wrong_key:
        # A renamedFrom-shaped line at 4-space indent OUTSIDE spec.lifecycle
        # (e.g. accidentally placed under spec.skillDependencies) -- must
        # NOT be picked up, matching gitapex_check_skill_shape.py's own
        # context-aware parser.
        body = f"  skillDependencies:\n    requires: []\n    renamedFrom: {renamed_from}\n"
    elif renamed_from:
        body = f"  lifecycle:\n    renamedFrom: {renamed_from}\n"
    else:
        body = ""
    (metadata_dir / "gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        f"  name: {new_name}\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        f"{body}",
        encoding="utf-8",
    )


def test_parse_names_reads_one_per_line():
    assert gate.parse_names("issue-to-branch\nissue-to-fix\n") == [
        "issue-to-branch",
        "issue-to-fix",
    ]


def test_parse_names_ignores_blank_lines():
    assert gate.parse_names("\na\n\n\nb\n\n") == ["a", "b"]


def test_parse_names_empty_input_is_empty_list():
    assert gate.parse_names("") == []
    assert gate.parse_names("\n\n") == []


def test_renamed_from_extracts_value_nested_under_lifecycle():
    text = "spec:\n  lifecycle:\n    renamedFrom: old-name\n  portability: Portable\n"
    assert gate._renamed_from(text) == "old-name"


def test_renamed_from_absent_is_none():
    text = "spec:\n  portability: Portable\n  capabilityAssumption: Broad\n"
    assert gate._renamed_from(text) is None


def test_renamed_from_blank_value_is_none():
    text = "spec:\n  lifecycle:\n    renamedFrom:\n  portability: Portable\n"
    assert gate._renamed_from(text) is None


def test_non_empty_or_none_rejects_empty_string():
    # Plain-Python replacement for the former pydantic RenamedFromValue
    # model: an empty string must become None -- the same "nothing usefully
    # recorded" case test_renamed_from_blank_value_is_none exercises
    # end-to-end above.
    assert gate._non_empty_or_none("") is None


def test_non_empty_or_none_accepts_non_empty_string():
    assert gate._non_empty_or_none("old-name") == "old-name"


def test_renamed_from_strips_double_quotes():
    text = 'spec:\n  lifecycle:\n    renamedFrom: "old-name"\n'
    assert gate._renamed_from(text) == "old-name"


def test_renamed_from_decodes_json_escape_sequences():
    # Mirrors gitapex_check_skill_shape.py's own _unquote: a double-quoted value
    # is JSON-decoded, not just naively stripped, so a real escape
    # sequence round-trips correctly instead of leaving literal backslashes.
    text = 'spec:\n  lifecycle:\n    renamedFrom: "old\\"name"\n'
    assert gate._renamed_from(text) == 'old"name'


def test_renamed_from_ignores_line_outside_lifecycle_block(tmp_path):
    # Regression: a renamedFrom-shaped line at 4-space indent OUTSIDE
    # spec.lifecycle (e.g. under spec.skillDependencies) must not be
    # picked up -- gitapex_check_skill_shape.py's state-aware parser would never
    # recognize it there either.
    text = (
        "spec:\n"
        "  portability: Portable\n"
        "  skillDependencies:\n"
        "    requires: []\n"
        "    renamedFrom: should-not-be-picked-up\n"
    )
    assert gate._renamed_from(text) is None


def test_renamed_from_lifecycle_block_with_other_subkeys_present():
    text = (
        "spec:\n"
        "  lifecycle:\n"
        "    stable:\n"
        '      since: "2026-07-21"\n'
        "    renamedFrom: old-name\n"
        "  skillDependencies:\n"
        "    requires: []\n"
    )
    assert gate._renamed_from(text) == "old-name"


def test_all_renamed_from_values_collects_across_skills(tmp_path):
    _write_sidecar(tmp_path, "new-a", renamed_from="old-a")
    _write_sidecar(tmp_path, "new-b", renamed_from="old-b")
    _write_sidecar(tmp_path, "unrelated-skill")
    assert gate.all_renamed_from_values(tmp_path) == {"old-a", "old-b"}


def test_all_renamed_from_values_empty_when_no_skills(tmp_path):
    (tmp_path / "skills").mkdir()
    assert gate.all_renamed_from_values(tmp_path) == set()


def test_find_offenders_recorded_name_passes(tmp_path):
    _write_sidecar(tmp_path, "new-name", renamed_from="old-name")
    assert gate.find_offenders(["old-name"], tmp_path) == []


def test_find_offenders_unrecorded_name_fails(tmp_path):
    _write_sidecar(tmp_path, "new-name")
    offenders = gate.find_offenders(["old-name"], tmp_path)
    assert len(offenders) == 1
    assert "old-name" in offenders[0]


def test_find_offenders_does_not_require_1to1_pairing(tmp_path):
    # find_offenders only needs SOME current skill to record the removed
    # name -- it does not try to pair a specific removed name with a
    # specific added directory (multiple simultaneous renames in one PR
    # cannot be reliably paired without the same fragile similarity
    # heuristic this design deliberately avoids).
    _write_sidecar(tmp_path, "completely-different-new-name", renamed_from="old-name")
    assert gate.find_offenders(["old-name"], tmp_path) == []


def test_find_offenders_stray_key_does_not_satisfy(tmp_path):
    _write_sidecar(tmp_path, "new-name", renamed_from="old-name", under_wrong_key=True)
    offenders = gate.find_offenders(["old-name"], tmp_path)
    assert len(offenders) == 1


def test_find_offenders_no_skills_directory_fails(tmp_path):
    offenders = gate.find_offenders(["old-name"], tmp_path)
    assert len(offenders) == 1


def test_find_offenders_multiple_names_reports_each_independently(tmp_path):
    _write_sidecar(tmp_path, "good-new", renamed_from="good-old")
    offenders = gate.find_offenders(["good-old", "bad-old"], tmp_path)
    assert len(offenders) == 1
    assert "bad-old" in offenders[0]


def test_main_no_removed_names_passes(capsys):
    assert gate.main(["--removed", "/dev/null"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reads_names_from_stdin(monkeypatch, tmp_path, capsys):
    _write_sidecar(tmp_path, "new-name", renamed_from="old-name")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"old-name\n"))
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reads_names_from_file(monkeypatch, tmp_path, capsys):
    _write_sidecar(tmp_path, "new-name", renamed_from="old-name")
    monkeypatch.chdir(tmp_path)
    names_file = tmp_path / "removed.txt"
    names_file.write_text("old-name\n", encoding="utf-8")
    assert gate.main(["--removed", str(names_file)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_and_reports_offenders(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "skills").mkdir()
    names_file = tmp_path / "removed.txt"
    names_file.write_text("old-name\n", encoding="utf-8")
    assert gate.main(["--removed", str(names_file)]) == 1
    err = capsys.readouterr().err
    assert "old-name" in err


def test_main_reports_error_for_missing_names_file(capsys):
    assert gate.main(["--removed", "/no/such/file.txt"]) == 1
    assert "not found" in capsys.readouterr().err


def test_main_reports_error_for_non_utf8_names_file(tmp_path, capsys):
    path = tmp_path / "removed.txt"
    path.write_bytes(b"\xff\xfe bad")
    assert gate.main(["--removed", str(path)]) == 1
    err = capsys.readouterr().err
    assert "not valid UTF-8" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_stdin(monkeypatch, capsys):
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    assert gate.main([]) == 1
    err = capsys.readouterr().err
    assert "standard input" in err and "not valid UTF-8" in err
    assert "Traceback" not in err


# --- GateSkillRenameLifecycleArgs -----------------------------------------


def test_args_defaults_removed_to_none():
    assert gate.GateSkillRenameLifecycleArgs().removed is None


def test_args_accepts_a_removed_path_string():
    assert gate.GateSkillRenameLifecycleArgs(removed="/tmp/removed.txt").removed == "/tmp/removed.txt"


def test_main_exits_two_when_args_fail_validation(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise make_validation_error()

    monkeypatch.setattr(gate, "GateSkillRenameLifecycleArgs", _raise)
    assert gate.main(["--removed", "/dev/null"]) == 2
    assert "invalid CLI arguments" in capsys.readouterr().err


# --- the real repository's own CI workflow -------------------------------


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    """Drift gate for an invariant this change establishes, per CLAUDE.md
    section 3: `git merge-base` is resolved between `BASE_SHA` and
    `HEAD_SHA` rather than diffing against `base.sha` directly (the same
    reason `skill-audit-gate.yml`'s three-dot diff is used there), so a
    rename that landed on the base branch after this PR forked is never
    misattributed to this PR.

    Checking only for the literal substring `git merge-base` would still
    pass a workflow that computes `$merge_base` and never actually uses
    it; the second assertion confirms the computed variable is the one
    actually fed to the `git ls-tree` invocations this gate depends on
    (this workflow's own producer command, unlike the sibling `git diff`-
    based gates covered by the same assertion shape elsewhere in this
    repository).

    Scoped to the parsed `jobs.*.steps[].run` content, not the whole file
    as text: a CodeRabbit review on this same PR found that even a
    comment-stripped, whole-file substring scan could still be satisfied
    by a non-comment YAML value living outside any `run:` block. `PyYAML`
    is already a dependency of this repository, so this parses the
    workflow properly rather than layering another line-based heuristic
    on top of the previous one. `on:` is deliberately never parsed here --
    PyYAML's default YAML-1.1 resolver reads the bare `on` key as boolean
    `True`, not the string `"on"`, a well-known GitHub Actions YAML gotcha
    this test sidesteps by never needing that key. The first assertion
    also now requires the exact `"$BASE_SHA" "$HEAD_SHA"` argument pair,
    not just the `merge_base=$(git merge-base` prefix, closing a narrower
    gap the previous version left: a swapped or substituted variable would
    still have matched. The producer-line scan requires the word `git`
    followed later by the word `diff` or `ls-tree` (a regex, not the bare
    substrings `diff`/`ls-tree`) -- kept consistent with the sibling
    `git diff`-based gates in this same PR, whose own real invocation
    (`git -c core.quotePath=false diff ...`) has a flag between `git` and
    `diff` that a contiguous-substring requirement would fail to match
    (caught by running those sibling tests, not just reasoned about). A
    fourth CodeRabbit round found that the prior bare substring
    `diff`/`ls-tree` let an unrelated executable line (its own example:
    `echo 'diff "$merge_base"'`) satisfy the check; that decoy carries no
    `git` token at all, so the word-pair regex excludes it correctly.
    """
    workflow_path = REPO_ROOT / ".github/workflows/skill-rename-lifecycle-gate.yml"
    parsed = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    run_text = "\n".join(
        step["run"] for job in parsed["jobs"].values() for step in job.get("steps", []) if "run" in step
    )
    assert 'merge_base=$(git merge-base "$BASE_SHA" "$HEAD_SHA")' in run_text, run_text
    producer_lines = [
        line
        for line in run_text.split("\n")
        if re.search(r"\bgit\b.*(\bdiff\b|\bls-tree\b)", line) and '"$merge_base"' in line
    ]
    assert producer_lines, run_text
