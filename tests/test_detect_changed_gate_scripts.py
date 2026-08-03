"""Tests for the deterministic-gate scope detector
(.github/scripts/detect_changed_gate_scripts.py).

Issue #673 (refs #665 repair 1). This script answers "is this changed path
one of our gates", which decides whether `deterministic-gate-quality` fires
at all -- so a wrong answer here is a silent fail-open in the check built
to catch silent fail-opens. The defeat cases carry as much weight as the
happy path:

- the glob-only first version under-covered by 16 of 35 registered paths,
  so rule 2 (the registry) is pinned per surface class;
- deletions and renames were filtered out, so a `git rm` of a gate made the
  whole job report green -- pinned here in both directions;
- a malformed or missing registry must not degrade to rule 1 alone, which
  would silently shrink the scope back to the under-covering version.
"""

from __future__ import annotations

import json
import pathlib

import pytest

import detect_changed_gate_scripts as detect

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registered():
    return detect.registered_gate_paths(REPO_ROOT)


def _fake_registry(tmp_path, payload):
    (tmp_path / ".gitapex").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gitapex" / "ssot.json").write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


# --- rule 1: the naming convention ---


@pytest.mark.parametrize(
    "path",
    [
        ".github/scripts/gate_skill_audit_disclosure.py",
        ".github/scripts/scan_ssot_schema.py",
        ".github/scripts/gate_.py",
    ],
)
def test_naming_convention_paths_are_in_scope(path, registered):
    assert detect.is_gate_path(path, registered)


@pytest.mark.parametrize(
    "path",
    [
        "hooks/check-bash-safety.sh",
        "hooks/check_acm_present_or_waiver.py",
        "hooks/check-new-and-unregistered.sh",
    ],
)
def test_hook_naming_convention_paths_are_in_scope(path, registered):
    """Rule 1 covers hooks/ as well: 9 of the 25 registered gates live
    there and registration is a separate, unenforced step, so anchoring the
    convention to .github/scripts/ alone let a brand-new PreToolUse deny
    gate ship entirely outside this check."""
    assert detect.is_gate_path(path, registered)


@pytest.mark.parametrize(
    "path",
    [
        ".github/scripts/gate_helpers/support.py",  # must not cross '/'
        ".github/scripts/gates_foo.py",  # no underscore after the prefix word
        ".github/scripts/mygate_foo.py",  # not anchored at the start
        ".github/scripts/gate_foo.txt",  # not .py
        "skills/foo/scripts/gate_foo.py",  # right name, wrong directory
        "tests/test_gate_skill_audit_disclosure.py",
        "hooks/checkers/deep.sh",  # must not cross '/'
        "hooks/README.md",
        "hooks/checkpoint.sh",  # no separator after "check"
    ],
)
def test_near_miss_paths_are_out_of_scope_under_the_convention(path, registered):
    # Each of these is out of scope under rule 1; none is registered either.
    assert path not in registered
    assert not detect.is_gate_path(path, registered)


def test_convention_matches_a_brand_new_unregistered_gate(tmp_path):
    """Rule 1's whole reason to exist: a gate is in scope in the window
    before anyone registers it."""
    root = _fake_registry(tmp_path, {"gates": [{"script": "hooks/other.sh"}]})
    reg = detect.registered_gate_paths(root)
    assert ".github/scripts/gate_brand_new.py" not in reg
    assert detect.is_gate_path(".github/scripts/gate_brand_new.py", reg)


# --- rule 2: the registry ---


@pytest.mark.parametrize(
    "path",
    [
        # The sharpest case: this script decides whether the sibling
        # adversarial-coverage-mapping check fires at all, and matches no glob.
        ".github/scripts/skill_security_relevance.py",
        ".github/scripts/skill_description_diff.py",
        ".github/scripts/extract_diff_added_lines.py",
        ".github/scripts/detect_touched_eval_skills.py",
        ".github/workflows/lint.yml",
        ".github/workflows/toolchain-nix.yml",
        ".github/workflows/waza-eval-gate.yml",
    ],
)
def test_registered_gate_paths_outside_the_convention_are_in_scope(path, registered):
    """These are the real under-coverage the glob-only version had."""
    assert not detect._CONVENTION_RE.fullmatch(path), "fixture no longer tests rule 2"
    assert detect.is_gate_path(path, registered)


def test_registry_covers_every_shape_of_the_script_field(tmp_path):
    """`script` is a bare string in some entries and a list in others."""
    root = _fake_registry(
        tmp_path,
        {"gates": [{"script": "hooks/a.sh"}, {"script": ["hooks/b.sh", "hooks/c.py"]}, {}]},
    )
    assert detect.registered_gate_paths(root) == {"hooks/a.sh", "hooks/b.sh", "hooks/c.py"}


# --- rule 3: the registry file itself ---


def test_the_registry_file_itself_is_in_scope(registered):
    """Editing it changes every other gate's scope, including this check's."""
    assert detect.is_gate_path(".gitapex/ssot.json", registered)


# --- deletions and renames stay in scope ---


def test_a_deleted_gate_is_selected(registered):
    """The live-reproduced defect: filtering D made `git rm` of a gate
    report a green required check."""
    assert detect.select("D\t.github/scripts/gate_foo.py\n", registered) == [
        ".github/scripts/gate_foo.py"
    ]


def test_a_byte_identical_rename_selects_both_sides(registered):
    """The new path is what exists now; the old path is what the invoking
    workflow step may still point at."""
    assert detect.select(
        "R100\t.github/scripts/gate_old.py\t.github/scripts/gate_new.py\n", registered
    ) == [".github/scripts/gate_new.py", ".github/scripts/gate_old.py"]


def test_a_deleted_registered_hook_gate_is_selected(registered):
    assert detect.select("D\thooks/check-bash-safety.sh\n", registered) == [
        "hooks/check-bash-safety.sh"
    ]


# --- selection over realistic --name-status input ---


def test_select_picks_only_gate_paths_from_a_mixed_diff(registered):
    text = (
        "M\t.github/scripts/gate_skill_audit_disclosure.py\n"
        "A\t.github/scripts/scan_new_thing.py\n"
        "M\t.github/scripts/skill_security_relevance.py\n"
        "A\ttests/test_gate_skill_audit_disclosure.py\n"
        "M\tREADME.md\n"
        "A\t.github/scripts/gate_helpers/support.py\n"
    )
    assert detect.select(text, registered) == [
        ".github/scripts/gate_skill_audit_disclosure.py",
        ".github/scripts/scan_new_thing.py",
        ".github/scripts/skill_security_relevance.py",
    ]


def test_select_is_empty_for_a_diff_touching_no_gate(registered):
    """An empty selection is legitimate, not an error -- the common case."""
    assert detect.select("M\tREADME.md\nA\tdocs/x.md\n", registered) == []


def test_select_tolerates_blank_lines_and_crlf(registered):
    text = "M\t.github/scripts/gate_a.py\r\n\r\nA\t.github/scripts/scan_b.py\r\n"
    assert detect.select(text, registered) == [
        ".github/scripts/gate_a.py",
        ".github/scripts/scan_b.py",
    ]


def test_select_deduplicates(registered):
    text = "M\t.github/scripts/gate_a.py\nM\t.github/scripts/gate_a.py\n"
    assert detect.select(text, registered) == [".github/scripts/gate_a.py"]


# --- fail closed ---


def test_a_status_line_with_no_path_is_an_error(registered):
    with pytest.raises(detect.ScopeError, match="unparseable"):
        detect.select("M\n", registered)


def test_a_comma_bearing_gate_path_is_an_error(registered):
    """It would split into two bogus entries in the comma-joined sink."""
    with pytest.raises(detect.ScopeError, match="comma"):
        detect.select("A\t.github/scripts/gate_a,b.py\n", registered)


def test_a_missing_registry_is_an_error_not_a_fallback(tmp_path):
    with pytest.raises(detect.ScopeError, match="cannot be read"):
        detect.registered_gate_paths(tmp_path)


def test_a_malformed_registry_is_an_error_not_a_fallback(tmp_path):
    (tmp_path / ".gitapex").mkdir()
    (tmp_path / ".gitapex" / "ssot.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(detect.ScopeError, match="not valid JSON"):
        detect.registered_gate_paths(tmp_path)


def test_a_registry_with_no_gates_is_an_error(tmp_path):
    root = _fake_registry(tmp_path, {"gates": []})
    with pytest.raises(detect.ScopeError, match="no usable"):
        detect.registered_gate_paths(root)


def test_a_non_string_script_entry_is_an_error(tmp_path):
    root = _fake_registry(tmp_path, {"gates": [{"script": [123]}]})
    with pytest.raises(detect.ScopeError, match="unsupported"):
        detect.registered_gate_paths(root)


def test_a_non_list_non_string_script_value_is_an_error(tmp_path):
    root = _fake_registry(tmp_path, {"gates": [{"script": {"a": 1}}]})
    with pytest.raises(detect.ScopeError, match="unsupported"):
        detect.registered_gate_paths(root)


# --- CLI ---


def test_main_writes_only_the_payload_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin",
        __import__("io").StringIO("M\t.github/scripts/gate_a.py\nM\tREADME.md\n"),
    )
    assert detect.main(["--repo-root", str(REPO_ROOT)]) == 0
    captured = capsys.readouterr()
    # Dimension 14: the machine-read channel carries the payload alone.
    assert captured.out == ".github/scripts/gate_a.py\n"
    assert "requiring disclosure" in captured.err


def test_main_prints_an_empty_line_when_nothing_matched(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("M\tREADME.md\n"))
    assert detect.main(["--repo-root", str(REPO_ROOT)]) == 0
    assert capsys.readouterr().out == "\n"


def test_main_exits_2_on_an_untrusted_registry(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(""))
    assert detect.main(["--repo-root", str(tmp_path)]) == 2
    assert "cannot be read" in capsys.readouterr().err


def test_main_exits_2_on_a_comma_bearing_path(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", __import__("io").StringIO("A\t.github/scripts/gate_a,b.py\n")
    )
    assert detect.main(["--repo-root", str(REPO_ROOT)]) == 2
    assert "comma" in capsys.readouterr().err


# --- the real repository ---


def test_this_repository_registers_more_gates_than_the_convention_matches(registered):
    """Anchors the finding that motivated rule 2: if this ever drops to
    zero, the registry rule has stopped adding coverage and someone should
    know before deleting it."""
    outside = {p for p in registered if not detect._CONVENTION_RE.fullmatch(p)}
    assert len(outside) >= 8, sorted(outside)


# --- rule 4 and the gate-wiring files (review findings) ---


@pytest.mark.parametrize(
    "path", [".gitapex/ssot.json", "hooks/hooks.json", ".github/workflows/skill-audit-gate.yml"]
)
def test_files_that_decide_whether_gates_run_are_in_scope(path, registered):
    """Each of these can disable a gate without touching its script:
    the registry defines rule 2's answer, hooks.json wires the PreToolUse
    plane, and skill-audit-gate.yml implements this very check. All three
    reported green for being gutted before the review caught it."""
    assert detect.is_gate_path(path, registered)


# --- trailing-newline anchoring ---


def test_a_trailing_newline_does_not_make_a_path_a_gate(registered):
    """`$` also matches before a trailing newline and `[^/]` matches `\n`,
    so `.match` would accept this and feed a newline-bearing path toward a
    single-line output sink. detect_touched_eval_skills.py documents the
    same pitfall; fullmatch is why this is False."""
    assert not detect.is_gate_path(".github/scripts/gate_a.py\n", registered)


# --- registry shapes that parse but are unusable ---


@pytest.mark.parametrize("payload", ["[]", '"x"', "1", "null", "true"])
def test_a_valid_but_non_object_registry_is_a_scope_error_not_a_traceback(tmp_path, payload):
    """These parse fine, so the JSONDecodeError branch never fires; without
    an explicit shape guard `data.get` raised an uncaught AttributeError and
    the CLI exited 1 with a raw traceback instead of the documented exit 2.
    That is literally PR #651's "uncaught traceback" defect class occurring
    inside the check built to catch it."""
    (tmp_path / ".gitapex").mkdir()
    (tmp_path / ".gitapex" / "ssot.json").write_text(payload, encoding="utf-8")
    with pytest.raises(detect.ScopeError, match="must be a JSON object"):
        detect.registered_gate_paths(tmp_path)


@pytest.mark.parametrize("payload", ["[]", '"x"', "1"])
def test_the_cli_exits_2_on_a_non_object_registry(monkeypatch, capsys, tmp_path, payload):
    (tmp_path / ".gitapex").mkdir()
    (tmp_path / ".gitapex" / "ssot.json").write_text(payload, encoding="utf-8")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(""))
    assert detect.main(["--repo-root", str(tmp_path)]) == 2
    assert "must be a JSON object" in capsys.readouterr().err
