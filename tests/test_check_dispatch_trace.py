import json
import subprocess
from pathlib import Path

import pytest

import check_dispatch_trace as cdt

# ---- synthetic stream-json transcript builders ----------------------------


def _line(obj) -> str:
    return json.dumps(obj) + "\n"


def _assistant_text(text: str) -> str:
    return _line({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})


def _assistant_tool_use(name: str, input_: dict | None = None, tool_id: str = "toolu_1") -> str:
    block = {"type": "tool_use", "name": name, "id": tool_id, "input": input_ or {}}
    return _line({"type": "assistant", "message": {"content": [block]}})


def _system_line() -> str:
    return _line({"type": "system", "subtype": "init", "tools": ["Task", "Bash"]})


def _result_line() -> str:
    return _line({"type": "result", "is_error": False, "result": "done"})


TRANSCRIPT_ONE_AGENT_DISPATCH = (
    _system_line()
    + _assistant_text("Dispatching now.")
    + _assistant_tool_use("Agent", {"prompt": "review the target"})
    + _result_line()
)

TRANSCRIPT_NO_DISPATCH = (
    _system_line()
    + _assistant_text("Here is my inline review: looks fine.")
    + _result_line()
)

TRANSCRIPT_TWO_AGENT_DISPATCHES = (
    _system_line()
    + _assistant_tool_use("Agent", tool_id="toolu_1")
    + _assistant_tool_use("Agent", tool_id="toolu_2")
    + _result_line()
)

TRANSCRIPT_UNRELATED_TOOLS_ONLY = (
    _system_line()
    + _assistant_tool_use("Read", {"file_path": "SKILL.md"})
    + _assistant_tool_use("Bash", {"command": "ls -la"})
    + _result_line()
)

TRANSCRIPT_NESTED_CLAUDE_P_VIA_BASH = (
    _system_line()
    + _assistant_tool_use("Bash", {"command": "claude -p 'review this' --output-format stream-json"})
    + _result_line()
)

TRANSCRIPT_BLANK_LINES = "\n" + TRANSCRIPT_ONE_AGENT_DISPATCH + "\n\n"


# ---- iter_tool_use_blocks / count_dispatches -------------------------------


def test_iter_tool_use_blocks_finds_single_block(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_ONE_AGENT_DISPATCH, encoding="utf-8")
    blocks = list(cdt.iter_tool_use_blocks(p))
    assert len(blocks) == 1
    assert blocks[0]["name"] == "Agent"


def test_iter_tool_use_blocks_skips_non_tool_use_lines(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_NO_DISPATCH, encoding="utf-8")
    assert list(cdt.iter_tool_use_blocks(p)) == []


def test_iter_tool_use_blocks_tolerates_blank_lines(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_BLANK_LINES, encoding="utf-8")
    assert len(list(cdt.iter_tool_use_blocks(p))) == 1


def test_iter_tool_use_blocks_raises_on_malformed_json(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text('{"type": "system"}\nnot json at all\n', encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        list(cdt.iter_tool_use_blocks(p))


def test_iter_tool_use_blocks_raises_on_non_object_line(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text('[1, 2, 3]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="expected a JSON object"):
        list(cdt.iter_tool_use_blocks(p))


def test_iter_tool_use_blocks_skips_non_list_content(tmp_path: Path):
    # A message.content that is a bare string (not the content-block-array
    # shape) must be skipped, not crash iteration.
    p = tmp_path / "t.jsonl"
    p.write_text(_line({"type": "user", "message": {"content": "plain string content"}}), encoding="utf-8")
    assert list(cdt.iter_tool_use_blocks(p)) == []


def test_count_dispatches_matches_configured_name():
    blocks = [{"name": "Agent"}, {"name": "Read"}]
    assert cdt.count_dispatches(blocks, ["Agent"]) == 1


def test_count_dispatches_multiple_names_and_multiple_matches():
    blocks = [{"name": "Agent"}, {"name": "Task"}, {"name": "Read"}]
    assert cdt.count_dispatches(blocks, ["Agent", "Task"]) == 2


def test_count_dispatches_zero_when_no_match():
    blocks = [{"name": "Read"}, {"name": "Bash", "input": {"command": "ls"}}]
    assert cdt.count_dispatches(blocks, ["Agent"]) == 0


def test_count_dispatches_bash_pattern_counts_nested_claude_p(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_NESTED_CLAUDE_P_VIA_BASH, encoding="utf-8")
    blocks = list(cdt.iter_tool_use_blocks(p))
    import re
    pattern = re.compile(r"claude\s+(-p|--print)\b")
    assert cdt.count_dispatches(blocks, ["Agent"], pattern) == 1
    # Without the bash pattern, the same transcript counts zero -- this is
    # the exact miss this module's docstring (lesson 2) warns about.
    assert cdt.count_dispatches(blocks, ["Agent"], None) == 0


def test_count_dispatches_bash_pattern_ignores_non_matching_command():
    blocks = [{"name": "Bash", "input": {"command": "ls -la"}}]
    import re
    pattern = re.compile(r"claude\s+(-p|--print)\b")
    assert cdt.count_dispatches(blocks, ["Agent"], pattern) == 0


def test_count_dispatches_bash_pattern_tolerates_non_dict_input():
    # A Bash tool_use block whose `input` is present but not a dict (a
    # malformed/unexpected transcript shape) must not crash count_dispatches
    # -- it simply cannot match the bash pattern, not an AttributeError.
    import re
    pattern = re.compile(r"claude\s+(-p|--print)\b")
    blocks = [
        {"name": "Bash", "input": ["not", "a", "dict"]},
        {"name": "Bash", "input": "also not a dict"},
        {"name": "Bash", "input": 42},
        {"name": "Bash", "input": None},
    ]
    assert cdt.count_dispatches(blocks, ["Agent"], pattern) == 0


def test_count_dispatches_bash_pattern_does_not_double_count_agent():
    blocks = [{"name": "Agent"}]
    import re
    pattern = re.compile(r"claude\s+(-p|--print)\b")
    assert cdt.count_dispatches(blocks, ["Agent"], pattern) == 1


def test_check_transcript_end_to_end(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_TWO_AGENT_DISPATCHES, encoding="utf-8")
    assert cdt.check_transcript(p, ["Agent"]) == 2


def test_count_dispatches_custom_bash_tool_name():
    import re
    pattern = re.compile(r"claude\s+(-p|--print)\b")
    blocks = [{"name": "Shell", "input": {"command": "claude -p 'x'"}}]
    # Default bash_tool_name="Bash" does not match a "Shell"-named block.
    assert cdt.count_dispatches(blocks, ["Agent"], pattern) == 0
    assert cdt.count_dispatches(blocks, ["Agent"], pattern, bash_tool_name="Shell") == 1


# ---- CLI: check-transcript --------------------------------------------------


def test_cli_check_transcript_exit_0_when_confirmed(tmp_path: Path, capsys):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_ONE_AGENT_DISPATCH, encoding="utf-8")
    rc = cdt.main(["check-transcript", "--transcript", str(p), "--dispatch-tool-name", "Agent"])
    assert rc == 0
    assert "DISPATCH_COUNT=1" in capsys.readouterr().out


def test_cli_check_transcript_exit_1_when_not_confirmed(tmp_path: Path, capsys):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_NO_DISPATCH, encoding="utf-8")
    rc = cdt.main(["check-transcript", "--transcript", str(p), "--dispatch-tool-name", "Agent"])
    assert rc == 1
    assert "DISPATCH_COUNT=0" in capsys.readouterr().out


def test_cli_check_transcript_respects_min_dispatches(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_ONE_AGENT_DISPATCH, encoding="utf-8")
    rc = cdt.main([
        "check-transcript", "--transcript", str(p),
        "--dispatch-tool-name", "Agent", "--min-dispatches", "2",
    ])
    assert rc == 1


def test_cli_check_transcript_missing_file_exit_2(tmp_path: Path, capsys):
    missing = tmp_path / "does-not-exist.jsonl"
    rc = cdt.main(["check-transcript", "--transcript", str(missing), "--dispatch-tool-name", "Agent"])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_cli_check_transcript_malformed_file_exit_2(tmp_path: Path, capsys):
    p = tmp_path / "t.jsonl"
    p.write_text("not json\n", encoding="utf-8")
    rc = cdt.main(["check-transcript", "--transcript", str(p), "--dispatch-tool-name", "Agent"])
    assert rc == 2
    assert "error:" in capsys.readouterr().err


def test_cli_check_transcript_multiple_dispatch_tool_names(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_UNRELATED_TOOLS_ONLY, encoding="utf-8")
    rc = cdt.main([
        "check-transcript", "--transcript", str(p),
        "--dispatch-tool-name", "Agent", "--dispatch-tool-name", "Task",
    ])
    assert rc == 1  # neither Read nor Bash(ls) counts


def test_cli_check_transcript_bash_pattern_flag(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_NESTED_CLAUDE_P_VIA_BASH, encoding="utf-8")
    rc = cdt.main([
        "check-transcript", "--transcript", str(p),
        "--dispatch-tool-name", "Agent",
        "--dispatch-bash-pattern", r"claude\s+(-p|--print)\b",
    ])
    assert rc == 0


def test_cli_check_transcript_invalid_bash_pattern_exit_2(tmp_path: Path, capsys):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_NO_DISPATCH, encoding="utf-8")
    rc = cdt.main([
        "check-transcript", "--transcript", str(p),
        "--dispatch-tool-name", "Agent",
        "--dispatch-bash-pattern", "(unclosed",
    ])
    assert rc == 2
    assert "invalid --dispatch-bash-pattern" in capsys.readouterr().err


def test_cli_run_invalid_bash_pattern_exit_2(tmp_path: Path):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")
    rc = cdt.main([
        "run", "--prompt-file", str(prompt_file),
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent",
        "--dispatch-bash-pattern", "(unclosed",
    ])
    assert rc == 2


def test_cli_requires_dispatch_tool_name(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_NO_DISPATCH, encoding="utf-8")
    with pytest.raises(SystemExit):
        cdt.main(["check-transcript", "--transcript", str(p)])


# ---- build_isolated_home ----------------------------------------------------


def test_build_isolated_home_strips_live_state_dirs(tmp_path: Path, monkeypatch):
    real_home = tmp_path / "real-home"
    claude_dir = real_home / ".claude"
    (claude_dir / "tasks").mkdir(parents=True)
    (claude_dir / "tasks" / "leaked-task.json").write_text("{}", encoding="utf-8")
    (claude_dir / "skills").mkdir(parents=True)
    (claude_dir / "skills" / "keep.txt").write_text("kept", encoding="utf-8")
    (real_home / ".claude.json").write_text('{"real": true}', encoding="utf-8")
    monkeypatch.setenv("HOME", str(real_home))

    base = tmp_path / "workdir"
    base.mkdir()
    isolated_home = cdt.build_isolated_home(base)

    assert (isolated_home / ".claude" / "skills" / "keep.txt").read_text(encoding="utf-8") == "kept"
    assert not list((isolated_home / ".claude" / "tasks").iterdir())
    assert (isolated_home / ".claude.json").read_text(encoding="utf-8") == '{"real": true}'


def test_build_isolated_home_raises_without_real_claude_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "no-claude-here"))
    with pytest.raises(FileNotFoundError):
        cdt.build_isolated_home(tmp_path / "workdir")


def test_build_isolated_home_raises_when_home_unset(tmp_path: Path, monkeypatch):
    # Must fail loudly, never silently fall back to a guessed location (e.g.
    # /root) that could belong to a different identity and defeat isolation.
    monkeypatch.delenv("HOME", raising=False)
    with pytest.raises(FileNotFoundError, match="HOME is not set"):
        cdt.build_isolated_home(tmp_path / "workdir")


def test_build_isolated_home_does_not_strip_nested_same_named_dir(tmp_path: Path, monkeypatch):
    # Only a direct child of $HOME/.claude named "tasks" (etc.) is stripped
    # -- a same-named directory nested inside a vendored skill's own content
    # must survive untouched (the strip is a top-level-only exclusion, not a
    # recursive ignore_patterns-style match).
    real_home = tmp_path / "real-home"
    claude_dir = real_home / ".claude"
    (claude_dir / "tasks").mkdir(parents=True)
    nested_tasks = claude_dir / "skills" / "some-skill" / "tasks"
    nested_tasks.mkdir(parents=True)
    (nested_tasks / "fixture.yaml").write_text("id: x", encoding="utf-8")
    monkeypatch.setenv("HOME", str(real_home))

    isolated_home = cdt.build_isolated_home(tmp_path / "workdir")

    assert not list((isolated_home / ".claude" / "tasks").iterdir())
    assert (isolated_home / ".claude" / "skills" / "some-skill" / "tasks" / "fixture.yaml").read_text(
        encoding="utf-8") == "id: x"


# ---- run_live_dispatch (argv construction only, no real subprocess) --------


def test_run_live_dispatch_constructs_expected_argv(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        captured["argv"] = argv
        captured["cwd"] = cwd
        captured["env"] = env
        stdout.write('{"type": "result"}\n')
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "should-be-unset")

    isolated_cwd = tmp_path / "cwd"
    isolated_cwd.mkdir()
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()
    transcript_out = tmp_path / "out.jsonl"

    result = cdt.run_live_dispatch(
        "review this", transcript_out,
        isolated_cwd=isolated_cwd, isolated_home=isolated_home,
        allowed_tools="Agent",
        plugin_dir=tmp_path / "plugin",
    )

    assert result.returncode == 0
    argv = captured["argv"]
    assert argv[0] == "claude"
    assert "-p" in argv and "review this" in argv
    assert "--plugin-dir" in argv
    assert captured["cwd"] == str(isolated_cwd)
    assert captured["env"]["HOME"] == str(isolated_home)
    assert captured["env"]["PWD"] == str(isolated_cwd)
    assert "CLAUDE_CODE_SESSION_ID" not in captured["env"]
    assert transcript_out.read_text(encoding="utf-8") == '{"type": "result"}\n'


def test_run_live_dispatch_includes_add_dir(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        captured["argv"] = argv
        stdout.write("{}\n")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    isolated_cwd = tmp_path / "cwd"
    isolated_cwd.mkdir()
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()

    cdt.run_live_dispatch(
        "review this", tmp_path / "out.jsonl",
        isolated_cwd=isolated_cwd, isolated_home=isolated_home,
        allowed_tools="Agent", add_dir=tmp_path / "mounted-repo",
    )
    argv = captured["argv"]
    assert "--add-dir" in argv
    assert str(tmp_path / "mounted-repo") in argv


# ---- CLI: run (mocked subprocess, no live model call) ----------------------


def test_cli_run_end_to_end_mocked(tmp_path: Path, monkeypatch):
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch a subagent", encoding="utf-8")
    transcript_out = tmp_path / "out.jsonl"

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        stdout.write(TRANSCRIPT_ONE_AGENT_DISPATCH)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    rc = cdt.main([
        "run",
        "--prompt-file", str(prompt_file),
        "--transcript-out", str(transcript_out),
        "--dispatch-tool-name", "Agent",
    ])
    assert rc == 0
    assert transcript_out.read_text(encoding="utf-8") == TRANSCRIPT_ONE_AGENT_DISPATCH


def test_cli_run_reports_claude_failure(tmp_path: Path, monkeypatch):
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")
    transcript_out = tmp_path / "out.jsonl"

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="boom")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    rc = cdt.main([
        "run", "--prompt-file", str(prompt_file), "--transcript-out", str(transcript_out),
        "--dispatch-tool-name", "Agent",
    ])
    assert rc == 2


def test_cli_run_catches_missing_claude_binary(tmp_path: Path, monkeypatch):
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        raise FileNotFoundError("[Errno 2] No such file or directory: 'claude'")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    rc = cdt.main([
        "run", "--prompt-file", str(prompt_file),
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent",
    ])
    assert rc == 2


def test_cli_run_catches_timeout(tmp_path: Path, monkeypatch, capsys):
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    rc = cdt.main([
        "run", "--prompt-file", str(prompt_file),
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent", "--timeout", "5",
    ])
    assert rc == 2
    assert "did not finish within 5" in capsys.readouterr().err


def test_cli_run_resolves_relative_isolated_home(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        captured["env"] = env
        stdout.write(TRANSCRIPT_ONE_AGENT_DISPATCH)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    reused_home = tmp_path / "reused-home"
    reused_home.mkdir()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    rc = cdt.main([
        "run", "--prompt-file", "prompt.txt",
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent",
        "--isolated-home", "reused-home",  # relative
    ])
    assert rc == 0
    # The child process runs with a different cwd (the tempdir isolated_cwd),
    # so a relative --isolated-home must be resolved against *this* process's
    # cwd before being written into env["HOME"], not left relative.
    assert captured["env"]["HOME"] == str(reused_home.resolve())


def test_cli_run_auto_appends_bash_tool_when_dispatch_bash_pattern_given(tmp_path: Path, monkeypatch):
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))
    captured = {}

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        captured["argv"] = argv
        stdout.write(TRANSCRIPT_NO_DISPATCH)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")

    cdt.main([
        "run", "--prompt-file", str(prompt_file),
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent",
        "--dispatch-bash-pattern", r"claude\s+-p",
        "--allowed-tools", "Agent",
    ])
    allowed_tools_index = captured["argv"].index("--allowedTools") + 1
    assert captured["argv"][allowed_tools_index] == "Agent Bash"


def test_cli_run_does_not_duplicate_already_allowed_bash(tmp_path: Path, monkeypatch):
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))
    captured = {}

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        captured["argv"] = argv
        stdout.write(TRANSCRIPT_NO_DISPATCH)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")

    cdt.main([
        "run", "--prompt-file", str(prompt_file),
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent",
        "--dispatch-bash-pattern", r"claude\s+-p",
        "--allowed-tools", "Agent Bash",
    ])
    allowed_tools_index = captured["argv"].index("--allowedTools") + 1
    assert captured["argv"][allowed_tools_index] == "Agent Bash"


def test_cli_run_does_not_append_bash_without_dispatch_bash_pattern(tmp_path: Path, monkeypatch):
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))
    captured = {}

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        captured["argv"] = argv
        stdout.write(TRANSCRIPT_NO_DISPATCH)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")

    cdt.main([
        "run", "--prompt-file", str(prompt_file),
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent",
        "--allowed-tools", "Agent",
    ])
    allowed_tools_index = captured["argv"].index("--allowedTools") + 1
    assert captured["argv"][allowed_tools_index] == "Agent"


def test_cli_check_transcript_empty_bash_pattern_is_not_treated_as_absent(tmp_path: Path):
    # Truthiness (`if args.dispatch_bash_pattern`) would silently treat an
    # explicitly-passed empty string the same as "not given"; an empty
    # regex is a valid (if unusual) pattern that matches every command, so
    # --dispatch-bash-pattern "" must still compile and be used.
    p = tmp_path / "t.jsonl"
    p.write_text(TRANSCRIPT_NESTED_CLAUDE_P_VIA_BASH, encoding="utf-8")
    rc = cdt.main([
        "check-transcript", "--transcript", str(p),
        "--dispatch-tool-name", "Agent", "--dispatch-bash-pattern", "",
    ])
    assert rc == 0


def test_cli_check_transcript_custom_bash_tool_name(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    p.write_text(_line({
        "type": "assistant",
        "message": {"content": [
            {"type": "tool_use", "name": "Shell", "id": "t1",
             "input": {"command": "claude -p 'x'"}},
        ]},
    }), encoding="utf-8")
    rc = cdt.main([
        "check-transcript", "--transcript", str(p),
        "--dispatch-tool-name", "Agent",
        "--dispatch-bash-pattern", r"claude\s+-p",
        "--bash-tool-name", "Shell",
    ])
    assert rc == 0


def test_cli_run_missing_prompt_file(tmp_path: Path):
    rc = cdt.main([
        "run", "--prompt-file", str(tmp_path / "missing.txt"),
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent",
    ])
    assert rc == 2


def test_cli_run_reuses_provided_isolated_home(tmp_path: Path, monkeypatch):
    # --isolated-home given: build_isolated_home must not be called at all.
    def fail_if_called(base_dir):
        raise AssertionError("build_isolated_home should not be called when --isolated-home is given")

    monkeypatch.setattr(cdt, "build_isolated_home", fail_if_called)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")
    transcript_out = tmp_path / "out.jsonl"
    reused_home = tmp_path / "reused-home"
    reused_home.mkdir()

    captured = {}

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        captured["env"] = env
        stdout.write(TRANSCRIPT_ONE_AGENT_DISPATCH)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    rc = cdt.main([
        "run", "--prompt-file", str(prompt_file), "--transcript-out", str(transcript_out),
        "--dispatch-tool-name", "Agent", "--isolated-home", str(reused_home),
    ])
    assert rc == 0
    assert captured["env"]["HOME"] == str(reused_home)


def test_cli_run_no_real_claude_dir_and_no_isolated_home_exit_2(tmp_path: Path, monkeypatch):
    # HOME has no .claude directory and --isolated-home was not given, so
    # build_isolated_home's FileNotFoundError must surface as exit 2, not a
    # crash or a silently-unisolated live call.
    monkeypatch.setenv("HOME", str(tmp_path / "no-claude-here"))
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")

    rc = cdt.main([
        "run", "--prompt-file", str(prompt_file),
        "--transcript-out", str(tmp_path / "out.jsonl"),
        "--dispatch-tool-name", "Agent",
    ])
    assert rc == 2


def test_cli_run_malformed_captured_transcript_exit_2(tmp_path: Path, monkeypatch):
    real_home = tmp_path / "real-home"
    (real_home / ".claude").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(real_home))

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("dispatch", encoding="utf-8")
    transcript_out = tmp_path / "out.jsonl"

    def fake_run(argv, cwd, env, stdout, stderr, text, check, timeout=None):
        stdout.write("not json at all\n")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(cdt.subprocess, "run", fake_run)

    rc = cdt.main([
        "run", "--prompt-file", str(prompt_file), "--transcript-out", str(transcript_out),
        "--dispatch-tool-name", "Agent",
    ])
    assert rc == 2
