#!/usr/bin/env python3
"""Preflight: verify the copilot-sdk custom-provider endpoint is configured.

Shared by ``.github/workflows/eval-matrix.yml`` (``eval-matrix`` job)
and ``.github/workflows/eval-gate.yml``, which previously each carried
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

**Why validation runs through a pydantic ``field_validator``, not
pydantic's own ``AnyUrl``/``HttpUrl``.** This repository's other
``.github/scripts/*.py`` gates commonly validate CLI input through a
``pydantic.BaseModel`` (e.g. ``gitapex_gate_behind_base.py``, safe here for
the same reason: this module's own production invocation already runs
under ``uv run``, never bare ``python3`` -- issue #1040/#1035). Using
pydantic's *built-in* URL type here was tried and rejected: verified live
(pydantic 2.13.4, ``TypeAdapter(AnyUrl)``) that it silently normalizes away
exactly the inputs this module exists to reject -- a trailing-whitespace
host (``"https://example.com   "``) and an embedded control character
(``"https://example.invalid/\\npath"``, a raw NUL) both came back
*accepted*, offending bytes silently stripped, per pydantic-core's own
WHATWG-URL-based parser -- the same class of gap CodeRabbit found in (and
this module was fixed to close against) Python's ``urlsplit``. Go's own
``url.Parse`` -- what ``providerHost()`` actually calls -- rejects both
outright. Adopting ``AnyUrl`` would have reintroduced a bug this module
already fixed once; the ``field_validator`` below keeps the same
Go-verified checks, now run through pydantic's own validation/error
machinery instead of a bespoke one.

**A second, independently found secret-hygiene gap, before it ever shipped:
pydantic's own ``ValidationError`` embeds the raw invalid value** in its
``str()``, ``repr()``, and structured ``.errors()`` output alike (verified
live: a deliberately malformed URL containing a sentinel string was fully
recoverable from ``e.errors()[0]["input"]``, and partially visible even in
``str(e)``). Chaining it onto ``EndpointMalformed`` with an ordinary
``raise ... from exc`` would retain that value on ``__cause__`` -- inert
today (``main()`` never prints a raw traceback), but exactly the kind of
latent leak a future caller that does print one (e.g. an added debug log)
would surface with nothing to catch the regression, the same accidental-
safety shape already rejected once for the bare ``ValueError`` case above.
``raise ... from None`` discards ``__cause__`` and stops default traceback
rendering from showing pydantic's own exception object -- but, verified
live, does *not* by itself clear ``__context__``: CPython auto-populates a
new exception's ``__context__`` with whatever was just caught, at the
moment ``raise`` executes inside an active ``except`` suite, regardless of
the ``from`` clause -- so the secret stayed fully recoverable via
``exc.__context__`` even after this fix (caught by an independent
adversarial review, not the test suite that existed at the time).
``validate_base_url`` below builds ``EndpointMalformed`` inside ``except``
but raises it only after control has left that block, so no exception is
being handled at the point of ``raise`` and ``__context__`` is never
populated at all.

Usage::

    uv run --frozen python3 .github/scripts/gitapex_check_copilot_endpoint_configured.py

A bare ``python3`` invocation is no longer sufficient now that this module
imports pydantic: it would fail with ``ModuleNotFoundError`` wherever
pydantic is not already on the ambient interpreter's path. Both real call
sites (``eval-matrix.yml``, ``eval-gate.yml``) already go through
``uv run``, per this repository's own ``bare-python3-invocation-gate``.

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

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

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


class _CopilotEndpointURL(BaseModel):
    """Pydantic wrapper around the scheme/host/control-character checks
    ``validate_base_url`` runs, each verified live against waza's own
    ``providerHost()`` and a throwaway Go ``net/url`` program (see the
    module docstring) rather than assumed:

    - Scheme and host (``.hostname``, not ``.netloc`` -- ``netloc`` folds
      userinfo into the same string as the host, so
      ``"https://user:pass@"`` reads non-empty even with no real host;
      Go's own ``Host`` field is empty for that input) must both be
      present.
    - The host must not contain whitespace: Go's own ``url.Parse`` refuses
      to parse one with an embedded space at all, stricter than Python's
      ``urlsplit``, which accepts it as part of the host string.
    - No raw C0 control character or DEL (ordinal < 0x20, or 0x7f)
      anywhere in the value, checked before ``urlsplit`` ever runs --
      ``urlsplit`` silently drops an embedded tab/newline/CR/NUL from
      anywhere in the string rather than erroring or preserving it, so a
      hostname-only check downstream never sees one; Go's own
      ``url.Parse`` rejects the identical input outright, before
      component parsing even starts. Found by an automated reviewer on
      this PR, independently reproduced against both Python's ``urlsplit``
      and a live Go program before fixing, not fixed on the report alone.

    Deliberately typed as plain ``str``, not pydantic's own ``AnyUrl``:
    verified live (pydantic 2.13.4) that ``AnyUrl`` itself silently
    normalizes away a trailing-whitespace host and an embedded control
    character -- the exact two gaps this model exists to close -- so using
    it here would reintroduce them; see the module docstring.

    No explicit ``try``/``except ValueError`` around ``urlsplit`` inside
    the validator below (unlike an earlier revision): pydantic's own
    ``field_validator`` already catches any ``ValueError`` raised inside
    it (confirmed live, including one bubbling up from ``urlsplit``'s own
    lazy ``.hostname`` property for a malformed IPv6 literal) and folds it
    into a clean ``ValidationError`` -- a second, redundant catch here
    would just be dead code.
    """

    model_config = ConfigDict(frozen=True)

    value: str

    @field_validator("value")
    @classmethod
    def _must_be_a_well_formed_endpoint(cls, value: str) -> str:
        if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
            raise ValueError("contains a raw C0 control character or DEL")
        parts = urlsplit(value)
        hostname = parts.hostname
        if not parts.scheme or not hostname:
            raise ValueError("missing a scheme or a host")
        if any(ch.isspace() for ch in hostname):
            raise ValueError("host contains whitespace")
        return value


def validate_base_url(var_name: str, value: str) -> None:
    """Raise EndpointMalformed unless ``value`` passes ``_CopilotEndpointURL``.

    ``from None``, not ``from exc``, is deliberate: pydantic's own
    ``ValidationError`` embeds the raw invalid *value* in its ``str()``,
    ``repr()``, and structured ``.errors()`` alike (verified live -- a
    sentinel planted in a deliberately malformed URL was fully recoverable
    from ``e.errors()[0]["input"]``, and partially visible even in
    ``str(e)``). Chaining it onto ``EndpointMalformed`` would retain that
    value on ``__cause__`` -- inert today (``main()`` below never prints a
    raw traceback) but exactly the kind of latent leak a future caller
    that does (e.g. an added debug log) would surface with nothing to
    catch the regression, the same accidental-safety shape already
    rejected once for the bare ``ValueError``-from-``urlsplit`` case this
    module fixed earlier.

    ``from None`` alone is not enough, verified live: it clears
    ``__cause__`` and sets ``__suppress_context__`` (so default traceback
    rendering and ``logging.exception`` both stay clean, which is why the
    existing test suite passed), but CPython still auto-populates
    ``__context__`` with the just-caught ``ValidationError`` at the moment
    ``raise`` executes *inside* an active ``except`` suite -- the ``from``
    clause has no say over that. Anything that explicitly walks
    ``exc.__cause__ or exc.__context__`` (a standard pattern, e.g. in
    structured-logging integrations) would still recover the secret. So
    the exception is built here, inside ``except``, but not raised until
    control has left that block -- at that point nothing is being handled
    in this frame, so ``__context__`` is never populated in the first
    place, verified live by asserting ``__context__ is None`` on the
    raised exception.
    """
    malformed: EndpointMalformed | None = None
    try:
        _CopilotEndpointURL(value=value)
    except ValidationError:
        malformed = EndpointMalformed(var_name)
    if malformed is not None:
        raise malformed from None


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
