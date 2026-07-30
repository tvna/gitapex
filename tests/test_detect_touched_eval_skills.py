"""Tests for the touched-eval-skill detector
(.github/scripts/detect_touched_eval_skills.py).

Issue #582: `waza-eval-gate.yml` needs the sorted, deduped set of skill
names under `evals/<skill>/...` touched by a diff, excluding the shared
`evals/scripts/` infrastructure directory, with any skill-name segment
outside `^[A-Za-z0-9_-]+$` raising loud rather than being silently dropped.
"""

from __future__ import annotations

import io

import pytest

import detect_touched_eval_skills as mod


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
