"""Tests for the shared ruleset source-of-truth helpers
(.github/scripts/_gitapex_rulesets.py).

Refs #439. Every fetch here is a plain dict-keyed fake rather than a mocked
urllib: the module deliberately takes a `JsonFetcher` callable so the
list-then-detail sequence, the name-collision refusal, and the projection can
all be driven with no network and no credential.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import _gitapex_rulesets
import pytest

SOT = {
    "name": "main-protection",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "bypass_actors": [],
    "rules": [
        {"type": "deletion"},
        {
            "type": "required_status_checks",
            "parameters": {"required_status_checks": [{"context": "pytest"}, {"context": "ruff"}]},
        },
    ],
}


def make_fetcher(list_body: Any, detail_body: Any = None) -> Any:
    """Fetcher that answers the list endpoint and the per-id detail endpoint."""

    def fetch(url: str) -> Any:
        return detail_body if "/rulesets/" in url else list_body

    return fetch


def write_sot(tmp_path: pathlib.Path, document: Any) -> pathlib.Path:
    path = tmp_path / "main.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_load_sot_reads_a_committed_definition(tmp_path: pathlib.Path) -> None:
    assert _gitapex_rulesets.load_sot(write_sot(tmp_path, SOT)) == SOT


def test_load_sot_rejects_a_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(_gitapex_rulesets.RulesetError, match="cannot read"):
        _gitapex_rulesets.load_sot(tmp_path / "absent.json")


def test_load_sot_rejects_a_non_utf8_file(tmp_path: pathlib.Path) -> None:
    # UnicodeDecodeError is not an OSError subclass; without its own handler it
    # would escape every caller's `except RulesetError` as a raw traceback.
    path = tmp_path / "main.json"
    path.write_bytes(b'{"name": "\xff\xfe"}')
    with pytest.raises(_gitapex_rulesets.RulesetError, match="cannot read"):
        _gitapex_rulesets.load_sot(path)


def test_load_sot_rejects_malformed_json(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "main.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(_gitapex_rulesets.RulesetError, match="not valid JSON"):
        _gitapex_rulesets.load_sot(path)


def test_load_sot_rejects_a_non_object_document(tmp_path: pathlib.Path) -> None:
    with pytest.raises(_gitapex_rulesets.RulesetError, match="must contain a JSON object"):
        _gitapex_rulesets.load_sot(write_sot(tmp_path, [SOT]))


def test_load_sot_rejects_a_definition_with_no_name(tmp_path: pathlib.Path) -> None:
    # `name` is the only join key to a live ruleset, so a file without one
    # cannot be matched, planned, or diffed -- failing here beats every
    # downstream caller failing in its own way.
    with pytest.raises(_gitapex_rulesets.RulesetError, match="no usable top-level 'name'"):
        _gitapex_rulesets.load_sot(write_sot(tmp_path, {"target": "branch"}))


def test_list_live_rulesets_rejects_a_non_array_body() -> None:
    with pytest.raises(_gitapex_rulesets.RulesetError, match="expected a JSON array"):
        _gitapex_rulesets.list_live_rulesets("o/r", make_fetcher({"message": "Not Found"}))


def test_list_live_rulesets_drops_non_object_entries() -> None:
    assert _gitapex_rulesets.list_live_rulesets("o/r", make_fetcher([{"id": 1}, "junk"])) == [{"id": 1}]


def test_resolve_live_ruleset_returns_none_when_no_name_matches() -> None:
    fetch = make_fetcher([{"id": 1, "name": "something-else"}])
    assert _gitapex_rulesets.resolve_live_ruleset("o/r", "main-protection", fetch) is None


def test_resolve_live_ruleset_fetches_the_detail_body_for_a_single_match() -> None:
    # The list endpoint returns summaries with no `rules`; only the per-id
    # detail body can be compared against a committed definition.
    detail = dict(SOT, id=7)
    fetch = make_fetcher([{"id": 7, "name": "main-protection"}], detail)
    assert _gitapex_rulesets.resolve_live_ruleset("o/r", "main-protection", fetch) == detail


def test_resolve_live_ruleset_refuses_to_guess_between_duplicate_names() -> None:
    fetch = make_fetcher([{"id": 7, "name": "main-protection"}, {"id": 8, "name": "main-protection"}])
    with pytest.raises(_gitapex_rulesets.RulesetError, match="refusing to guess"):
        _gitapex_rulesets.resolve_live_ruleset("o/r", "main-protection", fetch)


def test_resolve_live_ruleset_rejects_a_non_object_detail_body() -> None:
    fetch = make_fetcher([{"id": 7, "name": "main-protection"}], ["unexpected"])
    with pytest.raises(_gitapex_rulesets.RulesetError, match="expected an object"):
        _gitapex_rulesets.resolve_live_ruleset("o/r", "main-protection", fetch)


def test_canonical_projection_drops_api_only_fields() -> None:
    live = dict(SOT, id=7, node_id="R_x", created_at="2026-08-09", _links={})
    assert _gitapex_rulesets.canonical_projection(live) == _gitapex_rulesets.canonical_projection(SOT)


def test_render_projection_diff_is_empty_when_only_api_only_fields_differ() -> None:
    live = dict(SOT, id=7, updated_at="2026-08-09")
    assert _gitapex_rulesets.render_projection_diff(live, SOT) == ""


def test_render_projection_diff_reports_a_real_rule_difference() -> None:
    live = dict(SOT, enforcement="disabled")
    diff = _gitapex_rulesets.render_projection_diff(live, SOT)
    assert "-" in diff
    assert "disabled" in diff


def test_render_projection_diff_ignores_key_ordering() -> None:
    live = {key: SOT[key] for key in reversed(list(SOT))}
    assert _gitapex_rulesets.render_projection_diff(live, SOT) == ""


def test_required_check_contexts_is_sorted_and_deduplicated() -> None:
    ruleset = {
        "rules": [
            {
                "type": "required_status_checks",
                "parameters": {"required_status_checks": [{"context": "ruff"}, {"context": "pytest"}]},
            },
            {
                "type": "required_status_checks",
                "parameters": {"required_status_checks": [{"context": "ruff"}]},
            },
        ]
    }
    assert _gitapex_rulesets.required_check_contexts(ruleset) == ["pytest", "ruff"]


@pytest.mark.parametrize(
    "ruleset",
    [
        {},
        {"rules": None},
        {"rules": [{"type": "deletion"}]},
        {"rules": ["not a dict"]},
        {"rules": [{"type": "required_status_checks", "parameters": None}]},
        {"rules": [{"type": "required_status_checks", "parameters": {"required_status_checks": [{"ctx": "x"}]}}]},
    ],
)
def test_required_check_contexts_tolerates_every_shape_with_no_contexts(ruleset: dict[str, Any]) -> None:
    # Both an unapplied-yet ruleset and a deliberately check-free one are real,
    # expressible states; this function reports what is there and lets the
    # caller decide whether empty is a problem.
    assert _gitapex_rulesets.required_check_contexts(ruleset) == []
