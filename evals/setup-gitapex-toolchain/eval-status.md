# setup-gitapex-toolchain eval status

Real `battle-testing-a-skill` and `evaluating-skill-quality` dispatches have
now run against this skill (issues #57/#690). No `evals/setup-gitapex-toolchain/`
suite exists yet, though: no `eval.yaml`, no `tasks/` corpus, no no-skill
baseline, no model tier evaluated. That gap is tracked separately (issue
#721), not waived here -- a waiver is a PR-body decision
(`gitapex_gate_skill_audit_disclosure.py`, issue #248) made by a reviewer at
SKILL.md-change time, not something this file grants on its own.

## Real audit dispatches

**`battle-testing-a-skill` returned overall FAIL**, 6 of 22 applicable
dimensions failing: dimension 9 (an unsupported `(system, machine)` pair
crashed `main()` with a raw traceback instead of a clean `FAIL:` line),
dimension 12 (no install-time/vendoring-provenance discussion), dimension 13
(a stale receipt was trusted on file-existence alone, never re-verifying the
on-disk bytes), dimension 14 (no adversarial regression corpus -- see
"What remains open" below), dimension 15 (no re-derivation-per-invocation
guard for `--skip-apm-install`/`--tool`), and dimension 16 (raw third-party
`--version`/stderr output reached the terminal unsanitized). Dimensions 9,
12, 13, 15, and 16 were fixed; dimension 14 was not (see below). All five
fixes were verified with reproduced-failing-first evidence, not merely
patched and assumed correct: dimension 9's fix has a test that failed with
an uncaught `UnsupportedSystemError` pre-fix; dimension 13's fix has tests
that overwrite an installed binary's on-disk bytes directly and confirm the
stale receipt no longer causes a false "skipped"; dimension 16's fix has
tests with embedded ANSI/control-character payloads confirming they no
longer survive into `ProvisionResult.version_output` or either of two
exception messages that also carried the same raw-stderr gap (found by
follow-up code review, not the original audit, and fixed the same way).

**`evaluating-skill-quality` returned WELL-FORMED-NOT-MATURE**, with named
gaps in dimensions 2, 4, 5, 6, and 7 (nine lettered findings, C-1 through
C-9). Eight were fixed: C-1 (a 22-line `.claude/settings.json` behavior
section, paid on every load regardless of branch, compressed to 6 lines),
C-2 (the Output section's contract description corrected to the tokens
`main()` actually emits, including disambiguating the two different senses
of `SKIPPED`), C-3 (a new "if provisioning fails" section), C-5/C-6/C-8
(undeclared `python3 >= 3.12`, stdlib-only, and network-access preconditions
now stated), C-7 (four previously-unjustified timing constants now carry a
one-line rationale each), and C-9 (`skills/setup-gitapex-toolchain/scripts`
wired into `pyproject.toml`'s coverage gate, verified passing at 94.7%/98.9%
against the 90% floor after every fix in this round landed). **C-4 (change
`portability: Mixed` to `Repository-scoped`) was investigated and
deliberately NOT applied**: `docs/superpowers/specs/2026-07-21-portability-authorship-decision-table-design.md`'s
Table A states `Repository-scoped` is "Invalid under the operator's policy"
for this repository's own origin-authored skills, and issue #229 (closed,
`state_reason: completed`, closed by the repository owner) ratifies that
policy directly. The audit that produced C-4 evidently did not have this
precedent in view. `metadata/gitapex.yaml` keeps `portability: Mixed`,
documented in SKILL.md's own `## Notes` section; the underlying taxonomy gap
this surfaces (no value cleanly fits an origin-authored skill with zero
portable core) is tracked separately as issue #730.

## Dispatch-integrity caveats

Both dispatches disclosed real deviations from their own isolation
requirements, in their own words. `evaluating-skill-quality`'s own report
states directly: "This dispatch carries the calling repository's CLAUDE.md.
It was injected into context at session start" -- a violation of its own
Stop boundary -- and additionally discloses that calling-conversation
framing was included in its own dispatch prompt (also barred by that same
boundary) and that its own install-time provenance is unverified (the
`Skill` tool returned "Unknown skill" for it). `battle-testing-a-skill`'s
report discloses the same class of gap for the *outer* dispatch that invoked
it (this session's `Agent` tool call, which the report's own isolation
registry records as failing on this platform, and which -- as with every
`Agent`-tool dispatch in this session -- ran with this repository's own
`CLAUDE.md` already loaded); its *inner* grading trial, by contrast, did use
genuine subprocess-level isolation (`claude -p` under an isolated cwd +
`HOME`, with a positive/negative control pair independently re-verified
against this platform's current version) -- so the trial's own findings are
not contaminated the same way the outer dispatch was. Per both skills' own
stated discipline, every finding above rests on independently-checkable
evidence (a file read, a `git log`, a live GitHub API read, or a direct
reproduction against the pre-fix code) rather than the dispatch's own
unverified judgment, and the controller (this session) independently
re-verified the three citations underlying the C-4 non-application before
accepting it. Still, per both skills' own rule, these verdicts should be
reproduced by a genuinely isolated re-dispatch before being treated as fully
settled -- folded into issue #721 rather than a separate tracking issue,
since it is the same "run the eval mechanism for real" gap.

## What remains open

- Issue #721: a real `evals/setup-gitapex-toolchain/eval.yaml` + `tasks/`
  adversarial corpus (closes battle-testing-a-skill dimension 14 and
  evaluating-skill-quality dimensions 8-9), a no-skill baseline via
  `evals/scripts/gitapex_run_ablation.py`, a cross-model run via
  `waza-eval-matrix.yml`, and a genuinely isolated re-dispatch of both
  audits per the caveat above.
- Issue #730: the portability-taxonomy gap the C-4 non-application surfaced.
- Issue #724: makes `apm install` idempotent (only the two audits' dimension
  9/12/13/15/16 and C-1 through C-9 findings are this file's own scope;
  #724 is a separate architecture refinement raised independently of either
  audit).

## Script-level verification (pre-existing, updated)

This skill is also a thin orchestration wrapper around a deterministic
Python CLI (`scripts/gitapex_provision_class_b.py`: parse `flake.nix`'s Class B pins
at runtime, download + SHA256-verify + extract + install four binaries, run
`apm install`), and that axis has its own, separate verification history,
real rather than merely planned:

- 79 tests in `scripts/test_gitapex_provision_class_b.py` (70 original
  unit/integration + 8 for the apm-install idempotency fix + 1 for the
  exception-handler-gap fix)
  (`uv run --frozen pytest skills/setup-gitapex-toolchain/scripts`, all
  passing), built test-first across the skill's incremental commits --
  several with their own RED-phase or deliberate-bug-injection confirmation
  recorded in the commit message (e.g. commit `33d419c`'s 7 adversarial
  extraction tests, written first and confirmed failing against the pre-fix
  code; commit `093c065`'s deliberate `if False:` injection into the
  apm-install gate, confirmed to catch a regression the plan's own given
  test could not).
- A live, network-reaching smoke test against the real pinned GitHub release
  assets (commit `093c065`): fresh install (4/4 tools INSTALLED), immediate
  re-run (4/4 SKIPPED, no network calls), `--verify` against the real
  on-disk cache (4/4 PASS), and a full `apm install` run against a real
  `apm` binary in a scratch project directory.
- A real, separate fresh-session live proof (Task 10 of this skill's
  original implementation plan): a genuinely new Claude Code web session
  against this branch confirmed all four Class B binaries and the
  apm-deployed skills present with zero manual intervention.
- An internal review pass on the immediately preceding commit's own
  archive-extraction code found and fixed a real path-traversal-adjacent
  defect one commit later, before this work reached `main`: a hostile
  archive whose members all share the top-level segment `..` passed the
  existing single-top-level-dir cardinality check, and the flatten step
  would have relocated the parent directory's own contents into the install
  target. Fixed in commit `33d419c`, tracked as issue #706.

None of that substitutes for the still-open dimension 14 / dimensions 8-9
gap above -- it exercises the script against well-formed and adversarial
*inputs*, not an *agent's* judgment about when and how to invoke this skill.
Refs #57, #690, #706, #711, #717, #719, #721, #724, #730.
