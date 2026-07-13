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

Usage:
  python3 check_skill_shape.py <skill-dir-or-SKILL.md>

Exit code: 0 if every check passes, 1 if any check fails, 2 on bad usage or
when no readable SKILL.md is found.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DESCRIPTION_MAX_CHARS = 1024
NAME_MAX_CHARS = 64
BODY_MAX_LINES = 500
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

    return results


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
