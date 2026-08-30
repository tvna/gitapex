"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_bare_python3_invocation.py``'s
``hooks/*.sh`` shell-variable-indirected scan (issue #1446 Item 2,
closing issue #1178's own ``detection-logic-property-coverage`` gap for
the new ``_UV_WRAPPED_INVOCATION_RE``/``_SHELL_ASSIGNMENT_RE``/
``_GITHUB_SCRIPTS_PATH_RE`` module-level compiles and the
``.startswith()``/regex call sites inside ``_scan_hook``).

Every property below calls ``gate._scan_hook`` directly (not
``find_hooks_shell_indirected_invocations``'s directory-level wrapper)
from inside each ``@given``-decorated test's own body -- this
repository's ``detection-logic-property-coverage`` gate (issue #1178)
checks for the covered function's own name inside the decorated test
function's body, not inside a shared helper it merely calls, so a
helper-indirected call would not register as coverage.

This module resolves via ``import gitapex_gate_bare_python3_invocation``
-- ``.github/scripts`` is on pyproject.toml's own ``pythonpath``, the same
resolution ``tests/test_gitapex_gate_bare_python3_invocation.py`` already
uses.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples``
and ``deadline=None``, matching this repository's own established
rationale in ``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``
and ``tests/test_gitapex_check_post_write_provenance_properties.py``
(this repository runs pytest under ``pytest-xdist``, where a randomly-
seeded generator turns a latent failure into an intermittently red
suite).
"""

from __future__ import annotations

import pathlib
import tempfile

import gitapex_gate_bare_python3_invocation as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_VARNAMES = st.from_regex(r"[A-Za-z_][A-Za-z0-9_]{0,12}", fullmatch=True)
_SCRIPT_STEMS = st.from_regex(r"[a-z][a-z0-9_]{0,16}", fullmatch=True)
_PREFIXES = st.sampled_from(["", "${repo_root}", "$repo_root", "/abs/path"])


@_PROPERTIES
@given(varname=_VARNAMES, stem=_SCRIPT_STEMS, prefix=_PREFIXES)
def test_assignment_then_bare_invocation_is_always_detected(varname: str, stem: str, prefix: str) -> None:
    """**Model-based, proven property, not just the one hand-picked
    fixture:** for ANY shell-safe variable name and ANY `.github/scripts`
    script stem, a variable assigned a `.github/scripts/<stem>.py` path
    on one line and later invoked bare as `python3 "$VARNAME"` (no `uv
    run` anywhere) must always be detected -- the exact real-world shape
    `hooks/check-pr-skill-audit-disclosure.sh`'s own `full_gate` variable
    uses, driven across generated variable/script names instead of that
    one fixture."""
    content = f'{varname}="{prefix}/.github/scripts/{stem}.py"\n...\npython3 "${varname}"\n'
    with tempfile.TemporaryDirectory() as tmp:
        hook_path = pathlib.Path(tmp) / "generated.sh"
        hook_path.write_text(content, encoding="utf-8")
        findings = gate._scan_hook(hook_path)
    assert any(varname in label for label, _lineno, _line in findings)


@_PROPERTIES
@given(varname=_VARNAMES, stem=_SCRIPT_STEMS, prefix=_PREFIXES)
def test_uv_run_wrapped_invocation_is_never_flagged(varname: str, stem: str, prefix: str) -> None:
    """The uv-run-adjacency half of this scan's own contract, driven
    across generated names: the identical assignment shape as above, but
    with the invocation wrapped in `uv run --frozen`, must never be
    flagged -- `uv run` wrapping is exactly what this WARNING exists to
    NOT complain about."""
    content = f'{varname}="{prefix}/.github/scripts/{stem}.py"\n...\nuv run --frozen python3 "${varname}"\n'
    with tempfile.TemporaryDirectory() as tmp:
        hook_path = pathlib.Path(tmp) / "generated.sh"
        hook_path.write_text(content, encoding="utf-8")
        findings = gate._scan_hook(hook_path)
    assert findings == []


@_PROPERTIES
@given(varname=_VARNAMES, stem=_SCRIPT_STEMS)
def test_hooks_py_targeting_variable_is_never_flagged(varname: str, stem: str) -> None:
    """The Constraints-section guarantee (issue #1446): a variable whose
    own assignment targets a `hooks/*.py` path -- deliberately stdlib-
    only and bare-invoked by design, per docs/repository-layout.md --
    must never be flagged even when invoked bare, for any generated
    variable/script name, not just one hand-picked example."""
    content = f'{varname}="${{repo_root}}/hooks/{stem}.py"\n...\npython3 "${varname}"\n'
    with tempfile.TemporaryDirectory() as tmp:
        hook_path = pathlib.Path(tmp) / "generated.sh"
        hook_path.write_text(content, encoding="utf-8")
        findings = gate._scan_hook(hook_path)
    assert findings == []


@_PROPERTIES
@given(varname=_VARNAMES, stem=_SCRIPT_STEMS)
def test_commented_out_assignment_and_invocation_are_ignored(varname: str, stem: str) -> None:
    """The whole-line-comment carve-out (`line.lstrip().startswith("#")`)
    both passes inside `_scan_hook` share: a `#`-commented assignment
    line and a `#`-commented invocation line, for any generated
    variable/script name, must never produce a finding -- neither line
    ever executes."""
    content = f'# {varname}="${{repo_root}}/.github/scripts/{stem}.py"\n# python3 "${varname}"\n'
    with tempfile.TemporaryDirectory() as tmp:
        hook_path = pathlib.Path(tmp) / "generated.sh"
        hook_path.write_text(content, encoding="utf-8")
        findings = gate._scan_hook(hook_path)
    assert findings == []


@_PROPERTIES
@given(text=st.text(max_size=500))
def test_scan_hook_never_raises_and_is_deterministic(text: str) -> None:
    """Robustness: this scan runs inside a CI-invoked CLI (WARNING tier,
    but still a required-not-to-crash code path) -- arbitrary hook file
    content, generated rather than hand-picked, must always produce a
    result rather than an uncaught exception, and the same input must
    always produce the same result."""
    with tempfile.TemporaryDirectory() as tmp:
        hook_path = pathlib.Path(tmp) / "generated.sh"
        hook_path.write_text(text, encoding="utf-8")
        first = gate._scan_hook(hook_path)
        second = gate._scan_hook(hook_path)
    assert first == second
    assert isinstance(first, list)
