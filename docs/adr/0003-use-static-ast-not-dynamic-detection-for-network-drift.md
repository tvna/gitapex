# Use static AST parsing, not sys.addaudithook or DAST tooling, for find_network_drift's detection mechanism

## Status

Proposed

## Context and Problem Statement

Retrofit record: this decision is already implemented (issue [#1022](https://github.com/tvna/gitapex/issues/1022), closed via PR [#1027](https://github.com/tvna/gitapex/pull/1027), merged). This ADR documents rationale that currently lives only as prose inside `skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py`'s own module docstring, written after the fact rather than before the decision was made.

Issue #1022 requested a companion scanner cross-checking a skill's declared `spec.executionRequirements.network` (mode/domains) against what its bundled `scripts/*.py` actually do, catching the case where a skill declares `network.mode: disabled` while a bundled script performs real network I/O. The scanner (`find_network_drift`) must operate as a read-only, pre-execution check: per its own module docstring, it "must never itself run a skill's bundled scripts" -- the skill directories it scans are untrusted content from the reviewer's own threat model (a skill's bundled script could itself be adversarial or simply buggy), so executing them to observe behavior is not an option. A live design discussion on issue #1022 researched whether a dynamic/DAST-style approach -- including running a bundled script inside an isolated sandbox to observe its real behavior while containing the blast radius of that execution -- could replace or improve on static analysis for this detection.

## Considered Options

- Python's own `sys.addaudithook` (PEP 578) to observe network-related events at runtime
- Established DAST (Dynamic Application Security Testing) tooling
- Sandboxed/isolated execution (a container, OS-level namespace, or a similarly restricted subprocess) to observe a bundled script's real behavior while containing its blast radius
- Static analysis via Python's own `ast` module (stdlib)

## Decision Outcome

We will detect network-capable imports and literal `https?://` hosts via static AST parsing (Python's own `ast` module, stdlib), because all three alternatives require the target code to actually execute -- in full or inside an isolated copy -- to produce a signal, which is fundamentally incompatible with this scanner's own read-only, pre-execution safety constraint:

- `sys.addaudithook`'s own [PEP 578](https://peps.python.org/pep-0578/) documentation states plainly it is "not suitable for implementing a 'sandbox'" and only fires when the audited code path actually runs.
- Established DAST tooling targets a *running* application's own HTTP/UI surface -- there is no running application here, only a skill directory's static file content.
- A sandbox narrows the blast radius of running untrusted code; it does not eliminate the act of running it, which is exactly what this scanner's own stated invariant -- "must never itself run a skill's bundled scripts" (Context, above) -- exists to prevent. General-purpose isolation technology (containers, seccomp-bpf, gVisor-style user-space kernels) has a documented history of escape vulnerabilities, so "sandboxed" reduces the risk of executing adversarial code, it does not remove it. A sandbox harness is also itself a nontrivial, environment-dependent piece of infrastructure -- namespace/container-runtime availability, privilege level, and syscall-filtering support all vary by host -- working against this scanner's own portability requirement to run the same way across arbitrary CI runners, contributor machines, and restricted execution surfaces (`evaluating-skill-quality`'s own `spec.portability`), unlike `ast`, which is stdlib and runs identically in any Python 3 interpreter with no elevated privileges.

A real AST parse tree also has no comment nodes at all, so a commented-out reference can never register as usage without a filter having to say so, and the parser correctly distinguishes each real import syntax shape (`import X`, `import X.Y`, and `from X import Y` are each walked as their own distinct `ast.Import`/`ast.ImportFrom` node, not approximated by one regex trying to cover all three) before checking the parsed dotted module name against a fixed allowlist (`NETWORK_CAPABLE_MODULES`) -- string-membership matching, not Python's own runtime import resolution (which additionally handles `sys.path`, relative imports, and re-exports this scanner has no need to reproduce).

## Consequences

Good, because the scanner never needs to execute a skill's bundled scripts to produce a finding, holding the read-only safety constraint exactly.
Good, because a real parse tree gives exact, deterministic results for the shapes it does cover (same input always parses to the same finding) -- no reliance on brittle text-regex approximations of import syntax; unlike a text-regex scan, `ast.walk` also sees every import/call regardless of surrounding control flow (an `if False:`-guarded import is still a real `ast.Import` node in the tree), so conditional gating does not, by itself, evade this scanner -- verified directly: `ast.walk(ast.parse("if False:\n    import requests"))` still yields the `Import` node.
Bad, because static analysis cannot see every real network-capable call shape: a call routed through an unlisted helper function, or a host built at runtime (string concatenation, an f-string with a non-literal segment) can still slip past AST analysis exactly as it would past a human reading the same source. This is disclosed in the scanner's own docstring and demonstrated by a deliberately-constructed test (`test_dynamically_constructed_host_evades_allowlist_check`).
Bad, because `find_network_drift` only reads `skill_dir/scripts/*.py` -- a bundled non-Python script (e.g. a `.sh` file) is invisible to it, network-capable shell commands (`curl`, `wget`, `nc`, ...) included. Also disclosed and demonstrated (`test_non_python_bundled_scripts_are_not_scanned`).

## Confirmation

`skills/evaluating-skill-quality/scripts/test_gitapex_scan_execution_requirements_drift.py::test_dynamically_constructed_host_evades_allowlist_check` and `::test_non_python_bundled_scripts_are_not_scanned` are real, existing tests that pin the known limits of the chosen approach (Bad consequences above), so a future change to the detection mechanism that silently narrows or widens these limits would need to update these tests deliberately rather than by accident. No mechanism currently confirms the safety constraint itself (that the scanner never executes a bundled script) beyond code review -- relies on review for that specific property.
