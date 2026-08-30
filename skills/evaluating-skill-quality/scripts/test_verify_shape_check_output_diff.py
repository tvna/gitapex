"""Tests for verify_shape_check_output_diff.py (issue #1330's own
differential-output verification tool)."""

from __future__ import annotations

import subprocess
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest
import verify_shape_check_output_diff as vsc


@dataclass(frozen=True)
class _FakeResult:
    name: str
    passed: bool
    rule: str
    evidence: str


def test_load_module_from_source_imports_and_registers(tmp_path: Path) -> None:
    source = tmp_path / "fake_module.py"
    source.write_text("VALUE = 42\n", encoding="utf-8")

    module = vsc._load_module_from_source("fake_module_under_test", source)

    assert module.VALUE == 42
    assert sys.modules["fake_module_under_test"] is module


def test_load_module_from_source_raises_on_unloadable_path(tmp_path: Path) -> None:
    # spec_from_file_location happily builds a spec for a path that does not
    # exist -- the loader only discovers the file is missing once
    # exec_module actually tries to read it, so the real failure mode here
    # is FileNotFoundError, not the earlier `spec is None` ImportError guard.
    missing = tmp_path / "does-not-exist" / "module.py"

    with pytest.raises(FileNotFoundError):
        vsc._load_module_from_source("unloadable_module", missing)


def test_result_tuples_extracts_the_four_comparable_fields() -> None:
    results = [
        _FakeResult(name="a", passed=True, rule="rule-a", evidence="evidence-a"),
        _FakeResult(name="b", passed=False, rule="rule-b", evidence="evidence-b"),
    ]

    assert vsc._result_tuples(results) == [
        ("a", True, "rule-a", "evidence-a"),
        ("b", False, "rule-b", "evidence-b"),
    ]


def test_result_tuples_on_empty_input() -> None:
    assert vsc._result_tuples([]) == []


def test_load_old_module_writes_git_show_output_to_a_temp_file_and_imports_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_argv: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_argv.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="OLD_MARKER = 'old'\n", stderr="")

    monkeypatch.setattr(vsc.subprocess, "run", fake_run)

    module = vsc._load_old_module(tmp_path)

    assert module.OLD_MARKER == "old"
    assert captured_argv == [["git", "show", f"{vsc.BASE_SHA}:{vsc.OLD_RELATIVE_PATH}"]]
    assert (tmp_path / "gitapex_check_skill_shape_old.py").read_text(encoding="utf-8") == "OLD_MARKER = 'old'\n"


def test_load_old_module_propagates_a_git_show_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=128, cmd=argv)

    monkeypatch.setattr(vsc.subprocess, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError):
        vsc._load_old_module(tmp_path)


def test_load_new_module_loads_the_real_on_disk_hub_file() -> None:
    module = vsc._load_new_module()

    assert callable(module.check_shape)
    assert str(vsc.NEW_SCRIPTS_DIR) in sys.path


def test_main_fails_loudly_when_no_skill_md_files_are_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(vsc, "REPO_ROOT", tmp_path)

    exit_code = vsc.main()

    assert exit_code == 1
    assert "found zero skills/*/SKILL.md" in capsys.readouterr().out


def _stub_module(check_shape_fn: object) -> types.SimpleNamespace:
    return types.SimpleNamespace(check_shape=check_shape_fn)


def test_main_passes_when_old_and_new_agree_on_every_skill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "skills" / "skill-one").mkdir(parents=True)
    (tmp_path / "skills" / "skill-one" / "SKILL.md").write_text("---\nname: skill-one\n---\n", encoding="utf-8")
    monkeypatch.setattr(vsc, "REPO_ROOT", tmp_path)

    same_result = [_FakeResult(name="check-a", passed=True, rule="r", evidence="e")]
    monkeypatch.setattr(vsc, "_load_old_module", lambda _tmp: _stub_module(lambda _md: same_result))
    monkeypatch.setattr(vsc, "_load_new_module", lambda: _stub_module(lambda _md: same_result))

    exit_code = vsc.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "PASS: all 1 skills produced identical OLD/NEW check_shape() output." in out


def test_main_fails_and_reports_a_diff_when_old_and_new_disagree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "skills" / "skill-two").mkdir(parents=True)
    (tmp_path / "skills" / "skill-two" / "SKILL.md").write_text("---\nname: skill-two\n---\n", encoding="utf-8")
    monkeypatch.setattr(vsc, "REPO_ROOT", tmp_path)

    old_result = [_FakeResult(name="check-a", passed=True, rule="r", evidence="old-evidence")]
    new_result = [_FakeResult(name="check-a", passed=True, rule="r", evidence="new-evidence")]
    monkeypatch.setattr(vsc, "_load_old_module", lambda _tmp: _stub_module(lambda _md: old_result))
    monkeypatch.setattr(vsc, "_load_new_module", lambda: _stub_module(lambda _md: new_result))

    exit_code = vsc.main()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL: 1 skill(s) differ" in out
    assert "skill-two: OLD and NEW check_shape() output differs." in out
    assert "OLD only:" in out
    assert "NEW only:" in out


def test_main_reports_a_diff_when_result_counts_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "skills" / "skill-three").mkdir(parents=True)
    (tmp_path / "skills" / "skill-three" / "SKILL.md").write_text("---\nname: skill-three\n---\n", encoding="utf-8")
    monkeypatch.setattr(vsc, "REPO_ROOT", tmp_path)

    old_result = [_FakeResult(name="check-a", passed=True, rule="r", evidence="e")]
    new_result = [
        _FakeResult(name="check-a", passed=True, rule="r", evidence="e"),
        _FakeResult(name="check-b", passed=False, rule="r2", evidence="e2"),
    ]
    monkeypatch.setattr(vsc, "_load_old_module", lambda _tmp: _stub_module(lambda _md: old_result))
    monkeypatch.setattr(vsc, "_load_new_module", lambda: _stub_module(lambda _md: new_result))

    exit_code = vsc.main()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "result count: OLD=1 NEW=2" in out


def test_main_reports_the_old_check_shape_raising_as_a_failure_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "skills" / "skill-four").mkdir(parents=True)
    (tmp_path / "skills" / "skill-four" / "SKILL.md").write_text("---\nname: skill-four\n---\n", encoding="utf-8")
    monkeypatch.setattr(vsc, "REPO_ROOT", tmp_path)

    def raising_check_shape(_md: Path) -> list[_FakeResult]:
        raise ValueError("boom")

    monkeypatch.setattr(vsc, "_load_old_module", lambda _tmp: _stub_module(raising_check_shape))
    monkeypatch.setattr(vsc, "_load_new_module", lambda: _stub_module(lambda _md: []))

    exit_code = vsc.main()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "skill-four: OLD check_shape() raised" in out


def test_main_reports_the_new_check_shape_raising_as_a_failure_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "skills" / "skill-five").mkdir(parents=True)
    (tmp_path / "skills" / "skill-five" / "SKILL.md").write_text("---\nname: skill-five\n---\n", encoding="utf-8")
    monkeypatch.setattr(vsc, "REPO_ROOT", tmp_path)

    def raising_check_shape(_md: Path) -> list[_FakeResult]:
        raise ValueError("boom")

    monkeypatch.setattr(vsc, "_load_old_module", lambda _tmp: _stub_module(lambda _md: []))
    monkeypatch.setattr(vsc, "_load_new_module", lambda: _stub_module(raising_check_shape))

    exit_code = vsc.main()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "skill-five: NEW check_shape() raised" in out


@pytest.mark.slow
def test_main_end_to_end_against_the_real_repository() -> None:
    """One real, unmocked run against this branch's actual BASE commit and
    the actual working tree, matching how a contributor invokes this script
    directly (`python3 verify_shape_check_output_diff.py`) -- the mocked
    tests above cover each unit's own edge cases; this one proves the whole
    pipeline still wires together against real git history and a real
    shape_checks/ package, not just against fakes."""
    exit_code = vsc.main()

    assert exit_code == 0


# ---- BASE_SHA-drift defeat case (adversarial-review regression, issue
# ---- #1330) ----
#
# The one way to silently defeat this oracle: point BASE_SHA at a POST-split
# commit. The "OLD" source fetched from such a commit imports shape_checks,
# which resolves against the same live on-disk package "NEW" uses, so the
# comparison degenerates to comparing the working tree against itself and
# passes unconditionally. Reproduced live before this guard existed: a
# deliberate evidence-string regression in shape_checks/orchestrator.py made
# main() report all 29 skills differing at the real BASE_SHA, and report a
# clean PASS the moment BASE_SHA was moved to a post-split commit.


def test_assert_pre_split_source_accepts_a_stdlib_only_pre_split_source() -> None:
    # The real pre-split checker is a single stdlib-only file that never
    # imports shape_checks -- this must not be a false positive.
    vsc._assert_pre_split_source("import argparse\nimport sys\nfrom pathlib import Path\n")


def test_assert_pre_split_source_tolerates_a_prose_mention_of_the_package() -> None:
    # The guard matches an IMPORT, not a bare substring: a docstring or
    # comment naming shape_checks does not make the comparison vacuous, and
    # flagging it would block a legitimate pre-split revision.
    vsc._assert_pre_split_source('"""Superseded by the shape_checks package."""\nimport sys\n')


@pytest.mark.parametrize(
    "post_split_source",
    [
        "from shape_checks.constants import CheckResult\n",
        "import shape_checks.manifest\n",
        "import argparse\n\nfrom shape_checks.frontmatter import _parse_frontmatter\n",
    ],
)
def test_assert_pre_split_source_rejects_a_post_split_source(post_split_source: str) -> None:
    with pytest.raises(RuntimeError, match="POST-split revision"):
        vsc._assert_pre_split_source(post_split_source)


def test_load_old_module_refuses_a_post_split_base_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # End of the wiring: a drifted BASE_SHA must fail loudly out of
    # _load_old_module rather than importing a shape_checks-backed "OLD"
    # module and producing a vacuous PASS.
    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            argv, 0, stdout="from shape_checks.constants import CheckResult\n", stderr=""
        )

    monkeypatch.setattr(vsc.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="POST-split revision"):
        vsc._load_old_module(tmp_path)

    # And it refuses BEFORE writing the source out, so no half-materialized
    # OLD module is left behind for a later step to pick up.
    assert not (tmp_path / "gitapex_check_skill_shape_old.py").exists()


def test_the_real_base_sha_still_points_at_a_pre_split_revision() -> None:
    """The committed BASE_SHA constant itself must satisfy the guard --
    otherwise every run of this script is vacuous and the end-to-end test
    below passes for the wrong reason."""
    source = subprocess.run(
        ["git", "show", f"{vsc.BASE_SHA}:{vsc.OLD_RELATIVE_PATH}"],
        cwd=vsc.REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    vsc._assert_pre_split_source(source)


def test_main_reports_the_first_divergence_when_only_the_order_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Check ORDER is part of the contract this script asserts, and
    # reordering results is exactly what a decomposition of check_shape()
    # can get wrong. Both "only" lists are membership-based, so they come
    # back empty for a pure reorder -- without a positional fallback the
    # operator gets a bare "output differs." headline and nothing else.
    (tmp_path / "skills" / "skill-six").mkdir(parents=True)
    (tmp_path / "skills" / "skill-six" / "SKILL.md").write_text("---\nname: skill-six\n---\n", encoding="utf-8")
    monkeypatch.setattr(vsc, "REPO_ROOT", tmp_path)

    first = _FakeResult(name="check-a", passed=True, rule="r", evidence="e")
    second = _FakeResult(name="check-b", passed=True, rule="r", evidence="e")
    monkeypatch.setattr(vsc, "_load_old_module", lambda _tmp: _stub_module(lambda _md: [first, second]))
    monkeypatch.setattr(vsc, "_load_new_module", lambda: _stub_module(lambda _md: [second, first]))

    exit_code = vsc.main()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "differ in ORDER or multiplicity" in out
    assert "first divergence at index 0:" in out
    assert "OLD: ('check-a', True, 'r', 'e')" in out
    assert "NEW: ('check-b', True, 'r', 'e')" in out


def test_main_still_reports_a_plain_value_diff_without_the_order_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The ordinary OLD-only/NEW-only path must not start emitting the
    # order-fallback text: an evidence change is a value difference, not a
    # reorder, and mislabelling it would send a reader looking for the
    # wrong kind of regression.
    (tmp_path / "skills" / "skill-seven").mkdir(parents=True)
    (tmp_path / "skills" / "skill-seven" / "SKILL.md").write_text("---\nname: skill-seven\n---\n", encoding="utf-8")
    monkeypatch.setattr(vsc, "REPO_ROOT", tmp_path)

    monkeypatch.setattr(
        vsc,
        "_load_old_module",
        lambda _tmp: _stub_module(lambda _md: [_FakeResult(name="check-a", passed=True, rule="r", evidence="old")]),
    )
    monkeypatch.setattr(
        vsc,
        "_load_new_module",
        lambda: _stub_module(lambda _md: [_FakeResult(name="check-a", passed=True, rule="r", evidence="new")]),
    )

    exit_code = vsc.main()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "OLD only:" in out
    assert "differ in ORDER or multiplicity" not in out
