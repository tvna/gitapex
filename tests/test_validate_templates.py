from pathlib import Path

import pytest

import validate_templates as vt


def _mk(root: Path, rel: str) -> None:
    p = root / rel
    p.mkdir(parents=True, exist_ok=True)


def test_detect_github(tmp_path: Path):
    _mk(tmp_path, ".github/ISSUE_TEMPLATE")
    assert vt.detect_platform(tmp_path) == "github"


def test_detect_gitlab(tmp_path: Path):
    _mk(tmp_path, ".gitlab/issue_templates")
    assert vt.detect_platform(tmp_path) == "gitlab"


def test_detect_ambiguous_raises(tmp_path: Path):
    _mk(tmp_path, ".github/ISSUE_TEMPLATE")
    _mk(tmp_path, ".gitlab/issue_templates")
    with pytest.raises(ValueError):
        vt.detect_platform(tmp_path)


def test_detect_none_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        vt.detect_platform(tmp_path)
