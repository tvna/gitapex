#!/usr/bin/env python3
"""Report how many of a committed eval run's fixtures every model already
solves -- the corpus-level saturation figure (issue #1461).

This repository already measures whether an eval corpus is *broad*
(``gitapex_check_dimension_coverage.py``: which of a skill's own numbered
dimensions its fixtures cite) and whether its assertions are *well-formed*
(``gitapex_lint_fixture_assertions.py``: nine construct-validity checks).
Neither measures whether the corpus is *hard*, and nothing else here does
either: ``battle-testing-a-skill``'s dimension 14 grades an adversarial
regression corpus on existence, versioning, and growth, citing "growth
history (case count over time)" as its evidence, so a corpus of fixtures
every model already solves clears that bar while carrying no information.

**What this computes, and what it deliberately does not claim.** Vania et
al., "Comparing Test Sets with Item Response Theory" (ACL-IJCNLP 2021,
https://aclanthology.org/2021.acl-long.92/) estimate a per-item difficulty
and discrimination parameter by fitting a 3PL item-response model, using
roughly 90 responses per item (18 models x 5 checkpoints). This repository
has at most 3 responses per fixture. This module therefore computes the
cheap counting approximation of the same construct -- how many of the
available models scored a fixture at exactly 1.0 -- and never calls the
result an IRT estimate, a difficulty parameter, or a discrimination
parameter. It is a count over whichever models a single run happened to
include, and it is only as informative as that model set.

Report-only by contract (issue #1461's own sixth acceptance criterion):
exit code 0 for any well-formed run directory regardless of the figures,
including a fully saturated one. A non-zero exit is reserved for input this
module cannot parse into the shape it expects, matching
``gitapex_check_dimension_coverage.py``'s own report-tool contract. Choosing
a saturation threshold, and enforcing one, are deliberately out of scope:
exactly one committed run in this repository carries more than one
``model_id``, which is not a basis for a threshold -- see Miller, "Adding
Error Bars to Evals" (arXiv:2411.00640, https://arxiv.org/abs/2411.00640)
on using power analysis to decide whether an eval can test a hypothesis at
all before drawing a conclusion from it.

Three outcomes are reported separately, because collapsing them would hide
the one that is not about difficulty:

- **saturated** -- every model scored 1.0. The fixture cannot separate any
  two models in this run; adding more like it grows the case count without
  growing the information.
- **discriminating** -- at least one model scored below 1.0. This is the
  complement of saturated, so the two rates sum to 1.
- **uniformly hard** -- every model scored the *same* value below 1.0. This
  is a labelled subset of the discriminating set, not a fourth bucket, and
  it is reported separately because it is a likelier assertion defect than
  a hard case: Swayamdipta et al., "Dataset Cartography" (EMNLP 2020,
  https://aclanthology.org/2020.emnlp-main.746/) find hard-to-learn
  instances "often correspond to labeling errors". This repository has hit
  that defect class twice already (``gitapex_lint_fixture_assertions.py``'s
  own negation-trap check, and the ``multi-turn-escalation.yaml``
  ``DEPLOY_SIGNING_KEY isn't`` false match). The flag is a candidate for a
  human read, never a verdict.

**Which files in a run directory participate**, decided against the real
committed corpus rather than assumed. Only ``*.json`` in the run directory
root is read -- never ``artifacts/``, which
``evals/evaluating-skill-quality/results/README.md`` reserves for raw
prompts and model output. A file participates only when it carries both a
non-empty string ``model_id`` and a list ``scores``, which is exactly the
``eval-scores.schema.json`` shape. That rule, not a filename allowlist, is
what excludes the two other file kinds that really exist in this
repository's ``results/`` directories: every ``manifest.json`` (provenance,
no ``model_id``/``scores``) and ``dispatch-trace-check.json`` (a
``model_id``, but no ``scores``).

**Which entries participate.** An entry needs a string ``fixture_id`` and a
real numeric ``score`` (``bool`` is rejected despite being an ``int``
subclass). Entries carrying a ``condition`` field -- the before/after gate
records ``scorer-gated-skill-edits``' own strict improve-or-reject gate
writes -- contribute only their ``after`` arm: ``before`` is the pre-edit
state of a file that has since changed, so counting it would mix two
different corpora into one rate.

**Duplicate entries across files of the same model.** A run directory can
legitimately record the same fixture twice for one model -- a
``<model>-after.json`` aggregate alongside a ``<model>-before-after-detail
.json`` whose ``after`` arm repeats it. Verified against the real
2026-08-15 issue-1124 run: all five overlapping entries agree exactly. So
agreement is deduplicated silently, and a genuine disagreement is a loud
failure (exit 2), never silently resolved by taking the first, last, or
larger value -- which of two conflicting records is authoritative is not
something this module can know.

**Fixtures not scored by every model** are excluded from both rates and
listed separately. A saturation rate computed over a fixture one model
never ran would silently treat "not measured" as "not solved."

**Model identity is compared verbatim.** Two committed files carry a
``model_id`` with a disclosure suffix appended (for example
``claude-sonnet-5 (inferred, not independently confirmed -- see manifest
known_gaps)``). This module does not strip such a suffix -- inventing a
normalization rule could silently merge two genuinely different responders
-- so it instead reports every ``model_id`` verbatim and flags any that is
not a bare identifier, leaving the reader to judge. A run directory holding
both the bare and the suffixed form of one model would count them as two
responders; the flag is what makes that visible rather than silent.

Usage::

    uv run --frozen python3 evals/scripts/gitapex_compute_corpus_saturation.py \\
        evals/evaluating-skill-quality/results/2026-07-28-issue-500-phase1

Exit codes: 0 for any well-formed run directory, including one with fewer
than two models (reported as not computable, with the count found, rather
than as a zero rate). 2 for a path that is not a readable directory,
unparseable JSON, a malformed entry, or a score conflict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard

#: A bare model identifier, as `results/README.md` requires each per-model
#: file to be named by ("full, current model ID (e.g.
#: `claude-haiku-4-5-20251001`)"). Anything else -- a disclosure suffix, a
#: parenthetical, embedded whitespace -- is reported rather than normalized.
BARE_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

#: The only `condition` arm a before/after gate record contributes.
AFTER_CONDITION = "after"

#: The score a fixture must carry for a model to count as having solved it.
PERFECT_SCORE = 1.0

#: Fewer distinct models than this cannot define a cross-model rate.
MIN_MODELS_FOR_A_RATE = 2


class SaturationInputError(Exception):
    """The run directory could not be parsed into the expected shape."""


@dataclass(frozen=True)
class FixtureVerdict:
    """One fixture's scores across every model that ran it."""

    fixture_id: str
    scores: dict[str, float]

    @property
    def is_saturated(self) -> bool:
        """Every model scored exactly 1.0 -- no information in this run."""
        return all(score == PERFECT_SCORE for score in self.scores.values())

    @property
    def is_uniformly_hard(self) -> bool:
        """Every model scored the same value, and that value is below 1.0.

        A labelled subset of the discriminating set, not a fourth bucket:
        no model separated from another, so the fixture is a candidate
        assertion defect rather than evidence of difficulty.
        """
        distinct = set(self.scores.values())
        return len(distinct) == 1 and distinct != {PERFECT_SCORE}

    @property
    def spread(self) -> float:
        """Max minus min across models -- 0.0 when every model agreed."""
        return max(self.scores.values()) - min(self.scores.values())


@dataclass(frozen=True)
class SaturationReport:
    """What one run directory says about its corpus's saturation."""

    run_dir: Path
    model_ids: tuple[str, ...]
    complete: tuple[FixtureVerdict, ...]
    incomplete: tuple[FixtureVerdict, ...]
    unqualified_model_ids: tuple[str, ...]

    @property
    def computable(self) -> bool:
        """Whether a cross-model rate is defined for this run at all."""
        return len(self.model_ids) >= MIN_MODELS_FOR_A_RATE and bool(self.complete)

    @property
    def saturated(self) -> tuple[FixtureVerdict, ...]:
        return tuple(f for f in self.complete if f.is_saturated)

    @property
    def discriminating(self) -> tuple[FixtureVerdict, ...]:
        return tuple(f for f in self.complete if not f.is_saturated)

    @property
    def uniformly_hard(self) -> tuple[FixtureVerdict, ...]:
        return tuple(f for f in self.complete if f.is_uniformly_hard)


def _is_real_score(value: object) -> TypeGuard[float]:
    """True for a genuine numeric score.

    ``bool`` is excluded deliberately: it is an ``int`` subclass, so a
    ``true`` in a result file would otherwise be read as the score 1.0 and
    counted as a solved fixture.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _entry_contributes(entry: dict[str, Any]) -> bool:
    """Whether one ``scores[]`` entry counts toward the current corpus.

    An entry with no ``condition`` is an ordinary single-arm record. An
    entry with one contributes only when it is the ``after`` arm -- the
    ``before`` arm describes a file version that has since changed.
    """
    condition = entry.get("condition")
    return condition is None or condition == AFTER_CONDITION


def _read_result_files(run_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Every root-level JSON in ``run_dir`` that carries per-model scores."""
    if not run_dir.is_dir():
        raise SaturationInputError(f"not a readable directory: {run_dir}")

    participating: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(run_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SaturationInputError(f"could not read {path}: {exc}") from exc
        if not isinstance(payload, dict):
            continue
        model_id = payload.get("model_id")
        scores = payload.get("scores")
        if isinstance(model_id, str) and model_id.strip() and isinstance(scores, list):
            participating.append((path, payload))
    return participating


def _collect_scores(
    participating: list[tuple[Path, dict[str, Any]]],
) -> dict[str, dict[str, float]]:
    """Map ``model_id -> fixture_id -> score`` across the participating files.

    Raises on a malformed entry, and on the same model recording two
    different scores for one fixture.
    """
    by_model: dict[str, dict[str, float]] = {}
    for path, payload in participating:
        model_id = str(payload["model_id"])
        entries = payload["scores"]
        # Register the model before reading its entries, so a file that
        # contributes nothing -- an empty `scores[]`, or one holding only
        # `before` arms -- still counts as a model that ran. Registering it
        # lazily instead would drop it from the model list entirely, and a
        # fixture only one of two models scored would then be reported as
        # saturated across "every model". That is the same treat-unmeasured-
        # as-measured error this module refuses for fixtures, applied to the
        # model axis. Found by the property layer, not by an example test.
        by_model.setdefault(model_id, {})
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise SaturationInputError(f"{path}: scores[{index}] is not an object")
            if not _entry_contributes(entry):
                continue
            fixture_id = entry.get("fixture_id")
            score = entry.get("score")
            if not isinstance(fixture_id, str) or not fixture_id.strip():
                raise SaturationInputError(f"{path}: scores[{index}] has no fixture_id")
            if not _is_real_score(score):
                raise SaturationInputError(f"{path}: scores[{index}] ({fixture_id}) has a non-numeric score {score!r}")
            numeric = float(score)
            recorded = by_model.setdefault(model_id, {})
            if fixture_id in recorded and recorded[fixture_id] != numeric:
                raise SaturationInputError(
                    f"{path}: {model_id} records two different scores for {fixture_id} "
                    f"({recorded[fixture_id]} and {numeric}); "
                    "which is authoritative cannot be decided here"
                )
            recorded[fixture_id] = numeric
    return by_model


def compute_saturation(run_dir: Path) -> SaturationReport:
    """Read one committed run directory and compute its saturation figures."""
    by_model = _collect_scores(_read_result_files(run_dir))
    model_ids = tuple(sorted(by_model))

    every_fixture: set[str] = set()
    for scores in by_model.values():
        every_fixture |= set(scores)

    complete: list[FixtureVerdict] = []
    incomplete: list[FixtureVerdict] = []
    for fixture_id in sorted(every_fixture):
        scored = {m: by_model[m][fixture_id] for m in model_ids if fixture_id in by_model[m]}
        verdict = FixtureVerdict(fixture_id=fixture_id, scores=scored)
        if len(scored) == len(model_ids):
            complete.append(verdict)
        else:
            incomplete.append(verdict)

    unqualified = tuple(m for m in model_ids if not BARE_MODEL_ID_RE.match(m))

    return SaturationReport(
        run_dir=run_dir,
        model_ids=model_ids,
        complete=tuple(complete),
        incomplete=tuple(incomplete),
        unqualified_model_ids=unqualified,
    )


def _percent(count: int, total: int) -> str:
    return f"{(100.0 * count / total):.1f} percent"


def format_report(report: SaturationReport) -> str:
    """Render the report as plain text, in this repository's own report style."""
    lines: list[str] = [f"run: {report.run_dir}"]

    if report.model_ids:
        lines.append(f"models ({len(report.model_ids)}): {', '.join(report.model_ids)}")
    else:
        lines.append("models (0): none -- no file carried both model_id and scores[]")

    for model_id in report.unqualified_model_ids:
        lines.append(
            f"NOTE: model_id {model_id!r} is not a bare identifier; it is counted "
            "verbatim as its own responder, not normalized"
        )

    if not report.computable:
        lines.append(
            f"saturation: NOT COMPUTABLE -- {len(report.model_ids)} model(s) and "
            f"{len(report.complete)} fixture(s) scored by all of them; "
            f"a cross-model rate needs at least {MIN_MODELS_FOR_A_RATE} models"
        )
        if report.incomplete:
            lines.append(f"fixtures not scored by every model: {len(report.incomplete)}")
        return "\n".join(lines)

    total = len(report.complete)
    saturated = report.saturated
    discriminating = report.discriminating
    uniformly_hard = report.uniformly_hard

    lines.append(f"fixtures scored by every model: {total}")
    lines.append(f"saturated (every model 1.0): {len(saturated)} of {total} ({_percent(len(saturated), total)})")
    lines.append(
        f"discriminating (at least one model below 1.0): {len(discriminating)} of {total} "
        f"({_percent(len(discriminating), total)})"
    )
    lines.append(
        f"uniformly hard (subset of the discriminating set -- every model equal, below 1.0): {len(uniformly_hard)}"
    )

    if saturated:
        lines.append("")
        lines.append("saturated fixtures (no information in this run):")
        lines.extend(f"  {f.fixture_id}" for f in saturated)

    if uniformly_hard:
        lines.append("")
        lines.append("uniformly-hard fixtures (assertion-defect candidates, not verdicts):")
        lines.extend(f"  {f.fixture_id} -- every model scored {min(f.scores.values()):.6f}" for f in uniformly_hard)

    if report.incomplete:
        lines.append("")
        lines.append("fixtures excluded (not scored by every model):")
        lines.extend(
            f"  {f.fixture_id} -- scored by {len(f.scores)} of {len(report.model_ids)}" for f in report.incomplete
        )

    lines.append("")
    lines.append(
        "This is a count over the models this run happened to include, not an "
        "item-response difficulty or discrimination estimate."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report cross-model fixture saturation for one committed eval run (read-only).",
    )
    parser.add_argument("run_dir", help="path to one evals/<skill>/results/<run>/ directory")
    args = parser.parse_args(argv)

    try:
        report = compute_saturation(Path(args.run_dir))
    except SaturationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
