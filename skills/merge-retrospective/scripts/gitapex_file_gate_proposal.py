#!/usr/bin/env python3
"""Build the deterministic title and Acceptance Criteria Map body for a
`missing-deterministic-gate` retrospective repair's family
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
import re as _re
from collections.abc import Iterable, Sequence
from typing import NamedTuple

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

# The only verdicts a created issue can truthfully carry: `NEW` (a new
# family issue), or `DUPLICATE-OF #<N>` (issue #2097: a repair recorded
# on an existing family issue gets its own standalone issue, immediately
# closed as a duplicate of #N -- the GitHub-native relation the
# escalation count is derived from). `ABSORBED-BY` lands as a
# `DUPLICATE-OF` the mechanism's `extend` issue once that issue exists,
# and `RECLASSIFY`/`ALREADY-SHIPPED` never file, so none of them has a
# line shape here.
_DEDUP_SWEEP_VERDICT_RE = _re.compile(r"^(?:NEW|DUPLICATE-OF #[1-9]\d*)\Z")

# Reads the generator-made sweep line back out of a filed body. Parallel
# to the hook's own recognizer; only a body with exactly one such line
# names a duplicate target.
_DEDUP_SWEEP_LINE_RE = _re.compile(
    r"^Dedup-sweep: \d+ open gate-proposal issues at \S+; verdict (NEW|DUPLICATE-OF #([1-9]\d*))$",
    _re.MULTILINE,
)

# The label a family issue gets once `count_family_occurrences` reaches
# `ESCALATION_THRESHOLD` (issue #2097). Like `GATE_PROPOSAL_LABEL`, a
# parallel copy lives in
# .github/scripts/gitapex_scan_gate_proposal_consolidation_drift.py, kept
# in sync by tests/test_gitapex_retro_gate_label_sync.py.
GATE_PROPOSAL_ESCALATED_LABEL = "gate-proposal-escalated"
# 3 is the owner-selected threshold in issue #2097, counting the original
# filing: a third occurrence of one family is the next work item.
ESCALATION_THRESHOLD = 3

# An ssot gate id, as `.gitapex/ssot.json` spells them (lowercase words
# joined by hyphens). Anything else is refused rather than interpolated
# into an exact-match title.
_GATE_ID_RE = _re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def build_dedup_sweep_line(open_count: int, timestamp: str, verdict: str = "NEW") -> str:
    """Return the `Dedup-sweep:` proof line for one Step 4b backlog sweep.

    `open_count` is the live count of open `gate-proposal` issues observed
    by the sweep; `timestamp` is when the sweep ran, UTC
    `YYYY-MM-DDTHH:MM:SSZ`; `verdict` is the Step 4b verdict this filing
    records: `NEW` or `DUPLICATE-OF #<N>`. Raises `ValueError` when
    `open_count` is not a non-negative `int` (`bool` excluded explicitly --
    `isinstance(True, int)` is `True`, and a boolean count is the same
    contract violation `build_gate_proposal_title`'s own 1-based-index
    check already fails loudly on), when `timestamp` is not a real
    calendar instant in that exact format, or when `verdict` names a
    non-filing outcome.
    """
    # function-body-test-coverage: WAIVED: covered by tests/test_gitapex_dedup_sweep_generator_hook_agreement.py
    # (same diff, commit 422cdfe) via builder.build_dedup_sweep_line -- a differently-named integration test
    # file this gate's own tests/test_{stem}.py naming convention does not scan.
    if isinstance(open_count, bool) or not isinstance(open_count, int) or open_count < 0:
        raise ValueError(f"open_count must be a non-negative int, got {open_count!r}")
    if not isinstance(timestamp, str):
        raise ValueError(f"timestamp must be ISO-8601 UTC YYYY-MM-DDTHH:MM:SSZ, got {timestamp!r}")
    try:
        _datetime.datetime.strptime(timestamp, _DEDUP_SWEEP_TIMESTAMP_FORMAT)
    except ValueError:
        raise ValueError(f"timestamp must be ISO-8601 UTC YYYY-MM-DDTHH:MM:SSZ, got {timestamp!r}") from None
    if not isinstance(verdict, str) or not _DEDUP_SWEEP_VERDICT_RE.match(verdict):
        raise ValueError(f"verdict must be NEW or DUPLICATE-OF #<N>, got {verdict!r}")
    return f"Dedup-sweep: {open_count} open gate-proposal issues at {timestamp}; verdict {verdict}"


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


class FamilyRow(NamedTuple):
    """One repair's own fields, as its classification pass produced them.
    A family issue carries one ACM row per member repair (issue #2097), so
    a cluster never collapses two repairs into one summary row.

    A `NamedTuple`, not a dataclass: sibling tests load this module by
    file path without registering it in `sys.modules`, which `@dataclass`
    needs and `NamedTuple` does not."""

    repair_label: str
    classification_rationale: str
    proposed_gate_text: str
    residual_risk: str | None


def _acm_data_row(row: FamilyRow) -> str:
    """Map one repair onto the Decision 4 columns:

    - Criterion      = `repair_label` (the repair's own one-line label)
    - Interpretation = `classification_rationale`
    - Planned ops    = `proposed_gate_text`
    - Proof method   = the fixed `_PROOF_METHOD` string (same for every
      filed issue -- see its own comment above)
    - Residual risk  = `residual_risk`, or `_RESIDUAL_RISK_NONE_IDENTIFIED`
      when the repair's own text named none (empty, `None`, or
      whitespace-only)
    """
    stripped_risk = (row.residual_risk or "").strip()
    residual_risk_text = stripped_risk if stripped_risk else _RESIDUAL_RISK_NONE_IDENTIFIED
    criterion_cell = _sanitize_cell(row.repair_label)
    interpretation_cell = _sanitize_cell(row.classification_rationale)
    planned_ops_cell = _sanitize_cell(row.proposed_gate_text)
    residual_risk_cell = _sanitize_cell(residual_risk_text)
    return f"| {criterion_cell} | {interpretation_cell} | {planned_ops_cell} | {_PROOF_METHOD} | {residual_risk_cell} |"


def build_gate_proposal_family_acm_body(
    retrospective_issue_number: int,
    rows: Sequence[FamilyRow],
    *,
    dedup_sweep_open_count: int,
    dedup_sweep_timestamp: str,
    dedup_sweep_verdict: str = "NEW",
) -> str:
    """Return the Acceptance Criteria Map body for one family issue: every
    member repair of a verified CLUSTER (or a lone NEW repair) gets its
    own row, in the order given (issue #2097, row 1).

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

    Raises `ValueError` on an empty `rows`: a family issue with no member
    repair has nothing to propose.
    """
    if not rows:
        raise ValueError("rows must name at least one member repair")
    # The sweep line trails the body (never interleaved with the table) so
    # the header and first data row keep fixed positions for existing
    # readers. Free-text fields cannot forge one: `_sanitize_cell`
    # collapses their newlines to spaces, so no second `Dedup-sweep:` line
    # can ever start inside them.
    sweep_line = build_dedup_sweep_line(
        open_count=dedup_sweep_open_count, timestamp=dedup_sweep_timestamp, verdict=dedup_sweep_verdict
    )
    return "\n".join(
        [
            _ACM_HEADER_ROW,
            _ACM_DIVIDER_ROW,
            *(_acm_data_row(row) for row in rows),
            "",
            f"Refs #{retrospective_issue_number}",
            "",
            sweep_line,
        ]
    )


def build_gate_proposal_acm_body(
    retrospective_issue_number: int,
    repair_label: str,
    classification_rationale: str,
    proposed_gate_text: str,
    residual_risk: str | None,
    *,
    dedup_sweep_open_count: int,
    dedup_sweep_timestamp: str,
    dedup_sweep_verdict: str = "NEW",
) -> str:
    """Return the Acceptance Criteria Map body for a single-member family
    -- `build_gate_proposal_family_acm_body` with exactly one row."""
    # function-body-test-coverage: WAIVED: covered by tests/test_gitapex_dedup_sweep_generator_hook_agreement.py
    # (same diff, commit 422cdfe) via builder.build_gate_proposal_acm_body -- a differently-named integration
    # test file this gate's own tests/test_{stem}.py naming convention does not scan.
    return build_gate_proposal_family_acm_body(
        retrospective_issue_number,
        [FamilyRow(repair_label, classification_rationale, proposed_gate_text, residual_risk)],
        dedup_sweep_open_count=dedup_sweep_open_count,
        dedup_sweep_timestamp=dedup_sweep_timestamp,
        dedup_sweep_verdict=dedup_sweep_verdict,
    )


def build_absorption_family_title(gate_id: str) -> str:
    """Return the exact title of the one family issue that collects
    follow-up rows for a generic mechanism (ABSORBED-BY, issue #2097).

    One title per mechanism, so the exact-title search finds the same
    issue on every run and absorbed repairs never multiply issues. Raises
    `ValueError` when `gate_id` is not an ssot-shaped id.
    """
    if not isinstance(gate_id, str) or not _GATE_ID_RE.match(gate_id):
        raise ValueError(f"gate_id must be an ssot gate id (lowercase, hyphen-joined), got {gate_id!r}")
    return f"gate-proposal: extend {gate_id}"


def duplicate_target(body: str) -> int | None:
    """Return #N when `body` carries exactly one generator-made
    `Dedup-sweep: ...; verdict DUPLICATE-OF #N` line, else `None`.

    Only meaningful for an issue that carries `GATE_PROPOSAL_LABEL` and
    was opened by the account this procedure posts as: an issue's author
    can rewrite its body at any time, so only a body this procedure
    wrote, via `build_gate_proposal_acm_body` (whose free-text cells
    cannot start a second sweep line), names a trustworthy target."""
    matches = list(_DEDUP_SWEEP_LINE_RE.finditer((body or "").replace("\r\n", "\n")))
    if len(matches) != 1 or matches[0].group(2) is None:
        return None
    return int(matches[0].group(2))


def count_family_occurrences(duplicate_titles: Iterable[str]) -> int:
    """Return how many repairs one family issue records: 1 for its own
    original filing plus one per distinct title among the issues closed
    as its duplicates (issue #2097, owner decision: the original filing
    counts toward the threshold).

    The caller passes only issues that carry `GATE_PROPOSAL_LABEL`, are
    closed with `state_reason: duplicate`, and name this family as their
    duplicate target -- all three set by push- or triage-gated actions,
    none read from free text anyone can write. Titles are
    `build_gate_proposal_title` output, keyed on retrospective and repair
    index, so a repair filed twice by concurrent runs counts once."""
    return 1 + len({title.strip() for title in duplicate_titles if title and title.strip()})


def needs_escalation(occurrence_count: int) -> bool:
    """True once a family has recurred often enough to be the next work
    item rather than one more recorded recurrence."""
    return occurrence_count >= ESCALATION_THRESHOLD
