"""Deterministically resolve a battle-test model route for a Codex caller.

The default route inherits the caller's model. A fixed route is selected only
from a trusted, harness-owned JSON allowlist whose keys are matched exactly.
The script deliberately contains no model catalog: model availability,
execution, and policy belong to the invoking harness. A resolved route is not
a battle-test pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

DEFAULT_TRIALS = 3
MAX_TRIALS = 3


def _validate_model_slug(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be a non-empty, unpadded string")
    return value


def _validate_trials(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_TRIALS
    ):
        raise ValueError(f"trials must be an integer in [1,{MAX_TRIALS}]")
    return value


def validate_fixed_routes(value: object) -> dict[str, str]:
    """Validate and copy an exact caller-model to tester-model allowlist."""
    if not isinstance(value, Mapping):
        raise ValueError("fixed routes must be a JSON object")
    routes: dict[str, str] = {}
    for caller, tester in value.items():
        caller_slug = _validate_model_slug(caller, "fixed-route caller model")
        tester_slug = _validate_model_slug(tester, "fixed-route tester model")
        routes[caller_slug] = tester_slug
    return routes


def route_test_model(
    caller_model: object,
    *,
    trials: object = DEFAULT_TRIALS,
    fixed_routes: object | None = None,
) -> dict[str, object]:
    """Return a stable routing decision.

    With no fixed-route allowlist, the tester inherits the caller model.
    Supplying an allowlist requests fixed routing; an absent exact key is
    INDETERMINATE rather than an implicit fallback.
    """
    caller = _validate_model_slug(caller_model, "caller_model")
    trial_count = _validate_trials(trials)

    if fixed_routes is None:
        return {
            "caller_model": caller,
            "selected_tester_model": caller,
            "model_route": "inherited",
            "requested_trials": trial_count,
            "route_status": "RESOLVED",
            "reason": "tester model inherits the caller model",
        }

    routes = validate_fixed_routes(fixed_routes)
    if caller not in routes:
        return {
            "caller_model": caller,
            "selected_tester_model": None,
            "model_route": "indeterminate",
            "requested_trials": trial_count,
            "route_status": "INDETERMINATE",
            "reason": "caller model is not an exact key in the fixed-route allowlist",
        }

    return {
        "caller_model": caller,
        "selected_tester_model": routes[caller],
        "model_route": "fixed",
        "requested_trials": trial_count,
        "route_status": "RESOLVED",
        "reason": "exact caller-model allowlist match",
    }


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate fixed-route key: {key}")
        result[key] = value
    return result


def load_fixed_routes(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except FileNotFoundError as exc:
        raise ValueError(f"fixed-route file not found: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read fixed-route JSON {path}: {exc}") from exc
    return validate_fixed_routes(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Route a Codex battle-test model and print the decision as JSON."
    )
    parser.add_argument("--caller-model", required=True)
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument(
        "--fixed-routes",
        type=Path,
        help="Trusted, harness-owned JSON object mapping exact caller-model "
        "slugs to fixed tester slugs.",
    )
    args = parser.parse_args(argv)

    try:
        fixed_routes = (
            load_fixed_routes(args.fixed_routes) if args.fixed_routes else None
        )
        decision = route_test_model(
            args.caller_model,
            trials=args.trials,
            fixed_routes=fixed_routes,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(decision, sort_keys=True))
    return 0 if decision["route_status"] == "RESOLVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
