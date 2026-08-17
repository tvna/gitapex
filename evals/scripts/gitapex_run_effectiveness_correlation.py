"""Wire the effectiveness corpus, `gitapex_run_eval_suite.py` (the real
measurement mechanism), and `gitapex_compute_rank_correlation.py` together
end to end (issue #1143, Acceptance Criteria Map row 3: "The methodology
is usable end to end").

See `effectiveness-corpus-methodology.md` for the full design: what
"independently labeled" means here, the held-out selection/test split, and
why this script's own `x` value is a disclosed *placeholder*, not waza's
real body-structure/negative-delta-risk metric (that native implementation
is issue #1137 sub-task 3's own contingent, not-yet-built scope).

**What this script actually measures.** For each corpus entry in the
chosen split: `y` is a fresh `mean_score` from running that skill's own
committed `evals/<skill>/eval.yaml` suite through
`gitapex_run_eval_suite.run_eval_suite` (never a stale value read back out
of a historical `results/` file -- a corpus entry's own optional
`known_prior_result` is provenance/cross-reference only, see the
methodology doc); `x` is that skill's own `SKILL.md` body line count. Both
are real, computed values -- `x` is simply not the metric #1137 sub-task 3
will eventually need, and every JSON result this script prints says so
explicitly via `x_metric_caveat`, so a `--dry-run` cannot be mistaken for a
real correlation verdict by a reader who only sees the output.

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
valid but every entry's own measurement failed, or fewer than 2 usable
pairs remained after skipping (a correlation cannot be computed from
fewer than 2 points); 0 means success (regardless of some entries being
skipped, which is disclosed in the output, not a failure).

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
import gitapex_run_ablation
import gitapex_run_eval_suite
import jsonschema
from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent / "effectiveness-corpus.json"
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent / "effectiveness-corpus.schema.json"

X_METRIC_CAVEAT = (
    "x is SKILL.md body line count -- a real, mechanically computed value, but an illustrative "
    "PLACEHOLDER only. It is NOT waza's real body-structure/negative-delta-risk metric; a native, "
    "waza-independent implementation of that metric is issue #1137 sub-task 3's own contingent, "
    "not-yet-built scope. Do not read this run's correlation as a measurement of that question."
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
    x: float
    y: float


class SkippedEntry(BaseModel):
    skill: str
    reason: str


def _skip_reason(exc: Exception) -> str:
    """A safe, disclosed reason for a ``SkippedEntry`` -- never the raw
    text of a ``RuntimeError`` or ``subprocess.TimeoutExpired``, both of
    which can embed live, externally-produced content this tool's own
    JSON output must not republish verbatim: ``subprocess_executor``'s own
    ``RuntimeError`` message includes the invoked model CLI's raw stderr
    (issue #1143 adversarial review round), and ``TimeoutExpired``'s own
    string form includes the full argv it ran, which itself carries the
    fixture's prompt text (``gitapex_run_ablation.build_command``). Neither
    is safe to echo into a result blob this tool's own docstring calls
    "loud and visible in the tool's own output" -- CLAUDE.md's own rule
    against echoing untrusted/external content into a generated artifact.
    A ``ValueError``/``OSError``, in contrast, is always this module's or
    the standard library's own deterministic, code-controlled text (a
    missing-file path, a malformed-YAML complaint) -- never a live
    model's own output -- so those stay verbatim, genuinely useful and
    genuinely safe. The split is by exception type, not a per-instance
    guess.
    """
    if isinstance(exc, (RuntimeError, subprocess.TimeoutExpired)):
        return f"{type(exc).__name__}: model CLI invocation failed or timed out (detail intentionally not republished here)"
    return str(exc)


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
            body_line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
            suite_result = gitapex_run_eval_suite.run_eval_suite(
                eval_yaml,
                skill_md,
                executor=executor,
                model_cli=model_cli,
            )
        except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            skipped.append(SkippedEntry(skill=skill, reason=_skip_reason(exc)))
            continue
        pairs.append(CorpusEntryResult(skill=skill, x=float(body_line_count), y=suite_result.mean_score))
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

    try:
        correlation = rank_correlation.compute_correlation(
            [p.x for p in pairs],
            [p.y for p in pairs],
            confidence=validated_args.confidence,
            n_resamples=validated_args.n_resamples,
            seed=validated_args.seed,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
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
                "correlation": correlation.to_json_dict(),
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
