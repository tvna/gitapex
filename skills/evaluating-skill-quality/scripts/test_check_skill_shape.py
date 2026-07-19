"""Tests for the deterministic shape checker.

Fixtures are synthesized in tmp_path so the test is self-contained and
travels with the skill on vendoring.
"""
from pathlib import Path

import pytest

import check_skill_shape as css


def _write_skill(tmp_path, *, name="good-skill",
                 description="Does a thing. Use when doing the thing.",
                 body_lines=10, references=None,
                 sidecar=True, api_version="gitapex.dev/v1alpha1",
                 kind="SkillMetadata", meta_name="skill",
                 portability="Portable", capability_assumption="Broad"):
    d = tmp_path / "skill"
    d.mkdir()
    fm = ["---"]
    if name is not None:
        fm.append(f"name: {name}")
    if description is not None:
        fm.append(f"description: {description}")
    fm.append("---")
    filler = "\n".join(f"line {i}" for i in range(body_lines))
    (d / "SKILL.md").write_text(
        "\n".join(fm) + "\n\n" + filler + "\n", encoding="utf-8")
    if sidecar:
        lines = []
        if api_version is not None:
            lines.append(f"apiVersion: {api_version}")
        if kind is not None:
            lines.append(f"kind: {kind}")
        lines.append("metadata:")
        if meta_name is not None:
            lines.append(f"  name: {meta_name}")
        lines.append("spec:")
        if portability is not None:
            lines.append(f"  portability: {portability}")
        if capability_assumption is not None:
            lines.append(f"  capabilityAssumption: {capability_assumption}")
        (d / "gitapex_metadata.yaml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
    if references:
        refs = d / "references"
        refs.mkdir()
        for relpath, content in references.items():
            p = refs / relpath
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
    return d


def _by_name(results):
    return {r.name: r for r in results}


def test_well_formed_skill_passes(tmp_path):
    d = _write_skill(tmp_path)
    results = css.check_shape(d)
    assert all(r.passed for r in results)
    assert css.main([str(d)]) == 0


def test_accepts_skill_md_path_directly(tmp_path):
    d = _write_skill(tmp_path)
    assert css.main([str(d / "SKILL.md")]) == 0


def test_relative_target_matches_dir_name(tmp_path, monkeypatch):
    # A relative invocation (e.g. "." from inside the skill directory, or a
    # bare "SKILL.md") must not collapse skill_dir.name to "" -- the
    # directory name has to be resolved to an absolute path first so
    # metadata-name-matches-dir compares against the real directory name.
    d = _write_skill(tmp_path)
    monkeypatch.chdir(d)
    by_dot = _by_name(css.check_shape(Path(".")))
    assert by_dot["metadata-name-matches-dir"].passed is True
    assert css.main(["."]) == 0
    by_file = _by_name(css.check_shape(Path("SKILL.md")))
    assert by_file["metadata-name-matches-dir"].passed is True
    assert css.main(["SKILL.md"]) == 0


def test_missing_description_fails(tmp_path):
    d = _write_skill(tmp_path, description=None)
    assert _by_name(css.check_shape(d))["description-present"].passed is False
    assert css.main([str(d)]) == 1


def test_overlong_description_fails(tmp_path):
    d = _write_skill(tmp_path, description="x" * (css.DESCRIPTION_MAX_CHARS + 1))
    assert _by_name(css.check_shape(d))["description-length"].passed is False


def test_xml_tag_in_description_fails(tmp_path):
    d = _write_skill(tmp_path, description="Use <b>when</b> doing the thing.")
    assert _by_name(css.check_shape(d))["description-no-xml"].passed is False


def test_uppercase_name_fails(tmp_path):
    d = _write_skill(tmp_path, name="Good-Skill")
    assert _by_name(css.check_shape(d))["name-pattern"].passed is False


def test_reserved_name_fails(tmp_path):
    d = _write_skill(tmp_path, name="claude")
    assert _by_name(css.check_shape(d))["name-not-reserved"].passed is False


def test_reserved_word_as_substring_fails(tmp_path):
    # Per Anthropic's spec the name must not *contain* a reserved word;
    # "claude-tools" / "anthropic-helper" are the doc's own avoid-examples.
    for bad in ("claude-code", "anthropic-helper"):
        sub = tmp_path / bad
        sub.mkdir()
        d = _write_skill(sub, name=bad)
        assert _by_name(css.check_shape(d))["name-not-reserved"].passed is False


def test_absent_name_is_not_checked(tmp_path):
    d = _write_skill(tmp_path, name=None)
    names = _by_name(css.check_shape(d))
    assert not any(k.startswith("name-") for k in names)


def test_overlong_body_fails(tmp_path):
    d = _write_skill(tmp_path, body_lines=css.BODY_MAX_LINES + 5)
    assert _by_name(css.check_shape(d))["body-length"].passed is False


def test_nested_references_fail(tmp_path):
    d = _write_skill(tmp_path, references={"sub/deep.md": "x\n"})
    assert _by_name(css.check_shape(d))["references-flat"].passed is False


def test_long_reference_without_toc_fails(tmp_path):
    body = "\n".join(f"line {i}" for i in range(css.TOC_MIN_LINES + 5))
    d = _write_skill(tmp_path, references={"big.md": body})
    assert _by_name(css.check_shape(d))["toc:big.md"].passed is False


def test_long_reference_with_toc_passes(tmp_path):
    filler = "\n".join(f"line {i}" for i in range(css.TOC_MIN_LINES + 5))
    body = "# Big\n\n## Table of contents\n\n- a\n\n" + filler
    d = _write_skill(tmp_path, references={"big.md": body})
    assert _by_name(css.check_shape(d))["toc:big.md"].passed is True


def test_missing_argument_exits_2(tmp_path):
    # argparse exits (raises SystemExit) with code 2 when the required
    # target is absent or extra positionals are given.
    with pytest.raises(SystemExit) as exc:
        css.main([])
    assert exc.value.code == 2
    with pytest.raises(SystemExit):
        css.main([str(tmp_path), str(tmp_path)])


def test_nonexistent_target_returns_2(tmp_path):
    assert css.main([str(tmp_path / "nope")]) == 2


def test_overlong_name_fails(tmp_path):
    d = _write_skill(tmp_path, name="a" * (css.NAME_MAX_CHARS + 1))
    assert _by_name(css.check_shape(d))["name-length"].passed is False


def test_xml_tag_in_name_fails(tmp_path):
    d = _write_skill(tmp_path, name="foo<b>bar")
    assert _by_name(css.check_shape(d))["name-no-xml"].passed is False


def test_missing_frontmatter_fails_description(tmp_path):
    d = tmp_path / "skill"
    d.mkdir()
    (d / "SKILL.md").write_text("# No frontmatter here\n", encoding="utf-8")
    assert _by_name(css.check_shape(d))["description-present"].passed is False


def test_directory_without_skill_md_returns_2(tmp_path):
    empty = tmp_path / "emptydir"
    empty.mkdir()
    assert css.main([str(empty)]) == 2


def _write_raw(tmp_path, text, *, references=None):
    d = tmp_path / "skill"
    d.mkdir()
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    if references:
        refs = d / "references"
        refs.mkdir()
        for name, content in references.items():
            (refs / name).write_text(content, encoding="utf-8")
    return d


def test_folded_block_description_is_measured(tmp_path):
    long_desc = " ".join(["word"] * 300)  # ~1499 chars, over the 1024 cap
    text = (f"---\nname: folded\ndescription: >\n  {long_desc}\n---\n"
            "# body\nmore\n")
    d = _write_raw(tmp_path, text)
    res = _by_name(css.check_shape(d))
    assert res["description-present"].passed is True
    assert res["description-length"].passed is False


def test_literal_block_description_xml_is_caught(tmp_path):
    text = ("---\nname: literal\ndescription: |\n"
            "  Use <b>this</b> when doing the thing.\n---\n# body\n")
    d = _write_raw(tmp_path, text)
    assert _by_name(css.check_shape(d))["description-no-xml"].passed is False


def test_quoted_description_excludes_surrounding_quotes(tmp_path):
    inner = "x" * css.DESCRIPTION_MAX_CHARS  # exactly the cap once quotes drop
    text = f'---\nname: q\ndescription: "{inner}"\n---\n# body\n'
    d = _write_raw(tmp_path, text)
    assert _by_name(css.check_shape(d))["description-length"].passed is True


def test_bom_prefixed_skill_parses(tmp_path):
    text = ("﻿---\nname: bom-skill\n"
            "description: Valid desc. Use when testing.\n---\n# body\n")
    d = _write_raw(tmp_path, text)
    assert _by_name(css.check_shape(d))["description-present"].passed is True


def test_missing_closing_fence_is_malformed(tmp_path):
    # No closing '---'; a body line that looks like a key must NOT be read
    # as the description.
    text = ("---\nname: broken\ndescription: Real desc. Use when x.\n"
            "# body\ndescription: EVIL OVERRIDE <tag>\n")
    d = _write_raw(tmp_path, text)
    assert _by_name(css.check_shape(d))["description-present"].passed is False


def test_contents_heading_counts_as_toc(tmp_path):
    filler = "\n".join(f"line {i}" for i in range(css.TOC_MIN_LINES + 5))
    body = "# Big\n\n## Contents\n\n- [a](#a)\n- [b](#b)\n\n" + filler
    d = _write_raw(tmp_path, "---\nname: s\ndescription: d. Use when x.\n---\n",
                   references={"big.md": body})
    assert _by_name(css.check_shape(d))["toc:big.md"].passed is True


def test_junk_files_in_references_are_ignored(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n",
        references={"real.md": "ok\n"})
    (d / "gitapex_metadata.yaml").write_text(
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n",
        encoding="utf-8")
    refs = d / "references"
    (refs / ".DS_Store").write_bytes(b"\x00\xff\xfe junk")  # undecodable
    pycache = refs / "__pycache__"
    pycache.mkdir()
    (pycache / "m.cpython-312.pyc").write_bytes(b"\x00\xff")
    res = _by_name(css.check_shape(d))  # must not raise on the binary file
    assert res["references-flat"].passed is True
    assert css.main([str(d)]) == 0


def _result(results, name):
    return next(r for r in results if r.name == name)


def test_out_of_skill_link_fails(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Notes\n\nSee [design doc](../../docs/foo.md) for context.\n")
    results = css.check_shape(d)
    result = _result(results, "links-inside-skill")
    assert not result.passed
    assert "../../docs/foo.md" in result.evidence
    assert css.main([str(d)]) == 1


def test_in_skill_reference_link_passes(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Notes\n\nSee [background](references/foo.md) for context.\n",
        references={"foo.md": "background\n"})
    assert _result(css.check_shape(d), "links-inside-skill").passed


def test_absolute_url_link_is_skipped(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "See [the spec](https://example.com/y) for background.\n")
    assert _result(css.check_shape(d), "links-inside-skill").passed


def test_fragment_only_link_is_skipped(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "Jump to [the checklist](#checklist) below.\n")
    assert _result(css.check_shape(d), "links-inside-skill").passed


def test_absolute_path_link_fails(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "See [system config](/etc/passwd) for context.\n")
    result = _result(css.check_shape(d), "links-inside-skill")
    assert not result.passed
    assert "/etc/passwd" in result.evidence


def test_reference_style_out_of_skill_link_fails(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "See the [runbook][r] for details.\n\n"
        "[r]: ../../docs/runbook.md\n")
    result = _result(css.check_shape(d), "links-inside-skill")
    assert not result.passed
    assert "../../docs/runbook.md" in result.evidence


def test_reference_style_in_skill_link_passes(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "See the [background][b] for context.\n\n"
        "[b]: references/foo.md\n",
        references={"foo.md": "background\n"})
    assert _result(css.check_shape(d), "links-inside-skill").passed


def test_reference_style_angle_bracket_target_fails(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "See the [runbook][r] for details.\n\n"
        "[r]: <../../docs/runbook.md>\n")
    result = _result(css.check_shape(d), "links-inside-skill")
    assert not result.passed
    assert "../../docs/runbook.md" in result.evidence


def test_sidecar_checks_pass_on_good_skill(tmp_path):
    d = _write_skill(tmp_path)
    by = _by_name(css.check_shape(d))
    for check in ("metadata-file-present", "manifest-envelope",
                  "metadata-name-matches-dir", "portability-declared",
                  "capability-assumption-declared"):
        assert by[check].passed is True, check
    assert css.main([str(d)]) == 0


def test_portability_near_top_check_is_gone(tmp_path):
    d = _write_skill(tmp_path)
    assert "portability-near-top" not in _by_name(css.check_shape(d))


def test_missing_sidecar_fails(tmp_path):
    d = _write_skill(tmp_path, sidecar=False)
    by = _by_name(css.check_shape(d))
    assert by["metadata-file-present"].passed is False
    assert css.main([str(d)]) == 1


def test_wrong_api_version_fails(tmp_path):
    d = _write_skill(tmp_path, api_version="example.com/v1")
    assert _by_name(css.check_shape(d))["manifest-envelope"].passed is False


def test_wrong_kind_fails(tmp_path):
    d = _write_skill(tmp_path, kind="NotASkill")
    assert _by_name(css.check_shape(d))["manifest-envelope"].passed is False


def test_metadata_name_mismatch_fails(tmp_path):
    d = _write_skill(tmp_path, meta_name="some-other-name")
    assert _by_name(css.check_shape(d))["metadata-name-matches-dir"].passed is False


def test_missing_portability_fails(tmp_path):
    d = _write_skill(tmp_path, portability=None)
    assert _by_name(css.check_shape(d))["portability-declared"].passed is False


def test_invalid_portability_value_fails(tmp_path):
    d = _write_skill(tmp_path, portability="SomewhatPortable")
    assert _by_name(css.check_shape(d))["portability-declared"].passed is False


def test_missing_capability_assumption_fails(tmp_path):
    d = _write_skill(tmp_path, capability_assumption=None)
    assert _by_name(
        css.check_shape(d))["capability-assumption-declared"].passed is False


def test_invalid_capability_assumption_value_fails(tmp_path):
    d = _write_skill(tmp_path, capability_assumption="Medium")
    assert _by_name(
        css.check_shape(d))["capability-assumption-declared"].passed is False


def test_quoted_portability_value_passes(tmp_path):
    # A double-quoted scalar ("Portable") must be unquoted before matching
    # PORTABILITY_LEVELS -- exercises _unquote via _parse_manifest.
    d = _write_skill(tmp_path, portability='"Portable"')
    assert _by_name(css.check_shape(d))["portability-declared"].passed is True


def test_non_utf8_sidecar_exits_2(tmp_path):
    # Pinned behavior: check_shape() reads the sidecar with
    # read_text(encoding="utf-8") and does not catch the decode error
    # itself; main()'s top-level try/except (OSError, UnicodeDecodeError)
    # around check_shape(...) catches it instead, printing an error and
    # returning 2 -- the same "could not read skill files" exit code used
    # for a missing/unreadable SKILL.md, not a checkable FAIL result.
    d = _write_skill(tmp_path)
    (d / "gitapex_metadata.yaml").write_bytes(b"\xff\xfe not utf8 \x00\x01")
    assert css.main([str(d)]) == 2


def test_manifest_parser_ignores_deeper_nesting(tmp_path):
    text = (
        "apiVersion: gitapex.dev/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - other-skill\n"
        "  capabilityAssumption: Broad\n"
    )
    parsed = css._parse_manifest(text)
    assert parsed["apiVersion"] == "gitapex.dev/v1alpha1"
    assert parsed["metadata"]["name"] == "skill"
    assert parsed["spec"]["portability"] == "Portable"
    assert parsed["spec"]["capabilityAssumption"] == "Broad"
    assert "requires" not in parsed["spec"]
