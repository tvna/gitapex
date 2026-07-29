"""Tests for the security-relevance heuristic
(.github/scripts/skill_security_relevance.py).

Issue #517 (refs #454): heuristically flag a skill as security-relevant by
keyword match against its frontmatter block only, not its full body.
Replaces an earlier bash `sed -n '/^---$/,/^---$/p'` implementation whose
range address re-arms on any later '---' line in the body (e.g. a
markdown horizontal rule), leaking unrelated body prose into the scan.
"""

from __future__ import annotations

import io

import skill_security_relevance as mod

_WELL_FORMED = """\
---
name: foo
description: Use when checking security gate trust boundaries.
---

# Foo

Body text unrelated to frontmatter keywords.
"""

_NO_KEYWORD = """\
---
name: foo
description: Use when you need to aggregate and delegate ordinary tasks.
---

# Foo

Body mentions security and gate and trust, but that is body prose.
"""


def test_relevant_keyword_in_frontmatter_detected():
    assert mod.is_security_relevant(_WELL_FORMED) is True


def test_keyword_only_in_body_not_frontmatter_is_not_relevant():
    assert mod.is_security_relevant(_NO_KEYWORD) is False


def test_no_frontmatter_at_all_is_not_relevant():
    assert mod.is_security_relevant("# Foo\n\nsecurity gate trust\n") is False


def test_malformed_frontmatter_with_no_closing_delimiter_anywhere_fails_closed():
    # No second '---' line anywhere in the file -- genuinely malformed
    # frontmatter (missing closing delimiter). Must be treated as "no
    # frontmatter" (fail closed) rather than scanning to EOF, unlike the
    # original sed-based implementation this replaces.
    text = (
        "---\n"
        "name: foo\n"
        "description: ordinary skill, no closing delimiter anywhere\n"
        "\n"
        "# Foo\n"
        "\n"
        "This body has no horizontal rule at all, and mentions security "
        "and gate and trust.\n"
    )
    assert mod.extract_frontmatter(text) is None
    assert mod.is_security_relevant(text) is False


def test_horizontal_rule_in_body_does_not_leak_into_frontmatter_scan():
    # Well-formed frontmatter (no keyword), followed by a body containing
    # a horizontal rule and then a security-relevant word -- must not be
    # flagged, since that word is in the body, past the closing delimiter.
    text = (
        "---\n"
        "name: foo\n"
        "description: ordinary skill\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "---\n"
        "\n"
        "This paragraph after a horizontal rule mentions security and "
        "gate and trust.\n"
    )
    assert mod.is_security_relevant(text) is False


def test_word_boundary_excludes_aggregate_delegate_negotiate():
    text = (
        "---\n"
        "name: foo\n"
        "description: Use when you aggregate, delegate, and negotiate "
        "ordinary bookkeeping tasks.\n"
        "---\n"
    )
    assert mod.is_security_relevant(text) is False


def test_word_boundary_includes_gated_gateway_trusted_trustworthy():
    for word in ("gated", "gateway", "trusted", "trustworthy"):
        text = f"---\nname: foo\ndescription: Use for {word} workflows.\n---\n"
        assert mod.is_security_relevant(text) is True, word


def test_extract_frontmatter_returns_none_for_no_leading_delimiter():
    assert mod.extract_frontmatter("no frontmatter here\n") is None


def test_extract_frontmatter_returns_none_for_empty_text():
    assert mod.extract_frontmatter("") is None
    assert mod.extract_frontmatter(None) is None


def test_extract_frontmatter_returns_bounded_block():
    text = "---\nname: foo\n---\nBody\n"
    assert mod.extract_frontmatter(text) == "---\nname: foo\n---"


# --- main() ---


def test_main_prints_relevant(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_WELL_FORMED))
    assert mod.main([]) == 0
    assert capsys.readouterr().out.strip() == "relevant"


def test_main_prints_not_relevant(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(_NO_KEYWORD))
    assert mod.main([]) == 0
    assert capsys.readouterr().out.strip() == "not-relevant"


def test_main_reads_from_file(tmp_path, capsys):
    path = tmp_path / "SKILL.md"
    path.write_text(_WELL_FORMED, encoding="utf-8")
    assert mod.main(["--path", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "relevant"


def test_main_reports_error_for_missing_file(capsys):
    assert mod.main(["--path", "/no/such/file.md"]) == 1
    assert "not found" in capsys.readouterr().err
