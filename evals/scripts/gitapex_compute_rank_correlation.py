"""Spearman rank correlation plus a bootstrap confidence interval between two
paired numeric series (issue #1143).

Before this script, no file anywhere under `evals/scripts/` or
`.github/scripts/` implemented a correlation or statistical-confidence-
interval utility -- the only existing statistical mention in this
repository was `waza`'s own external bootstrap-confidence-interval
behavior at `trials_per_task > 1`, documented but never independently
implemented here. This script is the tool half of issue #1143's own two-
part deliverable (the other half is a held-out labeled corpus, see
`effectiveness-corpus.json`/`effectiveness-corpus-methodology.md` in this
same directory); `gitapex_run_effectiveness_correlation.py` wires the two
together.

The statistics themselves need no numpy/scipy, per issue #1143's own
Constraints section ("must not depend on the waza binary (only on this
repository's own tooling..)") -- this repository does not vendor either
(confirmed: neither is a `pyproject.toml` dependency, and neither imports
in this repository's own `.venv`), so Spearman's rho is computed here as
the Pearson correlation of average-rank-transformed data (the standard
general definition, correct with or without tied values -- the simplified
`1 - 6*sum(d**2)/(n*(n**2-1))` shortcut some references quote is only exact
when no ties exist, and this script's own intended input -- a handful of
skills, several of which may share the same illustrative x-metric value --
cannot assume that), and the confidence interval by percentile bootstrap
(resample paired observations with replacement, recompute rho, take
percentiles of the resulting distribution) rather than exact permutation.
This module is not otherwise dependency-free, though: like every other CLI
in this directory (`gitapex_run_ablation.py`, `gitapex_check_dimension_coverage.py`),
it uses `pydantic` for post-`argparse` CLI-argument validation -- run it
with `uv run`, not a bare `python3` (see Usage:: below).

**Why bootstrap, not exact permutation, for the CI**: issue #1143's own
Acceptance Criteria Map names "a bootstrap or exact permutation confidence
interval" as two acceptable options, not both. A permutation test's
native output is a p-value for a null hypothesis (observed rho vs. the
distribution of rho under random pairing) -- turning that into a genuine
confidence interval requires inverting the test (searching for the range
of shift values the test fails to reject), a materially more complex
procedure than this issue's own scope warrants. Percentile bootstrap
produces a CI directly from one resampling loop and is the more commonly
used method for a rank correlation's own sampling distribution, which is
not well approximated by a normal/Fisher-z interval at small n -- exactly
the regime this repository's own use case (a labeled corpus of at most a
few dozen skills) sits in.

**Small-sample power is a first-class, disclosed part of this tool's own
output, not left to the caller to infer** -- issue #1143's own Constraints
section: "Sample size and statistical power limitations must be disclosed
in the tool's own output, not just in this issue." ``power_caveat`` in
both ``CorrelationResult`` and the CLI's JSON output states this always,
scaled to the actual ``n`` passed in, never only in this module's own
docstring where a caller reading JSON output would never see it.

Exit code contract, matching `gitapex_run_ablation.py`'s own 2/1/0 split
(state which class applies -- this script never shells out to another
process, so its own "execution failure" class never applies and is
omitted, matching `gitapex_check_dimension_coverage.py`'s own simpler 2/0
convention for the same reason): 2 means the input itself was malformed
(fewer than 2 pairs, non-finite x/y, an out-of-range `--confidence`, a
non-positive `--n-resamples`, or a degenerate series with zero variance
that makes rho undefined); 0 means success.

Usage (``uv run`` -- see the dependency note above)::

    uv run python3 evals/scripts/gitapex_compute_rank_correlation.py --pairs-json PAIRS.json
                                                             [--confidence 0.95]
                                                             [--n-resamples 2000]
                                                             [--seed 0]

``PAIRS.json`` shape: ``{"pairs": [{"id": "optional-label", "x": 1.0, "y": 2.0}, ...]}``.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

# Fixed, not time-seeded: a caller re-running this tool against the same
# pairs gets the same CI back, matching this repository's broader
# hermetic/reproducible-by-default convention (e.g. gitapex_run_ablation.py's
# own explicit, allowlisted environment). --seed overrides it for a caller
# who deliberately wants an independent resampling draw.
DEFAULT_SEED = 0
DEFAULT_N_RESAMPLES = 2000
DEFAULT_CONFIDENCE = 0.95
# Below this many paired observations, a bootstrap CI is built from too few
# distinct resampling outcomes to trust as anything more than a rough
# signal -- a widely used rule of thumb for small-sample bootstrap, not a
# claim this repository has independently derived. Chosen as a disclosed
# threshold in this tool's own output rather than a silent, unstated one.
SMALL_N_THRESHOLD = 10
MODERATE_N_THRESHOLD = 30


def _average_ranks(values: Sequence[float]) -> list[float]:
    """Rank ``values`` ascending, 1-indexed, with tied values sharing the
    average of the ranks they span (the standard tie-handling convention
    Spearman's rho requires -- e.g. two values tied for 2nd/3rd place both
    receive rank 2.5).
    """
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        # Positions i..j (0-indexed) are tied; their shared rank is the
        # mean of the 1-indexed ranks i+1..j+1.
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation of ``xs``/``ys``. Raises ``ValueError`` if either
    series has zero variance (every value identical) -- correlation is
    undefined against a constant series, not zero, and silently returning
    0.0 would misrepresent "undefined" as "measured no relationship."
    """
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    var_x = sum(d * d for d in dx)
    var_y = sum(d * d for d in dy)
    if var_x == 0 or var_y == 0:
        raise ValueError("correlation is undefined against a constant (zero-variance) series")
    cov = sum(a * b for a, b in zip(dx, dy, strict=True))
    return cov / math.sqrt(var_x * var_y)


def spearman_rho(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman's rank correlation coefficient between ``xs`` and ``ys``:
    the Pearson correlation of their average-rank transforms. Correct with
    or without tied values (see module docstring for why the tie-free
    shortcut formula is not used here). Raises ``ValueError`` via
    ``_pearson`` if either series is constant (all ranks tied).
    """
    if len(xs) != len(ys):
        raise ValueError(f"xs and ys must be the same length, got {len(xs)} and {len(ys)}")
    if len(xs) < 2:
        raise ValueError(f"need at least 2 paired observations, got {len(xs)}")
    return _pearson(_average_ranks(xs), _average_ranks(ys))


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """The ``q``-quantile (``q`` in [0, 1]) of already-sorted ``sorted_values``,
    by linear interpolation between the two nearest ranks -- the same
    "linear" method NumPy's own ``percentile`` defaults to, chosen so this
    hand-rolled implementation reproduces a widely recognized convention
    rather than an ad hoc one.
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = q * (n - 1)
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return sorted_values[int(pos)]
    frac = pos - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


@dataclass(frozen=True)
class BootstrapResult:
    """A percentile bootstrap run's own CI plus how many of its resamples
    actually produced an estimate. Returning ``n_estimates`` alongside the
    interval (rather than only the two bounds) is what lets a caller learn
    the degenerate-resample rate from the one resampling pass that already
    computed it, instead of a second, separately-seeded pass recomputing
    the same draws just to count them -- see ``compute_correlation``,
    which relied on exactly that fragile re-derivation before an
    adversarial review round flagged it (issue #1143): a future change to
    this function's own internal draw order would have silently desynced
    a second, independently-seeded replay loop from the real resampling,
    misreporting the degenerate fraction with no test catching it, since
    both loops would still run to completion without error.
    """

    ci_low: float
    ci_high: float
    n_estimates: int


def bootstrap_ci(
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    confidence: float = DEFAULT_CONFIDENCE,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    rng: random.Random,
) -> BootstrapResult:
    """Percentile bootstrap confidence interval for ``spearman_rho(xs, ys)``.

    Resamples paired indices with replacement ``n_resamples`` times,
    recomputing rho each time; a resample landing on a constant series
    (``spearman_rho`` raising ``ValueError``) contributes no estimate to
    the distribution rather than crashing the whole run -- a degenerate
    resample is not itself a valid rho, and small-n inputs make such a
    resample more likely, not rarer. Raises ``ValueError`` if every single
    resample was degenerate (no estimate could be formed at all), which a
    silently empty-but-successful CI would misreport as "computed."

    ``confidence``/``n_resamples`` are validated here, not only by the CLI
    (``_ComputeRankCorrelationArgs``) -- this function, and
    ``compute_correlation`` above it, are a directly importable API this
    module's own tests already call without going through ``main()``
    (issue #1143 adversarial review round: confirmed live that an
    out-of-range ``confidence`` silently reverses ``ci_low``/``ci_high``
    via ``_percentile``'s own negative-index wraparound, e.g.
    ``confidence=-0.5`` returned ``ci_low > ci_high``; a non-positive
    ``n_resamples`` produced the misleading "every one of 0 ... was
    degenerate" message instead of a clear input-validation error). Raises
    ``ValueError`` -- the same exception type every other malformed-input
    rejection in this module already raises.
    """
    if not (0 < confidence < 1):
        raise ValueError(f"confidence must be strictly between 0 and 1, got {confidence}")
    if n_resamples <= 0:
        raise ValueError(f"n_resamples must be a positive integer, got {n_resamples}")
    n = len(xs)
    estimates: list[float] = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        try:
            estimates.append(spearman_rho([xs[i] for i in idx], [ys[i] for i in idx]))
        except ValueError:
            continue
    if not estimates:
        raise ValueError(
            f"every one of {n_resamples} bootstrap resamples was degenerate "
            "(constant ranks) -- cannot compute a confidence interval"
        )
    estimates.sort()
    alpha = (1 - confidence) / 2
    return BootstrapResult(
        ci_low=_percentile(estimates, alpha),
        ci_high=_percentile(estimates, 1 - alpha),
        n_estimates=len(estimates),
    )


def _power_caveat(n: int, n_resamples: int, n_bootstrap_estimates: int) -> str:
    """A human-readable statement of this result's own statistical power
    limitation, scaled to ``n`` -- always present (see module docstring's
    "Small-sample power" section), never only a hedge a caller has to know
    to look for elsewhere.
    """
    if n < SMALL_N_THRESHOLD:
        severity = (
            f"n={n} is a very small sample: treat rho as an indicative point estimate only, "
            "not a precise measurement, and expect the bootstrap CI below to be wide."
        )
    elif n < MODERATE_N_THRESHOLD:
        severity = (
            f"n={n} is a small-to-moderate sample: the bootstrap CI below should be read as a "
            "rough range, not a precise interval."
        )
    else:
        severity = f"n={n} is large enough for the bootstrap CI below to be reasonably stable."
    degenerate_fraction = 1 - (n_bootstrap_estimates / n_resamples)
    degenerate_note = (
        f" {degenerate_fraction:.1%} of the {n_resamples} bootstrap resamples were degenerate "
        "(a constant-ranked resample) and were excluded from the interval, which itself signals "
        "a small or low-variance input."
        if degenerate_fraction > 0
        else ""
    )
    return severity + degenerate_note


@dataclass(frozen=True)
class CorrelationResult:
    """One correlation computation's full, disclosed result."""

    n: int
    rho: float
    ci_low: float
    ci_high: float
    confidence: float
    n_resamples: int
    seed: int
    power_caveat: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "rho": self.rho,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "confidence": self.confidence,
            "n_resamples": self.n_resamples,
            "seed": self.seed,
            "power_caveat": self.power_caveat,
        }


def compute_correlation(
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    confidence: float = DEFAULT_CONFIDENCE,
    n_resamples: int = DEFAULT_N_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> CorrelationResult:
    """Spearman's rho between ``xs``/``ys`` plus its percentile bootstrap CI,
    bundled with a disclosed power caveat. The single entry point both the
    CLI (``main``) and ``gitapex_run_effectiveness_correlation.py`` use.
    """
    rho = spearman_rho(xs, ys)
    rng = random.Random(seed)  # noqa: S311 -- statistical resampling, not a security/cryptographic use
    n = len(xs)
    bootstrap = bootstrap_ci(xs, ys, confidence=confidence, n_resamples=n_resamples, rng=rng)
    return CorrelationResult(
        n=n,
        rho=rho,
        ci_low=bootstrap.ci_low,
        ci_high=bootstrap.ci_high,
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
        power_caveat=_power_caveat(n, n_resamples, bootstrap.n_estimates),
    )


class _Pair(BaseModel):
    id: str | None = None
    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def _must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("x and y must be finite numbers")
        return value


class _PairsFile(BaseModel):
    pairs: list[_Pair] = Field(min_length=2)


class _ComputeRankCorrelationArgs(BaseModel):
    """Validates the parsed CLI namespace immediately after
    ``parser.parse_args()``, the same pattern `gitapex_run_ablation.py`'s own
    ``_RunAblationArgs`` and `gitapex_check_dimension_coverage.py`'s own
    ``_CheckDimensionCoverageArgs`` already establish."""

    pairs_json: Path
    confidence: float
    n_resamples: int
    seed: int

    @field_validator("pairs_json")
    @classmethod
    def _pairs_json_must_exist(cls, value: Path) -> Path:
        if not value.is_file():
            raise ValueError(f"pairs file not found: {value}")
        return value

    @field_validator("confidence")
    @classmethod
    def _confidence_must_be_in_open_unit_interval(cls, value: float) -> float:
        if not (0 < value < 1):
            raise ValueError(f"--confidence must be strictly between 0 and 1, got {value}")
        return value

    @field_validator("n_resamples")
    @classmethod
    def _n_resamples_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError(f"--n-resamples must be a positive integer, got {value}")
        return value


def _validation_error_message(exc: ValidationError) -> str:
    """The first error's original message, unwrapped from pydantic's own
    "Value error, " prefix -- matches every other CLI in this directory's
    own established error-text convention."""
    error = exc.errors()[0]
    ctx = error.get("ctx") or {}
    original = ctx.get("error")
    if isinstance(original, Exception):
        return str(original)
    return str(error["msg"])


def load_pairs(path: Path) -> list[_Pair]:
    """Load and validate a ``--pairs-json`` file's ``pairs`` array. Raises
    ``ValueError`` on unreadable/non-UTF-8/invalid-JSON content or a shape
    that fails ``_PairsFile`` validation (fewer than 2 pairs, a non-finite
    x/y, a missing required key) -- one exception type for every malformed
    input, matching this directory's other loaders.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot read pairs file {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in pairs file {path}: {exc}") from exc
    try:
        parsed = _PairsFile.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"pairs file {path}: {_validation_error_message(exc)}") from exc
    return parsed.pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute Spearman rank correlation and a bootstrap confidence interval "
        "between two paired numeric series, disclosing a sample-size power caveat."
    )
    parser.add_argument(
        "--pairs-json", required=True, type=Path, help="Path to a {'pairs': [{id,x,y}, ...]} JSON file."
    )
    parser.add_argument("--confidence", type=float, default=DEFAULT_CONFIDENCE)
    parser.add_argument("--n-resamples", type=int, default=DEFAULT_N_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    try:
        validated_args = _ComputeRankCorrelationArgs(
            pairs_json=args.pairs_json,
            confidence=args.confidence,
            n_resamples=args.n_resamples,
            seed=args.seed,
        )
    except ValidationError as exc:
        print(f"error: {_validation_error_message(exc)}", file=sys.stderr)
        return 2

    try:
        pairs = load_pairs(validated_args.pairs_json)
        xs = [p.x for p in pairs]
        ys = [p.y for p in pairs]
        result = compute_correlation(
            xs,
            ys,
            confidence=validated_args.confidence,
            n_resamples=validated_args.n_resamples,
            seed=validated_args.seed,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result.to_json_dict(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
