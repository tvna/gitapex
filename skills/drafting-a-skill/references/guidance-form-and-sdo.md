# Guidance form and Single Decisive Outcome (SDO)

Loaded on demand: `SKILL.md`'s own Step 4 already states the guidance-
form basics and Step 5 already states the SDO one-sentence test directly
in the body -- load this file when that floor isn't enough for a real
drafting question (phrasing a Step that resists the "one sentence, no
'and'" test cleanly, or wanting the fuller rationale behind guidance
form). Two parts: how a Step should read (guidance form), and the deeper
elaboration of the test that tells you whether a Step, or a whole draft,
is trying to do one job or several (Single Decisive Outcome).

## Guidance form

A Step is an instruction a capable-but-context-free reader will follow
under time pressure. Write it that way:

- **Verb-first, one action per Step.** "Read the issue and extract its
  acceptance criteria" is one Step doing one thing. "Read the issue,
  extract its criteria, and also check whether the branch already exists"
  is two Steps wearing one number -- split it, per this file's own SDO
  test below.
- **Checkable, not evaluative.** "Confirm the target file exists" is
  checkable. "Make sure the target is reasonable" is not -- a reader
  cannot tell whether they've satisfied it. If a Step needs judgment, say
  what the judgment is actually weighing ("assess whether the change is
  reversible; if not, require explicit confirmation before continuing"),
  not just that judgment is required.
- **State the why only when it changes what a reader does.** A Step that
  says "run the checker (it catches shape defects CI would otherwise
  reject)" earns its parenthetical -- it tells a reader why skipping it is
  costly. A Step that explains background context with no bearing on
  execution is prose that belongs in `SKILL.md`'s own introduction or a
  reference file, not inline in the Step.
- **Name the escalation path inline, not as an afterthought.** If a Step
  can fail in a way the rest of the procedure can't route around, say so
  in the Step itself -- this skill's own Step 2 does this directly ("When
  the candidate genuinely fits neither list cleanly ... escalate to the
  requester with the specific ambiguity named"), not only in a separate
  Stop-boundaries bullet a reader may never reach.
- **Cite primary sources for a claim about an external tool, library, or
  platform**, per this repository's own `grounding-in-primary-sources`
  discipline -- a Step asserting how something outside this repository
  behaves needs a citation, not "as far as I know."

## Single Decisive Outcome (SDO)

**A well-formed Step, and a well-formed skill, each produce exactly one
decisive outcome.** This is the operational form of functional cohesion
(Stevens/Myers/Constantine's strongest cohesion class -- see
`references/mechanism-fit-and-cohesion.md` for how Step 5 uses the full
seven-way taxonomy): rather than asking "is this cohesive?" in the
abstract, ask "if I had to name the one thing this Step (or this whole
draft) decides or produces, could I do it in one sentence, without an
'and'?"

Apply the test at two levels:

- **Per Step.** "Extract the issue's acceptance criteria" -- one outcome
  (a list of criteria). "Extract the issue's acceptance criteria and
  decide whether the branch needs rebasing" -- two outcomes fused into one
  Step; a reader who only needs the first has to read past the second to
  find it, and a failure in the second silently blocks the first.
- **Per skill.** If a draft's own Steps decide two things that don't share
  a caller, a trigger, or a single Postcondition a reader could state in
  one sentence, that draft is probably two skills wearing one `SKILL.md`.
  This is exactly what Step 5 checks for, using the SDO test as its
  entry point before reaching for the full cohesion taxonomy.

**A failed SDO test is a drafting signal, not a verdict.** Finding two
outcomes in one Step means rewrite that Step (or split it into two
numbered Steps); finding two outcomes across the whole draft means route
back to Step 1 and draft two skills instead of one non-cohesive one. It is
not, on its own, the authoritative cohesion finding `evaluating-skill- quality` produces at handoff -- see `references/mechanism-fit-and- cohesion.md`'s "Step 5 and Step 7 are advisory" section for why that
distinction matters and how it's worded.

**A false failure is possible too.** Two Steps can look like they serve
different outcomes while actually converging on one: a Step that gathers
facts and a Step that acts on them are still one decisive outcome ("a
decision made on gathered evidence") if the whole draft's Postcondition
names that single, combined result. When a Step or a draft passes the
"one sentence" test only by stretching the sentence into a run-on, that
stretch is itself the finding -- name the two things the run-on is joining
rather than accepting the sentence as proof of cohesion.
