"""SKILL.md body token-budget check (design doc:
docs/superpowers/specs/2026-09-02-skill-body-cost-controls-design.md,
Decision 3) -- a rough, stdlib-only token-count estimate
(``len(content) // 4``, identical to NVIDIA/SkillEvaluator's own
formula) against ``BODY_MAX_TOKENS``. SKILL.md body only:
references/*.md is explicitly exempt (a reference file's job is
topic-scoped focus, not brevity for its own sake -- see
``BODY_MAX_TOKENS``'s own comment in ``constants.py``).

Tiered enforcement, per the design doc's own Decision 3: without
``--strict-token-budget`` (the default -- covers every already-shipped
skill), an over-budget body is advisory only (``passed=True``, a
warning in ``evidence``); with the flag (wired only into
``drafting-a-skill``'s own invocation, so only a brand-new skill draft
is held to it), ``passed`` reflects the real threshold comparison.
"""

from __future__ import annotations

from shape_checks.constants import BODY_MAX_TOKENS, CheckResult


def _token_budget_result(text: str, *, strict: bool) -> CheckResult:
    """``text`` is the SKILL.md's own full content (frontmatter included),
    matching ``_body_length_result``'s identical convention in
    ``orchestrator.py`` -- both the existing line-count sibling check and
    this one read the same input, keeping evidence line-count-comparable
    and (were a line number ever added to this check's own evidence)
    numbered against the real file rather than an offset frontmatter
    stripping would introduce."""
    estimated_tokens = len(text) // 4
    over_budget = estimated_tokens > BODY_MAX_TOKENS
    rule = (
        f"SKILL.md body <= {BODY_MAX_TOKENS} estimated tokens (len(content)//4; advisory unless --strict-token-budget)"
    )
    if strict:
        evidence = (
            f"{estimated_tokens} tokens"
            if not over_budget
            else f"over budget: {estimated_tokens} tokens > {BODY_MAX_TOKENS}"
        )
        return CheckResult("body-token-budget", not over_budget, rule, evidence)
    evidence = (
        f"over budget: {estimated_tokens} tokens > {BODY_MAX_TOKENS} (advisory only)"
        if over_budget
        else f"{estimated_tokens} tokens"
    )
    return CheckResult("body-token-budget", True, rule, evidence)
