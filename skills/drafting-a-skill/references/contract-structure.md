# Contract structure for a drafted skill

Loaded on demand: `SKILL.md`'s own Step 4 already states the three-part Precondition/Steps/Postcondition definition and the never-both rule directly in the body -- load this file for the fault-attribution rule, deeper worked examples, and the drafting checklist, when that inline definition alone doesn't resolve a real drafting question (or earlier, if Step 1's candidate job is already fuzzy enough that a contract shape would sharpen it). This file exists so a draft's Precondition, Steps, and Postcondition are written as a real contract, in Bertrand Meyer's Design by Contract sense of the term -- the same framing the review that later grades a draft already applies to itself, in its own Contract discipline section; see this skill's own `references/gitapex-cross-links.md` for the exact sibling-skill citation this shared framing depends on. Drafting and reviewing are separate bounded contexts (see this skill's own SKILL.md), but they share one vocabulary for what a contract is, so a drafted skill and the review that later grades it are talking about the same thing.

## The three parts, applied to a skill

- **Precondition** -- what must already be true before Step 1 begins, stated as one or a few checkable bullets, not scene-setting prose. This is the caller's (the invoking agent's, or the human directing it) obligation: if the Precondition doesn't hold and the skill is invoked anyway, that is a misuse, not a defect in the skill.
- **Steps** -- the routine body. Each Step is one action plus the local reasoning a reader needs to execute it correctly; it may assume everything the Precondition already established, and must not re-derive it.
- **Postcondition** -- what the skill guarantees once its Steps finish, stated so a caller can rely on it without re-reading the Steps. Write this to match what the skill's own last Step actually hands off, not an aspirational description of what a "good" run would produce.

An **Invariant** (something that stays true across every Step, not only at the boundaries) is optional -- most procedural skills don't need one. Declare it only when a real cross-step invariant exists (for example, "the target skill directory is never partially written to disk between Steps"), not as boilerplate.

## Fault attribution

The shared Design-by-Contract source this framing rests on (see this skill's own `references/gitapex-cross-links.md` for the sibling-skill citation this quote is taken from) states this principle directly: "A precondition violation indicates a bug in the client (caller). ... A postcondition violation is a bug in the supplier (the routine)." Applied to a drafted skill: if a run fails because the Precondition didn't actually hold (the skill was invoked for the wrong kind of request), that is a bug in how the request was routed to this skill -- fix the routing or the Precondition's own wording, not the Steps. If a run fails despite the Precondition genuinely holding, that is a bug in the Steps themselves. Write the Precondition precisely enough that this distinction is checkable, not a matter of judgment after the fact.

## Never both

Also from that same shared source (again, `references/gitapex-cross-links.md` carries the sibling-skill citation), stated as "an absolute rule": a condition is checked in exactly one place -- "either you have the condition in the [precondition], or you have it in an If instruction in the [routine's] body ... but never in both." A redundant re-check is not extra safety; it is a sign the responsibility split between Precondition and Steps was never actually decided.

Applied while drafting:

- Don't restate a Precondition bullet as an `if`-guard inside Step 1 -- the Precondition already owns that check. A Step that re-verifies its own Precondition is hedging against callers it should instead route away at the Precondition boundary.
- Don't bury a real precondition inside a later Step's prose where a reader has to infer it actually applied before Step 1 too. If a condition must hold before the whole procedure starts, it belongs in the Precondition section, not smuggled into the middle of the Steps.
- When two Steps could plausibly both check the same thing (for example, a metadata choice elicited at one Step and silently re-confirmed at another), pick exactly one owner and have the other Step consume that Step's own output instead of re-deriving it. This skill's own Step 3 and Step 5 apply this rule against a different kind of duplication -- see `references/mechanism-fit-and-cohesion.md` for why those two Steps are written as advisory self-checks rather than a second authoritative judgment of a question `evaluating-skill-quality` already owns exclusively.

## A drafting checklist

Before treating a draft's contract shape as done:

1. Does the Precondition state checkable facts, not narrative context?
2. Does any Step re-check something the Precondition already established? If so, drop the re-check or move the condition down into the Precondition -- never keep both.
3. Does the Postcondition match what the last Step actually produces, word for word in substance -- not a rounder, more optimistic summary of it?
4. If an Invariant is declared, is it genuinely true across every Step, including the failure/escalation branches -- not only the happy path?
