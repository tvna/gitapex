# Mechanism-fit: which domain should own a policy?

A deterministic gate can, in principle, be realized in any of the four
domains named in `SKILL.md`'s Scope section (git hook subprocess,
agent-harness hook subprocess, CI job step, MCP server subprocess). Before
grading a specific realization's own quality, check that its domain
placement is actually the right one -- a well-implemented gate in the
wrong domain is not fixed by polishing its implementation further, the
same way a well-written skill that should have been a hook is not fixed by
improving its prose.

Six criteria, applied together rather than any single one in isolation:

1. **Reversibility window.** Place the check at the earliest domain where
   the wrong action is still cheaply reversible. A domain that only
   observes the damage after it is already irreversible is too late,
   regardless of how clean that domain's own implementation would be --
   e.g., a policy about an action a live session is about to take
   belongs where it can still be blocked before it happens, not only
   detected afterward.
2. **Capability match.** A domain that structurally cannot perform the
   I/O a check needs (a live remote lookup, access to a specific
   credential, visibility into a specific event payload) cannot own that
   check, independent of timing -- no amount of reversibility-window
   advantage compensates for a domain that is simply unable to do the
   work.
3. **Credential/trust asymmetry.** Pair an earlier, lower-credential
   domain that can safely fail open (because nothing irreversible has
   happened yet) with a later domain that holds guaranteed credentials
   and can fail closed as the actual backstop -- neither alone is
   sufficient where both properties are needed.
4. **Tool-surface availability.** Place the check at whichever domain
   actually exposes a chokepoint for the guarded action. If only one
   domain's own tool surface can even observe the action in question,
   domain placement is not really a choice -- it is already determined.
5. **Precedent reuse, adapted for local constraints.** Prefer a placement
   a comparable, already-battle-tested gate already uses elsewhere --
   in the target repository itself, or in a sibling/upstream repository
   whose own precedent is cited and attributed rather than re-derived
   from scratch -- adjusted for constraints the precedent's own origin
   did not have.
6. **Prose-rule-to-gate mapping, by action kind.** As a starting
   heuristic, not a rigid rule: rules about *live agent-session actions*
   tend to map to the agent-harness-hook domain, since they require an
   active session to evaluate; rules about *repository/file state* tend
   to map to the CI-job-step domain (or a git hook), since they do not
   require an active session; rules about *aggregate, noisy signals over
   time* tend to map to scheduled/advisory CI, deliberately non-blocking
   rather than gating a single event.

Two additional, secondary criteria:

- **Zero-I/O gates are structurally safer.** A pure local predicate --
  no network call, no filesystem read outside its own inputs -- has no
  INDETERMINATE state to fail open or closed on at all. Prefer a
  zero-I/O realization where one is genuinely sufficient, since it
  removes an entire class of fail-open/fail-closed judgment calls.
- **Staged rollout.** A new gate can start advisory (observed, logged,
  non-blocking) and be promoted to blocking once proven clean on real
  traffic, rather than the placement-and-strictness decision being
  binary from day one.

## What this framework does not cover

These six criteria do not, on their own, state a general principle for
"does this policy need a backstop in a domain-independent context because
its primary realization is specific to one agent-harness or one client,
and a different client or a direct-to-repository change could bypass it
entirely." That property can hold incidentally for a gate justified on
credential/reversibility grounds alone (criterion 3), without ever being
argued on client-independence grounds specifically. Applying this
framework does not by itself answer whether a given policy needs
independent, client-agnostic coverage -- that question is the
[Reproducibility / Domain-coverage axis](../SKILL.md#axis-reproducibility--domain-coverage)'s
job, not this test's.

Nor does it decide how strong a specific realization's control is on an
external Foundation/Enterprise/Advanced maturity ladder, or whether that
strength is honestly claimed for its category -- that classification is
the [Security-level / Zero-Trust maturity classification
axis](../SKILL.md#axis-security-level--zero-trust-maturity-classification)'s
job, not this test's own, even though criteria 1 and 3 above already
reason in the same impossible-vs-tedious terms that axis names explicitly.
