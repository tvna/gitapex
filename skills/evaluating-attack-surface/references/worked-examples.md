# Worked examples

Explicitly repository-scoped, per this skill's own Portability
declaration (`metadata/gitapex.yaml`: `portability: Mixed`). Every path
and script name below is gitapex's own -- an illustrative example of the
portable checks in `SKILL.md`, not an assumption that a target repository
being reviewed has the same layout. Substitute the target's actual
equivalents; do not expect these specific files to exist elsewhere.

## Worked example: `.github/workflows/post-merge-retro.yml`

**Exposure minimization.** The create-issue POST body (built in
`.github/scripts/post_merge_retro.py`) sends owner, repo, PR number, PR
title, and PR URL. `pr_title` is received but deliberately never placed
in the created issue body -- the script's own docstring states why: "it
is untrusted, fork-controlled text, and republishing it verbatim would
let an `@user`/`@org` mention or Markdown in the title inject formatting
or trigger unwanted notifications." **Verdict: exposure-minimal** for the
issue-body field -- the one plausibly over-exposable field is deliberately
excluded, with a cited reason, not merely omitted by chance. One
caveat, named rather than folded into a false all-clear: the workflow's
`harden-runner` step sets `egress-policy: audit`, not `block` -- network
egress from this job is observed, not restricted, so this specific
control is detective, not preventive.

**Least privilege.** `permissions: contents: read, issues: write` is
declared at both workflow and job level, matching the job's only two
actions -- checking out code (read) and opening one deduplicated issue
(write). The workflow's own code comment states the constraint's
rationale directly: it deliberately does not have, and must never be
given, `pull-requests: write` or merge capability, because "100% human
review before any PR merges in this repository is a PERMANENT
architectural feature." **Verdict: privilege-minimal** -- the granted
scope traces exactly to the two actions performed, and the boundary's own
rationale is already documented in the artifact itself rather than left
for a reviewer to infer.
