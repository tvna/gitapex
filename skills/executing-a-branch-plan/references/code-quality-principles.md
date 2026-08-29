# Code Quality Principles

Step 6 and Step 8's own reference. Source: issue `#1388`, a
gitapex-filtered subset of 7 principles (from a candidate set of 21
surveyed against `cursor/plugins`' `pstack` collection) that duplicate no
existing gitapex principle -- CLAUDE.md sections 1-5's own discipline, or
a sibling skill's own coverage, was checked for each of the 14 excluded
candidates before this file was written; see the issue for the full
per-candidate accounting. Kept deliberately concise, one governing
statement plus one warning-sign example per principle, rather than this
directory's longer discursive reference-file style elsewhere -- these are
prompts to recognize a code smell while writing or reviewing a diff, not
a procedure to execute.

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
range-checked, re-parsed) at two or more internal call sites downstream
of the boundary that already validated it once.

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

**Governing statement:** give a business concept its own type or value
object instead of carrying it as the primitive it happens to be stored
in -- the type is where the concept's own rules live.

**Warning sign:** a concept like an email address, a money amount, or an
identifier is passed between functions as a bare `string`/`float`, with
its format or range assumptions re-asserted ad hoc at each new usage site
rather than made structurally impossible to violate.

## 6. Separate Before Serializing Shared State

**Governing statement:** when multiple writers can touch the same shared
state concurrently, resolve ownership or partitioning of that state
before reaching for a serialization mechanism (a lock, a mutex, a queue)
to arbitrate the conflict.

**Warning sign:** a lock is added around a shared mutable structure to
stop writers from interleaving, without first asking whether the
structure should instead be partitioned so each writer owns a disjoint
slice and no lock is needed at all.

## 7. Foundational Thinking

**Governing statement:** before writing new code for a capability, check
whether a lower layer -- a language builtin, an already-imported library,
the platform itself -- already provides it, rather than re-implementing
it bespoke at the application layer.

**Warning sign:** a hand-rolled retry/backoff loop, date parser, or
cache-eviction routine sits beside an already-available library import
that provides the same behavior with its own edge cases already handled.
