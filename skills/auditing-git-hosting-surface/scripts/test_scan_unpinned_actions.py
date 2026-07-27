"""Tests for scan_unpinned_actions.py.

Fixtures are synthesized in tmp_path so the test is self-contained and
travels with the skill on vendoring (same approach as
evaluating-skill-quality/scripts/test_check_skill_shape.py). Not wired into
the root pyproject.toml testpaths -- this skill's checklist item is meant to
stand alone; run directly with:
    python3 -m pytest skills/auditing-git-hosting-surface/scripts/
"""

from pathlib import Path

import scan_unpinned_actions as sua


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


def test_repository_workflows_are_pin_clean():
    """The gate: this repo's real workflows must all be SHA-pinned."""
    repo_root = Path(__file__).resolve().parents[3]
    findings = sua.find_unpinned_actions(repo_root / ".github" / "workflows")
    assert findings == [], f"unpinned actions in real workflows: {findings}"
