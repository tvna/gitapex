# Code Quality Principles

Steps 6 and 8's own reference: 7 gitapex-filtered code-design principles,
each with one governing statement and one warning-sign example. Kept
deliberately concise rather than this directory's longer discursive
reference-file style elsewhere -- prompts to recognize a code smell while
writing or reviewing a diff, not a procedure to execute. Source and the
excluded-candidate accounting: `metadata/gitapex.yaml`'s own
`spec.references` decision entry for issue `#1388`.

## Contents

- [1. Type System Discipline](#1-type-system-discipline)
- [2. Boundary Discipline](#2-boundary-discipline)
- [3. Make Operations Idempotent](#3-make-operations-idempotent)
- [4. Migrate Callers Then Delete Legacy APIs](#4-migrate-callers-then-delete-legacy-apis)
- [5. Model the Domain](#5-model-the-domain)
- [6. Separate Before Serializing Shared State](#6-separate-before-serializing-shared-state)
- [7. Foundational Thinking](#7-foundational-thinking)

## 1. Type System Discipline

**Governing statement:** encode an invariant in the type itself so the
type-checker rejects an invalid state at compile/check time, rather than
documenting the invariant in a comment or re-deriving it with a runtime
check at every call site.

**Warning sign:** a function parameter is typed as a broad primitive
(`string`, `any`, `dict`) and the function's own first few lines parse,
validate, or narrow it before doing anything else -- the narrowing
belongs in the parameter's own type, not in the function body.

## 2. Boundary Discipline

**Governing statement:** validate and shape external data exactly once,
at the module or service boundary where it enters; everything past that
boundary trusts the shape the boundary already enforced.

**Warning sign:** the same field is re-validated (null-checked,
range-checked, re-parsed) at two or more internal call sites, with no
evidence of a bypass the first checkpoint misses. Incidental, reflexive
re-validation only -- a second checkpoint `diagnosing-a-failure` or a
blast-radius judgment actually showed is needed is a deliberate layer,
not this warning sign.

## 3. Make Operations Idempotent

**Governing statement:** design an operation so invoking it twice with
the same input leaves the system in the same end state as invoking it
once -- no duplicated side effect from a retry.

**Warning sign:** a retried request (timeout, network blip, at-least-once
delivery) creates a second row, message, or charge instead of converging
on the same one an earlier, successful-but-unacknowledged attempt already
produced.

## 4. Migrate Callers Then Delete Legacy APIs

**Governing statement:** move every call site to the new API first,
confirm each migrated call site actually works, and only then delete the
old API -- never delete while a caller still references it.

**Warning sign:** a deprecated function or endpoint is removed in the
same change that introduces its replacement, with the removal's own diff
never actually enumerating which call sites were checked.

## 5. Model the Domain

**Governing statement:** when code branches a lot or repeats the same
shape assumption across files, encode the domain in one structure (a
state machine, a typed model, a registry, a reducer) instead of leaving
it scattered across conditionals -- distinct from Type System Discipline
above, which names an invalid *value* unrepresentable; this names an
invalid *combination of state* unrepresentable.

**Warning sign:** the same `if status == "x" and flag_y and not
flag_z`-shaped condition, or an equivalent chain of booleans, is
duplicated (exactly or with drift) across several files or functions
that all need to agree on which states are actually reachable together.

## 6. Separate Before Serializing Shared State

**Governing statement:** "serializing" here means arbitrating concurrent
access (forcing writers to take turns), not data serialization -- when
multiple writers can touch the same shared state concurrently, resolve
ownership or partitioning of that state before reaching for a
serialization mechanism (a lock, a mutex, a queue, a shared worktree) to
arbitrate the conflict.

**Warning sign:** a lock is added around a shared mutable structure to
stop writers from interleaving, without first asking whether the
structure should instead be partitioned so each writer owns a disjoint
slice and no lock is needed at all.

## 7. Foundational Thinking

**Governing statement:** settle the core data shape -- what fields exist,
what a name refers to, what concurrent actors actually share -- before
writing the logic that operates on it; get infrastructure a later phase
depends on (types, a schema, a CI check) in place before building the
feature that assumes it, not the other way around.

**Warning sign:** a task writes business logic against a data shape still
being decided elsewhere in the same change, or before the infrastructure
it depends on (a schema migration, a type definition) actually exists --
forcing a rewrite once the shape settles instead of settling it first.
