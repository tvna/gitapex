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

Issue #673 (refs #665 repair 1): a fifth process-disclosure check, same
RAN/NOT-RUN/WAIVED shape again.

- `deterministic-gate-quality`: required when the calling workflow's diff
  adds or modifies a `.github/scripts/gate_*.py` or
  `.github/scripts/scan_*.py` -- this repository's own deterministic
  gates. PR #651 shipped a new gate that itself fail-opened three separate
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

  The workflow's `paths:` trigger list does *not* grow for this check.
  Its existing `.github/scripts/*.py` entry already fires for both new
  globs, verified live rather than assumed: PR #651 touched none of
  `skills/**/SKILL.md`, `docs/superpowers/specs/*.md`,
  `skills/*/scripts/*.py`, or `evals/scripts/*.py` -- only
  `.github/scripts/gate_plugin_root_brace_notation.py` -- and this
  workflow's own `skill-audit-disclosure` check ran and passed on it
  (check run 91426145937). Adding `gate_*.py`/`scan_*.py` there would be
  a strict no-op.

The calling workflow decides applicability (only invoked when the PR's
diff adds or modifies a skills/*/SKILL.md file, a
docs/superpowers/specs/*.md design doc, or a deterministic checker
script) and which skills had a description-line change, need
eval-coverage disclosure, are security-relevant, which design docs
changed, which checker scripts changed, or which of those are this
repository's own deterministic gate scripts (all of this requires git
history this script deliberately does not access); this script only
grades the body text handed to it against those workflow-supplied facts.
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
# the calling workflow supplies a non-empty item list for it.
# "RAN"/"NOT-RUN" (case-insensitive, same as every other vocabulary here)
# discloses whether the named process happened at all -- WAIVED: <reason>
# is accepted too, via the shared _line_pattern factory, same as the two
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
# one-line since tests call them directly by name) into this table instead
# of hand-copying a fourth time. #673's deterministic-gate-quality entry
# below is that predicted fourth check, and it is exactly one table row
# plus one wrapper: the CLI flag, main() wiring, and FAIL-message block
# all come from this table with no edit.
_ProcessDisclosureCheck = collections.namedtuple(
    "_ProcessDisclosureCheck",
    ["name", "cli_flag", "cli_dest", "help_text", "fail_subject", "fail_hint"],
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
    ),
    # Issue #673 (refs #665 repair 1): this repository's own deterministic
    # gates (.github/scripts/gate_*.py, scan_*.py) are the narrower subset
    # of checker scripts for which a written grading rubric already exists
    # -- skills/evaluating-deterministic-gate-quality/references/
    # dimensions.md. PR #651's new gate shipped three fail-open defects,
    # each contradicting dimension 15, while the PR disclosed
    # checker-script-adversarial-review: RAN. So this is a distinct
    # process, not a duplicate of the check above: "was it read against the
    # rubric", not "did a review round happen".
    _ProcessDisclosureCheck(
        name="deterministic-gate-quality",
        cli_flag="--changed-gate-scripts",
        cli_dest="changed_gate_scripts",
        help_text=(
            "Comma-separated deterministic gate-script paths "
            "(.github/scripts/gate_*.py or .github/scripts/scan_*.py) "
            "added or modified in this diff (issue #673, refs #665 "
            "repair 1)."
        ),
        fail_subject="changed deterministic gate script",
        fail_hint=(
            ", disclosing whether this gate was read against "
            "skills/evaluating-deterministic-gate-quality/references/"
            "dimensions.md -- dimension 15's fail-closed-on-malformed-input "
            "default in particular, which PR #651's own new gate violated "
            "three separate ways"
        ),
    ),
)

_PROCESS_DISCLOSURE_LINE_RES = {
    check.name: _line_pattern(check.name, _PROCESS_DISCLOSURE_VERDICTS)
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


def find_missing_disclosures(body_text):
    """Return the list of audit names with no valid disclosure line in body_text."""
    section = _extract_section(_normalize_body(body_text))
    if section is None:
        return list(_VERDICTS)
    return [name for name, pattern in _LINE_PATTERNS.items() if not pattern.search(section)]


def find_disallowed_battle_testing_waiver(body_text, description_changed_skills):
    """Return description_changed_skills unchanged if the PR body discloses
    battle-testing-a-skill as WAIVED despite one of those skills' SKILL.md
    description line having changed in this diff (Repair 3); else [].
    """
    if not description_changed_skills:
        return []
    section = _extract_section(_normalize_body(body_text))
    if section is None:
        return []
    if _BATTLE_TESTING_WAIVED_RE.search(section):
        return list(description_changed_skills)
    return []


def _find_missing_disclosure(body_text, items, pattern):
    """Return `items` unchanged if none of them is covered by a line in the
    PR body's '## Skill audit evidence' section matching `pattern`; else
    []. Shared by the three conditional, workflow-supplied-list checks
    below (issue #517: collapses what were three structurally-identical
    functions differing only in which items/pattern they close over)."""
    if not items:
        return []
    section = _extract_section(_normalize_body(body_text))
    if section is None:
        return list(items)
    if pattern.search(section):
        return []
    return list(items)


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
    deterministic-gate-quality RAN/NOT-RUN/WAIVED line in the PR body
    (issue #673, refs #665 repair 1); else [].
    """
    return _find_missing_disclosure(
        body_text, changed_gate_scripts, _PROCESS_DISCLOSURE_LINE_RES["deterministic-gate-quality"]
    )


def _parse_skill_list(raw):
    """Comma-separated skill names -> a sorted, deduped, non-empty list."""
    return sorted({item.strip() for item in (raw or "").split(",") if item.strip()})


def main(argv=None):
    """CLI: exit 0 iff the given PR body discloses every applicable check --
    the two #248 audits when a SKILL.md changed, the two #427
    description-change-only checks, and each #517/#565/#673
    process-disclosure check the workflow flags as applicable -- else 1.
    """
    parser = argparse.ArgumentParser(
        description="Check that a PR body discloses the required skill-audit "
        "and deterministic-checker-script review evidence for this diff "
        "(see this module's own docstring for the full check catalogue)."
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
            open(args.body, encoding="utf-8").read() if args.body else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: body file not found: {args.body}", file=sys.stderr)
        return 1

    missing = find_missing_disclosures(body_text) if args.skill_md_changed else []
    description_changed_skills = _parse_skill_list(args.description_changed_skills)
    needs_eval_coverage_skills = _parse_skill_list(args.needs_eval_coverage_skills)
    disallowed_waiver_skills = find_disallowed_battle_testing_waiver(
        body_text, description_changed_skills
    )
    missing_eval_coverage_skills = find_missing_eval_coverage_disclosure(
        body_text, needs_eval_coverage_skills
    )
    process_disclosure_missing = {
        check.name: _find_missing_disclosure(
            body_text,
            _parse_skill_list(getattr(args, check.cli_dest)),
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
            print(
                f"FAIL: {check.fail_subject} with no {check.name} disclosure for: "
                + ", ".join(missing_items)
                + f". Add '{check.name}: RAN' or '{check.name}: NOT-RUN' (or "
                "'... : WAIVED: <reason>') in the '## Skill audit evidence' "
                f"section{check.fail_hint}.",
                file=sys.stderr,
            )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
