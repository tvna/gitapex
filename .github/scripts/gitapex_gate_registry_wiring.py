#!/usr/bin/env python3
"""Registry-introspection wiring scan.

Issue #682 item 2 (technique measurement group 5, defect J): a
``.github/scripts/*.py`` module can define a registry of named checks -- a
tuple/list of objects each carrying a ``cli_flag`` -- without every row
actually being passed to the script on the command line by the workflow
that invokes it. Argparse still registers the flag with ``default=""``, so
in real CI the corresponding value is always empty, the check's own
``find_missing_*`` logic always sees an empty item list, and the row's own
unit tests (which call that logic directly, supplying the item list
themselves) stay green throughout. Nothing fails; the check silently never
fires. ``.github/scripts/gitapex_gate_skill_audit_disclosure.py``'s own
``_PROCESS_DISCLOSURE_CHECKS`` registry documents this exact failure mode in
its own module docstring, and PR #674 closed it for that one registry with a
hand-written drift test
(``tests/test_gitapex_skill_audit_gate_workflow_wiring.py``'s
``test_every_registered_check_is_passed_on_the_command_line``). This module
generalizes that one hand-written test into a self-discovering scan: a
second registry landing anywhere under ``.github/scripts/`` gets this same
protection with no new test to author, where a hardcoded per-registry test
would need one.

**What counts as a registry.** Any module-level assignment in a
``.github/scripts/*.py`` file whose right-hand side is a tuple or list
literal, where at least one element is a call expression carrying a
``cli_flag=<string literal>`` keyword argument. This is deliberately the
same shape issue #682 itself names ("any iterable of objects carrying a
``cli_flag``"), detected structurally via :mod:`ast` rather than by
importing the module and introspecting live objects -- importing an
arbitrary ``.github/scripts/*.py`` file as a side effect of a CI gate would
execute its module-level code, which is not a property this scan should
depend on.

**What counts as "wired".** Every ``.github/workflows/*.yml``/``*.yaml``
file whose raw text mentions the registry-bearing script's own filename as
a whole token must also contain each discovered ``cli_flag`` string literal
as a whole token somewhere in its own text. "Whole token" means neither
match may be straddled by another identifier/flag/filename character
(``[A-Za-z0-9_.-]``) on either side -- see ``_contains_token`` -- so
``--foo`` does not match inside ``--foo-bar``, and ``gate_x.py`` does not
match inside ``sub_gate_x.py``. An earlier revision of this module used a
plain, unbounded substring test for both and was caught by its own
adversarial review reconstructing exactly this shape: a workflow passing
only the longer, unrelated flag left the shorter registered one silently
unflagged, which is defect J's own failure mode (argparse still registers
the short flag with ``default=""``) reappearing one level up, inside the
detector meant to catch it. This is plain text matching over the raw
workflow text, not real YAML/step-structure parsing -- deliberately so: it
keeps this detector free of any dependency beyond the standard library
(:mod:`ast`, :mod:`re`, :mod:`sys`, :mod:`dataclasses`, :mod:`pathlib`),
matching issue #682's own "under 1 s, stdlib" measurement for this
technique and its Acceptance Criteria Map row requiring items 1-3 to add no
runtime dependency to ``.github/scripts/``. ``PyYAML`` is available in the
``tests/`` plane (see ``tests/test_gitapex_skill_audit_gate_workflow_wiring.py``,
which does parse the one workflow it already knows about structurally), but
that is not a property a general-purpose, self-discovering scan across
every workflow file can lean on without giving up the stdlib-only
constraint.

**Known blind spots, disclosed rather than solved** (same practice
``gitapex_gate_exception_handler_gaps.py`` documents for its own rules):

- A script with a qualifying registry that no workflow file mentions by
  name at all is not flagged. It may be invoked only from a PreToolUse hook
  shell script (``hooks/*.sh``), a legitimate case this scan does not
  attempt to adjudicate -- it only asserts wiring into the CI/workflow
  plane, matching issue #682's own phrasing ("every workflow that invokes
  the script").
- A ``cli_flag`` value that is not a string literal (built at runtime, e.g.
  string-formatted from another constant) cannot be extracted by static
  analysis and is silently skipped rather than flagged either way.
- A workflow file that merely mentions a script's filename as a whole token
  -- in a comment, or a step unrelated to actually invoking it -- is
  treated the same as a real invocation. Six scripts in this repository
  today (including ``gitapex_post_merge_retro.py``, mentioned by three
  separate workflows) are named by more than one workflow file, so this is
  not a hypothetical shape; none of the six carries a qualifying cli_flag
  registry as of the measurement in the PR that added this module, which is
  the narrower, actually-verified claim -- "no script name appears in more
  than one workflow" would be false. It is disclosed because a future
  registry landing in one of those six, or any other multiply-mentioned
  script, could produce a false positive this scan cannot distinguish from
  a real one.

**The converse direction (issue #797): orphaned workflow flags.**
``find_unwired_rows`` above only checks registry -> workflow. It does not
catch the opposite drift shape: a workflow's ``run:`` step still passes a
``--flag``-shaped token to a registry-bearing script that no longer defines
it at all (a renamed or removed registry row, or a typo). ``find_orphaned_flags``
adds that direction.

*Why this is worth adding, measured rather than assumed.* A reconstruction
(a registry row removed, the stale flag left in the invoking workflow) shows
two different failure modes depending on how the workflow reaches the
invocation. On an **unconditional** path, ``argparse.parse_args()`` already
fails loudly and immediately: ``error: unrecognized arguments: --beta-items
b``, exit 2, on the very next CI run -- this scan adds earlier feedback
(caught in review, on this diff's own CI, rather than whenever that code
path next executes) but not a new failure class. On a **conditional /
branch-gated** path -- exactly the shape this repository's own
``skill-audit-gate.yml`` uses (``if:
steps.diff.outputs.applicable == 'true'``) for its one real registry today
-- the reconstruction's ordinary-path run exits 0 with no output difference
at all; the stale flag only surfaces the day that branch condition is
finally true. That is genuinely silent drift, not merely delayed feedback,
and it is not hypothetical: the one real registry-bearing script in this
repository is invoked exactly that way.

*The exclusion rule.* A script's CLI surface is not exclusively
registry-derived -- ``gitapex_gate_skill_audit_disclosure.py`` also defines
``--body``, ``--description-changed-skills``, ``--needs-eval-coverage-skills``,
and ``--skill-md-changed`` via its own explicit ``parser.add_argument("--foo",
...)`` calls, none of them registry rows. ``_iter_hardcoded_flags`` finds
these the same structural way ``find_registry_rows`` finds registry rows:
walk the script's AST for any ``*.add_argument(...)`` call whose first
positional argument is a string literal starting with ``-``. A
registry-driven call (``parser.add_argument(check.cli_flag, ...)``) passes
an attribute expression there, not a string literal, so it is naturally
excluded from this set -- already counted via the registry rows instead.
``-h``/``--help`` (always available, argparse's own default) is excluded
unconditionally. A token is only reported when it matches none of: the
script's live registry ``cli_flag`` values, its own hardcoded flags, or
``--help``.

*Scoping to avoid cross-script false positives.* Unlike ``find_unwired_rows``,
which only needs to know a flag appears *somewhere* in a workflow file that
mentions the script, this direction must not misattribute a flag that
belongs to a *different* step's invocation of an unrelated script in the
same workflow file. ``_iter_run_blocks`` extracts each ``run:`` step's own
text via YAML block-scalar indentation (still plain text/regex, not real
YAML parsing -- same stdlib-only constraint as the rest of this module):
a single-line ``run: <command>`` is that line's remainder; a block form
(``run: |``/``run: >``) collects every following line more indented than
the ``run:`` key itself, stopping at the first line that dedents back to it
or below. Flag-shaped tokens are then extracted only from the portion of a
matching run block starting at that block's first bounded occurrence of the
script's filename, not the whole block -- issue #1035's own standardization
onto ``uv run`` (e.g. ``uv run --frozen python3 .github/scripts/gate_x.py
--foo``) put a real, observed instance of the next blind spot on `main`:
without this scoping, ``--frozen`` (a flag belonging to ``uv``, preceding
the script's own filename in the same run block) would misattribute to the
script as an orphaned flag. Scoping to at-or-after the filename excludes
anything before the invocation while keeping every flag that follows it.

**Known blind spots for this direction, disclosed rather than solved:**

- A flag-shaped token (``--foo``) inside a comment line within a matching
  run block *at or after* the script's own filename, or inside a quoted
  *value* string rather than an actual argument position, is
  indistinguishable from a real invocation argument to this plain-text scan
  and would be flagged the same way. Not yet observed in this repository's
  real invocations, measured at the point this direction was last revised.
- Only long-form ``--flag`` tokens are considered candidates; a short-form
  single-dash flag (``-x``) is never extracted, matching this repository's
  own convention of registering only long-form flags today.
- The exclusion rule is tied to today's one real ``*.add_argument("--foo",
  ...)`` shape; a script that builds its non-registry flags a structurally
  different way (e.g. via a helper function rather than a direct
  ``add_argument`` call) would not have those flags recognized as
  hardcoded, and every one of its own ordinary arguments would false-positive.
  Re-measure this rule's zero-finding claim whenever a new registry-bearing
  script lands, the same discipline the wiring direction's own docstring
  already asks for.

**Re-verified, not inherited** (issue #682's own first Acceptance Criteria
Map row): ``tests/test_gitapex_gate_registry_wiring.py`` carries a fixture
pair reconstructing defect J's shape -- a registry row whose ``cli_flag`` is
never passed by its invoking workflow -- built from the real
``_PROCESS_DISCLOSURE_CHECKS``/``skill-audit-gate.yml`` structure rather
than copied from it, since defect J's original historical commit predates
this general pattern and issue #682's criterion explicitly allows
"check out or reconstruct". The real repository is measured separately: as
of the commit that added this module, exactly one qualifying registry
exists (``_PROCESS_DISCLOSURE_CHECKS``), it is fully wired, and this scan
reports zero findings against ``main``.

Run standalone: ``python .github/scripts/gitapex_gate_registry_wiring.py``
(exit 1 on drift, exit 0 clean) or via the pytest gate in
``tests/test_gitapex_gate_registry_wiring.py``.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# A character that can continue an identifier, a CLI flag (--foo-bar), or a
# filename (gate_x.py) -- used by _contains_token to require a real token
# boundary on both sides of a match, not a bare substring test.
_ADJACENT_CHAR_RE = r"[A-Za-z0-9_.-]"

# A long-form CLI flag token (--foo, --foo-bar), bounded the same way
# _contains_token bounds a single known token -- see find_orphaned_flags.
_FLAG_TOKEN_RE = re.compile(rf"(?<!{_ADJACENT_CHAR_RE})--[A-Za-z][A-Za-z0-9-]*(?!{_ADJACENT_CHAR_RE})")

# A GitHub Actions step's `run:` key, capturing its own indentation and
# whatever follows on the same line -- see _iter_run_blocks.
_RUN_KEY_RE = re.compile(r"^([ \t]*)run:(.*)$")

# argparse always registers these regardless of what a script's own code
# adds -- never a genuinely orphaned flag.
_ALWAYS_AVAILABLE_FLAGS = frozenset({"-h", "--help"})


class RegistryReadError(Exception):
    """A ``.github/scripts/*.py`` or ``.github/workflows/*`` file could not
    be read as UTF-8, a scripts file could not be parsed as Python, or an
    expected scripts/workflows directory does not exist -- exit 1, never an
    uncaught traceback."""


def _token_pattern(token: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!{_ADJACENT_CHAR_RE}){re.escape(token)}(?!{_ADJACENT_CHAR_RE})")


def _contains_token(text: str, token: str) -> bool:
    """True if `token` appears in `text` with no identifier/flag/filename
    character immediately before or after it -- so `--foo` does not match
    inside `--foo-bar`, and `gate_x.py` does not match inside
    `sub_gate_x.py`. See the module docstring's "What counts as wired"
    section for why a plain substring test is not enough."""
    return _token_pattern(token).search(text) is not None


def _text_from_first_token(text: str, token: str) -> str:
    """The suffix of `text` starting at the first bounded occurrence of
    `token` (see `_contains_token`), or `""` if `token` does not occur.
    Issue #1035: a `run:` block invoking a script through `uv run` (e.g.
    `uv run --frozen python3 .github/scripts/gate_x.py --foo`) carries a
    `--flag`-shaped token (`--frozen`) that precedes the script's own
    filename and belongs to `uv`, not to the script -- scoping flag
    extraction to text at-or-after the script name excludes it while
    keeping every flag that follows, matching the module docstring's own
    "must not misattribute a flag" scoping rule one level finer than the
    whole-block scoping it already does."""
    match = _token_pattern(token).search(text)
    return text[match.start() :] if match else ""


def _read_text_or_raise(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RegistryReadError(f"{path}: cannot be read as UTF-8: {error}") from error


@dataclass(frozen=True)
class RegistryRow:
    """One ``cli_flag``-bearing element found inside a module-level
    tuple/list assignment."""

    script: Path
    registry_name: str
    cli_flag: str
    lineno: int


def _iter_cli_flag_rows(tree: ast.Module, script: Path) -> list[RegistryRow]:
    """Walk every module-level-or-nested Assign/AnnAssign whose value is a
    tuple/list literal, yielding one RegistryRow per element carrying a
    string-literal ``cli_flag`` keyword argument. Both plain assignment
    (``_CHECKS = (...)``) and the annotated form
    (``_CHECKS: Final[tuple[...]] = (...)``) are covered -- the latter is
    already this repository's own style in
    ``gitapex_run_precommit_mypy.py``'s ``MYPY_GROUPS``, so a registry
    written that way must not be invisible to this scan. Nesting depth is
    not restricted: a registry built inside a function or class body is
    still a registry for this scan's purposes, and restricting to strict
    module-level top-level statements would only narrow coverage for no
    measured benefit."""
    rows: list[RegistryRow] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            target: ast.expr = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target = node.target
            value = node.value
        else:
            continue
        if not isinstance(value, (ast.Tuple, ast.List)):
            continue
        registry_name = target.id if isinstance(target, ast.Name) else "<unknown>"
        for element in value.elts:
            if not isinstance(element, ast.Call):
                continue
            for keyword in element.keywords:
                if (
                    keyword.arg == "cli_flag"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    rows.append(
                        RegistryRow(
                            script=script,
                            registry_name=registry_name,
                            cli_flag=keyword.value.value,
                            lineno=element.lineno,
                        )
                    )
    return rows


def _iter_script_files(scripts_dir: Path) -> list[Path]:
    if not scripts_dir.is_dir():
        raise RegistryReadError(f"{scripts_dir}: not a directory")
    return sorted(scripts_dir.glob("*.py"))


def _iter_workflow_files(workflows_dir: Path) -> list[Path]:
    if not workflows_dir.is_dir():
        raise RegistryReadError(f"{workflows_dir}: not a directory")
    return sorted(list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml")))


def _parse_script_or_raise(script: Path, source: str) -> ast.Module:
    """Parse `source` (already read from `script`) as Python, raising
    RegistryReadError with the script's own path on a SyntaxError. Shared by
    find_registry_rows and find_orphaned_flags -- both need an AST for the
    same script, and sharing this one parse-with-error-handling path keeps
    the failure mode covered by a single fixture
    (test_find_registry_rows_raises_on_unparseable_python) instead of a
    second, structurally-unreachable-in-practice copy (a script that parsed
    successfully once cannot fail to parse again on the same unchanged
    source)."""
    try:
        return ast.parse(source, filename=str(script))
    except SyntaxError as error:
        raise RegistryReadError(f"{script}: cannot be parsed as Python: {error}") from error


def find_registry_rows(scripts_dir: Path = SCRIPTS_DIR) -> list[RegistryRow]:
    """Discover every cli_flag-bearing registry row across scripts_dir's own
    *.py files (not recursive -- .github/scripts/ has no subdirectories of
    its own gate scripts), sorted for determinism."""
    rows: list[RegistryRow] = []
    for script in _iter_script_files(scripts_dir):
        source = _read_text_or_raise(script)
        tree = _parse_script_or_raise(script, source)
        rows.extend(_iter_cli_flag_rows(tree, script))
    return sorted(rows, key=lambda row: (str(row.script), row.registry_name, row.cli_flag))


def _iter_hardcoded_flags(tree: ast.Module) -> set[str]:
    """Every flag string passed as a positional, string-literal argument to
    a `*.add_argument(...)` call -- a script's own explicitly authored,
    non-registry CLI surface (e.g. --body, --skill-md-changed in
    gitapex_gate_skill_audit_disclosure.py). A registry-driven call such as
    `parser.add_argument(check.cli_flag, ...)` passes an attribute
    expression there, not a string literal, so it is naturally excluded --
    already counted via find_registry_rows instead. See the module
    docstring's "converse direction" section for why this exclusion is
    needed at all."""
    flags: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
        ):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("-"):
                flags.add(arg.value)
    return flags


def _iter_run_blocks(text: str) -> list[str]:
    """Extract each GitHub Actions step's own `run:` text from a workflow
    file's raw text -- a single-line `run: <command>` is that line's
    remainder; a block form (`run: |`/`run: >`, with any chomping
    indicator) collects every following line more indented than the `run:`
    key itself, stopping at the first line that dedents back to it (or
    below) or at end of file. Plain indentation-based text scanning, not
    real YAML parsing -- see the module docstring for why this module stays
    stdlib-only. Used by find_orphaned_flags to scope flag-token extraction
    to the specific step invoking a registry-bearing script, so a flag
    belonging to a different step's invocation of an unrelated script in
    the same file is never misattributed to this one."""
    lines = text.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        match = _RUN_KEY_RE.match(lines[index])
        if match is None:
            index += 1
            continue
        indent = len(match.group(1))
        rest = match.group(2).strip()
        if rest and rest not in ("|", ">", "|-", "|+", ">-", ">+"):
            blocks.append(rest)
            index += 1
            continue
        block_lines: list[str] = []
        index += 1
        while index < len(lines):
            line = lines[index]
            if line.strip() == "":
                block_lines.append(line)
                index += 1
                continue
            if len(line) - len(line.lstrip(" \t")) <= indent:
                break
            block_lines.append(line)
            index += 1
        blocks.append("\n".join(block_lines))
    return blocks


def _iter_flag_tokens(text: str) -> set[str]:
    """Every long-form `--flag`-shaped token in `text`, bounded the same
    way `_contains_token` bounds a single known token. Only long-form flags
    are considered -- see the module docstring's disclosed blind spot for
    why short-form single-dash flags are out of scope."""
    return set(_FLAG_TOKEN_RE.findall(text))


def find_orphaned_flags(scripts_dir: Path = SCRIPTS_DIR, workflows_dir: Path = WORKFLOWS_DIR) -> list[str]:
    """Return one finding per (workflow, flag) pair where a workflow's own
    run: step invokes a registry-bearing script with a `--flag`-shaped
    token that matches none of: the script's live registry `cli_flag`
    values, its own hardcoded (non-registry) `add_argument` flags, or
    `--help` -- the converse of find_unwired_rows (issue #797). See the
    module docstring's "converse direction" section for the exclusion rule
    and its disclosed blind spots."""
    rows_by_script: dict[Path, list[RegistryRow]] = {}
    for row in find_registry_rows(scripts_dir):
        rows_by_script.setdefault(row.script, []).append(row)

    # workflows_dir is validated unconditionally, even when rows_by_script
    # is empty and the loop below never runs -- same fail-open shape
    # find_unwired_rows's own equivalent comment already documents:
    # short-circuiting here before ever touching workflows_dir would
    # silently return a false-clean [] when workflows_dir is itself
    # misconfigured, for exactly the case where scripts_dir happens to have
    # no qualifying registry (e.g. mid-refactor).
    workflow_texts = _workflow_texts(workflows_dir)
    findings: list[str] = []
    for script in sorted(rows_by_script, key=str):
        registry_flags = {row.cli_flag for row in rows_by_script[script]}
        source = _read_text_or_raise(script)
        tree = _parse_script_or_raise(script, source)
        known_flags = registry_flags | _iter_hardcoded_flags(tree) | _ALWAYS_AVAILABLE_FLAGS

        for workflow in sorted(workflow_texts, key=str):
            text = workflow_texts[workflow]
            if not _contains_token(text, script.name):
                continue
            orphaned: set[str] = set()
            for block in _iter_run_blocks(text):
                invocation = _text_from_first_token(block, script.name)
                if not invocation:
                    continue
                orphaned.update(_iter_flag_tokens(invocation) - known_flags)
            for flag in sorted(orphaned):
                findings.append(
                    f"{workflow.name}: passes {flag!r} to {script.name} but it defines no such "
                    f"argument (known: {', '.join(sorted(known_flags))})"
                )
    return sorted(findings)


def _workflow_texts(workflows_dir: Path) -> dict[Path, str]:
    """Read every workflow file's text exactly once, sorted for
    determinism. Shared by find_invoking_workflows and find_unwired_rows so
    neither re-reads a file the other already read -- an earlier revision
    of find_unwired_rows re-read each matched workflow with no error
    handling at all, silently reintroducing the uncaught-traceback failure
    mode RegistryReadError exists to close."""
    return {workflow: _read_text_or_raise(workflow) for workflow in _iter_workflow_files(workflows_dir)}


def find_invoking_workflows(script_name: str, workflows_dir: Path = WORKFLOWS_DIR) -> list[Path]:
    """Return every workflow file whose raw text mentions script_name as a
    whole token, sorted for determinism. Plain text matching over the whole
    file, not real YAML/step-structure parsing -- see the module docstring
    for why."""
    return [workflow for workflow, text in _workflow_texts(workflows_dir).items() if _contains_token(text, script_name)]


def find_unwired_rows(scripts_dir: Path = SCRIPTS_DIR, workflows_dir: Path = WORKFLOWS_DIR) -> list[str]:
    """Return one finding per (row, workflow) pair where a discovered
    cli_flag never appears, as a whole token, in a workflow that otherwise
    mentions the row's own script by filename. A script with no invoking
    workflow at all contributes no finding -- see the module docstring's
    known-blind-spots section."""
    rows_by_script: dict[Path, list[RegistryRow]] = {}
    for row in find_registry_rows(scripts_dir):
        rows_by_script.setdefault(row.script, []).append(row)

    # workflows_dir is validated unconditionally, even when rows_by_script
    # is empty and the loop below never runs -- an earlier revision
    # short-circuited here before touching workflows_dir at all, which
    # silently reopened the "fail open on a missing directory" defect this
    # module's directory-existence checks otherwise close, for exactly the
    # case where .github/scripts/ happens to have no qualifying registry
    # (e.g. mid-refactor) and WORKFLOWS_DIR is itself misconfigured.
    findings: list[str] = []
    workflow_texts = _workflow_texts(workflows_dir)
    for script in sorted(rows_by_script, key=str):
        rows = rows_by_script[script]
        for workflow, text in workflow_texts.items():
            if not _contains_token(text, script.name):
                continue
            for row in rows:
                if not _contains_token(text, row.cli_flag):
                    findings.append(
                        f"{workflow.name}: invokes {script.name} but never passes "
                        f"{row.cli_flag!r} (registered in {row.registry_name} at "
                        f"{script.name}:{row.lineno})"
                    )
    return sorted(findings)


def main() -> int:
    # Looked up as module globals at call time, deliberately not relying on
    # find_unwired_rows's own default parameter values -- those are bound
    # once at function-definition time, so a caller (e.g. a test)
    # monkeypatching SCRIPTS_DIR/WORKFLOWS_DIR after import would silently
    # have no effect on them.
    try:
        findings = find_unwired_rows(SCRIPTS_DIR, WORKFLOWS_DIR) + find_orphaned_flags(SCRIPTS_DIR, WORKFLOWS_DIR)
    except RegistryReadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if findings:
        print("registry-wiring drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("OK: no unwired cli_flag registry rows or orphaned workflow flags found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
