"""Tests for evals/scripts/gitapex_compute_rank_correlation.py (issue #1143).

Known-value cases are hand-computed in comments at each assertion, not
cross-checked against scipy/numpy: neither is installed in this
repository's own environment (confirmed directly), matching the module's
own stdlib-only constraint.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import gitapex_compute_rank_correlation as m
import pytest

# ---------------------------------------------------------------------------
# _average_ranks
# ---------------------------------------------------------------------------


def test_average_ranks_no_ties() -> None:
    assert m._average_ranks([10, 20, 30]) == [1.0, 2.0, 3.0]


def test_average_ranks_one_tie_pair() -> None:
    # 10 -> rank 1; the two 20s share ranks 2 and 3 -> average 2.5 each; 30 -> rank 3 -> 4.
    assert m._average_ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]


def test_average_ranks_all_tied() -> None:
    # All three share ranks 1, 2, 3 -> average 2 each.
    assert m._average_ranks([5, 5, 5]) == [2.0, 2.0, 2.0]


# ---------------------------------------------------------------------------
# spearman_rho
# ---------------------------------------------------------------------------


def test_spearman_rho_perfect_positive() -> None:
    assert m.spearman_rho([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0


def test_spearman_rho_perfect_negative() -> None:
    assert m.spearman_rho([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0


def test_spearman_rho_known_tie_example() -> None:
    # xs=[1,2,2,3] -> ranks [1, 2.5, 2.5, 4]; ys=[1,2,3,3] -> ranks [1, 2, 3.5, 3.5].
    # Pearson correlation of those two rank vectors, hand-computed:
    #   mean_rx = mean_ry = 2.5
    #   dx = [-1.5, 0, 0, 1.5]; dy = [-1.5, -0.5, 1, 1]
    #   cov = 2.25 + 0 + 0 + 1.5 = 3.75; var_x = var_y = 4.5
    #   rho = 3.75 / sqrt(4.5 * 4.5) = 3.75 / 4.5 = 5/6
    rho = m.spearman_rho([1, 2, 2, 3], [1, 2, 3, 3])
    assert rho == pytest.approx(5 / 6, abs=1e-9)


def test_spearman_rho_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        m.spearman_rho([1, 2, 3], [1, 2])


def test_spearman_rho_too_few_points_raises() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        m.spearman_rho([1], [1])


def test_spearman_rho_constant_series_raises() -> None:
    with pytest.raises(ValueError, match="constant"):
        m.spearman_rho([1, 1, 1], [1, 2, 3])


# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------


def test_percentile_single_value() -> None:
    assert m._percentile([7.0], 0.5) == 7.0


def test_percentile_linear_interpolation() -> None:
    # pos = 0.5 * (4-1) = 1.5 -> interpolate between sorted[1]=2 and sorted[2]=3, frac 0.5 -> 2.5.
    assert m._percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5


def test_percentile_exact_position_no_interpolation() -> None:
    assert m._percentile([1.0, 2.0, 3.0], 0.5) == 2.0


# ---------------------------------------------------------------------------
# bootstrap_ci
# ---------------------------------------------------------------------------


def test_bootstrap_ci_perfect_correlation_is_a_point() -> None:
    # Every NON-degenerate resample of a perfectly-correlated series is
    # itself perfectly correlated (resampling preserves the elementwise
    # x_i == y_i pairing), so every estimate that does form is exactly
    # 1.0 and the CI collapses to exactly [1.0, 1.0] -- no interpolation
    # needed. A resample can still be degenerate (every one of its n draws
    # landing on the same original index, making both resampled series
    # constant) -- that is a fact about a single-valued series, not a
    # violation of the x_i == y_i invariant, so n_estimates is allowed to
    # land below n_resamples here too (some, not all, of 2000 resamples of
    # this 5-point series are expected to be degenerate).
    rng = random.Random(0)  # noqa: S311 -- statistical resampling, not a security/cryptographic use
    result = m.bootstrap_ci([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], rng=rng)
    assert result.ci_low == 1.0
    assert result.ci_high == 1.0
    assert 0 < result.n_estimates <= 2000


@pytest.mark.parametrize("bad_confidence", [-0.5, 0.0, 1.0, 1.5])
def test_bootstrap_ci_rejects_out_of_range_confidence(bad_confidence: float) -> None:
    # Defeat test (issue #1143 adversarial review): confidence=-0.5 used to
    # silently reverse ci_low/ci_high via _percentile's own negative-index
    # wraparound instead of raising -- verified live before this guard
    # existed.
    with pytest.raises(ValueError, match="confidence must be strictly between 0 and 1"):
        m.bootstrap_ci([1, 2, 3, 4], [4, 3, 2, 1], confidence=bad_confidence, rng=random.Random(0))  # noqa: S311


@pytest.mark.parametrize("bad_n_resamples", [0, -1])
def test_bootstrap_ci_rejects_non_positive_n_resamples(bad_n_resamples: int) -> None:
    # Defeat test: n_resamples=0 used to report the misleading "every one
    # of 0 bootstrap resamples was degenerate" instead of a clear
    # input-validation error -- verified live before this guard existed.
    with pytest.raises(ValueError, match="n_resamples must be a positive integer"):
        m.bootstrap_ci([1, 2, 3, 4], [4, 3, 2, 1], n_resamples=bad_n_resamples, rng=random.Random(0))  # noqa: S311


def test_compute_correlation_rejects_out_of_range_confidence_via_bootstrap_ci() -> None:
    # compute_correlation doesn't re-validate independently -- it calls
    # bootstrap_ci unconditionally, which does. This test proves the
    # validation actually reaches a compute_correlation() caller, not just
    # bootstrap_ci() called directly.
    with pytest.raises(ValueError, match="confidence must be strictly between 0 and 1"):
        m.compute_correlation([1, 2, 3, 4], [4, 3, 2, 1], confidence=-0.5, seed=0)


def test_bootstrap_ci_bounds_ordered_and_contain_point_estimate() -> None:
    xs = [1, 2, 3, 4, 5, 6, 7, 8]
    ys = [2, 1, 4, 3, 6, 5, 8, 9]
    rho = m.spearman_rho(xs, ys)
    result = m.bootstrap_ci(xs, ys, rng=random.Random(0))  # noqa: S311 -- statistical resampling
    assert -1.0 <= result.ci_low <= result.ci_high <= 1.0
    # A percentile bootstrap CI is not guaranteed to contain the point
    # estimate in general, but for a reasonably-sized, non-degenerate
    # sample like this one it should -- a sanity bound, not a law.
    assert result.ci_low <= rho <= result.ci_high


def test_bootstrap_ci_reports_n_estimates_below_n_resamples_when_some_resamples_are_degenerate() -> None:
    # A defeat test for BootstrapResult.n_estimates specifically (issue
    # #1143 adversarial review): a tie-heavy, small input produces some
    # degenerate resamples, so n_estimates must come in strictly below
    # n_resamples -- not silently report the full count regardless of how
    # many resamples were actually thrown away.
    result = m.bootstrap_ci([1, 1, 2], [1, 2, 2], n_resamples=500, rng=random.Random(0))  # noqa: S311
    assert 0 < result.n_estimates < 500


def test_bootstrap_ci_deterministic_given_same_seed() -> None:
    xs = [1, 5, 2, 8, 3, 9, 4]
    ys = [2, 4, 1, 9, 3, 8, 5]
    first = m.bootstrap_ci(xs, ys, rng=random.Random(42))  # noqa: S311 -- statistical resampling
    second = m.bootstrap_ci(xs, ys, rng=random.Random(42))  # noqa: S311 -- statistical resampling
    assert first == second


class _AlwaysZeroRng(random.Random):
    """Stub rng whose randrange always returns 0, so every bootstrap
    resample picks index 0 for every position -- a fully degenerate
    (constant) resample every time, deterministically, without relying on
    astronomically unlikely random luck to exercise this branch. Subclasses
    random.Random (rather than a bare duck-typed object) so it satisfies
    bootstrap_ci's own ``rng: random.Random`` type -- the function needs
    only ``.randrange()``, but the parameter is typed nominally.
    """

    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:
        return 0


def test_bootstrap_ci_raises_when_every_resample_is_degenerate() -> None:
    with pytest.raises(ValueError, match="every one of"):
        m.bootstrap_ci([1, 2, 3], [3, 2, 1], n_resamples=10, rng=_AlwaysZeroRng())


# ---------------------------------------------------------------------------
# compute_correlation / power caveat
# ---------------------------------------------------------------------------


def test_compute_correlation_full_result_shape() -> None:
    result = m.compute_correlation([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], seed=0)
    assert result.n == 5
    assert result.rho == 1.0
    assert result.ci_low == 1.0
    assert result.ci_high == 1.0
    assert result.confidence == m.DEFAULT_CONFIDENCE
    assert result.seed == 0
    assert "very small sample" in result.power_caveat


def test_compute_correlation_is_deterministic_given_same_seed() -> None:
    xs = [1, 5, 2, 8, 3, 9, 4, 6]
    ys = [2, 4, 1, 9, 3, 8, 5, 7]
    first = m.compute_correlation(xs, ys, seed=7)
    second = m.compute_correlation(xs, ys, seed=7)
    assert first == second


@pytest.mark.parametrize(
    ("n", "expected_phrase"),
    [
        (5, "very small sample"),
        (15, "small-to-moderate sample"),
        (40, "large enough"),
    ],
)
def test_power_caveat_scales_with_n(n: int, expected_phrase: str) -> None:
    xs = list(range(n))
    ys = list(range(n))
    result = m.compute_correlation(xs, ys, seed=0, n_resamples=200)
    assert expected_phrase in result.power_caveat


def test_power_caveat_notes_degenerate_fraction_when_present() -> None:
    # A small, tie-heavy input produces some degenerate resamples.
    result = m.compute_correlation([1, 1, 2], [1, 2, 2], seed=0, n_resamples=500)
    assert "degenerate" in result.power_caveat


def test_power_caveat_omits_degenerate_note_when_none_occurred() -> None:
    xs = list(range(50))
    ys = list(range(50))
    result = m.compute_correlation(xs, ys, seed=0, n_resamples=200)
    assert "degenerate" not in result.power_caveat


# ---------------------------------------------------------------------------
# load_pairs
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_load_pairs_happy_path(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "pairs.json",
        json.dumps({"pairs": [{"id": "a", "x": 1.0, "y": 2.0}, {"id": "b", "x": 2.0, "y": 3.0}]}),
    )
    pairs = m.load_pairs(path)
    assert [p.x for p in pairs] == [1.0, 2.0]
    assert [p.y for p in pairs] == [2.0, 3.0]


def test_load_pairs_id_is_optional(tmp_path: Path) -> None:
    path = _write(tmp_path, "pairs.json", json.dumps({"pairs": [{"x": 1.0, "y": 2.0}, {"x": 2.0, "y": 3.0}]}))
    pairs = m.load_pairs(path)
    assert pairs[0].id is None


def test_load_pairs_invalid_json_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "pairs.json", "{not json")
    with pytest.raises(ValueError, match="invalid JSON"):
        m.load_pairs(path)


def test_load_pairs_too_few_pairs_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "pairs.json", json.dumps({"pairs": [{"x": 1.0, "y": 2.0}]}))
    with pytest.raises(ValueError):
        m.load_pairs(path)


def test_load_pairs_non_finite_value_raises(tmp_path: Path) -> None:
    path = _write(tmp_path, "pairs.json", json.dumps({"pairs": [{"x": "nan", "y": 1.0}, {"x": 1.0, "y": 2.0}]}))
    with pytest.raises(ValueError):
        m.load_pairs(path)


def test_load_pairs_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot read"):
        m.load_pairs(tmp_path / "missing.json")


# ---------------------------------------------------------------------------
# main() / CLI
# ---------------------------------------------------------------------------


def test_main_happy_path_exits_zero_and_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(
        tmp_path,
        "pairs.json",
        json.dumps({"pairs": [{"x": i, "y": i} for i in range(6)]}),
    )
    exit_code = m.main(["--pairs-json", str(path), "--n-resamples", "50"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["n"] == 6
    assert payload["rho"] == 1.0
    assert set(payload) == {"n", "rho", "ci_low", "ci_high", "confidence", "n_resamples", "seed", "power_caveat"}


def test_main_missing_pairs_file_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = m.main(["--pairs-json", str(tmp_path / "missing.json")])
    assert exit_code == 2
    assert "not found" in capsys.readouterr().err


def test_main_too_few_pairs_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "pairs.json", json.dumps({"pairs": [{"x": 1.0, "y": 2.0}]}))
    exit_code = m.main(["--pairs-json", str(path)])
    assert exit_code == 2


def test_main_bad_confidence_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "pairs.json", json.dumps({"pairs": [{"x": i, "y": i} for i in range(4)]}))
    exit_code = m.main(["--pairs-json", str(path), "--confidence", "1.5"])
    assert exit_code == 2
    assert "--confidence" in capsys.readouterr().err


def test_main_bad_n_resamples_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "pairs.json", json.dumps({"pairs": [{"x": i, "y": i} for i in range(4)]}))
    exit_code = m.main(["--pairs-json", str(path), "--n-resamples", "0"])
    assert exit_code == 2
    assert "--n-resamples" in capsys.readouterr().err


def test_main_constant_series_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, "pairs.json", json.dumps({"pairs": [{"x": 1.0, "y": i} for i in range(4)]}))
    exit_code = m.main(["--pairs-json", str(path)])
    assert exit_code == 2
    assert "constant" in capsys.readouterr().err


def test_main_seed_is_reproducible_across_invocations(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(
        tmp_path,
        "pairs.json",
        json.dumps(
            {"pairs": [{"x": 1, "y": 5}, {"x": 2, "y": 1}, {"x": 3, "y": 9}, {"x": 4, "y": 3}, {"x": 5, "y": 7}]}
        ),
    )
    m.main(["--pairs-json", str(path), "--seed", "3"])
    first = capsys.readouterr().out
    m.main(["--pairs-json", str(path), "--seed", "3"])
    second = capsys.readouterr().out
    assert first == second
