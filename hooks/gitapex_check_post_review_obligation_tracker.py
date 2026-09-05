#!/usr/bin/env python3
"""PostToolUse state writer backing the review-thread-resolution +
mergeable_state-verification obligation (issue #1209).

CLAUDE.md section 3 states a turn-terminal obligation: "After a fix push
that addresses a review thread, explicitly call
mcp__github__resolve_review_thread to resolve the thread; then verify
mergeable_state before closing the turn." Nothing backed this
deterministically -- hooks/hooks.json carried zero Stop entries, so the
obligation depended solely on the agent remembering it.

Design (settled on issue #1209, not guessed at implementation time): a
marker-file state machine. This script is the writer half, invoked as a
PostToolUse hook (matcher: Bash|mcp__(github|plugin_github_github)__resolve_review_thread|
mcp__(github|plugin_github_github)__pull_request_read); hooks/gitapex_check_stop_review_obligation.py
is the reader half, invoked as a Stop hook. Neither half makes its own
GitHub API call -- this script reads only what the already-executed tool
call itself returned (its own tool_response), reusing the pattern
hooks/gitapex_check_post_write_provenance.py already established (issue
#908: a PostToolUse hook's stdin payload does carry the tool's actual
result). The Stop hook in turn reads only this state file, never the
network -- see that module's own docstring for the full split.

State file: ``${TMPDIR:-/tmp}/gitapex-review-obligation-<session_id>.json``,
deliberately outside the git work tree (never pollutes `git status`) and
keyed by session_id (stdin's own `session_id` field) so concurrent
sessions in different repos/worktrees never collide. Session-scoped, not
durable: a restarted session loses in-flight tracking, a disclosed,
deliberately-accepted false-negative (the Stop hook goes silent, never
silently wrong) -- see issue #1209's own Acceptance Criteria Map residual
risk for the full reasoning against a git-tracked alternative.

Fields:
    push_detected: bool -- a git-push Bash call was classified this cycle.
    target_pr: str | None -- "#<number>" or "<owner>/<repo>#<number>" for
        the PR this cycle's most recent pull_request_read call named;
        None until the first such call after a push. Switching to a
        different PR than the one currently tracked (including the very
        first observation) resets open_review_threads/resolve_calls/
        mergeable_checked to their initial values -- see `_pr_key` and
        `handle_pull_request_read`'s own docstring for why this is a
        deliberate design choice, not an incidental reset, and for the
        residual gap it does not close. "Different PR" is decided by
        `_same_pr`, not plain string equality: a bare "#1209" and a
        qualified "tvna/gitapex#1209" naming the same pull number are
        the same PR, tolerating owner/repo appearing on some calls and
        not others (see `_same_pr`'s own docstring for the bug this
        closes -- a third independent-review round found plain equality
        treated the identical PR, observed with and without owner/repo
        across two calls, as a switch).
    open_review_threads: int | None -- unresolved-thread count last
        observed from a get_review_comments response for `target_pr`;
        None means "never observed this cycle," not "zero."
    resolve_calls: int -- how many successful (non-error-response)
        resolve_review_thread calls fired since `target_pr` was last set
        (by the most recent PR switch, or the last push_detected reset,
        whichever is more recent).
    mergeable_checked: bool -- a pull_request_read(method="get") response
        for `target_pr` carrying mergeable_state was observed since
        `target_pr` was last set.

Three tool shapes update this file:

- Bash: reuses hooks/gitapex_check_bash_safety.py's own `classify()` --
  the same token-based, quote-splitting-resistant classifier
  hooks/check-bash-safety.sh already relies on for its own git-push
  provenance-scan gate -- rather than re-implementing git-push detection.
  `classify(command).is_git_push` true resets the state file to a fresh
  pending cycle (push_detected=true, target_pr unset, everything else
  cleared) -- deliberately unconditional on the tool_response (a denied/
  failed push still means the agent intended one), matching this
  module's own fail-toward-more-tracking posture.
- mcp__github__resolve_review_thread: increments resolve_calls, but only
  once `target_pr` is already set (a push happened AND at least one
  pull_request_read has already run this cycle -- see `_pr_key`'s own
  docstring for why resolve_review_thread's own arguments cannot
  establish `target_pr` by themselves, a residual gap disclosed below,
  not closed by this design) and only when the call's own tool_response
  does not report an error (`_reports_error`, mirroring
  hooks/gitapex_check_post_write_provenance.py's own marker vocabulary)
  -- independent review found a failed/rejected resolve call was
  previously counted identically to a successful one.
- mcp__github__pull_request_read: dispatches on tool_input.method, after
  first resolving/checking `target_pr` via `_pr_key(tool_input)`. A call
  naming a PR other than the one currently tracked -- including the very
  first pull_request_read call this cycle, which always "switches" from
  no tracked PR at all -- makes that PR the new `target_pr` and resets
  open_review_threads/resolve_calls/mergeable_checked, discarding
  whatever was tracked against the previous PR (see
  `handle_pull_request_read`'s own docstring for why a two-round
  independent review settled on always-reset over the first version's
  once-locked-never-updates design, and what residual gap even this
  still leaves open). get_review_comments records the unresolved-thread
  count, read out of the tool's own tool_response (unwrapped via
  `_unwrap_tool_response`, the same MCP content-envelope shapes
  hooks/gitapex_check_post_write_provenance.py's own response_payload()
  documents, generalized to also accept a bare list -- issue #908's own
  observed envelope is a list of text blocks, and get_review_comments'
  own return value is itself thread-shaped data that may or may not be a
  list at the top level, so this cannot assume dict the way that sibling
  helper does) by recursively counting every dict carrying
  `isResolved: false` -- deliberately shape-tolerant beyond just the MCP
  envelope (walks the whole unwrapped tree rather than assuming one
  fixed thread-list shape), since the exact response envelope is the MCP
  server's own contract, not this repository's (the identical fragility
  issue #908 already named). method get sets mergeable_checked when the
  unwrapped response tree contains a `mergeable_state`/`mergeableState`
  key anywhere.

Known, disclosed limitations (not fixed here):

- get_review_comments' pagination (perPage/after) is not followed -- a PR
  with more unresolved threads than fit in one page undercounts
  `open_review_threads` rather than following pageInfo.hasNextPage, since
  this module never makes its own API call. Undercounting is the safer
  direction (it can only make the Stop hook LESS strict, never let a
  genuinely-unresolved thread silently count as resolved), but is named
  here rather than left implicit.
- Neither `target_pr` establishment nor resolve_review_thread's own
  counting is grounded in which PR the actual `git push` targeted --
  there is no field on any of these three tool calls that names the
  pushed branch's own PR directly, and this module does not attempt to
  resolve one from the push command's own branch argument (a materially
  larger change than the two independent-review rounds' own fixes, per
  issue #1209's own PR body). `target_pr` is therefore a heuristic --
  whichever PR the agent's own pull_request_read calls most recently
  named -- not a verified fact, and resolve_calls counts every
  successful resolve_review_thread call since target_pr was last set
  regardless of which PR's thread it actually resolved (that tool's own
  arguments carry a thread node ID, never a PR number). An agent that
  fully walks an entirely unrelated PR's review flow (calls
  get_review_comments and get, and resolve_review_thread, against a PR
  that was never pushed to) still satisfies this gate for that PR --
  the always-reset-on-switch design (see above) closes the specific gap
  a second independent-review round found and reproduced (a wrong first
  PR permanently blocking the real one), not this broader one.
- The entire gate lives in state the same agent it gates can freely
  read, tamper with, or delete (a third independent-review round's own
  security-axis finding, confidence 0.9): the state-file path pattern
  and its sanitization are both readable in this module's own source,
  and nothing beyond ordinary filesystem permissions stops an agent
  from clearing or rewriting it directly. This is not a gap specific to
  this module -- it is a property this repository's entire hooks-as-
  deterministic-gate architecture already shares (an agent with Bash
  access can equally well edit or delete `hooks/check-bash-safety.sh`,
  `hooks/hooks.json`, or this very file), and is out of scope to close
  here: these hooks are a process safeguard against an honest agent
  forgetting a step, not a sandboxing boundary against one that has
  already decided to defeat its own tooling -- CLAUDE.md's own defense-
  in-depth framing (hooks are one layer among several, not the sole
  enforcement mechanism) already names this posture. Disclosed, not
  fixed, the same as the heuristic limitation above.
- `_reports_error`'s marker vocabulary (`status`/`is_error`/`isError`)
  may not recognize every failure shape the GitHub MCP server's
  `resolve_review_thread` call can actually return -- a raw GraphQL
  `{"errors": [...]}` array, in particular, carries none of those three
  keys. Unconfirmed (a third independent-review round's own security-axis
  finding, confidence 0.45, explicitly not verified against the live MCP
  server's actual envelope): this vocabulary already mirrors
  hooks/gitapex_check_post_write_provenance.py's own, already-merged
  `_reports_error()`, so if this gap is real it is not new to this
  module. Not fixed here absent primary-source confirmation of the
  actual failure envelope.
- `_contains_mergeable_state`'s recursive tree walk matches
  `mergeable_state`/`mergeableState` anywhere in the unwrapped response,
  not only on the target PR's own top-level object; a response embedding
  an unrelated nested object that happens to carry the same key name
  would satisfy `mergeable_checked` without the target PR's own field
  ever being present. Unconfirmed (confidence 0.3, speculative -- not
  verified against a real `pull_request_read(method="get")` response
  shape), and the same shape-tolerance trade-off `_count_unresolved_threads`
  already accepts deliberately (see above).

Fails OPEN on every error path (malformed payload, missing jq is handled
by the .sh wrapper, unwritable state dir, unreadable prior state) --
PostToolUse cannot block a tool call that already succeeded (Claude
Code's own hooks reference: "PostToolUse ... cannot block -- the tool
already executed successfully"), so there is nothing to gain by denying
here; the Stop hook's own fail-closed default is where an unverifiable
state gets treated as unresolved, not this half.

Standard library only.

Usage (matches the JSON the .sh wrapper pipes in)::

    printf '%s' '{"session_id":"abc","tool_name":"Bash","tool_input":{"command":"git push"}}' \\
        | python3 hooks/gitapex_check_post_review_obligation_tracker.py

A bare pipe here masks `printf`'s own exit status in a non-`pipefail`
shell (issue #1531) -- harmless for a literal `printf` producer, which
cannot itself fail in ordinary use, but add `set -o pipefail` first if
this recipe's producer is ever swapped for a command that can.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import gitapex_check_bash_safety as bash_safety

_DEFAULT_STATE: dict[str, Any] = {
    "push_detected": False,
    "target_pr": None,
    "open_review_threads": None,
    "resolve_calls": 0,
    "mergeable_checked": False,
}


def state_path(session_id: str) -> Path:
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id) or "unknown"
    # os.environ.get("TMPDIR") is read fresh on every call, unlike
    # tempfile.gettempdir(), which caches its result on first use for the
    # life of the process -- a test setting TMPDIR via monkeypatch after
    # some earlier, unrelated call already triggered that cache would
    # otherwise silently keep resolving to the original default dir.
    base = os.environ.get("TMPDIR") or tempfile.gettempdir()
    return Path(base) / f"gitapex-review-obligation-{safe_id}.json"


def _read_state(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return {**_DEFAULT_STATE, **data}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return dict(_DEFAULT_STATE)


def _write_state(path: Path, state: dict[str, Any]) -> None:
    # tempfile.mkstemp's own O_CREAT|O_EXCL open -- not a predictable,
    # PID-based filename this process then opens in a second step -- is
    # what closes a TOCTOU/symlink-following gap an independent review
    # found: a predictable temp name in a shared TMPDIR can be pre-planted
    # as a symlink by another process sharing that directory, redirecting
    # this write to an attacker-chosen path once opened. mkstemp's random
    # suffix cannot be predicted or pre-planted the same way.
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(state))
        Path(tmp_name).replace(path)
    except OSError:
        with contextlib.suppress(OSError):
            Path(tmp_name).unlink()
        raise


def _pr_key(tool_input: dict[str, Any]) -> str | None:
    """Return a string identifying the PR `tool_input` targets, or None
    when no usable pull-request number is present.

    `pullNumber` is the one field every covered call (resolve_review_thread
    takes a thread node ID, not a PR number, so it is never a source of
    this key -- see the module docstring's own note on why `target_pr`
    can only be established via pull_request_read) is guaranteed to carry
    as an ordinary tool_input field. owner/repo are read too when present
    for a tighter key, but are not required -- the GitHub MCP server's
    schema marks them `x-mcp-header`, which may mean they arrive via a
    request header this hook's stdin payload never sees rather than in
    tool_input, so a key scoped to pullNumber alone is the reliable
    floor even though it cannot distinguish same-numbered PRs across two
    different repositories in the (rare, same-session) case both owner
    and repo are absent."""
    pull_number = tool_input.get("pullNumber")
    if isinstance(pull_number, bool) or not isinstance(pull_number, int):
        return None
    owner = tool_input.get("owner")
    repo = tool_input.get("repo")
    if isinstance(owner, str) and owner and isinstance(repo, str) and repo:
        return f"{owner}/{repo}#{pull_number}"
    return f"#{pull_number}"


def _same_pr(call_pr: str, target_pr: str) -> bool:
    """True when CALL_PR and TARGET_PR (both `_pr_key`-shaped strings) name
    the same pull request, tolerating the owner/repo-optional key format
    `_pr_key` produces: a bare "#1209" and a qualified "tvna/gitapex#1209"
    naming the same pull number are the SAME PR whenever at least one side
    lacks owner/repo to disagree with -- only two BOTH-qualified keys
    naming different owner/repo pairs count as a genuine different-PR
    switch. Independent review found and reproduced the bug this closes:
    plain string equality treated two calls naming the identical PR --
    one with owner/repo present, one without (the GitHub MCP server's own
    schema marks them `x-mcp-header`, so their presence can vary call to
    call -- see `_pr_key`'s own docstring) -- as a PR switch, discarding
    already-confirmed progress and forcing redundant re-verification."""
    call_owner_repo, _, call_number = call_pr.rpartition("#")
    target_owner_repo, _, target_number = target_pr.rpartition("#")
    if call_number != target_number:
        return False
    return not call_owner_repo or not target_owner_repo or call_owner_repo == target_owner_repo


def _unwrap_tool_response(tool_response: Any) -> Any:
    """Best-effort unwrap of a PostToolUse tool_response's MCP content
    envelope, returning whatever JSON value the tool actually returned --
    a dict OR a list. Unlike
    hooks/gitapex_check_post_write_provenance.py's own response_payload(),
    which is dict-only (every caller there reads object fields off a
    single PR/issue), this cannot assume dict:
    mcp__github__pull_request_read's get_review_comments method returns
    thread data whose own top-level shape is not guaranteed to be an
    object.

    Same MCP envelope shapes response_payload() documents (issue #908):
    a bare text-block list, the returned value itself, an MCP
    ``{"content": "<json>"}`` string, or an MCP
    ``{"content": [{"type": "text", "text": "<json>"}, ...]}`` block
    list. Falls back to `tool_response` itself, unchanged, when nothing
    parses -- never raises, never silently drops data the caller's own
    recursive walk could still use."""
    content: Any = tool_response if isinstance(tool_response, list) else None
    if content is None and isinstance(tool_response, dict):
        content = tool_response.get("content")

    candidates: list[str] = []
    if isinstance(content, str):
        candidates.append(content)
    elif isinstance(content, list):
        candidates.extend(
            block["text"] for block in content if isinstance(block, dict) and isinstance(block.get("text"), str)
        )

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    return tool_response


def _reports_error(node: Any) -> bool:
    """True when NODE carries an explicit failure marker.

    Mirrors hooks/gitapex_check_post_write_provenance.py's own
    `_reports_error()` marker vocabulary (`status == "error"` /
    `is_error is True` / `isError is True`) -- kept as a separate,
    tiny re-implementation rather than imported, since that sibling's
    version is dict-only while this module's callers already hold an
    `Any`-typed unwrapped value (see `_unwrap_tool_response`)."""
    if not isinstance(node, dict):
        return False
    return node.get("status") == "error" or node.get("is_error") is True or node.get("isError") is True


def _iter_dicts(node: Any) -> Iterator[dict[str, Any]]:
    """Recursively yield every dict reachable within NODE, tolerating any
    surrounding envelope shape (a bare list, a `{"threads": [...]}`
    wrapper, a paginated `{"nodes": [...], "pageInfo": ...}` shape, or
    anything else) -- the exact response envelope is the MCP server's own
    contract, not this repository's (see module docstring). Factored out
    of `_count_unresolved_threads` and `_contains_mergeable_state`, which
    independent review found had each hand-rolled this identical
    recursive walk, differing only in their own leaf predicate."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _iter_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_dicts(item)


def _count_unresolved_threads(node: Any) -> int:
    """Count every dict in NODE carrying `isResolved: false` -- see
    `_iter_dicts` for the envelope-tolerant walk this counts over."""
    return sum(1 for candidate in _iter_dicts(node) if candidate.get("isResolved") is False)


def _contains_mergeable_state(node: Any) -> bool:
    """True when some dict in NODE carries a `mergeable_state`/
    `mergeableState` key anywhere -- see `_iter_dicts` for the
    envelope-tolerant walk this searches, and the module docstring's
    "Known, disclosed limitations" for why this is unscoped rather than
    limited to NODE's own top-level object."""
    return any("mergeable_state" in candidate or "mergeableState" in candidate for candidate in _iter_dicts(node))


def handle_bash(state: dict[str, Any], tool_input: dict[str, Any]) -> dict[str, Any]:
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return state
    verdict = bash_safety.classify(command)
    if not verdict.is_git_push:
        return state
    return dict(_DEFAULT_STATE, push_detected=True)


def handle_resolve_review_thread(state: dict[str, Any], tool_response: Any) -> dict[str, Any]:
    if not state.get("push_detected") or state.get("target_pr") is None:
        return state
    outer = tool_response if isinstance(tool_response, dict) else {}
    if _reports_error(outer) or _reports_error(_unwrap_tool_response(tool_response)):
        return state
    return {**state, "resolve_calls": int(state.get("resolve_calls") or 0) + 1}


def handle_pull_request_read(state: dict[str, Any], tool_input: dict[str, Any], tool_response: Any) -> dict[str, Any]:
    if not state.get("push_detected"):
        return state

    call_pr = _pr_key(tool_input)
    target_pr = state.get("target_pr")
    if call_pr is not None and (target_pr is None or not _same_pr(call_pr, target_pr)):
        # Switching to a different PR than the one this cycle was already
        # tracking (including the first PR ever observed this cycle)
        # resets every piece of tracked progress, not just target_pr
        # itself. A second independent review round found and reproduced
        # the gap the single-line target_pr reassignment this replaces
        # left open: once target_pr locked onto whichever PR the agent
        # happened to read FIRST, a call against the PR actually pushed
        # to -- if it differed -- was silently ignored forever, leaving
        # the Stop hook demanding a get_review_comments call the agent
        # had already made (just against the wrong PR) with no way to
        # recover short of a second push. Carrying open_review_threads/
        # resolve_calls/mergeable_checked forward across a PR switch
        # would reopen the original cross-PR gap from the other
        # direction (an unrelated PR's already-satisfied state leaking
        # into the newly-tracked one), so a switch clears all three.
        # `_same_pr`, not plain string equality, decides "different PR":
        # a third independent review round found and reproduced a
        # related gap this specific comparison closes -- see that
        # helper's own docstring.
        state = {
            **state,
            "target_pr": call_pr,
            "open_review_threads": None,
            "resolve_calls": 0,
            "mergeable_checked": False,
        }
    elif call_pr is None and target_pr is None:
        # No PR identifiable from this call, and none tracked yet --
        # nothing to attribute this read to.
        return state

    unwrapped = _unwrap_tool_response(tool_response)
    method = tool_input.get("method")
    if method == "get_review_comments":
        return {**state, "open_review_threads": _count_unresolved_threads(unwrapped)}
    if method == "get" and _contains_mergeable_state(unwrapped):
        return {**state, "mergeable_checked": True}
    return state


def process(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the new state to persist, or None to leave the state file
    untouched (an irrelevant tool call, or push_detected not yet set for
    a resolve/read call)."""
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    path = state_path(session_id)
    state = _read_state(path)

    if tool_name == "Bash":
        new_state = handle_bash(state, tool_input)
    elif isinstance(tool_name, str) and tool_name.endswith("__resolve_review_thread"):
        new_state = handle_resolve_review_thread(state, payload.get("tool_response"))
    elif isinstance(tool_name, str) and tool_name.endswith("__pull_request_read"):
        new_state = handle_pull_request_read(state, tool_input, payload.get("tool_response"))
    else:
        return None

    if new_state == state:
        return None
    _write_state(path, new_state)
    return new_state


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        # The .sh wrapper no longer pre-validates payload shape via jq
        # (see that script's own header for why) -- this systemMessage is
        # now the only surviving signal that a cycle's tracking silently
        # no-opped on a malformed payload.
        print(
            json.dumps(
                {
                    "systemMessage": "hooks/check-post-review-obligation-tracker.sh: the tool-call payload on stdin could not be parsed as JSON. Skipping this cycle's obligation tracking."
                }
            )
        )
        return 0
    if not isinstance(payload, dict):
        print(
            json.dumps(
                {
                    "systemMessage": "hooks/check-post-review-obligation-tracker.sh: the tool-call payload on stdin is not a JSON object. Skipping this cycle's obligation tracking."
                }
            )
        )
        return 0
    # Fail open: PostToolUse cannot block an already-executed tool call,
    # and an unwritable state dir is the Stop hook's own fail-closed
    # default's problem to surface, not this half's.
    with contextlib.suppress(OSError):
        process(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
