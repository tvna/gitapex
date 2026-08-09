#!/usr/bin/env python3
"""Validate every committed eval run record under `evals/*/results/`.

ACTIVE (issue #926): registered in `.gitapex/ssot.json` as
`eval-results-schema-drift`, on two planes. The CI plane has no dedicated
workflow step of its own: it runs because
`tests/test_gitapex_scan_eval_results_schema.py`'s own
`test_real_repository_run_records_have_no_drift` calls `find_drift()` against
the real `evals/` tree inside `.github/workflows/test.yml`'s pytest step. The
local plane is the `local_invocation` its registry row records, which
`gitapex_gate_local_preflight.py` discovers and runs before a push -- the
wording `gitapex_gate_eval_declared_model.py` already uses, rather than the
older sibling scanners' pre-#876 "no pre-commit hook" phrasing, which is
false for any gate carrying `planes: ["ci", "local"]`.

Before this scanner existed, `evals/*/results/` was the one committed,
machine-readable corpus in this repository with no schema and no drift gate.
It drifted anyway, which is issue #926's own headline finding: choosing JSON
is not what prevents drift, a schema plus a gate is. Measured at `edd14f4`,
seven manifests scored 9/9, 9/9, 9/9, 6/9, 6/9, 6/9 and 2/9 against the ten
keys `evals/evaluating-skill-quality/results/README.md` declares as its own
minimum; one run directory carried no manifest at all; `models` was spelled
`model` in one; and none of the 13 `.md` attachments was referenced from any
manifest.

Two layers, and the split is the whole design
---------------------------------------------

**Layer 1 -- this repository's own structural rules.** Applied to every run
directory, with no exemption. These are cross-file and cross-directory rules
that no single JSON Schema instance can express, because a JSON Schema
instance never sees the filesystem it sits in: which files may exist in a
run directory root, whether `artifacts[]` and the real files agree in both
directions, and whether a null `commit` carries the disclosure that makes it
a record rather than a gap. `KEY_SPELLING_DRIFT` is here for the same
reason -- a schema with `additionalProperties: true` (which
`eval-run.schema.json` deliberately is) cannot reject a misspelled key,
since to it a misspelling is simply an extra key it was told to permit.

**Layer 2 -- the skill-owned schemas.**
`skills/scorer-gated-skill-edits/references/eval-run.schema.json` and
`.../eval-scores.schema.json` ship inside the skill that owns the
run-record contract (issue #932), so the contract travels with `SKILL.md`
when the skill is installed elsewhere. This scanner reads them; it does not
author them, and a missing one is a hard error (`ResultsReadError`, exit 1),
never a silent skip -- a scanner that quietly passes when its schema has
gone missing is the vacuous-pass failure class issue #651's retrospective
named.

Why layer 2 does not apply to every record, stated rather than assumed
---------------------------------------------------------------------

`eval-run.schema.json` pins the shape of a *gate run* record --
`scorer-gated-skill-edits` Procedure step 7's own output. It requires
`runner` (the runner binary's own reported name and version) and `gate`
(a KEEP/REJECT verdict with the two means that produced it). None of the
eight records committed before that contract existed has either, and
neither is recoverable: those runs were measurement and audit sweeps driven
by `claude -p` subprocesses, not gate runs, so there is no verdict that was
reached and no runner version that was captured. Issue #926's own
constraint forbids reconstructing a value by inference, and
`eval-run.schema.json`'s own description says the same thing from the other
side: "a repository migrating pre-existing records onto this contract is
doing its own work, not being retro-graded by this file."

So a record declares which contract it is under, and the declaration is
mandatory -- `record_contract: "gate-run"` (validated in full against
`eval-run.schema.json`) or `record_contract: "pre-contract"` (layer 1 only,
plus a `known_gaps` entry disclosing that the exemption is in force). A
record declaring neither is a finding.

Declaring `pre-contract` is not self-service. Blocking omission alone would
have been a fail-open dressed as a fail-closed: omission is the harder path,
and *declaring* the exemption is the easier one, so a new run could have
skipped layer 2 by writing one word plus one disclosure line. The exemption
is therefore pinned to `LEGACY_PRE_CONTRACT_RUNS`, the frozen set of run
directories that predate the contract. A run directory outside that set
declaring `pre-contract` is a finding, so the set can only shrink.

A non-score root JSON file is one of two classes, decided by content
--------------------------------------------------------------------

`results/README.md` names a "checker report" -- a deterministic checker's
own verdict output, `dispatch-trace-check.json` being the one committed
instance -- as a root JSON file that is legitimately not a per-model score
file. The first version of this rule gave every such file one field,
`checker_reports[]`, to declare itself through. A CodeRabbit review round
found that conflation live: issue #537's own `claude-sonnet-5.json` is
scorer output in a nonstandard shape (it carries a real per-iteration
`score`, just inside a `condition`/`iteration` record `eval-scores.schema.
json`'s own `scores[]` item shape does not have), not a checker's verdict,
and the one field gave its author no way to say so -- and, worse, a bare
declared filename proved nothing about what actually produced it, which
is how a real score file could have been routed through the same field as
an unvalidated escape hatch.

Both halves are fixed together, by content rather than by trusting the
declaration. `_contains_score_field` decides which class an undeclared
root JSON file belongs to: a real per-item `score` anywhere in it means
`nonstandard_score_files[]`, never `checker_reports[]` -- a checker's own
verdict is a pass/fail (`dispatch-trace-check.json`'s `runs[]` reports
`dispatch_trace_verdict`/`checker_exit_code`, never a `[0,1]` score).
`checker_reports[]` stays a bare-filename array, since a checker's
findings have no shape either schema could usefully pin (the module
docstring already states this). `nonstandard_score_files[]` is validated
with a pydantic model (`NonstandardScoreFileEntry`, `extra="forbid"`)
instead, because it is a genuinely new structural requirement -- a
mandatory, non-empty `deviation` disclosure -- that has no jsonschema
equivalent to defer to: neither skill-owned schema mentions this key, so
there is nothing for pydantic to sit *behind* here the way it sits behind
`jsonschema` in this repository's other pydantic use
(`gitapex_scan_ssot_schema.py`, where a pydantic parse failure silently
returns `None` because `jsonschema` already reported the real problem).
Layer 2's own gate-run validation (`find_gate_run_schema_drift`) is
untouched by any of this: it is exactly the case pydantic does not need
to cover, since `jsonschema` already validates that shape in full.

What this scanner does NOT check, disclosed rather than solved
-------------------------------------------------------------

- **Layer 2 has no coverage on this repository's own corpus today.** All
  eight committed records are `pre-contract`, so `find_gate_run_schema_drift`
  returns nothing for every one of them and the real-tree gate test exercises
  layer 1 alone. Layer 2's own behaviour is covered by fixtures only until a
  real gate run lands. A transitional state, stated rather than left for a
  reader to work out from the record set.
- A schema pins a manifest's shape, not the truthfulness of its values. A
  run recording a model it did not invoke, or an `artifacts[]` entry
  pointing at a real but semantically unrelated file, passes here.
- The root-contents rule enforces the *extension* (`.json`) and not the
  `<full-model-id>` naming convention `results/README.md` states, because
  this scanner owns no notion of a valid model id. An arbitrarily named
  `.json` file in a run root passes as a score file as long as its own
  content validates against `eval-scores.schema.json` --
  `find_non_score_root_json_drift` only steps in for a root `.json` file
  that does *not* validate as a score file, requiring it to be declared in
  `checker_reports[]` (a deterministic checker's own verdict output, no
  per-item `score`) or `nonstandard_score_files[]` (scorer output that
  does carry a per-item `score`, just not in `eval-scores.schema.json`'s
  own shape, with a mandatory `deviation` disclosure) instead.
- `commit` is checked for hex shape, not for resolving on any remote. It
  deliberately does not shell out to git: a shallow clone (this
  repository's own CI checkout) cannot resolve a historical object name,
  and a gate that fails on a property of the clone rather than of the
  record would be worse than no gate.
- Whether the pytest job carrying this scanner is *actually* required on the
  protected branch is GitHub-side state this scanner does not read. It is not
  unreadable in general, though: `.github/rulesets/main.json` declares
  `pytest` required with an empty `bypass_actors`, and
  `.github/scripts/gitapex_scan_ruleset_drift.py --scope required-checks`
  reads the live ruleset through the API and diffs it against that file on
  every pull request. So the honest limit here is division of labour, not
  the blanket "no in-repo tooling can read it" the older gates assert.

Run standalone (exit 0 clean, 1 on drift or a read error) or via the pytest
gate.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import _gitapex_schema_validation
import jsonschema
from pydantic import BaseModel, ConfigDict, Field, ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
SCHEMA_DIR = REPO_ROOT / "skills" / "scorer-gated-skill-edits" / "references"
RUN_SCHEMA_NAME = "eval-run.schema.json"
SCORES_SCHEMA_NAME = "eval-scores.schema.json"
RUN_SCHEMA_PATH = SCHEMA_DIR / RUN_SCHEMA_NAME
SCORES_SCHEMA_PATH = SCHEMA_DIR / SCORES_SCHEMA_NAME

MANIFEST_NAME = "manifest.json"
ARTIFACTS_DIR_NAME = "artifacts"

# The keys `evals/evaluating-skill-quality/results/README.md` declares as
# every manifest's own minimum. Checked here rather than left to
# `eval-run.schema.json` because a pre-contract record is exempt from that
# schema (see the module docstring) and would otherwise be checked for
# nothing at all -- the drift issue #926 measured was in exactly these keys.
README_MINIMUM_KEYS = (
    "date",
    "issue",
    "commit",
    "fixture_set",
    "trials_per_fixture",
    "models",
    "dispatch_mechanism",
    "scorer",
    "known_gaps",
    "headline_pattern",
)

# Misspelling -> the one spelling this corpus uses. `model` really was
# committed in `2026-07-29-issue-537-confidentiality-gates`; the rest are
# the same singular/plural slip one field over, listed so the next one is
# caught on arrival rather than after it has been measured.
KEY_SPELLING_DRIFT = {
    "model": "models",
    "artifact": "artifacts",
    "known_gap": "known_gaps",
    "score_file": "score_files",
    "trials_per_task": "trials_per_fixture",
}

GATE_RUN_CONTRACT = "gate-run"
PRE_CONTRACT = "pre-contract"
RECORD_CONTRACTS = (GATE_RUN_CONTRACT, PRE_CONTRACT)

# The complete, frozen set of run directories that predate the run-record
# contract and may therefore claim the layer-2 exemption. Keyed
# `<skill>/<run>` -- the same label `find_drift` prefixes findings with.
#
# Frozen deliberately, and this is the difference between a fail-closed and a
# fail-open exemption. Without it, `pre-contract` is self-service: any future
# record skips `eval-run.schema.json` entirely by declaring one word and
# adding one disclosure line, which is *easier* than the omission the
# declaration requirement already blocks. The set can shrink (a record
# genuinely re-derived as a gate run drops off it) and must never grow: a new
# run has a runner version and a verdict to record, which is exactly what the
# gate-run contract asks for.
LEGACY_PRE_CONTRACT_RUNS = frozenset(
    {
        "battle-testing-a-skill/2026-07-30-issue-584-dispatch-trace",
        "evaluating-skill-quality/2026-07-28-issue-500-phase1",
        "evaluating-skill-quality/2026-07-29-issue-537-confidentiality-gates",
        "evaluating-skill-quality/2026-07-30-issue-584-dispatch-trace",
        "untrusted-input-triage/2026-08-01-issue-645-battle-test",
        "untrusted-input-triage/2026-08-01-issue-645-behavioral-eval",
        "untrusted-input-triage/2026-08-01-issue-646-behavioral-gate2",
        "untrusted-input-triage/2026-08-01-issue-646-transfer-check",
    }
)

_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
_RUN_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-issue-(\d+)-[a-z0-9]+(?:-[a-z0-9]+)*$")

# Anchored, not a substring test. A bare `"commit" in gap` check is satisfied
# by any English sentence that happens to contain the word -- "we did not
# commit to a second model tier" disclosed a null `commit` under the first
# version of this file, which is the gate's own stated failure mode ("an
# undisclosed null reads as a satisfied declaration") reappearing one level
# up, inside the check meant to prevent it. Every one of the eight committed
# records already opens its disclosure with exactly these words.
_COMMIT_GAP_RE = re.compile(r"^commit is null:\s*\S")
_CONTRACT_GAP_RE = re.compile(r"^record_contract is pre-contract:\s*\S")

# Fail-closed floor on discovery itself, the same purpose and shape as
# `gitapex_scan_skill_metadata_schema.py`'s own MIN_EXPECTED_SKILL_DIRS. Set
# at the real current count rather than below it: the corpus only grows, a
# `>=` floor never fires on an addition, and slack here would let a run
# directory vanish silently -- which is the failure this floor exists for.
MIN_EXPECTED_RUN_DIRS = 8


class ResultsReadError(Exception):
    """A manifest, a score file, or one of the two skill-owned schemas could
    not be read as UTF-8 or parsed as JSON at all -- exit 1, never a
    traceback. Distinct from a schema-invalid-but-parseable instance, which
    is an ordinary finding."""


def discover_run_dirs(evals_dir: pathlib.Path = EVALS_DIR) -> list[pathlib.Path]:
    """Every `evals/<skill>/results/<run>/` directory, sorted.

    A directory is a run directory by position alone -- one level under a
    `results/` directory -- deliberately not by whether it happens to
    contain a `manifest.json`. Requiring the manifest for discovery would
    make `manifest-present` unenforceable: the one directory in this
    repository that lacked a manifest
    (`2026-08-01-issue-646-transfer-check`) would have been discovered as
    "not a run directory" and skipped silently, which is how it stayed
    unnoticed through issue #926's own measurement pass."""
    if not evals_dir.is_dir():
        return []
    return sorted(p for p in evals_dir.glob("*/results/*") if p.is_dir())


def _load_json(path: pathlib.Path) -> Any:
    """`load_json_or_raise`, plus the one malformed-input class it does not
    convert: `RecursionError`. A pathologically nested JSON document (a
    manifest of 100000 open braces) raises it from inside `json.loads`, and it
    is not a `JSONDecodeError` subclass, so it previously escaped `find_drift`
    as a traceback -- contradicting `ResultsReadError`'s own "exit 1, never a
    traceback" contract. The same catch `gitapex_scan_skill_metadata_schema.py`'s
    `load_sidecar` already adds for the YAML equivalent."""
    try:
        return _gitapex_schema_validation.load_json_or_raise(path, ResultsReadError)
    except RecursionError as error:
        raise ResultsReadError(f"{path}: is too deeply nested to parse: {error}") from error


def find_misplaced_results_dirs(evals_dir: pathlib.Path) -> list[str]:
    """`results-dir-placement`: every `results` directory under `evals/` must
    sit at exactly `evals/<skill>/results/`.

    `discover_run_dirs` globs one fixed depth, so a `results/` directory
    anywhere else -- `evals/results/`, `evals/<skill>/<sub>/results/`, or a
    case variant like `Results/` -- takes its run records out of the gate's
    sight entirely. The discovery floor does not help: it counts directories,
    so eight correctly-placed records plus one misplaced drifting record still
    clears it and reports clean. Without this sweep the gate's own coverage
    silently depends on a convention nothing checks."""
    if not evals_dir.is_dir():
        return []
    expected = {p for p in evals_dir.glob("*/results") if p.is_dir()}
    findings: list[str] = []
    for candidate in sorted(evals_dir.rglob("*")):
        if not candidate.is_dir() or candidate.name.lower() != "results" or candidate in expected:
            continue
        findings.append(
            f"results-dir-placement: {candidate.relative_to(evals_dir).as_posix()!r} is not at "
            "evals/<skill>/results/, so any run record inside it is invisible to this gate"
        )
    return findings


def _load_schema(path: pathlib.Path, expected_id_suffix: str) -> dict[str, Any]:
    """Read one of the two skill-owned schemas, raising rather than returning
    something unusable. Issue #926's own proof method requires this scanner to
    "fail loudly if either is absent" -- but absence is only one of three ways
    the dependency can go bad, and guarding it alone leaves the other two
    fail-open, which is the vacuous-pass class this whole gate cites issue
    #651's retrospective for:

    1. **Absent.** Caught by `is_file()`.
    2. **Present but not an object** (`[]`, `null`, `"a string"` after a bad
       merge). Previously escaped `find_drift` as an uncaught `AttributeError`
       from deep inside `jsonschema`, a traceback rather than the exit 1
       `ResultsReadError` promises.
    3. **Present, a technically valid schema, and empty.** The nastiest of the
       three: `{}` passes `check_schema` because it *is* a legal JSON Schema
       -- one that validates every instance. A truncated or half-written
       schema file therefore turned all of layer 2 into a silent pass with
       every test still green.

    So the guard is four-part: object shape, `check_schema`, a non-empty
    `required` list, and an `$id` ending in `expected_id_suffix`. The last two
    are what catch case 3 -- shape validity cannot, since an empty schema is
    valid.

    `expected_id_suffix` is the caller's own declaration of which schema it
    means, deliberately not derived from `path.name`. A path-derived check
    validates that a file's `$id` matches wherever it happens to sit, which
    passes when the two schemas are swapped for each other -- each still names
    itself. Comparing against the caller's expectation catches that: loading
    `eval-scores.schema.json` as the run schema fails.
    """
    if not path.is_file():
        raise ResultsReadError(
            f"{path}: skill-owned run-record schema is missing -- layer 2 cannot run. "
            "It ships inside skills/scorer-gated-skill-edits/references/ (issue #932); "
            "this scanner reads it and never authors a fallback copy."
        )
    parsed = _load_json(path)
    if not isinstance(parsed, dict):
        raise ResultsReadError(f"{path}: skill-owned schema is not a JSON object, got {type(parsed).__name__}")
    try:
        jsonschema.Draft202012Validator.check_schema(parsed)
    except jsonschema.exceptions.SchemaError as error:
        raise ResultsReadError(f"{path}: skill-owned schema is not a valid JSON Schema: {error.message}") from error
    if not parsed.get("required"):
        raise ResultsReadError(
            f"{path}: skill-owned schema declares no required properties -- layer 2 cannot run. "
            "An empty or truncated schema is a legal JSON Schema that validates every instance, "
            "so this is checked separately from check_schema rather than through it."
        )
    if not str(parsed.get("$id", "")).endswith(expected_id_suffix):
        raise ResultsReadError(
            f"{path}: skill-owned schema's $id ({parsed.get('$id')!r}) does not end in "
            f"{expected_id_suffix!r} -- refusing to validate against a schema that is not the "
            "one this check means, which is how the two schemas swapped for each other would pass."
        )
    return parsed


def _escapes_run_dir(entry: str) -> bool:
    """Whether `entry` is anything other than a relative path that stays
    inside its run directory.

    `(run_dir / entry).is_file()` does not itself guard this: pathlib's
    absolute-operand rule replaces the left side outright
    (`Path("/a/b") / "/etc" == Path("/etc")`), so an absolute path that
    happens to exist reads as a resolved reference. Shared by
    `find_artifact_drift` and `find_gate_run_schema_drift` so the one
    containment predicate has a single implementation -- `score_files[].file`
    previously had no guard at all, which made an arbitrary JSON file
    anywhere on the runner readable and, worse, echoed its parsed content
    into a finding line and from there into a public CI log.
    """
    return not entry or entry.startswith("/") or ".." in pathlib.PurePosixPath(entry).parts


def _relative_files(run_dir: pathlib.Path) -> list[str]:
    """Every file under `run_dir`, as a POSIX path relative to `run_dir`,
    sorted.

    `lstat`-based, not `is_file()`-based, so a **broken symlink counts as
    present**. Under `is_file()` it did not: the walk silently dropped it, and
    because it was also unlisted nothing ever checked it -- invisible rather
    than reported, the opposite of what this function's own docstring used to
    claim. A dangling symlink beside a permanent record is exactly the orphan
    `artifacts[]` exists to surface.
    """
    return sorted(p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_symlink() or p.is_file())


def find_symlink_drift(run_dir: pathlib.Path) -> list[str]:
    """`no-symlinks`: a run record holds real files, never symlinks.

    A run record is a permanent, self-contained artifact. A symlink makes its
    content depend on something outside itself, and a symlink pointing outside
    the run directory defeats the containment `_escapes_run_dir` enforces on
    `artifacts[]` -- an entry can be a well-behaved relative path whose target
    is anywhere at all. Rejected outright rather than resolved-and-checked:
    there is no legitimate use for one here, so the narrow rule is also the
    simpler one.
    """
    return [
        f"no-symlinks: {p.relative_to(run_dir).as_posix()!r} is a symlink; a run record holds real files only"
        for p in sorted(run_dir.rglob("*"))
        if p.is_symlink()
    ]


def find_run_dir_name_drift(run_dir: pathlib.Path) -> list[str]:
    """`run-dir-naming`: the directory name must be
    `<date>-issue-<N>-<label>`, the layout
    `evals/evaluating-skill-quality/results/README.md` declares. Checked on
    the directory rather than inside the manifest because the name is the
    only part of a run record a reader sees before opening anything."""
    if _RUN_DIR_RE.match(run_dir.name):
        return []
    return [f"run-dir-naming: {run_dir.name!r} is not <date>-issue-<N>-<label> (lowercase, hyphen-separated label)"]


def find_root_content_drift(run_dir: pathlib.Path) -> list[str]:
    """`run-root-contents`: a run directory root holds `manifest.json`,
    `*.json` score files, and the `artifacts/` directory -- nothing else.

    This is what stops the shape issue #926 measured: 13 `.md` files sitting
    in run roots, outside the layout the README declared and referenced by
    no manifest. Raw prompts and model outputs belong under `artifacts/`, so
    the root stays the machine-readable surface."""
    findings: list[str] = []
    for entry in sorted(run_dir.iterdir()):
        if entry.is_dir():
            if entry.name != ARTIFACTS_DIR_NAME:
                findings.append(
                    f"run-root-contents: unexpected directory {entry.name!r} -- "
                    f"a run directory's only permitted subdirectory is {ARTIFACTS_DIR_NAME}/"
                )
            continue
        if entry.suffix != ".json":
            # The message states what is actually enforced -- the extension --
            # not README's `<full-model-id>.json` convention. This scanner
            # owns no notion of a valid model id, and a message promising a
            # check that does not exist is how a reader comes to trust one.
            # The unenforced half is disclosed in the module docstring.
            findings.append(
                f"run-root-contents: unexpected file {entry.name!r} -- the root holds "
                f"{MANIFEST_NAME} and .json score files only; raw prompts and model "
                f"outputs belong under {ARTIFACTS_DIR_NAME}/"
            )
    return findings


class NonstandardScoreFileEntry(BaseModel):
    """One `nonstandard_score_files[]` entry: a root JSON file that is
    scorer output, just not in `eval-scores.schema.json`'s own shape --
    issue #537's own `claude-sonnet-5.json` (per-iteration `condition`/
    `commit` records rather than `eval-scores.schema.json`'s flat
    `{fixture_id, score}`) is the one committed instance.

    Neither skill-owned schema mentions this key, so pydantic is the sole
    validator for its shape here -- not a secondary typed pass behind an
    already-`jsonschema`-checked instance the way this repository's other
    pydantic use (`gitapex_scan_ssot_schema.py`) works. `extra="forbid"`
    plus a required, non-empty `deviation` is what actually closes the
    escape hatch a CodeRabbit review round found in this rule's first
    version: a bare declared filename proved nothing about what produced
    it, which is how #537's real scorer output ended up mislabeled as a
    checker's. An object with a mandatory disclosure field cannot be
    produced by accident the way a bare string can."""

    model_config = ConfigDict(extra="forbid")

    file: str = Field(min_length=1)
    deviation: str = Field(min_length=1)


def _contains_score_field(payload: Any) -> bool:
    """Whether `payload` holds a numeric, non-boolean `score` key anywhere
    in a nested dict or list, however the file names its own top-level
    records.

    This is the content test that decides which of the two non-score
    classes an undeclared root JSON file belongs to. A genuine checker
    report never carries one: `dispatch-trace-check.json`'s own `runs[]`
    reports a pass/fail verdict (`dispatch_trace_verdict`,
    `checker_exit_code`), never a `[0,1]` score. Scorer output does, even
    when reshaped -- issue #537's `claude-sonnet-5.json` scores every
    iteration on the same scale `eval-scores.schema.json` uses, just inside
    a record shape that schema's own `scores[]` item does not have. `bool`
    is excluded because it is a `int` subclass in Python, and a stray
    `"score": true`/`"score": false` is not a score."""
    if isinstance(payload, dict):
        score = payload.get("score")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            return True
        return any(_contains_score_field(v) for v in payload.values())
    if isinstance(payload, list):
        return any(_contains_score_field(v) for v in payload)
    return False


def find_non_score_root_json_drift(
    instance: Any,
    run_dir: pathlib.Path,
    scores_validator: jsonschema.Draft202012Validator,
) -> list[str]:
    """`checker-report-declared` / `nonstandard-score-file-declared`: a root
    `*.json` file that does not validate as a per-model score file must be
    explicitly declared as one of two distinct classes -- `checker_reports[]`
    (a deterministic checker's own verdict output) or
    `nonstandard_score_files[]` (scorer output in a nonstandard shape, with a
    mandatory `deviation` disclosure) -- and content, not the declaration
    itself, decides which class a file actually belongs to (see
    `_contains_score_field`).

    `results/README.md` names "checker report" as a third permitted
    root-level class alongside per-model score files, but until this rule
    existed that classification was documentation only: the scanner accepted
    *any* root `.json` file once `artifacts[]` listed it, whatever its
    content -- an adversarial review round on this file found that gap, and a
    later CodeRabbit round found that the fix's own single field
    (`checker_reports[]`) reopened a narrower version of it, since a bare
    declared filename proved nothing about what produced the file and #537's
    own scorer output was mislabeled through exactly that gap. Both are
    closed together here: a root JSON file that already validates against
    `eval-scores.schema.json` needs no declaration at all (that is what a
    per-model score file's own committed shape already proves); one that
    does not and carries a per-item `score` must be declared in
    `nonstandard_score_files[]`, never `checker_reports[]`; one that does not
    and carries no `score` at all must be declared in `checker_reports[]`.
    A filename declared in both is a finding -- a root JSON file is exactly
    one class, not both.

    The three-way content check applies to a *declared* `nonstandard_score_files[]`
    entry too, not only to an undeclared file's classification walk: a
    CodeRabbit follow-up round found the declared-entry loop checked for a
    missing `score` but never checked `scores_validator.is_valid`, so a file
    that already validates in full could be declared `nonstandard` anyway
    and the mislabeling in the other direction went unflagged. Both declared
    loops now share the same invariant the undeclared walk enforces.

    Both keys are layer-1-only and optional: most records have neither and
    need not declare an empty list."""
    if not isinstance(instance, dict):
        return []
    findings: list[str] = []

    checker_raw = instance.get("checker_reports")
    if checker_raw is None:
        checker_raw = []
    checker_declared: set[str] = set()
    if not isinstance(checker_raw, list):
        findings.append("checker-report-declared: checker_reports must be an array of bare filenames")
        checker_raw = []
    for entry in checker_raw:
        if not isinstance(entry, str) or not entry:
            findings.append(f"checker-report-declared: checker_reports entry is not a non-empty string: {entry!r}")
            continue
        if _escapes_run_dir(entry) or "/" in entry:
            findings.append(
                f"checker-report-declared: checker_reports entry {entry!r} must be a bare filename in the run root"
            )
            continue
        checker_declared.add(entry)
        target = run_dir / entry
        if not target.is_file():
            findings.append(f"checker-report-declared: checker_reports lists {entry!r}, which does not exist")
            continue
        if _contains_score_field(_load_json(target)):
            findings.append(
                f"checker-report-declared: {entry!r} is declared in checker_reports[] but its own content "
                "carries a per-item score -- that is scorer output, not a checker's verdict, and belongs in "
                "nonstandard_score_files[] instead"
            )

    nonstandard_raw = instance.get("nonstandard_score_files")
    if nonstandard_raw is None:
        nonstandard_raw = []
    nonstandard_declared: set[str] = set()
    if not isinstance(nonstandard_raw, list):
        findings.append(
            "nonstandard-score-file-declared: nonstandard_score_files must be an array of {file, deviation} objects"
        )
        nonstandard_raw = []
    for entry in nonstandard_raw:
        try:
            parsed = NonstandardScoreFileEntry.model_validate(entry)
        except ValidationError as error:
            first = error.errors()[0]["msg"] if error.errors() else str(error)
            findings.append(
                f"nonstandard-score-file-declared: nonstandard_score_files entry {entry!r} is invalid: {first}"
            )
            continue
        if _escapes_run_dir(parsed.file) or "/" in parsed.file:
            findings.append(
                f"nonstandard-score-file-declared: nonstandard_score_files entry {parsed.file!r} must be a bare "
                "filename in the run root"
            )
            continue
        nonstandard_declared.add(parsed.file)
        target = run_dir / parsed.file
        if not target.is_file():
            findings.append(
                f"nonstandard-score-file-declared: nonstandard_score_files lists {parsed.file!r}, which does not exist"
            )
            continue
        payload = _load_json(target)
        if scores_validator.is_valid(payload):
            findings.append(
                f"nonstandard-score-file-declared: {parsed.file!r} is declared in nonstandard_score_files[] but "
                "its own content already validates against eval-scores.schema.json -- that is a standard score "
                "file and needs no declaration at all"
            )
        elif not _contains_score_field(payload):
            findings.append(
                f"nonstandard-score-file-declared: {parsed.file!r} is declared in nonstandard_score_files[] but "
                "its own content carries no per-item score -- that is not scorer output in a nonstandard shape, "
                "and belongs in checker_reports[] instead"
            )

    for both in sorted(checker_declared & nonstandard_declared):
        findings.append(
            f"non-score-root-json-declared: {both!r} is declared in both checker_reports[] and "
            "nonstandard_score_files[] -- a root JSON file is exactly one class, not both"
        )

    declared = checker_declared | nonstandard_declared
    for path in sorted(run_dir.glob("*.json")):
        if path.name == MANIFEST_NAME or path.name in declared:
            continue
        payload = _load_json(path)
        if scores_validator.is_valid(payload):
            continue
        if _contains_score_field(payload):
            findings.append(
                f"nonstandard-score-file-declared: {path.name!r} carries a per-item score but does not validate "
                "as a per-model score file and is not declared in nonstandard_score_files[] -- scorer output in "
                "a nonstandard shape must be declared with a deviation disclosure"
            )
        else:
            findings.append(
                f"checker-report-declared: {path.name!r} does not validate as a per-model score file, carries no "
                "per-item score, and is not declared in checker_reports[] -- a non-score root JSON file must be "
                "declared in one of the two classes"
            )
    return findings


def find_artifact_drift(instance: Any, run_dir: pathlib.Path) -> list[str]:
    """`artifacts-agree`: `artifacts[]` and the filesystem must agree in
    **both** directions -- a listed file that does not exist is a dangling
    reference, and a file present but unlisted is an orphan.

    `artifacts[]` covers every file in the run directory except
    `manifest.json` itself, score files included. One reachability rule, not
    two: `eval-run.schema.json`'s own `score_files` description states the
    principle ("an unreferenced file next to a record is an orphan, not a
    result"), and a second list covering only `.md` attachments would leave
    a stray `.json` beside a record unreachable from it."""
    if not isinstance(instance, dict):
        return []
    listed_raw = instance.get("artifacts")
    if not isinstance(listed_raw, list):
        return ["artifacts-agree: artifacts must be an array of paths relative to this manifest"]
    findings: list[str] = []
    listed: set[str] = set()
    for entry in listed_raw:
        if not isinstance(entry, str) or not entry:
            findings.append(f"artifacts-agree: artifacts entry is not a non-empty string: {entry!r}")
            continue
        if _escapes_run_dir(entry):
            findings.append(
                f"artifacts-agree: artifacts entry {entry!r} must be a relative path inside the run directory"
            )
            continue
        # Normalized before the set-difference, so `./artifacts/a.md`,
        # `artifacts//a.md` and `artifacts/./a.md` compare equal to the
        # `artifacts/a.md` the filesystem walk produces. Unnormalized, each of
        # those reported the listed file as an unlisted orphan -- still
        # fail-closed, but a finding that reads as a false positive teaches a
        # reader to distrust the gate.
        normalized = pathlib.PurePosixPath(entry).as_posix()
        if normalized in listed:
            findings.append(f"artifacts-agree: artifacts lists {entry!r} more than once")
            continue
        if normalized == MANIFEST_NAME:
            findings.append(
                f"artifacts-agree: artifacts must not list {MANIFEST_NAME} -- it is the record, not an attachment"
            )
            continue
        listed.add(normalized)
        try:
            exists = (run_dir / normalized).is_file()
        except OSError as error:
            # ENAMETOOLONG and friends: `Path.is_file()` swallows only
            # ENOENT/ENOTDIR/EBADF/ELOOP, so a 5000-character entry raised
            # straight out of find_drift as a traceback instead of a finding.
            findings.append(f"artifacts-agree: artifacts entry {entry!r} cannot be resolved: {error}")
            continue
        if not exists:
            findings.append(f"artifacts-agree: artifacts lists {entry!r}, which does not exist")
    present = set(_relative_files(run_dir)) - {MANIFEST_NAME}
    for orphan in sorted(present - listed):
        findings.append(f"artifacts-agree: {orphan!r} exists but is not listed in artifacts")
    return findings


def find_key_spelling_drift(instance: Any) -> list[str]:
    """`key-spelling`: reject a known misspelling of a contract key.

    Not expressible in either schema: both deliberately permit additional
    keys, so a misspelled `model` reads to them as an extra key they were
    told to allow. This is the drift that actually happened."""
    if not isinstance(instance, dict):
        return []
    return [
        f"key-spelling: {wrong!r} is not a contract key -- this corpus spells it {right!r}"
        for wrong, right in sorted(KEY_SPELLING_DRIFT.items())
        if wrong in instance
    ]


def find_minimum_key_drift(instance: Any) -> list[str]:
    """`minimum-keys`: every key
    `evals/evaluating-skill-quality/results/README.md` declares as the
    manifest minimum must be present. Presence only -- each key's own type
    and content is either `eval-run.schema.json`'s job (a gate run) or the
    dedicated checks below (`commit`, `known_gaps`, `issue`)."""
    if not isinstance(instance, dict):
        return ["minimum-keys: manifest is not a JSON object"]
    return [f"minimum-keys: missing {key!r}" for key in README_MINIMUM_KEYS if key not in instance]


def _known_gaps(instance: dict[str, Any]) -> list[str]:
    raw = instance.get("known_gaps")
    return [g for g in raw if isinstance(g, str)] if isinstance(raw, list) else []


def find_known_gaps_drift(instance: Any) -> list[str]:
    """`known-gaps-explicit`: `known_gaps` must be a non-empty array of
    non-empty strings. A run with nothing to disclose says so with an
    explicit "none known" entry, so an empty array can never read as a clean
    run -- the same rule `eval-run.schema.json` states for a gate run,
    applied to a pre-contract record too, since that is the class where a
    silent omission actually occurred."""
    if not isinstance(instance, dict) or "known_gaps" not in instance:
        return []
    raw = instance.get("known_gaps")
    if not isinstance(raw, list) or not raw:
        return ["known-gaps-explicit: known_gaps must be a non-empty array; state 'none known' explicitly"]
    return [
        "known-gaps-explicit: every known_gaps entry must be a non-empty string"
        for entry in raw
        if not isinstance(entry, str) or not entry.strip()
    ][:1]


def find_commit_drift(instance: Any) -> list[str]:
    """`commit-recorded-or-disclosed`: `commit` is a 7-40 character hex
    object name, or an explicit `null` accompanied by a `known_gaps` entry
    naming `commit`.

    Two of the eight committed records genuinely have no commit. A value
    guessed from their date and issue number would be inference presented as
    record, which is the failure class issue #631 blocker 2 already
    documented for `expected.exercises` -- an absent declaration reading as
    a satisfied one. So the null is allowed and its disclosure is
    mandatory. Note this is stricter than `eval-run.schema.json`, which
    permits no null at all: a gate run reaches that schema too and is held
    to it, so allowing null here widens nothing for a new run."""
    if not isinstance(instance, dict) or "commit" not in instance:
        return []
    commit = instance.get("commit")
    if commit is None:
        if any(_COMMIT_GAP_RE.match(gap) for gap in _known_gaps(instance)):
            return []
        return [
            "commit-recorded-or-disclosed: commit is null with no known_gaps entry opening "
            "'commit is null: <reason>' -- an undisclosed null reads as a satisfied declaration, "
            "and a substring test for the word would be satisfied by an unrelated sentence"
        ]
    if isinstance(commit, str) and _COMMIT_RE.match(commit):
        return []
    return [f"commit-recorded-or-disclosed: commit must be a 7-40 character hex object name or null, got {commit!r}"]


def find_issue_url_drift(instance: Any) -> list[str]:
    """`issue-full-url`: `issue` must be a full `http(s)://` URL. A bare
    number resolves only inside the repository that minted it, and a run
    record outlives that context -- `eval-run.schema.json` states the same
    rule for a gate run, and every existing record already satisfies it."""
    if not isinstance(instance, dict) or "issue" not in instance:
        return []
    issue = instance.get("issue")
    if isinstance(issue, str) and issue.startswith(("http://", "https://")):
        return []
    return [f"issue-full-url: issue must be a full URL, not a repository-local reference, got {issue!r}"]


def find_run_dir_agreement_drift(instance: Any, run_dir: pathlib.Path) -> list[str]:
    """`run-dir-agrees-with-manifest`: the date and issue number in the
    directory name must match the manifest's own `date` and `issue`.

    Cross-file by nature, so no schema can express it. Without it the
    directory name -- the only part of a record a reader sees before opening
    anything -- can say one thing while the record says another, and both pass
    every other rule here."""
    match = _RUN_DIR_RE.match(run_dir.name)
    if match is None or not isinstance(instance, dict):
        return []
    dir_date, dir_issue = match.group(1), match.group(2)
    findings: list[str] = []
    if instance.get("date") != dir_date:
        findings.append(
            f"run-dir-agrees-with-manifest: directory says date {dir_date}, manifest says {instance.get('date')!r}"
        )
    issue = instance.get("issue")
    if not (isinstance(issue, str) and issue.rstrip("/").endswith(f"/{dir_issue}")):
        findings.append(f"run-dir-agrees-with-manifest: directory says issue {dir_issue}, manifest issue is {issue!r}")
    return findings


def find_record_contract_drift(
    instance: Any,
    run_label: str,
    legacy_pre_contract_runs: frozenset[str] = LEGACY_PRE_CONTRACT_RUNS,
) -> list[str]:
    """`record-contract-declared`: every manifest declares
    `record_contract` as one of `gate-run` or `pre-contract`, and a
    `pre-contract` record discloses that exemption in `known_gaps`.

    Fail-closed by construction: an undeclared record is a finding rather
    than a layer-2 exemption, so omitting the key cannot buy the silence
    that omitting `models` and `commit` bought in the pre-existing
    manifests."""
    if not isinstance(instance, dict):
        return []
    contract = instance.get("record_contract")
    if contract not in RECORD_CONTRACTS:
        return [
            f"record-contract-declared: record_contract must be one of {list(RECORD_CONTRACTS)}, got {contract!r} -- "
            "an undeclared record is not exempt from the gate-run schema, it is unvalidatable"
        ]
    if contract == PRE_CONTRACT:
        if run_label not in legacy_pre_contract_runs:
            return [
                f"record-contract-declared: {run_label} is not one of the "
                f"{len(legacy_pre_contract_runs)} run directories that predate the run-record "
                "contract, so it may not claim the pre-contract exemption -- a new run has a "
                "runner version and a gate verdict to record, and must declare gate-run"
            ]
        if not any(_CONTRACT_GAP_RE.match(gap) for gap in _known_gaps(instance)):
            return [
                "record-contract-declared: a pre-contract record must carry a known_gaps entry "
                "opening 'record_contract is pre-contract: <which contract fields were never "
                "captured>'; a bare mention of the key does not disclose anything"
            ]
    if contract == GATE_RUN_CONTRACT and "gate" not in instance:
        return ["record-contract-declared: a gate-run record must carry the gate key eval-run.schema.json requires"]
    return []


def find_gate_run_schema_drift(
    instance: Any,
    run_dir: pathlib.Path,
    run_validator: jsonschema.Draft202012Validator,
    scores_validator: jsonschema.Draft202012Validator,
) -> list[str]:
    """Layer 2: a record declaring `record_contract: "gate-run"` validates
    in full against `eval-run.schema.json`, and every file its
    `score_files[]` points at validates against `eval-scores.schema.json`.

    A pre-contract record reaches neither validator, for the reason the
    module docstring states. A score file that cannot be read at all raises
    `ResultsReadError` rather than being reported as a finding, matching
    every other unparseable-input path here."""
    if not isinstance(instance, dict) or instance.get("record_contract") != GATE_RUN_CONTRACT:
        return []
    findings = _gitapex_schema_validation.schema_violations(instance, run_validator)
    score_files = instance.get("score_files")
    if not isinstance(score_files, list):
        return findings
    for row in score_files:
        if not isinstance(row, dict):
            continue
        rel = row.get("file")
        if not isinstance(rel, str) or not rel:
            continue
        if _escapes_run_dir(rel):
            findings.append(
                f"score-file-resolves: score_files points at {rel!r}, which must be a relative path "
                "inside the run directory -- refusing to read outside it"
            )
            continue
        target = run_dir / rel
        if not target.is_file():
            findings.append(f"score-file-resolves: score_files points at {rel!r}, which does not exist")
            continue
        findings.extend(
            f"score-file {rel}: {f}"
            for f in _gitapex_schema_validation.schema_violations(_load_json(target), scores_validator)
        )
    return findings


def find_drift(
    evals_dir: pathlib.Path = EVALS_DIR,
    run_schema_path: pathlib.Path = RUN_SCHEMA_PATH,
    scores_schema_path: pathlib.Path = SCORES_SCHEMA_PATH,
    min_expected_run_dirs: int = MIN_EXPECTED_RUN_DIRS,
    legacy_pre_contract_runs: frozenset[str] = LEGACY_PRE_CONTRACT_RUNS,
) -> list[str]:
    """Every finding across every discovered run directory. Empty list means
    the whole corpus is clean.

    `min_expected_run_dirs` is checked before anything else, for the reason
    `gitapex_scan_skill_metadata_schema.py`'s own floor states: without it a
    wrong `evals_dir`, or a checkout that lost most of `evals/`, passes this
    gate vacuously. A caller exercising a small fixture tree must lower it
    explicitly.

    Both schemas are loaded once and their validators reused across every
    record, rather than rebuilt per record -- `jsonschema` performs `$ref`
    resolution and registry setup on construction."""
    run_validator = _gitapex_schema_validation.build_validator(_load_schema(run_schema_path, RUN_SCHEMA_NAME))
    scores_validator = _gitapex_schema_validation.build_validator(_load_schema(scores_schema_path, SCORES_SCHEMA_NAME))
    run_dirs = discover_run_dirs(evals_dir)
    findings = find_misplaced_results_dirs(evals_dir)

    if len(run_dirs) < min_expected_run_dirs:
        return [
            *findings,
            f"run-discovery-floor: found only {len(run_dirs)} run "
            f"director{'y' if len(run_dirs) == 1 else 'ies'} under {evals_dir}/*/results/ "
            f"(expected at least {min_expected_run_dirs}) -- this usually means evals_dir "
            "is wrong or missing, not that run records were actually removed",
        ]

    for run_dir in run_dirs:
        prefix = f"{run_dir.parent.parent.name}/{run_dir.name}"
        findings.extend(f"{prefix}: {f}" for f in find_run_dir_name_drift(run_dir))
        findings.extend(f"{prefix}: {f}" for f in find_root_content_drift(run_dir))
        findings.extend(f"{prefix}: {f}" for f in find_symlink_drift(run_dir))
        manifest = run_dir / MANIFEST_NAME
        if not manifest.is_file():
            findings.append(f"{prefix}: manifest-present: missing {MANIFEST_NAME}")
            continue
        instance = _load_json(manifest)
        findings.extend(f"{prefix}: {f}" for f in find_minimum_key_drift(instance))
        findings.extend(f"{prefix}: {f}" for f in find_key_spelling_drift(instance))
        findings.extend(f"{prefix}: {f}" for f in find_known_gaps_drift(instance))
        findings.extend(f"{prefix}: {f}" for f in find_commit_drift(instance))
        findings.extend(f"{prefix}: {f}" for f in find_issue_url_drift(instance))
        findings.extend(f"{prefix}: {f}" for f in find_run_dir_agreement_drift(instance, run_dir))
        findings.extend(
            f"{prefix}: {f}" for f in find_record_contract_drift(instance, prefix, legacy_pre_contract_runs)
        )
        findings.extend(f"{prefix}: {f}" for f in find_artifact_drift(instance, run_dir))
        findings.extend(f"{prefix}: {f}" for f in find_non_score_root_json_drift(instance, run_dir, scores_validator))
        findings.extend(
            f"{prefix}: {f}" for f in find_gate_run_schema_drift(instance, run_dir, run_validator, scores_validator)
        )
    return findings


def main() -> int:
    try:
        findings = find_drift()
    except ResultsReadError as error:
        print("eval results schema drift:")
        print(f"  {error}")
        return 1
    if findings:
        print("eval results schema drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No eval results schema drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
