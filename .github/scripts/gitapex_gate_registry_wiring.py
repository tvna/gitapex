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


class RegistryReadError(Exception):
    """A ``.github/scripts/*.py`` or ``.github/workflows/*`` file could not
    be read as UTF-8, a scripts file could not be parsed as Python, or an
    expected scripts/workflows directory does not exist -- exit 1, never an
    uncaught traceback."""


def _contains_token(text: str, token: str) -> bool:
    """True if `token` appears in `text` with no identifier/flag/filename
    character immediately before or after it -- so `--foo` does not match
    inside `--foo-bar`, and `gate_x.py` does not match inside
    `sub_gate_x.py`. See the module docstring's "What counts as wired"
    section for why a plain substring test is not enough."""
    pattern = re.compile(rf"(?<!{_ADJACENT_CHAR_RE}){re.escape(token)}(?!{_ADJACENT_CHAR_RE})")
    return pattern.search(text) is not None


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


def find_registry_rows(scripts_dir: Path = SCRIPTS_DIR) -> list[RegistryRow]:
    """Discover every cli_flag-bearing registry row across scripts_dir's own
    *.py files (not recursive -- .github/scripts/ has no subdirectories of
    its own gate scripts), sorted for determinism."""
    rows: list[RegistryRow] = []
    for script in _iter_script_files(scripts_dir):
        source = _read_text_or_raise(script)
        try:
            tree = ast.parse(source, filename=str(script))
        except SyntaxError as error:
            raise RegistryReadError(f"{script}: cannot be parsed as Python: {error}") from error
        rows.extend(_iter_cli_flag_rows(tree, script))
    return sorted(rows, key=lambda row: (str(row.script), row.registry_name, row.cli_flag))


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
        findings = find_unwired_rows(SCRIPTS_DIR, WORKFLOWS_DIR)
    except RegistryReadError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if findings:
        print("registry-wiring drift:")
        for finding in findings:
            print(f"  {finding}")
        return 1
    print("OK: no unwired cli_flag registry rows found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
