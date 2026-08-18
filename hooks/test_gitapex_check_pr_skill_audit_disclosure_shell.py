"""Regression suite for check-pr-skill-audit-disclosure.sh's own deny/allow
matrix (issue #874).

Named `_shell` for the same pytest-basename reason
hooks/test_gitapex_check_pr_issue_acm_disclosure_shell.py documents: both
`tests/` and `hooks/` are on pyproject.toml's `testpaths` with no
`__init__.py` in either, so two files sharing a basename fail collection.

The hook had no automated coverage at all before issue #874 added a second
tier to it, which is the coverage this file closes. Each test runs the
shipped script via subprocess with the PreToolUse JSON shape Claude Code
sends on stdin, against a scratch git repository built to trigger one
specific path:

- **Tier 1** (the full local verdict) fires when `.github/scripts/`
  is present, i.e. inside this repository's own checkout. It reproduces
  CI's whole applicability computation, so it denies on the conditional
  extensions the bundled tier-2 copy defers to CI.
- **Tier 2** (the bundled base two-audit check) is what a plugin-installed
  consumer repository gets, where per docs/repository-layout.md `.github/`
  does not exist. Simulated here by omitting that directory.
- A tier-1 run that cannot *complete* must fall through to tier 2 with a
  warning rather than deny, matching the hook's documented
  fail-open-on-inconclusive-local-state posture.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "check-pr-skill-audit-disclosure.sh"
REPO_ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.slow

_TIER1_FILES = (
    ".gitapex/ssot.json",
    ".github/scripts/gitapex_compute_skill_audit_flags.py",
    ".github/scripts/gitapex_gate_skill_audit_disclosure.py",
    ".github/scripts/gitapex_detect_changed_gate_scripts.py",
    ".github/scripts/gitapex_skill_description_diff.py",
    ".github/scripts/gitapex_skill_security_relevance.py",
)

_HOOK_FILES = (
    "hooks/check-pr-skill-audit-disclosure.sh",
    "hooks/gitapex_check_skill_audit_disclosure_or_waiver.py",
)

_SKILL_MD = """---
name: sample-skill
description: A perfectly ordinary skill with nothing notable in it.
---

# Sample

Body text.
"""

_BASE_EVIDENCE = (
    "## Skill audit evidence\n\n- battle-testing-a-skill: PASS\n- evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _write(repo: Path, relative: str, content: str = "x\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy(repo: Path, relative: str) -> None:
    _write(repo, relative, (REPO_ROOT / relative).read_text(encoding="utf-8"))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A scratch repo with a `main` branch published as `origin/main`, which
    is what the hook resolves its base branch against."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    _git(tmp_path, "config", "user.email", "t@e")
    _git(tmp_path, "config", "user.name", "t")
    for relative in _HOOK_FILES:
        _copy(tmp_path, relative)
    _write(tmp_path, "README.md")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    # A local `origin` remote so `git merge-base origin/main HEAD` resolves
    # without any network access. `set-head` is not decoration: without
    # refs/remotes/origin/HEAD the hook's default-branch fallback resolves
    # to nothing and it exits early, so every no-explicit-base test would
    # pass for the wrong reason -- never reaching the code it is aimed at.
    _git(tmp_path, "remote", "add", "origin", str(tmp_path))
    _git(tmp_path, "fetch", "-q", "origin")
    _git(tmp_path, "remote", "set-head", "origin", "main")
    _git(tmp_path, "checkout", "-q", "-b", "feature")
    return tmp_path


def _with_tier1(repo: Path) -> Path:
    for relative in _TIER1_FILES:
        _copy(repo, relative)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "tier-1 scripts")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "feature")
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "checkout", "-q", "feature")
    return repo


def _commit(repo: Path, message: str = "change") -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _hook_env(**overrides: str) -> dict[str, str]:
    """Environment for a hook invocation, with the Claude Code path
    variables stripped.

    Applied at *every* call site rather than only in `_run`. Today this
    hook resolves its sibling script from `BASH_SOURCE[0]` and its repo
    root from `git rev-parse --show-toplevel`, so it reads neither
    variable and stripping them changes nothing -- verified by grep over
    its whole call chain. Three sibling hooks
    (check-bash-safety.sh, check-issue-acm-disclosure.sh,
    check-pr-issue-acm-disclosure.sh) *do* read them, which is where this
    suite inherited the pattern. Keeping it uniform here means a future
    `CLAUDE_PROJECT_DIR` fallback in this hook -- matching what its
    siblings already do -- cannot silently let a test resolve the real
    checkout instead of the scratch repository and pass for the wrong
    reason. That failure mode already bit this file once, via a fixture
    missing `refs/remotes/origin/HEAD`.
    """
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.update(overrides)
    return env


def _run(
    repo: Path, body: str, tool_name: str = "mcp__github__create_pull_request"
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"base": "main", "body": body}})
    return subprocess.run(
        ["bash", str(repo / "hooks" / "check-pr-skill-audit-disclosure.sh")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env=_hook_env(),
        cwd=str(repo),
    )


# --- tier 1: the full local verdict ---


def test_tier1_denies_a_conditional_extension_tier2_would_miss(repo: Path) -> None:
    """The whole point of issue #874: a gate change with no SKILL.md at all
    is invisible to the bundled base check and denied here."""
    _with_tier1(repo)
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo, "new gate")
    result = _run(repo, _BASE_EVIDENCE)
    assert result.returncode == 2
    assert "deterministic-gate-quality" in result.stderr


def test_tier1_denial_tells_the_caller_how_to_re_check_locally(repo: Path) -> None:
    """dimensions.md dimension 17: a deny that does not say how to
    reproduce the verdict sends the caller back to pushing and reading a
    failed check, which is the loop issue #874 exists to end."""
    _with_tier1(repo)
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo, "new gate")
    result = _run(repo, _BASE_EVIDENCE)
    assert result.returncode == 2
    assert "--check-diff" in result.stderr
    assert "--body-file" in result.stderr


def test_tier1_allows_the_same_diff_once_disclosed(repo: Path) -> None:
    _with_tier1(repo)
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo, "new gate")
    body = (
        _BASE_EVIDENCE
        + "- checker-script-adversarial-review: RAN\n"
        + "- deterministic-gate-quality: RAN\n"
        + "- defeat-test-disclosure: RAN\n"
    )
    result = _run(repo, body)
    assert result.returncode == 0, result.stderr


def test_tier1_allows_a_diff_that_triggers_nothing(repo: Path) -> None:
    _with_tier1(repo)
    _write(repo, "README.md", "changed\n")
    _commit(repo, "unrelated")
    result = _run(repo, "no evidence section at all")
    assert result.returncode == 0, result.stderr


def test_tier1_falls_back_when_its_own_computation_cannot_complete(repo: Path) -> None:
    """Fail open on inconclusive local state, not deny: an unreadable gate
    registry is a broken local checkout, not a verdict on the PR body. The
    diff carries no SKILL.md, so tier 2 then allows it and CI stays the
    authority."""
    _with_tier1(repo)
    _write(repo, ".gitapex/ssot.json", "{not json")
    _commit(repo, "break the registry")
    result = _run(repo, "no evidence section at all")
    assert result.returncode == 0
    assert "falling back to the bundled base two-audit check" in result.stderr


def test_tier1_denies_even_when_the_failure_output_is_large(repo: Path) -> None:
    """Regression: the FAIL-detection grep must read its input to
    completion.

    `grep -q` closes stdin on first match, which can SIGPIPE a
    still-writing upstream; under `set -o pipefail` that upstream's
    nonzero status outranks grep's own zero exit, turning a real match
    into a false "not found" -- here, a genuine deny silently downgraded
    to the warning fall-through, which then exits 0 for any diff with no
    SKILL.md. This repository banned the pattern in PR #428; this pins
    that the ban holds on a deny whose output is large enough to matter.
    """
    _with_tier1(repo)
    for index in range(60):
        _write(repo, f".github/scripts/gitapex_gate_bulk_{index}.py")
    _commit(repo, "many new gates")
    result = _run(repo, _BASE_EVIDENCE)
    assert result.returncode == 2, result.stderr
    assert "deterministic-gate-quality" in result.stderr


def test_tier1_is_skipped_when_no_explicit_base_was_supplied(repo: Path) -> None:
    """The stacked-PR false deny.

    An update_pull_request call carries no `tool_input.base`, so the base
    falls back to the default branch. For a PR actually based on another
    feature branch that drags the parent's gate and checker-script
    changes into tier 1's much wider scope and denies a body update for
    disclosure the PR does not owe. Tier 2's narrower SKILL.md-only scope
    has always lived with the same fallback; tier 1 must not widen it.
    """
    _with_tier1(repo)
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo, "new gate")
    payload = json.dumps({"tool_name": "mcp__github__update_pull_request", "tool_input": {"body": _BASE_EVIDENCE}})
    result = subprocess.run(
        ["bash", str(repo / "hooks" / "check-pr-skill-audit-disclosure.sh")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env=_hook_env(),
        cwd=str(repo),
    )
    assert result.returncode == 0, result.stderr
    assert "skipping the full local pre-check" in result.stderr


def test_tier1_still_runs_on_an_update_that_does_supply_a_base(repo: Path) -> None:
    """Guards the narrowing above: it must key on whether the base was
    explicit, not on the tool name, or an update_pull_request that does
    send `base` would lose coverage it can correctly have."""
    _with_tier1(repo)
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo, "new gate")
    result = _run(repo, _BASE_EVIDENCE, tool_name="mcp__github__update_pull_request")
    assert result.returncode == 2
    assert "deterministic-gate-quality" in result.stderr


# --- tier 2: the bundled, plugin-bundle-safe base check ---


def test_tier2_denies_a_skill_md_change_with_no_evidence(repo: Path) -> None:
    """No .github/ in this repo, so the plugin-bundle path is what runs."""
    _write(repo, "skills/sample/SKILL.md", _SKILL_MD)
    _commit(repo, "new skill")
    result = _run(repo, "no evidence section at all")
    assert result.returncode == 2
    assert "battle-testing-a-skill" in result.stderr


def test_tier2_allows_a_skill_md_change_that_discloses_both_audits(repo: Path) -> None:
    _write(repo, "skills/sample/SKILL.md", _SKILL_MD)
    _commit(repo, "new skill")
    result = _run(repo, _BASE_EVIDENCE)
    assert result.returncode == 0, result.stderr


def test_tier2_ignores_a_diff_with_no_skill_md(repo: Path) -> None:
    """The documented tier-2 limitation, pinned so the two tiers' different
    scopes stay a decision on the record rather than a surprise."""
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo, "gate change, no tier-1 scripts present")
    result = _run(repo, "no evidence section at all")
    assert result.returncode == 0, result.stderr


# --- shared guards ---


def test_an_unrelated_tool_call_is_ignored(repo: Path) -> None:
    _with_tier1(repo)
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo, "new gate")
    result = _run(repo, "no evidence", tool_name="mcp__github__add_issue_comment")
    assert result.returncode == 0


def test_an_update_call_with_no_body_is_ignored(repo: Path) -> None:
    _with_tier1(repo)
    _write(repo, ".github/scripts/gitapex_gate_new.py")
    _commit(repo, "new gate")
    payload = json.dumps({"tool_name": "mcp__github__update_pull_request", "tool_input": {}})
    result = subprocess.run(
        ["bash", str(repo / "hooks" / "check-pr-skill-audit-disclosure.sh")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env=_hook_env(),
        cwd=str(repo),
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Issue #1208: fail closed, not open, when jq is missing or the payload is
# malformed.
# ---------------------------------------------------------------------------


def _no_jq_path(tmp_path: Path) -> str:
    """A PATH directory holding every tool this script needs except jq, so
    `command -v jq` genuinely fails the way it would in an environment
    without jq installed -- rather than mocking that condition."""
    bin_dir = tmp_path / "no-jq-path"
    bin_dir.mkdir()
    for tool in ("bash", "cat", "git", "python3", "dirname", "mktemp"):
        real = shutil.which(tool)
        if real:
            (bin_dir / tool).symlink_to(real)
    return str(bin_dir)


def test_denied_when_jq_missing(tmp_path: Path) -> None:
    """Live-reproduced before this fix: with jq absent, the very first jq
    call (extracting tool_name) crashed under `set -e` with exit 127
    ("command not found") -- before deny() was even defined, and
    non-blocking per Claude Code's PreToolUse contract, so a PR carrying no
    skill-audit disclosure would have been created unchecked. Must now deny
    (exit 2) instead."""
    payload = json.dumps(
        {"tool_name": "mcp__github__create_pull_request", "tool_input": {"base": "main", "body": "no evidence"}}
    )
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "hooks" / "check-pr-skill-audit-disclosure.sh")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env=_hook_env(PATH=_no_jq_path(tmp_path)),
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "jq is not available" in parsed["systemMessage"]


def test_denied_on_malformed_json_stdin() -> None:
    """Live-reproduced before this fix: jq's own parse-error exit (5)
    propagated past deny() under `set -e` -- non-blocking per Claude Code's
    PreToolUse contract. Must now deny (exit 2) instead."""
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "hooks" / "check-pr-skill-audit-disclosure.sh")],
        input="not valid json{{{",
        capture_output=True,
        text=True,
        timeout=60,
        env=_hook_env(),
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "tool_input", [["not", "an", "object"], False, True, 0], ids=["array", "false", "true", "zero"]
)
def test_denied_when_tool_input_is_not_an_object(tool_input: object) -> None:
    """A well-formed top-level payload whose tool_input is itself a
    non-object would otherwise crash the `.tool_input.body`/`.tool_input.base`
    accesses with jq's own "Cannot index" error. Must deny.

    `false` is the case that actually escaped the original guard: found by
    code review (PR #1213) after the array/string cases above already
    passed -- jq's `//` operator treats JSON `false` the same as `null`
    (both are falsy), so `(.tool_input // {}) | type == "object"` wrongly
    accepted it, and the crash happened one line later, past deny()."""
    payload = json.dumps({"tool_name": "mcp__github__create_pull_request", "tool_input": tool_input})
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "hooks" / "check-pr-skill-audit-disclosure.sh")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env=_hook_env(),
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2) for tool_input={tool_input!r}, got {result.returncode}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_denied_on_valid_json_non_object_stdin() -> None:
    """Valid JSON that isn't an object at the top level (e.g. a bare array)
    would otherwise crash the first field-extraction jq call the same way.
    Must deny."""
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "hooks" / "check-pr-skill-audit-disclosure.sh")],
        input="[]",
        capture_output=True,
        text=True,
        timeout=60,
        env=_hook_env(),
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2, f"expected deny (exit 2), got {result.returncode}: stderr={result.stderr!r}"
    parsed = json.loads(result.stderr)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_outside_a_git_work_tree_the_hook_stays_out_of_the_way(tmp_path: Path) -> None:
    """No repository means no diff to compute applicability from; CI's
    skill-audit-gate.yml remains the backstop."""
    for relative in _HOOK_FILES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((REPO_ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")
    payload = json.dumps({"tool_name": "mcp__github__create_pull_request", "tool_input": {"body": ""}})
    result = subprocess.run(
        ["bash", str(tmp_path / "hooks" / "check-pr-skill-audit-disclosure.sh")],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        env=_hook_env(GIT_CEILING_DIRECTORIES=str(tmp_path)),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0
