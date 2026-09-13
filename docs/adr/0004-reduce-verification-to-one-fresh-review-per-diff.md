# Reduce verification to one fresh-context adversarial review per diff, keeping deterministic gates

## Status

Accepted (approved by tvna, 2026-09-13)

## Context and Problem Statement

This decision is prospective: none of it is implemented yet. It is
recorded ahead of implementation, which is tracked as child issue
https://github.com/tvna/gitapex/issues/1970 (PR0) under tracking issue
https://github.com/tvna/gitapex/issues/1964, and described in
`docs/gitapex/specs/2026-09-12-skill-contract-form-design.md` (section
"Verification reduction").

The repository owner asked, on 2026-09-11, for a structural redesign of
the skill pipeline that prefers prototyping over exhaustive adversarial
verification, without leaving the Domain-Driven Design framing. The
pipeline today runs several verification layers on every change, and
their yields and costs were measured on 2026-09-12 from primary sources
(the bodies of the eight most recently closed pull requests #1803,
#1825, #1916, #1917, #1936, #1942, #1945, #1954; retrospectives #1955
and #1951; issue #1807):

- `executing-a-branch-plan` Step 8 adversarial review (one fresh
  `review-persona` dispatch over the accumulated diff) found confirmed
  defects in every PR where it ran: #1954 eight findings, five fixed;
  #1942 three confirmed; #1916 six confirmed; #1825 seventeen confirmed.
- `drafting-a-pr-to-merge` Step 8 outer layer (GitHub Copilot, or the
  Claude Code Review App when installed) produced zero responses in the
  sample; #1916 skipped it on the owner's instruction; #1905 had already
  cut the wait from 30 to 15 minutes; on #1969 the delegated agent spent
  most of 27 minutes and roughly 350k tokens polling for a response that
  never came.
- `drafting-a-pr-to-merge` Step 8 inner layer (`reviewing-an-artifact`
  fan-out over the same diff the previous layer already reviewed)
  reported zero confirmed findings on #1954 and #1969, and real
  cross-file drift on #1825 across two fan-outs.
- `evaluating-skill-quality` found real dimension-6 defects (#1951
  repairs 2 and 3) but ran up to three independent passes per PR
  (#1942) under a two-hour dispatch timeout (#1825).
- `merge-retrospective` filed six gate-proposal issues from twelve
  repairs on #1955, five of which were closed as duplicates within
  minutes; #1807 (open, owner decision pending) documents that Step 8's
  own working-as-designed catches are the largest driver of
  gate-proposal volume (120 open, 141 closed at the time of writing).
- The Stop hook `check-stop-review-obligation` blocks a turn after any
  `git push`, including a push to a branch with no PR (reproduced live on
  2026-09-12; tracked as #1631, with #1940 closed as its duplicate).
- Local preflight (49 gates) and CI (73 gates) caught real gaps before
  push (#1955 repairs 2 and 3).

Three instruction sources bear on the same question. Anthropic's
"Prompting Claude Opus 5" guide
(https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
states that explicit verification instructions and "use a subagent to
verify" instructions cause over-verification and should be removed, and
that the model should not be told to use subagents to double-check its
own work. Anthropic's "Steering Claude Code"
(https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more)
states that a real guardrail must be deterministic, enforced by hooks and
permissions. AGENTS.md section 4 states that layers safety relies on
must not be collapsed to shorten text or implementation.

Published research from 2025 and 2026 bears on the same question. Each
paper below was read at its arXiv abstract page on 2026-09-13; what is
reported is what each abstract states, with the paper's own scope
carried along, not an endorsement beyond that scope.

- Cuadron et al., "The Danger of Overthinking: Examining the
  Reasoning-Action Dilemma in Agentic Tasks", arXiv:2502.08235
  (2025-02-12). On SWE-bench Verified trajectories, higher overthinking
  scores correlate with decreased performance, and selecting the
  solution with the lower overthinking score improves performance by
  almost 30 percent while reducing computational cost by 43 percent.
  Bears on: internal self-verification loops in agentic coding tasks.
- Cemri et al., "Why Do Multi-Agent LLM Systems Fail?", arXiv:2503.13657
  (2025-03-17, v3 2025-10-26). A taxonomy over 1600+ annotated traces
  across 7 frameworks with three failure categories, one of which is
  task verification. Bears on: verification is a real failure class,
  so the decision keeps one review layer rather than removing all.
- Chen et al., "The Self-Correction Illusion: Role Relabeling Gates
  Explicit Error Flagging in Large Language Models", arXiv:2606.05976
  (2026-06-04). LLM agents struggle to correct errors in their own
  reasoning traces despite correcting errors from external sources;
  relabeling an error from an internal thought to an external role
  raises the explicit-correction rate by 23 to 93 percentage points in
  10 of 12 settings. Bears on: a fresh-context reviewer (a separate
  dispatch reading the diff as external input) over self-review.
- Zhao, Awasthi, Gollapudi, "Sample, Scrutinize and Scale: Effective
  Inference-Time Search by Scaling Verification", arXiv:2502.01839
  (2025-02-03, v2 2025-02-20). Self-verification accuracy improves as
  the sampled pool grows, while frontier models show weak out-of-box
  verification. Bears on, as a qualifier: self-verification is not
  worthless in every regime; this decision cuts it where the measured
  yield here is zero, not on principle.
- Chowdhury et al., "From Industry Claims to Empirical Reality: An
  Empirical Study of Code Review Agents in Pull Requests",
  arXiv:2604.03196 (2026-04-03). Pull requests reviewed only by code
  review agents merge at 45.20 percent against 68.37 percent for
  human-only review; 12 of 13 agents show average signal ratios below
  60 percent. Bears on: the outer bot-review layer.
- Zhao, Esmaeili, Fard, "Bias in the Loop: Auditing LLM-as-a-Judge for
  Software Engineering", arXiv:2604.16790 (2026-04-18). Judge decisions
  are highly sensitive to prompt biases with the code unchanged, enough
  to change task-level conclusions. Bears on: treating a bot review's
  verdict as a weak signal, which the skill already discloses.
- Bertalanic and Fortuna, "The Cost of Consensus: Isolated
  Self-Correction Prevails Over Unguided Homogeneous Multi-Agent
  Debate", arXiv:2605.00914 (2026-04-29). For 7B-8B models, debate
  consumes 2.1 to 3.4 times more tokens for equal or lower accuracy
  than isolated self-correction. Scope: small open models. Bears on:
  redundant multi-reviewer rounds over the same diff.
- Tran and Kiela, "Single-Agent LLMs Outperform Multi-Agent Systems on
  Multi-Hop Reasoning Under Equal Thinking Token Budgets",
  arXiv:2604.02460 (2026-04-02). Under a fixed reasoning-token budget,
  single-agent systems match or outperform multi-agent systems, and
  many reported multi-agent advantages are better explained by
  unaccounted computation. Bears on: counting cost per diff, not per
  layer.
- Jwalapuram et al., "The Illusion of Multi-Agent Advantage",
  arXiv:2606.13003 (2026-06-11, v2 2026-06-13). Automatically generated
  multi-agent architectures underperform chain-of-thought
  self-consistency at up to 10 times the cost, while expert-architected
  systems with explicit decomposition and context separation
  outperform. Bears on: keeping the one deliberately placed fresh
  review and cutting the accumulated ones.
- Mehta, "The reach of a verification tool decides its value: A
  controlled study of verification surface, artifact quality, and cost
  in AI coding agents", arXiv:2608.28795 (2026-08-28). Across 1,116 web
  applications, six models and eight tool configurations, a verification
  tool improves the artifact only where its reach covers how the
  application actually fails; a single boot probe removes nearly all
  launch failures at about 35 percent of a full shell's token cost,
  while the full shell multiplies the no-tools cost by 2.35. Bears on:
  choosing verification by measured reach and cost, the method this
  decision applies to the pipeline's own layers.

Two related mechanisms are already in place and are not the subject of
this decision: #1806 (merged via PR #1819) added a backlog-grounded
review and a `Dedup-sweep:` hook to `merge-retrospective`, whose
create-then-close-as-duplicate behavior is deliberate and race-safe; and
the `independent-review-pending` required status check, which parses
the `## Independent review verdict` section of a PR body.

## Decision Drivers

- Per-PR wall-clock and token cost of verification that produces no
  finding.
- Measured defect-finding yield per layer, not the layer's design
  intent.
- AGENTS.md section 4: safety layers stay; only probabilistic
  self-verification is cut.
- A machine-readable record of which review ran against which head, so
  the later contract-form migration (issues #1965 to #1967) can cite it
  from a `proof` block instead of re-running.
- Consistency with the 2025-2026 published evidence above: verification
  pays where its reach matches the failure mode and where the reviewer
  reads the artifact as external input; redundant rounds over the same
  artifact cost tokens without measured gain; bot reviews are a weak,
  bias-sensitive signal.

## Considered Options

- Keep every layer as it is (status quo).
- Apply the Opus 5 guidance literally: remove every probabilistic
  review instruction from the pipeline and rely on deterministic gates
  alone.
- Cut layer by layer on measured yield under a reading rule that keeps
  deterministic gates, keeps exactly one fresh-context adversarial
  review per diff, and removes or conditions the layers that duplicate
  it or produce nothing.

## Decision Outcome

We will cut layer by layer on measured yield, under the reading rule:
deterministic gates (hooks, CI, local preflight) keep their layers;
probabilistic self-verification instructions are cut by measurement;
exactly one fresh-context adversarial review per diff is kept. Concretely:

- We will keep `executing-a-branch-plan` Step 8's adversarial review
  unchanged, because it is the layer with the highest measured yield,
  and it becomes the one fresh-context review per diff.
- We will make `drafting-a-pr-to-merge` Step 8's outer layer
  asynchronous: request the bot review, record the request, and handle
  any response at the next PR event or check-in, never waiting for it,
  because the sample shows no response to wait for.
- We will make `drafting-a-pr-to-merge` Step 8's inner layer
  conditional: when the PR body's Execution log records an
  `executing-a-branch-plan` Step 8 adversarial review naming the current
  head SHA, the verdict cites that record instead of re-running; when
  no such record exists, or the head moved after it, exactly one pass
  runs. The `## Independent review verdict` heading and its
  `- Verdict:` and `- Verified commit:` line shapes are unchanged.
- We will cap `evaluating-skill-quality` at one isolated pass plus one
  post-fix pass per skill per PR, escalating a third to the owner.
- We will adopt direction (a) of #1807 for `merge-retrospective`: a
  repair whose own record states that a review round caught what it was
  designed to catch is tagged `review-worked-as-designed`, recorded in
  the retrospective, and not filed as a gate proposal. #1806's dedup
  mechanics stay as they are.
- We will implement #1631: a push to a branch with no open PR does not
  arm the Stop-hook review obligation, failing closed on an API error.
- We will not change `battle-testing-a-skill`, local preflight, CI
  gates, PreToolUse hooks, or the `skill-audit-disclosure` lines.
- We will measure before deciding on two further candidates:
  `invoking-gitapex`'s Red Flags table (ablation) and per-task
  `screening-a-low-trust-contribution` on self-authored diffs
  (detection rate outside governance paths). Both need an eval baseline
  that requires API credentials this session does not hold.

## Consequences

Good, because the per-PR wall-clock cost drops by the 15-minute outer
wait and the polling that fills it, and the per-PR dispatch count drops
by one `reviewing-an-artifact` fan-out whenever a same-head review
record exists.

Good, because the layer that finds defects is left untouched, and the
change is a cut of duplication and dead waiting, not of coverage.

Good, because the recorded review becomes a citable fact the contract
form's `proof` block can consume, joining the two halves of the owner's
question.

Good, because gate-proposal volume driven by working-as-designed catches
stops, reducing the duplicate-then-close churn #1955 shows.

Bad, because a late outer-layer response is handled only if a later
event or check-in fires; a session that ends first never sees it. This
is disclosed in the verdict, as the unreachable case already is.

Bad, because the inner-layer rule reads the Execution log, which is text
in the PR body; a forged or stale record could skip the review. The
record must name the head SHA and the dispatch id, and
`independent-review-pending` still requires a verdict naming the head.

Bad, because a recurring working-as-designed catch is no longer tracked
as a gate proposal, the trade-off #1807 itself names.

Unknown, pending an eval baseline run with credentials: whether any of
these cuts changes measured skill quality. The eval-status index shows
run records for three of twenty-nine skills, none of them core pipeline
skills.

## Confirmation

Partially in place. `independent-review-pending` (CI, required) already
enforces that a verdict names the current head; it is unchanged by this
decision. The per-layer rules themselves have no deterministic check yet:
compliance relies on the fixtures PR0 adds under `evals/` for the four
edited skills and on review of `drafting-a-pr-to-merge`'s Execution log
entries, until a gate exists. Retrospective counts (gate proposals filed
per retrospective, duplicates closed) are the after-the-fact measure,
recorded in the tracking issue per its Definition of done.
