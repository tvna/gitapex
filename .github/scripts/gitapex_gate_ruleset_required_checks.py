#!/usr/bin/env python3
"""CI gate: the committed `main` ruleset is well-formed and every required
status check it names can actually run on every pull request.

Issue #439. The failure mode this exists to prevent is specific and permanent:
GitHub distinguishes a job that runs and reports `skipped` (which does not block
a required status check) from a workflow that never fires at all for a given
pull request, which leaves the required check `Pending` forever. A `paths:`
trigger filter is the second case. So naming a path-filtered gate's job as a
required status check does not harden `main` -- it deadlocks every pull request
that happens not to touch the matched paths, with no in-repository fix and no
error message pointing at the cause. Recovering means an admin editing the live
ruleset, which is exactly the manual, unreviewable path the committed
source-of-truth design exists to avoid.

`.github/workflows/lint.yml` and `.github/workflows/eval-gate.yml` both
already carry that reasoning in their own headers, as the stated justification
for deliberately having no `paths:` filter. This gate turns that prose into a
check, so a future edit that adds a `paths:` filter to one of those workflows --
or that adds a path-filtered gate's job to the required list -- fails here
instead of on the first pull request unlucky enough to trip it.

Everything checked here is a working-tree property. No API call, no credential:
what GitHub *currently enforces* is the separate concern of
`gitapex_scan_ruleset_drift.py`.
"""

from __future__ import annotations

import argparse
import fnmatch
import pathlib
import sys
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _gitapex_rulesets import PROJECTION_KEYS  # sys.path bootstrap above must run first
from _gitapex_schema_validation import load_json_or_raise  # same bootstrap

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_RULESET = REPO_ROOT / ".github" / "rulesets" / "main.json"
DEFAULT_WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

#: Rules whose absence would leave `main` deletable or rewritable even with a
#: pull request requirement in place.
REQUIRED_RULE_TYPES = ("deletion", "non_fast_forward", "pull_request", "required_status_checks")

#: GitHub's own placeholder ref for "whatever the default branch is called".
#: Pinning the literal name instead would silently stop protecting anything if
#: the default branch were ever renamed. (Named `..._REF`, not `..._TOKEN`:
#: ruff's S105 reads a `TOKEN` suffix as a hardcoded credential.)
DEFAULT_BRANCH_REF = "~DEFAULT_BRANCH"

#: `pull_request` parameters this repository states as required, in
#: `.gitapex/ssot.json` and `docs/runbooks/rulesets.md`. Each must be exactly
#: `true`; a rule carrying them as false passes a presence check while allowing
#: what the rule exists to prevent.
REQUIRED_PULL_REQUEST_FLAGS = (
    "require_code_owner_review",
    "required_review_thread_resolution",
    "dismiss_stale_reviews_on_push",
)

#: At least one of these must remain allowed. `rebase` replays branch commits
#: onto main without producing a merge commit, so a ruleset allowing only
#: rebase leaves no path that carries the pull request's own review with it.
_MERGE_METHODS_PRODUCING_A_REVIEWED_COMMIT = frozenset({"merge", "squash"})


class RulesetGateError(RuntimeError):
    """Raised when the ruleset file or the workflow directory cannot be read."""


# --------------------------------------------------------------------------
# Schema layer: what a committed ruleset file is allowed to *look like*.
#
# These models describe `.github/rulesets/*.json` only -- a document this
# repository authors, whose full key set is knowable, so `extra="forbid"` is
# both safe and the entire point. They must never be pointed at a live API
# response: GitHub stamps `id`, `created_at`, `_links`, per-check
# `integration_id` and its own rule-parameter defaults onto everything it
# returns, so a strict model would reject every real response. The live side
# stays a subset comparison in `_gitapex_rulesets.py`, and keeping the strict
# models in this file rather than the shared one is what keeps that boundary
# visible.
#
# The measured reason this layer exists: with only the hand-rolled key-set and
# flag checks, a committed ruleset carrying `require_code_owner_reviews` (the
# plural typo GitHub silently ignores), `required_approving_review_count:
# "zero"` (which the API rejects with a 422 at apply time, discovered only
# after a dispatch), an invented parameter, and a rule with an unknown `type`
# all passed together with exit 0 and "shape is valid". Every one of those is a
# ValidationError now.
# --------------------------------------------------------------------------


class RefNameCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include: list[str]
    exclude: list[str]


class RulesetConditions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_name: RefNameCondition


class DeletionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["deletion"]


class NonFastForwardRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["non_fast_forward"]


class PullRequestParameters(BaseModel):
    """Every field GitHub's `pull_request` rule accepts, all required here.

    Required rather than defaulted on purpose: these are security-relevant
    settings, and a file that omits one is silently accepting whatever GitHub's
    default happens to be today. Making them explicit means the committed file
    states the whole policy, and a future API default change cannot quietly
    move this repository's protection.
    """

    model_config = ConfigDict(extra="forbid")

    required_approving_review_count: int = Field(ge=0)
    dismiss_stale_reviews_on_push: bool
    require_code_owner_review: bool
    require_last_push_approval: bool
    required_review_thread_resolution: bool
    allowed_merge_methods: list[Literal["merge", "squash", "rebase"]] = Field(min_length=1)


class PullRequestRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["pull_request"]
    parameters: PullRequestParameters


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: str = Field(min_length=1)
    #: GitHub's own optional pin of which app must report the context. Not set
    #: by this repository, but modelled so adding it later is a one-line change
    #: rather than a validation failure.
    integration_id: int | None = None


class RequiredStatusChecksParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict_required_status_checks_policy: bool
    required_status_checks: list[StatusCheck]


class RequiredStatusChecksRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["required_status_checks"]
    parameters: RequiredStatusChecksParameters


#: Discriminated on `type`, so an unknown rule type is a validation error naming
#: the offending value rather than a silently-ignored entry. Extending this
#: union is the deliberate cost of adopting a new rule type: the same change
#: must then also update `.gitapex/ssot.json` and the runbook, which is the
#: coupling that keeps those two documents true.
CommittedRule = Annotated[
    DeletionRule | NonFastForwardRule | PullRequestRule | RequiredStatusChecksRule,
    Field(discriminator="type"),
]


class CommittedRuleset(BaseModel):
    """Exactly the key set GitHub's ruleset POST/PUT request body accepts.

    `enforcement` and `target` admit GitHub's full enums rather than pinning the
    values this repository uses: `evaluate` and `disabled` are the documented
    rollback lever in `docs/runbooks/rulesets.md`, so a file setting one must
    stay *valid* and be reported by the policy layer instead. Schema says what
    is expressible; policy says what this repository has chosen.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    target: Literal["branch", "tag", "push"]
    enforcement: Literal["active", "evaluate", "disabled"]
    conditions: RulesetConditions
    bypass_actors: list[dict[str, Any]]
    rules: list[CommittedRule]


#: `CommittedRuleset`'s own field set must never silently drift from
#: `_gitapex_rulesets.PROJECTION_KEYS` -- the six keys GitHub's ruleset
#: POST/PUT body accepts, and the same set `canonical_projection` narrows
#: every live/committed comparison to. An explicit RuntimeError, not a bare
#: `assert`, over dynamic model generation: Pydantic's own per-field
#: validation and error messages stay clearer with explicit fields than a
#: generated class would give up, and unlike `assert`, a `RuntimeError`
#: still fires when the interpreter runs under `python -O`/`PYTHONOPTIMIZE`,
#: which strips every plain `assert` statement at compile time.
if set(CommittedRuleset.model_fields) != set(PROJECTION_KEYS):
    raise RuntimeError(
        f"CommittedRuleset's fields {sorted(CommittedRuleset.model_fields)} have drifted from "
        f"_gitapex_rulesets.PROJECTION_KEYS {sorted(PROJECTION_KEYS)} -- update both together"
    )


def find_schema_violations(ruleset: dict[str, Any]) -> list[str]:
    """Validation errors against `CommittedRuleset`, one finding per error.

    Rendered by dotted location rather than re-raising, so a file with three
    problems reports all three in one run instead of one per fix-and-re-run
    cycle.
    """
    try:
        CommittedRuleset.model_validate(ruleset)
    except ValidationError as error:
        return [f"{'.'.join(str(part) for part in item['loc']) or '<root>'}: {item['msg']}" for item in error.errors()]
    return []


def load_json(path: pathlib.Path) -> dict[str, Any]:
    document = load_json_or_raise(path, RulesetGateError)
    if not isinstance(document, dict):
        raise RulesetGateError(f"{path} must contain a JSON object, found {type(document).__name__}")
    return document


def rule_of_type(ruleset: dict[str, Any], rule_type: str) -> dict[str, Any] | None:
    for rule in ruleset.get("rules") or []:
        if isinstance(rule, dict) and rule.get("type") == rule_type:
            return rule
    return None


def find_shape_violations(ruleset: dict[str, Any]) -> list[str]:
    """Findings about the committed ruleset itself: schema first, then policy.

    Schema errors short-circuit. A document that failed validation has an
    unknown shape, so every policy check below it would be reading fields that
    may not be the type it assumes -- and the operator would get one real error
    buried in a pile of consequences of it.
    """
    schema_findings = find_schema_violations(ruleset)
    if schema_findings:
        return schema_findings
    findings: list[str] = []
    if ruleset.get("enforcement") != "active":
        findings.append(f"enforcement is {ruleset.get('enforcement')!r}, not 'active' -- it would not block anything")
    if ruleset.get("bypass_actors"):
        # A bypass actor can silently un-enforce every other rule here, so
        # re-populating it must be a deliberate edit that also updates this
        # gate and docs/runbooks/rulesets.md, never a quiet one-line addition.
        findings.append("grants bypass actors; every rule below is optional for them (see docs/runbooks/rulesets.md)")
    findings.extend(
        f"has no {rule_type!r} rule" for rule_type in REQUIRED_RULE_TYPES if rule_of_type(ruleset, rule_type) is None
    )
    findings.extend(_find_condition_violations(ruleset))
    findings.extend(_find_pull_request_violations(ruleset))
    return findings


def _find_condition_violations(ruleset: dict[str, Any]) -> list[str]:
    """The ruleset must actually point at the default branch.

    Rule *presence* says nothing about what the rules apply to: a ruleset whose
    `conditions.ref_name.include` names a branch that does not exist carries
    every rule below and protects nothing, while this gate, the pull-request
    sync gate and the daily drift scan all stay green. `.gitapex/ssot.json`
    already claims this gate enforces `target ~DEFAULT_BRANCH`; until this
    check existed, that claim was false.

    Runs only after `find_schema_violations` passed, so `conditions.ref_name`
    is known to be an object with two string lists; what is left is purely the
    policy question of which ref those lists name.
    """
    if ruleset["target"] != "branch":
        return [f"target is {ruleset['target']!r}, not 'branch'"]
    ref_name = ruleset["conditions"]["ref_name"]
    if DEFAULT_BRANCH_REF not in ref_name["include"]:
        return [
            f"conditions.ref_name.include is {ref_name['include']!r}; it must contain {DEFAULT_BRANCH_REF!r} "
            "or the ruleset protects some other ref and every rule below is decorative"
        ]
    if DEFAULT_BRANCH_REF in ref_name["exclude"]:
        return [f"conditions.ref_name.exclude also contains {DEFAULT_BRANCH_REF!r}, cancelling the include"]
    return []


def _find_pull_request_violations(ruleset: dict[str, Any]) -> list[str]:
    """The pull-request rule must carry the review settings this repository claims.

    A `pull_request` rule with review requirements switched off still satisfies
    a presence check while allowing exactly what the rule exists to prevent.
    Each flag below is named in `.gitapex/ssot.json`'s own entry for this gate
    and in `docs/runbooks/rulesets.md`; checking them here is what makes those
    two documents true rather than aspirational.

    Runs only after `find_schema_violations` passed, so if the rule is present
    its `parameters` is known to carry all six fields at their declared types.
    What is left is the policy question of which *values* this repository
    accepts -- a schema can say "boolean", never "true".
    """
    rule = rule_of_type(ruleset, "pull_request")
    if rule is None:
        return []  # already reported as a missing rule
    parameters = rule["parameters"]
    findings = [
        f"pull_request.{flag} is {parameters[flag]!r}, not true"
        for flag in REQUIRED_PULL_REQUEST_FLAGS
        if parameters[flag] is not True
    ]
    methods = parameters["allowed_merge_methods"]
    if not set(methods) & _MERGE_METHODS_PRODUCING_A_REVIEWED_COMMIT:
        findings.append(
            f"pull_request.allowed_merge_methods is {methods!r}; none of "
            f"{sorted(_MERGE_METHODS_PRODUCING_A_REVIEWED_COMMIT)} is allowed, so no reviewed merge path remains"
        )
    return findings


def required_contexts(ruleset: dict[str, Any]) -> list[str]:
    rule = rule_of_type(ruleset, "required_status_checks")
    if rule is None:
        return []
    parameters = rule.get("parameters")
    if not isinstance(parameters, dict):
        return []
    entries = parameters.get("required_status_checks") or []
    return [entry["context"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("context"), str)]


#: `pull_request` activity types GitHub fires by default. A workflow that names
#: `types:` explicitly replaces this set rather than adding to it, so one that
#: omits `opened` never starts for a newly-opened pull request and one that
#: omits `synchronize` never re-runs when the branch is pushed to -- either way
#: the required check sits `Pending` and blocks the merge.
_REQUIRED_ACTIVITY_TYPES = frozenset({"opened", "synchronize"})


# `dict[Any, Any]`, not `dict[str, Any]`: PyYAML resolves the bare token `on`
# to the boolean True under YAML 1.1, so a parsed workflow genuinely has a
# non-string key and a str-keyed annotation would be a lie mypy rejects.
def _pull_request_filters(document: dict[Any, Any]) -> dict[str, Any] | None:
    """The `pull_request` trigger's own filter mapping, or `None` if absent.

    `on:` accepts three shapes and all three appear in real workflows:
    `on: pull_request` (scalar), `on: [push, pull_request]` (sequence), and
    `on: {pull_request: {...}}` (mapping). Only the third carries filters; the
    first two are unfiltered by construction and yield an empty mapping. An
    earlier revision of this function recognised the mapping form alone, which
    made every scalar/sequence workflow invisible to the gate and would have
    reported a perfectly reachable required check as naming no job.

    `on:` itself is read from the boolean key `True` first: PyYAML resolves the
    bare token `on` to a boolean under YAML 1.1, so the literal string key is
    only the fallback.
    """
    triggers = document.get(True, document.get("on"))
    if isinstance(triggers, str):
        return {} if triggers == "pull_request" else None
    if isinstance(triggers, list):
        return {} if "pull_request" in triggers else None
    if not isinstance(triggers, dict) or "pull_request" not in triggers:
        return None
    filters = triggers["pull_request"]
    return filters if isinstance(filters, dict) else {}


def _as_list(value: Any) -> list[Any] | None:
    """Normalise a YAML filter value that may be scalar or a sequence.

    `branches: main` and `branches: [main]` mean the same thing to GitHub, and
    so do `types: opened` and `types: [opened]`. An earlier revision tested
    `isinstance(value, list)` and fell straight through on the scalar spelling
    -- fail-open in both cases: a workflow scoped away from the default branch,
    or listening for a single activity type, was reported as backing a required
    check that would in fact sit `Pending` forever.

    `None` means "no filter given", which is different from an empty list.
    """
    if value is None:
        return None
    return value if isinstance(value, list) else [value]


def _branch_filter_admits(filters: dict[str, Any], default_branch: str) -> bool:
    """Whether the trigger still fires for a pull request targeting `default_branch`.

    `pull_request`'s `branches`/`branches-ignore` filter the *base* branch, so a
    workflow scoped to `branches: [release]` never runs for a pull request into
    `main` -- and a required check backed by it stays `Pending` forever. This is
    the fail-open half of the same class as the `paths:` check: the gate used to
    look only at path filters and would have passed such a workflow.

    Glob semantics are GitHub's own (`fnmatch`, plus a leading `!` negation in
    `branches`). Deliberately not a full reimplementation of GitHub's filter
    grammar: `**` and `+` are treated as ordinary `fnmatch` patterns, which is
    conservative in the direction that matters -- a pattern this function fails
    to recognise as matching is reported as a finding for a human to read, not
    silently accepted.
    """
    ignore = _as_list(filters.get("branches-ignore"))
    if ignore is not None and any(fnmatch.fnmatch(default_branch, str(p)) for p in ignore):
        return False
    include = _as_list(filters.get("branches"))
    if include is None:
        return True
    admitted = False
    for raw in include:
        pattern = str(raw)
        if pattern.startswith("!"):
            if fnmatch.fnmatch(default_branch, pattern[1:]):
                return False
        elif fnmatch.fnmatch(default_branch, pattern):
            admitted = True
    return admitted


def unconditional_pull_request_jobs(workflow_dir: pathlib.Path, default_branch: str = "main") -> dict[str, str]:
    """Check-run names produced on *every* pull request, mapped to their workflow file.

    A workflow qualifies only when all four hold:

    * it has a `pull_request` trigger at all (any of the three `on:` shapes);
    * it carries neither `paths` nor `paths-ignore`;
    * its branch filter, if any, still admits `default_branch`;
    * its `types:`, if named explicitly, includes both `opened` and
      `synchronize`.

    Each is the same failure wearing a different hat: a workflow that does not
    fire leaves its required check `Pending`, which blocks the merge with no
    in-repository fix.

    The check-run name is the job's own `name:` when it sets one and its job id
    otherwise. That is the string GitHub matches a required status check
    against, confirmed by reading the real check runs on a merged pull request
    in this repository rather than inferred from the field names.
    """
    jobs: dict[str, str] = {}
    paths = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))
    if not paths:
        raise RulesetGateError(f"no workflow files found under {workflow_dir}; refusing to report a vacuous pass")
    for path in paths:
        # A workflow this gate cannot read or parse is a hard stop, never a
        # silent skip: skipping would drop its jobs from `jobs` below, and the
        # only visible consequence would be this gate reporting that a
        # perfectly valid required check "names no job" -- a confusing false
        # failure pointing at the ruleset instead of at the unreadable file.
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            raise RulesetGateError(f"cannot read {path}: {error}") from error
        except yaml.YAMLError as error:
            raise RulesetGateError(f"{path} is not valid YAML: {error}") from error
        if not isinstance(document, dict):
            continue
        filters = _pull_request_filters(document)
        if filters is None or "paths" in filters or "paths-ignore" in filters:
            continue
        if not _branch_filter_admits(filters, default_branch):
            continue
        types = _as_list(filters.get("types"))
        if types is not None and not _REQUIRED_ACTIVITY_TYPES.issubset({str(entry) for entry in types}):
            continue
        # `or {}` covered a missing or null `jobs:` but not a present one that
        # is not a mapping (`jobs: 'text'`, `jobs: [a, b]`). That raised
        # AttributeError straight past `main`'s `except RulesetGateError`,
        # giving a raw traceback on the local pre-push run instead of this
        # gate's own exit-2 path -- for a file actionlint would reject anyway.
        # Skipping is fail-closed here: dropping a workflow's jobs can only make
        # a required context look unreachable, which is a finding, never a pass.
        workflow_jobs = document.get("jobs")
        if not isinstance(workflow_jobs, dict):
            continue
        for job_id, job in workflow_jobs.items():
            name = _check_run_name(job_id, job)
            if name is not None:
                jobs[name] = path.name
    return jobs


def _check_run_name(job_id: str, job: Any) -> str | None:
    """The single check-run name this job produces, or `None` if it produces no
    predictable single name.

    Two job shapes do not yield `job_id` as their check-run name, and both were
    silently accepted before:

    * **A matrix job** produces one check run *per combination*, named
      `job_id (value, value)`. Nothing is ever reported under the bare
      `job_id`, so requiring that name leaves the check `Pending` forever --
      the exact deadlock this gate exists to prevent, reachable today by adding
      a `strategy.matrix` to `test.yml`'s `pytest` job while this gate stayed
      green.
    * **A reusable-workflow call** (`uses:` at job level) reports its inner
      jobs as `job_id / inner_job_id`, again never as the bare `job_id`.

    Returning `None` excludes the job from the available set, so naming it as a
    required context becomes a finding a human reads rather than a merge that
    can never complete. Deliberately conservative: expanding the matrix into its
    real check-run names would mean reimplementing GitHub's own combination and
    `include`/`exclude` semantics, and getting that subtly wrong would fail open
    again.
    """
    if not isinstance(job, dict):
        return job_id
    if job.get("uses"):
        return None
    strategy = job.get("strategy")
    if isinstance(strategy, dict) and strategy.get("matrix"):
        return None
    name = job.get("name")
    return str(name) if name else job_id


def find_unreachable_contexts(
    ruleset: dict[str, Any], workflow_dir: pathlib.Path, default_branch: str = "main"
) -> list[str]:
    contexts = required_contexts(ruleset)
    if not contexts:
        return ["requires no status checks at all; a pull request rule with nothing to check blocks nothing"]
    available = unconditional_pull_request_jobs(workflow_dir, default_branch)
    return [
        f"required status check {context!r} names no job in any workflow that runs on every pull request; "
        "a path-filtered or absent workflow leaves that check Pending forever and blocks the merge"
        for context in contexts
        if context not in available
    ]


def find_violations(ruleset_path: pathlib.Path, workflow_dir: pathlib.Path, default_branch: str = "main") -> list[str]:
    ruleset = load_json(ruleset_path)
    return find_shape_violations(ruleset) + find_unreachable_contexts(ruleset, workflow_dir, default_branch)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ruleset", default=str(DEFAULT_RULESET), help="path to the committed ruleset JSON")
    parser.add_argument("--workflow-dir", default=str(DEFAULT_WORKFLOW_DIR), help="directory of workflow files")
    parser.add_argument(
        "--default-branch",
        default="main",
        help="branch the ruleset protects; a workflow whose branch filter excludes it cannot back a required check",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        violations = find_violations(pathlib.Path(args.ruleset), pathlib.Path(args.workflow_dir), args.default_branch)
    except RulesetGateError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 2
    if violations:
        print(f"{args.ruleset} has {len(violations)} finding(s):", file=sys.stderr)
        for violation in violations:
            print(f"::error::{args.ruleset} {violation}", file=sys.stderr)
        return 1
    print(f"{args.ruleset}: shape is valid and every required status check runs on every pull request.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
