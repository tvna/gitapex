"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_apm_binary_version_pin.py`` (issue #1817),
added because issue #1178's ``detection-logic-property-coverage`` gate
requires one for this module's regex-based detection logic: the
module-level ``_APM_PIN_RE``/``_APM_VERSION_OUTPUT_RE`` compiles, the
``parse_apm_pin_version``/``extract_apm_version`` call sites that use them,
and ``_strip_nix_line_comments``'s own ``.split("#", 1)`` string-splitting
call (added by this PR's independent-review round to fix a confirmed
defect: the pin regex matching a stale version string inside a comment).
"""

from __future__ import annotations

import gitapex_gate_apm_binary_version_pin as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_VERSION_PART = st.integers(min_value=0, max_value=999)

# No '#', and no line-separator character str.splitlines() itself treats as
# a line boundary (not just '\n' -- also '\r' and the other Unicode line/
# paragraph separators splitlines() recognizes): a clean "code" half a
# comment can be safely appended to without the strategy itself accidentally
# generating a second '#' or an internal line break.
_LINE_BREAK_CHARS = "\n\r\v\f\x1c\x1d\x1e\x85" + chr(0x2028) + chr(0x2029)
_CODE_LINE = st.text(alphabet=st.characters(blacklist_characters="#" + _LINE_BREAK_CHARS), max_size=20)
_COMMENT_TEXT = st.text(alphabet=st.characters(blacklist_characters=_LINE_BREAK_CHARS), max_size=20)


def _version_string(major: int, minor: int, patch: int) -> str:
    return f"{major}.{minor}.{patch}"


@_PROPERTIES
@given(major=_VERSION_PART, minor=_VERSION_PART, patch=_VERSION_PART)
def test_extract_apm_version_finds_any_semver_after_the_word_version(major: int, minor: int, patch: int) -> None:
    """For ANY major/minor/patch triple, `extract_apm_version` recovers the
    exact version string from real `apm --version`-shaped output -- the CLI
    banner text around it (product name, build hash) varies; only the
    "version X.Y.Z" substring is load-bearing."""
    version = _version_string(major, minor, patch)
    output = f"Agent Package Manager (APM) CLI version {version} (deadbeef)"
    assert gate.extract_apm_version(output) == version


@_PROPERTIES
@given(major=_VERSION_PART, minor=_VERSION_PART, patch=_VERSION_PART)
def test_parse_apm_pin_version_finds_any_pinned_version(major: int, minor: int, patch: int) -> None:
    """For ANY major/minor/patch triple embedded in flake.nix's own
    `apm = mkReleaseBinary pkgs { ... version = "X.Y.Z"; ... };` shape,
    `parse_apm_pin_version` recovers exactly that version -- independent of
    the exact asset/sha256 literals sitting alongside it in the same
    block."""
    version = _version_string(major, minor, patch)
    flake_text = (
        "      mkClassB = pkgs:\n"
        "        let sys = pkgs.stdenv.hostPlatform.system; d = classBData; in\n"
        "        {\n"
        "          apm = mkReleaseBinary pkgs {\n"
        '            pname = "apm";\n'
        f'            version = "{version}";\n'
        '            kind = "wrapperDir";\n'
        f'            url = ghRelease "microsoft" "apm" "v{version}" d.apm.${{sys}}.asset;\n'
        "            sha256 = d.apm.${sys}.sha256;\n"
        "          };\n"
        "        };\n"
    )
    assert gate.parse_apm_pin_version(flake_text) == version


@_PROPERTIES
@given(code=_CODE_LINE, comment=_COMMENT_TEXT)
def test_strip_nix_line_comments_always_drops_everything_from_the_first_hash(code: str, comment: str) -> None:
    """For ANY comment-free "code" prefix and ANY trailing text after a
    `#`, `_strip_nix_line_comments` keeps exactly the code prefix on that
    line and drops the `#` onward -- the property this PR's fix relies on
    to keep a comment mentioning an old/example version string from ever
    reaching the pin regex."""
    stripped = gate._strip_nix_line_comments(f"{code}#{comment}")
    assert stripped == code


@_PROPERTIES
@given(code=_CODE_LINE)
def test_strip_nix_line_comments_is_a_no_op_on_comment_free_text(code: str) -> None:
    """For ANY text with no `#` at all, `_strip_nix_line_comments` returns
    it unchanged."""
    assert gate._strip_nix_line_comments(code) == code
