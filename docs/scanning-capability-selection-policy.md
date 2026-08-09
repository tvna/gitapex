# `Scanning-*` capability-selection policy

The single source of truth for one decision every `scanning-*` skill
otherwise re-derives on its own: when a diagnostic capability exists both
as a libre CLI this repository can pin and as a hosting-platform-native
feature, which one may a skill actually reach for, and what has to be
true before the native one is reported as available at all.

Cite this document from a `scanning-*` skill's own `SKILL.md`; do not
copy the policy paragraph, the detection procedure, or the evidence table
into that skill. See `glossary.md`'s skill-naming-verb-family section for
what the `Scanning-*` family itself is, and issue #843 for the roster of
skills that will consume this policy.

Scope of this document: policy and recorded evidence only. It ships no
executable detection logic -- see "v1 ships no detection code" below.

## The policy: libre CLI first

The libre CLI tool a `scanning-*` skill wraps is the only
universally-guaranteed path. It works regardless of which platform hosts
the repository under scan, regardless of that repository's visibility,
and regardless of whether the platform is SaaS or self-hosted. It is
therefore the mandatory path whenever platform detection is ambiguous,
fails, or was never run.

A platform-native capability may be reported as available only when BOTH
of the following hold. This is a two-part test, and it does not soften
into either half alone:

1. **Free for this specific repository.** The platform's own current
   documentation confirms the capability is free for the actual
   visibility and hosting mode of the repository being scanned -- public
   vs. private, SaaS vs. self-hosted. Checked per run against live docs,
   never read from a tier table baked into a skill's own `references/`.
2. **Commercially licensed for this codebase.** The capability's own tool
   license permits commercial use on the codebase being scanned, without
   a fee.

A capability that fails either part is reported as a documented Gap or
Partial, with the paid tier or the license restriction named. It is never
silently treated as free merely because the platform ships it built in.

An earlier draft of this policy inverted the order -- native capability
first, libre CLI as fallback -- and was rejected by the repository owner
for assuming whichever platform happened to be reachable in one
particular authoring session. The evidence table below is what replaced
that assumption: in realistic private, commercial, and self-hosted
scenarios, most native capabilities fail part 1, part 2, or both.

### License constraints on the libre side too

Part 2 binds the libre CLI as well, not only native capabilities. Two
standing consequences:

- A tool whose *engine* is libre but whose *ruleset* ships under a
  separate, field-of-use-restricted license is not a free path, and the
  restriction is named rather than assumed away -- `[#843]` rejects one
  roster candidate on exactly this ground.
- AGPL-licensed tools are allowed by this policy, but are never the
  first-choice candidate for a domain `[#843]`. When one is chosen
  anyway, the mitigation is SHA-pinning plus a license re-check on every
  version bump -- not a one-time check at adoption `[#844]`.

## Platform detection: cited, not reimplemented

When a `scanning-*` skill needs to know which platform hosts the
repository at all, it reuses the mechanism
`skills/scanning-attack-surfaces/SKILL.md` step B1 already implements,
by citation. This document deliberately does not restate that procedure's
steps, so the two cannot drift apart:

- Match `git remote get-url origin`'s host against an explicit,
  operator-extendable allowlist of known GitHub and GitLab hosts.
- Fall back to a directory-marker check (`.github/` vs. `.gitlab/`) when
  the remote is absent or its host matches neither list.
- STOP and ask the operator when both markers are present, or when
  neither the remote nor a directory marker resolves the platform.

The allowlist stays exactly as wide as that skill's own: GitHub and
GitLab hosts. Bitbucket Cloud/Server and generic self-hosted Git servers
are recorded in the evidence table below but are deliberately not added
to any allowlist here.

Detection is an optimization, never a precondition. A skill that skips
detection entirely and runs its wrapped CLI is always correct under this
policy; a skill that reports a native capability it never verified per
run is not.

## Evidence table

Snapshot of the primary-source research recorded in the Facts section of
issue #844 (research date 2026-08-08). Every cell other than the row
label carries its own source tag: `[#844]` for a finding restated from
that issue's Facts, `[#843]` for a roster or rejected-candidate decision
recorded in the tracking issue. The three right-hand columns are the
platform-native capability per domain; the libre CLI column is the
guaranteed path the policy above mandates.

Verdict vocabulary, borrowed from `scanning-attack-surfaces`' own
platform checklist references and extended by one level: **Covered**, **Partial**,
**Gap**, and **Unknown**. `Unknown` means the recorded research did not cover that
domain-platform pair at all -- it is not a quiet `Gap`, and it is never
rounded up to `Covered` because the platform plausibly ships something.
Operationally `Unknown` and `Gap` lead to the same action (run the libre
CLI), but they differ in what a later pass has to do: a `Gap` row has
been checked, an `Unknown` row has not.

| Domain | Libre CLI (guaranteed path) | GitHub native | GitLab native | Bitbucket / other self-hosted |
|---|---|---|---|---|
| CI-workflow static analysis | zizmor + actionlint `[#843]` | **Unknown.** Outside the recorded research, which covered Advanced Security's own scope (code scanning, secret scanning), not CI-workflow linting `[#844]` | **Unknown.** Outside the recorded research, which covered GitLab's SAST/Secret Detection/IaC/Dependency/License capabilities, not `.gitlab-ci.yml` linting `[#844]` | **Gap.** No native equivalent; CLI-only `[#844]` |
| Secret detection | betterleaks (already SHA256-pinned in `flake.nix`, no consuming script/hook/workflow today per `skills/auditing-agent-product-scope/references/middleware-inventory.md:42`); TruffleHog is an AGPL alternative, never first choice `[#843]` | **Partial.** Secret scanning is free for public repos only; private repos need a paid per-committer Advanced Security license, and GitHub Enterprise Server is paid for all repos regardless of visibility `[#844]` | **Partial.** Secret Detection runs on all tiers, but Free produces only a JSON artifact -- no MR widget, Security tab, or vulnerability tracking, all Ultimate-gated -- over a Gitleaks-class libre engine this roster already wraps directly `[#844]` | **Gap.** Bitbucket's "Security" tab is a third-party Snyk integration, not a first-party platform capability `[#844]` |
| Dependency SCA | OSV-Scanner `[#843]` | **Unknown.** The recorded research fixed Advanced Security's tier split for code scanning and secret scanning; it did not separately establish the tier and license position of GitHub's dependency-analysis surface `[#844]` | **Gap.** Dependency Scanning is Ultimate-tier only `[#844]` | **Gap.** No native equivalent; CLI-only `[#844]` |
| SAST | Bandit primary, Opengrep multi-language fallback `[#843]` | **Gap.** Code scanning is CodeQL-based, and the CodeQL CLI's own license restricts use to OSI-licensed codebases, academic research, or demos regardless of hosting or visibility -- it fails part 2 of the test even where part 1 passes `[#844]` | **Partial.** SAST runs on all tiers, but Free produces only a JSON artifact with the same Ultimate-gated reporting surface, over Semgrep-class engines `[#844]` | **Gap.** No native equivalent; CLI-only `[#844]` |
| License compliance | ScanCode Toolkit -- reserved, deferred, no skill filed `[#843]` | **Unknown.** Outside the recorded research; Advanced Security's recorded scope does not include license compliance, but no tier or license position was established for any separate GitHub surface `[#844]` | **Gap.** License Compliance (License scanning of CycloneDX files) is Ultimate-tier only `[#844]` | **Gap.** No native equivalent; CLI-only `[#844]` |
| IaC misconfiguration | Checkov -- reserved name only, no IaC artifacts exist in this repository today `[#843]` | **Unknown.** Outside the recorded research, which established GitLab's IaC position but not GitHub's `[#844]` | **Partial.** IaC Scanning runs on all tiers, but Free produces only a JSON artifact with the same Ultimate-gated reporting surface, over a KICS-class engine `[#844]` | **Gap.** No native equivalent; CLI-only `[#844]` |

Two rejected tool candidates sit behind the SAST row and are recorded
here so a later skill does not re-propose them: Semgrep, whose ruleset
ships under a separate field-of-use-restricted "Semgrep Rules License"
rather than the engine's own LGPL-2.1, and CodeQL, per the license
restriction in the table `[#843]`.

Net finding: native-capability-first was evidence-rejected. Every
**Partial** above is a capability that is real but either paid for the
realistic case (private, commercial, self-hosted) or reduced to a raw
artifact whose useful reporting surface is tier-gated -- over the same
class of libre engines this roster wraps directly anyway.

## v1 ships no detection code

This pass is CLI-only by construction. No platform-native-capability
detection logic is written anywhere in this repository as part of it.
Native capabilities are represented solely as the documented
Covered/Partial/Gap/Unknown evidence table above -- the same table shape
`skills/scanning-attack-surfaces/references/github-surface-checklist.md`
and `skills/scanning-attack-surfaces/references/gitlab-surface-checklist.md`
already use -- never as executable branching a skill runs.

A future pass may add real detection. When it does, it inherits the
per-run verification requirement in part 1 of the test above: a detection
routine that consults a cached tier table instead of live documentation
satisfies neither this policy nor the reason it exists.

## Named residual risk

The tier placements above (what is free vs. paid on GitHub and GitLab)
are a snapshot as of the research date, and platforms change pricing and
tier boundaries. This document adds no staleness-detection gate for the
table. The risk is named here, not solved: a skill citing this document
inherits the per-run live-docs requirement precisely so a stale row here
cannot promote a paid capability to "free" in a real run.

## Refs

The two short source tags used throughout this document, in full:

- `[#844]` -- https://github.com/tvna/gitapex/issues/844 (this document's
  own scope and Acceptance Criteria Map; its Facts section carries the
  primary-source research this table restates).
- `[#843]` -- https://github.com/tvna/gitapex/issues/843 (tracking issue:
  the `scanning-*` roster, the rejected roster and tool candidates, and
  the capability-selection summary this document expands).
