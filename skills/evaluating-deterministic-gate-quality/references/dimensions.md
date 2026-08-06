# Deterministic-gate quality dimensions

Two lanes, mirroring `evaluating-skill-quality`'s own split:

- **Deterministic-shape checks** (1-6) -- fixed rules; a script could
  grade these mechanically if one existed for the target's own tooling.
  `scripts/gitapex_check_gate_shape.py` now mechanically grades dimensions 1, 2,
  4, 5, and 6 (dimension 3 as a disclosed heuristic only, never a hard
  fail) for Domain 2 (agent-harness hook subprocess) targets -- see that
  script's own module docstring for exactly which sub-checks it runs and
  why it is scoped to that one domain. Domains 1, 3, and 4 (git hook, CI
  job step, MCP server subprocess) have no bundled checker yet (see
  `SKILL.md`'s Lifecycle note); apply the checks below to those domains,
  and to whatever a Domain-2 target's own manual judgment still requires,
  by direct inspection.
- **Probabilistic-maturity dimensions** (7-22) -- need judgment; walk all
  of them, quoting the specific evidence that earns each verdict.

Every dimension is tagged with its own **domain-generalization scope**,
established for this build rather than left implicit:

- **Generalizes directly** -- the dimension's own statement is already
  domain-generic; apply it unchanged in any of the four domains.
- **Generalizes with adaptation** -- the underlying concern is
  domain-general, but the concrete failure mode or fix is domain-specific
  vocabulary; a per-domain note is given.
- **Domain-N-only / inapplicable elsewhere** -- the dimension names a
  mechanism that only exists in one domain, or does not exist by
  construction in another; graded there only, named explicitly rather
  than silently skipped.

One dimension currently carries a second, independent scoping tag
alongside domain-generalization -- **precondition-scoped applicability**
(dimension 22 below; more may gain it as the skill grows).
Domain-generalization asks *which of the four domains*; precondition
scoping asks whether the target's own operational capability -- something
that can be present or absent regardless of domain -- supports the
dimension at all. Where the precondition is absent, the dimension is
graded not-applicable, the same explicit-rather-than-silent treatment
domain-inapplicability already gets (see dimension 8). The two axes
compose independently: a dimension can carry both a domain-generalization
tag and a precondition-scope note at once.

## Contents

1. [Deterministic-shape checks](#deterministic-shape-checks)
2. [Probabilistic-maturity dimensions](#probabilistic-maturity-dimensions)

This numbering is a re-derivation for this skill's own build: one earlier
dimension (trust/blast-radius classification) was promoted into its own
`SKILL.md` axis, and a fourth cross-cutting axis (Security-level /
Zero-Trust maturity classification) was added later still, directly in
`SKILL.md` rather than as a numbered dimension here. See `SKILL.md`'s own
axis section and `references/security-level.md` for the full test and its
differentiation from dimensions 1 and 15 below.

## Deterministic-shape checks

1. **Deny path is non-bypassable-by-default, not silently downgraded to
   advisory.** A gate meant to block an action can fail to actually block
   it without anyone noticing at authoring time -- e.g., a check that
   reports failure but is not wired into what actually gates the guarded
   action (a required status, a hard exit, a rejected tool call).
   *Domains:* generalizes with adaptation. Agent-harness hook: the
   platform's own deny signal (e.g. a specific exit code, or a specific
   structured field) must be used, not a generic non-zero exit that
   degrades to non-blocking. CI job step: the job must both fail *and*
   be wired as a required check the merge path cannot bypass -- a red job
   that is not required blocks nothing, and an admin-bypass setting (e.g.
   `enforce_admins: false`) makes even a required check optional for some
   actors; check the platform's branch-protection configuration directly,
   not only the workflow YAML. Git hook subprocess: the hook
   must exit non-zero *and* the invocation path must not offer an
   unlogged bypass flag. MCP server subprocess: the response must surface
   as an actual tool error/denial the calling agent cannot route around,
   not merely disregardable text.
2. **Dual-signal deny (defense in depth across every channel the caller
   might read).** A deny decision is signaled through every channel the
   calling context might plausibly consult, not only the one channel a
   test happens to check.
   *Domains:* generalizes with adaptation. CI job step: job status
   *and* a required-check gate *and*, where useful, a visible annotation.
   Agent-harness hook: a structured decision field *and* a human-readable
   message on the channel the harness actually surfaces to the caller.
   Git hook subprocess: exit code is the only hard channel available;
   any message channel is soft (client-dependent), so this domain has
   structurally less redundancy available than the others -- note that
   as a real constraint, not a finding against the gate.
3. **Self-revalidation of the specific condition being gated.** The gate
   re-checks the specific condition it exists to enforce, rather than
   trusting the invocation context's own routing/filter/matcher to have
   selected correctly.
   *Domains:* generalizes directly. A CI job re-checks the event/path
   condition itself rather than trusting a trigger filter alone; an MCP
   tool handler re-validates the calling tool/method rather than trusting
   the server's own route dispatch; a hook re-validates its own
   matcher-relevant field.
4. **A bundled test exists beside the gate's own logic.** The gate's
   behavior is exercised by an automated test living alongside it, not
   only implied by the gate's own prose.
   *Domains:* generalizes directly.
5. **Untrusted input is never interpolated unsafely into a shell/command
   string.** Any value from outside the gate's own trust boundary (a
   branch name, a PR title, a tool-call argument) that reaches a
   shell/command invocation is passed through a parameterized/exec-form
   mechanism, never string-concatenated into an interpretable command.
   *Domains:* generalizes with adaptation. Agent-harness hook: exec-form
   argument arrays instead of a shell-form string. CI job step: `env:`
   indirection instead of directly interpolating an untrusted value into
   a `run:` block (a well-documented CI-injection class). MCP server
   subprocess and git hook subprocess: parameterized subprocess
   invocation, same underlying concern.
6. **Timeout/budget is set explicitly and is proportionate to the
   check's actual cost.** An unset timeout silently inherits whatever
   default ceiling the domain provides -- often much longer than the
   check actually needs -- which is a long time to block whatever the
   gate is sitting in front of.
   *Domains:* generalizes directly, with one domain-specific gap worth
   naming: a git hook subprocess has no built-in timeout mechanism at
   all -- if the invoking tooling does not add one, a hung git hook
   blocks indefinitely. Grading a Domain-1 gate should check whether the
   surrounding invocation (not the hook script itself) supplies a bound.

## Probabilistic-maturity dimensions

7. **Mechanism fit, trigger/event direction.** Does the specific
   event/trigger the gate is attached to actually match that domain's own
   documented semantics for when it fires and what it can still affect
   (e.g., a trigger that fires only after the guarded action has already
   completed cannot undo it; a trigger that fires on every occurrence of
   a broader event, not only the "real" one it is meant to gate)?
   *Domains:* generalizes with adaptation. Agent-harness hook: does a
   post-action event get used to attempt something only a pre-action
   event could actually block? CI job step: does the trigger's own
   checkout/secret-access semantics (e.g. a fork-triggered vs.
   target-repository-triggered event) match what the gate assumes about
   its own credentials and code under test?
8. **Implementation-mechanism fit: deterministic script vs. model-judged
   step.** Where a domain offers both a deterministic (script/rule-based)
   and a model-mediated (LLM-judged) way to implement a check, does the
   choice match whether the check is actually expressible
   deterministically, or does a model-mediated choice reintroduce the
   exact non-determinism a gate exists to avoid for a check that should
   have stayed deterministic (or been narrowed until it could)?
   *Domains:* generalizes with adaptation; genuinely inapplicable in a
   domain that offers no model-mediated variant at all (a plain git hook
   subprocess, for instance) -- graded as not-applicable there, not
   silently skipped.
9. **Known-limitation disclosure.** Rather than presenting untested or
   partial coverage as complete, does the gate's own documentation state
   its own bypass class or known gap explicitly, ideally tracked against
   a specific follow-up?
   *Domains:* generalizes directly.
10. **Empirical verification over assumed behavior.** Is a claim that the
    gate actually denies/allows what it says it does backed by quoted,
    live evidence gathered in the gate's real execution context, rather
    than a plausible-sounding but unverified assertion? This dimension's
    failure or gap blocks a well-formed verdict on that claim -- see
    `SKILL.md`'s Procedure step 6 and Stop boundaries. Where the gated
    actor is itself an LLM agent, its own natural-language claim of task
    success, or the guarded tool's own lack of an error, is not such
    evidence either -- a call can execute cleanly and be narrated as
    successful while the state transition it produced still violates the
    policy the gate exists to enforce; check the resulting state
    directly. "Reason Less, Verify More" (arXiv:2607.07405) names this
    class of failure explicitly and measured it as the majority (78%) of
    observed failures on an ungated baseline, reproducible across
    disjoint seeds.
    *Domains:* generalizes directly.
11. **Deployment-mode / enforcement-mode portability, disclosed.** Does
    the gate's own documentation state which deployment or enforcement
    mode it was actually verified in, and name the gap explicitly where
    another mode is unverified?
    *Domains:* generalizes with adaptation. Agent-harness hook:
    project-local vs. plugin-distributed. CI job step: verified as an
    actual required check on a protected branch, vs. only observed
    running (but not required, hence not truly blocking) elsewhere. MCP
    server subprocess: verified with the server run locally vs.
    remotely/hosted, which can change trust assumptions.
12. **Duplication/drift risk, named rather than hidden.** Does the same
    policy logic exist in more than one place (more than one script, more
    than one domain) without a synchronization check, risking silent
    drift between copies?
    *Domains:* generalizes directly.
13. **Side-effect independence from the deny decision.** For a gate that
    also logs, notifies, or writes as well as classifies: does a
    side-effecting action correctly avoid silently depending on a
    different gate's own deny decision to suppress it, in a domain where
    multiple gates or checks can run concurrently?
    *Domains:* generalizes with adaptation. CI job step: parallel/matrix
    jobs raise the same concern as concurrent agent-harness hooks. Git
    hook subprocess: hooks run in a fixed, sequential, well-documented
    order, which structurally reduces (but does not eliminate) this
    concern relative to the concurrent domains.
14. **Structured-output hygiene.** Where the gate communicates its
    decision over a structured, machine-parsed channel (not just a
    human-readable log), does the gate route every diagnostic/log line
    away from that channel, leaving it for the intended structured
    payload only? A single stray line on the wrong channel can silently
    corrupt parsing for whatever consumes the gate's decision.
    *Domains:* generalizes with adaptation. Directly applicable wherever
    a structured machine-readable channel exists (agent-harness hook
    stdout-as-JSON, a CI step's machine-parsed output/annotation, an MCP
    tool's structured response). A plain git hook subprocess that only
    needs its exit code is not exposed to this failure mode natively --
    the concern reappears only if something downstream also parses that
    hook's own stdout.
15. **Fail-closed default on incomplete or malformed input.** Does the
    gate default to deny (or escalate) when its own input is malformed,
    a field it depends on is missing, or a script/binary it shells out to
    is absent -- rather than silently defaulting to allow?
    *Domains:* generalizes directly -- this is the same principle as
    "an inability to verify is a deny, not an assume-clean," applied to
    a specific gate's own input handling. A bundled test's own scope does
    not by itself satisfy this dimension: if it exercises only
    well-formed, happy-path fixtures, independently construct and run a
    malformed, boundary, or missing-dependency input directly against the
    gate before crediting this dimension or dimension 10.
16. **Runtime tamper-detection awareness, distinct from review-time
    screening.** Review-time screening (a human/agent check on an
    incoming change) is a different, earlier layer from a check that
    notices the gate's own definition changing through some other path
    after it was already reviewed and merged -- a later commit, a local
    edit, a dependency update. Does anything in the gate's own domain
    provide (or explicitly lack) this second, later-time layer? Note this
    is tamper-*detection*, a real but distinct property from
    tamper-*prevention* -- detecting and warning about a change is not
    the same as blocking it from taking effect.
    *Domains:* generalizes directly -- the same question (does anything
    notice a post-review change to the gate's own definition) applies
    identically to a local git hook script, a CI workflow file or a
    reusable-workflow reference, and an MCP server's own config or
    underlying binary.
17. **Discoverability: the gate's existence and purpose is not silent
    magic.** Is the gate's presence, and the specific finding/decision/
    design rationale it backs, stated somewhere a reader would actually
    find it -- rather than a behavior that surprises whoever encounters
    it for the first time, with no visible trace of why it exists?
    *Domains:* generalizes directly.
18. **Secret/credential redaction in the gate's own output.** Distinct
    from dimension 14 (which asks whether a structured channel is kept
    parse-clean, not what it contains): where a gate's own check logic
    handles a secret, token, or credential value (validating one, or
    reading one to reach the resource it checks), does its own
    diagnostic output, deny message, or log line redact that value
    rather than echoing it -- into a place a lower-trust reader of the
    gate's own output (a CI log, a PR comment, a chat transcript) might
    see it?
    *Domains:* generalizes directly -- a CI job step's own log output,
    an agent-harness hook's own stderr message, and an MCP server's own
    error response are all readable by someone or something with less
    trust than the credential itself carries.
19. **Runtime-cost optimization, distinct from dimension 6's
    budget-proportionality check.** Dimension 6 asks only whether a
    timeout/budget is set explicitly and matches the check's stated cost;
    this dimension asks whether that cost itself has been minimized within
    what the policy genuinely requires -- does the gate's own implementation
    avoid avoidable overhead (a full clone or full-repository scan where a
    shallow fetch or diff-scoped scan would do, a synchronous network
    round-trip where a cached or local answer would do, re-paying a whole
    interpreter/toolchain cold-start on every invocation where a warm or
    incremental path exists, an unbounded quadratic pattern over input that
    could be linear)? A finding here must never come at the cost of
    dimensions 1, 3, or 15 -- narrowing scope, skipping self-revalidation, or
    defaulting to allow on a fast path are not optimizations, they are
    correctness regressions wearing an optimization's name; grade only a
    change that holds the gate's own deny / self-revalidation / fail-closed
    behavior fixed while reducing its cost. A gate's own comment, docstring,
    or commit message claiming its cost is "already optimized" is not
    itself evidence -- apply dimension 10's empirical-verification
    discipline to a claimed cost too: ground the finding in a direct
    reading of the actual code path or a live measurement, never the claim
    alone.
    *Domains:* generalizes with adaptation. Agent-harness hook: does the
    hook re-run expensive recomputation on every matching tool call, or
    scope/cache to only the changed surface since its last run? CI job
    step: does the job use the platform's own dependency/build caching and
    path filters, or needlessly rebuild full state and run unconditionally
    regardless of whether anything in its own scope changed? Git hook
    subprocess: on pre-commit/pre-push, does it operate on the staged/changed
    diff rather than re-scanning the whole working tree each invocation?
    MCP server subprocess: does the server hold a warm process or cached
    connection this call reuses, or pay a full cold-start cost on every
    request?
20. **Correspondence/sync gates check both set differences, not one.**
    Where a gate's own stated purpose is a "1:1 correspondence" or "sync"
    check between two enumerable sets (two directory listings, a table's
    rows vs. the files it indexes, a doc's disclosed-gap list vs. a
    tool's live computed output), does it assert both directions -- the
    set the driving spec happened to enumerate first, *and* its reverse
    -- rather than only one? A gate that checks only one direction can
    still name itself "correspondence" or "sync" while missing a rename,
    removal, or drift-toward-stale-disclosure that only the reverse
    direction would catch; a bundled test (dimension 4) covering only the
    forward direction does not itself satisfy this dimension.
    *Domains:* generalizes directly -- the same one-directional gap can
    occur in a git hook script, a CI job step, an agent-harness hook, or
    an MCP server subprocess; the question is about the assertion's own
    set-difference completeness, not which domain runs it.
21. **Gate precision, audited against real firings, not only synthetic
    correctness.** For a gate already deployed or exercised against real
    traffic (not merely a freshly authored one), are its actual firing
    instances audited against a ground-truth or best-available
    correctness signal (a ground-truth trajectory, a human-reviewed
    sample, a replay corpus) to compute a true-block vs. false-block
    rate, rather than crediting the gate as effective merely because it
    fires and denies? A gate can be dimension-1-through-6 clean --
    correctly wired, fail-closed, self-revalidating -- while its own
    policy predicate is wrong most of the time it actually fires,
    silently over-blocking legitimate actions. "Reason Less, Verify
    More" (arXiv:2607.07405) audited this directly and found a wide
    spread across its own four-gate suite: 100% precision for one gate
    versus 5% precision for another, concluding explicitly that gate
    precision must itself be audited, not assumed from correct wiring
    alone. Where no real-firing audit trail or correctness signal exists
    yet, mark this dimension indeterminate rather than silently
    crediting the gate, per dimension 10's own Stop-boundary discipline.
    A target's own documentation asserting an audit was performed and
    reporting a favorable precision figure is not itself evidence either
    -- the same "claim is not evidence" discipline dimension 19 already
    applies to a claimed optimization ("a gate's own comment, docstring,
    or commit message... is not itself evidence... never the claim
    alone"); ground this dimension's finding in direct inspection of the
    actual firing log or ground-truth sample, never a reported number
    alone.
    *Domains:* generalizes directly -- the audit itself (comparing real
    firings against a correctness signal) does not depend on which of
    the four domains realizes the gate, only on whether a real-firing
    trail and a correctness signal both exist for it.
22. **Aggregate-outcome attribution via firing/non-firing stratification
    -- precondition-scoped.** Applies only where the target supports
    repeated/multi-trial measurement (a benchmark harness, an A/B
    rollout, a replay corpus run at volume); where that precondition is
    absent, this dimension is not-applicable, not silently skipped, the
    same explicit treatment a domain-inapplicable dimension already gets.
    If it is uncertain whether the precondition holds -- a target's own
    documentation merely asserts no repeated-trial capability, or the
    reviewer cannot directly confirm one way or the other -- do not
    default to not-applicable: verify the target's actual capability
    directly, or mark this dimension indeterminate rather than assume
    the precondition away. Where the precondition holds: is a claimed
    aggregate outcome
    improvement (a pass-rate lift, an incident-rate drop) stratified by
    whether the gate actually fired on each trial, with the non-firing
    stratum's own movement checked for consistency with noise (e.g. a
    confidence interval including zero), before the improvement is
    attributed to the gate? An aggregate lift that includes similar
    movement in a non-firing stratum is evidence the improvement is not
    actually caused by the gate. "Reason Less, Verify More"
    (arXiv:2607.07405) names this decomposition explicitly and applied it
    live: its own firing stratum moved with a confidence interval
    excluding zero, while its own non-firing stratum moved with a
    confidence interval including zero -- the paper's aggregate lift is
    attributable to the gate only because this stratification was run
    and reported, not assumed from the aggregate number alone.
    *Precondition:* generalizes directly wherever repeated-trial
    measurement exists, regardless of domain; not-applicable, stated
    explicitly, for a single-shot production gate with no comparable
    trial volume. This is gitapex's own typical case -- a CI gate, a
    pre-commit hook, or an MCP server check usually runs once per real
    event, not across a multi-trial replication set -- so expect this
    dimension to read not-applicable for most real reviews this skill
    performs; that is an honest scope limit, not a defect in the
    dimension.
