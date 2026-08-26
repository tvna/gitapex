"""Shared jq falsy/type-confusion matrix test for every `(.field == null) or
(.field | type == "X")`-shaped guard clause in `hooks/*.sh` (issue #1312).

Issue #1237's own retrospective for PR #1213 records that this exact bug
class -- `jq -r` silently mis-handling a non-string/non-object value instead
of erroring, letting a malformed field slip past a hook's own fail-closed
guard -- needed four separate adversarial-review rounds to fully stamp out
across four hook files, and explicitly proposed "a parametrized property
test enumerating jq's full falsy/type-confusion matrix (absent, null,
false, true, 0, "", array, object) against every ... guard ... run in CI"
as the systemic gate that would have caught all four in one pass instead of
four.

This file is that gate: one canonical 8-value matrix (see
`REJECTED_FOR_OBJECT_GUARD`/`REJECTED_FOR_STRING_GUARD`/
`ACCEPTED_SHAPE_ONLY` below), applied via subprocess against every
currently-known guarded field across the six hooks issue #1218 names (the
four hooks PR #1213 touched, plus the two "origin" hooks
`check-pr-issue-acm-disclosure.sh`/`check-pr-title-convention.sh` that
issue #1218 found the proven fix had "twice failed to reach" -- tracked
separately as #1216/#1217 and fixed in the same change as this test, since
this test cannot honestly claim to "pass against current main" while two of
its six target hooks still fail closed on only 4 of the matrix's 8 values).

Scope (per issue #1312's own Constraints): `(.field == null) or (.field |
type == "X")`-shaped guards only. Does not re-derive each hook's own
business-logic tests (already covered by that hook's own
`test_gitapex_check_*.py` file) -- only that the shape/type guard itself
fails closed for every matrix value outside its accepted type, and does not
mis-fire (crash, or wrongly deny) for the null/absent case a real caller
legitimately sends.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).parent.parent
HOOKS_DIR = Path(__file__).parent

ABSENT = object()  # sentinel: omit the field from the payload entirely


def _set_field(payload: dict[str, Any], path: tuple[str, ...], value: Any) -> dict[str, Any]:
    """Returns a deep copy of `payload` with the field at `path` (a chain of
    dict keys) set to `value`, or removed entirely if `value is ABSENT`."""
    result = copy.deepcopy(payload)
    node = result
    for key in path[:-1]:
        node = node[key]
    leaf = path[-1]
    if value is ABSENT:
        node.pop(leaf, None)
    else:
        node[leaf] = value
    return result


def _run(script: Path, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    # Hermetic against this session's own ambient plugin/project/token env,
    # same convention every other hooks/test_gitapex_check_*.py file uses.
    for key in ("CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "GH_TOKEN", "GITHUB_TOKEN"):
        env.pop(key, None)
    return subprocess.run(
        ["bash", str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=str(REPO_ROOT),
    )


# The full jq falsy/type-confusion value matrix (issue #1312's own Facts):
# absent, null, false, true, 0, "", array, object -- split by which of the
# two guard shapes this repository's hooks use.
#
# `""` (empty string) is itself type "string", so it is the one matrix value
# that is REJECTED for an object guard but ACCEPTED (shape-wise) for a
# string guard -- it is deliberately absent from REJECTED_FOR_STRING_GUARD
# for that reason, not an oversight.
REJECTED_FOR_OBJECT_GUARD: list[tuple[Any, str]] = [
    (["x"], "array"),
    ("text", "string"),
    ("", "empty-string"),
    (0, "zero"),
    (True, "bool-true"),
    (False, "bool-false"),
]

REJECTED_FOR_STRING_GUARD: list[tuple[Any, str]] = [
    (["x"], "array"),
    ({"k": 1}, "object"),
    (0, "zero"),
    (True, "bool-true"),
    (False, "bool-false"),
]

ACCEPTED_SHAPE_ONLY: list[tuple[Any, str]] = [
    (None, "null"),
    (ABSENT, "absent"),
]


class GuardedField:
    """One `(.field == null) or (.field | type == "X")`-shaped guard clause
    in one hook, per issue #1312's own scope. `field_path` is the chain of
    JSON keys from the payload root to the guarded field (e.g. `("tool_name",)`
    or `("tool_input", "command")`). `base_payload` is a full, otherwise-valid
    payload that reaches this hook's own guard/downstream logic without
    tripping any *other* guard -- used as the substrate `_set_field` edits."""

    def __init__(
        self,
        *,
        hook_id: str,
        script_name: str,
        field_path: tuple[str, ...],
        field_label: str,
        expected_type: str,
        base_payload: dict[str, Any],
    ) -> None:
        self.hook_id = hook_id
        self.script = HOOKS_DIR / script_name
        self.field_path = field_path
        self.field_label = field_label
        self.expected_type = expected_type
        self.base_payload = base_payload

    @property
    def rejected_matrix(self) -> list[tuple[Any, str]]:
        return REJECTED_FOR_OBJECT_GUARD if self.expected_type == "object" else REJECTED_FOR_STRING_GUARD

    @property
    def bad_shape_phrases(self) -> tuple[str, str]:
        """Both known deny-message phrasings for a shape-guard rejection
        naming this field -- checked without branching on `expected_type`,
        since every guard in this registry's own null/absent case falls
        through to the hook's downstream logic (exit 0 or a real semantic
        deny) rather than ever tripping *either* shape guard, so which
        phrasing would have applied is not itself exercised here."""
        return (
            f"{self.field_label} in the payload is not a JSON object",
            f"{self.field_label} in the payload is not a string",
        )


# Six hooks issue #1218 names: the four hooks PR #1213 already fixed, plus
# the two origin hooks (#1216/#1217) fixed alongside this test. One entry
# per currently-known guarded field (per #1237's own repair records).
GUARDED_FIELDS: list[GuardedField] = [
    # --- check-bash-safety.sh (PR #1213) ------------------------------
    GuardedField(
        hook_id="bash-safety",
        script_name="check-bash-safety.sh",
        field_path=("tool_name",),
        field_label="tool_name",
        expected_type="string",
        base_payload={"tool_name": "Bash", "tool_input": {"command": "echo hi"}},
    ),
    GuardedField(
        hook_id="bash-safety",
        script_name="check-bash-safety.sh",
        field_path=("tool_input",),
        field_label="tool_input",
        expected_type="object",
        base_payload={"tool_name": "Bash", "tool_input": {"command": "echo hi"}},
    ),
    GuardedField(
        hook_id="bash-safety",
        script_name="check-bash-safety.sh",
        field_path=("tool_input", "command"),
        field_label="tool_input.command",
        expected_type="string",
        base_payload={"tool_name": "Bash", "tool_input": {"command": "echo hi"}},
    ),
    # --- check-template-overwrite.sh (PR #1213) -----------------------
    GuardedField(
        hook_id="template-overwrite",
        script_name="check-template-overwrite.sh",
        field_path=("tool_name",),
        field_label="tool_name",
        expected_type="string",
        base_payload={"tool_name": "Write", "tool_input": {"file_path": "/tmp/gitapex-matrix-test.txt"}},
    ),
    GuardedField(
        hook_id="template-overwrite",
        script_name="check-template-overwrite.sh",
        field_path=("tool_input",),
        field_label="tool_input",
        expected_type="object",
        base_payload={"tool_name": "Write", "tool_input": {"file_path": "/tmp/gitapex-matrix-test.txt"}},
    ),
    GuardedField(
        hook_id="template-overwrite",
        script_name="check-template-overwrite.sh",
        field_path=("tool_input", "file_path"),
        field_label="tool_input.file_path",
        expected_type="string",
        base_payload={"tool_name": "Write", "tool_input": {"file_path": "/tmp/gitapex-matrix-test.txt"}},
    ),
    # --- check-merge-pull-request-block.sh (PR #1213) -----------------
    # No tool_input-shape guard: this hook denies unconditionally once
    # tool_name matches, never reading any tool_input subfield.
    GuardedField(
        hook_id="merge-pull-request-block",
        script_name="check-merge-pull-request-block.sh",
        field_path=("tool_name",),
        field_label="tool_name",
        expected_type="string",
        base_payload={
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "pullNumber": 1},
        },
    ),
    # --- check-pr-skill-audit-disclosure.sh (PR #1213) ----------------
    GuardedField(
        hook_id="pr-skill-audit-disclosure",
        script_name="check-pr-skill-audit-disclosure.sh",
        field_path=("tool_name",),
        field_label="tool_name",
        expected_type="string",
        base_payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"base": "main", "body": "no evidence"},
        },
    ),
    GuardedField(
        hook_id="pr-skill-audit-disclosure",
        script_name="check-pr-skill-audit-disclosure.sh",
        field_path=("tool_input",),
        field_label="tool_input",
        expected_type="object",
        base_payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"base": "main", "body": "no evidence"},
        },
    ),
    # --- check-pr-issue-acm-disclosure.sh (origin hook, #1216/#1217) --
    # `body: "Refs #1"` is a context-only citation: short-circuits before
    # any network fetch, same convention
    # test_gitapex_check_pr_issue_acm_disclosure_shell.py's own
    # test_allowed_when_only_a_context_only_citation_is_present uses, so
    # this file stays hermetic/fast (no GH_TOKEN, no live API call).
    GuardedField(
        hook_id="pr-issue-acm-disclosure",
        script_name="check-pr-issue-acm-disclosure.sh",
        field_path=("tool_name",),
        field_label="tool_name",
        expected_type="string",
        base_payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "title": "x", "body": "Refs #1"},
        },
    ),
    GuardedField(
        hook_id="pr-issue-acm-disclosure",
        script_name="check-pr-issue-acm-disclosure.sh",
        field_path=("tool_input",),
        field_label="tool_input",
        expected_type="object",
        base_payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "title": "x", "body": "Refs #1"},
        },
    ),
    # --- check-pr-title-convention.sh (origin hook, #1216/#1217) ------
    GuardedField(
        hook_id="pr-title-convention",
        script_name="check-pr-title-convention.sh",
        field_path=("tool_name",),
        field_label="tool_name",
        expected_type="string",
        base_payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "title": "feat(x): valid title", "body": "x"},
        },
    ),
    GuardedField(
        hook_id="pr-title-convention",
        script_name="check-pr-title-convention.sh",
        field_path=("tool_input",),
        field_label="tool_input",
        expected_type="object",
        base_payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "title": "feat(x): valid title", "body": "x"},
        },
    ),
    # --- check-pr-duplicate-issue.sh (seventh hook, #1315) ------------
    # `body: "Refs #1"` is a context-only citation, same hermetic
    # convention the pr-issue-acm-disclosure entries above use: this
    # field's own guard fires before any citation parsing (and any
    # network fetch) would matter anyway. `tool_input` is deliberately
    # NOT registered here: issue #1315's own Constraints scope this fix
    # to the `tool_name` guard only (that hook's `tool_input` guard was
    # already fixed under issue #1197, before this matrix file existed).
    GuardedField(
        hook_id="pr-duplicate-issue",
        script_name="check-pr-duplicate-issue.sh",
        field_path=("tool_name",),
        field_label="tool_name",
        expected_type="string",
        base_payload={
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"owner": "tvna", "repo": "gitapex", "title": "x", "body": "Refs #1"},
        },
    ),
]


def _rejected_cases() -> list[tuple[GuardedField, Any, str]]:
    return [(field, value, label) for field in GUARDED_FIELDS for value, label in field.rejected_matrix]


def _accepted_cases() -> list[tuple[GuardedField, Any, str]]:
    return [(field, value, label) for field in GUARDED_FIELDS for value, label in ACCEPTED_SHAPE_ONLY]


@pytest.mark.parametrize(
    "field,value,value_label",
    _rejected_cases(),
    ids=[f"{field.hook_id}:{field.field_label}:{value_label}" for field, _value, value_label in _rejected_cases()],
)
def test_guard_fails_closed_for_every_type_confused_value(field: GuardedField, value: Any, value_label: str) -> None:
    """For every matrix value outside a guard's own accepted type, the hook
    must deny (exit 2) rather than let the value fall through to a crash
    (a raw jq runtime-error exit code, non-blocking per Claude Code's own
    PreToolUse contract) or a silent, incorrect "not our tool" skip."""
    payload = _set_field(field.base_payload, field.field_path, value)
    result = _run(field.script, payload)
    assert result.returncode == 2, (
        f"{field.hook_id}:{field.field_label}={value_label}: expected deny (exit 2), "
        f"got {result.returncode}: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert field.field_label in parsed["systemMessage"], (
        f"{field.hook_id}:{field.field_label}={value_label}: deny message does not name the guarded "
        f"field: {parsed['systemMessage']!r}"
    )


@pytest.mark.parametrize(
    "field,value,value_label",
    _accepted_cases(),
    ids=[f"{field.hook_id}:{field.field_label}:{value_label}" for field, _value, value_label in _accepted_cases()],
)
def test_guard_does_not_misfire_on_null_or_absent(field: GuardedField, value: Any, value_label: str) -> None:
    """null and absent are the two matrix values every guard here is
    documented to accept (jq indexes a missing key or an explicit `null`
    the same way, as `null`, never a runtime error) -- the hook must reach
    its own downstream verdict rather than crash (a raw jq error exit code)
    or have *this* shape guard wrongly reject it."""
    payload = _set_field(field.base_payload, field.field_path, value)
    result = _run(field.script, payload)
    assert result.returncode in (0, 2), (
        f"{field.hook_id}:{field.field_label}={value_label}: expected a real verdict (0 or 2), "
        f"got {result.returncode} (a crash?): stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    if result.returncode == 2:
        parsed = json.loads(result.stderr)
        message = parsed["systemMessage"]
        assert not any(phrase in message for phrase in field.bad_shape_phrases), (
            f"{field.hook_id}:{field.field_label}={value_label}: this guard wrongly rejected a "
            f"null/absent value as a bad shape: {message!r}"
        )
