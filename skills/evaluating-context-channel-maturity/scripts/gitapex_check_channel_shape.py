#!/usr/bin/env python3
"""Deterministic shape checker for the context channels this skill grades.

Issue #1963: `evaluating-skill-quality` has a deterministic shape layer
with numeric threshold constants underneath its rubric;
`evaluating-context-channel-maturity` had only the rubric, and that rubric
carried no numbers at all. This script is that missing layer. It grades
*arithmetic* -- characters, lines, an estimated token count -- and nothing
else. Whether a description carries a routing contract or a record of the
decision that produced it is axis B1's question, not this script's: a
description can sit inside every threshold below and still fail B1, which
is exactly why the two layers are separate.

Deliberately self-contained. It shares no module with
`evaluating-skill-quality`'s own `shape_checks/` package even though the
two solve the same shape of problem, because `docs/repository-layout.md`
puts `skills/` on the deployed side and `.github/`, `docs/` and `tests/`
on the never-deployed side: a shared module would have to live somewhere,
and the only places that are not another skill's private directory are on
the never-deployed side, which would break this checker's own
standalone execution once the plugin is installed. Every other
`skills/*/scripts/*.py` in this repository follows the same rule -- the
standard library plus same-directory imports, never a sibling skill's
module.

Two channel kinds are graded, because they are the two this repository
actually owns instances of:

- **subagent definition** (`agents/*.md`, `.claude/agents/*.md`, or any
  path given explicitly): YAML frontmatter with a `description`, and a
  Markdown body that serves as that subagent's system prompt.
- **project instruction** (`AGENTS.md`, `CLAUDE.md`, or any path given
  explicitly with `--kind project-instruction`): no frontmatter required;
  graded on length only.

Fails closed. A file that cannot be read, cannot be decoded as UTF-8, or
whose frontmatter is absent, unterminated, or missing `description` is
reported as a failure, never skipped and never silently passed -- an
unparseable channel is exactly the case where a size claim cannot be
trusted.

Usage:
  python3 gitapex_check_channel_shape.py --kind subagent PATH [PATH ...]
  python3 gitapex_check_channel_shape.py --kind project-instruction AGENTS.md

Exit codes: 0 every graded file passed; 1 at least one threshold was
exceeded or a file failed closed; 2 a usage error (no paths given, or an
unknown --kind).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# A subagent `description` is a routing contract that rides in EVERY
# request, so its cost is paid per request rather than per dispatch. No
# primary source publishes a per-file cap -- the Claude Code subagent
# documentation gives only a *combined* 15,000-token startup warning
# across every non-built-in subagent, which a small roster never
# approaches -- so this value is a gitapex-owned convention, not a
# published limit. 500 is grounded in this repository's own evidence:
# agents/review-persona.md routed correctly at 400 characters, so 500
# leaves headroom without licensing the 717- and 1,074-character
# descriptions that motivated issue #1963. It is deliberately a loose
# backstop: once axis B1 (trigger purity) is applied, real descriptions
# land well below it. This count is `B2`'s evidence, never `B1`'s (see
# SKILL.md's own "Where its output lands"): what pushes a description over
# a cap is detail that belongs in the body, which is B2. B1 grades content
# type and takes no input from this number -- a cap cannot make that
# judgement -- so B1 is what detects the failure this cap only bounds.
DESCRIPTION_MAX_CHARS = 500
# A subagent body is that subagent's system prompt and loads only when the
# subagent runs, so it is far cheaper than the description above. These
# two values are borrowed from the skill side's own body budget, and what
# transfers is the reason rather than the number: once the body is loaded,
# every token in it competes with conversation history and the rest of the
# dispatched context. Nothing in this repository is currently near either
# value; they are a ceiling against future growth, not a present
# constraint.
BODY_MAX_LINES = 500
# The token half of the same borrowed body budget: a line count alone does
# not bound a body whose lines are long, so the two are checked together.
BODY_MAX_TOKENS = 5000
# A project-instruction file loads into every session, and a non-fork
# subagent re-loads the whole hierarchy on every dispatch. Unlike the
# subagent values above, this one IS published: the Claude Code memory
# documentation states "target under 200 lines per CLAUDE.md file. Longer
# files consume more context and reduce adherence." A repository is free
# to declare a stricter local target; this checker enforces the published
# one so it is correct for any repository that has not.
PROJECT_INSTRUCTION_MAX_LINES = 200
# len(text) // 4 is the same rough, stdlib-only token estimate
# evaluating-skill-quality's own token_budget check uses. Kept identical
# so a body measured by one checker is comparable to a body measured by
# the other, rather than two estimates that disagree for no reason.
CHARS_PER_TOKEN_ESTIMATE = 4
# Frontmatter delimiter and top-level key shape. A key is recognised only
# at column 0, so an indented line is a continuation of the key above it
# -- which is how a folded or block-scalar `description` spanning several
# lines is kept whole instead of being truncated at its first newline.
_FRONTMATTER_DELIMITER = "---"
_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$")
# A YAML alias reference: the value is `*anchor`, resolved by the loader
# to an anchor defined elsewhere. Detected so the checker can fail closed
# rather than report the alias token's own two-character length.
_ALIAS_VALUE_RE = re.compile(r"\A\*[A-Za-z0-9_-]+\Z")

_SUBAGENT = "subagent"
_PROJECT_INSTRUCTION = "project-instruction"


@dataclass(frozen=True)
class Finding:
    """One graded result. `passed` False is a real threshold breach or a
    fail-closed parse failure; the two are not distinguished here because
    both block, and `detail` already says which happened."""

    path: str
    check: str
    passed: bool
    detail: str


class ChannelParseError(Exception):
    """Raised when a file cannot be split into frontmatter and body."""


def _is_delimiter(line: str) -> bool:
    """True only for a delimiter at column 0.

    Leading whitespace is NOT stripped, deliberately. An indented `---`
    is content -- inside a block scalar it is part of the value -- and
    treating it as the closing delimiter truncates the frontmatter there.
    That under-measures the value, which is the dangerous direction: a
    description carrying an indented `---` would measure as its first few
    lines and PASS a cap its real value exceeds. Trailing whitespace is
    tolerated because it is invisible and changes nothing.
    """
    return line.rstrip() == _FRONTMATTER_DELIMITER


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return `(frontmatter_text, body_text)`.

    Raises `ChannelParseError` when the file does not open with a `---`
    delimiter line or the block is never closed -- the fail-closed path.
    """
    lines = text.split("\n")
    if not lines or not _is_delimiter(lines[0]):
        raise ChannelParseError("no YAML frontmatter block: the file does not open with a '---' line")
    for index in range(1, len(lines)):
        if _is_delimiter(lines[index]):
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    raise ChannelParseError("unterminated YAML frontmatter block: no closing '---' line")


def frontmatter_values(frontmatter_text: str) -> dict[str, str]:
    """Map each top-level frontmatter key to its raw value text.

    Continuation lines (anything that is not itself a column-0 key) are
    joined onto the key above, so a multi-line `description` is measured
    whole. Values are not YAML-decoded: this checker measures size, and a
    quote or a block-scalar indicator contributes to the size a reader and
    a tokenizer both see.
    """
    values: dict[str, list[str]] = {}
    current: str | None = None
    for line in frontmatter_text.split("\n"):
        match = _TOP_LEVEL_KEY_RE.match(line)
        if match:
            current = match.group(1)
            values.setdefault(current, []).append(match.group(2).strip())
        elif current is not None:
            # Continuation lines are kept verbatim apart from trailing
            # whitespace. Stripping their indentation would under-measure
            # a block scalar with an explicit indentation indicator
            # (`|2`), where indentation past the declared column is
            # content, not layout -- and under-measuring is what lets an
            # over-cap value PASS. Keeping the indentation can over-count
            # by a few characters on an ordinary folded scalar; that
            # direction only ever tightens the cap.
            values[current].append(line.rstrip())
    return {key: "\n".join(parts).strip() for key, parts in values.items()}


def estimated_tokens(text: str) -> int:
    """The shared rough estimate; see `CHARS_PER_TOKEN_ESTIMATE`."""
    return len(text) // CHARS_PER_TOKEN_ESTIMATE


def _body_findings(path: str, body: str) -> list[Finding]:
    line_count = len(body.strip("\n").split("\n")) if body.strip() else 0
    tokens = estimated_tokens(body)
    return [
        Finding(
            path,
            "body-lines",
            line_count <= BODY_MAX_LINES,
            f"{line_count} lines (max {BODY_MAX_LINES})",
        ),
        Finding(
            path,
            "body-tokens",
            tokens <= BODY_MAX_TOKENS,
            f"{tokens} estimated tokens (max {BODY_MAX_TOKENS})",
        ),
    ]


def check_subagent(path: str, text: str) -> list[Finding]:
    """Grade one subagent definition."""
    try:
        frontmatter_text, body = split_frontmatter(text)
    except ChannelParseError as error:
        return [Finding(path, "frontmatter", False, str(error))]
    values = frontmatter_values(frontmatter_text)
    description = values.get("description")
    if description is None:
        return [Finding(path, "frontmatter", False, "frontmatter declares no 'description' key")]
    # A YAML alias (`description: *d`) measures as two characters here
    # while the loader resolves it to an anchor defined elsewhere in the
    # block -- an under-measurement with no upper bound. This checker does
    # not resolve anchors, so it must not report a size it cannot stand
    # behind.
    if _ALIAS_VALUE_RE.match(description):
        return [
            Finding(
                path,
                "frontmatter",
                False,
                f"'description' is a YAML alias ({description!r}); this checker does not resolve anchors",
            )
        ]
    findings = [
        Finding(
            path,
            "description-chars",
            len(description) <= DESCRIPTION_MAX_CHARS,
            f"{len(description)} characters (max {DESCRIPTION_MAX_CHARS})",
        )
    ]
    findings.extend(_body_findings(path, body))
    return findings


def check_project_instruction(path: str, text: str) -> list[Finding]:
    """Grade one project-instruction file. Frontmatter is not required and
    is not stripped: a CLAUDE.md/AGENTS.md is measured as the reader and
    the context window see it, whole."""
    line_count = len(text.strip("\n").split("\n")) if text.strip() else 0
    return [
        Finding(
            path,
            "file-lines",
            line_count <= PROJECT_INSTRUCTION_MAX_LINES,
            f"{line_count} lines (max {PROJECT_INSTRUCTION_MAX_LINES})",
        )
    ]


def check_path(path: Path, kind: str) -> list[Finding]:
    """Read and grade one file, failing closed on any read/decode error."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [Finding(str(path), "readable", False, "file not found")]
    except (OSError, UnicodeDecodeError) as error:
        return [Finding(str(path), "readable", False, f"unreadable: {error}")]
    if kind == _SUBAGENT:
        return check_subagent(str(path), text)
    if kind == _PROJECT_INSTRUCTION:
        return check_project_instruction(str(path), text)
    # Never fall through to a default grading: an unrecognised kind means
    # the caller asked for a grade this checker does not define, and
    # silently applying the looser project-instruction rules to a subagent
    # would skip the description cap entirely.
    return [Finding(str(path), "kind", False, f"unknown channel kind {kind!r}")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Grade the deterministic shape of a context channel: a subagent "
            "definition's description and body, or a project-instruction "
            "file's length. Arithmetic only -- content type is axis B1's job."
        )
    )
    parser.add_argument(
        "--kind",
        choices=(_SUBAGENT, _PROJECT_INSTRUCTION),
        required=True,
        help="Which channel kind every given path is.",
    )
    parser.add_argument("paths", nargs="*", help="Channel files to grade.")
    args = parser.parse_args(argv)
    if not args.paths:
        print("error: no paths given", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    for raw_path in args.paths:
        findings.extend(check_path(Path(raw_path), args.kind))

    failures = [finding for finding in findings if not finding.passed]
    for finding in findings:
        status = "PASS" if finding.passed else "FAIL"
        print(f"{status}  {finding.path}  {finding.check}: {finding.detail}")
    if failures:
        print(f"\nFAIL: {len(failures)} of {len(findings)} check(s) failed.")
        return 1
    print(f"\nPASS: all {len(findings)} check(s) passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
