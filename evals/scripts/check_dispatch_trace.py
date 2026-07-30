"""Check whether a captured live-dispatch transcript actually contains a
fresh subagent dispatch, rather than trusting the model's final output text
alone (issue #584).

`evaluating-skill-quality` and `battle-testing-a-skill` both mandate that
their core judgment steps run inside "one fresh subagent dispatch," not the
invoking context. Both skills' own `evals/<skill>/eval-status.md` disclosed
the same gap: the committed eval tasks assert only on final-output substrings
(`score_contract.py`), so they cannot confirm a dispatch actually happened.
This script closes that gap for a single captured run: it inspects a
`claude -p --output-format stream-json` transcript's own tool-call trace for
a dispatch-shaped tool invocation, rather than reading the final text.

Two independently-confirmed lessons from building this (recorded in
`evals/evaluating-skill-quality/eval-status.md` and
`evals/battle-testing-a-skill/eval-status.md`'s issue #584 entries) shape
this module's design:

1. **Never hardcode the dispatch tool's name.** A live probe against this
   exact platform found the tool exposed for subagent dispatch is reported
   as `"Task"` in the session's own `system`-init metadata, but an actual
   dispatch's `tool_use` block is emitted with `name: "Agent"` -- the
   system-init field and the model's own self-report both disagreed with
   the real, observed invocation. Only a captured transcript's actual
   `tool_use.name` is ground truth, and that name is platform-specific and
   can drift between harness versions. `check_transcript`'s
   `dispatch_tool_names` is therefore always caller-supplied, never a
   built-in default.
2. **A subagent dispatch is not always a same-transcript `tool_use` block.**
   When these two skills' real, unmodified `SKILL.md` content is loaded
   (via `--plugin-dir`) and its own Procedure is followed literally, the
   skill reads its own Isolation-verification registry
   (`skills/evaluating-skill-quality/references/adversarial-self-audit.md`)
   and -- correctly, per that registry -- shells out to a *nested*
   `claude -p` subprocess via the `Bash` tool instead of using the `Agent`
   tool, because the registry documents the `Agent` tool as contaminated on
   this platform. That nested invocation is still a real, isolated fresh
   dispatch; a checker that only matched `tool_use` names against a fixed
   dispatch-tool set would silently miss it. `dispatch_bash_pattern` lets a
   caller opt into recognizing this second, equally valid dispatch shape.

Standard library only, matching this repository's other `evals/scripts/*.py`
tooling.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Directories inside $HOME/.claude that carry live session/task state rather
# than durable configuration -- stripped from an isolated $HOME copy per the
# verified recipe in adversarial-self-audit.md's "Isolation verification"
# section (second leak vector), so a dispatched subprocess cannot see this
# calling session's own live task list or conversation history.
_HOME_COPY_STRIP_DIRS = ("tasks", "projects", "sessions", "shell-snapshots")


def iter_tool_use_blocks(transcript_path: Path):
    """Yield every ``tool_use`` content block from a
    ``claude -p --output-format stream-json`` transcript file, in file order.

    Each line is one JSON object; most (``system``, ``result``,
    ``rate_limit_event``, ``active_goal``, and plain-text ``user``/
    ``assistant`` turns) carry no ``tool_use`` block and are skipped. Blank
    lines are skipped. Raises ``ValueError`` on a line that is not valid
    JSON, or on a JSON value that is not a mapping -- a malformed transcript
    should fail loudly (exit 2 at the CLI layer), not be silently read as
    "zero dispatches found."
    """
    with transcript_path.open(encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {lineno}: not valid JSON: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"line {lineno}: expected a JSON object, got {type(obj).__name__}")
            message = obj.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    yield block


def count_dispatches(
    tool_use_blocks,
    dispatch_tool_names,
    dispatch_bash_pattern: re.Pattern | None = None,
) -> int:
    """Count dispatch-shaped ``tool_use`` blocks.

    A block counts if its ``name`` is in ``dispatch_tool_names`` (a same-
    transcript dispatch-tool invocation), OR -- when ``dispatch_bash_pattern``
    is given -- its ``name`` is ``"Bash"`` and its ``input.command`` matches
    that pattern (a nested ``claude -p`` subprocess dispatch; see this
    module's docstring, lesson 2). The two are independent checks: a
    fixture that only cares about the first passes ``dispatch_bash_pattern
    =None`` and gets exactly the same-transcript-tool_use behavior.
    """
    names = set(dispatch_tool_names)
    count = 0
    for block in tool_use_blocks:
        name = block.get("name")
        if name in names:
            count += 1
            continue
        if dispatch_bash_pattern is not None and name == "Bash":
            block_input = block.get("input")
            command = block_input.get("command") if isinstance(block_input, dict) else None
            if isinstance(command, str) and dispatch_bash_pattern.search(command):
                count += 1
    return count


def check_transcript(
    transcript_path: Path,
    dispatch_tool_names,
    dispatch_bash_pattern: re.Pattern | None = None,
) -> int:
    """Return the dispatch count for ``transcript_path``. Propagates
    ``ValueError``/``OSError`` from ``iter_tool_use_blocks`` unchanged --
    the CLI layer is what turns those into an exit-2 usage error."""
    blocks = list(iter_tool_use_blocks(transcript_path))
    return count_dispatches(blocks, dispatch_tool_names, dispatch_bash_pattern)


def build_isolated_home(base_dir: Path) -> Path:
    """Copy the real ``$HOME/.claude`` tree and ``$HOME/.claude.json`` into a
    fresh directory under ``base_dir``, stripping only the live-state
    subdirectories a dispatched subprocess must not see. Mirrors the
    verified recipe in ``adversarial-self-audit.md``'s Isolation verification
    section byte-for-byte (settings/hooks/skills untouched). Returns the new
    ``$HOME`` path. Raises ``FileNotFoundError`` if the real ``$HOME/.claude``
    does not exist -- there is nothing to isolate a copy of.
    """
    real_home = Path(os.environ.get("HOME", "/root"))
    real_claude_dir = real_home / ".claude"
    if not real_claude_dir.is_dir():
        raise FileNotFoundError(f"no {real_claude_dir} to build an isolated copy from")
    isolated_home = base_dir / "isolated-home"
    isolated_home.mkdir(parents=True, exist_ok=True)
    shutil.copytree(real_claude_dir, isolated_home / ".claude")
    real_claude_json = real_home / ".claude.json"
    if real_claude_json.is_file():
        shutil.copy2(real_claude_json, isolated_home / ".claude.json")
    for name in _HOME_COPY_STRIP_DIRS:
        target = isolated_home / ".claude" / name
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)
    return isolated_home


def run_live_dispatch(
    prompt: str,
    transcript_out: Path,
    *,
    isolated_cwd: Path,
    isolated_home: Path,
    allowed_tools: str,
    plugin_dir: Path | None = None,
    add_dir: Path | None = None,
    permission_mode: str = "acceptEdits",
    claude_bin: str = "claude",
) -> subprocess.CompletedProcess:
    """Run one live, isolated ``claude -p`` dispatch and capture its
    ``stream-json`` transcript to ``transcript_out``. Callers are responsible
    for confirming ``isolated_cwd``'s full ancestry carries no
    ``CLAUDE.md``/``AGENTS.md`` and for building ``isolated_home`` via
    ``build_isolated_home`` (or an equivalent) first -- this function does
    not verify isolation itself, only executes the already-isolated call, so
    a live proof run must still record the isolation check per
    ``adversarial-self-audit.md``'s Verification procedure.
    """
    argv = [
        claude_bin,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--allowedTools",
        allowed_tools,
        "--permission-mode",
        permission_mode,
    ]
    if plugin_dir is not None:
        argv += ["--plugin-dir", str(plugin_dir)]
    if add_dir is not None:
        argv += ["--add-dir", str(add_dir)]
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env["HOME"] = str(isolated_home)
    with transcript_out.open("w", encoding="utf-8") as out:
        result = subprocess.run(
            argv, cwd=str(isolated_cwd), env=env, stdout=out,
            stderr=subprocess.PIPE, text=True, check=False,
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether a claude -p transcript contains a fresh subagent dispatch."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check_p = sub.add_parser(
        "check-transcript",
        help="Offline: count dispatch-shaped tool_use blocks in a captured transcript.",
    )
    check_p.add_argument("--transcript", required=True, help="Path to a stream-json transcript file.")
    check_p.add_argument(
        "--dispatch-tool-name", action="append", required=True, dest="dispatch_tool_names",
        help="A tool_use name that counts as a dispatch (repeatable). Never defaulted -- "
             "see this module's docstring for why the name must be caller-verified.",
    )
    check_p.add_argument(
        "--dispatch-bash-pattern", default=None,
        help="Optional regex; a Bash tool_use whose input.command matches also counts as a "
             "dispatch (a nested `claude -p` subprocess dispatch, see docstring lesson 2).",
    )
    check_p.add_argument("--min-dispatches", type=int, default=1)

    run_p = sub.add_parser(
        "run", help="Live: run one isolated claude -p dispatch and check its transcript."
    )
    run_p.add_argument("--prompt-file", required=True)
    run_p.add_argument("--transcript-out", required=True)
    run_p.add_argument("--dispatch-tool-name", action="append", required=True, dest="dispatch_tool_names")
    run_p.add_argument("--dispatch-bash-pattern", default=None)
    run_p.add_argument("--min-dispatches", type=int, default=1)
    run_p.add_argument("--allowed-tools", default="Agent")
    run_p.add_argument("--permission-mode", default="acceptEdits")
    run_p.add_argument("--plugin-dir", default=None)
    run_p.add_argument("--add-dir", default=None)
    run_p.add_argument("--isolated-home", default=None, help="Reuse an existing isolated $HOME; else build a fresh one.")
    run_p.add_argument("--claude-bin", default="claude")

    args = parser.parse_args(argv)

    try:
        pattern = re.compile(args.dispatch_bash_pattern) if args.dispatch_bash_pattern else None
    except re.error as exc:
        print(f"error: invalid --dispatch-bash-pattern: {exc}", file=sys.stderr)
        return 2

    if args.command == "check-transcript":
        transcript = Path(args.transcript)
        if not transcript.is_file():
            print(f"error: transcript not found: {transcript}", file=sys.stderr)
            return 2
        try:
            count = check_transcript(transcript, args.dispatch_tool_names, pattern)
        except (ValueError, OSError) as exc:
            print(f"error: could not check transcript: {exc}", file=sys.stderr)
            return 2
        print(f"DISPATCH_COUNT={count}")
        return 0 if count >= args.min_dispatches else 1

    # args.command == "run"
    prompt_file = Path(args.prompt_file)
    if not prompt_file.is_file():
        print(f"error: prompt file not found: {prompt_file}", file=sys.stderr)
        return 2
    prompt = prompt_file.read_text(encoding="utf-8")
    transcript_out = Path(args.transcript_out)

    with tempfile.TemporaryDirectory(prefix="check-dispatch-trace-") as tmp:
        tmp_path = Path(tmp)
        isolated_cwd = tmp_path / "isolated-cwd"
        isolated_cwd.mkdir()
        if args.isolated_home:
            isolated_home = Path(args.isolated_home)
        else:
            try:
                isolated_home = build_isolated_home(tmp_path)
            except FileNotFoundError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
        result = run_live_dispatch(
            prompt, transcript_out,
            isolated_cwd=isolated_cwd, isolated_home=isolated_home,
            allowed_tools=args.allowed_tools,
            plugin_dir=Path(args.plugin_dir) if args.plugin_dir else None,
            add_dir=Path(args.add_dir) if args.add_dir else None,
            permission_mode=args.permission_mode,
            claude_bin=args.claude_bin,
        )
    if result.returncode != 0:
        print(f"error: claude -p exited {result.returncode}: {result.stderr}", file=sys.stderr)
        return 2

    try:
        count = check_transcript(transcript_out, args.dispatch_tool_names, pattern)
    except (ValueError, OSError) as exc:
        print(f"error: could not check captured transcript: {exc}", file=sys.stderr)
        return 2
    print(f"DISPATCH_COUNT={count}")
    return 0 if count >= args.min_dispatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
