"""Deterministic shape checker for a SKILL.md and its references/ dir.

Single source of truth for the deterministic "shape" lane of the
evaluating-skill-quality skill. It decides only the mechanically
checkable rules; the nine maturity dimensions stay model-judged and are
deliberately NOT implemented here.

Read-only: reads the target skill's files only. No writes, no network,
no mutation. Effects are limited to stdout and the process exit code.

Checks (the canonical list -- the manual fallback is to apply these):
  - description: present/non-empty, no XML tags, <= 1024 chars
  - name (only if present): lowercase-hyphenated, <= 64 chars,
    no XML tags, contains no reserved word (anthropic, claude)
  - SKILL.md body: <= 500 lines
  - portability declaration: appears within the first 6 body lines
    (a "Portability:" marker, e.g. "**Portability: Portable.**")
  - references/ files: exactly one level deep
  - any references/ file over 100 lines: contains a table of contents
    (a Markdown heading matching "Table of contents" or "Contents",
    case-insensitive). Junk files (dotfiles, __pycache__, non-UTF-8) under
    references/ are ignored, not flagged.
  - SKILL.md body: every Markdown link target -- inline ([text](path))
    or reference-style ([text][label] resolved via a [label]: path
    definition) -- that is not an absolute URL/scheme (http(s):,
    mailto:, etc.) or a bare in-page fragment (#section) must resolve
    inside the skill's own directory -- a relative link that escapes it
    (e.g. "../../docs/x.md") fails. This
    gives the skill's own "Portable" self-declaration (whose definition
    already requires every instruction to resolve inside the skill's own
    folder) a deterministic backstop.
  - Portable self-citation (only when the skill declares "Portable", not
    "Mixed" or "Repository-scoped"): no bare-prose GitHub issue/PR-number
    citation (#149 or owner/repo#149) and no bare-prose origin-repository
    path citation (evals/... or docs/...) in SKILL.md or references/*.md
    body text. A bare #N auto-links relative to whichever repository
    currently hosts the file and silently resolves to the wrong issue
    once the skill is vendored; a repo-relative path breaks the same way.
    Matches inside inline code (`#149`), fenced code blocks, absolute
    URLs, and Markdown links are excluded -- those are the established
    ways this repo's Portable skills quote such a token illustratively
    without it resolving live. This is the deterministic backstop for the
    rubric's dimension-6 Portable-skill rule; the semantic judgment of
    whether a citation is illustrative context vs. the skill's own
    bookkeeping stays with that model-judged dimension.

Usage:
  python3 check_skill_shape.py <skill-dir-or-SKILL.md>

Exit code: 0 if every check passes, 1 if any check fails, 2 on bad usage or
when no readable SKILL.md is found.
"""
from __future__ import annotations

import argparse
import os.path
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# The Claude Developer Platform Skills API enforces description <= 1024
# chars and name <= 64 lowercase-hyphen chars (platform.claude.com/docs/
# en/agents-and-tools/agent-skills/best-practices) -- stricter than Claude
# Code's own frontmatter parsing, so this checker uses the platform's
# tighter cap to stay valid on both surfaces.
DESCRIPTION_MAX_CHARS = 1024
NAME_MAX_CHARS = 64
# "Keep SKILL.md body under 500 lines for optimal performance" (same doc;
# also code.claude.com/docs/en/skills).
BODY_MAX_LINES = 500
# Not an Anthropic-specified number -- this repository's own convention
# for when a reference file earns a table of contents, chosen as a round
# threshold past which skimming a flat file gets slow.
TOC_MIN_LINES = 100
RESERVED_NAME_WORDS = ("anthropic", "claude")

TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Accept either "Table of contents" or a bare "Contents" heading.
TOC_RE = re.compile(r"^#+\s+(?:table of )?contents\b",
                    re.IGNORECASE | re.MULTILINE)
PORTABILITY_RE = re.compile(r"\bportability\s*:", re.IGNORECASE)
PORTABILITY_MAX_BODY_LINE = 6
BLOCK_SCALAR_INDICATORS = (">", "|", ">-", "|-", ">+", "|+")
# Markdown inline link syntax: [text](target).
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Reference-style link definitions: [label]: target -- the destination a
# [text][label] reference resolves to. Up to 3 leading spaces per
# CommonMark; destination is either <...>-wrapped or a bare non-space run.
REFDEF_RE = re.compile(r"^[ ]{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)", re.MULTILINE)
# An absolute-URL scheme (http:, https:, mailto:, ftp:, ...) -- anything
# matching this is external, not a same-repo relative path.
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

# Portable self-citation scan (see the module docstring). A skill counts as
# Portable only when its portability marker says "Portable" without the
# "Mixed" / "Repository-scoped" qualifiers -- those levels legitimately cite
# repo-specific paths and issues, so the scan does not apply to them.
PORTABLE_LEVEL_RE = re.compile(r"\bportable\b", re.IGNORECASE)
NON_PORTABLE_LEVEL_RE = re.compile(r"\b(?:mixed|repository-scoped|repo-scoped)\b",
                                   re.IGNORECASE)
# A GitHub issue/PR-number citation: an optional "owner/repo" prefix, then
# "#" and a digit run. The trailing (?![\d-]) rejects an in-page anchor slug
# like "#1-discovery" (a digit run followed by "-word"); a real citation ends
# at the digits.
ISSUE_CITATION_RE = re.compile(
    r"(?:[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*)?#\d+(?![\d-])")
# An origin-repository path citation rooted at this repo's own top-level
# tooling dirs. Kept deliberately narrow (evals/ and docs/) -- the two roots
# the historical incidents used -- rather than every path shape, so the scan
# stays a low-false-positive backstop, not a general path linter.
REPO_PATH_CITATION_RE = re.compile(r"(?:evals|docs)/[A-Za-z0-9._/-]+")
# A run of Markdown "already illustrative / already external" syntax whose
# contents must not be scanned: a fenced code block (``` ... ```), an inline
# code span (`...`), an absolute URL, an inline link ([text](target)), a
# reference-style link ([text][label]), or a reference definition
# ([label]: target). Stripping these leaves only bare prose.
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
BARE_URL_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s>)\]]+")
MD_INLINE_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
MD_REF_LINK_RE = re.compile(r"\[[^\]]*\]\[[^\]]*\]")
MD_REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s.*$")


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    rule: str
    evidence: str


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract top-level 'key: value' pairs from a leading --- block.

    Handles the scalar forms real SKILL.md files use: plain, single/double
    quoted, and YAML block scalars (folded '>' and literal '|', whose
    indented continuation lines are joined). Strips a leading UTF-8 BOM and
    requires a closing '---'; without one the frontmatter is treated as
    malformed (returns {}), rather than reading body lines as fields. No
    external YAML dependency.
    """
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines))
                if lines[i].strip() == "---"), None)
    if end is None:
        return {}
    fields: dict[str, str] = {}
    i = 1
    while i < end:
        m = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if value in BLOCK_SCALAR_INDICATORS:
            block: list[str] = []
            i += 1
            while i < end and (lines[i].strip() == ""
                               or lines[i][:1] in (" ", "\t")):
                block.append(lines[i].strip())
                i += 1
            joiner = "\n" if value[0] == "|" else " "
            fields[key] = joiner.join(block).strip()
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
        i += 1
    return fields


def _body_after_frontmatter(text: str) -> list[str]:
    """Lines after the closing frontmatter '---'. If there is no
    frontmatter, the whole text is the body."""
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    lines = text.splitlines()
    if not text.startswith("---"):
        return lines
    end = next((i for i in range(1, len(lines))
                if lines[i].strip() == "---"), None)
    if end is None:
        return lines
    return lines[end + 1:]


def _is_ignorable(p: Path) -> bool:
    """Junk that must not affect the references/ checks: dotfiles (e.g. a
    macOS .DS_Store) and Python bytecode caches."""
    return p.name.startswith(".") or "__pycache__" in p.parts


def _out_of_skill_link_targets(body_text: str, skill_dir: Path) -> list[str]:
    """Return each Markdown link target in ``body_text`` that resolves
    outside ``skill_dir``.

    Covers both inline links ([text](target)) and reference-style links
    ([text][label] resolved via a [label]: target definition elsewhere in
    the body) -- a reference-style target is exactly as capable of
    escaping the skill directory as an inline one. Skips absolute-URL/
    scheme targets (http:, https:, mailto:, ...) and bare in-page
    fragments (#section) -- neither is a same-repo relative path.
    Resolution is purely lexical (os.path.normpath), not a real
    filesystem lookup, since the target need not exist for this check.
    """
    skill_norm = os.path.normpath(str(skill_dir))
    raw_targets = [m.group(1) for m in LINK_RE.finditer(body_text)]
    raw_targets += [m.group(1) for m in REFDEF_RE.finditer(body_text)]
    offenders = []
    for raw in raw_targets:
        target = raw.strip()
        if len(target) >= 2 and target[0] == "<" and target[-1] == ">":
            target = target[1:-1].strip()
        if SCHEME_RE.match(target):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0].strip()
        if not path_part:
            continue  # fragment-only or query-only link
        if os.path.isabs(path_part):
            normalized = os.path.normpath(path_part)
        else:
            normalized = os.path.normpath(os.path.join(skill_norm, path_part))
        if normalized != skill_norm and not normalized.startswith(skill_norm + os.sep):
            offenders.append(target)
    return offenders


def _is_portable(body: list[str]) -> bool:
    """Whether the skill declares itself Portable (not Mixed/Repository-scoped).

    Reads the same near-top portability marker the ``portability-near-top``
    check locates. "Mixed" and "Repository-scoped" skills legitimately cite
    repo-specific paths and issues, so the Portable self-citation scan does
    not apply to them.
    """
    for line in body[:PORTABILITY_MAX_BODY_LINE]:
        if PORTABILITY_RE.search(line):
            return bool(PORTABLE_LEVEL_RE.search(line)) and not NON_PORTABLE_LEVEL_RE.search(line)
    return False


def _strip_illustrative_spans(body_text: str) -> str:
    """Return ``body_text`` with every span that quotes a token
    illustratively or externally removed, leaving only bare prose.

    Removes fenced code blocks wholesale, then per surviving line strips
    inline code spans, absolute URLs, Markdown inline/reference links, and
    reference definitions. These are exactly the forms in which this repo's
    Portable skills already write an issue number or repo path without it
    resolving live (an inline-code ``#149``, a full URL, a ``[PR #2][pr2]``
    worked-example link), so what remains is a citation sitting unguarded in
    running prose -- the shape the historical incidents took.
    """
    out: list[str] = []
    in_fence = False
    for line in body_text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        if MD_REF_DEF_RE.match(line):
            out.append("")
            continue
        stripped = INLINE_CODE_RE.sub(" ", line)
        stripped = BARE_URL_RE.sub(" ", stripped)
        stripped = MD_INLINE_LINK_RE.sub(" ", stripped)
        stripped = MD_REF_LINK_RE.sub(" ", stripped)
        out.append(stripped)
    return "\n".join(out)


def _portable_citation_offenders(body_text: str) -> tuple[list[str], list[str]]:
    """Return (issue-number, repo-path) bare-prose citations in ``body_text``.

    Applies the illustrative-span strip first, so only citations left
    unguarded in running prose are reported. Order-preserving and
    deduplicated so the evidence string is stable and terse.
    """
    prose = _strip_illustrative_spans(body_text)
    issues = _dedup(m.group(0) for m in ISSUE_CITATION_RE.finditer(prose))
    paths = _dedup(m.group(0) for m in REPO_PATH_CITATION_RE.finditer(prose))
    return issues, paths


def _dedup(items) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)


def _no_xml_check(field: str, value: str) -> CheckResult:
    has_tag = bool(TAG_RE.search(value))
    return CheckResult(
        f"{field}-no-xml", not has_tag, f"{field} has no XML tags",
        "tag found" if has_tag else "no tags")


def _length_check(field: str, value: str, limit: int) -> CheckResult:
    return CheckResult(
        f"{field}-length", len(value) <= limit,
        f"{field} <= {limit} chars", f"{len(value)} chars")


def _resolve_skill_md(target: Path) -> Path:
    return target / "SKILL.md" if target.is_dir() else target


def check_shape(target: Path) -> list[CheckResult]:
    skill_md = _resolve_skill_md(target)
    skill_dir = skill_md.parent
    results: list[CheckResult] = []

    text = skill_md.read_text(encoding="utf-8")
    fields = _parse_frontmatter(text)

    description = fields.get("description", "")
    if not description:
        results.append(CheckResult(
            "description-present", False,
            "description present and non-empty", "missing or empty"))
    else:
        results.append(CheckResult(
            "description-present", True,
            "description present and non-empty", "present"))
        results.append(_no_xml_check("description", description))
        results.append(_length_check(
            "description", description, DESCRIPTION_MAX_CHARS))

    name = fields.get("name")
    if name:
        results.append(CheckResult(
            "name-pattern", bool(NAME_RE.match(name)),
            "name is lowercase-hyphenated", repr(name)))
        results.append(_length_check("name", name, NAME_MAX_CHARS))
        results.append(_no_xml_check("name", name))
        lname = name.lower()
        reserved_hit = any(word in lname for word in RESERVED_NAME_WORDS)
        results.append(CheckResult(
            "name-not-reserved", not reserved_hit,
            f"name contains no reserved word {RESERVED_NAME_WORDS}",
            repr(name)))

    body_lines = len(text.splitlines())
    results.append(CheckResult(
        "body-length", body_lines <= BODY_MAX_LINES,
        f"SKILL.md body <= {BODY_MAX_LINES} lines", f"{body_lines} lines"))

    body = _body_after_frontmatter(text)
    near_top = any(PORTABILITY_RE.search(line)
                   for line in body[:PORTABILITY_MAX_BODY_LINE])
    results.append(CheckResult(
        "portability-near-top", near_top,
        f"a portability declaration appears within the first "
        f"{PORTABILITY_MAX_BODY_LINE} body lines",
        "found" if near_top else
        f"missing or below body line {PORTABILITY_MAX_BODY_LINE}"))

    offenders = _out_of_skill_link_targets("\n".join(body), skill_dir)
    results.append(CheckResult(
        "links-inside-skill", not offenders,
        "Markdown link targets resolve inside the skill's own directory",
        "all inside" if not offenders else "outside: " + ", ".join(offenders)))

    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        nested = sorted(
            str(p.relative_to(refs_dir)) for p in refs_dir.rglob("*")
            if p.is_file() and p.parent != refs_dir and not _is_ignorable(p))
        results.append(CheckResult(
            "references-flat", not nested,
            "references/ files are one level deep",
            "nested: " + ", ".join(nested) if nested else "flat"))
        for ref in sorted(refs_dir.iterdir()):
            if not ref.is_file() or _is_ignorable(ref):
                continue
            try:
                ref_text = ref.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # skip binary/unreadable junk, don't abort the run
            n = len(ref_text.splitlines())
            if n > TOC_MIN_LINES:
                has_toc = bool(TOC_RE.search(ref_text))
                results.append(CheckResult(
                    f"toc:{ref.name}", has_toc,
                    f"reference over {TOC_MIN_LINES} lines has a TOC",
                    f"{n} lines, " + ("TOC found" if has_toc else "no TOC")))

    if _is_portable(body):
        results.extend(_portable_citation_checks(skill_md, skill_dir, body))

    return results


def _portable_citation_checks(skill_md: Path, skill_dir: Path,
                              body: list[str]) -> list[CheckResult]:
    """The two Portable self-citation checks over SKILL.md body and
    references/*.md. Each source contributes its offenders labelled by file,
    so a failure points at the exact file to fix.
    """
    sources: list[tuple[str, str]] = [(skill_md.name, "\n".join(body))]
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref in sorted(refs_dir.iterdir()):
            if not ref.is_file() or _is_ignorable(ref):
                continue
            try:
                ref_text = ref.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            sources.append((f"references/{ref.name}",
                            "\n".join(_body_after_frontmatter(ref_text))))

    issue_hits: list[str] = []
    path_hits: list[str] = []
    for label, source_text in sources:
        issues, paths = _portable_citation_offenders(source_text)
        issue_hits += [f"{label}:{c}" for c in issues]
        path_hits += [f"{label}:{c}" for c in paths]

    return [
        CheckResult(
            "portable-no-issue-citation", not issue_hits,
            "Portable content has no bare-prose GitHub issue/PR-number citation",
            "none" if not issue_hits else "found: " + ", ".join(issue_hits)),
        CheckResult(
            "portable-no-repo-path-citation", not path_hits,
            "Portable content has no bare-prose origin-repository path citation",
            "none" if not path_hits else "found: " + ", ".join(path_hits)),
    ]


def format_report(results: list[CheckResult]) -> str:
    width = max((len(r.name) for r in results), default=5)
    lines = [f"{'CHECK'.ljust(width)}  RESULT  EVIDENCE (rule)"]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"{r.name.ljust(width)}  {status}    "
                     f"{r.evidence}  ({r.rule})")
    passed = sum(1 for r in results if r.passed)
    lines.append(f"\n{passed}/{len(results)} checks passed")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a SKILL.md's deterministic shape (read-only).")
    parser.add_argument(
        "target", help="Path to a skill directory or a SKILL.md file.")
    args = parser.parse_args(argv)
    target = Path(args.target)
    skill_md = _resolve_skill_md(target)
    if not skill_md.is_file():
        print(f"error: no SKILL.md found at: {target}", file=sys.stderr)
        return 2
    try:
        results = check_shape(target)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: could not read skill files: {exc}", file=sys.stderr)
        return 2
    print(format_report(results))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
