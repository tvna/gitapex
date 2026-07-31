"""Deterministic substring-contract scorer for a held-out gate.

Given a task's substring assertions (``output_contains`` /
``output_not_contains`` / ``output_contains_near``) and a run's output text,
returns the fraction of assertions satisfied as a deterministic ``float`` in
``[0, 1]``. Standard library only, so the scorer stays self-contained with no
external dependency. Producing the run output is out of scope: only the
scoring step is made deterministic here.

``output_icontains``/``output_not_icontains`` (issue #628) are a separate,
opt-in, case-insensitive form of ``output_contains``/``output_not_contains``
-- same shape (a list of substrings), matched via ``str.casefold()`` on both
sides instead of raw ``in``. This exists because a real, twice-observed
defect (a real-script ablation for issue #618, ``output_contains: ["test
name"]`` failing against a response whose only occurrence was the title-cased
heading ``**Test name**``) showed that case-SENSITIVE matching produces false
regressions/improvements that are a scorer artifact, not a real behavioral
difference -- the same pattern every established substring-assertion
framework handles as a *separate, explicit* assertion type rather than a
silent mode change (promptfoo's ``contains``/``icontains``; Hamcrest's
``containsString``/``containsStringIgnoringCase``; AssertJ's
``contains``/``containsIgnoringCase``). Strictly additive: ``output_contains``
/``output_not_contains`` keep their existing case-sensitive semantics
unchanged, and no already-banked score that used only those keys is affected.
Not extended to ``output_contains_near``/``output_not_contains_near`` in this
change -- the near-check's blank-line-boundary logic is a separate, higher-
risk surface this defect never implicated; deferred, not silently dropped.
``casefold()`` (not ``lower()``) is used for Unicode-correct caseless
matching per Python's own docs, with the disclosed edge case that it can
over-normalize beyond ASCII (e.g. German "straße" -> "strasse") -- irrelevant
to this repository's ASCII-dominated assertion corpus.

``output_contains``/``output_not_contains`` check presence/absence anywhere
in the text, independently of each other -- they cannot verify that two
substrings are actually *bound together* (e.g. a repair's own description
sitting next to its own classification label, rather than each merely
appearing somewhere in the output). ``output_contains_near`` closes half of
that gap: each entry is ``{"all": [s1, s2, ...], "window": int}`` and is
satisfied only when every listed substring's first occurrence falls within
a ``window``-character span of every other -- i.e. they co-occur in roughly
the same sentence/paragraph, not merely somewhere in the same document.
``window`` defaults to 400 when omitted.

Requiring the *right* pairing alone is not sufficient: a short enough
response can still accidentally satisfy a `near` window for the wrong
pairing too (a positive-only check cannot distinguish "these are correctly
bound" from "the whole response was too terse to separate them"). Pair each
`output_contains_near` requirement (this keyword IS near its correct label)
with `output_not_contains_near` entries banning that same keyword from also
being near each of the *other* possible labels, so a swapped assignment is
rejected even when it is compact. `output_not_contains_near` shares the
same ``{"all": [...], "window": int}`` shape and is satisfied when the
entry's pairing does *not* hold.

A raw character count alone cannot cleanly separate "these two substrings
are bound in the same logical unit" from "they merely happen to be within N
characters of each other" -- a verbose correct paragraph and a terse
adjacent (but unrelated) one can straddle any fixed window either way.
"Near" therefore means two things together, both required: (1) within
``window`` characters (a loose backstop, default 400), AND (2) no blank
line (``"\n\n"``, this repository's paragraph/list-item separator -- see
`merge-retrospective/SKILL.md`'s worked example, one blank-line-separated
item per repair) between the two occurrences. The blank-line check is what
actually carries the distinction in practice; the character window is a
secondary sanity bound.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping

CORRECTNESS_DECIMALS = 6


def _assertion_list(assertions, key):
    """Return ``assertions[key]`` as a list, failing loudly on a bad shape.

    A missing or ``None`` value is an empty list. A bare string (the natural
    ``{"output_contains": "LGTM"}`` mistake) is rejected rather than scored
    per character, which would silently miscount.
    """
    value = assertions.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(
            f"{key} must be a list of substrings, got {type(value).__name__}"
        )
    return value


def _near_entry_list(assertions, key="output_contains_near"):
    value = assertions.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list of {{'all': [...], 'window': int}} objects")
    return value


_DEFAULT_NEAR_WINDOW = 400


def _near_satisfied(text, entry):
    """One ``output_contains_near`` entry is satisfied iff every substring in
    ``entry["all"]`` occurs in ``text`` (each at its first occurrence), the
    whole span from the earliest start to the latest end is no wider than
    ``entry.get("window", 400)`` characters, AND no blank line separates the
    occurrences (see this module's docstring for why both checks are used
    together, not the character window alone)."""
    if not isinstance(entry, Mapping):
        raise ValueError(
            f"output_contains_near entries must be mappings, got {type(entry).__name__}"
        )
    substrings = entry.get("all")
    if not isinstance(substrings, list) or len(substrings) < 2:
        raise ValueError("output_contains_near entries need an 'all' list of >= 2 substrings")
    window = entry.get("window", _DEFAULT_NEAR_WINDOW)
    spans = []
    for substring in substrings:
        index = text.find(substring)
        if index == -1:
            return False
        spans.append((index, index + len(substring)))
    span_start = min(start for start, _ in spans)
    span_end = max(end for _, end in spans)
    if (span_end - span_start) > window:
        return False
    return "\n\n" not in text[span_start:span_end]


def score(output_text, assertions):
    """Return the fraction of substring assertions satisfied, in ``[0, 1]``.

    ``assertions`` is a mapping with optional ``output_contains`` (each
    substring must appear in ``output_text``), ``output_not_contains`` (each
    must be absent), ``output_icontains``/``output_not_icontains`` (the same
    two checks, case-insensitively via ``str.casefold()`` -- see this
    module's docstring for why this is a separate opt-in key rather than a
    mode change on ``output_contains``), ``output_contains_near`` (each
    entry's substrings must co-occur within a character window), and
    ``output_not_contains_near`` (each entry's substrings must NOT co-occur
    within a character window -- see this module's docstring for both `near`
    forms). Identical inputs always produce the same value.

    A ``None`` ``output_text`` is treated as the empty string. Each list
    entry is one assertion, so a duplicated substring is weighted twice and
    an empty-string substring is always satisfied; that is the fixture's
    responsibility. Raises ``ValueError`` when ``assertions`` is not a
    mapping, when a value is not a list, or when the assertion set is empty,
    since a fixture with nothing to assert cannot score a run.
    """
    if not isinstance(assertions, Mapping):
        raise ValueError(
            f"assertions must be a mapping, got {type(assertions).__name__}"
        )
    contains = _assertion_list(assertions, "output_contains")
    not_contains = _assertion_list(assertions, "output_not_contains")
    icontains = _assertion_list(assertions, "output_icontains")
    not_icontains = _assertion_list(assertions, "output_not_icontains")
    near = _near_entry_list(assertions, "output_contains_near")
    not_near = _near_entry_list(assertions, "output_not_contains_near")
    total = (
        len(contains) + len(not_contains)
        + len(icontains) + len(not_icontains)
        + len(near) + len(not_near)
    )
    if total == 0:
        raise ValueError(
            "empty assertion set: a fixture with no output_contains, "
            "output_not_contains, output_icontains, output_not_icontains, "
            "output_contains_near, or output_not_contains_near cannot score "
            "a run"
        )
    text = output_text or ""
    text_casefold = text.casefold()
    satisfied = (
        sum(s in text for s in contains)
        + sum(s not in text for s in not_contains)
        + sum(s.casefold() in text_casefold for s in icontains)
        + sum(s.casefold() not in text_casefold for s in not_icontains)
        + sum(_near_satisfied(text, entry) for entry in near)
        + sum(not _near_satisfied(text, entry) for entry in not_near)
    )
    return satisfied / total


def split_mean(scores):
    """Return the arithmetic mean of a non-empty sequence of scores."""
    scores = list(scores)
    if not scores:
        raise ValueError("cannot take the mean of an empty score list")
    for index, value in enumerate(scores):
        _validate_correctness(value, f"score[{index}]")
    return sum(scores) / len(scores)


def _validate_correctness(value, label):
    """Reject correctness values outside the finite ``[0, 1]`` contract."""
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number in [0,1]")
    try:
        valid = math.isfinite(value) and 0 <= value <= 1
    except TypeError as exc:
        raise ValueError(f"{label} must be a finite number in [0,1]") from exc
    if not valid:
        raise ValueError(f"{label} must be a finite number in [0,1]")


def _validate_context_cost(value, label):
    """Reject context costs that are non-finite or negative."""
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite non-negative number")
    try:
        valid = math.isfinite(value) and value >= 0
    except TypeError as exc:
        raise ValueError(f"{label} must be a finite non-negative number") from exc
    if not valid:
        raise ValueError(f"{label} must be a finite non-negative number")


def _published_correctness(value):
    """Normalize correctness to the precision emitted by this CLI."""
    return round(value, CORRECTNESS_DECIMALS)


def _validate_published_prior(value):
    """Require a prior copied from this CLI's six-decimal output."""
    if value != _published_correctness(value):
        raise ValueError(
            "prior correctness must use the CLI's published six-decimal precision"
        )


def strict_compare(before_mean, after_mean):
    """Return ``"KEEP"`` iff ``after_mean`` strictly exceeds ``before_mean``.

    Ties are rejected, matching the gate's strict improve-or-reject rule
    (Procedure step 3): a tied or worse selection-split mean is ``"REJECT"``.
    """
    _validate_correctness(before_mean, "before correctness")
    _validate_correctness(after_mean, "after correctness")
    _validate_published_prior(before_mean)
    after = _published_correctness(after_mean)
    return "KEEP" if after > before_mean else "REJECT"


def pruning_compare(
    before_correctness,
    after_correctness,
    before_context_cost,
    after_context_cost,
):
    """Apply the predeclared correctness-first pruning gate.

    A correctness improvement is a normal strict improvement. At matched
    correctness, pruning is kept only when context cost strictly falls.
    Correctness regressions and cost ties/increases are rejected.
    """
    _validate_correctness(before_correctness, "before correctness")
    _validate_correctness(after_correctness, "after correctness")
    _validate_context_cost(before_context_cost, "before context cost")
    _validate_context_cost(after_context_cost, "after context cost")
    _validate_published_prior(before_correctness)
    after = _published_correctness(after_correctness)
    if after > before_correctness:
        return "KEEP"
    if after < before_correctness:
        return "REJECT"
    return "KEEP" if after_context_cost < before_context_cost else "REJECT"


def main(argv=None):
    """CLI: score a run's output against a JSON assertions file.

    Reads the assertions from a JSON file (standard library only, no YAML
    dependency) and the run output from ``--output`` or standard input, then
    prints the score. With ``--compare-to``, treats each line read from
    ``--scores`` (or standard input, one float per line) as one task's
    selection-split score, prints the mean, and prints ``KEEP``/``REJECT``
    against the given prior mean per the strict improve-or-reject gate --
    this replaces re-deriving that mean/compare arithmetic by hand each
    iteration. With ``--compare-to`` and ``--judge-verdict``, additionally
    appends the outcome of an adversarially-verified semantic judge (already
    run by the caller; this script does not call a model) as ``JUDGE_AGREE``
    or ``JUDGE_DISAGREE_REVIEW_REQUIRED`` -- an additional recorded field,
    never blended into the substring mean or verdict. With
    ``--dispatch-trace-verdict`` (single-run scoring only, i.e. without
    ``--compare-to``), similarly appends whether a fresh subagent dispatch
    was confirmed in this run's own transcript (already resolved by the
    caller, typically via ``evals/scripts/check_dispatch_trace.py``; this
    script does not inspect any transcript itself) as
    ``DISPATCH_TRACE_CONFIRMED``, ``DISPATCH_TRACE_NOT_CONFIRMED``, or
    ``DISPATCH_TRACE_UNVERIFIED`` -- again a recorded field, never blended
    into the substring score (issue #584).
    """
    parser = argparse.ArgumentParser(
        description="Score a run against a task's substring assertions."
    )
    parser.add_argument(
        "--assertions",
        help="Path to a JSON file with output_contains / output_not_contains lists.",
    )
    parser.add_argument(
        "--output",
        help="Path to the run output text; reads standard input when omitted.",
    )
    parser.add_argument(
        "--scores",
        help="Path to a file of one float score per line (selection-split "
        "scores to average); reads standard input when omitted.",
    )
    parser.add_argument(
        "--compare-to",
        type=float,
        help="Prior selection-split mean. When given, read scores per "
        "--scores/stdin, print the new mean, then KEEP or REJECT per the "
        "strict improve-or-reject gate. Skips --assertions/--output.",
    )
    parser.add_argument(
        "--pruning-only",
        action="store_true",
        help="Use the predeclared pruning-only lexicographic gate. Requires "
        "--compare-to and both context-cost arguments.",
    )
    parser.add_argument(
        "--judge-verdict",
        choices=["agree", "disagree"],
        help="Outcome of an adversarially-verified semantic judge's read of "
        "whether the transcript's conclusion matches the fixture's intended "
        "finding, already resolved by the caller against this same "
        "--compare-to gate. Recorded alongside the substring verdict, never "
        "blended into it. Requires --compare-to; incompatible with "
        "--pruning-only, whose verdict is a context-cost comparison rather "
        "than the substring-derived KEEP/REJECT a semantic judge is scoped to.",
    )
    parser.add_argument(
        "--prior-context-cost",
        type=float,
        help="Context cost of the current skill for a pruning-only gate.",
    )
    parser.add_argument(
        "--candidate-context-cost",
        type=float,
        help="Context cost of the candidate skill for a pruning-only gate.",
    )
    parser.add_argument(
        "--dispatch-trace-verdict",
        choices=["confirmed", "not_confirmed", "unverified"],
        help="Whether a fresh subagent dispatch was confirmed in this run's "
        "own transcript, already resolved by the caller (typically via "
        "evals/scripts/check_dispatch_trace.py's exit code). Recorded "
        "alongside the substring score, never blended into it. Single-run "
        "scoring only -- incompatible with --compare-to, whose scores list "
        "has no single transcript for this to describe.",
    )
    args = parser.parse_args(argv)

    context_costs = (args.prior_context_cost, args.candidate_context_cost)
    if args.pruning_only and (
        args.compare_to is None or any(value is None for value in context_costs)
    ):
        print(
            "error: --pruning-only requires --compare-to, "
            "--prior-context-cost, and --candidate-context-cost",
            file=sys.stderr,
        )
        return 1
    if not args.pruning_only and any(value is not None for value in context_costs):
        print(
            "error: context-cost arguments require --pruning-only",
            file=sys.stderr,
        )
        return 1
    if args.judge_verdict is not None and args.compare_to is None:
        print(
            "error: --judge-verdict requires --compare-to",
            file=sys.stderr,
        )
        return 1
    if args.judge_verdict is not None and args.pruning_only:
        print(
            "error: --judge-verdict is not defined for --pruning-only -- a "
            "pruning verdict is a context-cost comparison, not the "
            "substring-derived KEEP/REJECT a semantic judge is scoped to",
            file=sys.stderr,
        )
        return 1
    if args.dispatch_trace_verdict is not None and args.compare_to is not None:
        print(
            "error: --dispatch-trace-verdict is not defined for --compare-to "
            "-- it describes one run's own transcript, not a selection-split "
            "scores list with no single transcript to describe",
            file=sys.stderr,
        )
        return 1
    if args.compare_to is not None:
        try:
            raw = (
                open(args.scores, encoding="utf-8").read()
                if args.scores
                else sys.stdin.read()
            )
            scores = [float(line) for line in raw.splitlines() if line.strip()]
            mean = split_mean(scores)
            verdict = (
                pruning_compare(
                    args.compare_to,
                    mean,
                    args.prior_context_cost,
                    args.candidate_context_cost,
                )
                if args.pruning_only
                else strict_compare(args.compare_to, mean)
            )
        except (FileNotFoundError, OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        line = f"{mean:.6f} {verdict}"
        if args.judge_verdict == "agree":
            line += " JUDGE_AGREE"
        elif args.judge_verdict == "disagree":
            line += " JUDGE_DISAGREE_REVIEW_REQUIRED"
        print(line)
        return 0

    if not args.assertions:
        print("error: --assertions is required unless --compare-to is used", file=sys.stderr)
        return 1
    try:
        with open(args.assertions, encoding="utf-8") as handle:
            assertions = json.load(handle)
    except FileNotFoundError:
        print(f"error: assertions file not found: {args.assertions}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {args.assertions}: {exc}", file=sys.stderr)
        return 1
    if args.output:
        try:
            with open(args.output, encoding="utf-8") as handle:
                output_text = handle.read()
        except FileNotFoundError:
            print(f"error: output file not found: {args.output}", file=sys.stderr)
            return 1
    else:
        output_text = sys.stdin.read()
    line = f"{score(output_text, assertions):.6f}"
    if args.dispatch_trace_verdict is not None:
        line += " DISPATCH_TRACE_" + args.dispatch_trace_verdict.upper()
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
