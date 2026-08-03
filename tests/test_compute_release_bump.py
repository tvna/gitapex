"""Tests for the release version-bump computation script
(.github/scripts/compute_release_bump.py).

Steps 1-4 and 6-7 (parse_header/is_breaking/classify, compute_next_version,
write_bumped_manifests, render_notes) are pure-function unit tests: plain
Python data in, zero real git calls. discover_last_tag is exercised via a
stub `git_runner` callable. main()/collect_commits get one end-to-end pass
against a real, throwaway git repository (matching this repo's existing
test_skill_description_diff.py convention) so the CLI wrapper is proven
against the real `git` service path, not only against mocks.
"""

from __future__ import annotations

import json
import subprocess

import pytest

import compute_release_bump as crb

# ---------------------------------------------------------------------
# parse_header
# ---------------------------------------------------------------------


def test_parse_header_scoped_commit():
    parsed = crb.parse_header("feat(plugin): add release automation")
    assert parsed == crb.ParsedCommit(
        commit_type="feat",
        scope="plugin",
        breaking_marker=False,
        description="add release automation",
    )


def test_parse_header_unscoped_commit():
    parsed = crb.parse_header("fix: correct typo")
    assert parsed.commit_type == "fix"
    assert parsed.scope is None
    assert parsed.breaking_marker is False


def test_parse_header_breaking_marker():
    parsed = crb.parse_header("feat(plugin)!: rework config schema")
    assert parsed.breaking_marker is True
    assert parsed.scope == "plugin"


def test_parse_header_rejects_merge_commit_subject():
    assert crb.parse_header("Merge pull request #123 from foo/bar") is None


def test_parse_header_rejects_freeform_text():
    assert crb.parse_header("bumped some stuff") is None


def test_parse_header_rejects_unknown_type():
    assert crb.parse_header("oops(plugin): not a real type") is None


def test_parse_header_rejects_uppercase_scope():
    # Scope charclass is [a-z0-9_-] only -- uppercase must not match.
    assert crb.parse_header("feat(PLUGIN): x") is None


def test_parse_header_every_declared_type_parses():
    for commit_type in (
        "feat",
        "fix",
        "docs",
        "refactor",
        "perf",
        "test",
        "chore",
        "build",
        "ci",
    ):
        parsed = crb.parse_header(f"{commit_type}(plugin): change")
        assert parsed is not None
        assert parsed.commit_type == commit_type


# ---------------------------------------------------------------------
# is_breaking
# ---------------------------------------------------------------------


def test_is_breaking_true_via_header_marker():
    assert crb.is_breaking("feat(plugin)!: drop old flag", "") is True


def test_is_breaking_true_via_body_footer():
    body = "Longer explanation.\n\nBREAKING CHANGE: old flag removed.\n"
    assert crb.is_breaking("feat(plugin): drop old flag", body) is True


def test_is_breaking_false_when_neither_present():
    assert crb.is_breaking("feat(plugin): add flag", "Just a normal body.") is False


def test_is_breaking_body_footer_detected_even_for_unparsed_subject():
    body = "BREAKING CHANGE: everything changed\n"
    assert crb.is_breaking("totally freeform subject", body) is True


# ---------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------


def test_classify_feat_plugin_is_minor():
    parsed = crb.parse_header("feat(plugin): add x")
    assert crb.classify(parsed, breaking=False) == "minor"


def test_classify_wrong_scope_is_none():
    # feat(skills): ... must NOT count toward the plugin's version.
    parsed = crb.parse_header("feat(skills): add new skill")
    assert crb.classify(parsed, breaking=False) is None


def test_classify_breaking_feat_plugin_is_minor_never_major():
    parsed = crb.parse_header("feat(plugin)!: breaking change")
    breaking = crb.is_breaking("feat(plugin)!: breaking change", "")
    result = crb.classify(parsed, breaking)
    assert result == "minor"
    assert result != "major"


@pytest.mark.parametrize("commit_type", ["fix", "refactor", "perf"])
def test_classify_patch_types(commit_type):
    parsed = crb.parse_header(f"{commit_type}(plugin): change")
    assert crb.classify(parsed, breaking=False) == "patch"


@pytest.mark.parametrize("commit_type", ["docs", "chore", "test", "build", "ci"])
def test_classify_non_bumping_types(commit_type):
    parsed = crb.parse_header(f"{commit_type}(plugin): change")
    assert crb.classify(parsed, breaking=False) is None


def test_classify_unparsed_subject_is_none():
    assert crb.classify(None, breaking=False) is None
    assert crb.classify(None, breaking=True) is None


def test_classify_no_scope_is_none():
    parsed = crb.parse_header("feat: no scope at all")
    assert crb.classify(parsed, breaking=False) is None


# ---------------------------------------------------------------------
# compute_next_version
# ---------------------------------------------------------------------


def _commit(sha: str, subject: str, body: str = "") -> dict:
    return {"sha": sha, "subject": subject, "body": body}


def test_compute_next_version_minor_bump():
    commits = [_commit("a" * 40, "feat(plugin): add thing")]
    assert crb.compute_next_version("0.1.0", commits) == {
        "version": "0.2.0",
        "bump": "minor",
    }


def test_compute_next_version_patch_bump():
    commits = [_commit("a" * 40, "fix(plugin): correct bug")]
    assert crb.compute_next_version("0.1.0", commits) == {
        "version": "0.1.1",
        "bump": "patch",
    }


def test_compute_next_version_minor_bump_resets_patch():
    commits = [_commit("a" * 40, "feat(plugin): add thing")]
    assert crb.compute_next_version("0.4.7", commits) == {
        "version": "0.5.0",
        "bump": "minor",
    }


def test_compute_next_version_no_op_returns_none():
    commits = [
        _commit("a" * 40, "docs(plugin): update readme"),
        _commit("b" * 40, "feat(skills): unrelated product"),
        _commit("c" * 40, "totally freeform"),
    ]
    assert crb.compute_next_version("0.1.0", commits) is None


def test_compute_next_version_empty_commit_list_is_none():
    assert crb.compute_next_version("0.1.0", []) is None


def test_compute_next_version_invalid_current_version_raises():
    commits = [_commit("a" * 40, "feat(plugin): add thing")]
    with pytest.raises(ValueError):
        crb.compute_next_version("not-a-version", commits)


def test_compute_next_version_max_of_signals_not_cumulative():
    # One feat(plugin) + one fix(plugin) must yield exactly ONE minor
    # bump -- not two bumps, not a cumulative/multiplied version jump.
    commits = [
        _commit("a" * 40, "feat(plugin): add thing"),
        _commit("b" * 40, "fix(plugin): correct bug"),
    ]
    result = crb.compute_next_version("0.1.0", commits)
    assert result == {"version": "0.2.0", "bump": "minor"}


def test_compute_next_version_many_feats_still_one_bump():
    commits = [_commit(str(i) * 40, "feat(plugin): add thing") for i in range(5)]
    result = crb.compute_next_version("0.1.0", commits)
    assert result == {"version": "0.2.0", "bump": "minor"}


def test_compute_next_version_bootstrap_long_history():
    # discover_last_tag() returning None means the caller passes the full
    # history; simulate ~20+ mixed commits and confirm a correct, single
    # bump is still computed from current_version.
    commits = []
    for i in range(8):
        commits.append(_commit(f"{i:040x}", "docs(plugin): update docs"))
    for i in range(8):
        commits.append(_commit(f"{i:040x}", "chore(plugin): tidy"))
    for i in range(5):
        commits.append(_commit(f"{i:040x}", "fix(plugin): fix bug"))
    commits.append(_commit("f" * 40, "feat(plugin): add capability"))
    for i in range(3):
        commits.append(_commit(f"{i:040x}", "feat(skills): unrelated"))

    assert len(commits) >= 20

    def stub_git_runner(_args: list[str]) -> str:
        return ""  # no tags

    assert crb.discover_last_tag(stub_git_runner) is None
    result = crb.compute_next_version("0.3.2", commits)
    assert result == {"version": "0.4.0", "bump": "minor"}


def test_compute_next_version_adversarial_many_breaking_feats_never_major():
    # Explicit adversarial case: many breaking-marked feat(plugin)!
    # commits must still yield exactly "minor", never "major", and the
    # major component of current_version must be unchanged.
    commits = [
        _commit(f"{i:040x}", "feat(plugin)!: breaking change") for i in range(200)
    ]
    result = crb.compute_next_version("2.9.9", commits)
    assert result is not None
    assert result["bump"] == "minor"
    assert result["bump"] != "major"
    new_major = int(result["version"].split(".")[0])
    assert new_major == 2  # unchanged from current_version's major
    assert result["version"] == "2.10.0"


# ---------------------------------------------------------------------
# discover_last_tag
# ---------------------------------------------------------------------


def test_discover_last_tag_returns_first_line():
    def git_runner(_args: list[str]) -> str:
        return "gitapex--v0.3.0\ngitapex--v0.2.0\ngitapex--v0.1.0\n"

    assert crb.discover_last_tag(git_runner) == "gitapex--v0.3.0"


def test_discover_last_tag_none_when_no_tags():
    def git_runner(_args: list[str]) -> str:
        return ""

    assert crb.discover_last_tag(git_runner) is None


def test_discover_last_tag_calls_expected_git_args():
    seen = {}

    def git_runner(args: list[str]) -> str:
        seen["args"] = args
        return ""

    crb.discover_last_tag(git_runner)
    assert seen["args"] == ["tag", "-l", "gitapex--v*", "--sort=-v:refname"]


# ---------------------------------------------------------------------
# write_bumped_manifests
# ---------------------------------------------------------------------

_PLUGIN_JSON_FIXTURE = """{
  "name": "gitapex",
  "description": "A distributable skills collection for gitapex.",
  "version": "0.1.0",
  "author": {
    "name": "tvna"
  },
  "homepage": "https://github.com/tvna/gitapex",
  "repository": "https://github.com/tvna/gitapex",
  "license": "MIT"
}
"""

_APM_YML_FIXTURE = """# gitapex is normally an apm *provider* (see docs/repository-layout.md); this
# declares the two plugins its own skills already assume are present
# (docs/motivation.md), so `apm install` provisions them too.
#
# name/version are required by apm's manifest schema; they mirror
# .claude-plugin/plugin.json (the version source of truth). The drift gate in
# .github/scripts/scan_apm_manifest_drift.py keeps the two in lockstep.
name: gitapex
version: 0.1.0
dependencies:
  apm:
    - obra/superpowers
    - tvna/clairvoyance
"""


def test_write_bumped_manifests_success(tmp_path):
    plugin_path = tmp_path / "plugin.json"
    apm_path = tmp_path / "apm.yml"
    plugin_path.write_text(_PLUGIN_JSON_FIXTURE)
    apm_path.write_text(_APM_YML_FIXTURE)

    crb.write_bumped_manifests(plugin_path, apm_path, "0.2.0")

    new_plugin_text = plugin_path.read_text()
    new_apm_text = apm_path.read_text()

    assert '"version": "0.2.0"' in new_plugin_text
    assert '"version": "0.1.0"' not in new_plugin_text
    assert "version: 0.2.0" in new_apm_text
    assert "version: 0.1.0" not in new_apm_text

    # Everything else byte-for-byte preserved, including apm.yml's leading
    # comment block and plugin.json's other fields/formatting.
    expected_plugin = _PLUGIN_JSON_FIXTURE.replace(
        '"version": "0.1.0"', '"version": "0.2.0"'
    )
    expected_apm = _APM_YML_FIXTURE.replace("version: 0.1.0", "version: 0.2.0")
    assert new_plugin_text == expected_plugin
    assert new_apm_text == expected_apm
    # apm.yml's comment block specifically survives (yaml.safe_dump would
    # have destroyed it).
    assert "# gitapex is normally an apm *provider*" in new_apm_text
    assert "# .github/scripts/scan_apm_manifest_drift.py keeps the two" in new_apm_text


def test_write_bumped_manifests_no_leftover_temp_file(tmp_path):
    plugin_path = tmp_path / "plugin.json"
    apm_path = tmp_path / "apm.yml"
    plugin_path.write_text(_PLUGIN_JSON_FIXTURE)
    apm_path.write_text(_APM_YML_FIXTURE)

    crb.write_bumped_manifests(plugin_path, apm_path, "0.2.0")

    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == ["apm.yml", "plugin.json"]


def test_write_bumped_manifests_missing_version_line_raises(tmp_path):
    plugin_path = tmp_path / "plugin.json"
    apm_path = tmp_path / "apm.yml"
    broken_plugin = _PLUGIN_JSON_FIXTURE.replace('"version": "0.1.0",\n', "")
    plugin_path.write_text(broken_plugin)
    apm_path.write_text(_APM_YML_FIXTURE)

    with pytest.raises(RuntimeError):
        crb.write_bumped_manifests(plugin_path, apm_path, "0.2.0")

    # Fail loud, not silent no-op: neither file was touched.
    assert plugin_path.read_text() == broken_plugin
    assert apm_path.read_text() == _APM_YML_FIXTURE


def test_write_bumped_manifests_duplicate_version_line_raises(tmp_path):
    plugin_path = tmp_path / "plugin.json"
    apm_path = tmp_path / "apm.yml"
    duplicated_plugin = _PLUGIN_JSON_FIXTURE.replace(
        '"version": "0.1.0",\n',
        '"version": "0.1.0",\n  "duplicateVersion": "0.9.9",\n',
        1,
    )
    # Force a genuine second match of the exact version-line pattern.
    duplicated_plugin = duplicated_plugin.replace(
        '"duplicateVersion": "0.9.9"', '"version": "0.9.9"'
    )
    plugin_path.write_text(duplicated_plugin)
    apm_path.write_text(_APM_YML_FIXTURE)

    with pytest.raises(RuntimeError):
        crb.write_bumped_manifests(plugin_path, apm_path, "0.2.0")

    # Raises rather than picking one of the two matches arbitrarily; file
    # is untouched.
    assert plugin_path.read_text() == duplicated_plugin
    assert apm_path.read_text() == _APM_YML_FIXTURE


def test_write_bumped_manifests_cleans_up_temp_file_on_write_failure(tmp_path, monkeypatch):
    plugin_path = tmp_path / "plugin.json"
    apm_path = tmp_path / "apm.yml"
    plugin_path.write_text(_PLUGIN_JSON_FIXTURE)
    apm_path.write_text(_APM_YML_FIXTURE)

    def failing_replace(_src, _dst):
        raise OSError("simulated os.replace failure")

    monkeypatch.setattr(crb.os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated os.replace failure"):
        crb.write_bumped_manifests(plugin_path, apm_path, "0.2.0")

    # The failure must not leave a stray temp file behind in the directory.
    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == ["apm.yml", "plugin.json"]


def test_write_bumped_manifests_apm_missing_version_raises(tmp_path):
    plugin_path = tmp_path / "plugin.json"
    apm_path = tmp_path / "apm.yml"
    plugin_path.write_text(_PLUGIN_JSON_FIXTURE)
    broken_apm = _APM_YML_FIXTURE.replace("version: 0.1.0\n", "")
    apm_path.write_text(broken_apm)

    with pytest.raises(RuntimeError):
        crb.write_bumped_manifests(plugin_path, apm_path, "0.2.0")

    # plugin.json is processed first and DID get bumped before apm.yml's
    # failure surfaced -- write_bumped_manifests only guarantees each
    # individual file's write is atomic, not both-or-neither across files.
    assert '"version": "0.2.0"' in plugin_path.read_text()
    assert apm_path.read_text() == broken_apm


def test_write_bumped_manifests_apm_empty_version_value_raises(tmp_path):
    # Regression: an apm.yml whose `version:` key carries no value must
    # fail loud, NOT swallow the following line. The version-line pattern
    # must not let its inter-token whitespace cross a newline: with `\s*`
    # (which matches "\n") the match ran from `version:` through the *next*
    # key, counted as exactly one match, and the substitution then wrote
    # `version: 0.2.0` over both lines -- silently deleting `dependencies:`
    # and leaving a structurally broken manifest that the "exactly one
    # match" guard was supposed to make impossible.
    plugin_path = tmp_path / "plugin.json"
    apm_path = tmp_path / "apm.yml"
    plugin_path.write_text(_PLUGIN_JSON_FIXTURE)
    broken_apm = _APM_YML_FIXTURE.replace("version: 0.1.0\n", "version:\n")
    apm_path.write_text(broken_apm)

    with pytest.raises(RuntimeError):
        crb.write_bumped_manifests(plugin_path, apm_path, "0.2.0")

    # The manifest is untouched -- in particular the key that followed the
    # valueless `version:` line is still there.
    assert apm_path.read_text() == broken_apm
    assert "dependencies:" in apm_path.read_text()


def test_apm_version_pattern_never_matches_across_a_newline():
    # Directly pin the property the bug violated: the pattern's whitespace
    # run may not span a line break, so it can never consume a following
    # key as if it were the version value.
    swallowing = "name: gitapex\nversion:\ndependencies:\n  apm:\n    - a/b\n"
    assert crb._APM_VERSION_RE.findall(swallowing) == []
    # ...while a normal one-line `version: X.Y.Z` still matches exactly once.
    assert len(crb._APM_VERSION_RE.findall("name: x\nversion: 0.1.0\n")) == 1


# ---------------------------------------------------------------------
# render_notes
# ---------------------------------------------------------------------


def test_render_notes_grouped_sections():
    commits = [
        _commit("1111111abc", "feat(plugin): add feature one"),
        _commit("2222222abc", "fix(plugin): correct bug one"),
        _commit("3333333abc", "refactor(plugin): tidy module"),
        _commit("4444444abc", "perf(plugin): speed up loop"),
        _commit("5555555abc", "docs(plugin): update readme"),
    ]
    notes = crb.render_notes(commits)

    assert "### Features" in notes
    assert "- feat(plugin): add feature one (1111111)" in notes
    assert "### Fixes" in notes
    assert "- fix(plugin): correct bug one (2222222)" in notes
    assert "### Refactors" in notes
    assert "- refactor(plugin): tidy module (3333333)" in notes
    assert "- perf(plugin): speed up loop (4444444)" in notes
    assert "_1 other commit(s) since the last release" in notes


def test_render_notes_omits_empty_sections():
    commits = [_commit("1111111abc", "feat(plugin): only a feature")]
    notes = crb.render_notes(commits)
    assert "### Features" in notes
    assert "### Fixes" not in notes
    assert "### Refactors" not in notes


def test_render_notes_zero_omitted_case_still_prints_line():
    commits = [_commit("1111111abc", "feat(plugin): only a feature")]
    notes = crb.render_notes(commits)
    assert "_0 other commit(s) since the last release" in notes


def test_render_notes_empty_commit_list():
    notes = crb.render_notes([])
    assert notes.strip() == (
        "_0 other commit(s) since the last release "
        "(docs/chore/ci/test) omitted above._"
    )


def test_render_notes_wrong_scope_is_omitted_not_bucketed():
    commits = [_commit("1111111abc", "feat(skills): unrelated product")]
    notes = crb.render_notes(commits)
    assert "### Features" not in notes
    assert "_1 other commit(s)" in notes


# ---------------------------------------------------------------------
# collect_commits / main() -- real throwaway git repo, end to end
# ---------------------------------------------------------------------


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "a@b.c")
    _git(repo, "config", "user.name", "t")
    (repo / ".claude-plugin").mkdir()
    (repo / ".claude-plugin" / "plugin.json").write_text(_PLUGIN_JSON_FIXTURE)
    (repo / "apm.yml").write_text(_APM_YML_FIXTURE)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore(plugin): bootstrap fixture repo")
    return repo


def _commit_in_repo(repo, message, filename="file.txt"):
    (repo / filename).write_text(message)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def test_collect_commits_bootstrap_no_tag(git_repo):
    _commit_in_repo(git_repo, "feat(plugin): add capability", "a.txt")
    _commit_in_repo(git_repo, "feat(skills): unrelated", "b.txt")

    git_runner = crb._default_git_runner(git_repo)
    assert crb.discover_last_tag(git_runner) is None

    commits = crb.collect_commits(git_repo, git_runner)
    subjects = [c["subject"] for c in commits]
    assert "feat(plugin): add capability" in subjects
    assert "feat(skills): unrelated" in subjects
    assert "chore(plugin): bootstrap fixture repo" in subjects
    for commit in commits:
        assert len(commit["sha"]) == 40


def test_collect_commits_since_last_tag(git_repo):
    _git(git_repo, "tag", "gitapex--v0.1.0")
    _commit_in_repo(git_repo, "fix(plugin): correct bug", "c.txt")

    git_runner = crb._default_git_runner(git_repo)
    assert crb.discover_last_tag(git_runner) == "gitapex--v0.1.0"

    commits = crb.collect_commits(git_repo, git_runner)
    subjects = [c["subject"] for c in commits]
    assert subjects == ["fix(plugin): correct bug"]


def test_main_write_and_notes_and_github_output(git_repo, tmp_path):
    _commit_in_repo(git_repo, "feat(plugin): add capability", "a.txt")
    _commit_in_repo(git_repo, "feat(skills): unrelated", "b.txt")
    notes_path = tmp_path / "notes.md"
    gh_output_path = tmp_path / "gh_output.txt"

    rc = crb.main(
        [
            "--repo-root",
            str(git_repo),
            "--write",
            "--notes-out",
            str(notes_path),
            "--github-output",
            str(gh_output_path),
        ]
    )
    assert rc == 0

    plugin_data = json.loads((git_repo / ".claude-plugin" / "plugin.json").read_text())
    assert plugin_data["version"] == "0.2.0"
    apm_text = (git_repo / "apm.yml").read_text()
    assert "version: 0.2.0" in apm_text

    notes_text = notes_path.read_text()
    assert "### Features" in notes_text
    assert "add capability" in notes_text
    assert "unrelated" not in notes_text  # wrong scope, omitted

    gh_output_text = gh_output_path.read_text()
    assert "bump=minor" in gh_output_text
    assert "version=0.2.0" in gh_output_text


def test_main_dry_run_does_not_write_without_flag(git_repo):
    _commit_in_repo(git_repo, "feat(plugin): add capability", "a.txt")

    rc = crb.main(["--repo-root", str(git_repo)])
    assert rc == 0

    plugin_data = json.loads((git_repo / ".claude-plugin" / "plugin.json").read_text())
    assert plugin_data["version"] == "0.1.0"  # unchanged: --write was omitted


def test_main_no_applicable_commits_reports_bump_none(git_repo, tmp_path):
    _commit_in_repo(git_repo, "docs(plugin): update readme", "a.txt")
    gh_output_path = tmp_path / "gh_output.txt"

    rc = crb.main(
        ["--repo-root", str(git_repo), "--write", "--github-output", str(gh_output_path)]
    )
    assert rc == 0

    plugin_data = json.loads((git_repo / ".claude-plugin" / "plugin.json").read_text())
    assert plugin_data["version"] == "0.1.0"  # nothing to bump

    gh_output_text = gh_output_path.read_text()
    assert "bump=none" in gh_output_text
    assert "version=0.1.0" in gh_output_text


def test_main_missing_version_field_returns_one(git_repo, capsys):
    plugin_path = git_repo / ".claude-plugin" / "plugin.json"
    data = json.loads(plugin_path.read_text())
    del data["version"]
    plugin_path.write_text(json.dumps(data))
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-q", "-m", "chore(plugin): drop version field")

    rc = crb.main(["--repo-root", str(git_repo)])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_main_invalid_current_version_returns_one(git_repo, capsys):
    plugin_path = git_repo / ".claude-plugin" / "plugin.json"
    data = json.loads(plugin_path.read_text())
    data["version"] = "not-a-version"
    plugin_path.write_text(json.dumps(data))
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-q", "-m", "chore(plugin): corrupt version")
    _commit_in_repo(git_repo, "feat(plugin): add capability", "a.txt")

    rc = crb.main(["--repo-root", str(git_repo), "--write"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err
