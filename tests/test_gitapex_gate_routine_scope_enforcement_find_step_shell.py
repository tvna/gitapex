"""Shell-level test for `routine-scope-enforcement-gate.yml`'s own "Find
Routine-connection docs" step.

Issue #1700 (Step 8 adversarial review, Finding 2): the
design-doc save-path convention was renamed from
`docs/superpowers/specs/...` to `docs/gitapex/specs/...`, and this step's
own `find docs/superpowers/specs -maxdepth 1 -iname '*routine*.md'`
invocation was extended to also search `docs/gitapex/specs`, each half
with its own `|| true` so a missing `docs/gitapex/specs` directory (which
does not yet exist anywhere in this repository) does not abort the step
under `set -euo pipefail`.

`tests/test_gitapex_gate_routine_scope_enforcement.py` only ever calls
`gitapex_gate_routine_scope_enforcement.main()` with an already-given doc
list passed as positional CLI arguments -- it never runs the workflow's
own `find`-based discovery step, so that file has no unit-test surface at
all for the change this issue makes to the step itself. This file
extracts the real `run:` block of the "Find Routine-connection docs" step
and executes it against a scratch directory, mirroring the established
pattern in `test_gitapex_skill_audit_gate_diff_step_shell.py` (extract the
shipped text from the YAML and execute it, rather than a paraphrase of
it).

The step is a plain filesystem `find` over the checked-out working tree
(no git operation at all -- see the step's own preceding comment in the
workflow), so the scratch fixture here is a bare directory, not a git
repository.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "routine-scope-enforcement-gate.yml"

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def find_step_script(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """The real `run:` block of the "Find Routine-connection docs" step
    (`id: find`), written out as a script."""
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["routine-scope-enforcement"]["steps"]
    run = next(s["run"] for s in steps if s.get("id") == "find")
    path = tmp_path_factory.mktemp("findstep") / "find_step.sh"
    path.write_text(run, encoding="utf-8")
    return path


def _write(root: pathlib.Path, relative: str, content: str = "# doc\n") -> pathlib.Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _parse_github_output(text: str) -> dict[str, str]:
    """Minimal parser for the `KEY=value` and `KEY<<DELIM\\n...\\nDELIM`
    forms `$GITHUB_OUTPUT` accepts -- enough to read back this one step's
    own `applicable` and `docs` outputs."""
    parsed: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if "<<" in line:
            key, _, delim = line.partition("<<")
            body: list[str] = []
            i += 1
            while i < len(lines) and lines[i] != delim:
                body.append(lines[i])
                i += 1
            parsed[key] = "\n".join(body)
        elif "=" in line:
            key, _, value = line.partition("=")
            parsed[key] = value
        i += 1
    return parsed


def run_find_step(script: pathlib.Path, cwd: pathlib.Path) -> tuple[int, dict[str, str], str]:
    """Run the real find step with cwd `cwd`, returning (returncode,
    parsed $GITHUB_OUTPUT dict, combined output)."""
    output_file = cwd.parent / f"{cwd.name}_gh_output.txt"
    output_file.write_text("", encoding="utf-8")
    env = {**os.environ, "GITHUB_OUTPUT": str(output_file)}
    proc = subprocess.run(["bash", str(script)], cwd=cwd, env=env, capture_output=True, text=True)
    parsed = _parse_github_output(output_file.read_text(encoding="utf-8"))
    return proc.returncode, parsed, proc.stdout + proc.stderr


def test_no_routine_docs_anywhere_reports_not_applicable(
    find_step_script: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    code, out, log = run_find_step(find_step_script, tmp_path)
    assert code == 0
    assert out["applicable"] == "false"
    assert "No Routine-connection docs found" in log


def test_still_finds_a_routine_doc_under_the_old_superpowers_specs_path(
    find_step_script: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Regression guard: `docs/gitapex/specs` does not exist at all in
    this scratch tree (matching this repository's real current state),
    and the old path must keep working exactly as before -- this is also
    the case that proves the added `|| true`/subshell reshape does not
    make `set -euo pipefail` abort the step when the new directory is
    simply absent."""
    _write(tmp_path, "docs/superpowers/specs/2026-07-25-a-routine.md")
    code, out, _ = run_find_step(find_step_script, tmp_path)
    assert code == 0
    assert out["applicable"] == "true"
    assert out["docs"] == "docs/superpowers/specs/2026-07-25-a-routine.md"


def test_finds_a_routine_doc_under_the_new_gitapex_specs_path(
    find_step_script: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    _write(tmp_path, "docs/gitapex/specs/2026-09-03-a-routine.md")
    code, out, _ = run_find_step(find_step_script, tmp_path)
    assert code == 0
    assert out["applicable"] == "true"
    assert out["docs"] == "docs/gitapex/specs/2026-09-03-a-routine.md"


def test_finds_docs_under_both_paths_combined_and_sorted(
    find_step_script: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    _write(tmp_path, "docs/superpowers/specs/2026-07-25-old-routine.md")
    _write(tmp_path, "docs/gitapex/specs/2026-09-03-new-routine.md")
    code, out, _ = run_find_step(find_step_script, tmp_path)
    assert code == 0
    assert out["applicable"] == "true"
    assert out["docs"] == (
        "docs/gitapex/specs/2026-09-03-new-routine.md\ndocs/superpowers/specs/2026-07-25-old-routine.md"
    )


def test_a_non_routine_doc_under_either_path_is_ignored(find_step_script: pathlib.Path, tmp_path: pathlib.Path) -> None:
    _write(tmp_path, "docs/superpowers/specs/2026-07-25-unrelated.md")
    _write(tmp_path, "docs/gitapex/specs/2026-09-03-unrelated.md")
    code, out, _ = run_find_step(find_step_script, tmp_path)
    assert code == 0
    assert out["applicable"] == "false"


def test_a_filename_with_an_embedded_newline_is_rejected_not_silently_passed_through(
    find_step_script: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Security regression guard (CWE-88/CWE-116/CWE-20), found by an
    independent security-axis review of this same step (drafting-a-pr-to-
    merge Step 8, refs #1700): a PR-author-controlled filename containing
    a real embedded newline byte -- POSIX forbids only "/" and NUL in a
    filename, so this is directly constructible, not hypothetical -- could
    otherwise produce a fragment reading exactly "GITAPEX_EOF" on its own
    line, terminating the `docs<<GITAPEX_EOF` heredoc below early and
    letting a later fragment overwrite `applicable` in $GITHUB_OUTPUT; or
    be read by the downstream `xargs -d '\\n'` call as an extra,
    attacker-chosen CLI argument (e.g. an injected `--skills-root`). The
    step's own shape check must reject this before it ever reaches
    $GITHUB_OUTPUT, not merely fail later or pass silently."""
    directory = tmp_path / "docs" / "gitapex" / "specs"
    directory.mkdir(parents=True, exist_ok=True)
    evil_name = "2026-01-01-a-routine\nGITAPEX_EOF\napplicable=false\nx.md"
    (directory / evil_name).write_text("# doc\n", encoding="utf-8")
    code, out, log = run_find_step(find_step_script, tmp_path)
    assert code != 0
    assert "does not match the expected" in log
    assert out.get("applicable") != "true"
