# Correction: issue #665 Repair 4's branch-coverage premise

Refs #665, #681.

## What was wrong

Issue #665's Repair 4 proposed enabling branch coverage (`branch = true`
under `[tool.coverage.run]`, `--cov-branch` in `addopts`) as the
deterministic gate that would have caught PR #651's dead-guard defect (a
`not lines` condition that can never be true, because `"".split("\n")` is
`[""]`, never `[]`). That premise was argued, not measured, and it is
wrong.

## The measurement

Minimal reproduction of the defect shape, with tests exercising both
outcomes, run with branch coverage on:

```python
def frontmatter(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":   # `not lines` is never true
        return ""
    return "block"
```

```
$ pytest --cov=dead --cov-branch --cov-report=term-missing
Name      Stmts   Miss Branch BrPart  Cover
dead.py       5      0      2      0   100%
2 passed
```

`Branch 2, BrPart 0, 100%`. coverage.py measures arcs at the `if` level,
not per boolean operand, so a short-circuited sub-condition that can never
be true is invisible to it. The dead `not lines` operand is exactly that
shape.

This was independently confirmed against the real defective file:
`pytest --cov-branch` on `gate_plugin_root_brace_notation.py` at commit
`f91383c` (the pre-fix state), using that commit's own 17 passing tests,
also reported 100 percent branch coverage with 0 partial branches.

## What actually catches it

A small deterministic mutation smoke test. Measured against the same
defective commit with the same 17 tests: 13 mutants, 4 survived, 6.5
seconds -- and three of the four survivors are on the defect's exact
line. The operator that finds it replaces each boolean operand with its
identity element, which is purpose-built for a dead sub-condition; a
general-purpose mutation tool is not required and a stdlib implementation
is enough.

Honest limits, so this is not a straight swap for Repair 4's original
proposal:

- Mutation testing perturbs *existing* code. Other defect classes in this
  repository's history are *missing* code (an absent guard, an absent
  `except`), and mutation is structurally blind to those. This replacement
  is narrower than Repair 4 claimed to be.
- Cost: full-repository runs extrapolate to 4-8 minutes, over the
  5-minute budget the gate jobs carry. Scoping to the changed gate scripts
  of a diff (which `.github/scripts/detect_changed_gate_scripts.py`
  computes, as of PR #674) puts it at 10-20 seconds per PR.
- Survivor triage is human work. Current fixed files show roughly a 10
  percent survivor rate, and each survivor needs a judgment call about
  whether it is a real test gap.

Adopting diff-scoped mutation smoke as an actual CI gate is tracked
separately (see issue #681's Non-goals) -- this document names it as
Repair 4's successor, it does not implement it.

## Re-check: does any other #665 Repair proposal make the same kind of
## unverified claim?

Bounded re-read of #665's own Repair 1-9 and its five carried-forward
items, checking specifically for the Repair-4 failure shape: a detection
mechanism whose yield against its named defect was asserted rather than
run and compared.

- **Repair 1** (fail-open disclosure gate) and **Repair 5**: yields were
  established by actually running the fail-open cases (nonexistent path,
  malformed frontmatter, unreadable file) and observing the wrong exit
  code/message. Measured, not argued.
- **Repair 2** (denylist -> `git ls-files`) and **Repair 6** (hidden-
  character lint): both are direct pattern/byte-level matches (a
  hardcoded ignored path, a specific Unicode codepoint), not statistical
  coverage metrics with hidden semantics. Their proposed gates were not
  independently run against a corpus of known cases in this cycle, so
  their yield is not separately measured here -- but the failure mode
  Repair 4 exhibited (a metric that reports success while structurally
  blind to the defect shape) is specific to arc/branch-style coverage
  statistics, not to a literal pattern match, so the same risk does not
  transfer directly.
- **Repair 3** (diagnostic self-check): the proposed test
  (`test_success_message_shows_the_braced_form`) already shipped in
  `25c8223`, running the script's own output back through its own
  matcher. Self-verifying by construction.
- **Repair 7, 8, 9**: classified as unclear-agent-instruction or
  external/human-decision, not a proposed detection gate; no yield claim
  to check.
- **Carry-forward #640, #616, #510**: process/tooling proposals (extend a
  local hook, consolidate a runner, add a citation-overlap heuristic), not
  claims about a metric's detection yield.
- **Carry-forward #598**: its claim (a same-thread review pass is weaker
  than an independent one) was itself established by a direct side-by-side
  comparison in this cycle -- the six-probe same-thread pass missed nine
  defects an independent `/code-review` caught. Measured.
- **Carry-forward #314**: about the retrospective drift-scanner's own
  citation logic, not a detection-mechanism yield claim.

Scope disclosure: this is a bounded re-check of #665's own listed
proposals, not a re-derivation of every one of the scanner's 97
no-citation items (per #665's own carry-forward section). No other entry
in #665 was found to repeat Repair 4's specific failure shape.
