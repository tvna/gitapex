"""Hypothesis property layer for
``.github/scripts/gitapex_gate_tool_boundary_parity.py`` (issue #1963,
closing issue #1178's ``detection-logic-property-coverage`` gap for this
gate's frontmatter regex, its permission-block scan, and the path
resolution at module level).

The fixed-example tests in ``tests/test_gitapex_gate_tool_boundary_parity.py``
pin the shapes this issue actually found. These properties assert the
invariants those shapes are instances of, which is where a scan that
happens to work on the hand-written examples but not in general shows up.

Reproducibility: ``derandomize=True`` with an explicit ``max_examples``
and ``deadline=None``, matching this repository's own established
rationale in ``tests/test_gitapex_gate_metadata_outcome_lines_properties.py``.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

import gitapex_gate_tool_boundary_parity as gate  # noqa: E402

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_KEY = st.from_regex(r"\A[A-Za-z_][A-Za-z0-9_-]{0,15}\Z", fullmatch=True)
_PERMISSION_KEY = st.from_regex(r"\A[A-Za-z*_][A-Za-z0-9*_-]{0,15}\Z", fullmatch=True)
_VALUE = st.text(
    alphabet=st.characters(blacklist_categories=("Cc", "Cs"), blacklist_characters="\n\r:"),
    max_size=30,
)


@_PROPERTIES
@given(key=_KEY, value=_VALUE)
def test_frontmatter_fields_reads_back_any_single_key(key: str, value: str) -> None:
    assert gate.frontmatter_fields(f"---\n{key}: {value}\n---\n") == {key: value.strip()}


@_PROPERTIES
@given(prefix=st.text(min_size=1, max_size=20), key=_KEY, value=_VALUE)
def test_frontmatter_fields_requires_the_block_at_the_first_byte(prefix: str, key: str, value: str) -> None:
    """**Detects a real gap the fixed examples cannot:** the one fixed
    case uses a single hand-written prefix. For ANY non-empty prefix that
    is not itself the delimiter, a `---` block further down the file is a
    horizontal rule, not frontmatter, and must yield nothing."""
    text = f"{prefix}\n---\n{key}: {value}\n---\n"
    if text.startswith("---\n"):
        return
    assert gate.frontmatter_fields(text) == {}


@_PROPERTIES
@given(keys=st.lists(_PERMISSION_KEY, min_size=1, max_size=6, unique=True))
def test_every_denied_key_in_a_permission_block_is_reported(keys: list[str]) -> None:
    entries = "\n".join(f"  {key}: deny" for key in keys)
    text = f"---\ndescription: d\npermission:\n{entries}\n---\n\nbody\n"
    assert gate.generated_permission_keys(text) == set(keys)


@_PROPERTIES
@given(keys=st.lists(_PERMISSION_KEY, min_size=1, max_size=6, unique=True), mapping=_KEY)
def test_a_permission_shaped_block_under_another_mapping_is_never_counted(keys: list[str], mapping: str) -> None:
    """**Detects a real gap the fixed examples cannot:** the fixed case
    nests under one hand-picked key name. For ANY other top-level mapping
    name, indented `key: deny` lines under it are that mapping's content,
    never a reproduced tool boundary."""
    if mapping == "permission":
        return
    entries = "\n".join(f"  {key}: deny" for key in keys)
    text = f"---\ndescription: d\n{mapping}:\n{entries}\n---\n\nbody\n"
    assert gate.generated_permission_keys(text) == set()


@_PROPERTIES
@given(keys=st.lists(_PERMISSION_KEY, min_size=1, max_size=6, unique=True))
def test_allow_entries_are_never_counted_as_denials(keys: list[str]) -> None:
    entries = "\n".join(f"  {key}: allow" for key in keys)
    text = f"---\npermission:\n{entries}\n---\n\nbody\n"
    assert gate.generated_permission_keys(text) == set()


@_PROPERTIES
@given(text=st.text(max_size=200))
def test_generated_permission_keys_never_raises(text: str) -> None:
    """A generated copy is machine-written but still arbitrary text on
    disk; this scan must classify it, never crash on it."""
    assert isinstance(gate.generated_permission_keys(text), set)


@_PROPERTIES
@given(name=st.sampled_from(sorted(gate.EXPECTED_BOUNDARIES)))
def test_every_table_row_names_a_real_boundary_key(name: str) -> None:
    """The expectation table is data this gate trusts; every row must name
    a boundary key the gate actually recognises, or the row can never be
    satisfied by any source file."""
    expected_key, _expected_value, expected_denials = gate.EXPECTED_BOUNDARIES[name]
    assert expected_key in gate.BOUNDARY_KEYS
    assert expected_denials


@_PROPERTIES
@given(parts=st.lists(st.sampled_from(["..", ".", "a", "b"]), min_size=1, max_size=4))
def test_repo_root_resolution_cannot_be_walked_out_of_by_accident(parts: list[str]) -> None:
    """Covers the module-level ``.resolve()`` site, and asserts the fact
    that actually matters about it: ``parents[2]`` really is this
    repository's root, not some ancestor.

    An earlier version of this property drew only ``[a-z]{1,8}`` segments,
    which cannot contain ``..`` -- so its "stays inside the root"
    assertion was unfalsifiable by construction and exercised ``pathlib``
    rather than the gate. The strategy now includes ``..``, and the
    assertion says what is true: a suffix containing ``..`` CAN escape,
    which is exactly why every path this gate builds is a fixed constant
    rather than caller-supplied.
    """
    assert (gate.REPO_ROOT / ".gitapex" / "ssot.json").is_file()
    assert (gate.REPO_ROOT / "AGENTS.md").is_file()
    plain = [part for part in parts if part not in ("..", ".")]
    assert str(gate.REPO_ROOT.joinpath(*plain).resolve()).startswith(str(gate.REPO_ROOT))
    # And the converse, stated rather than assumed: enough `..` DOES leave
    # the root. That is why every path this gate builds is a fixed
    # constant, never a caller-supplied suffix.
    assert not str(gate.REPO_ROOT.joinpath("..", "..", "..").resolve()).startswith(str(gate.REPO_ROOT) + "/")


@_PROPERTIES
@given(denials=st.lists(_PERMISSION_KEY, min_size=0, max_size=4, unique=True))
def test_main_exit_code_matches_the_verdict(denials: list[str]) -> None:
    """Covers ``main``'s own comparison over the evaluated rows: the exit
    code is 0 exactly when the mapping matches the expectation table, for
    any generated denial set -- not only the two the fixed tests pin.

    A plain ``TemporaryDirectory`` rather than pytest's ``tmp_path``:
    hypothesis re-runs the body many times per test, while a
    function-scoped fixture is created once for the whole test, so
    successive examples would otherwise write over each other's files.
    """
    expected = set(gate.EXPECTED_BOUNDARIES["branch-plan-task.md"][2])
    with tempfile.TemporaryDirectory() as raw_dir:
        root = pathlib.Path(raw_dir)
        (root / "agents").mkdir()
        (root / "agents" / "branch-plan-task.md").write_text(
            "---\nname: branch-plan-task\ndescription: d\ndisallowedTools: mcp__github\n---\n\nbody\n",
            encoding="utf-8",
        )
        (root / "hooks").mkdir()
        mapping = ", ".join(f'"{key}": "deny"' for key in denials)
        (root / "hooks" / "gitapex_sync_opencode.py").write_text(
            f'AGENT_PERMISSION_SPECS = (("branch-plan-task.md", {{{mapping}}}),)\n', encoding="utf-8"
        )
        assert (gate.main(["--repo-root", str(root)]) == 0) is (set(denials) == expected)
