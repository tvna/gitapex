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
import urllib.parse
from typing import Any

import _gitapex_rulesets
import pytest

SOT: dict[str, Any] = {
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
    with pytest.raises(_gitapex_rulesets.RulesetError, match="cannot be read"):
        _gitapex_rulesets.load_sot(tmp_path / "absent.json")


def test_load_sot_rejects_a_non_utf8_file(tmp_path: pathlib.Path) -> None:
    # UnicodeDecodeError is not an OSError subclass; without its own handler it
    # would escape every caller's `except RulesetError` as a raw traceback.
    path = tmp_path / "main.json"
    path.write_bytes(b'{"name": "\xff\xfe"}')
    with pytest.raises(_gitapex_rulesets.RulesetError, match="is not valid UTF-8"):
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


def paging_fetcher(pages: list[Any]) -> Any:
    """Fetcher that serves `pages[n-1]` for `?page=n` on the list endpoint.

    Requests past the end of `pages` get an empty page, which is what the real
    endpoint returns; a page-parameter-blind fake would let an unpaginated
    implementation pass by handing it the same body forever.
    """

    def fetch(url: str) -> Any:
        # Parsed as a query string rather than sliced off the end: the URL grew
        # an `includes_parents` parameter after `page`, and a positional parse
        # turned that into a ValueError inside the fake rather than a finding.
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        page = int(query["page"][0])
        return pages[page - 1] if page <= len(pages) else []

    return fetch


def test_list_live_rulesets_follows_pagination_past_the_first_page() -> None:
    # The failure this guards: `main-protection` sitting on page two reads as
    # absent, so apply plans a POST and creates a duplicate.
    first = [{"id": index, "name": f"filler-{index}"} for index in range(_gitapex_rulesets._PAGE_SIZE)]
    live = _gitapex_rulesets.list_live_rulesets(
        "o/r", paging_fetcher([first, [{"id": 999, "name": "main-protection"}]])
    )
    assert len(live) == _gitapex_rulesets._PAGE_SIZE + 1
    assert _gitapex_rulesets.match_by_name(live, "main-protection") == [{"id": 999, "name": "main-protection"}]


def test_list_live_rulesets_stops_on_a_short_page() -> None:
    fetch = paging_fetcher([[{"id": 1, "name": "main-protection"}]])
    assert _gitapex_rulesets.list_live_rulesets("o/r", fetch) == [{"id": 1, "name": "main-protection"}]


def test_list_live_rulesets_refuses_a_possibly_truncated_list() -> None:
    # Silently truncating would reproduce the exact "looks absent, actually
    # present" state pagination exists to prevent, so the ceiling must raise.
    full = [{"id": index, "name": f"filler-{index}"} for index in range(_gitapex_rulesets._PAGE_SIZE)]
    fetch = paging_fetcher([full] * (_gitapex_rulesets._MAX_PAGES + 1))
    with pytest.raises(_gitapex_rulesets.RulesetError, match="possibly truncated"):
        _gitapex_rulesets.list_live_rulesets("o/r", fetch)


def test_canonical_projection_sorts_rules_by_type() -> None:
    # GitHub publishes no ordering guarantee for `rules`; comparing positionally
    # would make a pure re-ordering read as drift.
    shuffled = {**SOT, "rules": list(reversed(SOT["rules"]))}
    assert _gitapex_rulesets.canonical_projection(shuffled) == _gitapex_rulesets.canonical_projection(SOT)


def test_canonical_projection_tolerates_a_non_list_rules_value() -> None:
    assert _gitapex_rulesets.canonical_projection({"rules": None})["rules"] is None


def test_find_subset_mismatches_ignores_fields_github_added() -> None:
    # The whole reason this is subset rather than equality: the response carries
    # server-stamped defaults the committed file never set.
    actual = {"name": "main-protection", "id": 99, "created_at": "2026-01-01", "_links": {"self": {}}}
    assert _gitapex_rulesets.find_subset_mismatches({"name": "main-protection"}, actual) == []


def test_find_subset_mismatches_reports_a_changed_scalar_by_path() -> None:
    expected = {"rules": [{"parameters": {"required_approving_review_count": 0}}]}
    actual = {"rules": [{"parameters": {"required_approving_review_count": 1}}]}
    assert _gitapex_rulesets.find_subset_mismatches(expected, actual) == [
        "rules[0].parameters.required_approving_review_count: is 1, the source of truth specifies 0"
    ]


def test_find_subset_mismatches_reports_a_key_github_dropped() -> None:
    findings = _gitapex_rulesets.find_subset_mismatches({"enforcement": "active"}, {"name": "x"})
    assert findings == ["enforcement: missing from what GitHub stored"]


def test_find_subset_mismatches_reports_a_dropped_required_check() -> None:
    # A silently shortened list is the dangerous case: the ruleset exists, the
    # apply returned 2xx, and one required check simply is not enforced.
    expected = {"checks": [{"context": "ruff"}, {"context": "pytest"}]}
    findings = _gitapex_rulesets.find_subset_mismatches(expected, {"checks": [{"context": "ruff"}]})
    assert findings == ["checks: has 1 entr(ies), the source of truth specifies 2"]


@pytest.mark.parametrize(
    ("expected", "actual", "fragment"),
    [
        ({"a": {"b": 1}}, {"a": "scalar"}, "expected an object"),
        ({"a": [1]}, {"a": 1}, "expected a list"),
    ],
)
def test_find_subset_mismatches_reports_a_type_change(expected: Any, actual: Any, fragment: str) -> None:
    assert fragment in _gitapex_rulesets.find_subset_mismatches(expected, actual)[0]


def test_list_live_rulesets_excludes_parent_org_rulesets() -> None:
    # GitHub documents `includes_parents` as defaulting to true, so the
    # unqualified call also returns org/enterprise rulesets. A parent sharing
    # the committed name makes the resolver refuse permanently; a parent-only
    # match makes apply plan a PUT onto an id it cannot write.
    seen: list[str] = []

    def fetch(url: str) -> Any:
        seen.append(url)
        return []

    _gitapex_rulesets.list_live_rulesets("o/r", fetch)
    assert "includes_parents=false" in seen[0]


def test_canonical_projection_sorts_required_status_checks() -> None:
    # Sorting only the outer `rules` array left this list compared positionally,
    # which is the same bug one level down.
    def ruleset(contexts: list[str]) -> dict[str, Any]:
        return {
            "rules": [
                {
                    "type": "required_status_checks",
                    "parameters": {"required_status_checks": [{"context": c} for c in contexts]},
                }
            ]
        }

    assert _gitapex_rulesets.canonical_projection(
        ruleset(["ruff", "pytest"])
    ) == _gitapex_rulesets.canonical_projection(ruleset(["pytest", "ruff"]))


def test_canonical_projection_sorts_allowed_merge_methods() -> None:
    def ruleset(methods: list[str]) -> dict[str, Any]:
        return {"rules": [{"type": "pull_request", "parameters": {"allowed_merge_methods": methods}}]}

    assert _gitapex_rulesets.canonical_projection(
        ruleset(["merge", "squash"])
    ) == _gitapex_rulesets.canonical_projection(ruleset(["squash", "merge"]))


def test_canonical_projection_does_not_mutate_its_argument() -> None:
    # Both callers pass their own live response and committed document; a
    # comparison helper that rewrote either would make the result depend on
    # which side was projected first.
    original = {"rules": [{"type": "pull_request", "parameters": {"allowed_merge_methods": ["squash", "merge"]}}]}
    snapshot = json.loads(json.dumps(original))
    _gitapex_rulesets.canonical_projection(original)
    assert original == snapshot


def test_canonical_projection_leaves_unlisted_parameter_lists_in_order() -> None:
    # The sort is an allowlist, not a blanket deep sort: a list whose order is
    # meaningful must keep reporting a re-ordering as the difference it is.
    ordered = {"rules": [{"type": "x", "parameters": {"some_ordered_list": ["b", "a"]}}]}
    projected = _gitapex_rulesets.canonical_projection(ordered)
    assert projected["rules"][0]["parameters"]["some_ordered_list"] == ["b", "a"]


def test_unobservable_keys_names_bypass_actors_when_the_api_withheld_it() -> None:
    # GitHub returns bypass_actors only to a caller with write access to the
    # ruleset, and the verify credential is Administration:Read by design.
    live = {key: value for key, value in SOT.items() if key != "bypass_actors"}
    assert _gitapex_rulesets.unobservable_keys(live) == ["bypass_actors"]


def test_unobservable_keys_is_empty_when_the_api_returned_the_field() -> None:
    assert _gitapex_rulesets.unobservable_keys(dict(SOT)) == []


def test_a_withheld_bypass_actors_is_not_reported_as_drift_when_excluded() -> None:
    live = {key: value for key, value in SOT.items() if key != "bypass_actors"}
    ignored = _gitapex_rulesets.unobservable_keys(live)
    assert _gitapex_rulesets.render_projection_diff(live, SOT, ignore_keys=ignored) == ""
    # Without the exclusion it is drift -- this is the regression being pinned,
    # not an incidental detail: the nightly scan was red every night for it.
    assert _gitapex_rulesets.render_projection_diff(live, SOT) != ""


def test_excluding_a_key_does_not_hide_drift_in_the_keys_that_remain() -> None:
    live = {key: value for key, value in SOT.items() if key != "bypass_actors"}
    live["enforcement"] = "disabled"
    diff = _gitapex_rulesets.render_projection_diff(live, SOT, ignore_keys=["bypass_actors"])
    assert "disabled" in diff


def test_an_absent_rules_key_is_still_drift_not_an_unobservable_field() -> None:
    # The unobservable set must stay narrow. A read-scoped token can see
    # `rules`, so its absence means something is genuinely wrong.
    live = {key: value for key, value in SOT.items() if key != "rules"}
    assert _gitapex_rulesets.unobservable_keys(live) == []
    assert _gitapex_rulesets.render_projection_diff(live, SOT) != ""


def test_canonical_projection_tolerates_a_non_object_rule_entry() -> None:
    # A malformed live response can put anything in `rules`; the projection is
    # a comparison helper, not a validator, so it must pass such an entry
    # through for the diff to show rather than raising inside the comparison.
    projected = _gitapex_rulesets.canonical_projection({"rules": ["not a rule", {"type": "deletion"}]})
    assert projected["rules"] == [{"type": "deletion"}, "not a rule"]
