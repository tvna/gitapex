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


VALID_FORM = """\
name: Bug report
description: Report a defect
body:
  - type: markdown
    attributes:
      value: Thanks for filing.
  - type: textarea
    id: what
    attributes:
      label: What happened
"""

VALID_PR = "## Summary\n\nWhat and why.\n"


def _github_repo(tmp_path: Path, form_text: str = VALID_FORM,
                 pr_text: str = VALID_PR) -> Path:
    it = tmp_path / ".github" / "ISSUE_TEMPLATE"
    it.mkdir(parents=True)
    (it / "bug.yml").write_text(form_text, encoding="utf-8")
    (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text(
        pr_text, encoding="utf-8"
    )
    return tmp_path


def test_github_valid(tmp_path: Path):
    assert vt.validate_github(_github_repo(tmp_path)) == []


def test_github_missing_required_key(tmp_path: Path):
    bad = "description: no name here\nbody:\n  - type: markdown\n    attributes:\n      value: hi\n"
    errs = vt.validate_github(_github_repo(tmp_path, form_text=bad))
    assert any("missing required key 'name'" in e for e in errs)


def test_github_empty_list_name(tmp_path: Path):
    bad = "name: []\ndescription: Y\nbody:\n  - type: markdown\n    attributes:\n      value: hi\n"
    errs = vt.validate_github(_github_repo(tmp_path, form_text=bad))
    assert any("missing required key 'name'" in e for e in errs)


def test_github_empty_list_description(tmp_path: Path):
    bad = "name: X\ndescription: []\nbody:\n  - type: markdown\n    attributes:\n      value: hi\n"
    errs = vt.validate_github(_github_repo(tmp_path, form_text=bad))
    assert any("missing required key 'description'" in e for e in errs)


def test_github_bad_body_type(tmp_path: Path):
    bad = "name: X\ndescription: Y\nbody:\n  - type: bogus\n    attributes:\n      label: hi\n"
    errs = vt.validate_github(_github_repo(tmp_path, form_text=bad))
    assert any("invalid type" in e for e in errs)


def test_github_markdown_needs_value(tmp_path: Path):
    bad = "name: X\ndescription: Y\nbody:\n  - type: markdown\n    attributes:\n      label: wrong\n"
    errs = vt.validate_github(_github_repo(tmp_path, form_text=bad))
    assert any("markdown needs attributes.value" in e for e in errs)


def test_github_dropdown_needs_options(tmp_path: Path):
    bad = (
        "name: X\ndescription: Y\nbody:\n"
        "  - type: dropdown\n    attributes:\n      label: Pick one\n"
    )
    errs = vt.validate_github(_github_repo(tmp_path, form_text=bad))
    assert any("dropdown needs a non-empty attributes.options list" in e for e in errs)


def test_github_checkboxes_needs_options(tmp_path: Path):
    bad = (
        "name: X\ndescription: Y\nbody:\n"
        "  - type: checkboxes\n    attributes:\n      label: Confirm\n      options: []\n"
    )
    errs = vt.validate_github(_github_repo(tmp_path, form_text=bad))
    assert any("checkboxes needs a non-empty attributes.options list" in e for e in errs)


def test_github_dropdown_valid_with_options(tmp_path: Path):
    good = (
        "name: X\ndescription: Y\nbody:\n"
        "  - type: dropdown\n    attributes:\n      label: Pick one\n"
        "      options:\n        - a\n        - b\n"
    )
    errs = vt.validate_github(_github_repo(tmp_path, form_text=good))
    assert errs == []


def test_github_invalid_yaml(tmp_path: Path):
    errs = vt.validate_github(_github_repo(tmp_path, form_text="name: [unclosed\n"))
    assert any("invalid YAML" in e for e in errs)


def test_github_missing_pr_template(tmp_path: Path):
    it = tmp_path / ".github" / "ISSUE_TEMPLATE"
    it.mkdir(parents=True)
    (it / "bug.yml").write_text(VALID_FORM, encoding="utf-8")
    errs = vt.validate_github(tmp_path)
    assert any("no PULL_REQUEST_TEMPLATE.md" in e for e in errs)


def test_github_non_ascii(tmp_path: Path):
    bad = "name: X\ndescription: café\nbody:\n  - type: markdown\n    attributes:\n      value: hi\n"
    errs = vt.validate_github(_github_repo(tmp_path, form_text=bad))
    assert any("non-ASCII" in e for e in errs)


VALID_CONFIG = (
    "blank_issues_enabled: false\n"
    "contact_links:\n"
    "  - name: Discuss\n"
    "    url: https://example.com\n"
    "    about: Talk to us\n"
)


def _write_config(tmp_path: Path, text: str) -> Path:
    repo = _github_repo(tmp_path)
    config = repo / ".github" / "ISSUE_TEMPLATE" / "config.yml"
    config.write_text(text, encoding="utf-8")
    return repo


def test_github_config_valid(tmp_path: Path):
    repo = _write_config(tmp_path, VALID_CONFIG)
    assert vt.validate_github(repo) == []


def test_github_config_bad_blank_issues_enabled(tmp_path: Path):
    bad = "blank_issues_enabled: 1\n"
    repo = _write_config(tmp_path, bad)
    errs = vt.validate_github(repo)
    assert any("blank_issues_enabled' must be boolean" in e for e in errs)


def test_github_config_bad_contact_link(tmp_path: Path):
    bad = "contact_links:\n  - name: Discuss\n    url: https://example.com\n"
    repo = _write_config(tmp_path, bad)
    errs = vt.validate_github(repo)
    assert any("contact_links[0] needs name/url/about" in e for e in errs)


def test_github_config_non_ascii(tmp_path: Path):
    bad = "blank_issues_enabled: false\n# café\n"
    repo = _write_config(tmp_path, bad)
    errs = vt.validate_github(repo)
    assert any("non-ASCII" in e for e in errs)


def _gitlab_repo(tmp_path: Path, issue_body="## Problem\n", mr_body="## Change\n") -> Path:
    it = tmp_path / ".gitlab" / "issue_templates"
    mt = tmp_path / ".gitlab" / "merge_request_templates"
    it.mkdir(parents=True)
    mt.mkdir(parents=True)
    (it / "bug.md").write_text(issue_body, encoding="utf-8")
    (mt / "default.md").write_text(mr_body, encoding="utf-8")
    return tmp_path


def test_gitlab_valid(tmp_path: Path):
    assert vt.validate_gitlab(_gitlab_repo(tmp_path)) == []


def test_gitlab_empty_template(tmp_path: Path):
    errs = vt.validate_gitlab(_gitlab_repo(tmp_path, issue_body="   \n"))
    assert any("is empty" in e for e in errs)


def test_gitlab_missing_dir(tmp_path: Path):
    (tmp_path / ".gitlab" / "issue_templates").mkdir(parents=True)
    (tmp_path / ".gitlab" / "issue_templates" / "b.md").write_text("hi\n", "utf-8")
    errs = vt.validate_gitlab(tmp_path)
    assert any("merge_request_templates" in e and "missing" in e for e in errs)


def test_validate_dispatch(tmp_path: Path):
    assert vt.validate(_gitlab_repo(tmp_path), "gitlab") == []


def test_main_ok(tmp_path: Path, capsys):
    _github_repo(tmp_path)
    rc = vt.main([str(tmp_path), "--platform", "github"])
    assert rc == 0
    assert "OK: github" in capsys.readouterr().out


def test_main_fail(tmp_path: Path, capsys):
    it = tmp_path / ".github" / "ISSUE_TEMPLATE"
    it.mkdir(parents=True)
    (it / "bug.yml").write_text("description: no name\nbody: []\n", "utf-8")
    rc = vt.main([str(tmp_path), "--platform", "github"])
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_bad_dir(tmp_path: Path):
    assert vt.main([str(tmp_path / "nope"), "--platform", "github"]) == 2


def test_main_ambiguous_platform(tmp_path: Path):
    _mk(tmp_path, ".github/ISSUE_TEMPLATE")
    _mk(tmp_path, ".gitlab/issue_templates")
    assert vt.main([str(tmp_path)]) == 2


def test_find_existing_real_template(tmp_path: Path):
    it = tmp_path / ".github" / "ISSUE_TEMPLATE"
    it.mkdir(parents=True)
    (it / "bug.yml").write_text("x", "utf-8")
    assert vt.find_existing_templates(tmp_path, "github") == [".github/ISSUE_TEMPLATE"]


def test_find_existing_ignores_config_yml(tmp_path: Path):
    # GitHub's ISSUE_TEMPLATE/config.yml is the template *chooser* config, not
    # a template -- a repo with only it has no templates and must not STOP.
    it = tmp_path / ".github" / "ISSUE_TEMPLATE"
    it.mkdir(parents=True)
    (it / "config.yml").write_text("blank_issues_enabled: false\n", "utf-8")
    assert vt.find_existing_templates(tmp_path, "github") == []


def test_find_existing_ignores_gitkeep(tmp_path: Path):
    it = tmp_path / ".github" / "ISSUE_TEMPLATE"
    it.mkdir(parents=True)
    (it / ".gitkeep").write_text("", "utf-8")
    assert vt.find_existing_templates(tmp_path, "github") == []


def test_find_existing_root_lowercase_pr_template(tmp_path: Path):
    # Root-level, lowercase pull_request_template.md is a real, GitHub-honored
    # location and must be detected.
    (tmp_path / "pull_request_template.md").write_text("## Summary\n", "utf-8")
    assert vt.find_existing_templates(tmp_path, "github") == ["pull_request_template.md"]


def test_check_existing_config_only_reports_none(tmp_path: Path, capsys):
    it = tmp_path / ".github" / "ISSUE_TEMPLATE"
    it.mkdir(parents=True)
    (it / "config.yml").write_text("blank_issues_enabled: false\n", "utf-8")
    rc = vt.main([str(tmp_path), "--platform", "github", "--check-existing"])
    assert rc == 0
    assert "NONE" in capsys.readouterr().out
