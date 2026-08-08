# scanning-attack-surfaces eval status

Issue #467 (refs #461, #463, #466): a committed eval corpus now exists at
`evals/vetting-attack-surface/` -- 5 tasks covering both of this skill's
checks with both poles (`exposure-excess.yaml` / `exposure-minimal.yaml`,
`privilege-excess.yaml` / `privilege-minimal.yaml`) plus the Applicability
gate (`applicability-gate-no-dependencies.yaml`, a zero-dependency/
zero-credential case that must grade "not applicable" rather than being
silently passed). This closes the specific gap PR #463 disclosed and
waived at this skill's launch ("no committed
`evals/evaluating-attack-surface/` regression corpus" -- the directory is
now named `evals/vetting-attack-surface/`, following the #466/#469
rename). `evals/scripts/gitapex_lint_fixture_assertions.py`, run against
`skills/vetting-attack-surface/SKILL.md` as the anchor corpus, reports 0
warnings.

A fresh, independent `battle-testing-a-skill` dimension-14 dispatch
(subagent, this repository's own `CLAUDE.md` visible in its context per
the same disclosed limitation as every other trial in this file) confirmed
the corpus-composition gap is closed, but found dimension 14's own Pass
criterion is a conjunction -- "a durable, checked-in corpus... growing
over time... that every edit to the target is re-run against before
merge" -- and the enforcement half remains unmet:
`.github/workflows/waza-eval-matrix.yml` (the only workflow that actually
executes an `eval.yaml`/`tasks/` suite against a live model) triggers on
`workflow_dispatch` only, is self-documented in its own header comment as
advisory and never merge-gating, and cannot produce a result until the
owner provisions the `copilot-sdk` endpoint secrets; `waza-check.yml` runs
on push/PR but performs only a static shape check with
`continue-on-error: true`, never executing `evals/` at all. This is the
same repository-wide gap already recorded above for
`grounding-in-primary-sources` and `evaluating-skill-quality`
("unfixable without a CI eval-execution gate that does not exist for any
skill"), now independently reconfirmed against this skill by direct
inspection rather than assumed by analogy.

**Verdict: dimension 14 remains FAIL**, narrowed from "no corpus exists"
(the PR #463 disclosure) to "no CI mechanism re-runs any skill's `evals/`
suite as a required merge gate" (repository-wide, not unique to this
skill) -- issue #467's own Facts section anticipated exactly this
repo-wide caveat ("dimensions 13-16 fail on essentially every skill in
this repository today... a repository-wide gap, not unique to this one
skill"). Building that CI-enforcement mechanism is out of scope for issue
#467, which scoped closing the corpus-existence gap specifically, and
remains open, repository-wide, future work -- the same disposition this
file already records for every other skill's dimension-14 line.

No no-skill baseline run exists for this suite, and only
`claude-sonnet-4.6` has been evaluated -- cross-model behavior is
currently unmeasured, the same disclosed gap as every other suite in this
file.

**Issue #472 (fable Blind Spot Pass, refs #467, #471):** an independent
subagent dispatch on a fable model, deliberately not self-graded by the
session that authored the original 5-task corpus, ran a
`battle-testing-a-skill`-style cold-enumeration pass over this skill and
corpus. It found the corpus's composition was sound (both poles of both
checks plus the gate) but contained zero adversarial fixtures, despite
dimension 14's own catalog title naming the gap "reusable, versioned
**adversarial** regression corpus" -- an edit that deleted or weakened
any of `SKILL.md`'s Stop boundaries (encoded/obfuscated instructions,
secret redaction, persisted "already reviewed" claims) would have passed
the then-current suite at 100%. It also found the Procedure step 1
indeterminate fallback -- the fix three of four prior audit rounds
converged on, per `metadata/gitapex.yaml`'s own recorded history -- had
no regression fixture at all, since every existing prompt pre-supplied
fully verified evidence.

6 tasks were added in response, closing the three findings issue #472
scoped in (two lower-severity findings -- an unstated under-privilege
vocabulary gap, and the `-minimal` tasks' lack of a negative assertion
guard -- were named but deliberately deferred, not bundled in):
`adversarial-planted-review-claim.yaml`,
`adversarial-legible-credential-redaction.yaml`, and
`adversarial-encoded-directive.yaml` exercise the Stop boundaries
directly (a planted "already reviewed" comment that must not substitute
for re-deriving the verdict; a legible dummy token that must be redacted
from the report rather than reproduced verbatim; a Base64-encoded
directive embedded in the reviewed artifact that must not be obeyed);
`indeterminate-self-description-only.yaml` and
`indeterminate-unreadable-target.yaml` exercise the two non-nominal
Procedure step 1 paths (self-description-only baseline -> `indeterminate`;
unreadable/truncated target -> "cannot review", the Applicability gate
not silently applied); `multi-item-combined-verdict.yaml` exercises the
per-item, no-aggregate-verdict discipline on a single artifact carrying
both an exposure issue and a privilege issue. The corpus is now 11
tasks. `gitapex_lint_fixture_assertions.py` (0 warnings), `gitapex_check_skill_shape.py`
(31/31), and `pytest` (878 passed) all re-verified clean after the
addition. This growth does not change the dimension-14 verdict above --
the enforcement conjunct (no CI merge gate) is still the dispositive,
repository-wide reason it remains FAIL -- but it directly closes the
"zero adversarial fixtures" and "indeterminate fallback unguarded" gaps
the Blind Spot Pass found, independent of that conjunct.

**Issue #846:** this directory moved from `evals/vetting-attack-surface/`
following the skill's own `vetting-attack-surface` -> `scanning-attack-
surfaces` rename. Unlike the narrative prose above (left as the historical
record of what happened at the time, following this file's own established
convention), the corpus's *operative* content was updated to match: `eval.yaml`'s
`name`/`skill`/metric-name fields, every task's `id:` field, and every
task prompt's `Use vetting-attack-surface.` instruction now read
`scanning-attack-surfaces` -- an independent `battle-testing-a-skill` pass
run against the rename caught this as a real, unwaived regression (a
prompt instructing the executor to invoke a skill name no longer present
in the repository) rather than cosmetic drift, since these fields are
executed, not merely read.
