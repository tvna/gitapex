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
import types

import detect_touched_eval_skills as mod
import pytest

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
    assert mod.touched_skills(["evals/zeta/eval.yaml", "evals/alpha/tasks/x.yaml"]) == ["alpha", "zeta"]


# --- exclusions ---


def test_evals_scripts_file_excluded_not_reported_as_skill_scripts():
    assert mod.touched_skills(["evals/scripts/set_config_model.py"]) == []


def test_evals_scripts_excluded_alongside_a_real_skill():
    assert mod.touched_skills(["evals/scripts/set_config_model.py", "evals/foo/eval.yaml"]) == ["foo"]


def test_bare_evals_top_level_file_excluded():
    # "evals/README.md" has no skill directory beneath it -- it is a
    # top-level file directly under evals/, not a file inside some
    # evals/<skill>/ directory.
    assert mod.touched_skills(["evals/README.md"]) == []


def test_bare_evals_skill_directory_with_no_further_segment_excluded():
    # A path with exactly "evals/<skill>" and nothing after it (no
    # trailing file/segment) must not count as touching that skill.
    assert mod.touched_skills(["evals/foo"]) == []


def test_bare_evals_skill_directory_with_trailing_slash_excluded():
    # Regression: "evals/foo/".split("/") == ["evals", "foo", ""] -- the
    # trailing empty segment produced by the literal trailing slash
    # satisfies "len(segments) >= 3" by accident, incorrectly counting a
    # bare directory path (no file inside it) as touching "foo".
    assert mod.touched_skills(["evals/foo/"]) == []


def test_empty_segment_in_the_middle_of_the_path_still_raises():
    # The trailing-slash fix above must be narrowly scoped to a single
    # trailing empty segment only -- an empty segment anywhere else in the
    # path (e.g. a literal double slash) must still fail the skill-name
    # regex check exactly as before.
    with pytest.raises(ValueError):
        mod.touched_skills(["evals//foo/x.yaml"])


def test_unrelated_top_level_directory_excluded():
    assert mod.touched_skills(["skills/foo/scripts/thing.py"]) == []


# --- adversarial defeat cases (required) ---


def test_nested_path_under_evals_scripts_still_excluded_despite_looking_skill_shaped():
    # The top-level segment right after "evals/" is "scripts", regardless
    # of what looks skill-shaped further down the path -- this must NOT
    # be reported as touching a skill named "looks-like-a-skill" (or
    # "subdir", or anything else).
    result = mod.touched_skills(["evals/scripts/subdir/looks-like-a-skill/eval.yaml"])
    assert result == []
    assert "looks-like-a-skill" not in result
    assert "scripts" not in result


def test_path_traversal_skill_segment_raises_value_error():
    with pytest.raises(ValueError, match=r"evals/\.\./etc/passwd"):
        mod.touched_skills(["evals/../etc/passwd"])


def test_leading_dot_dot_segment_raises_not_silently_dropped():
    # Regression: the docstring claims a ".." segment (leading or
    # otherwise) always raises -- but a *leading* ".." (not preceded by
    # "./") made segments[0] == ".." (not "evals"), which the old code
    # silently skipped via the "must start with evals" check before ever
    # reaching the skill-name regex validation that would otherwise have
    # caught it. touched_skills(["../evals/foo/eval.yaml"]) must raise,
    # not silently return [].
    with pytest.raises(ValueError, match=r"\.\./evals/foo/eval\.yaml"):
        mod.touched_skills(["../evals/foo/eval.yaml"])


def test_dot_dot_segment_outside_skill_name_position_raises():
    # A ".." segment elsewhere in the path (not the leading segment, not
    # the skill-name segment) must also raise -- not just when it happens
    # to land where the skill-name regex would incidentally catch it.
    with pytest.raises(ValueError, match=r"evals/foo/\.\./secret\.yaml"):
        mod.touched_skills(["evals/foo/../secret.yaml"])


def test_skill_segment_with_space_raises_value_error():
    with pytest.raises(ValueError, match=r"foo bar"):
        mod.touched_skills(["evals/foo bar/tasks/x.yaml"])


def test_invalid_skill_segment_does_not_silently_pass_through_or_get_dropped():
    # Regression guard for the specific failure mode this gate must avoid:
    # an invalid name must raise, not simply be excluded from the result
    # the way "scripts" or a too-short path is. Covers both a space-
    # containing and a dot-containing invalid segment mixed in with a
    # valid path, so one valid + one invalid path together still raises.
    with pytest.raises(ValueError):
        mod.touched_skills(["evals/foo/eval.yaml", "evals/bad name/x.yaml"])
    with pytest.raises(ValueError):
        mod.touched_skills(["evals/good-skill/eval.yaml", "evals/also.bad/tasks/x.yaml"])


@pytest.mark.parametrize("prefix", ["./", "././"])
def test_leading_dot_slash_does_not_silently_drop_a_touched_skill(prefix):
    # Regression: an un-stripped leading "./" makes segments[0] == "." (not
    # "evals"), which the old code silently dropped -- no error, no skill,
    # nothing to indicate a real touched path was ignored. "./" is a common
    # shape from tools like `find .`, which this script's own documented
    # CLI/stdin usage accepts as caller-supplied input. Repeated ("././")
    # must be handled the same way as a single "./".
    assert mod.touched_skills([f"{prefix}evals/foo/eval.yaml"]) == ["foo"]


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


def test_parse_paths_splits_only_on_literal_newline_not_other_line_breaks():
    # Regression: str.splitlines() additionally splits on \r, \v, \f,
    # \x1c-\x1e, \x85, U+2028, U+2029 -- a real path containing one of
    # those raw bytes must survive as a single path, split only at literal
    # "\n" boundaries.
    text = "evals/foo\r/eval.yaml\nevals/bar\x0b/eval.yaml\n"
    assert mod.parse_paths(text) == [
        "evals/foo\r/eval.yaml",
        "evals/bar\x0b/eval.yaml",
    ]


# --- parse_paths_nul (--nul/-0 mode) ---


def test_parse_paths_nul_splits_on_nul_and_drops_trailing_empty():
    data = b"evals/foo/eval.yaml\0evals/bar/eval.yaml\0"
    assert mod.parse_paths_nul(data) == [
        "evals/foo/eval.yaml",
        "evals/bar/eval.yaml",
    ]


def test_parse_paths_nul_empty_input_returns_empty_list():
    assert mod.parse_paths_nul(b"") == []
    # A single lone NUL (e.g. `printf '%s\0'` called with zero arguments,
    # as waza-eval-gate.yml's own step does when nothing was touched) must
    # also yield no paths, not a spurious empty-string path.
    assert mod.parse_paths_nul(b"\0") == []


def test_nul_mode_detects_a_path_containing_a_literal_embedded_newline_byte():
    # The whole point of --nul: a path with a raw newline byte inside it
    # (legal in a POSIX filename, here in the filename segment rather than
    # the skill-name segment -- an embedded newline *in* the skill-name
    # segment is a separate, correctly-rejected case, see
    # test_skill_segment_with_trailing_newline_raises_not_silently_accepted)
    # must not be split into two paths just because NUL-delimited data
    # happens to also contain that byte.
    data = b"evals/foo/\nweirdname.yaml\0evals/bar/eval.yaml\0"
    paths = mod.parse_paths_nul(data)
    assert paths == ["evals/foo/\nweirdname.yaml", "evals/bar/eval.yaml"]
    assert mod.touched_skills(paths) == ["bar", "foo"]


def test_tr_based_pipeline_would_have_split_a_literal_newline_byte_in_a_path():
    # Direct proof the old `tr '\0' '\n'` conversion is unsafe, reproduced
    # exactly as described: piping the same NUL-separated two-path data
    # (first path containing an embedded "\n" byte right after the
    # skill's own trailing "/", so the split truncates it down to a bare
    # "evals/foo/" directory path) through `tr '\0' '\n'` then through the
    # *existing* parse_paths() (newline mode) produces wrong, split
    # results that silently miss the "foo" skill entirely -- not
    # theoretical.
    data = b"evals/foo/\nweirdname.yaml\0evals/bar/eval.yaml\0"
    # A literal NUL cannot be passed as a subprocess argv element at all
    # (Python raises "embedded null byte"), but it does not need to be:
    # `tr` interprets the two-character escapes \0 and \n itself, so the
    # shell that used to be here was doing nothing but quoting. Byte-for-
    # byte identical output, one fewer shell=True.
    converted = subprocess.run(["tr", "\\0", "\\n"], input=data, check=True, capture_output=True).stdout.decode()
    broken = mod.parse_paths(converted)
    assert broken != ["evals/foo/\nweirdname.yaml", "evals/bar/eval.yaml"]
    assert mod.touched_skills(broken) == ["bar"], (
        "expected the old tr-based split to silently drop 'foo' from the "
        "result (the bare 'evals/foo/' fragment left behind by the split "
        "no longer has a further segment); if this now finds 'foo' too, "
        "the defeat case needs re-examining, not the fix"
    )


# --- main() ---


def test_main_prints_empty_line_for_no_touched_skills(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert mod.main([]) == 0
    assert capsys.readouterr().out == "\n"


def test_main_prints_sorted_comma_joined_skills_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("evals/zeta/eval.yaml\nevals/alpha/tasks/x.yaml\n"))
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


def _fake_stdin_with_nul_buffer(data: bytes) -> types.SimpleNamespace:
    # pytest replaces sys.stdin with its own capture object whose `.buffer`
    # is a read-only property, so `monkeypatch.setattr(sys.stdin, "buffer",
    # ...)` fails with "no setter" -- replace `sys.stdin` wholesale instead
    # with a minimal stand-in exposing just the `.buffer.read()` surface
    # `main()`'s --nul mode actually uses.
    return types.SimpleNamespace(buffer=io.BytesIO(data))


def test_main_nul_flag_reads_nul_delimited_stdin(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin",
        _fake_stdin_with_nul_buffer(b"evals/zeta/eval.yaml\0evals/alpha/tasks/x.yaml\0"),
    )
    assert mod.main(["--nul"]) == 0
    assert capsys.readouterr().out.strip() == "alpha,zeta"


def test_main_nul_flag_detects_embedded_newline_byte_where_default_mode_could_not(monkeypatch, capsys):
    # The embedded newline sits in the filename segment (not the
    # skill-name segment) -- an embedded newline in the skill-name segment
    # itself is correctly rejected by the existing ^[A-Za-z0-9_-]+$ check
    # (see test_skill_segment_with_trailing_newline_raises_not_silently_accepted),
    # not silently accepted either way.
    monkeypatch.setattr(
        "sys.stdin",
        _fake_stdin_with_nul_buffer(b"evals/foo/\nweirdname.yaml\0"),
    )
    assert mod.main(["-0"]) == 0
    assert capsys.readouterr().out.strip() == "foo"


def test_main_positional_args_ignore_nul_flag_and_stdin(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin",
        _fake_stdin_with_nul_buffer(b"evals/should-not-be-read/eval.yaml\0"),
    )
    assert mod.main(["--nul", "evals/foo/eval.yaml"]) == 0
    assert capsys.readouterr().out.strip() == "foo"


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
# quoting).


def test_workflow_uses_name_status_z_and_never_converts_nul_via_tr():
    # Structural regression guard, updated for the --name-status/--nul
    # pipeline: if a future edit reverts the workflow's git-diff invocation
    # back to plain `--name-only` (dropping `-z`), or reintroduces
    # `tr '\0' '\n'` (which cannot tell its own inserted separator apart
    # from a literal newline byte inside a real path -- see the
    # parse_paths_nul/tr comparison tests above), this must fail loudly
    # here rather than silently reintroducing either false-negative with
    # nothing left to catch it, per this repo's own "a fixed defeat-case
    # must be committed as a permanent regression test" convention.
    text = WORKFLOW_PATH.read_text()
    assert "git diff --name-status -z " in text, (
        "waza-eval-gate.yml's pull_request diff step must use "
        "`git diff --name-status -z` (NUL-delimited) -- plain --name-only "
        "quotes non-ASCII/special-character paths and silently drops them "
        "from touched-skill detection, and --name-status is what lets "
        "deleted/pure-rename paths be excluded"
    )
    assert "| tr '\\0' '\\n'" not in text, (
        "the -z output must stay NUL-delimited all the way into "
        "detect_touched_eval_skills.py's --nul mode, never actually piped "
        "through `tr '\\0' '\\n'` in bash first (mentioning it in an "
        "explanatory comment is fine; piping through it is not) -- `tr` "
        "cannot distinguish its own inserted separator from a literal "
        "newline byte inside a real path, silently mis-splitting it"
    )
    assert "--nul" in text, (
        "the workflow must feed the filtered path list into detect_touched_eval_skills.py's --nul mode"
    )
    assert "R100" in text and "D|R100" in text, (
        "the workflow's status-record filter must exclude D (deleted) and "
        "R100 (pure rename) records, mirroring skill-audit-gate.yml's own "
        "established convention"
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
    # Same repo/history as above, through `-z` + `tr '\0' '\n'`: pins that
    # `-z` alone (independent of the tr-vs-embedded-newline defeat case
    # covered separately below) correctly handles a non-ASCII filename --
    # the quoting defeat case and the embedded-newline defeat case are two
    # distinct bugs with two distinct fixes. waza-eval-gate.yml's actual
    # "Determine touched skills" step no longer uses `tr` at all (see the
    # embedded-newline-skill-name tests below for its real invocation).
    repo, base_sha, head_sha = eval_gate_git_repo
    # S602 waived: the shell pipeline IS the artefact under test. These two
    # tests reproduce the exact `git diff -z ... | tr` invocation the gate
    # used to run, to prove the false-negative it caused; rewriting them
    # without a shell would delete the thing being demonstrated. The only
    # interpolated values are SHAs the test's own fixture repo just made.
    result = subprocess.run(  # noqa: S602
        f"git diff --name-only -z \"{base_sha}...{head_sha}\" | tr '\\0' '\\n'",
        shell=True,
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "\x00" not in result.stdout
    fixed_skills = mod.touched_skills(mod.parse_paths(result.stdout))
    assert fixed_skills == ["foo"]


# --- regression: `tr '\0' '\n'` cannot distinguish its own inserted
# separator from a literal newline byte already inside a path (mandatory
# adversarial defeat-case for the --nul fix) ---


@pytest.fixture
def eval_gate_git_repo_with_embedded_newline_filename(tmp_path):
    # A filename containing a literal, unescaped newline byte, right after
    # the skill directory's own trailing "/" -- legal on a POSIX
    # filesystem, and not escaped by `git diff -z` (only bytes that
    # trigger core.quotepath -- a leading `"`, `\`, or non-ASCII byte --
    # get C-quoted without `-z`; a raw `\n` inside a path is passed
    # through unescaped by git either way, `-z` or not). The skill-name
    # segment itself ("foo") stays a valid, untouched name -- an embedded
    # newline *in* the skill-name segment is a separate, correctly-
    # rejected case (see
    # test_skill_segment_with_trailing_newline_raises_not_silently_accepted),
    # not this false-negative one.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

    (repo / "evals" / "placeholder").mkdir(parents=True)
    (repo / "evals" / "placeholder" / "eval.yaml").write_text("x\n")
    (repo / "evals" / "bar").mkdir(parents=True)
    (repo / "evals" / "bar" / "eval.yaml").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    foo_dir = repo / "evals" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "\nweirdname.yaml").write_bytes(b"y\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "add embedded-newline filename"],
        cwd=repo,
        check=True,
    )
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    return repo, base_sha, head_sha


def test_old_tr_pipeline_misses_a_skill_whose_touched_file_has_an_embedded_newline(
    eval_gate_git_repo_with_embedded_newline_filename,
):
    # End-to-end proof, against a real git repo (not a synthetic byte
    # string), that the old `tr '\0' '\n'` conversion reintroduces exactly
    # the false-negative class the `-z` fix was meant to eliminate: a real
    # touched skill ("foo") silently vanishes because its touched file's
    # embedded newline byte becomes indistinguishable from the
    # NUL-turned-newline record separator, truncating the path down to a
    # bare "evals/foo/" directory fragment with no further segment.
    repo, base_sha, head_sha = eval_gate_git_repo_with_embedded_newline_filename
    # S602 waived: the shell pipeline IS the artefact under test. These two
    # tests reproduce the exact `git diff -z ... | tr` invocation the gate
    # used to run, to prove the false-negative it caused; rewriting them
    # without a shell would delete the thing being demonstrated. The only
    # interpolated values are SHAs the test's own fixture repo just made.
    old = subprocess.run(  # noqa: S602
        f"git diff --name-only -z \"{base_sha}...{head_sha}\" | tr '\\0' '\\n'",
        shell=True,
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert mod.touched_skills(mod.parse_paths(old.stdout)) == [], (
        "expected the old tr-based pipeline to demonstrate the "
        "false-negative bug (a skill whose touched file contains a "
        "literal newline byte silently vanishes); if this now finds "
        "'foo', the defeat case needs re-examining, not the fix"
    )


def test_nul_mode_pipeline_detects_the_embedded_newline_filename_end_to_end(
    eval_gate_git_repo_with_embedded_newline_filename,
):
    # Same repo/history, but through the fixed `--name-status -z` + `--nul`
    # pipeline, mirroring waza-eval-gate.yml's actual "Determine touched
    # skills" step: a single "A" (added) record, so the path is simply the
    # second NUL-delimited field once the status field is dropped.
    repo, base_sha, head_sha = eval_gate_git_repo_with_embedded_newline_filename
    raw = subprocess.run(
        ["git", "diff", "--name-status", "-z", f"{base_sha}...{head_sha}"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields = fields[:-1]
    assert fields == [b"A", b"evals/foo/\nweirdname.yaml"]
    path_bytes = b"\0".join(fields[1:]) + b"\0"
    fixed_skills = mod.touched_skills(mod.parse_paths_nul(path_bytes))
    assert fixed_skills == ["foo"]
