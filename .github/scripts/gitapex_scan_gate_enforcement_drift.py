#!/usr/bin/env python3
"""Report (and fail CI on) active CI-plane gates missing from the committed
ruleset's required status checks.

Issue #1422: `skill-branch-fixture-coverage` was found registered in
`.gitapex/ssot.json` as `status: "active"`, running in CI on every relevant
pull request, and yet absent from `.github/rulesets/main.json`'s
`required_status_checks` -- so a failing run reported red but could not
block a merge. That specific gap is fixed alongside this script (see
`.github/workflows/skill-branch-fixture-coverage-gate.yml`'s `paths:`
filter removal and `.github/rulesets/main.json`'s new context entry). This
script exists so the same *class* of gap -- a gate built and wired into CI,
but never actually required -- is visible on every pull request going
forward, rather than found only by a retrospective's own manual
investigation.

**Report-only by design, not an auto-fix.** A direct comparison run against
this repository at the time this script was written found 53 such gates
once `skill-branch-fixture-coverage` itself is registered and this
scanner's own gate entry is added to `.gitapex/ssot.json` (this script is
itself an active CI-plane gate not yet in `required_status_checks`, so its
own addition is self-referentially part of the count it reports) -- far
more than this one issue's own scope. Some of that gap is real oversight; some
of it is a gate this repository has deliberately left non-blocking (for
example `docs/runbooks/rulesets.md`'s own documented `eval-gate` exclusion,
a known-red check that would block every merge if required). `.gitapex/ssot.json`
has no field distinguishing "deliberately advisory" from "should be
required" -- so this script's own job is narrower than "find every gap and
fix it": it reports the count against a `--threshold` (the same shape
`gitapex_scan_retrospective_gate_drift.py` already uses) and leaves the
per-gate judgment call to whoever reads a failing run.

**One-directional by design, not by oversight (dimension 20).** This
script only ever reports `gate_ids - required_contexts` -- an active
CI-plane `ssot.json` gate absent from `required_status_checks`. It
deliberately does not also report the reverse (`required_contexts -
gate_ids`): a direct check found 11 such reverse entries in this
repository today (`actionlint`, `ruff`, `pytest`, `mypy`, `betterleaks`,
`coverage-combine`, `exception-handler-gaps`, and four
`pytest-bash-oracle-*` jobs), none of which are `ssot.json` gate
registrations at all -- they are this repository's baseline lint/test/
type-check/secret-scan jobs, outside `ssot.schema.json`'s own stated scope
("gitapex's own deterministic gates", not every CI job the repository
runs). Reporting that direction as a "gap" would be a false claim that
those jobs are missing a registration they were never meant to have.

**Why this is a working-tree-only check, not a network scan.** Everything
it needs -- the gate registry and the committed ruleset -- is already
checked into this repository. Unlike `gitapex_scan_ruleset_drift.py`
(which asks what GitHub's live ruleset currently enforces, a question only
an API read can answer), this script only ever asks whether the *committed*
files agree with each other. That is also why it runs as a plain pytest
case (see `tests/test_gitapex_scan_gate_enforcement_drift.py`) rather than
its own scheduled workflow: `gitapex_gate_ruleset_required_checks.py`
(issue #439) already established that pattern for the same reason, and
riding the already-required `pytest` status check means this gate needs no
new entry of its own in `.github/rulesets/main.json` to actually block a
merge -- the same reachability problem this script itself was written to
report elsewhere.

Uses this repository's own shared `_gitapex_schema_validation.load_json_or_raise`
helper, which pulls in `jsonschema` -- run via `uv run` (see Usage), not a
bare `python3` invocation.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_scan_gate_enforcement_drift.py \\
        --ssot .gitapex/ssot.json --ruleset .github/rulesets/main.json --threshold 53

Exit codes:
    0  The count of active CI-plane gates missing from required_status_checks
       does not exceed the threshold.
    1  The count exceeds the threshold, or either input file cannot be read
       as usable JSON (never silently reported as "zero gates found").
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _gitapex_schema_validation import load_json_or_raise  # sys.path bootstrap above must run first

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"
DEFAULT_RULESET_PATH = REPO_ROOT / ".github" / "rulesets" / "main.json"

#: Measured against this repository once `skill-branch-fixture-coverage`
#: itself is registered (issue #1422's own Row 1) and this scanner's own
#: gate entry is added to `.gitapex/ssot.json` (self-referentially part of
#: the count -- see the module docstring). Not a target to shrink to zero
#: by this script alone -- see the module docstring's report-only
#: rationale -- but the ceiling this check exists to stop from growing
#: unnoticed.
DEFAULT_THRESHOLD = 53


class RegistryReadError(RuntimeError):
    """Raised when `.gitapex/ssot.json` cannot be read as a usable gate registry."""


class RulesetReadError(RuntimeError):
    """Raised when the committed ruleset cannot be read as a usable document."""


def load_active_ci_gate_ids(ssot: dict[str, Any]) -> set[str]:
    """Return the `id` of every gate in `ssot` whose `status` is `"active"`
    and whose `planes` includes `"ci"`.

    Mirrors `gitapex_scan_retrospective_gate_drift.py`'s own
    `load_gate_tracking_issues` in shape (read one field across every
    `gates[]` entry, tolerate a malformed *individual* entry rather than
    crashing on it) but reads `id`/`status`/`planes` instead of
    `tracking_issue`.

    Raises `RegistryReadError` when the top-level `gates` key is missing or
    not a list -- fail-closed, per
    `skills/evaluating-deterministic-gate-quality/references/dimensions.md`
    dimension 15: silently returning an empty set here would let a
    corrupted or truncated `gates` array read as "zero active CI-plane
    gates", which `run()` would then report as a clean PASS with no gap at
    all -- the exact "malformed input reads as clean" failure mode this
    script exists to avoid in the class of gate it itself checks for.
    Tolerating a malformed *individual* gate entry (not a dict, blank id,
    non-list `planes`) stays a skip, not a raise: one bad entry among many
    good ones is not evidence the whole registry is unusable, and skipping
    it only ever shrinks the counted set, which biases toward reporting
    more gaps, not fewer.
    """
    gates = ssot.get("gates")
    if not isinstance(gates, list):
        raise RegistryReadError("ssot: top-level 'gates' key is missing or not a list -- registry is unusable")
    gate_ids: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        gate_id = gate.get("id")
        planes = gate.get("planes")
        if not isinstance(gate_id, str) or not gate_id:
            continue
        if gate.get("status") != "active":
            continue
        if not isinstance(planes, list) or "ci" not in planes:
            continue
        gate_ids.add(gate_id)
    return gate_ids


def load_required_contexts(ruleset: dict[str, Any]) -> set[str]:
    """Return every `context` named in `ruleset`'s `required_status_checks` rule.

    Raises `RulesetReadError` when the top-level `rules` key is missing or
    not a list -- the same fail-closed reasoning `load_active_ci_gate_ids`
    applies to `gates` above: a corrupted `rules` array must not silently
    read as "zero required contexts" (which would, if anything, bias
    toward over-reporting gaps here, but a missing top-level key is still
    evidence the file itself is unusable, not a valid "no rules" state).
    A `required_status_checks`-typed rule that is simply absent from an
    otherwise well-formed `rules` list, or a malformed *individual* rule
    entry, is tolerated as "zero required contexts" -- that shape check
    against GitHub's own request schema is
    `gitapex_gate_ruleset_required_checks.py`'s own job, not this
    function's; this function only reads what is already known-valid
    top-level JSON.
    """
    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        raise RulesetReadError("ruleset: top-level 'rules' key is missing or not a list -- ruleset is unusable")
    contexts: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        parameters = rule.get("parameters")
        if not isinstance(parameters, dict):
            continue
        entries = parameters.get("required_status_checks")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("context"), str):
                contexts.add(entry["context"])
    return contexts


def find_unregistered_gates(gate_ids: set[str], required_contexts: set[str]) -> list[str]:
    """Return `gate_ids` not present in `required_contexts`, sorted for stable output."""
    return sorted(gate_ids - required_contexts)


def evaluate(unregistered_count: int, threshold: int) -> bool:
    """Return True iff `unregistered_count` exceeds `threshold`."""
    return unregistered_count > threshold


def format_report(unregistered: list[str], total_active_ci_gates: int, threshold: int) -> str:
    """Human-readable report, printed to stdout."""
    count = len(unregistered)
    lines = [
        f"Gate-enforcement drift report: {count} of {total_active_ci_gates} active CI-plane "
        f".gitapex/ssot.json gates have no matching context in .github/rulesets/main.json's "
        f"required_status_checks (threshold: {threshold}).",
    ]
    if unregistered:
        lines.append(
            "Gates that run in CI but cannot block a merge (a per-gate judgment call, not "
            "automatically a defect -- some may be deliberately advisory; see this script's "
            "own module docstring):"
        )
        lines.extend(f"  {gate_id}" for gate_id in unregistered)
    else:
        lines.append("Every active CI-plane gate is registered as a required status check.")
    if evaluate(count, threshold):
        lines.append(f"FAIL: {count} exceeds threshold {threshold}.")
    else:
        lines.append(f"PASS: {count} does not exceed threshold {threshold}.")
    return "\n".join(lines)


def run(ssot_path: pathlib.Path, ruleset_path: pathlib.Path, threshold: int) -> tuple[str, bool]:
    """Return `(report, ok)`. Raises RegistryReadError/RulesetReadError when
    either input cannot be read at all -- never silently treated as zero
    gates found, the same fail-loud contract
    `gitapex_scan_retrospective_gate_drift.py`'s own `load_gate_tracking_issues`
    upholds."""
    ssot = load_json_or_raise(ssot_path, RegistryReadError)
    if not isinstance(ssot, dict):
        raise RegistryReadError(f"{ssot_path}: gate registry must be a JSON object, got {type(ssot).__name__}")
    ruleset = load_json_or_raise(ruleset_path, RulesetReadError)
    if not isinstance(ruleset, dict):
        raise RulesetReadError(f"{ruleset_path}: ruleset must be a JSON object, got {type(ruleset).__name__}")

    gate_ids = load_active_ci_gate_ids(ssot)
    required_contexts = load_required_contexts(ruleset)
    unregistered = find_unregistered_gates(gate_ids, required_contexts)
    report = format_report(unregistered, len(gate_ids), threshold)
    return report, not evaluate(len(unregistered), threshold)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ssot", default=str(DEFAULT_SSOT_PATH), help="path to the gate registry (default: .gitapex/ssot.json)"
    )
    parser.add_argument(
        "--ruleset",
        default=str(DEFAULT_RULESET_PATH),
        help="path to the committed ruleset (default: .github/rulesets/main.json)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"fail if the unregistered-gate count exceeds this value (default: {DEFAULT_THRESHOLD})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report, ok = run(pathlib.Path(args.ssot), pathlib.Path(args.ruleset), args.threshold)
    except (RegistryReadError, RulesetReadError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
