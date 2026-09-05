#!/usr/bin/env python3
"""Check that every `## Iteration:` entry in every `evals/*/split.md` file
discloses a non-empty `### Transfer check` subsection -- whole-file, every
entry, not scoped to a diff.

Issue #517 (refs #487) shipped the original version of this gate: a
diff-scoped check that a *newly-added* Kept-edit-log `**Iteration:`
bold-paragraph entry discloses a `Transfer check` line somewhere in its
own span, mirroring `scorer-gated-skill-edits/SKILL.md`'s own stop
boundary, "Never ship a skill that has not passed a transfer check." That
version was deliberately scoped to entries under a top-level `##
Kept-edit log` heading only (a `## Rejected-edit log` entry was out of
scope, since a rejected candidate was never a ship decision) and only to
entries whose own header line was new in the current PR's diff -- a
pre-existing entry, however non-compliant, was never retroactively
flagged.

Issue #928's split.md/split.json migration (tasks T2-T6) standardizes
every `evals/*/split.md` file on one heading convention -- `## Iteration:
<issue>, <title>`, with `### Gate result` / `### Transfer check` / `###
Rejected-edit log` / `### Verdict` subsections -- superseding both the old
`**Iteration:` bold-paragraph form and the separate top-level `## Kept-edit
log` / `## Rejected-edit log` split. That migration's own ACM row widens
this gate's own scope to match: "every iteration entry in every file is in
scope for the transfer-check requirement" -- every `## Iteration:` entry,
KEEP or REJECT alike, not only ones that used to sit under `## Kept-edit
log`, and every entry currently on disk, not only ones newly added in the
active diff. This rewrite implements that:

1. Recognizes only the standardized `## Iteration:` heading form. The old
   `**Iteration:` bold-paragraph recognition is dropped entirely -- after
   T2-T6, no `evals/*/split.md` file uses it any more, and continuing to
   special-case it would just be dead code matching a convention that no
   longer exists anywhere in this repository.
2. Scans the whole file, every entry, every time -- not a diff-computed
   subset. There is no more "newly added" concept: a call to this script
   is a full-corpus audit of whatever `evals/*/split.md` files it is
   pointed at (by default, every file the `evals/*/split.md` glob finds),
   the same "audit the whole tree, not just what one PR touched" shape
   `gitapex_scan_skill_metadata_schema.py` already uses for schema
   validation.
3. No longer scopes to a `## Kept-edit log` heading at all -- there is no
   such heading left to scope to after the migration, and the widened
   requirement explicitly covers REJECT entries too (an entry landed
   "outside the scorer-gate's scope" on non-behavioral grounds, or
   correctly REJECTed as a tie, still owes a disclosed Transfer check
   subsection under the new convention, even if that subsection's own
   content is just "not run this iteration").

Known, disclosed consequence of this rewrite's own scope (`.github/scripts/
gitapex_gate_transfer_check_disclosure.py` and this file's own test suite
only -- the calling workflow, `.github/workflows/
transfer-check-disclosure-gate.yml`, is out of scope for this change and
was not touched): that workflow's own "Determine newly-added Kept-edit-log
entries" step still greps for `^\\*\\*Iteration:` lines to build the
`--entries` input this script used to accept. Since no file uses that
bold-paragraph form any more, that grep now always finds zero lines on
both sides of the diff, `applicable` is always `false`, and the workflow's
gate step is permanently skipped -- a real, disclosed gap needing a
follow-up edit to that workflow file (not made here, per this task's own
file scope) to stop computing a diff at all and instead invoke this
script argument-free so it audits the current `evals/*/split.md` glob
directly, matching this script's own new whole-file contract.

Issue #1062 (wave 3 of #1040's batch pydantic CLI-arg validation rollout):
`main`'s parsed namespace is now passed through
`TransferCheckDisclosureArgs` immediately after `parser.parse_args(argv)`,
matching the wrap `gitapex_gate_hidden_characters.py`/`gitapex_gate_behind_base.py`
already apply. `paths` (`nargs="*"`, default `[]`) has no constraint
beyond that already-guaranteed `list[str]` shape -- deliberately no
non-empty-list requirement: an empty `paths` list is this script's own
signal to fall back to the default `evals/*/split.md` glob discovery
(`using_default_discovery` above), a currently-load-bearing behavior this
wrap must not disturb. So construction can currently never raise
`ValidationError` for a real CLI invocation; the model exists for
consistency with #1040's repo-wide convention (a typed seam between
`parse_args` and business logic). This gate's own production invocation
(`transfer-check-disclosure-gate.yml`) already runs under `uv run` (issue
#1035), so the added `pydantic` import is safe here.

Line/entry selection mirrors the multiplicity- and span-handling
discipline the previous version established
(`gitapex_gate_skill_rename_lifecycle.py`'s own "read the current on-disk
working tree, not a diff hunk" precedent): each `## Iteration:` heading's
own entry span runs from its own line up to, but excluding, the next
`##`-level heading (any level-2 heading, not only another `## Iteration:`
one) or EOF. Within that
span, a `### Transfer check` subsection's own content runs from its own
heading line up to, but excluding, the next `###`- or `##`-level heading,
or the entry's own end. An entry is compliant only if that subsection
heading exists at all *and* its content is non-blank once stripped -- a
present-but-empty heading (someone added the heading, forgot to fill it
in) is exactly as non-compliant as a wholly-absent one, and reported the
same way.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from pydantic import BaseModel, ValidationError

DEFAULT_GLOB = "evals/*/split.md"
# Guards against _default_paths() silently finding nothing (a wrong working
# directory, a checkout that lost most of evals/) and main() then vacuously
# reporting "PASS: no files matched" -- the same fail-open shape PR #651's
# own precedent named, and the same purpose as
# gitapex_scan_split_schema.py's own MIN_EXPECTED_SPLIT_JSON_FILES floor
# (issue #928 adversarial review finding 3). This repository has 4 real
# evals/*/split.md files today; the floor is set below that real count so a
# partial-but-not-total discovery loss is not the trigger here (that shape
# is instead caught per-entry by find_missing_transfer_checks itself), only
# a near-total or total one. Applies only to the default-glob discovery
# path -- explicit CLI-supplied paths are never silently substituted here.
MIN_EXPECTED_SPLIT_MD_FILES = 3

# Deliberately `(.*)$` rather than `(\S.*)$`: a title-less heading (`##
# Iteration:` alone, or with trailing whitespace only -- a plausible
# authoring mistake where the entry was added before its title was filled
# in) must still be recognized as an iteration entry, so its missing
# Transfer check is caught rather than silently invisible to this scan
# (issue #928 adversarial review finding 2 -- the stricter `\S.*` let such
# a heading match nothing at all, and the entry vanished from this gate's
# view entirely).
_ITERATION_HEADING_RE = re.compile(r"^##[ \t]+Iteration:[ \t]*(.*)$", re.IGNORECASE)
_H2_RE = re.compile(r"^##[ \t]+\S.*$")
_H3_RE = re.compile(r"^###[ \t]+\S.*$")
_TRANSFER_CHECK_HEADING_RE = re.compile(r"^###[ \t]+Transfer check[ \t]*$", re.IGNORECASE)


def _iter_iteration_entries(lines):
    """Yield (start_index, heading_text) for every `## Iteration:` heading
    line in `lines`, in file order. `heading_text` is the full heading
    line, right-stripped, used only for human-readable reporting."""
    for index, line in enumerate(lines):
        if _ITERATION_HEADING_RE.match(line):
            yield index, line.rstrip()


def _entry_span_end(lines, start_index):
    """Index of the first `##`-level heading strictly after `start_index`
    (any level-2 heading, not only another `## Iteration:` one -- an
    entry's own span ends at the next section boundary regardless of what
    that next section is), or `len(lines)` if there is none."""
    for index in range(start_index + 1, len(lines)):
        if _H2_RE.match(lines[index]):
            return index
    return len(lines)


def _transfer_check_content(lines, entry_start, entry_end):
    """Return the stripped text of the entry's own `### Transfer check`
    subsection (the span from its own heading line, exclusive, up to the
    next `###`- or `##`-level heading, or the entry's own end), or `None`
    if no such subsection heading exists anywhere within
    `lines[entry_start:entry_end]`. Only the first matching heading in the
    span is used -- real entries never carry two."""
    for index in range(entry_start, entry_end):
        if _TRANSFER_CHECK_HEADING_RE.match(lines[index]):
            sub_end = entry_end
            for j in range(index + 1, entry_end):
                if _H3_RE.match(lines[j]) or _H2_RE.match(lines[j]):
                    sub_end = j
                    break
            return "\n".join(lines[index + 1 : sub_end]).strip()
    return None


def find_missing_transfer_checks(paths):
    """paths: an iterable of `evals/*/split.md`-shaped file paths. Returns
    a list of `(path, iteration_heading_text)` pairs -- one for every `##
    Iteration:` entry, anywhere in the file (whole-file, every entry, not
    diff-scoped), whose own span has no `### Transfer check` subsection
    heading at all, or has one whose own content is empty once stripped --
    either way a disclosure failure, never silently skipped. A file that
    cannot be read (missing, or not valid UTF-8) is itself reported as a
    single `(path, "<file unreadable>")` failure tuple rather than raising
    or being silently dropped from the scan."""
    missing = []
    for path in paths:
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"warning: could not read {path}: {exc}", file=sys.stderr)
            missing.append((path, "<file unreadable>"))
            continue
        for start, heading in _iter_iteration_entries(lines):
            end = _entry_span_end(lines, start)
            content = _transfer_check_content(lines, start, end)
            if not content:
                missing.append((path, heading))
    return missing


def _default_paths():
    """The whole-file audit's own default scope: every real `evals/*/
    split.md` file the glob finds in the current working directory (the
    calling workflow always runs from the repository root), sorted for
    deterministic output. Never a hardcoded 5-skill list -- a 6th skill
    gaining a `split.md` later must be picked up automatically."""
    return sorted(str(path) for path in Path().glob(DEFAULT_GLOB))


def _truncate(text, limit=100):
    return text if len(text) <= limit else text[: limit - 3] + "..."


class TransferCheckDisclosureArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace (issue #1062). See the
    module docstring's own issue #1062 section for why `paths` carries no
    additional field validator."""

    paths: list[str] = []


def main(argv: list[str] | None = None) -> int:
    """CLI: exit 0 iff every `## Iteration:` entry in every given (or
    glob-discovered) `evals/*/split.md` file discloses a non-empty
    `### Transfer check` subsection, 1 if not, 2 if the CLI arguments
    themselves failed validation (unreachable via this script's own
    argparse-guaranteed shape today; see TransferCheckDisclosureArgs)."""
    parser = argparse.ArgumentParser(
        description="Check that every '## Iteration:' entry in every evals/*/split.md "
        "file (whole-file, every entry, not diff-scoped) discloses a non-empty "
        "'### Transfer check' subsection."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help=f"split.md file paths to audit; defaults to the '{DEFAULT_GLOB}' glob when omitted.",
    )
    args = parser.parse_args(argv)

    try:
        validated = TransferCheckDisclosureArgs(paths=args.paths)
    except ValidationError:
        print("FAIL: invalid CLI arguments", file=sys.stderr)
        return 2

    using_default_discovery = not validated.paths
    paths = validated.paths if validated.paths else _default_paths()

    if using_default_discovery and len(paths) < MIN_EXPECTED_SPLIT_MD_FILES:
        print(
            f"FAIL: only {len(paths)} file(s) matched '{DEFAULT_GLOB}' "
            f"(expected at least {MIN_EXPECTED_SPLIT_MD_FILES}) -- treating this as a "
            "discovery failure (wrong working directory, or a checkout that lost most "
            "of evals/) rather than reporting a vacuous pass",
            file=sys.stderr,
        )
        return 1

    missing = find_missing_transfer_checks(paths)
    if not missing:
        print(f"PASS: every '## Iteration:' entry in {len(paths)} file(s) discloses a Transfer check")
        return 0

    print(
        "FAIL: the following '## Iteration:' entries have no disclosed, non-empty '### Transfer check' subsection:",
        file=sys.stderr,
    )
    for path, heading in missing:
        print(f"  - {path}: {_truncate(heading)}", file=sys.stderr)
    print(
        "Add a '### Transfer check' subsection within the entry's own span "
        "(disclosing a real cross-model result, or that it was not run this "
        "iteration), per the convention already used in "
        "evals/evaluating-skill-quality/split.md.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
