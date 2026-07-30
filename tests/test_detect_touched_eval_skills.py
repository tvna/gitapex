"""Tests for the touched-eval-skill detector
(.github/scripts/detect_touched_eval_skills.py).

Issue #582: `waza-eval-gate.yml` needs the sorted, deduped set of skill
names under `evals/<skill>/...` touched by a diff, excluding the shared
`evals/scripts/` infrastructure directory, with any skill-name segment
outside `^[A-Za-z0-9_-]+$` raising loud rather than being silently dropped.
"""

from __future__ import annotations

import io
import pathlib
import subprocess

import pytest

import detect_touched_eval_skills as mod

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "waza-eval-gate.yml"


# --- touched_skills: normal cases ---


def test_no_paths_touched_returns_empty():
    assert mod.touched_skills([]) == []


def test_no_matching_paths_returns_empty():
    assert mod.touched_skills(["README.md", "skills/foo/SKILL.md"]) == []


def test_single_skill_single_file():
    assert mod.touched_skills(["evals/foo/eval.yaml"]) == ["foo"]


def test_single_skill_multiple_files_dedup_to_one_name():
    assert mod.touched_skills(
        [
            "evals/foo/eval.yaml",
            "evals/foo/tasks/one.yaml",
            "evals/foo/tasks/two.yaml",
        ]
    ) == ["foo"]


def test_multiple_distinct_skills_both_present_sorted():
    assert mod.touched_skills(
        ["evals/zeta/eval.yaml", "evals/alpha/tasks/x.yaml"]
    ) == ["alpha", "zeta"]


# --- exclusions ---


def test_evals_scripts_file_excluded_not_reported_as_skill_scripts():
    assert mod.touched_skills(["evals/scripts/set_config_model.py"]) == []


def test_evals_scripts_excluded_alongside_a_real_skill():
    assert mod.touched_skills(
        ["evals/scripts/set_config_model.py", "evals/foo/eval.yaml"]
    ) == ["foo"]


def test_bare_evals_top_level_file_excluded():
    # "evals/README.md" has no skill directory beneath it -- it is a
    # top-level file directly under evals/, not a file inside some
    # evals/<skill>/ directory.
    assert mod.touched_skills(["evals/README.md"]) == []


def test_bare_evals_skill_directory_with_no_further_segment_excluded():
    # A path with exactly "evals/<skill>" and nothing after it (no
    # trailing file/segment) must not count as touching that skill.
    assert mod.touched_skills(["evals/foo"]) == []


def test_unrelated_top_level_directory_excluded():
    assert mod.touched_skills(["skills/foo/scripts/thing.py"]) == []


# --- adversarial defeat cases (required) ---


def test_nested_path_under_evals_scripts_still_excluded_despite_looking_skill_shaped():
    # The top-level segment right after "evals/" is "scripts", regardless
    # of what looks skill-shaped further down the path -- this must NOT
    # be reported as touching a skill named "looks-like-a-skill" (or
    # "subdir", or anything else).
    result = mod.touched_skills(
        ["evals/scripts/subdir/looks-like-a-skill/eval.yaml"]
    )
    assert result == []
    assert "looks-like-a-skill" not in result
    assert "scripts" not in result


def test_path_traversal_skill_segment_raises_value_error():
    with pytest.raises(ValueError, match=r"evals/\.\./etc/passwd"):
        mod.touched_skills(["evals/../etc/passwd"])


def test_skill_segment_with_space_raises_value_error():
    with pytest.raises(ValueError, match=r"foo bar"):
        mod.touched_skills(["evals/foo bar/tasks/x.yaml"])


def test_invalid_skill_segment_does_not_silently_pass_through_or_get_dropped():
    # Regression guard for the specific failure mode this gate must avoid:
    # an invalid name must raise, not simply be excluded from the result
    # the way "scripts" or a too-short path is.
    with pytest.raises(ValueError):
        mod.touched_skills(["evals/foo/eval.yaml", "evals/bad name/x.yaml"])


def test_valid_and_invalid_paths_mixed_still_raises():
    with pytest.raises(ValueError):
        mod.touched_skills(
            ["evals/good-skill/eval.yaml", "evals/also.bad/tasks/x.yaml"]
        )


def test_leading_dot_slash_does_not_silently_drop_a_touched_skill():
    # Regression: an un-stripped leading "./" makes segments[0] == "." (not
    # "evals"), which the old code silently dropped -- no error, no skill,
    # nothing to indicate a real touched path was ignored. "./" is a common
    # shape from tools like `find .`, which this script's own documented
    # CLI/stdin usage accepts as caller-supplied input.
    assert mod.touched_skills(["./evals/foo/eval.yaml"]) == ["foo"]


def test_repeated_leading_dot_slash_still_detected():
    assert mod.touched_skills(["././evals/foo/eval.yaml"]) == ["foo"]


def test_leading_dot_slash_does_not_weaken_path_traversal_rejection():
    # The "./" strip must be narrowly scoped to a literal leading "."
    # segment only -- it must never generalize into collapsing ".." (e.g.
    # via posixpath.normpath), which would silently resolve
    # "evals/../etc/passwd" down to "etc/passwd" and defeat the
    # traversal check instead of preserving it.
    with pytest.raises(ValueError, match=r"evals/\.\./etc/passwd"):
        mod.touched_skills(["./evals/../etc/passwd"])


def test_skill_segment_with_trailing_newline_raises_not_silently_accepted():
    # Regression: Python's "$" anchor (without re.MULTILINE) matches just
    # before a trailing newline as well as at the true end of string, so a
    # naive re.match(r"^[A-Za-z0-9_-]+$", ...) check would incorrectly
    # accept a skill-name segment ending in "\n" -- letting an embedded
    # newline through into the comma-joined $GITHUB_OUTPUT sink. This must
    # still raise, exactly like any other out-of-class character.
    with pytest.raises(ValueError, match=r"foo\\n"):
        mod.touched_skills(["evals/foo\n/tasks/x.yaml"])


# --- parse_paths ---


def test_parse_paths_reads_one_per_line_ignoring_blank_lines():
    assert mod.parse_paths("evals/foo/eval.yaml\n\nevals/bar/eval.yaml\n") == [
        "evals/foo/eval.yaml",
        "evals/bar/eval.yaml",
    ]


def test_parse_paths_empty_text_returns_empty_list():
    assert mod.parse_paths("") == []


# --- main() ---


def test_main_prints_empty_line_for_no_touched_skills(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert mod.main([]) == 0
    assert capsys.readouterr().out == "\n"


def test_main_prints_sorted_comma_joined_skills_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO("evals/zeta/eval.yaml\nevals/alpha/tasks/x.yaml\n")
    )
    assert mod.main([]) == 0
    assert capsys.readouterr().out.strip() == "alpha,zeta"


def test_main_reads_positional_args_instead_of_stdin(monkeypatch, capsys):
    # sys.stdin is deliberately left unset/unreadable-shaped here: passing
    # positional args must not touch stdin at all.
    monkeypatch.setattr("sys.stdin", io.StringIO("evals/should-not-be-read/eval.yaml"))
    assert mod.main(["evals/foo/eval.yaml", "evals/foo/tasks/x.yaml"]) == 0
    assert capsys.readouterr().out.strip() == "foo"


def test_main_exits_1_and_prints_error_on_invalid_skill_name(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("evals/foo bar/tasks/x.yaml\n"))
    assert mod.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err
    assert "foo bar" in captured.err


# --- regression: git's default path quoting must not silently defeat the
# gate (mandatory adversarial defeat-case for this deterministic script) ---
#
# `git diff --name-only` (no `-z`) wraps an entire path in double quotes
# with octal-escaped bytes the moment it contains a non-ASCII byte or a
# `"`/`\`/control character (core.quotepath, on by default). The quoted
# line's leading `"` then makes `touched_skills()`'s own
# `segments[0] != "evals"` check fail, silently dropping a real touched
# skill -- the exact "gate silently skips a suite it should have run"
# false-negative this gate exists to prevent. The fix lives in
# waza-eval-gate.yml's "Determine touched skills" step (`-z` disables the
# quoting; `tr '\0' '\n'` must convert to newlines *inside* the pipe,
# before bash's `$(...)` capture, since bash silently drops embedded NUL
# bytes on capture and would otherwise glue two touched paths together).


def test_workflow_uses_name_only_z_and_converts_nul_before_capture():
    # Structural regression guard: if a future edit reverts the workflow's
    # git-diff invocation back to plain `--name-only` (dropping `-z`), this
    # must fail loudly here rather than silently reintroducing the
    # quoting-defeats-detection false negative with nothing left to catch
    # it, per this repo's own "a fixed defeat-case must be committed as a
    # permanent regression test" convention.
    text = WORKFLOW_PATH.read_text()
    assert "git diff --name-only -z " in text, (
        "waza-eval-gate.yml's pull_request diff step must use "
        "`git diff --name-only -z` (NUL-delimited) -- plain --name-only "
        "quotes non-ASCII/special-character paths and silently drops them "
        "from touched-skill detection"
    )
    assert "| tr '\\0' '\\n'" in text, (
        "the -z output must be converted to newline-delimited via "
        "`tr '\\0' '\\n'` inside the same pipe, before capture into a bash "
        "variable (bash silently drops embedded NUL bytes on capture, "
        "which would otherwise glue multiple touched paths together)"
    )


def test_touched_skills_handles_a_non_ascii_path_directly():
    # touched_skills() itself already handles an *unquoted* non-ASCII path
    # correctly -- the defeat case lives entirely in git's own quoting of
    # the raw `--name-only` (no `-z`) output, not in this function. This
    # pins that contract so the two tests together fully cover the gap:
    # this one covers the function, the ones below cover the real `git
    # diff` invocation end to end.
    assert mod.touched_skills(["evals/foo/tasks/日本語.yaml"]) == ["foo"]
    assert mod.touched_skills(['evals/bar/tasks/weird"quote.yaml']) == ["bar"]


@pytest.fixture
def eval_gate_git_repo(tmp_path):
    # Matches tests/test_skill_description_diff.py's `git_repo` fixture
    # convention (per-repo `git config`, not global/env).
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

    (repo / "evals" / "foo" / "tasks").mkdir(parents=True)
    (repo / "evals" / "foo" / "tasks" / "plain.yaml").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    (repo / "evals" / "foo" / "tasks" / "日本語.yaml").write_bytes(b"y\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add unicode file"], cwd=repo, check=True)
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    return repo, base_sha, head_sha


def test_naive_git_diff_name_only_would_have_silently_dropped_the_skill(
    eval_gate_git_repo,
):
    # End-to-end proof of the bug this gate must never reintroduce: a real
    # git repo, a real touched file with a non-ASCII name inside
    # evals/<skill>/, and the *old, unfixed* invocation (plain
    # `--name-only`, no `-z`) -- demonstrating the false negative is real,
    # not theoretical, against actual git behavior (not a proxy).
    repo, base_sha, head_sha = eval_gate_git_repo
    naive = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    naive_skills = mod.touched_skills(mod.parse_paths(naive.stdout))
    assert naive_skills == [], (
        "expected the naive (unfixed) invocation to demonstrate the "
        "false-negative bug; if this now finds 'foo', git's own quoting "
        "behavior changed and this regression test needs re-examining, "
        "not the fix"
    )


def test_fixed_git_diff_name_only_z_detects_the_non_ascii_skill(eval_gate_git_repo):
    # Same repo/history as above, but through the fixed invocation
    # (`-z` + `tr '\0' '\n'` before capture, matching waza-eval-gate.yml's
    # "Determine touched skills" step) -- must correctly detect "foo".
    repo, base_sha, head_sha = eval_gate_git_repo
    result = subprocess.run(
        f'git diff --name-only -z "{base_sha}...{head_sha}" | tr \'\\0\' \'\\n\'',
        shell=True,
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "\x00" not in result.stdout
    fixed_skills = mod.touched_skills(mod.parse_paths(result.stdout))
    assert fixed_skills == ["foo"]
