#!/usr/bin/env python3
"""Validate every committed eval run record under `evals/*/results/`.

ACTIVE (issue #926): registered in `.gitapex/ssot.json` as
`eval-results-schema-drift`. Enforced exactly the way its three siblings
(`gitapex_scan_ssot_schema.py`, `gitapex_scan_skill_metadata_schema.py`,
`gitapex_scan_eval_suite_schema.py`) already are -- no dedicated workflow
step and no pre-commit hook, only
`tests/test_gitapex_scan_eval_results_schema.py`'s own
`test_real_repository_run_records_have_no_drift`, which calls `find_drift()`
against the real `evals/` tree inside `.github/workflows/test.yml`'s pytest
step.

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
record declaring neither is a finding: the fail-closed direction, so a new
run cannot slip past layer 2 by simply omitting the key the way the seven
pre-existing manifests omitted `models` and `commit`.

What this scanner does NOT check, disclosed rather than solved
-------------------------------------------------------------

- A schema pins a manifest's shape, not the truthfulness of its values. A
  run recording a model it did not invoke, or an `artifacts[]` entry
  pointing at a real but semantically unrelated file, passes here.
- `commit` is checked for hex shape, not for resolving on any remote. It
  deliberately does not shell out to git: a shallow clone (this
  repository's own CI checkout) cannot resolve a historical object name,
  and a gate that fails on a property of the clone rather than of the
  record would be worse than no gate.
- Whether the pytest job carrying this scanner is a *required* status check
  on the protected branch is a GitHub admin setting no in-repo tooling can
  read -- the same open item `.github/PULL_REQUEST_TEMPLATE.md` already
  records for every gate here.

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

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
SCHEMA_DIR = REPO_ROOT / "skills" / "scorer-gated-skill-edits" / "references"
RUN_SCHEMA_PATH = SCHEMA_DIR / "eval-run.schema.json"
SCORES_SCHEMA_PATH = SCHEMA_DIR / "eval-scores.schema.json"

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

_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
_RUN_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-issue-\d+-[a-z0-9]+(-[a-z0-9]+)*$")

# Fail-closed floor on discovery itself, the same purpose and shape as
# `gitapex_scan_skill_metadata_schema.py`'s own MIN_EXPECTED_SKILL_DIRS: set
# close to the real current count (8) with headroom, not at 1, so a partial
# discovery failure is caught too, not only a total-zero one.
MIN_EXPECTED_RUN_DIRS = 6


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
    return _gitapex_schema_validation.load_json_or_raise(path, ResultsReadError)


def _load_schema(path: pathlib.Path) -> dict[str, Any]:
    """Read one of the two skill-owned schemas, raising rather than
    returning an empty dict when it is absent. Issue #926's own proof method
    requires this scanner to "fail loudly if either is absent" -- a
    `{}`-shaped fallback validates every instance successfully, turning the
    whole of layer 2 into a silent pass the moment the skill is removed or
    its `references/` directory is renamed."""
    if not path.is_file():
        raise ResultsReadError(
            f"{path}: skill-owned run-record schema is missing -- layer 2 cannot run. "
            "It ships inside skills/scorer-gated-skill-edits/references/ (issue #932); "
            "this scanner reads it and never authors a fallback copy."
        )
    parsed: dict[str, Any] = _load_json(path)
    return parsed


def _relative_files(run_dir: pathlib.Path) -> list[str]:
    """Every regular file under `run_dir`, as a POSIX path relative to
    `run_dir` itself, sorted. Symlinks are excluded by `is_file()` following
    them only when the target exists, so a broken symlink is reported by
    `find_artifact_drift` as an unlisted-or-missing path rather than
    crashing the walk."""
    return sorted(p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_file())


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
            findings.append(
                f"run-root-contents: unexpected file {entry.name!r} -- the root holds "
                f"{MANIFEST_NAME} and <full-model-id>.json only; raw prompts and model "
                f"outputs belong under {ARTIFACTS_DIR_NAME}/"
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
        if entry.startswith("/") or ".." in pathlib.PurePosixPath(entry).parts:
            findings.append(
                f"artifacts-agree: artifacts entry {entry!r} must be a relative path inside the run directory"
            )
            continue
        listed.add(entry)
        if not (run_dir / entry).is_file():
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
        if any("commit" in gap for gap in _known_gaps(instance)):
            return []
        return [
            "commit-recorded-or-disclosed: commit is null with no known_gaps entry naming it -- "
            "an undisclosed null reads as a satisfied declaration"
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


def find_record_contract_drift(instance: Any) -> list[str]:
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
    if contract == PRE_CONTRACT and not any("record_contract" in gap for gap in _known_gaps(instance)):
        return [
            "record-contract-declared: a pre-contract record must carry a known_gaps entry naming "
            "record_contract and stating which contract fields were never captured"
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
    run_validator = _gitapex_schema_validation.build_validator(_load_schema(run_schema_path))
    scores_validator = _gitapex_schema_validation.build_validator(_load_schema(scores_schema_path))
    run_dirs = discover_run_dirs(evals_dir)

    if len(run_dirs) < min_expected_run_dirs:
        return [
            f"run-discovery-floor: found only {len(run_dirs)} run "
            f"director{'y' if len(run_dirs) == 1 else 'ies'} under {evals_dir}/*/results/ "
            f"(expected at least {min_expected_run_dirs}) -- this usually means evals_dir "
            "is wrong or missing, not that run records were actually removed"
        ]

    findings: list[str] = []
    for run_dir in run_dirs:
        prefix = f"{run_dir.parent.parent.name}/{run_dir.name}"
        findings.extend(f"{prefix}: {f}" for f in find_run_dir_name_drift(run_dir))
        findings.extend(f"{prefix}: {f}" for f in find_root_content_drift(run_dir))
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
        findings.extend(f"{prefix}: {f}" for f in find_record_contract_drift(instance))
        findings.extend(f"{prefix}: {f}" for f in find_artifact_drift(instance, run_dir))
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
