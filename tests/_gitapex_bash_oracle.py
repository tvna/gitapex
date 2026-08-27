"""Shared real-bash oracle harness (issue #1365, Task 1).

Both bash-safety classifiers this repository ships
(``hooks/gitapex_check_bash_safety.py`` and
``skills/executing-a-branch-plan/scripts/gitapex_check_task_bash_safety.py``)
carry ~20 docstring citations of the shape "confirmed live via a real bash
proxy" / "confirmed via bash -c argv expansion" -- a hand run, once, against
a real interactive shell, never re-executed by CI. This module is that real
shell, made safe to re-execute automatically and repeatedly: it runs an
attacker-shaped command string through a genuine ``bash -c``, but with every
external command name it could possibly resolve replaced by an inert stand-in
that only records how it was invoked, never runs anything real.

Leading underscore, matching this repository's one existing precedent for a
shared (not directly pytest-collected) module --
``skills/executing-a-branch-plan/scripts/_gitapex_path_normalize.py``'s own
module docstring states the same "not a public entry point, a sibling
import" convention, even though (per that module's own docstring) this
prefix convention did not previously exist under ``tests/`` -- this is its
first use there. Unlike that precedent, this module also directly contains
its own proof-method tests (see "Proof-method tests" below): the plan this
implements explicitly sanctions "unit tests directly in this module or a
small accompanying test file", and pytest collects an explicitly-named file
regardless of its own filename pattern (confirmed directly against this
repository's own installed pytest before relying on it: a file that does not
match ``python_files`` is still fully collected when it is the literal path
handed to ``pytest`` on the command line -- only *directory* recursion
consults that glob). ``uv run --frozen pytest tests/_gitapex_bash_oracle.py
-v`` therefore runs real, green tests; a whole-``tests/`` directory sweep
never auto-discovers this file (by the same glob rule), which is expected
and intentional, not a gap -- callers needing this harness import its four
functions below directly.

Four building blocks, used together by every future consumer (task-2,
task-3, task-5, task-6 of the branch plan this belongs to; the fourth,
:func:`assert_closed_vocabulary`, only by the two generative ones):

* :func:`write_stand_ins` -- the "fixture/helper": given a list of watched
  tool names and a directory (always ``tmp_path``/``tmp_path_factory``-
  rooted by the caller -- never a fixed/shared path, since this repository's
  own ``pytest -n auto`` addopts runs every test file under pytest-xdist),
  writes one inert stand-in script per name into that directory.
* :func:`run_bash_oracle` -- the "runner": invokes a real ``bash -c
  <command>`` with its ``$PATH`` fully replaced (never prepended) by the
  stand-in directory, so the *only* commands that can resolve at all are the
  stand-ins just written.
* :func:`parse_capture_file` -- the "parser": turns the capture file's
  contents back into an ordered ``list[tuple[str, list[str]]]`` of
  ``(tool_name, args)`` observations.
* :func:`assert_closed_vocabulary` -- the "grammar-closure guard" (added
  under issue #1365's own Step 8 independent adversarial review): the two
  generative consumers (task-5/6's differential property tests) build every
  command they execute out of vocabularies they IMPORT from the classifier
  modules under test (``_DENIED_ADJACENT``, ``_WATCHED_TOOLS``,
  ``_WATCHED_VERBS``, ``_FETCH_EXEC_WRAPPERS``, ``_GIT_LONG_VALUE_FLAGS``,
  ...). Their "no free redirection / no backgrounding / no unbounded
  nesting" closure claim therefore rests on a property of files they do not
  own and this branch may not modify: that no entry in those tables
  contains a shell metacharacter or whitespace. That was prose, checked by
  a reviewer's eye, and nothing re-checked it when a table changed -- so a
  future entry such as ``("gh", "pr", "merge --admin")`` or anything
  carrying ``;``/``&``/``|``/``>`` would silently widen what a real
  ``bash -c`` is handed here. This turns that assumption into a gate the
  importing module runs at import time, failing loudly instead.

Capture-file format (binding for every future consumer of this module --
task-2/3/5/6 all depend on this exact shape)
-------------------------------------------
One JSON array per line, UTF-8, newline-terminated. Each array is the
invoked stand-in's own verbatim ``sys.argv``, exactly as bash's own
word-splitting/expansion handed the arguments to ``execve`` --
``argv[1:]`` is the generated command's real arguments to that tool word,
unmodified. ``argv[0]`` is deliberately *not* used as the tool name
directly: every stand-in is a ``#!``-scripted file, and Linux's own
shebang handling (``binfmt_script``) substitutes the resolved *absolute
path* execve was actually called with in place of whatever argv[0] bash
itself constructed (confirmed empirically against this module's own
stand-ins before relying on it -- bash's conceptual "command word as
typed" does not survive a shebang re-exec the way it would for a real ELF
binary). :func:`parse_capture_file` therefore reads each line back as
``(pathlib.Path(argv[0]).name, argv[1:])``, i.e. ``(tool_name, args)`` --
the stand-in's own *basename*, which is always exactly the tool name
:func:`write_stand_ins` named that file after, regardless of whether a
given shell/kernel reports argv[0] as a bare name or a full path.
``tool_name`` is *not* re-included inside ``args``. Lines are appended in
strict invocation order (one call per line), so the returned list
preserves the real order commands actually ran in, including when a
generated command chains more than one watched tool (e.g. ``a && b``,
``a; b``, ``a | b``).

Stand-ins are genuinely inert
------------------------------
Every stand-in :func:`write_stand_ins` writes is a tiny Python script (its
own shebang line points at ``sys.executable``'s own absolute path -- a
*literal* absolute path baked into the file at write time, since the
kernel resolves a shebang interpreter directly, never via the child's own
``$PATH`` -- so this keeps working even though that child's ``$PATH`` is
about to be fully replaced by :func:`run_bash_oracle` below) whose entire
body is: append ``json.dumps(list(sys.argv))`` as one line to the caller's
capture file, then exit 0. No ``eval``, no argument parsing, no branching
on its own input -- it cannot be made to do anything other than record how
it was called, regardless of what a generated command passes it.

The one exception is :func:`_write_self_backgrounding_stand_in` below,
private to this module's own timeout/process-group proof test (never used
by a real classifier consumer) -- see its own docstring for why it is
deliberately not inert.

Safety design of the runner
----------------------------
* ``bash`` itself is resolved to an absolute path exactly once, via
  ``shutil.which("bash")`` against the *current*, real, unrestricted
  process environment (memoized by :func:`resolve_bash`) -- never invoked
  by the bare name ``"bash"``, since by the time it actually runs, its own
  ``$PATH`` has already been fully replaced and a bare-name lookup
  (``os.execvpe``-style, which several subprocess code paths perform
  against whatever ``env`` mapping is passed in, not the parent's real
  environment) could not find a real ``bash`` there at all.
* The child's ``$PATH`` is set to *only* the stand-in directory -- never
  prepended to the real ``$PATH``, never a relative path -- and the rest of
  its environment is an explicit two-key minimal dict (``PATH``,
  ``LC_ALL=C``), never the parent's inherited ``os.environ``.
* The child runs in a disposable, empty working directory, distinct from
  both the stand-in directory and the capture file's own parent directory.
  :func:`run_bash_oracle` enforces the first half of that directly (it
  rejects ``cwd == stand_in_dir`` rather than silently tolerating an
  alias); the capture file's own location is NOT passed to it at all --
  only :func:`write_stand_ins` ever sees that path -- so keeping ``cwd``
  out of the capture file's parent directory is a caller convention (every
  caller in this repository roots ``cwd``, ``stand_in_dir`` and the capture
  file in one ``tmp_path``/``tmp_path_factory`` directory, with ``cwd`` its
  own subdirectory), not something this module can check. Stated exactly
  that way deliberately: an enforced check and a convention are not the
  same guarantee, and this docstring previously claimed the stronger one
  for both halves (corrected under issue #1365, Step 8 independent
  adversarial review).
* The child is launched in its own new process group/session
  (``start_new_session=True``): on a hard wall-clock timeout (``communicate
  (timeout=...)`` raising ``subprocess.TimeoutExpired``), the *whole group*
  is killed via ``os.killpg`` -- not only the direct ``bash`` child -- and
  then re-waited via a second ``communicate()`` call, so a generated command
  that backgrounds a child of its own cannot outlive the timeout.
* An optional ``preexec_fn`` resource-limit prologue
  (``resource.setrlimit`` on ``RLIMIT_CPU``/``RLIMIT_NPROC``) is applied by
  default as defense-in-depth against a pathological, fork-bomb-shaped
  generated command. This is explicitly a soft backstop, not this task's
  own closure of the generation grammar (that closure is task-5/6's job,
  not this module's) -- and it is not universally enforced: Linux does not
  apply ``RLIMIT_NPROC`` to a privileged (``CAP_SYS_RESOURCE``, in practice
  root) process at all, so :func:`_resource_limit_prologue` tolerates
  ``setrlimit`` failing or silently not being honored. The hard wall-clock
  timeout plus ``killpg`` above is the real, unconditional backstop; this is
  an additional layer on top of it, not a substitute for it.

pytest-xdist safety
--------------------
Nothing in this module hardcodes a stand-in directory, capture file, or
working directory -- every one of :func:`write_stand_ins` and
:func:`run_bash_oracle`'s own directory/path parameters is supplied by the
caller, which must derive it from the per-test ``tmp_path`` fixture (or
``tmp_path_factory`` for a factory-style variant), so two workers running
concurrently under this repository's own ``-n auto`` addopts never collide.
:func:`test_concurrent_invocations_use_isolated_paths` below proves this
directly.

Proof-method tests
-------------------
Four tests below prove the design claims above, each directly:

(a) :func:`test_stand_in_tool_resolves_but_real_system_binary_is_unreachable`
    -- a stand-in-only tool name resolves and runs; a real system binary
    absent from the stand-in directory (``ls``) does not resolve at all,
    confirming the real ``$PATH`` is genuinely unreachable, not merely
    shadowed.
(b) :func:`test_concurrent_invocations_use_isolated_paths` -- two
    concurrent oracle invocations, each given its own
    ``tmp_path_factory``-rooted directories, never share a stand-in
    directory or capture file and never observe each other's argv.
(c) :func:`test_timeout_kills_the_whole_process_group` -- a deliberately
    slow, self-backgrounding generated command is actually killed at the
    process-group level by the timeout, not only its direct ``bash``
    child: proven by recording the background grandchild's own pid and
    confirming both that the pid is no longer alive and that the
    grandchild never lived long enough to write its own "I survived"
    marker file.
(d) :func:`test_closed_vocabulary_guard_rejects_a_metacharacter_entry` --
    the grammar-closure guard actually rejects the adversarial table entry
    it exists to catch (a tool/verb word carrying ``;``, ``&``, ``|``,
    ``>``, a space, a backtick, ``$``, ...), and accepts every real
    vocabulary token both classifier tables carry today, so that closure
    claim is enforced rather than merely asserted in prose.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import pathlib
import re
import resource
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class OracleRun:
    """One real-bash invocation's outcome, from :func:`run_bash_oracle`.

    ``returncode`` mirrors ``subprocess.Popen.returncode``'s own type: a
    real (possibly negative, i.e. "killed by signal N") int once the
    process has actually exited, ``None`` only if it somehow has not (never
    observed in practice here, since both the success path and the
    timeout path always re-wait to completion before returning).
    """

    timed_out: bool
    returncode: int | None
    stdout: str
    stderr: str


@functools.lru_cache(maxsize=1)
def resolve_bash() -> str:
    """Absolute path to a real ``bash`` executable, resolved exactly once
    against the *current* (real, unrestricted) process's own ``$PATH``.

    Memoized rather than re-resolved per call: by the time
    :func:`run_bash_oracle` actually launches a child, that child's own
    ``$PATH`` has been fully replaced by the stand-in directory, so a
    fresh ``shutil.which("bash")`` call made *after* that replacement
    would (correctly, but unhelpfully) fail to find a real ``bash`` at
    all. Resolving once, early, against the real environment is the whole
    point.
    """
    path = shutil.which("bash")
    if path is None:
        raise RuntimeError(
            "no real 'bash' executable found on this system's own $PATH; the oracle harness requires one"
        )
    return path


def write_stand_ins(tool_names: Iterable[str], stand_in_dir: pathlib.Path, capture_file: pathlib.Path) -> None:
    """Write one genuinely inert stand-in script per name in ``tool_names``
    into ``stand_in_dir`` (created if missing). Each stand-in, however
    invoked, only appends its own ``sys.argv`` (as one JSON array, this
    module's own documented capture-file line format) to ``capture_file``
    and exits 0 -- no ``eval``, no interpretation of its own arguments, so
    it cannot be made to do anything else regardless of what a generated
    command passes it.

    ``stand_in_dir`` and ``capture_file`` are always caller-supplied and
    must be derived from the per-test ``tmp_path``/``tmp_path_factory``
    fixture -- never a fixed or shared path -- so this is safe under this
    repository's own ``pytest -n auto`` addopts.
    """
    stand_in_dir.mkdir(parents=True, exist_ok=True)
    source = _inert_stand_in_source(capture_file)
    for name in tool_names:
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            raise ValueError(f"unsafe stand-in tool name: {name!r}")
        script_path = stand_in_dir / name
        script_path.write_text(source, encoding="utf-8")
        script_path.chmod(0o700)


def _inert_stand_in_source(capture_file: pathlib.Path) -> str:
    """The stand-in script body shared by every name :func:`write_stand_ins`
    writes -- see this module's own "Stand-ins are genuinely inert" section
    above. The shebang is ``sys.executable``'s own absolute path (a literal
    baked in at write time, not looked up again at run time), since a
    shebang interpreter is always resolved by the kernel directly, never
    via the invoked process's own ``$PATH``."""
    return (
        f"#!{sys.executable}\n"
        "import json\n"
        "import sys\n"
        "\n"
        f'with open({str(capture_file)!r}, "a", encoding="utf-8") as fh:\n'
        '    fh.write(json.dumps(list(sys.argv)) + "\\n")\n'
    )


def _resource_limit_prologue(cpu_seconds: int, nproc: int) -> Callable[[], None]:
    """A ``preexec_fn`` applying ``RLIMIT_CPU``/``RLIMIT_NPROC`` inside the
    forked child, before it execs ``bash``. Defense-in-depth only, against
    a pathological fork-bomb-shaped generated command -- not a substitute
    for the generation grammar's own closure (task-5/6's job, not this
    module's), and not universally enforced: Linux does not apply
    ``RLIMIT_NPROC`` to a privileged process at all, and *neither*
    ``setrlimit`` call can succeed when the ambient process already carries
    a HARDER limit than the one requested here (lowering a hard limit is
    unprivileged, raising one is not -- so an ambient ``RLIMIT_CPU`` hard
    limit below ``cpu_seconds``, which a hardened CI runner or container
    can legitimately impose, makes this call raise ``ValueError``).

    BOTH calls therefore swallow their own failure rather than raising it
    (issue #1365, Step 8 independent adversarial review): an exception
    escaping a ``preexec_fn`` is re-raised in the PARENT as
    ``subprocess.SubprocessError``, which would turn every single oracle
    invocation in this repository's test suite into a hard error on such a
    host -- reproduced directly, by lowering this process's own
    ``RLIMIT_CPU`` hard limit to 2 and calling :func:`run_bash_oracle`
    (``SubprocessError: Exception occurred in preexec_fn.``), rather than
    assumed. Swallowing is sound precisely because the only ordinary
    failure mode is "the ambient limit is already at least as strict", and
    because the hard wall-clock timeout plus ``os.killpg`` in
    :func:`run_bash_oracle` is the real, unconditional backstop this is
    layered on top of, not a replacement for."""

    def _apply() -> None:
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        with contextlib.suppress(ValueError, OSError):
            resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))

    return _apply


def run_bash_oracle(
    command: str,
    *,
    stand_in_dir: pathlib.Path,
    cwd: pathlib.Path,
    timeout: float = 5.0,
    cpu_seconds: int = 5,
    nproc: int = 64,
    enable_resource_limits: bool = True,
) -> OracleRun:
    """Run ``command`` through a real ``bash -c`` with its own ``$PATH``
    fully replaced by ``stand_in_dir`` (never prepended to the real
    ``$PATH``), an otherwise-minimal environment (``LC_ALL=C`` only,
    never the parent's inherited ``os.environ``), and ``cwd`` as its
    working directory -- ``cwd`` must be a distinct, disposable, empty
    directory, neither ``stand_in_dir`` itself nor the capture file's own
    parent directory. Only the first of those two is actually checked here
    (``cwd == stand_in_dir`` raises, rather than being silently
    tolerated); the capture file's own path is never passed to this
    function at all, so the second is a caller convention this function
    cannot verify -- see the module docstring's own "Safety design of the
    runner" section.

    Enforces a hard wall-clock ``timeout`` (seconds): the child is launched
    in its own new process group/session (``start_new_session=True``), so
    on ``subprocess.TimeoutExpired`` the *whole group* is killed via
    ``os.killpg`` (not only the direct ``bash`` child) and then re-waited,
    guaranteeing a generated command cannot outlive this call by
    backgrounding a child of its own.

    ``enable_resource_limits`` (default on) additionally applies the
    ``RLIMIT_CPU``/``RLIMIT_NPROC`` defense-in-depth prologue documented on
    :func:`_resource_limit_prologue` above.
    """
    stand_in_dir = stand_in_dir.resolve()
    cwd = cwd.resolve()
    if stand_in_dir == cwd:
        raise ValueError("stand_in_dir and cwd must be distinct directories")
    if not cwd.is_dir():
        raise ValueError(f"cwd does not exist or is not a directory: {cwd}")

    bash_path = resolve_bash()
    env: dict[str, str] = {"PATH": str(stand_in_dir), "LC_ALL": "C"}
    preexec = _resource_limit_prologue(cpu_seconds, nproc) if enable_resource_limits else None

    process: subprocess.Popen[str] = subprocess.Popen(
        [bash_path, "-c", command],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        preexec_fn=preexec,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        with contextlib.suppress(ProcessLookupError):
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        stdout, stderr = process.communicate()
    return OracleRun(timed_out=timed_out, returncode=process.returncode, stdout=stdout, stderr=stderr)


def _proc_is_terminated(pid: int) -> bool:
    """True if ``pid`` is either gone entirely or a zombie (already
    exited, only awaiting reap by whatever process it was reparented to
    after its own parent died) -- used only by
    :func:`test_timeout_kills_the_whole_process_group` below. ``os.kill
    (pid, 0)`` alone cannot distinguish "genuinely still running" from
    "zombie, already terminated": a zombie's pid is not released, and
    ``ESRCH`` is only ever raised once the process is fully reaped, which
    on this system's own init is not guaranteed to happen promptly (or at
    all) for an orphaned grandchild -- confirmed directly by reproducing
    this exact scenario before relying on it, rather than assumed. Reading
    ``/proc/<pid>/stat``'s own state field instead distinguishes the two
    directly; a missing entry (process fully reaped between the check and
    now) counts as terminated too."""
    stat_path = pathlib.Path(f"/proc/{pid}/stat")
    try:
        contents = stat_path.read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError):
        return True
    # Format: "pid (comm) state ...". comm can itself contain spaces or
    # parentheses, so split on the LAST ")" to find the state field
    # reliably rather than assuming comm has none.
    state_field = contents.rsplit(")", 1)[-1].split()[0]
    return state_field == "Z"


# One shell word, drawn from a closed vocabulary: letters/digits, an
# optional leading `-`/`--` (flag names), and the four inert punctuation
# characters real tool/verb/flag words in these tables actually use
# (`.` in `example.invalid`, `_`, `-` in `apt-get`/`--raw-field`, `/` and
# `=` in a fused `--git-dir=/tmp/decoy`). Deliberately an ALLOW-list, not a
# metacharacter deny-list: a deny-list has to enumerate every one of bash's
# own special characters correctly to be sound, and silently admits any it
# forgets.
_CLOSED_VOCABULARY_WORD = re.compile(r"\A-{0,2}[A-Za-z0-9][A-Za-z0-9._/=-]*\Z")


def assert_closed_vocabulary(words: Iterable[str], source: str) -> None:
    """Fail loudly (``ValueError``) unless every word in ``WORDS`` is a
    single inert shell word safe to splice into a generated command string
    -- see this module's own "Four building blocks" docstring section for
    why the generative consumers need this and what it is guarding against.

    ``SOURCE`` names the vocabulary being checked (e.g.
    ``"gitapex_check_bash_safety._DENIED_ADJACENT"``) so a failure points
    at the table that drifted, not merely at the test that noticed.
    Consumers call this at IMPORT time, over every vocabulary they import
    from a module they do not own, so a drifted table is a collection
    error rather than a real ``bash -c`` running a wider string than the
    grammar's own documented closure allows."""
    for word in words:
        if not _CLOSED_VOCABULARY_WORD.fullmatch(word):
            raise ValueError(
                f"{source}: {word!r} is not a closed-vocabulary shell word -- a generative "
                "consumer of this harness splices it directly into a real `bash -c` command "
                "string, so it must not carry whitespace or any shell metacharacter"
            )


def parse_capture_file(capture_file: pathlib.Path) -> list[tuple[str, list[str]]]:
    """Parse ``capture_file`` (this module's own documented one-JSON-array-
    per-line format) back into an ordered ``list[tuple[str, list[str]]]``
    of ``(tool_name, args)`` observations, in the order the underlying
    stand-ins actually ran. ``tool_name`` is ``argv[0]``'s own basename,
    not the raw value -- see the module docstring's own "Capture-file
    format" section for why (Linux's shebang handling substitutes a
    resolved absolute path for whatever argv[0] bash itself constructed).
    Returns ``[]`` (never raises) if the file was never written -- the
    command's own real bash run resolved nothing at all, itself a
    meaningful, legitimate observation for a caller to assert on."""
    if not capture_file.exists():
        return []
    observations: list[tuple[str, list[str]]] = []
    for line in capture_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        argv = json.loads(line)
        if not isinstance(argv, list) or not argv:
            raise ValueError(f"malformed capture line (expected a non-empty JSON array): {line!r}")
        tool_name = pathlib.PurePath(str(argv[0])).name
        observations.append((tool_name, [str(item) for item in argv[1:]]))
    return observations


# --- Proof-method tests -----------------------------------------------------
#
# See this module's own "Proof-method tests" docstring section above for
# what each of the three proves and why. All three are collected the moment
# this file is passed to pytest directly (`pytest tests/_gitapex_bash_oracle.py
# -v`) regardless of not matching pytest's own `python_files` glob, since
# that glob only gates *directory* recursion, not an explicitly-named path --
# confirmed directly against this repository's own installed pytest before
# relying on it (see the module docstring's own opening section).


def test_stand_in_tool_resolves_but_real_system_binary_is_unreachable(tmp_path: pathlib.Path) -> None:
    """(a) A stand-in-only tool name resolves and its stub actually runs
    (recording its own argv); a real system binary absent from the
    stand-in directory (``ls``) does not resolve at all -- exit 127,
    bash's own "command not found" -- confirming the child's ``$PATH`` is
    genuinely and fully replaced, never merely prepended to the real one
    (a prepend would still let `ls` resolve off the real system PATH
    behind the stand-in directory)."""
    stand_in_dir = tmp_path / "stand_ins"
    capture_file = tmp_path / "capture.jsonl"
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    write_stand_ins(["mytool"], stand_in_dir, capture_file)

    resolved = run_bash_oracle("mytool --flag value", stand_in_dir=stand_in_dir, cwd=cwd)
    assert not resolved.timed_out
    assert resolved.returncode == 0, resolved.stderr
    assert parse_capture_file(capture_file) == [("mytool", ["--flag", "value"])]

    unresolved = run_bash_oracle("ls /", stand_in_dir=stand_in_dir, cwd=cwd)
    assert not unresolved.timed_out
    assert unresolved.returncode == 127, (unresolved.returncode, unresolved.stderr)
    assert "not found" in unresolved.stderr


def test_concurrent_invocations_use_isolated_paths(tmp_path_factory: pytest.TempPathFactory) -> None:
    """(b) Two concurrent oracle invocations, each rooted at its own
    ``tmp_path_factory``-minted directory (the same mechanism this
    repository's own ``-n auto`` pytest-xdist run gives each worker),
    never share a stand-in directory or capture file, and each only ever
    observes its own argv -- never the other's."""

    def _one(worker_id: str) -> tuple[pathlib.Path, list[tuple[str, list[str]]]]:
        base = tmp_path_factory.mktemp(f"oracle_{worker_id}")
        stand_in_dir = base / "stand_ins"
        capture_file = base / "capture.jsonl"
        cwd = base / "cwd"
        cwd.mkdir()
        write_stand_ins(["mytool"], stand_in_dir, capture_file)
        # enable_resource_limits=False here: this test's own two calls run
        # concurrently from two Python threads within one process (below),
        # and Python's own subprocess docs flag `preexec_fn` (which forks)
        # combined with a multi-threaded parent as unsafe in general (a
        # sibling thread could hold a lock the single-threaded post-fork
        # child can then never release) -- irrelevant to what this test
        # itself is proving (path/capture-file isolation, not resource
        # limits), and a real classifier consumer never calls
        # `run_bash_oracle` from more than one Python thread at a time in
        # the first place (pytest-xdist parallelism is cross-*process*,
        # not cross-thread within one worker).
        run_bash_oracle(f"mytool {worker_id}", stand_in_dir=stand_in_dir, cwd=cwd, enable_resource_limits=False)
        return capture_file, parse_capture_file(capture_file)

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_alpha = pool.submit(_one, "alpha")
        future_beta = pool.submit(_one, "beta")
        capture_alpha, observed_alpha = future_alpha.result()
        capture_beta, observed_beta = future_beta.result()

    assert capture_alpha != capture_beta
    assert observed_alpha == [("mytool", ["alpha"])]
    assert observed_beta == [("mytool", ["beta"])]


@pytest.mark.parametrize(
    "bad_word",
    [
        "merge --admin",  # whitespace: two words where the grammar assumes one
        "install;touch",
        "pip&",
        "gh|cat",
        "install>out",
        "install<in",
        "$(id)",
        "`id`",
        "a'b",
        'a"b',
        "a\\b",
        "a*b",
        "",
    ],
)
def test_closed_vocabulary_guard_rejects_a_metacharacter_entry(bad_word: str) -> None:
    """(d) The grammar-closure guard rejects exactly the adversarial table
    entry it exists to catch -- an imported classifier-table word carrying
    whitespace or a shell metacharacter, which a generative consumer would
    otherwise splice straight into a real ``bash -c`` string -- while
    still accepting each SHAPE of token those tables really carry today
    (bare word, hyphenated tool, short/long flag, fused ``=`` value,
    dotted host name). The guard's application to the live tables
    themselves is not here but at the two differential modules' own import
    time, over the real imported objects; this test proves the guard those
    modules call actually discriminates."""
    with pytest.raises(ValueError, match="closed-vocabulary shell word"):
        assert_closed_vocabulary(["pip", bad_word], "test-source")

    # ... and every real token in use today passes, so the guard is a real
    # constraint on drift, not a tautology that would reject the status quo.
    assert_closed_vocabulary(
        [
            "gh",
            "pr",
            "merge",
            "apt-get",
            "pip3",
            "--raw-field",
            "-X",
            "--git-dir=/tmp/decoy",
            "POST",
            "example.invalid",
        ],
        "test-source",
    )


def _write_self_backgrounding_stand_in(
    name: str,
    stand_in_dir: pathlib.Path,
    pidfile: pathlib.Path,
    marker_file: pathlib.Path,
    sleep_seconds: float,
) -> None:
    """Deliberately NOT inert -- unlike :func:`write_stand_ins`'s own
    stand-ins, used only by
    :func:`test_timeout_kills_the_whole_process_group` below, never by a
    real classifier consumer. Forks a background grandchild that (1)
    records its own pid to ``pidfile`` immediately, then (2) sleeps
    ``sleep_seconds`` before writing ``marker_file`` -- reaching that
    write is proof the grandchild was never killed. The direct child
    (this stand-in's own process) also sleeps ``sleep_seconds``, so the
    whole invocation -- and thus the grandchild, still in the same
    process group since it never calls ``setpgid`` -- is still alive when
    the oracle's own timeout should fire."""
    stand_in_dir.mkdir(parents=True, exist_ok=True)
    source = (
        f"#!{sys.executable}\n"
        "import os\n"
        "import time\n"
        "\n"
        "child_pid = os.fork()\n"
        "if child_pid == 0:\n"
        f'    with open({str(pidfile)!r}, "w", encoding="utf-8") as fh:\n'
        "        fh.write(str(os.getpid()))\n"
        f"    time.sleep({sleep_seconds!r})\n"
        f'    with open({str(marker_file)!r}, "w", encoding="utf-8") as fh:\n'
        '        fh.write("survived")\n'
        "    os._exit(0)\n"
        "else:\n"
        f"    time.sleep({sleep_seconds!r})\n"
    )
    path = stand_in_dir / name
    path.write_text(source, encoding="utf-8")
    path.chmod(0o700)


@pytest.mark.slow
def test_timeout_kills_the_whole_process_group(tmp_path: pathlib.Path) -> None:
    """(c) A deliberately slow, self-backgrounding generated command is
    actually killed at the process-group level by the oracle's own
    timeout -- not only its direct ``bash`` child. Proven two independent
    ways: the background grandchild's own recorded pid is confirmed
    terminated (dead or zombie, never still genuinely running -- see
    :func:`_proc_is_terminated`'s own docstring for why a bare ``os.kill
    (pid, 0)`` cannot make this distinction), and it never lived long
    enough to write its own survival marker file. Marked ``slow`` (spawns
    a real subprocess and deliberately sleeps across it) per this
    repository's own registered marker, unlike (a)/(b) above which
    complete in well under a second."""
    stand_in_dir = tmp_path / "stand_ins"
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    pidfile = tmp_path / "child.pid"
    marker_file = tmp_path / "survived.marker"
    sleep_seconds = 1.5
    _write_self_backgrounding_stand_in("slowtool", stand_in_dir, pidfile, marker_file, sleep_seconds)

    result = run_bash_oracle("slowtool", stand_in_dir=stand_in_dir, cwd=cwd, timeout=0.4)
    assert result.timed_out

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not pidfile.exists():
        time.sleep(0.02)
    assert pidfile.exists(), "background grandchild never even started"
    child_pid = int(pidfile.read_text(encoding="utf-8").strip())

    # Killed (dead or zombie), not merely orphaned-and-still-running -- see
    # _proc_is_terminated's own docstring for why a bare `os.kill(pid, 0)`
    # is not sufficient here (a zombie's pid persists until reaped). A pid
    # reused for an unrelated process within this ~2-second window is not a
    # realistic risk on this system (a handful of processes total, a large
    # pid space).
    assert _proc_is_terminated(child_pid), f"background grandchild (pid {child_pid}) is still actually running"

    # Second, independent confirmation: wait comfortably past the point the
    # grandchild would have woken up and written its own marker had it
    # survived, then confirm it never did.
    time.sleep(sleep_seconds)
    assert not marker_file.exists(), "background grandchild survived the process-group kill"
