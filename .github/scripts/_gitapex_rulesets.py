#!/usr/bin/env python3
"""Shared repository-ruleset source-of-truth helpers for `.github/scripts/*.py`.

Issue #439: `main` carried no branch protection of any kind, so every gate in
this repository was detection-only -- a red check turned a pull request red
and blocked nothing at the merge boundary. The fix is a GitHub Repository
Ruleset, and this repository's own conventions say the ruleset's definition
must live in git (`.github/rulesets/main.json`) rather than only in the
Settings UI, where nothing can review or diff it.

Three scripts need the same four operations against that source of truth --
read it, list what is live, project both onto a comparable shape, and render
the difference -- so they live here rather than being copied three times:

* `gitapex_apply_rulesets.py` (plan/apply, human-dispatched)
* `gitapex_scan_ruleset_drift.py` `--scope required-checks` (pull-request-time
  lag gate)
* `gitapex_scan_ruleset_drift.py` `--scope full` (scheduled drift scan)

Follows the same `_gitapex_*` private-helper convention as
`_gitapex_github_http.py` and `_gitapex_schema_validation.py`: stdlib only, a
dedicated `tests/test_gitapex_rulesets.py`, and no `.github/scripts/*.py` gate
script importing any *other* gate script directly (only these underscore-
prefixed shared modules).

**Why the projection exists.** GitHub's ruleset API returns more than the
committed JSON carries -- `id`, `source`, `source_type`, `created_at`,
`updated_at`, `_links`, and a `node_id` -- none of which a source-of-truth
file can or should pin. Comparing raw bodies would report permanent drift on
fields no human authored. `canonical_projection` narrows both sides to the six
keys the API's own POST/PUT request body accepts, which is exactly the set a
committed definition is authoritative for.

**Why the list endpoint is not enough.** `GET /repos/{owner}/{repo}/rulesets`
returns ruleset *summaries*: `id`, `name`, `target`, `enforcement`, `source`
-- and no `rules`, `conditions`, or `bypass_actors`. Verified directly against
the live API this session rather than assumed from the field names. Any real
comparison therefore needs a second `GET .../rulesets/{id}` per match, which
is why `resolve_live_ruleset` takes a fetcher rather than a pre-fetched list.
"""

from __future__ import annotations

import difflib
import json
import pathlib
from collections.abc import Callable
from typing import Any

API_ROOT = "https://api.github.com"

#: The exact key set GitHub's own ruleset POST/PUT request body accepts. Both
#: sides of every comparison in this repository are narrowed to these keys --
#: see the module docstring for why the API's extra response fields must not
#: participate.
PROJECTION_KEYS = (
    "name",
    "target",
    "enforcement",
    "conditions",
    "bypass_actors",
    "rules",
)

#: Fetcher signature shared by every caller: takes a full URL, returns the
#: parsed JSON document. Injected rather than imported so tests can drive the
#: whole comparison with no network and no monkeypatching of urllib.
JsonFetcher = Callable[[str], Any]


class RulesetError(RuntimeError):
    """Raised when a ruleset source-of-truth file or API response is unusable."""


def load_sot(path: pathlib.Path) -> dict[str, Any]:
    """Read and parse one committed ruleset definition.

    Raises `RulesetError` -- never returns a partial or empty default -- on a
    missing file, undecodable bytes, malformed JSON, or a top-level document
    that is not an object. A source of truth that cannot be read is a hard
    stop for every caller here: the apply script would otherwise POST an empty
    body, and both drift scopes would report a clean comparison against
    nothing at all.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        # UnicodeDecodeError is not an OSError subclass, so it needs its own
        # arm: without it, a source-of-truth file saved in a non-UTF-8 encoding
        # escapes every caller's `except RulesetError` as a raw traceback
        # instead of the documented clean-error path.
        raise RulesetError(f"cannot read ruleset source of truth {path}: {error}") from error
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RulesetError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise RulesetError(f"{path} must contain a JSON object, found {type(document).__name__}")
    name = document.get("name")
    if not isinstance(name, str) or not name:
        raise RulesetError(f"{path} has no usable top-level 'name' -- it is the only key that matches a live ruleset")
    return document


#: Page size and page ceiling for the rulesets list endpoint. Paginating at all
#: matters more than the numbers: an unpaginated fetch silently sees only the
#: first page, and a `main-protection` ruleset sitting on page two reads as
#: absent -- which makes the apply script plan a POST and create a *duplicate*,
#: and makes both drift scopes report "not applied yet" (exit 2, green) while
#: GitHub is in fact enforcing something. Every other list-endpoint caller in
#: `.github/scripts` already paginates; this one did not.
_PAGE_SIZE = 100
_MAX_PAGES = 20


def list_live_rulesets(repo: str, fetch: JsonFetcher) -> list[dict[str, Any]]:
    """Fetch every live ruleset summary, following pagination to the end.

    A non-list body is treated as an error rather than coerced: the endpoint
    is documented to return an array, so anything else means the caller is
    talking to something other than the endpoint it thinks it is.

    Stops at `_MAX_PAGES` and raises rather than silently truncating -- a
    truncated list is exactly the "looks absent, actually present" failure this
    pagination exists to prevent, so hitting the ceiling must be loud.
    """
    collected: list[dict[str, Any]] = []
    for page in range(1, _MAX_PAGES + 1):
        url = f"{API_ROOT}/repos/{repo}/rulesets?per_page={_PAGE_SIZE}&page={page}"
        body = fetch(url)
        if not isinstance(body, list):
            raise RulesetError(f"GET {url} returned {type(body).__name__}, expected a JSON array")
        collected.extend(item for item in body if isinstance(item, dict))
        if len(body) < _PAGE_SIZE:
            return collected
    raise RulesetError(
        f"/repos/{repo}/rulesets still returned a full page after {_MAX_PAGES} pages; "
        "refusing to compare against a possibly truncated list"
    )


def match_by_name(live: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    """Every live ruleset whose `name` equals the source of truth's `name`.

    `name` is the only stable join key between a committed file and a live
    ruleset -- `id` is assigned by GitHub at creation time and deliberately
    absent from the committed JSON, so nothing else can match the two.
    """
    return [item for item in live if item.get("name") == name]


def resolve_live_ruleset(repo: str, name: str, fetch: JsonFetcher) -> dict[str, Any] | None:
    """Return the full live ruleset matching `name`, or `None` if absent.

    Raises `RulesetError` on more than one match. Two rulesets sharing a name
    is a state no caller here can resolve safely: the apply script would have
    to guess which id to PUT onto (silently overwriting the wrong one), and
    both drift scopes would have to guess which one the committed file is
    supposed to describe. Refusing is the only honest outcome.
    """
    matches = match_by_name(list_live_rulesets(repo, fetch), name)
    if not matches:
        return None
    if len(matches) > 1:
        ids = ", ".join(str(item.get("id")) for item in matches)
        raise RulesetError(f"{len(matches)} live rulesets are named {name!r} (ids: {ids}); refusing to guess which one")
    ruleset_id = matches[0].get("id")
    detail = fetch(f"{API_ROOT}/repos/{repo}/rulesets/{ruleset_id}")
    if not isinstance(detail, dict):
        raise RulesetError(
            f"GET /repos/{repo}/rulesets/{ruleset_id} returned {type(detail).__name__}, expected an object"
        )
    return detail


def canonical_projection(ruleset: dict[str, Any]) -> dict[str, Any]:
    """Narrow a ruleset (live or committed) to the comparable key set.

    `rules` is additionally sorted by `type`. GitHub's REST documentation
    publishes no ordering guarantee for that array, and nothing requires the
    stored order to match the order it was sent in -- so comparing it
    positionally would make a pure re-ordering read as drift, turning the daily
    scan permanently red for a live state that is in fact correct. Sorting by
    `type` is safe because a ruleset cannot carry two rules of the same type.
    """
    projected = {key: ruleset.get(key) for key in PROJECTION_KEYS}
    rules = projected.get("rules")
    if isinstance(rules, list):
        projected["rules"] = sorted(
            rules,
            key=lambda rule: str(rule.get("type")) if isinstance(rule, dict) else str(rule),
        )
    return projected


def find_subset_mismatches(expected: Any, actual: Any, path: str = "") -> list[str]:
    """Where `actual` fails to carry what `expected` specifies, by dotted path.

    Subset, not equality, and the distinction is load-bearing for the *apply*
    path. GitHub's ruleset response echoes back fields the committed file never
    set -- `dismissal_restriction`, `required_reviewers`,
    `do_not_enforce_on_create`, a per-check `integration_id` -- and stamps
    defaults onto rule parameters. Under equality every one of those reads as a
    mismatch, so the very first successful apply would report failure and the
    operator would have to hand-mirror GitHub's own defaults back into git to
    get a green run.

    What the source of truth actually asserts is "these settings must hold", not
    "the stored object must contain nothing else". This function checks exactly
    that: every scalar the committed file specifies is present and equal, every
    list matches element-wise after the caller's own normalisation, and anything
    GitHub added on its own is ignored.

    Full equality still has a place -- the scheduled drift scan uses
    `render_projection_diff` so a rule *added* in the Settings UI is visible --
    but a report a human reads can afford noise where a gate on a completed
    write cannot.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path or '<root>'}: expected an object, found {type(actual).__name__}"]
        mismatches: list[str] = []
        for key, value in expected.items():
            child = f"{path}.{key}" if path else key
            if key not in actual:
                mismatches.append(f"{child}: missing from what GitHub stored")
            else:
                mismatches.extend(find_subset_mismatches(value, actual[key], child))
        return mismatches
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path or '<root>'}: expected a list, found {type(actual).__name__}"]
        if len(expected) != len(actual):
            return [f"{path or '<root>'}: has {len(actual)} entr(ies), the source of truth specifies {len(expected)}"]
        return [
            mismatch
            for index, (want, got) in enumerate(zip(expected, actual, strict=True))
            for mismatch in find_subset_mismatches(want, got, f"{path}[{index}]")
        ]
    if expected != actual:
        return [f"{path or '<root>'}: is {actual!r}, the source of truth specifies {expected!r}"]
    return []


def canonical_json_lines(document: Any) -> list[str]:
    """Render a document as stable, sorted, line-per-entry JSON text.

    `sort_keys=True` so a live body whose keys arrive in a different order
    than the committed file's does not read as a difference; the trailing
    newline join keeps the output usable as `difflib` input.
    """
    text = json.dumps(document, indent=2, sort_keys=True)
    return [f"{line}\n" for line in text.splitlines()]


def render_projection_diff(live: dict[str, Any], sot: dict[str, Any]) -> str:
    """Unified diff of live-vs-committed, over the projected key set only.

    Returns the empty string when the two projections are identical, so every
    caller can use the return value itself as the drift signal rather than
    re-comparing.
    """
    return "".join(
        difflib.unified_diff(
            canonical_json_lines(canonical_projection(live)),
            canonical_json_lines(canonical_projection(sot)),
            fromfile="live",
            tofile="sot",
        )
    )


def required_check_contexts(ruleset: dict[str, Any]) -> list[str]:
    """Every status-check context the ruleset requires, sorted and de-duplicated.

    Tolerates a ruleset with no `required_status_checks` rule at all (returns
    an empty list) because that is a real, expressible state on both sides:
    a live ruleset applied before the checks rule was added, and a committed
    file for a ruleset that deliberately requires none. The caller decides
    whether empty is a problem; this function only reports what is there.
    """
    contexts: set[str] = set()
    for rule in ruleset.get("rules") or []:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        parameters = rule.get("parameters")
        if not isinstance(parameters, dict):
            continue
        for entry in parameters.get("required_status_checks") or []:
            if isinstance(entry, dict) and isinstance(entry.get("context"), str):
                contexts.add(entry["context"])
    return sorted(contexts)
