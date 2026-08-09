"""Tests for gitapex_scan_unpinned_actions.py.

Fixtures are synthesized in tmp_path so the test is self-contained and
travels with the skill on vendoring (same approach as
evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py). Not wired into
the root pyproject.toml testpaths -- this skill's checklist item is meant to
stand alone; run directly with:
    python3 -m pytest skills/scanning-attack-surfaces/scripts/
"""

from pathlib import Path

import gitapex_scan_unpinned_actions as sua


def _write(workflows_dir: Path, name: str, content: str) -> None:
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / name).write_text(content)


def test_sha_pinned_action_is_not_flagged(tmp_path):
    _write(
        tmp_path,
        "ci.yml",
        "      - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0  # v7.0.0\n",
    )
    assert sua.find_unpinned_actions(tmp_path) == []


def test_tag_pinned_action_is_flagged(tmp_path):
    _write(tmp_path, "ci.yml", "      - uses: actions/checkout@v4\n")
    findings = sua.find_unpinned_actions(tmp_path)
    assert len(findings) == 1
    assert findings[0][0].endswith("ci.yml")
    assert "actions/checkout@v4" in findings[0][2]


def test_branch_pinned_action_is_flagged(tmp_path):
    _write(tmp_path, "ci.yml", "      - uses: owner/repo@main\n")
    assert len(sua.find_unpinned_actions(tmp_path)) == 1


def test_local_action_is_not_flagged(tmp_path):
    _write(tmp_path, "ci.yml", "      - uses: ./local-action\n")
    assert sua.find_unpinned_actions(tmp_path) == []


def test_docker_action_is_not_flagged(tmp_path):
    _write(tmp_path, "ci.yml", "      - uses: docker://alpine:3.19\n")
    assert sua.find_unpinned_actions(tmp_path) == []


def test_trailing_version_comment_does_not_hide_a_real_line(tmp_path):
    # Regression: an earlier version of USES_RE anchored the ref group to
    # end-of-line, so any uses: line with a trailing "# vX.Y.Z" comment --
    # this repo's own convention on every real uses: line -- silently failed
    # to match at all. That made "no findings" mean "nothing was scanned",
    # not "every action is verified pinned" -- exactly the false-green
    # failure mode this whole skill exists to avoid.
    _write(tmp_path, "ci.yml", "      - uses: actions/checkout@v4  # intentionally unpinned\n")
    assert len(sua.find_unpinned_actions(tmp_path)) == 1


def test_double_quoted_sha_pinned_action_is_not_flagged(tmp_path):
    # Regression (Codex review on PR #111): `uses: "actions/checkout@<sha>"`
    # is valid YAML. Without stripping the quote pair, the ref capture group
    # keeps its trailing '"', fails the 40-char-SHA check, and a correctly
    # pinned line gets reported as a false unpinned finding.
    _write(
        tmp_path,
        "ci.yml",
        '      - uses: "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"\n',
    )
    assert sua.find_unpinned_actions(tmp_path) == []


def test_single_quoted_sha_pinned_action_is_not_flagged(tmp_path):
    _write(
        tmp_path,
        "ci.yml",
        "      - uses: 'actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0'\n",
    )
    assert sua.find_unpinned_actions(tmp_path) == []


def test_quoted_tag_pinned_action_is_still_flagged(tmp_path):
    _write(tmp_path, "ci.yml", '      - uses: "actions/checkout@v4"\n')
    assert len(sua.find_unpinned_actions(tmp_path)) == 1


def test_mismatched_quote_characters_are_not_stripped(tmp_path):
    # A leading '"' with no matching trailing '"' is not a real quote pair
    # -- must not be silently stripped, since that could hide a genuine
    # unpinned ref behind mismatched punctuation instead of flagging it.
    _write(tmp_path, "ci.yml", "      - uses: \"actions/checkout@v4'\n")
    assert len(sua.find_unpinned_actions(tmp_path)) == 1


def test_multiple_files_and_lines_all_reported(tmp_path):
    _write(tmp_path, "a.yml", "      - uses: actions/checkout@v4\n")
    _write(tmp_path, "b.yml", "      - uses: owner/repo@v1\n      - uses: owner/repo@main\n")
    assert len(sua.find_unpinned_actions(tmp_path)) == 3


def test_undecodable_workflow_file_is_skipped_not_crashed(tmp_path):
    # Regression: a non-UTF-8 workflow file raised an unhandled
    # UnicodeDecodeError from workflow.read_text() instead of being reported
    # as a finding, and clean files in the same directory must still be
    # scanned.
    workflows_dir = tmp_path
    workflows_dir.mkdir(exist_ok=True)
    (workflows_dir / "bad.yml").write_bytes(b"\xff\xfe bad")
    _write(workflows_dir, "ok.yml", "      - uses: actions/checkout@v4\n")
    findings = sua.find_unpinned_actions(workflows_dir)
    assert len(findings) == 2
    paths = {path for path, _, _ in findings}
    assert any(p.endswith("ok.yml") for p in paths)
    assert any(p.endswith("bad.yml") for p in paths)


def test_undecodable_workflow_file_fails_closed_even_when_it_is_the_only_file(tmp_path):
    # Dimension 15 (fail-closed on malformed input): a file that cannot be
    # decoded cannot be verified clean, so it must not scan as if it had no
    # unpinned actions -- an inability to verify is a finding, not a silent
    # pass, even when the corrupted file is the only one that would have
    # carried the real violation.
    workflows_dir = tmp_path
    workflows_dir.mkdir(exist_ok=True)
    (workflows_dir / "bad.yml").write_bytes(b"      - uses: actions/checkout@v4\n\xff\xfe")
    findings = sua.find_unpinned_actions(workflows_dir)
    assert findings != []
    assert findings[0][0].endswith("bad.yml")


def test_missing_workflow_directory_fails_closed(tmp_path):
    # Issue #848: an absent directory was never scanned, so it cannot have
    # been shown clean. Returning [] here reported "no unpinned actions
    # found" for a target that does not exist -- the empirically-confirmed
    # false-clean recorded against the pre-absorption skill.
    findings = sua.find_unpinned_actions(tmp_path / "nope")
    assert len(findings) == 1
    assert "cannot verify" in findings[0][2]


def test_workflow_directory_that_is_a_file_fails_closed(tmp_path):
    not_a_dir = tmp_path / "workflows"
    not_a_dir.write_text("")
    findings = sua.find_unpinned_actions(not_a_dir)
    assert len(findings) == 1
    assert "cannot verify" in findings[0][2]


def test_empty_workflow_directory_fails_closed(tmp_path):
    # A directory that exists but holds no *.yml/*.yaml is the same claim
    # failure as a missing one: nothing was scanned.
    (tmp_path / "workflows").mkdir()
    findings = sua.find_unpinned_actions(tmp_path / "workflows")
    assert len(findings) == 1
    assert "no *.yml or *.yaml" in findings[0][2]


def test_directory_holding_only_non_workflow_files_fails_closed(tmp_path):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "README.md").write_text("not a workflow\n")
    findings = sua.find_unpinned_actions(workflows_dir)
    assert len(findings) == 1
    assert "no *.yml or *.yaml" in findings[0][2]


def test_repository_workflows_are_pin_clean():
    """The gate: this repo's real workflows must all be SHA-pinned."""
    repo_root = Path(__file__).resolve().parents[3]
    findings = sua.find_unpinned_actions(repo_root / ".github" / "workflows")
    assert findings == [], f"unpinned actions in real workflows: {findings}"
