"""Deterministic substring-contract scorer for a held-out gate.

Given a task's substring assertions (``output_contains`` /
``output_not_contains`` / ``output_contains_near``) and a run's output text,
returns the fraction of assertions satisfied as a deterministic ``float`` in
``[0, 1]``. Standard library only. Producing the run output is out of scope:
only the scoring step is made deterministic here.

``output_icontains``/``output_not_icontains`` are the case-insensitive form
of ``output_contains``/``output_not_contains`` (matched via
``str.casefold()``), kept as separate, explicit keys rather than a mode flag
on the existing ones -- the same shape established frameworks use
(promptfoo's ``contains``/``icontains``; Hamcrest's
``containsString``/``containsStringIgnoringCase``). Case-sensitive matching
against natural-language agent output produces false regressions when the
only occurrence differs by case (e.g. a title-cased heading), so a fixture
whose text can plausibly vary in case should use the case-insensitive form
deliberately, not as a default. Strictly additive: ``output_contains``/
``output_not_contains`` keep their existing case-sensitive semantics.
``casefold()`` (not ``lower()``) is used for Unicode-correct caseless
matching.

``output_contains``/``output_not_contains`` check presence/absence
independently of each other -- they cannot verify that two substrings are
actually *bound together* (e.g. a repair's own description sitting next to
its own classification label, rather than each merely appearing somewhere in
the output). ``output_contains_near`` closes that gap: each entry is
``{"all": [s1, s2, ...], "window": int}`` and is satisfied only when every
listed substring's first occurrence falls within a ``window``-character span
of every other. ``window`` defaults to 400 when omitted.

A character-window check alone is not sufficient: a short response can
accidentally satisfy a ``near`` window for the *wrong* pairing too, since a
positive-only check cannot distinguish "these are correctly bound" from "the
whole response was too terse to separate them." Pair each
``output_contains_near`` requirement with ``output_not_contains_near``
entries banning that same keyword from also being near each of the other
possible labels, so a swapped assignment is rejected even when compact.
``output_not_contains_near`` shares the same shape and is satisfied when the
entry's pairing does *not* hold.

"Near" requires two conditions together: (1) within ``window`` characters (a
loose backstop), AND (2) no blank line (``"\\n\\n"``, this repository's
paragraph/list-item separator) between the two occurrences. The blank-line
check carries the actual distinction in practice; the character window is a
secondary sanity bound -- a verbose correct paragraph and a terse but
unrelated adjacent one can straddle any fixed character window either way.

Note for callers: this repository also has a separate, CI-side scorer
(waza's own built-in ``expected.*`` grading) that matches
case-insensitively. An exact-case match here always implies a case-folded
match, so any fixture that satisfies this scorer's contract also satisfies
that one -- the two never silently disagree.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

CORRECTNESS_DECIMALS = 6  # rounding precision for the reported correctness score


def _assertion_list(assertions: Mapping[str, Any], key: str) -> list[Any]:
    """Return ``assertions[key]`` as a list, failing loudly on a bad shape.

    A missing or ``None`` value is an empty list. A bare string (the natural
    ``{"output_contains": "LGTM"}`` mistake) is rejected rather than scored
    per character, which would silently miscount.
    """
    value = assertions.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list of substrings, got {type(value).__name__}")
    return value


def _near_entry_list(assertions: Mapping[str, Any], key: str = "output_contains_near") -> list[Any]:
    value = assertions.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list of {{'all': [...], 'window': int}} objects")
    return value


_DEFAULT_NEAR_WINDOW = 400


def _near_satisfied(text: str, entry: Any) -> bool:
    """One ``output_contains_near`` entry is satisfied iff every substring in
    ``entry["all"]`` occurs in ``text`` (each at its first occurrence), the
    whole span from the earliest start to the latest end is no wider than
    ``entry.get("window", 400)`` characters, AND no blank line separates the
    occurrences (see this module's docstring for why both checks are used
    together, not the character window alone)."""
    if not isinstance(entry, Mapping):
        raise ValueError(f"output_contains_near entries must be mappings, got {type(entry).__name__}")
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


def score(output_text: str | None, assertions: Mapping[str, Any]) -> float:
    """Return the fraction of substring assertions satisfied, in ``[0, 1]``.

    ``assertions`` is a mapping with optional ``output_contains`` (each
    substring must appear in ``output_text``), ``output_not_contains`` (each
    must be absent), ``output_icontains``/``output_not_icontains`` (the same
    two checks, case-insensitively -- see this module's docstring), and
    ``output_contains_near``/``output_not_contains_near`` (co-occurrence
    within a character window -- see this module's docstring). Identical
    inputs always produce the same value.

    A ``None`` ``output_text`` is treated as the empty string. Each list
    entry is one assertion, so a duplicated substring is weighted twice and
    an empty-string substring is always satisfied; that is the fixture's
    responsibility. Raises ``ValueError`` when ``assertions`` is not a
    mapping, when a value is not a list, or when the assertion set is empty,
    since a fixture with nothing to assert cannot score a run.
    """
    if not isinstance(assertions, Mapping):
        raise ValueError(f"assertions must be a mapping, got {type(assertions).__name__}")
    contains = _assertion_list(assertions, "output_contains")
    not_contains = _assertion_list(assertions, "output_not_contains")
    icontains = _assertion_list(assertions, "output_icontains")
    not_icontains = _assertion_list(assertions, "output_not_icontains")
    near = _near_entry_list(assertions, "output_contains_near")
    not_near = _near_entry_list(assertions, "output_not_contains_near")
    total = len(contains) + len(not_contains) + len(icontains) + len(not_icontains) + len(near) + len(not_near)
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


def split_mean(scores: Iterable[float]) -> float:
    """Return the arithmetic mean of a non-empty sequence of scores."""
    scores = list(scores)
    if not scores:
        raise ValueError("cannot take the mean of an empty score list")
    for index, value in enumerate(scores):
        _validate_correctness(value, f"score[{index}]")
    return sum(scores) / len(scores)


def _validate_correctness(value: float, label: str) -> None:
    """Reject correctness values outside the finite ``[0, 1]`` contract."""
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number in [0,1]")
    try:
        valid = math.isfinite(value) and 0 <= value <= 1
    except TypeError as exc:
        raise ValueError(f"{label} must be a finite number in [0,1]") from exc
    if not valid:
        raise ValueError(f"{label} must be a finite number in [0,1]")


def _validate_context_cost(value: float, label: str) -> None:
    """Reject context costs that are non-finite or negative."""
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite non-negative number")
    try:
        valid = math.isfinite(value) and value >= 0
    except TypeError as exc:
        raise ValueError(f"{label} must be a finite non-negative number") from exc
    if not valid:
        raise ValueError(f"{label} must be a finite non-negative number")


def _published_correctness(value: float) -> float:
    """Normalize correctness to the precision emitted by this CLI."""
    return round(value, CORRECTNESS_DECIMALS)


def _validate_published_prior(value: float) -> None:
    """Require a prior copied from this CLI's six-decimal output."""
    if value != _published_correctness(value):
        raise ValueError("prior correctness must use the CLI's published six-decimal precision")


def strict_compare(before_mean: float, after_mean: float) -> str:
    """Return ``"KEEP"`` iff ``after_mean`` strictly exceeds ``before_mean``.

    Ties are rejected: a tied or worse selection-split mean is ``"REJECT"``.
    """
    _validate_correctness(before_mean, "before correctness")
    _validate_correctness(after_mean, "after correctness")
    _validate_published_prior(before_mean)
    after = _published_correctness(after_mean)
    return "KEEP" if after > before_mean else "REJECT"


def pruning_compare(
    before_correctness: float,
    after_correctness: float,
    before_context_cost: float,
    after_context_cost: float,
) -> str:
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


def main(argv: list[str] | None = None) -> int:
    """CLI: score a run's output against a JSON assertions file.

    Reads the assertions from a JSON file and the run output from
    ``--output`` or standard input, then prints the score. With
    ``--compare-to``, treats each line read from ``--scores`` (or standard
    input, one float per line) as one task's selection-split score, prints
    the mean, and prints ``KEEP``/``REJECT`` against the given prior mean per
    the strict improve-or-reject gate. With ``--compare-to`` and
    ``--judge-verdict``, additionally appends the outcome of an
    adversarially-verified semantic judge (already run by the caller; this
    script does not call a model) as ``JUDGE_AGREE`` or
    ``JUDGE_DISAGREE_REVIEW_REQUIRED`` -- recorded alongside the substring
    verdict, never blended into it. With ``--dispatch-trace-verdict``
    (single-run scoring only), similarly appends whether a fresh subagent
    dispatch was confirmed in this run's own transcript (already resolved by
    the caller) as ``DISPATCH_TRACE_CONFIRMED``, ``DISPATCH_TRACE_NOT_CONFIRMED``,
    or ``DISPATCH_TRACE_UNVERIFIED``. With ``--schema-conformance-verdict``
    (single-run scoring only), similarly appends whether the run's own
    output carried a structured verdict conforming to this repository's
    output schema (already resolved by the caller) as
    ``SCHEMA_CONFORMANCE_CONFIRMED``, ``SCHEMA_CONFORMANCE_INVALID``, or
    ``SCHEMA_CONFORMANCE_NOT_ATTEMPTED``. Every verdict field beyond the
    substring score itself is a recorded, caller-resolved input passed
    through verbatim -- this script never derives one on its own.
    """
    parser = argparse.ArgumentParser(description="Score a run against a task's substring assertions.")
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
        "own transcript, already resolved by the caller. Recorded alongside "
        "the substring score, never blended into it. Single-run scoring "
        "only -- incompatible with --compare-to, whose scores list has no "
        "single transcript for this to describe.",
    )
    parser.add_argument(
        "--schema-conformance-verdict",
        choices=["confirmed", "invalid", "not_attempted"],
        help="Whether this run's own output carried a structured verdict "
        "conforming to this repository's output schema, already resolved "
        "by the caller. Recorded alongside the substring score, never "
        "blended into it. Single-run scoring only -- incompatible with "
        "--compare-to, whose scores list has no single run output for this "
        "to describe.",
    )
    args = parser.parse_args(argv)

    context_costs = (args.prior_context_cost, args.candidate_context_cost)
    if args.pruning_only and (args.compare_to is None or any(value is None for value in context_costs)):
        print(
            "error: --pruning-only requires --compare-to, --prior-context-cost, and --candidate-context-cost",
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
    if args.schema_conformance_verdict is not None and args.compare_to is not None:
        print(
            "error: --schema-conformance-verdict is not defined for "
            "--compare-to -- it describes one run's own output, not a "
            "selection-split scores list with no single run output to describe",
            file=sys.stderr,
        )
        return 1
    if args.compare_to is not None:
        try:
            raw = (
                Path(args.scores).read_text(encoding="utf-8")
                if args.scores
                else sys.stdin.buffer.read().decode("utf-8")
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
        with Path(args.assertions).open(encoding="utf-8") as handle:
            assertions = json.load(handle)
    except FileNotFoundError:
        print(f"error: assertions file not found: {args.assertions}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"error: could not decode assertions file {args.assertions}: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {args.assertions}: {exc}", file=sys.stderr)
        return 1
    if args.output:
        try:
            with Path(args.output).open(encoding="utf-8") as handle:
                output_text = handle.read()
        except FileNotFoundError:
            print(f"error: output file not found: {args.output}", file=sys.stderr)
            return 1
        except UnicodeDecodeError as exc:
            print(f"error: could not decode output file {args.output}: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            output_text = sys.stdin.buffer.read().decode("utf-8")
        except UnicodeDecodeError as exc:
            print(f"error: could not decode standard input: {exc}", file=sys.stderr)
            return 1
    line = f"{score(output_text, assertions):.6f}"
    if args.dispatch_trace_verdict is not None:
        line += " DISPATCH_TRACE_" + args.dispatch_trace_verdict.upper()
    if args.schema_conformance_verdict is not None:
        line += " SCHEMA_CONFORMANCE_" + args.schema_conformance_verdict.upper()
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
