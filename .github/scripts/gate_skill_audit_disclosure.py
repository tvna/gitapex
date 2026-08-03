#!/usr/bin/env python3
"""Check a PR body for skill-audit disclosure evidence.

Issue #248 (refs #242, #246): a PR that adds or modifies a skill's
SKILL.md must disclose that battle-testing-a-skill and
evaluating-skill-quality were run against it -- a verdict for each named
audit, or an explicit waiver with a reason -- rather than depending on
someone remembering to ask for either audit by name. This is the
deterministic backstop: it checks that disclosure was made, not that the
audits actually passed, which stays a human/reviewer judgment matching
the two audits' own model-graded nature.

Issue #427 (refs #422): when a changed SKILL.md's frontmatter
`description:` line itself changed, two extra rules apply, both computed
from the same workflow-supplied skill-name lists:

- `battle-testing-a-skill` may no longer be disclosed as WAIVED (Repair
  3) -- a real PASS/FAIL/INDETERMINATE verdict is required instead, since
  the description field is the highest-leverage text that audit exists to
  scrutinize.
- The PR's diff must also touch that skill's own `evals/<skill>/tasks/`
  or `evals/<skill>/eval-status.md` (issue #499: moved from the single
  central `docs/skill-eval-status.md`), or disclose an
  `eval-coverage-disclosure: WAIVED: <reason>` line (Repair 1).

Issue #517 (refs #454, #277): two more conditional, workflow-supplied-fact
checks, same shape as the #427 pair above but disclosing *whether a
process ran* rather than grading an audit's outcome, so both share a
"RAN"/"NOT-RUN" vocabulary (WAIVED still accepted, same as every other
check here) instead of a PASS/FAIL-style verdict:

- `adversarial-coverage-mapping`: required when the calling workflow
  heuristically flags a changed skill as security-relevant (keyword match
  on the skill's own frontmatter block, computed by the workflow -- this
  script only grades PR-body text, never skill content).
- `design-doc-adversarial-review`: required when the calling workflow's
  diff touches a `docs/superpowers/specs/*.md` design doc (added or
  modified). This is why the workflow's `paths:` trigger list grew to
  include that glob alongside `skills/**/SKILL.md`.

Issue #565 (refs #560 repair 5): a fourth process-disclosure check, same
RAN/NOT-RUN/WAIVED shape as the two above.

- `checker-script-adversarial-review`: required when the calling
  workflow's diff adds or modifies a deterministic checker script under
  `skills/*/scripts/*.py`, `evals/scripts/*.py`, or `.github/scripts/*.py`.
  PR #558 (retrospective: issue #560) touched only
  `skills/evaluating-skill-quality/scripts/check_skill_shape.py` -- no
  SKILL.md -- and still shipped four real correctness bugs (two regex
  boundary asymmetries, a hedge-proximity window bug, a duplicated cache)
  that pytest, ruff, and a full corpus sweep all missed; only a voluntary
  `/code-review` pass caught them, and nothing required that disclosure.
  This is why the workflow's `paths:` trigger list grows again to include
  these three globs.

Issue #673 (refs #665 repair 1): a fifth process-disclosure check. Same
WAIVED-with-reason escape as every check here, but the only one that
narrows the RAN/NOT-RUN pair to RAN alone -- see its own registry-row
comment for why "NOT-RUN" is not an acceptable answer for this one.

- `deterministic-gate-quality`: required when the calling workflow's diff
  touches one of this repository's own deterministic gates -- by naming
  convention (`.github/scripts/gate_*.py` / `scan_*.py`,
  `hooks/check-*.sh` / `check_*.py`), by registration (any
  `.gitapex/ssot.json` `gates[].script` path), or by being one of the two
  files that decide whether gates run at all (the registry itself and
  `hooks/hooks.json`). `detect_changed_gate_scripts.py` computes that
  membership and the workflow hands the result here; see that script's
  docstring for why each rule is needed, why a deletion or rename counts,
  and why it carries no dependency-pin exemption.
  PR #651 shipped a new gate that itself fail-opened three separate
  ways (zero discovered surfaces exited 0; an unterminated frontmatter
  block was read as "no frontmatter" so a real violation went ungraded; an
  unreadable or non-UTF-8 file produced a filenameless message or an
  uncaught traceback). Every one of those contradicts a criterion this
  repository already owns and already wrote down --
  `skills/evaluating-deterministic-gate-quality/references/dimensions.md`
  dimension 15 ("Fail-closed default on incomplete or malformed input")
  and `gate_evals_scripts_coverage.py`'s own docstring rule that an empty
  match set is an error, never a silent pass. The rubric existed; nothing
  made a new gate get read against it, and all three defects passed CI and
  every pre-review check, surfacing only when an operator ran
  `/code-review` by hand. This check is that missing step.

  Deliberately *not* folded into `checker-script-adversarial-review`
  above, even though every path this check fires on is also a checker
  script: the two disclose different processes. That one asks whether an
  adversarial review round happened at all; this one asks whether the
  change was read against a specific, already-written rubric. A PR
  touching `.github/scripts/gate_x.py` therefore owes both lines -- which
  is the intended outcome, not double-counting. PR #651 is the direct
  evidence: it disclosed `checker-script-adversarial-review: RAN` and
  still shipped all three fail-open defects.

  No `gate_*.py`/`scan_*.py` entry is added to the workflow's `paths:`
  trigger, because its existing `.github/scripts/*.py` entry already
  fires for both -- verified live rather than assumed: PR #651 touched
  none of `skills/**/SKILL.md`, `docs/superpowers/specs/*.md`,
  `skills/*/scripts/*.py`, or `evals/scripts/*.py` -- only
  `.github/scripts/gate_plugin_root_brace_notation.py` -- and this
  workflow's own `skill-audit-disclosure` check ran and passed on it
  (check run 91426145937). The registration rule *does* grow that list,
  though, to `hooks/**`, `.github/workflows/*.yml`,
  `.github/workflows/*.yaml` and `.gitapex/ssot.json`: the registry names
  gate implementations in all three places, and none of them matched any
  pre-existing entry, so without the additions this workflow would simply
  never run for them. tests/test_skill_audit_gate_workflow_wiring.py gates
  that correspondence, so a gate registered at an unreachable path fails
  rather than silently skipping the job.

The calling workflow decides applicability. It is invoked when the PR's
diff touches a skills/*/SKILL.md file, a docs/superpowers/specs/*.md
design doc, a deterministic checker script, or a deterministic gate --
the last of which is an *independent* condition, not a subset of the
checker-script one, even though the two overlap heavily today. The
workflow's own applicability test keeps them independent deliberately, so
narrowing the checker-script globs later can never silently disable the
gate check; do not "simplify" either side on the assumption that one
implies the other. The workflow also supplies which skills had a
description-line change, need eval-coverage disclosure, or are
security-relevant, and which design docs, checker scripts, and gates
changed (all of this requires git history this script deliberately does
not access); this script only grades the body text handed to it against
those workflow-supplied facts.
Deliberately not placed inside either audited skill's own directory: both
declare a portability level whose procedure must not depend on this
repository's specific tooling, and parsing this repository's PR-body
convention is exactly such repository-specific glue.

Mirrors skills/planning-a-branch-from-an-issue/scripts/check_acm_present.py's CLI shape
(--body <path> or stdin, PASS/FAIL output, same exit-code convention)
without importing or duplicating it -- different section, different
verdict vocabulary, no shared contract between the two checks.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

_SECTION_RE = re.compile(r"^##[ \t]*Skill audit evidence[ \t]*$", re.IGNORECASE | re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##[ \t]+\S", re.MULTILINE)

# Each audit's closed disclosure-line vocabulary. "WAIVED: <reason>" is
# accepted for either audit and is checked separately, not folded into
# these tuples, since it requires a non-empty trailing reason.
_VERDICTS = {
    "battle-testing-a-skill": ("PASS", "FAIL", "INDETERMINATE"),
    "evaluating-skill-quality": (
        "WELL-FORMED-AND-MATURE",
        "WELL-FORMED-NOT-MATURE",
        "NOT-WELL-FORMED",
    ),
}

# Shared fragments so the WAIVED syntax and the "- `name`:" line prefix are
# each defined exactly once -- reused below by both the two-audit verdict
# patterns and the description-change-only checks (issue #427), so there is
# never a second, subtly different waiver syntax to keep in sync.
_WAIVED_CLAUSE = r"WAIVED[ \t]*:[ \t]*\S.*"


def _name_prefix(name):
    return r"^[ \t]*[-*]?[ \t]*`?" + re.escape(name) + r"`?[ \t]*:[ \t]*"


def _line_pattern(name, verdicts):
    verdict_alt = "|".join(re.escape(v) for v in verdicts)
    return re.compile(
        _name_prefix(name)
        + r"(?:(?:"
        + verdict_alt
        + r")\b(?:[ \t]+\S.*)?|"
        + _WAIVED_CLAUSE
        + r")[ \t]*$",
        re.IGNORECASE | re.MULTILINE,
    )


def _waived_pattern(name):
    """A line disclosing `name` specifically via the WAIVED: <reason> form."""
    return re.compile(_name_prefix(name) + _WAIVED_CLAUSE + r"[ \t]*$", re.IGNORECASE | re.MULTILINE)


_LINE_PATTERNS = {name: _line_pattern(name, verdicts) for name, verdicts in _VERDICTS.items()}

# Issue #427 (refs #422): battle-testing-a-skill's WAIVED form is legal in
# general but rejected when the diff modifies a changed SKILL.md's own
# description line (Repair 3) -- checked separately from _LINE_PATTERNS
# above, which stays permissive for the unconditional case.
_BATTLE_TESTING_WAIVED_RE = _waived_pattern("battle-testing-a-skill")

# Issue #427 (refs #422): a skill whose description changed must also touch
# its own evals/<skill>/tasks/ or evals/<skill>/eval-status.md (checked by
# the calling workflow, not this script; issue #499 moved the latter from a
# single central docs/skill-eval-status.md), or disclose this WAIVED-only
# line -- there is no PASS/FAIL/INDETERMINATE verdict form for this check,
# since "touched evals/<skill>/" is a diff fact the workflow already
# verified, not a model-graded judgment this script can independently
# confirm (Repair 1).
_EVAL_COVERAGE_CHECK_NAME = "eval-coverage-disclosure"
_EVAL_COVERAGE_WAIVER_RE = _waived_pattern(_EVAL_COVERAGE_CHECK_NAME)

# Issue #517 (refs #454, #277) / #565 (refs #560 repair 5) / #673 (refs
# #665 repair 1): four process-disclosure checks, each required only when
# the calling workflow supplies a non-empty item list for it. Each row
# carries its own accepted-verdict tuple; three take the shared
# "RAN"/"NOT-RUN" pair (case-insensitive, same as every other vocabulary
# here) disclosing whether the named process happened at all, and the
# fourth narrows it -- see its own comment. "WAIVED: <reason>" is accepted
# for every row, via the shared _line_pattern factory, same as the two
# audits in _VERDICTS.
#
# A registry, not four hand-copied name/CLI-flag/help-text/FAIL-message
# constants: by the third such check (adversarial-coverage-mapping,
# design-doc-adversarial-review, checker-script-adversarial-review) each
# was duplicated across five places (module constant, `find_missing_*`
# wrapper, CLI flag, main() wiring, FAIL-message block). #565's own
# checker-script-adversarial-review addition was that third copy -- the
# signal to collapse the four still-generic places (everything but the
# named `find_missing_*` wrappers, which stay individually named and
# one-line since tests call them directly by name) into this table.
#
# What this table does NOT supply, stated explicitly because an earlier
# revision of this comment claimed otherwise and that claim was itself the
# fail-open this file exists to prevent: a row here does not make its check
# fire. Applicability is computed by `skill-audit-gate.yml`, which must
# separately pass the row's `cli_flag`; without that edit argparse still
# registers the flag with `default=""`, every list is empty, and the check
# silently never runs while every unit test that calls its wrapper directly
# still passes. `tests/test_skill_audit_gate_workflow_wiring.py` is the
# drift gate for that correspondence -- adding a row without wiring the
# workflow fails there rather than shipping a green no-op.
_ProcessDisclosureCheck = collections.namedtuple(
    "_ProcessDisclosureCheck",
    ["name", "cli_flag", "cli_dest", "help_text", "fail_subject", "fail_hint", "verdicts"],
)

_PROCESS_DISCLOSURE_VERDICTS = ("RAN", "NOT-RUN")

_PROCESS_DISCLOSURE_CHECKS = (
    _ProcessDisclosureCheck(
        name="adversarial-coverage-mapping",
        cli_flag="--security-relevant-skills",
        cli_dest="security_relevant_skills",
        help_text=(
            "Comma-separated skill names (skills/<name>/SKILL.md) whose "
            "frontmatter heuristically matches a security-relevant keyword "
            "(issue #517, refs #454)."
        ),
        fail_subject="security-relevant skill change",
        fail_hint=(
            ", disclosing whether an adversarial coverage-mapping round "
            "ran against this security-relevant skill"
        ),
        verdicts=_PROCESS_DISCLOSURE_VERDICTS,
    ),
    _ProcessDisclosureCheck(
        name="design-doc-adversarial-review",
        cli_flag="--changed-design-docs",
        cli_dest="changed_design_docs",
        help_text=(
            "Comma-separated docs/superpowers/specs/*.md filenames added "
            "or modified in this diff (issue #517, refs #277)."
        ),
        fail_subject="changed design doc",
        fail_hint="",
        verdicts=_PROCESS_DISCLOSURE_VERDICTS,
    ),
    # Issue #565 (refs #560 repair 5): a deterministic checker script
    # (skills/*/scripts/*.py, evals/scripts/*.py, .github/scripts/*.py) is
    # exactly as capable of shipping subtly wrong logic as skill content
    # is -- PR #558 is direct evidence -- so it gets the same
    # RAN/NOT-RUN/WAIVED process-disclosure shape as the two checks above,
    # not a PASS/FAIL verdict: this checks that an adversarial review
    # round happened, not what it concluded.
    _ProcessDisclosureCheck(
        name="checker-script-adversarial-review",
        cli_flag="--changed-checker-scripts",
        cli_dest="changed_checker_scripts",
        help_text=(
            "Comma-separated deterministic checker-script paths "
            "(skills/*/scripts/*.py, evals/scripts/*.py, or "
            ".github/scripts/*.py) added or modified in this diff "
            "(issue #565, refs #560 repair 5)."
        ),
        fail_subject="changed deterministic checker script",
        fail_hint=(
            ", disclosing whether an adversarial review round ran against "
            "this deterministic checker script"
        ),
        verdicts=_PROCESS_DISCLOSURE_VERDICTS,
    ),
    # Issue #673 (refs #665 repair 1): this repository's own deterministic
    # gates are the narrower subset of checker scripts for which a written
    # grading rubric already exists --
    # skills/evaluating-deterministic-gate-quality/references/dimensions.md.
    # PR #651's new gate shipped three fail-open defects, each contradicting
    # dimension 15, while the PR disclosed
    # checker-script-adversarial-review: RAN. So this is a distinct process,
    # not a duplicate of the check above: "was it read against the rubric",
    # not "did a review round happen". Scope is computed by
    # detect_changed_gate_scripts.py (naming convention, plus every
    # .gitapex/ssot.json gates[].script path, plus that registry file
    # itself), not by a glob in the workflow -- see that script's docstring.
    #
    # The only row that narrows the shared verdict pair, and the narrowing
    # is the point: "NOT-RUN" is a legitimate disclosure for the three
    # checks above, where the named process genuinely may not have run. It
    # is not legitimate here. The retrospective's finding was that nobody
    # read a new gate against a rubric that already existed, so accepting
    # "I did not read it against the rubric" as a passing disclosure would
    # leave the exact state this check was built to end. RAN, or
    # WAIVED: <reason> -- a waiver still carries an explicit reason a
    # reviewer sees, which "NOT-RUN" does not.
    _ProcessDisclosureCheck(
        name="deterministic-gate-quality",
        cli_flag="--changed-gate-scripts",
        cli_dest="changed_gate_scripts",
        help_text=(
            "Comma-separated deterministic gate paths added, modified, "
            "deleted, or renamed in this diff, as computed by "
            "detect_changed_gate_scripts.py (issue #673, refs #665 "
            "repair 1)."
        ),
        fail_subject="changed deterministic gate",
        fail_hint=(
            ", disclosing that this gate was read against "
            "skills/evaluating-deterministic-gate-quality/references/"
            "dimensions.md -- dimension 15's fail-closed-on-malformed-input "
            "default in particular, which PR #651's own new gate violated "
            "three separate ways"
        ),
        verdicts=("RAN",),
    ),
)

_PROCESS_DISCLOSURE_LINE_RES = {
    check.name: _line_pattern(check.name, check.verdicts)
    for check in _PROCESS_DISCLOSURE_CHECKS
}


def _normalize_body(body_text):
    # Normalize CRLF/CR line endings before matching: GitHub is known to
    # deliver github.event.pull_request.body with CRLF endings for PRs
    # authored/edited via the web UI, and the heading/line regexes below
    # assume bare LF.
    return (body_text or "").replace("\r\n", "\n").replace("\r", "\n")


def _extract_section(body_text):
    """Return the "## Skill audit evidence" section body, or None if absent."""
    match = _SECTION_RE.search(body_text)
    if not match:
        return None
    next_heading = _NEXT_HEADING_RE.search(body_text, match.end())
    end = next_heading.start() if next_heading else len(body_text)
    return body_text[match.end():end]


def _missing_base_disclosures(section):
    """Core of `find_missing_disclosures`, over an already-extracted section.

    Split out so main() can grade every check against one extraction
    without re-implementing this logic inline. An earlier revision did
    inline it, which quietly broke
    tests/test_check_skill_audit_disclosure_hook_sync.py's purpose: that
    drift gate compares `find_missing_disclosures` against the PreToolUse
    hook's own copy, so once CI stopped executing that function the gate
    was comparing something real grading no longer used, and the two could
    diverge with every test still green.
    """
    if section is None:
        return list(_VERDICTS)
    return [name for name, pattern in _LINE_PATTERNS.items() if not pattern.search(section)]


def find_missing_disclosures(body_text):
    """Return the list of audit names with no valid disclosure line in body_text."""
    return _missing_base_disclosures(_extract_section(_normalize_body(body_text)))


def _disallowed_battle_testing_waiver(section, description_changed_skills):
    """Core of `find_disallowed_battle_testing_waiver`, over an
    already-extracted section. Same single-source-of-truth reason as
    `_missing_base_disclosures` above."""
    if not description_changed_skills or section is None:
        return []
    if _BATTLE_TESTING_WAIVED_RE.search(section):
        return list(description_changed_skills)
    return []


def find_disallowed_battle_testing_waiver(body_text, description_changed_skills):
    """Return description_changed_skills unchanged if the PR body discloses
    battle-testing-a-skill as WAIVED despite one of those skills' SKILL.md
    description line having changed in this diff (Repair 3); else [].
    """
    return _disallowed_battle_testing_waiver(
        _extract_section(_normalize_body(body_text)), description_changed_skills
    )


def _missing_in_section(section, items, pattern):
    """Return `items` unchanged if `section` carries no line matching
    `pattern`; else []. `section` is the already-extracted '## Skill audit
    evidence' body, or None when the PR body has no such section.

    Takes the extracted section rather than the raw body so a caller
    grading several checks against one body normalizes and extracts once
    instead of once per check -- main() grades seven, and re-deriving an
    invariant value seven times is the avoidable overhead
    `evaluating-deterministic-gate-quality`'s dimension 19 asks about.
    """
    if not items:
        return []
    if section is None:
        return list(items)
    if pattern.search(section):
        return []
    return list(items)


def _find_missing_disclosure(body_text, items, pattern):
    """Body-taking adapter over `_missing_in_section`, for the named
    `find_missing_*` wrappers below (tests call those directly by name) and
    for any caller grading a single check against one body."""
    return _missing_in_section(_extract_section(_normalize_body(body_text)), items, pattern)


def find_missing_eval_coverage_disclosure(body_text, needs_eval_coverage_skills):
    """Return needs_eval_coverage_skills unchanged if none of them is covered
    by an eval-coverage-disclosure WAIVED line in the PR body (Repair 1);
    else [].
    """
    return _find_missing_disclosure(body_text, needs_eval_coverage_skills, _EVAL_COVERAGE_WAIVER_RE)


def find_missing_security_coverage_disclosure(body_text, security_relevant_skills):
    """Return security_relevant_skills unchanged if none of them is covered
    by an adversarial-coverage-mapping RAN/NOT-RUN/WAIVED line in the PR
    body (issue #517, refs #454); else [].
    """
    return _find_missing_disclosure(
        body_text, security_relevant_skills, _PROCESS_DISCLOSURE_LINE_RES["adversarial-coverage-mapping"]
    )


def find_missing_design_doc_disclosure(body_text, changed_design_docs):
    """Return changed_design_docs unchanged if none of them is covered by a
    design-doc-adversarial-review RAN/NOT-RUN/WAIVED line in the PR body
    (issue #517, refs #277); else [].
    """
    return _find_missing_disclosure(
        body_text, changed_design_docs, _PROCESS_DISCLOSURE_LINE_RES["design-doc-adversarial-review"]
    )


def find_missing_checker_script_disclosure(body_text, changed_checker_scripts):
    """Return changed_checker_scripts unchanged if none of them is covered by
    a checker-script-adversarial-review RAN/NOT-RUN/WAIVED line in the PR
    body (issue #565, refs #560 repair 5); else [].
    """
    return _find_missing_disclosure(
        body_text, changed_checker_scripts, _PROCESS_DISCLOSURE_LINE_RES["checker-script-adversarial-review"]
    )


def find_missing_gate_quality_disclosure(body_text, changed_gate_scripts):
    """Return changed_gate_scripts unchanged if none of them is covered by a
    deterministic-gate-quality disclosure line in the PR body (issue #673,
    refs #665 repair 1); else [].

    Unlike its three siblings this check accepts RAN or a WAIVED line
    carrying a reason, but NOT "NOT-RUN" -- see the registry row's own
    comment. Spelled out here rather than copied from a sibling, because a
    reader reconciling a stale "RAN/NOT-RUN/WAIVED" docstring against the
    row would most plausibly "fix" the row and silently restore the escape
    this check was built to remove.
    """
    return _find_missing_disclosure(
        body_text, changed_gate_scripts, _PROCESS_DISCLOSURE_LINE_RES["deterministic-gate-quality"]
    )


def _parse_comma_list(raw):
    """Comma-separated tokens -> a sorted, deduped list with no empty items.

    Deliberately named for the wire format rather than for skill names:
    only two of this CLI's five list-valued flags carry skill names. The
    other three (`--changed-design-docs`, `--changed-checker-scripts`,
    `--changed-gate-scripts`) carry repository-relative file paths, so a
    skill-name-specific contract here would misdescribe most call sites and
    point a reader auditing path handling at the wrong abstraction.

    The sort is load-bearing, not incidental: it fixes the order these
    items appear in the FAIL messages below, so a failing run is
    byte-identical across invocations regardless of the order the workflow
    happened to join them in. Tokens are otherwise opaque -- shape
    validation belongs to whoever produced them (see
    `detect_changed_gate_scripts.py`, which rejects a comma-bearing path
    before it can reach this splitter at all).
    """
    return sorted({item.strip() for item in (raw or "").split(",") if item.strip()})


def main(argv=None):
    """CLI: exit 0 iff the given PR body discloses every applicable check --
    the two #248 audits when a SKILL.md changed, the two #427
    description-change-only checks, and each #517/#565/#673
    process-disclosure check the workflow flags as applicable -- else 1.
    """
    parser = argparse.ArgumentParser(
        description="Check that a PR body discloses the required skill-audit, "
        "checker-script, and deterministic-gate review evidence for this "
        "diff (see this module's own docstring for the full check "
        "catalogue)."
    )
    parser.add_argument(
        "--body",
        help="Path to the PR body text; reads standard input when omitted.",
    )
    parser.add_argument(
        "--description-changed-skills",
        default="",
        help="Comma-separated skill names (skills/<name>/SKILL.md) whose "
        "frontmatter description: line changed in this diff.",
    )
    parser.add_argument(
        "--needs-eval-coverage-skills",
        default="",
        help="Comma-separated skill names whose description changed but "
        "whose diff touches neither evals/<skill>/tasks/ nor "
        "evals/<skill>/eval-status.md.",
    )
    for check in _PROCESS_DISCLOSURE_CHECKS:
        parser.add_argument(
            check.cli_flag, dest=check.cli_dest, default="", help=check.help_text
        )
    parser.add_argument(
        "--skill-md-changed",
        action="store_true",
        help="Set when this diff adds or modifies at least one "
        "skills/*/SKILL.md file. Gates the base battle-testing-a-skill / "
        "evaluating-skill-quality check (issue #517: the workflow's "
        "applicable path now also fires for a design-doc-only change with "
        "no SKILL.md touched at all, so that base check must no longer "
        "run unconditionally -- a design-doc-only PR has nothing to "
        "disclose about audits of a skill it never touched).",
    )
    args = parser.parse_args(argv)
    try:
        body_text = (
            Path(args.body).read_text(encoding="utf-8") if args.body else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1

    # Normalize and extract once, then grade all seven checks against the
    # result. Each `find_missing_*` wrapper re-derives this from the raw
    # body on its own, which is correct for a single-check caller (and for
    # the tests, which call them by name) but would repeat two string
    # copies and two regex searches seven times here.
    section = _extract_section(_normalize_body(body_text))

    missing = _missing_base_disclosures(section) if args.skill_md_changed else []
    description_changed_skills = _parse_comma_list(args.description_changed_skills)
    needs_eval_coverage_skills = _parse_comma_list(args.needs_eval_coverage_skills)
    disallowed_waiver_skills = _disallowed_battle_testing_waiver(
        section, description_changed_skills
    )
    missing_eval_coverage_skills = _missing_in_section(
        section, needs_eval_coverage_skills, _EVAL_COVERAGE_WAIVER_RE
    )
    process_disclosure_missing = {
        check.name: _missing_in_section(
            section,
            _parse_comma_list(getattr(args, check.cli_dest)),
            _PROCESS_DISCLOSURE_LINE_RES[check.name],
        )
        for check in _PROCESS_DISCLOSURE_CHECKS
    }

    if (
        not missing
        and not disallowed_waiver_skills
        and not missing_eval_coverage_skills
        and not any(process_disclosure_missing.values())
    ):
        print("PASS: all applicable skill-audit disclosure requirements are met")
        return 0

    if missing:
        print(
            "FAIL: PR body is missing a disclosed verdict (or waiver) for: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "Add a '## Skill audit evidence' section with one line per audit, e.g.:\n"
            "  - battle-testing-a-skill: PASS\n"
            "  - evaluating-skill-quality: WELL-FORMED-AND-MATURE\n"
            "or '<audit>: WAIVED: <reason>' if intentionally skipped.",
            file=sys.stderr,
        )
        if description_changed_skills and "battle-testing-a-skill" in missing:
            print(
                "Note: a WAIVED line for battle-testing-a-skill would not be "
                "accepted here either, because this PR modifies a frontmatter "
                "description line in: " + ", ".join(description_changed_skills),
                file=sys.stderr,
            )

    if disallowed_waiver_skills:
        print(
            "FAIL: battle-testing-a-skill cannot be disclosed as WAIVED "
            "because this PR modifies a frontmatter description line in: "
            + ", ".join(disallowed_waiver_skills)
            + ". Run the full battle-testing-a-skill audit and disclose a "
            "real PASS/FAIL/INDETERMINATE verdict instead.",
            file=sys.stderr,
        )

    if missing_eval_coverage_skills:
        print(
            "FAIL: changed SKILL.md description with no eval-coverage "
            "evidence for: "
            + ", ".join(missing_eval_coverage_skills)
            + ". Touch evals/<skill>/tasks/ or evals/<skill>/eval-status.md "
            "for the changed skill, or disclose "
            "'eval-coverage-disclosure: WAIVED: <reason>' in the "
            "'## Skill audit evidence' section.",
            file=sys.stderr,
        )

    for check in _PROCESS_DISCLOSURE_CHECKS:
        missing_items = process_disclosure_missing[check.name]
        if missing_items:
            # Derived from the row's own tuple, not hardcoded: the
            # deterministic-gate-quality row deliberately does not accept
            # NOT-RUN, and a message advertising a verdict the check then
            # rejects would send an author in a circle.
            accepted = " or ".join(f"'{check.name}: {verdict}'" for verdict in check.verdicts)
            print(
                f"FAIL: {check.fail_subject} with no {check.name} disclosure for: "
                + ", ".join(missing_items)
                + f". Add {accepted} (or "
                "'... : WAIVED: <reason>') in the '## Skill audit evidence' "
                f"section{check.fail_hint}.",
                file=sys.stderr,
            )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
