#!/usr/bin/env python3
"""Cross-check a skill's declared spec.executionRequirements against real
SKILL.md prose and bundled scripts/*.py content (issue #1022).

Bundled with the evaluating-skill-quality skill itself, alongside its
read-only shape checker (gitapex_check_skill_shape.py) -- run the same
way, against one target skill directory at a time, as part of that
skill's "Deterministic shape" lane (see SKILL.md's Two lanes section).
skills/evaluating-skill-quality/references/skill-metadata.schema.json
validates executionRequirements' SHAPE only; this scanner cross-checks
one skill's own declared network mode/domains, tools write/shell tags,
and packages.pip dependencies against what its own content actually does.

Three independent checks, one per executionRequirements sub-block, that
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
- find_packages_drift: declared executionRequirements.packages.pip vs.
  two evidence sources of its own (issue #1121, following packages.pip's
  own shape-recognition in PR2 of the same 5-PR sequence, issue #1118/PR
  #1120, which shipped 8 real defects -- including one CRITICAL fail-open
  -- found only by an independent adversarial review, direct precedent
  for this check's own review requirement) -- non-stdlib imports actually
  found in skill_dir/scripts/*.py (DETERMINISTIC, via the same AST-based
  root-module-extraction technique .github/scripts/gitapex_gate_stdlib_
  only_claim_drift.py's own _imported_root_modules/_is_stdlib already use
  for an analogous stale-claim check, resolved against declared
  packages.pip directly or via a small, disclosed, non-exhaustive
  import-name-to-distribution-name alias table -- pyyaml/yaml is the
  load-bearing entry, see _IMPORT_NAME_TO_DISTRIBUTION), and SKILL.md's
  own `compatibility` frontmatter field prose (BEST-EFFORT, exact-string
  match only, kind="heuristic" -- the same irreducibly-prose-based tier
  find_tools_drift's own "-vs-skill-md" lane already established, applied
  here to a different frontmatter field rather than the document body).
  Python-only by design (issue #1121's own Non-goals): a sidecar
  declaring packages under any OTHER ecosystem key (e.g. "npm") is real
  but simply not this function's concern, matching the originating ADR's
  own packages.pip scope (issue #1115/PR #1116, {pyyaml, jsonschema,
  pydantic}).

Each finding carries a severity: "error" for under-declaration (declared
narrower than actual) or "warning" for over-declaration (declared broader
than actual content ever exercises -- a hygiene finding, never failing a
run on its own). find_packages_drift's own compatibility-mention check is
graded "warning" under this same non-blocking-hygiene framing even though
it is not literally an over-declaration in the usage-evidence sense --
both sides of that specific check are human/metadata-authored
declarations, not independent proof of runtime behavior, so grading a
mismatch there at "error" would overstate what the check actually proves
(see find_packages_drift's own docstring).

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
prose has no parser. find_packages_drift's own deterministic half shares
the same AST-visibility class of gap (a dynamic
`importlib.import_module("yaml")` call is invisible to it, the same way
a runtime-constructed network host is to find_network_drift), and its
own alias table is necessarily incomplete by design (see
_IMPORT_NAME_TO_DISTRIBUTION's own comment) while its compatibility-
mention heuristic carries the same class of gap prose-matching always
does; see find_packages_drift's own docstring for the specifics.

Language scope: find_network_drift's AST-based half only reads
skill_dir/scripts/*.py. A bundled non-Python script (a .sh file, for
instance; this repository's own
skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh is one
real example) cannot be AST-parsed by this module at all, so it is
covered by a second, best-effort text-pattern lane instead (see
_NETWORK_COMMAND_PATTERN below) -- the same "irreducibly best-effort,
kind: 'heuristic'" precedent find_tools_drift's own "-vs-skill-md" lane
already established for prose that has no parser. That lane checks all
three network.mode values, not just 'disabled': a network-capable
command match flags under-declared usage in 'disabled' mode; a literal
https?:// host found in the same text (via _URL_LITERAL_PATTERN, the
same extraction the AST lane already applies to Python string-constant
text) is checked against declared allowlist domains in 'allowlist' mode,
tagged kind="heuristic" alongside the AST lane's own kind="deterministic"
per-host findings; and either signal, or an undetermined
unparseable/unreadable script (see below), suppresses 'unrestricted'
mode's over-declaration warning. A bare command match with no
extractable hostname (e.g. "ssh some-host") has nothing further to check
under allowlist mode beyond its own command-pattern-vs-disabled-mode
role (this matters beyond this one repository too: evaluating-skill-
quality itself travels as a portable skill, per its own
spec.portability, so a consuming repository's own skills may bundle
scripts in other languages this scanner was never taught to read).

This lane also mirrors several of the AST lane's own already-fixed
correctness properties, each found live against this repository's own
skills/ tree by adversarial review rounds rather than only reasoned
about in the abstract:

- A bundled non-Python file named "test_*" is excluded, the same
  pytest-discovery exclusion _bundled_script_trees already applies to
  *.py (a bundled non-Python test/fixture script's own network calls are
  not the skill's real shipped capability, no more than a Python test
  file's are).
- Only a file that looks like a bundled script -- a known script
  extension or a leading shebang line, see _looks_like_bundled_script --
  is read at all. An earlier version of this lane read every non-.py
  file under scripts/ unconditionally, so a bundled non-script asset (an
  image, a JSON/YAML fixture) that happened not to decode as UTF-8 text
  was misread as an unreadable "script" and flagged as undetermined
  network-capable usage even though it was never a script in the first
  place.
- A recognized script that cannot be read as UTF-8 text is surfaced as
  its own "non-python-script-unreadable" finding rather than silently
  scored clean, the same "undetermined, not clean" treatment
  network-script-unparseable already gives an unparseable .py file --
  and, symmetrically, that same undetermined state (like an unparseable
  .py file) suppresses 'unrestricted' mode's over-declaration warning
  rather than letting the two findings contradict each other in the same
  scan.
- A whole-line comment ('#'-prefixed) is stripped before matching, the
  one mechanical guarantee this text-only lane can give that a comment
  can never register as usage -- found live against
  check_task_bash_safety.sh's own comment mentioning "curl"/"wget" while
  documenting the exact fetch-and-execute pattern it exists to block.

What this lane does NOT close, and does not try to: a command name (or
URL) quoted as text inside an unrelated string/regex literal on a real
code line (check_task_bash_safety.sh's own fetch_exec_re variable
legitimately quotes "curl|wget" as detection text, not as an invocation,
and still matches) -- the same class of imprecision this module's own
SKILL.md prose heuristic already carries unmitigated for negated/quoted/
example text, and the same class the AST lane itself already accepts for
a non-docstring Python string constant containing pattern text (see
_tree_referenced_hosts, which excludes only docstrings). Disclosed as a
residual limitation rather than chased with a full shell/string-literal
parser disproportionate to a "best-effort" tier check. A host built at
runtime via shell variable/command substitution rather than appearing as
a literal string is the same class of false negative
test_dynamically_constructed_host_evades_allowlist_check already proves
for the AST lane.

See test_non_python_bundled_scripts_get_heuristic_network_scan and
test_non_python_allowlist_mode_flags_out_of_list_host for concrete,
deliberately-constructed proofs this lane catches real network-capable
shell content under 'disabled' and 'allowlist' modes respectively;
test_benign_non_python_bundled_script_produces_no_finding,
test_non_python_test_file_is_excluded_from_network_scan,
test_non_script_asset_under_scripts_dir_produces_no_finding, and
test_non_python_comment_only_network_mention_produces_no_finding for
negative-case proofs; test_unreadable_non_python_script_is_undetermined_
not_clean and test_unreadable_script_suppresses_unrestricted_over_
declared_warning for the fail-closed-on-unreadable proofs; and
test_non_python_quoted_network_command_text_still_produces_finding for
the disclosed residual limitation, proven concretely rather than only
asserted here.

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
warnings-only, 1 on any error-severity finding or a read error, 2 if a
required dependency -- PyYAML -- is missing from the import path) -- or via
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

try:
    import yaml
except ModuleNotFoundError as error:
    # why-not(#1076): only convert to SystemExit when run as a script.
    # A bare SystemExit raised while this module is merely *imported* (e.g.
    # pytest collecting test_gitapex_scan_execution_requirements_drift.py's
    # own `import ... as scanner`) is not a plain Exception, so pytest's
    # collection handler can't catch it cleanly -- live-verified: it surfaces
    # as INTERNALERROR (exit 3) instead of a normal, clean collection error
    # (exit 2), swallowing this guard's own message under a crash dump. The
    # __name__ check keeps every import path exactly as graceful as the
    # pre-#1076 unguarded `import yaml` was; only the documented CLI entry
    # point (`python3 gitapex_scan_execution_requirements_drift.py
    # <skill-dir>`) gets the friendly message. error.name narrows further to
    # "PyYAML itself is absent": a broken/partial install raises this same
    # exception type with error.name == "yaml.<submodule>", not "yaml", and
    # this guard's remediation ("uv sync --group dev") would not fix a
    # corrupted install, so that case re-raises unmodified rather than being
    # misdiagnosed.
    if error.name != "yaml" or __name__ != "__main__":
        raise
    print(
        f"error: {error}. This script requires PyYAML, which is not on "
        "the import path -- install the dev dependency group first: "
        "uv sync --group dev",
        file=sys.stderr,
    )
    raise SystemExit(2) from error

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
# Command-name match only, analogous in spirit to _SHELL_INTENT_PATTERN/
# _WRITE_INTENT_PATTERN's own SKILL.md prose matching: a non-Python bundled
# script has no AST this module can parse, so a network-capable command
# invocation is the only tractable signal, not a formal proof of network
# I/O (a script could reference one of these names in a comment, or an
# aliased/indirected call could evade this pattern entirely -- the same
# disclosed evasion class as the existing prose heuristic, see module
# docstring's own Language scope note).
_NETWORK_COMMAND_PATTERN = re.compile(
    r"\b(?:curl|wget|nc|ncat|netcat|ssh|scp|sftp|ftp|telnet)\b",
    re.IGNORECASE,
)
# Known non-Python script-file extensions -- one of the two signals
# (alongside a leading shebang, checked separately) deciding whether a
# scripts/ file is a bundled script this new lane should read at all, as
# opposed to a non-script asset (a bundled image, JSON/YAML fixture, or
# other binary/data file) that happens to sit in the same directory. Found
# live: without either signal, a plain PNG under scripts/ (no shebang, no
# script extension) was misread as an unreadable "script" and flagged as
# undetermined network-capable usage, even though it is not a script at
# all. Extension-based, not exhaustive -- a real script in an unlisted
# language with no shebang line would still be missed (the same disclosed
# language-scope gap as everywhere else in this heuristic lane).
_SCRIPT_EXTENSIONS = frozenset(
    {".sh", ".bash", ".zsh", ".ksh", ".fish", ".ps1", ".bat", ".cmd", ".rb", ".pl", ".php", ".js", ".mjs", ".ts"}
)
_SHEBANG_PREFIX = b"#!"
# Strips a whole line whose first non-whitespace content is a comment
# marker, before _NETWORK_COMMAND_PATTERN runs -- the one mechanical
# guarantee this text-only lane can give that a comment can never register
# as usage, the same guarantee the AST lane gets structurally for free (a
# real parse tree has no comment nodes at all; see module docstring). Found
# live: this repository's own
# skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh mentions
# "curl"/"wget" only in a comment documenting the exact fetch-and-execute
# pattern it exists to block, and used to be misreported as real network
# usage before this exclusion. Three patterns, not one, because
# _SCRIPT_EXTENSIONS spans languages with different whole-line comment
# syntax: '#' covers shell/Ruby/Perl/PowerShell (and any shebang-detected
# script with no recognized extension); '//' additionally covers
# JavaScript/TypeScript/PHP (found live by an adversarial review: a
# "// curl ..." line in a bundled .js script was NOT excluded by the '#'
# pattern alone and still produced a false finding); 'REM'/'::' cover
# Windows batch (.bat/.cmd). Applied per-file by _strip_line_comments based
# on the file's own suffix, not unconditionally, since a language whose
# comment marker also has a real-code meaning elsewhere (':' in shell,
# for instance) must not have every such line stripped. Does NOT exclude a
# trailing end-of-line comment, nor a command name quoted as text inside an
# unrelated string/regex literal (check_task_bash_safety.sh's own
# fetch_exec_re variable legitimately quotes "curl|wget" as detection
# text, not as an invocation, and still matches after this exclusion) --
# an accepted residual limitation, the same class of imprecision this
# module's own SKILL.md prose heuristic
# (_SHELL_INTENT_PATTERN/_WRITE_INTENT_PATTERN) already carries unmitigated
# for negated/quoted/example text. See
# test_non_python_comment_only_network_mention_produces_no_finding,
# test_non_python_slash_comment_only_network_mention_produces_no_finding,
# and test_non_python_quoted_network_command_text_still_produces_finding
# for these proven concretely, not only asserted here.
_HASH_COMMENT_LINE_PATTERN = re.compile(r"^[ \t]*#.*$", re.MULTILINE)
_SLASH_COMMENT_LINE_PATTERN = re.compile(r"^[ \t]*//.*$", re.MULTILINE)
_BATCH_COMMENT_LINE_PATTERN = re.compile(r"^[ \t]*(?:REM\b.*|::.*)$", re.MULTILINE | re.IGNORECASE)
# Extensions whose whole-line comment syntax is '//' (also accepting '#',
# since PHP supports both) rather than '#' alone.
_SLASH_COMMENT_EXTENSIONS = frozenset({".js", ".mjs", ".ts", ".php"})
_BATCH_COMMENT_EXTENSIONS = frozenset({".bat", ".cmd"})


def _strip_line_comments(text: str, suffix: str) -> str:
    """Strip whole-line comments from ``text`` using the comment syntax
    appropriate to ``suffix`` (see _HASH_COMMENT_LINE_PATTERN's own
    comment for why this is suffix-aware rather than one pattern applied
    unconditionally to every non-Python script). A shebang-detected script
    with an unrecognized or absent suffix falls back to '#', the
    convention the large majority of Unix scripting languages this lane
    targets share."""
    suffix = suffix.lower()
    if suffix in _BATCH_COMMENT_EXTENSIONS:
        return _BATCH_COMMENT_LINE_PATTERN.sub("", text)
    if suffix in _SLASH_COMMENT_EXTENSIONS:
        return _SLASH_COMMENT_LINE_PATTERN.sub("", _HASH_COMMENT_LINE_PATTERN.sub("", text))
    return _HASH_COMMENT_LINE_PATTERN.sub("", text)


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
    """Every .py file anywhere under skill_dir/scripts/ (RECURSIVELY, see
    below) that is not the skill's own test suite, parsed. Test files
    (pytest's own "test_*.py" discovery convention, the one this
    repository's own scripts actually use, matched on the file's own
    basename regardless of depth) are excluded -- a script's unit tests
    legitimately construct test-double URLs, mocked subprocess calls, and
    similar test-only content that is not the skill's own shipped
    capability; including them misattributes that content as real drift
    (found live against this repository's own skills/setup-gitapex-toolchain
    and skills/drafting-an-adr, each reporting a finding whose only real
    source was its own test file, not its implementation script).

    RECURSIVE (scripts_dir.rglob), not scripts_dir.glob("*.py") as an
    earlier version had it: a top-level-only glob never looks inside a
    recognized local sibling subpackage directory
    (_is_local_sibling_module's own scripts/<name>/ or
    scripts/<name>/__init__.py shape) at all, so that subpackage's own
    real content -- and any import it makes -- was silently invisible to
    every check built on this function's result, not merely unattributed.
    Found live (packages.pip's own drift check, issue #1121, an
    independent adversarial review, a CRITICAL-equivalent total fail-open):
    scripts/helperpkg/__init__.py importing "requests", with
    scripts/main.py doing a bare "import helperpkg" and an empty declared
    packages.pip, produced ZERO findings -- not because "requests" was
    correctly recognized as satisfied, but because helperpkg's own file was
    never even a candidate for parsing, the same "content nobody ever
    looked at gets scored as if it were clean" failure mode this function's
    own "an inability to verify is a deny, not an assume-clean" rule
    (below) already refuses to allow for a file it DOES attempt to read.
    Safe to widen this way: the one existing test that puts a .py file in
    a scripts/ subdirectory
    (test_local_sibling_subpackage_import_is_not_flagged) uses an EMPTY
    __init__.py, contributing zero imports/signals either way, and a live
    scan of this repository's own skills/ tree (none of which bundle a
    real scripts/ subpackage as of this writing) confirms no behavior
    change against real content. find_network_drift's and
    find_tools_drift's own script-content signals benefit symmetrically
    (a subpackage's own network/write/shell usage is just as much the
    skill's real shipped capability as a top-level script's), not just
    find_packages_drift, since all three share this same function's
    result via find_skill_drift.

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
    refuses to produce; reading directly here closes that gap. Each
    unparseable/unreadable name is recorded as its path RELATIVE TO
    scripts_dir (e.g. "helperpkg/broken.py"), not a bare basename, now that
    a name collision across two different subdirectories is possible and a
    caller's finding message (f"scripts/{name}") must still point at the
    real file, not a misleading top-level guess."""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return [], []
    trees: list[ast.AST] = []
    unparseable: list[str] = []
    for path in sorted(scripts_dir.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        relative_name = path.relative_to(scripts_dir).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unparseable.append(relative_name)
            continue
        try:
            trees.append(ast.parse(text, filename=str(path)))
        except SyntaxError:
            unparseable.append(relative_name)
    return trees, unparseable


def _looks_like_bundled_script(path: pathlib.Path) -> bool:
    """Whether ``path`` looks like a non-Python bundled script this lane
    should read at all, as opposed to a non-script asset (a bundled image,
    JSON/YAML fixture, or other binary/data file) sitting in the same
    scripts/ directory -- decided by a known script extension
    (_SCRIPT_EXTENSIONS) or a leading shebang line, checked on raw bytes
    so a non-UTF-8 file can still be recognized as a script (and thus
    correctly reported as unreadable-and-undetermined, not silently
    skipped) purely from its first two bytes, without needing a successful
    text decode first."""
    if path.suffix.lower() in _SCRIPT_EXTENSIONS:
        return True
    try:
        with path.open("rb") as handle:
            return handle.read(len(_SHEBANG_PREFIX)) == _SHEBANG_PREFIX
    except OSError:
        return False


def _bundled_non_python_script_texts(skill_dir: pathlib.Path) -> tuple[dict[str, str], list[str]]:
    """Every non-``.py`` file directly under skill_dir/scripts/ that looks
    like a bundled script (see _looks_like_bundled_script) and is not the
    skill's own test suite ("test_" prefix, same pytest-discovery
    convention and exclusion _bundled_script_trees already applies to
    *.py -- a bundled non-Python test/fixture script's own network calls
    against a mock or local test endpoint are exactly as much "not the
    skill's real shipped capability" as a Python test file's are; found
    live for the .py case against this repository's own
    skills/setup-gitapex-toolchain and skills/drafting-an-adr, and nothing
    about a different file extension makes that risk go away).

    Returns (name -> text, unreadable_names): a recognized script that
    cannot be read as UTF-8 text is excluded from the text dict and its
    name collected separately, rather than silently contributing zero
    pattern matches -- the same "an inability to verify is a deny, not an
    assume-clean" rule _bundled_script_trees's own docstring states for
    the parallel .py case. A prior version of this helper routed reads
    through _read_text_best_effort, which folds an unreadable file into
    "" -- _NETWORK_COMMAND_PATTERN.search("") never matches, so a
    genuinely network-capable but unreadable/non-UTF-8 script was scored
    clean exactly like an empty or absent one, the same assume-clean
    outcome this function's own docstring refuses to produce; a version
    after that read every non-.py file unconditionally, which instead
    flagged ordinary non-script assets (a bundled PNG, for instance) as
    an undetermined "script" -- both found by independent adversarial
    review rounds; _looks_like_bundled_script's own extension-or-shebang
    gate is what keeps this version from repeating either mistake."""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return {}, []
    texts: dict[str, str] = {}
    unreadable: list[str] = []
    for path in sorted(scripts_dir.iterdir()):
        if not path.is_file() or path.suffix == ".py" or path.name.startswith("test_"):
            continue
        if not _looks_like_bundled_script(path):
            continue
        try:
            texts[path.name] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unreadable.append(path.name)
    return texts, unreadable


def find_network_drift(
    network: Any,
    skill_dir: pathlib.Path,
    _scripts: tuple[list[ast.AST], list[str]] | None = None,
) -> list[Finding]:
    """network-mode-vs-script-content: declared executionRequirements.network
    vs. network-capable imports/literal https?:// hosts found in
    skill_dir/scripts/*.py, via AST parsing (deterministic -- see module
    docstring's own Language scope / Determinism note); plus a second,
    best-effort text-pattern check (kind="heuristic") for network-capable
    command usage in every non-``.py`` file under skill_dir/scripts/, which
    the AST-based check above cannot read at all (see module docstring's
    own Language scope note for what this second check does and does not
    cover).

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

    non_python_scripts, non_python_unreadable = _bundled_non_python_script_texts(skill_dir)
    non_python_texts_sans_comments = {
        name: _strip_line_comments(text, pathlib.Path(name).suffix) for name, text in non_python_scripts.items()
    }
    non_python_network_command_hits = sorted(
        name for name, text in non_python_texts_sans_comments.items() if _NETWORK_COMMAND_PATTERN.search(text)
    )
    non_python_hosts: set[str] = set()
    for text in non_python_texts_sans_comments.values():
        for literal in _URL_LITERAL_PATTERN.findall(text):
            hostname = urllib.parse.urlsplit(literal).hostname
            if hostname:
                non_python_hosts.add(hostname.lower())
    # An unreadable/unparseable script's real content is genuinely unknown
    # (see the two findings built from unparseable/non_python_unreadable
    # below) -- undetermined is not the same claim as "verified clean", so
    # neither over-declaration suppression below may treat it as clean.
    content_fully_undetermined = bool(unparseable or non_python_unreadable)

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
    ] + [
        Finding(
            "error",
            "deterministic",
            f"non-python-script-unreadable: scripts/{name} is not a Python "
            "script this scanner can AST-parse, and could not even be read "
            "as UTF-8 text for the best-effort heuristic network-command "
            "scan -- could not be analyzed for network-capable usage, "
            "treated as undetermined rather than clean",
        )
        for name in non_python_unreadable
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
        for host in sorted(non_python_hosts - declared_domains):
            findings.append(
                Finding(
                    "error",
                    "heuristic",
                    "network-mode-vs-non-python-script-content: bundled "
                    f"non-Python scripts reference host {host!r} not present "
                    f"in declared allowlist domains {sorted(declared_domains)} "
                    "-- flagged as a best-effort heuristic match (a literal "
                    "https?:// string found in a non-Python bundled script's "
                    "own text), not a formal proof",
                )
            )
    elif (
        mode == "unrestricted"
        and not has_network_import
        and not referenced_hosts
        and not non_python_network_command_hits
        and not non_python_hosts
        and not content_fully_undetermined
    ):
        findings.append(
            Finding(
                "warning",
                "deterministic",
                "network-mode-vs-script-content: declared network.mode "
                "'unrestricted' but no bundled script shows network-capable "
                "usage (over-declared)",
            )
        )
    # Heuristic, non-Python lane: command-pattern findings are only raised
    # for "disabled" -- allowlist's own per-host check above and
    # unrestricted's over-declaration suppression already account for
    # non_python_network_command_hits/non_python_hosts directly, and a bare
    # command match with no extractable hostname (e.g. "ssh some-host") has
    # nothing further to check under allowlist mode once its own host-based
    # check above has run.
    if mode == "disabled":
        findings.extend(
            Finding(
                "error",
                "heuristic",
                f"network-command-in-non-python-script: scripts/{name} is not "
                "a Python script this scanner can AST-parse, but its text "
                "contains a network-capable command pattern "
                "(curl/wget/nc/ncat/netcat/ssh/scp/sftp/ftp/telnet) while "
                f"declared network.mode is {mode_value!r} (absent or "
                "unrecognized values are treated as 'disabled') -- flagged "
                "as a best-effort heuristic match, not a formal proof",
            )
            for name in non_python_network_command_hits
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


# ---- find_packages_drift helpers ----

# Import-name -> canonical PyPI distribution name (values already
# PEP-503-normalized-shaped -- lowercase with '-' separators, though
# always re-normalized via _pep503_normalize before comparison rather
# than trusted as pre-normalized, see declared_pip_normalized's own
# construction in find_packages_drift for why). Exists for the well-known
# cases where a
# package's real IMPORTABLE module name differs from the DISTRIBUTION
# name PyPI (and this repository's own packages.pip declarations) use.
# pyyaml/yaml is the load-bearing entry this whole table exists for --
# this scanner's own top-of-file `import yaml` is exactly that case (a
# real runtime dependency on the pyyaml distribution), and the
# originating ADR's own allowlist (issue #1115/PR #1116: {pyyaml,
# jsonschema, pydantic}) names pyyaml specifically. Deliberately
# NON-EXHAUSTIVE (issue #1121's own Non-goals explicitly excludes
# "Exhaustively solving the general Python import-name-to-distribution-
# name mapping problem") and kept genuinely small -- a dozen-odd
# well-known cases, not a generated mirror of PyPI's own namespace. THE
# SPECIFIC FAILURE MODE an unlisted alias produces: a real package whose
# import name differs from its distribution name, and is not one of the
# entries below, is invisible to this table -- find_packages_drift falls
# back to comparing the import name directly against the declared set,
# which will not match a genuinely different distribution name, producing
# a FALSE "under-declared" (error-severity) positive even though the
# package really is correctly declared under its real distribution name
# (see test_unlisted_alias_produces_documented_false_positive, proven
# concretely against python-dotenv/dotenv -- a real, well-known pair
# deliberately left off this table). Keys are exact-case: Python import
# names are real, case-sensitive language identifiers ("PIL" is
# Pillow's own actual shipped top-level package name, not a stylistic
# choice this table makes -- "import pil" would be a ModuleNotFoundError
# against the real distribution), so a lookup against this table always
# uses the import name's own real case, never lower-cased first (unlike
# the declared-name side of every comparison below -- see
# _pip_declared_for_import).
_IMPORT_NAME_TO_DISTRIBUTION: dict[str, str] = {
    "yaml": "pyyaml",
    "PIL": "pillow",
    "cv2": "opencv-python",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "dateutil": "python-dateutil",
    "attr": "attrs",
    "attrs": "attrs",
    "jwt": "pyjwt",
}

# SKILL.md's leading YAML frontmatter block (---...---), captured as one
# group -- deliberately anchored to the very start of the file (no
# re.MULTILINE; "^"/"$" mean start/end of the WHOLE string here), the
# same "---" as the first line, real closing "---" required" contract as
# gitapex_check_skill_shape.py's own _parse_frontmatter already uses.
_FRONTMATTER_BLOCK_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.DOTALL)
# Only searched within the frontmatter block's own captured interior (see
# _extract_compatibility_field), so re.MULTILINE here means "any line
# inside that block," not "anywhere in the whole SKILL.md file." THE
# ACTUAL, NARROWER GUARANTEE (corrected -- an earlier version of this
# comment overclaimed "a body heading or prose sentence that happens to
# start a line with 'compatibility:' can never match," which is FALSE,
# found live by an independent adversarial review):
# _FRONTMATTER_BLOCK_RE's own captured group is bounded by the FIRST
# "---"-only line and the very NEXT "---"-only line after it (the same
# delimiter-pairing contract gitapex_check_skill_shape.py's own
# _parse_frontmatter already uses, and verified live to behave
# identically to it on the adversarial input below -- this module does
# not diverge from that shared, established convention), but -- exactly
# like that sibling parser -- it does NOT validate that every intervening
# line is itself a well-formed "key: value" pair before accepting the
# span as real frontmatter. A line that is merely SHAPED like a
# frontmatter field (matches "^compatibility:[ \t]*(.*)$") still matches
# even when OTHER, clearly non-YAML prose shares that same span -- e.g.
# _extract_compatibility_field("---\n\nSome body\n\ncompatibility: pyyaml
# is needed\n\n---\n") returns "pyyaml is needed", because there is no
# EARLIER "---"-only line to close the block first, so lines 1-5
# (including the "compatibility:" one) are, by this shared boundary
# rule, genuinely the captured interior -- not a body line slipping past
# a correctly-drawn boundary. What IS still guaranteed: a real,
# tightly-closed frontmatter block (an early second "---"-only line)
# correctly excludes any LATER "compatibility:" mention in the body, even
# one followed by its own further stray "---" (see
# test_extract_compatibility_field_body_mention_outside_frontmatter_is_ignored
# and test_extract_compatibility_field_body_mention_after_a_real_frontmatter_
# close_with_a_later_stray_delimiter_is_ignored). A full fix would mean
# validating every captured-interior line as real YAML before trusting the
# boundary at all -- a larger scope change that would also make this
# module's own boundary-finding diverge from the sibling parser above,
# not converge with it; disclosed here instead, matching this module's
# own established precedent for a proportionate, explicitly-disclosed
# residual limitation (see e.g. _NETWORK_COMMAND_PATTERN's own comment)
# over an unproportionate full parser rewrite for a warning-only,
# non-blocking heuristic check (see find_packages_drift's own docstring:
# compatibility-mention findings are graded "warning", never "error").
_COMPATIBILITY_FIELD_RE = re.compile(r"^compatibility:[ \t]*(.*)$", re.MULTILINE)


def _extract_compatibility_field(skill_md_text: str) -> str:
    """SKILL.md's own top-level frontmatter ``compatibility:`` field
    value, or "" if the file has no frontmatter, no closing "---", or no
    ``compatibility`` key at all -- never raises.

    A small, targeted, SINGLE-field extraction, not a second
    general-purpose frontmatter parser: gitapex_check_skill_shape.py's
    own _parse_frontmatter already fully handles quoted/plain/block-scalar
    SKILL.md frontmatter for that checker's own broader needs, and this
    module's own docstring commits to no cross-import from a sibling
    checker script (duplicate small helpers instead, the same convention
    SIDECAR_RELATIVE_PATH and discover_skill_dirs above already follow) --
    reimplementing that whole parser here for one substring-presence
    heuristic would be exactly the disproportionate complexity
    _NETWORK_COMMAND_PATTERN's own comment already argues against
    elsewhere ("a full shell/string-literal parser disproportionate to a
    best-effort tier check").

    Handles the plain, single-, and double-quoted scalar forms real
    SKILL.md files use (see skills/setup-gitapex-toolchain/SKILL.md, the
    only real ``compatibility:`` field in this repository as of this
    writing -- a double-quoted plain string). Does NOT join a YAML block
    scalar's (">"/"|") own indented continuation lines -- a disclosed gap,
    not a crash risk: a block-scalar compatibility value reads as a
    near-empty string, which only makes find_packages_drift's own
    compatibility-mention heuristic over-fire (a package genuinely
    mentioned, just inside an unsupported continuation line, reads as
    "not mentioned") -- a false positive on a warning-only, non-blocking
    finding, never a fail-open gap in the opposite (error-severity)
    direction.

    CRLF is normalized to LF before matching -- found live by this
    function's own required independent adversarial review (issue
    #1121): without it, a trailing "\\r" stays attached to the "---"
    frontmatter delimiter's own line, so _FRONTMATTER_BLOCK_RE's literal
    "\\n" immediately after "---[ \\t]*" never matches at all (the real
    next character is "\\r", not "\\n") -- the whole frontmatter block
    silently fails to match, and every declared package reads as "not
    mentioned" (a heuristic false positive, not a crash). The same
    normalization fixes the same class of bug this repository's own
    .github/scripts/gitapex_gate_stdlib_only_claim_drift.py already found
    and fixed once (its own parse_diff_added_third_party_imports: "a
    trailing '\\r' stays attached to a '+++ b/<path>' header's path...
    found by adversarial review") -- git's own local-plane invocation, or
    a file re-saved by a Windows-default editor, can carry CRLF even
    though this repository's own real, checked-in SKILL.md files are
    LF-only."""
    skill_md_text = skill_md_text.replace("\r\n", "\n")
    match = _FRONTMATTER_BLOCK_RE.match(skill_md_text.lstrip("\ufeff"))
    if not match:
        return ""
    field_match = _COMPATIBILITY_FIELD_RE.search(match.group(1))
    if not field_match:
        return ""
    value = field_match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def _tree_imported_root_modules(tree: ast.AST) -> set[str]:
    """Every root module name ``tree`` imports anywhere -- "import X" and
    "import X.Y" both contribute "X" (Python itself binds the top-level
    package name, not the submodule, for an unaliased dotted import --
    the same rule _module_aliases' own docstring already states for
    call-target resolution); "from X import Y" (absolute only, node.level
    == 0 -- a relative "from . import Y"/"from .sibling import Y" names no
    real external package at all) contributes "X", regardless of what Y
    itself is (a star import "from X import *" contributes "X" the same
    way, since only the module path -- never the imported names -- decides
    what package is actually required).

    Walks the FULL tree (ast.walk), not just top-level statements --
    unlike .github/scripts/gitapex_gate_stdlib_only_claim_drift.py's own
    _imported_root_modules, which parses one git-diff-added LINE at a
    time and is therefore already effectively top-level by construction.
    This function instead receives a whole parsed module (the same
    _bundled_script_trees(skill_dir) result find_network_drift/
    find_tools_drift already share), where a real import can legitimately
    sit inside a function body, a class body, or a try/except (the common
    "optional dependency" pattern) -- ast.walk finds all of these, the
    same way _tree_has_network_import/_module_aliases above already do
    for their own target modules, matching this file's own established
    convention over the diff-scanning gate's narrower one, which suits a
    different input shape, not a different design philosophy. Conditional
    gating (an "if False:"-guarded import, a TYPE_CHECKING-only import)
    does not suppress detection here either, for the same reason the
    module docstring already documents for find_network_drift: a real
    parse tree node exists regardless of whether the guarding condition
    could ever be true at runtime, and this scanner does not evaluate
    conditions, only structure."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _is_stdlib_module(module_name: str) -> bool:
    """Exact membership in sys.stdlib_module_names -- mirrors
    .github/scripts/gitapex_gate_stdlib_only_claim_drift.py's own
    _is_stdlib exactly (duplicated per this module's own no-cross-import
    convention, not imported). EXACT membership, not a prefix/substring
    check, is load-bearing: a real third-party package whose name merely
    starts with a stdlib module's own name (e.g. "osgeo", GDAL's own
    Python bindings, which is not itself in sys.stdlib_module_names even
    though it starts with the real stdlib module "os") must still be
    treated as non-stdlib -- a prefix-based check would silently and
    incorrectly exempt it from every check below, letting a genuinely
    undeclared package slip through undetected (see
    test_non_stdlib_module_sharing_stdlib_prefix_is_still_flagged)."""
    return module_name in sys.stdlib_module_names


# Real, syntactically ordinary import roots that are neither in
# sys.stdlib_module_names NOR ever a real PyPI-installable package --
# flagging either as "under-declared" would be an UNFIXABLE false
# positive (no packages.pip entry could ever satisfy it, since no such
# distribution exists to declare). A small, explicitly-commented,
# CLOSED set for these two confirmed cases only -- deliberately not an
# attempt to solve the general "which import names are real installable
# packages" problem (that would need a live PyPI query this offline,
# read-only checker must never perform; see _IMPORT_NAME_TO_DISTRIBUTION's
# own docstring for the same non-goal stated for the alias-table side).
#   - "_typeshed": typeshed's own stub-only, type-checker-internal module
#     (see https://github.com/python/typeshed/blob/main/stdlib/_typeshed/README.md,
#     "the _typeshed module... is not available at runtime"). It ships no
#     real runtime code and has no PyPI distribution of its own; the only
#     realistic way to see it imported at all is inside an
#     "if TYPE_CHECKING:" guard (e.g. "from _typeshed import StrPath" for
#     a type annotation), which _tree_imported_root_modules already
#     deliberately still detects as an import (by design -- a
#     TYPE_CHECKING-guarded import of a REAL third-party package must
#     still require a declaration). The bug this set closes is narrower
#     than that: _typeshed specifically can never be satisfied by any
#     real packages.pip entry, so flagging it is not a signal to declare
#     something, only a dead-end false positive.
#   - "__main__": the real, always-importable module every running
#     Python process has for its own entry-point namespace (see
#     https://docs.python.org/3/library/__main__.html) -- legitimate,
#     working code ("import __main__"), not in sys.stdlib_module_names
#     (it is not a library module the stdlib ships as content, just a
#     live runtime binding), and not a PyPI-installable package either.
_NON_STDLIB_NON_INSTALLABLE_MODULES = frozenset({"_typeshed", "__main__"})


def _non_stdlib_root_imports(trees: list[ast.AST]) -> set[str]:
    """Every root module name imported anywhere across ``trees`` that is
    NOT a standard-library module -- the "this script needs a real PyPI
    package for this" signal find_packages_drift's own under/over-declared
    checks are built from. A tree that failed to parse in the first place
    is already absent from ``trees`` (see _bundled_script_trees) and so
    contributes nothing here, by construction -- not a separate case this
    function has to handle.

    Also excludes _NON_STDLIB_NON_INSTALLABLE_MODULES's own two entries
    (see its own comment): found live (an independent adversarial review)
    that a TYPE_CHECKING-only "from _typeshed import StrPath" or "import
    __main__" was reported as an "under-declared" packages.pip gap with
    no way to ever satisfy it -- neither name is stdlib-per-
    sys.stdlib_module_names, but neither is a real installable
    third-party package either, so there is no real dependency to
    declare in the first place."""
    imports: set[str] = set()
    for tree in trees:
        imports.update(_tree_imported_root_modules(tree))
    return {name for name in imports if not _is_stdlib_module(name) and name not in _NON_STDLIB_NON_INSTALLABLE_MODULES}


def _is_local_sibling_module(skill_dir: pathlib.Path, import_name: str) -> bool:
    """Whether ``import_name`` resolves to a real Python file or
    subpackage sitting alongside the bundled scripts in
    skill_dir/scripts/ itself -- a bare "from _local_helper import x" (or
    "import local_helper") sibling import within that SAME directory
    names no real external PyPI dependency at all, whatever its own root
    name looks like. This is not a hypothetical: found live during this
    function's own real-repository self-check (issue #1121) against this
    repository's own skills/executing-a-branch-plan/scripts/
    gitapex_check_canonical_governance_paths.py and gitapex_check_file_
    ownership_conflicts.py, both of which do
    "from _gitapex_path_normalize import normalize" -- a real sibling
    file, skills/executing-a-branch-plan/scripts/_gitapex_path_
    normalize.py, made importable at runtime by pytest's own
    [tool.pytest.ini_options] pythonpath entry for that exact directory
    (pyproject.toml), the same resolution a direct
    ``python3 gitapex_check_canonical_governance_paths.py`` invocation
    gets for free via Python's own sys.path[0] convention (the invoked
    script's own directory). Without this check, completely ordinary,
    already-working code in a real skill would be misreported as an
    "under-declared" (error-severity) PyPI dependency gap -- exactly the
    "does this crash or misbehave against real, non-synthetic code" bar
    issue #1121's own required self-check step exists to catch, not a
    synthetic edge case reasoned about only in the abstract.

    Checked against skill_dir/scripts/ specifically -- not skill_dir as a
    whole -- because scripts/ is the one directory a real bare import like
    this ever resolves against at runtime (Python's own sys.path[0]
    convention for a directly-invoked script, or pytest's own
    [tool.pytest.ini_options] pythonpath entry for that exact directory);
    _bundled_script_trees itself now recurses INTO a recognized sibling
    subpackage's own further content once found here (see its own
    docstring), but the import NAME ITSELF always resolves exactly one
    level under scripts/, never deeper, matching Python's own resolution
    rule for a top-level bare import. A single-file module (scripts/foo.py),
    a proper regular subpackage (scripts/foo/__init__.py), AND a PEP 420
    namespace package (scripts/foo/ with no __init__.py at all, containing
    at least one real .py file somewhere under it) are all three
    recognized, matching every import shape Python's own import system
    actually resolves without any package-management step involved --
    corrected from an earlier version of this function, which recognized
    only the first two and claimed (in this same docstring) that
    recognizing a namespace package too "would be guessing, not
    observing." That claim was factually wrong, found live by an
    independent adversarial review: Python 3.3+ (PEP 420) resolves a
    directory with no __init__.py as a real, importable namespace package
    via the interpreter's own standard import machinery -- verified live,
    `python3 -c "import nspkg.mod"` succeeds from a directory containing
    nspkg/mod.py with no nspkg/__init__.py at all, resolving through
    CPython's own _NamespacePath, not a hypothetical or a lenient
    reading of the spec (see
    https://peps.python.org/pep-0420/#specification). Before this fix, a
    skill bundling a real (if today still rare in this repository)
    namespace-package-shaped subpackage under scripts/ would have every
    bare "import <that package>" misreported as an "under-declared"
    (error-severity) external PyPI dependency, the exact same class of
    live false positive this function's own docstring already documents
    fixing once for the ordinary-subpackage case above. An EMPTY
    same-named subdirectory (no .py file anywhere under it) is still NOT
    recognized -- that really would be guessing: nothing under it could
    actually satisfy the import at runtime, namespace package or not."""
    scripts_dir = skill_dir / "scripts"
    if (scripts_dir / f"{import_name}.py").is_file():
        return True
    subpackage_dir = scripts_dir / import_name
    return subpackage_dir.is_dir() and any(subpackage_dir.rglob("*.py"))


def _pep503_normalize(distribution_name: str) -> str:
    """The REAL PEP 503 "normalized name" comparison PyPI/pip themselves
    use to decide two distribution-name SPELLINGS name the same project --
    collapse any run of '-', '_', or '.' into a single '-', then
    lowercase -- not lowercasing alone (see
    https://peps.python.org/pep-0503/#normalized-names, which gives this
    exact expression: ``re.sub(r"[-_.]+", "-", name).lower()``). "scikit-
    learn", "scikit_learn", and "scikit.learn" all normalize to the same
    "scikit-learn" string under this rule -- lowercasing alone would
    still treat "scikit_learn" and "scikit-learn" as two different
    strings, which was found live (an independent adversarial review) to
    produce a false "under-declared" error for the real import alongside
    a spurious "over-declared" warning for the (actually-matching)
    declared entry, simultaneously, in opposite directions, for the exact
    same underlying package.

    Applied ONLY to DISTRIBUTION-name-shaped strings -- a declared
    packages.pip entry, or an _IMPORT_NAME_TO_DISTRIBUTION alias VALUE
    (itself a distribution name, e.g. "scikit-learn") -- never to a real
    Python IMPORT name used as an _IMPORT_NAME_TO_DISTRIBUTION table KEY
    lookup, which must stay exact-case and exact-separator (see
    _pip_declared_for_import's own docstring for why)."""
    return re.sub(r"[-_.]+", "-", distribution_name).lower()


def _pip_declared_for_import(import_name: str, declared_pip_normalized: set[str]) -> bool:
    """Whether ``import_name`` (a real, exact-case root module name found
    in a bundled script's own AST) counts as declared under
    executionRequirements.packages.pip -- either DIRECTLY (matched against
    ``declared_pip_normalized`` via full PEP 503 normalization, see
    _pep503_normalize -- PyPI distribution names are conventionally
    case- AND separator-insensitive, the same real-world reason
    find_network_drift's own declared_domains lower-cases hostnames, RFC
    4343, but going further than bare lower-casing the way that RFC-driven
    precedent does not need to) or via _IMPORT_NAME_TO_DISTRIBUTION's own
    alias, for the well-known cases where a package's real distribution
    name differs from its own importable module name.

    ``import_name`` is treated DIFFERENTLY by the two branches below,
    deliberately, not by oversight -- each branch compares it against a
    different KIND of string:

    - The DIRECT-match branch compares it against real DISTRIBUTION-name
      strings (``declared_pip_normalized`` -- a declared packages.pip
      entry may legitimately equal the import name itself, e.g. "requests"
      == "requests", or differ only by PEP 503 spelling convention, e.g.
      "my_pkg" imported vs. "my-pkg" declared), so ``import_name`` IS
      normalized here (_pep503_normalize -- both case AND separators) for
      that comparison, symmetrically with the declared side.
    - The ALIAS-table lookup uses ``import_name`` as a literal Python
      import IDENTIFIER -- a dict KEY into _IMPORT_NAME_TO_DISTRIBUTION,
      whose own keys are real, case-sensitive, syntactically-exact import
      names (see that table's own comment: "PIL" is Pillow's real shipped
      top-level module name, "import pil" would ModuleNotFoundError).
      ``import_name`` is used EXACTLY as-is for this lookup, never
      case-folded or separator-collapsed first -- confirmed by this
      module's own existing regression test,
      test_import_name_case_sensitivity_is_preserved_for_alias_lookup: a
      script spelling an import "Yaml" must NOT be silently treated as
      the real "yaml" module just because a sidecar happens to declare
      "pyyaml". Once a real alias VALUE is found this way, THAT value
      (itself a distribution-name string, e.g. "scikit-learn") is
      normalized before the final comparison, same as the direct-match
      branch.

    Found live by an independent adversarial review: an earlier version
    of the direct-match branch alone lower-cased ``import_name`` (but not
    fully PEP-503-normalized it) while the alias branch left it exact --
    an inconsistent, ad hoc split with no stated rationale, not the
    principled "which KIND of string is this being compared against"
    split above. Verified live before settling on this direction: making
    the alias branch case-fold ``import_name`` too (the OTHER way to
    remove the inconsistency) silently un-flags the exact "Yaml"-vs-"yaml"
    case that regression test exists to catch, trading a real,
    live-verified correctness property for a merely internally-consistent
    but wrong result.

    Reused for BOTH the under-declared check (called with the real
    declared_pip_normalized set) and the over-declared check (called with
    a ONE-element {declared_name_normalized} set, once per real import) --
    funneling both directions through this single predicate is
    deliberate, not merely convenient: it makes it structurally
    impossible for the alias table to be consulted in one direction for
    under-declared and a silently different, inconsistent direction for
    over-declared -- the exact class of bug an adversarial review hunts
    for in a checker like this one (direct, recent precedent: PR2 of this
    same 5-PR sequence, issue #1121's own motivating context, shipped 8
    real defects, including one CRITICAL fail-open, that only such a
    review caught)."""
    if _pep503_normalize(import_name) in declared_pip_normalized:
        return True
    alias = _IMPORT_NAME_TO_DISTRIBUTION.get(import_name)
    return alias is not None and _pep503_normalize(alias) in declared_pip_normalized


def find_packages_drift(
    packages: Any,
    skill_dir: pathlib.Path,
    _scripts: tuple[list[ast.AST], list[str]] | None = None,
) -> list[Finding]:
    """packages-pip-vs-script-content / packages-pip-over-declared /
    packages-pip-vs-compatibility: declared
    executionRequirements.packages.pip vs. two independent evidence
    sources (see module docstring's own "Three independent checks"
    intro) -- non-stdlib imports actually found in
    skill_dir/scripts/*.py (DETERMINISTIC, via AST -- see
    _non_stdlib_root_imports), and SKILL.md's own ``compatibility``
    frontmatter field prose (BEST-EFFORT, exact-string match only -- see
    _extract_compatibility_field).

    Only the "pip" ecosystem key under ``packages`` is checked (Python
    scripts import from PyPI packages); a sidecar declaring packages
    under a different ecosystem key (e.g. "npm") is real but simply not
    this function's concern -- issue #1121's own Non-goals scopes this
    module's whole packages-dependency premise to skills/*/scripts/*.py
    only, matching the originating ADR's own packages.pip focus (issue
    #1115/PR #1116).

    Deterministic half (under/over-declared): every non-stdlib root
    module name imported anywhere in the bundled Python scripts, OTHER
    THAN a local sibling module (a bare "from _helper import x" resolving
    to a real skill_dir/scripts/_helper.py sitting right alongside it --
    see _is_local_sibling_module, found live during this function's own
    required real-repository self-check against this repository's own
    skills/executing-a-branch-plan/scripts/_gitapex_path_normalize.py),
    is checked against declared packages.pip, directly or via
    _IMPORT_NAME_TO_DISTRIBUTION's own small alias table (see
    _pip_declared_for_import) -- an import with no declared (or aliased)
    backing is under-declared (error, the safety-relevant direction: a
    consumer trusting the sidecar alone would not know to provision this
    dependency); a declared entry with no matching import anywhere is
    over-declared (warning, hygiene only). Unlike find_tools_drift's own
    _over_declared_or_none, packages has only ONE evidence source (real
    imports -- no prose-based second signal the way tools.write/
    tools.shell each have their own "-vs-skill-md" lane), so over-declared
    here is graded on that one source alone, not jointly across two.

    A script that fails to parse is silently excluded from the
    script-content signal here, exactly like find_tools_drift's own
    treatment: find_network_drift already surfaces it as its own
    network-script-unparseable finding when all three checks run
    together via find_skill_drift, so this function does not
    double-report it. It DOES, however, suppress every over-declared
    warning while any bundled Python script is unparseable (mirroring
    find_network_drift's own unrestricted-mode suppression): an unparsed
    script's real imports are genuinely unknown, so asserting a declared
    package has "no matching import anywhere" would be an unproven claim,
    not a verified fact -- the same "undetermined is not the same claim
    as verified clean" principle find_network_drift's own
    content_fully_undetermined already established. This suppression does
    NOT extend to under-declared findings (built only from scripts this
    function could actually parse) nor to the compatibility-mention
    heuristic below (which never depends on script content signals at
    all, only on the sidecar's own declared strings and SKILL.md's own
    prose).

    Heuristic half (compatibility-mention): for each declared
    packages.pip name (in its own originally-declared case -- unlike the
    deterministic half above, deliberately NOT lower-cased first; see
    _extract_compatibility_field's own docstring and issue #1121's own
    Acceptance Criteria Map, which specifies exact-string matching here
    and explicitly accepts a casing/spacing mismatch as a disclosed
    limitation, not something to normalize away), an exact-string
    substring check against SKILL.md's own ``compatibility`` frontmatter
    field value; absent -> warning, kind="heuristic". Deliberately NOT
    graded "error": unlike an AST-parsed import or call, BOTH sides of
    this specific check are themselves human/metadata-authored
    declarations (a sidecar YAML string and a SKILL.md prose string), not
    independent proof of real runtime behavior -- grading a mismatch here
    at the same "error" tier as a genuine declared-vs-actual-behavior gap
    would overstate what this check actually proves. Structurally, this
    is the same "declared but unsupported by a second, independent
    source" shape find_network_drift's/find_tools_drift's own
    over-declared warnings already use (warning, non-blocking), not the
    safety-relevant under-declared direction.

    Absent packages/pip block and an explicit empty ``packages.pip: []``
    are treated identically here (both yield an empty declared set) --
    deliberately, unlike gitapex_check_skill_shape.py's own shape
    checker, which cares about that presence/absence distinction for
    SCHEMA validity; this drift-detection function only cares whether
    real content backs a real declared string, and an absent block backs
    nothing exactly as much as an explicitly empty one does.

    ``_scripts`` mirrors find_network_drift's/find_tools_drift's own
    internal parameter of the same name -- a pre-computed
    ``_bundled_script_trees(skill_dir)`` result, not part of the stable
    two-argument contract (every existing caller and test keeps working
    unchanged)."""
    pip_declared = packages.get("pip") if isinstance(packages, dict) else None
    # isinstance(..., list) guards against a classic footgun a careless
    # `set(pip_declared)`/`{p.lower() for p in pip_declared}` on a bare
    # STRING would not: a malformed sidecar declaring packages.pip as
    # "pyyaml" instead of ["pyyaml"] would otherwise iterate CHARACTER BY
    # CHARACTER ({'p', 'y', 'a', 'm', 'l'}), not raise and not no-op --
    # see test_pip_key_a_bare_string_does_not_iterate_characters. Mirrors
    # find_network_drift's own declared_domains construction exactly
    # (same guard, same shape, same reasoning).
    raw_declared_names = (
        [name for name in pip_declared if isinstance(name, str)] if isinstance(pip_declared, list) else []
    )
    # Full PEP 503 normalization (_pep503_normalize: separator-collapse
    # AND lowercase), not lower-casing alone -- found live (an independent
    # adversarial review) that bare .lower() let a real, PEP-503-equal
    # spelling variant (e.g. declared "scikit_learn" vs. the real
    # distribution "scikit-learn") read as a DIFFERENT string, producing a
    # false under-declared error for the real import and a spurious
    # over-declared warning for the declared entry at once. See
    # _pep503_normalize's own docstring.
    declared_pip_normalized = {_pep503_normalize(name) for name in raw_declared_names}

    trees, unparseable = _scripts if _scripts is not None else _bundled_script_trees(skill_dir)
    # A local sibling-module import (see _is_local_sibling_module's own
    # docstring for the real, live example this was found against) is
    # excluded here, before either the under- or over-declared check ever
    # sees it -- it is not merely "aliased" or "satisfied," it is not a
    # PyPI dependency in the first place, so it must never appear in
    # either direction's findings, not just be suppressed from one.
    non_stdlib_imports = {
        name for name in _non_stdlib_root_imports(trees) if not _is_local_sibling_module(skill_dir, name)
    }

    findings: list[Finding] = []

    for import_name in sorted(non_stdlib_imports):
        if not _pip_declared_for_import(import_name, declared_pip_normalized):
            findings.append(
                Finding(
                    "error",
                    "deterministic",
                    "packages-pip-vs-script-content: bundled scripts import "
                    f"{import_name!r} (a non-stdlib module) but declared "
                    "executionRequirements.packages.pip does not include it, "
                    f"directly or via the {import_name!r}->distribution alias "
                    "table (under-declared)",
                )
            )

    # See this function's own docstring: an unparsed script's real
    # imports are genuinely unknown, so an over-declared claim cannot be
    # proven true while any bundled Python script could not be parsed.
    # Iterates the RAW (non-normalized) declared spellings, not
    # declared_pip_normalized, and normalizes only per-entry for the
    # actual comparison -- found live (an independent adversarial review)
    # that reporting the already-normalized/lower-cased form here (e.g.
    # 'pyyaml' for a sidecar that actually wrote 'PyYAML') produces a
    # finding message naming a string that does not appear anywhere in
    # the real sidecar a human would grep for; using the original
    # spelling in the message keeps it searchable against the real file.
    if not unparseable:
        for declared_name in sorted(set(raw_declared_names)):
            declared_name_normalized = _pep503_normalize(declared_name)
            if not any(_pip_declared_for_import(imp, {declared_name_normalized}) for imp in non_stdlib_imports):
                findings.append(
                    Finding(
                        "warning",
                        "deterministic",
                        "packages-pip-over-declared: declared "
                        f"executionRequirements.packages.pip includes {declared_name!r} "
                        "but no bundled script imports it, directly or via the "
                        "alias table (over-declared)",
                    )
                )

    skill_md = skill_dir / "SKILL.md"
    compatibility_text = _extract_compatibility_field(_read_text_best_effort(skill_md)) if skill_md.is_file() else ""
    for declared_name in sorted(set(raw_declared_names)):
        if declared_name not in compatibility_text:
            findings.append(
                Finding(
                    "warning",
                    "heuristic",
                    "packages-pip-vs-compatibility: declared "
                    f"executionRequirements.packages.pip includes {declared_name!r} "
                    "but SKILL.md's compatibility field does not mention it -- "
                    "exact-string, case-sensitive match only (a disclosed "
                    "heuristic limitation, see module docstring)",
                )
            )

    return findings


def _spec_of(instance: Any) -> dict[str, Any]:
    if not isinstance(instance, dict):
        return {}
    spec = instance.get("spec")
    return spec if isinstance(spec, dict) else {}


def find_skill_drift(skill_dir: pathlib.Path) -> list[Finding]:
    """Every drift finding for exactly one skill directory: reads its own
    metadata/gitapex.yaml sidecar and runs find_network_drift/find_tools_drift/
    find_packages_drift against it. Messages carry no skill-name prefix
    (single-target use, the same convention gitapex_check_skill_shape.py's
    own single-target CLI follows) -- find_drift() below adds one when
    aggregating across many."""
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
    findings.extend(find_packages_drift(execution_requirements.get("packages"), skill_dir, scripts))
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
