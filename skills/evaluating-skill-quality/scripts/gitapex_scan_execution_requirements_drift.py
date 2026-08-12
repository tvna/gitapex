#!/usr/bin/env python3
"""Cross-check a skill's declared spec.executionRequirements against real
SKILL.md prose and bundled scripts/*.py content (issue #1022).

Bundled with the evaluating-skill-quality skill itself, alongside its
read-only shape checker (gitapex_check_skill_shape.py) -- run the same
way, against one target skill directory at a time, as part of that
skill's "Deterministic shape" lane (see SKILL.md's Two lanes section).
skills/evaluating-skill-quality/references/skill-metadata.schema.json
validates executionRequirements' SHAPE only; this scanner cross-checks
one skill's own declared network mode/domains and tools write/shell tags
against what its own content actually does.

Two independent checks, one per executionRequirements sub-block, that
differ in kind, not just in what they check -- a distinction worth
stating explicitly rather than lumping both under one "best-effort"
label (a distinction a live design discussion on issue #1022 surfaced,
including primary-source research into whether a dynamic/DAST-style
approach could replace either: Python's own sys.addaudithook (PEP 578)
docs state plainly it is "not suitable for implementing a 'sandbox'"
and requires the target code to actually execute to fire, and
established DAST tooling targets a *running* application's own HTTP/UI
surface, neither of which fits a read-only pre-execution checker that
must never itself run a skill's bundled scripts):

- find_network_drift: declared network.mode/domains vs. network-capable
  imports and literal https?:// hosts found in skill_dir/scripts/*.py --
  DETERMINISTIC, via Python's own ast module (stdlib), not a text regex.
  A real parse tree has no comment nodes at all, so a commented-out
  reference can never register as usage without a filter having to say
  so; import resolution checks the exact dotted module path Python
  itself would resolve ("import X", "import X.Y", and "from X import Y"
  are each handled on their own real shape, not approximated by one
  regex trying to cover all three). Still a net, not a formal proof of
  runtime behavior -- see the Residual limitations paragraph below for
  what AST parsing does not and structurally cannot close.
- find_tools_drift: declared tools.write/tools.shell vs. TWO independent
  evidence sources, checked separately (see test_gitapex_scan_
  execution_requirements_drift.py's own test names for the exact split):
  DETERMINISTIC via AST for a bundled script's own real file-write or
  subprocess/shell call ("-vs-script-content", same precision level as
  find_network_drift's own import/host detection), and BEST-EFFORT
  PATTERN-MATCH, irreducibly so, for mutating-action/shell-invocation
  language anywhere in skill_dir/SKILL.md's full text
  ("-vs-skill-md"): SKILL.md is natural-language prose describing what
  the *invoking agent* should do, not code, so there is no parser that
  resolves "does this English sentence describe a mutating action" the
  way ast.parse resolves a file-write call. This split matters beyond
  precision: "skill itself" behavior (an agent following SKILL.md prose)
  and "script" behavior (a bundled script's own code) are genuinely
  different capability sources -- a design discussion on issue #1022
  additionally researched whether the agent-tool-control side could be
  checked against the Agent Skills standard's own `allowed-tools`
  frontmatter field instead of staying prose-only, and found (via this
  skill's own already-cited runtime-compatibility.md, itself grounded in
  each runtime's official docs) that `allowed-tools`' enforcement
  semantics are not even consistent across runtimes to check against:
  Claude Code and GitHub Copilot document it as pre-approval only (not a
  restriction -- an unlisted tool still just prompts, never blocks),
  Devin documents the opposite (`allowed-tools` restricts to only the
  listed tools), and most other surveyed runtimes leave it Unknown/
  undocumented entirely. With no stable, portable enforcement semantics
  to validate against, SKILL.md prose matching remains the only
  tractable proxy for the "skill itself" (agent-facing) side. Deliberately
  NOT anchored to a single "Procedure" heading either: the heading name
  varies across real skills (Steps, Procedure, Exact sequence, Checklist,
  ...), so anchoring on one would blind the scanner on most of them.
  tools.read is not checked -- only write/shell are the safety-relevant
  under-declaration direction.

Each finding carries a severity: "error" for under-declaration (declared
narrower than actual) or "warning" for over-declaration (declared broader
than actual content ever exercises -- a hygiene finding, never failing a
run on its own).

Residual limitations, even in find_network_drift's deterministic half:
determinism means "the same input always parses to the same finding,"
not "every real network call is caught." A call routed through an
unlisted helper function, a host built at runtime (string
concatenation, an f-string with a non-literal segment), or a network
call gated behind a condition that never actually triggers can still
slip past AST analysis exactly as it would past a human reading the
same source -- these are facts about what static analysis can see, not
a defect in using ast over regex (see
test_dynamically_constructed_host_evades_allowlist_check for one
deliberately-constructed example). find_tools_drift's own natural-
language matching carries the same class of gap for the same reason
prose has no parser.

Language scope: find_network_drift only reads skill_dir/scripts/*.py --
a bundled non-Python script (a .sh file, for instance; this repository's
own skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh is
one real example) is invisible to it, network-capable shell commands
(curl, wget, nc, ...) included. This matters beyond this one repository:
evaluating-skill-quality itself travels as a portable skill (see its own
spec.portability), so a consuming repository's own skills may bundle
scripts in other languages this scanner was never taught to read. Not
fixed here -- see test_non_python_bundled_scripts_are_not_scanned for a
concrete, deliberately-constructed proof of the gap, not only this
paragraph's claim.

Not registered in .gitapex/ssot.json, matching gitapex_check_skill_shape.py's
own un-registered status: a per-skill checker invoked deliberately against
one target at a time is not the shape of a repo-wide automatic gate. A
live run against this repository's own skills/ tree reports real findings
issue #1022's own Non-goals excludes retroactively fixing here -- this
module's own fixture-based unit tests are what CI enforces.

Self-contained, stdlib + PyYAML only, no cross-import from any other
.github/scripts/*.py file -- the skill directory discovery and
sidecar-read helpers below intentionally duplicate
gitapex_scan_skill_metadata_schema.py's own small versions.

Run standalone against one skill directory --
``python3 skills/evaluating-skill-quality/scripts/
gitapex_scan_execution_requirements_drift.py <skill-dir>`` (exit 0 clean or
warnings-only, 1 on any error-severity finding or a read error) -- or via
the pytest gate in skills/evaluating-skill-quality/scripts/
test_gitapex_scan_execution_requirements_drift.py.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys
import urllib.parse
from typing import Any, NamedTuple

import yaml

# This file lives at skills/evaluating-skill-quality/scripts/<name>.py, so
# parents[2] is skills/ itself -- one level deeper than a .github/scripts/
# script's own parents[2] (repo root), since this module moved into the
# evaluating-skill-quality skill's own scripts/ bundle rather than staying
# a repo-root-level CI script.
SKILLS_DIR = pathlib.Path(__file__).resolve().parents[2]
# Mirrors gitapex_scan_skill_metadata_schema.py's own SIDECAR_RELATIVE_PATH
# constant, duplicated as a literal rather than imported (see module
# docstring's own no-cross-import constraint).
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"
# Same vacuous-pass guard and reasoning as gitapex_scan_skill_metadata_schema.py's
# own MIN_EXPECTED_SKILL_DIRS: a wrong or missing skills_dir must read as a
# finding, never as silent "no drift."
MIN_EXPECTED_SKILL_DIRS = 15

NETWORK_CAPABLE_MODULES = (  # modules whose import signals real network I/O capability
    # Bare "urllib" also matches pure-parsing submodules with no network
    # I/O of their own (urllib.parse) -- only the two network-capable
    # submodules are listed. Exact dotted-path membership (below), not a
    # prefix regex, decides a match, so this stays precise regardless of
    # import shape (`import X`, `import X.Y`, or `from X import Y`).
    "urllib.request",
    "urllib.error",
    "requests",
    "http.client",
    "socket",
    "ftplib",
    "smtplib",
    "xmlrpc",
    "httpx",
    "aiohttp",
)
# Matches the whole authority+path+query "rest of the URL" up to a
# character that could never legally be part of one in source text (real
# whitespace, a quote closing the string literal, or Markdown/HTML
# wrapping) -- deliberately broad, not a hand-rolled hostname character
# class. A prior version restricted the captured group to
# [A-Za-z0-9.-] and silently truncated at the first character outside
# that set (e.g. an underscore), so "https://internal_evilhost.attacker.com"
# matched only "internal" -- exactly the allowlisted-looking prefix an
# attacker would choose, defeating the allowlist check entirely. Real host
# extraction is delegated to urllib.parse.urlsplit below instead, the same
# stdlib parser Python's own networking code uses, rather than a second
# hand-rolled character class that could suffer the identical bug for a
# different character.
_URL_LITERAL_PATTERN = re.compile(r"https?://[^\s\"'<>)]+")


def _dotted_name_matches(dotted_name: str, target_modules: tuple[str, ...]) -> bool:
    """Whether ``dotted_name`` names one of ``target_modules`` or a
    submodule of one (e.g. "requests.exceptions" via "requests", or
    "os.path" via "os"), but never the reverse ("requests" alone does not
    match "requests.get" as a module name -- module names and call
    expressions are different things)."""
    return any(dotted_name == m or dotted_name.startswith(m + ".") for m in target_modules)


def _is_network_capable_module(dotted_name: str) -> bool:
    """Whether ``dotted_name`` names a recognized network-capable module or
    a submodule of one."""
    return _dotted_name_matches(dotted_name, NETWORK_CAPABLE_MODULES)


def _tree_has_network_import(tree: ast.AST) -> bool:
    """AST-based, not regex-over-text: a real parse tree has no comment
    nodes at all (a "# import requests" comment can never appear here),
    and precisely resolves every import shape -- "import X", "import X.Y",
    "from X import Y" (checked as both "X" itself and "X.Y", since Y may
    be a network-capable submodule of X, e.g. "from urllib import
    request") -- rather than a regex anchored on one textual shape."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(_is_network_capable_module(alias.name) for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module:
            candidates = (node.module, *(f"{node.module}.{alias.name}" for alias in node.names))
            if any(_is_network_capable_module(c) for c in candidates):
                return True
    return False


def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    """id() of every ast.Constant node that is a module/class/function
    docstring (a bare string expression as the first statement of that
    node's own body) -- used to exclude documentation/citation text from
    network-host detection. A doc citation like "see
    <https://code.claude.com/docs/en/hooks>" is exactly as much "not code"
    from a network-usage standpoint as a comment is, but ast.Constant does
    not distinguish a docstring from an ordinary string literal on its own;
    this walk identifies docstrings the same deterministic way
    ast.get_docstring does, by body-position, rather than guessing from
    content."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _tree_referenced_hosts(tree: ast.AST) -> set[str]:
    """Every https?://host referenced inside a real string literal constant
    anywhere in the parse tree (f-string literal segments included, module/
    class/function docstrings excluded via _docstring_constant_ids -- a
    comment can never appear here at all, unlike the prior regex-over-raw-
    text version, which needed an explicit comment-line filter to exclude
    it). The host itself is extracted with urllib.parse.urlsplit rather
    than a hand-rolled character class, so a userinfo prefix or port
    suffix is stripped correctly and no character silently truncates the
    match (see _URL_LITERAL_PATTERN's own comment)."""
    docstring_ids = _docstring_constant_ids(tree)
    hosts: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_ids:
            for literal in _URL_LITERAL_PATTERN.findall(node.value):
                hostname = urllib.parse.urlsplit(literal).hostname
                if hostname:
                    hosts.add(hostname.lower())
    return hosts


# Qualified as "module.function", resolved against each tree's own real
# import aliases (see _module_aliases/_resolve_call_target) rather than
# matched on a bare attribute name like "run" or "write" -- both are
# extremely common method names on unrelated objects (a test runner, a
# workflow class, a logger), so matching the name alone without confirming
# the receiver actually resolves to subprocess/os/shutil would be a severe
# false-positive source, not the kind of precision this module's own
# network-import detection already holds itself to.
_SHELL_INVOKING_CALLS = frozenset(
    {
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "subprocess.getoutput",
        "subprocess.getstatusoutput",
        "os.system",
        "os.popen",
        "os.execl",
        "os.execle",
        "os.execlp",
        "os.execlpe",
        "os.execv",
        "os.execve",
        "os.execvp",
        "os.execvpe",
        "os.spawnl",
        "os.spawnle",
        "os.spawnlp",
        "os.spawnv",
        "os.spawnve",
        "os.spawnvp",
        "os.posix_spawn",
        "os.posix_spawnp",
    }
)
_FILE_MUTATING_CALLS = frozenset(
    {
        "os.remove",
        "os.unlink",
        "os.rename",
        "os.renames",
        "os.replace",
        "os.mkdir",
        "os.makedirs",
        "os.rmdir",
        "os.removedirs",
        "os.chmod",
        "os.truncate",
        "os.ftruncate",
        "os.mkfifo",
        "os.mknod",
        "os.chown",
        "os.lchown",
        "os.symlink",
        "os.link",
        "shutil.copy",
        "shutil.copy2",
        "shutil.copyfile",
        "shutil.copytree",
        "shutil.move",
        "shutil.rmtree",
        "shutil.chown",
    }
)
# pathlib.Path's own write methods, matched by method name alone (no
# receiver-type inference -- the same disclosed precision level as
# _tree_referenced_hosts' bare string-literal matching, not full type
# checking), since a bound Path variable's own origin is not staticized
# by a plain ast.walk the way an imported module's origin is.
_PATH_WRITE_METHOD_NAMES = frozenset(
    {
        "write_text",
        "write_bytes",
        "unlink",
        "rmdir",
        "mkdir",
        "touch",
        "rename",
        "replace",
        "symlink_to",
        "hardlink_to",
        "chmod",
        "lchmod",
    }
)


def _module_aliases(tree: ast.AST, target_modules: tuple[str, ...]) -> dict[str, set[str]]:
    """Maps each local name this module's own code actually uses back to
    every real dotted origin it could resolve to for one of
    ``target_modules`` (or a submodule of one) -- "import subprocess as
    sp" -> {"sp": {"subprocess"}}, "from os import system" -> {"system":
    {"os.system"}}, a plain unaliased "import os.path" -> {"os": {"os"}}
    (Python itself binds the local name "os", the top-level package, not
    "os.path", when no "as" clause is given -- ``os.system(...)`` after
    "import os.path" is ordinary, valid code).

    A SET of origins per local name, not a single value: ast.walk has no
    scope awareness, so a name reused across independent function scopes
    (e.g. "sp" imported as "subprocess" in one function and later as "os"
    in an unrelated one) must not let the later import silently erase the
    earlier real one in a flat dict -- either origin resolving to a
    tracked capability is genuine evidence of that capability, not just
    whichever import this walk happened to see last."""
    aliases: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    local_name, origin = alias.asname, alias.name
                else:
                    local_name = origin = alias.name.split(".")[0]
                if _dotted_name_matches(origin, target_modules):
                    aliases.setdefault(local_name, set()).add(origin)
        elif isinstance(node, ast.ImportFrom) and node.module and _dotted_name_matches(node.module, target_modules):
            for alias in node.names:
                aliases.setdefault(alias.asname or alias.name, set()).add(f"{node.module}.{alias.name}")
    return aliases


def _resolve_call_targets(node: ast.Call, aliases: dict[str, set[str]]) -> set[str]:
    """Every real "module.function" ``node`` could resolve to, per
    ``aliases`` -- empty if it cannot be resolved this way at all (e.g. a
    call through an attribute chain deeper than one level, or a name never
    imported from one of the tracked modules) -- never guessed."""
    func = node.func
    if isinstance(func, ast.Name):
        return aliases.get(func.id, set())
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        bases = aliases.get(func.value.id)
        if bases:
            return {f"{base}.{func.attr}" for base in bases}
    return set()


def _open_call_is_write(node: ast.Call) -> bool:
    """Whether a call to the builtin ``open`` names a write-capable mode
    ("w", "a", "x", or "+" anywhere in it) via a literal string -- the
    positional ``mode`` argument or the ``mode=`` keyword. A missing mode
    defaults to "r" (read); a non-literal (dynamically constructed) mode
    cannot be resolved and is not flagged -- the same disclosed
    false-negative class as a runtime-constructed network host."""
    mode: str | None = None
    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
        mode = node.args[1].value
    else:
        for keyword in node.keywords:
            if (
                keyword.arg == "mode"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                mode = keyword.value.value
    return mode is not None and any(flag in mode for flag in "wax+")


def _tree_has_shell_invocation(tree: ast.AST) -> bool:
    """Whether the tree calls a real subprocess/os shell-invocation
    function, resolved via each call's own actual import alias (see
    _module_aliases) rather than matched on a bare method name."""
    aliases = _module_aliases(tree, ("subprocess", "os"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _resolve_call_targets(node, aliases) & _SHELL_INVOKING_CALLS:
            return True
    return False


def _tree_has_file_write(tree: ast.AST) -> bool:
    """Whether the tree calls a real file-mutating os/shutil function
    (resolved via import alias), a pathlib write method (by method name),
    or ``open`` with a write-capable literal mode."""
    aliases = _module_aliases(tree, ("os", "shutil"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _resolve_call_targets(node, aliases) & _FILE_MUTATING_CALLS:
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in _PATH_WRITE_METHOD_NAMES:
            return True
        if isinstance(node.func, ast.Name) and node.func.id == "open" and _open_call_is_write(node):
            return True
    return False


_WRITE_VERBS = r"(?:writes?|wrote|creates?|drafts?|edits?|updates?|modifies|generates?|authors?)"
# A single trailing \b (not one per alternative) applies to whichever
# alternative matched -- otherwise a no-\b alternative matches as a bare
# prefix of an unrelated word (e.g. "commit" inside "committee").
_WRITE_NOUNS = r"(?:file|SKILL\.md|script|\.py|\.md|\.ya?ml|\.json|branch|commit|PR|pull request|issue|document)\b"
_WRITE_INTENT_PATTERN = re.compile(
    rf"\b{_WRITE_VERBS}\b(?:\s+\S+){{0,4}}\s+{_WRITE_NOUNS}",
    re.IGNORECASE,
)
# Three alternations, not one \b-wrapped group: \b demands a word/non-word
# transition, and a backtick is itself non-word, so a backtick-prefixed
# alternative wrapped in a leading \b can never match right after ordinary
# Markdown whitespace/punctuation. The backtick-prefixed alternatives below
# need no \b: matching the backtick itself already anchors the position.
_SHELL_INTENT_PATTERN = re.compile(
    r"\b(?:Bash tool|shell command|subprocess|CLI)\b"
    r"|run\s+`"
    r"|`(?:git (?:commit|push|merge|rebase|checkout)|python3 |uv run|npm )",
    re.IGNORECASE,
)


class Finding(NamedTuple):
    """One drift finding. severity is "error" (under-declared -- the
    safety-relevant direction) or "warning" (over-declared -- a hygiene
    finding, never failing a run on its own). kind is "deterministic" (an
    AST-parsed fact -- a real import, call, or file read/parse outcome) or
    "heuristic" (SKILL.md natural-language pattern matching, irreducibly
    best-effort -- see module docstring). The module docstring's own claim
    that the two checks "differ in kind, not just in what they check" was
    previously only prose, recoverable (if at all) by parsing a substring
    out of message's own check_id prefix; this field carries that
    distinction into the data a caller actually consumes."""

    severity: str
    kind: str
    message: str


class ReadError(Exception):
    """A sidecar could not be read as UTF-8 text or parsed as YAML at all --
    exit 1, never a traceback."""


def discover_skill_dirs(skills_dir: pathlib.Path = SKILLS_DIR) -> list[pathlib.Path]:
    """Every skills/<name>/ directory with a real SKILL.md, sorted -- same
    discovery rule as gitapex_scan_skill_metadata_schema.py's own
    discover_skill_dirs, duplicated rather than imported."""
    if not skills_dir.is_dir():
        return []
    return sorted(p.parent for p in skills_dir.glob("*/SKILL.md") if p.is_file())


def _load_sidecar(path: pathlib.Path) -> Any:
    """Read and YAML-parse ``path``. Raises ReadError rather than letting a
    non-UTF-8 file, invalid YAML syntax, or pathologically deep nesting
    surface as an uncaught exception. RecursionError is caught alongside
    yaml.YAMLError, not folded into the same except clause -- it is not a
    YAMLError subclass, so a deeply nested sidecar (e.g. thousands of
    nested "[" flow-sequence levels) would otherwise propagate straight out
    of this function uncaught, crashing the whole scan instead of
    reporting one clean finding -- the same bug this module's own sibling,
    gitapex_scan_skill_metadata_schema.py's load_sidecar, already fixed
    (found there by an earlier adversarial review); this duplicated copy
    had not carried that fix forward until now."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReadError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise ReadError(f"{path}: is not valid UTF-8: {error}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ReadError(f"{path}: is not valid YAML: {error}") from error
    except RecursionError as error:
        raise ReadError(f"{path}: is too deeply nested to parse: {error}") from error


def _read_text_best_effort(path: pathlib.Path) -> str:
    """Read ``path`` as UTF-8 text, or "" if it cannot be read/decoded --
    a single unreadable script/SKILL.md must not crash the whole scan; an
    empty string simply contributes no pattern matches."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _bundled_script_trees(skill_dir: pathlib.Path) -> tuple[list[ast.AST], list[str]]:
    """Every skill_dir/scripts/*.py file that is not the skill's own test
    suite, parsed. Test files (pytest's own "test_*.py" discovery
    convention, the one this repository's own scripts actually use) are
    excluded -- a script's unit tests legitimately construct test-double
    URLs, mocked subprocess calls, and similar test-only content that is
    not the skill's own shipped capability; including them misattributes
    that content as real drift (found live against this repository's own
    skills/setup-gitapex-toolchain and skills/drafting-an-adr, each
    reporting a finding whose only real source was its own test file, not
    its implementation script).

    Returns (trees, unreadable_or_unparseable_names): a file that cannot
    even be read (a permission error, or content that is not valid UTF-8)
    or that is not valid Python (SyntaxError) is excluded from trees and
    its name collected separately, rather than either crashing the scan or
    silently treating it as clean -- the caller turns that list into its
    own finding (dimension 15: an inability to verify is a deny, not an
    assume-clean). A prior version routed the read through a helper that
    swallowed OSError/UnicodeDecodeError into an empty string, which
    ast.parse("") accepts as a valid, empty module -- silently scoring an
    unreadable script as having no network/write/shell signal at all,
    exactly the assume-clean outcome this function's own docstring says it
    refuses to produce; reading directly here closes that gap."""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return [], []
    trees: list[ast.AST] = []
    unparseable: list[str] = []
    for path in sorted(scripts_dir.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unparseable.append(path.name)
            continue
        try:
            trees.append(ast.parse(text, filename=str(path)))
        except SyntaxError:
            unparseable.append(path.name)
    return trees, unparseable


def find_network_drift(
    network: Any,
    skill_dir: pathlib.Path,
    _scripts: tuple[list[ast.AST], list[str]] | None = None,
) -> list[Finding]:
    """network-mode-vs-script-content: declared executionRequirements.network
    vs. network-capable imports/literal https?:// hosts found in
    skill_dir/scripts/*.py, via AST parsing (deterministic -- see module
    docstring's own Language scope / Determinism note).

    ``_scripts``, if given, is a pre-computed ``_bundled_script_trees(skill_dir)``
    result -- an internal parameter, not part of this function's stable
    two-argument contract (every existing caller and test keeps working
    unchanged): find_skill_drift parses skill_dir/scripts/*.py once and
    passes the same result to both find_network_drift and
    find_tools_drift, instead of each independently re-reading and
    re-parsing every bundled script from disk."""
    mode_value = network.get("mode") if isinstance(network, dict) else None
    # dict.get(key, default) only substitutes on an ABSENT key -- a real
    # `mode: null` or an unrecognized/mis-cased string must not slip
    # through unmatched by any branch below. Any value outside the three
    # recognized modes falls back to "disabled", the strictest treatment,
    # matching an absent network block's own equivalence to disabled.
    mode = mode_value if mode_value in ("disabled", "allowlist", "unrestricted") else "disabled"
    domains = network.get("domains") if isinstance(network, dict) else None
    # Hostnames are case-insensitive (RFC 4343); lower-cased here so the
    # allowlist set-difference below compares like-for-like.
    declared_domains = {d.lower() for d in domains if isinstance(d, str)} if isinstance(domains, list) else set()

    trees, unparseable = _scripts if _scripts is not None else _bundled_script_trees(skill_dir)
    has_network_import = any(_tree_has_network_import(tree) for tree in trees)
    referenced_hosts: set[str] = set()
    for tree in trees:
        referenced_hosts.update(_tree_referenced_hosts(tree))

    findings: list[Finding] = [
        Finding(
            "error",
            "deterministic",
            f"network-script-unparseable: scripts/{name} could not be read "
            "or parsed as valid Python -- could not be analyzed for "
            "network-capable usage, treated as undetermined rather than "
            "clean",
        )
        for name in unparseable
    ]
    if mode == "disabled" and (has_network_import or referenced_hosts):
        findings.append(
            Finding(
                "error",
                "deterministic",
                "network-mode-vs-script-content: declared network.mode "
                f"{mode_value!r} (absent or unrecognized values are treated "
                "as 'disabled') but bundled scripts show network-capable "
                "usage",
            )
        )
    elif mode == "allowlist":
        for host in sorted(referenced_hosts - declared_domains):
            findings.append(
                Finding(
                    "error",
                    "deterministic",
                    "network-mode-vs-script-content: bundled scripts reference "
                    f"host {host!r} not present in declared allowlist domains "
                    f"{sorted(declared_domains)}",
                )
            )
    elif mode == "unrestricted" and not has_network_import and not referenced_hosts:
        findings.append(
            Finding(
                "warning",
                "deterministic",
                "network-mode-vs-script-content: declared network.mode "
                "'unrestricted' but no bundled script shows network-capable "
                "usage (over-declared)",
            )
        )
    return findings


def _under_declared_or_none(declared: bool, signal: bool, check_id: str, evidence: str, kind: str) -> Finding | None:
    """Under-declaration is checked per evidence source, independently:
    either source alone (prose OR script) proves real usage regardless of
    what the other source shows, so a positive signal from just one of
    them is already a genuine finding."""
    if not declared and signal:
        return Finding("error", kind, f"{check_id}: {evidence}")
    return None


def _over_declared_or_none(declared: bool, prose_signal: bool, script_signal: bool, tag: str) -> Finding | None:
    """Over-declaration is checked JOINTLY across both evidence sources,
    unlike under-declaration: a declared capability is legitimate if
    EITHER source justifies it (a skill can validly declare tools.write
    purely because its own SKILL.md prose instructs the invoking agent to
    write files, with zero bundled scripts ever doing so directly, or the
    reverse) -- so this must not fire just because one source alone shows
    nothing; only when neither does. Tagged "heuristic": even though the
    script-content half of this joint check is deterministic, the finding
    as a whole rests on the prose signal's own absence, which -- like any
    negative from a natural-language heuristic -- is weaker evidence than
    a positive; a warning only, never blocking a run."""
    if declared and not prose_signal and not script_signal:
        return Finding(
            "warning",
            "heuristic",
            f"tools-{tag}-over-declared: declared executionRequirements.tools.{tag} but neither "
            "SKILL.md prose nor any bundled script's own code shows matching "
            f"{tag} usage (over-declared)",
        )
    return None


def find_tools_drift(
    tools: Any,
    skill_dir: pathlib.Path,
    _scripts: tuple[list[ast.AST], list[str]] | None = None,
) -> list[Finding]:
    """tools-write/tools-shell drift, checked against two independent
    evidence sources per tag (see module docstring's own "skill itself"
    vs. "script" distinction):

    - "-vs-skill-md": mutating-action/shell-invocation language anywhere
      in skill_dir/SKILL.md's full text -- irreducibly a best-effort
      natural-language heuristic (see module docstring).
    - "-vs-script-content": a real file-write or subprocess/shell call in
      skill_dir/scripts/*.py, via AST (deterministic, same precision
      level as find_network_drift's own import/host detection).

    Under-declaration is graded independently per source (either alone is
    real evidence); over-declaration is graded jointly across both (see
    _over_declared_or_none) -- a declared capability backed by only one
    of the two sources is not over-declared. tools.read is not checked --
    only write/shell are the safety-relevant under-declaration direction.
    A script that fails to parse is silently excluded from the
    script-content signal here (not double-reported): find_network_drift
    already surfaces it as its own network-script-unparseable finding
    when both run together via find_skill_drift.

    ``_scripts`` mirrors find_network_drift's own internal parameter of
    the same name -- a pre-computed ``_bundled_script_trees(skill_dir)``
    result, not part of the stable two-argument contract."""
    write_tags = tools.get("write") if isinstance(tools, dict) else None
    shell_tags = tools.get("shell") if isinstance(tools, dict) else None
    write_declared = bool(write_tags)
    shell_declared = bool(shell_tags)

    skill_md = skill_dir / "SKILL.md"
    text = _read_text_best_effort(skill_md) if skill_md.is_file() else ""
    trees, _unparseable = _scripts if _scripts is not None else _bundled_script_trees(skill_dir)

    write_prose_signal = bool(_WRITE_INTENT_PATTERN.search(text))
    write_script_signal = any(_tree_has_file_write(tree) for tree in trees)
    shell_prose_signal = bool(_SHELL_INTENT_PATTERN.search(text))
    shell_script_signal = any(_tree_has_shell_invocation(tree) for tree in trees)

    candidates = (
        _under_declared_or_none(
            write_declared,
            write_prose_signal,
            "tools-write-vs-skill-md",
            "declared executionRequirements.tools.write is empty/absent but SKILL.md shows mutating-action language",
            "heuristic",
        ),
        _under_declared_or_none(
            write_declared,
            write_script_signal,
            "tools-write-vs-script-content",
            "declared executionRequirements.tools.write is empty/absent but a bundled script performs a real file-write operation",
            "deterministic",
        ),
        _over_declared_or_none(write_declared, write_prose_signal, write_script_signal, "write"),
        _under_declared_or_none(
            shell_declared,
            shell_prose_signal,
            "tools-shell-vs-skill-md",
            "declared executionRequirements.tools.shell is empty/absent but SKILL.md shows shell-invocation language",
            "heuristic",
        ),
        _under_declared_or_none(
            shell_declared,
            shell_script_signal,
            "tools-shell-vs-script-content",
            "declared executionRequirements.tools.shell is empty/absent but a bundled script performs a real subprocess/shell invocation",
            "deterministic",
        ),
        _over_declared_or_none(shell_declared, shell_prose_signal, shell_script_signal, "shell"),
    )
    return [finding for finding in candidates if finding is not None]


def _spec_of(instance: Any) -> dict[str, Any]:
    if not isinstance(instance, dict):
        return {}
    spec = instance.get("spec")
    return spec if isinstance(spec, dict) else {}


def find_skill_drift(skill_dir: pathlib.Path) -> list[Finding]:
    """Every drift finding for exactly one skill directory: reads its own
    metadata/gitapex.yaml sidecar and runs find_network_drift/find_tools_drift
    against it. Messages carry no skill-name prefix (single-target use, the
    same convention gitapex_check_skill_shape.py's own single-target CLI
    follows) -- find_drift() below adds one when aggregating across many."""
    sidecar = skill_dir / SIDECAR_RELATIVE_PATH
    if not sidecar.is_file():
        return [Finding("error", "deterministic", f"metadata-file-present: missing {sidecar}")]
    try:
        instance = _load_sidecar(sidecar)
    except ReadError as error:
        return [Finding("error", "deterministic", str(error))]

    execution_requirements = _spec_of(instance).get("executionRequirements")
    if not isinstance(execution_requirements, dict):
        execution_requirements = {}

    scripts = _bundled_script_trees(skill_dir)
    findings: list[Finding] = []
    findings.extend(find_network_drift(execution_requirements.get("network"), skill_dir, scripts))
    findings.extend(find_tools_drift(execution_requirements.get("tools"), skill_dir, scripts))
    return findings


def find_drift(
    skills_dir: pathlib.Path = SKILLS_DIR,
    min_expected_skill_dirs: int = MIN_EXPECTED_SKILL_DIRS,
) -> list[Finding]:
    """Every drift finding across every discovered skill's declared
    executionRequirements -- find_skill_drift() run once per skill, with its
    findings prefixed by the skill directory name. Empty list means no
    drift detected (a clean scan, not a proof of correctness -- see module
    docstring). Not the CLI's own entry point (see main(), which checks
    exactly one skill directory, matching this skill's "Deterministic
    shape" lane); kept for the real-repository smoke test and any future
    batch use."""
    skill_dirs = discover_skill_dirs(skills_dir)
    if len(skill_dirs) < min_expected_skill_dirs:
        return [
            Finding(
                "error",
                "deterministic",
                f"skill-discovery-floor: found only {len(skill_dirs)} skill "
                f"director{'y' if len(skill_dirs) == 1 else 'ies'} with a "
                f"SKILL.md under {skills_dir} (expected at least "
                f"{min_expected_skill_dirs}) -- this usually means "
                "skills_dir is wrong or missing, not that skills were "
                "actually removed",
            )
        ]

    findings: list[Finding] = []
    for skill_dir in skill_dirs:
        prefix = skill_dir.name
        for finding in find_skill_drift(skill_dir):
            findings.append(Finding(finding.severity, finding.kind, f"{prefix}: {finding.message}"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check one skill's declared spec.executionRequirements against its "
            "actual SKILL.md prose and bundled scripts/*.py content (read-only). "
            "Network/import checks are AST-based and deterministic; SKILL.md "
            "prose matching is an irreducibly best-effort heuristic. Neither is "
            "a formal proof of runtime behavior."
        )
    )
    parser.add_argument("target", help="Path to a skill directory (e.g. skills/<name>).")
    args = parser.parse_args(argv)

    target = pathlib.Path(args.target)
    if not target.is_dir():
        # A wrong path or a file path must not be blamed on a missing
        # sidecar (find_skill_drift's own metadata-file-present message) --
        # found by an independent review.
        print(f"error: {target} is not a skill directory")
        return 1

    findings = find_skill_drift(target)
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    if errors:
        print("executionRequirements drift (error):")
        for finding in errors:
            print(f"  [{finding.kind}] {finding.message}")
    if warnings:
        print("executionRequirements drift (warning, non-blocking):")
        for finding in warnings:
            print(f"  [{finding.kind}] {finding.message}")
    if not findings:
        print("No executionRequirements drift found.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
