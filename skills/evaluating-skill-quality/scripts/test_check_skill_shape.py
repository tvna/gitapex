"""Tests for the deterministic shape checker.

Fixtures are synthesized in tmp_path so the test is self-contained and
travels with the skill on vendoring.
"""
from pathlib import Path

import pytest

import check_skill_shape as css


def _write_skill(tmp_path, *, name="good-skill",
                 description="Does a thing. Use when doing the thing.",
                 body_lines=10, references=None):
    d = tmp_path / "skill"
    d.mkdir()
    fm = ["---"]
    if name is not None:
        fm.append(f"name: {name}")
    if description is not None:
        fm.append(f"description: {description}")
    fm.append("---")
    portability = "**Portability: Portable.** Self-contained."
    filler = "\n".join(f"line {i}" for i in range(body_lines))
    (d / "SKILL.md").write_text(
        "\n".join(fm) + "\n\n" + portability + "\n\n" + filler + "\n",
        encoding="utf-8")
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
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability: Portable.** Self-contained.\n",
        references={"real.md": "ok\n"})
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


def test_portability_near_top_pass(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n\n"
        "# Title\n\n**Portability: Portable.** Self-contained.\n\nBody.\n",
        encoding="utf-8")
    results = css.check_shape(d / "SKILL.md")
    assert _result(results, "portability-near-top").passed


def test_portability_near_top_bold_colon_form(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n\n"
        "# Title\n\n**Portability:** Portable. Self-contained.\n\nBody.\n",
        encoding="utf-8")
    results = css.check_shape(d / "SKILL.md")
    assert _result(results, "portability-near-top").passed


def test_portability_near_top_missing_fails(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n\n# Title\n\nBody with no marker.\n",
        encoding="utf-8")
    results = css.check_shape(d / "SKILL.md")
    assert not _result(results, "portability-near-top").passed


def test_portability_near_top_buried_fails(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    filler = "\n".join(f"line {i}" for i in range(10))
    (d / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n\n# Title\n\n" + filler
        + "\n\n**Portability: Portable.** declared too low.\n",
        encoding="utf-8")
    results = css.check_shape(d / "SKILL.md")
    assert not _result(results, "portability-near-top").passed


def test_out_of_skill_link_fails(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability: Portable.** Self-contained.\n\n"
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
        "**Portability: Portable.** Self-contained.\n\n"
        "## Notes\n\nSee [background](references/foo.md) for context.\n",
        references={"foo.md": "background\n"})
    assert _result(css.check_shape(d), "links-inside-skill").passed


def test_absolute_url_link_is_skipped(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability: Portable.** Self-contained.\n\n"
        "See [the spec](https://example.com/y) for background.\n")
    assert _result(css.check_shape(d), "links-inside-skill").passed


def test_fragment_only_link_is_skipped(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability: Portable.** Self-contained.\n\n"
        "Jump to [the checklist](#checklist) below.\n")
    assert _result(css.check_shape(d), "links-inside-skill").passed


def test_absolute_path_link_fails(tmp_path):
    d = _write_raw(
        tmp_path,
        "---\nname: s\ndescription: d. Use when x.\n---\n\n"
        "**Portability: Portable.** Self-contained.\n\n"
        "See [system config](/etc/passwd) for context.\n")
    result = _result(css.check_shape(d), "links-inside-skill")
    assert not result.passed
    assert "/etc/passwd" in result.evidence
