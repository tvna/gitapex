# Gate-Proposal Filing Mechanics

Step 5's own detail for filing each `missing-deterministic-gate` repair
as its own standalone issue, plus the failure/resume and close-condition
rules that govern it.

## Filing each missing-deterministic-gate repair as its own standalone issue

In index order, call
`skills/merge-retrospective/scripts/gitapex_file_gate_proposal.py`
(pure, network-free -- see Prerequisite) with that repair's index,
one-line label, Classification rationale, Proposed gate text, any
residual risk already noted in this repair's own prose (or none),
this retrospective issue's own number, and the Step 4b sweep's
open-issue count, timestamp, and verdict for this repair, to get
back a deterministic title, an Acceptance Criteria Map body with
the generator-made `Dedup-sweep:` line (never hand-typed), and
the `gate-proposal` label constant -- the script itself never
calls `issue_write` or `issue_read`. Then, as direct
`mcp__github__*` tool calls:

- Search for an issue with that **exact** title, never substring.
- **No match:** create it with the script's own title, body, and
  label (regenerating the sweep line per create -- reusing one
  filing's line self-denies as stale), then re-fetch to confirm
  it exists before recording anything as filed.
- **Exactly one match:** confirm its body still carries an
  Acceptance Criteria Map first; a title match without one
  fails closed and escalates instead of recording filed.
- **More than one match:** fail closed and escalate -- the same
  discipline as Step 0's own ambiguous-stub-match handling.
  Never guess which one is authoritative, and never file a third.

Once a filing is confirmed (created-and-verified, or already
existed), record `Filed as: #<issue number>` immediately alongside
that repair's own `Status: missing-deterministic-gate` line in this
retrospective issue's body -- add it there; never remove or replace
the `Status:` line itself. `issue_write` has no native append
primitive: this "add" is always a whole-body rewrite, so re-fetch
this retrospective issue's own current body immediately before
this write and merge only this repair's own `Filed as:` line into
it, never reusing an earlier read -- a concurrent run recording a
different repair's own `Filed as:` line in the same body window
would otherwise be silently overwritten by a write built from a
stale copy. A DUPLICATE-OF #N filing closes
immediately after its create (`state_reason: duplicate`,
referencing #N); the 4b.3 umbrella append stays best-effort,
never the record itself.

## A failed or unconfirmed filing blocks that repair's line, not the rest of the cycle -- and blocks closing

If the script cannot compute a value for a repair (a required
classification field is missing), if the create call itself fails, or if
a write cannot be confirmed by re-fetch (treat an unconfirmed write as a
failure, the same as an outright one) -- skip only that repair's
`Filed as:` line and continue with the rest. Never close the retrospective
issue while any `missing-deterministic-gate` repair from this cycle
still lacks a confirmed `Filed as:` line. A later, resumed run retries
only the repairs still missing one -- but a `Filed as: #<N>` line
already present in this retrospective issue's own body is itself
untrusted state, not proof: the body is externally editable between runs
(a careless edit, or a hostile one), so re-fetch issue `#<N>` and
confirm it still exists with the `gate-proposal` label and this
repair's exact title before skipping it, under the same re-fetch
discipline this step already requires. A re-fetch that cannot complete
at all (a network/API error) is not the same finding as a completed
re-fetch that comes back mismatched or absent, but is handled
identically -- named separately here only so a reader does not assume
otherwise: neither one proves the filing is real, so both fall through
to the same re-file path rather than one silently trusting an
inconclusive check. A `Filed as:` line that does not re-verify this way
is treated exactly like an unconfirmed write: proceed to (re-)file that
repair through the exact-title search and create-or-match flow above, as
if the line were absent, rather than trusting its mere presence. The
exact-title search above is the backstop against a duplicate either way.

## Close condition

Close once every `missing-deterministic-gate` repair from this cycle
carries a confirmed `Filed as:` line (zero such repairs is the trivial
case). This follows the same attended/unattended rule the fast-close
path (`references/zero-repair-fast-close.md`) already uses, now extended
to every close this step performs, not only the zero-repair case: when
an operator is present to respond, preview the exact drafted body -- the
repair list, every filed-issue number, or the zero-repair paragraph --
and wait for an explicit go-ahead before calling close. When running
fully unattended with no operator able to respond, file everything above
but leave the retrospective issue open for a human to close after
review; never let a fully unattended context both draft the "everything
is filed" conclusion and act on it with nobody positioned to catch a
wrong call.
