"""Tests for the detection-logic-property-coverage rule-text drift gate
(.github/scripts/gitapex_scan_detection_logic_rule_drift.py).

The final test is the gate itself: the repository's real `.gitapex/
ssot.json` rule text for `detection-logic-property-coverage` must name
exactly the verbs `gitapex_gate_detection_logic_property_coverage.
ALL_TRIGGER_VERBS` actually grades, in both directions. The rest unit-test
`find_drift` against synthetic, injected `ssot_path`/`trigger_verbs` inputs
(mirroring `gitapex_scan_ssot_schema.find_drift`'s own explicit-path-with-
real-default shape) rather than only the real registry, so both drift
directions and every fail-closed input shape can be exercised directly.
Ordinary pytest, no Hypothesis -- matches every sibling scan-gate test file
(`test_gitapex_scan_ssot_schema.py`,
`test_gitapex_scan_independent_review_heading_drift.py`): this scanner's own
new file is outside `detection-logic-property-coverage`'s own scope by
naming convention (`gitapex_scan_*.py`, not `gitapex_gate_*.py` -- see that
gate's own module docstring, "#1032" paragraph), so it carries no Hypothesis
property-test obligation of its own.
"""

from __future__ import annotations

import json
import pathlib

import gitapex_gate_detection_logic_property_coverage as gate
import gitapex_scan_detection_logic_rule_drift as drift
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_GATE_ID = "detection-logic-property-coverage"


def _write_ssot(tmp_path: pathlib.Path, instance: object, *, filename: str = "ssot.json") -> pathlib.Path:
    path = tmp_path / filename
    path.write_text(json.dumps(instance), encoding="utf-8")
    return path


def _instance_with_rule(rule_text: str, *, gate_id: str = _GATE_ID) -> dict[str, list[dict[str, str]]]:
    return {"gates": [{"id": gate_id, "rule": rule_text}]}


# ---------------------------------------------------------------------------
# (a) real repository state -> no drift.
# ---------------------------------------------------------------------------


def test_real_repository_rule_text_has_no_drift() -> None:
    """The gate: the real `.gitapex/ssot.json` rule text for
    `detection-logic-property-coverage` must mention exactly the verbs
    `ALL_TRIGGER_VERBS` grades, no more and no fewer."""
    findings = drift.find_drift()
    assert findings == [], f"detection-logic-property-coverage rule-text drift found: {findings}"


def test_real_rule_text_extracts_exactly_the_trigger_verb_count(tmp_path: pathlib.Path) -> None:
    """Adversarial self-check (defeat-test obligation): pins that the live
    rule text's `verb()`-shaped token extraction yields *exactly*
    `ALL_TRIGGER_VERBS`, with no extra, coincidental `word()`-shaped token
    that is not itself one of the gate's real 16 trigger verbs. A rule text
    that grew such a coincidental token would be a real false-positive-risk
    case this module's own docstring asks to be checked; today's real text
    carries none (confirmed empirically, not assumed) -- this test fails
    loudly the day that stops being true, rather than the drift going
    unnoticed."""
    real_ssot = json.loads((REPO_ROOT / ".gitapex" / "ssot.json").read_text(encoding="utf-8"))
    rule_text, findings = drift._find_gate_rule(real_ssot)
    assert findings == []
    assert rule_text is not None
    assert drift._rule_verbs(rule_text) == gate.ALL_TRIGGER_VERBS


# ---------------------------------------------------------------------------
# (b) regression: reproduce the ORIGINAL defect (issue #1918 repair 6) --
# a verb present in the code's own trigger set but never mentioned in the
# registry's rule text.
# ---------------------------------------------------------------------------


def test_regression_verb_added_to_code_but_missing_from_rule_text_is_drift(tmp_path: pathlib.Path) -> None:
    """Reproduces the exact original defect class: `_STRING_SPLIT_RECEIVER_
    AGNOSTIC_ATTRS` grew `.split()`/`.rsplit()`/`.partition()` (issue #1532,
    consolidated into #1572) without the `.gitapex/ssot.json` rule text
    being updated in the same change -- fixed by hand only after the fact,
    in commit `1d4d67a9`. Synthesizes that exact shape: `trigger_verbs`
    knows about `"split"`, the rule-text fixture does not mention it at
    all. This must produce a drift finding naming the missing verb."""
    trigger_verbs = frozenset({"compile", "match", "split"})
    rule_text = "A regex .compile() or .match() call is graded."
    instance_path = _write_ssot(tmp_path, _instance_with_rule(rule_text))

    findings = drift.find_drift(instance_path, trigger_verbs)

    assert len(findings) == 1, findings
    assert "split" in findings[0]
    assert "not mentioned" in findings[0]


# ---------------------------------------------------------------------------
# (c) mirror direction: a stale verb() token in the rule text that the code
# no longer actually grades.
# ---------------------------------------------------------------------------


def test_mirror_stale_verb_in_rule_text_no_longer_graded_is_drift(tmp_path: pathlib.Path) -> None:
    """The mirror-image case: the rule text still names a verb that
    `ALL_TRIGGER_VERBS` no longer contains (e.g. a trigger verb removed from
    the gate script without the registry prose describing it being trimmed
    to match). Must be reported as drift too -- bidirectional, per design
    resolution 4 of this task's own plan doc."""
    trigger_verbs = frozenset({"compile"})
    rule_text = "A regex .compile() or a retired .obsolete_verb() call is graded."
    instance_path = _write_ssot(tmp_path, _instance_with_rule(rule_text))

    findings = drift.find_drift(instance_path, trigger_verbs)

    assert len(findings) == 1, findings
    assert "obsolete_verb" in findings[0]
    assert "stale rule text" in findings[0]


def test_both_directions_can_fire_together(tmp_path: pathlib.Path) -> None:
    trigger_verbs = frozenset({"compile", "split"})
    rule_text = "A regex .compile() or a retired .obsolete_verb() call is graded."
    instance_path = _write_ssot(tmp_path, _instance_with_rule(rule_text))

    findings = drift.find_drift(instance_path, trigger_verbs)

    assert len(findings) == 2, findings
    assert any("split" in f and "not mentioned" in f for f in findings)
    assert any("obsolete_verb" in f and "stale rule text" in f for f in findings)


# ---------------------------------------------------------------------------
# (d) missing gate id / missing rule field / malformed ssot.json -> each a
# fail-closed finding, never a crash.
# ---------------------------------------------------------------------------


def test_missing_ssot_file_is_fail_closed(tmp_path: pathlib.Path) -> None:
    missing_path = tmp_path / "does-not-exist" / "ssot.json"
    findings = drift.find_drift(missing_path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "cannot be read" in findings[0]


def test_non_utf8_ssot_is_fail_closed(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "ssot.json"
    path.write_bytes(b"\xff\xfe not utf-8")
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "not valid UTF-8" in findings[0]


def test_malformed_json_syntax_is_fail_closed(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "ssot.json"
    path.write_text("{not json", encoding="utf-8")
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "not valid JSON" in findings[0]


@pytest.mark.parametrize("bad_json", ["[]", '"a string"', "1", "null", "true"])
def test_non_object_top_level_json_is_fail_closed(tmp_path: pathlib.Path, bad_json: str) -> None:
    path = _write_ssot(tmp_path, json.loads(bad_json))
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "not an object" in findings[0]


def test_gates_not_a_list_is_fail_closed(tmp_path: pathlib.Path) -> None:
    path = _write_ssot(tmp_path, {"gates": "not-a-list"})
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "not an array" in findings[0]


def test_missing_gates_key_is_fail_closed(tmp_path: pathlib.Path) -> None:
    path = _write_ssot(tmp_path, {})
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "not an array" in findings[0]


def test_no_matching_gate_id_is_fail_closed(tmp_path: pathlib.Path) -> None:
    path = _write_ssot(tmp_path, {"gates": [{"id": "some-other-gate", "rule": "unrelated"}]})
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "no gates[] entry with id" in findings[0]
    assert _GATE_ID in findings[0]


def test_gates_entry_missing_id_is_treated_as_no_match(tmp_path: pathlib.Path) -> None:
    # A gates[] entry with no "id" at all must not crash entry.get("id")
    # comparison, and must not be mistaken for the target gate.
    path = _write_ssot(tmp_path, {"gates": [{"rule": "unrelated"}]})
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "no gates[] entry with id" in findings[0]


def test_non_dict_gates_entry_does_not_crash(tmp_path: pathlib.Path) -> None:
    # A schema-valid-*shaped* gates[] array can still carry a non-dict entry
    # -- mirrors gitapex_scan_ssot_schema.py's own defensive guard for the
    # identical shape.
    path = _write_ssot(tmp_path, {"gates": [1, 2, {"id": _GATE_ID, "rule": "a .compile() call"}]})
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert findings == []


def test_missing_rule_field_is_fail_closed(tmp_path: pathlib.Path) -> None:
    path = _write_ssot(tmp_path, {"gates": [{"id": _GATE_ID}]})
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "missing or non-string 'rule'" in findings[0]


def test_non_string_rule_field_is_fail_closed(tmp_path: pathlib.Path) -> None:
    path = _write_ssot(tmp_path, {"gates": [{"id": _GATE_ID, "rule": 12345}]})
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "missing or non-string 'rule'" in findings[0]


def test_null_rule_field_is_fail_closed(tmp_path: pathlib.Path) -> None:
    path = _write_ssot(tmp_path, {"gates": [{"id": _GATE_ID, "rule": None}]})
    findings = drift.find_drift(path, frozenset({"compile"}))
    assert len(findings) == 1
    assert "missing or non-string 'rule'" in findings[0]


# ---------------------------------------------------------------------------
# Extraction convention (design resolution 3): `verb()`-shaped, empty-parens
# tokens only.
# ---------------------------------------------------------------------------


def test_rule_verbs_extracts_only_empty_parens_tokens() -> None:
    text = "call .foo() then .bar(x) then baz then Qux() and _private()."
    assert drift._rule_verbs(text) == frozenset({"foo", "Qux", "_private"})


def test_rule_verbs_returns_empty_set_for_no_matches() -> None:
    assert drift._rule_verbs("no verb-shaped tokens in this sentence at all") == frozenset()


# ---------------------------------------------------------------------------
# Adversarial self-check (this task's own defeat-test obligation): a
# rewording that keeps the same verbs but reorders/rephrases the surrounding
# prose must still pass clean -- the drift check is token-presence, not
# sentence-shape, so paraphrasing the English around the verbs is not itself
# drift.
# ---------------------------------------------------------------------------


def test_reworded_prose_with_the_same_verb_set_is_still_clean(tmp_path: pathlib.Path) -> None:
    trigger_verbs = frozenset({"compile", "match", "split"})
    # Same three verbs as the fixture below, in a totally different sentence
    # order/phrasing/structure -- proves this checker is not accidentally
    # sensitive to prose shape, only to which verb() tokens appear.
    reworded_rule_text = (
        "Grades a call, wherever a .split() reaches untrusted text, or "
        "whenever an already-compiled pattern's own .match() runs -- built "
        "originally via re's own .compile(), among other things this "
        "sentence could say in any order without changing what verbs it "
        "names."
    )
    instance_path = _write_ssot(tmp_path, _instance_with_rule(reworded_rule_text))

    findings = drift.find_drift(instance_path, trigger_verbs)

    assert findings == [], findings


# ---------------------------------------------------------------------------
# (e) main(): exit code 0 clean, 1 on drift.
# ---------------------------------------------------------------------------


def test_main_prints_no_drift_and_returns_zero_when_clean(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: [])
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert f"No {_GATE_ID} rule-text drift found." in out


def test_main_prints_findings_and_returns_one_on_drift(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drift, "find_drift", lambda: ["gate 'detection-logic-property-coverage': example finding"])
    rc = drift.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert f"{_GATE_ID} rule-text drift found:" in out
    assert "example finding" in out
