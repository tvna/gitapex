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
    no XML tags, not a reserved word (anthropic, claude)
  - SKILL.md body: <= 500 lines
  - references/ files: exactly one level deep
  - any references/ file over 100 lines: contains a table of contents
    (a Markdown heading line matching "table of contents", case-insensitive)

Usage:
  python3 check_skill_shape.py <skill-dir-or-SKILL.md>

Exit code: 0 if every check passes, 1 if any check fails, 2 on bad usage or
when no readable SKILL.md is found.
"""
from __future__ import annotations

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
TOC_RE = re.compile(r"^#+\s+.*table of contents", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    rule: str
    evidence: str


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract top-level 'key: value' pairs from a leading --- block.

    Deliberately minimal: handles the single-line scalar values these
    skills use (name, description). No external YAML dependency.
    """
    if not text.startswith("---"):
        return {}
    fields: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


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
        has_tag = bool(TAG_RE.search(description))
        results.append(CheckResult(
            "description-no-xml", not has_tag,
            "description has no XML tags",
            "tag found" if has_tag else "no tags"))
        results.append(CheckResult(
            "description-length", len(description) <= DESCRIPTION_MAX_CHARS,
            f"description <= {DESCRIPTION_MAX_CHARS} chars",
            f"{len(description)} chars"))

    name = fields.get("name")
    if name:
        results.append(CheckResult(
            "name-pattern", bool(NAME_RE.match(name)),
            "name is lowercase-hyphenated", repr(name)))
        results.append(CheckResult(
            "name-length", len(name) <= NAME_MAX_CHARS,
            f"name <= {NAME_MAX_CHARS} chars", f"{len(name)} chars"))
        has_tag = bool(TAG_RE.search(name))
        results.append(CheckResult(
            "name-no-xml", not has_tag,
            "name has no XML tags", "tag found" if has_tag else "no tags"))
        results.append(CheckResult(
            "name-not-reserved", name.lower() not in RESERVED_NAME_WORDS,
            f"name not a reserved word {RESERVED_NAME_WORDS}", repr(name)))

    body_lines = len(text.splitlines())
    results.append(CheckResult(
        "body-length", body_lines <= BODY_MAX_LINES,
        f"SKILL.md body <= {BODY_MAX_LINES} lines", f"{body_lines} lines"))

    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        nested = [p for p in refs_dir.rglob("*")
                  if p.is_file() and p.parent != refs_dir]
        results.append(CheckResult(
            "references-flat", not nested,
            "references/ files are one level deep",
            "nested: " + ", ".join(sorted(str(p.relative_to(refs_dir))
                                          for p in nested))
            if nested else "flat"))
        for ref in sorted(refs_dir.glob("*")):
            if not ref.is_file():
                continue
            ref_text = ref.read_text(encoding="utf-8")
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


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python3 check_skill_shape.py <skill-dir-or-SKILL.md>",
              file=sys.stderr)
        return 2
    target = Path(argv[1])
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
    raise SystemExit(main(sys.argv))
