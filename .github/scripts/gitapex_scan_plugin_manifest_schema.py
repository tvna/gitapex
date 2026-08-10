#!/usr/bin/env python3
"""Validate the repository-root plugin.json against the vendored Agent
Plugins Specification (agent-plugins.org) v1.0.0 plugin.schema.json.

Issue #1028. plugin.json is this repository's plugin-identity
source of truth (see gitapex_generate_plugin_manifest.py); this scanner is
the schema-conformance half of that migration -- it does not generate or
mirror anything, it only checks that the hand-edited source itself is a
schema-valid Agent Plugins manifest.

Vendored schema, mirroring .gitapex/waza-eval.schema.json's own
vendor-pin-and-drift-check convention (gitapex_scan_eval_suite_schema.py):
.gitapex/agent-plugins-plugin.schema.json is a byte-exact copy of
schemas/1.0.0/plugin.schema.json from agentplugins/agent-plugins-spec at
commit VENDORED_SPEC_COMMIT below. Unlike waza's own release-tagged
vendoring, agent-plugins-spec carries no Git tag or GitHub Release as of
this pin (confirmed by listing the repository's tags directly) -- so the
pin is a commit SHA, not a tag, and this docstring records that as a fact
observed at pin time, not a promise upstream will ever cut one.

Three checks:

1. ``schema-conformance``: the real repository-root plugin.json validates
   against the vendored schema (jsonschema.Draft202012Validator, format
   assertion enabled, via _gitapex_schema_validation.py -- the same shared
   helper gitapex_scan_ssot_schema.py and
   gitapex_scan_skill_metadata_schema.py use, so this does not carry a
   third independently-drifting copy of the same
   load-or-raise/validator-build/iter-errors logic).
2. ``vendor-digest-drift``: the vendored schema file's sha256 must equal
   VENDORED_SCHEMA_SHA256 below, recorded at vendor time -- catches an
   accidental hand-edit of the vendored copy.
3. ``--verify-upstream`` (opt-in, network, off by default): fetches
   schemas/1.0.0/plugin.schema.json from agentplugins/agent-plugins-spec at
   VENDORED_SPEC_COMMIT and byte-compares it against the vendored copy --
   the only check that actually proves the vendored file matches upstream;
   run this when bumping the pin.

Run standalone (exit 0 clean, 1 on any finding) or via the pytest gate in
tests/test_gitapex_scan_plugin_manifest_schema.py -- same established
convention as this repository's other scanner-shaped gates: no dedicated
CI workflow step or pre-commit hook.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import urllib.request
from urllib.error import URLError

import _gitapex_schema_validation

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN_MANIFEST_PATH = REPO_ROOT / "plugin.json"
VENDORED_SCHEMA_PATH = REPO_ROOT / ".gitapex" / "agent-plugins-plugin.schema.json"

# Recorded at vendor time by fetching schemas/1.0.0/plugin.schema.json from
# agentplugins/agent-plugins-spec and computing its sha256; re-derive both by
# re-fetching at a new commit, re-vendoring
# .gitapex/agent-plugins-plugin.schema.json, and re-running this script with
# --verify-upstream.
VENDORED_SPEC_COMMIT = "bd383552095128f6effe895b9257cfd580a6d179"
VENDORED_SCHEMA_SHA256 = "0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883"

_UPSTREAM_RAW_URL = (
    "https://raw.githubusercontent.com/agentplugins/agent-plugins-spec/"
    f"{VENDORED_SPEC_COMMIT}/schemas/1.0.0/plugin.schema.json"
)
_HTTP_TIMEOUT_SECONDS = 30


class ScanReadError(Exception):
    """plugin.json or the vendored schema could not be read as UTF-8 text or
    parsed as JSON at all -- exit 1, never a traceback. Distinct from a
    schema-invalid-but-parseable plugin.json, which
    schema_conformance_findings reports as an ordinary finding."""


def schema_conformance_findings(
    plugin_manifest_path: pathlib.Path | None = None,
    vendored_schema_path: pathlib.Path | None = None,
) -> list[str]:
    """Every JSON-Schema violation plugin.json has against the vendored
    schema, each prefixed "schema-conformance: " -- empty list means
    plugin.json is a schema-valid Agent Plugins manifest."""
    if plugin_manifest_path is None:
        plugin_manifest_path = PLUGIN_MANIFEST_PATH
    if vendored_schema_path is None:
        vendored_schema_path = VENDORED_SCHEMA_PATH
    instance = _gitapex_schema_validation.load_json_or_raise(plugin_manifest_path, ScanReadError)
    schema = _gitapex_schema_validation.load_json_or_raise(vendored_schema_path, ScanReadError)
    return [
        f"schema-conformance: {message.removeprefix('schema: ')}"
        for message in _gitapex_schema_validation.validate(instance, schema)
    ]


def vendor_digest_drift_findings(vendored_schema_path: pathlib.Path | None = None) -> list[str]:
    """A finding when the vendored schema file's sha256 no longer equals
    VENDORED_SCHEMA_SHA256 -- an accidental hand-edit of the vendored copy,
    or a bumped pin whose digest constant was not updated to match."""
    if vendored_schema_path is None:
        vendored_schema_path = VENDORED_SCHEMA_PATH
    try:
        actual = hashlib.sha256(vendored_schema_path.read_bytes()).hexdigest()
    except OSError as error:
        raise ScanReadError(f"{vendored_schema_path}: cannot be read: {error}") from error
    if actual != VENDORED_SCHEMA_SHA256:
        return [
            f"vendor-digest-drift: {vendored_schema_path.name}: sha256 {actual} does not match the recorded "
            f"{VENDORED_SCHEMA_SHA256} for {VENDORED_SPEC_COMMIT}"
        ]
    return []


def upstream_drift_findings(vendored_schema_path: pathlib.Path | None = None) -> list[str]:
    """Opt-in network check: fetch schemas/1.0.0/plugin.schema.json from
    agentplugins/agent-plugins-spec at VENDORED_SPEC_COMMIT and byte-compare
    against the vendored copy. A fetch failure is itself a finding rather
    than a silent pass -- an unreachable upstream must never read as
    'matches'."""
    if vendored_schema_path is None:
        vendored_schema_path = VENDORED_SCHEMA_PATH
    try:
        with urllib.request.urlopen(_UPSTREAM_RAW_URL, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            upstream_bytes = response.read()
    except (URLError, OSError) as error:
        return [f"upstream-drift: could not fetch {_UPSTREAM_RAW_URL}: {error}"]
    try:
        vendored_bytes = vendored_schema_path.read_bytes()
    except OSError as error:
        raise ScanReadError(f"{vendored_schema_path}: cannot be read: {error}") from error
    if upstream_bytes != vendored_bytes:
        return [
            f"upstream-drift: {vendored_schema_path.name}: vendored bytes differ from "
            f"plugin.schema.json published at {VENDORED_SPEC_COMMIT}"
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--verify-upstream",
        action="store_true",
        help=(
            "Additionally fetch schemas/1.0.0/plugin.schema.json from agentplugins/agent-plugins-spec at "
            f"{VENDORED_SPEC_COMMIT} and compare bytes. Requires network access; run this when bumping the pin."
        ),
    )
    args = parser.parse_args(argv)

    try:
        findings = schema_conformance_findings() + vendor_digest_drift_findings()
        if args.verify_upstream:
            findings += upstream_drift_findings()
    except ScanReadError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    if findings:
        print("plugin manifest schema drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("No plugin manifest schema drift found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
