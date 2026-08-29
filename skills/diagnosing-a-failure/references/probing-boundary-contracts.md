# Probing Boundary Contracts

Supports Step 4 (`SKILL.md`) -- the full technique for the three boundary
kinds Step 4 introduces in brief, plus the redistribution-aware
conditional clauses and two worked examples.

## Contents

1. [Why boundaries specifically](#why-boundaries-specifically)
2. [The three boundary kinds](#the-three-boundary-kinds)
3. [Redistribution-aware conditional clauses](#redistribution-aware-conditional-clauses)

## Why boundaries specifically

Some failures are not caused by wrong logic anywhere -- every function
along the path does exactly what it says. The failure is that two sides
of a boundary agree on a value's *shape* but not its *meaning*, or that a
precondition one side assumes is actually in effect turns out not to be,
in this specific context. Neither shows up as a logic bug when either
side is read in isolation; both show up only when the boundary itself is
interrogated.

## The three boundary kinds

### 1. Translation points

Does a contract's *meaning* hold across the boundary, not just its type
or its presence? A parameter that type-checks and is non-null can still
mean something different on each side.

**Worked example (real precedent found in this skill's own origin
repository):** a GitHub issue-update tool's `body` parameter turned out
to be a whole-body *replace*, not an append -- confirmed independently by
two sibling skills that both write to issue bodies, each recording the
same "never a partial update built from anything other than a fresh
fetch" rule. A caller that treats `body` as "the text to add" rather than
"the full text after this write" produces a failure that looks like data
loss or corruption downstream, with nothing wrong in either side's own
logic -- the boundary's *meaning* was mismatched, not its type.

**Probe:** for a boundary under suspicion, don't just check the value
passed -- check what each side's own documentation or prior-precedent
`references/` material says that value *means*, and whether both sides'
stated meanings actually match.

### 2. Binding assumptions / ownership boundaries

Is a precondition one side assumes actually in effect *in this specific
context* -- not in general, not in the context it was designed for?

**Worked example (real precedent found in this skill's own origin
repository):** a safety hook was wired in via an environment variable
naming its own plugin-install root (e.g. `"$PLUGIN_ROOT/hooks/check.sh"`);
in a plain repository clone rather than a plugin-installed deployment,
that variable was unset, and the hook was never wired into the tool-call
path at all -- silently, with no error. A design or a diagnosis that
assumes the hook's protection holds, without checking whether this
specific deployment context actually binds it, inherits a false
assumption invisibly.

**Probe:** name the binding assumption explicitly, then check it
directly in the current context, rather than assuming it holds because it
holds in the common case. Where the consuming repository has an
ownership record (e.g. `CODEOWNERS`), and the failure crosses a boundary
between two differently-owned areas, weight the hypothesis toward an
interface/ownership gap rather than a defect purely internal to either
side.

### 3. Dependency kind

Is the code on the failing side of the boundary this repository's own
logic, or a wrapped external dependency (a library, an API, a platform
service)?

**Probe:** if external, route any claim about that dependency's actual
behavior through `grounding-in-primary-sources` before treating it as
either the cause or ruled out -- a claim about a third-party tool's
behavior sourced from memory rather than its own current docs or the
observed live state is exactly the kind of unverified claim that skill
exists to catch. This skill's own investigation of the *local* system
does not need that skill's discipline applied reflexively -- only the
external-behavior claim does.

## Redistribution-aware conditional clauses

gitapex's own skills are installed into *other* repositories via `apm`,
not only used on gitapex itself -- so a technique should not be rejected
merely because gitapex's own repository lacks a supporting artifact for
it. These clauses degrade safely (per `SKILL.md`'s own Prerequisite note)
when the consuming repository has none of the following, and are used
when it does:

- **Strategic classification record** (a Core Domain Chart, a Wardley
  map): if the consuming repository maintains one, read the failing
  component's own classification. A component classified generic or
  commodity raises the prior on a boundary-kind cause (misuse,
  misconfiguration, an integration gap); one classified core or genesis
  raises the prior on the internal-loop investment (Steps 5-7) being
  worth the deeper trace.
- **Ownership record** (`CODEOWNERS` or equivalent): see boundary kind 2
  above.
- **Recorded event history**: see `tracing-and-instrumentation.md`'s own
  "When a recorded event history already exists" section.

None of these three is a mechanism this repository has ever built for
*detecting* whether a consuming repository's own artifact exists and is
current -- that detection stays a judgment call (per `SKILL.md`'s own
Prerequisite note), the same honest limit `establishing-ubiquitous-language`,
`executing-a-branch-plan`, `outward-artifact-preflight`, and
`grounding-in-primary-sources` already carry for their own equivalent
conditional inputs.
