#!/usr/bin/env python3
"""Validate every committed waza eval suite against waza's own vendored schemas.

ACTIVE (issue #862): registered in .gitapex/ssot.json as
eval-suite-schema-drift. Enforced exactly the way its two siblings
.github/scripts/gitapex_scan_ssot_schema.py (ssot-schema-drift) and
.github/scripts/gitapex_scan_skill_metadata_schema.py
(skill-metadata-schema-drift) already are -- no dedicated CI workflow step
and no pre-commit hook, only tests/test_gitapex_scan_eval_suite_schema.py's
own test_real_repository_eval_suites_have_no_schema_drift calling find_drift()
against the real evals/ tree with no fixture override, inside the pytest
step of .github/workflows/test.yml. That is this repository's established
convention for this gate shape; a third enforcement path would be redundant.

Why this gate exists at all. Neither of waza's own two surfaces rejects an
unknown field in a committed suite:

- ``waza run`` logs ``level=WARN msg="unknown schema field ignored for
  same-major compatibility"`` and still passes the task.
- ``waza check`` does report it (``/expected: additional properties ''
  not allowed``) but exits 0, and .github/workflows/waza-check.yml used to
  set ``continue-on-error: true`` deliberately, describing itself in its
  own comments as "a report, not a gate". Issue #862 explicitly forbade
  changing that posture, so this scanner was built as the gate instead.
  Issue #1135 later dropped waza-check.yml entirely -- its schema-shape
  content was already fully covered here, waza-independently -- so this
  scanner is now the only check of this content, not merely a stricter
  sibling of an advisory report.

The repository-local consumers that read the extension keys below do so
through pydantic models configured ``extra="allow"``, so a *misspelled*
extension key is invisible from both directions at once: waza ignores it
and the local consumer never sees the field it was meant to populate. The
assertion silently asserts nothing. EXTENSION_KEYS converts that silent
acceptance into an explicit, reviewed set -- an approved key passes, a
misspelling of it fails.

Three layers, one findings list:

1. Schema validation. Each evals/*/eval.yaml is validated against
   .gitapex/waza-eval.schema.json and each evals/*/tasks/*.yaml against
   .gitapex/waza-task.schema.json, both vendored verbatim from waza's own
   published ``schemas/`` at the release tag flake.nix pins -- not from
   ``main``, which has already drifted ahead of the pinned tag (it adds
   ``$defs.jsonSchemaGraderConfig.properties.extract_json``). The vendored
   copy is the one matching the binary that actually runs here. Before
   validating, each vendored schema is *extended* by EXTENSION_KEYS, which
   re-opens exactly the named repository-local keys that the upstream
   ``expected`` object's own ``"additionalProperties": false`` would
   otherwise reject.

   FACT, verified against the vendored bytes rather than taken from issue
   #862's own prose: both schemas declare ``"$schema":
   "http://json-schema.org/draft-07/schema#"``, NOT draft 2020-12 as that
   issue states. This module therefore does not reuse
   _gitapex_schema_validation.build_validator, whose whole point is to
   always construct a Draft202012Validator (see its docstring); it selects
   the validator class from each schema's own declared ``$schema`` via
   ``jsonschema.validators.validator_for`` so the vendored files are graded
   under the draft they were written for. ``load_json_or_raise`` from that
   same shared module IS reused -- reading and JSON-parsing a file is
   draft-agnostic.

2. Allowlist integrity. Each EXTENSION_KEYS row names the schema ``$defs``
   object it re-opens and the repository file that actually reads the key.
   Both are checked against the real tree: the ``$defs`` anchor must exist
   in the vendored schema, the consumer file must exist, and the consumer
   must still mention the key by name. This is what keeps the allowlist
   from rotting into a list of keys nobody reads -- the residual risk issue
   #862's own acceptance map names for this row. A key upstream later
   adopts as a native property is also reported, so the row is deleted
   rather than left shadowing a field waza now owns.

3. Vendor-pin drift. Two offline checks plus one opt-in network check:

   - ``pin-drift``: flake.nix's own pinned waza release tag must equal
     VENDORED_WAZA_TAG. This is the check that catches the scenario issue
     #862 names -- a future waza version bump silently desynchronizing the
     vendored copies from the binary that runs.
   - ``vendor-digest-drift``: each vendored file's sha256 must equal the
     digest recorded here, so editing a vendored copy in place fails
     instead of quietly becoming the new baseline.
   - ``--verify-upstream``: fetches both schemas from raw.githubusercontent
     at VENDORED_WAZA_TAG and compares bytes. Off by default: the offline
     checks above must stay deterministic in a network-less checkout, and
     this repository's pytest gate runs without any guarantee of egress.
     It is the only check that proves the vendored bytes match what
     upstream actually published, so run it when bumping the pin.

Known limitations, stated rather than implied (dimensions 9 and 11 of
skills/evaluating-deterministic-gate-quality/references/dimensions.md):

- The digest check cannot catch an edit made *together with* a matching
  digest update in the same commit. Only ``--verify-upstream`` proves the
  vendored bytes are what upstream published, and it is off by default,
  so the offline path's real guarantee is "changed deliberately and
  visibly in review", not "matches upstream".
- The allowlist gates a key's *spelling*, not its value's shape. Each
  key's value shape stays with the consumer named in its row (for the
  ``near`` forms, gitapex_score_contract.py raises on a malformed entry;
  for ``requires_fresh_dispatch``, gitapex_lint_fixture_assertions.py's
  own dispatch-declaration check). A well-spelled key carrying a
  nonsense value passes this gate.
- ``find_pin_drift`` reads flake.nix as text, anchored on the waza tag's
  own literal prefix. A future flake.nix that stops spelling the tag
  literally (composing it from a version variable, say) would report
  "pins no recognizable waza release tag" rather than silently passing --
  fail-closed, but it would need this pattern updated.
- A suite directory holding an eval.yaml but no tasks/ files is not
  itself reported by the empty-corpus check; only a wholly empty evals/
  tree is. Such a suite is still caught from the other direction, by
  ``find_declared_task_coverage`` -- its own ``tasks`` glob would resolve
  to nothing. What stays out of scope is whether a suite has *enough*
  tasks, which is skill-branch-fixture-coverage's job, not this gate's.
- ``find_declared_task_coverage`` reconciles each suite's declared
  ``tasks`` globs against ``_TASK_GLOBS``, but cannot follow a
  ``tasks_from`` reference into another file; it reports the reference
  as ungraded rather than pretending to have graded it.
- Enforcement mode verified: the pytest gate of .github/workflows/test.yml
  (the same mode ssot-schema-drift and skill-metadata-schema-drift run in).
  Whether that job is a *required* status check on the protected branch is
  a GitHub admin setting no in-repo tooling can read -- the same open item
  .github/PULL_REQUEST_TEMPLATE.md already names for every CI gate here.

Run standalone (exit 0 clean, 1 on drift or a read error) or via the pytest
gate in tests/test_gitapex_scan_eval_suite_schema.py.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import http.client
import pathlib
import re
import sys
import urllib.request
from typing import Any, NamedTuple

import _gitapex_schema_validation
import jsonschema
import jsonschema.validators
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
EVAL_SCHEMA_PATH = REPO_ROOT / ".gitapex" / "waza-eval.schema.json"
TASK_SCHEMA_PATH = REPO_ROOT / ".gitapex" / "waza-task.schema.json"
FLAKE_PATH = REPO_ROOT / "flake.nix"

# The waza release tag both vendored schemas were copied from, and the tag
# flake.nix must still pin for those copies to describe the binary that
# runs. Bumping waza means re-vendoring both files, re-recording both
# digests below, and re-running this script with --verify-upstream.
VENDORED_WAZA_TAG = "azd-ext-microsoft-azd-waza_0.38.0"
_UPSTREAM_RAW = "https://raw.githubusercontent.com/microsoft/waza/{tag}/schemas/{name}"

# sha256 of each vendored file exactly as committed. Recorded, not derived:
# a digest recomputed at check time would agree with any edit.
VENDORED_DIGESTS: dict[str, str] = {
    "eval.schema.json": "3618c117343aef3589bc960f9af31b14ef68bf83231bc630278c0b75597c2a49",
    "task.schema.json": "0981881ecfd93b081b2ecfce31aeb14467f68db4b424ede64d23aa50af465e55",
}

# flake.nix pins waza by the full release tag inside its ghRelease call.
# Anchored on the tag's own literal prefix rather than on a `version = `
# assignment: the same file carries a `version = "0.38.0"` line for every
# Class B tool, and matching the wrong one would grade apm's pin as waza's.
_FLAKE_WAZA_TAG_RE = re.compile(r'"(azd-ext-microsoft-azd-waza_[0-9][^"]*)"')

_HTTP_TIMEOUT_SECONDS = 30


class SuiteReadError(Exception):
    """A vendored schema, a flake.nix, or a committed suite file could not be
    read or parsed at all -- exit 1 with a message, never a traceback.
    Distinct from a parseable-but-drifted file, which find_drift reports as
    an ordinary finding."""


class ExtensionKey(NamedTuple):
    """One repository-local key that extends waza's own task schema.

    ``schema_def`` is the ``$defs`` object the key is re-opened inside
    (every current key extends ``expected``; the field exists so a future
    key at another location is expressible without reshaping this table).
    ``consumer`` is the repository file that actually reads the key, and
    ``reads`` is what that consumer does with it -- the "named consumer"
    issue #862's acceptance map requires for every listed key.
    """

    key: str
    schema_def: str
    consumer: str
    reads: str


# The reviewed allowlist. Adding a row here is the approval step: it is the
# only way a non-waza key may appear in a committed suite. Every row's
# consumer is verified to exist and to still mention the key by
# find_allowlist_drift below, so a row cannot outlive the code that reads it.
EXTENSION_KEYS: tuple[ExtensionKey, ...] = (
    ExtensionKey(
        key="exercises",
        schema_def="expected",
        consumer=".github/scripts/gitapex_gate_split_fixture_coverage.py",
        reads="check_exercises_declaration_coverage requires each selected fixture to name a real ###-level split.md section",
    ),
    ExtensionKey(
        key="requires_fresh_dispatch",
        schema_def="expected",
        consumer="evals/scripts/gitapex_lint_fixture_assertions.py",
        reads="dispatch-declaration coverage: a fixture asserting a subagent dispatch must declare tool_names/min_dispatches",
    ),
    ExtensionKey(
        key="output_icontains",
        schema_def="expected",
        consumer="skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py",
        reads="score() counts each entry as satisfied when present case-insensitively (str.casefold)",
    ),
    ExtensionKey(
        key="output_not_icontains",
        schema_def="expected",
        consumer="skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py",
        reads="score() counts each entry as satisfied when absent case-insensitively (str.casefold)",
    ),
    ExtensionKey(
        key="output_contains_near",
        schema_def="expected",
        consumer="skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py",
        reads="score() counts each entry satisfied when its substrings co-occur inside a character window",
    ),
    ExtensionKey(
        key="output_not_contains_near",
        schema_def="expected",
        consumer="skills/scorer-gated-skill-edits/scripts/gitapex_score_contract.py",
        reads="score() counts each entry satisfied when its substrings do NOT co-occur inside a character window",
    ),
)


def _read_text_or_raise(path: pathlib.Path) -> str:
    """Read `path` as UTF-8. Raises SuiteReadError naming the path rather
    than letting an OSError/UnicodeDecodeError surface as a traceback."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise SuiteReadError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise SuiteReadError(f"{path}: is not valid UTF-8: {error}") from error


def _load_yaml_or_raise(path: pathlib.Path) -> Any:
    """Read and YAML-parse `path`. A suite file that is not valid YAML is a
    read failure, not a schema finding: there is no instance to validate."""
    text = _read_text_or_raise(path)
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise SuiteReadError(f"{path}: is not valid YAML: {error}") from error


def extend_schema(schema: dict[str, Any], keys: tuple[ExtensionKey, ...] = EXTENSION_KEYS) -> dict[str, Any]:
    """A deep copy of `schema` with each allowlisted key added as a permitted
    property of its own ``$defs`` object.

    The value schema is ``True`` (accept anything): this gate's job is the
    key's *spelling*, and every listed key's own value shape is already
    graded by the consumer named in its row -- re-deriving those shapes here
    would be a second, drift-prone copy of them. A row naming a ``$defs``
    object the schema does not have is skipped silently here and reported by
    find_allowlist_drift, so one missing anchor cannot mask every other
    finding behind a KeyError.
    """
    extended = copy.deepcopy(schema)
    defs = extended.get("$defs")
    if not isinstance(defs, dict):
        return extended
    for entry in keys:
        target = defs.get(entry.schema_def)
        if not isinstance(target, dict):
            continue
        properties = target.setdefault("properties", {})
        if isinstance(properties, dict):
            properties.setdefault(entry.key, True)
    return extended


def _validator_for(schema: dict[str, Any]) -> Any:
    """A validator for `schema` under the draft `schema` itself declares,
    with format assertion enabled. See this module's docstring for why
    _gitapex_schema_validation.build_validator (hardcoded to draft 2020-12)
    is deliberately not used for these vendored draft-07 files."""
    validator_cls = jsonschema.validators.validator_for(schema)
    return validator_cls(schema, format_checker=jsonschema.FormatChecker())


def _violations(instance: Any, validator: Any, label: str) -> list[str]:
    """One message per validation error, each locating the offending member
    by JSON pointer inside `label`."""
    findings: list[str] = []
    for error in validator.iter_errors(instance):
        location = "/".join(str(part) for part in error.path) or "<root>"
        findings.append(f"schema: {label}: {location}: {error.message}")
    return findings


# The task-file layout this gate discovers. Both YAML spellings, because
# waza's own `tasks` field takes arbitrary glob patterns and .yml is as
# legal a YAML extension as .yaml -- discovering only one of them would
# leave the other silently ungraded. Whatever a suite actually declares is
# separately reconciled against this set by find_declared_task_coverage.
_TASK_GLOBS = ("*/tasks/*.yaml", "*/tasks/*.yml")


def iter_suite_files(evals_dir: pathlib.Path = EVALS_DIR) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """Every committed (eval.yaml, tasks/*.yaml|yml) pair under `evals_dir`,
    each list sorted so findings are reported in a stable order. A suite
    directory with no eval.yaml simply contributes none -- evals/scripts/ is
    such a directory and is not a suite."""
    eval_files = sorted(evals_dir.glob("*/eval.yaml"))
    task_files = sorted({path for pattern in _TASK_GLOBS for path in evals_dir.glob(pattern)})
    return eval_files, task_files


def find_declared_task_coverage(evals_dir: pathlib.Path = EVALS_DIR) -> list[str]:
    """Reconcile what each suite *declares* against what this gate actually
    discovers, and report the difference.

    `iter_suite_files` scans a fixed layout, but waza's own eval schema lets
    `tasks` carry any glob (``cases/*.yaml``) and `tasks_from` pull task
    definitions in from another file entirely. A suite using either shape
    would run under waza while every one of its task files sat outside this
    gate's discovery -- passing not because it was clean but because nothing
    graded it. That is the same fail-open dimension 15 of
    skills/evaluating-deterministic-gate-quality/references/dimensions.md
    names, and the same one find_suite_violations' empty-corpus check
    closes for the whole-tree case; this closes it per suite.

    Reported, not silently absorbed: a declared glob resolving to a file
    outside the discovered set, a declared glob resolving to nothing at all,
    and a `tasks_from` reference (whose pulled-in tasks this gate cannot
    follow). Widening `_TASK_GLOBS`, or teaching the gate the new shape, is
    the fix in each case -- never dropping the declaration."""
    discovered = set(iter_suite_files(evals_dir)[1])
    findings: list[str] = []
    for eval_path in sorted(evals_dir.glob("*/eval.yaml")):
        suite = eval_path.parent
        label = eval_path.relative_to(evals_dir.parent).as_posix()
        document = _load_yaml_or_raise(eval_path)
        if not isinstance(document, dict):
            continue
        if document.get("tasks_from") is not None:
            findings.append(
                f"undiscovered-tasks: {label}: declares tasks_from, whose task definitions this gate does not follow"
            )
        declared = document.get("tasks")
        if not isinstance(declared, list):
            continue
        for pattern in declared:
            if not isinstance(pattern, str):
                continue
            # pathlib rejects some patterns outright -- an absolute one
            # ("/etc/*.yaml") raises NotImplementedError, an empty one
            # raises ValueError. Both are reachable: this function runs on
            # every eval.yaml, including one whose own `tasks` entries
            # find_suite_violations separately reports as schema-invalid.
            # Reported as a finding, never a traceback, per this module's
            # own read-or-report contract.
            try:
                matched = sorted(suite.glob(pattern))
            except (NotImplementedError, ValueError) as error:
                findings.append(
                    f"undiscovered-tasks: {label}: declared tasks glob {pattern!r} is not a usable "
                    f"relative pattern: {error}"
                )
                continue
            if not matched:
                findings.append(f"undiscovered-tasks: {label}: declared tasks glob {pattern!r} matches no file")
                continue
            for path in matched:
                if path not in discovered:
                    relative = path.relative_to(evals_dir.parent).as_posix()
                    findings.append(
                        f"undiscovered-tasks: {label}: declared tasks glob {pattern!r} matches {relative}, "
                        f"which this gate does not discover -- it would run under waza ungraded here"
                    )
    return findings


def find_suite_violations(
    evals_dir: pathlib.Path = EVALS_DIR,
    eval_schema_path: pathlib.Path = EVAL_SCHEMA_PATH,
    task_schema_path: pathlib.Path = TASK_SCHEMA_PATH,
) -> list[str]:
    """Validate every committed suite against the vendored schemas extended
    by EXTENSION_KEYS. One validator is built per schema and reused across
    every file, rather than rebuilt per file.

    Fail-closed on an empty match set (dimension 15 of
    skills/evaluating-deterministic-gate-quality/references/dimensions.md,
    and the same rule gitapex_gate_evals_scripts_coverage.py states in its
    own docstring): a scan that found no suites at all is a scan that
    graded nothing, and must not be reported as a clean corpus."""
    eval_files, task_files = iter_suite_files(evals_dir)
    if not eval_files:
        return [f"empty-corpus: no */eval.yaml found under {evals_dir} -- nothing was graded"]
    if not task_files:
        return [f"empty-corpus: no {' or '.join(_TASK_GLOBS)} found under {evals_dir} -- nothing was graded"]

    eval_schema = extend_schema(_gitapex_schema_validation.load_json_or_raise(eval_schema_path, SuiteReadError))
    task_schema = extend_schema(_gitapex_schema_validation.load_json_or_raise(task_schema_path, SuiteReadError))
    eval_validator = _validator_for(eval_schema)
    task_validator = _validator_for(task_schema)

    findings: list[str] = []
    for path, validator in [(p, eval_validator) for p in eval_files] + [(p, task_validator) for p in task_files]:
        label = path.relative_to(evals_dir.parent).as_posix()
        findings.extend(_violations(_load_yaml_or_raise(path), validator, label))
    return findings


def _native_properties(schema: Any, schema_def: str) -> set[str] | None:
    """The property names waza's own `$defs[schema_def]` declares, or None
    when the schema has no such `$defs` object at all."""
    defs = schema.get("$defs") if isinstance(schema, dict) else None
    target = defs.get(schema_def) if isinstance(defs, dict) else None
    if not isinstance(target, dict):
        return None
    properties = target.get("properties")
    return set(properties) if isinstance(properties, dict) else set()


def find_allowlist_drift(
    keys: tuple[ExtensionKey, ...] = EXTENSION_KEYS,
    task_schema_path: pathlib.Path = TASK_SCHEMA_PATH,
    repo_root: pathlib.Path = REPO_ROOT,
) -> list[str]:
    """Return one message per allowlist row that no longer describes reality:
    a ``$defs`` anchor the vendored schema does not have, a key upstream has
    since adopted natively (delete the row), a consumer file that does not
    exist, or a consumer that no longer mentions the key it is credited with
    reading."""
    schema = _gitapex_schema_validation.load_json_or_raise(task_schema_path, SuiteReadError)
    findings: list[str] = []
    for entry in keys:
        native = _native_properties(schema, entry.schema_def)
        if native is None:
            findings.append(f"allowlist-drift: {entry.key}: vendored task schema has no $defs/{entry.schema_def}")
        elif entry.key in native:
            findings.append(
                f"allowlist-drift: {entry.key}: waza's own $defs/{entry.schema_def} now declares this property "
                f"natively -- drop the allowlist row"
            )
        consumer = repo_root / entry.consumer
        if not consumer.is_file():
            findings.append(f"allowlist-drift: {entry.key}: consumer does not exist: {entry.consumer}")
            continue
        if entry.key not in _read_text_or_raise(consumer):
            findings.append(
                f"allowlist-drift: {entry.key}: consumer {entry.consumer} no longer mentions this key "
                f"(row claims it {entry.reads}) -- remove the allowlist row or restore the consumer"
            )
    return findings


def find_pin_drift(flake_path: pathlib.Path = FLAKE_PATH) -> list[str]:
    """Return a finding when flake.nix no longer pins VENDORED_WAZA_TAG. This
    is the check that stops a waza version bump from silently leaving the
    vendored schemas describing a binary that no longer runs."""
    text = _read_text_or_raise(flake_path)
    tags = sorted(set(_FLAKE_WAZA_TAG_RE.findall(text)))
    if not tags:
        return [f"pin-drift: {flake_path.name} pins no recognizable waza release tag"]
    if tags != [VENDORED_WAZA_TAG]:
        return [
            f"pin-drift: {flake_path.name} pins waza at {', '.join(tags)} but the vendored schemas were taken from "
            f"{VENDORED_WAZA_TAG} -- re-vendor both .gitapex/waza-*.schema.json and re-record their digests"
        ]
    return []


def find_vendor_digest_drift(
    eval_schema_path: pathlib.Path = EVAL_SCHEMA_PATH,
    task_schema_path: pathlib.Path = TASK_SCHEMA_PATH,
) -> list[str]:
    """Return one message per vendored schema whose bytes no longer hash to
    the digest recorded in VENDORED_DIGESTS."""
    expected = VENDORED_DIGESTS
    findings: list[str] = []
    for name, path in (("eval.schema.json", eval_schema_path), ("task.schema.json", task_schema_path)):
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise SuiteReadError(f"{path}: cannot be read: {error}") from error
        if actual != expected.get(name):
            findings.append(
                f"vendor-digest-drift: {path.name}: sha256 {actual} does not match the recorded "
                f"{expected.get(name)} for {name} at {VENDORED_WAZA_TAG}"
            )
    return findings


def default_opener(url: str) -> bytes:
    """Fetch `url` and return its raw body. Split out so tests exercise
    find_upstream_drift's comparison logic without real egress."""
    # S310 justification: `url` is built here from a fixed
    # raw.githubusercontent.com template plus a module-level literal tag.
    with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
        body: bytes = response.read()
    return body


def find_upstream_drift(
    eval_schema_path: pathlib.Path = EVAL_SCHEMA_PATH,
    task_schema_path: pathlib.Path = TASK_SCHEMA_PATH,
    opener: Any = default_opener,
) -> list[str]:
    """Opt-in network check (``--verify-upstream``): compare each vendored
    file byte-for-byte against what microsoft/waza published at
    VENDORED_WAZA_TAG. A fetch failure is itself a finding rather than a
    silent pass -- an unverifiable claim is not a verified one."""
    findings: list[str] = []
    for name, path in (("eval.schema.json", eval_schema_path), ("task.schema.json", task_schema_path)):
        url = _UPSTREAM_RAW.format(tag=VENDORED_WAZA_TAG, name=name)
        try:
            published = opener(url)
        # http.client.HTTPException (IncompleteRead, BadStatusLine, ...) is
        # NOT an OSError subclass, so OSError alone would let a truncated or
        # malformed response surface as a traceback instead of a finding.
        except (OSError, http.client.HTTPException) as error:
            findings.append(f"upstream-drift: {name}: cannot fetch {url}: {error}")
            continue
        try:
            local = path.read_bytes()
        except OSError as error:
            raise SuiteReadError(f"{path}: cannot be read: {error}") from error
        if local != published:
            findings.append(
                f"upstream-drift: {path.name}: vendored bytes differ from {name} published at {VENDORED_WAZA_TAG}"
            )
    return findings


def find_drift(
    evals_dir: pathlib.Path = EVALS_DIR,
    eval_schema_path: pathlib.Path = EVAL_SCHEMA_PATH,
    task_schema_path: pathlib.Path = TASK_SCHEMA_PATH,
    repo_root: pathlib.Path = REPO_ROOT,
    flake_path: pathlib.Path = FLAKE_PATH,
) -> list[str]:
    """Every offline finding, in one list. Empty means the committed corpus,
    the allowlist, and the vendored pin are all clean. The network check is
    deliberately not part of this: see the module docstring."""
    findings: list[str] = []
    findings.extend(find_pin_drift(flake_path))
    findings.extend(find_vendor_digest_drift(eval_schema_path, task_schema_path))
    findings.extend(find_allowlist_drift(EXTENSION_KEYS, task_schema_path, repo_root))
    findings.extend(find_suite_violations(evals_dir, eval_schema_path, task_schema_path))
    findings.extend(find_declared_task_coverage(evals_dir))
    return findings


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate every committed evals/ suite against waza's own vendored schemas plus this "
            "repository's reviewed extension-key allowlist, and check the vendored copies against "
            "the release tag flake.nix pins."
        )
    )
    parser.add_argument(
        "--verify-upstream",
        action="store_true",
        help=(
            "Additionally fetch both schemas from microsoft/waza at "
            f"{VENDORED_WAZA_TAG} and compare bytes. Requires network access; run this when bumping the pin."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        findings = find_drift()
        if args.verify_upstream:
            findings.extend(find_upstream_drift())
    except SuiteReadError as error:
        print("eval suite schema drift:")
        print(f"  {error}")
        return 1
    if findings:
        print("eval suite schema drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No eval suite schema drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
