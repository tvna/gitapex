#!/usr/bin/env python3
"""Shared destination-refspec git-fetch helpers for the ``local`` gate plane
(issue #1345).

**The defect this module exists to close.** A *source-only* ``git fetch
<remote> <branch>`` -- the form both `gitapex_gate_behind_base.py`'s own
``fetch_base`` and ``.claude/hooks/session-start.sh`` used before issue
#1345, which this same issue's fix also corrects in both places -- exits
0 in a restricted-refspec clone (the shape ``git clone --single-branch
--branch`` produces) without materializing ``refs/remotes/<remote>/<branch>``
at all.
Git only auto-creates a remote-tracking ref when the fetched source matches
a pattern in the repository's *configured* ``remote.<remote>.fetch``
refspec, and a restricted-refspec clone's configured refspec only covers
the one branch it was cloned with. Live-verified, not assumed: the
identical fetch command against a repo whose configured refspec is the
ordinary wildcard (``+refs/heads/*:refs/remotes/origin/*``) does correctly
create the ref -- the determining factor is the configured refspec's
shape, not whether the branch was fetched before. Only a **destination
refspec** (``+refs/heads/<branch>:refs/remotes/<remote>/<branch>``) works
in both cases, verified live in two experiments: it fixes the broken
restricted-refspec case and is a no-op-safe, no-regression replacement in
the already-working wildcard-refspec case.

**Why this lives in its own module rather than in either caller.**
``gitapex_gate_behind_base.py`` (issue #985) and the new
``gitapex_run_base_diff.py`` (issue #1345) both need to fetch a base
branch this same correct way and both need the same "never trust the
fetch's exit code alone" re-verification discipline. Duplicating the git
subprocess plumbing in both would leave two copies to drift apart, the
same duplication-then-drift risk ``_gitapex_schema_validation.py``'s own
docstring names for its two callers. This module follows the same
``_gitapex_*.py`` private-helper convention as the five that already exist
in this directory (``_gitapex_argv_safety.py``, ``_gitapex_github_http.py``,
``_gitapex_rulesets.py``, ``_gitapex_schema_validation.py``,
``_gitapex_vocabulary_lock.py``): a private module name, public function
names, its own dedicated test file
(``tests/test_gitapex_base_ref.py``), and an ``error_cls`` parameter on
every function that can fail so each caller keeps raising its own
already-tested exception type (``GateError`` for
``gitapex_gate_behind_base.py``, ``DiffProducerError`` for
``gitapex_run_base_diff.py``) rather than converging on one generic type
neither caller's existing tests expect.

**Message-text stability.** ``gitapex_gate_behind_base.py`` had passing
tests asserting on ``fetch_base``'s exact `GateError` message text before
this issue (e.g. matching ``"git fetch"``, ``"cannot run git to fetch"``,
``"cannot find a common ancestor"``). This module's ``run_git`` and
``fetch_destination_refspec`` deliberately keep the same ``label``/message
shape those tests already pin -- only the fetch's own refspec argument
changes, never the label text built from ``remote``/``branch`` -- so
``gitapex_gate_behind_base.py``'s pre-#1345 test suite keeps passing
unmodified once it delegates here.

**The personal-fork-remote risk, mitigated not closed.** If a
contributor's own ``origin`` remote is a personal fork rather than the
canonical repository, silently fetching and comparing against that fork's
own history produces a plausible-looking but wrong verdict --
``gitapex_gate_behind_base.py``'s own docstring already names this risk
and never acted on it. ``announce_fetch`` prints the fetched remote's
resolved URL to stderr before every fetch this module performs, matching
that gate's own accepted treatment of the identical risk class. This is a
disclosure, not a detection: a contributor who does not read stderr still
gets the wrong verdict silently -- named here rather than solved.

**The peeled-ref probe, and the same shadowing gap in actual usage.**
``git rev-parse --verify --quiet <ref>`` alone reports a dangling ref
(the object it points at is missing) or a same-named tag shadowing a
missing branch ref as "resolves" -- a pre-existing gap in the raw
command this issue's fix already replaces, not a regression it
introduces. ``peeled_ref_exists`` uses the peeled ``<ref>^{commit}``
form instead, which fails to resolve in both of those cases, closing
this gap for the existence check itself. That alone does not protect a
caller's later ``merge-base``/``rev-list``/``diff`` invocation, though:
this module's own :func:`require_common_ancestor` resolves whatever
``base_ref`` string a caller passes using git's ordinary, non-peeled
disambiguation order, which checks ``refs/tags/<name>`` before
``refs/remotes/<name>`` for a bare, ambiguous name -- a same-named local
tag can still silently win there even though ``peeled_ref_exists``
correctly reported the real branch ref as present, producing a
plausible-looking but wrong comparison (live-reproduced: a false "up to
date" verdict from ``gitapex_gate_behind_base.py``'s own
``count_behind``, issue #1345 follow-up review). Both of this module's
callers close this the same way :func:`peeled_ref_exists` does: passing
the fully-qualified ``refs/remotes/<remote>/<branch>`` -- never the bare
``<remote>/<branch>`` form -- to every git command that actually walks
history, not only to the existence probe.

**The shallow-clone case.** A shallow clone (``--depth N``, as opposed to
a restricted-refspec clone) can fetch a base branch correctly and still
have no common ancestor with ``HEAD``, because its own truncated history
does not reach far enough back. Live-verified: a bare ``git merge-base``
call on such a repo prints nothing to stderr at all on failure, so
``require_common_ancestor``'s own message is the only informative signal
available -- callers needing to distinguish this from a missing-ref
failure must call it explicitly, before attempting the real diff/compare.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from typing import TextIO

# Canonical timeout for one git subprocess call (fetch, rev-parse,
# merge-base, or remote get-url). Both callers of this module import this
# constant rather than redefining 60 as a second literal -- matches
# gitapex_gate_behind_base.py's own pre-#1345 GIT_TIMEOUT_SECONDS value and
# rationale (generous for a local call or a fetch over an ordinary network,
# while still failing loudly on a hung connection rather than blocking
# indefinitely).
GIT_TIMEOUT_SECONDS = 60


class BaseRefError(Exception):
    """Fallback error class for direct/standalone use of this module. Every
    real call site in this repository passes its own ``error_cls`` instead
    (``GateError``, ``DiffProducerError``), so each caller's own tests keep
    catching the exception type they already assert on -- mirrors
    ``_gitapex_schema_validation.load_json_or_raise``'s own ``error_cls``
    parameterization for the identical reason."""


def destination_refspec(remote: str, branch: str) -> str:
    """The destination-refspec form issue #1345 requires:
    ``+refs/heads/<branch>:refs/remotes/<remote>/<branch>``. A source-only
    ``git fetch <remote> <branch>`` exits 0 in a restricted-refspec clone
    but does not materialize ``refs/remotes/<remote>/<branch>`` at all --
    see this module's own docstring for why. Only ``remote`` is used to
    name the destination ref (matching git's own default remote-tracking
    layout); ``remote`` is not otherwise validated here, since every call
    site already resolves it from a fixed, repository-owned constant
    (``BASE_REMOTE`` in both callers today), never from external input."""
    return f"+refs/heads/{branch}:refs/remotes/{remote}/{branch}"


def run_git(
    root: pathlib.Path,
    args: list[str],
    *,
    label: str,
    timeout: int,
    error_cls: type[Exception],
    stdin_text: str | None = None,
    # function-body-test-coverage: WAIVED: the added `stdin_text` parameter
    # (issue #1212) is exercised by the pre-existing, extensively-updated
    # tests/test_gitapex_base_ref.py (test_run_git_* mentions `run_git` by
    # name repeatedly) -- but gitapex_gate_function_body_test_coverage.py's
    # own _stem() keeps this module's leading underscore
    # ("_gitapex_base_ref"), so it looks for tests/test__gitapex_base_ref.py
    # (double underscore) rather than this repository's own actual,
    # established single-underscore convention for a `_`-prefixed private
    # helper module's test file. A genuine gate limitation, not a real
    # coverage gap -- disclosed here rather than worked around by adding a
    # second, oddly-named test file just to match the gate's own stem
    # computation.
) -> subprocess.CompletedProcess[str]:
    """Run ``git -C root <args>`` and return the completed process,
    regardless of its exit code -- callers decide what a nonzero
    ``returncode`` means for their own step. Raises ``error_cls`` for every
    way the subprocess itself can fail to produce one: a missing ``git``
    executable, a hang past ``timeout``, or any other subprocess-layer
    failure. Message shape (``"cannot run git to {label}: ..."`` /
    ``"git {label} timed out after {timeout}s"``) is byte-identical to
    ``gitapex_gate_behind_base.py``'s own pre-#1345 ``_run_git``, which
    this function replaces there -- existing tests asserting on that text
    keep passing unmodified.

    ``stdin_text`` feeds a git subcommand that reads its input from stdin
    (``git stripspace``, this module's own third caller
    ``gitapex_gate_commit_citation.py``) -- added here rather than as a
    second, near-identical ``subprocess.run`` wrapper in that caller,
    which is precisely the duplicate-then-drift this module exists to
    prevent. Default ``None`` leaves ``subprocess.run``'s own stdin
    handling exactly as it was for every pre-existing caller: no pipe is
    opened and no behavior changes.

    ``errors="replace"`` rather than ``text=True``'s own strict default,
    matching ``gitapex_gate_behind_base.py``'s documented regression: a
    byte sequence on stdout/stderr that is not valid UTF-8 must not raise
    ``UnicodeDecodeError`` (a ``ValueError``) from inside this call, which
    would otherwise escape as an uncaught exception distinct from this
    module's own documented error handling."""
    try:
        # S603/S607 waived: a fixed argv list with no shell, and `git` is
        # intentionally resolved from PATH -- pinning an absolute path
        # would break the three environments this has to run in (GitHub
        # runner, the nix devShell, a contributor's machine). Same
        # rationale as every other gate script in this file's family.
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(root), *args],  # noqa: S607
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout,
            input=stdin_text,
        )
    except subprocess.TimeoutExpired as error:
        raise error_cls(f"git {label} timed out after {timeout}s") from error
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise error_cls(f"cannot run git to {label}: {error}") from error


def remote_url(root: pathlib.Path, remote: str, *, timeout: int = GIT_TIMEOUT_SECONDS) -> str:
    """``git remote get-url <remote>``, stripped. Raises :class:`BaseRefError`
    if the remote is not configured or the call fails -- always this
    module's own fallback error class, never a caller's ``error_cls``,
    because ``announce_fetch`` (the only caller) treats a resolution
    failure here as non-fatal to the fetch it precedes and needs to
    distinguish "could not resolve the URL" from any error a caller's own
    ``error_cls`` would otherwise signal as fatal. Never touches the
    network -- ``remote get-url`` only reads local config."""
    result = run_git(
        root,
        ["remote", "get-url", remote],
        label=f"resolve the URL for {remote}",
        timeout=timeout,
        error_cls=BaseRefError,
    )
    if result.returncode != 0:
        raise BaseRefError(f"git remote get-url {remote} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def announce_fetch(
    root: pathlib.Path, remote: str, branch: str, *, timeout: int = GIT_TIMEOUT_SECONDS, file: TextIO | None = None
) -> None:
    """Print ``"gitapex: fetching {branch} from {remote} ({url})"`` to
    ``file`` (default: ``sys.stderr``, resolved at call time -- not bound
    as a default-argument value, which would capture the stream object
    present at *module import* time and silently escape a test's own
    ``capsys``/``sys.stderr`` redirection) before the real fetch runs --
    mitigates (does not close) the personal-fork-remote risk this module's
    own docstring names. Never raises: a ``remote_url`` failure degrades
    to ``"(url unresolved: <error>)"`` in the printed line rather than
    aborting the fetch this notice exists to accompany, not gate."""
    try:
        url = remote_url(root, remote, timeout=timeout)
    except BaseRefError as error:
        url = f"(url unresolved: {error})"
    print(f"gitapex: fetching {branch} from {remote} ({url})", file=file if file is not None else sys.stderr)


def fetch_destination_refspec(
    root: pathlib.Path, remote: str, branch: str, *, timeout: int = GIT_TIMEOUT_SECONDS, error_cls: type[Exception]
) -> None:
    """Fetch ``branch`` from ``remote`` into ``refs/remotes/<remote>/<branch>``
    using the destination-refspec form (issue #1345) -- never falls back
    to a source-only fetch. Raises ``error_cls`` -- never a silent
    no-op -- on any fetch failure: an offline machine, an unreachable
    remote, an auth failure, or a hang. Calls :func:`announce_fetch` first
    (the personal-fork-remote mitigation). Does NOT itself verify the ref
    now resolves afterward -- issue #1345's own "never trust the fetch's
    exit code alone" requirement -- callers needing that guarantee call
    :func:`peeled_ref_exists` afterward themselves."""
    announce_fetch(root, remote, branch, timeout=timeout)
    refspec = destination_refspec(remote, branch)
    result = run_git(
        root, ["fetch", remote, refspec], label=f"fetch {remote} {branch}", timeout=timeout, error_cls=error_cls
    )
    if result.returncode != 0:
        raise error_cls(f"git fetch {remote} {branch} failed: {result.stderr.strip()}")


def peeled_ref_exists(
    root: pathlib.Path,
    remote: str,
    branch: str,
    *,
    timeout: int = GIT_TIMEOUT_SECONDS,
    error_cls: type[Exception] = BaseRefError,
) -> bool:
    """Whether ``refs/remotes/<remote>/<branch>`` resolves to a real commit
    right now -- ``git rev-parse --verify --quiet <ref>^{commit}``, the
    peeled form that closes the dangling-ref/tag-shadowing gap this
    module's own docstring names (a bare ``rev-parse --verify --quiet
    origin/main`` reports either as "resolves"; the peeled ``^{commit}``
    form does not). Returns ``False`` for an ordinary "does not exist yet"
    (git's own nonzero exit from ``rev-parse``) -- a probe, not a fatal
    check. Still raises ``error_cls`` for a subprocess-layer failure (a
    missing ``git`` executable, a hang): that is not "the ref is missing",
    it is "this check itself could not run," and conflating the two would
    let a broken environment read as a merely-unfetched ref."""
    result = run_git(
        root,
        ["rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{branch}^{{commit}}"],
        label=f"verify refs/remotes/{remote}/{branch}",
        timeout=timeout,
        error_cls=error_cls,
    )
    return result.returncode == 0


def require_common_ancestor(
    root: pathlib.Path, base_ref: str, *, timeout: int = GIT_TIMEOUT_SECONDS, error_cls: type[Exception]
) -> None:
    """Raise ``error_cls`` when ``git merge-base`` cannot find a common
    ancestor between ``base_ref`` and ``HEAD``. Extracted verbatim
    (message text included) from ``gitapex_gate_behind_base.py``'s
    pre-#1345 module-local ``_require_common_ancestor``, shared here
    because ``gitapex_run_base_diff.py`` needs this exact check for its
    own "fetched but still no merge base" (shallow clone) ACM row, and
    duplicating it in two files is exactly the drift this module exists to
    prevent -- confirmed live (not assumed) that a bare ``git merge-base``
    call prints nothing to stderr on a shallow clone with no common
    ancestor, so this check's own message is the only informative signal
    available before a caller's real diff/compare attempt.

    Checked explicitly, before a caller's own rev-list/diff call: unrelated
    histories do not make ``git rev-list --left-right --count
    base_ref...HEAD`` (or ``git diff --merge-base base_ref HEAD``) fail
    outright -- it silently returns a numeric ahead/behind pair, or an
    empty diff, for the *empty* merge base, which would otherwise produce
    a plausible-looking but meaningless result instead of the honest "this
    comparison cannot be trusted" signal this case actually needs. Verified
    directly against a real orphan-history pair and a real shallow clone,
    not assumed.

    The raised message deliberately does not assert *why* no common
    ancestor was found -- a nonzero ``merge-base`` exit has more than one
    real cause (genuinely unrelated histories, ``base_ref`` never fetched
    locally, or a shallow clone whose truncated history does not reach far
    enough back), and this function cannot distinguish them from the exit
    code alone. Naming one as though it were established would mislead a
    caller debugging a shallow-clone or missing-ref case toward the wrong
    fix; git's own stderr, appended verbatim, carries whatever specificity
    is actually available (often none, for the shallow-clone case)."""
    result = run_git(
        root,
        ["merge-base", base_ref, "HEAD"],
        label=f"find a common ancestor with {base_ref}",
        timeout=timeout,
        error_cls=error_cls,
    )
    if result.returncode != 0:
        raise error_cls(
            f"cannot find a common ancestor between {base_ref} and HEAD -- unrelated histories, "
            f"{base_ref} not yet fetched, or a shallow clone: {result.stderr.strip()}"
        )
