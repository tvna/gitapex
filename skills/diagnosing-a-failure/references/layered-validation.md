# Layered Validation

Supports Step 4 (`SKILL.md`) and Step 8's Verdict content -- what a
"checkpoint map" is and when adding more validation layers is actually
warranted. Deliberately named `layered validation`, not `defense-in-depth`:
some consuming repositories already reserve the term `defense-in-depth`
for a different, broader sense -- layering *safety controls* (prompts,
hooks, CI, review, operator procedure) rather than layering
*code-correctness checkpoints*, which is what this file's own technique
covers. Where the calling repository has an established meaning for
`defense-in-depth`, defer to it and use `layered validation` here
instead, rather than assuming readers will disambiguate two different
concepts sharing the same words from context alone.

## Core principle

One validation point can be bypassed -- by a different code path, a
refactor, or a mock that skips it. Multiple layers, each independently
checking the same invariant at a different point in the data's path,
make the failure mode structurally harder to reintroduce even after this
diagnosis is closed.

## Where this fits in a Diagnosis

This skill investigates and produces a Verdict -- it does not implement a
fix. What it *does* own is naming which checkpoints exist along the
failure path (Step 4's boundary map already collects this), and stating
in the Verdict which of those checkpoints validated correctly and which
did not. That checkpoint map is handed to the caller alongside the
Verdict; whether the caller adds validation at every layer the map
names, or only at the one that actually failed, is scoped by the calling
Issue/ACM -- not mandated unconditionally by this skill. This is a
deliberate, stated tension with the source material's own "ALWAYS
validate at every layer" framing: a repository's own minimal-fix
discipline, where one exists, means a full four-layer retrofit is not
automatically warranted just because a Diagnosis surfaced the checkpoint
map.

## The four checkpoint kinds worth naming in a map

Not a fixed layer count to always fill in -- name only the checkpoints
that genuinely exist on this failure's own path:

- **Entry validation** -- does the boundary the bad value first crosses
  (a function argument, an API parameter, a config read) reject it, or
  silently accept it?
- **Business-logic validation** -- once past entry, does the code that
  actually uses the value re-check it makes sense for *this* operation,
  or trust the caller unconditionally?
- **Environment/context guards** -- is there a check that a dangerous
  operation is only reachable in the context it's meant for (e.g. a
  destructive operation gated on not running against production data)?
- **Instrumentation** -- if all three above are silent, is there any
  logging capturing enough context (the value, the call stack, the
  environment) to have made this Diagnosis faster? Its absence is itself
  a finding worth naming in the Verdict, even when it isn't the fix.

## When multiple layers genuinely earn their place

Not a default -- reserve it for a case where a single checkpoint has
already been shown, in this Diagnosis's own evidence, to be bypassable by
more than one real path (not merely hypothetically bypassable). A
checkpoint that has only ever been reached one way does not yet justify
a second layer on its own account; that judgment belongs to the caller,
applying whatever irreversible-operation and blast-radius guidance the
calling repository has, informed by this Diagnosis's checkpoint map, not
decided here.

## Applying it during a Diagnosis

1. Trace the data flow (per `tracing-and-instrumentation.md`) to the
   earliest divergence point.
2. List every checkpoint the bad value passed through on its way there,
   using the four kinds above as a checklist, not a mandate.
3. For each checkpoint, note validated / silently passed.
4. Include the resulting checkpoint map in the Diagnosis Verdict (Step
   8) -- this is the map the caller uses to scope its own fix, not a
   direction to add every missing layer.
