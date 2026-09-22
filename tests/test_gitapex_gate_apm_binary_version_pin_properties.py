"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_apm_binary_version_pin.py`` (issue #1817),
added because issue #1178's ``detection-logic-property-coverage`` gate
requires one for this module's regex-based detection logic: the
module-level ``_APM_PIN_RE``/``_APM_VERSION_OUTPUT_RE`` compiles, and the
``parse_apm_pin_version``/``extract_apm_version`` call sites that use them.
"""

from __future__ import annotations

import gitapex_gate_apm_binary_version_pin as gate
from hypothesis import given, settings
from hypothesis import strategies as st

_PROPERTIES = settings(derandomize=True, max_examples=200, deadline=None)

_VERSION_PART = st.integers(min_value=0, max_value=999)


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
