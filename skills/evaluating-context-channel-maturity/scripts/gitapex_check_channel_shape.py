"""Deterministic shape checker for one CLAUDE.md/AGENTS.md/subagent-definition
channel file (issue #1987, axis group B of evaluating-context-channel-
maturity/SKILL.md).

Companion to skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py
(the SKILL.md shape checker), NOT an extension of it: this module imports
nothing from that checker's own ``shape_checks/`` package. Issue #1963's own
correction C4 is the reason, restated precisely rather than assumed: `skills/`
sits on the *deployed* side of docs/repository-layout.md's distribution
boundary (apm/Claude/Codex deploy each `skills/<name>/` directory, including
its own `scripts/`, independently of every other skill directory), so a
module shared between two different skills' own `scripts/` directories would
break whichever skill's standalone execution once the two are vendored
separately -- the failing skill would import a sibling skill's internal
module that a standalone install of just the failing skill never carries.
This module therefore carries its own frontmatter parser, its own
``CheckResult`` type, and its own threshold constants, duplicated rather than
imported, exactly as issue #1987's own Branch Plan requires.

Read-only, matching the sibling checker's own contract: reads the target
file (and, for the tool-boundary checks, ``hooks/gitapex_sync_opencode.py``)
only. No writes, no network, no mutation.

Checks (one CheckResult each):

  - channel-file-readable: the target file is readable as UTF-8 text. An
    unreadable target (missing, a directory, non-UTF-8) fails this one check
    and short-circuits every other check below -- there is nothing left to
    read a description or a tool boundary out of -- rather than raising out
    of check_shape(), mirroring gitapex_check_skill_shape.py's own
    skill-md-readable short-circuit.
  - frontmatter-parsable: when the target text opens a ``---``-delimited
    frontmatter block, that block is properly closed by a second ``---``
    line. A target carrying no frontmatter block at all (AGENTS.md, which
    this checker's own scope also covers, normally has none) is not a
    defect and passes this check trivially -- only an *opened-but-never-
    closed* block, a real authoring mistake, fails it. Every check below
    that reads frontmatter is downstream of this one: a malformed block is
    treated the same as no frontmatter (fields=None), never guessed at.
  - description-length: the frontmatter ``description:`` field, if present,
    is <= DESCRIPTION_MAX_CHARS (500) characters -- this channel's own cap,
    per issue #1987's own stated figure. Deliberately NOT
    gitapex_check_skill_shape.py's own DESCRIPTION_MAX_CHARS (1024): that
    constant grades a SKILL.md description under the Claude Code Skills
    frontmatter contract, a different channel with its own, larger,
    already-established cap; this module's own cap is unrelated and not
    reused. A target with no ``description:`` field at all (AGENTS.md
    today) reports this check as passed/not-applicable, the same
    absent-optional-content convention gitapex_check_skill_shape.py already
    uses throughout its own docstring.
  - yaml-plain-scalar-safety: the same rule gitapex_check_skill_shape.py's
    own module docstring already states for a SKILL.md description, applied
    here to this channel's own description field instead: an unquoted YAML
    plain scalar must not contain ": " (colon + space), must not end with a
    trailing ":", must not start with "#", and must not contain " #"
    (space + hash) anywhere -- each either breaks YAML parsing or silently
    truncates the value as a comment to a real YAML parser. A description
    written instead as a quoted scalar ('...'/"...") or a YAML block scalar
    (">"/"|") is exempt from this specific check, since either form is
    already safe under a real YAML parser regardless of content -- again
    mirroring the sibling checker's own stated exemption. Not-applicable
    under the same absent-description convention as description-length
    above.
  - tool-boundary-declared: does the target's frontmatter state a tool
    boundary at all -- a ``disallowedTools:`` or ``tools:`` key present?
    This check is about Claude Code's own frontmatter only, per issue
    #1987's own row 1. Design choice, disclosed here rather than left
    implicit: a target carrying frontmatter but declaring *neither* key
    FAILS this check (an actionable gap -- a subagent-definition file this
    checker's own scope targets is expected to state one); a target
    carrying no frontmatter block at all (AGENTS.md) is reported
    not-applicable (passed=True) instead, since the very concept of a
    frontmatter-declared tool boundary does not apply to a file with no
    frontmatter mechanism at all.
  - tool-boundary-mapping-present: for a target whose tool-boundary-declared
    check found a real boundary, does
    hooks/gitapex_sync_opencode.py's own AGENT_SPECS carry a non-None
    permission-mapping entry for this same filename? Not-applicable when no
    boundary is declared (nothing to look up a mapping for).
  - tool-boundary-mapping-equivalent: for a target with both a declared
    boundary and a present mapping, does that mapping actually deny an
    OpenCode-permission-key equivalent of the declared Claude-side surface --
    not merely exist? See _opencode_key_for_token's own docstring for the
    small, explicitly-scoped Claude-tool-name -> OpenCode-permission-key
    translation table this check applies (deliberately narrow: this
    module's own synthetic-fixture-only proof scope, per issue #1987's own
    Task 2, does not require -- and this module does not attempt -- a fully
    general cross-runtime tool-name equivalence resolver). Not-applicable
    when no boundary is declared, or no mapping is present (the two checks
    above already report the reason in that case).

Runtime frontmatter compatibility -- primary sources fetched fresh for this
module's own authoring (per this repository's own AGENTS.md section 2
grounding requirement), not recalled from memory or from an earlier fetch,
and recorded here rather than as a new versioned registry file (issue #1987's
own correction E1 reads row 1's Planned ops this way, to keep the change
surface narrow):

  - Claude Code sub-agent frontmatter. primarySource:
    https://code.claude.com/docs/en/sub-agents . Fetched 2026-09-16; no
    version number was surfaced by this fetch (unlike
    .gitapex/runtime-compatibility-matrix.json's own claude-code entries,
    which cite an observed CLI version elsewhere -- not re-derived here).
    Notes: ``tools:`` is an ALLOW-list (only listed tools are available;
    omitted means every tool a subagent can inherit); ``disallowedTools:``
    is a DENY-list removing tools from the inherited/specified pool, applied
    BEFORE ``tools:`` is resolved when both are present; both accept MCP
    server-level patterns (``mcp__<server>`` or ``mcp__<server>__*``).
    Description carries no hard character limit in the documentation itself
    -- only a combined-across-all-subagents 15,000-token startup-warning
    threshold. This module's own 500-char DESCRIPTION_MAX_CHARS is
    therefore this repository's own stricter policy choice (issue #1987),
    not a limit Claude Code's own docs impose.
  - OpenCode agent frontmatter. primarySource:
    https://opencode.ai/docs/agents . Fetched 2026-09-16; no version number
    is exposed by this documentation page (an evergreen docs site, not a
    versioned release note). Notes: the ``permission`` mapping is the
    canonical tool-boundary mechanism (``tools:`` is documented as
    deprecated in OpenCode's favor of ``permission``); each permission key
    accepts ``"allow"``/``"deny"``/``"ask"``; per the documentation's own
    wording, "permission keys are matched as wildcard patterns against the
    underlying tool name" -- the primary-source confirmation for
    hooks/gitapex_sync_opencode.py's own ``"*mcp*": "deny"`` wildcard-key
    convention this module's own equivalence check (below) also relies on.
    No description character limit is documented either.

**Residual risk, stated plainly per row 1's own note (Branch Plan, Task 2):
this is declaration parity, not effective-set parity.** Every check above
compares what each runtime's own frontmatter/permission-mapping *declares*;
none of them execute either runtime's real tool-dispatch path to confirm the
declared boundary is actually enforced identically at runtime (a materially
different question -- and, per pluginSubagentLimitations in
.gitapex/runtime-compatibility-matrix.json, Claude Code's own subagent
tools: field is already known to be narrowed by two further, undeclared
filters beyond what its own frontmatter states).

Usage:
  python3 gitapex_check_channel_shape.py <path-to-channel-file>
  python3 gitapex_check_channel_shape.py --allowed-root <dir> <path>

Exit code: 0 if every check passes, 1 if any check fails, 2 on bad usage or
an out-of-scope/unreadable target under --allowed-root.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

# This channel's own description-length cap (issue #1987's own stated
# figure) -- deliberately NOT gitapex_check_skill_shape.py's
# DESCRIPTION_MAX_CHARS (1024), a different channel's own, larger cap. See
# this module's own docstring for the full rationale.
DESCRIPTION_MAX_CHARS = 500

# The two Claude Code frontmatter keys that state a tool boundary (module
# docstring's own "Claude Code sub-agent frontmatter" citation above).
_TOOL_BOUNDARY_KEYS = ("disallowedTools", "tools")

# hooks/gitapex_sync_opencode.py's own AGENT_SPECS is keyed by bare agent
# filename ("review-persona.md"), never a path -- this module resolves
# every target to Path(...).name before looking it up, matching that
# module's own key shape exactly (see _load_agent_specs's own docstring).
_HOOKS_RELATIVE_PATH = Path("hooks") / "gitapex_sync_opencode.py"


class CheckResult(NamedTuple):
    name: str
    passed: bool
    rule: str
    evidence: str


class _Field(NamedTuple):
    """One parsed top-level frontmatter field. ``style`` records how the
    scalar was written -- ``plain`` (unquoted, at risk of the YAML-breaking
    patterns yaml-plain-scalar-safety checks for), ``quoted``
    ('...'/"..."), ``block`` (">"/"|", concatenated), or ``empty`` (a bare
    ``key:`` with nothing on the same line and no indented continuation --
    treated as an empty plain scalar, since none of the fields this module
    reads -- description, tools, disallowedTools -- are ever legitimately
    written as a nested list/mapping in a real Claude Code agent file).
    ``value`` is the already-unquoted-or-joined logical text, ready for a
    length count or a safety scan without further processing."""

    style: str
    value: str


_FRONTMATTER_OPEN_RE = re.compile(r"\A---[ \t]*\n")
_FRONTMATTER_BLOCK_RE = re.compile(r"\A---[ \t]*\n(?P<body>.*?)\n---[ \t]*\n", re.DOTALL)
_TOP_LEVEL_KEY_RE = re.compile(r"^(?P<key>[A-Za-z0-9_-]+):(?P<rest>.*)$")


def _closing_quote_index(rest: str) -> int | None:
    """The index within `rest` (which must open with a quote character at
    index 0) of its real, unescaped closing quote -- honoring YAML's own
    per-style escape rule: a double-quoted scalar escapes via a backslash
    (`\\"` is a literal `"`, never a terminator); a single-quoted scalar
    escapes via doubling (`''` is a literal `'`, never a terminator).
    None when no real closing quote exists on this line (an unterminated
    scalar)."""
    quote = rest[0]
    n = len(rest)
    i = 1
    if quote == '"':
        while i < n:
            if rest[i] == "\\":
                i += 2
                continue
            if rest[i] == '"':
                return i
            i += 1
        return None
    while i < n:
        if rest[i] == "'":
            if i + 1 < n and rest[i + 1] == "'":
                i += 2
                continue
            return i
        i += 1
    return None


def _quoted_scalar_value(rest: str) -> str | None:
    """The unescaped value of `rest` when it is a genuinely closed,
    single-line YAML quoted scalar, optionally followed by nothing but
    whitespace and/or a real trailing comment -- None otherwise (an
    unclosed scalar, or one followed by other same-line content a real
    YAML parser would reject as trailing garbage rather than accept as a
    validly-closed scalar).

    Two defeat classes this closes, both confirmed against PyYAML raising
    `ScannerError: found unexpected end of stream` on the exact input --
    issue #1987's own Step 8 adversarial review found both as instances
    of the same fail-open bypass class `_parse_frontmatter_fields` below
    already documents fixing once (an opened-but-never-closed leading
    quote with no trailing quote at all): a backslash-escaped trailing
    `"` inside a double-quoted scalar, and an un-paired trailing `''`
    inside a single-quoted scalar. `rest[0] == rest[-1]` alone (matching-
    first/last-character, the check this replaces) misclassifies both as
    closed. A third, correctness-only (not security-tier) defect this
    also closes: the matching-first/last-character check also
    misclassified a genuinely closed quoted scalar followed by a real
    same-line YAML comment (e.g. `"value" # note`) as UNclosed, since the
    comment text, not the closing quote, was the actual last character --
    a false FAIL on legitimate, safe frontmatter (confirmed against
    PyYAML: both `"value" # note` and `"value"#note`, no separating
    space, parse to `value` with the comment discarded).
    """
    if len(rest) < 2 or rest[0] not in ("'", '"'):
        return None
    closing = _closing_quote_index(rest)
    if closing is None:
        return None
    trailing = rest[closing + 1 :].lstrip()
    if trailing and not trailing.startswith("#"):
        return None
    return _unquote(rest[: closing + 1])


def _quote_is_genuinely_closed(rest: str) -> bool:
    """True when `rest` is a genuinely closed, single-line YAML quoted
    scalar (optionally followed only by whitespace/a real trailing
    comment) -- see `_quoted_scalar_value`'s own docstring for the full
    rationale and defeat cases this closes."""
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's
    # test_escaped_trailing_double_quote_is_not_exempt_and_still_fails_yaml_safety
    # and test_doubled_trailing_single_quote_is_not_exempt_and_still_fails_yaml_safety
    # exercise both the double-quote-backslash and single-quote-doubling
    # unclosed branches; the closed/genuinely-safe path (trailing-comment
    # included) is exercised by every other quoted-scalar test in the
    # same file. Same disclosed gate-side co-located-test gap as this
    # module's other WAIVED comments, not a real coverage hole.
    return _quoted_scalar_value(rest) is not None


def _unquote(raw: str) -> str:
    """Strip one matching pair of leading/trailing quote characters. Not a
    full YAML unescape (no backslash-escape decoding) -- sufficient for a
    length count and this checker's own synthetic fixtures, which never
    rely on escape-sequence-widened length."""
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py (not tests/test_gitapex_check_
    # channel_shape.py) exercises this function via
    # test_quoted_scalar_with_unsafe_substrings_passes_yaml_safety, which
    # depends on a quoted description being correctly unquoted. This gate's
    # own tests/test_{stem}.py-only crosswalk has no fallback for this
    # repository's pre-existing co-located test convention (the same
    # disclosed gap gitapex_check_skill_shape.py's own WAIVED comments
    # already name), not a real coverage hole.
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    return raw


def _parse_frontmatter_fields(text: str) -> tuple[dict[str, _Field] | None, bool]:
    """Split leading YAML-ish frontmatter into per-key fields.

    Returns ``(fields, malformed)``. ``fields`` is ``None`` when the text
    carries no frontmatter block at all (legitimately optional -- e.g.
    AGENTS.md) -- not itself a defect. ``malformed`` is True only when the
    text opens a ``---`` block but never closes it with a second ``---``
    line -- a real authoring defect, reported by check_shape() as a
    dedicated failed ``frontmatter-parsable`` result. When malformed is
    True, ``fields`` is always None: a broken block has nothing trustworthy
    to read fields out of, so downstream checks must treat it exactly like
    "no frontmatter" rather than guessing at a partial parse.
    """
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py (not tests/test_gitapex_check_
    # channel_shape.py) already calls this function (directly, and
    # indirectly through every check_shape() fixture test) for every
    # branch its own body takes: no frontmatter, an unterminated block, a
    # plain scalar, a quoted scalar, and a block scalar. This gate's own
    # tests/test_{stem}.py-only crosswalk has no fallback for this
    # repository's pre-existing co-located test convention (the same
    # disclosed gap gitapex_check_skill_shape.py's own WAIVED comments
    # already name), not a real coverage hole.
    normalized = text.replace("\r\n", "\n").lstrip("\ufeff")
    if not _FRONTMATTER_OPEN_RE.match(normalized):
        return None, False
    match = _FRONTMATTER_BLOCK_RE.match(normalized)
    if match is None:
        return None, True

    lines = match.group("body").split("\n")
    fields: dict[str, _Field] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line[:1] in ("", " ", "\t", "#"):
            i += 1
            continue
        key_match = _TOP_LEVEL_KEY_RE.match(line)
        if key_match is None:
            i += 1
            continue
        key = key_match.group("key")
        rest = key_match.group("rest").strip()
        i += 1
        if rest[:1] in ("|", ">"):
            block_lines: list[str] = []
            while i < n and (lines[i][:1] in (" ", "\t") or lines[i].strip() == ""):
                if lines[i].strip():
                    block_lines.append(lines[i].strip())
                i += 1
            fields[key] = _Field(style="block", value=" ".join(block_lines))
        elif (quoted_value := _quoted_scalar_value(rest)) is not None:
            # A genuinely closed quote pair only -- `rest[:1] in ("'", '"')`
            # alone (an earlier check this replaced) misclassified an
            # OPENED-BUT-NEVER-CLOSED quote (e.g. `"unsafe: value` with no
            # matching trailing quote) as "quoted" and therefore exempt
            # from yaml-plain-scalar-safety below, even though a real YAML
            # parser would not treat it as a valid, safely-quoted scalar
            # either -- a fail-open bypass a crafted description could
            # exploit to smuggle a colon-space/trailing-colon/hash pattern
            # straight past this checker. `_quoted_scalar_value` also
            # rejects an *escaped* trailing quote (see its own docstring)
            # -- a second instance of the same bypass class found by
            # issue #1987's own Step 8 adversarial review -- and, unlike
            # the boolean check this replaced, extracts the value up to
            # the real closing quote only, so a legitimate trailing
            # same-line comment after that quote is discarded rather than
            # retained as (incorrectly) part of the scalar's own value.
            fields[key] = _Field(style="quoted", value=quoted_value)
        elif rest == "":
            fields[key] = _Field(style="empty", value="")
        else:
            fields[key] = _Field(style="plain", value=rest)
    return fields, False


def _yaml_unsafe_reasons(value: str) -> list[str]:
    """The four YAML-breaking patterns an unquoted plain scalar must avoid
    (gitapex_check_skill_shape.py's own module docstring states the
    identical rule for a SKILL.md description; duplicated here per this
    module's own no-shared-import constraint, not re-derived independently).
    """
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's test_plain_scalar_* tests
    # exercise each of the four branches below directly (colon-space,
    # trailing colon, leading hash, space-hash). This gate's own
    # tests/test_{stem}.py-only crosswalk has no fallback for this
    # repository's pre-existing co-located test convention, not a real
    # coverage hole.
    reasons = []
    if ": " in value:
        reasons.append('contains ": " (colon + space)')
    if value.endswith(":"):
        reasons.append('ends with a trailing ":"')
    if value.startswith("#"):
        reasons.append('starts with "#"')
    if " #" in value:
        reasons.append('contains " #" (space + hash)')
    return reasons


def _description_checks(fields: dict[str, _Field] | None) -> list[CheckResult]:
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py directly exercises every branch
    # below (no description field, plain-scalar under/over/at the cap,
    # plain-scalar each of the four unsafe shapes, quoted-scalar exempt,
    # block-scalar exempt) via test_description_* and test_*_scalar_* --
    # same disclosed gate-side co-located-test gap as
    # _parse_frontmatter_fields above, not a real coverage hole.
    length_rule = f"description <= {DESCRIPTION_MAX_CHARS} chars"
    safety_rule = (
        "plain-scalar description avoids YAML-breaking patterns (colon-space, trailing colon, leading/embedded hash)"
    )
    if fields is None or "description" not in fields:
        na = "no frontmatter description field found (not-applicable)"
        return [
            CheckResult("description-length", True, length_rule, na),
            CheckResult("yaml-plain-scalar-safety", True, safety_rule, na),
        ]

    field = fields["description"]
    length_ok = len(field.value) <= DESCRIPTION_MAX_CHARS
    results = [
        CheckResult(
            "description-length",
            length_ok,
            length_rule,
            f"{len(field.value)} chars" if length_ok else f"{len(field.value)} chars exceeds {DESCRIPTION_MAX_CHARS}",
        )
    ]
    if field.style in ("quoted", "block"):
        results.append(
            CheckResult(
                "yaml-plain-scalar-safety",
                True,
                safety_rule,
                f"{field.style} scalar, exempt (already safe under a real YAML parser regardless of content)",
            )
        )
    else:
        reasons = _yaml_unsafe_reasons(field.value)
        results.append(
            CheckResult(
                "yaml-plain-scalar-safety",
                not reasons,
                safety_rule,
                "safe" if not reasons else "; ".join(reasons),
            )
        )
    return results


class _DeclaredBoundary(NamedTuple):
    """The Claude-side tool boundary a target's own frontmatter states.
    ``mode`` is "deny" (``disallowedTools:`` -- every token must end up
    denied) or "allow" (``tools:`` -- every token NOT in this list must end
    up denied, since ``tools:`` is an allow-list per this module's own
    "Claude Code sub-agent frontmatter" citation above)."""

    mode: str
    tokens: tuple[str, ...]


_COMMENT_START_RE = re.compile(r"(?:^|\s)#")


def _strip_trailing_comment(value: str) -> str:
    """Strip a real YAML plain-scalar trailing comment from `value` -- a
    `#` that is either the first character or immediately preceded by
    whitespace, through end of line. Confirmed against PyYAML: both
    'a, b # comment' and 'a,b#nothash' (no preceding whitespace) parse as
    expected -- the latter keeps '#nothash' as literal content, never a
    comment. Only meaningful for a PLAIN-style field's raw value; a
    quoted or block-scalar value has already had any real comment
    resolved (or excluded) by the parser itself."""
    match = _COMMENT_START_RE.search(value)
    if match is None:
        return value
    return value[: match.start()].rstrip()


def _boundary_field_tokens(field: _Field) -> tuple[str, ...]:
    """Tokenize a `tools:`/`disallowedTools:` field's own declared value
    into individual tool-name tokens, discarding a real trailing YAML
    comment first for a plain-style value. Without this, comment prose
    (e.g. `tools: Read, Grep  # not bash here`) tokenizes indistinguishably
    from real tool names -- a comment word that happens to match a real
    Claude tool name (`bash`, `edit`, ...) is then silently counted as
    declared-allowed, shrinking the required-denied OpenCode surface
    below what the frontmatter actually declares. Issue #1987's own
    Step 8 adversarial review found this as a live false-PASS on
    `tool-boundary-mapping-equivalent` -- the exact deterministic gate
    this module exists to keep honest -- confirmed by independently
    reproducing it: an allow-mode `tools:` value with a comment naming an
    otherwise-still-allowed tool passed the equivalence check even though
    the real `AGENT_SPECS` mapping never denied that tool."""
    value = _strip_trailing_comment(field.value) if field.style == "plain" else field.value
    return tuple(t for t in re.split(r"[,\s]+", value) if t)


def _declared_boundary(fields: dict[str, _Field] | None) -> _DeclaredBoundary | None:
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's test_*_tool_boundary_declared*
    # and test_*_mapping_* tests exercise both branches (disallowedTools
    # present, tools present, neither present) directly, and every
    # mapping-equivalence test depends on this function's own
    # tokenization -- same disclosed gate-side co-located-test gap as
    # above, not a real coverage hole.
    if fields is None:
        return None
    if "disallowedTools" in fields:
        return _DeclaredBoundary(mode="deny", tokens=_boundary_field_tokens(fields["disallowedTools"]))
    if "tools" in fields:
        return _DeclaredBoundary(mode="allow", tokens=_boundary_field_tokens(fields["tools"]))
    return None


def _tool_boundary_declared_check(fields: dict[str, _Field] | None) -> CheckResult:
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's
    # test_frontmatter_with_no_boundary_key_fails_tool_boundary_declared
    # and test_*_passes_tool_boundary_declared tests exercise both the
    # FAIL and PASS branches, and
    # test_no_frontmatter_at_all_passes_frontmatter_parsable_not_applicable
    # exercises the not-applicable branch -- same disclosed gate-side
    # co-located-test gap as above, not a real coverage hole.
    name = "tool-boundary-declared"
    rule = "frontmatter states disallowedTools: or tools:"
    if fields is None:
        return CheckResult(name, True, rule, "no frontmatter block found (not-applicable)")
    declared_keys = [k for k in _TOOL_BOUNDARY_KEYS if k in fields]
    if not declared_keys:
        return CheckResult(name, False, rule, "neither disallowedTools nor tools present in frontmatter")
    return CheckResult(name, True, rule, f"{', '.join(declared_keys)} present")


# Claude Code tool-name token (as written in `tools:`/`disallowedTools:`
# frontmatter) -> the OpenCode permission key that must be set to "deny"
# for an equivalent boundary. Grounded in hooks/gitapex_sync_opencode.py's
# own REVIEW_PERSONA_PERMISSION constant and its module comment -- the only
# place this repository's Claude-tool-name -> OpenCode-permission-key
# bridge is currently documented -- duplicated here (not imported) as a
# small, deliberately narrow table rather than a general cross-runtime
# tool-name resolver: this module's own synthetic-fixture-only proof scope
# (issue #1987's own Task 2) does not ask for, and this table does not
# attempt, coverage of every tool name either runtime documents.
_CLAUDE_TOOL_TO_OPENCODE_KEY = {
    "write": "edit",
    "edit": "edit",
    "bash": "bash",
    "webfetch": "webfetch",
    "websearch": "websearch",
    "task": "task",
    "agent": "task",
}

# The OpenCode permission-key "surface" an allow-list-mode boundary
# (`tools:`) is understood to protect, for tool-boundary-mapping-equivalent
# below: every key here not covered by an explicitly allowed token must be
# denied. Mirrors REVIEW_PERSONA_PERMISSION's own real key set
# (hooks/gitapex_sync_opencode.py) exactly, minus the keys that carry no
# Claude-tool-name counterpart at all (todowrite, question,
# external_directory, skill, lsp) -- those are OpenCode-only surface with no
# Claude-side frontmatter token to ever declare an equivalence claim about,
# so no synthetic fixture in this module's own test file needs them.
_MCP_TOKEN_PREFIX = "mcp__"  # noqa: S105 -- an MCP tool-name prefix, not a credential
_MCP_OPENCODE_KEY = "*mcp*"
_DENY_SURFACE_OPENCODE_KEYS = ("edit", "bash", "task", "webfetch", "websearch", _MCP_OPENCODE_KEY)


def _opencode_key_for_token(token: str) -> str | None:
    """The OpenCode permission key equivalent to one Claude tool-name
    token, or None when this module's own deliberately narrow table (above)
    has no translation for it. An `mcp__`-prefixed token (any MCP tool or
    server, per this module's own "Claude Code sub-agent frontmatter"
    citation) always maps to the wildcard "*mcp*" key -- the primary-source-
    confirmed OpenCode convention this module's own "OpenCode agent
    frontmatter" citation states ("permission keys are matched as wildcard
    patterns against the underlying tool name")."""
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's mapping-equivalence tests
    # (e.g. test_mapping_denies_wildcard_mcp_passes_mapping_equivalent_
    # deny_mode, test_mapping_full_surface_denied_passes_mapping_
    # equivalent_allow_mode) exercise this function through
    # _required_denied_opencode_keys. Same disclosed gate-side
    # co-located-test gap as above, not a real coverage hole.
    normalized = token.strip().lower()
    if normalized.startswith(_MCP_TOKEN_PREFIX):
        return _MCP_OPENCODE_KEY
    return _CLAUDE_TOOL_TO_OPENCODE_KEY.get(normalized)


def _required_denied_opencode_keys(boundary: _DeclaredBoundary) -> set[str] | None:
    """The OpenCode permission keys that must be denied for `boundary` to
    be equivalently reproduced. None when a "deny"-mode token has no known
    translation (_opencode_key_for_token) -- fails the equivalence check
    closed rather than silently under-checking an untranslatable token."""
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's
    # test_mapping_missing_one_key_fails_mapping_equivalent_allow_mode and
    # test_mapping_full_surface_denied_passes_mapping_equivalent_allow_mode
    # (plus the deny-mode equivalents) exercise both the "deny" and
    # "allow" branches. Same disclosed gate-side co-located-test gap as
    # above, not a real coverage hole.
    if boundary.mode == "deny":
        required: set[str] = set()
        for token in boundary.tokens:
            key = _opencode_key_for_token(token)
            if key is None:
                return None
            required.add(key)
        return required
    allowed_keys = {key for t in boundary.tokens if (key := _opencode_key_for_token(t)) is not None}
    return set(_DENY_SURFACE_OPENCODE_KEYS) - allowed_keys


def _mapping_denies_key(mapping: dict[str, str], key: str) -> bool:
    """True when `mapping` denies `key`, either by an exact key match or by
    an OpenCode wildcard-pattern key (e.g. "*mcp*") that matches it --
    fnmatch is the same glob-style matching OpenCode's own documented
    "matched as wildcard patterns" rule implies."""
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's
    # test_mapping_denies_wildcard_mcp_passes_mapping_equivalent_deny_mode
    # and test_mapping_unrelated_denial_fails_mapping_equivalent_deny_mode
    # exercise both the wildcard-match and no-match branches. Same
    # disclosed gate-side co-located-test gap as above, not a real
    # coverage hole.
    for mapped_key, value in mapping.items():
        if str(value).strip().lower() != "deny":
            continue
        if mapped_key == key or fnmatch.fnmatchcase(key, mapped_key):
            return True
    return False


def _load_agent_specs(repo_root: Path) -> tuple[tuple[tuple[str, dict[str, str] | None], ...] | None, str | None]:
    """Load hooks/gitapex_sync_opencode.py's own AGENT_SPECS by file path
    (importlib.util.spec_from_file_location + exec_module), not a
    sys.path.insert + bare `import` -- this avoids mutating the interpreter's
    global sys.path/sys.modules state for what is, from this module's own
    side, a single one-off read of one sibling module's one exported
    constant. `hooks/` is a repository-root, non-skill directory: per
    docs/repository-layout.md, only `skills/` (and, "in the future",
    `hooks/`) are deployed runtime primitives -- `hooks/` is NOT currently
    deployed, so a standalone vendor of just this skill (without the rest of
    the gitapex repository) would not carry hooks/gitapex_sync_opencode.py
    at all. This is a different shape from issue #1963's own correction C4
    (a shared module between two *skills'* own `scripts/` directories,
    which C4 forbids): C4's own stated concern is specifically a skill
    depending on ANOTHER SKILL's scripts/, not a skill depending on a
    non-skill, repository-root module. But it carries a related, disclosed
    risk of its own: this checker's own tool-boundary-mapping-* checks are
    inherently gitapex-repository-specific (they ask about THIS
    repository's own hooks/gitapex_sync_opencode.py, not a general
    property), matching this skill's own declared "Portability: Mixed" (not
    "Portable") -- a Mixed skill legitimately carries this class of
    repository-operational dependency, per gitapex_check_skill_shape.py's
    own established distinction between what Portable and Mixed/
    Repository-scoped content may depend on. Returns (None, reason) rather
    than raising when hooks/ is missing, unreadable, or carries no
    AGENT_SPECS -- so a vendored deployment without hooks/ reports the two
    mapping checks as a clear FAIL (per this module's own fail-closed
    contract), never an unhandled exception escaping check_shape().
    """
    # function-body-test-coverage: WAIVED: unlike this module's other
    # helpers, this one genuinely has NO direct test in this diff -- every
    # test in the co-located test_gitapex_check_channel_shape.py injects a
    # synthetic `agent_specs` tuple into check_shape() instead, bypassing
    # this function entirely, by this module's own explicit design (issue
    # #1987's own Task 2 scope is synthetic-fixture-only; proving this
    # loader against the real hooks/gitapex_sync_opencode.py -- and
    # against a vendored deployment missing it -- is left to Task 4 or a
    # follow-up, not silently claimed covered here). Disclosed as a real,
    # deliberate gap, not the co-located-test-convention gate-side blind
    # spot this module's other WAIVED comments name.
    hooks_path = repo_root / _HOOKS_RELATIVE_PATH
    if not hooks_path.is_file():
        return None, f"{hooks_path} not found (vendored without gitapex's own hooks/ directory?)"
    try:
        spec = importlib.util.spec_from_file_location("_gitapex_sync_opencode_for_channel_shape", hooks_path)
        if spec is None or spec.loader is None:
            return None, f"could not build an import spec for {hooks_path}"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:  # any import-time failure must fail closed as a CheckResult (see docstring above), never escape check_shape
        return None, f"{type(exc).__name__}: {exc}"
    agent_specs = getattr(module, "AGENT_SPECS", None)
    if agent_specs is None:
        return None, f"{hooks_path} carries no AGENT_SPECS"
    return agent_specs, None


def _tool_boundary_mapping_checks(
    boundary: _DeclaredBoundary | None,
    target_filename: str,
    agent_specs: tuple[tuple[str, dict[str, str] | None], ...] | None,
    agent_specs_error: str | None,
) -> list[CheckResult]:
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's test_*_mapping_present* and
    # test_*_mapping_equivalent* tests exercise every branch (no boundary
    # declared, agent_specs load error, filename absent, entry None,
    # entry present-but-non-equivalent, entry present-and-equivalent,
    # both "deny" and "allow" declaration modes) by passing a synthetic
    # `agent_specs` tuple directly into check_shape() -- same disclosed
    # gate-side co-located-test gap as above, not a real coverage hole.
    present_rule = (
        "hooks/gitapex_sync_opencode.py's AGENT_SPECS carries a non-None permission mapping for this filename"
    )
    equivalent_rule = (
        "the mapping denies an OpenCode-permission-key equivalent of every declared Claude-side boundary token"
    )

    if boundary is None:
        na = "no declared tool boundary (not-applicable)"
        return [
            CheckResult("tool-boundary-mapping-present", True, present_rule, na),
            CheckResult("tool-boundary-mapping-equivalent", True, equivalent_rule, na),
        ]

    if agent_specs_error is not None:
        evidence = f"could not load hooks/gitapex_sync_opencode.py's AGENT_SPECS: {agent_specs_error}"
        return [
            CheckResult("tool-boundary-mapping-present", False, present_rule, evidence),
            CheckResult("tool-boundary-mapping-equivalent", False, equivalent_rule, evidence),
        ]

    by_filename = dict(agent_specs or ())
    if target_filename not in by_filename:
        evidence = f"{target_filename!r} not found in AGENT_SPECS"
        return [
            CheckResult("tool-boundary-mapping-present", False, present_rule, evidence),
            CheckResult("tool-boundary-mapping-equivalent", False, equivalent_rule, "no mapping present"),
        ]

    mapping = by_filename[target_filename]
    if mapping is None:
        evidence = f"AGENT_SPECS[{target_filename!r}] is None (no permission mapping)"
        return [
            CheckResult("tool-boundary-mapping-present", False, present_rule, evidence),
            CheckResult("tool-boundary-mapping-equivalent", False, equivalent_rule, "no mapping present"),
        ]

    present_result = CheckResult(
        "tool-boundary-mapping-present", True, present_rule, f"AGENT_SPECS[{target_filename!r}] carries a mapping"
    )
    required = _required_denied_opencode_keys(boundary)
    if required is None:
        equivalent_result = CheckResult(
            "tool-boundary-mapping-equivalent",
            False,
            equivalent_rule,
            f"no known OpenCode-permission-key translation for one or more declared tokens: {list(boundary.tokens)}",
        )
        return [present_result, equivalent_result]

    missing = sorted(key for key in required if not _mapping_denies_key(mapping, key))
    equivalent_result = CheckResult(
        "tool-boundary-mapping-equivalent",
        not missing,
        equivalent_rule,
        "all required keys denied" if not missing else f"mapping does not deny: {', '.join(missing)}",
    )
    return [present_result, equivalent_result]


_UNSET = object()


def check_shape(
    target: Path,
    *,
    agent_specs: object = _UNSET,
    repo_root: Path | None = None,
) -> list[CheckResult]:
    """Check one AGENTS.md/agents/*.md/.claude/agents/*.md file's shape.

    ``agent_specs``, when passed explicitly (as a tuple, or as None to mean
    "no AGENT_SPECS available"), is used as-is instead of loading
    hooks/gitapex_sync_opencode.py -- this is how this module's own test
    file proves the tool-boundary-mapping-* checks against synthetic
    fixtures without touching the real hooks/ directory. Left unset (the
    default, matching Task 4's own real-tree usage), AGENT_SPECS is loaded
    from hooks/gitapex_sync_opencode.py under ``repo_root`` (default: this
    file's own repository root, three directories up from
    skills/evaluating-context-channel-maturity/scripts/).
    """
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py exercises this function
    # directly in every single test -- the channel-file-readable/
    # frontmatter-parsable short-circuits, and the full pass-through to
    # every check above, via a synthetic tmp_path fixture per test plus
    # an injected `agent_specs` parameter (never the real
    # hooks/gitapex_sync_opencode.py) -- same disclosed gate-side
    # co-located-test gap as above, not a real coverage hole.
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [
            CheckResult(
                "channel-file-readable",
                False,
                "target file is readable as UTF-8 text",
                f"{type(exc).__name__}: {exc}",
            )
        ]

    results: list[CheckResult] = [
        CheckResult("channel-file-readable", True, "target file is readable as UTF-8 text", "readable")
    ]

    fields, malformed = _parse_frontmatter_fields(text)
    results.append(
        CheckResult(
            "frontmatter-parsable",
            not malformed,
            "a `---`-opened frontmatter block is properly closed by a second `---` line",
            "no frontmatter block, or a well-formed one" if not malformed else "opens '---' but never closes it",
        )
    )

    results.extend(_description_checks(fields))

    boundary = _declared_boundary(fields)
    results.append(_tool_boundary_declared_check(fields))

    if agent_specs is _UNSET:
        root = repo_root if repo_root is not None else Path(__file__).resolve().parents[3]
        loaded_specs, agent_specs_error = _load_agent_specs(root)
    elif agent_specs is None:
        loaded_specs, agent_specs_error = None, "no AGENT_SPECS supplied"
    else:
        loaded_specs, agent_specs_error = agent_specs, None  # type: ignore[assignment]

    results.extend(_tool_boundary_mapping_checks(boundary, target.name, loaded_specs, agent_specs_error))
    return results


def format_report(results: list[CheckResult]) -> str:
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's
    # test_format_report_prints_check_names_and_pass_fail_counts calls
    # this function directly. Same disclosed gate-side co-located-test
    # gap as above, not a real coverage hole.
    width = max((len(r.name) for r in results), default=5)
    lines = [f"{'CHECK'.ljust(width)}  RESULT  EVIDENCE (rule)"]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"{r.name.ljust(width)}  {status}    {r.evidence}  ({r.rule})")
    passed = sum(1 for r in results if r.passed)
    lines.append(f"\n{passed}/{len(results)} checks passed")
    return "\n".join(lines)


def _validate_read_scope(target: Path, allowed_root: Path) -> None:
    """Reject a target outside `allowed_root`, or a symlink anywhere in its
    own path -- the same caller-approved-root/no-symlinks contract
    gitapex_check_skill_shape.py's own --allowed-root guard states, applied
    here to a single file target rather than a skill directory tree.

    Walks every path component between `allowed_root` and `target`, not
    only `target` itself: issue #1987's own Step 8 adversarial review
    found that checking only `target.is_symlink()` did not match this
    function's own stated "symlink anywhere in its own path" contract --
    an intermediate symlinked directory component was never inspected.
    `os.path.abspath` (not `Path.resolve()`) absolutizes both paths
    first, deliberately WITHOUT following symlinks, so the loop below can
    still see -- and reject -- each symlinked component along the way;
    resolving first would collapse the very links this check exists to
    catch, the same reasoning gitapex_check_skill_shape.py's own
    equivalent guard states for its own identical PTH100-waived calls."""
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's
    # test_main_allowed_root_rejects_outside_target,
    # test_validate_read_scope_accepts_inside_target, and
    # test_validate_read_scope_rejects_symlinked_intermediate_directory
    # call this function (directly, and through main()'s own
    # --allowed-root path). Same disclosed gate-side co-located-test gap
    # as above, not a real coverage hole.
    root = Path(os.path.abspath(allowed_root))  # noqa: PTH100
    candidate = Path(os.path.abspath(target))  # noqa: PTH100
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{target} resolves outside --allowed-root {allowed_root}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{current} is a symlink, which --allowed-root refuses to read")

    resolved_root = root.resolve()
    resolved_target = candidate.resolve()
    if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
        raise ValueError(f"{target} resolves outside --allowed-root {allowed_root}")


def main(argv: list[str] | None = None) -> int:
    # function-body-test-coverage: WAIVED: this diff's own co-located
    # test_gitapex_check_channel_shape.py's test_main_* tests call
    # main([...]) directly and assert on its return code for the
    # clean-pass, failing-check, missing-target, and
    # --allowed-root-rejection branches -- same disclosed gate-side
    # co-located-test gap as above, not a real coverage hole.
    parser = argparse.ArgumentParser(
        description="Check one or more AGENTS.md/agents/*.md/.claude/agents/*.md files' deterministic shape (read-only)."
    )
    parser.add_argument(
        "--allowed-root",
        help="Caller-approved directory that must contain every target; also rejects a symlinked target.",
    )
    parser.add_argument("target", nargs="+", help="One or more paths to a channel file.")
    args = parser.parse_args(argv)
    allowed_root = Path(args.allowed_root) if args.allowed_root else None

    guard_error = False
    check_error = False
    for raw in args.target:
        target = Path(raw)
        if allowed_root is not None:
            try:
                _validate_read_scope(target, allowed_root)
            except (OSError, ValueError) as exc:
                print(f"error: unsafe target path: {exc}", file=sys.stderr)
                guard_error = True
                continue
        if not target.is_file():
            print(f"error: no such file: {target}", file=sys.stderr)
            guard_error = True
            continue
        results = check_shape(target)
        print(f"{target}:")
        print(format_report(results))
        if not all(r.passed for r in results):
            check_error = True

    if guard_error:
        return 2
    return 1 if check_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
