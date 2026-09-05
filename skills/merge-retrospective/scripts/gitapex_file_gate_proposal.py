#!/usr/bin/env python3
"""Build the deterministic title and Acceptance Criteria Map body for a
`missing-deterministic-gate` retrospective repair's own standalone
`gate-proposal`-labelled issue.

Design doc: docs/superpowers/specs/2026-08-29-flat-gate-proposal-issues-design.md
(Decision 1: collision-proof, index-keyed title; Decision 4: ACM body, not a
waiver; Decision 6: the label constant as a sync-tested parallel copy;
Component 2). Branch Plan: docs/superpowers/plans/2026-08-29-claude-gitapex-pr-1395-f1t7w4.md
("Shared contract" section, Task B).

PURE, NETWORK-FREE. This module makes no GitHub API calls, no
`issue_write`/`issue_read` calls, and no network access of any kind -- it
only computes strings from its inputs. `skills/merge-retrospective/SKILL.md`'s
own Step 5 prose is what invokes `mcp__github__*` tool calls directly with
the values this module returns (search-then-create-then-verify); this
module never performs those calls itself (Decision 6, Non-goals). That
split is why this module stays trivially unit-testable with no network
mocking, and why every GitHub write in this design still passes through
this repository's own `hooks/check-issue-acm-disclosure.sh` the same way
every other `issue_write` call already does.

`GATE_PROPOSAL_LABEL` below is a **parallel, independent copy** of the
identical literal string `.github/scripts/gitapex_scan_retrospective_gate_drift.py`
defines on its own -- never an import of that file, and never imported
back from it. Per `docs/repository-layout.md`, only `skills/` and `hooks/`
ship with the installed plugin; `.github/` is dev-only CI tooling that is
never installed into a consumer repository, so a cross-tree import would
break at install time (the same structural reason
`hooks/gitapex_check_pr_title_convention.py` and
`.github/scripts/gitapex_gate_pr_title_convention.py` already carry
independent copies of the same Conventional-Commits regex). The two
copies are kept from silently drifting apart by
`tests/test_gitapex_retro_gate_label_sync.py` (Task D), which imports
both real, on-disk constants by file path and asserts equality -- do not
change this literal here without changing that file's own copy in the
same commit, or that sync test will fail loudly by design.

The ACM body's table header below is written to match
`hooks/gitapex_check_acm_present_or_waiver.py`'s own `_HEADER_RE` exactly
(read directly from that file, not guessed): a `has_acm_disclosure()`
check must be able to recognize the header row this module emits.
"""

from __future__ import annotations

import datetime as _datetime

# The literal label name every `gate-proposal`-classified issue this
# design files carries (Decision 6). Exact-match string -- do not deviate;
# see this module's own docstring for why a second, independent copy of
# this same literal lives in .github/scripts/gitapex_scan_retrospective_gate_drift.py
# and how the two are kept in sync.
GATE_PROPOSAL_LABEL = "gate-proposal"

# Fixed per Decision 4 -- every filed issue states the same proof method,
# since the acceptance bar for "this gate was actually built" is identical
# across every `missing-deterministic-gate` finding this mechanism files.
_PROOF_METHOD = (
    "implementing PR adds the check plus a regression test; confirm it "
    "fails against a reintroduced instance of the original defect, then passes"
)

# Decision 4's own fallback text: "or the fixed string 'none identified'
# if the repair's own text named none."
_RESIDUAL_RISK_NONE_IDENTIFIED = "none identified"

# Byte-for-byte the same column set `hooks/gitapex_check_acm_present_or_waiver.py`'s
# own `_HEADER_RE` recognizes (read directly from that file -- not
# reproduced from memory).
_ACM_HEADER_ROW = "| Criterion | Interpretation | Planned ops | Proof method | Residual risk |"
_ACM_DIVIDER_ROW = "|---|---|---|---|---|"

# Fixed shape of the Step 4b backlog-sweep proof line (issue #1806). The
# line is generated only by `build_dedup_sweep_line` below -- never
# hand-typed at a Step 5 call site -- so the PreToolUse hook
# (`hooks/gitapex_check_gate_proposal_dedup_sweep.py`) can treat its
# presence plus a live count match as proof a fresh backlog sweep ran.
# `timestamp` is UTC `YYYY-MM-DDTHH:MM:SSZ`, validated with `strptime`
# (not a bare digit-shape regex, which would accept month 13).
_DEDUP_SWEEP_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def build_dedup_sweep_line(open_count: int, timestamp: str) -> str:
    """Return the `Dedup-sweep:` proof line for one Step 4b backlog sweep.

    `open_count` is the live count of open `gate-proposal` issues observed
    by the sweep; `timestamp` is when the sweep ran, UTC
    `YYYY-MM-DDTHH:MM:SSZ`. Raises `ValueError` when `open_count` is not
    a non-negative `int` (`bool` excluded explicitly -- `isinstance(True,
    int)` is `True`, and a boolean count is the same contract violation
    `build_gate_proposal_title`'s own 1-based-index check already fails
    loudly on) or when `timestamp` is not a real calendar instant in that
    exact format.
    """
    if isinstance(open_count, bool) or not isinstance(open_count, int):
        raise ValueError(f"open_count must be a non-negative int, got {open_count!r}")
    if open_count < 0:
        raise ValueError(f"open_count must be a non-negative int, got {open_count!r}")
    if not isinstance(timestamp, str):
        raise ValueError(f"timestamp must be ISO-8601 UTC YYYY-MM-DDTHH:MM:SSZ, got {timestamp!r}")
    try:
        _datetime.datetime.strptime(timestamp, _DEDUP_SWEEP_TIMESTAMP_FORMAT)
    except ValueError:
        raise ValueError(f"timestamp must be ISO-8601 UTC YYYY-MM-DDTHH:MM:SSZ, got {timestamp!r}") from None
    return f"Dedup-sweep: {open_count} open gate-proposal issues at {timestamp}; verdict NEW"


def build_gate_proposal_title(
    retrospective_issue_number: int,
    repair_index: int,
    repair_label: str,
) -> str:
    """Return the deterministic, collision-proof issue title for one
    `missing-deterministic-gate` repair (Decision 1).

    Keyed on `repair_index` (the repair's own fixed, 1-based position
    within its cycle's single classification pass), not on
    `repair_label` alone: two distinct repairs in the same cycle can
    produce byte-identical labels (this repository's own worked example,
    `[Failed CI rerun]`/`[Review fix round]`, shows how generic a label
    already is in practice) -- an exact-title search keyed on label text
    alone would then find the *first* repair's issue for the *second*
    repair too, and silently skip filing the real, second finding. The
    index is what actually disambiguates; the label stays in the title
    only for human readability.

    Raises `ValueError` if `repair_index` is not a positive integer --
    Decision 1's own "1-based index" contract is the one property this
    whole title-collision fix depends on, so a caller passing a 0-based
    or negative index (the exact off-by-one an in-memory index-assignment
    pass could produce) fails loudly here rather than silently minting a
    title indistinguishable from a different repair's own index-1 title.
    """
    if repair_index < 1:
        raise ValueError(f"repair_index must be a 1-based positive integer, got {repair_index!r}")
    return f"gate-proposal: retro #{retrospective_issue_number} repair {repair_index}: {repair_label}"


def _sanitize_cell(value: str) -> str:
    """Collapse embedded newlines to spaces and escape a literal `\\` and
    `|`.

    `has_acm_disclosure()`'s own `_HEADER_RE` only inspects the header
    row (unaffected either way by this function, which is only ever
    applied to a data-row cell), but a repair's free-text field
    (Interpretation/Planned ops/Residual risk) genuinely can contain a
    raw newline or `|` in practice -- left unescaped, either would break
    the Markdown table's column alignment when the issue body actually
    renders on GitHub, not merely fail a downstream check.

    The backslash pass runs **first, and is not optional**: a Markdown
    backslash escapes whatever character follows it, so escaping only the
    pipe turns an input that already reads `\\|` (a proposed gate naming a
    regex, or a `grep 'a\\|b'` alternation -- the realistic shape for a
    gate proposal, not a contrived one) into `\\\\|`: an escaped
    *backslash* followed by a live, unescaped column delimiter, silently
    adding a column and shifting every cell after it. Escaping the
    backslash first makes that same input `\\\\\\|` -- one literal
    backslash, one literal pipe, one cell. Order matters: swapping these
    two `replace` calls would re-escape the backslashes the first pass
    just introduced.
    """
    collapsed = " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    return collapsed.replace("\\", "\\\\").replace("|", "\\|").strip()


def build_gate_proposal_acm_body(
    retrospective_issue_number: int,
    repair_label: str,
    classification_rationale: str,
    proposed_gate_text: str,
    residual_risk: str | None,
    *,
    dedup_sweep_open_count: int,
    dedup_sweep_timestamp: str,
) -> str:
    """Return the fully-populated Acceptance Criteria Map body for one
    `missing-deterministic-gate` repair (Decision 4), mapped directly from
    fields the repair's own classification pass already produced:

    - Criterion      = `repair_label` (the repair's own one-line label)
    - Interpretation = `classification_rationale`
    - Planned ops    = `proposed_gate_text`
    - Proof method   = the fixed `_PROOF_METHOD` string (same for every
      filed issue -- see its own comment above)
    - Residual risk  = `residual_risk`, or `_RESIDUAL_RISK_NONE_IDENTIFIED`
      when the repair's own text named none (empty, `None`, or
      whitespace-only)

    The produced body carries a real ACM table, not a `tracking` waiver:
    per Decision 4, a filed issue is genuine, actionable future work, so
    it must stay closeable-by-citation by a future implementing PR, which
    `hooks/gitapex_check_pr_issue_acm_disclosure.py` specifically denies
    for a `tracking`-waivered issue. The table header matches
    `hooks/gitapex_check_acm_present_or_waiver.py`'s own `_HEADER_RE`
    (verified by this module's own test suite, which imports
    `has_acm_disclosure` directly and asserts it passes on this
    function's own output). A trailing `Refs #<retrospective-issue-number>`
    line supplies the back-link Decision 1/Architecture require.
    """
    residual_risk_text = (
        residual_risk.strip() if residual_risk and residual_risk.strip() else _RESIDUAL_RISK_NONE_IDENTIFIED
    )
    criterion_cell = _sanitize_cell(repair_label)
    interpretation_cell = _sanitize_cell(classification_rationale)
    planned_ops_cell = _sanitize_cell(proposed_gate_text)
    residual_risk_cell = _sanitize_cell(residual_risk_text)
    data_row = (
        f"| {criterion_cell} | {interpretation_cell} | {planned_ops_cell} | {_PROOF_METHOD} | {residual_risk_cell} |"
    )
    # The sweep line trails the body (never interleaved with the table) so
    # rows 0-2 keep fixed positions for existing readers. Free-text fields
    # cannot forge one: `_sanitize_cell` collapses their newlines to
    # spaces, so no second `Dedup-sweep:` line can ever start inside them.
    sweep_line = build_dedup_sweep_line(open_count=dedup_sweep_open_count, timestamp=dedup_sweep_timestamp)
    return "\n".join(
        [
            _ACM_HEADER_ROW,
            _ACM_DIVIDER_ROW,
            data_row,
            "",
            f"Refs #{retrospective_issue_number}",
            "",
            sweep_line,
        ]
    )
