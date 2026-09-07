"""Tests for the network exception-set drift gate
(.github/scripts/gitapex_gate_network_exception_set_drift.py).

Refs #1512 (consolidated into #1572's own umbrella). The motivating case:
`_gitapex_github_http.py`'s `graphql_call` caught only `except
urllib.error.URLError` around its own `opener(request)` call, while its
sibling `request_with_retry` -- the function `graphql_call` was itself
ported from -- already caught `except (OSError, http.client.
IncompleteRead)` around the identical call shape. Found only by issue
#729's own Step 8 adversarial review, and fixed in the same PR. Nothing in
this repository's own gate suite would have caught the drift itself before
this gate: each function is individually well-formed, so the defect is
only visible by comparing the two against each other.

The regression fixture below reconstructs that pre-fix shape (preserving
the defect and the `opener(request)` call structure this gate's rules have
to traverse, dropping unrelated surrounding logic and imports needed only
to parse standalone) -- the same reconstruction convention
`tests/test_gitapex_gate_exception_handler_gaps.py`'s own three regression
fixtures use.

The defeat cases carry as much weight as the happy path: a gate that fired
on two unrelated functions sharing no real call shape would be reverted the
first time someone wrote two ordinary, differently-scoped try/except
blocks in the same file.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess

import gitapex_gate_network_exception_set_drift as gate
import pytest
from conftest import (
    assert_workflow_checkout_pins_head_sha_with_full_history,
    assert_workflow_diff_carries_flags,
    assert_workflow_feeds_merge_base_to,
    assert_workflow_has_no_trigger_path_filter,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

_SCRIPT = ".github/scripts/gitapex_gate_network_exception_set_drift.py"
_REAL_GITHUB_HTTP = ".github/scripts/_gitapex_github_http.py"


# --- helpers --------------------------------------------------------------


def _whole_file_diff(path: str, source: str) -> str:
    """A unified diff in which every line of `source` is an added line."""
    lines = source.split("\n")
    body = "".join("+" + line + "\n" for line in lines)
    return f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + body


def _partial_diff(path: str, source: str, added: list[int]) -> str:
    """A unified diff adding only the 1-based line numbers in `added`."""
    lines = source.split("\n")
    hunks = "".join(f"@@ -{number},0 +{number},1 @@\n+{lines[number - 1]}\n" for number in added)
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n{hunks}"


def _write(root: pathlib.Path, relative: str, source: str) -> pathlib.Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _grade(tmp_path: pathlib.Path, source: str, *, relative: str = ".github/scripts/gate_x.py") -> list[gate.Finding]:
    """Write `source` at `relative`, grade it as wholly added, return violations."""
    _write(tmp_path, relative, source)
    violations, _waived, graded = gate.find_violations(_whole_file_diff(relative, source), tmp_path)
    assert graded == 1, f"{relative} was not graded at all"
    return violations


def _rules(findings: list[gate.Finding]) -> list[str]:
    return [finding.rule for finding in findings]


# --- regression fixture: the real graphql_call/request_with_retry drift ---

# Reconstructed from `_gitapex_github_http.py`'s own pre-fix shape (issue
# #729's Step 8 adversarial review): `graphql_call` caught only
# `except urllib.error.URLError`, missing `http.client.IncompleteRead`
# (not a URLError/OSError subclass) that its sibling `request_with_retry`
# already caught around the identical `opener(request)` call.
_PRE_FIX_GITHUB_HTTP = """
import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any


def request_with_retry(
    method: str,
    url: str,
    token: str,
    opener: Callable[[urllib.request.Request], Any],
    sleeper: Callable[[float], None],
) -> tuple[int, str]:
    request = urllib.request.Request(url, method=method)
    try:
        with opener(request) as response:
            code = int(response.status)
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        code = int(error.code)
        body = error.read().decode("utf-8", errors="replace")
    except (OSError, http.client.IncompleteRead) as error:
        code = 0
        body = str(error)
    return code, body


def graphql_call(
    *,
    query: str,
    variables: dict[str, Any],
    token: str,
    opener: Callable[[urllib.request.Request], Any],
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request("https://api.github.com/graphql", method="POST")
    try:
        with opener(request) as response:
            code = int(response.status)
            body_str = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        code = int(error.code)
        body_str = error.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:
        code = 0
        body_str = str(error)
    try:
        parsed = json.loads(body_str) if body_str else {}
    except json.JSONDecodeError:
        parsed = {}
    return code, parsed if isinstance(parsed, dict) else {}
"""

# The identical fixture, post-fix: graphql_call's own handler tuple is
# realigned to request_with_retry's exact `(OSError, http.client.
# IncompleteRead)` -- the real fix (issue #729's own Step 8 adversarial
# review), not merely adding IncompleteRead alongside the narrower
# URLError: this gate matches handler *names* literally, with no
# subclass/ancestor resolution, so a set naming "URLError" and a set
# naming "OSError" are different sets to it even though URLError is an
# OSError subclass at runtime.
_POST_FIX_GITHUB_HTTP = _PRE_FIX_GITHUB_HTTP.replace(
    "except urllib.error.URLError as error:",
    "except (OSError, http.client.IncompleteRead) as error:",
)


def test_the_reconstructed_pre_fix_shape_is_flagged(tmp_path: pathlib.Path) -> None:
    """The regression proof, half one: reintroducing the real defect --
    `graphql_call` missing `http.client.IncompleteRead` while its sibling
    `request_with_retry` catches it, both wrapping `opener(request)` -- is
    flagged."""
    violations = _grade(tmp_path, _PRE_FIX_GITHUB_HTTP, relative=_REAL_GITHUB_HTTP)
    assert _rules(violations) == [gate._DRIFT_RULE]
    message = violations[0].message
    assert "request_with_retry" in message
    assert "graphql_call" in message
    assert "IncompleteRead" in message


def test_the_reconstructed_post_fix_shape_grades_clean(tmp_path: pathlib.Path) -> None:
    """The regression proof, half two: once both functions catch the
    identical tuple, the drift disappears."""
    assert _grade(tmp_path, _POST_FIX_GITHUB_HTTP, relative=_REAL_GITHUB_HTTP) == []


def test_the_real_already_fixed_file_grades_clean(tmp_path: pathlib.Path) -> None:
    """The real, currently-shipped `_gitapex_github_http.py` -- not a
    reconstruction -- graded as a synthetic diff touching every line,
    confirming `request_with_retry` and `graphql_call` are aligned today."""
    source = (REPO_ROOT / _REAL_GITHUB_HTTP).read_text(encoding="utf-8")
    assert _grade(tmp_path, source, relative=_REAL_GITHUB_HTTP) == []


# --- defeat test: unrelated calls must never false-positive ---------------


def test_unrelated_calls_with_different_exceptions_are_not_flagged(tmp_path: pathlib.Path) -> None:
    """Built to defeat this gate's own detection logic: two functions in one
    module, each wrapping a call in try/except with a *different* exception
    tuple -- but neither call is network-shaped (no `opener(...)` call, no
    `urlopen`/`urllib.request`/`http.client` in the callee's dotted name).
    Must not be flagged: these functions are never even candidates, let
    alone grouped together.
    """
    source = """
def parse_config(loader):
    try:
        data = loader.parse()
    except ValueError:
        data = {}
    return data


def parse_manifest(loader):
    try:
        data = loader.parse()
    except KeyError:
        data = {}
    return data
"""
    assert _grade(tmp_path, source) == []


def test_different_network_call_shapes_are_never_cross_compared(tmp_path: pathlib.Path) -> None:
    """A second defeat case: one function wraps the `opener(request)` shape,
    the other a `urllib.request.urlopen(...)` call -- both are real network
    calls, but different shapes, so this gate's own "only the SAME
    recognizable call shape" rule must not compare them even though their
    exception sets differ."""
    source = """
import urllib.request


def fetch_via_opener(opener, request):
    try:
        return opener(request)
    except OSError:
        return None


def fetch_via_urlopen(url):
    try:
        return urllib.request.urlopen(url)
    except ValueError:
        return None
"""
    assert _grade(tmp_path, source) == []


def test_identical_exception_sets_on_the_same_shape_grade_clean(tmp_path: pathlib.Path) -> None:
    """Two functions wrapping the identical network-call shape with the
    identical exception set must not be flagged -- there is no drift."""
    source = """
def fetch_a(opener, request):
    try:
        return opener(request)
    except OSError:
        return None


def fetch_b(opener, request):
    try:
        return opener(request)
    except OSError:
        return None
"""
    assert _grade(tmp_path, source) == []


def test_a_differing_pair_on_the_urllib_attr_shape_is_flagged(tmp_path: pathlib.Path) -> None:
    """The second recognized signal (an attribute chain containing
    urlopen/urllib.request/http.client), exercised independently of the
    opener-call regression fixture above."""
    source = """
import http.client
import urllib.request


def fetch_one(url):
    try:
        return urllib.request.urlopen(url)
    except urllib.error.URLError:
        return None


def fetch_two(host):
    try:
        return http.client.HTTPSConnection(host).getresponse()
    except (urllib.error.URLError, TimeoutError):
        return None
"""
    violations = _grade(tmp_path, source)
    assert _rules(violations) == [gate._DRIFT_RULE]


# --- nested-try handler accumulation (the fix for this file's own nested- ---
# --- try mishandling: a network call sitting in an INNER try nested inside
# --- an OUTER try must be graded against the UNION of both tries' own
# --- handler names, not just the outer one's -- see `_network_call_handlers`
# --- own docstring and the module docstring's own "Design" section) --------


def test_a_nested_try_wrapping_the_call_is_unioned_with_the_outer_handlers_no_false_positive(
    tmp_path: pathlib.Path,
) -> None:
    """The false-positive half of the nested-try regression: `fetch_a`
    catches `(OSError, ValueError)` in one `except` clause; `fetch_b` catches
    the identical two names, split across an outer `try/except OSError:`
    wrapping an inner `try/except ValueError:` around the same call. Both
    functions effectively catch the same set -- reading only the outer
    `try`'s own handlers (the pre-fix behaviour) would report `fetch_b` as
    catching only `{OSError}`, a spurious drift against `fetch_a`'s
    `{OSError, ValueError}`. Fixed: no finding."""
    source = """
def fetch_a(opener, request):
    try:
        return opener(request)
    except (OSError, ValueError):
        return None


def fetch_b(opener, request):
    try:
        try:
            return opener(request)
        except ValueError:
            return None
    except OSError:
        return None
"""
    assert _grade(tmp_path, source) == []


def test_a_nested_try_wrapping_the_call_reveals_real_drift_no_false_negative(
    tmp_path: pathlib.Path,
) -> None:
    """The false-negative half, and the more serious direction (issue #1512's
    own defect class): `fetch_c` catches only `OSError` around the call, so a
    `ValueError` from it propagates uncaught. `fetch_d` uses the identical
    nested `try/except OSError:` wrapping `try/except ValueError:` shape as
    the previous test, and genuinely swallows both. Reading only the outer
    `try`'s own handlers (the pre-fix behaviour) would record both as
    `{OSError}` and grade this pair clean, missing the real difference in
    what each function actually catches. Fixed: the drift is caught."""
    source = """
def fetch_c(opener, request):
    try:
        return opener(request)
    except OSError:
        return None


def fetch_d(opener, request):
    try:
        try:
            return opener(request)
        except ValueError:
            return None
    except OSError:
        return None
"""
    violations = _grade(tmp_path, source)
    assert _rules(violations) == [gate._DRIFT_RULE]
    message = violations[0].message
    assert "fetch_c" in message
    assert "fetch_d" in message
    assert "['OSError']" in message
    assert "['OSError', 'ValueError']" in message


# --- diff scoping -----------------------------------------------------------


_OPENER_DRIFT_SOURCE = """# top comment, not part of either function
def fetch_a(opener, request):
    try:
        return opener(request)
    except OSError:
        return None


def fetch_b(opener, request):
    try:
        return opener(request)
    except (OSError, ValueError):
        return None
"""


def test_a_pre_existing_drift_untouched_by_the_diff_is_not_reported(tmp_path: pathlib.Path) -> None:
    """Scope is the diff, not the repository: a real drift that neither
    function's own `try` was touched by this diff is not this diff's
    failure."""
    _write(tmp_path, ".github/scripts/gate_x.py", _OPENER_DRIFT_SOURCE)
    diff = _partial_diff(".github/scripts/gate_x.py", _OPENER_DRIFT_SOURCE, [1])
    violations, _waived, graded = gate.find_violations(diff, tmp_path)
    assert graded == 1
    assert violations == []


def test_touching_only_one_functions_try_still_reports_the_pair(tmp_path: pathlib.Path) -> None:
    """Only one of the two functions' own `try` needs to be touched."""
    _write(tmp_path, ".github/scripts/gate_x.py", _OPENER_DRIFT_SOURCE)
    # Line 3 is `try:` inside fetch_a -- part of fetch_a's own try span.
    diff = _partial_diff(".github/scripts/gate_x.py", _OPENER_DRIFT_SOURCE, [3])
    violations, _waived, graded = gate.find_violations(diff, tmp_path)
    assert graded == 1
    assert _rules(violations) == [gate._DRIFT_RULE]


# --- waiver -----------------------------------------------------------------


def test_an_inline_waiver_on_the_anchor_line_suppresses_the_finding(tmp_path: pathlib.Path) -> None:
    """The anchor is the *later* function's own `try:` line (`fetch_b`'s,
    line 10 of `_OPENER_DRIFT_SOURCE`) -- see `findings_for_source`'s own
    `anchor = max(first_start, second_start)`. The waiver has to sit there,
    not on the `except` line, to be honoured."""
    source = _OPENER_DRIFT_SOURCE.replace(
        "def fetch_b(opener, request):\n    try:\n",
        "def fetch_b(opener, request):\n"
        "    try:  # network-exception-set-drift: WAIVED: deliberate, ValueError is local\n",
    )
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    violations, waived, graded = gate.find_violations(_whole_file_diff(".github/scripts/gate_x.py", source), tmp_path)
    assert graded == 1
    assert violations == []
    assert _rules(waived) == [gate._DRIFT_RULE]


def test_a_bare_waiver_marker_with_no_reason_is_not_honoured(tmp_path: pathlib.Path) -> None:
    source = _OPENER_DRIFT_SOURCE.replace(
        "def fetch_b(opener, request):\n    try:\n",
        "def fetch_b(opener, request):\n    try:  # network-exception-set-drift: WAIVED:\n",
    )
    violations = _grade(tmp_path, source)
    assert _rules(violations) == [gate._DRIFT_RULE]


def test_waiver_text_inside_a_string_literal_is_not_honoured(tmp_path: pathlib.Path) -> None:
    source = _OPENER_DRIFT_SOURCE + '\nDOC = "# network-exception-set-drift: WAIVED: not a real comment"\n'
    violations = _grade(tmp_path, source)
    assert _rules(violations) == [gate._DRIFT_RULE]


# --- findings_for_source / find_violations direct unit coverage ------------


def test_findings_for_source_reports_the_drift_pair_directly() -> None:
    """`find_violations`'s own per-file caller, called directly rather than
    only through that wrapper: `_OPENER_DRIFT_SOURCE`'s own fetch_b `try:`
    sits on line 10, so `added={10}` alone is enough to bring the pair into
    scope."""
    violations, waived = gate.findings_for_source(".github/scripts/gate_x.py", _OPENER_DRIFT_SOURCE, {10})
    assert waived == []
    assert [violation.rule for violation in violations] == [gate._DRIFT_RULE]
    assert violations[0].line == 10


def test_findings_for_source_honours_an_inline_waiver_directly() -> None:
    source = _OPENER_DRIFT_SOURCE.replace(
        "def fetch_b(opener, request):\n    try:\n",
        "def fetch_b(opener, request):\n"
        "    try:  # network-exception-set-drift: WAIVED: deliberate, ValueError is local\n",
    )
    violations, waived = gate.findings_for_source(".github/scripts/gate_x.py", source, {10})
    assert violations == []
    assert [finding.rule for finding in waived] == [gate._DRIFT_RULE]


def test_find_violations_skips_a_file_the_diff_touches_outside_the_in_scope_paths(
    tmp_path: pathlib.Path,
) -> None:
    """`in_scope` is unit-tested directly elsewhere; this pins that
    `find_violations` itself actually consults it and skips (never reads or
    grades) a diff-touched path outside the four checker-script directories
    -- covering the `continue` branch `in_scope`'s own call site takes."""
    diff = "diff --git a/src/not_scanned.py b/src/not_scanned.py\n--- /dev/null\n+++ b/src/not_scanned.py\n@@ -0,0 +1,1 @@\n+x = 1\n"
    violations, waived, graded = gate.find_violations(diff, tmp_path)
    assert (violations, waived, graded) == ([], [], 0)


# --- _network_call_shape / _dotted_name unit coverage ------------------------


def _parse_call(expression: str) -> ast.Call:
    """Parse `expression` (a single call expression) in `eval` mode and
    return its top-level `ast.Call` node, typed precisely rather than as
    the general `ast.expr` a statement-mode parse's `Expr.value` carries --
    `ast.parse(..., mode="eval").body` is itself only `ast.expr` too, so the
    `isinstance` assert below is what actually narrows it for mypy, not the
    parse mode alone."""
    tree = ast.parse(expression, mode="eval")
    assert isinstance(tree.body, ast.Call)
    return tree.body


def test_network_call_shape_recognizes_opener_calls() -> None:
    assert gate._network_call_shape(_parse_call("opener(request)")) == gate._OPENER_CALL


def test_network_call_shape_recognizes_urllib_and_http_client_calls() -> None:
    for expression, expected in (
        ("urllib.request.urlopen(url)", gate._URLLIB_ATTR_CALL),
        ("http.client.HTTPSConnection(host)", gate._URLLIB_ATTR_CALL),
        ("some_module.urlopen(url)", gate._URLLIB_ATTR_CALL),
    ):
        assert gate._network_call_shape(_parse_call(expression)) == expected, expression


def test_network_call_shape_rejects_unrelated_calls() -> None:
    for expression in ("loader.parse()", "requests.get(url)", "self.session.request(url)", "print(x)"):
        assert gate._network_call_shape(_parse_call(expression)) is None, expression


def test_dotted_name_returns_none_for_a_call_result_in_the_chain() -> None:
    # The receiver `get_module()` is itself a Call, not a Name/Attribute
    # chain, so `_dotted_name` cannot resolve it -- and this must not be
    # misread as the bare-Name "opener" shape either.
    assert gate._network_call_shape(_parse_call("get_module().urlopen(url)")) is None


def test_dotted_name_joins_a_multi_segment_attribute_chain() -> None:
    """Direct coverage of `_dotted_name` itself (not only through
    `_network_call_shape`'s own call above): a pure `Name`/`Attribute` chain
    joins in source order, and a bare `Name` alone still resolves."""
    tree = ast.parse("a.b.c", mode="eval")
    assert gate._dotted_name(tree.body) == "a.b.c"
    bare = ast.parse("a", mode="eval")
    assert gate._dotted_name(bare.body) == "a"


# --- _handler_names unit coverage -------------------------------------------


def _parse_handler(source: str) -> ast.ExceptHandler:
    """Parse a one-`try` module and return its first `except` clause."""
    tree = ast.parse(source)
    try_node = tree.body[0]
    assert isinstance(try_node, ast.Try)
    return try_node.handlers[0]


def test_handler_names_reads_a_bare_except_as_baseexception() -> None:
    handler = _parse_handler("try:\n    pass\nexcept:\n    pass\n")
    assert gate._handler_names(handler) == {"BaseException"}


def test_handler_names_reads_a_single_name_handler() -> None:
    handler = _parse_handler("try:\n    pass\nexcept OSError:\n    pass\n")
    assert gate._handler_names(handler) == {"OSError"}


def test_handler_names_reads_a_tuple_handler_by_final_names() -> None:
    handler = _parse_handler("try:\n    pass\nexcept (OSError, ValueError):\n    pass\n")
    assert gate._handler_names(handler) == {"OSError", "ValueError"}


def test_handler_names_reads_an_attribute_handler_by_its_final_segment() -> None:
    handler = _parse_handler("try:\n    pass\nexcept urllib.error.URLError:\n    pass\n")
    assert gate._handler_names(handler) == {"URLError"}


def test_handler_names_ignores_a_tuple_element_that_is_neither_name_nor_attribute() -> None:
    """A tuple element that is itself a call result (e.g. a factory-returned
    exception type) is neither an `ast.Name` nor an `ast.Attribute`, so it
    contributes nothing -- the remaining, recognizable element(s) still do."""
    handler = _parse_handler("try:\n    pass\nexcept (some_call(), OSError):\n    pass\n")
    assert gate._handler_names(handler) == {"OSError"}


# --- _iter_excluding_nested_defs unit coverage ------------------------------


def test_iter_excluding_nested_defs_skips_nested_function_and_lambda_bodies() -> None:
    """A nested `def`/`lambda` inside the walked node's own body is its own
    scope: neither the nested def/lambda node itself, nor anything inside
    its body, is yielded -- only the outer function's own two `Return`
    statements are."""
    tree = ast.parse(
        "def outer():\n"
        "    return opener(request)\n"
        "    def inner():\n"
        "        return opener(request2)\n"
        "    lam = lambda: opener(request3)\n"
        "    return 1\n"
    )
    outer = tree.body[0]
    nodes = list(gate._iter_excluding_nested_defs(outer))
    assert not any(isinstance(node, ast.FunctionDef | ast.Lambda) for node in nodes)
    assert sum(isinstance(node, ast.Return) for node in nodes) == 2


# --- _contains_network_call_shape unit coverage -----------------------------


def test_contains_network_call_shape_matches_the_node_itself() -> None:
    call = _parse_call("opener(request)")
    assert gate._contains_network_call_shape(call) == gate._OPENER_CALL


def test_contains_network_call_shape_matches_a_descendant_call() -> None:
    stmt = ast.parse("x = [opener(request)]").body[0]
    assert gate._contains_network_call_shape(stmt) == gate._OPENER_CALL


def test_contains_network_call_shape_returns_none_for_a_nested_def_passed_directly() -> None:
    """The stated exclusion, hit when `node` itself is a nested
    function/lambda rather than merely containing one: the network call
    inside `inner`'s own body must never be found."""
    inner_def = ast.parse("def inner():\n    return opener(request)\n").body[0]
    assert gate._contains_network_call_shape(inner_def) is None


def test_contains_network_call_shape_returns_none_when_nothing_matches() -> None:
    stmt = ast.parse("x = 1 + 2").body[0]
    assert gate._contains_network_call_shape(stmt) is None


# --- _try_body_network_shape / _first_network_try unit coverage ------------


def _parse_try(source: str) -> ast.Try:
    """Parse a one-`try` module and return the `Try` statement itself,
    typed precisely for mypy rather than the general `ast.stmt`
    `Module.body[0]` carries."""
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.Try)
    return node


def _parse_function(source: str) -> ast.FunctionDef:
    """Parse a one-`def` module and return the `FunctionDef` itself, typed
    precisely rather than as the general `ast.stmt` `Module.body[0]`
    carries."""
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_try_body_network_shape_returns_the_shape_when_present() -> None:
    try_node = _parse_try("try:\n    return opener(request)\nexcept OSError:\n    pass\n")
    assert gate._try_body_network_shape(try_node) == gate._OPENER_CALL


def test_try_body_network_shape_returns_none_when_absent() -> None:
    try_node = _parse_try("try:\n    return 1\nexcept OSError:\n    pass\n")
    assert gate._try_body_network_shape(try_node) is None


def test_first_network_try_skips_a_non_qualifying_try_and_returns_the_next() -> None:
    function_node = _parse_function(
        "def f():\n"
        "    try:\n"
        "        return 1\n"
        "    except ValueError:\n"
        "        pass\n"
        "    try:\n"
        "        return opener(request)\n"
        "    except OSError:\n"
        "        pass\n"
    )
    found = gate._first_network_try(function_node)
    assert found is not None
    try_node, shape = found
    assert shape == gate._OPENER_CALL
    assert try_node.lineno == 6


def test_first_network_try_returns_none_when_no_try_qualifies() -> None:
    function_node = _parse_function("def g():\n    try:\n        return 1\n    except ValueError:\n        pass\n")
    assert gate._first_network_try(function_node) is None


# --- _first_nested_network_try / _network_call_handlers unit coverage ------
# --- (the nested-try accumulation fix itself, unit-tested directly rather
# --- than only through _module_candidates/_grade above) --------------------


def test_first_nested_network_try_finds_a_try_that_is_itself_the_next_statement() -> None:
    """The exact shape the bug report names: the nested `try` IS the first
    (and only) statement in the outer `try`'s own body -- not buried inside
    some other statement -- which `_iter_excluding_nested_defs` alone would
    miss since it yields a node's CHILDREN, never the node itself."""
    outer = _parse_try(
        "try:\n"
        "    try:\n"
        "        return opener(request)\n"
        "    except ValueError:\n"
        "        return None\n"
        "except OSError:\n"
        "    return None\n"
    )
    nested = gate._first_nested_network_try(outer)
    assert nested is not None
    assert nested.lineno == 2
    assert gate._handler_names(nested.handlers[0]) == {"ValueError"}


def test_first_nested_network_try_finds_a_try_buried_inside_another_statement() -> None:
    """The nested `try` is not itself a direct statement of the outer `try`'s
    own body -- it sits inside an `if` -- exercising the
    `_iter_excluding_nested_defs(statement)` descent, not just the
    self-check `itertools.chain` adds in front of it."""
    outer = _parse_try(
        "try:\n"
        "    if flag:\n"
        "        try:\n"
        "            return opener(request)\n"
        "        except ValueError:\n"
        "            return None\n"
        "except OSError:\n"
        "    return None\n"
    )
    nested = gate._first_nested_network_try(outer)
    assert nested is not None
    assert nested.lineno == 3


def test_first_nested_network_try_returns_none_when_the_call_is_not_further_wrapped() -> None:
    """The base case every recursion needs: the call sits directly in the
    outer `try`'s own body, wrapped by no further nested `try` at all."""
    outer = _parse_try("try:\n    return opener(request)\nexcept OSError:\n    pass\n")
    assert gate._first_nested_network_try(outer) is None


def test_network_call_handlers_returns_just_the_outer_handlers_when_not_nested() -> None:
    """No nested `try` around the call: the effective set is exactly that
    `try`'s own handlers, matching the pre-fix behaviour for this case."""
    try_node = _parse_try("try:\n    return opener(request)\nexcept OSError:\n    pass\n")
    assert gate._network_call_handlers(try_node) == frozenset({"OSError"})


def test_network_call_handlers_unions_one_level_of_nesting() -> None:
    """One inner `try` wrapping the call inside the outer one: the union of
    both tries' own handler names -- this file's own Finding 1 fix."""
    outer = _parse_try(
        "try:\n"
        "    try:\n"
        "        return opener(request)\n"
        "    except ValueError:\n"
        "        return None\n"
        "except OSError:\n"
        "    return None\n"
    )
    assert gate._network_call_handlers(outer) == frozenset({"OSError", "ValueError"})


def test_network_call_handlers_unions_two_levels_of_nesting() -> None:
    """The recursive case, generalized past one level: three tries deep, all
    three handler-name sets are unioned, not just the outermost or the
    innermost pair."""
    outer = _parse_try(
        "try:\n"
        "    try:\n"
        "        try:\n"
        "            return opener(request)\n"
        "        except TimeoutError:\n"
        "            return None\n"
        "    except ValueError:\n"
        "        return None\n"
        "except OSError:\n"
        "    return None\n"
    )
    assert gate._network_call_handlers(outer) == frozenset({"OSError", "ValueError", "TimeoutError"})


# --- _module_candidates / _drift_pairs / _try_span unit coverage -----------


def test_module_candidates_lists_only_functions_with_a_qualifying_try() -> None:
    tree = ast.parse(
        "def not_qualifying():\n"
        "    return 1\n"
        "\n\n"
        "def fetch_a(opener, request):\n"
        "    try:\n"
        "        return opener(request)\n"
        "    except OSError:\n"
        "        return None\n"
    )
    candidates = gate._module_candidates(tree)
    assert [candidate.function_name for candidate in candidates] == ["fetch_a"]
    assert candidates[0].shape == gate._OPENER_CALL
    assert candidates[0].handlers == frozenset({"OSError"})


def test_drift_pairs_yields_only_differing_pairs_within_the_same_shape_group() -> None:
    try_node = _parse_try("try:\n    return opener(request)\nexcept OSError:\n    pass\n")
    a = gate._TryCandidate("a", gate._OPENER_CALL, frozenset({"OSError"}), try_node)
    b = gate._TryCandidate("b", gate._OPENER_CALL, frozenset({"OSError", "ValueError"}), try_node)
    c = gate._TryCandidate("c", gate._OPENER_CALL, frozenset({"OSError"}), try_node)

    pairs = [(first.function_name, second.function_name) for first, second in gate._drift_pairs([a, b, c])]
    assert pairs == [("a", "b"), ("b", "c")]

    # Identical handler sets across the whole group: no drift at all.
    assert list(gate._drift_pairs([a, c])) == []
    # A group of one candidate can never form a pair.
    assert list(gate._drift_pairs([a])) == []


def test_try_span_returns_the_inclusive_header_through_handler_line_range() -> None:
    try_node = _parse_try("try:\n    return opener(request)\nexcept OSError:\n    pass\n")
    assert gate._try_span(try_node) == (1, 4)


# --- scope limits: nested / non-module-level functions are not scanned -----


def test_functions_nested_inside_a_class_are_not_scanned(tmp_path: pathlib.Path) -> None:
    """Stated known miss: only `tree.body`'s own direct FunctionDef/
    AsyncFunctionDef entries are visited, so two methods on the same class
    that drift exactly this way are invisible to this first version."""
    source = """
class Client:
    def fetch_a(self, opener, request):
        try:
            return opener(request)
        except OSError:
            return None

    def fetch_b(self, opener, request):
        try:
            return opener(request)
        except (OSError, ValueError):
            return None
"""
    assert _grade(tmp_path, source) == []


def test_only_the_first_qualifying_try_per_function_is_graded(tmp_path: pathlib.Path) -> None:
    """Stated known miss: a function with two separate `try` blocks, each
    independently wrapping a recognized network call, only has its first
    one graded -- a differing set on the second is never reached."""
    source = """
def fetch_a(opener, request):
    try:
        return opener(request)
    except OSError:
        return None


def fetch_b(opener, request):
    try:
        return opener(request)
    except OSError:
        return None
    try:
        return opener(request)
    except (OSError, ValueError):
        return None
"""
    # fetch_b's *first* try already matches fetch_a's handler set exactly
    # ({"OSError"}); its second try's differing set ({"OSError", "ValueError"})
    # is never reached, since only the first qualifying try per function is
    # considered.
    assert _grade(tmp_path, source) == []


# --- ScanError / exit-2 conditions ------------------------------------------


def test_an_unparseable_python_file_fails_closed(tmp_path: pathlib.Path) -> None:
    relative = ".github/scripts/gate_x.py"
    source = "def f(:\n"
    _write(tmp_path, relative, source)
    with pytest.raises(gate.ScanError, match="cannot be parsed as Python"):
        gate.find_violations(_whole_file_diff(relative, source), tmp_path)


def test_an_unreadable_file_fails_closed(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An OSError that is not FileNotFoundError still fails closed."""
    (tmp_path / ".github" / "scripts").mkdir(parents=True)
    (tmp_path / ".github" / "scripts" / "gate_x.py").mkdir()
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", "text = 1\n"))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 2
    assert "cannot be read as UTF-8 text" in capsys.readouterr().err


def test_a_file_named_by_the_diff_but_missing_from_root_fails_closed(tmp_path: pathlib.Path) -> None:
    diff = _whole_file_diff(".github/scripts/gate_x.py", "text = 1\n")
    with pytest.raises(gate.ScanError, match="missing from"):
        gate.find_violations(diff, tmp_path)


def test_a_malformed_diff_fails_closed() -> None:
    with pytest.raises(gate.ScanError):
        gate.parse_added_lines("+++ b/.github/scripts/gate_x.py\n")


# --- diff-parsing hardening (ported from gitapex_gate_except_fail_open.py's --
# --- own regression tests of the same name, byte-identical parse_added_lines
# --- mechanics -- see that file's own docstring for the full rationale) -----


def test_an_over_declared_hunk_before_the_next_diff_git_header_raises_scanerror() -> None:
    """Exercises `_reject_if_hunk_incomplete`'s own raise (the private closure
    nested inside `parse_added_lines`, waived by name at that closure's own
    `def` line): a hunk declaring 2 post-image lines but only 1 real added
    line before the next file's own `diff --git ` header."""
    diff = (
        "diff --git a/.github/scripts/x.py b/.github/scripts/x.py\n"
        "--- a/x.py\n+++ b/.github/scripts/x.py\n"
        "@@ -1,0 +1,2 @@\n+x = 1\n"
        "diff --git a/.github/scripts/y.py b/.github/scripts/y.py\n"
    )
    with pytest.raises(gate.ScanError, match="declared more pre-/post-image line"):
        gate.parse_added_lines(diff)


def test_an_over_declared_hunk_at_end_of_input_raises_scanerror() -> None:
    """Same closure, reached via `parse_added_lines`'s own final call at the
    diff's own end rather than at the next `diff --git ` header."""
    diff = "diff --git a/.github/scripts/x.py b/.github/scripts/x.py\n--- a/x.py\n+++ b/.github/scripts/x.py\n@@ -1,0 +1,2 @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="the diff ended"):
        gate.parse_added_lines(diff)


def test_an_over_declared_hunk_length_before_a_new_hunk_header_raises_scanerror() -> None:
    """Same closure again, reached at the next hunk header (`@@ ... @@`)
    rather than a file boundary: `@@ -0,0 +1,5 @@` declares 5 post-image
    lines but only 2 real added lines follow before the next file's own
    headers begin -- with no `diff --git ` separator, `new_remaining` stays
    above zero, so the guard must catch this at the second file's own `@@`
    line before any of its content is consumed."""
    diff = (
        "--- a/.github/scripts/file1.py\n"
        "+++ b/.github/scripts/file1.py\n"
        "@@ -0,0 +1,5 @@\n"
        "+def f():\n"
        "+    pass\n"
        "--- a/.github/scripts/file2.py\n"
        "+++ b/.github/scripts/file2.py\n"
        "@@ -1,1 +1,2 @@\n"
    )
    with pytest.raises(gate.ScanError, match=r"2 post-image line\(s\) still unconsumed"):
        gate.parse_added_lines(diff)


def test_an_unparseable_hunk_header_raises_scanerror() -> None:
    """A distinct raise from the closure above: `_HUNK_RE.match(line)`
    itself fails to match a `@@ ... @@`-shaped line with no parseable
    line-number groups."""
    diff = "diff --git a/.github/scripts/x.py b/.github/scripts/x.py\n--- a/x.py\n+++ b/.github/scripts/x.py\n@@ nonsense @@\n+x = 1\n"
    with pytest.raises(gate.ScanError, match="unparseable hunk header"):
        gate.parse_added_lines(diff)


def test_an_over_declared_hunk_that_drains_into_a_real_header_pair_raises_scanerror() -> None:
    """The disguised-header-absorption bypass this gate's own diff parser
    guards against: a hunk whose declared count is honestly satisfied by
    content that itself looks like a `--- `/`+++ ` header pair, immediately
    followed by something `@@`-/`diff --git `-shaped -- ambiguous between
    coincidental hunk-closing content and a real file transition missing its
    `diff --git ` separator, so this fails closed rather than guessing."""
    diff = (
        "--- a/.github/scripts/x.py\n"
        "+++ b/.github/scripts/x.py\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a/.github/scripts/y.py\n"
        "+++ b/.github/scripts/y.py\n"
        "@@ -1,1 +1,2 @@\n"
    )
    with pytest.raises(gate.ScanError, match="shaped like a new file's own post-image header"):
        gate.parse_added_lines(diff)


def test_a_header_shaped_pair_with_nothing_confirming_it_after_is_not_an_error() -> None:
    """Pins the one case `_looks_like_real_header_pair` alone cannot resolve
    (issue #1200's own already-disclosed gap, ported unchanged from
    gitapex_gate_exception_handler_gaps.py/gitapex_gate_except_fail_open.py):
    a hunk whose declared count is small enough to be honestly, exactly
    satisfied by content that itself happens to look header-shaped, with
    nothing `@@`-/`diff --git `-shaped confirming it afterward."""
    diff = (
        "--- a/.github/scripts/file1.py\n"
        "+++ b/.github/scripts/file1.py\n"
        "@@ -1,1 +1,1 @@\n"
        "--- a/.github/scripts/file2.py\n"
        "+++ b/.github/scripts/file2.py\n"
    )
    assert gate.parse_added_lines(diff) == {".github/scripts/file1.py": {1}}


def test_an_added_line_under_a_deleted_files_hunk_is_not_recorded() -> None:
    """A `+`-prefixed line reached while `path is None` (a deletion's own
    hunk -- malformed input a hand-fed patch could produce, never real `git
    diff` output) advances the counters but is not recorded anywhere."""
    diff = "--- a/.github/scripts/gone.py\n+++ /dev/null\n@@ -0,0 +1,1 @@\n+phantom\n"
    assert gate.parse_added_lines(diff) == {}


# --- in_scope ---------------------------------------------------------------


def test_in_scope_matches_the_four_checker_directories() -> None:
    assert gate.in_scope(".github/scripts/gitapex_gate_foo.py") is True
    assert gate.in_scope("hooks/gitapex_check_foo.py") is True
    assert gate.in_scope("evals/scripts/gitapex_foo.py") is True
    assert gate.in_scope("skills/some-skill/scripts/gitapex_foo.py") is True
    assert gate.in_scope("src/gitapex_gate_foo.py") is False
    assert gate.in_scope(".github/scripts/test_gitapex_gate_foo.py") is False
    assert gate.in_scope(".github/scripts/conftest.py") is False


# --- CLI ----------------------------------------------------------------


def test_an_empty_diff_is_clean_and_says_so(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "diff.txt", "")
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 0
    assert "OK: 0 in-scope file(s) graded" in capsys.readouterr().out


def test_main_returns_one_and_explains_the_failure(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, _REAL_GITHUB_HTTP, _PRE_FIX_GITHUB_HTTP)
    _write(tmp_path, "diff.txt", _whole_file_diff(_REAL_GITHUB_HTTP, _PRE_FIX_GITHUB_HTTP))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 1
    stderr = capsys.readouterr().err
    assert gate._DRIFT_RULE in stderr
    assert "#1512" in stderr
    assert "network-exception-set-drift: WAIVED:" in stderr


def test_main_exits_0_and_prints_honoured_waivers_to_stderr(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean run (no unwaived violations) that still carries an honoured
    waiver: `main`'s own `for finding in waived: print(...)` loop must run
    even though the exit code is 0, not only the violations-reporting branch
    `test_main_returns_one_and_explains_the_failure` above already covers."""
    source = _OPENER_DRIFT_SOURCE.replace(
        "def fetch_b(opener, request):\n    try:\n",
        "def fetch_b(opener, request):\n"
        "    try:  # network-exception-set-drift: WAIVED: deliberate, ValueError is local\n",
    )
    _write(tmp_path, ".github/scripts/gate_x.py", source)
    _write(tmp_path, "diff.txt", _whole_file_diff(".github/scripts/gate_x.py", source))
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "diff.txt")]) == 0
    stderr = capsys.readouterr().err
    assert "waived inline" in stderr
    assert gate._DRIFT_RULE in stderr


def test_main_exits_2_on_a_root_that_does_not_exist(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--root", str(tmp_path / "nope")]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_main_exits_2_on_a_root_that_is_a_file(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    a_file = _write(tmp_path, "not-a-directory", "x")
    assert gate.main(["--root", str(a_file)]) == 2
    assert "must be an existing directory" in capsys.readouterr().err


def test_root_must_exist_validator_rejects_a_nonexistent_directory(tmp_path: pathlib.Path) -> None:
    """`_root_must_exist` itself, called directly rather than only through
    `main`'s own CLI wrapper or pydantic's own construction path."""
    missing = tmp_path / "nope"
    with pytest.raises(ValueError, match="must be an existing directory"):
        gate.GateNetworkExceptionSetDriftArgs._root_must_exist(missing)


def test_root_must_exist_validator_passes_through_an_existing_directory(tmp_path: pathlib.Path) -> None:
    assert gate.GateNetworkExceptionSetDriftArgs._root_must_exist(tmp_path) == tmp_path


def test_root_must_exist_validator_fires_during_args_construction(tmp_path: pathlib.Path) -> None:
    """The same validator, reached the way `main` actually reaches it: via
    `GateNetworkExceptionSetDriftArgs(root=...)`'s own pydantic validation,
    not a direct call."""
    with pytest.raises(gate.ValidationError, match="must be an existing directory"):
        gate.GateNetworkExceptionSetDriftArgs(root=tmp_path / "nope")
    assert gate.GateNetworkExceptionSetDriftArgs(root=tmp_path).root == tmp_path


def test_main_exits_2_when_the_diff_file_is_missing(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--root", str(tmp_path), "--diff", str(tmp_path / "nope.diff")]) == 2
    assert "diff cannot be read" in capsys.readouterr().err


def test_main_exits_2_when_the_diff_file_is_not_utf8(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    diff_path = tmp_path / "diff.bin"
    diff_path.write_bytes(b"\xff\xfe not a diff")
    assert gate.main(["--root", str(tmp_path), "--diff", str(diff_path)]) == 2
    assert "diff cannot be read" in capsys.readouterr().err


class _FakeStdin:
    """Just the surface `main` uses: `sys.stdin.buffer.read()`."""

    def __init__(self, data: bytes) -> None:
        import io as _io

        self.buffer = _io.BytesIO(data)


def test_main_reads_the_diff_from_stdin_when_no_flag_is_given(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, _REAL_GITHUB_HTTP, _PRE_FIX_GITHUB_HTTP)
    diff = _whole_file_diff(_REAL_GITHUB_HTTP, _PRE_FIX_GITHUB_HTTP)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(diff.encode("utf-8")))
    assert gate.main(["--root", str(tmp_path)]) == 1
    assert gate._DRIFT_RULE in capsys.readouterr().err


def test_a_non_utf8_byte_on_stdin_fails_closed_instead_of_crashing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path, _REAL_GITHUB_HTTP, _PRE_FIX_GITHUB_HTTP)
    diff = _whole_file_diff(_REAL_GITHUB_HTTP, _PRE_FIX_GITHUB_HTTP)
    monkeypatch.setattr(gate.sys, "stdin", _FakeStdin(diff.encode("utf-8") + b"+# \xff\xfe\n"))
    assert gate.main(["--root", str(tmp_path)]) == 2
    assert "diff cannot be read as UTF-8 text" in capsys.readouterr().err


def test_this_gates_own_source_grades_clean_against_itself(tmp_path: pathlib.Path) -> None:
    """Dogfooding: this gate's own source contains no drift by its own
    rules (it defines no pair of module-level functions wrapping a
    recognized network call at all)."""
    source = (REPO_ROOT / _SCRIPT).read_text(encoding="utf-8")
    violations, waived, graded = gate.find_violations(_whole_file_diff(_SCRIPT, source), REPO_ROOT)
    assert graded == 1
    assert violations == []
    assert waived == []


# --- the real repository ------------------------------------------------


def test_the_workflow_passes_the_two_flags_the_gate_depends_on() -> None:
    assert_workflow_diff_carries_flags("network-exception-set-drift-gate.yml", "--no-renames", "core.quotePath=false")


def test_the_workflow_checks_out_the_head_sha_with_full_history() -> None:
    assert_workflow_checkout_pins_head_sha_with_full_history("network-exception-set-drift-gate.yml")


def test_the_workflow_has_no_paths_filter() -> None:
    assert_workflow_has_no_trigger_path_filter("network-exception-set-drift-gate.yml")


def test_the_workflow_uses_merge_base_not_base_sha() -> None:
    assert_workflow_feeds_merge_base_to("network-exception-set-drift-gate.yml", "diff")


def test_against_real_git_diff_output(tmp_path: pathlib.Path) -> None:
    """Live proof, not a hand-authored approximation of one: a real git
    repository, a real edit, and `git diff -U0` exactly as the workflow
    invokes it -- the same pattern
    `tests/test_gitapex_gate_exception_handler_gaps.py`'s own
    `test_against_real_git_diff_output` uses."""
    run = subprocess.run
    run(["git", "init", "-q", str(tmp_path)], check=True)
    run(["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True)
    run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    relative = ".github/scripts/gate_x.py"
    clean = (
        "def fetch_a(opener, request):\n"
        "    try:\n"
        "        return opener(request)\n"
        "    except OSError:\n"
        "        return None\n"
    )
    _write(tmp_path, relative, clean)
    run(["git", "-C", str(tmp_path), "add", "--", relative], check=True)
    run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)

    (tmp_path / relative).write_text(
        clean + "\n\ndef fetch_b(opener, request):\n    try:\n        return opener(request)\n"
        "    except (OSError, ValueError):\n        return None\n",
        encoding="utf-8",
    )
    diff = run(
        ["git", "-C", str(tmp_path), "diff", "-U0", "--", "*.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    violations, _waived, graded = gate.find_violations(diff, tmp_path)
    assert graded == 1
    assert _rules(violations) == [gate._DRIFT_RULE]
