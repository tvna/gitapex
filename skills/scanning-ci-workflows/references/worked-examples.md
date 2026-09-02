# Worked example: one recorded run

A real, end-to-end pass of `scanning-ci-workflows`' own Procedure against
this skill's authoring repository (`tvna/gitapex`), captured on
2026-08-08. Every number, exit code, and quoted line below is transcript
from that run -- nothing here is illustrative.

**Read this as evidence that the Procedure executes and that the two
tools do not overlap, never as a pattern to expect in another target.**
A different repository will produce entirely different findings, and a
finding shape seen here is not a reason to expect or report the same one
elsewhere. The Stop boundary against carrying a conclusion over by
analogy applies to this file specifically.

## Contents

1. [Step 2 -- tool versions](#step-2----tool-versions)
2. [Step 1 -- collected inputs](#step-1----collected-inputs)
3. [Step 3 -- actionlint](#step-3----actionlint)
4. [Step 4 -- zizmor](#step-4----zizmor)
5. [Step 5 -- what the run demonstrates](#step-5----what-the-run-demonstrates)
6. [What the run did not do](#what-the-run-did-not-do)

## Step 2 -- tool versions

```console
$ actionlint --version
1.7.12

$ zizmor --version
zizmor 1.25.2
```

Both match the versions carried by the nixpkgs revision this
repository's own `flake.lock` pins, so the run reflects what the
toolchain actually provisions rather than whatever happened to be on
`PATH`.

## Step 1 -- collected inputs

Two lists, kept apart as the Procedure requires:

- **Workflow files:** 25 under `.github/workflows/` (`*.yml`; no `*.yaml`
  present). Both tools read these.
- **Composite action definitions:** one, at
  `.github/actions/harden-checkout/action.yml`. zizmor only.

## Step 3 -- actionlint

```console
$ actionlint -format '{{json .}}'
[]
exit=0
```

Zero findings. Exit `0`, and the output parses as the expected result
array, so this is a completed run reporting nothing -- not the ambiguous
non-zero case Procedure step 3 warns about.

The split matters, and this target is where it shows. Passing the one
composite action definition to actionlint anyway produces:

```console
$ actionlint .github/actions/harden-checkout/action.yml
.github/actions/harden-checkout/action.yml:1:1: "jobs" section is missing in workflow [syntax-check]
.github/actions/harden-checkout/action.yml:1:1: "on" section is missing in workflow [syntax-check]
exit=1
```

Two findings that are not findings -- actionlint parsed an action
definition against the workflow schema. A run that fed it the whole
collected input set would have reported a syntactically broken
repository. It is not broken.

## Step 4 -- zizmor

```console
$ zizmor --offline --no-progress --format=json .github/workflows/ .github/actions/
exit=14
```

zizmor did collect the composite action -- its own verbose log shows
`registering action input as with key file://.github/actions/harden-checkout/action.yml`, then scheduling
`artipacked`, `unsound-contains`, `excessive-permissions`, and
`dangerous-triggers` against it. It produced no finding there, so the
totals below are identical to a workflows-only run. That is a result
about this target, not a reason to omit the composite-action list next
time.

Exit `14` is a *completed* audit reporting findings at high severity, not
an error. Reading it as a failure, or reading any non-zero as "findings",
is the mistake Procedure step 4 exists to prevent: `1`, `2`, and `3` from
this same tool are run failures.

The same run in `--format=plain` closes with:

```text
67 findings (56 suppressed, 8 unsafe fixes): 7 informational, 0 low, 0 medium, 4 high
```

11 findings surfaced under the default `regular` persona; 56 more were
suppressed by persona and ignore rules. Procedure step 5's reporting
contract requires carrying that suppressed count through, so a reader
knows 11 is the visible subset of 67, not the total.

Findings by audit identifier, from the JSON output:

| Audit | Count | Severity |
|---|---|---|
| `template-injection` | 8 | 7 Informational, 1 High |
| `dangerous-triggers` | 1 | High |
| `unpinned-uses` | 1 | High |
| `github-app` | 1 | High |

The two quotations below are indented code blocks rather than fenced
ones, deliberately and against the usual house style. They reproduce a
tool's own rendering of content that came out of a scanned file, and
this skill's own Stop boundaries require exactly that form for such
material: an indented block cannot be closed early by a backtick run
inside the quoted text, while a fixed-length fence can. The style
inconsistency is the point, not an oversight.

One finding, quoted with its own structure intact:

    error[dangerous-triggers]: use of fundamentally insecure workflow trigger
      --> .github/workflows/post-merge-retro.yml:30:1
       |
    30 | / on:
    ...  |
    36 | |   pull_request_target:
    37 | |     types: [closed]

And the machine-readable form of another, showing exactly which fields
Procedure step 5 requires be carried through unmodified:

    {
     "ident": "unpinned-uses",
     "desc": "unpinned action reference",
     "url": "https://docs.zizmor.sh/audits/#unpinned-uses",
     "determinations": {
      "confidence": "High",
      "severity": "High",
      "persona": "Regular"
     }
    }

The `ident`, `desc`, `confidence`, `severity`, and location are the
tool's own vocabulary. The report reproduces them; it does not translate
them into a gitapex verdict vocabulary.

## Step 5 -- what the run demonstrates

Same repository, same 25 workflow files, same moment: **actionlint
reported 0 findings on the workflow list where zizmor reported 67 across
the workflow list and the composite action.** That is the division of
labor measured rather than asserted. actionlint's audits are about
validity -- schema conformance, expression typing, runner labels,
embedded shell -- and this repository's workflows are valid. zizmor's
audits are about security posture, and validity says nothing about it.

Running only one of the two would have produced a confidently wrong
answer in this exact case: actionlint alone reports a clean repository
that has four high-severity security findings.

The report for this run also carries the offline coverage gap, per the
Procedure: `impostor-commit`, `known-vulnerable-actions`,
`ref-confusion`, and `stale-action-refs` did not run at all, and
`typosquat-uses` ran at reduced confidence, because `--offline` was in
force. The `unpinned-uses` finding above is an offline-capable audit and
is unaffected; a reader must not generalize from it that pinning
coverage was complete.

## What the run did not do

No workflow file was edited. `--fix` was never passed, despite 8 of the
67 findings advertising an available unsafe fix and several more
advertising safe ones. No GitHub token was supplied and no token
environment variable was set. Those are the report-only and offline Stop
boundaries holding in a real run, on a target where the tool actively
offered to do otherwise.
