# Primary-source grounding for the five criteria

Portable grounding for `SKILL.md`'s five criteria (state provenance/trust,
cold-start/absence, replay/reproducibility, bounded growth, blocking-posture
justification) in real, independently-verified primary sources, in the same
spirit as `evaluating-skill-quality/references/rubric.md`'s own citation
convention. Every source below was actually fetched (directly, or via the
session's proxy when a tool's default fetch path was blocked) and read --
never cited from memory or a secondary summary, per this repository's own
grounding discipline. All reference URLs are collected under
[References](#references) at the end of this file.

## Table of contents

- [1. State provenance/trust](#1-state-provenancetrust)
- [2. Cold-start/absence behavior](#2-cold-startabsence-behavior)
- [3. Replay/reproducibility](#3-replayreproducibility)
- [4. Bounded growth](#4-bounded-growth)
- [5. Blocking-posture justification](#5-blocking-posture-justification)
- [Sources considered and not used](#sources-considered-and-not-used)
- [References](#references)

## 1. State provenance/trust

The criterion: can an actor a decision constrains also write the state that
decides whether they are constrained?

Primary grounding is Saltzer and Schroeder's **"Separation of privilege"**
design principle [saltzer] -- the same 1975 paper grounds criterion 2 below
under a different named principle, so it is cited twice in this file, not
duplicated as two sources:

> "Separation of privilege: Where feasible, a protection mechanism that
> requires two keys to unlock it is more robust and flexible than one that
> allows access to the presenter of only a single key. ... The reason is
> that, once the mechanism is locked, the two keys can be physically
> separated and distinct programs, organizations, or individuals made
> responsible for them. From then on, no single accident, deception, or
> breach of trust is sufficient to compromise the protected information."

Applied here: a release gate's own "deny" key and the metrics-store's
"write" key must be held independently. A deployer holding both -- able to
edit the very evidence the gate reads -- collapses the two-key design back
into a single key, the exact failure this criterion grades.

Secondary, standards-body corroboration from NIST SP 800-53 Rev. 5, control
**AC-5 (Separation of Duties)** [nist80053]:

> "Separation of duties addresses the potential for abuse of authorized
> privileges and helps to reduce the risk of malevolent activity without
> collusion. Separation of duties includes ... ensuring that security
> personnel who administer access control functions do not also administer
> audit functions."

Related, narrower context: Norm Hardy's **"The Confused Deputy"** [hardy]
names a genuinely distinct failure (a service commingling its own authority
with a caller's, not a constrained party writing its own constraining
state) but is worth citing as the origin of "authority independence"
thinking in this same neighborhood:

> "The fundamental problem is that the compiler runs with authority
> stemming from two sources. (That's why the compiler is a confused
> deputy.) ... The compiler serves two masters and carries some authority
> from each to perform its respective duties. It has no way to keep them
> apart."

## 2. Cold-start/absence behavior

The criterion: with the state store empty, missing, freshly created, or
unreachable, does the decision deny or escalate, or does it silently allow?

Primary grounding is the same Saltzer and Schroeder paper's **"Fail-safe
defaults"** design principle [saltzer]:

> "Fail-safe defaults: Base access decisions on permission rather than
> exclusion. ... the default situation is lack of access, and the
> protection scheme identifies conditions under which access is permitted.
> ... In a large system some objects will be inadequately considered, so a
> default of lack of permission is safer. ... a mechanism that explicitly
> excludes access tends to fail by allowing access, a failure which may go
> unnoticed in normal use."

This is a near-exact match: an inadequately-considered case (the criterion's
own "brand-new-deployment, fresh-session, or first-invocation-against-a-
not-yet-populated-store" fixture) should default to lack of access, and the
paper names the silent-allow failure mode directly.

Secondary, modern standards-body corroboration from NIST SP 800-53 Rev. 5,
controls **SI-17 (Fail-safe Procedures)** and **SC-24 (Fail in Known
State)** [nist80053] -- weaker for this specific criterion since neither
control itself asserts default-deny (SI-17's own example remediation is
alerting operator personnel, not access denial), but real, verified, and
on-topic for the general fail-safe/fail-to-known-state pattern:

> "Implement the indicated fail-safe procedures when the indicated failures
> occur ... Failure conditions include the loss of communications among
> critical system components or between system components and operational
> facilities." (SI-17)

> "Fail to a [organization-defined known system state] for the following
> failures ... Failure in a known state prevents the loss of
> confidentiality, integrity, or availability of information in the event
> of failures of organizational systems or system components." (SC-24)

## 3. Replay/reproducibility

The criterion: is the state snapshot behind a past decision recorded, so
that decision can be re-verified later against the same input?

Primary grounding is Martin Fowler's **"Event Sourcing"** writeup
[fowler-es], whose "External Queries" section is close to a verbatim match
for this criterion's own examples ("a fetched window logged as a build
artifact, a cache key with a retained value"):

> "The primary problem with external queries is that the data that they
> return has an effect on the results on handling an event. If I ask for an
> exchange rate on December 5th and replay that event on December 20th, I
> will need the exchange rate on Dec 5 not the later one."

> "One approach is to design the gateway to the external system so that it
> remembers the responses to its queries and uses them during replay. To be
> complete this means that the response to every external query needs to be
> remembered."

> "Event Sourcing ensures that all changes to application state are stored
> as a sequence of events. ... we can also use the event log to reconstruct
> past states ... it's easy to serialize the events to make an Audit Log."

Secondary reinforcement from the Reproducible Builds project's own
**Definition** [reproducible-builds] -- a different domain (re-deriving a
build artifact from recorded inputs, not a runtime decision reading mutable
external state) but the same underlying principle, that a recorded input
must make independent re-verification possible:

> "A build is reproducible if given the same source code, build environment
> and build instructions, any party can recreate bit-by-bit identical
> copies of all specified artifacts."

Tertiary support, general audit-trail framing only, from NIST SP 800-92
[nist80092]:

> "Logs that are secured improperly in storage or in transit might also be
> susceptible to intentional and unintentional alteration and destruction.
> This could cause a variety of impacts, including allowing malicious
> activities to go unnoticed and manipulating evidence to conceal the
> identity of a malicious party."

## 4. Bounded growth

The criterion: is the state's own size or age bounded, or does the
decision's cost or behavior drift as history accumulates without limit?

Two verified sources ground the two halves of this criterion (a *size*
bound and an *age* bound), not one alone.

**Size bound** -- RFC 2697, "A Single Rate Three Color Marker" [rfc2697], a
formally specified token-bucket algorithm whose token count is mechanically
prevented from growing past a fixed cap regardless of how much history
accumulates:

> "The maximum size of the token bucket C is CBS and the maximum size of the
> token bucket E is EBS. ... If Tc is less than CBS, Tc is incremented by
> one, else if Te is less then EBS, Te is incremented by one, else neither
> Tc nor Te is incremented."

RFC 2698, "A Two Rate Three Color Marker" [rfc2698], corroborates the same
bounding shape for a second rate/burst pair, confirming this is the
algorithm's standard shape rather than a one-off.

**Age bound** -- the Google SRE book's **"Handling Overload"** chapter
[sre-overload] describes adaptive throttling driven by state explicitly
scoped to a fixed age, not a service's entire lifetime history:

> "We implemented client-side throttling through a technique we call
> adaptive throttling. Specifically, each client task keeps the following
> information for the last two minutes of its history: `requests` -- The
> number of requests attempted by the application layer ... `accepts` --
> The number of requests accepted by the backend."

> "Figure 21-1 shows the number of attempts in each request received by a
> given backend task in various example situations, over a sliding window
> (corresponding to 1,000 initial requests, not counting retries)."

## 5. Blocking-posture justification

The criterion: where the state-coupled signal is aggregate and noisy (a
trend, a rate, a rolling average), is a blocking -- not advisory -- posture
argued somewhere, rather than a single event being blocked on a signal no
single event fully controls, left unexplained?

Primary grounding is the Google SRE book's **"Embracing Risk"** chapter
[sre-risk], which argues explicitly against binary blocking on an aggregate
error-budget signal in favor of graduated response:

> "Many products use this control loop to manage release velocity: as long
> as the system's SLOs are met, releases can continue. If SLO violations
> occur frequently enough to expend the error budget, releases are
> temporarily halted ... More subtle and effective approaches are available
> than this simple on/off technique: for instance, slowing down releases or
> rolling them back when the SLO-violation error budget is close to being
> used up."

Secondary support from the SRE Workbook's **"Alerting on SLOs"** chapter
[sre-alerting], on why a single noisy event should not drive the same
response as a systematic one:

> "Single requests can fail for a large number of ephemeral and
> uninteresting reasons that aren't necessarily cost-effective to solve in
> the same way as large systematic outages."

> "It's also a good idea to set up ticket notifications for incidents that
> typically go unnoticed but can exhaust your error budget if left
> unchecked ... since the rate of budget consumption provides adequate time
> to address the event, you don't need to page someone."

Foundational grounding for *why* a noisy signal cannot be treated as a
single-point trigger at all, from Shewhart's original statistical-
process-control text [shewhart]:

> "It is too much to expect that the criteria will be infallible. We are
> amply rewarded if they appear to work in the majority of cases."

> "Of course, as previously noted, a few points should fall outside control
> limits in the long run even though there is no lack of control."

None of the three sources for this criterion use continuous-control-loop
vocabulary borrowed from industrial process control -- deliberately:
importing that framing into this skill's own text was already considered
and rejected as a category error for this repository's four
gate-realization domains (see `metadata/gitapex.yaml`'s own recorded
decision, anchored to <https://github.com/tvna/gitapex/issues/547>). This
file's own citations stay in the statistical-process-control/SRE-practice
lane for the same reason.

## Sources considered and not used

Recorded here, not silently dropped, so a future editor does not re-spend
research effort re-discovering the same dead end:

- **ITU-T Recommendation I.371** (leaky bucket / Usage Parameter Control for
  ATM networks) -- a real, widely-cited standard for criterion 4's size
  bound, but its full text could not be located or fetched (ITU
  recommendations are not freely hosted); only secondhand paraphrases were
  found. Not cited above; do not cite it without independently obtaining
  the actual ITU-T text first.
- **Clark and Wilson, "A Comparison of Commercial and Military Computer
  Security Policies," IEEE S&P, 1987** -- a plausible secondary candidate
  for criterion 1's separation-of-duty grounding, but the original IEEE
  proceedings text is paywalled and no open mirror was found. Not cited
  above for the same reason: an unverified quote is not evidence.

## References

Every inline `[label]` citation above resolves to the source below.

- **[saltzer]** J. H. Saltzer and M. D. Schroeder -- The Protection of
  Information in Computer Systems, Proceedings of the IEEE 63(9):1278-1308,
  September 1975.
  <https://web.mit.edu/Saltzer/www/publications/protection/Basic.html>
- **[nist80053]** National Institute of Standards and Technology --
  Security and Privacy Controls for Information Systems and Organizations,
  NIST Special Publication 800-53 Revision 5, September 2020.
  <https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf>
- **[hardy]** Norm Hardy -- The Confused Deputy: (or why capabilities might
  have been invented), ACM SIGOPS Operating Systems Review 22(4):36-38,
  October 1988.
  <https://css.csail.mit.edu/6.858/2015/readings/confused-deputy.html>
- **[fowler-es]** Martin Fowler -- Event Sourcing, Further Enterprise
  Application Architecture, 2005 (living page).
  <https://martinfowler.com/eaaDev/EventSourcing.html>
- **[reproducible-builds]** Reproducible Builds project -- Definition
  (ongoing living specification).
  <https://reproducible-builds.org/docs/definition/>
- **[nist80092]** Karen Kent and Murugiah Souppaya, NIST -- Guide to
  Computer Security Log Management, NIST Special Publication 800-92,
  September 2006.
  <https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-92.pdf>
- **[rfc2697]** J. Heinanen and R. Guerin -- A Single Rate Three Color
  Marker, RFC 2697, IETF, September 1999.
  <https://www.rfc-editor.org/rfc/rfc2697.txt>
- **[rfc2698]** J. Heinanen and R. Guerin -- A Two Rate Three Color Marker,
  RFC 2698, IETF, September 1999.
  <https://www.rfc-editor.org/rfc/rfc2698.txt>
- **[sre-overload]** Alejandro Forero Cuervo, ed. Sarah Chavis -- Handling
  Overload, ch. 21 in Site Reliability Engineering: How Google Runs
  Production Systems, O'Reilly/Google, 2017.
  <https://sre.google/sre-book/handling-overload/>
- **[sre-risk]** Marc Alvidrez, ed. Kavita Guliani -- Embracing Risk, ch. 3
  in Site Reliability Engineering: How Google Runs Production Systems,
  O'Reilly/Google, 2017.
  <https://sre.google/sre-book/embracing-risk/>
- **[sre-alerting]** Steven Thurgood et al. -- Alerting on SLOs, ch. 5 in
  The Site Reliability Workbook, O'Reilly/Google, 2018.
  <https://sre.google/workbook/alerting-on-slos/>
- **[shewhart]** W. A. Shewhart -- Economic Control of Quality of
  Manufactured Product, D. Van Nostrand Company, 1931.
  <https://archive.org/details/in.ernet.dli.2015.150272>

<!-- Link reference definitions below power the inline [label] shortcuts; keep in sync with the visible list above. -->

[saltzer]: https://web.mit.edu/Saltzer/www/publications/protection/Basic.html "Saltzer and Schroeder, The Protection of Information in Computer Systems"
[nist80053]: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf "NIST SP 800-53 Rev. 5"
[hardy]: https://css.csail.mit.edu/6.858/2015/readings/confused-deputy.html "Hardy, The Confused Deputy"
[fowler-es]: https://martinfowler.com/eaaDev/EventSourcing.html "Fowler, Event Sourcing"
[reproducible-builds]: https://reproducible-builds.org/docs/definition/ "Reproducible Builds, Definition"
[nist80092]: https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-92.pdf "NIST SP 800-92"
[rfc2697]: https://www.rfc-editor.org/rfc/rfc2697.txt "RFC 2697"
[rfc2698]: https://www.rfc-editor.org/rfc/rfc2698.txt "RFC 2698"
[sre-overload]: https://sre.google/sre-book/handling-overload/ "Google SRE Book, Handling Overload"
[sre-risk]: https://sre.google/sre-book/embracing-risk/ "Google SRE Book, Embracing Risk"
[sre-alerting]: https://sre.google/workbook/alerting-on-slos/ "Google SRE Workbook, Alerting on SLOs"
[shewhart]: https://archive.org/details/in.ernet.dli.2015.150272 "Shewhart, Economic Control of Quality of Manufactured Product"
