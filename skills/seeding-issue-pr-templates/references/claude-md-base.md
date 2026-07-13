# claude-md canonical base (platform-neutral)

Distilled from tvna/claude-md's template set. Used as the STARTING base,
then right-sized per target repo. claude-md's server-side enforcement
scripts (body_policy.py, preflight_pr_template_shape.py) are deliberately
NOT copied -- see right-sizing-and-gate-gap.md.

## Issue types (offer a subset; never invent extras)
- feat     -- new capability
- fix      -- defect repair
- chore    -- maintenance, deps, tooling
- docs     -- documentation only
- refactor -- behavior-preserving restructure
- tracking -- umbrella/parent issue coordinating sub-work
- generic  -- fallback for anything above categories

## PR/MR section catalog (abstract; keep only what the repo will use)
- Summary            -- conclusion in 1-2 sentences
- Facts              -- observable evidence only (diffs, test output)
- Assumptions        -- unverified trusts, tagged speculation
- Risk / blast radius-- who/what breaks if this fails
- Rollback           -- exact revert/disable steps
- Verification       -- command + result pairs
- Checklist          -- pre/after/post-merge gates the repo actually has
- Related Issue      -- Closes/Refs the issue number
- (heavy, default OFF) Resource Consumption, Text delta

## Right-sizing rule
Keep a section only if the target repo can act on it. Drop the rest and
record each dropped invariant in the Gate Gaps output.
