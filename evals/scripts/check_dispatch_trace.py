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
3. **The Skill tool cannot discover a target it was never told exists.**
   `--plugin-dir` auto-triggers Skill-tool discovery, but only because it
   loads the skill directly; a caller that instead wants an isolated target
   to be discovered the way a real downstream consumer would install it --
   via `claude plugin marketplace add` + `claude plugin install` -- gets
   nothing if the isolated copy has no `.claude-plugin/marketplace.json`.
   Two consecutive gate cycles (gitapex issues #614 and #619) silently ran
   in this degraded mode: the dispatch, unable to find the skill, fell back
   to reading `SKILL.md` directly and reasoning about it in prose instead of
   invoking a real subagent (gitapex issue #621's root-cause writeup, and
   `references/adversarial-self-audit.md`'s Isolation-verification registry
   entry for this mechanism, have the full history). `run`'s
   `--marketplace-source`/`--plugin-name` flags below run that real
   registration and fail loudly -- before any dispatch is attempted -- if
   the isolated copy has no `.claude-plugin/marketplace.json`, rather than
   silently letting the dispatch proceed in degraded mode.

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
    bash_tool_name: str = "Bash",
) -> int:
    """Count dispatch-shaped ``tool_use`` blocks.

    A block counts if its ``name`` is in ``dispatch_tool_names`` (a same-
    transcript dispatch-tool invocation), OR -- when ``dispatch_bash_pattern``
    is given -- its ``name`` equals ``bash_tool_name`` and its
    ``input.command`` matches that pattern (a nested ``claude -p`` subprocess
    dispatch; see this module's docstring, lesson 2). ``bash_tool_name``
    defaults to ``"Bash"`` but is caller-overridable, for the same reason
    ``dispatch_tool_names`` is never hardcoded (docstring lesson 1) -- a
    shell-tool name is platform-specific too, even if it drifts less often
    than the dispatch-tool name observed to. The two are independent checks:
    a fixture that only cares about the first passes ``dispatch_bash_pattern
    =None`` and gets exactly the same-transcript-tool_use behavior.
    """
    names = set(dispatch_tool_names)
    count = 0
    for block in tool_use_blocks:
        name = block.get("name")
        if name in names:
            count += 1
            continue
        if dispatch_bash_pattern is not None and name == bash_tool_name:
            block_input = block.get("input")
            command = block_input.get("command") if isinstance(block_input, dict) else None
            if isinstance(command, str) and dispatch_bash_pattern.search(command):
                count += 1
    return count


def check_transcript(
    transcript_path: Path,
    dispatch_tool_names,
    dispatch_bash_pattern: re.Pattern | None = None,
    bash_tool_name: str = "Bash",
) -> int:
    """Return the dispatch count for ``transcript_path``. Propagates
    ``ValueError``/``OSError`` from ``iter_tool_use_blocks`` unchanged --
    the CLI layer is what turns those into an exit-2 usage error. Streams
    ``tool_use`` blocks directly into ``count_dispatches`` rather than
    materializing a list first -- ``count_dispatches`` only ever makes one
    forward pass, so buffering the whole transcript in memory first would
    cost real memory on a long transcript for no benefit."""
    return count_dispatches(
        iter_tool_use_blocks(transcript_path), dispatch_tool_names,
        dispatch_bash_pattern, bash_tool_name,
    )


def build_isolated_home(base_dir: Path) -> Path:
    """Copy the real ``$HOME/.claude`` tree and ``$HOME/.claude.json`` into a
    fresh directory under ``base_dir``, stripping only the live-state
    subdirectories a dispatched subprocess must not see. Mirrors the
    verified recipe in ``adversarial-self-audit.md``'s Isolation verification
    section (settings/hooks/skills untouched). Returns the new ``$HOME``
    path. Raises ``FileNotFoundError`` if ``$HOME`` is unset or the real
    ``$HOME/.claude`` does not exist -- there is nothing to isolate a copy
    of, and guessing a fallback (e.g. ``/root``) risks silently copying a
    different identity's config/skills into the "isolated" copy, defeating
    the isolation guarantee this function exists to provide.
    """
    home_env = os.environ.get("HOME")
    if not home_env:
        raise FileNotFoundError(
            "$HOME is not set -- refusing to guess a fallback location"
        )
    real_home = Path(home_env)
    real_claude_dir = real_home / ".claude"
    if not real_claude_dir.is_dir():
        raise FileNotFoundError(f"no {real_claude_dir} to build an isolated copy from")
    isolated_home = base_dir / "isolated-home"
    isolated_home.mkdir(parents=True, exist_ok=True)

    def _ignore_top_level_strip_dirs(directory, names):
        # Only strip these names as direct children of real_claude_dir
        # itself -- an ignore_patterns-style recursive match could also
        # exclude an unrelated same-named directory nested inside a vendored
        # skill (e.g. a skill's own tasks/ content), which the prior
        # copy-then-rmtree approach never touched either.
        if Path(directory) == real_claude_dir:
            return [n for n in names if n in _HOME_COPY_STRIP_DIRS]
        return []

    shutil.copytree(
        real_claude_dir, isolated_home / ".claude",
        ignore=_ignore_top_level_strip_dirs,
    )
    real_claude_json = real_home / ".claude.json"
    if real_claude_json.is_file():
        shutil.copy2(real_claude_json, isolated_home / ".claude.json")
    for name in _HOME_COPY_STRIP_DIRS:
        (isolated_home / ".claude" / name).mkdir(parents=True, exist_ok=True)
    return isolated_home


class PluginRegistrationError(Exception):
    """Raised when ``claude plugin marketplace add`` or ``claude plugin
    install`` exits non-zero against an isolated ``$HOME`` -- a failed
    registration must stop the run, not silently fall through to a dispatch
    that cannot actually discover the target skill."""


_DEFAULT_PLUGIN_REGISTRATION_TIMEOUT_SECONDS = 120


def register_plugin_marketplace(
    marketplace_source: Path,
    plugin_name: str,
    *,
    isolated_home: Path,
    isolated_cwd: Path,
    claude_bin: str = "claude",
    timeout_seconds: float | None = _DEFAULT_PLUGIN_REGISTRATION_TIMEOUT_SECONDS,
) -> None:
    """Register ``marketplace_source`` as a plugin marketplace and install
    ``plugin_name`` from it, against the isolated ``isolated_home``, so a
    subsequent dispatch's Skill tool can discover the target skill the same
    way a real downstream consumer would -- rather than via ``--plugin-dir``,
    which loads skill content directly and never exercises this discovery
    path (see this module's docstring, lesson 3).

    Raises ``FileNotFoundError`` *before* running any subprocess if
    ``marketplace_source`` has no ``.claude-plugin/marketplace.json`` -- this
    is the durable fix for gitapex issue #621: two consecutive gate cycles
    silently dispatched against a target the Skill tool could never actually
    discover, because nothing checked for this file's presence and the
    dispatch quietly fell back to prose reasoning about ``SKILL.md`` instead
    of a real subagent invocation. Failing loudly here means that can no
    longer happen unnoticed.

    Raises ``PluginRegistrationError`` if either ``claude plugin marketplace
    add`` or ``claude plugin install`` exits non-zero. Raises
    ``OSError``/``FileNotFoundError`` if ``claude_bin`` is not launchable, and
    ``subprocess.TimeoutExpired`` if either command stalls past
    ``timeout_seconds`` -- callers should catch these the same way they
    already catch ``run_live_dispatch``'s failure modes.
    """
    marketplace_json = marketplace_source / ".claude-plugin" / "marketplace.json"
    if not marketplace_json.is_file():
        raise FileNotFoundError(
            f"no {marketplace_json} -- the isolated copy has no marketplace "
            "manifest, so the Skill tool cannot discover the target plugin; "
            "refusing to dispatch in degraded/simulated mode (gitapex #621)"
        )

    env = dict(os.environ)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env["HOME"] = str(isolated_home)
    env["PWD"] = str(isolated_cwd)

    for argv in (
        [claude_bin, "plugin", "marketplace", "add", str(marketplace_source)],
        [claude_bin, "plugin", "install", plugin_name],
    ):
        # S603 waived: argv is built above from a resolved absolute
        # claude_bin plus fixed literals, and runs with no shell.
        result = subprocess.run(  # noqa: S603
            argv, cwd=str(isolated_cwd), env=env, capture_output=True,
            text=True, check=False, timeout=timeout_seconds,
        )
        if result.returncode != 0:
            raise PluginRegistrationError(
                f"{' '.join(argv)} exited {result.returncode}: {result.stderr}"
            )


_DEFAULT_LIVE_DISPATCH_TIMEOUT_SECONDS = 600


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
    timeout_seconds: float | None = _DEFAULT_LIVE_DISPATCH_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    """Run one live, isolated ``claude -p`` dispatch and capture its
    ``stream-json`` transcript to ``transcript_out``. Callers are responsible
    for confirming ``isolated_cwd``'s full ancestry carries no
    ``CLAUDE.md``/``AGENTS.md`` and for building ``isolated_home`` via
    ``build_isolated_home`` (or an equivalent) first -- this function does
    not verify isolation itself, only executes the already-isolated call, so
    a live proof run must still record the isolation check per
    ``adversarial-self-audit.md``'s Verification procedure.

    Raises ``subprocess.TimeoutExpired`` if the dispatch does not finish
    within ``timeout_seconds`` (default 10 minutes -- a real observed
    dispatch on this platform took over 3 minutes; pass ``None`` to disable)
    rather than blocking indefinitely on a stalled or permission-prompt-stuck
    subprocess, and ``OSError``/``FileNotFoundError`` if ``claude_bin`` is not
    launchable at all -- callers should catch both alongside this function's
    own contract, matching every other failure path in this module's CLI.
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
    # Some tools consult $PWD (a POSIX-shell convention) instead of calling
    # getcwd(); left unset/stale here it would still carry the *calling*
    # process's real cwd even though `cwd=` below is the isolated one,
    # potentially resolving back to a CLAUDE.md-carrying location by a path
    # other than the one this isolation recipe actually controls.
    env["PWD"] = str(isolated_cwd)
    with transcript_out.open("w", encoding="utf-8") as out:
        # S603 waived: same caller-supplied argv list, no shell.
        result = subprocess.run(  # noqa: S603
            argv, cwd=str(isolated_cwd), env=env, stdout=out,
            stderr=subprocess.PIPE, text=True, check=False,
            timeout=timeout_seconds,
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
    check_p.add_argument("--bash-tool-name", default="Bash", help="Tool name matched by --dispatch-bash-pattern.")
    check_p.add_argument("--min-dispatches", type=int, default=1)

    run_p = sub.add_parser(
        "run", help="Live: run one isolated claude -p dispatch and check its transcript."
    )
    run_p.add_argument("--prompt-file", required=True)
    run_p.add_argument("--transcript-out", required=True)
    run_p.add_argument("--dispatch-tool-name", action="append", required=True, dest="dispatch_tool_names")
    run_p.add_argument("--dispatch-bash-pattern", default=None)
    run_p.add_argument("--bash-tool-name", default="Bash", help="Tool name matched by --dispatch-bash-pattern.")
    run_p.add_argument("--min-dispatches", type=int, default=1)
    run_p.add_argument(
        "--allowed-tools", default="Agent",
        help="Space-separated tools to allow in the dispatched session. If --dispatch-bash-"
             "pattern is also given and --bash-tool-name is not already listed here, it is "
             "auto-appended -- otherwise the nested-dispatch shape this flag exists to detect "
             "would always be denied by the harness itself before it could ever be observed.",
    )
    run_p.add_argument("--permission-mode", default="acceptEdits")
    run_p.add_argument("--plugin-dir", default=None)
    run_p.add_argument("--add-dir", default=None)
    run_p.add_argument("--isolated-home", default=None, help="Reuse an existing isolated $HOME; else build a fresh one.")
    run_p.add_argument("--claude-bin", default="claude")
    run_p.add_argument(
        "--timeout", type=float, default=_DEFAULT_LIVE_DISPATCH_TIMEOUT_SECONDS,
        help="Seconds before a stalled live dispatch is killed (default 600). "
             "0 or negative disables the timeout.",
    )
    run_p.add_argument(
        "--marketplace-source", default=None,
        help="Path to an isolated copy that should contain "
             ".claude-plugin/marketplace.json. When given (with --plugin-name), "
             "runs `claude plugin marketplace add`/`claude plugin install` "
             "against the isolated $HOME before dispatching, and fails loudly "
             "(exit 2) if the manifest is missing, rather than dispatching in "
             "degraded mode (gitapex #621). Must be given together with "
             "--plugin-name.",
    )
    run_p.add_argument(
        "--plugin-name", default=None,
        help="Plugin name to `claude plugin install` (e.g. gitapex@gitapex). "
             "Must be given together with --marketplace-source.",
    )

    args = parser.parse_args(argv)

    # `None` (the flag was never passed -- check-transcript's own sub-parser
    # doesn't define these two flags at all, so getattr's default covers that
    # case too) means "opted out of marketplace registration", legitimate.
    # An explicitly-passed value that strips to empty (e.g. an unset
    # environment variable interpolated as `--marketplace-source ""` by a
    # caller's own shell wiring) is a DIFFERENT case -- the caller opted in
    # but supplied a broken value -- and must fail loudly here rather than
    # being silently treated the same as "opted out": that would fall
    # through to an ordinary dispatch with no marketplace registration and
    # no error, reproducing the exact silent-degraded-dispatch failure mode
    # this flag exists to close.
    raw_marketplace_source = getattr(args, "marketplace_source", None)
    raw_plugin_name = getattr(args, "plugin_name", None)
    marketplace_source = (raw_marketplace_source or "").strip()
    plugin_name = (raw_plugin_name or "").strip()
    if args.command == "run":
        given = (raw_marketplace_source is not None, raw_plugin_name is not None)
        if given[0] != given[1]:
            print(
                "error: --marketplace-source and --plugin-name must be given together",
                file=sys.stderr,
            )
            return 2
        if any(given) and not (marketplace_source and plugin_name):
            print(
                "error: --marketplace-source and --plugin-name must not be blank",
                file=sys.stderr,
            )
            return 2

    try:
        pattern = re.compile(args.dispatch_bash_pattern) if args.dispatch_bash_pattern is not None else None
    except re.error as exc:
        print(f"error: invalid --dispatch-bash-pattern: {exc}", file=sys.stderr)
        return 2

    if args.command == "check-transcript":
        transcript = Path(args.transcript)
        if not transcript.is_file():
            print(f"error: transcript not found: {transcript}", file=sys.stderr)
            return 2
        try:
            count = check_transcript(transcript, args.dispatch_tool_names, pattern, args.bash_tool_name)
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

    allowed_tools = args.allowed_tools
    if pattern is not None and args.bash_tool_name not in allowed_tools.split():
        allowed_tools = f"{allowed_tools} {args.bash_tool_name}"

    with tempfile.TemporaryDirectory(prefix="check-dispatch-trace-") as tmp:
        tmp_path = Path(tmp)
        isolated_cwd = tmp_path / "isolated-cwd"
        isolated_cwd.mkdir()
        if args.isolated_home:
            isolated_home = Path(args.isolated_home).resolve()
        else:
            try:
                isolated_home = build_isolated_home(tmp_path)
            except FileNotFoundError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2

        if marketplace_source:
            try:
                register_plugin_marketplace(
                    # Resolved eagerly: the subprocess calls below run with
                    # cwd=isolated_cwd (a fresh tempdir unrelated to this
                    # process's real cwd), so a relative path must be
                    # resolved against *this* process's cwd first -- the
                    # same reasoning --isolated-home already applies above.
                    Path(marketplace_source).resolve(), plugin_name,
                    isolated_home=isolated_home, isolated_cwd=isolated_cwd,
                    claude_bin=args.claude_bin,
                )
            except PluginRegistrationError as exc:
                print(f"error: plugin registration failed: {exc}", file=sys.stderr)
                return 2
            except OSError as exc:
                # Covers both this function's own FileNotFoundError (missing
                # .claude-plugin/marketplace.json -- the fail-loud check
                # itself, message already fully descriptive) and a genuinely
                # unlaunchable claude_bin (also FileNotFoundError, raised by
                # subprocess.run) -- the two are the same exception type and
                # not worth distinguishing further here.
                print(f"error: {exc}", file=sys.stderr)
                return 2
            except subprocess.TimeoutExpired:
                print("error: plugin registration did not finish in time -- killed", file=sys.stderr)
                return 2

        try:
            result = run_live_dispatch(
                prompt, transcript_out,
                isolated_cwd=isolated_cwd, isolated_home=isolated_home,
                allowed_tools=allowed_tools,
                plugin_dir=Path(args.plugin_dir) if args.plugin_dir else None,
                add_dir=Path(args.add_dir) if args.add_dir else None,
                permission_mode=args.permission_mode,
                claude_bin=args.claude_bin,
                timeout_seconds=args.timeout if args.timeout > 0 else None,
            )
        except OSError as exc:
            print(f"error: could not launch {args.claude_bin!r}: {exc}", file=sys.stderr)
            return 2
        except subprocess.TimeoutExpired:
            print(
                f"error: claude -p did not finish within {args.timeout}s -- killed",
                file=sys.stderr,
            )
            return 2
    if result.returncode != 0:
        print(f"error: claude -p exited {result.returncode}: {result.stderr}", file=sys.stderr)
        return 2

    try:
        count = check_transcript(transcript_out, args.dispatch_tool_names, pattern, args.bash_tool_name)
    except (ValueError, OSError) as exc:
        print(f"error: could not check captured transcript: {exc}", file=sys.stderr)
        return 2
    print(f"DISPATCH_COUNT={count}")
    return 0 if count >= args.min_dispatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
