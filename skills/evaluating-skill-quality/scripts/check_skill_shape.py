"""Deterministic shape checker for a SKILL.md and its references/ dir.

Single source of truth for the deterministic "shape" lane of the
evaluating-skill-quality skill. It decides only the mechanically
checkable rules; the nine maturity dimensions stay model-judged and are
deliberately NOT implemented here.

Read-only: reads the target skill's files only. No writes, no network,
no mutation. Effects are limited to stdout and the process exit code.

Checks (the canonical list -- the manual fallback is to apply these):
  - description: present/non-empty, no XML tags, <= 1024 chars, and --
    only when actually written as an unquoted YAML plain scalar in the
    source (the form every SKILL.md in this repository currently uses) --
    safe against ": " (colon + whitespace) or a trailing ":" (either reads
    as the start of a new mapping key to a real YAML parser and breaks
    parsing), and against " #" or a leading "#" (reads as a comment marker
    and silently truncates the rest of the value). A description that is
    instead quoted or a block scalar (">"/"|") is exempt from this specific
    check, since those forms are already safe under a real YAML parser
    regardless of content. This checker's own frontmatter parser is
    deliberately lenient and does not reproduce either failure on its own,
    so this is a dedicated check rather than a side effect of parsing.
  - name (only if present): lowercase-hyphenated, <= 64 chars,
    no XML tags, contains no reserved word (anthropic, claude)
  - SKILL.md body: <= 500 lines
  - metadata sidecar (metadata/gitapex.yaml, under the skill directory):
    present; has no malformed top-level lines (manifest-parsable -- a
    column-0 line that is not blank/comment/document-marker and does not
    match the top-level "key:" pattern, e.g. a stray "- invalid mapping
    entry"); apiVersion is gitapex.io/v1alpha1 and kind is SkillMetadata;
    metadata.name equals the skill directory name; spec.portability is one
    of Portable/Repository-scoped/Mixed; spec.capabilityAssumption is one
    of Broad/Frontier/Adaptive; spec.references, if present, is a non-empty
    list of non-empty scalar strings, each item consistently indented with
    its own list, not an unquoted YAML mapping key such as "path: foo", and
    not an unquoted null/boolean/numeric scalar such as "null"/"true"/"123"
    (issue #356: a real YAML parser resolves such a plain scalar to that
    type, not a string, so it must fail rather than be silently accepted
    as one; a quoted item, e.g. "\"true\"", is unaffected -- it is a
    deliberate string regardless of its contents)
    (references-well-formed); spec.skillDependencies, if present, is a
    mapping -- itself never real YAML null (a block header with no
    requires/relatedTo key at all under it fails as the wrong type rather
    than being read as "declared, nothing inside": see the
    absent-vs-null-vs-empty paragraph below) -- with only the keys
    requires/relatedTo, each -- if present -- a
    list of non-empty scalar strings with the same per-item shape rules as
    spec.references (including the same null/boolean/numeric-scalar
    rejection), except an empty list is valid here, unlike
    spec.references (skill-dependencies-well-formed); every name listed in
    either list resolves to an existing sibling skill directory
    (skill-dependencies-resolve); and a non-empty
    spec.skillDependencies.requires is incompatible with
    spec.portability: Portable (requires-portability-compatible).
    spec.lifecycle, if present, is a mapping -- likewise never real YAML
    null, per the same rule -- with only the keys
    experimental/deprecated/stable/renamedFrom. experimental
    (reason/trackingIssue required, since optional), deprecated
    (reason/replacement required, since/removeAfter optional), and stable
    (since required, compatibilityGuarantee optional) are each -- if
    present -- a mapping of their own recognized scalar fields (each,
    like spec.lifecycle itself, failing as the wrong type rather than
    passing as an empty mapping when its own header is left blank with
    no field at all under it);
    renamedFrom, if present, is a non-empty scalar string (not a
    sub-block). since/removeAfter, if present, must be real calendar
    dates in strict YYYY-MM-DD shape; trackingIssue, if present, an
    anchored #123 or owner/repo#123 reference; compatibilityGuarantee, if
    present, one of Alpha/Beta/GA (lifecycle-well-formed); and, when
    deprecated.replacement is a non-empty string, it resolves to an
    existing sibling skill directory, the same dangling-reference gate
    spec.skillDependencies uses (lifecycle-deprecated-replacement-resolves).
    experimental and deprecated are independent and optional -- neither
    implies nor excludes the other -- but experimental and stable are
    mutually exclusive: a non-empty spec.lifecycle.experimental cannot
    coexist with a non-empty spec.lifecycle.stable
    (experimental-stable-compatible). renamedFrom is deliberately NOT
    resolved against sibling directories, unlike deprecated.replacement
    -- it names the skill's own former, now-nonexistent directory name
    (a git mv target), backward-pointing on the surviving skill rather
    than a forward-pointing tombstone on a directory that no longer
    exists. No skill's runtime procedure may read or branch on any part
    of spec.lifecycle (the sidecar's behavior-neutrality invariant).
    spec.executionRequirements, if present, is a mapping with only the
    tools key so far (issue #349, GitApex sidecar execution-requirement
    schema, Workstream W1 first slice of the parent tracking issue --
    filesystem/network/mcp/credentials/browser/externalServices/context
    categories are deferred to sibling child issues and, until they land,
    any key other than tools here is an unknown key, not reserved space);
    tools, if present, is itself a mapping -- like spec.executionRequirements
    itself, never real YAML null -- with only the keys
    read/write/shell, each -- if present -- a list of non-empty scalar
    strings (free-form capability tags; this issue does not define a
    fixed vocabulary), with the same per-item shape rules
    (mapping-like-item, indent-consistency, and null/boolean/numeric-scalar
    detection) spec.references and spec.skillDependencies items already use
    (execution-requirements-well-formed). An absent executionRequirements
    block, an absent tools block, or an absent read/write/shell key each
    mean "not yet declared"; an explicit empty list (e.g. read: [])
    means "declared, zero tools of that kind needed" -- a deliberate
    statement, not the same as absence.

    Three-way absent/null/empty-mapping distinction (issue #356, ACM row
    2), shared by every gated *mapping*-valued block above
    (spec.skillDependencies, spec.lifecycle and each of its
    experimental/deprecated/stable sub-blocks, spec.executionRequirements,
    and spec.executionRequirements.tools): the key never appearing at all
    means "not declared" (optional, passes); the key appearing with a
    blank value and no child key ever following at the next indent level
    is real YAML null -- a real YAML parser never reads a bare block
    header followed by a dedent as an empty mapping, so this checker
    fails it as the wrong type rather than reading it as "declared,
    nothing inside" (the bug the issue reported: "A blank tools: value is
    YAML null, but the parser converts it to an empty mapping and
    passes"); and the key appearing with at least one real child key
    (however that child's own value turns out) is a genuine, non-null
    mapping, checked normally -- there is no way to spell "declared, but
    deliberately an empty mapping" in this parser's supported block-style
    subset (it has no inline flow-mapping "{}" support anywhere), so that
    third state does not exist for these fields the way an explicit empty
    *list* (read: []) does for list-valued fields. This distinction does
    NOT extend to list-valued keys (spec.references;
    spec.skillDependencies.requires/relatedTo;
    spec.executionRequirements.tools.read/write/shell) -- a blank list
    header is still read as an empty list, unchanged, matching each
    field's own already-established "explicit empty list is a deliberate
    statement" semantics documented above. Other
    ungated sidecar fields (e.g. spec.evalStatus) are parsed into the spec
    map by _parse_manifest only if written as a single inline scalar; a
    nested/block-shaped field (e.g. evalStatus's documented baseline:/lift:
    children) is dropped entirely, not gated/checked here or anywhere --
    only nested maps and list items under them are skipped by the parser,
    and indented lines are never flagged as malformed regardless of shape.
  - references/ files: exactly one level deep
  - any references/ file over 100 lines: contains a table of contents
    (a Markdown heading matching "Table of contents" or "Contents",
    case-insensitive). Junk files (dotfiles, __pycache__, non-UTF-8) under
    references/ are ignored, not flagged.
  - SKILL.md body: every Markdown link target -- inline ([text](path))
    or reference-style ([text][label] resolved via a [label]: path
    definition) -- that is not an absolute URL/scheme (http(s):,
    mailto:, etc.) or a bare in-page fragment (#section) must resolve
    inside the skill's own directory -- a relative link that escapes it
    (e.g. "../../docs/x.md") fails. This
    gives the skill's own "Portable" self-declaration (whose definition
    already requires every instruction to resolve inside the skill's own
    folder) a deterministic backstop.
  - Markdown anchor-fragment resolution (anchor-targets-resolve, issue
    #280 row 11 / issue #289): every Markdown link's ``#fragment`` --
    inline or reference-style, same as the check above -- must match a
    real heading anchor GitHub's own renderer would generate for the
    link's target file (the link's own file, when no path is given, or
    the resolved path otherwise). Runs on SKILL.md (bare check name,
    mirroring links-inside-skill's own SKILL.md-only scope) and
    independently on every references/*.md file (``anchor-targets-
    resolve:{ref.name}``, mirroring toc:{ref.name}'s per-file naming and
    loop, but unconditionally -- not gated on the 100-line TOC threshold,
    since an anchor mismatch is not correlated with file length). Reuses
    this check's own link-gathering rules verbatim (same absolute-URL/
    scheme skip, same reference-style-definition support), plus stripping
    an inline link's optional CommonMark title before reading its
    fragment. A link whose path resolves outside the skill directory is
    silently skipped here -- that is links-inside-skill's own separate
    failure, not duplicated by this check. A target file that cannot be
    read (missing, a directory, binary, non-UTF-8), by contrast, IS
    flagged as broken: there is no real heading it could possibly expose,
    so a dangling `[ghost](references/missing.md#x)`-shaped link is
    exactly the defect class this check exists to catch, not a case to
    tolerate the way the references/ TOC check above tolerates junk files
    it merely iterates past. GitHub's real heading-slug algorithm:
    recognizes both ATX headings (``#`` through ``######``, 0-3 leading
    spaces, an optional trailing closing ``#`` sequence stripped before
    slugging) and Setext headings (a text line immediately underlined by
    a run of ``=`` or ``-``); lowercases the heading text, strips a fixed
    punctuation denylist (ASCII punctuation plus two Unicode punctuation
    blocks) while preserving every Unicode letter/digit plus underscore/
    hyphen/space -- not an ASCII-only allowlist, since GitHub's own
    slugger preserves accented and non-Latin letters -- then each
    surviving space becomes its own literal ``-`` (adjacent stripped
    punctuation is not collapsed first, so e.g. "Trust & authority" ->
    "trust--authority", a real in-repo example). A slug that repeats an
    earlier heading's slug earns the lowest ``-1``, ``-2``, ... suffix not
    already claimed by some OTHER heading's own literal slug (not simply
    a per-base occurrence count, which can under-suffix and collide when
    a document already contains a heading literally named e.g. "Foo-1"),
    counted across every heading in the target document in order -- not
    only the ones actually linked. A heading-shaped line inside a fenced
    code block is never treated as a real heading (the same fence-
    blanking already used for the citation checks below, which also
    normalizes CRLF/CR line endings to bare ``\n`` first).
  - Bare issue/PR-number citation (no-bare-issue-citation, issue #254):
    no bare-prose GitHub issue/PR-number citation (#149 or owner/repo#149)
    in SKILL.md or references/*.md body text. Runs unconditionally on
    every skill regardless of declared portability level -- Portable,
    Mixed, and Repository-scoped alike, unlike the two repo-path checks
    below. A bare #N auto-links relative to whichever repository
    currently hosts the file and silently resolves to the wrong issue
    once the skill is vendored or simply read out of context, and that
    risk does not depend on the skill's declared portability: a Mixed or
    Repository-scoped skill's own issue/PR provenance belongs in the
    metadata sidecar's spec.references instead (maintainer-facing, never
    auto-loaded), not a bare number sitting in prose. Other repo-specific
    content -- sibling-skill names, repo-specific paths/conventions --
    remains legitimate Mixed/Repository-scoped territory; this rule is
    narrowly about issue/PR numbers. Matches inside inline code (`#149`),
    fenced code blocks, absolute URLs, and Markdown links are excluded from
    THIS bare-prose scan -- those are the established ways this repo's
    skills quote such a token illustratively without it resolving live.
    Inline code is not unconditionally safe, though: for Portable-declared
    content specifically, the separate check below (issue #263) re-inspects
    exactly the inline-code spans this scan skips.
  - Portable self-citation, repo-path half (only when the skill declares
    "Portable", not "Mixed" or "Repository-scoped" -- unlike the
    issue-number scan above, these two checks stay level-gated:
    operational dependence on a repo-specific *path* is the legitimate,
    undisputed core of what Mixed/Repository-scoped is for, and there is
    no URL-equivalent escape hatch for a filesystem path the way there is
    for an issue number). The declaration is read sidecar-primary with a
    body-marker fallback: the sidecar's spec.portability decides whenever
    it is present and usable -- the form every skill in this repository
    uses -- a skill with no sidecar at all (typically one vendored in
    from another repository) falls back to the near-top
    "**Portability: <level>.**" body marker, and a skill whose sidecar
    exists but is unreadable or carries no recognised spec.portability
    runs the scan unconditionally (a false negative in a gate is worse
    than a false positive, and such a skill is already failing
    portability-declared) -- so no Portable-declared skill state ever
    silently skips it. The scan itself: no bare-prose origin-repository
    path citation (evals/... or docs/...) in SKILL.md or references/*.md
    body text. A repo-relative path breaks the same way a bare issue
    number does once the skill is vendored. Matches inside inline code
    (`evals/...`), fenced code blocks, absolute URLs, and Markdown links
    are excluded -- those are the established ways this repo's Portable
    skills quote such a token illustratively without it resolving live.
    This is the deterministic backstop for the rubric's dimension-6
    Portable-skill rule; the semantic judgment of whether a citation is
    illustrative context vs. the skill's own bookkeeping stays with that
    model-judged dimension.
  - Portable inline-code repo-path citation without a hedge (issue #220,
    narrowing the blind spot the exemption above leaves open): treating
    every inline-code path citation as automatically illustrative was
    itself the gap -- an inline-code `evals/...`/`docs/...` citation reads
    exactly as authoritative as a bare-prose one to a reader who has no
    way to tell "illustrative example" from "this repository's own real
    file" from the backticks alone. This check re-inspects exactly the
    inline-code spans the bare-prose scan above deliberately skips, and
    fails one that has no approved hedge phrase (HEDGE_PHRASES) in its own
    sentence or the sentence immediately before it -- this repository's
    own established convention for marking such a citation as deliberate
    rather than a dangling self-reference (see e.g. rubric.md's "This
    repository has also used ..." and scorer-gated-skill-edits/SKILL.md's
    "This repository has also recorded ..."). The citation's own inline-code
    text is excluded from that hedge search, so a citation cannot
    self-satisfy the requirement merely because its own path happens to
    contain a hedge word (e.g. a path under `docs/superpowers/specs/`
    literally named with "gitapex" in it). Fenced code blocks stay exempt
    unconditionally, as the module docstring above already covers -- this
    check never runs on blocks, only on inline code, since a worked
    example's illustrative fenced output is a different, already-settled
    case (issue #171 acceptance criterion 3) that this issue does not
    reopen.
  - Portable inline-code issue/PR-number citation without a hedge (issue
    #263, the same blind spot as #220 above but for issue numbers instead
    of repo paths): the bare-issue-citation scan's inline-code exclusion
    (see its own entry above) let a fictional worked-example citation like
    `` `#42` `` or `` `#142` `` sit in Portable content indefinitely, since
    dimension 6's rubric bans an issue/PR-number citation from Portable
    content even fully hedged inside inline code. This check re-inspects
    exactly the inline-code spans the bare-prose scan above deliberately
    skips, and fails one with no approved hedge phrase
    (ISSUE_CITATION_HEDGE_PHRASES -- see that constant's own comment for the
    full rationale, including why its phrase list is separate from and
    narrower than HEDGE_PHRASES) nearby. Portable-gated, alongside the two
    repo-path checks above, unlike the unconditional bare-prose scan.

Usage:
  python3 check_skill_shape.py <skill-dir-or-SKILL.md>

Exit code: 0 if every check passes, 1 if any check fails, 2 on bad usage or
when no readable SKILL.md is found.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os.path
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# The Claude Developer Platform Skills API enforces description <= 1024
# chars and name <= 64 lowercase-hyphen chars (platform.claude.com/docs/
# en/agents-and-tools/agent-skills/best-practices) -- stricter than Claude
# Code's own frontmatter parsing, so this checker uses the platform's
# tighter cap to stay valid on both surfaces.
DESCRIPTION_MAX_CHARS = 1024
NAME_MAX_CHARS = 64
# "Keep SKILL.md body under 500 lines for optimal performance" (same doc;
# also code.claude.com/docs/en/skills).
BODY_MAX_LINES = 500
# Not an Anthropic-specified number -- this repository's own convention
# for when a reference file earns a table of contents, chosen as a round
# threshold past which skimming a flat file gets slow.
TOC_MIN_LINES = 100
RESERVED_NAME_WORDS = ("anthropic", "claude")

# The sidecar is this repository's own metadata convention, not part of the
# Anthropic Agent Skills standard -- hence its own metadata/ subdirectory
# and gitapex-labelled apiVersion. It is never auto-loaded by the skill
# runtime, so it can never change skill behavior.
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"
# Kubernetes-manifest-shaped envelope, borrowed as a convention only; the
# version lets the schema grow without breaking older sidecars.
EXPECTED_API_VERSION = "gitapex.io/v1alpha1"
EXPECTED_KIND = "SkillMetadata"
PORTABILITY_LEVELS = ("Portable", "Repository-scoped", "Mixed")
CAPABILITY_ASSUMPTIONS = ("Broad", "Frontier", "Adaptive")
# A plain "- <value>" list item, indented 2 or more spaces -- real YAML
# accepts a block sequence indented level with its mapping key (2 spaces,
# same as spec.references' own key) or further indented (4 spaces, this
# repo's convention); requiring one exact width would silently drop an
# otherwise-valid item at a different indent instead of reading it. The
# only list shape this parser understands, and only under spec.references
# specifically.
REFERENCES_LIST_ITEM_RE = re.compile(r"^[ ]{2,}-\s*(.*)$")
# An unquoted item that itself looks like a YAML mapping key ("key: value"
# or a bare "key:"), e.g. "- path: references/rubric.md" -- real YAML
# parses that as a single-key mapping, not a scalar string, and this
# parser has no map-shaped-item support. A quoted string starting with
# this same text (e.g. "\"path: something\"") is a deliberate scalar and
# is excluded by the caller checking for a wrapping quote first.
REFERENCES_MAPPING_LIKE_RE = re.compile(r"^[A-Za-z0-9_.-]+:(\s|$)")
# An unquoted plain scalar that YAML's core schema resolves to something
# OTHER than a string -- null, boolean, or numeric -- rather than the
# string every list-of-scalar-strings field (spec.references,
# spec.skillDependencies.requires/relatedTo,
# spec.executionRequirements.tools.read/write/shell) assumes each of its
# items is (issue #356: "Unquoted YAML scalars such as true, 123, and
# null are converted to strings in list-valued fields and pass a
# list-of-strings check"). Deliberately the common, uncontroversial
# subset -- not YAML 1.1's yes/no/on/off, which are also ordinary English
# words a legitimate capability-tag or reference string could contain --
# rather than a full type resolver. Checked only against an UNQUOTED
# item's raw text; a caller already tests for a wrapping quote first (the
# same way REFERENCES_MAPPING_LIKE_RE above is only checked when
# unquoted), since a quoted item (e.g. "\"true\"") is a deliberate string
# regardless of its contents.
YAML_NON_STRING_SCALAR_RE = re.compile(
    r"^(?:~|[Nn]ull|NULL"
    r"|[Tt]rue|TRUE|[Ff]alse|FALSE"
    r"|[-+]?[0-9]+"
    r"|[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$")
# A real YAML comment: an unquoted "#" preceded by start-of-string or
# whitespace -- YAML never treats a "#" glued directly onto a preceding
# non-space character as a comment marker (e.g. "true#tag" is the
# literal string "true#tag", not "true" plus a comment). Used only to
# strip a trailing comment before classifying an unquoted list item's own
# scalar type in _is_non_string_plain_scalar below -- the item's stored
# value is unaffected either way, only the type classification is (Codex
# review on this PR: a comment-bearing item such as "true # rationale"
# defeated YAML_NON_STRING_SCALAR_RE's own full-string anchor on its own,
# silently certifying a real YAML boolean/null/numeric as a string
# whenever it carried a trailing comment).
_INLINE_COMMENT_RE = re.compile(r"(?:^|\s)#.*$")


def _is_non_string_plain_scalar(raw_text: str) -> bool:
    """Whether an UNQUOTED list item's raw text is a YAML null/boolean/
    numeric scalar rather than a string, comment stripped first the same
    way a real YAML parser would before resolving the item's type.
    Shared by every gated list-of-scalar-strings site (spec.references;
    spec.skillDependencies.requires/relatedTo;
    spec.executionRequirements.tools.read/write/shell)."""
    stripped = _INLINE_COMMENT_RE.sub("", raw_text).strip()
    return bool(YAML_NON_STRING_SCALAR_RE.match(stripped))

# spec.skillDependencies's two recognized subkeys, and the shape of their
# lines. Subkeys sit at 4 spaces (one level under skillDependencies' own
# 2-space key). List items accept 4 or more spaces -- real YAML allows a
# block sequence indented level with its own key (4 spaces, same as
# "requires:"/"relatedTo:" themselves) or further indented (this repo's
# convention); requiring one exact width would silently drop an otherwise-
# valid item at a different indent instead of reading it, the same
# accommodation REFERENCES_LIST_ITEM_RE already makes for spec.references.
SKILL_DEPENDENCY_SUBKEYS = ("requires", "relatedTo")
SKILL_DEP_LIST_ITEM_RE = re.compile(r"^[ ]{4,}-\s*(.*)$")

# spec.lifecycle's three recognized sub-blocks -- "experimental" (entry
# side: not yet proven, mirrors Rust's #[unstable(feature, issue)],
# Python's provisional/PendingDeprecationWarning APIs, Go's
# GOEXPERIMENT-gated features, Kubernetes' alpha/beta feature gates),
# "deprecated" (exit side: superseded, mirrors Rust's
# #[deprecated(since, note)], Go's "// Deprecated:" doc comment, Python's
# warnings.deprecated/PEP 702, Kubernetes' API deprecation policy), and
# "stable" (a graduation record, mirrors Rust's
# #[stable(feature, since)]). experimental and deprecated are independent
# -- neither implies nor excludes the other. experimental and stable ARE
# mutually exclusive, though (see EXPERIMENTAL_STABLE_RULE below): "not
# yet graduated" and "already graduated on some date" cannot both be
# true, unlike experimental+deprecated which is merely unusual, not
# contradictory. A skill declaring none of the three is implicitly
# Stable (every skill in this repository today). One nesting level
# deeper than spec.skillDependencies: subkeys sit at 4 spaces (same as
# requires/relatedTo), but each subkey opens ANOTHER nested block of
# scalar fields at 6 spaces, rather than a list.
LIFECYCLE_SUBKEYS = ("experimental", "deprecated", "stable")
LIFECYCLE_FIELDS = {
    "experimental": ("reason", "trackingIssue", "since"),
    "deprecated": ("reason", "replacement", "since", "removeAfter"),
    "stable": ("since", "compatibilityGuarantee"),
}
LIFECYCLE_REQUIRED_FIELDS = {
    "experimental": ("reason", "trackingIssue"),
    "deprecated": ("reason", "replacement"),
    "stable": ("since",),
}
# Kubernetes' alpha/beta/GA API-stability tiers, borrowed as spec.
# lifecycle.stable's optional compatibilityGuarantee enum -- shape-gated
# only; no rule ties a sibling's spec.skillDependencies.requires to this
# value (that would be new cross-skill coupling beyond what was asked).
COMPATIBILITY_GUARANTEE_LEVELS = ("Alpha", "Beta", "GA")
# spec.lifecycle.renamedFrom is different in kind from the three
# sub-blocks above: a plain scalar directly under lifecycle: (like
# metadata.name under metadata:), never opening a nested block. Backward-
# pointing by deliberate choice -- it lives on the *surviving* (new)
# skill's sidecar, naming the old, now-nonexistent directory, because
# `git mv` deletes the old directory itself, leaving nowhere to host a
# forward-pointing renamedTo/tombstone sidecar. Free-form and NOT
# resolved against sibling directories (unlike deprecated.replacement) --
# the whole point is that the old name is expected to no longer exist.
LIFECYCLE_SCALAR_KEYS = ("renamedFrom",)
# Strict calendar-date shape for spec.lifecycle's since/removeAfter
# fields: YYYY-MM-DD only. Real-date validity (rejecting e.g. 2026-02-30)
# is checked separately via datetime.date.fromisoformat in
# _valid_lifecycle_date -- this regex only gates the shape first, so that
# lenient ISO-variant parsing in Python 3.11+ never gets a chance to
# accept an off-shape string.
LIFECYCLE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A GitHub issue/PR reference anchoring the whole string (unlike
# ISSUE_CITATION_RE above, which scans for the same shape inside running
# prose): an optional "owner/repo" prefix, then "#" and a digit run.
# Shape-only -- never resolved against a live GitHub API call, since this
# checker is offline/read-only by design.
LIFECYCLE_ISSUE_REF_RE = re.compile(
    r"^(?:[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*)?#\d+$")

# A YAML mapping key at a given indent, however it was written: a bare
# scalar key (any run of characters up to the first unquoted ":" that
# does not start with whitespace, a quote, or "#") or a single/double-
# quoted string key. Shared by every gated block's key-recognition site
# (spec.skillDependencies' requires/relatedTo, spec.lifecycle's
# experimental/deprecated/stable/renamedFrom and their own nested fields).
# Earlier per-field pairs -- a specific-name alternation regex for
# recognized keys, plus a [A-Za-z0-9_-]+ catch-all for unrecognized ones --
# shared one blind spot: a quoted key (`"extra": foo`) or a key containing
# a character outside that narrow class matched NEITHER regex, so it fell
# through both checks into the "stray content, skip silently" branch
# instead of ever reaching unknown-key detection (issue #356). Matching
# broadly here and leaving "recognized vs. unknown" entirely to the
# caller's own membership check closes that gap: every syntactically
# key-shaped line at this indent is now seen as A key, so an unrecognized
# one can no longer hide behind a narrow character class the way a
# recognized one never had to. Still not a real YAML string lexer, though
# -- it has no escape-sequence support and requires the closing quote to
# be immediately followed by ":" -- so a key using an escaped quote
# (`"ex\"tra": foo`) or whitespace before its colon (`"extra" : foo`) does
# not match this regex either. Each of this regex's three call sites
# handles that residual gap the same way: a line at the gated indent that
# matches neither a list item currently being collected nor this key
# pattern is itself flagged as unknown/malformed, not silently skipped --
# rejecting every unmatched line at that indent, rather than only the
# ones this regex happens to parse, is the actual fail-closed contract
# (Codex review on #356's own PR).
KEY_LINE_RE_4 = re.compile(
    r'^[ ]{4}(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')
KEY_LINE_RE_6 = re.compile(
    r'^[ ]{6}(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')

# spec.executionRequirements' one recognized subkey so far (issue #349,
# #307 Workstream W1 first slice): "tools", at 4-space indent -- same
# depth as spec.skillDependencies' requires/relatedTo and
# spec.lifecycle's experimental/deprecated/stable. Recognized via the
# same shared KEY_LINE_RE_4 matcher those two fields use (issue #356),
# not a field-specific regex -- consistency across all three gated
# blocks, per #356's own constraint against patching just the newest one.
EXEC_REQ_TOOLS_SUBKEYS = ("read", "write", "shell")
# List items accept 6 or more spaces -- the same indent-drift tolerance
# REFERENCES_LIST_ITEM_RE/SKILL_DEP_LIST_ITEM_RE already give their own
# lists (an item at their own subkey's depth, or deeper).
EXEC_REQ_TOOLS_LIST_ITEM_RE = re.compile(r"^[ ]{6,}-\s*(.*)$")

TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
# A YAML plain (unquoted) scalar cannot safely contain ": " (colon followed
# by whitespace) or end in a bare ":" -- a real YAML parser reads either as
# the start of a new mapping key and either raises ("mapping values are not
# allowed in this context") or misparses the rest of the line. It similarly
# treats " #" (or a leading "#") as a comment marker, silently truncating
# everything after it. This repository's own frontmatter parser
# (_parse_frontmatter, above) is deliberately lenient and reproduces
# neither failure, so this check exists independently of it.
UNSAFE_COLON_RE = re.compile(r":(?:\s|$)")
UNSAFE_COMMENT_RE = re.compile(r"(?:^|\s)#")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Accept either "Table of contents" or a bare "Contents" heading.
TOC_RE = re.compile(r"^#+\s+(?:table of )?contents\b",
                    re.IGNORECASE | re.MULTILINE)
BLOCK_SCALAR_INDICATORS = (">", "|", ">-", "|-", ">+", "|+")
# Markdown inline link syntax: [text](target).
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Reference-style link definitions: [label]: target -- the destination a
# [text][label] reference resolves to. Up to 3 leading spaces per
# CommonMark; destination is either <...>-wrapped or a bare non-space run.
REFDEF_RE = re.compile(r"^[ ]{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)", re.MULTILINE)
# The "Related skills" bullet convention this repo's own skills use to name
# a sibling skill by directory name: "**vs. `name`:**", optionally two
# names separated by " / " (e.g. "**vs. `a` / `b`:**"), followed by
# explanatory prose that commonly repeats or adds further skill-name
# backticks of its own (e.g. "... produces the PR `other-skill` would then
# take over."). Matches the whole bullet -- header through its own
# explanatory text -- up to the next bullet marker, a blank line, or end of
# string, so BACKTICK_SKILL_NAME_RE can pull every backtick-quoted name out
# of the full bullet, not just its header. Deliberately narrower than "any
# backtick-quoted kebab-case token in the body" -- that broader scan has a
# high false-positive rate (CI-gate names, shape-checker check IDs, subagent
# names, executor names, filenames, and sibling/external-project skill names
# all appear in backticks elsewhere in skill prose without being a
# same-repo skill-directory reference); this bullet is the one
# consistently-used, low-ambiguity convention for one skill naming another,
# and that convention covers its own body prose just as much as its header.
RELATED_SKILL_BULLET_RE = re.compile(
    r"\*\*vs\.\s+.+?:\*\*.*?(?=\n[ \t]*-\s|\n[ \t]*\n|\Z)", re.DOTALL)
BACKTICK_SKILL_NAME_RE = re.compile(r"`([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)`")
# An absolute-URL scheme (http:, https:, mailto:, ftp:, ...) -- anything
# matching this is external, not a same-repo relative path.
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

# Portable self-citation scans (see the module docstring). A skill counts as
# Portable only when its portability marker says "Portable" without the
# "Mixed" / "Repository-scoped" qualifiers -- those levels legitimately cite
# repo-specific paths, so the two repo-path checks below do not apply to
# them. The bare-issue-citation check is different: it runs unconditionally
# on every skill regardless of this classification (issue #254).
# The near-top body marker, kept only as the fallback declaration form for a
# skill vendored in from another repository that has no sidecar. Skills in
# this repository declare portability in metadata/gitapex.yaml instead.
PORTABILITY_RE = re.compile(r"\bportability\s*:", re.IGNORECASE)
PORTABILITY_MAX_BODY_LINE = 6
PORTABLE_LEVEL_RE = re.compile(r"\bportable\b", re.IGNORECASE)
NON_PORTABLE_LEVEL_RE = re.compile(r"\b(?:mixed|repository-scoped|repo-scoped)\b",
                                   re.IGNORECASE)
# A GitHub issue/PR-number citation: an optional "owner/repo" prefix, then
# "#" and a digit run. The trailing (?![\d-]) rejects an in-page anchor slug
# like "#1-discovery" (a digit run followed by "-word"); a real citation ends
# at the digits.
ISSUE_CITATION_RE = re.compile(
    r"(?:[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*)?#\d+(?![\d-])")
# An origin-repository path citation rooted at this repo's own top-level
# tooling dirs. Kept deliberately narrow (evals/ and docs/) -- the two roots
# the historical incidents used -- rather than every path shape, so the scan
# stays a low-false-positive backstop, not a general path linter.
REPO_PATH_CITATION_RE = re.compile(r"(?:evals|docs)/[A-Za-z0-9._/-]+")
# A run of Markdown "already illustrative / already external" syntax whose
# contents must not be scanned: a fenced code block (``` ... ```), an inline
# code span (`...`), an absolute URL, an inline link ([text](target)), a
# reference-style link ([text][label]), or a reference definition
# ([label]: target). Stripping these leaves only bare prose.
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
# A Markdown inline code span: a run of 1-3 backticks, non-greedy content,
# then a closing run of the SAME length (\1) -- CommonMark's own rule, used
# e.g. when the span's content itself needs to contain a literal backtick
# (` ``a`b`` `). A first cut of this regex (`` `[^`]*` ``) assumed every span
# uses exactly one backtick each side; a review finding on issue #263 showed
# that a double-backtick span (` ``#42`` `) instead reads as two adjacent
# EMPTY single-backtick spans under that assumption, so its content was
# never inspected by either citation check below -- a silent evasion route,
# not just a cosmetic gap. Capped at 3 backticks (this file already reserves
# exactly 3 for FENCE_RE's own fenced-block markers, handled separately
# per-line by ``_blank_fenced_blocks`` before this regex ever runs on that
# line) rather than an unbounded ``+``, since this checker is deliberately a
# practical approximation of CommonMark, not a full parser.
INLINE_CODE_RE = re.compile(r"(`{1,3})(?!`)(.+?)(?<!`)\1(?!`)")
BARE_URL_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s>)\]]+")
MD_INLINE_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
MD_REF_LINK_RE = re.compile(r"\[[^\]]*\]\[[^\]]*\]")
MD_REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s.*$")

# Approved hedge phrases for the inline-code repo-path citation check (see
# the module docstring's issue #220 entry). Matched case-insensitively as a
# plain substring, not a word-boundary regex, so a longer phrase already in
# use (e.g. "this repository's own", "this repository has also") is covered
# by the shorter "this repository" entry without a separate one per variant.
# "this repository" / "gitapex" mark a citation as a deliberate, known-real
# reference to this repository's own file; "the calling repository" / "the
# target repository" mark the opposite -- a generic illustrative path name
# for whatever repository the skill lands in or reviews. Both directions are
# already this repository's own established phrasing (rubric.md, worked-
# example-explaining-the-work.md, establishing-ubiquitous-language), not
# invented for this check.
HEDGE_PHRASES = (
    "this repository",
    "the calling repository",
    "the target repository",
    "gitapex",
)

# Approved hedge phrases for the inline-code issue/PR-number citation check
# (see the module docstring's issue #263 entry). Deliberately a separate,
# narrower list from HEDGE_PHRASES: that list marks a repo-*path* citation as
# a deliberate reference to a real (or explicitly generic) repository; this
# one marks an issue-*number* citation as a rule/syntax illustration rather
# than worked-example bookkeeping -- different questions, so a shared phrase
# list would blur both.
# Deliberately full multi-word phrases, not bare words, matching HEDGE_PHRASES'
# own convention (a first cut of this check used the bare words "anchored"
# and "citation" and was caught by review: an ordinary sentence like "See the
# citation in PR `#144` for prior art" or "the review is anchored to PR
# `#88`" contains either bare word while citing a real, banned issue number --
# the exact defect this check exists to catch). Full phrases collapse that
# false-negative surface close to zero without adding new mechanism.
# "must be an anchored" is this repository's own established way of
# introducing a trackingIssue field's *shape* (`trackingIssue` must be an
# anchored `#123` or `owner/repo#123` reference) rather than citing a
# specific issue as content -- see evaluating-skill-quality's own SKILL.md
# and rubric.md trackingIssue documentation, verbatim in both.
# "issue/pr-number citation" (matched case-insensitively, like every other
# entry here) catches this skill's own, distinct self-referential case: this
# very shape check's rule stated in prose (e.g. "A bare GitHub issue/PR-
# number citation (#149, owner/repo#149) is barred ..."), the same way the
# module docstring above states it, just duplicated for the model reader.
# Both of the above are this repository's own already-established phrasing,
# not invented for this check.
#
# "hex color" / "css color" are different in kind from the two phrases
# above: a pre-emptive escape hatch for a known, unresolved limitation
# (issue #272) rather than a hedge drawn from existing in-repo prose --
# ISSUE_CITATION_RE (`#\d+`) cannot syntactically distinguish a real issue
# number from a decimal-digit-only CSS hex color (`#123456`, `#123`,
# `#000000` are all valid CSS, all also valid GitHub issue-number shapes).
# This repository has no web-design skill yet (issue #271), but a future
# one documenting a literal color value would hit this false positive with
# no natural way to phrase around it otherwise. Naming the color's own
# nature ("the hex color `#123456`", "this CSS color") is how such a skill
# would phrase it anyway, so the escape hatch costs no awkward wording.
# Reserved in advance of that skill landing, not drawn from existing
# content the way the two phrases above are. Does not replace the deeper,
# still-open fix tracked in #272 (context-aware classification instead of
# a hedge word).
ISSUE_CITATION_HEDGE_PHRASES = (
    "must be an anchored",
    "issue/pr-number citation",
    "hex color",
    "css color",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    rule: str
    evidence: str


@dataclass(frozen=True)
class FrontmatterParse:
    """Result of ``_parse_frontmatter``: the parsed top-level scalar fields,
    plus which of them were written as an unquoted YAML plain scalar rather
    than quoted or a block scalar (``>``/``|``).

    Only a plain scalar is at risk of the ": "/trailing ":"/" #" hazard
    ``_yaml_plain_scalar_safety_check`` exists to catch -- a quoted or
    block-scalar value is already safe under a real YAML parser regardless
    of what characters it contains, so a caller needs to know which form a
    field actually used, not just its already-unquoted/already-joined
    value in ``fields``.
    """
    fields: dict[str, str]
    plain_fields: frozenset[str]


def _parse_frontmatter(text: str) -> FrontmatterParse:
    """Extract top-level 'key: value' pairs from a leading --- block.

    Handles the scalar forms real SKILL.md files use: plain, single/double
    quoted, and YAML block scalars (folded '>' and literal '|', whose
    indented continuation lines are joined). Strips a leading UTF-8 BOM and
    requires a closing '---'; without one the frontmatter is treated as
    malformed (returns an empty result), rather than reading body lines as
    fields. No external YAML dependency.
    """
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return FrontmatterParse(fields={}, plain_fields=frozenset())
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines))
                if lines[i].strip() == "---"), None)
    if end is None:
        return FrontmatterParse(fields={}, plain_fields=frozenset())
    fields: dict[str, str] = {}
    plain_fields: set[str] = set()
    i = 1
    while i < end:
        m = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if value in BLOCK_SCALAR_INDICATORS:
            block: list[str] = []
            i += 1
            while i < end and (lines[i].strip() == ""
                               or lines[i][:1] in (" ", "\t")):
                block.append(lines[i].strip())
                i += 1
            joiner = "\n" if value[0] == "|" else " "
            fields[key] = joiner.join(block).strip()
            continue
        is_quoted = (len(value) >= 2 and value[0] == value[-1]
                     and value[0] in "\"'")
        fields[key] = _unquote(value)
        if not is_quoted:
            plain_fields.add(key)
        i += 1
    return FrontmatterParse(fields=fields, plain_fields=frozenset(plain_fields))


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        if value[0] == '"':
            # A double-quoted YAML scalar's escaping is a superset-safe
            # match for JSON string escaping (this repository's own
            # sidecar-generation method deliberately relies on that: see
            # the design plan's Task 1, which builds these values with
            # json.dumps). Decoding via the stdlib json module handles
            # every escape a generator might emit (\", \\, \n, \uXXXX,
            # ...), not just the two this parser previously hand-decoded.
            # Fall back to a naive strip on decode failure (e.g. a stray
            # unescaped literal quote) rather than raising -- this parser
            # never raises on malformed sidecar content.
            try:
                decoded = json.loads(value)
            except ValueError:
                decoded = None
            if isinstance(decoded, str):
                return decoded
        return value[1:-1]
    return value


def _strip_bare_comment(value: str) -> str:
    """Return ``value`` unchanged, unless it is an UNQUOTED value that
    starts with ``#`` -- real YAML never allows an unquoted scalar to
    start with ``#`` (that always opens a comment, making the actual
    value null/absent), so such a ``value`` must read as empty here too.

    This parser otherwise deliberately does not strip inline comments
    (see ``_parse_manifest``'s docstring: trailing ``# comment`` text
    after a real value is read as part of that value, "safe" because it
    fails closed against the expected enum/literal). That reasoning does
    NOT hold when the field's own valid shape can itself start with
    ``#`` -- e.g. ``spec.lifecycle.experimental.trackingIssue: #123``
    (unquoted) is real YAML for "trackingIssue is null", not the literal
    string ``"#123"``, yet ``"#123"`` is exactly this field's valid
    shape, so the old fails-closed argument fails open here instead.
    Used only by the three ``spec.lifecycle`` value-extraction sites
    (block-open decision, leaf fields, ``renamedFrom``) -- not applied
    to every other sidecar scalar, since none of their valid shapes start
    with ``#`` the way an issue reference does, and rewriting the whole
    parser's comment handling is a larger, separate change than this
    field's specific collision.
    """
    return "" if value.startswith("#") else value


def _match_key_line(pattern: re.Pattern[str], line: str) -> tuple[str, str] | None:
    """Match ``line`` against ``pattern`` (``KEY_LINE_RE_4`` or
    ``KEY_LINE_RE_6``). Returns ``(key, value)`` with the key already
    unquoted (a quoted key's own quote characters are never part of the
    key name) and the value right-stripped, or ``None`` if ``line`` is not
    a key-shaped line at that indent. The one shared recognition site
    every gated block's key handling uses (issue #356) -- callers decide
    "recognized vs. unknown" themselves via membership in their own set of
    valid names; this function only decides "is this syntactically a key
    at all," so an unrecognized key can never again bypass detection by
    virtue of being quoted or containing a character a narrower per-field
    regex did not anticipate.
    """
    m = pattern.match(line)
    if not m:
        return None
    key = m.group(1) if m.group(1) is not None else (
        m.group(2) if m.group(2) is not None else m.group(3))
    return key, m.group(4).strip()


@dataclass(frozen=True)
class ManifestParse:
    """Result of ``_parse_manifest``: the parsed top-level mapping plus any
    malformed top-level lines found alongside it.

    ``malformed_lines`` holds each offending line (trimmed), in file order --
    empty when the sidecar's top-level structure is clean. See
    ``_parse_manifest`` for the exact malformed-line rule.

    ``malformed_reference_items`` holds each spec.references list item
    (trimmed) that could not be read as a plain scalar string -- an
    unquoted mapping-shaped entry (e.g. "path: foo") or one indented
    inconsistently with the rest of its own list. Empty when every item in
    every spec.references list parsed cleanly. Unlike ``malformed_lines``,
    these are indented lines; they would otherwise be silently skipped by
    this parser's own "indented lines are never malformed" rule, which is
    why they need this separate, explicit channel rather than reusing
    ``malformed_lines``.

    ``malformed_skill_dependency_items`` and ``unknown_skill_dependency_keys``
    are spec.skillDependencies' equivalents: the former holds each
    requires/relatedTo list item that is mapping-shaped or inconsistently
    indented (same rule as ``malformed_reference_items``, one nesting level
    deeper); the latter holds each key found directly under
    spec.skillDependencies that is not ``requires`` or ``relatedTo``
    (trimmed line, e.g. "extra: foo"). Both empty when the field is absent
    or parsed cleanly.

    ``unknown_lifecycle_keys`` and ``unknown_lifecycle_fields`` are
    spec.lifecycle's equivalents, one nesting level deeper again:
    ``unknown_lifecycle_keys`` holds each key found directly under
    spec.lifecycle that is not ``experimental``, ``deprecated``,
    ``stable``, or ``renamedFrom`` (trimmed line); ``unknown_lifecycle_fields``
    holds each key found inside any of the three block sub-keys
    (``experimental``/``deprecated``/``stable``) that is not one of its
    own recognized fields (e.g. "extra: foo" under experimental). Both
    empty when the field is absent or parsed cleanly. There is no
    malformed-item channel for spec.lifecycle the way
    spec.references/spec.skillDependencies have one for list items --
    every leaf under spec.lifecycle is a plain scalar, so a wrong-type
    value is simply stored as the raw string by the field parser and
    fails the downstream well-formed check on shape, with nothing that
    needs a separate parse-time detection channel.

    ``unknown_execution_requirement_keys``, ``unknown_execution_requirement_tools_keys``,
    and ``malformed_execution_requirement_tools_items`` are
    spec.executionRequirements' equivalents (issue #349, #307 Workstream
    W1 first slice): the first holds each key found directly under
    spec.executionRequirements that is not ``tools`` (only one recognized
    key exists so far -- further categories are deferred to sibling child
    issues, and any other key here is unknown, not reserved space); the
    second holds each key found directly under ``tools`` that is not
    ``read``, ``write``, or ``shell``; the third holds each
    read/write/shell list item that is mapping-shaped or inconsistently
    indented, the same rule ``malformed_reference_items``/
    ``malformed_skill_dependency_items`` use one nesting level shallower.
    All three empty when the field is absent or parsed cleanly.
    """
    root: dict[str, object]
    malformed_lines: list[str]
    malformed_reference_items: list[str]
    malformed_skill_dependency_items: list[str]
    unknown_skill_dependency_keys: list[str]
    unknown_lifecycle_keys: list[str]
    unknown_lifecycle_fields: list[str]
    unknown_execution_requirement_keys: list[str]
    unknown_execution_requirement_tools_keys: list[str]
    malformed_execution_requirement_tools_items: list[str]


def _parse_manifest(text: str) -> ManifestParse:
    """Parse the YAML subset the metadata sidecar is specified to use.

    Reads top-level 'key: value' scalars and exactly-two-space-indented
    scalars under a top-level map (metadata:, spec:). Two exceptions:

    - spec.references (and only that key, and only directly under spec) is
      read as a flat list of scalar strings, each a "- <value>" line
      indented 2 or more spaces -- the shape this repository's sidecars use
      for maintainer-facing provenance (see the design spec's
      Sub-project C).
    - spec.skillDependencies (and only that key, and only directly under
      spec) is read as a mapping with exactly two recognized subkeys,
      ``requires`` and ``relatedTo`` (see the design spec's Sub-project D).
      Each subkey, at exactly 4-space indent, is either an inline empty
      list (``requires: []``) or an empty value opening a block list of
      "- <value>" items at 4 or more spaces indent -- the same depth as
      the subkey's own line, or deeper, with the same per-item shape rules
      (mapping-like-item and indent-consistency detection) and the same
      indent-drift tolerance as spec.references' items. A key inside
      spec.skillDependencies other than ``requires``/``relatedTo`` is
      collected into ``ManifestParse.unknown_skill_dependency_keys``
      instead of being silently skipped, since an unrecognized key here is
      a real shape defect the checker is expected to catch, not reserved
      space. Every gated block's key recognition (this one, spec.lifecycle's
      below, and any future one) shares one key-line matcher,
      ``_match_key_line`` over ``KEY_LINE_RE_4``/``KEY_LINE_RE_6`` --
      it recognizes a bare OR quoted YAML key as A key regardless of its
      characters, leaving "recognized vs. unknown" entirely to the
      caller's own membership check. A narrower, name-specific regex used
      to do both jobs at once (matching only the recognized names, with a
      separate ``[A-Za-z0-9_-]+`` catch-all for everything else); a quoted
      key (``"extra": foo``) or a key containing a character outside that
      narrow class matched neither regex and fell through both into the
      "stray content, skip silently" branch instead of ever reaching
      unknown-key detection (issue #356).
    - spec.lifecycle (and only that key, and only directly under spec) is
      read as a mapping with exactly three recognized block sub-keys --
      ``experimental``, ``deprecated``, ``stable`` -- plus one recognized
      plain scalar key, ``renamedFrom``. Each block sub-key, at exactly
      4-space indent, is an empty value opening a nested block of scalar
      fields at exactly 6-space indent (``reason``/``trackingIssue``/
      ``since`` for ``experimental``; ``reason``/``replacement``/
      ``since``/``removeAfter`` for ``deprecated``; ``since``/
      ``compatibilityGuarantee`` for ``stable``). ``renamedFrom``, also
      at 4-space indent, takes an inline scalar value directly instead of
      opening a block -- structurally like ``metadata.name`` under
      ``metadata:``, not like the other three. One nesting level deeper
      than spec.skillDependencies, but with scalar leaves instead of a
      list -- there is no list-item shape inside spec.lifecycle at all. A
      key directly under spec.lifecycle other than one of these four is
      collected into ``ManifestParse.unknown_lifecycle_keys``; a key
      inside any of the three block sub-keys that is not one of its own
      recognized fields is collected into
      ``ManifestParse.unknown_lifecycle_fields`` -- both instead of being
      silently skipped, for the same reason
      ``unknown_skill_dependency_keys`` exists. A block sub-key header
      written as an inline scalar instead of opening a block (e.g.
      ``experimental: true``) is stored as that raw scalar under its own
      key, exactly as spec.skillDependencies' non-list scalar fallback
      works, so the checker layer reports it as the wrong type rather
      than silently dropping it -- and symmetrically, ``renamedFrom``
      given a block instead of a scalar (e.g. nested children under
      ``renamedFrom:``) is detected one line later (see
      ``lifecycle_scalar_pending`` in the parsing loop below) and stored
      as an empty mapping, so it fails the same way in reverse.
    - spec.executionRequirements (and only that key, and only directly
      under spec) is read as a mapping with exactly one recognized
      block sub-key so far, ``tools`` (issue #349, #307 Workstream W1
      first slice -- further categories are deferred to sibling child
      issues). ``tools``, at exactly 4-space indent, is an empty value
      opening a nested block of list-of-scalars fields at exactly
      6-space indent: ``read``/``write``/``shell``, each either an
      inline empty list (``read: []``) or an empty value opening a
      block list of "- <value>" items at 6 or more spaces indent -- the
      same per-item shape rules and indent-drift tolerance
      spec.skillDependencies' requires/relatedTo already use, one
      nesting level deeper. A key directly under
      spec.executionRequirements other than ``tools`` is collected into
      ``ManifestParse.unknown_execution_requirement_keys``; a key inside
      ``tools`` other than ``read``/``write``/``shell`` is collected into
      ``ManifestParse.unknown_execution_requirement_tools_keys`` -- both
      instead of being silently skipped, for the same reason
      ``unknown_skill_dependency_keys`` exists. A malformed (mapping-shaped
      or inconsistently indented) list item under any of the three tools
      subkeys is collected into
      ``ManifestParse.malformed_execution_requirement_tools_items``.

    Every other nested map or list (e.g. spec.evalStatus) is still
    deliberately skipped, exactly as before: skipping keeps this
    stdlib-only with no YAML dependency. Inline '# comment' text after a
    value on the same line is not stripped -- it is read as part of the
    value, which is safe (fails closed against the expected enum/literal)
    but is not a supported way to annotate a sidecar field. Exception:
    every gated-block-opening site (the top-level ``nested`` dispatch for
    spec.references/skillDependencies/lifecycle/executionRequirements;
    spec.skillDependencies' own requires/relatedTo; spec.lifecycle's
    experimental/deprecated/stable and their own value-extraction sites;
    spec.executionRequirements' own tools; and tools' own
    read/write/shell) strips a value that is NOTHING BUT a comment
    (starts with ``#`` unquoted) down to empty via
    ``_strip_bare_comment`` before deciding whether that value is blank,
    since real YAML never allows an unquoted scalar to start with ``#``
    (it always opens a comment there) -- the general "fails closed"
    reasoning above does not hold when a blank-vs-not decision gates
    whether a whole nested block opens at all: a code-review finding
    caught that ``executionRequirements:  # not yet fully specified``
    (and the equivalent for every other gated block/list-opening key)
    read the comment as a literal, wrong-type scalar value instead of a
    blank one, silently discarding everything nested underneath it
    before this fix. Applies one level deeper too, for the same reason:
    ``experimental.trackingIssue``'s ``#123``/``owner/repo#123`` shape
    means an unquoted ``trackingIssue: #123`` must read as absent, not as
    the literal string ``"#123"`` a quoted value would give.

    A top-level (column-0) line that is not blank, not a '#' comment, not a
    YAML document marker ('---' or '...'), and does not match the top-level
    'key:' pattern is malformed -- e.g. a stray '- invalid mapping entry'
    that real PyYAML would reject with a ParserError. Every such line is
    collected (trimmed) into the returned ``ManifestParse.malformed_lines``,
    so a caller can fail the sidecar even though this permissive parser
    itself does not raise. Indented lines are NEVER considered malformed
    this same way -- every indented line belongs to nested/list structures
    this parser deliberately does not interpret, and flagging them would
    defeat that reserved-field design. spec.references and
    spec.skillDependencies list items are the exceptions with their own
    malformed channels: an unquoted item shaped like a YAML mapping key
    ("path: foo", real YAML would read that as a nested mapping, not a
    scalar), an item indented inconsistently with the rest of its own
    list, or an unquoted null/boolean/numeric scalar (issue #356: real
    YAML resolves e.g. "true"/"123"/"null" to that type, not a string) is
    collected (trimmed) into ``ManifestParse.malformed_reference_items``
    or ``ManifestParse.malformed_skill_dependency_items`` respectively,
    instead of being silently accepted as a garbled or wrongly-typed
    scalar string.

    Every gated *mapping*-valued block (spec.skillDependencies,
    spec.lifecycle and its experimental/deprecated/stable sub-blocks,
    spec.executionRequirements, spec.executionRequirements.tools) stores
    ``None`` -- real YAML null -- rather than ``{}`` when its own block
    header was seen with zero child key lines ever following it at the
    next indent level (issue #356, ACM row 2): a bare block header
    immediately followed by a dedent is null under any real YAML parser,
    never an empty-but-present mapping, so this parser must not silently
    promote that shape to ``{}`` the way an earlier version of it did. A
    block that does see at least one child key line (however that
    child's own value turns out) still stores a real, non-null ``dict``.
    This null/non-null distinction is orthogonal to whether the key
    appears in its parent dict at all -- a key that never appears means
    "not declared" (the pre-existing, unaffected "absent" state); only a
    key that DOES appear, with nothing under it, newly resolves to
    ``None`` instead of ``{}``. List-valued keys under these same blocks
    (requires/relatedTo, tools.read/write/shell) are NOT affected by this
    change -- a blank list header still parses to ``[]``, per each
    field's own pre-existing "explicit empty list" semantics.
    """
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    root: dict[str, object] = {}
    current: dict[str, object] | None = None
    collecting_refs: list[str] | None = None
    refs_indent: int | None = None
    malformed: list[str] = []
    malformed_refs: list[str] = []
    in_skill_deps = False
    skill_deps: dict[str, object] = {}
    # Whether spec.skillDependencies has seen at least one real child line
    # (a recognized or unknown key) since it was opened -- distinguishes a
    # block header left with nothing under it (real YAML null) from one
    # that genuinely has content, however malformed (issue #356: a blank
    # mapping header used to always finalize to {}, an empty-but-present
    # mapping, conflating "declared null" with "declared, zero subkeys").
    # Mirrored by lifecycle_has_content/lifecycle_subkey_has_content/
    # exec_req_has_content/exec_tools_has_content below, one per gated
    # mapping block.
    skill_deps_has_content = False
    collecting_dep_list: list[str] | None = None
    collecting_dep_key: str | None = None
    dep_list_indent: int | None = None
    malformed_deps: list[str] = []
    unknown_dep_keys: list[str] = []
    in_lifecycle = False
    lifecycle: dict[str, object] = {}
    lifecycle_has_content = False
    lifecycle_subkey: str | None = None
    lifecycle_field_buffer: dict[str, object] = {}
    lifecycle_subkey_has_content = False
    unknown_lifecycle_keys: list[str] = []
    unknown_lifecycle_fields: list[str] = []
    # Set when a scalar-only lifecycle key (currently only renamedFrom) is
    # seen with a blank/comment-only value -- deferred one line, since that
    # shape is ambiguous until the next line is known: it is either a
    # legitimately absent declaration (next line dedents or is a sibling),
    # or the start of a wrongly block-shaped value (next line is more
    # deeply indented than spec.lifecycle's own 4-space level). See the
    # "if lifecycle_scalar_pending is not None:" handling below.
    lifecycle_scalar_pending: str | None = None
    in_execution_requirements = False
    execution_requirements: dict[str, object] = {}
    exec_req_has_content = False
    in_exec_tools = False
    exec_tools: dict[str, object] = {}
    exec_tools_has_content = False
    collecting_exec_tools_list: list[str] | None = None
    collecting_exec_tools_key: str | None = None
    exec_tools_list_indent: int | None = None
    malformed_exec_tools_items: list[str] = []
    unknown_exec_req_keys: list[str] = []
    unknown_exec_tools_keys: list[str] = []

    def _finalize_refs() -> None:
        nonlocal collecting_refs, refs_indent
        if collecting_refs is not None and current is not None:
            current["references"] = collecting_refs
        collecting_refs = None
        refs_indent = None

    def _finalize_dep_list() -> None:
        nonlocal collecting_dep_list, collecting_dep_key, dep_list_indent
        if collecting_dep_list is not None and collecting_dep_key is not None:
            skill_deps[collecting_dep_key] = collecting_dep_list
        collecting_dep_list = None
        collecting_dep_key = None
        dep_list_indent = None

    def _finalize_skill_deps() -> None:
        nonlocal in_skill_deps, skill_deps, skill_deps_has_content
        _finalize_dep_list()
        if in_skill_deps and current is not None:
            # A block header with zero real children ever seen is real
            # YAML null, not an empty-but-present mapping (issue #356).
            current["skillDependencies"] = (
                skill_deps if skill_deps_has_content else None)
        in_skill_deps = False
        skill_deps = {}
        skill_deps_has_content = False

    def _finalize_lifecycle_subkey() -> None:
        nonlocal lifecycle_subkey, lifecycle_field_buffer, lifecycle_subkey_has_content
        if lifecycle_subkey is not None:
            lifecycle[lifecycle_subkey] = (
                lifecycle_field_buffer if lifecycle_subkey_has_content else None)
        lifecycle_subkey = None
        lifecycle_field_buffer = {}
        lifecycle_subkey_has_content = False

    def _finalize_lifecycle() -> None:
        nonlocal in_lifecycle, lifecycle, lifecycle_has_content
        _finalize_lifecycle_subkey()
        if in_lifecycle and current is not None:
            current["lifecycle"] = lifecycle if lifecycle_has_content else None
        in_lifecycle = False
        lifecycle = {}
        lifecycle_has_content = False

    def _finalize_exec_tools_list() -> None:
        nonlocal collecting_exec_tools_list, collecting_exec_tools_key, exec_tools_list_indent
        if collecting_exec_tools_list is not None and collecting_exec_tools_key is not None:
            exec_tools[collecting_exec_tools_key] = collecting_exec_tools_list
        collecting_exec_tools_list = None
        collecting_exec_tools_key = None
        exec_tools_list_indent = None

    def _finalize_exec_tools() -> None:
        nonlocal in_exec_tools, exec_tools, exec_tools_has_content
        _finalize_exec_tools_list()
        if in_exec_tools:
            execution_requirements["tools"] = (
                exec_tools if exec_tools_has_content else None)
        in_exec_tools = False
        exec_tools = {}
        exec_tools_has_content = False

    def _finalize_execution_requirements() -> None:
        nonlocal in_execution_requirements, execution_requirements, exec_req_has_content
        _finalize_exec_tools()
        if in_execution_requirements and current is not None:
            current["executionRequirements"] = (
                execution_requirements if exec_req_has_content else None)
        in_execution_requirements = False
        execution_requirements = {}
        exec_req_has_content = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if collecting_refs is not None:
            item = REFERENCES_LIST_ITEM_RE.match(line)
            if item:
                item_indent = len(line) - len(line.lstrip(" "))
                if refs_indent is None:
                    refs_indent = item_indent
                if item_indent != refs_indent:
                    # Same list, different indent than its own first item --
                    # real YAML would reject this outright.
                    malformed_refs.append(line.strip())
                    continue
                raw_text = item.group(1).strip()
                is_quoted = (len(raw_text) >= 2 and raw_text[0] == raw_text[-1]
                             and raw_text[0] in "\"'")
                if not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text):
                    # An unquoted "key: value" item -- real YAML reads this
                    # as a nested mapping, not the scalar string this
                    # parser understands; flag it rather than silently
                    # truncating the mapping into a garbled string.
                    malformed_refs.append(line.strip())
                elif not is_quoted and _is_non_string_plain_scalar(raw_text):
                    # An unquoted null/boolean/numeric scalar -- real YAML
                    # resolves this to that type, not a string (issue #356).
                    malformed_refs.append(line.strip())
                else:
                    collecting_refs.append(_unquote(raw_text))
                continue
            # Not a list item: the references list ends here. Finalize it
            # and fall through to process this line normally below.
            _finalize_refs()
        if collecting_dep_list is not None:
            item = SKILL_DEP_LIST_ITEM_RE.match(line)
            if item:
                item_indent = len(line) - len(line.lstrip(" "))
                if dep_list_indent is None:
                    dep_list_indent = item_indent
                if item_indent != dep_list_indent:
                    malformed_deps.append(line.strip())
                    continue
                raw_text = item.group(1).strip()
                is_quoted = (len(raw_text) >= 2 and raw_text[0] == raw_text[-1]
                             and raw_text[0] in "\"'")
                if not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text):
                    malformed_deps.append(line.strip())
                elif not is_quoted and _is_non_string_plain_scalar(raw_text):
                    malformed_deps.append(line.strip())
                else:
                    collecting_dep_list.append(_unquote(raw_text))
                continue
            # Not a list item: this requires/relatedTo list ends here.
            _finalize_dep_list()
        if in_skill_deps:
            matched = _match_key_line(KEY_LINE_RE_4, line)
            if matched:
                skill_deps_has_content = True
                key, value = matched
                # A value that is NOTHING BUT a comment (e.g. "requires:
                # # comment") must read as blank/absent, not as the
                # literal comment text -- otherwise it neither opens the
                # list nor equals "[]" and is instead stored as a raw,
                # wrong-type scalar (found by review: "requires:  #
                # inline comment" silently discarded the whole list).
                value = _strip_bare_comment(value)
                if key not in SKILL_DEPENDENCY_SUBKEYS:
                    unknown_dep_keys.append(line.strip())
                elif value == "[]":
                    skill_deps[key] = []
                elif not value:
                    collecting_dep_list = []
                    collecting_dep_key = key
                    dep_list_indent = None
                else:
                    # Not an empty list and not "[]" -- this narrow parser
                    # has no flow-sequence support; store the raw scalar so
                    # the shape gate can fail it as the wrong type rather
                    # than silently dropping it.
                    skill_deps[key] = value
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 4:
                # An indented line reaching here is neither an active list
                # item nor a key line KEY_LINE_RE_4 recognizes -- including
                # a key using YAML quoting/escaping that regex cannot
                # parse (an escaped quote, or whitespace between a closing
                # quote and its colon). spec.skillDependencies has no
                # legitimate reserved nested structure beyond its own two
                # list-valued keys, so flag it as unknown rather than
                # silently tolerating it: rejecting every unmatched line at
                # this indent, not just the ones a regex happens to parse,
                # is the actual fail-closed contract (issue #356 follow-up).
                skill_deps_has_content = True
                unknown_dep_keys.append(line.strip())
                continue
            # Dedented below the block's own indent: skillDependencies ends
            # here. Finalize it and fall through to process this line
            # normally below.
            _finalize_skill_deps()
        if lifecycle_subkey is not None:
            matched = _match_key_line(KEY_LINE_RE_6, line)
            if matched:
                lifecycle_subkey_has_content = True
                key, value = matched
                value = _strip_bare_comment(value)
                if key in LIFECYCLE_FIELDS.get(lifecycle_subkey, ()):
                    if value:
                        lifecycle_field_buffer[key] = _unquote(value)
                else:
                    unknown_lifecycle_fields.append(line.strip())
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 6:
                # Same fail-closed reasoning as spec.skillDependencies'
                # equivalent branch above -- an unmatched line at this
                # indent (including one KEY_LINE_RE_6 cannot parse due to
                # quoting/escaping) is flagged, not silently tolerated.
                lifecycle_subkey_has_content = True
                unknown_lifecycle_fields.append(line.strip())
                continue
            # Dedented below the sub-block's own indent: this
            # experimental/deprecated block ends here. Finalize it and
            # fall through to process this line normally below (it may be
            # the other sub-block's header, or a dedent out of lifecycle
            # entirely).
            _finalize_lifecycle_subkey()
        if lifecycle_scalar_pending is not None:
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent > 4:
                # A block followed a scalar-only key (e.g. renamedFrom
                # given nested children instead of a plain value) -- the
                # wrong type, not the documented plain scalar. Store a
                # non-string sentinel so the checker layer reports it as
                # such; deeper sibling lines of this same mistaken block
                # are then silently absorbed by the existing "stray
                # content" fallback below (their own internal shape does
                # not matter -- the type error is already captured).
                lifecycle[lifecycle_scalar_pending] = {}
                lifecycle_scalar_pending = None
                continue
            # Not more deeply indented: the key really was declared blank
            # (or comment-only) with nothing following -- matches this
            # parser's "blank scalar assignment means not declared"
            # convention. Fall through to process the current line
            # normally below.
            lifecycle_scalar_pending = None
        if in_lifecycle:
            matched = _match_key_line(KEY_LINE_RE_4, line)
            if matched:
                lifecycle_has_content = True
                key, value = matched
                value = _strip_bare_comment(value)
                if key in LIFECYCLE_SUBKEYS:
                    if value:
                        # Not opening a block -- a bare scalar written where a
                        # mapping is expected (e.g. "experimental: true").
                        # Store the raw scalar under the subkey itself so the
                        # checker layer reports it as the wrong type, exactly
                        # as spec.skillDependencies' non-list scalar fallback
                        # works.
                        lifecycle[key] = value
                    else:
                        lifecycle_subkey = key
                        lifecycle_field_buffer = {}
                elif key in LIFECYCLE_SCALAR_KEYS:
                    if value:
                        lifecycle[key] = _unquote(value)
                    else:
                        # Blank (or comment-only) value: ambiguous until the
                        # next line is seen -- see the
                        # "lifecycle_scalar_pending is not None" handling above.
                        lifecycle_scalar_pending = key
                else:
                    unknown_lifecycle_keys.append(line.strip())
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 4:
                # Same fail-closed reasoning as spec.skillDependencies'
                # equivalent branch above.
                lifecycle_has_content = True
                unknown_lifecycle_keys.append(line.strip())
                continue
            # Dedented below spec.lifecycle's own indent: the block ends
            # here. Finalize it and fall through to process this line
            # normally below.
            _finalize_lifecycle()
        if collecting_exec_tools_list is not None:
            item = EXEC_REQ_TOOLS_LIST_ITEM_RE.match(line)
            if item:
                item_indent = len(line) - len(line.lstrip(" "))
                if exec_tools_list_indent is None:
                    exec_tools_list_indent = item_indent
                if item_indent != exec_tools_list_indent:
                    # Same list, different indent than its own first item --
                    # real YAML would reject this outright.
                    malformed_exec_tools_items.append(line.strip())
                    continue
                raw_text = item.group(1).strip()
                is_quoted = (len(raw_text) >= 2 and raw_text[0] == raw_text[-1]
                             and raw_text[0] in "\"'")
                if not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text):
                    malformed_exec_tools_items.append(line.strip())
                elif not is_quoted and _is_non_string_plain_scalar(raw_text):
                    malformed_exec_tools_items.append(line.strip())
                else:
                    collecting_exec_tools_list.append(_unquote(raw_text))
                continue
            # Not a list item: this read/write/shell list ends here.
            _finalize_exec_tools_list()
        if in_exec_tools:
            matched = _match_key_line(KEY_LINE_RE_6, line)
            if matched:
                exec_tools_has_content = True
                key, value = matched
                # Same comment-only-value fix as spec.skillDependencies'
                # equivalent branch above (e.g. "read:  # comment").
                value = _strip_bare_comment(value)
                if key not in EXEC_REQ_TOOLS_SUBKEYS:
                    unknown_exec_tools_keys.append(line.strip())
                elif value == "[]":
                    exec_tools[key] = []
                elif not value:
                    collecting_exec_tools_list = []
                    collecting_exec_tools_key = key
                    exec_tools_list_indent = None
                else:
                    # Not an empty list and not "[]" -- no flow-sequence
                    # support; store the raw scalar so the shape gate can
                    # fail it as the wrong type rather than silently
                    # dropping it, exactly as spec.skillDependencies does.
                    exec_tools[key] = value
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 6:
                # Same fail-closed reasoning as spec.skillDependencies'/
                # spec.lifecycle's equivalent branches -- an unmatched
                # line at this indent is flagged, not silently tolerated.
                exec_tools_has_content = True
                unknown_exec_tools_keys.append(line.strip())
                continue
            # Dedented below tools' own indent: the block ends here.
            # Finalize it and fall through to process this line normally
            # below.
            _finalize_exec_tools()
        if in_execution_requirements:
            matched = _match_key_line(KEY_LINE_RE_4, line)
            if matched:
                exec_req_has_content = True
                key, value = matched
                # Same comment-only-value fix as spec.skillDependencies'
                # equivalent branch above (e.g. "tools:  # comment").
                value = _strip_bare_comment(value)
                if key != "tools":
                    unknown_exec_req_keys.append(line.strip())
                elif value:
                    # Not opening a block -- a bare scalar written where a
                    # mapping is expected (e.g. "tools: true"). Store the
                    # raw scalar so the checker layer reports it as the
                    # wrong type rather than silently dropping it.
                    execution_requirements[key] = value
                else:
                    in_exec_tools = True
                    exec_tools = {}
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 4:
                # Same fail-closed reasoning as spec.skillDependencies'/
                # spec.lifecycle's equivalent branches.
                exec_req_has_content = True
                unknown_exec_req_keys.append(line.strip())
                continue
            # Dedented below spec.executionRequirements' own indent: the
            # block ends here. Finalize it and fall through to process
            # this line normally below.
            _finalize_execution_requirements()
        if line[:1] in (" ", "\t"):
            # Indented: nested/list content this parser does not interpret,
            # except spec.references and spec.skillDependencies (handled
            # above once each starts). Exactly two spaces: a four-space
            # line (a child of a nested map) has a space where this
            # expects a key character, so it will not match and is
            # skipped -- never malformed either way.
            nested = re.match(r"[ ]{2}([A-Za-z0-9_-]+):\s*(.*)$", line)
            if nested and current is not None:
                key, value = nested.group(1), nested.group(2).strip()
                # A value that is NOTHING BUT a comment (e.g.
                # "executionRequirements:  # not yet fully specified")
                # must read as blank, the same way a real YAML parser
                # reads it -- otherwise `not value` is False, none of
                # these four gated blocks ever opens, and the entire
                # nested block underneath is discarded as a raw,
                # wrong-type scalar string instead (found by review).
                value = _strip_bare_comment(value)
                # current is root["spec"] by identity exactly while inside
                # the spec: block, so this is "are we directly under spec"
                # without tracking a separate current-top-key variable.
                if key == "references" and current is root.get("spec") and not value:
                    collecting_refs = []
                elif key == "skillDependencies" and current is root.get("spec") and not value:
                    in_skill_deps = True
                    skill_deps = {}
                elif key == "lifecycle" and current is root.get("spec") and not value:
                    in_lifecycle = True
                    lifecycle = {}
                elif key == "executionRequirements" and current is root.get("spec") and not value:
                    in_execution_requirements = True
                    execution_requirements = {}
                elif value:
                    current[key] = _unquote(value)
            continue
        if line.strip() in ("---", "..."):
            continue
        top = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            if value:
                root[key] = _unquote(value)
                current = None
            else:
                child: dict[str, object] = {}
                root[key] = child
                current = child
            continue
        malformed.append(line.strip())
    _finalize_refs()
    _finalize_skill_deps()
    _finalize_lifecycle()
    _finalize_execution_requirements()
    return ManifestParse(root=root, malformed_lines=malformed,
                          malformed_reference_items=malformed_refs,
                          malformed_skill_dependency_items=malformed_deps,
                          unknown_skill_dependency_keys=unknown_dep_keys,
                          unknown_lifecycle_keys=unknown_lifecycle_keys,
                          unknown_lifecycle_fields=unknown_lifecycle_fields,
                          unknown_execution_requirement_keys=unknown_exec_req_keys,
                          unknown_execution_requirement_tools_keys=unknown_exec_tools_keys,
                          malformed_execution_requirement_tools_items=malformed_exec_tools_items)


def spec_of(parsed: ManifestParse) -> dict[str, object] | None:
    """Return ``parsed.root["spec"]`` if present and a mapping, else None.

    A malformed sidecar can write ``spec:`` as a scalar or list rather than
    a mapping; every consumer that only cares about "does this sidecar have
    a real spec mapping" needs the same isinstance guard around
    ``root.get("spec")``, and inlining it separately at each call site let
    the exact same unguarded pattern regress twice in one file within a
    single PR (issue #228 repairs 2/3). Callers outside this module (e.g.
    tests/test_skill_metadata_sidecar.py) should use this instead of
    inlining ``parsed.root.get("spec")`` themselves.
    """
    spec = parsed.root.get("spec")
    return spec if isinstance(spec, dict) else None


def _body_after_frontmatter(text: str) -> list[str]:
    """Lines after the closing frontmatter '---'. If there is no
    frontmatter, the whole text is the body."""
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    lines = text.splitlines()
    if not text.startswith("---"):
        return lines
    end = next((i for i in range(1, len(lines))
                if lines[i].strip() == "---"), None)
    if end is None:
        return lines
    return lines[end + 1:]


def _is_ignorable(p: Path) -> bool:
    """Junk that must not affect the references/ checks: dotfiles (e.g. a
    macOS .DS_Store) and Python bytecode caches."""
    return p.name.startswith(".") or "__pycache__" in p.parts


def _raw_link_targets(body_text: str) -> list[str]:
    """Return every raw Markdown link target string in ``body_text`` --
    both inline ([text](target)) and reference-style ([text][label]
    resolved via a [label]: target definition elsewhere in the body) --
    unprocessed (no stripping, ``<...>``-unwrapping, or scheme filtering
    yet).

    Shared by ``_out_of_skill_link_targets`` and ``_broken_anchor_targets``:
    this exact gathering step (the two regex sources) is identical between
    them, but their per-target cleanup afterward is not (the latter also
    strips an inline link's optional CommonMark title before its fragment
    is read), so only this common prefix is factored out rather than the
    whole per-target loop.
    """
    raw_targets = [m.group(1) for m in LINK_RE.finditer(body_text)]
    raw_targets += [m.group(1) for m in REFDEF_RE.finditer(body_text)]
    return raw_targets


def _escapes_skill_dir(normalized: str, skill_norm: str) -> bool:
    """Whether a lexically-normalized path ``normalized`` falls outside
    ``skill_norm`` (the skill directory's own normalized path).

    Shared by ``_out_of_skill_link_targets`` (which flags an escaping
    SKILL.md link as broken) and ``_resolve_anchor_link_file`` (which
    instead treats an escaping path as out of that check's own scope) --
    the same boundary test, applied by two callers that each respond to
    it differently.
    """
    return normalized != skill_norm and not normalized.startswith(skill_norm + os.sep)


def _out_of_skill_link_targets(body_text: str, skill_dir: Path) -> list[str]:
    """Return each Markdown link target in ``body_text`` that resolves
    outside ``skill_dir``.

    Covers both inline links ([text](target)) and reference-style links
    ([text][label] resolved via a [label]: target definition elsewhere in
    the body) -- a reference-style target is exactly as capable of
    escaping the skill directory as an inline one. Skips absolute-URL/
    scheme targets (http:, https:, mailto:, ...) and bare in-page
    fragments (#section) -- neither is a same-repo relative path.
    Resolution is purely lexical (os.path.normpath), not a real
    filesystem lookup, since the target need not exist for this check.
    """
    skill_norm = os.path.normpath(str(skill_dir))
    offenders = []
    for raw in _raw_link_targets(body_text):
        target = raw.strip()
        if len(target) >= 2 and target[0] == "<" and target[-1] == ">":
            target = target[1:-1].strip()
        if SCHEME_RE.match(target):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0].strip()
        if not path_part:
            continue  # fragment-only or query-only link
        if os.path.isabs(path_part):
            normalized = os.path.normpath(path_part)
        else:
            normalized = os.path.normpath(os.path.join(skill_norm, path_part))
        if _escapes_skill_dir(normalized, skill_norm):
            offenders.append(target)
    return offenders


# A Markdown ATX heading line: 0-3 leading spaces (CommonMark's own
# indent tolerance, matching REFDEF_RE's identical "[ ]{0,3}" convention
# elsewhere in this file), 1-6 '#', a space/tab, the heading text, then an
# optional CommonMark closing sequence (one or more trailing '#'
# characters, itself preceded by at least one space/tab) and any trailing
# whitespace. The closing sequence must be stripped in the regex itself,
# not left for ANCHOR_SLUG_STRIP_RE to clean up afterward -- a first cut
# of this regex assumed the strip step would handle a trailing "## Heading
# ##" safely, but that leaves the space before the closing '#'s in the
# captured text, which then survives stripping and becomes a spurious
# trailing '-' in the slug ("heading-" instead of "heading"), confirmed
# by direct execution during review. Applied only to fence-blanked text
# (see _heading_slugs) so a heading-shaped line inside a fenced code
# example is never read as a real heading.
HEADING_RE = re.compile(
    r"^[ ]{0,3}#{1,6}[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", re.MULTILINE)
# A Markdown Setext heading: a non-blank text line (0-3 leading spaces,
# CommonMark's tolerance again), immediately followed (no blank line
# between) by an underline of only '=' characters (renders an H1) or only
# '-' characters (renders an H2), itself 0-3-space-indented with optional
# trailing whitespace. The negative lookahead excludes a text line that is
# itself already a valid ATX heading (1-6 '#' then a space/tab, or '#'s
# alone at end of line) -- CommonMark gives ATX-heading parsing priority
# for that line, so it can never simultaneously serve as a Setext
# underline's own text line; without this exclusion, an ATX heading
# immediately followed by a "---" divider (a common section-break
# convention, distinct from a Setext underline) would be misread as a
# Setext H2 whose "text" is the whole "## Heading" line, hashes included
# -- confirmed empirically not to happen with this exclusion in place, and
# confirmed to still correctly recognize a real, marker-free Setext
# heading immediately above a bare "---"/"===" line.
SETEXT_HEADING_RE = re.compile(
    r"^[ ]{0,3}(?!#{1,6}(?:[ \t]|$))(\S.*?)[ \t]*\n[ ]{0,3}(?:=+|-+)[ \t]*$",
    re.MULTILINE)
# GitHub's own heading-to-anchor slug punctuation strip set -- a denylist
# of specific ASCII punctuation plus two Unicode "General Punctuation"/
# "Supplemental Punctuation" blocks, matching the real github-slugger
# algorithm's own regex, NOT an ASCII allowlist. An earlier cut of this
# constant stripped everything outside [a-z0-9_ -], which also deleted
# every non-ASCII Unicode LETTER (e.g. "## Café Notes" -> "caf-notes"
# instead of GitHub's real "café-notes") -- confirmed by direct
# execution during review to diverge from real GitHub rendering. This
# denylist form preserves Unicode letters/digits (and underscore/hyphen/
# space, as before) while still stripping the same fixed punctuation set.
# Re-validated against every real hand-written "## Contents" TOC in this
# repository (battle-testing-a-skill, executing-a-branch-plan,
# scorer-gated-skill-edits references/*.md) after the change -- all still
# match, since every punctuation character those TOCs' own headings use
# ('&', '.', ':', etc.) is covered by this denylist too.
ANCHOR_SLUG_STRIP_RE = re.compile(
    r"[\u2000-\u206F\u2E00-\u2E7F\\'!\"#$%&()*+,./:;<=>?@\[\]^`{|}~]")


def _github_slug(heading: str, occurrences: dict[str, int]) -> str:
    """Return the GitHub-rendered anchor slug for one ``heading``'s text,
    given ``occurrences`` (a same-document-wide table of every slug string
    already assigned, mapped to a running per-base counter -- mutated in
    place by this call, and threaded across every heading in the target
    document, in order, not reset per link, since GitHub's own dedup
    counts every rendered heading, not only the ones some other document
    happens to link to).

    Lowercase, strip via ANCHOR_SLUG_STRIP_RE, then each surviving space
    becomes its own literal '-' -- adjacent punctuation removed by the
    strip step is NOT collapsed first, so "Trust & authority" becomes
    "trust  authority" (two spaces where '&' was deleted) and then
    "trust--authority", a real slug already in this repository's own
    executing-a-branch-plan TOC-validated data.

    A slug that repeats an earlier heading's slug earns a '-1', '-2', ...
    suffix -- but the candidate suffix must itself be checked against
    every slug already assigned, not just counted against its own base:
    for headings "Foo", "Foo-1", "Foo" in that order, the naive "count how
    many times 'foo' was seen" approach would slug the third heading
    "foo-1" again, colliding with the second heading's own real slug
    "foo-1" (confirmed by direct execution during review, matching a
    reported false-negative). This loop instead keeps incrementing the
    base's own counter and re-probing until it lands on a slug string not
    already in ``occurrences`` -- exactly the real github-slugger
    algorithm's own occurrence-tracking approach -- so the third "Foo"
    above correctly slugs to "foo-2", skipping over the already-taken
    "foo-1".
    """
    slug = ANCHOR_SLUG_STRIP_RE.sub("", heading.lower()).replace(" ", "-")
    original = slug
    while slug in occurrences:
        occurrences[original] = occurrences.get(original, 0) + 1
        slug = f"{original}-{occurrences[original]}"
    occurrences[slug] = 0
    return slug


def _heading_slugs(text: str) -> frozenset[str]:
    """Return every GitHub-rendered anchor slug ``text`` (a Markdown
    document body) would expose, in heading order, deduplicated exactly
    as GitHub's own renderer does (see ``_github_slug``).

    Fenced code blocks are blanked first via ``_blank_fenced_blocks`` (the
    same helper the citation checks already share) so an illustrative
    heading-shaped line inside a worked example is never treated as a
    real heading; that same helper also normalizes CRLF/CR line endings
    to bare '\\n' via its own ``str.splitlines()`` + ``"\\n".join`` pass,
    so a Windows-checked-out file with trailing '\\r' characters cannot
    leak into a captured heading's text either.

    ATX (HEADING_RE) and Setext (SETEXT_HEADING_RE) matches are gathered
    together and sorted by position before slugging, since GitHub's own
    per-document dedup counter must see every heading in true document
    order regardless of which of the two forms produced it.
    """
    defenced = _blank_fenced_blocks(text)
    matches = [(m.start(), m.group(1)) for m in HEADING_RE.finditer(defenced)]
    matches += [(m.start(), m.group(1)) for m in SETEXT_HEADING_RE.finditer(defenced)]
    matches.sort(key=lambda pair: pair[0])
    occurrences: dict[str, int] = {}
    return frozenset(_github_slug(heading, occurrences) for _pos, heading in matches)


# An optional Markdown link *title* trailing an inline link's destination
# (CommonMark: destination, one or more spaces, then "title", 'title', or
# (title)). LINK_RE's own capture group is the entire parenthesized
# content -- destination and title together -- so a titled inline link
# like [text](#heading "Jump there") would otherwise leave the title text
# stuck onto the fragment once split on '#'. Reference-style definitions
# (REFDEF_RE) already exclude the title naturally, since their own
# capture group is a bare non-whitespace run; applying this to a
# REFDEF_RE-sourced target is harmless (no whitespace+quoted-suffix shape
# to strip from an untitled destination).
LINK_TITLE_RE = re.compile(r'''[ \t]+(?:"[^"]*"|'[^']*'|\([^()]*\))[ \t]*$''')


def _resolve_anchor_link_file(raw_path: str, source_dir: Path,
                              skill_norm: str) -> Path | None:
    """Resolve a Markdown link's path portion to the file it actually
    points at, for the purpose of validating its ``#fragment`` -- real
    relative-link semantics, resolved against ``source_dir`` (the
    directory of the file that CONTAINS the link), not against the skill
    root the way ``_out_of_skill_link_targets`` resolves paths.

    That existing helper's skill-root-relative resolution is only ever
    exercised against SKILL.md, which happens to sit at the skill root --
    so "relative to the containing file" and "relative to the skill root"
    coincide there and the difference was never actually observable. This
    check also runs per references/*.md file, which does not sit at the
    skill root, so the two resolution rules would diverge for a
    cross-reference link written there; this function uses the real,
    file-relative rule so it stays correct in both places.

    Returns ``None`` when the resolved path falls outside the skill
    directory -- deliberately out of scope for this check: an escaping
    path is a distinct defect class links-inside-skill (for SKILL.md)
    already owns separately, not one this anchor check duplicates or
    re-flags.
    """
    if os.path.isabs(raw_path):
        resolved = os.path.normpath(raw_path)
    else:
        resolved = os.path.normpath(os.path.join(str(source_dir), raw_path))
    if _escapes_skill_dir(resolved, skill_norm):
        return None
    return Path(resolved)


def _cached_target_heading_slugs(
        path: Path, cache: dict[Path, frozenset[str] | None]) -> frozenset[str] | None:
    """Return ``path``'s heading-slug set (see ``_heading_slugs``), reading
    and parsing the file at most once per ``check_shape`` run -- ``cache``
    is shared across the SKILL.md check and every references/*.md check in
    one call, since more than one link can point at the same target file.

    Returns ``None`` (a cached miss) when ``path`` cannot be read as UTF-8
    text (missing, a directory, binary, or non-UTF-8) -- the caller treats
    that as "this fragment can never resolve" (a broken-anchor failure),
    not a skip: unlike the references/ TOC check's own tolerance for
    unreadable junk (which exists so a stray binary file sitting in
    references/ cannot abort the whole run), a link that names a target
    file which does not exist -- or cannot be read as one -- has no
    possible real heading to match, so silently passing it would leave
    exactly the kind of dead link (`[ghost](references/missing.md#x)`)
    this check exists to catch undetected.
    """
    if path in cache:
        return cache[path]
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        cache[path] = None
        return None
    body = "\n".join(_body_after_frontmatter(text))
    slugs = _heading_slugs(body)
    cache[path] = slugs
    return slugs


def _broken_anchor_targets(
        body_text: str, source_path: Path, skill_dir: Path,
        cache: dict[Path, frozenset[str] | None]) -> list[str]:
    """Return each Markdown link target in ``body_text`` (the body of
    ``source_path``) whose ``#fragment`` does not match any real
    GitHub-rendered heading anchor in its target file.

    Shares ``_out_of_skill_link_targets``'s own link-gathering step
    (``_raw_link_targets``) and its ``<...>``-unwrap/SCHEME_RE
    absolute-URL skip, but inspects the fragment instead of validating
    the path. An inline link's optional CommonMark title
    (``[text](#heading "Jump there")``) is stripped via LINK_TITLE_RE
    before the fragment is read -- LINK_RE's own capture group is the
    entire parenthesized destination-plus-title, so without this step a
    titled link's title text would stay stuck onto the fragment
    (`heading "Jump there"`), which could never match any real anchor and
    would false-positive-fail a link GitHub renders and resolves
    correctly. A target with no ``#`` or an empty fragment (path-only, or
    a bare trailing ``#``) has nothing to check and is skipped. A bare
    fragment (``#section``, no path) resolves against ``source_path``
    itself; otherwise the path portion resolves via
    ``_resolve_anchor_link_file`` -- a path that escapes the skill
    directory is silently skipped (see that function's own docstring for
    why: it is links-inside-skill's own separate, already-owned failure).
    A target file that cannot be read as one, by contrast, IS flagged
    here (see ``_cached_target_heading_slugs``'s own docstring): there is
    no real heading it could possibly expose, so every fragment link into
    it is broken.
    """
    skill_norm = os.path.normpath(str(skill_dir))
    source_dir = source_path.parent
    offenders = []
    for raw in _raw_link_targets(body_text):
        target = raw.strip()
        title_match = LINK_TITLE_RE.search(target)
        if title_match:
            target = target[:title_match.start()].rstrip()
        if len(target) >= 2 and target[0] == "<" and target[-1] == ">":
            target = target[1:-1].strip()
        if SCHEME_RE.match(target):
            continue
        path_part, _sep, fragment = target.partition("#")
        path_part = path_part.split("?", 1)[0].strip()
        fragment = fragment.strip()
        if not fragment:
            continue  # path-only, query-only, or bare trailing '#'
        if path_part:
            resolved = _resolve_anchor_link_file(path_part, source_dir, skill_norm)
            if resolved is None:
                continue  # escapes the skill dir -- a different check's concern
        else:
            resolved = source_path
        slugs = _cached_target_heading_slugs(resolved, cache)
        if slugs is None or fragment not in slugs:
            offenders.append(target)
    return _dedup(offenders)


def _stale_related_skill_references(body_text: str, skill_dir: Path) -> list[str]:
    """Return each skill name referenced anywhere inside a "**vs. `name`:**"
    Related-skills bullet (its header AND its own explanatory prose) in
    ``body_text`` that does not resolve to an existing sibling skill
    directory.

    A rename that updates every skill's own Steps/Output but misses one
    sibling's "vs. `old-name`:" cross-reference leaves prose that reads
    fine in isolation but names a directory that no longer exists -- this
    is a purely static, single-tree-state check (no git history needed):
    every currently-committed bullet's name must resolve right now.
    """
    offenders: list[str] = []
    for bullet_match in RELATED_SKILL_BULLET_RE.finditer(body_text):
        for name in BACKTICK_SKILL_NAME_RE.findall(bullet_match.group(0)):
            if not (skill_dir.parent / name).is_dir():
                offenders.append(name)
    return offenders


@dataclass(frozen=True)
class SidecarPortability:
    """Three-state summary of the sidecar's portability declaration.

    Derived once, in ``check_shape``, from the single sidecar read+parse
    performed there -- this module never reads the sidecar a second time to
    answer the portability question. Handed to ``_is_portable``, which
    dispatches on ``state`` instead of touching the filesystem itself.

    - "absent": no ``metadata/gitapex.yaml`` under the skill directory. The
      vendored-from-elsewhere case: ``_is_portable`` falls back to the
      near-top body marker.
    - "usable": the sidecar was read and parsed, and its
      ``spec.portability`` is one of ``PORTABILITY_LEVELS``. ``level``
      carries that value; ``_is_portable`` returns ``level == "Portable"``.
    - "unusable": the sidecar exists but could not be read/parsed (bad
      encoding, OS error), or its ``spec.portability`` is missing or not a
      recognised level. ``_is_portable`` returns True unconditionally in
      this state -- see its docstring for why.
    """
    state: str
    level: str | None = None


def _is_portable(body: list[str], sidecar: SidecarPortability) -> bool:
    """Whether the skill declares itself Portable (not Mixed/Repository-scoped).

    Dispatches on ``sidecar`` (a ``SidecarPortability`` derived once in
    ``check_shape`` from its single sidecar read -- this function never
    reads the sidecar itself):

    1. ``sidecar.state == "usable"``: the sidecar alone decides --
       "Portable" -> True, "Mixed" / "Repository-scoped" -> False. This is
       the declaration form every skill in this repository uses, since the
       enum moved out of the SKILL.md body and into the sidecar.
    2. ``sidecar.state == "absent"``: no sidecar file at all -- fall back to
       the near-top body marker (``**Portability: Portable.**``). A skill
       vendored in from another repository carries that marker and no
       sidecar, and must still get the path-citation scan rather than
       silently skipping it.
    3. ``sidecar.state == "unusable"``: the sidecar exists but is
       unreadable, or its ``spec.portability`` is missing/unrecognised.
       Returns True -- run the scan -- WITHOUT consulting the body marker.
       This is deliberate: when a sidecar is present it is authoritative,
       and this repo's own rule is that a false negative in a gate (a
       silently skipped scan) is worse than a false positive (extra
       citation findings). A skill in this state is already failing
       ``portability-declared``, so the extra findings land on an
       already-red skill rather than a silently-skipped one.

    "Mixed" and "Repository-scoped" skills legitimately cite repo-specific
    paths, so the two Portable-only repo-path citation checks
    (``_portable_path_citation_checks``) do not apply to them. The
    bare-issue-citation check (``_issue_citation_checks``) is different: it
    runs unconditionally on every skill regardless of what this function
    returns (issue #254) -- this function's return value never gates it.

    In the fallback (absent) path the level word may wrap onto the line
    after the ``Portability:`` marker (e.g. ``**Portability:**`` then
    ``Portable. ...``). Reading only the marker line would then classify a
    Portable skill as non-Portable and silently skip the path-citation scan
    -- a false negative in the gate, worse than a false positive -- so when
    the marker line carries no level word, the immediately following line
    is folded in before deciding.
    """
    if sidecar.state == "usable":
        return sidecar.level == "Portable"
    if sidecar.state == "unusable":
        return True
    window = body[:PORTABILITY_MAX_BODY_LINE]
    for i, line in enumerate(window):
        if PORTABILITY_RE.search(line):
            decl = line
            if not (PORTABLE_LEVEL_RE.search(line)
                    or NON_PORTABLE_LEVEL_RE.search(line)):
                decl = " ".join(window[i:i + 2])  # level wrapped to next line
            return bool(PORTABLE_LEVEL_RE.search(decl)) and not NON_PORTABLE_LEVEL_RE.search(decl)
    return False


def _blank_fenced_blocks(body_text: str) -> str:
    """Return ``body_text`` with every fenced code block's lines (the
    fence markers themselves included) replaced by empty lines, preserving
    line count and every other line verbatim.

    Shared by ``_strip_illustrative_spans`` (which goes on to also strip
    inline code, URLs, and links) and ``_inline_citation_offenders``
    (which deliberately keeps inline code intact, since it inspects
    exactly those spans) -- both need fenced blocks excluded the same way,
    since a fenced code block is "already illustrative" regardless of
    which citation shape is being scanned for.
    """
    out: list[str] = []
    in_fence = False
    for line in body_text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


# Sentence-ending punctuation followed by whitespace. A deliberately simple
# tokenizer (not a full sentence-boundary detector): it can over-split on an
# abbreviation like "e.g." mid-sentence, but ``_inline_citation_offenders``
# checks both the current AND the immediately preceding sentence for a
# hedge, so an over-split still finds a hedge that landed just before the
# split point -- the failure mode is graceful, not silent. Semicolons are
# handled separately, by ``_split_at_bridging_semicolon`` below, rather than
# folded into this regex -- see that function's docstring for why a blanket
# semicolon split is wrong.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
# A blank line (a run of whitespace-only lines) separating paragraphs, and a
# run of whitespace collapsed to one space -- both precompiled, matching
# this file's own convention, since ``_inline_citation_offenders`` applies
# them to every paragraph of every source file for every citation spec.
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_illustrative_spans(defenced_text: str) -> str:
    """Return ``defenced_text`` (already fence-blanked via
    ``_blank_fenced_blocks``) with every span that quotes a token
    illustratively or externally removed, leaving only bare prose.

    Per line, strips inline code spans, absolute URLs, Markdown
    inline/reference links, and reference definitions. These are exactly
    the forms in which this repo's Portable skills already write an issue
    number or repo path without it resolving live (an inline-code
    ``#149``, a full URL, a ``[PR #2][pr2]`` worked-example link), so what
    remains is a citation sitting unguarded in running prose -- the shape
    the historical incidents took.
    """
    out: list[str] = []
    for line in defenced_text.splitlines():
        if MD_REF_DEF_RE.match(line):
            out.append("")
            continue
        stripped = INLINE_CODE_RE.sub(" ", line)
        stripped = BARE_URL_RE.sub(" ", stripped)
        stripped = MD_INLINE_LINK_RE.sub(" ", stripped)
        stripped = MD_REF_LINK_RE.sub(" ", stripped)
        out.append(stripped)
    return "\n".join(out)


def _split_at_bridging_semicolon(sentence: str,
                                 citation_res: tuple[re.Pattern[str], ...]) -> list[str]:
    """Split ``sentence`` at its first semicolon into two clauses, but ONLY
    when an inline-code citation (matching any of ``citation_res``, across
    every spec, not just one) appears on BOTH sides of it -- otherwise
    return ``[sentence]`` unsplit (issue #273).

    A semicolon is structurally ambiguous in real prose: it can join two
    independent clauses ("Use the hex color `#123456`; see PR `#42` for
    the implementation history." -- Codex's exact reported example, PR
    #269/#273), which must split so the second, unrelated citation does
    not inherit the first's hedge; or it can sit inside a single
    parenthetical aside about ONE citation ("`docs/adr/NNNN-*.md` (line
    24; gitapex's own state on this path is covered under Portability
    level above), uses forward slashes." -- real, pre-existing content in
    this repository's own worked-example-explaining-the-work.md), which
    must NOT split, or the hedge phrase that lands after the semicolon
    loses the citation it was actually describing. Blanket semicolon
    splitting (a first cut of this fix) and blanket non-splitting (the
    original, exploitable design) each broke one of these; requiring a
    citation on both sides is the narrowest rule that keeps both correct.
    Only the FIRST semicolon is considered -- multiple semicolons in one
    sentence are rare enough in this repository's own prose that handling
    only the common case matches this checker's own established "simple,
    not a full parser" tolerance elsewhere in this module.
    """
    semi = sentence.find(";")
    if semi == -1:
        return [sentence]
    before, after = sentence[:semi + 1], sentence[semi + 1:]

    def _has_citation(text: str) -> bool:
        return any(cre.search(m.group(2))
                  for m in INLINE_CODE_RE.finditer(text) for cre in citation_res)

    if _has_citation(before) and _has_citation(after):
        return [before, after]
    return [sentence]


def _inline_citation_offenders(
        defenced_text: str,
        specs: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...],
) -> list[list[str]]:
    """Return, for each ``(citation_re, hedge_phrases)`` pair in ``specs``,
    the list of inline-code citations matching that ``citation_re`` in
    ``defenced_text`` (already fence-blanked via ``_blank_fenced_blocks``)
    that have no phrase from that spec's ``hedge_phrases`` in their own
    sentence (or bridging-semicolon-split clause, see
    ``_split_at_bridging_semicolon``) or the one immediately before it (see
    the module docstring's issue #220 and #263 entries for the rationale,
    and issue #273 for the clause-splitting refinement). The returned list
    is ordered the same as ``specs``. Shared by the repo-path check
    (``REPO_PATH_CITATION_RE``/``HEDGE_PHRASES``) and the issue-number
    check (``ISSUE_CITATION_RE``/``ISSUE_CITATION_HEDGE_PHRASES``) -- the
    citation shape and hedge vocabulary differ per spec, but the
    paragraph/sentence tokenization and the inline-code-span search below
    are identical, so both specs are evaluated in one pass over the same
    tokens rather than one pass per spec (a prior cut of this function
    took one ``citation_re``/``hedge_phrases`` pair and was called once
    per spec by the caller, redoing the full paragraph/sentence split for
    each).

    Bounded to a paragraph first (a run of contiguous non-blank lines),
    then to a sentence within it via ``_SENTENCE_SPLIT_RE``, each further
    split at a bridging semicolon (see ``_split_at_bridging_semicolon`` --
    across every spec's citation shape at once, since clause boundaries
    are shared infrastructure, not per-spec) -- not paragraph-wide, so a
    hedge written for one citation cannot silently exempt an unrelated
    citation many sentences later in the same (possibly long, multi-topic)
    paragraph. Whitespace inside a paragraph is normalized to single
    spaces first, since Markdown line-wraps a hedge phrase across lines
    exactly as often as it wraps any other prose (e.g. "the calling\\n
    repository's own").

    Every inline-code span in the clause -- not just the citation being
    checked -- is blanked out of that clause's hedge search text, so a
    citation cannot self-satisfy the requirement merely because its own
    text happens to contain a hedge word (e.g. a path literally named with
    "gitapex" in it). A hedge is the author's own prose explaining a
    citation; text inside any backtick span is never that, regardless of
    which citation it is or whether it happens to match a citation shape
    at all.

    Two or more citations WITHIN one clause deliberately still share that
    whole clause's hedge search -- this file's own real content relies on
    one leading hedge introducing a list of several different citations
    (e.g. "in this repository's own bookkeeping ...:
    `evals/.../split.md`'s Kept-edit log and `docs/skill-eval-status.md`."),
    which a stricter per-citation windowing design (tried and reverted
    while closing issue #273) broke. The "clause immediately before"
    fallback is instead the layer doing the real work for the reported
    exploit shape: it is used ONLY when that previous clause has no
    citation of its own for this spec -- the established, tested pattern
    is a pure hedge clause ("This repository has also recorded background
    context here.") followed by a citation clause, never two back-to-back
    clauses that each cite something. Without this restriction, a hedge
    that correctly justifies one clause's own citation (e.g. "Use the hex
    color `#123456` for the button.") would leak into a completely
    unrelated citation in the very next clause (e.g. "See PR `#42` for the
    implementation history.") purely because they are clause-adjacent -- a
    review finding on an earlier cut of this check that a bare "previous
    sentence, no further condition" fallback could not tell apart.

    A narrower residual is accepted, not solved, by this design: two
    DIFFERENT citations within the same clause, comma- or
    apposition-joined (no bridging semicolon), where only one is
    genuinely hedged (e.g. "See `#123456`, a hex color reference,
    followed by the real bug `#42`.") still share the clause-wide hedge
    and both pass. Distinguishing that shape from the legitimate "one
    hedge, a list of several citations" shape above would require more
    than a punctuation-based tokenizer can resolve; this checker is a
    deliberately simple, practical approximation (see the module's own
    established tolerance for this tokenizer's "e.g." over-split,
    elsewhere in this file), not a full parser, and the bridging-semicolon
    case is the one issue #273 was actually filed to close.

    Fenced code blocks are already excluded by the caller via
    ``_blank_fenced_blocks`` -- a citation inside a fenced illustrative
    example never reaches this check, matching the module docstring's
    "fenced code blocks stay exempt unconditionally" note. Each spec's
    result list is order-preserving and deduplicated, matching
    ``_portable_citation_offenders``.
    """
    citation_res = tuple(citation_re for citation_re, _hedge_phrases in specs)
    offenders_per_spec: list[list[str]] = [[] for _ in specs]
    for para in _PARAGRAPH_SPLIT_RE.split(defenced_text):
        if not para.strip():
            continue
        normalized = _WHITESPACE_RE.sub(" ", para)
        clauses: list[str] = []
        for sentence in _SENTENCE_SPLIT_RE.split(normalized):
            clauses.extend(_split_at_bridging_semicolon(sentence, citation_res))
        # Precomputed once per paragraph (not just-in-time per clause) so
        # the "previous clause has no citation of its own" check below can
        # look at any earlier clause's code spans without re-scanning.
        all_code_spans = [list(INLINE_CODE_RE.finditer(c)) for c in clauses]
        for i, clause in enumerate(clauses):
            code_spans = all_code_spans[i]
            if not code_spans:
                continue
            prev_lower = clauses[i - 1].lower() if i > 0 else ""
            clause_lower = clause.lower()
            blanked = list(clause_lower)
            for cs in code_spans:
                for pos in range(cs.start(), cs.end()):
                    blanked[pos] = " "
            blanked_lower = "".join(blanked)
            for spec_idx, (citation_re, hedge_phrases) in enumerate(specs):
                spec_matches = [cs for cs in code_spans
                               if citation_re.search(cs.group(2))]
                if not spec_matches:
                    continue
                prev_has_own_citation = i > 0 and any(
                    citation_re.search(cs.group(2)) for cs in all_code_spans[i - 1])
                candidate_prev = "" if prev_has_own_citation else prev_lower
                hedged = any(phrase in blanked_lower or phrase in candidate_prev
                            for phrase in hedge_phrases)
                if not hedged:
                    offenders_per_spec[spec_idx].extend(
                        cs.group(0) for cs in spec_matches)
    return [_dedup(offenders) for offenders in offenders_per_spec]


def _portable_citation_offenders(defenced_text: str) -> tuple[list[str], list[str]]:
    """Return (issue-number, repo-path) bare-prose citations in
    ``defenced_text`` (already fence-blanked via ``_blank_fenced_blocks``).

    Applies the illustrative-span strip first, so only citations left
    unguarded in running prose are reported. Order-preserving and
    deduplicated so the evidence string is stable and terse.
    """
    prose = _strip_illustrative_spans(defenced_text)
    issues = _dedup(m.group(0) for m in ISSUE_CITATION_RE.finditer(prose))
    paths = _dedup(m.group(0) for m in REPO_PATH_CITATION_RE.finditer(prose))
    return issues, paths


def _dedup(items) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)


def _no_xml_check(field: str, value: str) -> CheckResult:
    has_tag = bool(TAG_RE.search(value))
    return CheckResult(
        f"{field}-no-xml", not has_tag, f"{field} has no XML tags",
        "tag found" if has_tag else "no tags")


def _length_check(field: str, value: str, limit: int) -> CheckResult:
    return CheckResult(
        f"{field}-length", len(value) <= limit,
        f"{field} <= {limit} chars", f"{len(value)} chars")


def _yaml_plain_scalar_safety_check(field: str, value: str,
                                    is_plain_scalar: bool) -> CheckResult:
    rule = (f"{field} (an unquoted YAML plain scalar) has no ': ', trailing "
            "':', or ' #'/leading '#' that would break or silently "
            "truncate under a real YAML parser")
    if not is_plain_scalar:
        # A quoted or block-scalar (>/|) value is already safe under a real
        # YAML parser regardless of what characters it contains -- the
        # hazard this check exists for is specific to the unquoted plain
        # scalar form (the one every SKILL.md in this repository currently
        # uses), so a quoted/block-scalar field is exempt rather than
        # scanned against already-unquoted/already-joined text that no
        # longer reflects how it was actually written.
        return CheckResult(f"{field}-yaml-safe", True, rule,
                            "safe (quoted or block scalar in source)")
    colon_hit = UNSAFE_COLON_RE.search(value)
    comment_hit = UNSAFE_COMMENT_RE.search(value)
    # Report whichever hazard occurs first in the string -- a real YAML
    # parser stops at the first one it hits, so that is also the one a
    # maintainer needs to see in order to fix the value.
    if colon_hit and (comment_hit is None or colon_hit.start() <= comment_hit.start()):
        ok, evidence = False, f"unquoted ': ' or trailing ':' at char {colon_hit.start()}"
    elif comment_hit:
        ok, evidence = False, f"unquoted ' #' or leading '#' at char {comment_hit.start()}"
    else:
        ok, evidence = True, "safe"
    return CheckResult(f"{field}-yaml-safe", ok, rule, evidence)


def _resolve_skill_md(target: Path) -> Path:
    return target / "SKILL.md" if target.is_dir() else target


def check_shape(target: Path) -> list[CheckResult]:
    skill_md = _resolve_skill_md(target)
    skill_dir = skill_md.parent
    results: list[CheckResult] = []

    text = skill_md.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)
    fields = frontmatter.fields

    description = fields.get("description", "")
    if not description:
        results.append(CheckResult(
            "description-present", False,
            "description present and non-empty", "missing or empty"))
    else:
        results.append(CheckResult(
            "description-present", True,
            "description present and non-empty", "present"))
        results.append(_no_xml_check("description", description))
        results.append(_length_check(
            "description", description, DESCRIPTION_MAX_CHARS))
        results.append(_yaml_plain_scalar_safety_check(
            "description", description,
            "description" in frontmatter.plain_fields))

    name = fields.get("name")
    if name:
        results.append(CheckResult(
            "name-pattern", bool(NAME_RE.match(name)),
            "name is lowercase-hyphenated", repr(name)))
        results.append(_length_check("name", name, NAME_MAX_CHARS))
        results.append(_no_xml_check("name", name))
        lname = name.lower()
        reserved_hit = any(word in lname for word in RESERVED_NAME_WORDS)
        results.append(CheckResult(
            "name-not-reserved", not reserved_hit,
            f"name contains no reserved word {RESERVED_NAME_WORDS}",
            repr(name)))

    body_lines = len(text.splitlines())
    results.append(CheckResult(
        "body-length", body_lines <= BODY_MAX_LINES,
        f"SKILL.md body <= {BODY_MAX_LINES} lines", f"{body_lines} lines"))

    sidecar = skill_dir / SIDECAR_RELATIVE_PATH
    if not sidecar.is_file():
        results.append(CheckResult(
            "metadata-file-present", False,
            f"{SIDECAR_RELATIVE_PATH} exists", "missing"))
        sidecar_portability = SidecarPortability(state="absent")
    else:
        results.append(CheckResult(
            "metadata-file-present", True,
            f"{SIDECAR_RELATIVE_PATH} exists", "present"))
        # Single read+parse site for the sidecar in this module (see the
        # SidecarPortability docstring): a corrupt (non-UTF-8) or otherwise
        # unreadable sidecar must not raise out of check_shape -- it is a
        # shape defect, reported as FAILed checks, not a usage error.
        try:
            parsed = _parse_manifest(sidecar.read_text(encoding="utf-8"))
            manifest: dict[str, object] | None = parsed.root
            malformed_lines = parsed.malformed_lines
            malformed_reference_items = parsed.malformed_reference_items
            malformed_skill_dependency_items = parsed.malformed_skill_dependency_items
            unknown_skill_dependency_keys = parsed.unknown_skill_dependency_keys
            unknown_lifecycle_keys = parsed.unknown_lifecycle_keys
            unknown_lifecycle_fields = parsed.unknown_lifecycle_fields
            unknown_execution_requirement_keys = parsed.unknown_execution_requirement_keys
            unknown_execution_requirement_tools_keys = parsed.unknown_execution_requirement_tools_keys
            malformed_execution_requirement_tools_items = parsed.malformed_execution_requirement_tools_items
            read_error: str | None = None
        except (OSError, UnicodeDecodeError) as exc:
            manifest = None
            malformed_lines = []
            malformed_reference_items = []
            malformed_skill_dependency_items = []
            unknown_skill_dependency_keys = []
            unknown_lifecycle_keys = []
            unknown_lifecycle_fields = []
            unknown_execution_requirement_keys = []
            unknown_execution_requirement_tools_keys = []
            malformed_execution_requirement_tools_items = []
            read_error = type(exc).__name__

        if manifest is None:
            evidence = f"unreadable: {read_error}"
            results.append(CheckResult(
                "manifest-parsable", False,
                f"{SIDECAR_RELATIVE_PATH} has no malformed top-level lines",
                evidence))
            results.append(CheckResult(
                "manifest-envelope", False,
                f"apiVersion is {EXPECTED_API_VERSION} and kind is {EXPECTED_KIND}",
                evidence))
            results.append(CheckResult(
                "metadata-name-matches-dir", False,
                "metadata.name equals the skill directory name", evidence))
            results.append(CheckResult(
                "portability-declared", False,
                f"spec.portability is one of {PORTABILITY_LEVELS}", evidence))
            results.append(CheckResult(
                "capability-assumption-declared", False,
                f"spec.capabilityAssumption is one of {CAPABILITY_ASSUMPTIONS}",
                evidence))
            results.append(CheckResult(
                "references-well-formed", False,
                "spec.references, if present, is a non-empty list of non-empty strings",
                evidence))
            results.append(CheckResult(
                "skill-dependencies-well-formed", False,
                "spec.skillDependencies, if present, is a mapping with only "
                "requires/relatedTo keys, each -- if present -- a list of "
                "non-empty strings", evidence))
            results.append(CheckResult(
                "skill-dependencies-resolve", False,
                "every name in spec.skillDependencies.requires/relatedTo "
                "resolves to an existing sibling skill directory", evidence))
            results.append(CheckResult(
                "requires-portability-compatible", False,
                "a non-empty spec.skillDependencies.requires is incompatible "
                "with spec.portability: Portable", evidence))
            results.append(CheckResult(
                "lifecycle-well-formed", False,
                "spec.lifecycle, if present, is a mapping with only "
                "experimental/deprecated/stable/renamedFrom keys, each "
                "block sub-key (experimental/deprecated/stable) -- if "
                "present -- a mapping of its own recognized scalar fields "
                "with required fields non-empty and since/removeAfter, if "
                "present, real YYYY-MM-DD dates, and renamedFrom, if "
                "present, a non-empty scalar string", evidence))
            results.append(CheckResult(
                "lifecycle-deprecated-replacement-resolves", False,
                "spec.lifecycle.deprecated.replacement, if a non-empty "
                "string, resolves to an existing sibling skill directory",
                evidence))
            results.append(CheckResult(
                "experimental-stable-compatible", False,
                "spec.lifecycle.experimental and spec.lifecycle.stable "
                "cannot both be present -- a skill cannot be both "
                "not-yet-graduated and already graduated", evidence))
            results.append(CheckResult(
                "execution-requirements-well-formed", False,
                "spec.executionRequirements, if present, is a mapping with "
                "only the tools key; tools, if present, is a mapping with "
                "only read/write/shell keys, each -- if present -- a list "
                "of non-empty strings", evidence))
            # Deliberately not the body-marker fallback: a present-but-broken
            # sidecar is authoritative-and-failing, not absent. Running the
            # scan (rather than skipping it) lands extra findings on a skill
            # that is already failing portability-declared -- a false
            # negative in the gate is worse than a false positive.
            sidecar_portability = SidecarPortability(state="unusable")
        else:
            if malformed_lines:
                count = len(malformed_lines)
                plural = "" if count == 1 else "s"
                manifest_parsable_evidence = (
                    f"{count} malformed line{plural}: {malformed_lines[0]!r}")
            else:
                manifest_parsable_evidence = "no malformed lines"
            results.append(CheckResult(
                "manifest-parsable", not malformed_lines,
                f"{SIDECAR_RELATIVE_PATH} has no malformed top-level lines",
                manifest_parsable_evidence))
            api = manifest.get("apiVersion")
            kind_value = manifest.get("kind")
            envelope_ok = (api == EXPECTED_API_VERSION
                           and kind_value == EXPECTED_KIND)
            results.append(CheckResult(
                "manifest-envelope", envelope_ok,
                f"apiVersion is {EXPECTED_API_VERSION} and kind is {EXPECTED_KIND}",
                f"apiVersion={api!r}, kind={kind_value!r}"))
            meta = manifest.get("metadata")
            meta_name = meta.get("name") if isinstance(meta, dict) else None
            resolved_dir_name = Path(os.path.abspath(skill_dir)).name
            results.append(CheckResult(
                "metadata-name-matches-dir", meta_name == resolved_dir_name,
                "metadata.name equals the skill directory name",
                f"{meta_name!r} vs directory {resolved_dir_name!r}"))
            spec_raw = manifest.get("spec")
            spec_is_mapping = isinstance(spec_raw, dict)
            spec = spec_raw if spec_is_mapping else {}
            portability = spec.get("portability")
            results.append(CheckResult(
                "portability-declared", portability in PORTABILITY_LEVELS,
                f"spec.portability is one of {PORTABILITY_LEVELS}",
                repr(portability)))
            capability = spec.get("capabilityAssumption")
            results.append(CheckResult(
                "capability-assumption-declared",
                capability in CAPABILITY_ASSUMPTIONS,
                f"spec.capabilityAssumption is one of {CAPABILITY_ASSUMPTIONS}",
                repr(capability)))
            references = spec.get("references")
            if not spec_is_mapping:
                # spec itself failed to parse as a mapping (e.g. "spec:
                # some-scalar"), the same precondition failure
                # portability-declared/capability-assumption-declared
                # already report above -- "not declared" would misreport
                # this as the ordinary optional-and-absent case.
                results.append(CheckResult(
                    "references-well-formed", False,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    f"spec is not a mapping: {spec_raw!r}"))
            elif malformed_reference_items:
                # A mapping-shaped or inconsistently-indented list item was
                # already flagged by the parser -- fail loudly instead of
                # reporting on whatever garbled scalar it was misparsed
                # into, even if the rest of the list otherwise looks like
                # a clean list of strings.
                count = len(malformed_reference_items)
                results.append(CheckResult(
                    "references-well-formed", False,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    f"{count} malformed entr{'y' if count == 1 else 'ies'}: "
                    f"{malformed_reference_items[0]!r}"))
            elif references is None:
                results.append(CheckResult(
                    "references-well-formed", True,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    "not declared (optional)"))
            elif (isinstance(references, list) and references
                  and all(isinstance(r, str) and r.strip() for r in references)):
                ref_count = len(references)
                ref_noun = "entry" if ref_count == 1 else "entries"
                results.append(CheckResult(
                    "references-well-formed", True,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    f"{ref_count} {ref_noun}"))
            else:
                ref_evidence = ("empty list" if references == []
                                else f"not a list of non-empty strings: {references!r}")
                results.append(CheckResult(
                    "references-well-formed", False,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    ref_evidence))
            results.extend(_skill_dependency_checks(
                spec_is_mapping, spec_raw, spec,
                malformed_skill_dependency_items, unknown_skill_dependency_keys,
                skill_dir, portability))
            results.extend(_lifecycle_checks(
                spec_is_mapping, spec_raw, spec,
                unknown_lifecycle_keys, unknown_lifecycle_fields, skill_dir))
            results.extend(_execution_requirements_checks(
                spec_is_mapping, spec_raw, spec,
                unknown_execution_requirement_keys,
                unknown_execution_requirement_tools_keys,
                malformed_execution_requirement_tools_items))
            if portability in PORTABILITY_LEVELS:
                sidecar_portability = SidecarPortability(
                    state="usable", level=portability)
            else:
                sidecar_portability = SidecarPortability(state="unusable")

    body = _body_after_frontmatter(text)

    offenders = _out_of_skill_link_targets("\n".join(body), skill_dir)
    results.append(CheckResult(
        "links-inside-skill", not offenders,
        "Markdown link targets resolve inside the skill's own directory",
        "all inside" if not offenders else "outside: " + ", ".join(offenders)))

    # Shared across the SKILL.md anchor check below and every
    # references/*.md anchor check in the loop that follows -- more than
    # one link (in either file) can point at the same target file, and
    # each target's heading-slug set only needs computing once per run.
    # Pre-seeded with SKILL.md's own already-read/parsed body (below) and,
    # in the loop, each reference file's own already-read body -- without
    # this, a same-file bare-fragment link (or a cross-link back into
    # SKILL.md from a references/*.md file) would otherwise cost a second,
    # redundant read()+frontmatter-strip of a file this function already
    # has the text of in hand.
    anchor_slug_cache: dict[Path, frozenset[str] | None] = {
        skill_md: _heading_slugs("\n".join(body)),
    }
    broken_anchors = _broken_anchor_targets(
        "\n".join(body), skill_md, skill_dir, anchor_slug_cache)
    results.append(CheckResult(
        "anchor-targets-resolve", not broken_anchors,
        "Markdown link #fragments resolve to a real heading anchor in "
        "their target file",
        "all resolve" if not broken_anchors
        else "broken: " + ", ".join(broken_anchors)))

    stale_refs = _stale_related_skill_references("\n".join(body), skill_dir)
    results.append(CheckResult(
        "related-skill-references-resolve", not stale_refs,
        "every '**vs. `name`:**' Related-skills bullet name resolves to "
        "an existing sibling skill directory",
        "all resolve" if not stale_refs else "dangling: " + ", ".join(stale_refs)))

    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        nested = sorted(
            str(p.relative_to(refs_dir)) for p in refs_dir.rglob("*")
            if p.is_file() and p.parent != refs_dir and not _is_ignorable(p))
        results.append(CheckResult(
            "references-flat", not nested,
            "references/ files are one level deep",
            "nested: " + ", ".join(nested) if nested else "flat"))
        for ref in sorted(refs_dir.iterdir()):
            if not ref.is_file() or _is_ignorable(ref):
                continue
            try:
                ref_text = ref.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # skip binary/unreadable junk, don't abort the run
            n = len(ref_text.splitlines())
            if n > TOC_MIN_LINES:
                has_toc = bool(TOC_RE.search(ref_text))
                results.append(CheckResult(
                    f"toc:{ref.name}", has_toc,
                    f"reference over {TOC_MIN_LINES} lines has a TOC",
                    f"{n} lines, " + ("TOC found" if has_toc else "no TOC")))
            ref_body = "\n".join(_body_after_frontmatter(ref_text))
            anchor_slug_cache.setdefault(ref, _heading_slugs(ref_body))
            ref_broken_anchors = _broken_anchor_targets(
                ref_body, ref, skill_dir, anchor_slug_cache)
            results.append(CheckResult(
                f"anchor-targets-resolve:{ref.name}", not ref_broken_anchors,
                "Markdown link #fragments resolve to a real heading anchor "
                "in their target file",
                "all resolve" if not ref_broken_anchors
                else "broken: " + ", ".join(ref_broken_anchors)))

    results.extend(_issue_citation_checks(skill_md, skill_dir, body))
    if _is_portable(body, sidecar_portability):
        results.extend(_portable_path_citation_checks(skill_md, skill_dir, body))

    return results


def _citation_sources(skill_md: Path, skill_dir: Path,
                      body: list[str]) -> list[tuple[str, str]]:
    """Return (label, body-text) for SKILL.md and every references/*.md
    file -- the shared source set both citation-check functions below scan.
    """
    sources: list[tuple[str, str]] = [(skill_md.name, "\n".join(body))]
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref in sorted(refs_dir.iterdir()):
            if not ref.is_file() or _is_ignorable(ref):
                continue
            try:
                ref_text = ref.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            sources.append((f"references/{ref.name}",
                            "\n".join(_body_after_frontmatter(ref_text))))
    return sources


def _issue_citation_checks(skill_md: Path, skill_dir: Path,
                           body: list[str]) -> list[CheckResult]:
    """The bare GitHub issue/PR-number citation scan over SKILL.md body and
    references/*.md (see the module docstring's issue #254 entry). Runs
    unconditionally on every skill regardless of declared portability level
    -- unlike ``_portable_path_citation_checks`` below, the caller does not
    gate this one on ``_is_portable``.
    """
    issue_hits: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        defenced = _blank_fenced_blocks(source_text)
        issues, _paths = _portable_citation_offenders(defenced)
        issue_hits += [f"{label}:{c}" for c in issues]

    return [
        CheckResult(
            "no-bare-issue-citation", not issue_hits,
            "No bare-prose GitHub issue/PR-number citation, at any "
            "portability level",
            "none" if not issue_hits else "found: " + ", ".join(issue_hits)),
    ]


# (check-name, citation_re, hedge_phrases, human-readable citation-kind
# label) for each Portable-only inline-code citation check. Table-driven so
# a third citation kind is "add a row", not "copy the block a third time" --
# ``_portable_path_citation_checks`` below builds one ``CheckResult`` per
# row from a single loop instead of a hand-duplicated block per kind.
_INLINE_CITATION_CHECK_SPECS = (
    ("portable-no-unhedged-inline-path-citation", REPO_PATH_CITATION_RE,
     HEDGE_PHRASES, "origin-repository path"),
    ("portable-no-unhedged-inline-issue-citation", ISSUE_CITATION_RE,
     ISSUE_CITATION_HEDGE_PHRASES, "issue/PR-number"),
)


def _portable_path_citation_checks(skill_md: Path, skill_dir: Path,
                                   body: list[str]) -> list[CheckResult]:
    """The Portable-only repo-path and inline-code-issue-number self-citation
    checks over SKILL.md body and references/*.md. Each source contributes
    its offenders labelled by file, so a failure points at the exact file to
    fix. Only called when ``_is_portable`` is true (see ``check_shape``) --
    unlike the bare-prose issue-number scan in ``_issue_citation_checks``,
    every check here stays level-gated (see the module docstring's issue
    #254 entry for why the bare-prose scan is different, and the #263 entry
    for why the inline-code issue-number check joins the two repo-path
    checks here rather than the unconditional one).
    """
    path_hits: list[str] = []
    inline_hits_per_spec: list[list[str]] = [[] for _ in _INLINE_CITATION_CHECK_SPECS]
    inline_specs = tuple((citation_re, hedge_phrases)
                        for _name, citation_re, hedge_phrases, _label
                        in _INLINE_CITATION_CHECK_SPECS)
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        # Fence-blanked once and shared -- the bare-prose scan and the
        # inline-code scan (itself now one pass covering every spec in
        # _INLINE_CITATION_CHECK_SPECS) both need fenced code excluded the
        # same way, and source_text can be a multi-hundred-line references/
        # file.
        defenced = _blank_fenced_blocks(source_text)
        _issues, paths = _portable_citation_offenders(defenced)
        path_hits += [f"{label}:{c}" for c in paths]
        offenders_per_spec = _inline_citation_offenders(defenced, inline_specs)
        for spec_idx, offenders in enumerate(offenders_per_spec):
            inline_hits_per_spec[spec_idx] += [f"{label}:{c}" for c in offenders]

    results = [
        CheckResult(
            "portable-no-repo-path-citation", not path_hits,
            "Portable content has no bare-prose origin-repository path citation",
            "none" if not path_hits else "found: " + ", ".join(path_hits)),
    ]
    for (check_name, _citation_re, hedge_phrases, kind_label), hits in zip(
            _INLINE_CITATION_CHECK_SPECS, inline_hits_per_spec):
        results.append(CheckResult(
            check_name, not hits,
            f"Portable content has no inline-code {kind_label} citation "
            f"without an approved hedge phrase {hedge_phrases} in its own "
            "sentence or the sentence immediately before it",
            "none" if not hits else "found: " + ", ".join(hits)))
    return results


def _valid_skill_dependency_list(value: object) -> bool:
    """Whether ``value`` is a valid requires/relatedTo list: a list of
    non-empty strings. Unlike spec.references, an empty list is valid here
    -- most skills' spec.skillDependencies.requires is expected to be
    empty (see the design spec's Sub-project D rationale)."""
    return isinstance(value, list) and all(
        isinstance(v, str) and v.strip() for v in value)


def _skill_dependency_checks(spec_is_mapping: bool, spec_raw: object,
                              spec: dict[str, object],
                              malformed_items: list[str],
                              unknown_keys: list[str],
                              skill_dir: Path,
                              portability: object) -> list[CheckResult]:
    """The three spec.skillDependencies checks (Sub-project D):
    ``skill-dependencies-well-formed`` (shape), ``skill-dependencies-resolve``
    (every named sibling exists -- the dangling-reference gate), and
    ``requires-portability-compatible`` (a non-empty ``requires`` cannot
    coexist with ``spec.portability: Portable`` -- a portable skill cannot
    hard-depend on a sibling that does not travel with it).

    Mirrors the spec.references cascade in ``check_shape``: shape is
    checked first, since a badly-shaped field has nothing sensible to
    resolve or contradict against -- in every early-return branch below,
    ``skill-dependencies-resolve`` and ``requires-portability-compatible``
    report "nothing to check" rather than silently passing on data that was
    never actually a list.
    """
    well_formed_rule = ("spec.skillDependencies, if present, is a mapping "
                         "with only requires/relatedTo keys, each -- if "
                         "present -- a list of non-empty strings")
    resolve_rule = ("every name in spec.skillDependencies.requires/relatedTo "
                     "resolves to an existing sibling skill directory")
    contradiction_rule = ("a non-empty spec.skillDependencies.requires is "
                           "incompatible with spec.portability: Portable")

    if not spec_is_mapping:
        evidence = f"spec is not a mapping: {spec_raw!r}"
        return [
            CheckResult("skill-dependencies-well-formed", False,
                        well_formed_rule, evidence),
            CheckResult("skill-dependencies-resolve", True, resolve_rule,
                        "nothing to check (spec is not a mapping)"),
            CheckResult("requires-portability-compatible", True,
                        contradiction_rule,
                        "nothing to check (spec is not a mapping)"),
        ]

    if "skillDependencies" not in spec:
        return [
            CheckResult("skill-dependencies-well-formed", True,
                        well_formed_rule, "not declared (optional)"),
            CheckResult("skill-dependencies-resolve", True, resolve_rule,
                        "not declared (optional)"),
            CheckResult("requires-portability-compatible", True,
                        contradiction_rule, "not declared (optional)"),
        ]

    deps = spec.get("skillDependencies")
    # deps is None here means the key was present with a blank (YAML null)
    # value, not absent -- distinct from the "not in spec" case above
    # (issue #356). isinstance(None, dict) is already False, so the
    # existing "not a mapping" branch below fails it correctly without
    # further special-casing.
    if not isinstance(deps, dict):
        evidence = f"not a mapping: {deps!r}"
        return [
            CheckResult("skill-dependencies-well-formed", False,
                        well_formed_rule, evidence),
            CheckResult("skill-dependencies-resolve", True, resolve_rule,
                        "nothing to check (not a mapping)"),
            CheckResult("requires-portability-compatible", True,
                        contradiction_rule, "nothing to check (not a mapping)"),
        ]

    results: list[CheckResult] = []
    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: "
                         f"{unknown_keys[0]!r}")
    if malformed_items:
        count = len(malformed_items)
        problems.append(f"{count} malformed entr{'y' if count == 1 else 'ies'}: "
                         f"{malformed_items[0]!r}")
    for key in SKILL_DEPENDENCY_SUBKEYS:
        if key in deps and not _valid_skill_dependency_list(deps[key]):
            problems.append(f"{key} is not a list of non-empty strings: "
                             f"{deps[key]!r}")

    if problems:
        results.append(CheckResult("skill-dependencies-well-formed", False,
                                    well_formed_rule, "; ".join(problems)))
    else:
        declared = [k for k in SKILL_DEPENDENCY_SUBKEYS if k in deps]
        evidence = f"{', '.join(declared)} declared" if declared else "no keys declared"
        results.append(CheckResult("skill-dependencies-well-formed", True,
                                    well_formed_rule, evidence))

    requires = deps.get("requires")
    requires = requires if _valid_skill_dependency_list(requires) else []
    related = deps.get("relatedTo")
    related = related if _valid_skill_dependency_list(related) else []
    named = list(dict.fromkeys(requires + related))
    dangling = [n for n in named if not (skill_dir.parent / n).is_dir()]
    results.append(CheckResult(
        "skill-dependencies-resolve", not dangling, resolve_rule,
        "all resolve" if not dangling else "dangling: " + ", ".join(dangling)))

    contradiction = bool(requires) and portability == "Portable"
    results.append(CheckResult(
        "requires-portability-compatible", not contradiction, contradiction_rule,
        "ok" if not contradiction
        else f"non-empty requires with portability={portability!r}"))

    return results


def _valid_lifecycle_date(value: object) -> bool:
    """Whether ``value`` is a real calendar date in strict YYYY-MM-DD
    shape, for spec.lifecycle's since/removeAfter fields.

    Regex first (rejects any non-dashed or wrong-width shape outright),
    then ``datetime.date.fromisoformat`` (rejects a shape-valid but
    non-existent date, e.g. "2026-13-45" or "2026-02-30", that a
    regex-only check would silently accept). Gating the regex first also
    blocks ``fromisoformat``'s lenient Python 3.11+ ISO-variant parsing
    from accepting an off-shape string that happens to still be valid
    ISO 8601.
    """
    if not (isinstance(value, str) and LIFECYCLE_DATE_RE.match(value)):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _valid_tracking_issue(value: object) -> bool:
    """Shape-only check for spec.lifecycle.experimental.trackingIssue: an
    anchored ``#123`` or ``owner/repo#123``. Never resolved against a
    live GitHub API call -- this checker is offline/read-only by design.
    """
    return isinstance(value, str) and bool(LIFECYCLE_ISSUE_REF_RE.match(value))


def _lifecycle_checks(spec_is_mapping: bool, spec_raw: object,
                       spec: dict[str, object],
                       unknown_keys: list[str],
                       unknown_fields: list[str],
                       skill_dir: Path) -> list[CheckResult]:
    """The three spec.lifecycle checks: ``lifecycle-well-formed`` (shape),
    ``lifecycle-deprecated-replacement-resolves`` (the dangling-reference
    gate for ``deprecated.replacement``, mirroring
    ``skill-dependencies-resolve``), and
    ``experimental-stable-compatible`` (the one cross-field rule: a skill
    cannot be simultaneously "not yet graduated" and "already graduated on
    some date").

    ``experimental``, ``deprecated``, and ``stable`` are independent,
    optional sub-blocks; ``renamedFrom`` is a plain scalar directly under
    ``spec.lifecycle``, never a sub-block. ``experimental`` and
    ``deprecated`` do not exclude each other (an experimental skill can
    legitimately be superseded by a different experiment) -- but
    ``experimental`` and ``stable`` are a real logical contradiction, so
    unlike the ``deprecated`` pairing, that combination is gated. Mirrors
    the ``_skill_dependency_checks`` cascade: shape is checked first,
    since a badly-shaped field has nothing sensible to resolve or
    contradict against -- every early-return branch below reports both
    ``lifecycle-deprecated-replacement-resolves`` and
    ``experimental-stable-compatible`` as "nothing to check" rather than
    silently passing on data that was never actually a mapping.
    """
    well_formed_rule = (
        "spec.lifecycle, if present, is a mapping with only "
        "experimental/deprecated/stable/renamedFrom keys. experimental "
        "(reason/trackingIssue required, since optional), deprecated "
        "(reason/replacement required, since/removeAfter optional), and "
        "stable (since required, compatibilityGuarantee optional) are "
        "each -- if present -- a mapping of their own recognized scalar "
        "fields; renamedFrom, if present, is a non-empty scalar string. "
        "since/removeAfter, if present, must be real YYYY-MM-DD dates; "
        "trackingIssue, if present, an anchored #123 or owner/repo#123 "
        "reference; compatibilityGuarantee, if present, one of "
        f"{COMPATIBILITY_GUARANTEE_LEVELS}")
    resolve_rule = (
        "spec.lifecycle.deprecated.replacement, if a non-empty string, "
        "resolves to an existing sibling skill directory")
    contradiction_rule = (
        "spec.lifecycle.experimental and spec.lifecycle.stable cannot "
        "both be present -- a skill cannot be both not-yet-graduated and "
        "already graduated")

    if not spec_is_mapping:
        evidence = f"spec is not a mapping: {spec_raw!r}"
        return [
            CheckResult("lifecycle-well-formed", False, well_formed_rule, evidence),
            CheckResult("lifecycle-deprecated-replacement-resolves", True,
                        resolve_rule, "nothing to check (spec is not a mapping)"),
            CheckResult("experimental-stable-compatible", True,
                        contradiction_rule, "nothing to check (spec is not a mapping)"),
        ]

    if "lifecycle" not in spec:
        return [
            CheckResult("lifecycle-well-formed", True, well_formed_rule,
                        "not declared (optional)"),
            CheckResult("lifecycle-deprecated-replacement-resolves", True,
                        resolve_rule, "not declared (optional)"),
            CheckResult("experimental-stable-compatible", True,
                        contradiction_rule, "not declared (optional)"),
        ]

    lifecycle = spec.get("lifecycle")
    # lifecycle is None here means present-but-blank (YAML null), distinct
    # from absent above (issue #356) -- isinstance(None, dict) is already
    # False, so the existing "not a mapping" branch below fails it.
    if not isinstance(lifecycle, dict):
        evidence = f"not a mapping: {lifecycle!r}"
        return [
            CheckResult("lifecycle-well-formed", False, well_formed_rule, evidence),
            CheckResult("lifecycle-deprecated-replacement-resolves", True,
                        resolve_rule, "nothing to check (not a mapping)"),
            CheckResult("experimental-stable-compatible", True,
                        contradiction_rule, "nothing to check (not a mapping)"),
        ]

    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: "
                         f"{unknown_keys[0]!r}")
    if unknown_fields:
        count = len(unknown_fields)
        problems.append(f"{count} unknown field{'' if count == 1 else 's'}: "
                         f"{unknown_fields[0]!r}")

    sub_blocks: dict[str, dict[str, object]] = {}
    for key in LIFECYCLE_SUBKEYS:
        if key not in lifecycle:
            continue
        block = lifecycle[key]
        if not isinstance(block, dict):
            problems.append(f"{key} is not a mapping: {block!r}")
            continue
        sub_blocks[key] = block
        for field in LIFECYCLE_REQUIRED_FIELDS[key]:
            val = block.get(field)
            if not (isinstance(val, str) and val.strip()):
                problems.append(
                    f"{key}.{field} is missing or not a non-empty string: {val!r}")
        for field in ("since", "removeAfter"):
            if field in block and not _valid_lifecycle_date(block[field]):
                problems.append(
                    f"{key}.{field} is not a YYYY-MM-DD date: {block[field]!r}")
        if key == "experimental" and "trackingIssue" in block \
                and not _valid_tracking_issue(block["trackingIssue"]):
            problems.append(
                f"experimental.trackingIssue is not a #123 or owner/repo#123 "
                f"reference: {block['trackingIssue']!r}")
        if key == "stable" and "compatibilityGuarantee" in block \
                and block["compatibilityGuarantee"] not in COMPATIBILITY_GUARANTEE_LEVELS:
            problems.append(
                f"stable.compatibilityGuarantee is not one of "
                f"{COMPATIBILITY_GUARANTEE_LEVELS}: "
                f"{block['compatibilityGuarantee']!r}")

    if "renamedFrom" in lifecycle:
        renamed_from = lifecycle["renamedFrom"]
        if not (isinstance(renamed_from, str) and renamed_from.strip()):
            problems.append(
                f"renamedFrom is not a non-empty string: {renamed_from!r}")

    if problems:
        results = [CheckResult("lifecycle-well-formed", False, well_formed_rule,
                                "; ".join(problems))]
    else:
        declared = [k for k in LIFECYCLE_SUBKEYS if k in sub_blocks]
        if "renamedFrom" in lifecycle:
            declared.append("renamedFrom")
        evidence = f"{', '.join(declared)} declared" if declared else "no keys declared"
        results = [CheckResult("lifecycle-well-formed", True, well_formed_rule,
                                evidence)]

    deprecated = sub_blocks.get("deprecated")
    replacement = deprecated.get("replacement") if deprecated else None
    if isinstance(replacement, str) and replacement.strip():
        exists = (skill_dir.parent / replacement).is_dir()
        results.append(CheckResult(
            "lifecycle-deprecated-replacement-resolves", exists, resolve_rule,
            "resolves" if exists else f"dangling: {replacement!r}"))
    else:
        results.append(CheckResult(
            "lifecycle-deprecated-replacement-resolves", True, resolve_rule,
            "nothing to check (replacement missing or invalid)"))

    contradiction = "experimental" in sub_blocks and "stable" in sub_blocks
    results.append(CheckResult(
        "experimental-stable-compatible", not contradiction, contradiction_rule,
        "ok" if not contradiction
        else "both experimental and stable are present"))
    return results


def _valid_execution_requirements_tools_list(value: object) -> bool:
    """Whether ``value`` is a valid tools.read/write/shell list: a list of
    non-empty strings. Mirrors ``_valid_skill_dependency_list`` -- an empty
    list is valid here too, since it is a deliberate "zero tools of this
    kind needed" statement, distinct from the subkey being absent
    entirely."""
    return isinstance(value, list) and all(
        isinstance(v, str) and v.strip() for v in value)


def _execution_requirements_checks(spec_is_mapping: bool, spec_raw: object,
                                    spec: dict[str, object],
                                    unknown_keys: list[str],
                                    unknown_tools_keys: list[str],
                                    malformed_tools_items: list[str]
                                    ) -> list[CheckResult]:
    """The one spec.executionRequirements check landed so far (issue #349,
    #307 Workstream W1 first slice): ``execution-requirements-well-formed``.

    Mirrors ``_skill_dependency_checks``'s early-return ladder (spec not a
    mapping / not declared / not a mapping) before real validation, and its
    problem-accumulation-then-single-CheckResult pattern. Unlike
    spec.skillDependencies or spec.lifecycle, this field has only one
    recognized top-level subkey so far, ``tools`` -- the remaining #307 W1
    categories (filesystem, network, mcp, credentials, browser,
    externalServices, context) are deferred to sibling child issues, and
    any key here other than ``tools`` fails closed via ``unknown_keys``
    rather than being silently accepted as reserved space, per #307's
    security invariant 4. There is no dangling-reference or cross-field
    check the way spec.skillDependencies/spec.lifecycle have one each --
    tools' read/write/shell entries are free-form capability tags, not
    names that resolve against sibling skill directories, and no rule
    ties this field to portability/capabilityAssumption/lifecycle.
    """
    well_formed_rule = ("spec.executionRequirements, if present, is a "
                         "mapping with only the tools key; tools, if "
                         "present, is a mapping with only read/write/shell "
                         "keys, each -- if present -- a list of non-empty "
                         "strings")

    if not spec_is_mapping:
        return [CheckResult(
            "execution-requirements-well-formed", False, well_formed_rule,
            f"spec is not a mapping: {spec_raw!r}")]

    if "executionRequirements" not in spec:
        return [CheckResult(
            "execution-requirements-well-formed", True, well_formed_rule,
            "not declared (optional)")]

    execution_requirements = spec.get("executionRequirements")
    # None here means present-but-blank (YAML null), distinct from absent
    # above (issue #356) -- isinstance(None, dict) is already False, so
    # the existing "not a mapping" branch below fails it correctly.
    if not isinstance(execution_requirements, dict):
        return [CheckResult(
            "execution-requirements-well-formed", False, well_formed_rule,
            f"not a mapping: {execution_requirements!r}")]

    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: "
                         f"{unknown_keys[0]!r}")

    tools_present = "tools" in execution_requirements
    tools = execution_requirements.get("tools")
    # tools_present with tools is None means present-but-blank (YAML
    # null), distinct from tools being absent entirely -- previously both
    # fell through this elif ladder untouched and passed silently
    # (issue #356: "A blank tools: value is YAML null, but the parser
    # converts it to an empty mapping and passes").
    if tools_present and not isinstance(tools, dict):
        problems.append(f"tools is not a mapping: {tools!r}")
    elif isinstance(tools, dict):
        if unknown_tools_keys:
            count = len(unknown_tools_keys)
            problems.append(
                f"{count} unknown tools key{'' if count == 1 else 's'}: "
                f"{unknown_tools_keys[0]!r}")
        if malformed_tools_items:
            count = len(malformed_tools_items)
            problems.append(
                f"{count} malformed tools entr{'y' if count == 1 else 'ies'}: "
                f"{malformed_tools_items[0]!r}")
        for key in EXEC_REQ_TOOLS_SUBKEYS:
            if key in tools and not _valid_execution_requirements_tools_list(tools[key]):
                problems.append(f"tools.{key} is not a list of non-empty "
                                 f"strings: {tools[key]!r}")

    if problems:
        return [CheckResult("execution-requirements-well-formed", False,
                             well_formed_rule, "; ".join(problems))]

    declared = ([f"tools.{k}" for k in EXEC_REQ_TOOLS_SUBKEYS if k in tools]
                if isinstance(tools, dict) else [])
    evidence = ", ".join(declared) + " declared" if declared else "no keys declared"
    return [CheckResult("execution-requirements-well-formed", True,
                         well_formed_rule, evidence)]


def format_report(results: list[CheckResult]) -> str:
    width = max((len(r.name) for r in results), default=5)
    lines = [f"{'CHECK'.ljust(width)}  RESULT  EVIDENCE (rule)"]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"{r.name.ljust(width)}  {status}    "
                     f"{r.evidence}  ({r.rule})")
    passed = sum(1 for r in results if r.passed)
    lines.append(f"\n{passed}/{len(results)} checks passed")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a SKILL.md's deterministic shape (read-only).")
    parser.add_argument(
        "target", help="Path to a skill directory or a SKILL.md file.")
    args = parser.parse_args(argv)
    target = Path(args.target)
    skill_md = _resolve_skill_md(target)
    if not skill_md.is_file():
        print(f"error: no SKILL.md found at: {target}", file=sys.stderr)
        return 2
    try:
        results = check_shape(target)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: could not read skill files: {exc}", file=sys.stderr)
        return 2
    print(format_report(results))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
