# Script test quality

Dimension 7's deeper grading pass for a bundled script's *test suite*,
factored out of `references/rubric.md` because it only applies when the
reviewed skill ships a script with its own test suite -- most skills do
not, so skipping this file is not itself a finding. Dimension 7's five
core bullets in `references/rubric.md` (solve-don't-punt, no voodoo
constants, dependencies/execution intent, clear documentation, verifiable
intermediate outputs) already grade the script's code quality; this file
grades a distinct question -- the rigor of the test suite itself.

## Table of contents

- [Test methodology](#test-methodology)
- [Test code structure and design](#test-code-structure-and-design)
- [References](#references)

## Test methodology

Using ISTQB's ([istqb]) systematized categories rather than an ad hoc
"are there tests" check. This content is drawn from established
knowledge of the ISTQB CTFL syllabus rather than a live fetch of the
primary PDF -- confirm specific technique wording against the current
official syllabus before treating any phrase below as a verbatim quote
from it.

- **Test levels named explicitly.** Component/unit-level (the script's
  functions exercised in isolation, e.g. via direct import) is not the
  same claim as integration-level (the script exercised end-to-end
  through its actual CLI entry point -- argv parsing, exit codes, stdout
  contract) or system-level (the whole skill procedure invoking it as
  written). A test suite that only ever imports internals and never
  invokes the real CLI path has an unstated integration-level gap, even
  if unit coverage is thorough.
- **Test design technique diversity**, across ISTQB's three categories --
  a large suite that only ever varies one dimension is not automatically
  a mature one:
  - *Black-box*: equivalence partitioning (valid and invalid input
    classes named as classes, not just "some passing and some failing
    cases"); boundary value analysis (exact-limit, one-under, and
    one-over cases for every numeric or length constant the script
    enforces); decision table testing (when the script's logic branches
    on a combination of independent conditions, a table names the
    combinations actually exercised rather than a handful of ad hoc
    cases); state transition testing (for a script with sequential or
    stateful behavior).
  - *White-box*: statement/branch coverage as a measurable floor, not
    "we wrote a lot of tests" -- name the coverage tool and threshold if
    one is configured; if none is, say coverage is unmeasured rather than
    silently treating test count as a coverage proxy (the same
    never-silently-skip discipline dimension 8 applies to unmeasured
    behavioural evidence).
  - *Experience-based*: error guessing and exploratory probing for
    inputs the author expects to break the script (malformed encoding,
    adversarial fixtures) -- complementary to the systematic techniques
    above, not a substitute for them.
  - Fail: a suite that is large but single-dimensional (all valid-input
    variants with no boundary or invalid-class case, or the reverse).
    Pass: the suite's cases are traceable to which technique(s) produced
    them, even briefly, so coverage-by-design is inspectable rather than
    incidental.
- **Static testing as a distinct, prior layer.** ISTQB's review taxonomy
  (informal review, walkthrough, technical review, inspection -- in
  increasing formality) and static analysis (linting, type-checking) both
  catch defects before the script ever runs, cheaper than a dynamic test
  run. Name which layer(s) actually apply to the script under review
  (e.g. "PR review is this script's technical review; no linter or
  type-checker is configured" is a specific, legitimate answer) rather
  than treating the dynamic test suite as the only quality gate.
- **Risk-based prioritization.** Deeper technique coverage (more
  boundary and decision-table cases) belongs on the script's
  highest-risk logic -- fail-closed parsing, anything security- or
  data-integrity relevant -- with lighter coverage on low-risk paths.
  The same principle rubric.md's dimension-7 "verifiable intermediate
  outputs for high-stakes... work" bullet already applies to output
  artifacts, extended here to how test effort itself is allocated.
- **Defect-to-regression traceability** -- a narrow, single-script echo of
  one TMMi ([tmmi]) process area (Defect Prevention: root-causing a found
  defect and feeding it back into the test process so it cannot recur),
  not the staged organizational framework TMMi actually is -- see
  rubric.md's dimension 8 for where that fuller maturity-staging concept
  applies instead, and why TMMi's organizational apparatus (test policy,
  test-organization roles, cross-project staging) has no referent at this
  single-script scale. At this scale the citable form is simple: does a
  regression test name the specific defect or review finding it exists to
  prevent recurrence of (e.g. a comment citing the issue or PR where the
  defect was found), so a future reader can tell a case is a deliberate
  regression guard rather than incidental coverage. This is not
  hypothetical for this repository -- its own script test suites already
  do this pervasively, e.g. `test_check_skill_shape.py`'s many
  `# Regression guard (issue #N)` / `# Regression (Codex review on PR
  #N)` comments. Fail: a regression-motivated test with no stated defect
  provenance, indistinguishable from an arbitrarily added case. Pass: the
  provenance is visible in the test itself (a comment or name), not only
  in an external PR description a future reader of the test file would
  never see.

## Test code structure and design

Using Gerard Meszaros's xUnit Test Patterns ([xunittestpatterns])
catalog: fixture setup/teardown patterns, test-double usage, and named
test smells, rather than an ad hoc "the tests look clean" read. This
content is drawn from established knowledge of the book's catalog rather
than a live fetch of the primary text -- the book is not a freely
fetchable web document, and the two primary sources tried for this
content in this session (the author's own companion site and the
publisher's listing page) both returned a network-policy denial, the
same egress-blocked pattern the Test methodology section above already
documents for its own sources -- confirm specific pattern names and
definitions against the book before treating any phrase below as a
verbatim quote from it.

- **Fixture design.** Fresh Fixture (each test builds and tears down its
  own isolated test data) vs. Shared Fixture (fixture state persists or is
  deliberately reused across tests, typically for performance) -- a suite
  that claims isolation while actually sharing mutable fixture state across
  tests is a real defect (Interacting Tests, below), not a style choice.
  Prefer automatic teardown (a fixture-scoped mechanism the harness runs
  regardless of pass/fail) over manual teardown code an author must
  remember to write and that a failing assertion can skip entirely.
- **Test-double usage**, matched to what the double actually needs to do: a
  Dummy (never used, only fills a required parameter), a Stub (returns
  canned answers, no interaction verification), a Spy (records calls for
  the test to inspect afterward), a Mock (pre-programmed with expectations,
  fails the test itself if the expected interaction does not occur), and a
  Fake (a working but simplified stand-in, e.g. an in-memory store for a
  real database). Reaching for a Mock where a Stub would do -- asserting on
  incidental interaction detail no requirement actually cares about --
  couples the test to implementation rather than behavior; reaching for a
  Stub where the test's actual point is verifying an interaction happened
  is the opposite miss. Where the code under test has no external
  collaborator to substitute at all (pure functions, or I/O confined to a
  harness-provided sandbox), say so explicitly rather than treating an
  absence of test doubles as an unexplained gap.
- **Named test smells** -- treat each as a specific, citable defect, not a
  vague "could be cleaner":
  - *Mystery Guest*: the test depends on external state invisible in the
    test itself (a file elsewhere on disk, a database row, an environment
    variable) that a reader cannot see by reading the test alone.
  - *Eager Test*: one test method exercises several unrelated behaviors, so
    a failure does not say which behavior broke without reading the
    assertion that tripped. A test that asserts several *related*
    consequences of one root cause is not this smell by itself -- the
    question is whether the assertions trace to one cause, not their count.
  - *Test Code Duplication*: the same setup or assertion logic copy-pasted
    across tests instead of factored into a shared Creation Method (a
    parameterized helper that builds a ready-to-use fixture, taking only
    the parameters relevant to what a given test varies) or Custom
    Assertion.
  - *Conditional Test Logic*: an `if`, loop, or other branch inside a
    test's own body, which makes the test's own correctness something that
    now needs testing. A loop iterating a fixed, hardcoded literal with an
    identical per-item assertion is a milder instance of this than
    data-dependent branching, but is still the named smell in its literal
    form -- cite it as such rather than waving it through because it looks
    tame. Prefer a real parameterized test (the harness's own
    data-driven-test mechanism, e.g. `pytest.mark.parametrize`) over a
    manual loop with inline branching: it also isolates and reports which
    specific case failed, which a bare loop does not.
  - *Assertion Roulette*: several assertions in one test with no
    distinguishing message, so a failure does not say which one fired.
  - *Interacting Tests*: a test's outcome depends on another test having
    run first (order-dependent shared state), so tests fail differently in
    isolation than in the full suite.
- Fail: fixture state leaks between tests with no stated reason, a test
  double is used purely because it is the most capable option regardless of
  what the test needs, a named smell above is present with no mitigation,
  or setup is duplicated ad hoc across tests with no Creation Method
  emerging. Pass: fixtures are fresh and self-contained (or a Shared
  Fixture's reuse is deliberate and stated), test doubles are the least
  powerful kind that gets the job done (or their absence is explained by
  the code under test having no collaborator to substitute), and repeated
  setup has been factored into a named, reusable helper rather than
  copy-pasted.

## References

Every inline `[label]` citation above resolves to the source below.

- **[istqb]** ISTQB (International Software Testing Qualifications
  Board) -- Certified Tester Foundation Level Syllabus, v4.0, 2023.
  <https://istqb.org/certifications/certified-tester-foundation-level-ctfl-v4-0/>
- **[xunittestpatterns]** Gerard Meszaros -- xUnit Test Patterns:
  Refactoring Test Code, Addison-Wesley, 2007.
  <http://xunitpatterns.com>
- **[tmmi]** TMMi Foundation -- Test Maturity Model integration (TMMi).
  Version unverified against the publisher -- this session's fetch of
  tmmi.org returned HTTP 403, the same egress-blocked pattern this file's
  ISTQB and xUnit Test Patterns sources already hit; confirm the current
  release before citing a specific number.
  <https://www.tmmi.org/tmmi-model/>

<!-- Link reference definitions below power the inline [label] shortcuts; keep in sync with the visible list above. -->

[istqb]: https://istqb.org/certifications/certified-tester-foundation-level-ctfl-v4-0/ "ISTQB -- Certified Tester Foundation Level Syllabus, v4.0, 2023"
[xunittestpatterns]: http://xunitpatterns.com "Gerard Meszaros -- xUnit Test Patterns: Refactoring Test Code, Addison-Wesley, 2007"
[tmmi]: https://www.tmmi.org/tmmi-model/ "TMMi Foundation -- Test Maturity Model integration (TMMi); version unverified, tmmi.org fetch returned HTTP 403 this session"
