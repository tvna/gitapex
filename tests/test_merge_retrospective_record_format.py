"""Drift gate for merge-retrospective's Repair record format (issue #313).

Codex review on PR #359 found that the "Repair record format" section
declares a fixed, machine-readable shape for repair and carried-forward
entries, but nothing checked that shape stayed intact -- the skill's own
Worked example had already drifted from its declared carried-forward
schema (a `Proposed gate (repeated from issue #N):` label instead of the
fixed `Proposed gate:`, see the corrected schema below) with nothing to
catch it. This parses SKILL.md's own Worked example the same way a real
drift-check script would and asserts every entry matches the format
`SKILL.md` itself declares, so a future edit that silently breaks the
fixed shape fails CI instead of shipping unnoticed.
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

_REPAIR_ENTRY_RE = re.compile(
    r"^\d+\.\s\[[^\]]+\].*?(?=\n\d+\.\s\[|\Z)", re.MULTILINE | re.DOTALL
)
_CLASSIFICATION_RE = re.compile(
    r"^\s*Classification:\s*([^\n]+?)\.?$", re.MULTILINE
)
_STATUS_RE = re.compile(r"^\s*Status:\s*`([^`]+)`", re.MULTILINE)
_PROPOSED_GATE_LINE_RE = re.compile(r"^\s*Proposed gate[^:]*:", re.MULTILINE)
_PROPOSED_GATE_FIXED_LABEL_RE = re.compile(r"^\s*Proposed gate:", re.MULTILINE)


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
    end = issue_body.index("## Carried-forward gate")
    return issue_body[start:end]


def _carried_forward_section(issue_body: str) -> str:
    start = issue_body.index("## Carried-forward gate") + len(
        "## Carried-forward gate"
    )
    end = issue_body.index("## Notes")
    return issue_body[start:end]


def test_repair_record_format_declares_the_three_fixed_fields():
    text = _skill_text()
    section = text[
        text.index("## Repair record format") : text.index("## Procedure")
    ]
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
        assert status_match is not None, (
            f"repair entry {label!r} has no 'Status: `<slug>`' line."
        )
        slug = status_match.group(1)
        assert slug in _VALID_SLUGS, (
            f"repair entry {label!r} has Status slug {slug!r}, not one of "
            f"the three fixed slugs {sorted(_VALID_SLUGS)}."
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


def test_carried_forward_entry_uses_its_own_two_field_schema():
    section = _carried_forward_section(_worked_example_issue_body())

    assert not _CLASSIFICATION_RE.search(section), (
        "the Carried-forward gate entry carries a 'Classification:' line, "
        "but the carried-forward schema never classifies -- it only "
        "re-reports a prior issue's still-unimplemented gate."
    )

    status_match = _STATUS_RE.search(section)
    assert status_match is not None, (
        "the Carried-forward gate entry has no 'Status: `carried-forward`' "
        "line."
    )
    assert status_match.group(1) == "carried-forward", (
        f"the Carried-forward gate entry's Status is `{status_match.group(1)}`, "
        "not the fixed literal `carried-forward` token."
    )

    assert _PROPOSED_GATE_FIXED_LABEL_RE.search(section), (
        "the Carried-forward gate entry has no line with the exact fixed "
        "label 'Proposed gate:' -- the schema requires this literal label "
        "(e.g. never 'Proposed gate (repeated from issue #N):') so a "
        "drift-check can match the field name."
    )
    assert "repeated from issue" not in section, (
        "the Carried-forward gate entry annotates the 'Proposed gate' "
        "field label itself (e.g. 'repeated from issue #N') instead of "
        "putting the prior issue's number in the prose 'what happened' "
        "clause -- this breaks the fixed field-label shape a drift-check "
        "matches on."
    )
