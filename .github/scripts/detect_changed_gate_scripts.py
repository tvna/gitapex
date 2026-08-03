#!/usr/bin/env python3
"""Select, from a diff's `--name-status` output, the paths that are this
repository's own deterministic gates.

Issue #673 (refs #665 repair 1). `gate_skill_audit_disclosure.py`'s
`deterministic-gate-quality` check needs to know which changed paths are
gates; this script answers that question, and the calling workflow
(`skill-audit-gate.yml`) supplies the `git diff` output, keeping the
git-access split every other signal in that workflow already uses
(`skill_description_diff.py`, `skill_security_relevance.py`,
`detect_touched_eval_skills.py`).

Four membership rules, unioned, each covering a gap the others leave:

1. **Naming convention** -- `.github/scripts/gate_*.py`,
   `.github/scripts/scan_*.py`, and `hooks/check-*.sh` / `hooks/check_*.py`.
   Catches a brand-new gate in the window before it is registered, which
   rule 2 cannot see. Both directories are covered, not just the first: 9
   of the 25 registered gates live under `hooks/`, registration is a
   separate unenforced step, and an earlier revision anchored this rule to
   `.github/scripts/` alone -- so a new `hooks/check-new-deny.sh`
   PreToolUse gate shipped entirely outside this check. That also brings
   `hooks/check-merge-pull-request-block.sh`, a live deny gate that is
   unregistered today, into scope without needing a registry edit
   (`scan_ssot_schema.py` documents under-registration as a known gap).
2. **The registry** -- any path listed in a `.gitapex/ssot.json`
   `gates[].script` value. Rule 1 alone was the first version of this
   check and it under-covered badly: 16 of the 35 registered gate script
   paths do not match it, including `hooks/*.sh` and `hooks/*.py`
   PreToolUse deny logic, three workflow YAML files the registry itself
   records as gate implementation, and -- most sharply --
   `.github/scripts/skill_security_relevance.py`, the script that decides
   whether this very workflow's `adversarial-coverage-mapping` check fires
   at all. A wrong answer there is a silent fail-open in a sibling gate,
   which is exactly the class this check exists to catch. The registry is
   the repository's own single source of truth for "what is a gate"
   (issue #123), so keying off it makes the scope self-maintaining: a gate
   named `check_foo.py` or `verify_foo.py` tomorrow is in scope the moment
   it is registered, with no edit here.
3. **The registry file itself** -- `.gitapex/ssot.json`. It determines
   rule 2's answer, so an edit that removes a gate from it narrows this
   check's own scope. Treating it as in-scope makes that narrowing
   visible instead of silent.
4. **Gate wiring** -- `hooks/hooks.json`, which decides whether the
   PreToolUse gates run at all. Same reasoning as rule 3, applied to the
   other plane: rewriting it to unhook a gate is as complete a disable as
   deleting the gate's script, and was invisible while only the scripts
   themselves were in scope. `.github/workflows/skill-audit-gate.yml` is
   covered by rule 2 instead, via its registration (see below).

Excluded on purpose, and this is the fail-open the rules above are shaped
around: nothing here selects a file merely because it *sits* in one of
these directories. `tests/`, `hooks/hooks.json`'s siblings, and unrelated
workflow YAML stay out.

**There is no exemption, and that is a deliberate reversal.** An earlier
revision carved one out: three registered gates are workflow YAML, so
Dependabot's weekly `github-actions` update (`.github/dependabot.yml`)
touches them, and a bot cannot add a disclosure to its own PR body. The
carve-out exempted a workflow file whose entire change was `uses:` pin
bumps -- about 130 lines of hand-rolled unified-diff parsing whose only
job was to make a check pass.

A review round found three defects in those 130 lines, all of the class
this whole check exists to catch: any added or removed `uses:` line counted
as a pin bump, so *deleting the step that invokes a gate* was exempted (a
green required check for disabling a gate -- the same fail-open that
motivated including deletions above, reintroduced by the code meant to
narrow scope), a wholesale swap to a different action was exempted, a
`--`-prefixed removed line defeated the header skip, and a non-UTF-8 diff
raised an uncaught traceback.

So the exemption is gone rather than patched. Deciding "is this diff
*merely* a dependency bump" is a judgment about intent, and encoding a
judgment as a parser is what produced the defects; a gate that cannot be
sure fails closed. The cost is real and accepted: a Dependabot PR touching
a registered gate workflow requires a `deterministic-gate-quality`
disclosure line, which the human merging it adds. A pin bump into a gate's
own workflow is a supply-chain change to a gate, so a human looking at it
is not obviously the wrong outcome.

Deletions and renames are **in scope**, unlike every other signal
`skill-audit-gate.yml` computes. Those exclude `D` and `R100` because a
deleted or byte-identically-renamed SKILL.md or design doc has no new
content to audit. That rationale does not transfer to a gate: removing one
is the single highest-blast-radius change that can be made to it, and the
first version of this check inherited the exclusion anyway -- verified
live, a PR whose only change was `git rm
.github/scripts/gate_plugin_root_brace_notation.py` made the whole job
report `applicable=false` and exit 0, a green required check for deleting a
gate. Dimension 1 of
`skills/evaluating-deterministic-gate-quality/references/dimensions.md`
is about the deny path being non-bypassable; removal was the direct bypass.

Fail-closed, never a silent empty result (dimension 15, and
`gate_evals_scripts_coverage.py`'s own "an empty match set is an error"
rule): an unreadable or malformed registry raises rather than degrading to
rule 1 alone, and a selected path containing a comma raises rather than
corrupting the comma-joined sink the caller writes to `$GITHUB_OUTPUT`.
An empty *selection* is legitimate here and is not an error -- a diff
genuinely touching no gate is the common case, and the caller acts on the
empty list by not requiring the disclosure.

Standard library only, so the calling workflow needs no dependency install.

Usage::

    git diff --name-status BASE...HEAD | python3 detect_changed_gate_scripts.py

Reads `--name-status` lines on stdin, writes the comma-joined selection to
stdout (empty line when nothing matched) and diagnostics to stderr, so the
machine-read channel carries only the payload (dimension 14).

Exit codes: 0 selection computed (possibly empty), 2 the selection could
not be trusted.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SSOT_RELATIVE_PATH = ".gitapex/ssot.json"
HOOK_WIRING_PATH = "hooks/hooks.json"

# Rule 1. `[^/]*` rather than `.*` so the pattern cannot cross a directory
# separator -- the same single-level boundary the calling workflow's
# `:(glob)` pathspecs enforce, restated here rather than assumed from them
# (dimension 3: re-check the condition, do not trust the caller's own
# filter to have selected correctly).
#
# Always applied with `re.fullmatch`, never `re.match`: Python's `$` also
# matches immediately before a trailing newline and `[^/]` matches `\n`, so
# `.match` would accept ".github/scripts/gate_a.py\n" as a gate and feed a
# newline-bearing path toward the single-line $GITHUB_OUTPUT sink.
# `.github/scripts/detect_touched_eval_skills.py` documents this same
# pitfall and uses fullmatch for it; this follows that precedent rather
# than rediscovering it.
_CONVENTION_RE = re.compile(
    r"\.github/scripts/(?:gate|scan)_[^/]*\.py|hooks/check[-_][^/]*\.(?:sh|py)"
)



class ScopeError(Exception):
    """The gate selection could not be trusted -- exit 2, never a silent pass."""


def registered_gate_paths(repo_root: pathlib.Path = REPO_ROOT) -> set[str]:
    """Return every `gates[].script` path in `.gitapex/ssot.json` (rule 2).

    Raises ``ScopeError`` rather than returning an empty set when the
    registry is missing or malformed: an empty set here would silently
    shrink this check's scope back to rule 1 alone, which is the
    under-coverage this script exists to fix.
    """
    path = repo_root / SSOT_RELATIVE_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ScopeError(f"{path}: gate registry cannot be read: {error}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ScopeError(f"{path}: gate registry is not valid JSON: {error}") from error

    # `[]`, `"x"` and `1` are all valid JSON, so parsing succeeding does not
    # mean the shape is usable. Without this guard `data.get` raised an
    # uncaught AttributeError and the script exited 1 with a raw traceback
    # instead of the documented ScopeError/exit 2 -- literally the
    # "unreadable file produced an uncaught traceback" defect class from
    # PR #651 that this whole check exists to catch, reproduced inside the
    # check itself.
    if not isinstance(data, dict):
        raise ScopeError(
            f"{path}: gate registry must be a JSON object, got {type(data).__name__}"
        )

    gates = data.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ScopeError(f"{path}: gate registry has no usable 'gates' list")

    paths: set[str] = set()
    for gate in gates:
        script = gate.get("script") if isinstance(gate, dict) else None
        if script is None:
            continue
        # A `script` is either one path or a list of them (both shapes are
        # live in the registry today); anything else is a schema violation
        # this script surfaces rather than skipping past.
        candidates = [script] if isinstance(script, str) else script
        if not isinstance(candidates, list):
            raise ScopeError(f"{path}: unsupported 'script' value: {script!r}")
        for candidate in candidates:
            if not isinstance(candidate, str):
                raise ScopeError(f"{path}: unsupported 'script' entry: {candidate!r}")
            paths.add(candidate)
    return paths


def is_gate_path(path: str, registered: set[str]) -> bool:
    """Return True iff `path` is in scope under any of the four rules."""
    return (
        bool(_CONVENTION_RE.fullmatch(path))
        or path in registered
        or path in (SSOT_RELATIVE_PATH, HOOK_WIRING_PATH)
    )


def select(name_status_text: str, registered: set[str]) -> list[str]:
    """Return the sorted, deduped gate paths named in `--name-status` output.

    Every status is honoured, including `D` and `R100` -- see this module's
    docstring for why a gate's removal must not be filtered out. For a
    rename both sides are considered: the new path because it is what now
    exists, and the old path because a gate that moved out from under the
    workflow step invoking it is the same breakage as one deleted.
    """
    selected: set[str] = set()
    for line in name_status_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 2:
            raise ScopeError(f"unparseable --name-status line: {line!r}")
        for candidate in fields[1:]:
            candidate = candidate.strip()
            if candidate and is_gate_path(candidate, registered):
                selected.add(candidate)

    for path in selected:
        # The caller comma-joins this into $GITHUB_OUTPUT and the gate
        # script comma-splits it back apart. A path carrying a literal
        # comma would silently split into two bogus entries, so it is a
        # hard error here rather than a corrupted sink downstream.
        if "," in path:
            raise ScopeError(f"gate path contains a comma, which the output sink cannot carry: {path}")
    return sorted(selected)


class DetectChangedGateScriptsArgs:
    """Typed view of `main`'s parsed CLI namespace. `repo_root` must be an
    existing directory -- every existing caller already passes one, so this
    only gives a --repo-root pointing nowhere a clear, early error instead
    of the deeper, less specific "gate registry cannot be read" ScopeError
    it would otherwise surface."""

    def __init__(self, *, repo_root: pathlib.Path) -> None:
        if not repo_root.is_dir():
            raise ValueError(f"--repo-root must be an existing directory, got {repo_root}")
        self.repo_root = repo_root


def main(argv: list[str] | None = None) -> int:
    """CLI: print the comma-joined gate paths named on stdin."""
    parser = argparse.ArgumentParser(
        description="Select this repository's own deterministic gate paths "
        "from git diff --name-status output read on standard input."
    )
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root holding .gitapex/ssot.json (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    try:
        validated = DetectChangedGateScriptsArgs(repo_root=args.repo_root)
    except ValueError:
        print(f"{args.repo_root}: --repo-root must be an existing directory", file=sys.stderr)
        return 2

    try:
        registered = registered_gate_paths(validated.repo_root)
        selected = select(sys.stdin.read(), registered)
    except ScopeError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    if selected:
        print("Changed deterministic gate paths requiring disclosure:", file=sys.stderr)
        for path in selected:
            print(f"  {path}", file=sys.stderr)
    print(",".join(selected))
    return 0


if __name__ == "__main__":
    sys.exit(main())
