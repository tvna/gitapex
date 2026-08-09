# Absorb auditing-git-hosting-surface into scanning-attack-surfaces

**Goal:** Fold `auditing-git-hosting-surface`'s full capability into the
already-renamed `scanning-attack-surfaces`, delete the standalone skill,
back the surviving skill's least-privilege check with zizmor, and
re-point every live inbound reference in the same change. Source:
https://github.com/tvna/gitapex/issues/848.

**Architecture:** No new directories. One skill directory grows (three
reference files, a `scripts/` directory, and a merged `SKILL.md`), one
skill directory is deleted, one eval corpus absorbs another's four
tasks, and two hardcoded CI paths follow the relocated script.

## Facts established live, this session

Each row was verified directly in this session against the working tree,
not recalled from the issue's own snapshot.

| Fact | How it was established |
|---|---|
| Both blockers landed | Issues #846 and #847 both read `state: closed`, `state_reason: completed` |
| The reference count is 34, not the issue's 28 | `grep -rl auditing-git-hosting-surface` excluding `.venv`/`.git`; #846 and #847 each added references after the issue was filed. The issue's own residual-risk row predicted exactly this and required a live re-run |
| The rename-lifecycle gate does not fire | `.github/workflows/skill-rename-lifecycle-gate.yml` sets `applicable=true` only when `[ -s "$removed_file" ] && [ "$added_count" -gt 0 ]`. This diff removes one skill directory and adds none |
| No `references/` filename collision | `scanning-attack-surfaces/references/` held only `worked-examples.md`; the three incoming files are `github-surface-checklist.md`, `gitlab-surface-checklist.md`, `gitapex-cross-links.md` |
| No eval task filename collision | The 11 surviving task files and the 4 incoming ones share no basename; the incoming four were still renamed with a `hosting-surface-` prefix so the two modes stay distinguishable in a run report |
| `scanning-attack-surfaces` is security-relevant | `gitapex_skill_security_relevance.py --path skills/scanning-attack-surfaces/SKILL.md` prints `relevant`, exit 0 -- so `adversarial-coverage-mapping` disclosure applies, computed rather than judged by eye |
| zizmor's real invocation contract, and a real finding | zizmor 1.29.0 run live against `.github/workflows/sync-agent-instructions.yml`: exit 14, `github-app` at High confidence, "app token inherits blanket installation permissions" at line 91 |
| **The issue understated the reference sweep in one place** | `docs/scanning-capability-selection-policy.md` (landed by #847, after this issue was filed) carries four references the issue never enumerated, including the canonical platform-detection citation. All four are updated here |

## The two design questions the issue left open

Both were named in the issue's own Acceptance Criteria Map as residual
risks that its implementing pass had to resolve explicitly rather than
default into. Both are resolved here and recorded in
`skills/scanning-attack-surfaces/metadata/gitapex.yaml`.

### 1. Merged verdict style

The absorbed skill reported `Covered`/`Partial`/`Gap` per checklist item.
The absorbing skill reports `exposure-minimal`/`exposure-excess` and
`privilege-minimal`/`privilege-excess` per item. Neither vocabulary is a
superset of the other, and concatenating both unreconciled was the
failure mode the issue's Non-goals section explicitly barred.

**Resolution: two named modes, one shared reporting discipline.** Mode A
is artifact exposure and privilege; Mode B is a repository's standing
hosting-platform surface. Mode selection is read off the target kind, not
chosen by preference. Each mode keeps its own vocabulary; the two are
never merged into one ranked list or one headline. What they share is
made explicit and binding: per item never aggregate, never upgrade an
unproven item, read-only.

The two procedures are labelled `A1`-`A4` and `B1`-`B4` rather than both
using bare "step 1", which is also what keeps
`gitapex_check_skill_shape.py`'s `no-step-location-contradiction` check
satisfied with two procedures in one file.

### 2. zizmor's scope boundary

zizmor covers GitHub Actions workflows and composite actions. It covers
none of the other artifact types this skill reviews. Declaring
`shell: [zizmor]` without saying so would imply tool backing the skill
does not have.

**Resolution:** the least-privilege check gains a sub-section naming the
sub-case precisely -- workflow and composite-action artifacts only,
invoked `--offline --no-progress --format=json` -- and requires every
report to state, per artifact, whether the check was tool-backed or
manual. A missing binary is a named fallback, never a clean result. The
`--offline`, no-token, no-`--fix` constraints are Stop boundaries, which
is what makes the absent `network` declaration true rather than merely
claimed.

This also required correcting `scanning-ci-workflows`, whose own
description and Related-skills bullet asserted that
`scanning-attack-surfaces` "wraps no tool". That is now false, and both
places say what is actually true: this skill reads a subset of one tool's
findings as evidence for one per-item verdict, while that skill reports
both tools' complete findings over a whole input set.

## What is updated, and what is deliberately left alone

The live/historical split follows the practice #846's own rename commit
recorded and justified: operative pointers are updated, historical
audit-trail prose is not.

**Updated (operative):** three sidecars' `relatedTo` entries (gate-enforced
by `skill-dependencies-resolve`), `scanning-ci-workflows`' description and
Related-skills bullet, `auditing-agent-product-scope`'s description,
Related-skills bullet, Notes citation and all three
`references/gitapex-cross-links.md` mentions,
`screening-a-low-trust-contribution`'s five body mentions,
`docs/agent-product-scope.md`'s Axis E, `docs/glossary.md`'s `Auditing-*`
example list and `Scanning-*` partial-membership note,
`docs/scanning-capability-selection-policy.md`'s four references,
`docs/skill-eval-status.md`'s index row, the live
`platform-routing-probe.yaml` eval assertion, `.github/workflows/test.yml`'s
mypy step, `.github/scripts/gitapex_run_precommit_mypy.py`'s path tuple and
its test, and `.test_durations`' two now-unreachable node IDs.

**Left unchanged (historical records):** six dated `docs/superpowers/`
plans, specs and notes; `evals/screening-a-low-trust-contribution/eval-status.md`'s
narrative; `docs/glossary.md`'s `#459` rename-provenance note and the
`Vetting-*` lineage paragraph's historical sentence (extended with the
absorption rather than rewritten); and the `spec.references` provenance
summaries in two sidecars that describe what was true when they were
written.

## Disclosed, not fixed

`skills/scanning-attack-surfaces/scripts/test_gitapex_scan_unpinned_actions.py`
carries `test_repository_workflows_are_pin_clean`, which fails against
this repository's own workflows today:
`.github/workflows/ranking-the-open-queue-weekly.yml:49` uses
`anthropics/claude-code-action@v1`, a tag rather than a 40-character SHA.
Confirmed pre-existing by running the scanner at the base commit, before
any change here.

That test has never executed in CI, before or after this change: its
directory was not in `[tool.pytest.ini_options] testpaths` under the old
skill name and is not added under the new one. Preserving that exactly is
deliberate -- adding the path would turn a pre-existing repository
condition into a failure of this refactor's own PR, which is neither this
issue's scope nor a decision this change should make on its own. Both the
unpinned action and the untested test path are named here so neither
reads as coverage this change silently acquired.

## Verification

- `gitapex_check_skill_shape.py`: 45/45 on `scanning-attack-surfaces`,
  39/39 on `scanning-ci-workflows`, 41/41 on
  `auditing-agent-product-scope`, 40/40 on
  `screening-a-low-trust-contribution`.
- `gitapex_gate_local_preflight.py`: all 19 wired gates PASS.
- `pytest`: 3583 passed.
- `gitapex_lint_fixture_assertions.py`: 4 warnings, all pre-existing and
  in unrelated skills.
- `gitapex_gate_skill_audit_disclosure.py --check-diff`: run against the
  drafted PR body before the PR is opened.
