# Use static AST parsing, not sys.addaudithook or DAST tooling, for find_network_drift's detection mechanism

## Status

Proposed

## Context and Problem Statement

Retrofit record: this decision is already implemented (issue #1022, closed via PR #1027, merged). This ADR documents rationale that currently lives only as prose inside `skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`'s own module docstring, written after the fact rather than before the decision was made.

Issue #1022 requested a companion scanner cross-checking a skill's declared `spec.executionRequirements.network` (mode/domains) against what its bundled `scripts/*.py` actually do, catching the case where a skill declares `network.mode: disabled` while a bundled script performs real network I/O. The scanner (`find_network_drift`) must operate as a read-only, pre-execution check: per its own module docstring, it "must never itself run a skill's bundled scripts" -- the skill directories it scans are untrusted content from the reviewer's own threat model (a skill's bundled script could itself be adversarial or simply buggy), so executing them to observe behavior is not an option. A live design discussion on issue #1022 researched whether a dynamic/DAST-style approach could replace or improve on static analysis for this detection.

## Considered Options

- Python's own `sys.addaudithook` (PEP 578) to observe network-related events at runtime
- Established DAST (Dynamic Application Security Testing) tooling
- Static analysis via Python's own `ast` module (stdlib)

## Decision Outcome

We will detect network-capable imports and literal `https?://` hosts via static AST parsing (Python's own `ast` module, stdlib), because both alternatives require the target code to actually execute to produce a signal, which is fundamentally incompatible with this scanner's own read-only, pre-execution safety constraint:

- `sys.addaudithook`'s own PEP 578 documentation states plainly it is "not suitable for implementing a 'sandbox'" and only fires when the audited code path actually runs.
- Established DAST tooling targets a *running* application's own HTTP/UI surface -- there is no running application here, only a skill directory's static file content.

A real AST parse tree also has no comment nodes at all, so a commented-out reference can never register as usage without a filter having to say so, and import resolution checks the exact dotted module path Python itself would resolve (`import X`, `import X.Y`, and `from X import Y` each handled on their own real shape, not approximated by one regex trying to cover all three).

## Consequences

Good, because the scanner never needs to execute a skill's bundled scripts to produce a finding, holding the read-only safety constraint exactly.
Good, because a real parse tree gives exact, deterministic results for the shapes it does cover (same input always parses to the same finding) -- no reliance on brittle text-regex approximations of import syntax.
Bad, because static analysis cannot see every real network-capable call shape: a call routed through an unlisted helper function, a host built at runtime (string concatenation, an f-string with a non-literal segment), or a network call gated behind a condition that never actually triggers can all slip past AST analysis exactly as they would past a human reading the same source. This is disclosed in the scanner's own docstring and demonstrated by a deliberately-constructed test (`test_dynamically_constructed_host_evades_allowlist_check`).
Bad, because `find_network_drift` only reads `skill_dir/scripts/*.py` -- a bundled non-Python script (e.g. a `.sh` file) is invisible to it, network-capable shell commands (`curl`, `wget`, `nc`, ...) included. Also disclosed and demonstrated (`test_non_python_bundled_scripts_are_not_scanned`).

## Confirmation

`skills/evaluating-skill-quality/scripts/test_gitapex_scan_execution_requirements_drift.py::test_dynamically_constructed_host_evades_allowlist_check` and `::test_non_python_bundled_scripts_are_not_scanned` are real, existing tests that pin the known limits of the chosen approach (Bad consequences above), so a future change to the detection mechanism that silently narrows or widens these limits would need to update these tests deliberately rather than by accident. No mechanism currently confirms the safety constraint itself (that the scanner never executes a bundled script) beyond code review -- relies on review for that specific property.
