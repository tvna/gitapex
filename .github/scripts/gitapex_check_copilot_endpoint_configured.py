#!/usr/bin/env python3
"""Preflight: verify the copilot-sdk custom-provider endpoint is configured.

Shared by ``.github/workflows/waza-eval-matrix.yml`` (``eval-matrix`` job)
and ``.github/workflows/waza-eval-gate.yml``, which previously each carried
their own copy of the identical bash check
(``if [ -z "$COPILOT_BASE_URL" ] && [ -z "$COPILOT_PROVIDER_BASE_URL" ]``).
This module is the single source of truth those two call sites now share
(issue #124, carried forward from PR #120: "confirm which of
COPILOT_BASE_URL / COPILOT_PROVIDER_BASE_URL the copilot-sdk executor
actually requires, then tighten the workflow preflight -- it currently fails
only when BOTH are unset, so a run with only the wrong one set passes
preflight and fails opaquely later").

**Primary-source verification (grounding-in-primary-sources).** Read live
against waza's own upstream source, github.com/microsoft/waza, commit
f3afa6aa61dd9bbbc893067c7e949672952f9cd0,
``internal/execution/copilot.go``'s ``providerFromEnv``/``envFirst``/
``providerHost``, and its published CLI reference
(``site/src/content/docs/reference/cli.mdx``): ``COPILOT_BASE_URL`` and
``COPILOT_PROVIDER_BASE_URL`` are fully interchangeable aliases for the same
field -- ``envFirst`` returns whichever is non-empty, with the short name
winning when both are set. There is therefore no scenario where setting "the
wrong one" of *this specific pair* causes a failure -- both name the same
thing. Issue #124's Step 1 premise did not hold under that verification, and
this module does not encode it.

The gap that *is* real, independently found in the same source read: the
prior check only asked whether a base-URL string was non-empty, never
whether it was a URL at all. Upstream's own ``providerHost()`` parses the
winning value and rejects it unless it carries both a scheme and a host --
and only raises that error once a session actually starts, deep inside a
run, not at the cheap preflight step. A non-empty-but-malformed value (a
bare hostname with no ``https://``, a typo'd scheme) passed the old
preflight and would fail opaquely 45 minutes into a live matrix dispatch.
This module closes exactly that gap: the same "which one wins" selection as
upstream, plus the same scheme+host requirement, checked before any run
starts.

Deliberately NOT enforced here: an API key or bearer token
(``COPILOT_API_KEY``/``COPILOT_PROVIDER_API_KEY``,
``COPILOT_BEARER_TOKEN``/``COPILOT_PROVIDER_BEARER_TOKEN``). Upstream's own
CLI reference documents both as "if required" -- whether a custom endpoint
needs auth at all is endpoint-specific, so a generic preflight cannot safely
demand one without risking rejection of a legitimately unauthenticated
endpoint.

Fail-loud contract (CLAUDE.md section 4): the secret's *value* is never
printed, on either the error or the success path -- only which env var name
resolved (a name is not a secret) and the class of problem (unset vs.
malformed).

Disclosed residual risk: Python's ``urlsplit`` does not fail to parse the
way Go's ``url.Parse`` occasionally can on malformed percent-encoding or
control characters; this module only replicates upstream's scheme+host
presence check, not full parser-parity with Go's ``net/url``.

Usage::

    python3 .github/scripts/gitapex_check_copilot_endpoint_configured.py

Reads ``COPILOT_BASE_URL`` / ``COPILOT_PROVIDER_BASE_URL`` from the process
environment; exits 0 (printing which var resolved) when configured and
well-formed, exits 1 with an ``::error::`` line otherwise. Run standalone or
via the pytest gate in
``tests/test_gitapex_check_copilot_endpoint_configured.py``.
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlsplit

#: Short canonical name first, long COPILOT_PROVIDER_* alias second -- the
#: short name wins when both are set, matching waza's own envFirst() order.
BASE_URL_VARS = ("COPILOT_BASE_URL", "COPILOT_PROVIDER_BASE_URL")


class EndpointNotConfigured(Exception):
    """Neither COPILOT_BASE_URL nor COPILOT_PROVIDER_BASE_URL is set."""


class EndpointMalformed(Exception):
    """The winning env var is set but is not a valid absolute URL.

    Carries ``var_name`` (never the value) so a caller can name which
    variable needs fixing without echoing what it was set to.
    """

    def __init__(self, var_name: str) -> None:
        self.var_name = var_name
        super().__init__(f"{var_name} is set but is not a valid absolute URL (needs a scheme and a host)")


def resolve_base_url_var(env: dict[str, str]) -> str:
    """The name of the env var that wins, per waza's own envFirst() order.

    Returns only the *name*, never the value, so this function's return
    value is always safe to log. Raises EndpointNotConfigured if both are
    unset or empty -- an explicitly empty string (``COPILOT_BASE_URL=""``,
    what a missing GitHub Actions secret resolves to via
    ``${{ secrets.X }}``) counts as unset, matching upstream's own
    ``v != ""`` check.
    """
    for name in BASE_URL_VARS:
        if env.get(name, ""):
            return name
    raise EndpointNotConfigured(f"neither {BASE_URL_VARS[0]} nor {BASE_URL_VARS[1]} is set")


def validate_base_url(var_name: str, value: str) -> None:
    """Raise EndpointMalformed unless ``value`` has both a scheme and a host.

    Mirrors waza's own ``providerHost()`` (``internal/execution/copilot.go``):
    the parsed URL must carry a non-empty scheme and a non-empty host.

    Deliberately checks ``.hostname``, not ``.netloc``: ``netloc`` folds
    userinfo into the same string as the host (``urlsplit("https://user:pass@").netloc
    == "user:pass@"``, non-empty even though there is no host at all), while
    Go's ``net/url.URL.Host`` -- what ``providerHost()`` actually reads -- is
    empty for that same input (verified live with a throwaway Go program
    against the local toolchain: ``url.Parse("https://user:pass@").Host ==
    ""``). A netloc-only check would have silently accepted a value with
    credentials and no endpoint to send them to.

    Also rejects a hostname containing whitespace. Go's own ``url.Parse``
    refuses to parse a host with an embedded space at all (confirmed by the
    same throwaway program: ``url.Parse("https://example.com   ")`` returns
    the error ``invalid character " " in host name``) -- stricter than
    Python's ``urlsplit``, which silently accepts the space as part of the
    host string.

    Also rejects any raw C0 control character or DEL (ordinal < 0x20, or
    0x7f) anywhere in ``value``, checked before ``urlsplit`` ever runs.
    ``urlsplit`` silently drops an embedded tab/newline/CR from anywhere in
    the string rather than erroring or preserving it (confirmed live:
    ``urlsplit("https://example.invalid/\\npath").path == "/path"``, the
    ``\\n`` simply gone) -- so a hostname-only whitespace check downstream
    never sees it. Go's own ``url.Parse`` rejects the same input outright,
    for the same range, before component parsing even starts (confirmed
    live: every one of ``\\n``, ``\\r``, ``\\t``, ``\\x00``, ``\\x1e``,
    ``\\x1f``, ``\\x7f`` anywhere in the string -- host or path alike --
    fails with ``invalid control character in URL``; a literal space,
    0x20, is explicitly fine and left alone). Found by an automated
    reviewer on this PR, independently reproduced against both Python's
    ``urlsplit`` and a live Go program before this fix, not fixed on the
    reviewer's say-so alone.

    ``urlsplit``/``.hostname`` can also raise ``ValueError`` on other
    malformed input (confirmed live: an unterminated IPv6 literal like
    ``https://[::1``), caught here and folded into the same
    ``EndpointMalformed`` outcome. An uncaught exception here would still
    exit this script non-zero -- Python's default handling for an
    unhandled exception -- so letting it escape was never a fail-*open*
    risk on its own. The reason to catch it explicitly: an uncaught
    exception was an *accidental* deny (whatever CPython's default
    happened to do that day, unverified by any test), not a *designed*
    one -- dimension 15 of
    skills/evaluating-deterministic-gate-quality/references/dimensions.md
    is explicit that a bundled test covering only well-formed input does
    not by itself earn credit here, and an accidental deny path is exactly
    the kind of thing a later refactor (e.g. wrapping main()'s body in a
    broader except-and-continue for an unrelated reason) could silently
    flip to fail-open with nothing to catch the regression. Routing it
    through the same explicit, tested path as every other malformed-input
    case closes that risk and gives a consistent, actionable ``::error::``
    message instead of a raw traceback either way.
    """
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise EndpointMalformed(var_name)
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
    except ValueError as exc:
        # e.g. an unterminated IPv6 literal ("https://[::1") -- urlsplit or
        # the lazy .hostname property can raise instead of returning a
        # falsy value; both must land here, not escape as a bare traceback.
        raise EndpointMalformed(var_name) from exc
    if not parts.scheme or not hostname or any(ch.isspace() for ch in hostname):
        raise EndpointMalformed(var_name)


def check(env: dict[str, str]) -> str:
    """Full preflight check against ``env``.

    Returns the winning var name on success. Raises EndpointNotConfigured or
    EndpointMalformed otherwise.
    """
    var_name = resolve_base_url_var(env)
    validate_base_url(var_name, env[var_name])
    return var_name


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    return argparse.ArgumentParser(
        description=(
            "Fail loudly unless COPILOT_BASE_URL or COPILOT_PROVIDER_BASE_URL "
            "(process environment) is set to a well-formed absolute URL. Never "
            "prints the value, only which variable resolved."
        )
    ).parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _parse_args(argv)
    try:
        var_name = check(dict(os.environ))
    except EndpointNotConfigured:
        print(
            "::error::No copilot-sdk endpoint configured. Set repository secret "
            f"{BASE_URL_VARS[0]} (and/or {BASE_URL_VARS[1]}) under Settings -> "
            "Secrets and variables -> Actions before dispatching. See issue #106 "
            "(scaffolding) and #124 (issuance path) for the credential-provisioning "
            "prerequisite.",
            file=sys.stderr,
        )
        return 1
    except EndpointMalformed as exc:
        print(
            f"::error::{exc.var_name} is set but is not a valid absolute URL -- "
            "it must include both a scheme (e.g. 'https://') and a host. The "
            "value itself is intentionally not printed here; check it under "
            "Settings -> Secrets and variables -> Actions.",
            file=sys.stderr,
        )
        return 1
    print(f"copilot-sdk endpoint configured via {var_name} (value not printed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
