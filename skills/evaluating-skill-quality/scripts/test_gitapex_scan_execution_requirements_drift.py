"""Tests for the executionRequirements companion drift scanner
(skills/evaluating-skill-quality/scripts/gitapex_scan_execution_requirements_drift.py,
issue #1022). Co-located with the scanner itself, mirroring
skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py's
own placement next to gitapex_check_skill_shape.py.

Fixture-based: each ACM-named mismatch shape (disabled-but-networked,
allowlist-but-out-of-list-host, unrestricted-but-no-network-use, and the
tools.write/tools.shell under/over-declaration pairs) gets its own test
against a minimal on-disk skill directory built under tmp_path, plus a
clean-pass counterpart proving the scanner does not fire on matching
declarations. A dedicated regression section pins four correctness bugs an
independent adversarial review of this module found and that were fixed
before merge. The final test is a real-repository *smoke* test only --
find_drift() must run without raising against the real skills/ tree, but
its result is deliberately NOT asserted to be empty: issue #1022's own
Non-goals excludes retroactively auditing every existing skill for a
pre-existing mismatch, and a live check found several already exist (e.g.
planning-a-branch-from-an-issue declares shell: [] but its own Step 8
invokes `python3 scripts/gitapex_check_acm_present.py`). This mirrors
gitapex_check_skill_shape.py's own un-registered status: neither carries a
.gitapex/ssot.json gate entry of its own; each is run deliberately against
one target skill at a time as part of evaluating-skill-quality's own
"Deterministic shape" lane, not as an automatic repo-wide CI gate.
"""

from __future__ import annotations

import pathlib

import gitapex_scan_execution_requirements_drift as scanner
import pytest


def _make_skill(
    tmp_path: pathlib.Path,
    *,
    name: str = "example-skill",
    skill_md: str = "# Example Skill\n\n## Steps\n\n1. Read the input.\n",
    scripts: dict[str, str] | None = None,
) -> pathlib.Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    if scripts:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        for filename, content in scripts.items():
            (scripts_dir / filename).write_text(content, encoding="utf-8")
    return skill_dir


def _severities(findings: list[scanner.Finding]) -> list[str]:
    return [f.severity for f in findings]


# ---- find_network_drift ----


def test_disabled_but_networked_script_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import urllib.request\n"})
    findings = scanner.find_network_drift({"mode": "disabled"}, skill_dir)
    assert _severities(findings) == ["error"]
    assert "network-mode-vs-script-content" in findings[0].message


def test_absent_network_block_but_networked_script_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import requests\n"})
    findings = scanner.find_network_drift(None, skill_dir)
    assert _severities(findings) == ["error"]


def test_disabled_and_no_network_use_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import pathlib\n"})
    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_allowlist_with_in_list_host_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": 'import urllib.request\nurllib.request.urlopen("https://github.com/x")\n'},
    )
    findings = scanner.find_network_drift({"mode": "allowlist", "domains": ["github.com"]}, skill_dir)
    assert findings == []


def test_allowlist_with_out_of_list_host_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": 'import requests\nrequests.get("https://evil.example.com/x")\n'},
    )
    findings = scanner.find_network_drift({"mode": "allowlist", "domains": ["github.com"]}, skill_dir)
    assert _severities(findings) == ["error"]
    assert "evil.example.com" in findings[0].message


def test_unrestricted_with_use_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import httpx\n"})
    assert scanner.find_network_drift({"mode": "unrestricted"}, skill_dir) == []


def test_unrestricted_but_no_use_is_warning(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import pathlib\n"})
    findings = scanner.find_network_drift({"mode": "unrestricted"}, skill_dir)
    assert _severities(findings) == ["warning"]
    assert "over-declared" in findings[0].message


def test_no_scripts_directory_does_not_crash(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path)
    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


# ---- find_tools_drift ----


def test_write_under_declared_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Creates a new file for the fixture.\n",
    )
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert _severities(findings) == ["error"]
    assert "tools-write-vs-skill-md" in findings[0].message


def test_write_declared_and_matches_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Creates a new file for the fixture.\n",
    )
    findings = scanner.find_tools_drift({"write": ["files"], "shell": []}, skill_dir)
    assert findings == []


def test_write_declared_but_no_match_is_warning(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, skill_md="# Example\n\n## Steps\n\n1. Read the input.\n")
    findings = scanner.find_tools_drift({"write": ["files"], "shell": []}, skill_dir)
    assert _severities(findings) == ["warning"]
    assert "tools-write-vs-skill-md" in findings[0].message
    assert "over-declared" in findings[0].message


def test_shell_under_declared_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Run `git commit` to record the change.\n",
    )
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert _severities(findings) == ["error"]
    assert "tools-shell-vs-skill-md" in findings[0].message


def test_shell_declared_and_matches_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Run `git commit` to record the change.\n",
    )
    findings = scanner.find_tools_drift({"write": [], "shell": ["git"]}, skill_dir)
    assert findings == []


def test_shell_declared_but_no_match_is_warning(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, skill_md="# Example\n\n## Steps\n\n1. Read the input.\n")
    findings = scanner.find_tools_drift({"write": [], "shell": ["git"]}, skill_dir)
    assert _severities(findings) == ["warning"]
    assert "tools-shell-vs-skill-md" in findings[0].message


def test_fully_clean_skill_has_no_tools_findings(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, skill_md="# Example\n\n## Steps\n\n1. Read the input.\n")
    assert scanner.find_tools_drift({"write": [], "shell": []}, skill_dir) == []


def test_missing_skill_md_does_not_crash(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "no-skill-md"
    skill_dir.mkdir()
    assert scanner.find_tools_drift({"write": [], "shell": []}, skill_dir) == []


# ---- regression tests for bugs found by an independent adversarial review
# of this module (fixed before merge; each test pins the fix) ----


def test_shell_backtick_alternatives_match_without_a_preceding_run(tmp_path: pathlib.Path) -> None:
    """The real-world case the module docstring cites as motivation: a
    prior version of _SHELL_INTENT_PATTERN wrapped every alternative,
    including four starting with a literal backtick, in one leading \\b --
    but \\b demands a word/non-word transition, and a backtick is itself
    non-word, so those four alternatives could never match in ordinary
    Markdown (a backtick preceded by whitespace/punctuation). Only the
    generic ``run\\s+```` alternative worked, silently masking the bug --
    every case below previously returned no match."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Its own Step 8 invokes `python3 scripts/gitapex_check_acm_present.py`.\n",
    )
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert _severities(findings) == ["error"]

    for phrase in (
        'Then invoke `git commit -m "x"` to save.',
        "Use `uv run pytest` here.",
        "Finish with `git push` to publish.",
        "Run `npm install` first.",
    ):
        assert scanner._SHELL_INTENT_PATTERN.search(phrase), f"should match: {phrase!r}"


def test_write_nouns_do_not_match_as_a_bare_prefix(tmp_path: pathlib.Path) -> None:
    """A prior version of _WRITE_NOUNS left several alternatives (file,
    script, branch, commit, document, ...) with no trailing \\b, so they
    matched as a bare prefix of an unrelated word right after them --
    "creates a review committee" matched via "commit", "creates a
    scripting-friendly interface" matched via "script". Neither sentence
    has anything to do with writing a file; both must produce zero
    findings when tools.write is correctly declared empty."""
    cases = {
        "committee-case": "# Example\n\n## Steps\n\n1. This skill creates a review committee for the launch.\n",
        "scripting-case": "# Example\n\n## Steps\n\n1. This skill creates a scripting-friendly interface for review.\n",
    }
    for name, skill_md in cases.items():
        skill_dir = _make_skill(tmp_path, name=name, skill_md=skill_md)
        findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
        assert findings == [], f"false positive for: {skill_md!r}"


def test_null_network_mode_still_fails_closed_on_real_usage(tmp_path: pathlib.Path) -> None:
    """A prior version used ``network.get("mode", "disabled")``, which only
    substitutes the default when the key is ABSENT -- a real ``mode: null``
    (valid YAML) or a mis-cased/typo'd mode string (e.g. "Disabled") passed
    straight through as the effective mode, matched none of the three
    recognized-mode branches, and silently returned no findings even
    against a script making real, unrestricted network calls. Any
    unrecognized mode value must now fall back to the strictest treatment
    ("disabled") and still flag real usage."""
    skill_dir = _make_skill(
        tmp_path, scripts={"fetch.py": 'import requests\nrequests.get("https://evil.example.com")\n'}
    )
    for network in ({"mode": None}, {"mode": "Disabled"}, {"mode": "off"}):
        findings = scanner.find_network_drift(network, skill_dir)
        assert _severities(findings) == ["error"], f"should fail closed for network={network!r}"


def test_allowlist_host_comparison_is_case_insensitive(tmp_path: pathlib.Path) -> None:
    """Hostnames are case-insensitive (RFC 4343); a prior version compared
    the literal-cased extracted host against the literal-cased declared
    domains, so a script referencing "https://GitHub.com/x" against a
    correctly declared ``domains: [github.com]`` produced a false-positive
    error finding."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": 'import requests\nrequests.get("https://GitHub.com/x")\n'},
    )
    findings = scanner.find_network_drift({"mode": "allowlist", "domains": ["github.com"]}, skill_dir)
    assert findings == []


# ---- find_drift (integration) ----


def _write_sidecar(skill_dir: pathlib.Path, execution_requirements: dict[str, object]) -> None:
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        f"metadata:\n  name: {skill_dir.name}\n"
        "spec:\n"
        "  executionRequirements:\n"
        f"    network:\n      mode: {execution_requirements.get('network_mode', 'disabled')}\n"
        f"    tools:\n"
        f"      write: {execution_requirements.get('write_tags', [])}\n"
        f"      shell: {execution_requirements.get('shell_tags', [])}\n",
        encoding="utf-8",
    )


def test_find_drift_wires_network_and_tools_checks_end_to_end(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Creates a new file for the fixture.\n",
        scripts={"fetch.py": "import urllib.request\n"},
    )
    _write_sidecar(skill_dir, {"network_mode": "disabled", "write_tags": [], "shell_tags": []})

    findings = scanner.find_drift(skills_dir=tmp_path, min_expected_skill_dirs=1)

    messages = [f.message for f in findings]
    assert any("network-mode-vs-script-content" in m and m.startswith("example-skill:") for m in messages)
    assert any("tools-write-vs-skill-md" in m and m.startswith("example-skill:") for m in messages)


def test_find_drift_below_floor_is_error(tmp_path: pathlib.Path) -> None:
    findings = scanner.find_drift(skills_dir=tmp_path, min_expected_skill_dirs=5)
    assert _severities(findings) == ["error"]
    assert "skill-discovery-floor" in findings[0].message


def test_find_drift_missing_sidecar_is_error(tmp_path: pathlib.Path) -> None:
    _make_skill(tmp_path)
    findings = scanner.find_drift(skills_dir=tmp_path, min_expected_skill_dirs=1)
    assert _severities(findings) == ["error"]
    assert "metadata-file-present" in findings[0].message


# ---- find_skill_drift (single-target, the CLI's own entry point) ----


def test_find_skill_drift_wires_network_and_tools_checks(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Creates a new file for the fixture.\n",
        scripts={"fetch.py": "import urllib.request\n"},
    )
    _write_sidecar(skill_dir, {"network_mode": "disabled", "write_tags": [], "shell_tags": []})

    findings = scanner.find_skill_drift(skill_dir)

    messages = [f.message for f in findings]
    assert any("network-mode-vs-script-content" in m for m in messages)
    assert any("tools-write-vs-skill-md" in m for m in messages)
    # Unlike find_drift(), messages carry no skill-name prefix -- single-target use.
    assert not any(m.startswith("example-skill:") for m in messages)


def test_find_skill_drift_missing_sidecar_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path)
    findings = scanner.find_skill_drift(skill_dir)
    assert _severities(findings) == ["error"]
    assert "metadata-file-present" in findings[0].message


def test_find_skill_drift_invalid_yaml_sidecar_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path)
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "gitapex.yaml").write_text("key: [unclosed\n", encoding="utf-8")

    findings = scanner.find_skill_drift(skill_dir)

    assert _severities(findings) == ["error"]
    assert "not valid YAML" in findings[0].message


def test_find_skill_drift_clean_skill_has_no_findings(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, skill_md="# Example\n\n## Steps\n\n1. Read the input.\n")
    _write_sidecar(skill_dir, {"network_mode": "disabled", "write_tags": [], "shell_tags": []})
    assert scanner.find_skill_drift(skill_dir) == []


# ---- main() CLI ----


def test_main_requires_a_target_argument() -> None:
    with pytest.raises(SystemExit):
        scanner.main([])


def test_main_clean_tree_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scanner, "find_skill_drift", lambda skill_dir: [])
    assert scanner.main(["some/skill/dir"]) == 0


def test_main_warning_only_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scanner,
        "find_skill_drift",
        lambda skill_dir: [scanner.Finding("warning", "some over-declaration")],
    )
    assert scanner.main(["some/skill/dir"]) == 0


def test_main_error_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scanner,
        "find_skill_drift",
        lambda skill_dir: [scanner.Finding("error", "some under-declaration")],
    )
    assert scanner.main(["some/skill/dir"]) == 1


def test_main_end_to_end_against_a_real_skill_dir_no_mocking(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No monkeypatching -- proves the CLI wiring (argument parsing ->
    find_skill_drift -> exit code) works end to end, not just that main()
    correctly reacts to a mocked find_skill_drift."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Creates a new file for the fixture.\n",
    )
    _write_sidecar(skill_dir, {"network_mode": "disabled", "write_tags": [], "shell_tags": []})

    exit_code = scanner.main([str(skill_dir)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "tools-write-vs-skill-md" in captured.out


# ---- error-path coverage: discover_skill_dirs / _load_sidecar / _spec_of ----


def test_discover_skill_dirs_missing_directory_is_empty(tmp_path: pathlib.Path) -> None:
    assert scanner.discover_skill_dirs(tmp_path / "does-not-exist") == []


def test_load_sidecar_nonexistent_file_raises_read_error(tmp_path: pathlib.Path) -> None:
    with pytest.raises(scanner.ReadError, match="cannot be read"):
        scanner._load_sidecar(tmp_path / "missing.yaml")


def test_load_sidecar_non_utf8_raises_read_error(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "bad-encoding.yaml"
    path.write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(scanner.ReadError, match="not valid UTF-8"):
        scanner._load_sidecar(path)


def test_load_sidecar_invalid_yaml_raises_read_error(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("key: [unclosed\n", encoding="utf-8")
    with pytest.raises(scanner.ReadError, match="not valid YAML"):
        scanner._load_sidecar(path)


def test_read_text_best_effort_on_directory_returns_empty(tmp_path: pathlib.Path) -> None:
    directory = tmp_path / "a-directory"
    directory.mkdir()
    assert scanner._read_text_best_effort(directory) == ""


def test_spec_of_non_dict_instance_is_empty() -> None:
    assert scanner._spec_of(["not", "a", "dict"]) == {}


def test_find_drift_invalid_yaml_sidecar_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path)
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "gitapex.yaml").write_text("key: [unclosed\n", encoding="utf-8")

    findings = scanner.find_drift(skills_dir=tmp_path, min_expected_skill_dirs=1)

    assert _severities(findings) == ["error"]
    assert "not valid YAML" in findings[0].message


def test_find_drift_non_dict_execution_requirements_is_tolerated(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path)
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        f"metadata:\n  name: {skill_dir.name}\n"
        "spec:\n"
        "  executionRequirements: not-a-mapping\n",
        encoding="utf-8",
    )

    findings = scanner.find_drift(skills_dir=tmp_path, min_expected_skill_dirs=1)

    assert findings == []


# ---- defeat tests: adversarially probing the detection logic itself,
# not just its happy path (evaluating-deterministic-gate-quality dimension
# 15's own instruction: "independently construct and run a malformed,
# boundary, or missing-dependency input directly against the gate before
# crediting this dimension") ----


def test_malformed_execution_requirements_still_fail_closed_on_real_usage(tmp_path: pathlib.Path) -> None:
    """Dimension 15 proof: a garbage (non-mapping) executionRequirements
    value must NOT silently read as "nothing to check" when the skill's
    real content actually performs the capability that would have been
    gated -- it must fall back to the strictest defaults (network
    'disabled', tools not declared) and still flag the real usage as an
    error, not silently pass because the declaration itself was malformed."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Creates a new file for the fixture.\n",
        scripts={"fetch.py": "import urllib.request\n"},
    )
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        f"metadata:\n  name: {skill_dir.name}\n"
        "spec:\n"
        "  executionRequirements: [1, 2, 3]\n",
        encoding="utf-8",
    )

    findings = scanner.find_drift(skills_dir=tmp_path, min_expected_skill_dirs=1)

    messages = [f.message for f in findings]
    assert any("network-mode-vs-script-content" in m for m in messages)
    assert any("tools-write-vs-skill-md" in m for m in messages)
    assert all(f.severity == "error" for f in findings)


def test_dynamically_constructed_host_evades_allowlist_check(tmp_path: pathlib.Path) -> None:
    """Attempted evasion of the allowlist out-of-list-host check: a host
    built at runtime from string concatenation, rather than appearing as a
    literal https?://host substring, is genuinely invisible to
    _URL_HOST_PATTERN's regex-only matching. This is NOT a passing
    detection -- it is the documented false-negative limitation
    (module docstring: "a network call routed through an unlisted helper,
    or dynamic/reflective invocation, can still slip through undetected")
    proven concretely rather than only asserted in prose. If a future
    change to find_network_drift starts catching this case, this test's
    own assertion (== []) will fail and must be updated deliberately, not
    silently -- it is not a regression to fix quietly."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": ('import requests\nhost = "evil" + ".example.com"\nrequests.get(f"https://{host}/x")\n')},
    )
    findings = scanner.find_network_drift({"mode": "allowlist", "domains": ["github.com"]}, skill_dir)
    assert findings == []


# ---- real-repository smoke test ----


def test_real_repository_scan_runs_without_raising() -> None:
    """Deliberately NOT asserting == [] -- see module docstring: issue
    #1022's own Non-goals excludes the retroactive sweep that would be
    needed to make the real repository clean under this scanner today.
    This test only proves find_drift() executes end-to-end against the
    real tree without an unhandled exception."""
    findings = scanner.find_drift()
    assert isinstance(findings, list)
    assert all(isinstance(f, scanner.Finding) for f in findings)
