"""Deterministic substring-contract scorer for a held-out gate.

Given a task's substring assertions (``output_contains`` /
``output_not_contains``) and a run's output text, returns the fraction of
assertions satisfied as a deterministic ``float`` in ``[0, 1]``. Standard
library only, so the scorer stays self-contained with no external
dependency. Producing the run output is out of scope: only the scoring step
is made deterministic here.
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


def score(output_text, assertions):
    """Return the fraction of substring assertions satisfied, in ``[0, 1]``.

    ``assertions`` is a mapping with optional ``output_contains`` (each
    substring must appear in ``output_text``) and ``output_not_contains``
    (each must be absent). Identical inputs always produce the same value.

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
    total = len(contains) + len(not_contains)
    if total == 0:
        raise ValueError(
            "empty assertion set: a fixture with no output_contains or "
            "output_not_contains cannot score a run"
        )
    text = output_text or ""
    satisfied = sum(s in text for s in contains) + sum(s not in text for s in not_contains)
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
    never blended into the substring mean or verdict.
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
        "blended into it. Requires --compare-to.",
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
    print(f"{score(output_text, assertions):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
