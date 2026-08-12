#!/usr/bin/env python3
"""CI gate: a diff touching `.github/workflows/**` or `hooks/**` from a
low-trust PR author must be explicitly maintainer-reviewed.

Issue #136 (Mechanism-fit finding from #128's evaluating-skill-quality
pass): `screening-a-low-trust-contribution/SKILL.md`'s checks 2 and 4
call every such edit a "hard flag, not a sampled subset", but that
guarantee depended entirely on an agent choosing to invoke the skill --
no CI path-filter or CODEOWNERS gate backed it. This script is that
backstop: the calling workflow
(`.github/workflows/low-trust-workflow-hooks-gate.yml`) supplies the PR's
`author_association` and current label list from the `pull_request` event
payload; this script only grades them, matching this repository's
existing `.github/scripts/gitapex_gate_*.py` convention of a workflow
that computes inputs and a script that only grades them.

Trust boundary: OWNER/MEMBER/COLLABORATOR pass unconditionally. Any other
association (CONTRIBUTOR, FIRST_TIME_CONTRIBUTOR, FIRST_TIMER, NONE)
passes only if the `workflow-hooks-reviewed` label is present --
applying a label requires triage/write access on this repository, so the
label itself carries the same trust signal a CODEOWNERS-gated approval
would, without requiring a branch-protection setting change this script
cannot make itself. No CODEOWNERS file exists in this repository and none
is added here (see the design doc cited below for why).

No network calls -- the workflow supplies both inputs as CLI args. Was
stdlib-only through wave 2 of issue #1040's batch; issue #1062 (wave 3)
added the `pydantic` import below, so this file now requires `uv run`
like `gitapex_gate_hidden_characters.py`/`gitapex_gate_behind_base.py` already
do, not a bare `python3` invocation.

Design: docs/superpowers/specs/2026-08-06-screening-low-trust-contribution-gaps-design.md

Issue #1062 (wave 3 of #1040's batch pydantic CLI-arg validation rollout):
`main`'s parsed namespace is now passed through `LowTrustWorkflowHooksArgs`
immediately after `parser.parse_args(argv)`, matching the wrap
`gitapex_gate_hidden_characters.py`/`gitapex_gate_behind_base.py` already apply.
Unlike those two files' own `--root` (a filesystem path with a real
existence constraint), neither `author_association` (required, no
`type=`) nor `labels` (defaults to `""`) has any constraint beyond the
`str` shape `argparse` already guarantees -- so construction can
currently never raise `ValidationError` for a real CLI invocation; the
model exists for consistency with #1040's repo-wide convention (a typed
seam between `parse_args` and business logic), not because either field
has a known-invalid case today. This gate's own production invocation
(`low-trust-workflow-hooks-gate.yml`) already runs under `uv run`
(issue #1035), so the added `pydantic` import is safe here.

Usage (run via `uv run` -- needed for the pydantic import, matching
`gitapex_gate_hidden_characters.py`'s own convention)::

    uv run --frozen python3 .github/scripts/gitapex_gate_low_trust_workflow_hooks.py \\
        --author-association CONTRIBUTOR --labels bug,workflow-hooks-reviewed

Exit codes:
    0  Trusted author, or an untrusted author with the review label present.
    1  Untrusted author, review label absent.
    2  CLI arguments failed validation (unreachable via this script's own
       argparse-guaranteed shape today; see LowTrustWorkflowHooksArgs).
"""

from __future__ import annotations

import argparse
import sys

from pydantic import BaseModel, ValidationError

TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
REVIEW_LABEL = "workflow-hooks-reviewed"


class LowTrustWorkflowHooksArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace (issue #1062). See the
    module docstring's own issue #1062 section for why neither field
    carries an additional field validator."""

    author_association: str
    labels: str = ""


def is_trusted(author_association: str) -> bool:
    return author_association.strip().upper() in TRUSTED_ASSOCIATIONS


def has_review_label(labels: list[str]) -> bool:
    return REVIEW_LABEL in {label.strip() for label in labels}


def check(author_association: str, labels: list[str]) -> tuple[bool, str]:
    """Return (passed, message) for the given author_association and the
    PR's current label list."""
    if is_trusted(author_association):
        return True, f"PASS: author_association={author_association!r} is trusted"
    if has_review_label(labels):
        return True, (
            f"PASS: author_association={author_association!r} is untrusted, but the {REVIEW_LABEL!r} label is present"
        )
    return False, (
        f"author_association={author_association!r} is not OWNER/MEMBER/COLLABORATOR, "
        f"and no {REVIEW_LABEL!r} label is present on this PR. A maintainer must review "
        "this diff's .github/workflows/** or hooks/** changes and apply the "
        f"{REVIEW_LABEL!r} label before this check can pass."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gate .github/workflows/** or hooks/** edits from a low-trust PR author."
    )
    parser.add_argument(
        "--author-association",
        required=True,
        help="The pull_request event payload's author_association field.",
    )
    parser.add_argument(
        "--labels",
        default="",
        help="Comma-separated list of the PR's current labels (empty string for none).",
    )
    args = parser.parse_args(argv)

    try:
        validated = LowTrustWorkflowHooksArgs(author_association=args.author_association, labels=args.labels)
    except ValidationError:
        print("::error::invalid CLI arguments", file=sys.stderr)
        return 2

    labels = [label for label in validated.labels.split(",") if label.strip()]
    passed, message = check(validated.author_association, labels)
    if passed:
        print(message)
        return 0
    print(f"::error::{message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
