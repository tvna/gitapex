#!/usr/bin/env python3
"""Guard the self-referential gate registry invariant.

``.gitapex/ssot.json`` (issue #123) is gitapex's own registry of its real,
currently-enforced deterministic gates -- "references and routing only,
never policy values," mirroring the upstream ``tvna/claude-md`` precedent's
own stated constraint. Left unguarded, the registry drifts from the files it
claims to describe: a gate's script gets renamed or deleted, or a
``policy_refs``/``cluster`` entry points at something that no longer exists,
and the registry silently goes stale.

This scanner is the drift gate shipped alongside that registry. It fails if:

- ``.gitapex/ssot.json`` does not validate against ``.gitapex/ssot.schema.json``;
- any ``gates[].script`` path (``kind: "script"``) does not exist as a real
  file in the repository;
- any ``gates[].policy_refs[]`` value does not resolve to a real
  ``policy_sources[].id``;
- any ``gates[].cluster`` value does not name a real top-level ``clusters``
  key; or
- any ``gates[].id`` or ``policy_sources[].id`` is used more than once (an
  unnoticed duplicate would silently make one entry invisible to every
  cross-reference this scanner performs); or
- any ``gates[].local_invocation``/``local_stdin`` argv token that is
  unambiguously a repository path does not exist as a real file, or escapes
  the repository root (issue #876 -- see ``find_local_invocation_drift``);
- any such argv re-introduces a shell or hands inline code to an
  interpreter, which would make this registry a carrier of arbitrary
  commands rather than of references (``find_local_shell_argv``); or
- a local-plane gate's ``local_invocation`` names none of that gate's own
  ``script`` paths, so the preflight would report PASS for a gate that
  never ran (``find_local_invocation_identity_drift``).

Validation is layered. ``jsonschema.Draft202012Validator`` first checks the
raw instance against ``.gitapex/ssot.schema.json`` and reports every
violation with a JSON-pointer-shaped location -- the general schema-invalid
case, with a good error message. The reference-drift checks
(``find_script_drift``/``find_policy_ref_drift``/``find_cluster_drift``)
then run against a ``SsotRegistry`` pydantic model parsed from that same
instance, which gives them typed ``Gate``/``PolicySource`` objects to work
with instead of hand-rolled ``dict.get``/``isinstance`` re-derivation. A
schema-invalid instance (a missing required field, or an explicit JSON
``null`` in place of an array -- a schema-invalid but not-impossible shape
for a hand-edited file) may also fail this pydantic parse; when it does,
``_parse_registry`` returns ``None`` rather than raising, and the three
reference-drift checks below simply have nothing typed to check, deferring
to ``find_schema_violations`` to report the real problem instead of
crashing with an unhandled exception.

``find_duplicate_ids`` still walks the raw instance dict directly, not
through the pydantic model, since a duplicate id can occur in an otherwise
schema-valid and pydantic-valid instance (neither the schema nor these
models express a cross-item uniqueness constraint) -- every list/dict
lookup it performs defaults on an absent key, an explicit JSON ``null``,
and a non-dict ``gates``/``policy_sources`` entry (e.g. a bare int or
string), for the same reason as before: a schema-invalid entry is
``find_schema_violations``'s finding to report, not a reason for this
function to raise past it.

It does not check the converse -- a real gate script with no registry entry
at all (under-registration, a "shadow gate") is a known, accepted gap; see
the PR that introduced this scanner for why that was left as a follow-up
rather than folded in here.

Issue #755: the JSON-load-or-raise and validator-build/iter-errors logic
below is shared with ``gitapex_scan_skill_metadata_schema.py`` via
``_gitapex_schema_validation.py`` rather than each script carrying its own
near-verbatim copy -- see that module's own docstring for why, including
the format-checker drift this extraction backports a fix for.

Run standalone (exit 1 on drift) or via the pytest gate in
``tests/test_gitapex_scan_ssot_schema.py``.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any, Literal

import _gitapex_argv_safety
import _gitapex_schema_validation
from pydantic import BaseModel, ConfigDict, ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"
SCHEMA_PATH = REPO_ROOT / ".gitapex" / "ssot.schema.json"


class RegistryReadError(Exception):
    """Either ``.gitapex/ssot.json`` or ``.gitapex/ssot.schema.json`` could
    not be read as UTF-8 text or parsed as JSON at all -- exit 1, never a
    traceback. Distinct from a schema-valid-JSON-but-drifted instance,
    which ``find_schema_violations`` reports as an ordinary finding."""


class PolicySource(BaseModel):
    """.gitapex/ssot.json ``policy_sources[]`` entry: a file at least one
    gate reads as authoritative data via ``policy_refs``."""

    model_config = ConfigDict(extra="forbid")

    id: str
    path: str
    format: Literal["toml", "json", "yaml", "rego"]
    authority: str


class GateFailMode(BaseModel):
    """Mirrors gate.fail_mode (issue #1231): what a gate does when it cannot
    correctly evaluate its own condition, distinct from a confirmed policy
    violation. Bare ``str`` on ``rationale``, no extra length constraint --
    same division of responsibility as ``Gate`` itself (jsonschema is the
    strict validator; this is the secondary typed-access layer)."""

    model_config = ConfigDict(extra="forbid")

    on_error: Literal["fail-open", "fail-closed", "mixed"]
    rationale: str


class GateTargetEntry(BaseModel):
    """Mirrors one gate.target[] entry (issue #1231): the machine-comparable
    subset of what ``trigger`` describes in prose."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "mcp-tool", "bash-pattern", "file-glob", "workflow-event", "github-native", "cross-registry-consistency"
    ]
    ref: str


class Gate(BaseModel):
    """.gitapex/ssot.json ``gates[]`` entry: one deterministic gate gitapex
    enforces on itself. ``script``/``native_rule`` stay optional here -- the
    schema's own if/then keeps them conditionally required by ``kind``,
    already enforced by ``find_schema_violations`` before this model is ever
    constructed."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["script", "native", "opa-rego"]
    script: str | list[str] | None = None
    native_rule: str | None = None
    rule: str
    planes: list[Literal["pretooluse", "posttooluse", "ci", "local"]]
    local_invocation: list[str] | None = None
    local_stdin: list[str] | None = None
    local_exclusion: str | None = None
    trigger: str
    policy_refs: list[str]
    cluster: str | list[str]
    tracking_issue: int | None
    status: Literal["experimental", "active", "deprecated"]
    supersedes: str | None
    fail_mode: GateFailMode | None = None
    target: list[GateTargetEntry] | None = None
    bypass_review_status: Literal["not-yet-reviewed", "reviewed-none-found", "reviewed-found-listed-below"] | None = (
        None
    )


class SsotMeta(BaseModel):
    """.gitapex/ssot.json ``meta``: registry-level lifecycle, distinct from
    any single gate's own status."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    tracking_issue: int
    status: Literal["draft", "active", "deprecated"]
    phase: str


class SsotRegistry(BaseModel):
    """The full, already-jsonschema-checked ``.gitapex/ssot.json`` document,
    typed for the reference-drift checks below."""

    model_config = ConfigDict(extra="forbid")

    meta: SsotMeta
    policy_sources: list[PolicySource]
    gates: list[Gate]
    clusters: dict[str, str]


def _get_list(d: Any, key: str) -> list[Any]:
    """d.get(key, []), but also defaults when `d` isn't a dict at all (not
    just when the key's own value is an explicit JSON null) -- dict.get's
    default only covers the latter, and callers such as find_duplicate_ids
    may be handed a whole-instance value that jsonschema will separately
    flag as a schema violation but that isn't itself a dict (e.g. `[]` or
    `1` at the JSON document root). Used only by find_duplicate_ids, which
    stays dict-based (see module docstring)."""
    if not isinstance(d, dict):
        return []
    value = d.get(key)
    return value if isinstance(value, list) else []


def _script_paths(gate: dict[str, Any]) -> list[str]:
    """Dict-based script-path extraction. Kept for its own direct test
    coverage (test_script_paths_defaults_to_empty_when_absent); the
    pydantic-driven find_script_drift below normalizes Gate.script itself
    via _as_list instead of calling this."""
    script = gate.get("script")
    if script is None:
        return []
    return [script] if isinstance(script, str) else list(script)


def _cluster_values(gate: dict[str, Any]) -> list[str]:
    """Dict-based cluster-value extraction. Kept for its own direct test
    coverage (test_cluster_values_defaults_to_empty_when_absent); the
    pydantic-driven find_cluster_drift below normalizes Gate.cluster itself
    via _as_list instead of calling this."""
    cluster = gate.get("cluster")
    if cluster is None:
        return []
    return [cluster] if isinstance(cluster, str) else list(cluster)


def _as_list(value: str | list[str] | None) -> list[str]:
    """Normalize a oneOf(string, array-of-string) pydantic field
    (Gate.script or Gate.cluster) to a list -- the typed equivalent of
    _script_paths/_cluster_values above, used by the pydantic-driven checks
    below."""
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _parse_registry(instance: Any) -> SsotRegistry | None:
    """Parse an already-jsonschema-checked instance dict into a typed
    SsotRegistry. Never raises: a schema-invalid instance (a missing field,
    an explicit null in place of an array/object) may also fail this parse,
    in which case find_schema_violations already reports the real problem
    and the reference-drift checks below simply have nothing typed to
    check."""
    try:
        return SsotRegistry.model_validate(instance)
    except ValidationError:
        return None


def find_schema_violations(instance: Any, schema: dict[str, Any]) -> list[str]:
    """Return one message per JSON-Schema (draft 2020-12) validation error
    against the given schema. Empty list means the instance is valid."""
    return _gitapex_schema_validation.validate(instance, schema)


def find_script_drift(registry: SsotRegistry | None, repo_root: pathlib.Path = REPO_ROOT) -> list[str]:
    """Return one message per gates[] script path that doesn't exist as a real
    file. Only checked for kind == "script" -- "native" gates have no repo
    file to check, and "opa-rego" gates aren't seeded yet."""
    if registry is None:
        return []
    findings: list[str] = []
    for gate in registry.gates:
        if gate.kind != "script":
            continue
        for path in _as_list(gate.script):
            if not (repo_root / path).is_file():
                findings.append(f"script-drift: {gate.id}: script path does not exist: {path}")
    return findings


# Suffixes that make a token unambiguously a path to a tracked file rather
# than an ordinary argument -- see _looks_like_repo_path.
_PATH_SUFFIXES = (".py", ".sh", ".yml", ".yaml", ".json", ".toml")


def _looks_like_repo_path(token: str) -> bool:
    """True for an argv token that is unambiguously a repo-root-relative
    path to a tracked file, so ``find_local_invocation_drift`` can check it
    exists without misreading a token that merely *contains* a slash or a
    suffix. Deliberately conservative, each rule closing a real token shape
    present in ``.gitapex/ssot.json``'s own local_invocation / local_stdin
    values today:

    - a leading ``-`` is an option, never a path (``--merge-base``);
    - a ``*`` marks a pathspec or glob resolved by the invoked tool itself,
      not a file this scanner can stat (``*.py`` as git's own pathspec).

    A token with no ``/`` (``pyproject.toml``, ``ruff``) and a token with no
    recognized suffix (``origin/main`` -- a git revision, not a file) are
    both skipped for the same reason: neither is distinguishable from a
    non-path argument by inspection alone, and stat-ing them would report
    drift for arguments that are working exactly as intended.

    Note what this deliberately does *not* skip any more: a comma. An
    earlier revision treated any ``,``-bearing token as a delimited list and
    skipped it whole, which silently exempted a real path -- xenon's
    ``--exclude apm_modules/*,skills/.../gitapex_check_skill_shape.py``
    carries a genuine, stat-able repository path in its second element, and
    renaming that file would have made the exclusion silently ineffective
    with this scanner reporting clean. ``_iter_path_tokens`` splits on
    commas first and applies this predicate per element instead, so the
    glob element is skipped on its own merits and the path element is
    checked on its own."""
    if not token or token.startswith("-") or "*" in token or "/" not in token:
        return False
    return token.endswith(_PATH_SUFFIXES)


def _iter_path_tokens(token: str) -> list[str]:
    """Every comma-delimited element of one argv token that
    _looks_like_repo_path accepts. A token with no comma yields at most
    itself; see that predicate's own docstring for why commas are split
    rather than used to skip the whole token."""
    return [element for element in token.split(",") if _looks_like_repo_path(element)]


def find_local_invocation_drift(registry: SsotRegistry | None, repo_root: pathlib.Path = REPO_ROOT) -> list[str]:
    """Return one message per ``local_invocation``/``local_stdin`` argv token
    that names a repository file which does not exist, or that escapes the
    repository root entirely (issue #876).

    The schema's own if/then/else already enforces the structural half of
    the local plane -- ``local`` in ``planes`` requires ``local_invocation``
    and forbids ``local_exclusion``, and its absence requires the converse --
    so this adds only the half JSON Schema cannot express: that the argv
    actually points at something real. It is the same drift shape
    ``find_script_drift`` closes for ``gates[].script``, one field over: a
    renamed or deleted gate script would otherwise leave
    ``gitapex_gate_local_preflight.py`` reporting that gate as a *failure* on
    every contributor's machine (exit 127, "No such file or directory")
    rather than as registry drift caught here on the diff that caused it.

    An absolute token, or one containing ``..``, is a finding in its own
    right rather than something to stat. ``pathlib``'s ``/`` operator
    *discards* its left operand when the right side is absolute, so
    ``repo_root / "/etc/passwd"`` is simply ``/etc/passwd``: an absolute
    ``local_invocation`` token that happens to exist on its author's machine
    would validate there and fail on a CI runner, making this gate's own
    verdict machine-dependent -- the one property a drift gate cannot have.
    """
    if registry is None:
        return []
    findings: list[str] = []
    for gate in registry.gates:
        for field, argv in (("local_invocation", gate.local_invocation), ("local_stdin", gate.local_stdin)):
            for token in argv or []:
                for path_token in _iter_path_tokens(token):
                    if pathlib.PurePosixPath(path_token).is_absolute() or ".." in path_token.split("/"):
                        findings.append(
                            f"local-invocation-drift: {gate.id}: {field} must stay inside the "
                            f"repository root, got: {path_token}"
                        )
                    elif not (repo_root / path_token).is_file():
                        findings.append(
                            f"local-invocation-drift: {gate.id}: {field} references missing file: {path_token}"
                        )
    return findings


def find_local_shell_argv(registry: SsotRegistry | None) -> list[str]:
    """Return one message per ``local_invocation``/``local_stdin`` argv that
    would re-introduce a shell, or hand inline code to an interpreter
    (issue #876).

    ``gitapex_gate_local_preflight.py`` runs every argv through
    :func:`subprocess.run` in exec form with no ``shell=True``, which stops
    *the runner* from introducing a shell. It does not stop the argv from
    *being* one: ``["sh", "-c", "<anything>"]`` is a perfectly valid argv
    list. That matters because this change makes ``.gitapex/ssot.json`` --
    until now a pure reference/routing manifest, reviewed as data -- into a
    carrier of commands that CONTRIBUTING.md tells contributors to execute
    before every push. A maintainer running the preflight while reviewing a
    fork's branch would execute whatever that branch's registry declared.

    This closes the shape rather than the intent: an argv naming a real
    interpreter and a real script file is still arbitrary code by
    construction, and this scanner cannot and does not try to adjudicate
    what that script does. What it removes is the ability to hide the
    payload *inside the registry entry itself*, where no reviewer expects
    executable content and where none of this repository's
    executable-surface conventions (see
    ``skills/screening-a-low-trust-contribution``) currently point. Widening
    those conventions and CODEOWNERS to cover ``.gitapex/**`` is the
    complementary half, tracked separately rather than assumed here.

    **This is the review-time half of a two-layer guard, not the whole
    guard.** A review of PR #888 observed that the gate running this scanner
    (``ssot-schema-drift``) is itself one of the wired gates, so it executes
    in gate-id order and is not the first id in that order, and a
    hostile argv on any gate sorting before it has already run by the time this function
    is reached. ``gitapex_gate_local_preflight.py`` therefore applies the
    same predicates itself, before starting any subprocess, via the shared
    ``_gitapex_argv_safety`` module. This one stays because it reports the
    problem as reviewable registry drift on the diff that introduces it,
    which a hard refusal to run does not."""
    if registry is None:
        return []
    findings: list[str] = []
    for gate in registry.gates:
        for field, argv in (("local_invocation", gate.local_invocation), ("local_stdin", gate.local_stdin)):
            if not argv:
                continue
            findings.extend(
                f"local-shell-argv: {gate.id}: {field} {violation}"
                for violation in _gitapex_argv_safety.find_argv_safety_violations(argv)
            )
    return findings


def find_local_invocation_identity_drift(registry: SsotRegistry | None) -> list[str]:
    """Return one message per local-plane gate whose ``local_invocation``
    never names one of that gate's own ``gates[].script`` paths (issue
    #876).

    ``find_local_invocation_drift`` above only asks whether an argv's path
    tokens *exist*. That leaves the wiring's whole point unguarded: pointing
    ``hidden-characters``'s ``local_invocation`` at ``["true"]`` -- or at a
    *different* gate's real script -- is schema-valid, passes the existence
    check, and makes the preflight report ``PASS  hidden-characters`` for a
    gate that never ran. That is a false-clean verdict on a green pre-push
    run, which is the exact outcome the whole local plane exists to prevent.

    The rule: a ``kind: "script"`` gate on the local plane must carry, as one
    of its argv tokens, at least one of its own registered ``script`` paths.

    **The one exemption, and why it is not a loophole.** A gate whose every
    registered ``script`` is a workflow file (``.yml``/``.yaml``) has its
    enforcement logic inline in that workflow, with no separate script file
    to name -- ``python-lint`` (``uv run --locked ruff check .``) and
    ``cyclomatic-complexity-floor`` (``uv run --frozen xenon ...``) are both
    that shape, and no argv could satisfy this rule for them without naming
    a workflow file the local runner cannot execute. They are exempted by a
    property of their own registry entry, checked here, not by an id
    allowlist that would silently grow. Measured at the commit that added
    this check, and re-checked since: those two wired gates are the only
    ones taking the exemption, and every other wired gate satisfies the
    rule unmodified. Stated as the property rather than as a pair of
    counts, for the reason issue #904's third finding gives. A gate
    with a mixed ``.yml``-and-script list (``mypy-type-check``,
    ``exception-handler-gap``) is *not* exempt and must name its script."""
    if registry is None:
        return []
    findings: list[str] = []
    for gate in registry.gates:
        if gate.kind != "script" or not gate.local_invocation:
            continue
        script_paths = _as_list(gate.script)
        if not script_paths or all(path.endswith((".yml", ".yaml")) for path in script_paths):
            continue
        argv_tokens = {element for token in gate.local_invocation for element in token.split(",")}
        if not argv_tokens.intersection(script_paths):
            findings.append(
                f"local-invocation-identity-drift: {gate.id}: local_invocation names none of "
                f"this gate's own script paths ({', '.join(script_paths)})"
            )
    return findings


def find_policy_ref_drift(registry: SsotRegistry | None) -> list[str]:
    """Return one message per gates[].policy_refs[] value that doesn't resolve
    to a real policy_sources[].id."""
    if registry is None:
        return []
    known_ids = {source.id for source in registry.policy_sources}
    findings: list[str] = []
    for gate in registry.gates:
        for ref in gate.policy_refs:
            if ref not in known_ids:
                findings.append(
                    f"policy-ref-drift: {gate.id}: policy_refs references unknown policy_sources id {ref!r}"
                )
    return findings


def find_cluster_drift(registry: SsotRegistry | None) -> list[str]:
    """Return one message per gates[].cluster value that doesn't name a real
    top-level clusters key."""
    if registry is None:
        return []
    known_clusters = set(registry.clusters)
    findings: list[str] = []
    for gate in registry.gates:
        for cluster in _as_list(gate.cluster):
            if cluster not in known_clusters:
                findings.append(f"cluster-drift: {gate.id}: cluster references unknown clusters key {cluster!r}")
    return findings


def find_duplicate_ids(instance: Any) -> list[str]:
    """Return one message per id used more than once across gates[] or
    across policy_sources[] (checked as two separate namespaces -- a gate
    and a policy source are never cross-referenced by the same field, so a
    shared string between the two namespaces is not itself a collision).
    An unnoticed duplicate would silently make one entry invisible to every
    cross-reference the other checks in this module perform."""
    findings: list[str] = []
    for label, key in (("gate", "gates"), ("policy-source", "policy_sources")):
        seen: dict[str, int] = {}
        for entry in _get_list(instance, key):
            # A schema-valid-shaped gates[]/policy_sources[] array can still
            # carry a non-dict entry (e.g. a bare int or string, or an
            # explicit null) -- schema-invalid, caught separately by
            # find_schema_violations, but entry.get("id") below would raise
            # an uncaught AttributeError on such an entry before that
            # finding was even reported. Skip it here the same way an
            # entry missing "id" is already skipped.
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id")
            # The schema requires `id` to be a string; a non-string value
            # (missing/null, but also a list/dict/int/bool -- all
            # schema-invalid, caught separately by find_schema_violations)
            # is skipped here rather than used as a dict key below, which
            # would raise an uncaught TypeError for an unhashable list/dict.
            if not isinstance(entry_id, str):
                continue
            seen[entry_id] = seen.get(entry_id, 0) + 1
        for entry_id, count in seen.items():
            if count > 1:
                findings.append(f"duplicate-id: {label} id {entry_id!r} is used {count} times")
    return findings


def find_drift(
    instance_path: pathlib.Path = SSOT_PATH,
    schema_path: pathlib.Path = SCHEMA_PATH,
    repo_root: pathlib.Path = REPO_ROOT,
) -> list[str]:
    """Return every drift finding across schema validation and the three
    repo-grounded reference checks. Empty list means the registry is clean."""
    instance = _gitapex_schema_validation.load_json_or_raise(instance_path, RegistryReadError)
    schema = _gitapex_schema_validation.load_json_or_raise(schema_path, RegistryReadError)
    registry = _parse_registry(instance)

    findings: list[str] = []
    findings.extend(find_schema_violations(instance, schema))
    findings.extend(find_script_drift(registry, repo_root))
    findings.extend(find_local_invocation_drift(registry, repo_root))
    findings.extend(find_local_shell_argv(registry))
    findings.extend(find_local_invocation_identity_drift(registry))
    findings.extend(find_policy_ref_drift(registry))
    findings.extend(find_cluster_drift(registry))
    findings.extend(find_duplicate_ids(instance))
    return findings


def main() -> int:
    try:
        findings = find_drift()
    except RegistryReadError as error:
        print("ssot.json drift:")
        print(f"  {error}")
        return 1
    if findings:
        print("ssot.json drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No ssot.json drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
