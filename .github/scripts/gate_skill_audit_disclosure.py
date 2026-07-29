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

The calling workflow decides applicability (only invoked when the PR's
diff adds or modifies a skills/*/SKILL.md file or a
docs/superpowers/specs/*.md design doc) and which skills had a
description-line change, need eval-coverage disclosure, are
security-relevant, or which design docs changed (all of this requires git
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

# Issue #517 (refs #454, #277): two process-disclosure checks, each
# required only when the calling workflow supplies a non-empty skill/doc
# list for it. "RAN"/"NOT-RUN" (case-insensitive, same as every other
# vocabulary here) discloses whether the named process happened at all --
# WAIVED: <reason> is accepted too, via the shared _line_pattern factory,
# same as the two audits in _VERDICTS.
_PROCESS_DISCLOSURE_VERDICTS = ("RAN", "NOT-RUN")

_SECURITY_COVERAGE_CHECK_NAME = "adversarial-coverage-mapping"
_SECURITY_COVERAGE_LINE_RE = _line_pattern(
    _SECURITY_COVERAGE_CHECK_NAME, _PROCESS_DISCLOSURE_VERDICTS
)

_DESIGN_DOC_CHECK_NAME = "design-doc-adversarial-review"
_DESIGN_DOC_LINE_RE = _line_pattern(_DESIGN_DOC_CHECK_NAME, _PROCESS_DISCLOSURE_VERDICTS)


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
    return _find_missing_disclosure(body_text, security_relevant_skills, _SECURITY_COVERAGE_LINE_RE)


def find_missing_design_doc_disclosure(body_text, changed_design_docs):
    """Return changed_design_docs unchanged if none of them is covered by a
    design-doc-adversarial-review RAN/NOT-RUN/WAIVED line in the PR body
    (issue #517, refs #277); else [].
    """
    return _find_missing_disclosure(body_text, changed_design_docs, _DESIGN_DOC_LINE_RE)


def _parse_skill_list(raw):
    """Comma-separated skill names -> a sorted, deduped, non-empty list."""
    return sorted({item.strip() for item in (raw or "").split(",") if item.strip()})


def main(argv=None):
    """CLI: exit 0 iff the given PR body discloses both audits (and, when
    applicable, the two description-change-only checks from issue #427),
    else 1.
    """
    parser = argparse.ArgumentParser(
        description="Check that a PR body discloses battle-testing-a-skill and "
        "evaluating-skill-quality audit evidence for a skill-content change."
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
    parser.add_argument(
        "--security-relevant-skills",
        default="",
        help="Comma-separated skill names (skills/<name>/SKILL.md) whose "
        "frontmatter heuristically matches a security-relevant keyword "
        "(issue #517, refs #454).",
    )
    parser.add_argument(
        "--changed-design-docs",
        default="",
        help="Comma-separated docs/superpowers/specs/*.md filenames added "
        "or modified in this diff (issue #517, refs #277).",
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
    security_relevant_skills = _parse_skill_list(args.security_relevant_skills)
    missing_security_coverage_skills = find_missing_security_coverage_disclosure(
        body_text, security_relevant_skills
    )
    changed_design_docs = _parse_skill_list(args.changed_design_docs)
    missing_design_doc_skills = find_missing_design_doc_disclosure(
        body_text, changed_design_docs
    )

    if (
        not missing
        and not disallowed_waiver_skills
        and not missing_eval_coverage_skills
        and not missing_security_coverage_skills
        and not missing_design_doc_skills
    ):
        print("PASS: skill audit evidence disclosed for both audits")
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

    if missing_security_coverage_skills:
        print(
            "FAIL: security-relevant skill change with no "
            "adversarial-coverage-mapping disclosure for: "
            + ", ".join(missing_security_coverage_skills)
            + ". Add 'adversarial-coverage-mapping: RAN' or "
            "'adversarial-coverage-mapping: NOT-RUN' (or "
            "'... : WAIVED: <reason>') in the '## Skill audit evidence' "
            "section, disclosing whether an adversarial coverage-mapping "
            "round ran against this security-relevant skill.",
            file=sys.stderr,
        )

    if missing_design_doc_skills:
        print(
            "FAIL: changed design doc with no design-doc-adversarial-review "
            "disclosure for: "
            + ", ".join(missing_design_doc_skills)
            + ". Add 'design-doc-adversarial-review: RAN' or "
            "'design-doc-adversarial-review: NOT-RUN' (or "
            "'... : WAIVED: <reason>') in the '## Skill audit evidence' "
            "section.",
            file=sys.stderr,
        )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
