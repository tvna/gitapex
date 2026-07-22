"""Tests for the skill-rename lifecycle gate
(.github/scripts/gate_skill_rename_lifecycle.py).

Refs #285 (repair 2): a renamed skill directory's surviving sidecar must
record spec.lifecycle.renamedFrom naming the old directory -- this gate
grades the (old-name, new-name) pairs the calling workflow's git-diff step
hands it, deterministically catching what a reviewer bot caught by hand on
PR #282.
"""

from __future__ import annotations

import io

import pytest

import gate_skill_rename_lifecycle as gate


def _write_sidecar(tmp_path, new_name, *, renamed_from=None, missing=False):
    skill_dir = tmp_path / "skills" / new_name
    if missing:
        return
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    lifecycle_block = f"  lifecycle:\n    renamedFrom: {renamed_from}\n" if renamed_from else ""
    (metadata_dir / "gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        f"  name: {new_name}\n"
        "spec:\n"
        f"{lifecycle_block}"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n",
        encoding="utf-8")


def test_parse_pairs_reads_space_separated_lines():
    text = "issue-to-branch planning-a-branch-from-an-issue\nissue-to-fix fixing-a-reported-issue\n"
    assert gate.parse_pairs(text) == [
        ("issue-to-branch", "planning-a-branch-from-an-issue"),
        ("issue-to-fix", "fixing-a-reported-issue"),
    ]


def test_parse_pairs_ignores_blank_lines():
    text = "\na b\n\n\nc d\n\n"
    assert gate.parse_pairs(text) == [("a", "b"), ("c", "d")]


def test_parse_pairs_empty_input_is_empty_list():
    assert gate.parse_pairs("") == []
    assert gate.parse_pairs("\n\n") == []


def test_parse_pairs_malformed_line_raises():
    with pytest.raises(ValueError, match="line 1"):
        gate.parse_pairs("only-one-token\n")


def test_parse_pairs_too_many_tokens_raises():
    with pytest.raises(ValueError, match="line 2"):
        gate.parse_pairs("a b\nc d e\n")


def test_renamed_from_extracts_value():
    text = "spec:\n  lifecycle:\n    renamedFrom: old-name\n  portability: Portable\n"
    assert gate._renamed_from(text) == "old-name"


def test_renamed_from_absent_is_none():
    text = "spec:\n  portability: Portable\n  capabilityAssumption: Broad\n"
    assert gate._renamed_from(text) is None


def test_renamed_from_blank_value_is_none():
    text = "spec:\n  lifecycle:\n    renamedFrom:\n  portability: Portable\n"
    assert gate._renamed_from(text) is None


def test_renamed_from_strips_quotes():
    text = 'spec:\n  lifecycle:\n    renamedFrom: "old-name"\n'
    assert gate._renamed_from(text) == "old-name"


def test_find_offenders_correct_rename_passes(tmp_path):
    _write_sidecar(tmp_path, "new-name", renamed_from="old-name")
    offenders = gate.find_offenders([("old-name", "new-name")], tmp_path)
    assert offenders == []


def test_find_offenders_missing_renamed_from_fails(tmp_path):
    _write_sidecar(tmp_path, "new-name")
    offenders = gate.find_offenders([("old-name", "new-name")], tmp_path)
    assert len(offenders) == 1
    assert "new-name" in offenders[0]
    assert "missing" in offenders[0]
    assert "old-name" in offenders[0]


def test_find_offenders_wrong_renamed_from_value_fails(tmp_path):
    _write_sidecar(tmp_path, "new-name", renamed_from="some-other-old-name")
    offenders = gate.find_offenders([("old-name", "new-name")], tmp_path)
    assert len(offenders) == 1
    assert "some-other-old-name" in offenders[0]
    assert "old-name" in offenders[0]


def test_find_offenders_missing_sidecar_fails(tmp_path):
    offenders = gate.find_offenders([("old-name", "new-name")], tmp_path)
    assert len(offenders) == 1
    assert "missing" in offenders[0]


def test_find_offenders_multiple_pairs_reports_each_independently(tmp_path):
    _write_sidecar(tmp_path, "good-new", renamed_from="good-old")
    _write_sidecar(tmp_path, "bad-new")
    offenders = gate.find_offenders(
        [("good-old", "good-new"), ("bad-old", "bad-new")], tmp_path)
    assert len(offenders) == 1
    assert "bad-new" in offenders[0]


def test_main_no_pairs_passes(capsys):
    assert gate.main(["--pairs", "/dev/null"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reads_pairs_from_stdin(monkeypatch, tmp_path, capsys):
    _write_sidecar(tmp_path, "new-name", renamed_from="old-name")
    monkeypatch.setattr("sys.stdin", io.StringIO("old-name new-name\n"))
    assert gate.main(["--repo-root", str(tmp_path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_reads_pairs_from_file(tmp_path, capsys):
    _write_sidecar(tmp_path, "new-name", renamed_from="old-name")
    pairs_file = tmp_path / "pairs.txt"
    pairs_file.write_text("old-name new-name\n", encoding="utf-8")
    assert gate.main(["--pairs", str(pairs_file), "--repo-root", str(tmp_path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_and_reports_offenders(tmp_path, capsys):
    pairs_file = tmp_path / "pairs.txt"
    pairs_file.write_text("old-name new-name\n", encoding="utf-8")
    assert gate.main(["--pairs", str(pairs_file), "--repo-root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "new-name" in err
    assert "old-name" in err


def test_main_reports_error_for_missing_pairs_file(capsys):
    assert gate.main(["--pairs", "/no/such/file.txt"]) == 1
    assert "not found" in capsys.readouterr().err


def test_main_reports_error_for_malformed_pairs(tmp_path, capsys):
    pairs_file = tmp_path / "pairs.txt"
    pairs_file.write_text("only-one-token\n", encoding="utf-8")
    assert gate.main(["--pairs", str(pairs_file)]) == 1
    assert "line 1" in capsys.readouterr().err
