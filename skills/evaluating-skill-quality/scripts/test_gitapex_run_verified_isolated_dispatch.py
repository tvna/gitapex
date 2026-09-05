"""Tests for gitapex_run_verified_isolated_dispatch.py (issue #1809).

Covers the pure registry read/write/matching logic and the isolated-HOME/
target-snapshot construction with real filesystem fixtures, and the
subprocess-invoking paths (controls, real dispatch) with a monkeypatched
`subprocess.run` -- the same pattern
`tests/test_gitapex_check_dispatch_trace.py` already uses for its own
isolated-dispatch helpers. The live two-control behavior itself (does
`claude -p` actually behave as expected against a real CLI) is not
CI-mockable and is out of scope here, per the design doc's own Testing
section.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import gitapex_run_verified_isolated_dispatch as gvid
import pytest
import yaml

# ---- read_identifying_signals ----------------------------------------------


def test_read_identifying_signals_collects_env_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE", "cloud_default")

    def fake_run(
        argv: list[str], capture_output: bool, text: bool, check: bool, timeout: float | None
    ) -> subprocess.CompletedProcess[str]:
        assert argv == ["claude", "--version"]
        return subprocess.CompletedProcess(argv, 0, stdout="2.1.300 (Claude Code)\n", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    signals = gvid.read_identifying_signals()

    assert signals == {
        "CLAUDE_CODE_REMOTE": "true",
        "CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE": "cloud_default",
        "claude_version": "2.1.300 (Claude Code)",
    }


def test_read_identifying_signals_omits_unset_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE", raising=False)

    def fake_run(
        argv: list[str], capture_output: bool, text: bool, check: bool, timeout: float | None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="command not found")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    signals = gvid.read_identifying_signals()

    assert "CLAUDE_CODE_REMOTE" not in signals
    assert signals["claude_version"] == "command not found"


def test_read_identifying_signals_propagates_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(
        argv: list[str], capture_output: bool, text: bool, check: bool, timeout: float | None
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("no such file: claude")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    with pytest.raises(FileNotFoundError):
        gvid.read_identifying_signals()


# ---- load_registry / save_registry ------------------------------------------


def test_load_registry_returns_empty_list_when_file_missing(tmp_path: Path) -> None:
    assert gvid.load_registry(tmp_path / "missing.yaml") == []


def test_load_registry_returns_empty_list_for_malformed_content(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text("not-a-mapping\n", encoding="utf-8")
    assert gvid.load_registry(path) == []


def test_save_and_load_registry_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    entries: list[dict[str, Any]] = [
        {
            "identifying_signals": {"claude_version": "2.1.300"},
            "leak_vector": "claude_md_agents_md",
            "date": "2026-09-05",
        }
    ]

    gvid.save_registry(path, entries)
    loaded = gvid.load_registry(path)

    assert loaded == entries
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["entries"] == entries


def test_load_registry_drops_non_dict_entries(tmp_path: Path) -> None:
    # A plausible hand-authored YAML slip (this file is also meant to be
    # human-edited during review/promotion, per the design doc's own
    # Migration section) -- must be skipped, not crash a later caller's own
    # entry.get(...) with AttributeError (issue #1809, Step 8 follow-up).
    path = tmp_path / "registry.yaml"
    path.write_text("entries:\n  - not-a-mapping\n  - identifying_signals: {}\n", encoding="utf-8")

    assert gvid.load_registry(path) == [{"identifying_signals": {}}]


def test_append_registry_entry_preserves_existing_content(tmp_path: Path) -> None:
    # Regression test for issue #1809's Step 8 finding: save_registry's own
    # whole-file round trip through yaml.safe_dump strips the hand-authored
    # header comment and reformats every existing entry, turning a
    # single-entry addition into a full-file diff. append_registry_entry
    # must never touch a single byte that came before the new entry.
    path = tmp_path / "registry.yaml"
    original = '# A hand-authored header comment.\n\nentries:\n  - date: "2026-01-01"\n'
    path.write_text(original, encoding="utf-8")

    gvid.append_registry_entry(path, {"date": "2026-09-05", "leak_vector": "claude_md_agents_md"})

    new_content = path.read_text(encoding="utf-8")
    assert new_content.startswith(original)
    entries = gvid.load_registry(path)
    assert [entry["date"] for entry in entries] == ["2026-01-01", "2026-09-05"]


def test_append_registry_entry_creates_file_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"

    gvid.append_registry_entry(path, {"date": "2026-09-05"})

    assert gvid.load_registry(path) == [{"date": "2026-09-05"}]


def test_find_reviewed_match_succeeds_against_real_shipped_registry() -> None:
    # Regression test for issue #1809's Step 8 finding: _CANONICAL_MECHANISM
    # previously matched none of the real, shipped registry's own migrated
    # entries, so find_reviewed_match always returned None against real
    # data even though a byte-for-byte-equivalent reviewed/isolated entry
    # existed -- every prior test here constructed its own synthetic entry
    # instead of loading the actual file, so this gap went uncaught. Loads
    # the real metadata/isolation-registry.yaml this repository ships.
    real_registry_path = Path(__file__).resolve().parent.parent / "metadata" / "isolation-registry.yaml"
    entries = gvid.load_registry(real_registry_path)
    assert entries, "the real shipped registry must not be empty"

    signals = {
        "CLAUDE_CODE_REMOTE": "true",
        "CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE": "cloud_default",
        "claude_version": "2.1.226 (Claude Code)",
    }

    match = gvid.find_reviewed_match(entries, signals)

    assert match is not None
    assert match["mechanism"] == gvid._CANONICAL_MECHANISM
    assert match["trust_class"] == "reviewed"
    assert match["result"] == "isolated"


# ---- find_reviewed_match -----------------------------------------------------


_SIGNALS = {"CLAUDE_CODE_REMOTE": "true", "claude_version": "2.1.300 (Claude Code)"}


def test_find_reviewed_match_returns_matching_entry() -> None:
    entries: list[dict[str, Any]] = [
        {
            "identifying_signals": _SIGNALS,
            "mechanism": gvid._CANONICAL_MECHANISM,
            "leak_vector": "claude_md_agents_md",
            "result": "isolated",
            "trust_class": "reviewed",
            "date": "x",
        }
    ]
    assert gvid.find_reviewed_match(entries, _SIGNALS) == entries[0]


def test_find_reviewed_match_ignores_same_signals_different_mechanism() -> None:
    # Regression for an independent-review finding (issue #1809): several
    # migrated registry entries share byte-identical identifying_signals
    # with different mechanisms and results (a contaminated Agent-tool
    # dispatch and an isolated --plugin-dir dispatch, for instance, both
    # recorded at the same platform signature). Matching on signals alone
    # would let this function return an entry recorded for a mechanism this
    # script never actually runs.
    entries: list[dict[str, Any]] = [
        {
            "identifying_signals": _SIGNALS,
            "mechanism": "claude -p --plugin-dir (a different recipe this script does not implement)",
            "leak_vector": "claude_md_agents_md",
            "result": "isolated",
            "trust_class": "reviewed",
        }
    ]
    assert gvid.find_reviewed_match(entries, _SIGNALS, gvid._CANONICAL_MECHANISM) is None


def test_find_reviewed_match_picks_correct_entry_among_same_signals_multiple_mechanisms() -> None:
    contaminated_entry: dict[str, Any] = {
        "identifying_signals": _SIGNALS,
        "mechanism": "Agent tool dispatch (contaminated)",
        "leak_vector": "claude_md_agents_md",
        "result": "contaminated",
        "trust_class": "reviewed",
    }
    other_isolated_entry: dict[str, Any] = {
        "identifying_signals": _SIGNALS,
        "mechanism": "claude -p --plugin-dir (a different recipe this script does not implement)",
        "leak_vector": "claude_md_agents_md",
        "result": "isolated",
        "trust_class": "reviewed",
    }
    canonical_entry: dict[str, Any] = {
        "identifying_signals": _SIGNALS,
        "mechanism": gvid._CANONICAL_MECHANISM,
        "leak_vector": "claude_md_agents_md",
        "result": "isolated",
        "trust_class": "reviewed",
    }
    entries = [contaminated_entry, other_isolated_entry, canonical_entry]
    assert gvid.find_reviewed_match(entries, _SIGNALS, gvid._CANONICAL_MECHANISM) == canonical_entry


def test_find_reviewed_match_ignores_same_run_unreviewed_entry() -> None:
    entries: list[dict[str, Any]] = [
        {
            "identifying_signals": _SIGNALS,
            "leak_vector": "claude_md_agents_md",
            "trust_class": "same-run-unreviewed",
        }
    ]
    assert gvid.find_reviewed_match(entries, _SIGNALS) is None


def test_find_reviewed_match_ignores_signal_mismatch() -> None:
    entries: list[dict[str, Any]] = [
        {
            "identifying_signals": {"claude_version": "2.1.999 (Claude Code)"},
            "leak_vector": "claude_md_agents_md",
            "trust_class": "reviewed",
        }
    ]
    assert gvid.find_reviewed_match(entries, _SIGNALS) is None


def test_find_reviewed_match_ignores_wrong_leak_vector() -> None:
    entries: list[dict[str, Any]] = [
        {
            "identifying_signals": _SIGNALS,
            "mechanism": gvid._CANONICAL_MECHANISM,
            "leak_vector": "home_task_list",
            "result": "isolated",
            "trust_class": "reviewed",
        }
    ]
    assert gvid.find_reviewed_match(entries, _SIGNALS, leak_vector="claude_md_agents_md") is None


def test_find_reviewed_match_ignores_contaminated_result() -> None:
    # A registry entry can be "reviewed" and still document a contaminated
    # mechanism (a negative finding kept on record) -- matching on
    # leak_vector alone would let a caller "reuse" that entry's own signals
    # as if they verified isolation, which is exactly backwards.
    entries: list[dict[str, Any]] = [
        {
            "identifying_signals": _SIGNALS,
            "mechanism": gvid._CANONICAL_MECHANISM,
            "leak_vector": "claude_md_agents_md",
            "result": "contaminated",
            "trust_class": "reviewed",
        }
    ]
    assert gvid.find_reviewed_match(entries, _SIGNALS) is None


# ---- build_isolated_home (adapted from test_gitapex_check_dispatch_trace.py) -


def test_build_isolated_home_strips_live_state_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_home = tmp_path / "real-home"
    (real_home / ".claude" / "tasks").mkdir(parents=True)
    (real_home / ".claude" / "tasks" / "leaked.json").write_text("{}", encoding="utf-8")
    (real_home / ".claude" / "skills").mkdir(parents=True)
    (real_home / ".claude" / "skills" / "keep.txt").write_text("kept", encoding="utf-8")
    (real_home / ".claude.json").write_text('{"real": true}', encoding="utf-8")
    monkeypatch.setenv("HOME", str(real_home))

    isolated_home = gvid.build_isolated_home(tmp_path / "workdir")

    assert (isolated_home / ".claude" / "skills" / "keep.txt").read_text(encoding="utf-8") == "kept"
    assert not list((isolated_home / ".claude" / "tasks").iterdir())
    assert (isolated_home / ".claude.json").read_text(encoding="utf-8") == '{"real": true}'


def test_build_isolated_home_raises_when_home_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOME", raising=False)
    with pytest.raises(FileNotFoundError, match="HOME is not set"):
        gvid.build_isolated_home(tmp_path / "workdir")


def test_build_isolated_home_raises_without_real_claude_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "no-claude-here"))
    with pytest.raises(FileNotFoundError):
        gvid.build_isolated_home(tmp_path / "workdir")


def test_build_isolated_home_does_not_strip_nested_same_named_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ported from tests/test_gitapex_check_dispatch_trace.py's own identically
    # named test -- an independent adversarial review found this copy's own
    # test file had silently dropped this regression guard while adapting
    # the rest of that file's build_isolated_home tests (issue #1809, Step 8
    # follow-up). Only a direct child of $HOME/.claude named "tasks" (etc.)
    # is stripped -- a same-named directory nested inside a vendored skill's
    # own content must survive untouched (the strip is a top-level-only
    # exclusion, not a recursive ignore_patterns-style match).
    real_home = tmp_path / "real-home"
    claude_dir = real_home / ".claude"
    (claude_dir / "tasks").mkdir(parents=True)
    nested_tasks = claude_dir / "skills" / "some-skill" / "tasks"
    nested_tasks.mkdir(parents=True)
    (nested_tasks / "fixture.yaml").write_text("id: x", encoding="utf-8")
    monkeypatch.setenv("HOME", str(real_home))

    isolated_home = gvid.build_isolated_home(tmp_path / "workdir")

    assert not list((isolated_home / ".claude" / "tasks").iterdir())
    assert (isolated_home / ".claude" / "skills" / "some-skill" / "tasks" / "fixture.yaml").read_text(
        encoding="utf-8"
    ) == "id: x"


def test_build_isolated_home_hardens_directory_permissions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))

    isolated_home = gvid.build_isolated_home(tmp_path / "workdir")

    assert (isolated_home.stat().st_mode & 0o777) == 0o700


def test_build_isolated_home_matches_sibling_copy_in_dispatch_trace() -> None:
    """Drift-detection guard for the deliberate copy-paste this module's own
    docstring discloses (evals/scripts/gitapex_check_dispatch_trace.py's
    build_isolated_home cannot be imported here across the never-deployed-
    with-skills/ boundary -- see that docstring). An independent adversarial
    review found this duplication has no guard against silent drift between
    the two copies (issue #1809, Step 8 follow-up); this test compares both
    functions' own parsed AST structure (after dropping each one's own
    leading docstring, whose prose deliberately differs between the two
    files) rather than raw source text, so formatting/comment/docstring
    differences neither file promises to keep identical never produce a
    false failure, while an actual logic change to only one copy does."""
    import ast
    import inspect
    import sys
    import textwrap

    scripts_dir = Path(__file__).resolve().parent.parent.parent.parent / "evals" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import gitapex_check_dispatch_trace as cdt
    finally:
        sys.path.remove(str(scripts_dir))

    def _body_structure(func: object) -> str:
        source = textwrap.dedent(inspect.getsource(func))  # type: ignore[arg-type]
        module = ast.parse(source)
        function_def = module.body[0]
        assert isinstance(function_def, ast.FunctionDef)
        body = function_def.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]  # drop the leading docstring -- prose differs by design
        return "\n".join(ast.dump(node, annotate_fields=False) for node in body)

    assert _body_structure(gvid.build_isolated_home) == _body_structure(cdt.build_isolated_home), (
        "gitapex_run_verified_isolated_dispatch.build_isolated_home has drifted from "
        "evals/scripts/gitapex_check_dispatch_trace.build_isolated_home -- port the change to both "
        "copies (issue #1809, Step 8 follow-up)"
    )


# ---- run_two_controls (mocked subprocess) -----------------------------------


def test_run_two_controls_both_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "real-home"))
    (tmp_path / "real-home" / ".claude").mkdir(parents=True)

    def fake_run(
        argv: list[str],
        cwd: str,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
        check: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]:
        if "CLAUDE.md" in "\n".join(str(p) for p in Path(cwd).iterdir()):
            return subprocess.CompletedProcess(argv, 0, stdout=gvid._SENTINEL_MARKER, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="none loaded", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    positive_ok, negative_ok, transcript = gvid.run_two_controls(
        tmp_path / "work", gvid.build_isolated_home(tmp_path / "work"), "claude", 30.0
    )

    assert positive_ok is True
    assert negative_ok is True
    assert gvid._SENTINEL_MARKER in transcript


def test_run_two_controls_negative_fails_when_marker_leaks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "real-home"))
    (tmp_path / "real-home" / ".claude").mkdir(parents=True)

    def fake_run(
        argv: list[str],
        cwd: str,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
        check: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]:
        # Both controls "leak" the marker -- simulates a contaminated mechanism.
        return subprocess.CompletedProcess(argv, 0, stdout=gvid._SENTINEL_MARKER, stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    positive_ok, negative_ok, _ = gvid.run_two_controls(
        tmp_path / "work", gvid.build_isolated_home(tmp_path / "work"), "claude", 30.0
    )

    assert positive_ok is True
    assert negative_ok is False


def test_run_two_controls_positive_fails_when_mechanism_is_blind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "real-home"))
    (tmp_path / "real-home" / ".claude").mkdir(parents=True)

    def fake_run(
        argv: list[str],
        cwd: str,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
        check: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout="none loaded", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    positive_ok, negative_ok, _ = gvid.run_two_controls(
        tmp_path / "work", gvid.build_isolated_home(tmp_path / "work"), "claude", 30.0
    )

    assert positive_ok is False
    assert negative_ok is True


# ---- print_no_verified_mechanism_block --------------------------------------


def test_print_no_verified_mechanism_block_shape(capsys: pytest.CaptureFixture[str]) -> None:
    gvid.print_no_verified_mechanism_block("a control failed", "no entry matches")

    output = capsys.readouterr().err
    assert "No verified mechanism available: a control failed" in output
    assert "no entry matches" in output
    assert "# Option A: fix this environment" in output
    assert "# Option B: hand off to a verified environment" in output


# ---- build_target_snapshot ---------------------------------------------------


def test_build_target_snapshot_copies_directory_read_only(tmp_path: Path) -> None:
    target = tmp_path / "target-skill"
    target.mkdir()
    (target / "SKILL.md").write_text("content", encoding="utf-8")

    snapshot = gvid.build_target_snapshot(target, tmp_path / "work")

    copied = snapshot / "SKILL.md"
    assert copied.read_text(encoding="utf-8") == "content"
    assert not (copied.stat().st_mode & 0o222)


def test_build_target_snapshot_copies_single_file(tmp_path: Path) -> None:
    target = tmp_path / "SKILL.md"
    target.write_text("content", encoding="utf-8")

    snapshot = gvid.build_target_snapshot(target, tmp_path / "work")

    assert (snapshot / "SKILL.md").read_text(encoding="utf-8") == "content"


# ---- run_real_dispatch (argv construction only) ------------------------------


def test_run_real_dispatch_includes_allowed_tools_when_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(
        argv: list[str],
        cwd: str,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
        check: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["env"] = env
        return subprocess.CompletedProcess(argv, 0, stdout="report", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "should-be-unset")

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    home = tmp_path / "home"

    result = gvid.run_real_dispatch("review this", cwd, home, "claude", "Read,Glob", 60.0)

    assert result.stdout == "report"
    assert captured["argv"] == ["claude", "-p", "review this", "--allowedTools", "Read,Glob"]
    assert "CLAUDE_CODE_SESSION_ID" not in captured["env"]
    assert captured["env"]["HOME"] == str(home)


def test_run_real_dispatch_omits_allowed_tools_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(
        argv: list[str],
        cwd: str,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
        check: bool,
        timeout: float | None,
    ) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    gvid.run_real_dispatch("review this", tmp_path, tmp_path / "home", "claude", None, 60.0)

    assert captured["argv"] == ["claude", "-p", "review this"]


# ---- regenerate_markdown_summary --------------------------------------------


def test_regenerate_markdown_summary_renders_table(tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    gvid.save_registry(
        registry,
        [
            {
                "date": "2026-09-05",
                "leak_vector": "claude_md_agents_md",
                "mechanism": "claude -p | isolated cwd",
                "result": "isolated",
                "trust_class": "reviewed",
            }
        ],
    )
    markdown_path = tmp_path / "history.md"

    gvid.regenerate_markdown_summary(registry, markdown_path)

    content = markdown_path.read_text(encoding="utf-8")
    assert "claude -p \\| isolated cwd" in content
    assert "2026-09-05" in content
    assert "do not hand-edit" in content


# ---- main() CLI, end to end, mocked subprocess ------------------------------


def _stub_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "real-home"))
    (tmp_path / "real-home" / ".claude").mkdir(parents=True)


def test_main_reuses_reviewed_entry_and_launches_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_home(tmp_path, monkeypatch)

    def fake_run(
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="2.1.300 (Claude Code)\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="review report", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    monkeypatch.delenv("CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE", raising=False)

    registry = tmp_path / "registry.yaml"
    gvid.save_registry(
        registry,
        [
            {
                "identifying_signals": {"CLAUDE_CODE_REMOTE": "true", "claude_version": "2.1.300 (Claude Code)"},
                "leak_vector": "claude_md_agents_md",
                "result": "isolated",
                "trust_class": "reviewed",
                "date": "2026-08-01",
                "mechanism": gvid._CANONICAL_MECHANISM,
            }
        ],
    )
    target = tmp_path / "target"
    target.mkdir()
    (target / "SKILL.md").write_text("x", encoding="utf-8")
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("review this skill", encoding="utf-8")

    exit_code = gvid.main(
        [
            "--target",
            str(target),
            "--prompt-file",
            str(prompt_file),
            "--registry",
            str(registry),
            "--history-markdown",
            str(tmp_path / "history.md"),
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert "review report" in output.out
    assert "verifiedLeakVectors: ['claude_md_agents_md']" in output.out
    assert "Reusing Reviewed registry entry" in output.err


def test_main_establishes_new_entry_when_no_match_controls_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_home(tmp_path, monkeypatch)

    def fake_run(
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="2.1.301 (Claude Code)\n", stderr="")
        if cwd is not None and (Path(cwd) / "CLAUDE.md").is_file():
            return subprocess.CompletedProcess(argv, 0, stdout=gvid._SENTINEL_MARKER, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="none loaded", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)

    registry = tmp_path / "registry.yaml"
    history = tmp_path / "history.md"

    exit_code = gvid.main(["--controls-only", "--registry", str(registry), "--history-markdown", str(history)])

    assert exit_code == 0
    entries = gvid.load_registry(registry)
    assert len(entries) == 1
    assert entries[0]["trust_class"] == "same-run-unreviewed"
    assert entries[0]["leak_vector"] == "claude_md_agents_md"
    assert history.is_file()


def test_main_reports_no_verified_mechanism_on_control_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_home(tmp_path, monkeypatch)

    def fake_run(
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="2.1.302 (Claude Code)\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="none loaded", stderr="")  # positive control fails

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    registry = tmp_path / "registry.yaml"
    exit_code = gvid.main(["--controls-only", "--registry", str(registry)])

    assert exit_code == 1
    output = capsys.readouterr()
    assert "No verified mechanism available" in output.err
    assert gvid.load_registry(registry) == []


def test_main_requires_target_and_prompt_file_unless_controls_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert gvid.main(["--registry", str(tmp_path / "registry.yaml")]) == 1


def test_main_rejects_missing_prompt_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target"
    target.mkdir()
    assert (
        gvid.main(
            [
                "--target",
                str(target),
                "--prompt-file",
                str(tmp_path / "missing-prompt.txt"),
                "--registry",
                str(tmp_path / "registry.yaml"),
            ]
        )
        == 1
    )


def test_main_reports_missing_claude_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(
        argv: list[str],
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("no such file: claude")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    exit_code = gvid.main(["--controls-only", "--registry", str(tmp_path / "registry.yaml")])

    assert exit_code == 1


def test_main_reports_control_run_execution_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_home(tmp_path, monkeypatch)
    call_count = {"n": 0}

    def fake_run(
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="2.1.303 (Claude Code)\n", stderr="")
        call_count["n"] += 1
        raise subprocess.TimeoutExpired(cmd=argv, timeout=30)

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    exit_code = gvid.main(["--controls-only", "--registry", str(tmp_path / "registry.yaml")])

    assert exit_code == 1
    assert "No verified mechanism available" in capsys.readouterr().err
    assert call_count["n"] >= 1


def test_main_reports_real_dispatch_execution_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_home(tmp_path, monkeypatch)

    def fake_run(
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="2.1.304 (Claude Code)\n", stderr="")
        if cwd is not None and (Path(cwd) / "CLAUDE.md").is_file():
            return subprocess.CompletedProcess(argv, 0, stdout=gvid._SENTINEL_MARKER, stderr="")
        if cwd is not None and "target-snapshot" in str(cwd):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=60)
        return subprocess.CompletedProcess(argv, 0, stdout="none loaded", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    target = tmp_path / "target"
    target.mkdir()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("review", encoding="utf-8")

    exit_code = gvid.main(
        [
            "--target",
            str(target),
            "--prompt-file",
            str(prompt_file),
            "--registry",
            str(tmp_path / "registry.yaml"),
            "--history-markdown",
            str(tmp_path / "history.md"),
        ]
    )

    assert exit_code == 1
    assert "the real dispatch failed to execute" in capsys.readouterr().err


def test_main_prints_dispatch_stderr_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_home(tmp_path, monkeypatch)

    def fake_run(
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="2.1.305 (Claude Code)\n", stderr="")
        if cwd is not None and (Path(cwd) / "CLAUDE.md").is_file():
            return subprocess.CompletedProcess(argv, 0, stdout=gvid._SENTINEL_MARKER, stderr="")
        if cwd is not None and "target-snapshot" in str(cwd):
            return subprocess.CompletedProcess(argv, 0, stdout="report", stderr="a warning from the dispatch")
        return subprocess.CompletedProcess(argv, 0, stdout="none loaded", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    target = tmp_path / "target"
    target.mkdir()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("review", encoding="utf-8")

    exit_code = gvid.main(
        [
            "--target",
            str(target),
            "--prompt-file",
            str(prompt_file),
            "--registry",
            str(tmp_path / "registry.yaml"),
            "--history-markdown",
            str(tmp_path / "history.md"),
        ]
    )

    assert exit_code == 0
    assert "a warning from the dispatch" in capsys.readouterr().err


def test_main_reports_isolated_home_build_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("HOME", raising=False)

    def fake_run(
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout="2.1.306 (Claude Code)\n", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    exit_code = gvid.main(["--controls-only", "--registry", str(tmp_path / "registry.yaml")])

    assert exit_code == 1
    assert "No verified mechanism available" in capsys.readouterr().err


def test_load_registry_returns_empty_list_for_non_utf8_content(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_bytes(b"\xff\xfe not valid utf-8")
    assert gvid.load_registry(path) == []


def test_main_reports_unreadable_prompt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stub_home(tmp_path, monkeypatch)

    def fake_run(
        argv: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if argv[:2] == ["claude", "--version"]:
            return subprocess.CompletedProcess(argv, 0, stdout="2.1.307 (Claude Code)\n", stderr="")
        if cwd is not None and (Path(cwd) / "CLAUDE.md").is_file():
            return subprocess.CompletedProcess(argv, 0, stdout=gvid._SENTINEL_MARKER, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="none loaded", stderr="")

    monkeypatch.setattr(gvid.subprocess, "run", fake_run)

    target = tmp_path / "target"
    target.mkdir()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_bytes(b"\xff\xfe not valid utf-8")

    exit_code = gvid.main(
        [
            "--target",
            str(target),
            "--prompt-file",
            str(prompt_file),
            "--registry",
            str(tmp_path / "registry.yaml"),
            "--history-markdown",
            str(tmp_path / "history.md"),
        ]
    )

    assert exit_code == 1
    assert "could not read --prompt-file" in capsys.readouterr().err
