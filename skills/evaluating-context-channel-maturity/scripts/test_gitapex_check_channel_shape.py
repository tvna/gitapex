"""Tests for gitapex_check_channel_shape.py's deterministic shape checker.

Every fixture is synthesized in tmp_path -- synthetic-fixture-only, per
issue #1987's own Task 2 scope: proving the three tool-boundary checks
against this repository's real agents/*.md/.claude/agents/*.md files (and
the real hooks/gitapex_sync_opencode.py) is Task 4's own separate,
sequenced scope, once Task 1 (the OpenCode mapping fix) and Task 3 (the
description rewrites) are also merged. Every mapping-related test below
injects a synthetic `agent_specs` tuple directly into check_shape() instead
of touching the real hooks/gitapex_sync_opencode.py, so this suite never
depends on that file's real content or on repository layout beyond its own
tmp_path fixtures.
"""

from __future__ import annotations

import gitapex_check_channel_shape as ccs
import pytest


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _by_name(results):
    return {r.name: r for r in results}


# -- channel-file-readable / frontmatter-parsable (fail-closed) -------------


def test_missing_target_fails_closed_on_channel_file_readable(tmp_path):
    missing = tmp_path / "does-not-exist.md"
    results = ccs.check_shape(missing, agent_specs=None)
    assert len(results) == 1
    result = results[0]
    assert result.name == "channel-file-readable"
    assert result.passed is False


def test_unterminated_frontmatter_block_fails_closed(tmp_path):
    target = _write(
        tmp_path,
        "agents/broken.md",
        "---\nname: broken\ndescription: opens but never closes\n\nBody text.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["channel-file-readable"].passed is True
    assert results["frontmatter-parsable"].passed is False


def test_no_frontmatter_at_all_passes_frontmatter_parsable_not_applicable(tmp_path):
    target = _write(tmp_path, "AGENTS.md", "# AGENTS.md\n\nJust prose, no frontmatter block.\n")
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["frontmatter-parsable"].passed is True
    # description checks are not-applicable, not a defect, for a file with
    # no frontmatter at all -- also PASS.
    assert results["description-length"].passed is True
    assert results["yaml-plain-scalar-safety"].passed is True
    assert results["tool-boundary-declared"].passed is True


# -- description-length -------------------------------------------------


def test_description_at_cap_passes_length_check(tmp_path):
    desc = "x" * ccs.DESCRIPTION_MAX_CHARS
    target = _write(tmp_path, "agents/at-cap.md", f"---\nname: at-cap\ndescription: {desc}\n---\n\nBody.\n")
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["description-length"].passed is True


def test_description_over_cap_fails_length_check(tmp_path):
    desc = "x" * (ccs.DESCRIPTION_MAX_CHARS + 1)
    target = _write(tmp_path, "agents/over-cap.md", f"---\nname: over-cap\ndescription: {desc}\n---\n\nBody.\n")
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["description-length"].passed is False
    assert str(ccs.DESCRIPTION_MAX_CHARS + 1) in results["description-length"].evidence


# -- yaml-plain-scalar-safety: the four unsafe plain-scalar shapes --------


def test_plain_scalar_colon_space_fails_yaml_safety(tmp_path):
    target = _write(
        tmp_path,
        "agents/colon-space.md",
        "---\nname: colon-space\ndescription: Does X: and then Y\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is False
    assert "colon" in results["yaml-plain-scalar-safety"].evidence


def test_plain_scalar_trailing_colon_fails_yaml_safety(tmp_path):
    target = _write(
        tmp_path,
        "agents/trailing-colon.md",
        "---\nname: trailing-colon\ndescription: Ends with a colon:\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is False
    assert "trailing" in results["yaml-plain-scalar-safety"].evidence


def test_plain_scalar_leading_hash_fails_yaml_safety(tmp_path):
    target = _write(
        tmp_path,
        "agents/leading-hash.md",
        "---\nname: leading-hash\ndescription: #starts with hash\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is False
    assert "#" in results["yaml-plain-scalar-safety"].evidence


def test_plain_scalar_space_hash_fails_yaml_safety(tmp_path):
    target = _write(
        tmp_path,
        "agents/space-hash.md",
        "---\nname: space-hash\ndescription: Some text #looks-like-a-comment\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is False
    assert " #" in results["yaml-plain-scalar-safety"].evidence


def test_quoted_scalar_with_unsafe_substrings_passes_yaml_safety(tmp_path):
    target = _write(
        tmp_path,
        "agents/quoted.md",
        '---\nname: quoted\ndescription: "Does X: and Y #not-a-comment, trailing:"\n---\n\nBody.\n',
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is True
    assert "exempt" in results["yaml-plain-scalar-safety"].evidence


def test_block_scalar_with_unsafe_substrings_passes_yaml_safety(tmp_path):
    target = _write(
        tmp_path,
        "agents/block.md",
        "---\nname: block\ndescription: >\n  Does X: and Y #not-a-comment, trailing:\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is True
    assert "exempt" in results["yaml-plain-scalar-safety"].evidence


def test_block_scalar_description_still_counted_for_length(tmp_path):
    desc_line = "x" * (ccs.DESCRIPTION_MAX_CHARS + 5)
    target = _write(
        tmp_path,
        "agents/block-over-cap.md",
        f"---\nname: block-over-cap\ndescription: >\n  {desc_line}\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["description-length"].passed is False


# -- tool-boundary-declared -------------------------------------------------


def test_frontmatter_with_no_boundary_key_fails_tool_boundary_declared(tmp_path):
    target = _write(
        tmp_path,
        "agents/no-boundary.md",
        "---\nname: no-boundary\ndescription: Has frontmatter but no tool boundary key.\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["tool-boundary-declared"].passed is False


def test_disallowed_tools_present_passes_tool_boundary_declared(tmp_path):
    target = _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["tool-boundary-declared"].passed is True


def test_tools_present_passes_tool_boundary_declared(tmp_path):
    target = _write(
        tmp_path,
        "agents/allow-mode.md",
        "---\nname: allow-mode\ndescription: Declares an allow-list boundary.\ntools: Read, Grep, Glob\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["tool-boundary-declared"].passed is True


# -- tool-boundary-mapping-present -------------------------------------------


def test_missing_agent_specs_entry_fails_mapping_present(tmp_path):
    target = _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=(("some-other-file.md", {"bash": "deny"}),)))
    assert results["tool-boundary-mapping-present"].passed is False
    assert "not found" in results["tool-boundary-mapping-present"].evidence


def test_none_agent_specs_entry_fails_mapping_present(tmp_path):
    target = _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", None),)))
    assert results["tool-boundary-mapping-present"].passed is False
    assert "None" in results["tool-boundary-mapping-present"].evidence


def test_present_mapping_passes_mapping_present(tmp_path):
    target = _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", {"*mcp*": "deny"}),)))
    assert results["tool-boundary-mapping-present"].passed is True


def test_no_declared_boundary_reports_mapping_checks_not_applicable(tmp_path):
    target = _write(tmp_path, "AGENTS.md", "# AGENTS.md\n\nNo frontmatter at all.\n")
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["tool-boundary-mapping-present"].passed is True
    assert "not-applicable" in results["tool-boundary-mapping-present"].evidence
    assert results["tool-boundary-mapping-equivalent"].passed is True
    assert "not-applicable" in results["tool-boundary-mapping-equivalent"].evidence


# -- tool-boundary-mapping-equivalent ----------------------------------------


def test_mapping_unrelated_denial_fails_mapping_equivalent_deny_mode(tmp_path):
    target = _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    # Denies something unrelated to the declared mcp__github boundary.
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", {"edit": "deny"}),)))
    assert results["tool-boundary-mapping-equivalent"].passed is False
    assert "*mcp*" in results["tool-boundary-mapping-equivalent"].evidence


def test_mapping_empty_dict_fails_mapping_equivalent(tmp_path):
    target = _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", {}),)))
    assert results["tool-boundary-mapping-equivalent"].passed is False


def test_mapping_denies_wildcard_mcp_passes_mapping_equivalent_deny_mode(tmp_path):
    target = _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", {"*mcp*": "deny"}),)))
    assert results["tool-boundary-mapping-equivalent"].passed is True


def test_mapping_missing_one_key_fails_mapping_equivalent_allow_mode(tmp_path):
    target = _write(
        tmp_path,
        "agents/allow-mode.md",
        "---\nname: allow-mode\ndescription: Declares an allow-list boundary.\ntools: Read, Grep, Glob\n---\n\nBody.\n",
    )
    # Missing "bash" from an otherwise-complete denial set.
    mapping = {"edit": "deny", "task": "deny", "webfetch": "deny", "websearch": "deny", "*mcp*": "deny"}
    results = _by_name(ccs.check_shape(target, agent_specs=(("allow-mode.md", mapping),)))
    assert results["tool-boundary-mapping-equivalent"].passed is False
    assert "bash" in results["tool-boundary-mapping-equivalent"].evidence


def test_mapping_full_surface_denied_passes_mapping_equivalent_allow_mode(tmp_path):
    target = _write(
        tmp_path,
        "agents/allow-mode.md",
        "---\nname: allow-mode\ndescription: Declares an allow-list boundary.\ntools: Read, Grep, Glob\n---\n\nBody.\n",
    )
    mapping = {
        "edit": "deny",
        "bash": "deny",
        "task": "deny",
        "webfetch": "deny",
        "websearch": "deny",
        "*mcp*": "deny",
    }
    results = _by_name(ccs.check_shape(target, agent_specs=(("allow-mode.md", mapping),)))
    assert results["tool-boundary-mapping-equivalent"].passed is True


def test_agent_specs_load_error_fails_both_mapping_checks(tmp_path):
    target = _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["tool-boundary-mapping-present"].passed is False
    assert results["tool-boundary-mapping-equivalent"].passed is False


# -- main() -------------------------------------------------------------


def test_main_exits_zero_on_all_pass(tmp_path, capsys):
    target = _write(tmp_path, "AGENTS.md", "# AGENTS.md\n\nNo frontmatter at all.\n")
    code = ccs.main([str(target)])
    assert code == 0


def test_main_exits_one_on_a_failing_check(tmp_path, capsys):
    target = _write(
        tmp_path,
        "agents/no-boundary.md",
        "---\nname: no-boundary\ndescription: Has frontmatter but no tool boundary key.\n---\n\nBody.\n",
    )
    code = ccs.main([str(target)])
    assert code == 1


def test_main_exits_two_on_missing_target(tmp_path, capsys):
    missing = tmp_path / "nope.md"
    code = ccs.main([str(missing)])
    assert code == 2


def test_main_allowed_root_rejects_outside_target(tmp_path, capsys):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    target = _write(outside, "AGENTS.md", "# AGENTS.md\n\nNo frontmatter.\n")
    code = ccs.main(["--allowed-root", str(inside), str(target)])
    assert code == 2


# -- format_report / _validate_read_scope (direct unit coverage) ------------


def test_format_report_prints_check_names_and_pass_fail_counts():
    results = [
        ccs.CheckResult("some-check", True, "some rule", "ok"),
        ccs.CheckResult("other-check", False, "other rule", "bad"),
    ]
    report = ccs.format_report(results)
    assert "some-check" in report
    assert "PASS" in report
    assert "other-check" in report
    assert "FAIL" in report
    assert "1/2 checks passed" in report


def test_validate_read_scope_accepts_inside_target(tmp_path):
    target = _write(tmp_path, "AGENTS.md", "# AGENTS.md\n")
    # Must not raise.
    ccs._validate_read_scope(target, tmp_path)


def test_validate_read_scope_rejects_outside_target(tmp_path):
    inside = tmp_path / "inside"
    outside = tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()
    target = _write(outside, "AGENTS.md", "# AGENTS.md\n")
    with pytest.raises(ValueError, match="outside"):
        ccs._validate_read_scope(target, inside)


def test_validate_read_scope_rejects_symlink(tmp_path):
    real = _write(tmp_path, "real.md", "# real\n")
    link = tmp_path / "link.md"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="symlink"):
        ccs._validate_read_scope(link, tmp_path)
