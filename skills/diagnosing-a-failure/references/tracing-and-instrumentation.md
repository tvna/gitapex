# Tracing and Instrumentation

Supports Step 4 (`SKILL.md`) -- how to walk a boundary map back to its
earliest divergence point once the map itself exists. See
`layered-validation.md` for what to do once the earliest divergence point
is found.

## Core principle

A failure that surfaces deep in a call chain is rarely caused there.
Trace backward, one caller at a time, until the chain stops -- that stop
point, not the surface symptom, is what Step 4's boundary map is built
around. Fixing only where the error appears leaves the actual trigger
free to resurface through a different path.

## The trace, one hop at a time

1. **Observe the symptom** exactly as it presents (the error text, the
   wrong value, the line it appears on).
2. **Find the immediate cause** -- the one line of code that directly
   produces the symptom.
3. **Ask what called it**, and with what arguments. Do not assume; read
   the actual call site.
4. **Keep tracing up** one hop at a time. At each hop, ask: is the value
   passed in already wrong, or does it go wrong here?
5. **Stop at the earliest point the value was already wrong** -- this is
   Step 4's earliest-divergence point, not necessarily the outermost
   caller. Tracing past it (into code that received an already-bad value
   and merely propagated it) adds nothing.

## When manual tracing dead-ends: add instrumentation

If the call chain isn't traceable by reading alone (async boundaries,
generated code, a third-party call you can't step into), add temporary
logging immediately before the operation that fails, capturing: the
input values, the current working context (directory, environment,
session), and a captured stack trace. **Never log a secret's own value**
-- a credential, token, key, or PII field -- treating every debug output
sink as an attack surface; if a suspect value might be one, log which
field carried it and its shape (present/absent, length), not its
content. Run the failing path -- a shell command, a test invocation, or
whatever reproduces it -- capture the output, and
read the stack trace for the calling file/line rather than guessing from
the symptom alone. Remove the instrumentation once the divergence point
is found -- it is a diagnostic aid, not a permanent addition (a permanent
one is a Step 8 `root-cause-confirmed` Verdict follow-up for the caller
to decide, not something this skill leaves behind on its own authority).

## When a recorded event history already exists

Where the consuming repository maintains a recorded event history (event
sourcing, an append-only audit log, a maintained Event Model), prefer
reading it over hand-tracing: build the expected-vs-actual comparison
directly from the record rather than re-deriving it by manual
instrumentation. `executing-a-branch-plan`'s own Execution log is a
concrete example already shipped in this repository -- its
`TaskCompleted{commit_sha}` events are reconciled against real branch
state on resume, the same "record vs. observed reality" comparison this
step performs generally. This is the Decision 4 Prerequisite note's own
conditional: use the record when one genuinely exists and its currency
is confirmed, fall back to manual tracing otherwise.

## What "the earliest divergence point" is not

It is not necessarily the first line of the program, and it is not
necessarily a bug in code your team owns -- Step 4's own three boundary
kinds (translation point, binding assumption/ownership boundary,
dependency kind) exist precisely because the earliest divergence can sit
at any of them. A trace that dead-ends at a boundary you cannot see past
(a third-party library's internals, a system call) is itself a valid
stopping point -- route it through `grounding-in-primary-sources` before
concluding the boundary itself is the cause, per `probing-boundary- contracts.md`.
