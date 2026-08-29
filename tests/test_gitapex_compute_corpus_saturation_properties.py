"""Hypothesis property layer for
``evals/scripts/gitapex_compute_corpus_saturation.py`` (issue #1461).

Why property-based here, and not only the example tests in
``test_gitapex_compute_corpus_saturation.py``: this module's classification
is a set partition over generated per-model score tables, and the defect
class that matters is a *silent* mis-partition -- a fixture counted in two
buckets, or in neither, so the reported rate is wrong while every example
test still passes because none of them happened to generate that shape.
Line coverage cannot close that; input-shape generation can.

Two properties are model-based rather than self-consistent, which is what
lets them fail a buggy implementation at all:
:func:`test_saturation_matches_an_independently_computed_expectation` and
:func:`test_uniformly_hard_matches_an_independently_computed_expectation`
recompute the intended answer from the generated table directly, so the
module's own output never defines correctness.

The remaining properties are invariants the report's own arithmetic must
satisfy for the printed percentages to mean what they say.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import gitapex_compute_corpus_saturation as mod
from hypothesis import given, settings
from hypothesis import strategies as st

# Scores drawn from a small ladder rather than arbitrary floats: real fixture
# scores are fractions of satisfied assertions, and a coarse ladder makes ties
# (the case uniformly-hard turns on) actually occur instead of being
# vanishingly unlikely.
_SCORES = st.sampled_from([0.0, 0.25, 0.5, 0.75, 0.833333, 1.0])
_MODEL_IDS = st.lists(
    st.sampled_from(["model-a", "model-b", "model-c", "model-d"]),
    min_size=1,
    max_size=4,
    unique=True,
)
_FIXTURE_IDS = st.lists(
    st.sampled_from(["f1", "f2", "f3", "f4", "f5"]),
    min_size=1,
    max_size=5,
    unique=True,
)


@st.composite
def _score_tables(draw: st.DrawFn) -> dict[str, dict[str, float]]:
    """A ``model_id -> fixture_id -> score`` table, some cells omitted."""
    models = draw(_MODEL_IDS)
    fixtures = draw(_FIXTURE_IDS)
    table: dict[str, dict[str, float]] = {}
    for model in models:
        scored = draw(st.lists(st.sampled_from(fixtures), min_size=0, max_size=len(fixtures), unique=True))
        table[model] = {fixture: draw(_SCORES) for fixture in scored}
    return table


@contextmanager
def _materialized(table: dict[str, dict[str, float]]) -> Iterator[Path]:
    """Write a generated table out as real per-model result files.

    A fresh directory per example, deliberately: pytest's own ``tmp_path`` is
    function-scoped, so every Hypothesis example inside one test would share
    it and leave the previous example's files behind -- state leakage that
    would make a later example read a table it was never given.
    """
    with tempfile.TemporaryDirectory() as raw:
        run_dir = Path(raw) / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        for index, (model, scores) in enumerate(sorted(table.items())):
            payload = {
                "model_id": model,
                "scores": [{"fixture_id": f, "score": s} for f, s in sorted(scores.items())],
            }
            (run_dir / f"m{index}.json").write_text(json.dumps(payload), encoding="utf-8")
        yield run_dir


def _expected_complete(table: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """The fixtures every model in the table scored, computed independently."""
    models = sorted(table)
    every_fixture = sorted({f for scores in table.values() for f in scores})
    return {
        fixture: {m: table[m][fixture] for m in models}
        for fixture in every_fixture
        if all(fixture in table[m] for m in models)
    }


@settings(max_examples=150, deadline=None)
@given(table=_score_tables())
def test_saturation_matches_an_independently_computed_expectation(
    table: dict[str, dict[str, float]],
) -> None:
    with _materialized(table) as run_dir:
        report = mod.compute_saturation(run_dir)

    expected = _expected_complete(table)
    expected_saturated = {f for f, s in expected.items() if all(v == 1.0 for v in s.values())}

    assert {f.fixture_id for f in report.saturated} == expected_saturated


@settings(max_examples=150, deadline=None)
@given(table=_score_tables())
def test_uniformly_hard_matches_an_independently_computed_expectation(
    table: dict[str, dict[str, float]],
) -> None:
    with _materialized(table) as run_dir:
        report = mod.compute_saturation(run_dir)

    expected = _expected_complete(table)
    expected_hard = {f for f, s in expected.items() if len(set(s.values())) == 1 and set(s.values()) != {1.0}}

    assert {f.fixture_id for f in report.uniformly_hard} == expected_hard


@settings(max_examples=150, deadline=None)
@given(table=_score_tables())
def test_saturated_and_discriminating_always_partition_the_complete_set(
    table: dict[str, dict[str, float]],
) -> None:
    with _materialized(table) as run_dir:
        report = mod.compute_saturation(run_dir)

    saturated = {f.fixture_id for f in report.saturated}
    discriminating = {f.fixture_id for f in report.discriminating}
    complete = {f.fixture_id for f in report.complete}

    assert saturated | discriminating == complete
    assert saturated & discriminating == set()


@settings(max_examples=150, deadline=None)
@given(table=_score_tables())
def test_uniformly_hard_is_always_a_subset_of_discriminating(
    table: dict[str, dict[str, float]],
) -> None:
    with _materialized(table) as run_dir:
        report = mod.compute_saturation(run_dir)

    assert {f.fixture_id for f in report.uniformly_hard} <= {f.fixture_id for f in report.discriminating}


@settings(max_examples=150, deadline=None)
@given(table=_score_tables())
def test_a_computable_report_never_divides_by_an_empty_set(
    table: dict[str, dict[str, float]],
) -> None:
    """The printed percentages exist only when there is something to divide by."""
    with _materialized(table) as run_dir:
        report = mod.compute_saturation(run_dir)
    text = mod.format_report(report)

    if report.computable:
        assert len(report.complete) > 0
        assert "percent" in text
    else:
        assert "NOT COMPUTABLE" in text
        assert "percent" not in text


@settings(max_examples=100, deadline=None)
@given(table=_score_tables())
def test_report_never_raises_on_any_well_formed_table(
    table: dict[str, dict[str, float]],
) -> None:
    """Report-only means every well-formed run directory renders and exits 0."""
    with _materialized(table) as run_dir:
        assert mod.main([str(run_dir)]) == 0
