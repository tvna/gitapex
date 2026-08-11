"""Issue #1035: every `.github/scripts/*.py` invocation from a workflow
`run:` step must go through `uv run`. See
`.github/scripts/gitapex_gate_bare_python3_invocation.py`'s own module
docstring for the incident this gate exists to prevent from recurring.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_bare_python3_invocation as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _write(tmp_path: pathlib.Path, name: str, content: str) -> pathlib.Path:
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    path = workflows_dir / name
    path.write_text(content, encoding="utf-8")
    return workflows_dir


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


# --- live proof against this repository's own real workflow files: after
# issue #1035's own fix lands, this is the actual regression backstop.
# Deliberately reads the real .github/workflows/ tree, not a fixture --
# the whole point of this gate is to grade what this repository's real CI
# invokes. ---


def test_this_repositorys_own_workflows_have_no_bare_invocation() -> None:
    findings = gate.find_bare_invocations(REPO_ROOT / ".github" / "workflows")
    assert findings == [], findings
