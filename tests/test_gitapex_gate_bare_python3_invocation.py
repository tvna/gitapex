"""Issue #1035: every `.github/scripts/*.py` invocation from a workflow
`run:` step must go through `uv run`. See
`.github/scripts/gitapex_gate_bare_python3_invocation.py`'s own module
docstring for the incident this gate exists to prevent from recurring.
"""

from __future__ import annotations

import json
import pathlib
import time

import gitapex_gate_bare_python3_invocation as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _write_in(target_dir: pathlib.Path, name: str, content: str) -> pathlib.Path:
    """Write `content` to `target_dir / name`, creating `target_dir` (and
    any missing parents) first. Returns `target_dir` -- both `_write` and
    `_write_hook` below hand this back to their own callers, which is why
    this shared helper returns the directory rather than the file path."""
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / name).write_text(content, encoding="utf-8")
    return target_dir


def _write(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    return _write_in(tmp_path / ".github" / "workflows", name, content)


def _write_hook(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    return _write_in(tmp_path / "hooks", name, content)


# --- happy paths ---


def test_uv_run_prefixed_invocation_passes(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "clean.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          uv run --frozen python3 .github/scripts/gitapex_gate_foo.py\n",
    )
    assert gate.find_bare_invocations(workflows_dir) == []


def test_no_script_invocation_at_all_passes(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "clean.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: echo hi\n",
    )
    assert gate.find_bare_invocations(workflows_dir) == []


def test_step_with_uses_not_run_is_ignored(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "clean.yml",
        "jobs:\n  a:\n    steps:\n      - name: checkout\n        uses: actions/checkout@v4\n",
    )
    assert gate.find_bare_invocations(workflows_dir) == []


def test_job_with_no_steps_key_is_ignored(tmp_path: pathlib.Path) -> None:
    # e.g. a reusable-workflow call job (`uses:` at job level, no steps:).
    workflows_dir = _write(tmp_path, "reusable.yml", "jobs:\n  a:\n    uses: ./.github/workflows/other.yml\n")
    assert gate.find_bare_invocations(workflows_dir) == []


# --- the defect this gate exists to catch ---


def test_bare_python3_invocation_is_flagged(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "bare.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          python3 .github/scripts/gitapex_gate_foo.py\n",
    )
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    path, lineno, line = findings[0]
    assert "bare.yml" in path
    assert "[a/run]" in path
    assert lineno == 1
    assert line == "python3 .github/scripts/gitapex_gate_foo.py"


def test_piped_invocation_is_flagged(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "piped.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          cat foo | python3 .github/scripts/gitapex_gate_foo.py\n",
    )
    assert len(gate.find_bare_invocations(workflows_dir)) == 1


def test_xargs_invocation_is_flagged(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "xargs.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          printf '%s\\n' \"$X\" | xargs -d '\\n' -r python3 .github/scripts/gitapex_gate_foo.py --flag\n",
    )
    assert len(gate.find_bare_invocations(workflows_dir)) == 1


def test_multiple_bare_invocations_in_one_step_are_all_flagged(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "multi.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          python3 .github/scripts/gitapex_gate_foo.py\n"
        "          python3 .github/scripts/gitapex_gate_bar.py\n",
    )
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 2
    assert {f[1] for f in findings} == {1, 2}


def test_bare_invocation_across_multiple_jobs_and_files_all_flagged(tmp_path: pathlib.Path) -> None:
    _write(
        tmp_path,
        "one.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: python3 .github/scripts/gitapex_x.py\n",
    )
    workflows_dir = _write(
        tmp_path,
        "two.yml",
        "jobs:\n  b:\n    steps:\n      - name: run\n        run: python3 .github/scripts/gitapex_y.py\n",
    )
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 2


# --- adversarial: a decoy "uv run" elsewhere must not suppress a real
# bare invocation on a different line of the same step (defeat-test-
# disclosure, issue #998's own convention: at least one test specifically
# constructed to try to bypass the new detection logic, not merely
# exercise its happy path) ---


def test_decoy_uv_run_on_a_different_line_does_not_suppress_detection(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "decoy.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          # this step correctly uses uv run elsewhere\n"
        "          uv run --frozen python3 .github/scripts/gitapex_gate_ok.py\n"
        "          python3 .github/scripts/gitapex_gate_snuck_in.py\n",
    )
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "gitapex_gate_snuck_in.py" in findings[0][2]


def test_uv_run_substring_inside_an_unrelated_word_does_not_suppress_detection(tmp_path: pathlib.Path) -> None:
    # "uv run" is checked with word boundaries; a line that merely
    # contains "uv" and "run" as parts of other tokens (not the literal
    # command) must still be flagged as bare.
    workflows_dir = _write(
        tmp_path,
        "wordboundary.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          echo uvrun && python3 .github/scripts/gitapex_gate_foo.py\n",
    )
    assert len(gate.find_bare_invocations(workflows_dir)) == 1


def test_unrelated_uv_run_command_on_the_same_line_does_not_suppress_detection(tmp_path: pathlib.Path) -> None:
    # Code-review defeat case: `uv run` present on the same line, but
    # wrapping a DIFFERENT command (joined by `&&`), not the flagged
    # invocation -- a plain "does the line contain uv run" check would
    # have missed this.
    workflows_dir = _write(
        tmp_path,
        "shellop.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          uv run --frozen true && python3 .github/scripts/gitapex_gate_foo.py\n",
    )
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "gitapex_gate_foo.py" in findings[0][2]


def test_uv_run_in_a_trailing_comment_does_not_suppress_a_preceding_bare_invocation(
    tmp_path: pathlib.Path,
) -> None:
    # Another defeat case: "uv run" text appears on the same line, but
    # AFTER the bare invocation (in a trailing comment), not wrapping it.
    workflows_dir = _write(
        tmp_path,
        "trailingcomment.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          python3 .github/scripts/gitapex_gate_foo.py  # TODO: migrate to uv run\n",
    )
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "gitapex_gate_foo.py" in findings[0][2]


def test_whole_line_comment_mentioning_the_invocation_shape_is_not_flagged(tmp_path: pathlib.Path) -> None:
    # CodeRabbit review (PR #1041): a documentation line that is entirely
    # a shell comment never executes, so a `python3 .github/scripts/*.py`
    # phrase inside one must not be graded as a real invocation.
    workflows_dir = _write(
        tmp_path,
        "wholelinecomment.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          # python3 .github/scripts/gitapex_gate_foo.py\n"
        "          uv run --frozen python3 .github/scripts/gitapex_gate_real.py\n",
    )
    assert gate.find_bare_invocations(workflows_dir) == []


def test_indented_whole_line_comment_is_not_flagged(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "indentedcomment.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "              # python3 .github/scripts/gitapex_gate_foo.py\n",
    )
    assert gate.find_bare_invocations(workflows_dir) == []


def test_two_invocations_on_one_line_are_graded_independently(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(
        tmp_path,
        "mixed.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        "      - name: run\n"
        "        run: |\n"
        "          python3 .github/scripts/gitapex_bare.py"
        " && uv run --frozen python3 .github/scripts/gitapex_wrapped.py\n",
    )
    findings = gate.find_bare_invocations(workflows_dir)
    # Exactly one finding, not two: the wrapped invocation is correctly
    # excluded even though its script name appears in the same reported
    # line text as the bare one (both are on the same physical line).
    assert len(findings) == 1
    assert "gitapex_bare.py" in findings[0][2]


# --- fail-closed on malformed/incomplete input (dimension 15) ---


def test_missing_workflows_directory_is_a_finding(tmp_path: pathlib.Path) -> None:
    findings = gate.find_bare_invocations(tmp_path / "does-not-exist")
    assert len(findings) == 1
    assert "not found" in findings[0][2]


def test_workflows_directory_with_no_yaml_files_is_a_finding(tmp_path: pathlib.Path) -> None:
    empty_dir = tmp_path / ".github" / "workflows"
    empty_dir.mkdir(parents=True)
    (empty_dir / "README.md").write_text("not a workflow\n", encoding="utf-8")
    findings = gate.find_bare_invocations(empty_dir)
    assert len(findings) == 1
    assert "no *.yml or *.yaml" in findings[0][2]


def test_undecodable_file_is_a_finding_not_a_skip(tmp_path: pathlib.Path) -> None:
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "bad.yml").write_bytes(b"\xff\xfe\x00bad")
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "could not decode" in findings[0][2]


def test_unreadable_file_is_a_finding_not_an_uncaught_exception(tmp_path: pathlib.Path) -> None:
    # A path glob() discovers can still fail to read for reasons other
    # than a decode error (permissions, deleted mid-scan) -- read_text()
    # on a directory raises IsADirectoryError (an OSError subclass), a
    # portable way to reproduce that without relying on permission bits.
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "trap.yml").mkdir()
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "could not decode" in findings[0][2]


def test_invalid_yaml_is_a_finding(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(tmp_path, "broken.yml", "jobs: [unclosed\n")
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "could not parse as YAML" in findings[0][2]


def test_non_mapping_top_level_is_a_finding(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(tmp_path, "list.yml", "- just\n- a\n- list\n")
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "did not parse to a mapping" in findings[0][2]


def test_missing_jobs_key_is_a_finding(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(tmp_path, "nojobs.yml", "name: no jobs here\n")
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "no jobs:" in findings[0][2]


def test_job_not_a_mapping_is_a_finding(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(tmp_path, "badjob.yml", "jobs:\n  a: not-a-mapping\n")
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "is not a mapping" in findings[0][2]


def test_steps_not_a_list_is_a_finding(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(tmp_path, "badsteps.yml", "jobs:\n  a:\n    steps: not-a-list\n")
    findings = gate.find_bare_invocations(workflows_dir)
    assert len(findings) == 1
    assert "steps: is not a list" in findings[0][2]


def test_step_that_is_not_a_mapping_is_skipped_not_crashed(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(tmp_path, "weirdstep.yml", "jobs:\n  a:\n    steps:\n      - just-a-string\n")
    assert gate.find_bare_invocations(workflows_dir) == []


def test_run_value_that_is_not_a_string_is_skipped_not_crashed(tmp_path: pathlib.Path) -> None:
    workflows_dir = _write(tmp_path, "nullrun.yml", "jobs:\n  a:\n    steps:\n      - name: x\n        run: null\n")
    assert gate.find_bare_invocations(workflows_dir) == []


# --- CLI ---


def test_main_returns_zero_on_clean_dir(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    workflows_dir = _write(
        tmp_path,
        "clean.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: uv run --frozen python3 .github/scripts/x.py\n",
    )
    monkeypatch.setattr("sys.argv", ["prog", str(workflows_dir)])
    assert gate.main() == 0
    assert "No bare" in capsys.readouterr().out


def test_main_returns_one_and_prints_findings_on_bare_invocation(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    workflows_dir = _write(
        tmp_path,
        "bare.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: python3 .github/scripts/x.py\n",
    )
    monkeypatch.setattr("sys.argv", ["prog", str(workflows_dir)])
    assert gate.main() == 1
    out = capsys.readouterr().out
    assert "bare.yml" in out
    assert "x.py" in out


# --- hooks/*.sh shell-variable-indirected invocations (WARNING tier,
# issue #1446 Item 2): a hooks/*.sh script almost never invokes a
# `.github/scripts/*.py` gate directly on the same line -- it assigns the
# path to a shell variable on one line, then invokes `python3 "$var"` on a
# later line, which `find_bare_invocations`'s same-line regex cannot see.
# `find_hooks_shell_indirected_invocations` closes that blind spot with a
# two-step static scan scoped to the direct single-assignment-then-
# invocation shape this repository's real hooks/*.sh files actually use. ---


def test_hooks_shell_indirected_bare_invocation_is_flagged(tmp_path: pathlib.Path) -> None:
    # Reproduces hooks/check-pr-skill-audit-disclosure.sh's real shape:
    # a variable assignment targeting a .github/scripts/*.py path, then a
    # bare `python3 "$var"` invocation several lines later.
    hooks_dir = _write_hook(
        tmp_path,
        "check-pr-skill-audit-disclosure.sh",
        "#!/bin/bash\n"
        'repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || repo_root=""\n'
        'full_gate="${repo_root}/.github/scripts/gitapex_gate_skill_audit_disclosure.py"\n'
        "\n"
        'if [ -f "$full_gate" ]; then\n'
        '  if full_output=$(cd "$repo_root" && python3 "$full_gate" \\\n'
        '      --check-diff "$merge_base" HEAD --body-file "$body_file" 2>&1); then\n'
        "    full_exit=0\n"
        "  fi\n"
        "fi\n",
    )
    findings = gate.find_hooks_shell_indirected_invocations(hooks_dir)
    assert len(findings) == 1
    path, lineno, line = findings[0]
    assert "check-pr-skill-audit-disclosure.sh" in path
    assert lineno == 6
    assert "full_gate" in line


def test_hooks_shell_indirected_invocation_uv_run_wrapped_is_not_flagged(tmp_path: pathlib.Path) -> None:
    hooks_dir = _write_hook(
        tmp_path,
        "wrapped.sh",
        "#!/bin/bash\n"
        'full_gate="${repo_root}/.github/scripts/gitapex_gate_skill_audit_disclosure.py"\n'
        'uv run --frozen python3 "$full_gate" --check-diff a b\n',
    )
    assert gate.find_hooks_shell_indirected_invocations(hooks_dir) == []


def test_hooks_shell_indirected_variable_targeting_hooks_py_is_not_flagged(tmp_path: pathlib.Path) -> None:
    # A hooks/*.py sibling script is deliberately stdlib-only,
    # self-contained, and bare-invoked by design (docs/repository-layout.md)
    # -- a shell variable pointing at one must never be flagged even
    # though it is invoked bare, exactly like every other real hooks/*.sh
    # file in this repository (only .github/scripts/*.py targets are
    # in scope).
    hooks_dir = _write_hook(
        tmp_path,
        "check-bash-safety.sh",
        "#!/bin/bash\n"
        'classifier="${repo_root}/hooks/gitapex_check_bash_safety.py"\n'
        'classifier_output=$(printf %s "$input" | python3 "$classifier" 2>/dev/null)\n',
    )
    assert gate.find_hooks_shell_indirected_invocations(hooks_dir) == []


def test_hooks_shell_indirected_unquoted_invocation_is_flagged(tmp_path: pathlib.Path) -> None:
    hooks_dir = _write_hook(
        tmp_path,
        "unquoted.sh",
        '#!/bin/bash\ngate_script="${repo_root}/.github/scripts/gitapex_gate_foo.py"\npython3 $gate_script --flag\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(hooks_dir)
    assert len(findings) == 1
    assert "gate_script" in findings[0][2]


def test_hooks_shell_indirected_brace_wrapped_invocation_is_flagged(tmp_path: pathlib.Path) -> None:
    # Defeat case found in adversarial review (issue #1446 step 8): the
    # variable reference at the *invocation* site can be brace-wrapped
    # (`python3 "${var}"`), not just the bare `$var` form
    # test_hooks_shell_indirected_bare_invocation_is_flagged already
    # covers -- a plausible shell idiom this repository's own hooks/*.sh
    # files already use at *assignment* sites (e.g.
    # `full_gate="${repo_root}/..."`). Confirmed to previously slip past
    # var_ref undetected before the fix.
    hooks_dir = _write_hook(
        tmp_path,
        "brace-wrapped.sh",
        '#!/bin/bash\nfull_gate="${repo_root}/.github/scripts/gitapex_gate_foo.py"\npython3 "${full_gate}"\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(hooks_dir)
    assert len(findings) == 1
    assert "full_gate" in findings[0][2]


def test_hooks_shell_indirected_brace_wrapped_uv_run_wrapped_is_not_flagged(tmp_path: pathlib.Path) -> None:
    hooks_dir = _write_hook(
        tmp_path,
        "brace-wrapped-ok.sh",
        '#!/bin/bash\nfull_gate="${repo_root}/.github/scripts/gitapex_gate_foo.py"\nuv run --frozen python3 "${full_gate}" --flag\n',
    )
    assert gate.find_hooks_shell_indirected_invocations(hooks_dir) == []


def test_hooks_shell_indirected_variable_name_substring_does_not_cross_match(tmp_path: pathlib.Path) -> None:
    # Defeat case: "gate" is a substring of "full_gate". Both get assigned
    # a `.github/scripts/*.py` path, but only "full_gate" is invoked --
    # the word-boundary anchor in var_ref must prevent the "gate" tracked
    # variable from falsely matching inside "$full_gate".
    hooks_dir = _write_hook(
        tmp_path,
        "substring.sh",
        "#!/bin/bash\n"
        'gate="${repo_root}/.github/scripts/gate_a.py"\n'
        'full_gate="${repo_root}/.github/scripts/gate_b.py"\n'
        'python3 "$full_gate"\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(hooks_dir)
    assert len(findings) == 1
    assert "full_gate" in findings[0][2]


def test_hooks_shell_indirected_reassignment_is_whole_file_not_ordered(tmp_path: pathlib.Path) -> None:
    # Disclosed limitation (see _scan_hook's own Pass-1 comment), pinned
    # here rather than left as prose: tracking is whole-file, not
    # ordered. A variable assigned a `.github/scripts/*.py` path and then
    # reassigned to something unrelated before the bare invocation is
    # still flagged, the mirror image of
    # test_hooks_shell_indirected_bare_invocation_is_flagged's own
    # hooks/*.py-then-.github/scripts/*.py order. Both directions are
    # graded identically because no assignment-order dataflow is
    # attempted -- confirmed here as intentional behavior, not a defect,
    # per the module's own "no ... multi-hop reassignment tracing"
    # non-goal.
    hooks_dir = _write_hook(
        tmp_path,
        "reassigned.sh",
        '#!/bin/bash\nvar="${repo_root}/.github/scripts/gate.py"\nvar="hooks/unrelated.py"\npython3 "$var"\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(hooks_dir)
    assert len(findings) == 1


def test_hooks_shell_indirected_no_matching_assignment_passes(tmp_path: pathlib.Path) -> None:
    hooks_dir = _write_hook(
        tmp_path,
        "clean.sh",
        "#!/bin/bash\necho hi\n",
    )
    assert gate.find_hooks_shell_indirected_invocations(hooks_dir) == []


def test_hooks_shell_indirected_missing_dir_returns_empty(tmp_path: pathlib.Path) -> None:
    # Non-blocking WARNING tier: unlike find_bare_invocations's fail-closed
    # hard-fail behavior for a missing workflows dir, a missing hooks dir
    # simply has nothing to warn about.
    assert gate.find_hooks_shell_indirected_invocations(tmp_path / "does-not-exist") == []


# --- main() composition: the new WARNING-tier hooks/*.sh scan must never
# change find_bare_invocations's existing hard-fail exit-code behavior ---


def test_main_exit_code_becomes_one_with_a_hooks_shell_indirected_finding(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #1697: a hooks/*.sh shell-variable-indirected bare invocation
    of a `.github/scripts/*.py` target is now a HARD FAIL, not a
    report-only WARNING (formerly issue #1446 Item 2's own WARNING-tier
    addition) -- see this repository's own live incident (a bare
    `python3` invocation of exactly this shape, inside
    hooks/check-pr-skill-audit-disclosure.sh, false-denied
    create_pull_request/update_pull_request under an ambient PATH lacking
    this checkout's own uv-managed .venv)."""
    workflows_dir = _write(
        tmp_path,
        "clean.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: uv run --frozen python3 .github/scripts/x.py\n",
    )
    hooks_dir = _write_hook(
        tmp_path,
        "indirect.sh",
        '#!/bin/bash\nfull_gate="${repo_root}/.github/scripts/gitapex_gate_foo.py"\npython3 "$full_gate"\n',
    )
    monkeypatch.setattr("sys.argv", ["prog", str(workflows_dir), str(hooks_dir)])
    assert gate.main() == 1
    out = capsys.readouterr().out
    assert "full_gate" in out


def test_main_exit_code_stays_one_with_a_workflow_finding_regardless_of_hooks(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    workflows_dir = _write(
        tmp_path,
        "bare.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: python3 .github/scripts/x.py\n",
    )
    hooks_dir = _write_hook(tmp_path, "clean.sh", "#!/bin/bash\necho hi\n")
    monkeypatch.setattr("sys.argv", ["prog", str(workflows_dir), str(hooks_dir)])
    assert gate.main() == 1
    out = capsys.readouterr().out
    assert "bare.yml" in out


# --- live proof against this repository's own real workflow files: after
# issue #1035's own fix lands, this is the actual regression backstop.
# Deliberately reads the real .github/workflows/ tree, not a fixture --
# the whole point of this gate is to grade what this repository's real CI
# invokes. ---


def test_this_repositorys_own_workflows_have_no_bare_invocation() -> None:
    findings = gate.find_bare_invocations(REPO_ROOT / ".github" / "workflows")
    assert findings == [], findings


# --- _scan_hook's own WARNING-tier read-failure fallback (issue #1446) ---


def test_scan_hook_missing_file_returns_empty(tmp_path: pathlib.Path) -> None:
    """A hook path that does not exist raises FileNotFoundError (an
    OSError subclass) inside read_text() -- caught and degraded to no
    findings, matching this WARNING-tier scan's own report-only contract
    (there is no exit-code fail-closed guarantee here to protect, unlike
    find_bare_invocations's own missing-directory finding)."""
    assert gate._scan_hook(tmp_path / "does-not-exist.sh") == []


def test_scan_hook_invalid_utf8_returns_empty(tmp_path: pathlib.Path) -> None:
    """A hook file that is not valid UTF-8 raises UnicodeDecodeError inside
    read_text() -- caught alongside OSError and degraded to no findings,
    the same graceful-degradation contract
    ratified_trailer_disclosure_text() in hooks/gitapex_check_post_write_provenance.py
    uses for the same failure class (confirmed consistent during this
    issue's own step-8 adversarial review)."""
    bad = tmp_path / "bad.sh"
    bad.write_bytes(b"\xff\xfe not valid utf-8")
    assert gate._scan_hook(bad) == []


# --- Independent-review defeat cases (issue #1446, drafting-a-pr-to-merge
# Step 8 inner-layer review) ---


def test_uv_run_prefix_does_not_catastrophically_backtrack_on_a_long_flag_run() -> None:
    """CWE-1333 regression: `_UV_RUN_PREFIX`'s old `-{1,2}[\\w-]+` shape let
    the `-{1,2}` quantifier and the following `[\\w-]+` class both claim a
    `-` character, giving a run of N `--flag=value` tokens 2**N equivalent
    parses that the regex engine exhausted on a non-matching tail --
    reproduced live pre-fix at ~40s for a 25-flag line (up from ~1ms at 10
    flags). A CI job scanning this pattern against every PR's own
    workflow/hooks content (no path filter, 5-minute timeout) could be
    hung by a single crafted line. This asserts the fix (`-[\\w-]+`, no
    overlap) stays well under a generous ceiling at 5x the size that used
    to take ~40s."""
    line = "uv run" + (" --flag=xxx" * 125) + " NOMATCHTAIL"
    start = time.monotonic()
    result = gate._UV_WRAPPED_INVOCATION_RE.search(line)
    elapsed = time.monotonic() - start
    assert result is None
    assert elapsed < 2.0, f"took {elapsed:.2f}s -- catastrophic backtracking may have regressed"


def test_scan_hook_ignores_a_github_scripts_path_mentioned_only_in_a_trailing_comment(
    tmp_path: pathlib.Path,
) -> None:
    """Correctness regression: Pass 1 used to search an assignment's
    *entire* right-hand side (including any trailing `# comment`) for a
    `.github/scripts/*.py`-shaped substring, so a variable holding an
    unrelated value could still get tracked -- and later flagged -- purely
    because its assignment line's own trailing comment happened to mention
    a different gate script's path (an ordinary documentation habit).
    Found live in review: `other_var="unrelated_value"  # see also
    .github/scripts/some_other_gate.py` tracked `other_var`, and its later
    bare `python3 "$other_var"` invocation was reported as a false
    positive."""
    hooks_dir = _write_hook(
        tmp_path,
        "demo.sh",
        'other_var="unrelated_value"  # see also .github/scripts/some_other_gate.py for context\n'
        "echo noop\n"
        'python3 "$other_var"\n',
    )
    assert gate.find_hooks_shell_indirected_invocations(hooks_dir) == []


# --- load_python_dependent_hook_script_names() (issue #1697) ---


def _write_ssot(tmp_path: pathlib.Path, gates: list[dict[str, object]]) -> pathlib.Path:
    ssot_path = tmp_path / "ssot.json"
    ssot_path.write_text(json.dumps({"gates": gates}), encoding="utf-8")
    return ssot_path


def test_load_python_dependent_hook_script_names_returns_hooks_py_basenames(tmp_path: pathlib.Path) -> None:
    ssot_path = _write_ssot(
        tmp_path,
        [
            {
                "id": "skill-audit-disclosure",
                "script": [
                    "hooks/check-pr-skill-audit-disclosure.sh",
                    "hooks/gitapex_check_python_precondition.py",
                    ".github/scripts/gitapex_gate_skill_audit_disclosure.py",
                ],
                "preconditions": {"requires_python_packages": ["pydantic"]},
            }
        ],
    )
    assert gate.load_python_dependent_hook_script_names(ssot_path) == frozenset(
        {"gitapex_check_python_precondition.py"}
    )


def test_load_python_dependent_hook_script_names_ignores_gates_with_no_preconditions(tmp_path: pathlib.Path) -> None:
    ssot_path = _write_ssot(
        tmp_path,
        [
            {
                "id": "some-other-gate",
                "script": ["hooks/gitapex_check_something.py"],
            }
        ],
    )
    assert gate.load_python_dependent_hook_script_names(ssot_path) == frozenset()


def test_load_python_dependent_hook_script_names_ignores_empty_requires_python_packages(
    tmp_path: pathlib.Path,
) -> None:
    ssot_path = _write_ssot(
        tmp_path,
        [
            {
                "id": "some-other-gate",
                "script": ["hooks/gitapex_check_something.py"],
                "preconditions": {"requires_python_packages": []},
            }
        ],
    )
    assert gate.load_python_dependent_hook_script_names(ssot_path) == frozenset()


def test_load_python_dependent_hook_script_names_ignores_non_hooks_py_scripts(tmp_path: pathlib.Path) -> None:
    ssot_path = _write_ssot(
        tmp_path,
        [
            {
                "id": "skill-audit-disclosure",
                "script": [
                    "hooks/check-pr-skill-audit-disclosure.sh",
                    ".github/scripts/gitapex_gate_skill_audit_disclosure.py",
                ],
                "preconditions": {"requires_python_packages": ["pydantic"]},
            }
        ],
    )
    assert gate.load_python_dependent_hook_script_names(ssot_path) == frozenset()


def test_load_python_dependent_hook_script_names_gates_key_not_a_list_returns_none(tmp_path: pathlib.Path) -> None:
    """A malformed registry returns None (a "cannot verify" signal), never
    an empty frozenset that a caller could mistake for "nothing
    registered" -- issue #1697 adversarial-review finding: the latter
    shape let a malformed .gitapex/ssot.json silently mask a real bare
    invocation of a registered hooks/*.py target."""
    ssot_path = tmp_path / "ssot.json"
    ssot_path.write_text(json.dumps({"gates": "not-a-list"}), encoding="utf-8")
    assert gate.load_python_dependent_hook_script_names(ssot_path) is None


def test_load_python_dependent_hook_script_names_missing_file_returns_none(tmp_path: pathlib.Path) -> None:
    assert gate.load_python_dependent_hook_script_names(tmp_path / "does-not-exist.json") is None


def test_load_python_dependent_hook_script_names_invalid_json_returns_none(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not valid json{", encoding="utf-8")
    assert gate.load_python_dependent_hook_script_names(bad) is None


def test_load_python_dependent_hook_script_names_non_mapping_top_level_returns_none(tmp_path: pathlib.Path) -> None:
    weird = tmp_path / "weird.json"
    weird.write_text("[1, 2, 3]", encoding="utf-8")
    assert gate.load_python_dependent_hook_script_names(weird) is None


def test_load_python_dependent_hook_script_names_malformed_gate_entries_without_hooks_py_are_skipped(
    tmp_path: pathlib.Path,
) -> None:
    """Defeat case: a `gates` array containing shapes this loader must not
    crash on -- a non-mapping entry and a non-list `script` -- neither of
    which names a `hooks/*.py` target, so neither is "cannot verify":
    there is nothing here this scan needs to widen its scope with."""
    ssot_path = _write_ssot(
        tmp_path,
        [
            "not-a-mapping",  # type: ignore[list-item]
            {"id": "a", "script": "not-a-list", "preconditions": {"requires_python_packages": ["x"]}},
        ],
    )
    assert gate.load_python_dependent_hook_script_names(ssot_path) == frozenset()


def test_load_python_dependent_hook_script_names_hooks_py_gate_with_malformed_preconditions_returns_none(
    tmp_path: pathlib.Path,
) -> None:
    """Regression, adversarial-review finding (issue #1697): a `gates`
    entry that DOES name a `hooks/*.py` script but whose own
    `preconditions` is present and malformed (not a mapping) must fail
    closed (`None`), not silently skip -- this is the exact per-gate,
    narrower-trigger mirror of the whole-file fail-open bug this loader
    was already fixed for once. Skipping this case previously let a
    single corrupted `preconditions` field mask a real bare invocation
    of the registered hooks/*.py target while still reporting a false
    "clean" exit 0."""
    ssot_path = _write_ssot(
        tmp_path,
        [{"id": "b", "script": ["hooks/foo.py"], "preconditions": "not-a-mapping"}],
    )
    assert gate.load_python_dependent_hook_script_names(ssot_path) is None


def test_load_python_dependent_hook_script_names_hooks_py_gate_with_malformed_requires_packages_returns_none(
    tmp_path: pathlib.Path,
) -> None:
    """Same regression as above, one field narrower: `preconditions` is a
    mapping, but its own `requires_python_packages` is present and
    malformed (not a list) -- also fails closed (`None`), not skipped."""
    ssot_path = _write_ssot(
        tmp_path,
        [{"id": "c", "script": ["hooks/bar.py"], "preconditions": {"requires_python_packages": "not-a-list"}}],
    )
    assert gate.load_python_dependent_hook_script_names(ssot_path) is None


# --- HARD-FAIL promotion of hooks/*.py targets (issue #1697) ---


def test_scan_hook_directly_flags_a_registered_hooks_py_target(tmp_path: pathlib.Path) -> None:
    """Calls `_scan_hook` directly (not through
    `find_hooks_shell_indirected_invocations`'s directory-level wrapper)
    to cover its own new `hard_fail_hooks_py_names` parameter -- the same
    real defect shape as `test_hooks_shell_indirected_registered_hooks_py_target_is_flagged`
    below, exercised at the function this repository's own diff actually
    changed."""
    hook = tmp_path / "check-pr-skill-audit-disclosure.sh"
    hook.write_text(
        "#!/bin/bash\n"
        'script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'precondition_script="$script_dir/gitapex_check_python_precondition.py"\n'
        'precondition_json=$(python3 "$precondition_script" -- pydantic)\n',
        encoding="utf-8",
    )
    findings = gate._scan_hook(hook, frozenset({"gitapex_check_python_precondition.py"}))
    assert len(findings) == 1
    assert "precondition_script" in findings[0][2]


def test_scan_hook_directly_leaves_an_unregistered_hooks_py_target_unflagged(tmp_path: pathlib.Path) -> None:
    hook = tmp_path / "check-bash-safety.sh"
    hook.write_text(
        "#!/bin/bash\n"
        'classifier="${repo_root}/hooks/gitapex_check_bash_safety.py"\n'
        'classifier_output=$(printf %s "$input" | python3 "$classifier" 2>/dev/null)\n',
        encoding="utf-8",
    )
    assert gate._scan_hook(hook, frozenset({"gitapex_check_python_precondition.py"})) == []


def test_hooks_shell_indirected_registered_hooks_py_target_is_flagged(tmp_path: pathlib.Path) -> None:
    """Reproduces hooks/check-pr-skill-audit-disclosure.sh's own real
    defect (issue #1697): a bare `python3 "$precondition_script"`
    invocation of a `hooks/*.py` file registered under a gate that
    declares a non-empty `preconditions.requires_python_packages` is now
    flagged, closing the exact blind spot that let this defect ship."""
    hooks_dir = _write_hook(
        tmp_path,
        "check-pr-skill-audit-disclosure.sh",
        "#!/bin/bash\n"
        'script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'precondition_script="$script_dir/gitapex_check_python_precondition.py"\n'
        'precondition_json=$(python3 "$precondition_script" -- pydantic)\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(
        hooks_dir, frozenset({"gitapex_check_python_precondition.py"})
    )
    assert len(findings) == 1
    assert "precondition_script" in findings[0][2]


def test_hooks_shell_indirected_unregistered_hooks_py_target_is_still_not_flagged(tmp_path: pathlib.Path) -> None:
    """A hooks/*.py target NOT named in hard_fail_hooks_py_names stays
    exactly as before (bare-invoked by design, per
    docs/repository-layout.md) -- the promotion is scoped to registered,
    third-party-dependent targets only, not every hooks/*.py sibling."""
    hooks_dir = _write_hook(
        tmp_path,
        "check-bash-safety.sh",
        "#!/bin/bash\n"
        'classifier="${repo_root}/hooks/gitapex_check_bash_safety.py"\n'
        'classifier_output=$(printf %s "$input" | python3 "$classifier" 2>/dev/null)\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(
        hooks_dir, frozenset({"gitapex_check_python_precondition.py"})
    )
    assert findings == []


def test_hooks_shell_indirected_registered_hooks_py_target_uv_wrapped_is_not_flagged(tmp_path: pathlib.Path) -> None:
    hooks_dir = _write_hook(
        tmp_path,
        "fixed.sh",
        "#!/bin/bash\n"
        'precondition_script="$script_dir/gitapex_check_python_precondition.py"\n'
        'uv run --frozen python3 "$precondition_script" -- pydantic\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(
        hooks_dir, frozenset({"gitapex_check_python_precondition.py"})
    )
    assert findings == []


def test_hooks_shell_indirected_registered_hooks_py_target_via_python3_cmd_array_is_not_flagged(
    tmp_path: pathlib.Path,
) -> None:
    """The actual fix shape this repository's own hooks/*.sh files now
    use (a `python3_cmd` array resolved to either `uv run --frozen
    python3` or a bare `python3` fallback) must not itself be
    misdetected as a NEW bare invocation -- "python3" only ever appears
    here as a substring of the array variable's own name
    (`python3_cmd`), never as a standalone token immediately followed by
    the target variable."""
    hooks_dir = _write_hook(
        tmp_path,
        "fixed.sh",
        "#!/bin/bash\n"
        'precondition_script="$script_dir/gitapex_check_python_precondition.py"\n'
        "python3_cmd=(python3)\n"
        "if command -v uv >/dev/null 2>&1; then python3_cmd=(uv run --frozen python3); fi\n"
        '"${python3_cmd[@]}" "$precondition_script" -- pydantic\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(
        hooks_dir, frozenset({"gitapex_check_python_precondition.py"})
    )
    assert findings == []


def test_hooks_shell_indirected_hooks_py_name_substring_does_not_cross_match(tmp_path: pathlib.Path) -> None:
    """Defeat case: a decoy file `gitapex_check_python_precondition_extra.py`
    must not be treated as a match for the registered
    `gitapex_check_python_precondition.py` merely because one name is a
    substring of the other's own prefix -- the trailing `$` anchor in the
    generated pattern requires the registered name to end the (quote-
    trimmed) right-hand side exactly."""
    hooks_dir = _write_hook(
        tmp_path,
        "decoy.sh",
        '#!/bin/bash\ndecoy_script="$script_dir/gitapex_check_python_precondition_extra.py"\npython3 "$decoy_script"\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(
        hooks_dir, frozenset({"gitapex_check_python_precondition.py"})
    )
    assert findings == []


def test_hooks_shell_indirected_unregistered_name_ending_in_a_registered_name_is_not_flagged(
    tmp_path: pathlib.Path,
) -> None:
    """Mirror-image defeat case (adversarial-review finding, issue
    #1697): a decoy file `my_other_gitapex_check_python_precondition.py`
    must not be treated as a match merely because the registered name
    `gitapex_check_python_precondition.py` is a SUFFIX of the decoy's own
    name -- the `(?:^|/)` boundary requires the registered name to start
    right after a path separator (or the start of the value), not merely
    end the value. Without that boundary, a bare trailing `$` anchor
    alone would wrongly flag this decoy, over-blocking a target that was
    never registered."""
    hooks_dir = _write_hook(
        tmp_path,
        "decoy2.sh",
        "#!/bin/bash\n"
        'decoy_script="$script_dir/my_other_gitapex_check_python_precondition.py"\n'
        'python3 "$decoy_script"\n',
    )
    findings = gate.find_hooks_shell_indirected_invocations(
        hooks_dir, frozenset({"gitapex_check_python_precondition.py"})
    )
    assert findings == []


def test_main_flags_a_registered_hooks_py_target_and_exits_one(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    workflows_dir = _write(
        tmp_path,
        "clean.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: uv run --frozen python3 .github/scripts/x.py\n",
    )
    hooks_dir = _write_hook(
        tmp_path,
        "check-pr-skill-audit-disclosure.sh",
        "#!/bin/bash\n"
        'precondition_script="$script_dir/gitapex_check_python_precondition.py"\n'
        'python3 "$precondition_script" -- pydantic\n',
    )
    ssot_path = _write_ssot(
        tmp_path,
        [
            {
                "id": "skill-audit-disclosure",
                "script": ["hooks/gitapex_check_python_precondition.py"],
                "preconditions": {"requires_python_packages": ["pydantic"]},
            }
        ],
    )
    monkeypatch.setattr("sys.argv", ["prog", str(workflows_dir), str(hooks_dir), str(ssot_path)])
    assert gate.main() == 1
    out = capsys.readouterr().out
    assert "precondition_script" in out


def test_main_returns_zero_when_no_gate_requires_a_python_package(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hooks/*.py target invoked bare stays clean when no registered
    gate declares a `requires_python_packages` precondition for it --
    the pre-#1697 behavior for every ordinary, stdlib-only hooks/*.py
    sibling."""
    workflows_dir = _write(
        tmp_path,
        "clean.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: uv run --frozen python3 .github/scripts/x.py\n",
    )
    hooks_dir = _write_hook(
        tmp_path,
        "ordinary.sh",
        '#!/bin/bash\nclassifier="$script_dir/gitapex_check_bash_safety.py"\npython3 "$classifier"\n',
    )
    ssot_path = _write_ssot(tmp_path, [])
    monkeypatch.setattr("sys.argv", ["prog", str(workflows_dir), str(hooks_dir), str(ssot_path)])
    assert gate.main() == 0


def test_main_hard_fails_on_an_unreadable_ssot_registry_even_with_no_other_findings(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for the issue #1697 adversarial-review finding: before
    this fix, a malformed .gitapex/ssot.json made
    load_python_dependent_hook_script_names degrade to an empty
    frozenset, which find_hooks_shell_indirected_invocations then read as
    "nothing registered" -- so a real bare invocation of a registered
    hooks/*.py target went completely undetected AND main() printed a
    false "No ... bare invocations found" while exiting 0. This asserts
    main() now hard-fails on the unreadable registry itself, matching
    find_bare_invocations's own established "cannot verify" convention,
    even though the hooks/*.sh scan below it finds nothing (since it has
    no registered names to check against)."""
    workflows_dir = _write(
        tmp_path,
        "clean.yml",
        "jobs:\n  a:\n    steps:\n      - name: run\n        run: uv run --frozen python3 .github/scripts/x.py\n",
    )
    hooks_dir = _write_hook(
        tmp_path,
        "check-pr-skill-audit-disclosure.sh",
        "#!/bin/bash\n"
        'precondition_script="$script_dir/gitapex_check_python_precondition.py"\n'
        'python3 "$precondition_script" -- pydantic\n',
    )
    bad_ssot_path = tmp_path / "bad_ssot.json"
    bad_ssot_path.write_text("not valid json{", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["prog", str(workflows_dir), str(hooks_dir), str(bad_ssot_path)])
    assert gate.main() == 1
    out = capsys.readouterr().out
    assert "Could not read or parse" in out
    assert str(bad_ssot_path) in out


# --- live proof against this repository's own real ssot.json + hooks/ ---


def test_this_repositorys_own_hooks_have_no_hard_fail_indirected_invocation() -> None:
    """After issue #1697's own fix lands, this is the actual regression
    backstop: scan this repository's REAL hooks/ directory against its
    REAL ssot.json, exactly as CI/local-preflight will."""
    hard_fail_names = gate.load_python_dependent_hook_script_names(REPO_ROOT / ".gitapex" / "ssot.json")
    assert hard_fail_names is not None, "this repository's own .gitapex/ssot.json must be readable"
    findings = gate.find_hooks_shell_indirected_invocations(REPO_ROOT / "hooks", hard_fail_names)
    assert findings == [], findings
