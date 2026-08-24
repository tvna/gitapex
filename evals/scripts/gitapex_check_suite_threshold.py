#!/usr/bin/env python3
"""Check a ``gitapex_run_eval_suite.py`` result JSON against its suite's own
``metrics[]`` threshold (issue #1259 reuse/simplification-review finding).

Extracted from an inline ``python3 -c "..."`` one-liner (JSON+YAML parsing,
an "exactly one ``metrics[]`` entry" invariant, and a threshold-direction
comparison) that ``waza-eval-matrix.yml``'s ``eval-matrix`` and
``eval-matrix-hf-gemma4`` jobs both carried byte-for-byte duplicated inline
(a third copy lives in ``waza-eval-gate.yml``, out of this PR's scope --
issue #1259 only touches ``waza-eval-matrix.yml``). This repository's own
established convention for CI-step logic this size is a real, tested,
committed script (``gitapex_set_config_model.py``, called by name from the
very same step) -- not opaque shell-embedded Python with no test coverage
of its own. This exact comparison already needed two adversarial-review
bug fixes once while still inline (see the step's own former comment,
carried into this module's own history); a third untested inline copy was
a realistic path to silent divergence.

Usage (matching ``gitapex_set_config_model.py``'s own argv-only CLI shape)::

    uv run --frozen python3 evals/scripts/gitapex_check_suite_threshold.py \\
        results/<model>/<skill>.json evals/<skill>/eval.yaml

Exit code contract: 0 if the result's ``mean_score`` is >= the suite's own
single ``metrics[]`` entry's ``threshold``; 1 otherwise, and 1 also for a
malformed/missing suite ``metrics[]`` (not exactly one entry) or a missing
``mean_score``/``threshold`` key -- printed as a clear one-line message to
stderr instead of a bare traceback (this repository's own fail-loud-with-a-
legible-message convention, matching ``gitapex_set_config_model.py``'s own
``main()``), not a change to which exit code either calling job's own
``failed=1`` bash logic sees versus the original inline one-liner's
observable behavior. Only a wrong argument count exits 2, matching that
same sibling script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml


def check_suite_threshold(result: Any, suite: Any) -> tuple[bool, str]:
    """Return ``(passed, message)`` for ``result`` (a parsed
    ``gitapex_run_eval_suite.py`` JSON output) against ``suite`` (a parsed
    ``eval.yaml``). Raises ``ValueError`` if ``suite`` does not declare
    exactly one ``metrics[]`` entry, or if either input is not a mapping or
    is missing the one key this check needs from it."""
    if not isinstance(suite, dict):
        raise ValueError(f"eval.yaml did not parse to a mapping, got {type(suite).__name__}")
    metrics = suite.get("metrics") or []
    if len(metrics) != 1:
        raise ValueError(f"expected exactly 1 metrics[] entry, got {len(metrics)}")
    if not isinstance(metrics[0], dict) or "threshold" not in metrics[0]:
        raise ValueError("suite's metrics[0] is missing 'threshold'")
    threshold = metrics[0]["threshold"]
    if not isinstance(result, dict) or "mean_score" not in result:
        raise ValueError("result is missing 'mean_score'")
    mean_score = result["mean_score"]
    return mean_score >= threshold, f"mean_score={mean_score!r} threshold={threshold!r}"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: gitapex_check_suite_threshold.py <result.json> <eval.yaml>",
            file=sys.stderr,
        )
        return 2

    result_path, suite_path = Path(argv[1]), Path(argv[2])
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        suite = yaml.safe_load(suite_path.read_text(encoding="utf-8"))
        passed, message = check_suite_threshold(result, suite)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError, ValueError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(message, file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
