"""Drift gate for merge-retrospective's Repair record format (issue #313).

Codex review on PR #359 found that the "Repair record format" section
declares a fixed, machine-readable shape for repair entries, but nothing
checked that shape stayed intact -- the skill's own Worked example had
already drifted from its declared shape with nothing to catch it. This
parses SKILL.md's own Worked example the same way a real drift-check
script would and asserts every entry matches the format `SKILL.md` itself
declares, so a future edit that silently breaks the fixed shape fails CI
instead of shipping unnoticed.

Issue #1406's flat gate-proposal-issues redesign unified "this cycle's
own Repairs" and "carried-forward from history" into one filing path
(Decision 2), removing the separate two-field carried-forward schema this
file used to also cover -- a carried-forward finding is no longer a
distinct record shape, it is filed the same way any other
missing-deterministic-gate repair is. This file's scope narrowed to match:
the fixed `Filed as: #<N>` field (Decision 1) that Step 5 now records
against a missing-deterministic-gate repair once its own standalone issue
is filed.
"""

from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "skills" / "merge-retrospective" / "SKILL.md"

_TAXONOMY_PHRASE_TO_SLUG = {
    "missing deterministic gate": "missing-deterministic-gate",
    "unclear agent instruction": "unclear-agent-instruction",
    "external/human decision": "external-human-decision",
}
_VALID_SLUGS = set(_TAXONOMY_PHRASE_TO_SLUG.values())

_REPAIR_ENTRY_RE = re.compile(r"^\d+\.\s\[[^\]]+\].*?(?=\n\d+\.\s\[|\Z)", re.MULTILINE | re.DOTALL)
_CLASSIFICATION_RE = re.compile(r"^\s*Classification:\s*([^\n]+?)\.?$", re.MULTILINE)
_STATUS_RE = re.compile(r"^\s*Status:\s*`([^`]+)`", re.MULTILINE)
_PROPOSED_GATE_LINE_RE = re.compile(r"^\s*Proposed gate[^:]*:", re.MULTILINE)


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _worked_example_issue_body() -> str:
    text = _skill_text()
    anchor = text.index("## Worked example")
    fence_start = text.index("```\nTitle:", anchor)
    fence_end = text.index("\n```", fence_start)
    return text[fence_start + len("```\n") : fence_end]


def _repairs_section(issue_body: str) -> str:
    start = issue_body.index("## Repairs") + len("## Repairs")
    end = issue_body.index("## Notes")
    return issue_body[start:end]


_FILED_AS_RE = re.compile(r"^\s*Filed as:\s*#(\d+)\s*$", re.MULTILINE)


def test_repair_record_format_declares_the_three_fixed_fields():
    text = _skill_text()
    section = text[text.index("## Repair record format") : text.index("## Procedure")]
    assert "Classification: <exact taxonomy phrase>" in section
    assert "Status: `<machine-readable slug>`" in section
    assert "Proposed gate: <durable gate text" in section


def test_worked_example_has_exactly_three_repairs():
    repairs = _REPAIR_ENTRY_RE.findall(_repairs_section(_worked_example_issue_body()))
    assert len(repairs) == 3, (
        f"expected 3 repair entries in the Worked example's Repairs section, "
        f"found {len(repairs)} -- {SKILL_PATH} may have drifted from its own "
        "documented three-taxonomy-category example."
    )


def test_worked_example_repairs_match_the_declared_record_format():
    repairs = _REPAIR_ENTRY_RE.findall(_repairs_section(_worked_example_issue_body()))
    for entry in repairs:
        label = entry.splitlines()[0]

        classification_match = _CLASSIFICATION_RE.search(entry)
        assert classification_match is not None, (
            f"repair entry {label!r} has no 'Classification:' line -- every "
            "repair entry must carry one per the Repair record format."
        )
        classification = classification_match.group(1).split(" -- ")[0].strip()
        assert classification in _TAXONOMY_PHRASE_TO_SLUG, (
            f"repair entry {label!r} has Classification {classification!r}, "
            f"which is not one of the three fixed taxonomy phrases "
            f"{sorted(_TAXONOMY_PHRASE_TO_SLUG)} -- never invent a fourth "
            "category or paraphrase the fixed phrase."
        )

        status_match = _STATUS_RE.search(entry)
        assert status_match is not None, f"repair entry {label!r} has no 'Status: `<slug>`' line."
        slug = status_match.group(1)
        assert slug in _VALID_SLUGS, (
            f"repair entry {label!r} has Status slug {slug!r}, not one of the three fixed slugs {sorted(_VALID_SLUGS)}."
        )
        assert _TAXONOMY_PHRASE_TO_SLUG[classification] == slug, (
            f"repair entry {label!r} pairs Classification {classification!r} "
            f"with Status `{slug}`, but the Repair record format requires "
            f"Status to restate the same classification as its fixed slug "
            f"(expected `{_TAXONOMY_PHRASE_TO_SLUG[classification]}`)."
        )

        has_proposed_gate = bool(_PROPOSED_GATE_LINE_RE.search(entry))
        if slug == "missing-deterministic-gate":
            assert has_proposed_gate, (
                f"repair entry {label!r} is classified "
                "missing-deterministic-gate but has no 'Proposed gate:' "
                "line -- Step 4 requires a gate proposal for this category."
            )
        else:
            assert not has_proposed_gate, (
                f"repair entry {label!r} is classified `{slug}` but carries "
                "a 'Proposed gate' line -- the Repair record format omits "
                "this field entirely for the unclear-agent-instruction and "
                "external-human-decision categories."
            )

        has_filed_as = bool(_FILED_AS_RE.search(entry))
        if slug == "missing-deterministic-gate":
            assert has_filed_as, (
                f"repair entry {label!r} is classified "
                "missing-deterministic-gate but has no 'Filed as: #<N>' "
                "line -- Step 5 records this once its own standalone "
                "gate-proposal issue is filed and confirmed."
            )
        else:
            assert not has_filed_as, (
                f"repair entry {label!r} is classified `{slug}` but carries "
                "a 'Filed as:' line -- only a missing-deterministic-gate "
                "repair ever gets a standalone filed issue."
            )
