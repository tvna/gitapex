#!/usr/bin/env python3
"""Generate .claude-plugin/plugin.json (the Claude Code/Codex plugin manifest)
from the repository-root plugin.json (the Agent Plugins Specification
(agent-plugins.org) v1.0.0 manifest, and this repository's own
plugin-identity single source of truth as of issue #1028).

Before this script, .claude-plugin/plugin.json was itself the SSOT for the
plugin's name/version/description/author/homepage/repository/license, hand-
edited directly (see docs/repository-layout.md, docs/versioning.md, and
.github/scripts/gitapex_scan_apm_manifest_drift.py -- that script's own drift
check against apm.yml is unchanged by this migration, see its module
docstring). The Agent Plugins Specification's plugin.schema.json requires a
$schema key and imposes its own field constraints that
.claude-plugin/plugin.json, as a Claude-Code-specific manifest format, does
not carry and must not gain -- so the two files cannot simply be the same
file. Instead, the repository-root plugin.json is now hand-edited, and
.claude-plugin/plugin.json is mechanically regenerated from it: identical
content, minus the $schema key, in the same key order the source declares.

Two modes, matching the .github/scripts/gitapex_generate_skill_eval_status.py
precedent this is modeled on:

- Default (no flags): regenerate and overwrite .claude-plugin/plugin.json.
- --check: regenerate in memory and diff against the committed file; exit 1
  on any difference, 0 if byte-identical. This is what
  tests/test_gitapex_generate_plugin_manifest.py's final test calls, so a
  hand-edit to .claude-plugin/plugin.json (or a stale committed copy after
  plugin.json changed) fails CI rather than silently drifting.

Deliberately NOT attempted here: validating plugin.json's shape against the
upstream plugin.schema.json -- that is a separate concern, covered by
gitapex_scan_plugin_manifest_schema.py. This script trusts plugin.json is a
JSON object with a $schema key to strip and does no further inspection.

ACTIVE (issue #1028): enforced via the pytest gate in
tests/test_gitapex_generate_plugin_manifest.py -- no dedicated CI workflow
step, the same established convention as
gitapex_generate_skill_eval_status.py and this repository's other
scanner-shaped gates.
"""

# Not folded into the module docstring above: `argparse.ArgumentParser` below
# is constructed with `description=__doc__, formatter_class=RawDescriptionHelpFormatter`,
# so anything added there changes real `--help` output -- the exact thing
# waves 1-3 of #1040's batch confirmed byte-identical before/after as their
# own proof method. Kept as a plain comment instead so that guarantee still
# holds for this wave.
#
# Issue #1071 (wave 4 of #1040's batch pydantic CLI-arg validation rollout):
# `main`'s parsed namespace is now passed through `GeneratePluginManifestArgs`
# immediately after `parser.parse_args(argv)`, matching the wrap already
# applied in waves 1-3. `check` (`action="store_true"`) has no constraint
# beyond the `bool` shape `argparse` already guarantees, so construction can
# currently never raise `ValidationError` for a real CLI invocation; the
# model exists for consistency with #1040's repo-wide convention (a typed
# seam between `parse_args` and business logic). This script's own
# production invocation is exercised in-process by pytest (see the module
# docstring's ACTIVE note above), not a separate bare-`python3` workflow
# step, so the added `pydantic` import needs no `uv run` prefix of its own
# to be safe.

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from pydantic import BaseModel, ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE_PATH = REPO_ROOT / "plugin.json"
OUTPUT_PATH = REPO_ROOT / ".claude-plugin" / "plugin.json"

_STRIPPED_KEY = "$schema"


class GenerationError(Exception):
    """A checked-in input this generator depends on (the root plugin.json
    source or, in --check mode, the committed .claude-plugin/plugin.json
    output) could not be read as UTF-8 text, or the source did not parse as
    a JSON object -- exit 1 with a clear message, never an uncaught
    traceback."""


def _read_utf8_text(path: pathlib.Path) -> str:
    """Read `path` as UTF-8 text, or raise GenerationError naming `path`
    and the failure -- the one read boundary both the source read (in
    generate()) and the --check-mode committed-output read (in main()) go
    through, mirroring gitapex_generate_skill_eval_status.py's own
    _read_utf8_text so the two do not carry independently-drifting copies
    of the same OSError/UnicodeDecodeError handling."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise GenerationError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise GenerationError(f"{path}: is not valid UTF-8: {error}") from error


def strip_schema_key(source_text: str, source_path: pathlib.Path | None = None) -> dict[str, object]:
    """Parse `source_text` as a JSON object and return a copy with the
    top-level $schema key removed, preserving every other key's original
    order -- json.loads already preserves source key order in the returned
    dict, so no explicit reordering is needed. Raises GenerationError
    (naming `source_path`, used only for the error message) if the text is
    not valid JSON, or is valid JSON that is not a top-level object.
    `source_path` defaults to None, resolved to the current module-level
    SOURCE_PATH inside the body rather than as the parameter's own default
    value -- mirrors generate()'s own reasoning: a default value is bound
    once at function-definition time, so `= SOURCE_PATH` here would freeze
    in the *original* path forever and silently ignore a test's own
    monkeypatch.setattr override."""
    source_path = SOURCE_PATH if source_path is None else source_path
    try:
        data = json.loads(source_text)
    except json.JSONDecodeError as error:
        raise GenerationError(f"{source_path}: is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise GenerationError(f"{source_path}: must be a JSON object, got {type(data).__name__}")
    return {key: value for key, value in data.items() if key != _STRIPPED_KEY}


def render_mirror(mirror_data: dict[str, object]) -> str:
    """The exact text to write to .claude-plugin/plugin.json: 2-space
    indent, a trailing newline -- matches the committed file's existing
    formatting convention exactly."""
    return json.dumps(mirror_data, indent=2, ensure_ascii=False) + "\n"


def generate(source_path: pathlib.Path | None = None) -> str:
    """The full rendered .claude-plugin/plugin.json content: the
    repository-root plugin.json, $schema stripped, re-serialized with a
    trailing newline. `source_path` defaults to None, resolved to the
    current module-level SOURCE_PATH inside the body rather than as the
    parameter's own default value -- a default value is bound once at
    function-definition time, so `= SOURCE_PATH` here would freeze in the
    *original* path forever and silently ignore a test's own
    monkeypatch.setattr override."""
    source_path = SOURCE_PATH if source_path is None else source_path
    source_text = _read_utf8_text(source_path)
    mirror_data = strip_schema_key(source_text, source_path)
    return render_mirror(mirror_data)


class GeneratePluginManifestArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace (issue #1071). See the
    module docstring's own issue #1071 section for why `check` carries no
    additional field validator."""

    check: bool = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate in memory and diff against the committed .claude-plugin/plugin.json; exit 1 on drift.",
    )
    args = parser.parse_args(argv)

    try:
        validated = GeneratePluginManifestArgs(check=args.check)
    except ValidationError:
        print("FAIL: invalid CLI arguments", file=sys.stderr)
        return 2

    try:
        rendered = generate()
    except GenerationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    if validated.check:
        try:
            committed = _read_utf8_text(OUTPUT_PATH)
        except GenerationError as error:
            print(f"FAIL: {error}", file=sys.stderr)
            return 1
        if rendered != committed:
            rendered_lines = rendered.splitlines()
            committed_lines = committed.splitlines()
            first_diff = next(
                (
                    index
                    for index in range(max(len(rendered_lines), len(committed_lines)))
                    if (rendered_lines[index] if index < len(rendered_lines) else None)
                    != (committed_lines[index] if index < len(committed_lines) else None)
                ),
                0,
            )
            print(
                f"FAIL: {OUTPUT_PATH} is stale -- a fresh regeneration differs "
                f"starting at line {first_diff + 1}. Re-run without --check to "
                "regenerate, then commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"PASS: {OUTPUT_PATH} matches a fresh regeneration")
        return 0

    try:
        OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    except OSError as error:
        print(f"FAIL: {OUTPUT_PATH}: cannot be written: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
