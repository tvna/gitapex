"""Deterministic shape checker for a SKILL.md and its references/ dir.

Single source of truth for the deterministic "shape" lane of the
evaluating-skill-quality skill. It decides only the mechanically
checkable rules; the nine maturity dimensions stay model-judged and are
deliberately NOT implemented here.

Read-only: reads the target skill's files only. No writes, no network,
no mutation. Effects are limited to stdout and the process exit code.

Checks (the canonical list -- the manual fallback is to apply these):
  - description: present/non-empty, no XML tags, <= 1024 chars
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
    its own list and not an unquoted YAML mapping key such as "path: foo"
    (references-well-formed); spec.skillDependencies, if present, is a
    mapping with only the keys requires/relatedTo, each -- if present -- a
    list of non-empty scalar strings with the same per-item shape rules as
    spec.references, except an empty list is valid here, unlike
    spec.references (skill-dependencies-well-formed); every name listed in
    either list resolves to an existing sibling skill directory
    (skill-dependencies-resolve); and a non-empty
    spec.skillDependencies.requires is incompatible with
    spec.portability: Portable (requires-portability-compatible).
    spec.lifecycle, if present, is a mapping with only the keys
    experimental/deprecated, each -- if present -- a mapping of its own
    recognized scalar fields (experimental: reason/trackingIssue
    required, since optional; deprecated: reason/replacement required,
    since/removeAfter optional), with since/removeAfter, if present, real
    calendar dates in strict YYYY-MM-DD shape and trackingIssue, if
    present, an anchored #123 or owner/repo#123 reference
    (lifecycle-well-formed); and, when deprecated.replacement is a
    non-empty string, it resolves to an existing sibling skill directory,
    the same dangling-reference gate spec.skillDependencies uses
    (lifecycle-deprecated-replacement-resolves). experimental and
    deprecated are independent and optional -- neither implies nor
    excludes the other, and no skill's runtime procedure may read or
    branch on either (the sidecar's behavior-neutrality invariant). Other
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
  - Portable self-citation (only when the skill declares "Portable", not
    "Mixed" or "Repository-scoped"). The declaration is read
    sidecar-primary with a body-marker fallback: the sidecar's
    spec.portability decides whenever it is present and usable -- the form
    every skill in this repository uses -- a skill with no sidecar at all
    (typically one vendored in from another repository) falls back to the
    near-top "**Portability: <level>.**" body marker, and a skill whose
    sidecar exists but is unreadable or carries no recognised
    spec.portability runs the scan unconditionally (a false negative in a
    gate is worse than a false positive, and such a skill is already
    failing portability-declared) -- so no skill state ever silently skips
    it. The scan itself: no bare-prose GitHub issue/PR-number
    citation (#149 or owner/repo#149) and no bare-prose origin-repository
    path citation (evals/... or docs/...) in SKILL.md or references/*.md
    body text. A bare #N auto-links relative to whichever repository
    currently hosts the file and silently resolves to the wrong issue
    once the skill is vendored; a repo-relative path breaks the same way.
    Matches inside inline code (`#149`), fenced code blocks, absolute
    URLs, and Markdown links are excluded -- those are the established
    ways this repo's Portable skills quote such a token illustratively
    without it resolving live. This is the deterministic backstop for the
    rubric's dimension-6 Portable-skill rule; the semantic judgment of
    whether a citation is illustrative context vs. the skill's own
    bookkeeping stays with that model-judged dimension.
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

# spec.skillDependencies's two recognized subkeys, and the shape of their
# lines. Subkeys sit at 4 spaces (one level under skillDependencies' own
# 2-space key). List items accept 4 or more spaces -- real YAML allows a
# block sequence indented level with its own key (4 spaces, same as
# "requires:"/"relatedTo:" themselves) or further indented (this repo's
# convention); requiring one exact width would silently drop an otherwise-
# valid item at a different indent instead of reading it, the same
# accommodation REFERENCES_LIST_ITEM_RE already makes for spec.references.
SKILL_DEPENDENCY_SUBKEYS = ("requires", "relatedTo")
SKILL_DEP_SUBKEY_RE = re.compile(r"^[ ]{4}(requires|relatedTo):\s*(.*)$")
SKILL_DEP_UNKNOWN_KEY_RE = re.compile(r"^[ ]{4}([A-Za-z0-9_-]+):")
SKILL_DEP_LIST_ITEM_RE = re.compile(r"^[ ]{4,}-\s*(.*)$")

# spec.lifecycle's two recognized sub-blocks -- "experimental" (entry side:
# not yet proven, mirrors Rust's #[unstable(feature, issue)], Python's
# provisional/PendingDeprecationWarning APIs, Go's GOEXPERIMENT-gated
# features, Kubernetes' alpha/beta feature gates) and "deprecated" (exit
# side: superseded, mirrors Rust's #[deprecated(since, note)], Go's
# "// Deprecated:" doc comment, Python's warnings.deprecated/PEP 702,
# Kubernetes' API deprecation policy). The two are independent and
# optional -- neither implies nor excludes the other, and a skill with
# neither is implicitly Stable (every skill in this repository today).
# One nesting level deeper than spec.skillDependencies: subkeys sit at 4
# spaces (same as requires/relatedTo), but each subkey opens ANOTHER
# nested block of scalar fields at 6 spaces, rather than a list.
LIFECYCLE_SUBKEYS = ("experimental", "deprecated")
LIFECYCLE_FIELDS = {
    "experimental": ("reason", "trackingIssue", "since"),
    "deprecated": ("reason", "replacement", "since", "removeAfter"),
}
LIFECYCLE_REQUIRED_FIELDS = {
    "experimental": ("reason", "trackingIssue"),
    "deprecated": ("reason", "replacement"),
}
LIFECYCLE_SUBKEY_RE = re.compile(r"^[ ]{4}(experimental|deprecated):\s*(.*)$")
LIFECYCLE_UNKNOWN_SUBKEY_RE = re.compile(r"^[ ]{4}([A-Za-z0-9_-]+):")
# Matches ANY key at this indent, recognized or not -- the handler tells
# them apart by membership in LIFECYCLE_FIELDS[subkey], the same "match
# broad, filter narrow" approach SKILL_DEP_UNKNOWN_KEY_RE's sibling
# SKILL_DEP_SUBKEY_RE takes one level up.
LIFECYCLE_FIELD_RE = re.compile(r"^[ ]{6}([A-Za-z0-9_-]+):\s*(.*)$")
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

TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
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
# An absolute-URL scheme (http:, https:, mailto:, ftp:, ...) -- anything
# matching this is external, not a same-repo relative path.
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

# Portable self-citation scan (see the module docstring). A skill counts as
# Portable only when its portability marker says "Portable" without the
# "Mixed" / "Repository-scoped" qualifiers -- those levels legitimately cite
# repo-specific paths and issues, so the scan does not apply to them.
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
INLINE_CODE_RE = re.compile(r"`[^`]*`")
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


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    rule: str
    evidence: str


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract top-level 'key: value' pairs from a leading --- block.

    Handles the scalar forms real SKILL.md files use: plain, single/double
    quoted, and YAML block scalars (folded '>' and literal '|', whose
    indented continuation lines are joined). Strips a leading UTF-8 BOM and
    requires a closing '---'; without one the frontmatter is treated as
    malformed (returns {}), rather than reading body lines as fields. No
    external YAML dependency.
    """
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines))
                if lines[i].strip() == "---"), None)
    if end is None:
        return {}
    fields: dict[str, str] = {}
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
        fields[key] = _unquote(value)
        i += 1
    return fields


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
    spec.lifecycle that is not ``experimental`` or ``deprecated`` (trimmed
    line); ``unknown_lifecycle_fields`` holds each key found inside either
    of those sub-blocks that is not one of its own recognized fields
    (e.g. "extra: foo" under experimental). Both empty when the field is
    absent or parsed cleanly. There is no malformed-item channel for
    spec.lifecycle the way spec.references/spec.skillDependencies have
    one for list items -- every leaf under spec.lifecycle is a plain
    scalar, so a wrong-type value is simply stored as the raw string by
    the field parser and fails the downstream well-formed check on shape,
    with nothing that needs a separate parse-time detection channel.
    """
    root: dict[str, object]
    malformed_lines: list[str]
    malformed_reference_items: list[str]
    malformed_skill_dependency_items: list[str]
    unknown_skill_dependency_keys: list[str]
    unknown_lifecycle_keys: list[str]
    unknown_lifecycle_fields: list[str]


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
      space.
    - spec.lifecycle (and only that key, and only directly under spec) is
      read as a mapping with exactly two recognized sub-blocks,
      ``experimental`` and ``deprecated``, each -- at exactly 4-space
      indent -- an empty value opening a nested block of scalar fields at
      exactly 6-space indent (``reason``/``trackingIssue``/``since`` for
      ``experimental``; ``reason``/``replacement``/``since``/
      ``removeAfter`` for ``deprecated``). One nesting level deeper than
      spec.skillDependencies, but with scalar leaves instead of a list --
      there is no list-item shape inside spec.lifecycle at all. A key
      directly under spec.lifecycle other than ``experimental``/
      ``deprecated`` is collected into
      ``ManifestParse.unknown_lifecycle_keys``; a key inside either
      sub-block that is not one of its own recognized fields is collected
      into ``ManifestParse.unknown_lifecycle_fields`` -- both instead of
      being silently skipped, for the same reason
      ``unknown_skill_dependency_keys`` exists. A sub-block header written
      as an inline scalar instead of opening a block (e.g.
      ``experimental: true``) is stored as that raw scalar under its own
      key, exactly as spec.skillDependencies' non-list scalar fallback
      works, so the checker layer reports it as the wrong type rather than
      silently dropping it.

    Every other nested map or list (e.g. spec.evalStatus) is still
    deliberately skipped, exactly as before: skipping keeps this
    stdlib-only with no YAML dependency. Inline '# comment' text after a
    value on the same line is not stripped -- it is read as part of the
    value, which is safe (fails closed against the expected enum/literal)
    but is not a supported way to annotate a sidecar field.

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
    scalar) or an item indented inconsistently with the rest of its own
    list is collected (trimmed) into ``ManifestParse.malformed_reference_items``
    or ``ManifestParse.malformed_skill_dependency_items`` respectively,
    instead of being silently accepted as a garbled scalar string.
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
    collecting_dep_list: list[str] | None = None
    collecting_dep_key: str | None = None
    dep_list_indent: int | None = None
    malformed_deps: list[str] = []
    unknown_dep_keys: list[str] = []
    in_lifecycle = False
    lifecycle: dict[str, object] = {}
    lifecycle_subkey: str | None = None
    lifecycle_field_buffer: dict[str, object] = {}
    unknown_lifecycle_keys: list[str] = []
    unknown_lifecycle_fields: list[str] = []

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
        nonlocal in_skill_deps, skill_deps
        _finalize_dep_list()
        if in_skill_deps and current is not None:
            current["skillDependencies"] = skill_deps
        in_skill_deps = False
        skill_deps = {}

    def _finalize_lifecycle_subkey() -> None:
        nonlocal lifecycle_subkey, lifecycle_field_buffer
        if lifecycle_subkey is not None:
            lifecycle[lifecycle_subkey] = lifecycle_field_buffer
        lifecycle_subkey = None
        lifecycle_field_buffer = {}

    def _finalize_lifecycle() -> None:
        nonlocal in_lifecycle, lifecycle
        _finalize_lifecycle_subkey()
        if in_lifecycle and current is not None:
            current["lifecycle"] = lifecycle
        in_lifecycle = False
        lifecycle = {}

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
                else:
                    collecting_dep_list.append(_unquote(raw_text))
                continue
            # Not a list item: this requires/relatedTo list ends here.
            _finalize_dep_list()
        if in_skill_deps:
            subkey = SKILL_DEP_SUBKEY_RE.match(line)
            if subkey:
                key, value = subkey.group(1), subkey.group(2).strip()
                if value == "[]":
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
            unknown = SKILL_DEP_UNKNOWN_KEY_RE.match(line)
            if unknown:
                unknown_dep_keys.append(line.strip())
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 4:
                # Stray content deeper inside the block that is not a
                # recognized subkey or list-item line -- skip silently,
                # consistent with "indented lines are never malformed"
                # except the explicit channels above.
                continue
            # Dedented below the block's own indent: skillDependencies ends
            # here. Finalize it and fall through to process this line
            # normally below.
            _finalize_skill_deps()
        if lifecycle_subkey is not None:
            field = LIFECYCLE_FIELD_RE.match(line)
            if field:
                key, value = field.group(1), field.group(2).strip()
                if key in LIFECYCLE_FIELDS.get(lifecycle_subkey, ()):
                    if value:
                        lifecycle_field_buffer[key] = _unquote(value)
                else:
                    unknown_lifecycle_fields.append(line.strip())
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 6:
                # Stray content deeper inside the sub-block that is not a
                # recognized field line -- skip silently, consistent with
                # "indented lines are never malformed" except the
                # explicit unknown_lifecycle_fields channel above.
                continue
            # Dedented below the sub-block's own indent: this
            # experimental/deprecated block ends here. Finalize it and
            # fall through to process this line normally below (it may be
            # the other sub-block's header, or a dedent out of lifecycle
            # entirely).
            _finalize_lifecycle_subkey()
        if in_lifecycle:
            subkey = LIFECYCLE_SUBKEY_RE.match(line)
            if subkey:
                key, value = subkey.group(1), subkey.group(2).strip()
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
                continue
            unknown = LIFECYCLE_UNKNOWN_SUBKEY_RE.match(line)
            if unknown:
                unknown_lifecycle_keys.append(line.strip())
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 4:
                # Stray content deeper inside spec.lifecycle that is not a
                # recognized sub-block header -- skip silently, same
                # reserved-field treatment as spec.skillDependencies.
                continue
            # Dedented below spec.lifecycle's own indent: the block ends
            # here. Finalize it and fall through to process this line
            # normally below.
            _finalize_lifecycle()
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
    return ManifestParse(root=root, malformed_lines=malformed,
                          malformed_reference_items=malformed_refs,
                          malformed_skill_dependency_items=malformed_deps,
                          unknown_skill_dependency_keys=unknown_dep_keys,
                          unknown_lifecycle_keys=unknown_lifecycle_keys,
                          unknown_lifecycle_fields=unknown_lifecycle_fields)


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
    raw_targets = [m.group(1) for m in LINK_RE.finditer(body_text)]
    raw_targets += [m.group(1) for m in REFDEF_RE.finditer(body_text)]
    offenders = []
    for raw in raw_targets:
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
        if normalized != skill_norm and not normalized.startswith(skill_norm + os.sep):
            offenders.append(target)
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
       sidecar, and must still get the citation scan rather than silently
       skipping it.
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
    paths and issues, so the Portable self-citation scan does not apply to
    them.

    In the fallback (absent) path the level word may wrap onto the line
    after the ``Portability:`` marker (e.g. ``**Portability:**`` then
    ``Portable. ...``). Reading only the marker line would then classify a
    Portable skill as non-Portable and silently skip the citation scan -- a
    false negative in the gate, worse than a false positive -- so when the
    marker line carries no level word, the immediately following line is
    folded in before deciding.
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
    inline code, URLs, and links) and ``_inline_repo_path_offenders``
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
# abbreviation like "e.g." mid-sentence, but ``_inline_repo_path_offenders``
# checks both the current AND the immediately preceding sentence for a
# hedge, so an over-split still finds a hedge that landed just before the
# split point -- the failure mode is graceful, not silent.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


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


def _inline_repo_path_offenders(defenced_text: str) -> list[str]:
    """Return each inline-code ``evals/``/``docs/`` path citation in
    ``defenced_text`` (already fence-blanked via ``_blank_fenced_blocks``)
    that has no approved hedge phrase (see ``HEDGE_PHRASES``) in its own
    sentence or the sentence immediately before it (see the module
    docstring's issue #220 entry for the rationale).

    Bounded to a paragraph first (a run of contiguous non-blank lines),
    then to a sentence within it, via the deliberately simple
    ``_SENTENCE_SPLIT_RE`` tokenizer -- sentence-level, not paragraph-wide,
    so a hedge written for one citation cannot silently exempt an unrelated
    citation many sentences later in the same (possibly long, multi-topic)
    paragraph. Whitespace inside a paragraph is normalized to single spaces
    first, since Markdown line-wraps a hedge phrase across lines exactly as
    often as it wraps any other prose (e.g. "the calling\\n   repository's
    own"). Each citation's own matched text is excluded from its hedge
    search, so a citation cannot self-satisfy the requirement merely
    because its own path text happens to contain a hedge word (e.g. a path
    literally named with "gitapex" in it). Fenced code blocks are already
    excluded by the caller via ``_blank_fenced_blocks`` -- a citation
    inside a fenced illustrative example never reaches this check, matching
    the module docstring's "fenced code blocks stay exempt unconditionally"
    note. Order-preserving and deduplicated, matching
    ``_portable_citation_offenders``.
    """
    offenders: list[str] = []
    for para in re.split(r"\n\s*\n", defenced_text):
        if not para.strip():
            continue
        normalized = re.sub(r"\s+", " ", para)
        sentences = _SENTENCE_SPLIT_RE.split(normalized)
        for i, sentence in enumerate(sentences):
            matches = [m for m in INLINE_CODE_RE.finditer(sentence)
                       if REPO_PATH_CITATION_RE.search(m.group(0)[1:-1])]
            if not matches:
                continue
            prev_lower = sentences[i - 1].lower() if i > 0 else ""
            for m in matches:
                local_lower = (sentence[:m.start()] + sentence[m.end():]).lower()
                if not any(phrase in local_lower or phrase in prev_lower
                          for phrase in HEDGE_PHRASES):
                    offenders.append(m.group(0))
    return _dedup(offenders)


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


def _resolve_skill_md(target: Path) -> Path:
    return target / "SKILL.md" if target.is_dir() else target


def check_shape(target: Path) -> list[CheckResult]:
    skill_md = _resolve_skill_md(target)
    skill_dir = skill_md.parent
    results: list[CheckResult] = []

    text = skill_md.read_text(encoding="utf-8")
    fields = _parse_frontmatter(text)

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
            read_error: str | None = None
        except (OSError, UnicodeDecodeError) as exc:
            manifest = None
            malformed_lines = []
            malformed_reference_items = []
            malformed_skill_dependency_items = []
            unknown_skill_dependency_keys = []
            unknown_lifecycle_keys = []
            unknown_lifecycle_fields = []
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
                "experimental/deprecated keys, each -- if present -- a "
                "mapping of its own recognized scalar fields with required "
                "fields non-empty and since/removeAfter, if present, real "
                "YYYY-MM-DD dates", evidence))
            results.append(CheckResult(
                "lifecycle-deprecated-replacement-resolves", False,
                "spec.lifecycle.deprecated.replacement, if a non-empty "
                "string, resolves to an existing sibling skill directory",
                evidence))
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

    if _is_portable(body, sidecar_portability):
        results.extend(_portable_citation_checks(skill_md, skill_dir, body))

    return results


def _portable_citation_checks(skill_md: Path, skill_dir: Path,
                              body: list[str]) -> list[CheckResult]:
    """The two Portable self-citation checks over SKILL.md body and
    references/*.md. Each source contributes its offenders labelled by file,
    so a failure points at the exact file to fix.
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

    issue_hits: list[str] = []
    path_hits: list[str] = []
    inline_path_hits: list[str] = []
    for label, source_text in sources:
        # Fence-blanked once and shared -- both offender scans below need
        # fenced code excluded the same way, and source_text can be a
        # multi-hundred-line references/ file.
        defenced = _blank_fenced_blocks(source_text)
        issues, paths = _portable_citation_offenders(defenced)
        issue_hits += [f"{label}:{c}" for c in issues]
        path_hits += [f"{label}:{c}" for c in paths]
        inline_path_hits += [f"{label}:{c}"
                             for c in _inline_repo_path_offenders(defenced)]

    return [
        CheckResult(
            "portable-no-issue-citation", not issue_hits,
            "Portable content has no bare-prose GitHub issue/PR-number citation",
            "none" if not issue_hits else "found: " + ", ".join(issue_hits)),
        CheckResult(
            "portable-no-repo-path-citation", not path_hits,
            "Portable content has no bare-prose origin-repository path citation",
            "none" if not path_hits else "found: " + ", ".join(path_hits)),
        CheckResult(
            "portable-no-unhedged-inline-path-citation", not inline_path_hits,
            "Portable content has no inline-code origin-repository path "
            f"citation without an approved hedge phrase {HEDGE_PHRASES} in "
            "its own sentence or the sentence immediately before it",
            "none" if not inline_path_hits
            else "found: " + ", ".join(inline_path_hits)),
    ]


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

    deps = spec.get("skillDependencies")
    if deps is None:
        return [
            CheckResult("skill-dependencies-well-formed", True,
                        well_formed_rule, "not declared (optional)"),
            CheckResult("skill-dependencies-resolve", True, resolve_rule,
                        "not declared (optional)"),
            CheckResult("requires-portability-compatible", True,
                        contradiction_rule, "not declared (optional)"),
        ]

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
    """The two spec.lifecycle checks: ``lifecycle-well-formed`` (shape) and
    ``lifecycle-deprecated-replacement-resolves`` (the dangling-reference
    gate for ``deprecated.replacement``, mirroring
    ``skill-dependencies-resolve``).

    ``experimental`` and ``deprecated`` are independent, optional
    sub-blocks -- neither implies nor excludes the other, and there is no
    mutual-exclusion check between them. Mirrors the
    ``_skill_dependency_checks`` cascade: shape is checked first, since a
    badly-shaped field has nothing sensible to resolve against -- every
    early-return branch below reports ``lifecycle-deprecated-replacement-resolves``
    as "nothing to check" rather than silently passing on data that was
    never actually a mapping.
    """
    well_formed_rule = (
        "spec.lifecycle, if present, is a mapping with only "
        "experimental/deprecated keys, each -- if present -- a mapping of "
        "its own recognized scalar fields (experimental: reason/"
        "trackingIssue required, since optional; deprecated: reason/"
        "replacement required, since/removeAfter optional), with since/"
        "removeAfter, if present, real YYYY-MM-DD dates and trackingIssue, "
        "if present, an anchored #123 or owner/repo#123 reference")
    resolve_rule = (
        "spec.lifecycle.deprecated.replacement, if a non-empty string, "
        "resolves to an existing sibling skill directory")

    if not spec_is_mapping:
        evidence = f"spec is not a mapping: {spec_raw!r}"
        return [
            CheckResult("lifecycle-well-formed", False, well_formed_rule, evidence),
            CheckResult("lifecycle-deprecated-replacement-resolves", True,
                        resolve_rule, "nothing to check (spec is not a mapping)"),
        ]

    lifecycle = spec.get("lifecycle")
    if lifecycle is None:
        return [
            CheckResult("lifecycle-well-formed", True, well_formed_rule,
                        "not declared (optional)"),
            CheckResult("lifecycle-deprecated-replacement-resolves", True,
                        resolve_rule, "not declared (optional)"),
        ]

    if not isinstance(lifecycle, dict):
        evidence = f"not a mapping: {lifecycle!r}"
        return [
            CheckResult("lifecycle-well-formed", False, well_formed_rule, evidence),
            CheckResult("lifecycle-deprecated-replacement-resolves", True,
                        resolve_rule, "nothing to check (not a mapping)"),
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

    if problems:
        results = [CheckResult("lifecycle-well-formed", False, well_formed_rule,
                                "; ".join(problems))]
    else:
        declared = [k for k in LIFECYCLE_SUBKEYS if k in sub_blocks]
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
    return results


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
