# setup-gitapex-toolchain eval status

No `evals/setup-gitapex-toolchain/` suite exists yet: no `eval.yaml`, no
`tasks/` corpus, no no-skill baseline, no model tier evaluated. More
specifically -- and this is the actual disclosed gap, not a claim that it
doesn't apply -- neither a `battle-testing-a-skill` nor an
`evaluating-skill-quality` dispatch has been run against this skill since
it was first scaffolded (issues #57/#690, commit `1844836`). Both stay
open. Nothing here waives them: a waiver is a PR-body decision
(`gate_skill_audit_disclosure.py`, issue #248) made by a reviewer at
SKILL.md-change time, not something this file grants on its own.

This skill is a thin orchestration wrapper around a deterministic Python
CLI (`scripts/provision_class_b.py`: parse `flake.nix`'s Class B pins at
runtime, download + SHA256-verify + extract + install four binaries, run
`apm install`), not a judgment/reasoning skill whose behavior turns on
how it interprets ambiguous natural-language input -- the axis both
prompt-based audits are built to probe. What verification exists instead
targets the script's own logic, and was real rather than merely planned:

- 54 unit/integration tests in `scripts/test_provision_class_b.py`
  (`uv run --frozen pytest skills/setup-gitapex-toolchain/scripts`, all
  passing), built test-first across the skill's incremental commits --
  several with their own RED-phase or deliberate-bug-injection
  confirmation recorded in the commit message (e.g. commit `33d419c`'s 7
  adversarial extraction tests, written first and confirmed failing
  against the pre-fix code; commit `093c065`'s deliberate `if False:`
  injection into the apm-install gate, confirmed to catch a regression
  the plan's own given test could not).
- A live, network-reaching smoke test against the real pinned GitHub
  release assets (commit `093c065`): fresh install (4/4 tools
  INSTALLED), immediate re-run (4/4 SKIPPED, no network calls),
  `--verify` against the real on-disk cache (4/4 PASS), and a full `apm
  install` run against a real `apm` binary in a scratch project
  directory.
- An internal review pass on the immediately preceding commit's own
  archive-extraction code (a task-review step in this repo's own
  development flow, not a dedicated `vetting-attack-surface`-style
  audit) found and fixed a real path-traversal-adjacent defect one
  commit later, before this work reached `main`: a hostile archive whose
  members all share the top-level segment `..` passed the existing
  single-top-level-dir cardinality check, and the flatten step would
  have relocated the parent directory's own contents into the install
  target. Fixed in commit `33d419c`, tracked as issue #706.

None of that substitutes for the missing audits -- it exercises the
script against well-formed and adversarial *inputs*, not an *agent's*
judgment about when and how to invoke this skill (wrong tool selection, a
misread PASS/FAIL summary, working around a `--verify` failure instead of
surfacing it). That gap stays open until a real `battle-testing-a-skill`
/ `evaluating-skill-quality` dispatch runs against this skill. Refs #57,
#690, #706, #711.
