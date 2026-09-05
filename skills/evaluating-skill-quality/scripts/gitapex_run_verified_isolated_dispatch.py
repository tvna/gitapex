"""Verify isolation and then launch a real review dispatch, as one operation
that never delegates the verification step to the dispatch it is about to
launch (issue #1809, design doc
``docs/gitapex/specs/2026-09-05-verified-isolated-dispatch-design.md``).

Before this script existed, ``adversarial-self-audit.md``'s Isolation
verification section asked a *human operator* to run its Verification
procedure by hand before every isolated dispatch: compare this run's own
identifying signals against the Known entries registry, and if nothing
matches, run a positive/negative control pair and record a new entry. That
procedure is correct, but hand-running it every time is exactly the kind of
manually-re-derived, session-scoped work this repository's own
"evaluation-first" thesis should not depend on. This script mechanizes it.

**Why this closes the circularity a dispatch's own self-report cannot.** A
dispatched subagent reporting "I don't see a CLAUDE.md" is not evidence of
isolation -- it is a claim from inside the very context whose isolation is in
question. The two-control procedure below always runs from the *orchestrator's*
own process (this script's, or an interactive operator's shell), never from
the dispatch under review, so the dispatch being asked to do real review work
never verifies its own isolation; it only ever inherits an already-established,
externally-verified recipe.

**Methodology, transcribed from the current source of truth.** The exact
two-control procedure this script automates is the one documented in
``references/adversarial-self-audit.md``'s own "Verification procedure"
subsection as of this script's writing -- this docstring does not restate
that section's full rationale, only the parts needed to explain this script's
own behavior:

- **Positive control**: from a scratch directory outside any real repository,
  write a synthetic sentinel ``CLAUDE.md`` (never the calling repository's
  real file -- that would send real, possibly sensitive project-instruction
  content to whatever endpoint backs the dispatch mechanism) and ask the
  candidate mechanism to report whether it has project-level instructions
  loaded, quoting them if so. This proves the mechanism can see a
  project-instruction file at all, so a "none loaded" result in the negative
  control below means something.
- **Negative control**: identical prompt, identical mechanism, from a
  location with no ``CLAUDE.md``/``AGENTS.md`` anywhere in its full directory
  ancestry. Counts as evidence of isolation only because the positive control
  already proved the mechanism is not simply blind to the file.

**What this script actually verifies, and what it does not.** The automated
procedure above verifies exactly one leak vector: whether the calling
repository's own ``CLAUDE.md``/``AGENTS.md`` is visible to the dispatch
(``leak_vector: claude_md_agents_md`` in the registry schema below). The
separately-documented ``home_task_list`` leak vector (a dispatched
subprocess inheriting the caller's real ``$HOME`` and so its live task list)
is out of this procedure's scope; a caller needing that guarantee too must
still apply ``adversarial-self-audit.md``'s own ``$HOME``-copy recipe on top
of this script's result. This is why this script's own returned report
carries a ``verifiedLeakVectors`` list naming exactly what was checked this
run, never an unqualified ``dispatchIsolation: true`` boolean that would
overstate what was actually verified.

**Why a freshly-established (same-run) recipe still needs a human eye.**
Today's manual procedure has an operator directly read both control
transcripts before trusting the result. Automating the pass/fail comparison
removes that observation unless this script keeps printing the full
transcripts on every same-run establishment (not only a bare PASS/FAIL) --
so a bug in this script's own comparison logic (matching the wrong output
field, a sentinel string that is too loose) still has a chance of being
caught by a human reading the actual text, the same way the manual procedure
always relied on. This is why ``run_two_controls`` returns the full
transcript text unconditionally, and the CLI below prints it before
consulting the boolean verdict derived from it.

**Trust class.** A registry entry this script itself just wrote
(``trust_class: same-run-unreviewed``) is never read back as established
within the same run -- matching ``adversarial-self-audit.md``'s own Trust
class rule. Only a ``reviewed`` entry (one already present in the registry
copy this run started from, having passed this repository's own review
gate) may be reused without re-running the controls.

Standard library plus PyYAML -- ``evaluating-skill-quality`` already
declares ``dependencyPolicy: Declared`` and ``executionRequirements.packages.
pip: [pyyaml, ...]`` in its own ``metadata/gitapex.yaml`` sidecar, so this is
not a new dependency for this skill. Deliberately self-contained (no import
from ``evals/scripts/``, which is CI/dev-only and never deployed alongside
``skills/`` to a consumer installing this skill per
``docs/repository-layout.md``) even though ``evals/scripts/
gitapex_check_dispatch_trace.py`` already implements a similar isolated-HOME-
copy and live-dispatch helper -- importing across that boundary would break
this skill's own bundled script the moment a consumer installs ``skills/``
without also getting ``evals/``.
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

# Directories inside $HOME/.claude that carry live session/task state rather
# than durable configuration -- stripped from an isolated $HOME copy per
# adversarial-self-audit.md's own "Second leak vector" recipe, so a
# dispatched subprocess cannot see this calling session's own live task list
# or conversation history.
_HOME_COPY_STRIP_DIRS = ("tasks", "projects", "sessions", "shell-snapshots")

# Fixed, distinctive, non-sensitive sentence -- never the calling repository's
# real CLAUDE.md content (see this module's own docstring for why).
_SENTINEL_MARKER = "gitapex-isolation-sentinel-8f2c1a"
_SENTINEL_CLAUDE_MD = f"# Sentinel\n\nIf you can read this file, say exactly: {_SENTINEL_MARKER}\n"
_CONTROL_PROMPT = (
    "Do you currently have a project-level instruction file (CLAUDE.md or "
    "AGENTS.md) loaded in your context? If so, quote its exact content "
    "verbatim. If not, say so plainly."
)

# The only leak vector this script's own automated procedure verifies (see
# this module's docstring, "What this script actually verifies").
_PRIMARY_LEAK_VECTOR = "claude_md_agents_md"

# The exact recipe this script itself implements: cwd isolation (the target
# snapshot itself, via build_target_snapshot) plus an isolated $HOME copy, no
# permission-bypass flag. Used both when this script writes a new same-run
# entry (so the entry accurately names what was actually run) and when it
# looks one up (so it never reuses a registry entry recorded for a different
# mechanism -- e.g. `--plugin-dir` or a marketplace install -- merely because
# that entry happens to share this run's own identifying signals; the
# registry's own schema keys entries on the *pair* (identifying-signal-set,
# mechanism), not signals alone, and several migrated historical entries
# share identical signals with different mechanisms and results).
_CANONICAL_MECHANISM = "claude -p subprocess, isolated cwd (script-established baseline recipe)"

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_DEFAULT_REGISTRY_PATH = _SKILL_DIR / "metadata" / "isolation-registry.yaml"
_DEFAULT_HISTORY_MARKDOWN_PATH = _SKILL_DIR / "references" / "isolation-registry-history.md"

_DEFAULT_CONTROL_TIMEOUT_SECONDS = 120.0
_DEFAULT_DISPATCH_TIMEOUT_SECONDS = 600.0
_DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 30.0


def read_identifying_signals(
    claude_bin: str = "claude",
) -> dict[str, str]:
    """Collect this run's own identifying signals: the two environment
    variables every existing registry entry keys on, plus ``claude
    --version`` output. Raises ``OSError``/``FileNotFoundError`` if
    ``claude_bin`` is not launchable, and ``subprocess.TimeoutExpired`` if it
    stalls -- callers must treat both as "no verified mechanism available"
    causes, the same as every other subprocess failure path in this module.
    """
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    signals: dict[str, str] = {}
    for var in ("CLAUDE_CODE_REMOTE", "CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE"):
        value = os.environ.get(var)
        if value is not None:
            signals[var] = value
    # S603 waived: claude_bin is caller-supplied (default "claude"), argv is
    # a fixed two-element list, no shell.
    result = subprocess.run(  # noqa: S603
        [claude_bin, "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=_DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    signals["claude_version"] = (result.stdout or result.stderr).strip()
    return signals


def load_registry(
    path: Path,
) -> list[dict[str, Any]]:
    """Return the registry's ``entries`` list, or ``[]`` if the file does not
    exist yet, is not valid UTF-8/YAML, or carries no well-formed ``entries``
    list -- all treated the same way as "nothing usable here yet", never a
    crash: a freshly-created registry file starts out empty in exactly this
    shape."""
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (UnicodeDecodeError, yaml.YAMLError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, list) else []


def save_registry(path: Path, entries: list[dict[str, Any]]) -> None:
    """Write ``entries`` back to ``path`` as ``{"entries": [...]}``."""
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    path.write_text(
        yaml.safe_dump({"entries": entries}, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def find_reviewed_match(
    entries: list[dict[str, Any]],
    signals: dict[str, str],
    mechanism: str = _CANONICAL_MECHANISM,
    leak_vector: str = _PRIMARY_LEAK_VECTOR,
) -> dict[str, Any] | None:
    """Return the first ``reviewed`` entry whose own ``identifying_signals``
    exactly equal ``signals``, whose ``mechanism`` exactly equals
    ``mechanism``, whose ``leak_vector`` matches, and whose ``result`` is
    ``"isolated"`` -- or ``None``.

    ``mechanism`` is compared, not only ``identifying_signals``, because the
    registry's own schema keys an entry on the *pair* (identifying-signal-set,
    mechanism) -- several migrated historical entries share byte-identical
    ``identifying_signals`` with *different* mechanisms and results (a
    contaminated Agent-tool dispatch, an isolated ``--plugin-dir`` dispatch,
    and an isolated plain ``claude -p`` dispatch all recorded at the same
    platform signature). Matching on signals alone would let this function
    return an entry recorded for a mechanism this script does not actually
    implement (e.g. ``--plugin-dir``), which would be reused as if it
    verified the recipe this script is about to run -- an independent
    adversarial review caught this gap (issue #1809).

    The registry also carries ``"contaminated"`` entries (a mechanism this
    run does not even use, kept on record as a negative finding); matching
    on ``leak_vector`` alone would let a caller "reuse" a contaminated
    entry's own signals as if they verified isolation, which is exactly
    backwards. Never matches a ``same-run-unreviewed`` entry -- per
    ``adversarial-self-audit.md``'s Trust class rule, a same-run entry is
    never read back as established within a later lookup, only the two
    control outcomes that run actually observed count as evidence.
    """
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    for entry in entries:
        if entry.get("trust_class") != "reviewed":
            continue
        if entry.get("mechanism") != mechanism:
            continue
        if entry.get("leak_vector") != leak_vector:
            continue
        if entry.get("result") != "isolated":
            continue
        if entry.get("identifying_signals") == signals:
            return entry
    return None


def build_isolated_home(
    base_dir: Path,
) -> Path:
    """Copy the real ``$HOME/.claude`` tree and ``$HOME/.claude.json`` into a
    fresh directory under ``base_dir``, stripping only the live-state
    subdirectories a dispatched subprocess must not see -- mirrors the
    verified recipe in ``adversarial-self-audit.md``'s Isolation verification
    section (settings/hooks/skills untouched). Raises ``FileNotFoundError``
    if ``$HOME`` is unset or the real ``$HOME/.claude`` does not exist,
    rather than guessing a fallback location, which would risk silently
    copying a different identity's config/skills into the "isolated" copy.
    """
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    home_env = os.environ.get("HOME")
    if not home_env:
        raise FileNotFoundError("$HOME is not set -- refusing to guess a fallback location")
    real_home = Path(home_env)
    real_claude_dir = real_home / ".claude"
    if not real_claude_dir.is_dir():
        raise FileNotFoundError(f"no {real_claude_dir} to build an isolated copy from")
    isolated_home = base_dir / "isolated-home"
    isolated_home.mkdir(parents=True, exist_ok=True)

    def _ignore_top_level_strip_dirs(directory: str, names: list[str]) -> list[str]:
        # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
        if Path(directory) == real_claude_dir:
            return [n for n in names if n in _HOME_COPY_STRIP_DIRS]
        return []

    shutil.copytree(real_claude_dir, isolated_home / ".claude", ignore=_ignore_top_level_strip_dirs)
    real_claude_json = real_home / ".claude.json"
    if real_claude_json.is_file():
        shutil.copy2(real_claude_json, isolated_home / ".claude.json")
    for name in _HOME_COPY_STRIP_DIRS:
        (isolated_home / ".claude" / name).mkdir(parents=True, exist_ok=True)
    return isolated_home


def _dispatch_env(home: Path, cwd: Path) -> dict[str, str]:
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    env["HOME"] = str(home)
    # Some tools consult $PWD instead of calling getcwd(); left stale here it
    # would still carry the calling process's real cwd even though `cwd=`
    # below is the isolated one (adversarial-self-audit.md's own
    # $PWD-vs-real-cwd methodology pitfall).
    env["PWD"] = str(cwd)
    return env


def run_control(
    cwd: Path, home: Path, claude_bin: str, timeout_seconds: float | None
) -> subprocess.CompletedProcess[str]:
    """Run one control invocation (positive or negative, depending on
    whether ``cwd`` carries the sentinel ``CLAUDE.md``) and return the
    completed process, stdout/stderr captured as text."""
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    # S603 waived: claude_bin is caller-supplied, argv built from fixed
    # literals plus that binary name, no shell.
    return subprocess.run(  # noqa: S603
        [claude_bin, "-p", _CONTROL_PROMPT],
        cwd=str(cwd),
        env=_dispatch_env(home, cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )


def run_two_controls(
    base_dir: Path, home: Path, claude_bin: str, timeout_seconds: float | None
) -> tuple[bool, bool, str]:
    """Run the positive/negative control pair from fresh scratch directories
    under ``base_dir``, using the caller-supplied isolated ``$HOME`` copy
    ``home`` for both. ``home`` is a parameter rather than built here so the
    caller can reuse the exact same isolated ``$HOME`` for the real dispatch
    that follows -- calling ``build_isolated_home`` a second time against the
    same ``base_dir`` would collide with the copy this function already made.
    Returns ``(positive_ok, negative_ok, transcript)`` -- ``transcript`` is
    the full stdout/stderr of both runs, always returned regardless of
    outcome, so a human reviewing a same-run establishment sees the same
    evidence the manual procedure always required (see this module's
    docstring).
    """
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    positive_cwd = base_dir / "positive-control"
    positive_cwd.mkdir(parents=True, exist_ok=True)
    (positive_cwd / "CLAUDE.md").write_text(_SENTINEL_CLAUDE_MD, encoding="utf-8")
    negative_cwd = base_dir / "negative-control"
    negative_cwd.mkdir(parents=True, exist_ok=True)

    positive = run_control(positive_cwd, home, claude_bin, timeout_seconds)
    negative = run_control(negative_cwd, home, claude_bin, timeout_seconds)

    positive_ok = _SENTINEL_MARKER in (positive.stdout or "")
    negative_ok = negative.returncode == 0 and _SENTINEL_MARKER not in (negative.stdout or "")

    transcript = (
        "--- positive control (expects the sentinel marker below) ---\n"
        f"marker written: {_SENTINEL_MARKER}\n"
        f"stdout:\n{positive.stdout}\nstderr:\n{positive.stderr}\n"
        "--- negative control (expects the marker to be absent) ---\n"
        f"stdout:\n{negative.stdout}\nstderr:\n{negative.stderr}\n"
    )
    return positive_ok, negative_ok, transcript


def print_no_verified_mechanism_block(reason: str, current_platform_note: str) -> None:
    """Emit the required, fixed two-option fenced code block (issue #1410's
    own "No verified mechanism available" shape): never a bare error
    message, and never a silent fall-through to an unverified dispatch. The
    two options are illustrative placeholders here, the same as
    ``adversarial-self-audit.md``'s own worked example -- filling in the
    real values for the platform at hand is the operator's job, this script
    cannot know which environment fix or hand-off target actually applies.
    """
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    print(f"No verified mechanism available: {reason}", file=sys.stderr)
    print(current_platform_note, file=sys.stderr)
    print(
        "```bash\n"
        "# Option A: fix this environment\n"
        "<install/configure command(s) the verified mechanism actually needs here>\n"
        "\n"
        "# Option B: hand off to a verified environment\n"
        "<exact command or session-creation steps to run the identical review\n"
        "elsewhere, plus exactly what to pass it>\n"
        "```",
        file=sys.stderr,
    )


def build_target_snapshot(target: Path, base_dir: Path) -> Path:
    """Copy ``target`` into a fresh scratch directory under ``base_dir`` and
    make it read-only, so the real dispatch's own isolated cwd *is* the
    review target itself rather than an empty directory pointed at an
    absolute path elsewhere -- adversarial-self-audit.md's own methodology
    pitfall: the harness's permission sandbox confines a dispatch to reads
    inside its working directory, so any other arrangement silently truncates
    the dispatch's output to a bare read-grant request. "Read-only" here is
    caller-created and not written by the dispatch, not an OS-enforced
    guarantee under a uid-0 process, which bypasses the mode bits.
    """
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    snapshot = base_dir / "target-snapshot"
    if target.is_dir():
        shutil.copytree(target, snapshot)
    else:
        snapshot.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, snapshot / target.name)
    for root, dirs, files in os.walk(snapshot):
        for name in dirs + files:
            path = Path(root) / name
            path.chmod(path.stat().st_mode & ~0o222)
    return snapshot


def run_real_dispatch(
    prompt: str,
    cwd: Path,
    home: Path,
    claude_bin: str,
    allowed_tools: str | None,
    timeout_seconds: float | None,
) -> subprocess.CompletedProcess[str]:
    """Launch the real review dispatch, using exactly the verified isolated
    recipe: ``cwd`` (the target snapshot) carries no permission-bypass flag
    by default -- only ``--allowedTools`` when the caller supplies one,
    matching ``_CANONICAL_MECHANISM``, the most recently reconfirmed
    baseline recorded in ``metadata/isolation-registry.yaml``."""
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    argv = [claude_bin, "-p", prompt]
    if allowed_tools:
        argv += ["--allowedTools", allowed_tools]
    # S603 waived: claude_bin is caller-supplied, prompt/allowed_tools are
    # caller-supplied strings passed as discrete argv elements, no shell.
    return subprocess.run(  # noqa: S603
        argv,
        cwd=str(cwd),
        env=_dispatch_env(home, cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )


def regenerate_markdown_summary(registry_path: Path, markdown_path: Path) -> None:
    """Render ``registry_path``'s entries as a human-browsable Markdown
    table, replacing ``markdown_path`` wholesale. This is generated,
    conditional reference material (Components item 3 of the design doc):
    relevant when a human is reviewing a same-run entry for promotion, or
    maintaining this script -- not needed for ordinary dispatch operation."""
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    entries = load_registry(registry_path)
    lines = [
        "<!-- GENERATED by gitapex_run_verified_isolated_dispatch.py's",
        "     regenerate_markdown_summary -- do not hand-edit. Edit",
        "     metadata/isolation-registry.yaml and regenerate instead. -->",
        "",
        "# Isolation verification registry (generated history view)",
        "",
        "One row per `(identifying-signal-set, mechanism)` pair. See",
        "`references/adversarial-self-audit.md`'s Isolation verification",
        "section for the Trust class rule this `trust_class` column encodes.",
        "",
        "| Date | Leak vector | Mechanism | Result | Trust class |",
        "|---|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| {date} | {leak_vector} | {mechanism} | {result} | {trust_class} |".format(
                date=entry.get("date") or "(unspecified)",
                leak_vector=entry.get("leak_vector", ""),
                mechanism=str(entry.get("mechanism", "")).replace("|", "\\|"),
                result=entry.get("result", ""),
                trust_class=entry.get("trust_class", ""),
            )
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(
    argv: list[str] | None = None,
) -> int:
    # function-body-test-coverage: WAIVED: covered by the co-located test file (100% coverage); this gate's own tests/-only search doesn't see it (issue #1809)
    parser = argparse.ArgumentParser(
        description="Verify isolation (reusing a Reviewed registry entry, or running the "
        "two-control procedure live) and then launch a real review dispatch using exactly "
        "the verified recipe."
    )
    parser.add_argument("--target", type=Path, help="Path to the review target (required unless --controls-only).")
    parser.add_argument(
        "--prompt-file", type=Path, help="Path to the real dispatch's prompt (required unless --controls-only)."
    )
    parser.add_argument(
        "--controls-only",
        action="store_true",
        help="Run isolation verification only; never launch a real dispatch. Used by the "
        "scheduled registry-refresh workflow.",
    )
    parser.add_argument("--allowed-tools", default=None, help="Passed through as --allowedTools to the real dispatch.")
    parser.add_argument("--registry", type=Path, default=_DEFAULT_REGISTRY_PATH)
    parser.add_argument("--history-markdown", type=Path, default=_DEFAULT_HISTORY_MARKDOWN_PATH)
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--control-timeout-seconds", type=float, default=_DEFAULT_CONTROL_TIMEOUT_SECONDS)
    parser.add_argument("--dispatch-timeout-seconds", type=float, default=_DEFAULT_DISPATCH_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    if not args.controls_only:
        if args.target is None or not args.target.exists():
            print(f"error: --target not found: {args.target}", file=sys.stderr)
            return 1
        if args.prompt_file is None or not args.prompt_file.is_file():
            print(f"error: --prompt-file not found: {args.prompt_file}", file=sys.stderr)
            return 1

    try:
        signals = read_identifying_signals(args.claude_bin)
    except (OSError, subprocess.TimeoutExpired) as error:
        print_no_verified_mechanism_block(
            f"could not read identifying signals via `{args.claude_bin} --version`: {error}",
            "This environment cannot even determine its own identifying signals.",
        )
        return 1

    entries = load_registry(args.registry)
    matched = find_reviewed_match(entries, signals, _CANONICAL_MECHANISM)

    with tempfile.TemporaryDirectory(prefix="gitapex-verified-dispatch-") as tmp_name:
        base_dir = Path(tmp_name)
        try:
            home = build_isolated_home(base_dir)
        except (OSError, FileNotFoundError) as error:
            print_no_verified_mechanism_block(
                f"could not build an isolated $HOME copy: {error}",
                "This environment cannot even establish an isolated $HOME.",
            )
            return 1

        if matched is not None:
            print(
                f"Reusing Reviewed registry entry dated {matched.get('date')}: {matched.get('mechanism')}",
                file=sys.stderr,
            )
            verified_leak_vectors = [str(matched.get("leak_vector", _PRIMARY_LEAK_VECTOR))]
        else:
            try:
                positive_ok, negative_ok, transcript = run_two_controls(
                    base_dir, home, args.claude_bin, args.control_timeout_seconds
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                print_no_verified_mechanism_block(
                    f"the live control run failed to execute: {error}",
                    f"No existing registry entry matches this run's own signals: {signals}.",
                )
                return 1
            print(transcript)
            if not (positive_ok and negative_ok):
                print_no_verified_mechanism_block(
                    "a control did not pass -- see the transcript above.",
                    f"No existing registry entry matches this run's own signals: {signals}.",
                )
                return 1
            new_entry: dict[str, Any] = {
                "identifying_signals": signals,
                "mechanism": _CANONICAL_MECHANISM,
                "leak_vector": _PRIMARY_LEAK_VECTOR,
                "result": "isolated",
                "verified_alternative": "isolated cwd with no CLAUDE.md/AGENTS.md in its ancestry; the "
                "target snapshot itself is used as that cwd for the real dispatch",
                "companion_flags": [f"--allowedTools {args.allowed_tools}"] if args.allowed_tools else [],
                "methodology_pitfalls": [],
                "trust_class": "same-run-unreviewed",
                "date": datetime.date.today().isoformat(),
                "notes": [
                    "Established automatically by gitapex_run_verified_isolated_dispatch.py. "
                    "Per adversarial-self-audit.md's Trust class rule, this entry must not be "
                    "read back as established until it has merged through this repository's "
                    "own review gate."
                ],
            }
            entries.append(new_entry)
            save_registry(args.registry, entries)
            regenerate_markdown_summary(args.registry, args.history_markdown)
            verified_leak_vectors = [_PRIMARY_LEAK_VECTOR]

        if args.controls_only:
            print("controls-only mode: isolation verified, not launching a real dispatch.")
            return 0

        snapshot = build_target_snapshot(args.target, base_dir)
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"error: could not read --prompt-file {args.prompt_file}: {error}", file=sys.stderr)
            return 1
        try:
            result = run_real_dispatch(
                prompt, snapshot, home, args.claude_bin, args.allowed_tools, args.dispatch_timeout_seconds
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f"error: the real dispatch failed to execute: {error}", file=sys.stderr)
            return 1

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        print(f"verifiedLeakVectors: {verified_leak_vectors}")
        return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
