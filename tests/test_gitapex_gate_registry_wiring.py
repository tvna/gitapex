"""Tests for the registry-introspection wiring scan
(.github/scripts/gitapex_gate_registry_wiring.py, issue #682 item 2).

Fixture-based tests exercise the detection logic against synthetic
scripts/workflows directories (tmp_path), including a reconstruction of
issue #682's defect J -- a registry row never passed on the command line by
its invoking workflow -- since J's real historical commit predates this
general pattern and issue #682's own Acceptance Criteria Map explicitly
allows "check out or reconstruct" in that case. The final tests are the
gate itself, against this repository's real .github/scripts and
.github/workflows directories.
"""

from __future__ import annotations

import ast
import pathlib

import gitapex_gate_registry_wiring as wiring
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _make_dirs(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    scripts_dir = tmp_path / "scripts"
    workflows_dir = tmp_path / "workflows"
    scripts_dir.mkdir()
    workflows_dir.mkdir()
    return scripts_dir, workflows_dir


# A minimal reconstruction of _PROCESS_DISCLOSURE_CHECKS's own shape: a
# namedtuple-style registry whose elements carry a cli_flag keyword.
_REGISTRY_SOURCE = """
import collections

_Check = collections.namedtuple("_Check", ["name", "cli_flag"])

_CHECKS = (
    _Check(name="alpha-check", cli_flag="--alpha-items"),
    _Check(name="beta-check", cli_flag="--beta-items"),
)
"""


def test_find_registry_rows_discovers_cli_flag_elements(tmp_path: pathlib.Path) -> None:
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")

    rows = wiring.find_registry_rows(scripts_dir)

    assert [row.cli_flag for row in rows] == ["--alpha-items", "--beta-items"]
    assert {row.registry_name for row in rows} == {"_CHECKS"}
    assert all(row.script == scripts_dir / "gate_example.py" for row in rows)


def test_find_registry_rows_ignores_non_registry_shapes(tmp_path: pathlib.Path) -> None:
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "not_a_registry.py").write_text(
        """
# A plain dict assignment is not a tuple/list literal.
CONFIG = {"cli_flag": "--ignored"}

# A tuple of non-Call elements.
NAMES = ("a", "b")

# A tuple of Call elements whose keyword is not named cli_flag.
OTHER = (dict(other_flag="--also-ignored"),)
""",
        encoding="utf-8",
    )

    assert wiring.find_registry_rows(scripts_dir) == []


def test_find_registry_rows_skips_non_literal_cli_flag(tmp_path: pathlib.Path) -> None:
    """A cli_flag built at runtime cannot be extracted by static analysis --
    a documented blind spot, not a crash."""
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "gate_dynamic.py").write_text(
        """
import collections

_Check = collections.namedtuple("_Check", ["cli_flag"])
_FLAG_NAME = "--computed"

_CHECKS = (
    _Check(cli_flag=_FLAG_NAME),
    _Check(cli_flag=f"--{'formatted'}"),
    _Check(**{"cli_flag": "--spread"}),
)
""",
        encoding="utf-8",
    )

    assert wiring.find_registry_rows(scripts_dir) == []


def test_find_registry_rows_discovers_annotated_assignment(tmp_path: pathlib.Path) -> None:
    """The annotated-assignment form (`_CHECKS: Final[tuple[...]] = (...)`)
    is already this repository's own style in
    gitapex_run_precommit_mypy.py's MYPY_GROUPS -- a registry written that
    way must not be invisible to this scan."""
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "gate_annotated.py").write_text(
        """
import collections
from typing import Final

_Check = collections.namedtuple("_Check", ["cli_flag"])

_CHECKS: Final[tuple] = (
    _Check(cli_flag="--alpha-items"),
)
""",
        encoding="utf-8",
    )

    rows = wiring.find_registry_rows(scripts_dir)
    assert [row.cli_flag for row in rows] == ["--alpha-items"]
    assert [row.registry_name for row in rows] == ["_CHECKS"]


def test_find_registry_rows_ignores_bare_annotation_with_no_value(tmp_path: pathlib.Path) -> None:
    """`x: SomeType` with no `= ...` has AnnAssign.value is None -- must not
    crash treating None as the tuple/list to scan."""
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "gate_bare_annotation.py").write_text("_CHECKS: tuple\n", encoding="utf-8")

    assert wiring.find_registry_rows(scripts_dir) == []


def test_find_registry_rows_reports_unknown_target_name(tmp_path: pathlib.Path) -> None:
    """An assignment target that is not a plain Name (a subscript, an
    attribute, a tuple-unpack) still has its elements scanned -- the
    registry_name just falls back to "<unknown>" instead of crashing."""
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "gate_subscript_target.py").write_text(
        """
import collections

_Check = collections.namedtuple("_Check", ["cli_flag"])

CONFIG = {}
CONFIG["checks"] = (_Check(cli_flag="--x"),)
""",
        encoding="utf-8",
    )

    rows = wiring.find_registry_rows(scripts_dir)
    assert [row.registry_name for row in rows] == ["<unknown>"]


def test_find_registry_rows_raises_on_unparseable_python(tmp_path: pathlib.Path) -> None:
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "broken.py").write_text("def (: this is not python", encoding="utf-8")

    with pytest.raises(wiring.RegistryReadError, match="cannot be parsed"):
        wiring.find_registry_rows(scripts_dir)


def test_find_registry_rows_raises_on_non_utf8_script(tmp_path: pathlib.Path) -> None:
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "binary.py").write_bytes(b"\xff\xfe\x00 not utf-8")

    with pytest.raises(wiring.RegistryReadError, match="cannot be read as UTF-8"):
        wiring.find_registry_rows(scripts_dir)


def test_find_registry_rows_raises_on_unreadable_script_path(tmp_path: pathlib.Path) -> None:
    """A *.py glob match that is actually a directory (IsADirectoryError,
    an OSError subclass) must fail closed, not crash uncaught."""
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "not_really_a_file.py").mkdir()

    with pytest.raises(wiring.RegistryReadError, match="cannot be read as UTF-8"):
        wiring.find_registry_rows(scripts_dir)


def test_find_registry_rows_raises_when_scripts_dir_does_not_exist(tmp_path: pathlib.Path) -> None:
    """A misconfigured or moved scripts directory must fail closed, not
    silently glob to an empty result (Path.glob on a missing directory
    returns [] rather than raising)."""
    with pytest.raises(wiring.RegistryReadError, match="not a directory"):
        wiring.find_registry_rows(tmp_path / "does-not-exist")


def test_find_invoking_workflows_raises_when_workflows_dir_does_not_exist(tmp_path: pathlib.Path) -> None:
    with pytest.raises(wiring.RegistryReadError, match="not a directory"):
        wiring.find_invoking_workflows("gate_example.py", tmp_path / "does-not-exist")


def test_contains_token_does_not_match_a_flag_that_is_only_a_prefix(tmp_path: pathlib.Path) -> None:
    """A workflow passing only the longer, unrelated `--alpha-items-extra`
    must not be read as having passed the registered `--alpha-items` --
    exactly defect J's own failure shape (argparse still registers the
    shorter flag with default="") reappearing inside this detector."""
    assert wiring._contains_token("--alpha-items-extra", "--alpha-items") is False
    assert wiring._contains_token('--alpha-items "$A"', "--alpha-items") is True


def test_contains_token_does_not_match_a_script_name_that_is_only_a_suffix(tmp_path: pathlib.Path) -> None:
    """A workflow invoking `sub_gate_example.py` must not be read as
    invoking `gate_example.py`."""
    assert wiring._contains_token("run: python sub_gate_example.py", "gate_example.py") is False
    assert wiring._contains_token("run: python .github/scripts/gate_example.py", "gate_example.py") is True


def test_find_unwired_rows_does_not_false_negative_on_a_flag_prefix_collision(tmp_path: pathlib.Path) -> None:
    """Reconstructs the false-negative an earlier, unbounded substring-match
    revision of this module had: a workflow passing only a longer flag that
    happens to start with the registered one must still be reported as
    unwired, not silently treated as satisfying it."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        # --alpha-items-extra is a different, unrelated flag that merely
        # starts with the registered --alpha-items text.
        'run: python .github/scripts/gate_example.py --alpha-items-extra "$A" --beta-items "$B"',
        encoding="utf-8",
    )

    findings = wiring.find_unwired_rows(scripts_dir, workflows_dir)

    assert len(findings) == 1
    assert "--alpha-items" in findings[0]
    assert "--beta-items" not in findings[0]


def test_find_invoking_workflows_matches_by_filename_substring(tmp_path: pathlib.Path) -> None:
    _, workflows_dir = _make_dirs(tmp_path)
    (workflows_dir / "a.yml").write_text(
        "run: python .github/scripts/gate_example.py --alpha-items x", encoding="utf-8"
    )
    (workflows_dir / "b.yaml").write_text("run: echo unrelated", encoding="utf-8")

    matches = wiring.find_invoking_workflows("gate_example.py", workflows_dir)

    assert [path.name for path in matches] == ["a.yml"]


def test_find_invoking_workflows_raises_on_non_utf8_workflow(tmp_path: pathlib.Path) -> None:
    _, workflows_dir = _make_dirs(tmp_path)
    (workflows_dir / "bad.yml").write_bytes(b"\xff\xfe not utf-8")

    with pytest.raises(wiring.RegistryReadError, match="cannot be read as UTF-8"):
        wiring.find_invoking_workflows("gate_example.py", workflows_dir)


def test_find_invoking_workflows_raises_on_unreadable_workflow_path(tmp_path: pathlib.Path) -> None:
    _, workflows_dir = _make_dirs(tmp_path)
    (workflows_dir / "not_really_a_file.yml").mkdir()

    with pytest.raises(wiring.RegistryReadError, match="cannot be read as UTF-8"):
        wiring.find_invoking_workflows("gate_example.py", workflows_dir)


def test_find_unwired_rows_is_clean_when_every_flag_is_passed(tmp_path: pathlib.Path) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        'run: python .github/scripts/gate_example.py --alpha-items "$A" --beta-items "$B"',
        encoding="utf-8",
    )

    assert wiring.find_unwired_rows(scripts_dir, workflows_dir) == []


def test_find_unwired_rows_flags_a_missing_flag_defect_j_reconstruction(tmp_path: pathlib.Path) -> None:
    """Reconstructs defect J's shape: a registry gains a row (or a
    workflow's argument list loses one) and the mismatch ships silently
    because every unit test that exercises the check's own logic supplies
    the item list directly, never through the workflow's command line."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        # beta-items dropped from the invocation -- the exact defect shape.
        'run: python .github/scripts/gate_example.py --alpha-items "$A"',
        encoding="utf-8",
    )

    findings = wiring.find_unwired_rows(scripts_dir, workflows_dir)

    assert len(findings) == 1
    assert "ci.yml" in findings[0]
    assert "gate_example.py" in findings[0]
    assert "--beta-items" in findings[0]
    assert "--alpha-items" not in findings[0]


def test_find_unwired_rows_ignores_a_script_with_no_invoking_workflow(tmp_path: pathlib.Path) -> None:
    """Documented blind spot: a registry whose script is invoked only from
    a PreToolUse hook shell script (never mentioned in any workflow file)
    is out of this scan's declared scope, not a finding."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "unrelated.yml").write_text("run: echo hello", encoding="utf-8")

    assert wiring.find_unwired_rows(scripts_dir, workflows_dir) == []


def test_find_unwired_rows_validates_workflows_dir_even_with_no_registries(tmp_path: pathlib.Path) -> None:
    """A missing/misconfigured workflows_dir must fail closed even when
    scripts_dir has no qualifying cli_flag registry at all -- an earlier
    revision short-circuited before ever touching workflows_dir in this
    case, silently returning [] (a false-clean result) instead of raising."""
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "not_a_registry.py").write_text("X = 1\n", encoding="utf-8")

    with pytest.raises(wiring.RegistryReadError, match="not a directory"):
        wiring.find_unwired_rows(scripts_dir, tmp_path / "does-not-exist")


def test_find_unwired_rows_is_deterministic_across_repeated_calls(tmp_path: pathlib.Path) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        'run: python .github/scripts/gate_example.py --alpha-items "$A"',
        encoding="utf-8",
    )

    first = wiring.find_unwired_rows(scripts_dir, workflows_dir)
    second = wiring.find_unwired_rows(scripts_dir, workflows_dir)

    assert first == second
    assert first == wiring.find_unwired_rows(scripts_dir, workflows_dir)


def test_main_reports_drift_and_exits_nonzero(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        'run: python .github/scripts/gate_example.py --alpha-items "$A"',
        encoding="utf-8",
    )
    monkeypatch.setattr(wiring, "SCRIPTS_DIR", scripts_dir)
    monkeypatch.setattr(wiring, "WORKFLOWS_DIR", workflows_dir)

    exit_code = wiring.main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "registry-wiring drift" in captured.out
    assert "--beta-items" in captured.out


def test_main_reports_a_read_error_and_exits_nonzero(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "broken.py").write_bytes(b"\xff\xfe not utf-8")
    monkeypatch.setattr(wiring, "SCRIPTS_DIR", scripts_dir)
    monkeypatch.setattr(wiring, "WORKFLOWS_DIR", workflows_dir)

    exit_code = wiring.main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "error:" in captured.err


def test_main_passes_cleanly_when_nothing_is_registered(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    monkeypatch.setattr(wiring, "SCRIPTS_DIR", scripts_dir)
    monkeypatch.setattr(wiring, "WORKFLOWS_DIR", workflows_dir)

    exit_code = wiring.main()

    assert exit_code == 0
    assert "OK:" in capsys.readouterr().out


# --- The converse direction (issue #797): orphaned workflow flags ---------


def test_iter_hardcoded_flags_finds_literal_add_argument_calls() -> None:
    """A script's own directly-authored `add_argument("--foo", ...)` calls
    are found by string-literal first argument; a call passing a variable
    (the registry-driven shape) is not -- see find_registry_rows for that
    half instead."""
    tree = ast.parse(
        """
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--body")
    parser.add_argument("--skill-md-changed", action="store_true")
    parser.add_argument(some_variable)
"""
    )

    assert wiring._iter_hardcoded_flags(tree) == {"--body", "--skill-md-changed"}


def test_iter_run_blocks_extracts_single_line_and_block_scalar_forms() -> None:
    text = (
        "steps:\n"
        "  - name: step one\n"
        "    run: echo one\n"
        "  - name: step two\n"
        "    run: |\n"
        "      echo two\n"
        "      echo three\n"
        "  - name: step three\n"
        "    run: echo four\n"
    )

    blocks = wiring._iter_run_blocks(text)

    assert blocks[0] == "echo one"
    assert "echo two" in blocks[1]
    assert "echo three" in blocks[1]
    assert blocks[2] == "echo four"


def test_find_orphaned_flags_flags_a_stale_flag_removed_from_the_registry(tmp_path: pathlib.Path) -> None:
    """Reconstructs issue #797's own motivating shape: a registry row is
    removed or renamed but the invoking workflow's command line was never
    updated to match."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(
        """
import collections

_Check = collections.namedtuple("_Check", ["name", "cli_flag"])

_CHECKS = (
    _Check(name="alpha-check", cli_flag="--alpha-items"),
)
""",
        encoding="utf-8",
    )
    (workflows_dir / "ci.yml").write_text(
        # --beta-items was removed from the registry; the workflow was
        # never updated to drop it.
        'run: python .github/scripts/gate_example.py --alpha-items "$A" --beta-items "$B"',
        encoding="utf-8",
    )

    findings = wiring.find_orphaned_flags(scripts_dir, workflows_dir)

    assert len(findings) == 1
    assert "ci.yml" in findings[0]
    assert "gate_example.py" in findings[0]
    assert "--beta-items" in findings[0]


def test_find_orphaned_flags_excludes_a_scripts_own_hardcoded_flags(tmp_path: pathlib.Path) -> None:
    """Reconstructs the false-positive risk PR #796's own body disclosed:
    a script's ordinary non-registry flags (--body, --skill-md-changed in
    the real gitapex_gate_skill_audit_disclosure.py) must never be flagged
    as orphaned."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(
        """
import argparse
import collections

_Check = collections.namedtuple("_Check", ["name", "cli_flag", "cli_dest"])

_CHECKS = (
    _Check(name="alpha-check", cli_flag="--alpha-items", cli_dest="alpha_items"),
)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--body", default="")
    parser.add_argument("--skill-md-changed", action="store_true")
    for check in _CHECKS:
        parser.add_argument(check.cli_flag, dest=check.cli_dest, default="")
    return parser.parse_args(argv)
""",
        encoding="utf-8",
    )
    (workflows_dir / "ci.yml").write_text(
        'run: python .github/scripts/gate_example.py --alpha-items "$A" --body "$B" --skill-md-changed',
        encoding="utf-8",
    )

    assert wiring.find_orphaned_flags(scripts_dir, workflows_dir) == []


def test_find_orphaned_flags_excludes_help(tmp_path: pathlib.Path) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text("run: python .github/scripts/gate_example.py --help", encoding="utf-8")

    assert wiring.find_orphaned_flags(scripts_dir, workflows_dir) == []


def test_find_orphaned_flags_scans_a_multiline_backslash_continued_run_block(tmp_path: pathlib.Path) -> None:
    """Real workflows split a long invocation across multiple `\\`-continued
    lines inside a `run: |` block (see .github/workflows/skill-audit-gate.yml) --
    the orphaned flag here is on its own continuation line, not the line
    that names the script."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        "steps:\n"
        "  - name: run gate\n"
        "    run: |\n"
        "      python .github/scripts/gate_example.py \\\n"
        '        --alpha-items "$A" \\\n'
        '        --beta-items "$B" \\\n'
        '        --gamma-items "$C"\n',
        encoding="utf-8",
    )

    findings = wiring.find_orphaned_flags(scripts_dir, workflows_dir)

    assert len(findings) == 1
    assert "--gamma-items" in findings[0]


def test_find_orphaned_flags_does_not_leak_flags_across_steps_for_different_scripts(
    tmp_path: pathlib.Path,
) -> None:
    """Proves the per-run-block scoping in _iter_run_blocks is load-bearing:
    an unscoped, whole-file scan would misattribute
    --totally-unrelated-flag (passed to a different script in a different
    step) to gate_example.py and flag it as orphaned."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        "steps:\n"
        "  - name: run gate\n"
        "    run: |\n"
        '      python .github/scripts/gate_example.py --alpha-items "$A" --beta-items "$B"\n'
        "  - name: run unrelated\n"
        "    run: |\n"
        '      python .github/scripts/other_script.py --totally-unrelated-flag "$X"\n',
        encoding="utf-8",
    )

    assert wiring.find_orphaned_flags(scripts_dir, workflows_dir) == []


def test_find_orphaned_flags_is_clean_when_every_passed_flag_is_known(tmp_path: pathlib.Path) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        'run: python .github/scripts/gate_example.py --alpha-items "$A" --beta-items "$B"',
        encoding="utf-8",
    )

    assert wiring.find_orphaned_flags(scripts_dir, workflows_dir) == []


def test_find_orphaned_flags_excludes_a_flag_belonging_to_uv_run_before_the_script(
    tmp_path: pathlib.Path,
) -> None:
    """Issue #1035: standardizing every `.github/scripts/*.py` invocation
    on `uv run` put a `--flag`-shaped token (`--frozen`) in the same run
    block as the script's filename, but belonging to `uv`, not the
    script -- preceding the filename rather than following it. This
    reconstructs the false positive that shape produced on `main`
    (`skill-audit-gate.yml` passing `--frozen` to
    `gitapex_gate_skill_audit_disclosure.py`) before `_text_from_first_token`
    scoped extraction to at-or-after the script's own filename."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        'run: uv run --frozen python3 .github/scripts/gate_example.py --alpha-items "$A" --beta-items "$B"',
        encoding="utf-8",
    )

    assert wiring.find_orphaned_flags(scripts_dir, workflows_dir) == []


def test_find_orphaned_flags_still_catches_a_real_stale_flag_after_uv_run(tmp_path: pathlib.Path) -> None:
    """The scoping fix above must not become a new blind spot: a genuinely
    orphaned flag placed *after* the script's filename, in a `uv run`-
    prefixed invocation, is still caught."""
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(_REGISTRY_SOURCE, encoding="utf-8")
    (workflows_dir / "ci.yml").write_text(
        'run: uv run --frozen python3 .github/scripts/gate_example.py --alpha-items "$A" --stale-flag "$B"',
        encoding="utf-8",
    )

    findings = wiring.find_orphaned_flags(scripts_dir, workflows_dir)

    assert len(findings) == 1
    assert "--stale-flag" in findings[0]


def test_find_orphaned_flags_returns_empty_when_nothing_is_registered(tmp_path: pathlib.Path) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "not_a_registry.py").write_text("X = 1\n", encoding="utf-8")

    assert wiring.find_orphaned_flags(scripts_dir, workflows_dir) == []


def test_find_orphaned_flags_validates_workflows_dir_even_with_no_registries(tmp_path: pathlib.Path) -> None:
    """Mirrors test_find_unwired_rows_validates_workflows_dir_even_with_no_registries:
    a missing/misconfigured workflows_dir must fail closed even when
    scripts_dir has no qualifying cli_flag registry at all -- an earlier
    revision of find_orphaned_flags short-circuited before ever touching
    workflows_dir in this case, silently returning [] (a false-clean
    result) instead of raising."""
    scripts_dir, _ = _make_dirs(tmp_path)
    (scripts_dir / "not_a_registry.py").write_text("X = 1\n", encoding="utf-8")

    with pytest.raises(wiring.RegistryReadError, match="not a directory"):
        wiring.find_orphaned_flags(scripts_dir, tmp_path / "does-not-exist")


def test_main_reports_orphaned_flag_drift_and_exits_nonzero(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scripts_dir, workflows_dir = _make_dirs(tmp_path)
    (scripts_dir / "gate_example.py").write_text(
        """
import collections

_Check = collections.namedtuple("_Check", ["cli_flag"])

_CHECKS = (
    _Check(cli_flag="--alpha-items"),
)
""",
        encoding="utf-8",
    )
    (workflows_dir / "ci.yml").write_text(
        'run: python .github/scripts/gate_example.py --alpha-items "$A" --stale-items "$B"',
        encoding="utf-8",
    )
    monkeypatch.setattr(wiring, "SCRIPTS_DIR", scripts_dir)
    monkeypatch.setattr(wiring, "WORKFLOWS_DIR", workflows_dir)

    exit_code = wiring.main()

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "registry-wiring drift" in captured.out
    assert "--stale-items" in captured.out


# --- The gate itself, against the real repository -------------------------


def test_real_repo_registry_rows_include_the_known_process_disclosure_checks() -> None:
    rows = wiring.find_registry_rows()
    flags = {row.cli_flag for row in rows}
    assert {
        "--security-relevant-skills",
        "--changed-design-docs",
        "--changed-checker-scripts",
        "--changed-gate-scripts",
    }.issubset(flags)


def test_real_repo_has_no_unwired_registry_rows() -> None:
    assert wiring.find_unwired_rows() == []


def test_real_repo_has_no_orphaned_workflow_flags() -> None:
    assert wiring.find_orphaned_flags() == []


def test_main_passes_cleanly_against_the_real_repo(capsys: pytest.CaptureFixture[str]) -> None:
    assert wiring.main() == 0
    assert "OK:" in capsys.readouterr().out
