#!/usr/bin/env python3
"""Guard the self-referential invariant between `detection-logic-property-
coverage`'s own `.gitapex/ssot.json` `rule` text and the trigger-verb
constants its gate script (`gitapex_gate_detection_logic_property_coverage.py`)
actually enforces.

Issue #1921 (refs #1918 repair 6). The motivating defect: category (c) of
`detection-logic-property-coverage` was widened, by commit history, to also
grade `.split()`/`.rsplit()`/`.partition()` (issue #1532, consolidated into
#1572) -- a real, shipped trigger-verb change to
`_STRING_SPLIT_RECEIVER_AGNOSTIC_ATTRS` in the gate script itself -- but the
human-readable verb list spelled out in that gate's own `.gitapex/ssot.json`
`rule` field was not updated in the same change. The registry's own prose
silently fell out of sync with the code it describes, and nothing caught it;
the gap was closed by hand, after the fact, in commit `1d4d67a9`. This
scanner is the drift gate issue #1921 adds so that class of slip fails a PR
instead of waiting for a human to notice a stale sentence.

What it checks
---------------
Reads `.gitapex/ssot.json`, locates the `gates[]` entry whose `"id"` is
`"detection-logic-property-coverage"`, and reads its `"rule"` string. Every
`verb()`-shaped token in that string -- matched by
``\\b[a-zA-Z_][a-zA-Z0-9_]*\\(\\)``, e.g. ``compile()``, ``split()``,
``frozenset()`` -- is extracted and compared **bidirectionally** against
`gitapex_gate_detection_logic_property_coverage.ALL_TRIGGER_VERBS`, the gate
script's own public union of every trigger-verb constant it actually grades:

- a verb present in `ALL_TRIGGER_VERBS` but never mentioned as `verb()` in
  the rule text is drift (the exact defect class above: the code trigger
  set grew and the registry prose did not follow);
- a `verb()` token present in the rule text but absent from
  `ALL_TRIGGER_VERBS` is drift too (the mirror-image case: stale prose
  naming a verb the gate no longer actually grades -- e.g. a verb removed
  from the gate script without also being removed from the registry
  sentence describing it).

Piloted on exactly this one gate, matching this repository's own established
narrow-pilot convention for `*_drift.py`/`*_scan_*.py` scan scripts
(`gitapex_scan_ssot_schema.py`, `gitapex_scan_independent_review_heading_
drift.py`, `gitapex_scan_retrospective_gate_drift.py` each target one fixed,
named thing, not a generic sweep across every gate's own rule text).
Generalizing this bidirectional-verb-drift check to every gate that spells
triggers this way is a disclosed future widening, not attempted here.

A missing `.gitapex/ssot.json`, JSON that fails to parse, a registry with no
`"id": "detection-logic-property-coverage"` entry in `gates[]`, or that
entry missing a `"rule"` field (or carrying a non-string one) is each
reported as its own drift finding -- fail closed, never a crash and never a
silent pass. This mirrors `gitapex_scan_independent_review_heading_drift.py`'s
own "a missing target is drift, not a skip" convention, applied here to the
registry file itself rather than to a target it names.

Known limit, disclosed rather than found later. This is a **token-presence
heuristic on the rule text's current `verb()` prose convention**, not a
semantic parse of the rule's English. It works today because every trigger
verb in the live rule text happens to be spelled `<name>()` (empty
parentheses, no arguments shown) -- confirmed by direct inspection of the
live file, not assumed. A future rewrite of the rule text that stops using
that convention (e.g. spelling a verb with example arguments shown, or in a
different grammatical form entirely) would silently stop being checked by
this scanner and would need this checker's own extraction regex updated
alongside it; this scanner cannot detect that its own extraction has gone
stale, only that the tokens it did extract disagree with
`ALL_TRIGGER_VERBS`. A verb-shaped word appearing in the rule text's
surrounding prose for a reason unrelated to being a real trigger (a
false-positive risk in principle) would also read as drift by this
heuristic; empirically, against the current live rule text, no such
coincidental `word()`-shaped token exists that is not one of the gate's own
16 real trigger verbs -- see this module's own test file for the check that
pins that count and would fail loudly the day it stops being true.

Run standalone (exit 1 on drift) or via the pytest gate in
`tests/test_gitapex_scan_detection_logic_rule_drift.py`.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gitapex_gate_detection_logic_property_coverage as gate  # sys.path bootstrap above must run first

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"

_GATE_ID = "detection-logic-property-coverage"

# `verb()` -- empty parentheses, matching this gate's own rule-text
# convention (see module docstring's "Known limit" section for why this is
# a heuristic on that convention, not a semantic parse).
_VERB_TOKEN_RE = re.compile(r"\b[a-zA-Z_][a-zA-Z0-9_]*\(\)")


def _rule_verbs(rule_text: str) -> frozenset[str]:
    """Every `verb()`-shaped token in `rule_text`, with the trailing `()`
    stripped -- e.g. `"a .compile() call"` -> `{"compile"}`."""
    return frozenset(token[:-2] for token in _VERB_TOKEN_RE.findall(rule_text))


def _find_gate_rule(instance: object) -> tuple[str | None, list[str]]:
    """Return `(rule_text, findings)` for the `detection-logic-property-
    coverage` entry inside an already-JSON-parsed `.gitapex/ssot.json`
    instance. `rule_text` is `None` whenever a finding was reported --
    every failure mode below (non-dict instance, non-list `gates`, no
    matching id, missing/non-string `rule`) is fail-closed: reported as
    drift, never a crash, and never silently treated as "no drift"."""
    if not isinstance(instance, dict):
        return None, [f"{SSOT_PATH}: top-level JSON is not an object, cannot locate gate {_GATE_ID!r}"]
    gates = instance.get("gates")
    if not isinstance(gates, list):
        return None, [f"{SSOT_PATH}: 'gates' is missing or not an array, cannot locate gate {_GATE_ID!r}"]
    for entry in gates:
        if isinstance(entry, dict) and entry.get("id") == _GATE_ID:
            rule = entry.get("rule")
            if not isinstance(rule, str):
                return None, [f"{SSOT_PATH}: gate {_GATE_ID!r} has a missing or non-string 'rule' field"]
            return rule, []
    return None, [f"{SSOT_PATH}: no gates[] entry with id {_GATE_ID!r} found"]


def find_drift(
    ssot_path: pathlib.Path = SSOT_PATH,
    trigger_verbs: frozenset[str] = gate.ALL_TRIGGER_VERBS,
) -> list[str]:
    """Return every drift finding between `ssot_path`'s own
    `detection-logic-property-coverage` `rule` text and `trigger_verbs`.
    Empty list means no drift.

    Both parameters default to the real repository values (mirroring
    `gitapex_scan_ssot_schema.find_drift`'s own explicit-path-with-real-
    default shape) but are injectable so tests can exercise a synthetic
    rule text or trigger-verb set without touching the real registry or
    the real gate script -- including reproducing the original defect this
    gate exists to catch (a verb present in `trigger_verbs` but absent from
    `ssot_path`'s rule text)."""
    try:
        text = ssot_path.read_text(encoding="utf-8")
    except OSError as error:
        return [f"{ssot_path}: cannot be read: {error}"]
    except UnicodeDecodeError as error:
        return [f"{ssot_path}: is not valid UTF-8: {error}"]
    try:
        instance = json.loads(text)
    except json.JSONDecodeError as error:
        return [f"{ssot_path}: is not valid JSON: {error}"]

    rule_text, findings = _find_gate_rule(instance)
    if rule_text is None:
        return findings

    rule_verbs = _rule_verbs(rule_text)
    missing_from_rule_text = sorted(trigger_verbs - rule_verbs)
    stale_in_rule_text = sorted(rule_verbs - trigger_verbs)

    for verb in missing_from_rule_text:
        findings.append(
            f"gate {_GATE_ID!r}: trigger verb {verb!r} is graded by "
            f"gitapex_gate_detection_logic_property_coverage.ALL_TRIGGER_VERBS but not mentioned as "
            f"{verb}() in .gitapex/ssot.json's own rule text for this gate"
        )
    for verb in stale_in_rule_text:
        findings.append(
            f"gate {_GATE_ID!r}: rule text mentions {verb}() but "
            f"gitapex_gate_detection_logic_property_coverage.ALL_TRIGGER_VERBS no longer grades {verb!r} "
            "-- stale rule text"
        )
    return findings


def main() -> int:
    findings = find_drift()
    if findings:
        print(f"{_GATE_ID} rule-text drift found:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print(f"No {_GATE_ID} rule-text drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
