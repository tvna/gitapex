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


def _deny_mode_target(tmp_path):
    """`agents/deny-mode.md`, declaring `disallowedTools: mcp__github` --
    the one fixture every deny-mode tool-boundary/mapping test below
    shares verbatim."""
    return _write(
        tmp_path,
        "agents/deny-mode.md",
        "---\nname: deny-mode\ndescription: Declares a deny-list boundary.\ndisallowedTools: mcp__github\n---\n\nBody.\n",
    )


def _allow_mode_target(tmp_path):
    """`agents/allow-mode.md`, declaring `tools: Read, Grep, Glob` -- the
    one fixture every allow-mode tool-boundary/mapping test below shares
    verbatim."""
    return _write(
        tmp_path,
        "agents/allow-mode.md",
        "---\nname: allow-mode\ndescription: Declares an allow-list boundary.\ntools: Read, Grep, Glob\n---\n\nBody.\n",
    )


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


def test_double_quoted_scalar_with_escaped_backslash_then_real_close_passes_yaml_safety(tmp_path):
    """A double-quoted scalar ending in an escaped backslash (`\\\\`, a
    literal single backslash) followed by a real closing quote IS
    genuinely closed -- confirmed against PyYAML. The escape-awareness fix
    for the sibling defeat test below must not start rejecting this
    still-valid, still-safe shape."""
    target = _write(
        tmp_path,
        "agents/escaped-backslash-then-closed.md",
        '---\nname: t\ndescription: "a path C:\\\\\\\\"\n---\n\nBody.\n',
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is True
    assert "exempt" in results["yaml-plain-scalar-safety"].evidence


def test_single_quoted_scalar_with_doubled_quote_then_real_close_passes_yaml_safety(tmp_path):
    """A single-quoted scalar containing a doubled `''` (one embedded
    literal quote) followed by a real closing quote IS genuinely closed --
    confirmed against PyYAML. The escape-awareness fix for the sibling
    defeat test below must not start rejecting this still-valid,
    still-safe shape."""
    target = _write(
        tmp_path,
        "agents/doubled-quote-then-closed.md",
        "---\nname: t\ndescription: 'it''s fine'\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is True
    assert "exempt" in results["yaml-plain-scalar-safety"].evidence


def test_unclosed_leading_quote_is_not_exempt_and_still_fails_yaml_safety(tmp_path):
    """Defeat test (issue #1987's own defeat-test-disclosure obligation):
    a description that OPENS with a quote character but never closes it is
    not a validly-quoted YAML scalar -- classifying it as "quoted" (exempt
    from the safety scan below) would let a crafted value smuggle a
    colon-space/trailing-colon pattern straight past this checker, exactly
    the truncation-hazard class issue #1982 already recorded once for a
    different generator. Confirmed to genuinely defeat a naive
    `rest[:1] in ("'", '"')`-only classification before the fix landed."""
    target = _write(
        tmp_path,
        "agents/unclosed-quote.md",
        '---\nname: unclosed-quote\ndescription: "unsafe value with a colon: and a trailing colon:\n---\n\nBody.\n',
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is False
    assert "colon" in results["yaml-plain-scalar-safety"].evidence


def test_escaped_trailing_double_quote_is_not_exempt_and_still_fails_yaml_safety(tmp_path):
    """Defeat test (issue #1987's own Step 8 adversarial review): a
    double-quoted description whose trailing quote is backslash-escaped
    (`\\"`) is NOT a real closing quote in YAML -- a real parser (confirmed
    against PyYAML) raises ScannerError "found unexpected end of stream"
    on this exact shape, it does not parse it as a safely-quoted scalar.
    Classifying it as "quoted" (exempt from the safety scan below) would
    both hide a colon-space pattern from the scan AND wrongly claim
    "already safe under a real YAML parser" for a value a real parser
    cannot parse at all -- confirmed to genuinely defeat the
    `rest[0] == rest[-1]`-only classification (the check this test's own
    fix replaced) before that fix landed."""
    target = _write(
        tmp_path,
        "agents/escaped-quote.md",
        '---\nname: escaped-quote\ndescription: "unsafe: value\\"\n---\n\nBody.\n',
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is False
    assert "colon" in results["yaml-plain-scalar-safety"].evidence


def test_doubled_trailing_single_quote_is_not_exempt_and_still_fails_yaml_safety(tmp_path):
    """Defeat test (issue #1987's own Step 8 adversarial review): a
    single-quoted description ending in a doubled `''` (YAML's own
    literal-quote escape) with no further closing quote is NOT a real
    closing quote either -- a real parser (confirmed against PyYAML)
    raises the same ScannerError as the double-quote case above. The
    naive `rest[0] == rest[-1]` classification this test's own fix
    replaced would misread the trailing `''` as a plain closing quote and
    exempt this value from the safety scan below."""
    target = _write(
        tmp_path,
        "agents/doubled-quote.md",
        "---\nname: doubled-quote\ndescription: 'unsafe: value''\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["yaml-plain-scalar-safety"].passed is False
    assert "colon" in results["yaml-plain-scalar-safety"].evidence


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
    target = _deny_mode_target(tmp_path)
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["tool-boundary-declared"].passed is True


def test_tools_present_passes_tool_boundary_declared(tmp_path):
    target = _allow_mode_target(tmp_path)
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["tool-boundary-declared"].passed is True


# -- tool-boundary-mapping-present -------------------------------------------


def test_missing_agent_specs_entry_fails_mapping_present(tmp_path):
    target = _deny_mode_target(tmp_path)
    results = _by_name(ccs.check_shape(target, agent_specs=(("some-other-file.md", {"bash": "deny"}),)))
    assert results["tool-boundary-mapping-present"].passed is False
    assert "not found" in results["tool-boundary-mapping-present"].evidence


def test_none_agent_specs_entry_fails_mapping_present(tmp_path):
    target = _deny_mode_target(tmp_path)
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", None),)))
    assert results["tool-boundary-mapping-present"].passed is False
    assert "None" in results["tool-boundary-mapping-present"].evidence


def test_present_mapping_passes_mapping_present(tmp_path):
    target = _deny_mode_target(tmp_path)
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
    target = _deny_mode_target(tmp_path)
    # Denies something unrelated to the declared mcp__github boundary.
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", {"edit": "deny"}),)))
    assert results["tool-boundary-mapping-equivalent"].passed is False
    assert "*mcp*" in results["tool-boundary-mapping-equivalent"].evidence


def test_mapping_empty_dict_fails_mapping_equivalent(tmp_path):
    target = _deny_mode_target(tmp_path)
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", {}),)))
    assert results["tool-boundary-mapping-equivalent"].passed is False


def test_mapping_denies_wildcard_mcp_passes_mapping_equivalent_deny_mode(tmp_path):
    target = _deny_mode_target(tmp_path)
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", {"*mcp*": "deny"}),)))
    assert results["tool-boundary-mapping-equivalent"].passed is True


def test_mapping_key_matches_but_value_is_allow_fails_mapping_equivalent_deny_mode(tmp_path):
    target = _deny_mode_target(tmp_path)
    # Same key pattern as the wildcard-mcp denial above, but declares
    # "allow" instead of "deny" -- a mapping entry whose KEY matches the
    # required OpenCode surface but whose VALUE is not itself a denial
    # must not be treated as equivalent to denying it. Distinct from
    # test_mapping_unrelated_denial_fails_mapping_equivalent_deny_mode
    # above, which covers a "deny"-valued entry whose key does not match.
    results = _by_name(ccs.check_shape(target, agent_specs=(("deny-mode.md", {"*mcp*": "allow"}),)))
    assert results["tool-boundary-mapping-equivalent"].passed is False
    assert "*mcp*" in results["tool-boundary-mapping-equivalent"].evidence


def test_mapping_missing_one_key_fails_mapping_equivalent_allow_mode(tmp_path):
    target = _allow_mode_target(tmp_path)
    # Missing "bash" from an otherwise-complete denial set.
    mapping = {"edit": "deny", "task": "deny", "webfetch": "deny", "websearch": "deny", "*mcp*": "deny"}
    results = _by_name(ccs.check_shape(target, agent_specs=(("allow-mode.md", mapping),)))
    assert results["tool-boundary-mapping-equivalent"].passed is False
    assert "bash" in results["tool-boundary-mapping-equivalent"].evidence


def test_mapping_full_surface_denied_passes_mapping_equivalent_allow_mode(tmp_path):
    target = _allow_mode_target(tmp_path)
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
    target = _deny_mode_target(tmp_path)
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["tool-boundary-mapping-present"].passed is False
    assert results["tool-boundary-mapping-equivalent"].passed is False


def test_untranslatable_deny_token_fails_closed_on_mapping_equivalent(tmp_path):
    """Defeat test: a `disallowedTools:` token this module's own small,
    deliberately narrow Claude-tool-name -> OpenCode-permission-key table
    (_CLAUDE_TOOL_TO_OPENCODE_KEY) has no translation for must fail
    mapping-equivalent closed, never silently pass it as though the
    (unverifiable) boundary were satisfied."""
    target = _write(
        tmp_path,
        "agents/unknown-token.md",
        "---\nname: unknown-token\ndescription: Declares an untranslatable deny token.\n"
        "disallowedTools: some_unrecognized_tool_xyz\n---\n\nBody.\n",
    )
    # A generous mapping that denies everything this module knows how to
    # translate -- if the untranslatable token were silently ignored
    # rather than failing closed, this mapping would wrongly pass.
    mapping = {"edit": "deny", "bash": "deny", "task": "deny", "webfetch": "deny", "websearch": "deny", "*mcp*": "deny"}
    results = _by_name(ccs.check_shape(target, agent_specs=(("unknown-token.md", mapping),)))
    assert results["tool-boundary-mapping-present"].passed is True
    assert results["tool-boundary-mapping-equivalent"].passed is False
    assert "no known OpenCode-permission-key translation" in results["tool-boundary-mapping-equivalent"].evidence


def test_empty_disallowed_tools_value_declares_a_vacuous_boundary(tmp_path):
    """Edge case surfaced while defeat-testing: `disallowedTools:` with
    nothing after the colon is syntactically present (tool-boundary-declared
    still PASSes) but tokenizes to zero tokens, so mapping-equivalent has
    nothing to require and PASSes vacuously even with an empty mapping.
    This is the checker's own documented "declared key present" contract
    (frontmatter-shape only, per tool-boundary-declared's own rule text),
    not a silent bypass of a real boundary -- a human/AGENTS.md-authoring
    convention question, not this checker's own defect, and is captured
    here as a pinned, disclosed behavior rather than left unobserved."""
    target = _write(
        tmp_path,
        "agents/empty-boundary.md",
        "---\nname: empty-boundary\ndescription: Declares an empty deny-list value.\ndisallowedTools:\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=(("empty-boundary.md", {}),)))
    assert results["tool-boundary-declared"].passed is True
    assert results["tool-boundary-mapping-equivalent"].passed is True
    assert "all required keys denied" in results["tool-boundary-mapping-equivalent"].evidence


# -- frontmatter body parsing edge cases (blank/comment lines, non-key lines) -


def test_frontmatter_body_tolerates_blank_and_comment_lines_around_fields(tmp_path):
    target = _write(
        tmp_path,
        "agents/spaced-out.md",
        "---\n"
        "name: spaced-out\n"
        "\n"
        "# a full-line comment between fields\n"
        "not a key-shaped line at all\n"
        "description: Still parses the real fields correctly.\n"
        "---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["frontmatter-parsable"].passed is True
    assert results["description-length"].passed is True
    assert results["yaml-plain-scalar-safety"].passed is True


def test_block_scalar_tolerates_a_blank_continuation_line(tmp_path):
    target = _write(
        tmp_path,
        "agents/block-with-blank.md",
        "---\nname: block-with-blank\ndescription: >\n  First line.\n\n  Second line after a blank one.\n---\n\nBody.\n",
    )
    results = _by_name(ccs.check_shape(target, agent_specs=None))
    assert results["frontmatter-parsable"].passed is True
    assert results["yaml-plain-scalar-safety"].passed is True
    assert "exempt" in results["yaml-plain-scalar-safety"].evidence


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
