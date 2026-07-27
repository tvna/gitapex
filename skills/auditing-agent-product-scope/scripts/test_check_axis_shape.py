"""Tests for check_axis_shape.py.

Fixtures are synthesized in-memory (no repository file is read) so the
test is self-contained and travels with the skill on vendoring. Not
wired into the root pyproject.toml testpaths -- this skill's checklist
item is meant to stand alone (same approach as
git-hosting-surface-audit/scripts/test_scan_unpinned_actions.py); run
directly with:
    python3 -m pytest skills/auditing-agent-product-scope/scripts/
"""

import check_axis_shape as cas

_COMPLETE_AXIS = """\
## Axis A: Plugin-distribution target

**Governs:** which agent products GitApex can be installed into.

**Current scope:** Claude Code.

**Owning doc:** repository-layout.md.

**Boundary:** expanding this axis is real engineering work.
"""

_COMPLETE_TWO_AXES = _COMPLETE_AXIS + """
## Axis B: Enforcement-adapter target set

**Governs:** which runtimes a future enforcement adapter targets.

**Current scope:** six runtimes.

**Owning issue:** gitapex#307.

**Boundary:** this is a target list, not an installability claim.
"""


def test_complete_single_axis_passes():
    assert cas.check_axis_shape(_COMPLETE_AXIS) == []


def test_complete_multiple_axes_pass():
    assert cas.check_axis_shape(_COMPLETE_TWO_AXES) == []


def test_missing_governs_flagged():
    text = _COMPLETE_AXIS.replace(
        "**Governs:** which agent products GitApex can be installed into.\n",
        "",
    )
    offenses = cas.check_axis_shape(text)
    assert len(offenses) == 1
    assert "governs" in offenses[0]


def test_empty_field_value_flagged():
    text = _COMPLETE_AXIS.replace(
        "**Boundary:** expanding this axis is real engineering work.",
        "**Boundary:**",
    )
    offenses = cas.check_axis_shape(text)
    assert len(offenses) == 1
    assert "boundary" in offenses[0]


def test_no_owning_prefix_field_flagged():
    text = _COMPLETE_AXIS.replace(
        "**Owning doc:** repository-layout.md.\n", ""
    )
    offenses = cas.check_axis_shape(text)
    assert len(offenses) == 1
    assert "owning" in offenses[0]


def test_owning_issues_plural_satisfies_owning_prefix():
    text = _COMPLETE_AXIS.replace(
        "**Owning doc:** repository-layout.md.",
        "**Owning issues:** gitapex#332 and gitapex#443.",
    )
    assert cas.check_axis_shape(text) == []


def test_no_axis_heading_reports_offense():
    offenses = cas.check_axis_shape("# Just a title\n\nNo axis here.\n")
    assert len(offenses) == 1
    assert "no '## Axis" in offenses[0]


def test_second_of_two_axes_missing_field_isolated():
    broken_second = _COMPLETE_TWO_AXES.replace(
        "**Current scope:** six runtimes.\n", ""
    )
    offenses = cas.check_axis_shape(broken_second)
    assert len(offenses) == 1
    assert offenses[0].startswith("Axis B")
    assert "current scope" in offenses[0]


def test_cli_pass(tmp_path, capsys):
    doc = tmp_path / "scope.md"
    doc.write_text(_COMPLETE_AXIS)
    exit_code = cas.main([str(doc)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_cli_fail(tmp_path, capsys):
    doc = tmp_path / "scope.md"
    doc.write_text("# No axes here\n")
    exit_code = cas.main([str(doc)])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_cli_missing_file(capsys):
    exit_code = cas.main(["/nonexistent/path/scope.md"])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err
