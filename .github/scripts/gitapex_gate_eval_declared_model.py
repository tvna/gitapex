#!/usr/bin/env python3
"""Grade every committed model identifier against a reviewed allowlist.

ACTIVE (issue #925): registered in .gitapex/ssot.json as
eval-declared-model-allowlist. Enforced the same way its sibling
.github/scripts/gitapex_scan_eval_suite_schema.py (eval-suite-schema-drift)
is -- no dedicated CI workflow step and no pre-commit hook, only
tests/test_gitapex_gate_eval_declared_model.py's own
test_real_repository_declares_only_approved_models calling find_findings()
against the real tree with no fixture override, inside the pytest step of
.github/workflows/test.yml -- plus the working-tree invocation
.gitapex/ssot.json records under local_invocation, which
gitapex_gate_local_preflight.py discovers and runs before a push.

Why this gate exists. Issue #925 measured 23 of the 24 committed
evals/*/eval.yaml declaring ``config.model: claude-sonnet-4.6``, a model
confirmed retired on 2026-06-15. Nothing in the repository noticed. The
sibling schema gate validates each suite against waza's own vendored JSON
Schemas, but a model identifier is a plain ``string`` there: a retired,
misspelled, or never-existing id satisfies the schema exactly as well as a
dispatchable one. The failure surfaced only when somebody happened to run a
suite, and was then patched per-run inside a result artifact
(evals/untrusted-input-triage/results/2026-08-01-issue-645-behavioral-eval/
untrusted-input-triage-normal.md records the substitution) while the
declaration itself stayed broken for another five weeks.

**What this gate is, and is not.** APPROVED_MODELS records what a human last
reviewed and approved -- it does not make a declaration self-verifying.
Nothing in this repository can currently ask the copilot-sdk executor which
models it serves: .github/workflows/skill-eval-matrix.yml cannot run until the
owner provisions COPILOT_BASE_URL / COPILOT_PROVIDER_BASE_URL (see
docs/skill-eval-status.md), so no offline check can confirm an id is
dispatchable. This gate converts a silent failure into a reviewed one: an id
enters the corpus only by passing through a diff on this file, where the
evidence column has to be filled in. That is a strictly weaker claim than
"the declared model works", and it is deliberately the strongest claim an
offline gate can make. RETIRED_MODELS exists purely to turn the most likely
failure into a specific message instead of a generic "not on the allowlist".

**Declaration is not provenance (issue #925, fourth acceptance row).**
A declared model states *intent*: which model a suite asks to be run against.
It is demonstrably not a record of what ran -- the substitution cited above
is the proof. The only trustworthy source for "this skill was evaluated on
model X" is a run record, under a suite's own ``results/`` directory. No
consumer may read a declaration as evidence of an executed run, and this
module -- the one thing issue #925 adds that reads these fields at all --
reads them only to grade the declaration against the allowlist, never to
report what a skill has been evaluated on.

Three surfaces are graded, because each is a committed declaration of a model
id that a dispatch would actually use:

1. Every ``evals/*/eval.yaml``, walked recursively for any key named ``model``
   or ending in ``_model``. Issue #937 found the original revision reading
   ``config.model`` alone while claiming to grade "every committed model
   identifier": waza's own vendored schemas also define ``config.judge_model``
   and a ``model`` override on both ``graderConfig`` and
   ``promptGraderConfig``, all as plain strings. None is populated in the
   committed corpus today, which is exactly why a hardcoded field list would
   have rotted -- the walk grades whichever of them appears first, and any
   ``*_model`` key waza adds later, with no edit here.
2. Every ``evals/*/tasks/*.yaml``, walked the same way. The task schema
   carries its own two model-bearing fields (``inputs.responder.model`` and a
   ``promptGraderConfig`` ``model``), and four committed task files already
   declare ``graders``.
3. ``.github/workflows/skill-eval-matrix.yml``: its ``models`` dispatch-input
   *default* -- the value that runs when an operator dispatches the matrix
   workflow without typing a list -- and every ``*_MODEL`` environment value
   the workflow hardcodes (today, ``HF_GEMMA4_MODEL``). Its non-default
   dispatch *input* is not graded and must not be: probing an unapproved id is
   a legitimate way to discover whether it belongs on the allowlist, and this
   gate must not stand in the way of the live probe that would let the
   allowlist be updated with real evidence. A hardcoded ``env:`` value is not
   operator-supplied and gets no such exemption.

Run standalone (exit 1 on any finding) or via the pytest gate in
tests/test_gitapex_gate_eval_declared_model.py.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
MATRIX_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "skill-eval-matrix.yml"
#: Registered in .gitapex/ssot.json's policy_sources as this gate's own
#: reviewed-evidence data source (issue #1013) -- previously the two maps
#: below were hardcoded Python dict literals with no policy_sources entry
#: pointing at them at all.
MODEL_ALLOWLIST_PATH = REPO_ROOT / ".gitapex" / "eval-model-allowlist.yaml"


class DeclarationReadError(Exception):
    """A graded file could not be read or has no gradable declaration.

    Raised rather than skipped: a suite whose declaration this gate cannot
    find is a suite this gate is not actually grading, and silently passing it
    would reproduce the exact shape issue #925 reports -- a declaration nobody
    checked (CLAUDE.md section 4, fail loudly). Also raised by
    `_load_model_allowlist` below for the allowlist file itself, for the same
    reason: an allowlist that failed to load is not an allowlist this gate
    can grade against at all.
    """


class _DuplicateKeyLoader(yaml.SafeLoader):
    """`yaml.SafeLoader`, except a duplicate key in any mapping -- the
    top-level `approved_models`/`retired_models` pair or a model id inside
    either section -- raises instead of silently keeping the last value.
    PyYAML's own default behavior (confirmed against the pinned version:
    the later occurrence wins, no error) would let a duplicate model id
    silently overwrite reviewed evidence with unreviewed text elsewhere in
    the same diff, defeating the review-forcing property this file exists
    for (see this module's own docstring)."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[object, object]:
        seen: set[object] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in seen:
                    raise yaml.YAMLError(f"duplicate key {key!r} in mapping")
                seen.add(key)
            except TypeError as error:
                # A YAML sequence/mapping used as a mapping key (e.g. `? [x]`)
                # constructs to an unhashable Python object -- `key in seen`
                # then raises a bare TypeError, which is not a yaml.YAMLError
                # and would otherwise escape _load_model_allowlist's own
                # handler as a raw traceback instead of a DeclarationReadError.
                raise yaml.YAMLError(f"unhashable key in mapping: {error}") from error
        return super().construct_mapping(node, deep=deep)


def _load_model_allowlist(path: pathlib.Path) -> tuple[dict[str, str], dict[str, str]]:
    """`(approved_models, retired_models)` from `path`'s own
    `approved_models`/`retired_models` YAML mappings. Fails loudly (never a
    silently empty allowlist) on a missing/unreadable/malformed file or
    either top-level key holding anything other than a mapping of
    string -> string -- an allowlist that failed to load must not be
    mistaken for an allowlist that is genuinely empty, which would grade
    every declared model id as unapproved. Also fails loudly on a duplicate
    mapping key (`_DuplicateKeyLoader`), rather than silently keeping
    PyYAML's own last-value-wins default.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise DeclarationReadError(f"{path}: cannot be read: {error}") from error
    try:
        document = yaml.load(raw, Loader=_DuplicateKeyLoader)  # noqa: S506 -- _DuplicateKeyLoader subclasses SafeLoader
    except yaml.YAMLError as error:
        raise DeclarationReadError(f"{path}: is not valid YAML: {error}") from error
    if not isinstance(document, dict):
        raise DeclarationReadError(f"{path}: must contain a YAML mapping, found {type(document).__name__}")

    def section(key: str) -> dict[str, str]:
        value = document.get(key)
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            raise DeclarationReadError(f"{path}: '{key}' must be a mapping of model id (string) to evidence (string)")
        return value

    return section("approved_models"), section("retired_models")


# The reviewed allowlist, loaded at import time. See MODEL_ALLOWLIST_PATH's
# own header comment for the full rationale (what each map means, and why
# a row there is the review event this gate exists to force).
APPROVED_MODELS, RETIRED_MODELS = _load_model_allowlist(MODEL_ALLOWLIST_PATH)


def _describe(model: str, approved: dict[str, str], retired: dict[str, str]) -> str:
    """One rejection message for ``model``, naming its retirement if known.

    Both mappings are parameters, never read from this module's globals:
    issue #937 found an earlier revision reading the globals here while
    ``find_findings`` graded against whatever the caller passed, so an
    override changed the verdict but not the message explaining it -- the
    override path this module's own docstring documents reported against an
    allowlist that had not been used.
    """
    reason = f"a known-undispatchable model ({retired[model]})" if model in retired else "not on the reviewed allowlist"
    names = ", ".join(sorted(approved)) or "(none)"
    return (
        f"{model!r} is {reason}. Approved ids: {names}. To add one, add a row to "
        f"APPROVED_MODELS in {pathlib.Path(__file__).name} with the evidence that justifies it."
    )


def find_allowlist_integrity_violations(
    approved: dict[str, str] | None = None,
    retired: dict[str, str] | None = None,
) -> list[str]:
    """Findings about the allowlist itself, before it grades anything.

    An id in both mappings would let a known-retired model pass, which is the
    one outcome this gate exists to prevent. A blank justification is checked
    on *both* mappings, not only APPROVED_MODELS: an approved row with no
    evidence would let a future id be added without the review this gate's
    whole value rests on, and a retired row with no reason renders as
    ``is a known-undispatchable model ().``, defeating the registry rule's own
    "rejected with that reason named" (issue #937).
    """
    approved = APPROVED_MODELS if approved is None else approved
    retired = RETIRED_MODELS if retired is None else retired
    findings: list[str] = []
    for model in sorted(set(approved) & set(retired)):
        findings.append(f"allowlist integrity: {model!r} is listed in both APPROVED_MODELS and RETIRED_MODELS")
    for label, mapping in (("APPROVED_MODELS", approved), ("RETIRED_MODELS", retired)):
        for model, justification in sorted(mapping.items()):
            if not justification.strip():
                findings.append(f"allowlist integrity: {label}[{model!r}] carries no evidence")
    return findings


def _is_model_key(key: object) -> bool:
    """Whether ``key`` names a model identifier in waza's own vocabulary.

    ``model`` exactly, or any ``*_model`` suffix. Deliberately a shape rule
    rather than a hardcoded field list: waza's vendored schemas define four
    such fields today (``config.model``, ``config.judge_model``, and a
    ``model`` override on each of ``graderConfig`` and ``promptGraderConfig``),
    none of which the committed corpus populates yet -- so a hardcoded list
    would have been correct on the day it was written and silently incomplete
    the day waza added the fifth (issue #937).
    """
    return isinstance(key, str) and (key == "model" or key.endswith("_model"))


def _walk_model_declarations(node: object, path: str = "") -> list[tuple[str, object]]:
    """Every ``(dotted-path, value)`` under ``node`` at a model-named key.

    Returns values unvalidated -- the caller decides what a non-string means,
    because "there is no model here at all" and "the model here is an integer"
    are different findings.
    """
    found: list[tuple[str, object]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            if _is_model_key(key):
                found.append((child, value))
            found.extend(_walk_model_declarations(value, child))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_walk_model_declarations(value, f"{path}[{index}]"))
    return found


def find_suite_violations(
    evals_dir: pathlib.Path | None = None,
    approved: dict[str, str] | None = None,
    retired: dict[str, str] | None = None,
) -> list[str]:
    """Findings for every model-named key in every committed suite and task.

    Both ``evals/*/eval.yaml`` and ``evals/*/tasks/*.yaml`` are walked
    recursively (issue #937) -- the task schema carries its own model-bearing
    fields, and four committed task files already declare ``graders``.

    Discovering zero suites raises rather than returning no findings. A
    renamed directory, a moved ``evals/`` tree, or a glob that stops matching
    would otherwise make this gate report a clean tree while grading nothing
    -- the fail-open shape ``gitapex_gate_evals_scripts_coverage.py``'s own
    docstring rule already names ("an empty match set is an error, never a
    silent pass") and that PR #651 shipped three times over.

    A task file declaring no model at all is not an error: only ``eval.yaml``
    is required to pin one, and the task schema's model fields are optional
    overrides.
    """
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    approved = APPROVED_MODELS if approved is None else approved
    retired = RETIRED_MODELS if retired is None else retired
    eval_paths = sorted(evals_dir.glob("*/eval.yaml"))
    if not eval_paths:
        raise DeclarationReadError(
            f"{evals_dir}: no */eval.yaml found, so this gate would grade nothing -- "
            "an empty match set is an error, never a silent pass"
        )
    findings: list[str] = []
    for eval_path in eval_paths:
        findings.extend(_grade_document(eval_path, approved, retired, require_config_model=True))
        for task_path in sorted((eval_path.parent / "tasks").glob("*.yaml")):
            findings.extend(_grade_document(task_path, approved, retired, require_config_model=False))
    return findings


def _grade_document(
    path: pathlib.Path,
    approved: dict[str, str],
    retired: dict[str, str],
    *,
    require_config_model: bool,
) -> list[str]:
    """Findings for one committed YAML document's model-named keys."""
    rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise DeclarationReadError(f"{rel}: cannot be read as UTF-8 YAML ({error})") from error
    if not isinstance(document, dict):
        raise DeclarationReadError(f"{rel}: top level is {type(document).__name__}, expected a mapping")
    if require_config_model:
        config = document.get("config")
        if not isinstance(config, dict):
            raise DeclarationReadError(f"{rel}: has no 'config' mapping, so its declared model cannot be graded")
        if "model" not in config:
            raise DeclarationReadError(f"{rel}: 'config' declares no 'model', so nothing here can be graded")
    findings: list[str] = []
    for field, value in _walk_model_declarations(document):
        if not isinstance(value, str):
            raise DeclarationReadError(f"{rel}: {field} is {type(value).__name__}, expected a string")
        if value not in approved:
            findings.append(f"{rel}: {field} {_describe(value, approved, retired)}")
    return findings


def _matrix_default_models(workflow_path: pathlib.Path) -> list[str]:
    """The ``models`` dispatch input's default, parsed as the JSON array the
    workflow's own ``fromJSON(github.event.inputs.models)`` will parse it as.

    YAML 1.1 resolves a bare ``on:`` key to the boolean ``True``, which is why
    both spellings are looked up rather than only the readable one.
    """
    try:
        document = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise DeclarationReadError(f"{workflow_path.name}: cannot be read as UTF-8 YAML ({error})") from error
    if not isinstance(document, dict):
        raise DeclarationReadError(f"{workflow_path.name}: top level is not a mapping")
    triggers = document.get("on", document.get(True))
    # Each level is checked for being a mapping before it is indexed. Issue
    # #937: an earlier revision guarded `triggers` only, so a workflow
    # declaring `workflow_dispatch:` with no children parsed that key to None
    # and `.get("inputs", {})` raised an AttributeError -- which is not a
    # DeclarationReadError, so it escaped main()'s handler and surfaced as a
    # raw traceback from a gate whose whole contract is a typed, fail-loud
    # message.
    dispatch = triggers.get("workflow_dispatch") if isinstance(triggers, dict) else None
    inputs = dispatch.get("inputs") if isinstance(dispatch, dict) else None
    if not isinstance(inputs, dict) or "models" not in inputs:
        raise DeclarationReadError(f"{workflow_path.name}: has no workflow_dispatch input named 'models'")
    default = inputs["models"].get("default") if isinstance(inputs["models"], dict) else None
    if not isinstance(default, str):
        raise DeclarationReadError(f"{workflow_path.name}: the 'models' input declares no string default")
    try:
        parsed = json.loads(default)
    except json.JSONDecodeError as error:
        raise DeclarationReadError(
            f"{workflow_path.name}: the 'models' default {default!r} is not the JSON array fromJSON() will parse ({error})"
        ) from error
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise DeclarationReadError(
            f"{workflow_path.name}: the 'models' default {default!r} is not a JSON array of strings"
        )
    return parsed


def _hardcoded_env_models(workflow_path: pathlib.Path) -> list[tuple[str, str]]:
    """Every ``(NAME, value)`` the workflow hardcodes at a ``*_MODEL`` env key.

    Walks the parsed workflow for any ``env:`` mapping at any depth (workflow,
    job, or step level) and returns its string-valued ``*_MODEL`` entries. A
    value containing ``${{`` is skipped: that is an expression resolved at
    dispatch time from an input or secret, which is operator-supplied and
    carries the same live-probe exemption the ``models`` input does.

    A ``*_MODEL`` key whose value is not a string at all raises instead of
    being skipped. Skipping it would have been the same silent-drop shape the
    suite-side walk already refuses for exactly this input (``_grade_document``
    raises on a non-string model), so the two halves of this gate would have
    disagreed about what a malformed committed declaration means -- caught in
    review on PR #938 and confirmed live: ``HF_X_MODEL: null`` and
    ``HF_X_MODEL: 123`` both returned no finding at all.
    """
    try:
        document = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise DeclarationReadError(f"{workflow_path.name}: cannot be read as UTF-8 YAML ({error})") from error

    found: list[tuple[str, str]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            environment = node.get("env")
            if isinstance(environment, dict):
                for name, value in environment.items():
                    if not (isinstance(name, str) and name.endswith("_MODEL")):
                        continue
                    if not isinstance(value, str):
                        raise DeclarationReadError(
                            f"{workflow_path.name}: hardcoded env {name} is {type(value).__name__}, expected a string"
                        )
                    if "${{" not in value:
                        found.append((name, value))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(document)
    return found


def find_matrix_default_violations(
    workflow_path: pathlib.Path | None = None,
    approved: dict[str, str] | None = None,
    retired: dict[str, str] | None = None,
) -> list[str]:
    """Findings for the matrix workflow's own committed model identifiers.

    Two of them: the ``models`` dispatch-input *default*, and every hardcoded
    ``*_MODEL`` env value (issue #937). An operator-supplied dispatch input is
    deliberately not graded -- see this module's docstring for why.
    """
    workflow_path = MATRIX_WORKFLOW_PATH if workflow_path is None else workflow_path
    approved = APPROVED_MODELS if approved is None else approved
    retired = RETIRED_MODELS if retired is None else retired
    rel = workflow_path.relative_to(REPO_ROOT) if workflow_path.is_relative_to(REPO_ROOT) else workflow_path
    findings = [
        f"{rel}: the 'models' dispatch-input default names {_describe(model, approved, retired)}"
        for model in _matrix_default_models(workflow_path)
        if model not in approved
    ]
    findings.extend(
        f"{rel}: hardcoded env {name} names {_describe(value, approved, retired)}"
        for name, value in _hardcoded_env_models(workflow_path)
        if value not in approved
    )
    return findings


def find_findings(
    evals_dir: pathlib.Path | None = None,
    workflow_path: pathlib.Path | None = None,
    approved: dict[str, str] | None = None,
    retired: dict[str, str] | None = None,
) -> list[str]:
    """Every finding, in one list. Empty means every committed model id in the
    tree is one a human has reviewed and recorded evidence for.

    Every parameter defaults to ``None`` and is resolved against this module's
    globals at *call* time, not bound at definition time, so a caller that
    replaces ``APPROVED_MODELS`` -- a test, or a future consumer importing this
    module -- actually changes what gets graded instead of silently grading the
    original mapping. Both mappings are threaded all the way down to the
    rejection message too, not only to the verdict (issue #937).
    """
    findings = find_allowlist_integrity_violations(approved, retired)
    findings.extend(find_suite_violations(evals_dir, approved, retired))
    findings.extend(find_matrix_default_violations(workflow_path, approved, retired))
    return findings


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    return argparse.ArgumentParser(
        description=(
            "Fail when a committed eval suite or task file, or the cross-model matrix "
            "workflow's default dispatch input or a hardcoded env model, declares a model "
            "identifier outside this repository's reviewed allowlist. Grades declarations "
            "only; a skill's evaluated-on provenance comes from a run record under that "
            "suite's own results/ directory, never from a declared model field."
        )
    ).parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _parse_args(argv)
    try:
        findings = find_findings()
    except DeclarationReadError as error:
        print("declared model allowlist:")
        print(f"  {error}")
        return 1
    if findings:
        print("declared model allowlist:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No unapproved declared model identifiers found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
