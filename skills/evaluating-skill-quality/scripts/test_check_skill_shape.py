"""Tests for the deterministic shape checker.

Fixtures are synthesized in tmp_path so the test is self-contained and
travels with the skill on vendoring.
"""
import os
import tempfile
from pathlib import Path

import pytest

import check_skill_shape as css


def _symlinks_supported():
    """Probe once whether this platform/user can create symlinks (e.g.
    Windows without Developer Mode or admin rights cannot)."""
    try:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "target"
            target.mkdir()
            os.symlink(target, Path(td) / "link", target_is_directory=True)
        return True
    except OSError:
        return False


_SYMLINKS_SUPPORTED = _symlinks_supported()


def _write_skill(tmp_path, *, name="good-skill",
                 description="Does a thing. Use when doing the thing.",
                 body_lines=10, references=None,
                 sidecar=True, api_version="gitapex.io/v1alpha1",
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
        (d / "metadata").mkdir(parents=True, exist_ok=True)
        (d / "metadata/gitapex.yaml").write_text(
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


@pytest.mark.skipif(not _SYMLINKS_SUPPORTED,
                    reason="platform cannot create symlinks")
def test_metadata_name_matches_symlink_basename_not_target(tmp_path):
    # skill_dir must be made absolute WITHOUT following symlinks: if a
    # skill directory is itself a symlink whose target has a different
    # basename, the check must compare metadata.name against the
    # symlink's own name, not the real directory it points to.
    real_dir = _write_skill(tmp_path, meta_name="link-name")
    link = tmp_path / "link-name"
    os.symlink(real_dir, link, target_is_directory=True)
    by = _by_name(css.check_shape(link))
    assert by["metadata-name-matches-dir"].passed is True
    assert css.main([str(link)]) == 0


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


def test_unquoted_colon_space_in_description_fails(tmp_path):
    d = _write_skill(tmp_path, description="Read-only: never mutates state.")
    res = _by_name(css.check_shape(d))["description-yaml-safe"]
    assert res.passed is False
    assert "unquoted ': ' or trailing ':'" in res.evidence


def test_trailing_colon_in_description_fails(tmp_path):
    d = _write_skill(tmp_path, description="Use when doing the thing:")
    res = _by_name(css.check_shape(d))["description-yaml-safe"]
    assert res.passed is False
    assert "unquoted ': ' or trailing ':'" in res.evidence


def test_unquoted_comment_marker_in_description_fails(tmp_path):
    d = _write_skill(tmp_path, description="Does a thing # not a comment")
    res = _by_name(css.check_shape(d))["description-yaml-safe"]
    assert res.passed is False
    assert "unquoted ' #' or leading '#'" in res.evidence


def test_hyphenated_aside_in_description_passes(tmp_path):
    # This repository's own established convention for the same kind of
    # aside a raw colon would otherwise be used for.
    d = _write_skill(tmp_path, description="Read-only -- never mutates state.")
    assert _by_name(css.check_shape(d))["description-yaml-safe"].passed is True


def test_earlier_comment_marker_reported_over_later_colon(tmp_path):
    # A real YAML parser truncates at the first hazard it hits -- the
    # earlier ' #' here, not the later ': ' -- so the evidence must point
    # at char 12 (the comment marker), not char 19 (the colon).
    d = _write_skill(tmp_path, description="Does a thing # note: still unsafe")
    res = _by_name(css.check_shape(d))["description-yaml-safe"]
    assert res.passed is False
    assert res.evidence == "unquoted ' #' or leading '#' at char 12"


def test_quoted_description_with_colon_passes_yaml_safe(tmp_path):
    # A double-quoted description is already safe under a real YAML parser
    # regardless of an embedded ": " -- _parse_frontmatter strips the
    # quotes, so the check must know the source was quoted rather than
    # scanning the already-unquoted text.
    text = ('---\nname: quoted-desc\n'
            'description: "Read-only: never mutates state."\n---\n# body\n')
    d = _write_raw(tmp_path, text)
    res = _by_name(css.check_shape(d))["description-yaml-safe"]
    assert res.passed is True
    assert res.evidence == "safe (quoted or block scalar in source)"


def test_folded_block_description_with_colon_passes_yaml_safe(tmp_path):
    # A folded block scalar (">") is already safe under a real YAML parser
    # regardless of an embedded ": " -- _parse_frontmatter joins the
    # continuation lines into plain text, so the check must know the
    # source was a block scalar rather than scanning the joined text.
    text = ("---\nname: folded-desc\ndescription: >\n"
            "  Read-only: never mutates state,\n"
            "  safely written as a folded block scalar.\n---\n# body\n")
    d = _write_raw(tmp_path, text)
    res = _by_name(css.check_shape(d))["description-yaml-safe"]
    assert res.passed is True
    assert res.evidence == "safe (quoted or block scalar in source)"


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
    (d / "metadata").mkdir()
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
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


# ---- related-skill-references-resolve ----

def test_related_skill_reference_absent_passes(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Notes\n\nNo cross-references here.\n")
    result = _result(css.check_shape(d), "related-skill-references-resolve")
    assert result.passed
    assert result.evidence == "all resolve"


def test_related_skill_reference_resolves_passes(tmp_path):
    (tmp_path / "sibling-skill").mkdir()
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Related skills\n\n"
        "- **vs. `sibling-skill`:** does something else entirely.\n")
    assert _result(css.check_shape(d), "related-skill-references-resolve").passed


def test_related_skill_reference_dangling_fails(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Related skills\n\n"
        "- **vs. `renamed-away-skill`:** used to exist, doesn't anymore.\n")
    result = _result(css.check_shape(d), "related-skill-references-resolve")
    assert not result.passed
    assert "renamed-away-skill" in result.evidence
    assert css.main([str(d)]) == 1


def test_related_skill_reference_dual_name_bullet_both_resolve(tmp_path):
    (tmp_path / "sibling-a").mkdir()
    (tmp_path / "sibling-b").mkdir()
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Related skills\n\n"
        "- **vs. `sibling-a` / `sibling-b`:** both distinct from this one.\n")
    assert _result(css.check_shape(d), "related-skill-references-resolve").passed


def test_related_skill_reference_dual_name_bullet_one_dangling_fails(tmp_path):
    (tmp_path / "sibling-a").mkdir()
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Related skills\n\n"
        "- **vs. `sibling-a` / `ghost-sibling`:** one real, one stale.\n")
    result = _result(css.check_shape(d), "related-skill-references-resolve")
    assert not result.passed
    assert "ghost-sibling" in result.evidence
    assert "sibling-a" not in result.evidence  # resolves fine, not dangling


def test_related_skill_reference_body_prose_mention_also_checked(tmp_path):
    # Regression: a name repeated in the bullet's own explanatory prose
    # (after the header, before the next bullet/blank line) must be
    # checked too, not just the "vs. `name`:" header itself -- a skill
    # can be named only in body prose with no header bullet of its own
    # elsewhere in the file, exactly as `driving-pr-to-merge` is inside
    # `fixing-a-reported-issue`'s own Related-skills section.
    (tmp_path / "sibling-a").mkdir()
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Related skills\n\n"
        "- **vs. `sibling-a`:** that skill does X; this one produces the\n"
        "  thing `ghost-sibling` would then take over.\n")
    result = _result(css.check_shape(d), "related-skill-references-resolve")
    assert not result.passed
    assert "ghost-sibling" in result.evidence


def test_related_skill_reference_bullet_stops_at_next_bullet(tmp_path):
    # Regression: extending the match to cover body prose must not bleed
    # into the NEXT bullet's own header/body -- each bullet's names are
    # independent.
    (tmp_path / "sibling-a").mkdir()
    (tmp_path / "sibling-b").mkdir()
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "## Related skills\n\n"
        "- **vs. `sibling-a`:** fine on its own.\n"
        "- **vs. `sibling-b`:** also fine, mentions `sibling-a` again.\n")
    result = _result(css.check_shape(d), "related-skill-references-resolve")
    assert result.passed


def test_sidecar_checks_pass_on_good_skill(tmp_path):
    d = _write_skill(tmp_path)
    by = _by_name(css.check_shape(d))
    for check in ("metadata-file-present", "manifest-envelope",
                  "metadata-name-matches-dir", "portability-declared",
                  "capability-assumption-declared", "references-well-formed"):
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


def test_non_utf8_sidecar_fails_checks_not_exit_2(tmp_path):
    # Updated contract: a corrupt sidecar is a shape defect, not a usage
    # error. check_shape() wraps its single sidecar read+parse in
    # try/except (OSError, UnicodeDecodeError) itself, so the exception
    # never propagates out -- it is reported as FAILed CheckResults with
    # evidence naming the read failure. metadata-file-present still PASSes
    # (the file does exist); the five checks that need the parsed manifest
    # FAIL. main() returns 1 (a full readable report), same as any other
    # shape failure -- not 2, which stays reserved for a missing/unreadable
    # SKILL.md (see test_directory_without_skill_md_returns_2).
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_bytes(b"\xff\xfe not utf8 \x00\x01")
    by = _by_name(css.check_shape(d))
    assert by["metadata-file-present"].passed is True
    for check in ("manifest-envelope", "metadata-name-matches-dir",
                  "portability-declared", "capability-assumption-declared",
                  "references-well-formed"):
        assert by[check].passed is False, check
        assert "UnicodeDecodeError" in by[check].evidence, check
    assert css.main([str(d)]) == 1


def test_manifest_parser_ignores_deeper_nesting(tmp_path):
    text = (
        "apiVersion: gitapex.io/v1alpha1\n"
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
    assert parsed.root["apiVersion"] == "gitapex.io/v1alpha1"
    assert parsed.root["metadata"]["name"] == "skill"
    assert parsed.root["spec"]["portability"] == "Portable"
    assert parsed.root["spec"]["capabilityAssumption"] == "Broad"
    assert "requires" not in parsed.root["spec"]
    assert parsed.malformed_lines == []


# ---- manifest-parsable (malformed top-level line detection) ----

def test_malformed_top_level_line_fails_manifest_parsable(tmp_path):
    # The exact reported case: a top-level '- invalid mapping entry' line
    # that real PyYAML rejects with a ParserError, sitting alongside an
    # otherwise fully valid sidecar.
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "- invalid mapping entry\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    result = by["manifest-parsable"]
    assert result.passed is False
    assert "1 malformed line" in result.evidence
    assert "- invalid mapping entry" in result.evidence
    assert css.main([str(d)]) == 1


def test_legitimate_deeper_nesting_passes_manifest_parsable(tmp_path):
    # Pins that the malformed-line fix does not break the reserved-field
    # design: a nested map like spec.skillDependencies (a list-valued
    # 'requires' and a 'relatedTo' list) must never have its indented
    # lines flagged as malformed top-level lines -- that's a distinct
    # concern from the field's own shape gates
    # (skill-dependencies-well-formed et al., covered separately below).
    # spec.references' own mapping-shaped-item case is a distinct scenario,
    # covered by test_references_mapping_shaped_item_fails_well_formed
    # below (that field is no longer ungated as of Sub-project C).
    (tmp_path / "other-skill").mkdir()
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - other-skill\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["manifest-parsable"].passed is True
    assert by["manifest-parsable"].evidence == "no malformed lines"
    assert css.main([str(d)]) == 0


def test_references_mapping_shaped_item_fails_well_formed(tmp_path):
    # Regression guard for the bug an independent review round found: a
    # mapping-shaped spec.references item (the exact shape the previous
    # test used to carry, back when this field was still fully ungated)
    # must not be silently truncated into a garbled scalar string and
    # certified as well-formed -- it must fail loudly instead.
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - path: references/rubric.md\n"
        "      title: Rubric\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["manifest-parsable"].passed is True
    assert by["references-well-formed"].passed is False
    assert "path: references/rubric.md" in by["references-well-formed"].evidence
    assert css.main([str(d)]) == 1
    parsed = css._parse_manifest((d / "metadata/gitapex.yaml").read_text(encoding="utf-8"))
    assert parsed.malformed_reference_items == ["- path: references/rubric.md"]
    # The malformed item is excluded from the parsed list entirely (not
    # silently kept as a garbled string); nothing else in this fixture's
    # references block was well-formed, so the list itself ends up empty.
    assert parsed.root["spec"]["references"] == []


def test_references_inconsistent_indent_item_fails_well_formed(tmp_path):
    # Regression guard: real YAML rejects a block sequence whose items are
    # not all at the same indent. A well-formed item followed by one at a
    # different indent must be flagged, not silently accepted alongside it.
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - \"a\"\n"
        "  - \"b\"\n"
        "      - \"c\"\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is False
    assert css.main([str(d)]) == 1
    parsed = css._parse_manifest((d / "metadata/gitapex.yaml").read_text(encoding="utf-8"))
    assert parsed.root["spec"]["references"] == ["a"]
    assert parsed.malformed_reference_items == ['- "b"', '- "c"']


def test_comment_and_document_marker_pass_manifest_parsable(tmp_path):
    # A '#' comment and YAML document markers ('---' / '...') at column 0
    # must not be flagged as malformed.
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "# a leading comment\n"
        "---\n"
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "...\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["manifest-parsable"].passed is True
    assert css.main([str(d)]) == 0


def test_unreadable_sidecar_fails_manifest_parsable(tmp_path):
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_bytes(b"\xff\xfe not utf8 \x00\x01")
    by = _by_name(css.check_shape(d))
    assert by["manifest-parsable"].passed is False
    assert "UnicodeDecodeError" in by["manifest-parsable"].evidence
    assert css.main([str(d)]) == 1


# ---- Portable self-citation scan (issue #171) ----

def _portable_body(body="", *,
                   marker="**Portability: Portable.** Self-contained."):
    return (f"---\nname: s\ndescription: d. Use when x.\n---\n\n"
            f"{marker}\n\n{body}\n")


def test_portable_bare_issue_citation_fails(tmp_path):
    # The first historical incident: a bare #N cited as provenance in prose.
    d = _write_raw(tmp_path, _portable_body(
        "The ambiguous-timezone edge case first reported in issue #149 of "
        "this project defaults to the most common value."))
    res = _by_name(css.check_shape(d))
    assert res["no-bare-issue-citation"].passed is False
    assert "#149" in res["no-bare-issue-citation"].evidence
    assert css.main([str(d)]) == 1


def test_portable_qualified_issue_citation_fails(tmp_path):
    # The second historical incident: a fully-qualified owner/repo#N citation.
    d = _write_raw(tmp_path, _portable_body(
        "Provenance: owner/repo#149 recorded the original decision."))
    res = _by_name(css.check_shape(d))
    assert res["no-bare-issue-citation"].passed is False
    assert "owner/repo#149" in res["no-bare-issue-citation"].evidence


def test_portable_unhedged_repo_path_citation_fails(tmp_path):
    # The third historical incident: an unhedged origin-repo path citation.
    d = _write_raw(tmp_path, _portable_body(
        "This behaviour is checked in "
        "evals/evaluating-skill-quality/tasks/guardrail.yaml today."))
    res = _by_name(css.check_shape(d))
    result = res["portable-no-repo-path-citation"]
    assert result.passed is False
    assert "evals/evaluating-skill-quality/tasks/guardrail.yaml" in result.evidence


def test_portable_inline_code_citation_is_excluded(tmp_path):
    # The rubric's own way of quoting a bad-example token: inline code.
    # This exclusion is specific to the two bare-prose checks below --
    # portable-no-unhedged-inline-path-citation (issue #220) and
    # portable-no-unhedged-inline-issue-citation (issue #263) both inspect
    # exactly this kind of inline-code span and DO flag it, since this
    # fixture's `evals/foo/bar.yaml` and `#149`/`owner/repo#149` citations
    # have no hedge phrase nearby; see test_portable_unhedged_inline_repo_path_fails
    # and test_portable_unhedged_inline_issue_citation_fails for those checks'
    # own dedicated fixtures.
    d = _write_raw(tmp_path, _portable_body(
        "No bare (`#149`) or fully-qualified (`owner/repo#149`) number, and "
        "no `evals/foo/bar.yaml` path, belongs in portable content."))
    res = _by_name(css.check_shape(d))
    assert res["no-bare-issue-citation"].passed is True
    assert res["portable-no-repo-path-citation"].passed is True
    assert res["portable-no-unhedged-inline-path-citation"].passed is False
    assert res["portable-no-unhedged-inline-issue-citation"].passed is False


def test_portable_fenced_illustrative_citation_is_excluded(tmp_path):
    # A fixture's own quoted target text, shown as a fenced illustrative
    # sample, must not trip the scan (issue #171 acceptance criterion 3).
    d = _write_raw(tmp_path, _portable_body(
        "Bad-example target content under review:\n\n"
        "```\nreported in issue #88 of this project; see evals/x/y.yaml\n```"))
    res = _by_name(css.check_shape(d))
    assert res["no-bare-issue-citation"].passed is True
    assert res["portable-no-repo-path-citation"].passed is True


def test_portable_linked_issue_citation_is_excluded(tmp_path):
    # An illustrative worked-example citation carried by a Markdown link.
    d = _write_raw(tmp_path, _portable_body(
        "Merged in [PR #2][pr2] -- kept as a worked example.\n\n"
        "[pr2]: https://github.com/tvna/gitapex/pull/2"))
    assert _by_name(css.check_shape(d))["no-bare-issue-citation"].passed is True


def test_portable_url_path_is_excluded(tmp_path):
    d = _write_raw(tmp_path, _portable_body(
        "See <https://platform.claude.com/docs/en/agent-skills/best-practices>."))
    assert _by_name(css.check_shape(d))["portable-no-repo-path-citation"].passed is True


def test_non_portable_skill_skips_path_scan_but_not_issue_scan(tmp_path):
    # A Mixed skill legitimately cites repo paths, so the two path checks
    # do not run at all -- absent from the result set. The bare-issue-
    # citation check is different (issue #254): it still runs and fails,
    # since a bare issue number is barred at every portability level.
    d = _write_raw(tmp_path, _portable_body(
        "Handled in evals/foo/bar.yaml, first reported in issue #149.",
        marker="**Portability: Mixed.** Repo-specific detail is split out."))
    names = _by_name(css.check_shape(d))
    assert "portable-no-repo-path-citation" not in names
    assert "portable-no-unhedged-inline-path-citation" not in names
    assert "portable-no-unhedged-inline-issue-citation" not in names
    assert names["no-bare-issue-citation"].passed is False
    assert "#149" in names["no-bare-issue-citation"].evidence


def test_portable_citation_in_reference_file_fails(tmp_path):
    # The scan covers references/*.md, not just SKILL.md, and labels the file.
    d = _write_raw(tmp_path, _portable_body("Clean body."),
                   references={"notes.md": "First reported in issue #149.\n"})
    result = _by_name(css.check_shape(d))["no-bare-issue-citation"]
    assert result.passed is False
    assert "references/notes.md:#149" in result.evidence


def test_portable_clean_skill_passes_citation_scan(tmp_path):
    d = _write_raw(tmp_path, _portable_body(
        "A clean portable body: no issue numbers, no repo paths."))
    res = _by_name(css.check_shape(d))
    assert res["no-bare-issue-citation"].passed is True
    assert res["portable-no-repo-path-citation"].passed is True


def test_wrapped_portable_marker_still_runs_citation_scan(tmp_path):
    # The level word wraps onto the line after the marker; the scan must
    # still run, not silently skip (a false negative in the gate).
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability:**\nPortable. Self-contained.\n\n"
        "First reported in issue #149 of this project.\n")
    assert _by_name(css.check_shape(d))["no-bare-issue-citation"].passed is False


def test_wrapped_mixed_marker_still_skips_path_scan_but_not_issue_scan(tmp_path):
    # The same wrap, but a Mixed level: the two path checks stay skipped
    # (Mixed skills legitimately cite repo paths), while the bare-issue-
    # citation check still runs and fails (issue #254).
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability:**\nMixed. Repo detail is split out.\n\n"
        "Handled in evals/foo/bar.yaml, first reported in issue #149.\n")
    names = _by_name(css.check_shape(d))
    assert "portable-no-repo-path-citation" not in names
    assert "portable-no-unhedged-inline-path-citation" not in names
    assert "portable-no-unhedged-inline-issue-citation" not in names
    assert names["no-bare-issue-citation"].passed is False


# ---- Portable inline-code repo-path citation hedge scan (issue #220) ----
#
# #171's illustrative-span exemption treats every inline-code citation as
# automatically safe. #220's own reported bug is exactly that gap: an
# inline-code citation of a real origin-repository path
# (`docs/superpowers/specs/...`) that passed the #171 scan cleanly despite
# having no hedge explaining it is this repository's own file. These tests
# cover the negative (no hedge -> still flagged) and positive (an approved
# hedge phrase -> passes) cases the acceptance criteria call for, plus the
# two real citations issue #220 names by name. The hedge search is bounded
# to a citation's own sentence or the sentence immediately before it (not
# the whole paragraph) and excludes the citation's own matched text --
# see test_hedge_in_next_sentence_of_same_paragraph_does_not_count and
# test_citation_text_cannot_self_satisfy_hedge below for why both of those
# narrower bounds matter.

def test_portable_unhedged_inline_repo_path_fails(tmp_path):
    # The reported bug's exact shape: a real-looking inline-code citation
    # with no hedge anywhere nearby.
    d = _write_raw(tmp_path, _portable_body(
        "See the design spec: `docs/superpowers/specs/2026-07-20-x.md`."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is False
    assert "docs/superpowers/specs/2026-07-20-x.md" in result.evidence


@pytest.mark.parametrize("body", [
    # rubric.md's own established phrasing.
    "This repository has also recorded the design spec at "
    "`docs/superpowers/specs/2026-07-20-x.md`.",
    # Mirrors the exact citation named in issue #220's acceptance criteria
    # 2: rubric.md's "This repository has also used the same move
    # informally ..." sentence, confirmed not to false-positive.
    "This repository has also used the same move informally, once, "
    "to find gaps in its own *skill coverage* rather than in one "
    "skill's rubric "
    "(`docs/superpowers/specs/2026-07-15-triage-cluster-design.md`: "
    '"a Fable-assisted skill-gap analysis").',
    # Mirrors the exact citation named in issue #220's acceptance criteria
    # 3: scorer-gated-skill-edits/SKILL.md's added-in-#217 hedge.
    "This repository has also recorded the design spec for that flag, "
    "for readers working in this specific repository, at "
    "`docs/superpowers/specs/2026-07-20-judge-mode-scorer-design.md`; "
    "a vendored copy of this skill has no such file and does not "
    "need one.",
    # The opposite direction: a generic, illustrative path name for
    # whatever repository the skill lands in, matching
    # establishing-ubiquitous-language's own phrasing.
    "Record the winning term in the calling repository's own "
    "glossary doc (e.g. `docs/glossary.md`).",
    # rubric.md's own dimension-8 phrasing.
    "Check the target repository for an eval mechanism -- for a "
    "Claude Code target, that's an `evals/evals.json` file.",
    # worked-example-explaining-the-work.md's own phrasing.
    "gitapex's own repository does not currently have a "
    "`docs/adr/` directory.",
], ids=["this-repository", "rubric-style", "scorer-gated-style",
       "calling-repository", "target-repository", "gitapex"])
def test_approved_hedge_phrase_passes(tmp_path, body):
    d = _write_raw(tmp_path, _portable_body(body))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is True


def test_leading_hedge_covers_a_list_of_different_paths(tmp_path):
    # Real content in this repository (worked-example-self-review.md, "in
    # this repository's own bookkeeping ...: `evals/.../split.md`'s
    # Kept-edit log and `docs/skill-eval-status.md`.") uses ONE leading
    # hedge to introduce a comma-joined list of TWO DIFFERENT path
    # citations in a single clause -- this must keep passing. A stricter
    # per-citation windowing design (tried and reverted while closing a
    # Codex-reported issue-citation exploit on PR #273) broke this exact
    # pattern, which is why the fix for that exploit is a conditional
    # bridging-semicolon split (see _split_at_bridging_semicolon) plus a
    # "previous clause already cites something" guard, not per-citation
    # isolation within one clause.
    d = _write_raw(tmp_path, _portable_body(
        "In this repository's own bookkeeping: `evals/x/split.md`'s "
        "Kept-edit log and `docs/skill-eval-status.md`."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is True


def test_semicolon_inside_one_citations_own_aside_does_not_split(tmp_path):
    # Real, pre-existing content in this repository
    # (worked-example-explaining-the-work.md) uses a semicolon INSIDE a
    # single parenthetical aside about ONE citation, with the hedge word
    # landing after the semicolon: "`docs/adr/NNNN-*.md` (line 24;
    # gitapex's own state on this path is covered under Portability level
    # above), uses forward slashes." A blanket semicolon split (a second
    # cut of the #273 fix, after the bare-word-hedge fix) broke this by
    # separating the citation from its own hedge; splitting only when a
    # citation appears on BOTH sides of the semicolon (there is no second
    # citation here) fixes it without reopening the Codex-reported case.
    d = _write_raw(tmp_path, _portable_body(
        "The one path in the skill, `docs/adr/NNNN-*.md` (line 24; "
        "gitapex's own state on this path is covered elsewhere), uses "
        "forward slashes."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is True


def test_semicolon_with_citations_on_both_sides_still_splits(tmp_path):
    # The other half of the same fix: when a citation genuinely does
    # appear on both sides of a semicolon, it must still split -- this is
    # exactly Codex's reported shape, generalized to the repo-path spec so
    # both specs' behavior stays consistent (specs share the same clause
    # splitter, see _inline_citation_offenders's own docstring).
    d = _write_raw(tmp_path, _portable_body(
        "This repository has also recorded `docs/a.md`; see `docs/b.md` "
        "for the unrelated details."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is False
    assert "docs/b.md" in result.evidence
    assert "docs/a.md" not in result.evidence


def test_hedge_in_different_paragraph_does_not_count(tmp_path):
    # Bounded distance, not whole-document: a hedge phrase two paragraphs
    # away must not exempt an unrelated citation in its own paragraph.
    d = _write_raw(tmp_path, _portable_body(
        "This repository has also recorded some background context "
        "elsewhere.\n\n"
        "See the design spec: `docs/superpowers/specs/2026-07-20-x.md`."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is False


def test_hedge_in_next_sentence_of_same_paragraph_does_not_count(tmp_path):
    # Regression guard for a review finding on the first cut of this check:
    # paragraph-wide scoping let a hedge written for one citation silently
    # exempt a completely unrelated citation several sentences later in the
    # same paragraph (reproduced for real in this repository's own
    # worked-example-self-review.md before it was fixed). The bound is now
    # a citation's own sentence or the one immediately before it, so a
    # hedge three sentences away must not count.
    d = _write_raw(tmp_path, _portable_body(
        "This repository has also recorded background context here. "
        "A second, unrelated sentence with no citation. "
        "See the design spec: `docs/superpowers/specs/2026-07-20-x.md`."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is False


def test_citation_text_cannot_self_satisfy_hedge(tmp_path):
    # Regression guard: the hedge search must exclude the citation's own
    # matched inline-code text, so a path whose filename happens to contain
    # a HEDGE_PHRASES word (e.g. "gitapex") cannot self-satisfy the
    # requirement with no hedge actually written by the author. A real file
    # at exactly this path exists in this repository.
    d = _write_raw(tmp_path, _portable_body(
        "See the design spec: "
        "`docs/superpowers/specs/2026-07-15-gitapex-cli-governance-design.md`."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is False


def test_hedge_wrapped_across_lines_within_paragraph_counts(tmp_path):
    # A hedge phrase that Markdown line-wraps across two lines of the same
    # sentence must still be found -- whitespace is normalized before the
    # search, matching how the real establishing-ubiquitous-language
    # citation is actually wrapped in the repository.
    d = _write_raw(tmp_path, _portable_body(
        "Record the winning term in the calling\n"
        "repository's own glossary doc (e.g. `docs/glossary.md`)."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is True


def test_fenced_inline_repo_path_still_excluded_from_hedge_scan(tmp_path):
    # A citation inside a fenced code block stays exempt unconditionally
    # (issue #171 acceptance criterion 3) -- this new, narrower check must
    # not reopen that case.
    d = _write_raw(tmp_path, _portable_body(
        "Bad-example target content under review:\n\n"
        "```\nsee `docs/superpowers/specs/2026-07-20-x.md`\n```"))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is True


def test_unhedged_inline_repo_path_in_reference_file_fails(tmp_path):
    # The scan covers references/*.md, not just SKILL.md, and labels the
    # file, matching the other two Portable citation checks.
    d = _write_raw(tmp_path, _portable_body("Clean body."),
                   references={"notes.md":
                               "See `docs/superpowers/specs/x.md` for context.\n"})
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-path-citation"]
    assert result.passed is False
    assert "references/notes.md:`docs/superpowers/specs/x.md`" in result.evidence


# ---- Portable inline-code issue/PR-number citation hedge scan (issue #263) ----
#
# #171's illustrative-span exemption treats every inline-code citation as
# automatically safe. #263's own reported bug is exactly that gap, mirrored
# from #220's repo-path fix: a fictional worked-example citation like
# `` `#42` `` sits unflagged in Portable content because it is inline code,
# even though dimension 6 bans an issue/PR-number citation from Portable
# content regardless of how it is quoted. Unlike the repo-path check, there
# is no "deliberate reference to this repository's own file" case to
# preserve here -- only the narrower "illustrating the citation *syntax*
# itself" case (evaluating-skill-quality's own `trackingIssue` field
# documentation, "an anchored `#123` or `owner/repo#123` reference"), hence
# the separate, narrower ISSUE_CITATION_HEDGE_PHRASES rather than reusing
# HEDGE_PHRASES. The hedge search shares the same sentence-bounded mechanism
# as the repo-path check above -- see that section's own comment for why
# the bound is a citation's own sentence or the one immediately before it,
# not the whole paragraph.

def test_portable_unhedged_inline_issue_citation_fails(tmp_path):
    # The reported bug's exact shape: a fictional worked-example citation
    # with no hedge anywhere nearby.
    d = _write_raw(tmp_path, _portable_body(
        "Fictitious PR `#42`, \"Add retry to fetch helper,\" has just been "
        "opened."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "#42" in result.evidence


def test_portable_unhedged_inline_qualified_issue_citation_fails(tmp_path):
    d = _write_raw(tmp_path, _portable_body(
        "See `owner/repo#42` for the original discussion."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "owner/repo#42" in result.evidence


@pytest.mark.parametrize("body", [
    # evaluating-skill-quality's own SKILL.md/rubric.md phrasing: a
    # citation-syntax illustration, not a specific issue being cited.
    "`trackingIssue` must be an anchored `#123` or `owner/repo#123` "
    "reference.",
    # A distinct legitimate case discovered while wiring this check up:
    # evaluating-skill-quality's own SKILL.md/rubric.md restate the
    # no-bare-issue-citation rule itself in prose (mirroring this module's
    # own docstring), using `#149`/`owner/repo#149` as the rule's example
    # numbers -- real text, not a hypothetical. "anchored" does not appear
    # here; "issue/pr-number citation" is the shared phrase that marks this
    # as rule documentation rather than worked-example bookkeeping.
    "A bare GitHub issue/PR-number citation (`#149`, `owner/repo#149`) "
    "is barred from SKILL.md/references/*.md at every level.",
    # Pre-emptive escape hatch (issue #271) for a known, unresolved
    # limitation (issue #272): ISSUE_CITATION_RE cannot syntactically
    # distinguish a real issue number from a decimal-digit-only CSS hex
    # color. No web-design skill exists in this repo yet, but this is how
    # one would naturally phrase a color worked example.
    "Set the accent to the hex color `#123456` for the primary button.",
    "The theme defines this CSS color: `#123`.",
], ids=["trackingIssue-shape", "self-referential-rule-statement",
       "hex-color-escape-hatch", "css-color-escape-hatch"])
def test_approved_issue_hedge_phrase_passes(tmp_path, body):
    d = _write_raw(tmp_path, _portable_body(body))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is True


def test_unhedged_css_shaped_number_still_flagged(tmp_path):
    # The escape hatch above requires the author to actually name the
    # color's nature -- an unhedged decimal-digit-only token still reads as
    # a possible issue/PR citation and must still fail (issue #272 is the
    # deeper, still-open fix for this false-positive shape; this test only
    # guards that the interim hedge phrases in issue #271 don't silently
    # exempt every digit-only inline-code token).
    d = _write_raw(tmp_path, _portable_body(
        "Set the accent to `#123456` for the primary button."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "#123456" in result.evidence


def test_bare_hedge_word_does_not_exempt_a_real_citation(tmp_path):
    # Regression guard for a review finding on the first cut of this check:
    # a bare single-word hedge ("anchored"/"citation") is satisfied by
    # ordinary prose that uses the word while citing a real, banned issue
    # number -- exactly the defect this check exists to catch. The approved
    # phrases are full multi-word phrases for this reason; "citation" alone
    # (not the full "issue/pr-number citation" phrase) must not exempt this.
    d = _write_raw(tmp_path, _portable_body(
        "For provenance citation, see PR `#42` which fixed the bug."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "#42" in result.evidence


def test_bare_anchored_word_does_not_exempt_a_real_citation(tmp_path):
    # Same regression guard, the other bare word: ordinary prose using
    # "anchored" in an unrelated sense must not exempt a real citation.
    d = _write_raw(tmp_path, _portable_body(
        "The review is anchored to PR `#88` for full context."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "#88" in result.evidence


def test_issue_hedge_in_different_paragraph_does_not_count(tmp_path):
    # Bounded distance, not whole-document: a hedge phrase two paragraphs
    # away must not exempt an unrelated citation in its own paragraph.
    d = _write_raw(tmp_path, _portable_body(
        "This field's value must be an anchored reference, described "
        "elsewhere.\n\n"
        "Fictitious PR `#42` has just been opened."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False


def test_issue_hedge_in_next_sentence_of_same_paragraph_does_not_count(tmp_path):
    # Same regression guard as the repo-path check's own test: a hedge
    # written for one citation must not silently exempt an unrelated
    # citation several sentences later in the same paragraph.
    d = _write_raw(tmp_path, _portable_body(
        "`trackingIssue` must be an anchored reference. "
        "A second, unrelated sentence about something else entirely. "
        "Fictitious PR `#42` has just been opened."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False


def test_issue_citation_text_cannot_self_satisfy_hedge(tmp_path):
    # Regression guard: the hedge search must exclude the citation's own
    # matched inline-code text, so an owner/repo naming coincidence cannot
    # self-satisfy the requirement with no hedge actually written by the
    # author.
    d = _write_raw(tmp_path, _portable_body(
        "See `anchored-org/repo#42` for the original discussion."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False


def test_one_citations_own_text_cannot_hedge_a_different_citation(tmp_path):
    # Regression guard for a review finding: excluding only the CURRENT
    # citation's own span from the hedge search left a DIFFERENT citation's
    # inline-code span still visible -- so one citation's own text (however
    # implausible) satisfying a hedge phrase could silently exempt an
    # unrelated, genuinely unhedged citation next to it in the same
    # sentence. Every inline-code span in the sentence is now excluded from
    # the search, not just the one being checked, so both citations here
    # must be flagged.
    d = _write_raw(tmp_path, _portable_body(
        "Compare `this must be an anchored citation#42` with `#100` for "
        "details."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "#42" in result.evidence
    assert "#100" in result.evidence


def test_color_hedge_does_not_exempt_a_different_real_citation_same_sentence(tmp_path):
    # Regression guard for a Codex review finding on PR #273: because the
    # hedge search originally covered the WHOLE sentence, a legitimate
    # color hedge for one citation silently exempted a completely
    # different, genuinely unhedged issue/PR citation sitting in the same
    # sentence -- exactly the gate-weakening failure #263 exists to
    # prevent. The two citations here have different numbers (123456 vs
    # 42), so they are different groups: the color citation must pass, and
    # the real citation must still fail.
    d = _write_raw(tmp_path, _portable_body(
        "Use the hex color `#123456`; see PR `#42` for the implementation "
        "history."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "#42" in result.evidence
    assert "#123456" not in result.evidence


def test_comma_joined_different_citations_share_the_clause_hedge(tmp_path):
    # A known, DELIBERATELY ACCEPTED residual (issue #263/#273's own
    # docstring rationale), not a guarantee: two different citations
    # joined within one clause by a comma/apposition (no semicolon) still
    # share that clause's hedge search, so an unhedged real citation can
    # slip through alongside a legitimately hedged one. An earlier, more
    # aggressive per-citation windowing design closed this specific case,
    # but broke a real, legitimate pattern already in this repository's own
    # content (see test_leading_hedge_covers_a_list_of_different_paths):
    # one leading hedge introducing a LIST of several different citations,
    # comma-joined, with no semicolon between them. Distinguishing "a list"
    # from "an unrelated aside" from punctuation alone is exactly the kind
    # of natural-language judgment this deterministic checker's own
    # docstring says it does not attempt -- the semicolon-based clause
    # split (issue #273) closes the actually-reported (Codex, PR #269/#273)
    # exploit shape; this narrower one is intentionally left to the
    # model-judged rubric dimension as the backstop.
    d = _write_raw(tmp_path, _portable_body(
        "See `#123456`, a hex color reference, followed by the real bug "
        "`#42`."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is True


def test_color_hedge_in_previous_sentence_does_not_exempt_next_sentence_citation(tmp_path):
    # Same conflation as the two tests above, recurring across a sentence
    # boundary: the "previous sentence" fallback exists for a pure hedge
    # sentence with NO citation of its own (see
    # test_hedge_in_next_sentence_of_same_paragraph_does_not_count's own
    # fixture for the established pattern). When the previous sentence
    # instead has its OWN single citation, that sentence's hedge is already
    # "spent" justifying it and must not leak into an unrelated citation in
    # the very next sentence.
    d = _write_raw(tmp_path, _portable_body(
        "Use the hex color `#123456` for the button. See PR `#42` for the "
        "implementation history."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "#42" in result.evidence
    assert "#123456" not in result.evidence


def test_issue_hedge_wrapped_across_lines_within_paragraph_counts(tmp_path):
    # A hedge phrase that Markdown line-wraps across two lines of the same
    # sentence must still be found -- whitespace is normalized before the
    # search.
    d = _write_raw(tmp_path, _portable_body(
        "`trackingIssue` must be an anchored\n"
        "`#123` or `owner/repo#123` reference."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is True


def test_fenced_inline_issue_citation_still_excluded_from_hedge_scan(tmp_path):
    # A citation inside a fenced code block stays exempt unconditionally
    # (issue #171 acceptance criterion 3) -- this new, narrower check must
    # not reopen that case.
    d = _write_raw(tmp_path, _portable_body(
        "Bad-example target content under review:\n\n"
        "```\nFictitious PR `#42` has just been opened.\n```"))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is True


def test_unhedged_inline_issue_citation_in_reference_file_fails(tmp_path):
    # The scan covers references/*.md, not just SKILL.md, and labels the
    # file, matching the other two Portable citation checks.
    d = _write_raw(tmp_path, _portable_body("Clean body."),
                   references={"notes.md":
                               "Fictitious PR `#42` has just been opened.\n"})
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "references/notes.md:`#42`" in result.evidence


def test_double_backtick_code_span_citation_still_flagged(tmp_path):
    # Regression guard for a review finding: INLINE_CODE_RE's first cut
    # assumed every code span uses exactly one backtick on each side. A
    # double-backtick span (Markdown's own escape form for content that
    # itself needs a literal backtick) reads as two adjacent EMPTY
    # single-backtick spans under that assumption, so its content was never
    # inspected -- a citation using two backticks instead of one silently
    # evaded this check entirely. INLINE_CODE_RE now matches a same-length
    # closing delimiter run (1-3 backticks), so this must still be flagged.
    d = _write_raw(tmp_path, _portable_body(
        "Fictitious PR ``#42`` has just been opened."))
    result = _by_name(css.check_shape(d))["portable-no-unhedged-inline-issue-citation"]
    assert result.passed is False
    assert "``#42``" in result.evidence


# ---- Portability source precedence: sidecar first, body marker as fallback ----

# The three Portable-only citation checks -- gated by _is_portable, unlike
# no-bare-issue-citation, which is asserted separately in each test below
# since it is present regardless of the portability source under test
# (issue #254).
_PATH_CITATION_CHECKS = ("portable-no-repo-path-citation",
                         "portable-no-unhedged-inline-path-citation",
                         "portable-no-unhedged-inline-issue-citation")


def _write_sidecar(skill_dir, portability):
    (skill_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (skill_dir / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        f"  portability: {portability}\n"
        "  capabilityAssumption: Broad\n",
        encoding="utf-8")
    return skill_dir


def test_sidecar_portable_without_body_marker_runs_citation_scan(tmp_path):
    # The declaration form every skill in this repo now uses: the enum lives
    # only in the sidecar and the body carries no marker at all. The scan
    # must still run -- otherwise main's two path checks silently never fire.
    d = _write_sidecar(_write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "Self-contained body with no portability marker.\n"), "Portable")
    names = _by_name(css.check_shape(d))
    for check in _PATH_CITATION_CHECKS:
        assert check in names, check
    assert "no-bare-issue-citation" in names


def test_sidecar_mixed_without_body_marker_skips_path_scan_but_not_issue_scan(tmp_path):
    d = _write_sidecar(_write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "Handled in evals/foo/bar.yaml, first reported in issue #149.\n"),
        "Mixed")
    names = _by_name(css.check_shape(d))
    for check in _PATH_CITATION_CHECKS:
        assert check not in names, check
    # Mixed skips the two path checks, but not the bare-issue-citation scan
    # (issue #254): it runs regardless of portability and fails here.
    assert names["no-bare-issue-citation"].passed is False


def test_sidecar_beats_conflicting_body_marker(tmp_path):
    # Precedence, not mere presence: the body marker says Portable while the
    # sidecar says Mixed. The sidecar must win, so the path scan stays
    # skipped (the bare-issue-citation scan runs and fails either way).
    d = _write_sidecar(_write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability: Portable.** Self-contained.\n\n"
        "Handled in evals/foo/bar.yaml, first reported in issue #149.\n"),
        "Mixed")
    names = _by_name(css.check_shape(d))
    for check in _PATH_CITATION_CHECKS:
        assert check not in names, check
    assert names["no-bare-issue-citation"].passed is False


def test_body_marker_used_when_no_sidecar_present(tmp_path):
    # A skill vendored in from another repository: a marker, no sidecar.
    # The fallback path must run the scan rather than silently skipping it.
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability: Portable.** Self-contained.\n\n"
        "A clean portable body.\n")
    assert not (d / "metadata/gitapex.yaml").exists()
    names = _by_name(css.check_shape(d))
    for check in _PATH_CITATION_CHECKS:
        assert check in names, check
    assert "no-bare-issue-citation" in names


def test_unusable_sidecar_portability_runs_scan_regardless_of_body_marker(tmp_path):
    # A sidecar whose spec.portability is not a recognised level is
    # "unusable": _is_portable returns True unconditionally for it, WITHOUT
    # consulting the body marker -- a present sidecar is authoritative even
    # when broken (see _is_portable's docstring, state 3). Here the body
    # marker says Mixed; if the old fall-back-to-body-marker behavior were
    # still in effect, the path scan would be skipped. It must not be.
    d = _write_sidecar(_write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability: Mixed.** Repo-specific detail is split out.\n\n"
        "Handled in evals/foo/bar.yaml, first reported in issue #149.\n"),
        "SomewhatPortable")
    names = _by_name(css.check_shape(d))
    for check in _PATH_CITATION_CHECKS:
        assert check in names, check
    assert names["no-bare-issue-citation"].passed is False
    assert names["portable-no-repo-path-citation"].passed is False


def test_typo_portability_does_not_skip_citation_scan(tmp_path):
    # Confirmed defect this pass fixes: a typo'd spec.portability value
    # (e.g. "Portible") used to make the old _sidecar_portability() return
    # None, so _is_portable fell back to the (in this repo, always absent)
    # body marker and the Portable path-citation scan was silently skipped.
    # Now an unusable sidecar runs the scan unconditionally, so a bare #149
    # citation is caught (as it always would be, regardless of portability,
    # per issue #254), and portability-declared also fails -- the skill is
    # red on both checks instead of silently green on one of them.
    d = _write_sidecar(_write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "First reported in issue #149 of this project.\n"), "Portible")
    by = _by_name(css.check_shape(d))
    assert by["portability-declared"].passed is False
    assert "no-bare-issue-citation" in by
    assert by["no-bare-issue-citation"].passed is False
    assert "#149" in by["no-bare-issue-citation"].evidence

    # 3. sidecar absent + body marker Portable -> fallback still runs the
    #    scan: covered by test_body_marker_used_when_no_sidecar_present.
    # 4. sidecar Mixed while body marker says Portable -> sidecar wins,
    #    path-citation checks absent: covered by
    #    test_sidecar_beats_conflicting_body_marker.


# ---- references-well-formed ----

def test_references_absent_is_well_formed(tmp_path):
    d = _write_skill(tmp_path)
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is True
    assert by["references-well-formed"].evidence == "not declared (optional)"
    assert css.main([str(d)]) == 0


def test_references_valid_list_is_well_formed(tmp_path):
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - \"gitapex#25\"\n"
        "    - \"PR #29\"\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is True
    assert by["references-well-formed"].evidence == "2 entries"
    assert css.main([str(d)]) == 0


def test_references_empty_list_fails(tmp_path):
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is False
    assert by["references-well-formed"].evidence == "empty list"
    assert css.main([str(d)]) == 1


def test_references_blank_entry_fails(tmp_path):
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - \"gitapex#25\"\n"
        "    -    \n"
        "    - \"PR #29\"\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is False
    assert css.main([str(d)]) == 1


def test_references_non_list_scalar_fails(tmp_path):
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references: gitapex#25\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is False
    assert css.main([str(d)]) == 1


def test_references_well_formed_fails_when_sidecar_unreadable(tmp_path):
    d = _write_skill(tmp_path)
    sidecar = d / "metadata/gitapex.yaml"
    sidecar.write_bytes(b"\xff\xfe\x00\x01invalid")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is False


def test_manifest_parser_parses_spec_references_list():
    text = (
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - \"gitapex#25\"\n"
        "    - \"PR #29\"\n"
    )
    parsed = css._parse_manifest(text)
    assert parsed.root["spec"]["references"] == ["gitapex#25", "PR #29"]
    assert parsed.malformed_lines == []


def test_manifest_parser_parses_spec_skill_dependencies():
    # Sub-project D: unlike spec.evalStatus (still reserved and ungated),
    # spec.skillDependencies now gets a real parser, mirroring the
    # spec.references precedent one nesting level deeper.
    text = (
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Mixed\n"
        "  capabilityAssumption: Broad\n"
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - other-skill\n"
    )
    parsed = css._parse_manifest(text)
    assert parsed.root["spec"]["skillDependencies"] == {
        "requires": [], "relatedTo": ["other-skill"]}
    assert parsed.malformed_lines == []
    assert parsed.malformed_skill_dependency_items == []
    assert parsed.unknown_skill_dependency_keys == []


def test_manifest_parser_parses_spec_lifecycle():
    # One nesting level deeper than spec.skillDependencies: each sub-block
    # (experimental/deprecated) opens ANOTHER nested block of scalar
    # fields, rather than a list.
    text = (
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Mixed\n"
        "  capabilityAssumption: Broad\n"
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: \"#123\"\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: other-skill\n"
        "      since: \"2026-07-21\"\n"
    )
    parsed = css._parse_manifest(text)
    assert parsed.root["spec"]["lifecycle"] == {
        "experimental": {"reason": "not yet proven", "trackingIssue": "#123"},
        "deprecated": {"reason": "superseded", "replacement": "other-skill",
                        "since": "2026-07-21"},
    }
    assert parsed.malformed_lines == []
    assert parsed.unknown_lifecycle_keys == []
    assert parsed.unknown_lifecycle_fields == []


def test_manifest_parser_lifecycle_unknown_keys_are_collected():
    text = (
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Mixed\n"
        "  capabilityAssumption: Broad\n"
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      extraField: foo\n"
        "    stage: Beta\n"
    )
    parsed = css._parse_manifest(text)
    assert parsed.unknown_lifecycle_fields == ["extraField: foo"]
    assert parsed.unknown_lifecycle_keys == ["stage: Beta"]


def test_manifest_parser_still_ignores_eval_status():
    # Regression guard: spec.skillDependencies gaining a real parser must
    # not widen to spec.evalStatus (reserved for issue #185, untouched by
    # this sub-project).
    text = (
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  evalStatus:\n"
        "    baseline: 2026-01-01\n"
        "    lift: 0.2\n"
    )
    parsed = css._parse_manifest(text)
    assert "evalStatus" not in parsed.root["spec"]
    assert parsed.malformed_lines == []


def test_references_entries_decode_escaped_quotes():
    # Regression guard: _unquote must decode \" (and \\) inside a
    # double-quoted spec.references entry, not leave a literal backslash
    # in the parsed string -- the exact shape battle-testing-a-skill's
    # real sidecar entries use.
    text = (
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "    - \"a \\\"quoted\\\" phrase\"\n"
        "    - \"a literal backslash: \\\\\"\n"
    )
    parsed = css._parse_manifest(text)
    assert parsed.root["spec"]["references"] == [
        'a "quoted" phrase', "a literal backslash: \\"]


def test_unquote_falls_back_on_invalid_json_escaping():
    # _unquote decodes double-quoted values via json.loads; a value that
    # is not valid JSON (e.g. a stray unescaped inner quote) must fall back
    # to a naive strip rather than raising or propagating the exception.
    assert css._unquote('"bad "quote" here"') == 'bad "quote" here'


def test_references_list_item_at_two_space_indent_is_read(tmp_path):
    # Regression guard: a block-sequence item aligned with its own key
    # (2-space indent, same as "references:" itself) is valid YAML and
    # must be read, not silently dropped as an empty list.
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "  - \"gitapex#25\"\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is True
    assert by["references-well-formed"].evidence == "1 entry"


def test_references_list_item_at_three_space_indent_is_read(tmp_path):
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  capabilityAssumption: Broad\n"
        "  references:\n"
        "   - \"gitapex#25\"\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is True
    assert by["references-well-formed"].evidence == "1 entry"


def test_references_list_ended_by_a_following_sibling_key(tmp_path):
    # Regression guard for the mid-loop finalize path (as opposed to the
    # end-of-file finalize): spec.references followed by another spec key
    # must close the list correctly and not swallow the next key.
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        "  portability: Portable\n"
        "  references:\n"
        "    - \"a\"\n"
        "    - \"b\"\n"
        "  capabilityAssumption: Broad\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["references-well-formed"].passed is True
    assert by["references-well-formed"].evidence == "2 entries"
    assert by["capability-assumption-declared"].passed is True
    assert by["capability-assumption-declared"].evidence == "'Broad'"


def test_references_well_formed_fails_when_spec_is_not_a_mapping(tmp_path):
    # Regression guard: "spec: some-scalar" is the same precondition
    # failure portability-declared/capability-assumption-declared already
    # report -- references-well-formed must not misreport it as the
    # ordinary optional-and-absent case.
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec: not-a-mapping-scalar\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["portability-declared"].passed is False
    assert by["references-well-formed"].passed is False
    assert "not a mapping" in by["references-well-formed"].evidence


# ---- skill-dependencies-well-formed / skill-dependencies-resolve /
#      requires-portability-compatible (Sub-project D) ----

_SKILL_DEP_CHECKS = ("skill-dependencies-well-formed",
                     "skill-dependencies-resolve",
                     "requires-portability-compatible")


def _write_skill_deps_sidecar(d, body, *, portability="Mixed"):
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        f"  portability: {portability}\n"
        "  capabilityAssumption: Broad\n"
        f"{body}",
        encoding="utf-8")
    return d


def test_skill_dependencies_absent_is_well_formed(tmp_path):
    d = _write_skill(tmp_path)
    by = _by_name(css.check_shape(d))
    for check in _SKILL_DEP_CHECKS:
        assert by[check].passed is True, check
        assert by[check].evidence == "not declared (optional)"
    assert css.main([str(d)]) == 0


def test_skill_dependencies_valid_resolves_and_is_well_formed(tmp_path):
    (tmp_path / "other-skill").mkdir()
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - other-skill\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is True
    assert by["skill-dependencies-resolve"].passed is True
    assert by["skill-dependencies-resolve"].evidence == "all resolve"
    assert by["requires-portability-compatible"].passed is True
    assert css.main([str(d)]) == 0


def test_skill_dependencies_both_lists_empty_is_valid(tmp_path):
    # Unlike spec.references, an empty list is the expected common case for
    # requires, and relatedTo may legitimately be empty too (no siblings
    # mention this skill) -- neither is a failure.
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo: []\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is True
    assert by["skill-dependencies-resolve"].passed is True
    assert by["requires-portability-compatible"].passed is True
    assert css.main([str(d)]) == 0


def test_skill_dependencies_unknown_key_fails_well_formed(tmp_path):
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires: []\n"
        "    extra: foo\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is False
    assert "unknown key" in by["skill-dependencies-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_skill_dependencies_non_list_scalar_fails_well_formed(tmp_path):
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires: yes\n"
        "    relatedTo: []\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is False
    assert "requires is not a list" in by["skill-dependencies-well-formed"].evidence
    # The malformed subkey is treated as empty for the other two gates,
    # not silently trusted -- no dangling/contradiction false negative.
    assert by["skill-dependencies-resolve"].passed is True
    assert by["requires-portability-compatible"].passed is True
    assert css.main([str(d)]) == 1


def test_skill_dependencies_mapping_shaped_item_fails_well_formed(tmp_path):
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - name: other-skill\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is False
    assert "malformed entry" in by["skill-dependencies-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_skill_dependencies_inconsistent_indent_fails_well_formed(tmp_path):
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - \"a\"\n"
        "       - \"b\"\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is False
    assert css.main([str(d)]) == 1


def test_skill_dependencies_whole_field_wrong_type_fails_well_formed(tmp_path):
    d = _write_skill_deps_sidecar(_write_skill(tmp_path), "  skillDependencies: oops\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is False
    assert "not a mapping" in by["skill-dependencies-well-formed"].evidence
    assert by["skill-dependencies-resolve"].passed is True
    assert by["requires-portability-compatible"].passed is True


def test_skill_dependencies_dangling_requires_fails_resolve(tmp_path):
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires:\n"
        "      - ghost-skill\n"
        "    relatedTo: []\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is True
    assert by["skill-dependencies-resolve"].passed is False
    assert "ghost-skill" in by["skill-dependencies-resolve"].evidence
    assert css.main([str(d)]) == 1


def test_skill_dependencies_list_item_at_four_space_indent_is_read(tmp_path):
    # Regression guard: a block-sequence item aligned with its own key
    # (4-space indent, same as "requires:" itself) is valid YAML and must
    # be read, not silently dropped as an empty list -- mirrors
    # test_references_list_item_at_two_space_indent_is_read for the
    # sibling spec.references parser.
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires:\n"
        "    - ghost-skill\n"
        "    relatedTo: []\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is True
    assert by["skill-dependencies-resolve"].passed is False
    assert "ghost-skill" in by["skill-dependencies-resolve"].evidence
    assert css.main([str(d)]) == 1


def test_skill_dependencies_dangling_related_to_fails_resolve(tmp_path):
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo:\n"
        "      - ghost-skill\n")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-resolve"].passed is False
    assert "ghost-skill" in by["skill-dependencies-resolve"].evidence


def test_requires_portability_contradiction_fails_on_portable(tmp_path):
    (tmp_path / "other-skill").mkdir()
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires:\n"
        "      - other-skill\n"
        "    relatedTo: []\n",
        portability="Portable")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-resolve"].passed is True
    assert by["requires-portability-compatible"].passed is False
    assert "Portable" in by["requires-portability-compatible"].evidence
    assert css.main([str(d)]) == 1


def test_requires_non_empty_on_mixed_does_not_contradict(tmp_path):
    (tmp_path / "other-skill").mkdir()
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires:\n"
        "      - other-skill\n"
        "    relatedTo: []\n",
        portability="Mixed")
    by = _by_name(css.check_shape(d))
    assert by["requires-portability-compatible"].passed is True
    assert css.main([str(d)]) == 0


def test_requires_empty_on_portable_does_not_contradict(tmp_path):
    d = _write_skill_deps_sidecar(
        _write_skill(tmp_path),
        "  skillDependencies:\n"
        "    requires: []\n"
        "    relatedTo: []\n",
        portability="Portable")
    by = _by_name(css.check_shape(d))
    assert by["requires-portability-compatible"].passed is True
    assert css.main([str(d)]) == 0


def test_skill_dependencies_checks_fail_when_sidecar_unreadable(tmp_path):
    d = _write_skill(tmp_path)
    sidecar = d / "metadata/gitapex.yaml"
    sidecar.write_bytes(b"\xff\xfe\x00\x01invalid")
    by = _by_name(css.check_shape(d))
    for check in _SKILL_DEP_CHECKS:
        assert by[check].passed is False, check


def test_skill_dependencies_well_formed_fails_when_spec_is_not_a_mapping(tmp_path):
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec: not-a-mapping-scalar\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["skill-dependencies-well-formed"].passed is False
    assert "not a mapping" in by["skill-dependencies-well-formed"].evidence
    assert by["skill-dependencies-resolve"].passed is True
    assert by["requires-portability-compatible"].passed is True


# ---- lifecycle-well-formed / lifecycle-deprecated-replacement-resolves ----

_LIFECYCLE_CHECKS = ("lifecycle-well-formed",
                     "lifecycle-deprecated-replacement-resolves",
                     "experimental-stable-compatible")


def _write_lifecycle_sidecar(d, body, *, portability="Mixed"):
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec:\n"
        f"  portability: {portability}\n"
        "  capabilityAssumption: Broad\n"
        f"{body}",
        encoding="utf-8")
    return d


def test_lifecycle_absent_is_well_formed(tmp_path):
    d = _write_skill(tmp_path)
    by = _by_name(css.check_shape(d))
    for check in _LIFECYCLE_CHECKS:
        assert by[check].passed is True, check
        assert by[check].evidence == "not declared (optional)"
    assert css.main([str(d)]) == 0


def test_lifecycle_experimental_only_is_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: \"#123\"\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert "experimental" in by["lifecycle-well-formed"].evidence
    assert by["lifecycle-deprecated-replacement-resolves"].passed is True
    assert css.main([str(d)]) == 0


def test_lifecycle_deprecated_only_is_well_formed_and_resolves(tmp_path):
    (tmp_path / "other-skill").mkdir()
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: other-skill\n"
        "      since: \"2026-07-21\"\n"
        "      removeAfter: \"2026-10-01\"\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert by["lifecycle-deprecated-replacement-resolves"].passed is True
    assert by["lifecycle-deprecated-replacement-resolves"].evidence == "resolves"
    assert css.main([str(d)]) == 0


def test_lifecycle_both_blocks_present_is_valid(tmp_path):
    # Confirmed non-goal: no mutual-exclusion gate between experimental and
    # deprecated -- both present simultaneously is unusual but not an error
    # (unlike experimental+stable, which IS gated -- see
    # test_lifecycle_experimental_and_stable_fails_compatible below).
    (tmp_path / "other-skill").mkdir()
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: \"#123\"\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: other-skill\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert by["lifecycle-deprecated-replacement-resolves"].passed is True
    assert by["experimental-stable-compatible"].passed is True
    assert css.main([str(d)]) == 0


def test_lifecycle_missing_tracking_issue_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "trackingIssue" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_missing_replacement_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    deprecated:\n"
        "      reason: superseded\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "replacement" in by["lifecycle-well-formed"].evidence
    # The malformed sub-block is treated as absent for the resolve gate,
    # not silently trusted -- no false negative.
    assert by["lifecycle-deprecated-replacement-resolves"].passed is True
    assert css.main([str(d)]) == 1


def test_lifecycle_unknown_field_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: \"#123\"\n"
        "      extraField: foo\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "unknown field" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_unknown_top_level_key_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: \"#123\"\n"
        "    stage: Beta\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "unknown key" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_dangling_replacement_fails_resolve(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: ghost-skill\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert by["lifecycle-deprecated-replacement-resolves"].passed is False
    assert "ghost-skill" in by["lifecycle-deprecated-replacement-resolves"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_wrong_shape_date_fails_well_formed(tmp_path):
    (tmp_path / "other-skill").mkdir()
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: other-skill\n"
        "      since: \"2026/07/21\"\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "since" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_nonexistent_calendar_date_fails_well_formed(tmp_path):
    # Regression guard proving the datetime.date.fromisoformat layer, not
    # just LIFECYCLE_DATE_RE's shape check -- "2026-13-45" matches the
    # regex but is not a real calendar date.
    (tmp_path / "other-skill").mkdir()
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: other-skill\n"
        "      since: \"2026-13-45\"\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "since" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_malformed_tracking_issue_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: \"see the tracker\"\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "trackingIssue" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_whole_field_wrong_type_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(_write_skill(tmp_path), "  lifecycle: oops\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "not a mapping" in by["lifecycle-well-formed"].evidence
    assert by["lifecycle-deprecated-replacement-resolves"].passed is True
    assert by["experimental-stable-compatible"].passed is True


def test_lifecycle_sub_block_wrong_type_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental: true\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "experimental is not a mapping" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_stable_only_is_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    stable:\n"
        "      since: \"2026-07-21\"\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert "stable" in by["lifecycle-well-formed"].evidence
    assert by["experimental-stable-compatible"].passed is True
    assert css.main([str(d)]) == 0


def test_lifecycle_stable_with_compatibility_guarantee_is_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    stable:\n"
        "      since: \"2026-07-21\"\n"
        "      compatibilityGuarantee: GA\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert css.main([str(d)]) == 0


def test_lifecycle_stable_missing_since_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    stable:\n"
        "      compatibilityGuarantee: GA\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "stable.since" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_stable_invalid_compatibility_guarantee_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    stable:\n"
        "      since: \"2026-07-21\"\n"
        "      compatibilityGuarantee: Delta\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "compatibilityGuarantee" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_experimental_and_stable_fails_compatible(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: \"#123\"\n"
        "    stable:\n"
        "      since: \"2026-07-21\"\n")
    by = _by_name(css.check_shape(d))
    # Both sub-blocks are individually well-formed -- the contradiction is
    # its own check, independent of lifecycle-well-formed, mirroring how
    # requires-portability-compatible is independent of
    # skill-dependencies-well-formed.
    assert by["lifecycle-well-formed"].passed is True
    assert by["experimental-stable-compatible"].passed is False
    assert "both experimental and stable" in by["experimental-stable-compatible"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_renamed_from_valid_does_not_require_sibling_directory(tmp_path):
    # Deliberate asymmetry from deprecated.replacement: renamedFrom names
    # the skill's own former, now-nonexistent directory, so it must NOT be
    # resolved against sibling directories -- no ghost-skill-style dangling
    # check applies here.
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    renamedFrom: old-skill-name\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert css.main([str(d)]) == 0


def test_lifecycle_renamed_from_blank_is_read_as_absent(tmp_path):
    # Mirrors this parser's repo-wide convention: a blank scalar assignment
    # (e.g. "portability:" with nothing after it) reads as "not declared",
    # not as an explicit empty-string declaration.
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    renamedFrom:\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: other-skill\n")
    (tmp_path / "other-skill").mkdir()
    parsed = css._parse_manifest((d / "metadata/gitapex.yaml").read_text(encoding="utf-8"))
    assert "renamedFrom" not in parsed.root["spec"]["lifecycle"]
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True


def test_lifecycle_renamed_from_empty_string_fails_well_formed(tmp_path):
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    renamedFrom: \"\"\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "renamedFrom" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_unquoted_tracking_issue_is_read_as_bare_comment(tmp_path):
    # Regression guard (adversarial review finding): an unquoted value
    # that is nothing but a comment (starts with "#") must read as
    # absent, not as the literal string -- real YAML treats
    # "trackingIssue: #123" as trackingIssue: null, not "#123", even
    # though "#123" happens to be this exact field's valid shape.
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: #123\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "trackingIssue is missing" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_quoted_tracking_issue_starting_with_hash_still_valid(tmp_path):
    # Companion to the bare-comment regression above: a QUOTED value
    # starting with "#" is a real string in YAML, not a comment, and must
    # still validate normally.
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    experimental:\n"
        "      reason: not yet proven\n"
        "      trackingIssue: \"#123\"\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert css.main([str(d)]) == 0


def test_lifecycle_renamed_from_given_a_block_fails_well_formed(tmp_path):
    # Regression guard (adversarial review finding): renamedFrom is
    # documented as a plain scalar, not a sub-block -- a nested mapping
    # given where a scalar is expected must fail the same way
    # "experimental: true" (a scalar given where a mapping is expected)
    # already does, not silently vanish as "not declared".
    (tmp_path / "other-skill").mkdir()
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    renamedFrom:\n"
        "      old: name\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: other-skill\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "renamedFrom is not a non-empty string" in by["lifecycle-well-formed"].evidence
    assert css.main([str(d)]) == 1


def test_lifecycle_renamed_from_only_evidence_names_it(tmp_path):
    # Regression guard (adversarial review finding): the "declared"
    # evidence string must name renamedFrom when it is the only field
    # present, not report "no keys declared" for a sidecar that did
    # declare something.
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    renamedFrom: old-skill-name\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert "renamedFrom" in by["lifecycle-well-formed"].evidence
    assert by["lifecycle-well-formed"].evidence != "no keys declared"


def test_lifecycle_stable_and_deprecated_coexist(tmp_path):
    # A graduated skill later superseded by another is a normal lifecycle
    # progression -- only experimental+stable is gated, not
    # deprecated+stable.
    (tmp_path / "other-skill").mkdir()
    d = _write_lifecycle_sidecar(
        _write_skill(tmp_path),
        "  lifecycle:\n"
        "    stable:\n"
        "      since: \"2026-01-01\"\n"
        "    deprecated:\n"
        "      reason: superseded\n"
        "      replacement: other-skill\n")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is True
    assert by["experimental-stable-compatible"].passed is True
    assert css.main([str(d)]) == 0


def test_lifecycle_checks_fail_when_sidecar_unreadable(tmp_path):
    d = _write_skill(tmp_path)
    sidecar = d / "metadata/gitapex.yaml"
    sidecar.write_bytes(b"\xff\xfe\x00\x01invalid")
    by = _by_name(css.check_shape(d))
    for check in _LIFECYCLE_CHECKS:
        assert by[check].passed is False, check


def test_lifecycle_well_formed_fails_when_spec_is_not_a_mapping(tmp_path):
    d = _write_skill(tmp_path)
    (d / "metadata/gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        "  name: skill\n"
        "spec: not-a-mapping-scalar\n",
        encoding="utf-8")
    by = _by_name(css.check_shape(d))
    assert by["lifecycle-well-formed"].passed is False
    assert "not a mapping" in by["lifecycle-well-formed"].evidence
    assert by["lifecycle-deprecated-replacement-resolves"].passed is True
    assert by["experimental-stable-compatible"].passed is True
