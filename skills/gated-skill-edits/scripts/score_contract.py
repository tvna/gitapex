"""Deterministic substring-contract scorer for a held-out gate. See gitapex#30.

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
import sys
from collections.abc import Mapping


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


def main(argv=None):
    """CLI: score a run's output against a JSON assertions file.

    Reads the assertions from a JSON file (standard library only, no YAML
    dependency) and the run output from ``--output`` or standard input, then
    prints the score.
    """
    parser = argparse.ArgumentParser(
        description="Score a run against a task's substring assertions."
    )
    parser.add_argument(
        "--assertions",
        required=True,
        help="Path to a JSON file with output_contains / output_not_contains lists.",
    )
    parser.add_argument(
        "--output",
        help="Path to the run output text; reads standard input when omitted.",
    )
    args = parser.parse_args(argv)
    with open(args.assertions, encoding="utf-8") as handle:
        assertions = json.load(handle)
    if args.output:
        with open(args.output, encoding="utf-8") as handle:
            output_text = handle.read()
    else:
        output_text = sys.stdin.read()
    print(f"{score(output_text, assertions):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
