"""Wire the effectiveness corpus, `gitapex_run_eval_suite.py` (the real
measurement mechanism), and `gitapex_compute_rank_correlation.py` together
end to end (issue #1143, Acceptance Criteria Map row 3: "The methodology
is usable end to end"; issue #1144 replaced the original placeholder
x-metric with the two real, native metrics below).

See `effectiveness-corpus-methodology.md` for the full design: what
"independently labeled" means here, and the held-out selection/test
split.

**What this script actually measures.** For each corpus entry in the
chosen split: `y` is a fresh `mean_score` from running that skill's own
committed `evals/<skill>/eval.yaml` suite through
`gitapex_run_eval_suite.run_eval_suite` (never a stale value read back out
of a historical `results/` file -- a corpus entry's own optional
`known_prior_result` is provenance/cross-reference only, see the
methodology doc). Two `x` metrics are computed per entry, both via
`gitapex_compute_waza_advisory_metrics.py` against that skill's own
`SKILL.md` body (frontmatter stripped): `x_negative_delta_risk`
(`count_constraint_signals`) and `x_body_structure`
(`count_body_structure_signals`) -- this repository's own fresh,
corpus-calibrated, waza-independent operational definitions of waza's own
advisory concepts, not a reverse-engineered copy of waza's own
undisclosed counting algorithm (see that module's own docstring). A
correlation is computed separately for each metric against the same `y`
series -- two independent questions, never averaged into one score, since
issue #1144's own resolved scope treats a possible rubric port for each
as independent, never a package deal.

**`--dry-run` vs. a live run.** `run_eval_suite`'s own `executor` parameter
is dependency-injected (the same `Executor` type
`gitapex_run_ablation.py` defines) precisely so this script's plumbing can
be proven without live model credentials, matching every other
`evals/scripts/*.py` module's own established precedent (issue #583's
explicit constraint that a runner's "shape and interface are built and
unit-tested against a stub executor first"). `--dry-run` (the only mode
this issue's own environment can actually exercise -- see the methodology
doc's Scope section) substitutes a fixed, clearly-labeled stub string for
every model call; omitting it uses the real
`gitapex_run_ablation.subprocess_executor`, which needs
`ANTHROPIC_API_KEY` allowlisted exactly as that module's own module
docstring already documents.

**Per-entry failure handling.** 25 real `eval.yaml` suites are each
maintained for their own skill's purposes, not for this corpus's -- a
suite `gitapex_run_eval_suite.py` cannot run (a malformed declaration, an
empty `tasks:` glob) is a fact about that one suite, not a reason to
abort every other skill's measurement. Such an entry is recorded in the
result's own `skipped` list with its reason and excluded from the
correlation input for that run -- loud and visible in the tool's own
output, never silently dropped. Only `ValueError`/`RuntimeError`/`OSError`/
`subprocess.TimeoutExpired` are caught this way (the same set
`gitapex_run_eval_suite.py`'s own `main()` already treats as "this
suite's own failure," not a bug in this script) -- anything else
propagates and crashes loudly, per this repository's own "an inability to
verify is a deny, not an assume-clean" convention. The recorded `reason`
is never a `RuntimeError`'s or `subprocess.TimeoutExpired`'s own raw text
-- see `_skip_reason`'s own docstring for why those two specifically can
carry a live model CLI's own stderr or full invoked command line, and
must not be republished verbatim into this tool's own output.

Exit code contract: 2 means the input was malformed (corpus file missing
or fails schema validation, `--split` matched zero entries, a corpus path
that does not exist as a real file); 1 means the corpus and its paths were
valid but every entry's own measurement failed, fewer than 2 usable pairs
remained after skipping (a correlation cannot be computed from fewer than
2 points), or either metric's own series was degenerate (e.g. constant --
`gitapex_compute_rank_correlation.compute_correlation` rejects that
outright, reported by name so a reader knows which of the two metrics
failed); 0 means success (regardless of some entries being skipped, which
is disclosed in the output, not a failure).

Usage (``uv run`` -- reaches PyYAML/jsonschema/pydantic transitively
through ``gitapex_run_eval_suite``/``gitapex_compute_rank_correlation``,
same as those modules' own Usage:: blocks)::

    uv run python3 evals/scripts/gitapex_run_effectiveness_correlation.py \\
        --corpus evals/scripts/effectiveness-corpus.json --split selection --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import gitapex_compute_rank_correlation as rank_correlation
import gitapex_compute_waza_advisory_metrics as advisory_metrics
import gitapex_run_ablation
import gitapex_run_eval_suite
import jsonschema
from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent / "effectiveness-corpus.json"
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent / "effectiveness-corpus.schema.json"

X_METRIC_CAVEAT = (
    "x_negative_delta_risk and x_body_structure are real, waza-independent metrics computed by "
    "gitapex_compute_waza_advisory_metrics.py (count_constraint_signals / count_body_structure_signals) "
    "against each skill's own SKILL.md body. They are this repository's own fresh, corpus-calibrated "
    "operational definitions of waza's advisory concepts -- NOT a reverse-engineered copy of waza's own "
    "undisclosed counting algorithm, so a given skill's exact count here is not expected to match what "
    "waza itself would report. See that module's own docstring for the calibration rationale."
)


def _dry_run_executor(argv: Sequence[str], timeout: int) -> str:
    """A fixed, clearly-labeled stand-in for a live model call. Never
    invoked when a live run is requested (only wired in for ``--dry-run``,
    see ``main``) -- exists so this script's own plumbing (corpus loading,
    suite execution, x/y pairing, correlation) can be proven without
    ``ANTHROPIC_API_KEY``, matching every sibling ``evals/scripts/*.py``
    module's own established stub-executor precedent.
    """
    return "[dry-run stub output -- no live model was invoked]"


class CorpusEntryResult(BaseModel):
    skill: str
    x_negative_delta_risk: float
    x_body_structure: float
    y: float


class SkippedEntry(BaseModel):
    skill: str
    reason: str


# A safe, disclosed reason for a SkippedEntry -- never a RuntimeError's or
# TimeoutExpired's own raw text, both of which can embed live,
# externally-produced content (a model CLI's stderr, a fixture's prompt
# text) this tool's own "loud and visible" JSON output must not republish
# verbatim. Hoisted into gitapex_run_ablation.py (issue #1144, both
# gitapex_run_eval_suite.py and this module already import it) rather than
# duplicated -- kept as a module-level alias here so existing call sites
# and tests (`m._skip_reason`) keep working unchanged. See that function's
# own docstring for the full redaction rationale.
_skip_reason = gitapex_run_ablation.redact_executor_failure_reason


def load_corpus(corpus_path: Path, schema_path: Path) -> dict[str, Any]:
    """Load and schema-validate ``corpus_path`` against ``schema_path``.

    Raises ``ValueError`` on an unreadable/non-UTF-8/invalid-JSON file, a
    schema that itself fails to load the same way, or a corpus that fails
    validation -- one exception type, matching this directory's other
    loaders.
    """
    for label, path in (("corpus", corpus_path), ("schema", schema_path)):
        if not path.is_file():
            raise ValueError(f"{label} file not found: {path}")
    try:
        schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read schema {schema_path}: {exc}") from exc
    try:
        corpus: dict[str, Any] = json.loads(corpus_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read corpus {corpus_path}: {exc}") from exc
    try:
        jsonschema.validate(corpus, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"corpus {corpus_path} failed schema validation: {exc.message}") from exc
    return corpus


def select_entries(corpus: dict[str, Any], split: str) -> list[dict[str, Any]]:
    """Entries matching ``split`` ("selection", "test", or "all"), in the
    corpus's own committed order. Raises ``ValueError`` if none match --
    a split that silently produces zero entries must fail loudly, the
    same "empty match set is an error" convention
    ``gitapex_run_eval_suite.discover_task_fixtures`` already established
    for a `tasks:` glob matching nothing.
    """
    entries: list[dict[str, Any]] = corpus["entries"]
    if split != "all":
        entries = [e for e in entries if e["split"] == split]
    if not entries:
        raise ValueError(f"no corpus entries matched split={split!r}")
    return entries


def compute_pairs(
    entries: list[dict[str, Any]],
    *,
    executor: gitapex_run_ablation.Executor,
    model_cli: str,
) -> tuple[list[CorpusEntryResult], list[SkippedEntry]]:
    """For each entry, resolve its real repo-relative paths and compute a
    fresh ``(x, y)`` pair (see module docstring for what each measures).
    Returns ``(pairs, skipped)`` -- an entry whose own suite run fails
    (``ValueError``, ``RuntimeError``, ``OSError``, or
    ``subprocess.TimeoutExpired`` -- see module docstring's "Per-entry
    failure handling" section) lands in ``skipped`` with its reason, never
    silently dropped and never aborting the remaining entries.

    The four types are named directly in the ``except`` clause below,
    not read from a shared module-level tuple: this repository's own
    ``gitapex_gate_exception_handler_gaps.py`` CI gate statically matches an
    ``except`` clause's own type names against a fixed table (covering
    ``read_text``'s ``UnicodeDecodeError``) and, by its own documented
    design, does not expand a named constant to see what it resolves to --
    an indirect ``except _SOME_TUPLE:`` would read as uncovered even though
    ``ValueError`` (``UnicodeDecodeError``'s own ancestor) is genuinely
    among the caught types.
    """
    pairs: list[CorpusEntryResult] = []
    skipped: list[SkippedEntry] = []
    for entry in entries:
        skill = entry["skill"]
        skill_md = REPO_ROOT / entry["skill_md"]
        eval_yaml = REPO_ROOT / entry["eval_yaml"]
        try:
            if not skill_md.is_file():
                raise ValueError(f"skill_md not found: {skill_md}")
            body = advisory_metrics.strip_frontmatter(skill_md.read_text(encoding="utf-8"))
            negative_delta_risk = advisory_metrics.count_constraint_signals(body)
            body_structure = advisory_metrics.count_body_structure_signals(body)
            suite_result = gitapex_run_eval_suite.run_eval_suite(
                eval_yaml,
                skill_md,
                executor=executor,
                model_cli=model_cli,
            )
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            skipped.append(SkippedEntry(skill=skill, reason=_skip_reason(exc)))
            continue
        pairs.append(
            CorpusEntryResult(
                skill=skill,
                x_negative_delta_risk=float(negative_delta_risk),
                x_body_structure=float(body_structure),
                y=suite_result.mean_score,
            )
        )
    return pairs, skipped


class _RunEffectivenessCorrelationArgs(BaseModel):
    # Named schema_path, not `schema`: pydantic's BaseModel already exposes
    # a class-level `schema` attribute of its own (its legacy JSON-schema
    # generator), and a field of the same name shadows it -- pydantic warns
    # on exactly this at class-definition time. The CLI flag stays
    # `--schema`; only this internal field name differs.
    corpus: Path
    schema_path: Path
    split: str
    confidence: float
    n_resamples: int
    seed: int

    @field_validator("split")
    @classmethod
    def _split_must_be_known(cls, value: str) -> str:
        if value not in ("selection", "test", "all"):
            raise ValueError(f"--split must be one of 'selection', 'test', 'all', got {value!r}")
        return value


def _validation_error_message(exc: ValidationError) -> str:
    """Matches this directory's other CLIs' own error-text convention."""
    error = exc.errors()[0]
    ctx = error.get("ctx") or {}
    original = ctx.get("error")
    if isinstance(original, Exception):
        return str(original)
    return str(error["msg"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the effectiveness corpus through gitapex_run_eval_suite.py and "
        "gitapex_compute_rank_correlation.py end to end (issue #1143)."
    )
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--split", default="selection", help="'selection', 'test', or 'all'.")
    parser.add_argument("--model-cli", default=gitapex_run_ablation.DEFAULT_MODEL_CLI)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use a fixed stub instead of a live model call -- no credentials needed.",
    )
    parser.add_argument("--confidence", type=float, default=rank_correlation.DEFAULT_CONFIDENCE)
    parser.add_argument("--n-resamples", type=int, default=rank_correlation.DEFAULT_N_RESAMPLES)
    parser.add_argument("--seed", type=int, default=rank_correlation.DEFAULT_SEED)
    args = parser.parse_args(argv)

    try:
        validated_args = _RunEffectivenessCorrelationArgs(
            corpus=args.corpus,
            schema_path=args.schema,
            split=args.split,
            confidence=args.confidence,
            n_resamples=args.n_resamples,
            seed=args.seed,
        )
    except ValidationError as exc:
        print(f"error: {_validation_error_message(exc)}", file=sys.stderr)
        return 2

    try:
        corpus = load_corpus(validated_args.corpus, validated_args.schema_path)
        entries = select_entries(corpus, validated_args.split)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    executor = _dry_run_executor if args.dry_run else gitapex_run_ablation.subprocess_executor
    pairs, skipped = compute_pairs(entries, executor=executor, model_cli=args.model_cli)

    if len(pairs) < 2:
        print(
            f"error: only {len(pairs)} usable pair(s) after skipping {len(skipped)} entr(y/ies) "
            "-- need at least 2 to compute a correlation",
            file=sys.stderr,
        )
        return 1

    # Both metrics are computed against the same pairs (one run_eval_suite
    # call per skill already covers both -- see compute_pairs -- so this
    # never doubles live-model cost). Each is its own independent
    # correlation question, never averaged into one score: issue #1144's
    # own resolved scope treats a possible rubric port for each metric as
    # independent, never a package deal, and that independence carries
    # through to how each is measured here.
    try:
        negative_delta_risk_correlation = rank_correlation.compute_correlation(
            [p.x_negative_delta_risk for p in pairs],
            [p.y for p in pairs],
            confidence=validated_args.confidence,
            n_resamples=validated_args.n_resamples,
            seed=validated_args.seed,
        )
    except ValueError as exc:
        print(f"error: negative_delta_risk correlation: {exc}", file=sys.stderr)
        return 1

    try:
        body_structure_correlation = rank_correlation.compute_correlation(
            [p.x_body_structure for p in pairs],
            [p.y for p in pairs],
            confidence=validated_args.confidence,
            n_resamples=validated_args.n_resamples,
            seed=validated_args.seed,
        )
    except ValueError as exc:
        print(f"error: body_structure correlation: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "corpus": str(validated_args.corpus),
                "split": validated_args.split,
                "dry_run": args.dry_run,
                "x_metric_caveat": X_METRIC_CAVEAT,
                "pairs": [p.model_dump() for p in pairs],
                "skipped": [s.model_dump() for s in skipped],
                "correlations": [
                    {"metric": "negative_delta_risk", **negative_delta_risk_correlation.to_json_dict()},
                    {"metric": "body_structure", **body_structure_correlation.to_json_dict()},
                ],
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
