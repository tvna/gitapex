"""Tests for check_axis_shape.py.

Fixtures are synthesized in-memory (no repository file is read) so the
test is self-contained and travels with the skill on vendoring. Wired
into the root pyproject.toml testpaths (issue #562: check_axis_shape.py
sat at 64% file coverage precisely because this file, despite existing,
was never collected by the repository's default pytest run) -- can
still be run directly with:
    python3 -m pytest skills/auditing-agent-product-scope/scripts/

Most tests pass an explicit, narrow `expected_labels` so a fixture
built for one specific behavior isn't also flagged for the unrelated
"expected axis missing" offense every other axis letter in the real
six-axis default would otherwise trigger.
"""

import check_axis_shape as cas

_COMPLETE_AXIS = """\
## Axis A: Plugin-distribution target

**Governs:** which agent products GitApex can be installed into.

**Current scope:** Claude Code.

**Owning doc:** repository-layout.md.

**Boundary:** expanding this axis is real engineering work.
"""

_COMPLETE_TWO_AXES = (
    _COMPLETE_AXIS
    + """
## Axis B: Enforcement-adapter target set

**Governs:** which runtimes a future enforcement adapter targets.

**Current scope:** six runtimes.

**Owning issue:** gitapex#307.

**Boundary:** this is a target list, not an installability claim.
"""
)

_ONLY_A = frozenset("A")
_A_AND_B = frozenset("AB")


def test_complete_single_axis_passes():
    assert cas.check_axis_shape(_COMPLETE_AXIS, expected_labels=_ONLY_A) == []


def test_complete_multiple_axes_pass():
    assert cas.check_axis_shape(_COMPLETE_TWO_AXES, expected_labels=_A_AND_B) == []


def test_missing_governs_flagged():
    text = _COMPLETE_AXIS.replace(
        "**Governs:** which agent products GitApex can be installed into.\n",
        "",
    )
    offenses = cas.check_axis_shape(text, expected_labels=_ONLY_A)
    assert len(offenses) == 1
    assert "governs" in offenses[0]


def test_empty_field_value_flagged():
    text = _COMPLETE_AXIS.replace(
        "**Boundary:** expanding this axis is real engineering work.",
        "**Boundary:**",
    )
    offenses = cas.check_axis_shape(text, expected_labels=_ONLY_A)
    assert len(offenses) == 1
    assert "boundary" in offenses[0]


def test_no_owning_prefix_field_flagged():
    text = _COMPLETE_AXIS.replace("**Owning doc:** repository-layout.md.\n", "")
    offenses = cas.check_axis_shape(text, expected_labels=_ONLY_A)
    assert len(offenses) == 1
    assert "owning" in offenses[0]


def test_owning_issues_plural_satisfies_owning_prefix():
    text = _COMPLETE_AXIS.replace(
        "**Owning doc:** repository-layout.md.",
        "**Owning issues:** gitapex#332 and gitapex#443.",
    )
    assert cas.check_axis_shape(text, expected_labels=_ONLY_A) == []


def test_no_axis_heading_reports_offense():
    offenses = cas.check_axis_shape("# Just a title\n\nNo axis here.\n")
    assert len(offenses) == 1
    assert "no '## Axis" in offenses[0]


def test_second_of_two_axes_missing_field_isolated():
    broken_second = _COMPLETE_TWO_AXES.replace("**Current scope:** six runtimes.\n", "")
    offenses = cas.check_axis_shape(broken_second, expected_labels=_A_AND_B)
    assert len(offenses) == 1
    assert offenses[0].startswith("Axis B")
    assert "current scope" in offenses[0]


def test_cli_pass(tmp_path, capsys):
    doc = tmp_path / "scope.md"
    doc.write_text(_COMPLETE_AXIS)
    exit_code = cas.main([str(doc), "--expected-labels", "A"])
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


def test_cli_undecodable_file_fails_closed(tmp_path, capsys):
    doc = tmp_path / "scope.md"
    doc.write_bytes(b"\xff\xfe bad")
    exit_code = cas.main([str(doc)])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_unexpected_axis_label_flagged_even_when_fields_complete():
    forged = _COMPLETE_AXIS.replace(
        "## Axis A: Plugin-distribution target",
        "## Axis G: Injected axis",
    )
    offenses = cas.check_axis_shape(forged, expected_labels=_ONLY_A)
    assert any(o.startswith("Axis G") and "not in the expected set" in o for o in offenses)


def test_unexpected_label_offense_does_not_also_report_missing_fields():
    forged_and_incomplete = _COMPLETE_AXIS.replace(
        "## Axis A: Plugin-distribution target",
        "## Axis G: Injected axis",
    ).replace("**Boundary:** expanding this axis is real engineering work.", "")
    offenses = cas.check_axis_shape(forged_and_incomplete, expected_labels=_ONLY_A)
    # The forged "G" section itself contributes exactly one offense (the
    # unexpected-label one, not also a missing-boundary one); a separate
    # "Axis A: expected but ... not found" offense is also correct here,
    # since renaming A to G really did remove the only A section.
    g_offenses = [o for o in offenses if o.startswith("Axis G")]
    assert len(g_offenses) == 1
    assert "not in the expected set" in g_offenses[0]


def test_expected_labels_override_allows_new_axis():
    widened = _COMPLETE_AXIS.replace(
        "## Axis A: Plugin-distribution target",
        "## Axis G: A deliberate new axis",
    )
    assert cas.check_axis_shape(widened, expected_labels=frozenset("G")) == []


def test_cli_expected_labels_flag(tmp_path, capsys):
    doc = tmp_path / "scope.md"
    doc.write_text(
        _COMPLETE_AXIS.replace(
            "## Axis A: Plugin-distribution target",
            "## Axis G: A deliberate new axis",
        )
    )
    assert cas.main([str(doc), "--expected-labels", "A"]) == 1
    assert "not in the expected set" in capsys.readouterr().err

    exit_code = cas.main([str(doc), "--expected-labels", "G"])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_missing_expected_axis_flagged():
    offenses = cas.check_axis_shape(_COMPLETE_AXIS, expected_labels=_A_AND_B)
    assert len(offenses) == 1
    assert offenses[0] == ("Axis B: expected but no '## Axis B:' heading found in the document")


def test_duplicate_axis_label_flagged():
    duplicated = _COMPLETE_AXIS + "\n" + _COMPLETE_AXIS
    offenses = cas.check_axis_shape(duplicated, expected_labels=_ONLY_A)
    assert len(offenses) == 1
    assert offenses[0] == "Axis A: appears 2 times, expected exactly once"


def test_duplicate_and_missing_axis_both_reported():
    duplicated_a_no_b = _COMPLETE_AXIS + "\n" + _COMPLETE_AXIS
    offenses = cas.check_axis_shape(duplicated_a_no_b, expected_labels=_A_AND_B)
    assert len(offenses) == 2
    assert any("Axis B: expected" in o for o in offenses)
    assert any("Axis A: appears 2 times" in o for o in offenses)


def test_final_axis_section_does_not_leak_into_later_non_axis_heading():
    # The final axis is missing its own Boundary field; a *different*
    # section further down the document happens to carry a line that
    # would satisfy the "boundary" label. A correct implementation must
    # not let that later, unrelated section's field count toward the
    # axis section it does not belong to.
    text = (
        _COMPLETE_AXIS.replace("**Boundary:** expanding this axis is real engineering work.\n", "")
        + "\n## Maintenance\n\n**Boundary:** unrelated content in a later section.\n"
    )
    offenses = cas.check_axis_shape(text, expected_labels=_ONLY_A)
    assert len(offenses) == 1
    assert offenses[0].startswith("Axis A")
    assert "boundary" in offenses[0]


def test_middle_axis_section_does_not_leak_into_next_axis_heading():
    # Sanity check that the any-heading boundary fix didn't regress the
    # original axis-to-axis boundary: axis A's own missing field must
    # not be satisfiable by axis B's fields either.
    broken_first = _COMPLETE_TWO_AXES.replace(
        "**Governs:** which agent products GitApex can be installed into.\n",
        "",
    )
    offenses = cas.check_axis_shape(broken_first, expected_labels=_A_AND_B)
    assert len(offenses) == 1
    assert offenses[0].startswith("Axis A")
    assert "governs" in offenses[0]
