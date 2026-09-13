"""Mirror gitapex's own skills/agents into OpenCode discovery paths.

Claude Code sessions in this checkout get gitapex's own skills via the
self-referential marketplace (``.claude/hooks/session-start.sh``); OpenCode
has no equivalent, and the repository-root ``skills/`` directory is not on
OpenCode's discovery list (``.opencode/skills/``, ``.claude/skills/``,
``.agents/skills/`` -- see https://opencode.ai/docs/skills/). This script
closes that gap for OpenCode sessions (issue #1812):

- every ``skills/<name>/`` directory carrying a ``SKILL.md`` whose
  frontmatter ``name`` matches the directory is symlinked (relative target,
  so the checkout stays relocatable) into ``.agents/skills/<name>`` -- the
  same directory ``apm install --target opencode`` deploys to. A symlink
  tracks the live working tree, which a released-pin ``apm install
  tvna/gitapex`` copy would not.
- ``agents/review-persona.md`` and ``agents/branch-plan-task.md`` are
  materialized as generated copies under ``.opencode/agents/`` (OpenCode
  derives the agent name from the file name). Copies, not symlinks,
  because ``review-persona.md``'s ``tools: Read, Grep, Glob`` string form
  is rejected by OpenCode at load time (observed via apm's own
  diagnostic); the generated copy carries the equivalent ``permission:``
  mapping instead. The sources under ``agents/`` stay Claude-canonical and
  are never rewritten by this script.

Collision policy: a destination path that already exists as a real file
or directory (e.g. an ``apm install tvna/gitapex --target opencode`` copy
of a released revision) is left untouched -- an explicit install wins
over this working-tree mirror. Only symlinks pointing into this
checkout's own ``skills/`` tree are ever replaced or pruned.

Stdlib only, like ``gitapex_provision_class_b.py``. Fail-soft by contract:
callers (``.opencode/plugins/gitapex-session.js``) must treat a non-zero
exit as advisory, never session-blocking.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

SKILLS_SRC_DIRNAME = "skills"
SKILLS_DST_DIRNAME = Path(".agents") / "skills"
AGENTS_SRC_DIRNAME = "agents"
AGENTS_DST_DIRNAME = Path(".opencode") / "agents"

GENERATED_HEADER = (
    "<!-- GENERATED from {source} by hooks/gitapex_sync_opencode.py "
    "(issue #1812) -- do not edit; re-run the script instead. -->"
)

# review-persona.md's Claude allow-list (tools: Read, Grep, Glob) restated
# as OpenCode's canonical permission mapping. OpenCode allows everything by
# default, so every exfiltration/mutation path outside the read-only
# triple must be denied explicitly to preserve the source file's own
# isolation rationale (prompt-injected review content must have neither an
# exfiltration path nor a mutation path). read/glob/grep/list stay at
# their default (allowed); `list` has no Claude-side counterpart but is
# the OpenCode half of directory reading, which Claude's Read covers.
# `*mcp*` uses OpenCode's own wildcard-pattern permission keys
# (opencode.ai/docs/agents: keys match tool names as wildcards) to deny
# MCP-server-provided tools under any server's naming scheme -- the
# OpenCode half of the source's structural unavailability of
# `mcp__github__*`. No built-in tool name contains "mcp", so nothing
# legitimate is denied.
REVIEW_PERSONA_PERMISSION = {
    "edit": "deny",
    "bash": "deny",
    "task": "deny",
    "webfetch": "deny",
    "websearch": "deny",
    "todowrite": "deny",
    "question": "deny",
    "external_directory": "deny",
    "skill": "deny",
    "lsp": "deny",
    "*mcp*": "deny",
}

# Keys meaningful only to Claude Code's own agent loader. Dropped from the
# generated OpenCode copies (OpenCode ignores unknown frontmatter, but
# carrying a Claude-only allow-list string next to the permission mapping
# that actually enforces it would invite misreading).
CLAUDE_ONLY_FRONTMATTER_KEYS = ("name", "tools", "disallowedTools")

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_FRONTMATTER_FIELD_RE = re.compile(r"^(?P<key>[A-Za-z0-9_-]+)\s*:\s*(?P<value>.*?)\s*$")

# A scalar is emitted bare only when it matches this allowlist: it starts
# with a letter or underscore, and carries nothing but letters, digits,
# underscore, dot and hyphen. An allowlist deliberately, not a denylist of
# "dangerous" characters -- YAML gives meaning to enough indicators (`*`
# alias, `&` anchor, `!` tag, `%` directive, `@` and backtick reserved, the
# flow set `[]{},`, `: ` and ` #`, a leading or trailing space) that any
# denylist is one indicator away from silently emitting a line that will
# not parse, which is the defect this guards (issue #1971). The
# leading-character rule also keeps a bare scalar from being read back as a
# number, and from opening a `---` document marker.
_SAFE_BARE_SCALAR_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_.-]*\Z")

# Matching the allowlist is necessary but not sufficient: these plain
# scalars parse cleanly and are then *resolved* to bool or null rather than
# to the string itself, corrupting a mapping silently with no parse error
# to notice. Compared case-insensitively against a wider list than any one
# parser uses: PyYAML 6.0.3's own resolver takes yes/no/true/false/on/off
# (lower, Capitalized and UPPER only), while YAML 1.1's type repository
# (yaml.org/type/bool.html) also lists y/Y/n/N. OpenCode's own parser is
# unobserved -- this script exists precisely to write files another tool
# reads -- so quote for the widest rule. Over-quoting a key costs nothing;
# under-quoting one turns it into `True`.
_YAML_TYPED_WORDS = frozenset({"y", "n", "yes", "no", "true", "false", "on", "off", "null"})

# The agent/permission table `sync_agents` materializes. A module
# attribute rather than a local, so a test can iterate the value
# production actually uses: transcribing it into a test instead would
# leave a newly added agent covered by nothing, silently.
AGENT_SPECS: tuple[tuple[str, dict[str, str] | None], ...] = (
    ("review-persona.md", REVIEW_PERSONA_PERMISSION),
    ("branch-plan-task.md", None),
)

# Refused outright rather than escaped. Written as a NEGATION of what a
# one-line double-quoted scalar can carry, not as a list of offenders: an
# earlier enumerating form missed U+FFFE, U+FFFF and the lone surrogates,
# which emitted quoted and then raised ``ReaderError`` at load -- the same
# defect class this helper exists to prevent, one codepoint outside the
# list. The allowed set below is PyYAML 6.0.3's own printable class
# minus six characters it accepts that this generator will not. Quoted
# verbatim rather than recalled, because the exact membership is what
# makes this derivation safe to repeat:
#
#   NON_PRINTABLE = [^\x09\x0A\x0D\x20-\x7E\x85\xA0-\uD7FF
#                     \uE000-\uFFFD\U00010000-\U0010ffff]
#
# The first two are the ones a careless re-derivation gets wrong:
#
# - LF and CR: PyYAML lists BOTH as printable. They are excluded here, by
#   this class's own `\x20` floor -- never by PyYAML's. Re-deriving this
#   regex from "PyYAML's printable class" alone would let them back in and
#   re-open the split-line defect this helper exists to prevent.
# - U+0085, U+2028, U+2029: line breaks under YAML 1.1. Measured -- U+0085
#   folds to a space in a value and is rejected in a key; U+2028/U+2029
#   survive a value but are rejected in a key. One rule covers both halves
#   of an entry, so the stricter half sets it.
# - TAB: the one deliberate over-refusal. PyYAML carries it in both
#   positions, but a tab inside a permission key is a mistake worth
#   failing on.
_UNQUOTABLE_RE = re.compile(r"[^\x20-\x7e\xa0-\u2027\u202a-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def _yaml_scalar(text: str) -> str:
    """Render one scalar so a YAML parser reads it back as exactly ``text``.

    Returned byte-identical when it is already safe bare, so ``bash`` stays
    ``bash``; otherwise double-quoted with backslash and ``"`` escaped, so
    ``*mcp*`` becomes ``"*mcp*"``. Raises ``ValueError`` for a scalar this
    generator refuses to put on one line, rather than emitting something
    that would not read back -- ``sync_agents`` turns that into a SKIP
    note, so the script stays fail-soft without ever writing a broken
    file.

    Callers are the permission mapping only, whose keys and values are
    module constants: every input is known at import time, so the refusal
    path is unreachable in production and one bound goes unenforced. A
    YAML *key* may not exceed 1024 characters, quotes included -- measured
    at 1024 (parses) and 1025 (``ScannerError``, raised by the reader, not
    here) -- and the longest key in ``REVIEW_PERSONA_PERMISSION`` above is
    18.
    """
    if _SAFE_BARE_SCALAR_RE.match(text) and text.lower() not in _YAML_TYPED_WORDS:
        return text
    unquotable = _UNQUOTABLE_RE.search(text)
    if unquotable:
        raise ValueError(
            f"scalar {text!r} carries U+{ord(unquotable.group()):04X}, which this generator refuses to emit on one line"
        )
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _split_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Split leading YAML frontmatter into (fields, body). None when the
    file carries no ``---``-delimited block at all."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        field = _FRONTMATTER_FIELD_RE.match(line)
        if field:
            fields[field.group("key")] = field.group("value")
    return fields, text[match.end() :]


def _read_skill_name(skill_md: Path) -> str | None:
    """The frontmatter ``name`` of a SKILL.md, or None when the file has
    no parseable frontmatter name at all."""
    try:
        parsed = _split_frontmatter(skill_md.read_text(encoding="utf-8"))
    # An unreadable SKILL.md means "not a valid skill" -- the caller skips
    # it with a SKIP note printed to stdout, so the None sentinel below is
    # surfaced, never silent.
    except (OSError, UnicodeDecodeError):  # except-fail-open: WAIVED: skip-with-note surfacing (see above)
        return None
    if parsed is None:
        return None
    name = parsed[0].get("name", "").strip().strip("\"'")
    return name or None


def _is_our_symlink(link: Path, skills_src: Path) -> bool:
    """True when ``link`` is a symlink resolving inside ``skills_src`` --
    i.e. a mirror this script owns. A symlink pointing anywhere else
    belongs to someone else and is never touched."""
    if not link.is_symlink():
        return False
    try:
        return skills_src.resolve() in link.resolve().parents or link.resolve() == skills_src.resolve()
    except OSError:
        # A dangling symlink raises on resolve(): still ours when its raw
        # target text points into the skills tree.
        try:
            raw = link.readlink()
        # readlink on an already-proven symlink fails only on races; False
        # treats the link as foreign (left untouched), the safe direction,
        # and every skip/prune decision is printed as a note by the caller.
        except OSError:  # except-fail-open: WAIVED: safe-direction sentinel with note surfacing (see above)
            return False
        return not raw.is_absolute() and SKILLS_SRC_DIRNAME in raw.parts


def sync_skills(project_dir: Path, verify_only: bool, notes: list[str]) -> int:
    """Symlink every valid ``skills/<name>/`` into ``.agents/skills/``.
    Returns the number of changes made (0 in verify_only mode or when
    already in sync)."""
    skills_src = project_dir / SKILLS_SRC_DIRNAME
    skills_dst = project_dir / SKILLS_DST_DIRNAME
    changes = 0
    if not skills_src.is_dir():
        notes.append(f"SKIP: {skills_src} not found (not a gitapex checkout?)")
        return 0
    if not verify_only:
        skills_dst.mkdir(parents=True, exist_ok=True)

    expected: set[str] = set()
    for child in sorted(skills_src.iterdir()):
        if not child.is_dir() or not (child / "SKILL.md").is_file():
            continue
        name = _read_skill_name(child / "SKILL.md")
        if name is None:
            notes.append(f"SKIP: skills/{child.name}/SKILL.md carries no frontmatter name")
            continue
        if name != child.name:
            notes.append(f"SKIP: skills/{child.name}/SKILL.md frontmatter name {name!r} != directory")
            continue
        expected.add(child.name)
        dst = skills_dst / child.name
        want_target = os.path.relpath(child, skills_dst)
        if dst.is_symlink():
            if _is_our_symlink(dst, skills_src) and str(dst.readlink()) == want_target:
                continue
            if not _is_our_symlink(dst, skills_src):
                notes.append(f"SKIP: {dst} is a foreign symlink; left untouched")
                continue
            notes.append(f"REPAIR: stale symlink {dst}")
            if verify_only:
                changes += 1
                continue
            dst.unlink()
        elif dst.exists():
            # A real file/directory -- e.g. an `apm install tvna/gitapex`
            # copy of a released revision. An explicit install wins.
            notes.append(f"SKIP: {dst} exists as a real path (apm-managed?); left untouched")
            continue
        else:
            notes.append(f"LINK: {dst} -> {want_target}")
        if verify_only:
            changes += 1
            continue
        dst.symlink_to(want_target)
        changes += 1

    # Prune only our own dead mirrors: our symlinks whose skill directory
    # went away (rename/retirement). Everything else stays.
    if skills_dst.is_dir():
        for dst in sorted(skills_dst.iterdir()):
            if dst.name in expected:
                continue
            if _is_our_symlink(dst, skills_src):
                notes.append(f"PRUNE: {dst} (source skill gone)")
                if verify_only:
                    changes += 1
                    continue
                # dst is a symlink (proven by _is_our_symlink), so unlink
                # only ever removes the link itself -- never a tree.
                dst.unlink()
                changes += 1
    return changes


def _render_agent_copy(source_text: str, source_rel: str, permission: dict[str, str] | None) -> str:
    """Rebuild an agent definition for OpenCode: keep ``description`` and
    the body verbatim, drop Claude-only frontmatter keys, add
    ``mode: subagent`` + ``hidden: true`` (+ the permission mapping when
    given). The header line records provenance so a hand-edit is never
    mistaken for source."""
    parsed = _split_frontmatter(source_text)
    if parsed is None:
        raise ValueError(f"{source_rel} carries no frontmatter block")
    fields, body = parsed
    if "description" not in fields:
        raise ValueError(f"{source_rel} frontmatter carries no description")
    # The captured scalar is copied through, deliberately, and NOT
    # re-encoded through `_yaml_scalar`: it is already a YAML scalar, so
    # copying it is what makes the two runtimes read the same value.
    # Re-encoding does the opposite -- measured across four description
    # shapes, it diverges for one that is already quoted (double-encoded)
    # and for one a plain scalar truncates (OpenCode would then see more
    # than Claude does).
    #
    # "Copied through", not byte-identical: `_FRONTMATTER_FIELD_RE`
    # normalizes the `key:` separator and strips surrounding whitespace,
    # and its `\s*` is Unicode-wide, so a description led or trailed by
    # U+00A0 (or another non-YAML space) is emitted without it. That is a
    # divergence, not a normalization -- small, pre-existing, and left
    # alone here rather than widened into: the whole point of this line is
    # that the generator does not reinterpret what the source declared.
    #
    # Two adjacent holes are pre-existing and NOT closed here, both on
    # issue #1982: a multi-line description is captured as its first line
    # and the rest is dropped silently, and an empty `permission` mapping
    # emits a bare `permission:` key that reads back as None. Guards for
    # both were written on this branch and reverted -- twice they refused
    # frontmatter the generator handles correctly (a YAML list under a
    # dropped key) or missed the shape they were written for (a `#` inside
    # a block scalar is content, not a comment). They are a defect of this
    # module, not of this change, and they deserve their own diff.
    out = ["---", f"description: {fields['description']}", "mode: subagent", "hidden: true"]
    if permission is not None:
        out.append("permission:")
        for key, value in permission.items():
            out.append(f"  {_yaml_scalar(key)}: {_yaml_scalar(value)}")
    out.append("---")
    out.append(GENERATED_HEADER.format(source=source_rel))
    out.append(body)
    return "\n".join(out)


def sync_agents(project_dir: Path, verify_only: bool, notes: list[str]) -> int:
    """Materialize OpenCode copies of the plugin-distributed agents.
    Returns the number of changes made."""
    agents_src = project_dir / AGENTS_SRC_DIRNAME
    agents_dst = project_dir / AGENTS_DST_DIRNAME
    changes = 0
    for filename, permission in AGENT_SPECS:
        src = agents_src / filename
        if not src.is_file():
            notes.append(f"SKIP: {src} not found")
            continue
        try:
            rendered = _render_agent_copy(
                src.read_text(encoding="utf-8"), f"{AGENTS_SRC_DIRNAME}/{filename}", permission
            )
        except (OSError, UnicodeDecodeError, ValueError) as error:
            notes.append(f"SKIP: {src}: {error}")
            continue
        dst = agents_dst / filename
        # Symlink check first: is_file() follows links, so a non-dangling
        # symlink would otherwise take the REWRITE path below and
        # write_text() would write through the link into whatever it
        # points at (issue #1814 review finding). Mirrors sync_skills.
        if dst.is_symlink():
            notes.append(f"SKIP: {dst} exists in an unexpected form; left untouched")
            continue
        if dst.is_file():
            try:
                current = dst.read_text(encoding="utf-8")
            # None only means "unknown, rewrite" -- the write_text below
            # then surfaces any real I/O error loudly instead of trusting
            # a stale copy.
            except (OSError, UnicodeDecodeError):  # except-fail-open: WAIVED: rewrite-forces-loud-error (see above)
                current = None
            if current == rendered:
                continue
            notes.append(f"REWRITE: {dst}")
        else:
            if dst.exists():
                notes.append(f"SKIP: {dst} exists in an unexpected form; left untouched")
                continue
            notes.append(f"WRITE: {dst}")
        if verify_only:
            changes += 1
            continue
        agents_dst.mkdir(parents=True, exist_ok=True)
        dst.write_text(rendered, encoding="utf-8")
        changes += 1
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument(
        "--verify",
        action="store_true",
        help="report what would change without writing anything; exit non-zero on drift",
    )
    args = parser.parse_args(argv)

    project_dir: Path = args.project_dir
    if not (project_dir / "apm.yml").is_file():
        print(f"FAIL: {project_dir}/apm.yml not found -- refusing outside a gitapex checkout", file=sys.stderr)
        return 1
    notes: list[str] = []
    changes = sync_skills(project_dir, args.verify, notes) + sync_agents(project_dir, args.verify, notes)
    for note in notes:
        print(note)
    if args.verify and changes:
        print(f"DRIFT: {changes} change(s) pending", file=sys.stderr)
        return 1
    print(f"OK: {changes} change(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
