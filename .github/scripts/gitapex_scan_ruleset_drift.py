#!/usr/bin/env python3
"""Compare the live `main` ruleset against its committed source of truth.

Issue #439. Two scopes, one script, because both answer the same question --
does GitHub still enforce what `.github/rulesets/main.json` says it enforces?
-- and differ only in how much of the ruleset they look at and when they run:

* `--scope required-checks` runs on every pull request. It asserts only that the
  live ruleset's required status checks have not *lagged behind* the committed
  file. The workflow feeds it the source of truth as it exists on the pull
  request's **base** ref, never the head ref: a pull request that adds a new
  required check to the committed file has by definition not applied it yet
  (applying is a separate human dispatch), so grading the head ref would make
  every such pull request fail itself for doing exactly what it set out to do.

* `--scope full` runs on a schedule and compares the entire projected ruleset --
  conditions, bypass actors, and every rule -- so a change made directly in the
  Settings UI, which no pull request would ever show, surfaces within a day.

Both scopes are dispatched from the single `.github/workflows/ruleset-verify.yml`
workflow, which derives the scope and the source of truth's origin from
`github.event_name`; this `--scope` flag is where that choice is actually
implemented, and it lives here rather than in YAML because this layer is
testable, type-checked, and runnable locally. The mutating counterpart
(`.github/workflows/apply-rulesets.yml`) stays a separate workflow on purpose --
see that file's header.

**Exit codes are three-valued on purpose.** `0` in sync, `1` drift, `2` nothing
was verified. The third state exists because "GitHub enforces something other
than what git says" and "this scan never got to look" are different facts, and
a pull request can fix only the first. Collapsing `2` into `1` would make every
pull request red for a condition no pull request can fix; collapsing it into `0`
would be exactly the silent default CLAUDE.md section 4 forbids. Both workflows
surface `2` as a GitHub `::warning::` naming the runbook step that clears it, so
it is loud without being a merge blocker.

**Where the 1/2 line falls.** Exit 2 covers every way this scan can fail to
*read* the live state, which is a wider set than it first looks: no live ruleset
carries the committed name yet, no token was supplied, the token is rejected,
the API is down, the response is truncated. The first two are the owner-gated
interval between this file landing in git and a human dispatching
`apply-rulesets.yml` with the `RULESETS_PAT` handoff complete; the rest arrive
as `GitHubApiError`. Exit 1 is reserved for the two things that are genuinely
wrong rather than merely unknown: the live ruleset disagrees with the committed
file, or the committed file itself is unreadable/ambiguous (`RulesetError`,
which also covers two live rulesets sharing one name).

An earlier revision of this module put a rejected credential on the exit-1
side, reasoning that a broken handoff should fail loudly rather than warn.
Corrected after review: exit 1 makes the workflow print "the live main ruleset
requires fewer status checks than the base ref claims", which during an API
outage is a statement this scan has no evidence for. Emitting a confident false
diagnostic is worse than a warning, so the whole read-failure class is exit 2 --
and to keep that from becoming a silent forever-pass, the specific failure text
(the HTTP status, the URL) is printed on **stdout**, which is what both
workflows pipe into the job summary.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time
from collections.abc import Callable
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _gitapex_github_http import (  # sys.path bootstrap above must run first
    GitHubApiError,
    default_opener,
    fetch_json_document,
)
from _gitapex_rulesets import (  # same bootstrap
    RulesetError,
    load_sot,
    render_projection_diff,
    required_check_contexts,
    resolve_live_ruleset,
    unobservable_keys,
)

EXIT_IN_SYNC = 0
EXIT_DRIFT = 1
#: Nothing was verified -- no live ruleset carries the committed name yet, no
#: token was supplied, or the API could not be read (rejected credential,
#: outage, unparseable response). Distinct from `EXIT_DRIFT` so a caller can
#: tell "GitHub enforces something other than what git says" from "this scan
#: never got to look"; see the module docstring for why that distinction is
#: load-bearing rather than cosmetic.
EXIT_UNVERIFIED = 2


def default_fetch(url: str, token: str) -> Any:
    return fetch_json_document(url, token, default_opener, time.sleep)


def compare_required_checks(live: dict[str, Any], sot: dict[str, Any]) -> list[str]:
    """Committed contexts that the live ruleset does not require.

    Deliberately one-directional. A context present live but absent from the
    committed file is not reported here: that is the shape a pull request
    *removing* a required check has while it is still open, and failing it in
    this scope would block the removal from ever landing. The scheduled
    `--scope full` run compares both directions and catches it either way.
    """
    live_contexts = set(required_check_contexts(live))
    return [context for context in required_check_contexts(sot) if context not in live_contexts]


def render_required_checks_report(missing: list[str], ruleset_name: str) -> str:
    if not missing:
        return f"Live ruleset `{ruleset_name}` requires every status check the committed source of truth names."
    listed = "\n".join(f"- `{context}`" for context in missing)
    return (
        f"Live ruleset `{ruleset_name}` is missing {len(missing)} required status "
        f"check(s) that `.github/rulesets/` already names:\n{listed}\n\n"
        "Dispatch `Apply rulesets` (dry run first) to reconcile -- see "
        "docs/runbooks/rulesets.md."
    )


def render_unobservable_note(unobserved: list[str]) -> str:
    """Name the fields this credential could not read, on every run.

    Printed whether the scan passed or failed. A scan that quietly narrowed what
    it compared and still reported "matches" would be asserting more than it
    checked -- the exact shape CLAUDE.md section 1 rules out. Saying it every
    time also keeps the compensating control visible: the apply path holds the
    read/write token and does verify these fields immediately after the write.
    """
    if not unobserved:
        return ""
    listed = ", ".join(f"`{key}`" for key in unobserved)
    return (
        "\n\n> [!NOTE]\n"
        f"> Not compared: {listed}. GitHub returns `bypass_actors` only to a caller with **write**\n"
        "> access to the ruleset, and this scan deliberately runs with the read-only `RULESETS_PAT`\n"
        "> on the `ruleset-verify` Environment. The field is verified post-write by `Apply rulesets`,\n"
        "> which holds the read/write token -- see docs/runbooks/rulesets.md."
    )


def render_full_report(diff: str, ruleset_name: str, unobserved: list[str] | None = None) -> str:
    note = render_unobservable_note(unobserved or [])
    if not diff:
        return f"Live ruleset `{ruleset_name}` matches its committed source of truth.{note}"
    return (
        f"Live ruleset `{ruleset_name}` has drifted from its committed source of truth "
        f"(`live` is what GitHub enforces now, `sot` is what git says it should):\n\n"
        f"```diff\n{diff}```\n\n"
        "Reconcile by dispatching `Apply rulesets`, or by opening a pull request that "
        "updates the committed JSON if the live state is the intended one -- "
        f"see docs/runbooks/rulesets.md.{note}"
    )


def render_not_applied_report(ruleset_name: str) -> str:
    return (
        f"No live ruleset is named `{ruleset_name}`. The committed source of truth has not been "
        "applied to GitHub yet; this is an owner action, not drift. Dispatch `Apply rulesets` with "
        "`dry_run: true`, read the plan, then re-dispatch with `dry_run: false` -- "
        "see docs/runbooks/rulesets.md."
    )


def run(repo: str, sot_path: pathlib.Path, scope: str, fetch: Callable[[str], Any]) -> tuple[str, int]:
    """Execute one scan; returns the report markdown and the exit code."""
    sot = load_sot(sot_path)
    live = resolve_live_ruleset(repo, sot["name"], fetch)
    if live is None:
        return render_not_applied_report(sot["name"]), EXIT_UNVERIFIED
    if scope == "required-checks":
        missing = compare_required_checks(live, sot)
        code = EXIT_DRIFT if missing else EXIT_IN_SYNC
        return render_required_checks_report(missing, sot["name"]), code
    unobserved = unobservable_keys(live)
    diff = render_projection_diff(live, sot, ignore_keys=unobserved)
    return render_full_report(diff, sot["name"], unobserved), EXIT_DRIFT if diff else EXIT_IN_SYNC


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name of the repository to scan")
    parser.add_argument("--sot", required=True, help="path to the committed ruleset JSON to compare against")
    parser.add_argument(
        "--scope",
        required=True,
        choices=("required-checks", "full"),
        help="required-checks asserts the live ruleset has not lagged behind the file; full compares everything",
    )
    parser.add_argument("--token-env", default="GITHUB_TOKEN", help="environment variable holding the API token")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get(args.token_env, "")
    if not token:
        print(
            f"{args.token_env} is empty, so nothing was verified: the rulesets API is not readable with the "
            "default job token. Complete the RULESETS_PAT handoff in docs/runbooks/rulesets.md."
        )
        return EXIT_UNVERIFIED
    try:
        report, code = run(args.repo, pathlib.Path(args.sot), args.scope, lambda url: default_fetch(url, token))
    except GitHubApiError as error:
        # The read failed, so nothing was compared. Printed on stdout, not
        # stderr: both workflows pipe only stdout into $GITHUB_STEP_SUMMARY, so
        # a stderr-only diagnostic would leave the summary blank on exactly the
        # runs where someone needs to know what went wrong.
        print(f"Nothing was verified -- the rulesets API could not be read: {error}")
        return EXIT_UNVERIFIED
    except RulesetError as error:
        # Not a read failure: the committed file is unusable, or two live
        # rulesets share one name. Both are real, actionable repository state.
        print(f"::error::{error}", file=sys.stderr)
        print(f"Ruleset drift scan failed: {error}")
        return EXIT_DRIFT
    print(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
