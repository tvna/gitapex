# ADR significance criteria and template

## Table of contents

- [Significance checklist](#significance-checklist)
- [Template](#template)
- [Worked example](#worked-example)
- [References](#references)

## Significance checklist

Apply this before drafting anything. It is a **qualitative gate**, not a
score -- there is nothing to add up or cross a threshold on.

An ADR is warranted when the decision affects at least one of these five
categories ([nygard], corroborated independently by [awsprescriptive] via
Richards and Ford):

1. **Structure** -- e.g. adopting a pattern such as microservices, or a
   significant change to how components are organized.
2. **Non-functional characteristics** -- security, availability,
   performance, fault tolerance.
3. **Dependencies** -- coupling between components, what depends on what.
4. **Interfaces** -- APIs and published contracts.
5. **Construction techniques** -- libraries, frameworks, tools, processes.

AND passes Nygard's effect test: "it should be something that has an
effect on how the rest of the project will run" [nygard]. A decision that
fits one of the five categories in name only, with no real effect on how
the project runs, does not clear the gate.

**Documented gap, not filled in:** no primary source checked for this
skill -- [nygard], [awsprescriptive], [madr], [adrgithubio], or
[thoughtworks] -- gives a quantitative threshold (a reversal-cost number,
an alternatives-considered count, a team-count figure) for when a
decision crosses into "architecturally significant." [madr]'s own
authors explicitly decline to draw the line at all: "we believe that any
(important) decision should be captured in a structured way... to
capture *any* decision" -- they widen the net instead of narrowing it (in
2022 the project briefly renamed itself "Markdown *Any* Decision
Records" for exactly this reason, reverting to "Architectural" in 4.0
while keeping the non-restrictive posture). [adrgithubio]'s "measurable
effect on the architecture" is not itself defined anywhere as a measure.
This silence is itself the honest finding -- inventing a number here
would fabricate rigor the primary literature does not actually have.

## Template

Sections marked *(optional)* may be omitted entirely rather than filled
with a placeholder.

```markdown
# <Title>

## Status

Proposed
<!-- Accepted | Deprecated | Superseded, only once a named owner has approved -->

## Context and Problem Statement

<Value-neutral facts: the forces at play -- technological, project-local,
or otherwise -- that make a decision necessary. Not an argument for any
particular answer.>

## Decision Drivers

<!-- optional; omit the heading entirely if none were stated -->
- <a desired quality, constraint, or concern that shaped the choice>

## Considered Options

- <option actually discussed>
- <option actually discussed>

## Decision Outcome

We will <chosen option>, because <justification tied to a driver or the
context above>.

## Consequences

Good, because <a real, specific upside>.
Bad, because <a real, specific downside>.
<!-- every consequence you can state, not only the favorable ones;
     "unknown, pending X" for one you cannot yet assess -->

## Confirmation

<!-- optional; a real mechanism, or state plainly none exists -->
<How compliance can/will be verified -- a code-review checklist item, a
lint rule, an architecture test -- or "none -- relies on review.">
```

## Worked example

A real-shaped decision, for illustration only.

```markdown
# Switch session store from in-memory affinity to Redis

## Status

Accepted (approved by @platform-lead, 2026-06-02)

## Context and Problem Statement

The API's session store is currently sticky in-memory affinity: each
node holds its own session state, and the load balancer routes a given
session's requests back to the same node. This blocks horizontal
autoscaling -- a new node cannot serve a request for a session it never
saw -- and a node restart drops every session pinned to it.

## Considered Options

- Keep sticky affinity, add faster failover
- Client-side JWT sessions
- Shared Redis-backed session store

## Decision Outcome

We will move to a shared Redis-backed session store, because it removes
the node-affinity requirement entirely: any node can serve any request,
and a node restart no longer drops sessions.

## Consequences

Good, because autoscaling and rolling deploys no longer need
session-aware routing.
Good, because a node restart no longer loses in-flight sessions.
Bad, because the API now depends on Redis's own availability -- a Redis
outage is a new single point of failure the sticky-affinity design did
not have.
Bad, because every session read/write now costs a network round trip
instead of an in-process lookup.

## Confirmation

A code-review checklist item: any new session-touching code path must
read/write through the shared store's client, not process-local state.
```

## References

- **[nygard]** Michael Nygard -- Documenting Architecture Decisions
  (2011). <https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions>
- **[madr]** Markdown Architectural Decision Records (MADR) project.
  <https://github.com/adr/madr>
- **[awsprescriptive]** AWS Prescriptive Guidance -- ADR process, citing
  Mark Richards and Neal Ford, *Fundamentals of Software Architecture*
  (2020). <https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html>
- **[adrgithubio]** Architectural Decision Records -- adr.github.io.
  <https://adr.github.io/>
- **[thoughtworks]** ThoughtWorks Technology Radar -- Lightweight
  Architecture Decision Records. <https://www.thoughtworks.com/radar/techniques/lightweight-architecture-decision-records>
- **[ystatements]** Olaf Zimmermann -- Y-Statements (SATURN 2012).
  <https://medium.com/olzzio/y-statements-10eb07b5a177>
