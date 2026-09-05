"""Drift gate: the post-write hook's covered-tool list is stated in three
places and must stay identical across all three.

Issue #878's own gate names the same three MCP write tools in
`hooks/hooks.json`'s PostToolUse `matcher` regex, in
`hooks/check-post-write-provenance.sh`'s `case "$tool_name"` arms, and in
`hooks/gitapex_check_post_write_provenance.py`'s `_COVERED_TOOLS`. The
triplication is deliberate -- the matcher routes, and the other two are
independent self-revalidations (evaluating-deterministic-gate-quality
dimension 3, which explicitly wants the gate to re-check its own
matcher-relevant field rather than trust the harness's routing). What was
missing is the gate on the triplication itself.

An adversarial review of this hook found the failure mode concretely:
adding a fourth tool to two of the three places yields a gate that either
never fires (matcher not updated) or fires and immediately SKIPs (a
revalidation not updated) -- silently, in both directions, with every
existing test still green because each one exercises only tools already
present in all three lists.

Same shape and same rationale as this repository's own established sync
gates, `tests/test_gitapex_check_acm_present_sync.py` and
`tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py`: a
policy value duplicated across files that cannot import each other gets a
drift test rather than a comment asking future authors to remember.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import gitapex_check_post_write_provenance as checker

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
WRAPPER = REPO_ROOT / "hooks" / "check-post-write-provenance.sh"

_WRAPPER_NAME = "check-post-write-provenance.sh"
# The wrapper's own self-revalidation arm, e.g.
#   case "$tool_name" in
#     mcp__github__create_pull_request | mcp__plugin_github_github__create_pull_request | ... ) ;;
_CASE_ARM_RE = re.compile(r"^\s*(mcp__(?:github|plugin_github_github)__[\w|\s]*?)\)\s*;;", re.MULTILINE)


def _matcher_tools() -> set[str]:
    """Every tool named by the PostToolUse entry that wires this wrapper."""
    config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    tools: set[str] = set()
    for entry in config["hooks"]["PostToolUse"]:
        wires_this_wrapper = any(_WRAPPER_NAME in hook.get("command", "") for hook in entry.get("hooks", []))
        if wires_this_wrapper:
            tools.update(part.strip() for part in entry["matcher"].split("|") if part.strip())
    return tools


def _wrapper_case_tools() -> set[str]:
    """Every tool named by the wrapper's own `case "$tool_name"` arms."""
    match = _CASE_ARM_RE.search(WRAPPER.read_text(encoding="utf-8"))
    assert match is not None, (
        "the wrapper no longer carries a recognizable mcp__github__ or mcp__plugin_github_github__ case arm"
    )
    return {part.strip() for part in match.group(1).split("|") if part.strip()}


def test_the_matcher_and_the_wrapper_name_the_same_tools() -> None:
    assert _matcher_tools() == _wrapper_case_tools()


def test_the_wrapper_and_the_checker_name_the_same_tools() -> None:
    assert _wrapper_case_tools() == set(checker._COVERED_TOOLS)


def test_the_matcher_and_the_checker_name_the_same_tools() -> None:
    """Asserted directly rather than left to transitivity, so a failure
    report names the two lists that actually disagree."""
    assert _matcher_tools() == set(checker._COVERED_TOOLS)


def test_the_shared_list_is_non_empty() -> None:
    """A regex that stopped matching would make all three comparisons above
    trivially true against three empty sets."""
    assert len(_matcher_tools()) >= 6
