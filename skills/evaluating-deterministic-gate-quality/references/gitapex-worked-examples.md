# gitapex's own worked examples

Explicitly repository-scoped, per this skill's own Portability declaration
(`metadata/gitapex.yaml`: `portability: Mixed`). Every path, script name,
and issue number below is gitapex's own -- an illustrative example of the
portable categories in `SKILL.md` and `references/`, not an assumption
that a target repository being reviewed has the same layout. Substitute
the target's actual equivalents; do not expect these specific files to
exist elsewhere. Every elided issue number in a quote below is recorded
once in `metadata/gitapex.yaml`'s sidecar, per this skill's own
no-bare-citation rule for body prose -- in-body mentions are marked
`[elided]` rather than repeating that rule each time.

Source: `docs/superpowers/reports/2026-07-27-hook-evaluation-quality-research.md`
(the adversarially-verified research report this skill's model is built
from). Quotes below were independently re-verified against the live
repository files during that report's own review rounds, not merely
copied from the report's own text.

## Contents

1. [Worked example: Reproducibility / Domain-coverage axis](#worked-example-reproducibility--domain-coverage-axis-argued-multi-domain-coverage)
2. [Worked example: retrospective-identity, single-source-of-truth predicate](#worked-example-retrospective-identity-single-source-of-truth-predicate)
3. [Worked example: mechanism-fit criterion 5 and sibling-repository provenance](#worked-example-mechanism-fit-criterion-5-precedent-reuse-and-sibling-repository-provenance)
4. [Worked example: dimension 12, redistribution-boundary-aware resolution](#worked-example-dimension-12-redistribution-boundary-aware-resolution)
5. [Smoke test: this skill applied to a real Domain-2 gate](#smoke-test-this-skill-applied-to-a-real-domain-2-gate)
6. [Worked example: Security-level / Zero-Trust maturity classification axis](#worked-example-security-level--zero-trust-maturity-classification-axis-this-repositorys-own-established-ceiling)
7. [Worked example: dimension 19 (runtime-cost optimization) applied to the same Domain-2 gate pair](#worked-example-dimension-19-runtime-cost-optimization-applied-to-the-same-domain-2-gate-pair)
8. [Audit history: Security-level axis hardening round](#audit-history-security-level-axis-hardening-round)
9. [Worked example: dimension 21 (gate precision audit), cited from the source paper](#worked-example-dimension-21-gate-precision-audit-cited-from-the-source-paper)
10. [Worked example: dimension 22 (firing-share attribution), cited from the source paper](#worked-example-dimension-22-firing-share-attribution-cited-from-the-source-paper)
11. [Worked example: Contract role / input-domain closure axis, and its sibling-repository prior art](#worked-example-contract-role--input-domain-closure-axis-and-its-sibling-repository-prior-art)

## Worked example: Reproducibility / Domain-coverage axis (argued, multi-domain coverage)

The ACM-disclosure policy -- "does an issue body carry an Acceptance
Criteria Map or an explicit waiver" -- is realized three times in this
repository:

| Realization | Domain | Trust/coverage property |
|---|---|---|
| `skills/drafting-issues/SKILL.md` | (per-session, not domain-scoped) | Probabilistic -- depends on the agent choosing to invoke the skill |
| `hooks/check-issue-acm-disclosure.sh` | 2 (agent-harness hook) | Environment-scoped -- fires only where this repository's own hook harness is loaded |
| `.github/scripts/gitapex_gate_acm_issue_disclosure.py` | 3 (CI/CD) | Environment-independent -- fires on the `issues` webhook regardless of which client created the issue |

`gitapex_gate_acm_issue_disclosure.py`'s own docstring states the rationale for
needing all three explicitly (lines 5-12; verbatim except two `[elided]`
backing-issue numbers): "[a prior investigation] found that no workflow
in this repository triggers on `issues:` events, so a missing ACM on an
issue body... had no
universal, environment-independent backstop -- only a per-session
skill-trigger (probabilistic) and a PreToolUse hook (the paired
agent-harness hook mentioned above, which only fires where this repo's
own hook harness is loaded). This script is that backstop's check-and-act
half." This is **deliberate,
argued, three-domain coverage** -- the model for what a "good"
Reproducibility score looks like: not just multiple realizations, but a
stated reason each one is needed.

Also fail-closed on a missing companion, confirmed directly in
`hooks/check-issue-acm-disclosure.sh:54-56`: the hook denies, with a
named reason, if its own companion script
`hooks/gitapex_check_acm_present_or_waiver.py` is not found -- rather than
silently defaulting to allow when a dependency it needs is absent.
Dimension 15 (fail-closed default) applied to a real gate.

## Worked example: retrospective-identity, single-source-of-truth predicate

`.github/scripts/gitapex_scan_retrospective_gate_drift.py`'s own docstring (lines
4-8; verbatim except four `[elided]` issue numbers): "[an issue, itself
referencing
three earlier ones]: `merge-retrospective`'s Step 0 requires, every
cycle, a manual search of every `retrospective`-labelled issue for a
commit on `main` citing it. [The first of those earlier issues] proposed
automating this as a meta-gate; [the other two] each ran that search by
hand again and confirmed the meta-gate itself was never built." This is
a bottom-up-discovered gate: three separate incidents (an original
proposal, then two independent re-derivations of the same need) before
the standing check was actually built -- a real
example of the "Top-down model, bottom-up discovery" pattern this skill's
research history documented (top-down for finalizing what "good" means;
bottom-up for discovering which specific gates are missing).

This is also the pattern this skill recommends any target repository
build for its own coverage-attestation findings: a *standing*,
drift-detecting meta-gate, not only a one-time audit.

## Worked example: mechanism-fit criterion 5 (precedent reuse) and sibling-repository provenance

`.github/scripts/gitapex_gate_owasp_asi_mapping.py:4` (verbatim except one
`[elided]` backing-issue number): "[an issue] ports `tvna/claude-md`'s
OWASP Agentic Top 10 mapping..." --
`.github/scripts/gitapex_gate_owasp_llm_mapping.py:6-11` (verified verbatim)
calls itself "a **sibling** gate to `gitapex_gate_owasp_asi_mapping.py`, not an
extension of it... Same discipline as the ASI gate -- completeness only...
never correctness." Both gates port a mapping discipline from a sibling
repository (`tvna/claude-md`) rather than inventing gitapex's own from
scratch -- a real example of mechanism-fit criterion 5 (precedent reuse,
adapted for local constraints): reusing an already-battle-tested pattern
from elsewhere rather than re-deriving one.

## Worked example: dimension 12, redistribution-boundary-aware resolution

`hooks/gitapex_check_skill_audit_disclosure_or_waiver.py`'s own docstring
(verified verbatim except two `[elided]` spans: a mid-docstring paragraph
about a later applicability-computation move, and a trailing clause about
a second, unrelated sync-tested file family -- neither bears on this
worked example's own point):
"Per docs/repository-layout.md, only skills/ and hooks/ are deployed
runtime primitives when this repository is installed as a plugin --
.github/ is dev-only CI tooling and is never installed into a consumer
repository. [elided] **Deliberately not imported** from
.github/scripts/gitapex_gate_skill_audit_disclosure.py or any other copy:
this file must work standalone from inside a distributed plugin bundle
with no access to .github/. **Kept in sync** with that script's own
[elided] logic by
`tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py`[elided]."

This is dimension 12 resolved correctly under a redistribution-boundary
mismatch: `.github/scripts/gitapex_gate_skill_audit_disclosure.py` (never
deployed) and `hooks/gitapex_check_skill_audit_disclosure_or_waiver.py`
(deployed, or being engineered ahead of the boundary going live) implement
overlapping policy logic. Consolidating them into one shared module would
force the never-deployed side's import path onto the deployed side,
breaking its standalone-execution guarantee. Instead, the two stay
deliberately independent, and a dedicated parity test
(`tests/test_gitapex_check_skill_audit_disclosure_hook_sync.py`) asserts
their policy-relevant logic stays in sync -- duplication named and backed
by an automated synchronization check, exactly this dimension's bar,
without crossing the boundary. A ponytail-audit-style pass (a generic,
product-code-oriented minimalism sweep -- see `dimensions.md` dimension
12's own redistribution-boundary clause) proposed consolidating a
different, `.github/scripts/`-only cluster of duplicated GitHub-API-retry
logic and initially missed that one of the proposed carriers had this
exact same hooks/-vs-.github/ mismatch; the sibling pattern above is what
caught it on review.

## Smoke test: this skill applied to a real Domain-2 gate

Recorded below after this skill's own build: a fresh, isolated dispatch
followed this skill's procedure (`SKILL.md`) against
`hooks/check-issue-acm-disclosure.sh` and
`hooks/gitapex_check_acm_present_or_waiver.py`, given only this skill's own files
(`SKILL.md`, `references/dimensions.md`, `references/mechanism-fit.md` --
this file was deliberately withheld from that dispatch to avoid
contaminating a fresh grading pass with pre-cooked answers) -- not this
build's own conversation history -- as input. This is the live proof the
built procedure is actually followable and produces real, evidence-cited
output, not only that the files parse. The dispatch ran live commands
(including piping malformed input directly into the hook script) and
fetched Claude Code's own primary documentation rather than relying on
memory -- it found a genuine, previously-undocumented bug in the graded
hook, which is exactly the kind of real finding a smoke test is meant to
prove the procedure can surface, not something staged for this record.

### Smoke-test verdict, quoted in full

**Target:** `hooks/check-issue-acm-disclosure.sh` +
`hooks/gitapex_check_acm_present_or_waiver.py` (Domain 2, agent-harness hook).

**Step 1, Discover:** `hooks/hooks.json` registers this hook under
`PreToolUse`, matcher `mcp__github__issue_write`, timeout 10s. Its
top-level `description` states it "backs [a specific issue, itself a
sub-issue of an earlier one]: blocking a new-issue-creation tool call
whose body lacks an Acceptance Criteria Map or an explicit waiver" (two
`[elided]` issue numbers). The hook shells out to its sibling
`gitapex_check_acm_present_or_waiver.py` and denies via `exit 2` if absent. This
is a Domain-2 artifact paired with a documented Domain-3 CI backstop
(`.github/workflows/acm-issue-gate.yml` +
`.github/scripts/gitapex_gate_acm_issue_disclosure.py`, its own backing issue
also recorded in the sidecar).

**Step 2, Deterministic-gate mechanism-fit check:** all six criteria PASS, well-argued --
reversibility window (only a pre-action hook can block issue creation
before it happens), capability match (the paired CI gate's own comment
states it "can only comment/label after the fact, never block it"),
credential/trust asymmetry (Domain 2 fails cheap, Domain 3 holds
`GITHUB_TOKEN` as the guaranteed-credential backstop), tool-surface
availability, precedent reuse (an identical `deny()` pattern is shared
with the sibling `Bash`-matcher hook, confirmed byte-for-byte), and
prose-rule-to-gate mapping. The framework's own named gap
(client-independence) is filled correctly here: the CI backstop triggers
on the raw `issues:` webhook, independent of which client created the
issue. **Verdict: correct domain, deliberately paired, argued rather
than accidental.**

**Step 3, Two-lane walk -- headline findings only (full 6+11 walk
available in this dispatch's own retained report):**

- Deterministic-shape checks 1, 3, 4, 5, 6: PASS.
- Deterministic-shape check 2 (dual-signal deny): **FAIL.** The script's
  own header comment claims it denies "via the PreToolUse
  hookSpecificOutput JSON on stdout AND exit 2 / stderr (both
  conventions...)," but the code only ever writes JSON to stderr (`>&2`),
  never stdout -- and Claude Code's own live-fetched docs state that on
  an `exit 2` path, "Claude Code ignores stdout and any JSON in it...
  stderr text is fed back to Claude as an error message," not parsed as
  structured data. Only one real channel fires; the header's "both
  conventions" claim is inaccurate, though the deny itself still works.
- Dimension 15 (fail-closed default on malformed input): **FAIL,
  live-verified.** The dispatch ran
  `printf 'not valid json{{{' | bash hooks/check-issue-acm-disclosure.sh`
  directly against the real script. `jq`'s parse failure propagates
  through `set -euo pipefail` as exit code 5, not exit code 2 -- and per
  Claude Code's own docs, "any other exit code is a non-blocking error
  for most hook events... execution continues." **Malformed stdin JSON
  causes this gate to fail open, letting the tool call through
  unchecked** -- the opposite of the fail-closed behavior dimension 15
  requires, and untested by the hook's own bundled test file (every
  fixture there uses well-formed JSON).
- Dimension 16 (runtime tamper-detection): named gap, no signature/hash
  check found.
- Dimensions 7, 8, 11, 12, 17: PASS, several strongly evidenced (e.g.
  deployment-mode portability has a real test exercising the
  plugin-distributed path with `CLAUDE_PROJECT_DIR` pointed elsewhere;
  duplication/drift risk is explicitly named in the companion script's
  own docstring and floor-guarded by a sync test).
- Dimension 9, 10: mixed -- the known-limitation disclosure and the
  plugin-bundle regression test are both genuine, but the inaccurate
  "dual-channel" claim above was never itself empirically verified by
  the artifact's own authors.
- Dimension 13: N/A (single decision channel, no separate side effect to
  decouple).

**Step 4, cross-cutting axes:** Compatibility awareness flags an
undocumented gap -- nothing in `hooks/` states whether this gate fires
under a non-Claude-Code agent-tool session. Reproducibility/
Domain-coverage: 2 of 4 domains, argued rather than accidental (Domain 3
exists specifically to catch what Domain 2 cannot); Domains 1 and 4 show
zero coverage but are structurally inapplicable here, not unnoticed
gaps. Blast-radius/trust-classification: reconstructable but not
concentrated in one place -- a reader of the hook script alone would not
find the consequence-of-bypass statement without also reading the paired
CI workflow's own comment.

**Step 5, coverage attestation (explicitly scoped, not a full pass):**
`CLAUDE.md` was checked directly and contains zero mentions of "ACM" or
"Acceptance Criteria Map" -- this invariant's real source is the cited
issues and design docs, not the top-level contributor-instruction file.
Within that narrow scope: 2 deterministic domains cover this policy,
replacing what the CI gate's own docstring calls a prior "per-session
skill-trigger (probabilistic)" mechanism alone. The dispatch was explicit
that this is not a full coverage-attestation pass, which needs the
target's complete invariant list -- out of scope for a single-artifact
smoke test.

**Step 6, final verdict: well-formed and well-placed, with named,
evidence-cited maturity gaps** -- the fail-open-on-malformed-JSON bug
above, the inaccurate dual-channel claim, the undocumented cross-runtime
applicability, and the absent tamper-detection layer. None of these
overturn the mechanism-fit verdict; per this skill's own Stop boundaries,
a strong placement verdict does not excuse glossing over live-verified
maturity failures.

### Disposition of the live-verified bug this smoke test found

The fail-open-on-malformed-stdin-JSON finding is a real defect in an
existing, previously-shipped hook, discovered as a side effect of
proving this skill's own procedure works -- not something introduced by
this skill's build. Fixing `hooks/check-issue-acm-disclosure.sh` itself
is out of this PR's own scope (a different artifact, a different
concern, and CLAUDE.md's own "touch only what the active task requires"
convention) -- filed instead as its own follow-up issue (`[elided]`) per
this repository's own "open a GitHub issue before any branch, commit, or
PR" convention.

## Worked example: Security-level / Zero-Trust maturity classification axis (this repository's own established ceiling)

Applies the axis to the same Domain-2 gate pair already graded in the
smoke test above (`hooks/check-issue-acm-disclosure.sh` +
`hooks/gitapex_check_acm_present_or_waiver.py`, paired with the Domain-3 CI
backstop) -- reusing that smoke test's already-live-verified findings
rather than re-testing. This worked example recasts existing evidence
through a new lens; it makes no new live-tested claim.

This repository's own established tier/ceiling documentation, per the
reuse-not-re-derive procedure in
[references/security-level.md](security-level.md):
`docs/superpowers/specs/2026-07-18-init-capability-tiers-design.md` (a
design doc adapting Anthropic's Zero Trust tier framework onto this
repository's own `init` scaffolding) and `docs/security-control-inventory.md`
(a separate, already-shipped control-coverage inventory mapping this
repository's design onto external security taxonomies). Both are named
here by their real path -- consumed as already-settled input, not
re-derived, and not merely described abstractly.

**Category placement:** primarily **input validation and output
controls** (validating an issue-creation tool call's own body content
before the write proceeds), with a secondary touch on **AI governance
policies** (documenting an approver-facing acceptance-criteria
convention).

**Honest-ceiling cross-check:** the tier-design doc's input-validation
category table tags Foundation-tier input validation as schema/enum/size
validation everywhere input enters, its `configure`-class (an enforced,
not merely documented, obligation). The ACM-disclosure hook is exactly
this pattern -- a schema-shaped presence/waiver check on a tool call's
own body field, deterministically enforced (shape check 1: PASS, the
correct Domain-2 exit-2 deny signal is used) -- so Foundation-tier
input-validation coverage for this specific policy is honestly claimable
in principle.

**Floor-or-scalable classification, at the category level:** the
ACM-disclosure *policy's own category* is **tier-scalable, not
floor-class**. The cited design doc's own floors table names no
ACM-shaped requirement among this repository's non-negotiable floors; the
requirement to disclose an ACM at all is friction-class (it raises the
cost of an under-specified issue slipping through; it does not remove an
attack path an agentic actor has no other route around -- a determined
caller could still supply a syntactically valid but hollow waiver line
and pass). Naming the category tier-scalable surfaces a real gap on its
own: nothing currently escalates its strictness at a higher tier. This is
a separate question from whether *this specific gate's own behavior*
meets the cross-cutting floors below -- see
[references/security-level.md](security-level.md)'s own warning against
conflating the two.

**Floor violation, at the gate level -- this is not merely an overclaim
to cap, it disqualifies the gate from Foundation entirely:** the smoke
test above found, live-verified, that malformed stdin JSON causes this
same hook to fail OPEN (dimension 15: FAIL) rather than deny.
Fail-closed-on-malformed-input is a cross-cutting floor that gates every
tier regardless of category (per
[references/security-level.md](security-level.md)'s impossible-vs-tedious
test) -- so this is not a category-ceiling question the tier ladder
merely caps lower; it is a floor violation that means **no tier is
honestly claimable for this control today**, not even Foundation, until
the fail-open defect is fixed. This matches
`docs/security-control-inventory.md`'s own, independently derived
verdict for this exact hook (`LLM05 Improper Output Handling`:
`partially covered`, coverage scoped to specific sinks with named gaps) --
the security-level axis's own verdict is corroborated by, not contradicted
by, the already-shipped control inventory. The defect is already filed as
its own follow-up issue (`[elided]`).

**Verdict:** This control does **not** honestly clear Foundation today.
The ACM-disclosure category itself is tier-scalable and, once the
fail-open defect above is fixed, Foundation-tier coverage for it would be
honestly reachable (shape check 1 already passes: the correct Domain-2
exit-2 deny signal is used on the well-formed path) -- but a live-tested
floor violation disqualifies a gate from any tier, it does not cap it at
one. No Enterprise/Advanced-tier escalation exists or is claimed either
way.

## Worked example: dimension 19 (runtime-cost optimization) applied to the same Domain-2 gate pair

Reuses -- does not re-derive -- the same smoke-test target already graded
above: `hooks/check-issue-acm-disclosure.sh` + `hooks/gitapex_check_acm_present_or_waiver.py`
(Domain 2, registered in `hooks/hooks.json:26-32` under the
`mcp__github__issue_write` matcher with a 10-second `timeout`). This is a
live-measured pass, not an assumed one.

**What the gate actually does per invocation, by path** (confirmed by
direct reading of both files, not assumed from their names): one `cat` of
stdin, then three sequential `jq -r` field extractions
(`hooks/check-issue-acm-disclosure.sh:28,36,42` -- `tool_name`, `method`,
`body`, each gated behind the previous field's own early-exit check), then
one `python3` cold start running `gitapex_check_acm_present_or_waiver.py` (two
`re.compile` calls, one `re.search` each, no network I/O, no filesystem
scan beyond the sibling script's own existence check). That is the **allow
path**: 1 `cat` + 3 `jq` processes + 1 `python3` process, 5 subprocess
launches total (the `cat` in `input=$(cat)` at line 26 is itself an
external-command fork, not a shell builtin, and is counted above). The
**deny path** (line 42's
body fails the Python check) launches one more: `deny()`'s own `jq -n`
call at line 49, to build the `hookSpecificOutput` JSON written to stderr
-- 1 `cat` + 4 `jq` processes + 1 `python3` process, 6 subprocess launches
total. The two paths are not process-count-identical; deny costs one more
fork than allow.

**Live measurement, five consecutive runs against a passing (waiver-line)
synthetic `mcp__github__issue_write` payload**, run directly against the
real script with bash's own `time` builtin (copy-pasteable and reproducible
as written; substitute a different repository checkout's own path if
re-running elsewhere):

```
$ payload='{"tool_name":"mcp__github__issue_write","tool_input":{"method":"create","body":"ACM: not-applicable (docs): example"}}'
$ for i in 1 2 3 4 5; do
    echo "$payload" | { time bash hooks/check-issue-acm-disclosure.sh > /dev/null; } 2>&1 | sed "s/^/run $i: /"
  done
run 1:
run 1: real	0m0.066s
run 1: user	0m0.053s
run 1: sys	0m0.016s
run 2:
run 2: real	0m0.043s
run 2: user	0m0.031s
run 2: sys	0m0.014s
run 3:
run 3: real	0m0.043s
run 3: user	0m0.032s
run 3: sys	0m0.013s
run 4:
run 4: real	0m0.051s
run 4: user	0m0.037s
run 4: sys	0m0.015s
run 5:
run 5: real	0m0.038s
run 5: user	0m0.034s
run 5: sys	0m0.006s
```

Run 1 (0.066s) is consistently the slowest across repeated trials of this
same measurement, ahead of runs 2-5 (0.038-0.051s) -- an ordinary
first-invocation cold-start effect (disk-cache/page-cache warmup for the
`bash`/`jq`/`python3` binaries themselves), not a defect in the gate and
not cherry-picked away: all five raw runs are reported above rather than
only the fastest ones. A separate run against a failing (no-ACM) body
measured `real 0m0.062s`, `exit=2` -- within the same noise band as the
allow-path runs above at this timing resolution, even though the deny path
launches one more subprocess (6 vs. 5, per the process count above); the
extra `jq -n` fork is too cheap to separate from run-to-run variance at
this measurement precision, which is itself worth stating plainly rather
than rounding up to "identical."

**Verdict: PASS against the registered budget, with a named minor gap
against this dimension's own bar.** Measured cost (~38-66ms wall across
five runs, including the slower first invocation) is roughly 150-260x
under the registered 10s budget (shape check 6's own concern, not restated
here) -- comfortably PASS on that axis. But this dimension asks a stricter
question than "is it fast enough," and a strict read finds a real, if
minor, instance of avoidable overhead: the three sequential `jq -r` calls
on the allow path (and the
matching three plus a fourth on the deny path) each parse the *same*
already-buffered `$input` string independently, forking a fresh `jq`
process per field, when a single `jq -r` invocation extracting
`tool_name`, `tool_input.method`, and `tool_input.body` together (e.g. as
tab-separated output) would collapse 3 of those 5 (or 4 of those 6)
process launches into 1 -- real, avoidable, process-fork overhead by this
dimension's own letter, not merely a cost that is already at the floor.
Applying this dimension's own guard before crediting that as a fix: the
current staged structure exits early on `tool_name`/`method` mismatches
before ever touching `body`, which a single upfront extraction would
partly forfeit -- collapsing to one call is not risk-free by construction
and would need to preserve the same early-exit behavior, not just be
assumed cost-free. **Net assessment:** a genuine minor optimization
opportunity exists; its absolute impact (a small fraction of the measured
~40-65ms, itself ~150-260x under budget) does not change this gate's
overall placement verdict -- named as a low-priority finding, not a
blocking one, per this dimension's own "grade only a change that holds
... behavior fixed while reducing its cost" guard, which cuts both ways:
a real gap is still worth naming even when fixing it would not matter
much, and a candidate fix is not free of risk just because the process
savings are cheap to state. Every claim above is confirmed by direct
reading of both files (quoted above) and by the live measurements, never
accepted from either script's own header comment alone, per this
dimension's own verification-mandate clause.

## Audit history: Security-level axis hardening round

Two fresh, isolated audit rounds (a standard `evaluating-skill-quality` +
`battle-testing-a-skill` pass, then a Fable-model blind-spot analysis plus
eight adversarial trials) hardened the Security-level axis after it was
added; both found real gaps, now all fixed across `SKILL.md`'s Stop
boundaries, `references/grading-procedure.md`, `references/security-level.md`,
and `references/dimensions.md`. Round-by-round detail:
`metadata/gitapex.yaml`'s `spec.references`.

## Worked example: dimension 21 (gate precision audit), cited from the source paper

Unlike every other worked example in this file, this one is not drawn from
a gitapex-native artifact -- no gate in this repository yet has a real,
multi-firing audit trail comparable to what dimension 21 asks for. It
instead applies dimension 21 to the source paper's own reported audit,
disclosed as cited evidence rather than a freshly-run local measurement
(the same disclosure dimension 21's own text requires of a target that
lacks a real-firing audit trail).

"Reason Less, Verify More" (arXiv:2607.07405) Table 6 audits its own
five-gate candidate set (four promoted into the paper's headline suite,
one held back) by comparing every rejected call to the ground-truth
trajectory -- a **true block** is a rejected write the ground truth also
avoids; a **false block** is a rejected write the ground truth actually
performs:

| Gate | Fires | True blocks | False blocks | Precision | Removal Δ |
|---|---|---|---|---|---|
| `cancellation_eligibility` | 161 | 161 | 0 | 100% | -2 |
| `must_read_before_write` | 90 | 70 | 20 | 78% | +3 |
| `baggage_allowance` | 42 | 2 | 40 | 5% | +3 |
| `basic_economy` | 18 | 15 | 3 | 83% | +6 |
| `passenger_count` | 9 | 9 | 0 | 100% | +4 |

Applying dimension 21's own question: `cancellation_eligibility` is the
only gate whose removal *lowers* the paper's own pass1 metric (Removal
Δ = -2) -- it is both the highest-precision gate (100%) and the only
load-bearing one on this task distribution. `baggage_allowance` fires
almost as often (42 times) but is 5% precision -- 40 of its 42 rejections
block a write the ground truth actually performs, and removing it *raises*
pass1 by 3pp. A review that stopped at "the gate fires and denies
correctly per its own deterministic-shape checks" (shape checks 1-6) would
credit both gates equally; only the real-firing precision audit this
dimension requires distinguishes a gate that is helping the target policy
from one that is silently over-blocking legitimate actions while looking,
by every shape check, identical.

**Verdict, applying dimension 21 to the paper's own suite:**
`cancellation_eligibility` and `passenger_count` (both 100% precision)
clear this dimension; `must_read_before_write` and `basic_economy`
(78%/83%) are mixed -- real value, non-trivial false-block rate, named as
such rather than rounded up to "fine"; `baggage_allowance` (5%) fails this
dimension outright and is exactly the case the paper's own conclusion
names: "not that every hand-written gate helps... gate precision must
itself be audited."

## Worked example: dimension 22 (firing-share attribution), cited from the source paper

Same disclosure as the dimension 21 example above: cited from the source
paper's own reported numbers, not independently re-run against a
gitapex-native artifact or multi-trial harness.

Section 3.4 of "Reason Less, Verify More" (arXiv:2607.07405) states the
precondition this dimension requires explicitly satisfied in the paper's
own setup: the airline benchmark is run at 5 trials per task (250 trials),
with a disjoint 15-seed replication (750 trials) -- repeated-trial
measurement, not a single-shot run. The paper decomposes its own aggregate
lift as `Δ_aggregate ≈ p_fire × Δ_fire` and reports the stratified budget-
model result directly:

| Stratum | Tasks | Vanilla | Verified | Δ |
|---|---|---|---|---|
| Gate fires | 26 | 18/130 (13.8%) | 43/130 (33.1%) | +19.2pp, 95% CI [+6.9, +33.1], P=0.0006 |
| Gate never fires | 24 | 56/120 (46.7%) | 62/120 (51.7%) | +5.0pp, 95% CI [-5.0, +14.2], P=0.18 |

Applying dimension 22: the firing stratum's 95% CI excludes zero
(+6.9 to +33.1) -- a real, statistically supported improvement where the
gate actually fired. The non-firing stratum's own 95% CI *includes* zero
(-5.0 to +14.2) -- its movement is consistent with noise, not a real
effect. The paper's own text draws exactly the conclusion this dimension
requires before crediting an aggregate number: "we therefore do not claim
that gates improve non-firing tasks... aggregate lift is concentrated
where the intervention is exercised." Separately, the paper reports the
same decomposition numerically (132 rejections across 83/250 trials; of
the aggregate +31 successful trials, +25 occur in the firing stratum) --
two independent presentations of the same stratified-attribution finding,
not merely the confidence-interval table alone.

**Verdict, applying dimension 22 to the paper's own result:** PASS -- the
paper's own aggregate lift claim is attributable to the gate specifically
because this stratification was run and both strata's confidence
intervals are reported, not merely asserted from the unstratified
aggregate number. Contrast with gitapex's own real gates (the
ACM-disclosure hook pair graded in the dimension-19 worked example above,
for instance): none of them run under repeated/multi-trial measurement in
production, so dimension 22 reads not-applicable for them today -- exactly
the precondition-scoped outcome this dimension's own text names as the
expected case for gitapex's real review targets, not a gap in the
dimension itself.

## Worked example: Contract role / input-domain closure axis, and its sibling-repository prior art

**The prior art, and what was actually read to confirm it.** The
open-versus-closed asymmetry in that axis's second sub-judgment is ported
from the sibling repository `tvna/claude-md`, whose
`scripts/scan_nonexhaustive_invariant_drift.py` locks a fixed registry of
bullets in its own `.apm/instructions/master.instructions.md` to the
literal marker phrase `non-exhaustive instances`. Confirmed on 2026-08-09
by reading that file directly from a fresh clone of that repository, not
from a summary of it: the module defines `MARKER = "non-exhaustive
instances"` and a four-entry `REGISTERED_BULLETS` map (untrusted-data
sources, adversarial payloads, destructive operations, secret lifecycle),
and its own docstring states the grounding -- "a closed list is a control
that is merely *tedious* for an attacker to evade by finding an unlisted
variant, while the open invariant *removes* the gap." gitapex's own
`CLAUDE.md` sections 2 and 4 carry the same `non-exhaustive instances` and
default-in-scope wording, descended from that doctrine; that is the live
example a reader of the portable axis can inspect here. Neither fact
transfers to a target under review: confirm the target's own equivalents,
or report that it has none.

**The axis applied to a real gitapex gate.**
`.github/scripts/gitapex_scan_contract_axis_vocabulary_drift.py` -- the
lock shipped alongside that axis.

- *Contract role:* **invariant**. It is bound to no operation and no
  caller. It asserts that a property of the tree (the axis's vocabulary is
  still where the skill says it is) holds whenever it is observed, and a
  violation attributes fault to the state, not to whoever last ran pytest.
  Contrast the two Domain-2 hooks graded in the smoke test above, both
  preconditions on a proposed tool call.
- *Input domain:* **structural / protocol value**, correctly closed. Its
  inputs are a fixed vocabulary this repository itself owns -- three
  Design-by-Contract role labels, two input-domain-kind labels, and two
  JSON Schema `enum` token sets -- so enumerating exactly the accepted
  spellings and treating everything else as drift is the safe direction. A
  permissive match ("contains the word precondition somewhere") would
  admit the re-cased or reworded spellings the lock exists to catch.
- *The boundary, named rather than smoothed over:* one of the locked
  strings is the marker phrase `non-exhaustive`, which belongs to a
  threat-classification category that must stay open. The gate's own input
  domain is still structural -- it checks that the marker is *present*,
  a fixed string either there or not -- while the category the marker
  describes stays open. This is the both-readings boundary case the axis
  names, resolved by asking which domain the *check* draws from rather
  than which domain the checked prose is about.
- *Verdict impact:* none. Both classifications are warning-only, reported
  beside this gate's own verdict, never inside it.
