"""Tests for evals/scripts/gitapex_check_skill_guardrail_presence.py.

`test_real_repository_guardrail_manifests_pass` is the actual CI gate: it
runs the checker against the real, committed
`skills/*/evals/guardrail-manifest.yaml` files with no fixture override, so
an edit that silently strips one of the guarded clauses fails the ordinary
`pytest` run this repository's `.github/workflows/test.yml` already runs
on every PR -- no separate workflow or gate registration needed.

Everything else here unit-tests one function or CLI path at a time against
a temp-directory fixture, including defeat tests: `anchor` fields that
would otherwise pass trivially (whitespace-only) or that must NOT match a
merely similar-looking file (a reworded, not removed, clause) -- proving
the check isn't foolable by either extreme.
"""

from __future__ import annotations

import pathlib

import gitapex_check_skill_guardrail_presence as guardrail_presence
import pytest
import yaml
from pydantic import ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_VALID_ENTRY: dict[str, str] = {
    "file": "SKILL.md",
    "anchor": "Never do the dangerous thing.",
    "description": "The core prohibition.",
    "source": "https://github.com/tvna/gitapex/issues/1",
}


def _write_manifest(path: pathlib.Path, entries: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"entries": entries}), encoding="utf-8")


# --- _normalize ---------------------------------------------------------


def test_normalize_collapses_whitespace_runs_and_trims() -> None:
    assert guardrail_presence._normalize("  a  b\nc\t\td  ") == "a b c d"


def test_normalize_whitespace_only_is_empty() -> None:
    assert guardrail_presence._normalize("   \n\t  ") == ""


# --- GuardrailEntry / GuardrailManifest validation ----------------------


def test_guardrail_entry_accepts_valid_data() -> None:
    entry = guardrail_presence.GuardrailEntry.model_validate(_VALID_ENTRY)
    assert entry.file == "SKILL.md"


def test_guardrail_entry_rejects_absolute_file_path() -> None:
    with pytest.raises(ValidationError):
        guardrail_presence.GuardrailEntry.model_validate({**_VALID_ENTRY, "file": "/etc/passwd"})


def test_guardrail_entry_rejects_parent_traversal_file_path() -> None:
    with pytest.raises(ValidationError):
        guardrail_presence.GuardrailEntry.model_validate({**_VALID_ENTRY, "file": "../../etc/passwd"})


def test_guardrail_entry_rejects_whitespace_only_anchor() -> None:
    """Defeat test: a whitespace-only anchor normalizes to "", which is a
    substring of every string, so it would otherwise pass against any file
    -- including one where the real guardrail was removed. Must be
    rejected at parse time, not silently accepted as an always-PASS entry.
    """
    with pytest.raises(ValidationError):
        guardrail_presence.GuardrailEntry.model_validate({**_VALID_ENTRY, "anchor": "   \n\t  "})


def test_guardrail_entry_rejects_bare_issue_number_source() -> None:
    with pytest.raises(ValidationError):
        guardrail_presence.GuardrailEntry.model_validate({**_VALID_ENTRY, "source": "#364"})


def test_guardrail_entry_rejects_empty_required_field() -> None:
    with pytest.raises(ValidationError):
        guardrail_presence.GuardrailEntry.model_validate({**_VALID_ENTRY, "description": ""})


def test_guardrail_entry_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        guardrail_presence.GuardrailEntry.model_validate({**_VALID_ENTRY, "unexpected": "nope"})


def test_guardrail_manifest_rejects_empty_entries_list() -> None:
    with pytest.raises(ValidationError):
        guardrail_presence.GuardrailManifest.model_validate({"entries": []})


# --- load_manifest -------------------------------------------------------


def test_load_manifest_valid(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "skills" / "fixture" / "evals" / "guardrail-manifest.yaml"
    _write_manifest(manifest_path, [_VALID_ENTRY])
    manifest = guardrail_presence.load_manifest(manifest_path)
    assert len(manifest.entries) == 1


def test_load_manifest_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(guardrail_presence.ManifestError, match="not a file"):
        guardrail_presence.load_manifest(tmp_path / "nope.yaml")


def test_load_manifest_not_utf8(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "guardrail-manifest.yaml"
    manifest_path.write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(guardrail_presence.ManifestError, match="UTF-8"):
        guardrail_presence.load_manifest(manifest_path)


def test_load_manifest_invalid_yaml(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "guardrail-manifest.yaml"
    manifest_path.write_text("entries: [unterminated", encoding="utf-8")
    with pytest.raises(guardrail_presence.ManifestError, match="invalid YAML"):
        guardrail_presence.load_manifest(manifest_path)


def test_load_manifest_top_level_not_mapping(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "guardrail-manifest.yaml"
    manifest_path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(guardrail_presence.ManifestError, match="must be a mapping"):
        guardrail_presence.load_manifest(manifest_path)


def test_load_manifest_schema_validation_error(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "guardrail-manifest.yaml"
    manifest_path.write_text(yaml.safe_dump({"entries": [{"file": "SKILL.md"}]}), encoding="utf-8")
    with pytest.raises(guardrail_presence.ManifestError, match="does not match the guardrail-manifest schema"):
        guardrail_presence.load_manifest(manifest_path)


# --- discover_manifests ---------------------------------------------------


def test_discover_manifests_finds_multiple(tmp_path: pathlib.Path) -> None:
    _write_manifest(tmp_path / "skills" / "a" / "evals" / "guardrail-manifest.yaml", [_VALID_ENTRY])
    _write_manifest(tmp_path / "skills" / "b" / "evals" / "guardrail-manifest.yaml", [_VALID_ENTRY])
    (tmp_path / "skills" / "c" / "evals").mkdir(parents=True)  # no manifest here
    found = guardrail_presence.discover_manifests(tmp_path)
    assert found == sorted(found)
    assert len(found) == 2


def test_discover_manifests_empty_when_none_present(tmp_path: pathlib.Path) -> None:
    assert guardrail_presence.discover_manifests(tmp_path) == []


# --- check_entry / check_manifest -----------------------------------------


def test_check_entry_pass_exact_match(tmp_path: pathlib.Path) -> None:
    (tmp_path / "SKILL.md").write_text("before. Never do the dangerous thing. after", encoding="utf-8")
    entry = guardrail_presence.GuardrailEntry.model_validate(_VALID_ENTRY)
    result = guardrail_presence.check_entry(tmp_path, entry)
    assert result.ok
    assert "anchor present" in result.reason


def test_check_entry_pass_tolerates_soft_rewrap(tmp_path: pathlib.Path) -> None:
    """A guardrail sentence that got reflowed onto new line boundaries
    (e.g. by a later editor's formatter) must not read as a regression --
    only a real wording change should."""
    (tmp_path / "SKILL.md").write_text("before.\nNever   do\nthe  dangerous\n  thing.\nafter", encoding="utf-8")
    entry = guardrail_presence.GuardrailEntry.model_validate(_VALID_ENTRY)
    result = guardrail_presence.check_entry(tmp_path, entry)
    assert result.ok


def test_check_entry_fail_missing_file(tmp_path: pathlib.Path) -> None:
    entry = guardrail_presence.GuardrailEntry.model_validate(_VALID_ENTRY)
    result = guardrail_presence.check_entry(tmp_path, entry)
    assert not result.ok
    assert "file not found" in result.reason


def test_check_entry_fail_anchor_removed(tmp_path: pathlib.Path) -> None:
    (tmp_path / "SKILL.md").write_text("this guardrail clause is gone now", encoding="utf-8")
    entry = guardrail_presence.GuardrailEntry.model_validate(_VALID_ENTRY)
    result = guardrail_presence.check_entry(tmp_path, entry)
    assert not result.ok
    assert "anchor not found" in result.reason


def test_check_entry_fail_anchor_reworded(tmp_path: pathlib.Path) -> None:
    """Defeat test: a paraphrase that keeps the same idea but changes the
    actual wording must still FAIL -- proving this is a literal (modulo
    whitespace) presence check, not a fuzzy/semantic one that a
    plausible-looking rewording could quietly satisfy."""
    (tmp_path / "SKILL.md").write_text(
        "You must never perform the dangerous thing under any circumstances.", encoding="utf-8"
    )
    entry = guardrail_presence.GuardrailEntry.model_validate(_VALID_ENTRY)
    result = guardrail_presence.check_entry(tmp_path, entry)
    assert not result.ok
    assert "anchor not found" in result.reason


def test_check_entry_fail_non_utf8_target_file(tmp_path: pathlib.Path) -> None:
    (tmp_path / "SKILL.md").write_bytes(b"\xff\xfe not utf-8")
    entry = guardrail_presence.GuardrailEntry.model_validate(_VALID_ENTRY)
    result = guardrail_presence.check_entry(tmp_path, entry)
    assert not result.ok
    assert "UTF-8" in result.reason


def test_check_manifest_returns_one_result_per_entry(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "skills" / "fixture" / "evals" / "guardrail-manifest.yaml"
    second_entry = {**_VALID_ENTRY, "anchor": "A second clause."}
    _write_manifest(manifest_path, [_VALID_ENTRY, second_entry])
    (tmp_path / "skills" / "fixture" / "SKILL.md").write_text(
        "Never do the dangerous thing. A second clause.", encoding="utf-8"
    )
    manifest = guardrail_presence.load_manifest(manifest_path)
    results = guardrail_presence.check_manifest(manifest_path, manifest)
    assert len(results) == 2
    assert all(result.ok for result in results)


# --- main() CLI ------------------------------------------------------------


def _build_repo(tmp_path: pathlib.Path, *, anchor_text: str = "Never do the dangerous thing.") -> pathlib.Path:
    manifest_path = tmp_path / "skills" / "fixture" / "evals" / "guardrail-manifest.yaml"
    _write_manifest(manifest_path, [_VALID_ENTRY])
    (tmp_path / "skills" / "fixture" / "SKILL.md").write_text(f"prefix. {anchor_text} suffix.", encoding="utf-8")
    return tmp_path


def test_main_pass_via_discovery(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo_root = _build_repo(tmp_path)
    exit_code = guardrail_presence.main(["--repo-root", str(repo_root)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "PASS: 1/1 guardrail anchor(s) present" in out


def test_main_fail_when_anchor_missing(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo_root = _build_repo(tmp_path, anchor_text="the guardrail was deleted")
    exit_code = guardrail_presence.main(["--repo-root", str(repo_root)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "FAIL:" in captured.out
    assert "1/1 guardrail anchor(s) missing" in captured.err


def test_main_fail_when_zero_manifests_discovered(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = guardrail_presence.main(["--repo-root", str(tmp_path)])
    assert exit_code == 1
    assert "no guardrail-manifest.yaml discovered" in capsys.readouterr().err


def test_main_explicit_manifest_flag(tmp_path: pathlib.Path) -> None:
    repo_root = _build_repo(tmp_path)
    manifest_path = repo_root / "skills" / "fixture" / "evals" / "guardrail-manifest.yaml"
    assert guardrail_presence.main(["--manifest", str(manifest_path)]) == 0


def test_main_explicit_skill_dir_flag(tmp_path: pathlib.Path) -> None:
    repo_root = _build_repo(tmp_path)
    skill_dir = repo_root / "skills" / "fixture"
    assert guardrail_presence.main(["--skill-dir", str(skill_dir)]) == 0


def test_main_manifest_error_exits_2(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest_path = tmp_path / "guardrail-manifest.yaml"
    manifest_path.write_text("not: [valid", encoding="utf-8")
    exit_code = guardrail_presence.main(["--manifest", str(manifest_path)])
    assert exit_code == 2
    assert "ERROR:" in capsys.readouterr().err


# --- Real repository gate --------------------------------------------------


def test_real_repository_guardrail_manifests_pass(capsys: pytest.CaptureFixture[str]) -> None:
    """The actual CI-enforced regression gate for issue #364: every
    committed skills/*/evals/guardrail-manifest.yaml anchor must still be
    present in the file it names, checked against this repository's real
    tree, not a fixture."""
    exit_code = guardrail_presence.main(["--repo-root", str(REPO_ROOT)])
    out = capsys.readouterr().out
    assert exit_code == 0, out
    assert "battle-testing-a-skill" in out
    assert "evaluating-skill-quality" in out
