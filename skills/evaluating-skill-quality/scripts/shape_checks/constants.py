"""Module-level constants, regexes, and the CheckResult dataclass shared
across every shape_checks submodule. No detection logic lives here."""

from __future__ import annotations

import re
from dataclasses import dataclass

# The Claude Developer Platform Skills API enforces description <= 1024
# chars and name <= 64 lowercase-hyphen chars (platform.claude.com/docs/
# en/agents-and-tools/agent-skills/best-practices) -- stricter than Claude
# Code's own frontmatter parsing, so this checker uses the platform's
# tighter cap to stay valid on both surfaces.
DESCRIPTION_MAX_CHARS = 1024
NAME_MAX_CHARS = 64  # same Skills API cap family as DESCRIPTION_MAX_CHARS above
# Cap on spec.references' summary field (and spec.lifecycle.experimental/
# deprecated.reason) in metadata/gitapex.yaml -- these free-text fields have
# no length limit otherwise and can grow unbounded by mixing multiple
# distinct events into one string. There is no overflow escape
# valve (e.g. a second file to move detail into): the fix for an
# over-budget entry is to decompose it into one list entry per distinct
# event (see REFERENCES_KIND_VOCAB/REFERENCES_ITEM_SUBKEYS below), each of
# which is short by construction once it stops being fused with its
# siblings.
REFERENCES_ENTRY_MAX_CHARS = 500
# spec.references is a list whose items are themselves mappings -- the one
# field in this sidecar with real nested structure one level *inside* a
# list item, rather than under a scalar key the way spec.skillDependencies/
# spec.lifecycle/spec.executionRequirements all nest. Each item has three
# required scalar fields (kind, anchor, summary) and one optional nested
# mapping (outcome, free-form key/value atoms -- verdict, found, fixed,
# open, ... -- with no closed vocabulary of its own, since real entries use
# too varied a set of outcome facts for a fixed schema to fit).
REFERENCES_ITEM_SUBKEYS = ("kind", "anchor", "summary", "outcome")
REFERENCES_ITEM_REQUIRED_SUBKEYS = ("kind", "anchor", "summary")  # outcome is the one optional subkey
# Exactly 4 spaces -- one level under spec.references' own 2-space key,
# matching every other gated block's own fixed-indent convention.
REFERENCES_ITEM_INDENT = 4
# Closed vocabulary for the "kind" field, derived from the recurring entry
# shapes actually found across every sidecar's spec.references: a
# decision/change record, an audit-round record (a named
# method/dispatch/verdict/finding-count), a deferral to a follow-up issue,
# an external (non-gitapex) corroboration, a portability/worked-example
# caveat, a citation-elision disclosure, or a correction/retraction of an
# earlier entry. Not speculative -- no kind is included that the corpus
# does not already contain an example of.
REFERENCES_KIND_VOCAB = (
    "decision",
    "audit",
    "deferral",
    "corroboration",
    "caveat",
    "elision",
    "correction",
)
# spec.externalCitations (issue #1055): a Portable skill's own opt-in
# declaration that a specific evals/docs/CLAUDE.md-chapter path citation
# names an input source or output destination, not a control dependency --
# see rubric.md's Portability level section for the underlying distinction
# this supplements, not replaces, GENERIC_ROLE_HEDGE_PHRASES for. Each item
# is a flat two-field mapping (no nested "outcome" sub-block, unlike
# spec.references' own items), structurally the simpler of the two list-of-
# mappings fields this sidecar has.
EXTERNAL_CITATION_ITEM_SUBKEYS = ("path", "role")
EXTERNAL_CITATION_ITEM_REQUIRED_SUBKEYS = ("path", "role")  # both subkeys are required; no optional field here
# Exactly 4 spaces, matching REFERENCES_ITEM_INDENT's own convention -- one
# level under spec.externalCitations' own 2-space key.
EXTERNAL_CITATION_ITEM_INDENT = 4
# A repo-external path cited only as an input source (read whatever the
# calling repository has) or an output destination (this skill's own
# result is consumed downstream by X) is not a control dependency -- see
# rubric.md's Portability level section. Closed vocabulary; not
# speculative -- both values are already this repository's own established
# vocabulary from that section's prose.
EXTERNAL_CITATION_ROLES = ("input-source", "output-destination")
# A declared spec.externalCitations path must be rooted at evals/ or docs/,
# the same two prefixes REPO_PATH_CITATION_RE's own evals/docs alternative
# gates -- this mechanism exists to rescue exactly that check's own
# citations, so a path outside both prefixes could never be a real rescue
# target in the first place (code-review finding, issue #1055). Mirrors
# skill-metadata.schema.json's own externalCitationItem.path pattern; kept
# as a separate, hand-duplicated regex here rather than shared, matching
# this module's own established convention for a schema constraint that
# also needs enforcing in this dependency-free parser (see
# EXEC_REQ_NETWORK_SUBKEYS' own comment for the precedent).
EXTERNAL_CITATION_PATH_RE = re.compile(r"^(?:evals|docs)/[A-Za-z0-9._/-]+$")
# "Keep SKILL.md body under 500 lines for optimal performance" (same doc;
# also code.claude.com/docs/en/skills).
BODY_MAX_LINES = 500
# Not an Anthropic-specified number -- this repository's own convention
# for when a reference file earns a table of contents, chosen as a round
# threshold past which skimming a flat file gets slow.
TOC_MIN_LINES = 100
RESERVED_NAME_WORDS = ("anthropic", "claude")  # Anthropic's own reserved skill-name words

# Invocation-control frontmatter. Both fields are Claude Code product
# extensions the Agent Skills standard does not define; both are booleans
# whose accepted literals are documented at code.claude.com/docs/en/skills
# ("Boolean fields accept yes, no, on, off, 1, and 0 in any letter case, in
# addition to true and false"), so the VALUE is lowercased before lookup.
# The KEY is matched case-sensitively and deliberately so: YAML keys are
# case-sensitive and the documented field names are lowercase, so a
# differently-cased "Disable-Model-Invocation" is a different key the
# runtime would not read either -- correctly invisible to this check.
INVOCATION_TRUE_LITERALS = ("true", "yes", "on", "1")
INVOCATION_FALSE_LITERALS = ("false", "no", "off", "0")  # the false half of the same documented vocabulary above
# disable-model-invocation defaults to false (Claude may auto-load);
# user-invocable defaults to true (the skill shows in the / menu). The
# defaults matter here because the pair only fails as a COMBINATION, so an
# absent field still has to resolve to a value.
INVOCATION_FIELD_DEFAULTS = {
    "disable-model-invocation": False,
    "user-invocable": True,
}

# The sidecar is this repository's own metadata convention, not part of the
# Anthropic Agent Skills standard -- hence its own metadata/ subdirectory
# and gitapex-labelled apiVersion. It is never auto-loaded by the skill
# runtime, so it can never change skill behavior.
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"
# Kubernetes-manifest-shaped envelope, borrowed as a convention only; the
# version lets the schema grow without breaking older sidecars.
EXPECTED_API_VERSION = "gitapex.io/v1alpha1"
EXPECTED_KIND = "SkillMetadata"  # the sidecar's fixed manifest kind, alongside EXPECTED_API_VERSION above
PORTABILITY_LEVELS = ("Portable", "Repository-scoped", "Mixed")  # closed vocabulary for spec.portability
CAPABILITY_ASSUMPTIONS = ("Broad", "Frontier", "Adaptive")  # closed vocabulary for spec.capabilityAssumption
DEPENDENCY_POLICY_LEVELS = ("StdlibOnly", "Declared")  # closed vocabulary for spec.dependencyPolicy
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
# spec.executionRequirements.tools.read/write/shell,
# spec.executionRequirements.packages.<ecosystem>) assumes each of its
# items is. Deliberately the common, uncontroversial
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
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
)
# A real YAML comment: an unquoted "#" preceded by start-of-string or
# whitespace -- YAML never treats a "#" glued directly onto a preceding
# non-space character as a comment marker (e.g. "true#tag" is the
# literal string "true#tag", not "true" plus a comment). Used only to
# strip a trailing comment before classifying an unquoted list item's own
# scalar type in _is_non_string_plain_scalar below -- the item's stored
# value is unaffected either way, only the type classification is --
# a comment-bearing item such as "true # rationale" would otherwise defeat
# YAML_NON_STRING_SCALAR_RE's own full-string anchor, silently certifying
# a real YAML boolean/null/numeric as a string whenever it carries a
# trailing comment.
_INLINE_COMMENT_RE = re.compile(r"(?:^|\s)#.*$")


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
# A full GitHub issue/PR URL anchoring the whole string: any owner/repo
# segment (metadata/gitapex.yaml is maintainer-facing provenance for
# whichever repository actually hosts the skill directory at the time --
# this repository today, a different one once vendored -- never something
# a portable skill body depends on), an "issues" or "pull" segment, then a
# digit run. Deliberately a full URL, not a bare "#123"/"owner/repo#123"
# shape: a bare issue number means nothing once this sidecar travels with
# its skill directory to another repository (e.g. plugin vendoring); a
# full URL still resolves to the right place wherever it lands -- but only
# if the owner/repo segment itself is not hardcoded to this repository's
# own name, which would defeat that same vendoring case. Shape-only --
# never resolved against a live GitHub API call, since this checker is
# offline/read-only by design.
LIFECYCLE_ISSUE_REF_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9._-]+/(?:issues|pull)/\d+$"
)

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
# instead of ever reaching unknown-key detection. Matching
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
# ones this regex happens to parse, is the actual fail-closed contract.
KEY_LINE_RE_4 = re.compile(r'^[ ]{4}(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')
KEY_LINE_RE_6 = re.compile(r'^[ ]{6}(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')
# One nesting level deeper than KEY_LINE_RE_6: spec.references' own item
# mappings nest an optional "outcome" sub-mapping (8-space indent, one
# level under the item's own 6-space fields) -- the only field in this
# sidecar three levels deep under spec.
KEY_LINE_RE_8 = re.compile(r'^[ ]{8}(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')
# Matches a spec.references list item's own first field, given inline
# right after its "- " marker (e.g. "kind: decision" from
# "- kind: decision") -- same key-shape alternation as KEY_LINE_RE_4/6, but
# with no anchored leading indent, since the "- " prefix itself already
# consumed a variable amount of the line before this text was isolated.
INLINE_KEY_VALUE_RE = re.compile(r'^(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')

# spec.executionRequirements' two recognized subkeys so far: "tools" and
# "network" (issue #845), each at 4-space indent -- same depth as
# spec.skillDependencies' requires/relatedTo and spec.lifecycle's
# experimental/deprecated/stable. Recognized via the same shared
# KEY_LINE_RE_4 matcher those two fields use, not a field-specific regex --
# for consistency across all three gated blocks.
EXEC_REQ_TOOLS_SUBKEYS = ("read", "write", "shell")
# List items accept 6 or more spaces -- the same indent-drift tolerance
# REFERENCES_LIST_ITEM_RE/SKILL_DEP_LIST_ITEM_RE already give their own
# lists (an item at their own subkey's depth, or deeper). Reused verbatim
# by spec.executionRequirements.network's own domains list below --
# domains sits at the identical 6-space depth tools' own read/write/shell
# lists do, so a second, byte-identical regex would add nothing.
EXEC_REQ_TOOLS_LIST_ITEM_RE = re.compile(r"^[ ]{6,}-\s*(.*)$")

# spec.executionRequirements.network's two recognized subkeys (issue #845,
# resolving the mixed scalar-plus-list shape issue #349 deferred): "mode"
# (a scalar enum) and "domains" (a list), in the SAME sub-block -- unlike
# tools, whose read/write/shell are all list-valued. The parser layer below
# does not judge which subkey should hold a scalar vs. a list; each subkey
# is captured exactly as written (an inline value is stored as a raw
# scalar, a blank value opens a list), the same per-subkey mechanism
# tools' own read/write/shell already use -- type validity (mode must be a
# recognized enum string; domains must be a list) is entirely a
# checker-layer question (_execution_requirements_checks), never a
# parser-layer one. This slice hand-duplicates tools' own state machine
# (in_exec_tools/exec_tools/... -> in_exec_network/exec_network/...) rather
# than extracting a shared generic-subblock helper both could call -- the
# existing tools state machine is threaded through this loop via several
# mutually exclusive `nonlocal` flags, and a real extraction touching that
# already-proven path was judged higher regression risk than the size of
# this slice's own scope justifies. A future mixed-shape category (mcp,
# per issue #349's own deferral) can copy this block's shape directly, but
# still cannot literally reuse it as a function without that extraction --
# stated explicitly here per this issue's own disclosure requirement,
# rather than silently claiming a generalization that was not attempted.
EXEC_REQ_NETWORK_SUBKEYS = ("mode", "domains")
EXEC_REQ_NETWORK_MODES = ("disabled", "allowlist", "unrestricted")  # closed vocabulary for network.mode

# spec.executionRequirements' third recognized block sub-key: "packages" --
# the first whose own subkeys are NOT a fixed, closed tuple the way tools'
# read/write/shell (EXEC_REQ_TOOLS_SUBKEYS) and network's mode/domains
# (EXEC_REQ_NETWORK_SUBKEYS) are. A package ecosystem (pip, npm, cargo, ...)
# is an open-ended set by design -- skill-metadata.schema.json's own
# executionRequirementsPackages deliberately declares no closed enum of
# supported ecosystems, via propertyNames rather than a fixed properties
# list -- so unknown-subkey detection here must be a REGEX match against
# that same pattern, not a tuple-membership check: a future ecosystem
# becomes usable with no parser change, matching the schema's own design
# intent. Kept as a separate, hand-duplicated regex here rather than
# imported from the schema (the same precedent EXTERNAL_CITATION_PATH_RE
# already established for a schema constraint that also needs enforcing in
# this dependency-free, no-YAML-library parser).
EXEC_REQ_PACKAGES_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*$")
# Detects a line that LOOKS like an attempted "- <value>" packages list item
# (a "-" as its first non-whitespace character, tabs included) but whose
# leading whitespace fails EXEC_REQ_TOOLS_LIST_ITEM_RE's own strict "6 or
# more literal SPACE characters" requirement -- a tab anywhere in the
# indent, or fewer than 6 spaces. Used only to distinguish that case from a
# packages ecosystem list genuinely ending (a real dedent, or a new sibling
# ecosystem key) while collecting_exec_packages_list is open: without it, a
# line like "\t- some-package" (or "  - some-package", 2 spaces) silently
# finalizes the list as empty -- indistinguishable from the package truly
# never having been declared -- instead of being recorded into
# malformed_execution_requirement_packages_items the way an item
# EXEC_REQ_TOOLS_LIST_ITEM_RE itself rejects (mapping-shaped, wrong type)
# already is. Cannot collide with a legitimate new KEY_LINE_RE_6 sibling
# key: whenever this matches AND the strict item regex already failed, the
# leading whitespace run is provably not "exactly 6 literal spaces" (either
# shorter, or tab-containing), which KEY_LINE_RE_6 requires verbatim -- so
# the two can never both match the same line. Scoped to packages only, per
# this fix's own issue: tools' and network's own sibling list-item blocks
# (collecting_exec_tools_list/collecting_exec_network_list below) share this
# exact latent gap -- no equivalent fail-closed check exists at their own
# list-item level either, only at the surrounding key level -- and are
# deliberately left as-is here rather than silently duplicating the fix
# beyond this issue's own scope.
EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE = re.compile(r"^[ \t]*-\s*(.*)$")

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
TOC_RE = re.compile(r"^#+\s+(?:table of )?contents\b", re.IGNORECASE | re.MULTILINE)
BLOCK_SCALAR_INDICATORS = (
    ">",
    "|",
    ">-",
    "|-",
    ">+",
    "|+",
)  # YAML block-scalar indicators (folded/literal, chomping variants)
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
RELATED_SKILL_BULLET_RE = re.compile(r"\*\*vs\.\s+.+?:\*\*.*?(?=\n[ \t]*-\s|\n[ \t]*\n|\Z)", re.DOTALL)
BACKTICK_SKILL_NAME_RE = re.compile(r"`([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)`")
# An absolute-URL scheme (http:, https:, mailto:, ftp:, ...) -- anything
# matching this is external, not a same-repo relative path.
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

# Portable self-citation scans (see the module docstring). A skill counts as
# Portable only when its portability marker says "Portable" without the
# "Mixed" / "Repository-scoped" qualifiers -- those levels legitimately cite
# repo-specific paths, so the two repo-path checks below do not apply to
# them. The bare-issue-citation check is different: it runs unconditionally
# on every skill regardless of this classification.
# The near-top body marker, kept only as the fallback declaration form for a
# skill vendored in from another repository that has no sidecar. Skills in
# this repository declare portability in metadata/gitapex.yaml instead.
PORTABILITY_RE = re.compile(r"\bportability\s*:", re.IGNORECASE)
PORTABILITY_MAX_BODY_LINE = 6  # the fallback body marker must appear "near the top", not anywhere in the body
PORTABLE_LEVEL_RE = re.compile(r"\bportable\b", re.IGNORECASE)
NON_PORTABLE_LEVEL_RE = re.compile(r"\b(?:mixed|repository-scoped|repo-scoped)\b", re.IGNORECASE)
# A GitHub issue/PR-number citation: an optional "owner/repo" prefix, then
# "#" and a digit run. The trailing (?![\d-]) rejects an in-page anchor slug
# like "#1-discovery" (a digit run followed by "-word"); a real citation ends
# at the digits.
ISSUE_CITATION_RE = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*)?#\d+(?![\d-])")
# An origin-repository path citation rooted at this repo's own top-level
# tooling dirs. Kept deliberately narrow (evals/ and docs/) -- the two roots
# the historical incidents used -- rather than every path shape, so the scan
# stays a low-false-positive backstop, not a general path linter. The second
# alternative (issue #192, Refs #26 repair 1) catches a bare citation of the
# *calling repository's own instruction-file* chapter/section -- the same
# self-containment defect as an evals/docs path citation (a consumer repo
# vendoring this skill has no such chapter, or a different one), just a
# different citation shape. Three real phrasings are already in use
# elsewhere in this repository ("CLAUDE.md ch.2", "CLAUDE.md chapter 3",
# "CLAUDE.md section 4") -- all three are covered rather than guessing at
# just the one issue #26 happened to quote. The CLAUDE.md alternative is
# scoped case-insensitive via an inline ``(?i:...)`` group (a review
# finding: "CLAUDE.md Chapter 2" or "claude.md section 4" otherwise
# evaded both checks this constant feeds) -- scoped rather than a
# pattern-wide ``re.IGNORECASE``, so the evals/docs alternative, whose
# real targets are always lowercase POSIX paths, keeps its existing
# case-sensitive behavior unchanged.
#
# evals/, docs/, and CLAUDE.md-chapter citations get identical treatment,
# as of issue #1051 -- a corpus incident (rubric.md's own Execution
# requirements section) showed that the *disclosing* half of the old hedge
# vocabulary ("this repository" / "gitapex") lets a hedge phrase disclose a
# repo-path dependency without removing it: the cited file still does not
# travel with a vendored copy of the skill, hedged or not. Earlier
# revisions of this check gave evals/ that same full hedge escape in
# inline-code form while unconditionally banning docs/ -- an asymmetric,
# enumerated exception table that itself reproduced the same class of gap
# (a future third top-level dir would need its own manual entry in that
# table to get the strict treatment). Both prefixes now get identical
# treatment in both the bare-prose form (unconditional, as always -- no
# hedge phrase has ever rescued a bare-prose match) and the inline-code
# form (rescued only by GENERIC_ROLE_HEDGE_PHRASES, the narrow half of the
# old vocabulary that marks a citation as a generic illustrative
# placeholder rather than a real reference to this repository's own file
# -- see that constant's own comment for the full rationale). This mirrors
# the same resolve-inside-the-skill-directory-or-fail rule
# SCRIPTS_PATH_BARE_RE below already applies to scripts/ citations (the
# one prefix that legitimately CAN resolve inside the citing skill's own
# directory, so it gets a resolution check instead of a pattern ban).
REPO_PATH_CITATION_RE = re.compile(
    r"(?:evals|docs)/[A-Za-z0-9._/-]+"
    r"|(?i:CLAUDE\.md\s+(?:ch\.|chapter|section)\s*\d+)"
)
# A bare-prose "scripts/PATH" mention (issue #192, Refs #26 repair 3/#36
# repair 3/#20 item d). Deliberately NOT folded into REPO_PATH_CITATION_RE's
# alternation above: unlike evals/ or docs/, a "scripts/..." path routinely
# DOES legitimately resolve inside the citing skill's own directory (every
# skill's SKILL.md refers to its own bundled script this way -- confirmed
# by a corpus-wide check before adding this pattern), so this citation kind
# needs its own directory-resolution check
# (_out_of_skill_scripts_offenders), not the evals/docs family's
# unconditional-flag-or-hedge treatment. Only the bare-prose form is
# checked here: the Markdown-link form of the identical "must resolve
# inside the skill's own directory" rule is already covered by
# links-inside-skill/_out_of_skill_link_targets above. The leading ``\b``
# (a review finding) keeps this from matching inside an unrelated word
# that merely ends in "scripts" (e.g. "manuscripts/genX.py",
# "postscripts/cleanup.sh") -- unlike REPO_PATH_CITATION_RE's evals/docs
# alternative, which only gates presence and is harmless without one,
# this pattern drives an existence check, so a mid-word false match would
# produce a wrong verdict rather than a merely-imprecise offender string.
SCRIPTS_PATH_BARE_RE = re.compile(r"\bscripts/[A-Za-z0-9._/-]+")
# A real, versioned Claude model identifier: "claude-" plus a known
# model-family word (opus/sonnet/haiku/fable/instant) plus a version-like
# digit, e.g. "claude-sonnet-5", "claude-opus-4.7",
# "claude-haiku-4-5-20251001". Deliberately narrower than
# outward-artifact-preflight/scripts/gitapex_scan_provenance.py's bare
# "claude-[a-z0-9.-]+" match (a different check, scanning outgoing artifact
# text for undisclosed disclosure -- a different false-positive budget):
# requiring a family word immediately after "claude-" excludes this
# repository's own legitimate non-model tokens already in skills/ content
# today, e.g. "claude-code", "claude-plugin", or a descriptive title like
# "claude-fable-finding-your-unknowns" (starts with a family word but has no
# version digit after it) -- none of these name an actual model. A
# placeholder like "claude-example-model" never matches either, since
# "example" is not a recognized family word.
ILLUSTRATIVE_MODEL_ID_RE = re.compile(
    r"\bclaude-(?:opus|sonnet|haiku|fable|instant)-?[0-9][a-z0-9.\-]*\b", re.IGNORECASE
)
# A citation to Anthropic's own documentation, in the exact forms this
# repository's own reference lists use: a GFM autolink
# ("<https://platform.claude.com/...>"), an inline link target, with or
# without CommonMark's optional title
# ("[text](https://code.claude.com/... \"Title\")"), or a reference-style
# link definition ("[label]: https://claude.com/..."). A real, current model
# identifier appearing only inside one of these -- e.g. a doc URL whose own
# slug names the model the page documents -- is a primary-source citation,
# not "illustrative content" in rule 1's sense (a worked example or sample
# value a reader might copy-paste); rule 1's own found-via incident (a
# worked example's flagged "bad" sample) never involved a citation URL.
# Narrowly scoped to the three Anthropic-owned domains this rubric's own
# Stop boundaries already name as primary sources (platform.claude.com,
# code.claude.com) plus claude.com (the blog domain [steering]/[fable]/
# [modeleffort] already cite), so this exemption cannot become a general
# escape hatch for illustrative content wrapped in an arbitrary URL.
ANTHROPIC_DOC_CITATION_RE = re.compile(
    r"<https://(?:platform\.claude\.com|code\.claude\.com|claude\.com)/"
    r"[^\s>]*>"
    r"|\]\(https://(?:platform\.claude\.com|code\.claude\.com|claude\.com)/"
    r"[^)\s]*(?:\s+\"[^\"]*\"|\s+'[^']*')?\)"
    r"|^[ ]{0,3}\[[^\]]+\]:\s*<?https://"
    r"(?:platform\.claude\.com|code\.claude\.com|claude\.com)/[^\s>]*>?",
    re.MULTILINE,
)
# An opening angle-bracket placeholder token in raw prose: "<" then a single
# word of letters/digits/underscore/hyphen (no "/" or ":"), then ">". The
# no-"/"-or-":" restriction means a GFM autolink ("<https://example.com>")
# can never match -- that syntax is already a real, safe Markdown form, not
# the defect this check exists to catch.
RAW_PLACEHOLDER_OPEN_RE = re.compile(r"<([A-Za-z][A-Za-z0-9_-]*)>")
# A run of Markdown "already illustrative / already external" syntax whose
# contents must not be scanned: a fenced code block (``` ... ```), an inline
# code span (`...`), an absolute URL, an inline link ([text](target)), a
# reference-style link ([text][label]), or a reference definition
# ([label]: target). Stripping these leaves only bare prose.
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
# A Markdown inline code span: a run of 1-3 backticks, non-greedy content,
# then a closing run of the SAME length (\1) -- CommonMark's own rule, used
# e.g. when the span's content itself needs to contain a literal backtick
# (` ``a`b`` `). A span using two backticks each side (` ``#42`` `) must be
# read as one citation, not two adjacent empty single-backtick spans --
# otherwise its content is never inspected by either citation check below,
# a silent evasion route, not just a cosmetic gap. Capped at 3 backticks
# (this file already reserves
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
# the module docstring's repo-path citation entry above). Matched case-insensitively as a
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

# The generic-placeholder half of HEDGE_PHRASES only (issue #1051's own
# refinement): "the calling repository" / "the target repository" mark a
# citation as a generic illustrative path name for WHATEVER repository the
# skill lands in or reviews -- not a citation to this origin repository's
# own real file at all, so there is no vendoring-breaks-it dependency to
# disclose in the first place. "this repository" / "gitapex" mark the
# opposite: a deliberate, known-real reference to this repository's own
# file -- exactly the #220 failure shape (a hedge phrase that *discloses* a
# real dependency without *removing* it) issue #1051 closed by making the
# repo-path check unconditional. Only the generic-placeholder half still
# rescues a match here; the real-reference half never did and still does
# not. See the module docstring's repo-path citation entry and rubric.md's
# Portability level section (the control-dependency vs. input-source vs.
# output-destination distinction) for the underlying rationale.
GENERIC_ROLE_HEDGE_PHRASES = (
    "the calling repository",
    "the target repository",
)

# Approved hedge phrases for the inline-code issue/PR-number citation check
# (see the module docstring's issue-number citation entry above). Deliberately a separate,
# narrower list from HEDGE_PHRASES: that list marks a repo-*path* citation as
# a deliberate reference to a real (or explicitly generic) repository; this
# one marks an issue-*number* citation as a rule/syntax illustration rather
# than worked-example bookkeeping -- different questions, so a shared phrase
# list would blur both.
# Deliberately full multi-word phrases, not bare words, matching HEDGE_PHRASES'
# own convention: a bare word such as "anchored" or "citation" is not enough --
# an ordinary sentence like "See the citation in PR `#144` for prior art" or
# "the review is anchored to PR `#88`" contains either bare word while citing
# a real, banned issue number, the exact defect this check exists to catch.
# Full phrases collapse that false-negative surface close to zero without
# adding new mechanism.
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
# rather than a hedge drawn from existing in-repo prose --
# ISSUE_CITATION_RE (`#\d+`) cannot syntactically distinguish a real issue
# number from a decimal-digit-only CSS hex color (`#123456`, `#123`,
# `#000000` are all valid CSS, all also valid GitHub issue-number shapes).
# This repository has no web-design skill yet, but a future
# one documenting a literal color value would hit this false positive with
# no natural way to phrase around it otherwise. Naming the color's own
# nature ("the hex color `#123456`", "this CSS color") is how such a skill
# would phrase it anyway, so the escape hatch costs no awkward wording.
# Reserved in advance of that skill landing, not drawn from existing
# content the way the two phrases above are. Does not replace the deeper,
# still-open fix of context-aware classification instead of
# a hedge word.
ISSUE_CITATION_HEDGE_PHRASES = (
    "must be an anchored",
    "issue/pr-number citation",
    "hex color",
    "css color",
)

# A possessive citation of a named sibling skill -- e.g.
# "`scorer-gated-skill-edits`' own fixture-authoring guidance already
# names X for a pure substring scorer". Matches either
# "`name`'s" (a name not already ending in "s") or the bare-apostrophe
# English possessive "`name`'" (a name that already ends in "s", e.g.
# "scorer-gated-skill-edits'"). ``clause`` captures the text up to the
# next sentence/clause boundary (an approximation, same tolerance this
# file's own _SENTENCE_SPLIT_RE-based tokenizer elsewhere accepts, not a
# full parser) for the caller to search for "already" and an approved
# hedge phrase.
#
# Deliberately narrower than "any backtick-quoted resolving skill name" --
# an unscoped "any resolving citation, no hedge" rule fires on eleven of
# this repository's own already-shipped skills -- the possessive-citation
# shape alone ("`NAME`'s own X") is this repository's single most common,
# entirely benign way to cite a sibling skill's content, used dozens of
# times across nearly every skill. Requiring "already" in the same clause
# reduces that same corpus-wide scan to zero real false positives (three
# residual hits were all inside Repository-scoped/Mixed skills this
# check's own Portable gate already excludes). This narrowness is a
# deliberate, evidence-grounded trade-off, not an oversight: it will not
# catch a differently-worded unhedged fact-claim that never uses the word
# "already".
#
# A trailing ``\b`` word-boundary assertion (the usual way this file marks
# "end of token" elsewhere) does NOT work after the bare-apostrophe form:
# at the position right after a lone ``'`` with no ``s`` following, both
# the apostrophe itself and the whitespace after it are non-word
# characters, so no word/non-word transition exists there for ``\b`` to
# match, and the bare-apostrophe form (a name already ending in "s", e.g.
# "scorer-gated-skill-edits'") would never match at all. A negative
# lookahead for a word character is used instead (matches whitespace,
# punctuation, or end of string, but never a further letter/digit
# continuing the possessive itself) rather than ``(?=\s)`` (requires
# whitespace specifically): a citation immediately followed by
# punctuation before further prose (e.g. "`name`', already noted, ...")
# has a comma, not whitespace, right after the possessive, and
# ``(?=\s)`` would silently never match that either.
PORTABLE_SKILL_FACT_CLAIM_RE = re.compile(
    r"`([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)`'s?(?![A-Za-z0-9])"
    r"(?P<clause>[^.;\n]{0,120})"
)

# Issue #218 (Repair 3) / #1399: a bare demonstrative "this origin
# repository" inside Portable-declared content either dangles or silently
# narrows to the rubric's own host once vendored elsewhere -- the exact
# defect PR #216's own new Dimension 6 bullet shipped and then had to
# correct to "the origin repository" (evals/evaluating-skill-quality/
# split.md's "Iteration: issue #200" entry, Correction item 3). This
# repository's own established convention -- the sibling issue/PR-number-
# citation bullet's lead sentence, and that same correction -- is the
# definite article "the origin repository", never the demonstrative "this
# origin repository".
#
# Deliberately narrower than banning "this repository's own" outright, an
# earlier draft of this check considered per issue #218's own retrospective
# text: that longer phrase is this repository's own single most common way
# to cite itself in disclosure/rationale prose (174 occurrences across
# skills/ at authoring time, all benign -- e.g. rubric.md's own "labelled
# here as this repository's own reasoned extension rather than an
# Anthropic-sourced claim"), and an unscoped ban on it would false-positive
# on nearly every Portable skill in the corpus, the same over-broad-ban
# shape issue #1051 already found and narrowed once for
# GENERIC_ROLE_HEDGE_PHRASES. "this origin repository" carries no such
# legitimate use: "origin" only ever modifies "repository" to mean *this
# specific repository, as opposed to wherever a Portable skill is vendored
# to* -- there is no reading of "this origin repository" that is not the
# demonstrative defect this check exists to catch. No hedge-phrase rescue
# either, for the same reason: unlike a repo-path or issue-number citation,
# which can legitimately disclose a real, deliberate same-repo dependency,
# there is no legitimate reading of this specific demonstrative to hedge.
#
# ``\s+`` between words, not a literal space: this repository's own
# Markdown source is hard-wrapped at roughly 80 columns, so a live
# occurrence of this exact phrase (references/worked-example-self-review.md,
# found while validating this check against the real corpus) lands with an
# actual newline between "origin" and "repository" -- "this origin\n
# repository's tree" -- which a literal-space pattern silently misses
# even though a rendered reader sees one continuous phrase.
DEMONSTRATIVE_ORIGIN_REPOSITORY_RE = re.compile(r"\bthis\s+origin\s+repository\b", re.IGNORECASE)

# Issue #192 (Refs #93 repair 1): a "step N" / "steps N-M" reference,
# case-insensitive (this repo's own SKILL.md files use both "Step 1" and
# "step 5"). Deliberately does not attempt to parse "and"/comma-joined
# multi-step lists (e.g. "Steps 1-2 and 5-7") into every individual number
# they name -- a lower-precision, whole-match extraction is enough for the
# same-number-two-locations contradiction this check exists to catch, and
# a false negative here (an uncaught multi-step list) is far cheaper than
# a hand-rolled list grammar earning its own false positives.
# The \u2013 in the character class below is an EN DASH, written as an escape
# rather than as a literal. The character is load-bearing -- SKILL.md prose
# writes both "Steps 1-2" and "Steps 1\u20132" -- and an escape says so, where a
# literal en dash is visually indistinguishable from the hyphen beside it.
STEP_NUM_RE = re.compile(r"\bsteps?\s+(\d+)(?:\s*[-\u2013]\s*\d+)?\b", re.IGNORECASE)
# A closed, narrow vocabulary of execution-location assertions, grounded in
# the exact wording of the historical incident this check mechanizes
# (issue #93: SKILL.md's Procedure intro said step 6 "stays in the main
# thread" while its Subagent dispatch section required step 6 to "execute
# inside" the dispatch -- an internal contradiction with no location
# explicitly ceding authority to the other). Deliberately not a general
# "location" or "environment" prose linter -- this repo's own real-world
# location-shaped phrasing is otherwise sparse (a corpus-wide check while
# designing this rule found only two hits total, both hedged/unrelated),
# so a broader vocabulary would have no evidence base and a much larger
# false-positive surface. Captures up to 3 further whitespace-separated
# tokens after the verb phrase (deliberately short, not the rest of the
# sentence) so the offender text names WHERE ("the main thread", "the ...
# dispatch") without also absorbing unrelated trailing prose that would
# make two mentions of the exact same location read as "distinct" purely
# because of what was said afterward in one sentence but not the other.
STEP_LOCATION_ASSERTION_RE = re.compile(
    r"\b(?:stays?\s+in|runs?\s+(?:inside|in)|executes?\s+(?:inside|in))"
    r"\b(?:\s+\S+){0,3}",
    re.IGNORECASE,
)
# This repo's own established way (issue #93's own fix commit) of marking
# that one location's statement is authoritative and a second, differently
# located mention of the same step is not a real contradiction -- e.g. "see
# the Subagent dispatch section for the authoritative statement." Matched
# as a case-insensitive substring, the same convention HEDGE_PHRASES and
# ISSUE_CITATION_HEDGE_PHRASES already use.
STEP_LOCATION_CEDING_PHRASE = "authoritative"

# Issue #192 item 4 (Refs #24 repairs 1, 4): a broad, incident-agnostic
# recognition of an untrusted-content declaration, grounded in a survey of
# this repository's own 29 SKILL.md files (16/29 carry some form of this
# declaration), reduced to three lexical roots the real phrasing there
# reduces to: (a) "as untrusted" ("as untrusted data", "as untrusted by
# default", "flags it as untrusted", "treats X as untrusted"); (b) a form
# of treat/treats/treated/treating, or "recorded", paired with "as data"
# ("treat it as data", "treats it as data", "treated as data", "recorded
# as data"); (c) "never execute"/"never follow" applied to embedded
# instructions. Deliberately broad on this side (unlike
# AUTHORITY_VIOLATION_RE below): missing a real declaration only weakens
# this check's own coverage, while missing a real violation would let the
# exact issue #24 repair 1 incident recur silently.
#
# Adversarial review (issue #192 step 8) found the verb alternation
# omitted the 3rd-person-singular present form "treats" -- present, live,
# in this repository's own prose (e.g.
# reviewing-an-artifact/references/security-tier-handling.md: "...exactly
# the class of content untrusted-input-triage already treats as data...").
# A SKILL.md pairing that exact declaration style with a genuine unhedged
# override/narrow-scope violation would have passed this check silently,
# precisely the incident class it exists to catch. Added.
UNTRUSTED_DECLARATION_RE = re.compile(
    r"\bas\s+untrusted\b"
    r"|\b(?:treats?|treated|treating|recorded)\b(?:\s+\S+){0,6}?\s+as\s+data\b"
    r"|\bnever\s+(?:execute|follow)\b",
    re.IGNORECASE,
)
# Issue #192 item 4 (Refs #24 repair 1): the narrow, incident-grounded
# violation pattern -- an authority-granting verb applied to
# already-declared-untrusted content, using #24 repair 1's own incident
# wording verbatim ("any comment could narrow/override the issue body's
# scope"). Deliberately NOT broadened to a wider verb list (apply, adopt,
# follow, ...) -- rejected during this check's own design elicitation as
# an unacceptable false-positive risk from common English words in a
# zero-false-positive-tolerant CI gate.
#
# Both verbs share a required "scope"/"scopes" object (up to 4 intervening
# words, accommodating the incident's own real wording "narrow the issue
# body's scope") -- this requirement was added after a corpus sweep found a
# bare "overrides?" (with no object constraint) false-positives on
# eliciting-a-design/SKILL.md's "A spec location ... overrides this
# default", an unrelated file-path-precedence sentence with no
# authority-over-untrusted-content meaning at all. Per this check's own
# shipping-bar rule (design doc "Scope and shipping bar"), the fix is
# narrowing the violation vocabulary, never a hedge exception around the
# specific false positive.
#
# Adversarial review (issue #192 step 8) found the object was pinned to the
# SINGULAR "scope" only, so "override the declared scopes" -- the identical
# violation, pluralized -- slipped through with the whole check still
# nominally armed. Widened to "scopes?"; the corpus sweep stays at zero
# false positives.
#
# Disclosed residual (structural, not a fixable gap in this vocabulary):
# a violation phrased without the literal word "scope" at all ("override
# the issue body"), or with more than 4 words between verb and object, is
# not matched. That is the deliberate incident-narrow trade-off the design
# doc records above -- widening it is a design change, not a repair.
#
# Adversarial review (issue #192 step 8) found the verb alternation only
# covered the bare/3rd-person-singular forms, missing progressive and past
# tense ("overriding", "overrode", "narrowing", "narrowed") -- the
# identical violation, just conjugated differently. Not yet found live in
# this repository's own corpus (a latent gap, not a currently-manifesting
# false negative), but the same class of incidental omission the "treats"
# fix above closed for the declaration side, so closed here too rather
# than left for a future incident to surface it.
AUTHORITY_VIOLATION_RE = re.compile(
    r"\b(?:overrides?|overriding|overrode|narrows?|narrowing|narrowed)\b(?:\s+\S+){0,4}?\s+scopes?\b",
    re.IGNORECASE,
)
# A negation of AUTHORITY_VIOLATION_RE's own verb, anywhere in the same
# suppression unit (see AUTHORITY_SUPPRESSION_UNIT_SPLIT_RE below),
# suppresses every violation match in that unit -- the exact
# false-positive class a dispatched adversarial review of this check's own
# design doc found already live in this repository:
# untrusted-input-triage/SKILL.md pairs a declaration with "external text
# must never override your trusted instructions," a safe-side statement,
# not a violation. Matched the same simple sentence-substring way
# STEP_LOCATION_CEDING_PHRASE above already is, not a positional window.
#
# Disclosed residual (structural, the same class of ceiling
# scripts/check_task_bash_safety.sh already discloses for its own
# regex-based scan): this is a lexical negation, not a syntactic one, so a
# negation belonging to an unrelated clause of the same sentence ("a
# commenter who is not the reporter may still override the issue body's
# scope") suppresses a genuine violation. Deciding which verb a "not"
# actually negates needs a parser this deliberately LLM-free, regex-based
# checker does not have. The suppression UNIT is bounded as tightly as it
# can be without one -- see AUTHORITY_SUPPRESSION_UNIT_SPLIT_RE below.
AUTHORITY_VIOLATION_NEGATION_RE = re.compile(
    r"\b(?:never|not|won'?t|cannot|can'?t)\b",
    re.IGNORECASE,
)
# A nearby explicit restriction (owner/maintainer-only, or a confirmation
# requirement) also suppresses an AUTHORITY_VIOLATION_RE match in the same
# suppression unit -- the same "ceding" concept STEP_LOCATION_CEDING_PHRASE above
# already uses, applied to this check's own violation side per issue #24
# repair 1's own actual fix ("restricting auto-override to owner/
# maintainer comments; anything else routes through ... ask instead").
#
# Anchored on a LEADING word boundary (not the bare substring test an
# earlier revision used), after adversarial review (issue #192 step 8)
# found the substring form inverted the check's own meaning: "an
# unconfirmed comment may override the issue body's scope" -- a comment
# with NO confirmation requirement, i.e. exactly the defect -- was
# suppressed by "confirm" matching inside "unconfirmed", and "a landowner
# comment ..." by "owner" inside "landowner". A leading \b keeps every
# intended form hedging (owner's/owners, co-maintainer,
# confirms/confirmed/confirmation) while "unconfirmed" and
# "disconfirmation" correctly no longer hedge.
AUTHORITY_VIOLATION_HEDGE_RE = re.compile(
    r"\b(?:owner|maintainer|confirm)",
    re.IGNORECASE,
)
# A Markdown list-item marker starting a new line. The suppression unit for
# AUTHORITY_VIOLATION_NEGATION_RE/AUTHORITY_VIOLATION_HEDGE_RE is a
# sentence, but _SENTENCE_SPLIT_RE only breaks after ".", "!" or "?" -- so
# a run of list items written without terminal punctuation (ordinary in a
# SKILL.md Procedure or Stop-boundaries list) collapses into ONE "sentence",
# and a "Never ..." bullet then silently clears a genuine violation stated
# in a DIFFERENT bullet. That is the file-wide-suppression failure mode the
# check's own docstring says it avoids, reached through the back door
# (adversarial review, issue #192 step 8). Breaking the unit at each new
# list item closes it without breaking a hedge/negation that merely wraps
# across lines inside one prose sentence, which stays in one unit.
AUTHORITY_SUPPRESSION_UNIT_SPLIT_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+\.)[ \t]+", re.MULTILINE)

# Grounded in the exact historical incident this check mechanizes (issue
# #79's PR #75 retrospective, re-scoped by issue #577 after #192 carried the
# original proposal's "every Fail/Pass example needs a backtick" framing
# too far): battle-testing-a-skill's own SKILL.md Procedure requires "quote
# the exact offending line" for every finding, with dimension 14 (a
# regression-corpus check evidenced by inspecting the target's `evals/`
# directory, not a SKILL.md line) named as the one exception. The defect
# #79 found was this exception drifting out of sync across the two files --
# dimension 14's catalog entry was reworded to be structural before
# SKILL.md's own Procedure text was updated to exempt it. This check
# mechanizes exactly that cross-file consistency, not a blanket
# every-example-needs-a-backtick rule: issue #577 found the blanket
# reading would fail CI on roughly 18 of 22 real dimensions in the current,
# already-reviewed adversarial-dimensions.md corpus, none of which make any
# "quote a SKILL.md line" claim in the first place.
#
# Every inter-word gap below is `\s+`, not a literal space -- a review
# finding: battle-testing-a-skill's own real SKILL.md hard-wraps "quote the
# exact offending" and "line" across a line break, so a literal-space
# pattern never matches the exact prose this check exists to read, and the
# whole check silently no-ops (QUOTED_LINE_RULE_RE finds nothing, so
# _dimension_quote_exemption_offenders returns early) rather than actually
# comparing the two files. `\s+` matches across that wrap the same way
# every other multi-word phrase constant in this module already does (e.g.
# STEP_NUM_RE above).
DIMENSION_QUOTE_EXEMPTION_RE = re.compile(
    r"except\s+dimensions?\s+(\d+(?:\s*(?:,|and)\s*\d+)*)",
    re.IGNORECASE,
)
# Presence marks that SKILL.md's Procedure states the blanket "quote a
# line" rule at all -- when absent, there is no blanket rule for a
# references/ catalog's own structural exemption to contradict, so the
# check below is trivially satisfied (the same "not applicable, contributes
# zero offenders" shape _mechanism_fit_citation_offenders already uses for
# a document with no '## Mechanism fit' heading). Deliberately the exact
# phrase battle-testing-a-skill's own SKILL.md uses, not a generic "cites a
# line" linter -- see DIMENSION_QUOTE_EXEMPTION_RE's own comment for why a
# narrow, incident-grounded phrase beats a broader vocabulary with no
# evidence base, and for why every gap below is `\s+`.
QUOTED_LINE_RULE_RE = re.compile(r"quote\s+the\s+exact\s+offending\s+line", re.IGNORECASE)
# A references/ catalog's own numbered dimension section marks itself
# structurally exempt from the quoted-line rule with one of these two
# phrasings -- both drawn verbatim from adversarial-dimensions.md's real
# dimension 14 section (its intro uses the first, its Fail bullet the
# second). Two fixed alternatives, not a paraphrase-matching linter: the
# same narrow, evidence-grounded posture as every other closed-vocabulary
# marker in this module.
CATALOG_QUOTE_EXEMPTION_MARKER_RE = re.compile(
    r"not\s+(?:by\s+)?quoting\s+a\s+line|not\s+a\s+skill\.md\s+line",
    re.IGNORECASE,
)
# A references/ file's own numbered dimension/rubric-item heading, e.g.
# adversarial-dimensions.md's "## 14. Reusable, versioned adversarial
# regression corpus". Matched generically over ANY references/*.md file's
# top-level numbered headings -- not hardcoded to adversarial-dimensions.md
# by filename -- the same generic-over-any-document posture
# _mechanism_fit_citation_offenders already documents for its own heading
# scan.
NUMBERED_CATALOG_HEADING_RE = re.compile(r"^##\s+(\d+)\.\s+.+$", re.MULTILINE)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    rule: str
    evidence: str


# A Markdown ATX heading line: 0-3 leading spaces (CommonMark's own
# indent tolerance, matching REFDEF_RE's identical "[ ]{0,3}" convention
# elsewhere in this file), 1-6 '#', a space/tab, the heading text, then an
# optional CommonMark closing sequence (one or more trailing '#'
# characters, itself preceded by at least one space/tab) and any trailing
# whitespace. The closing sequence must be stripped in the regex itself,
# not left for ANCHOR_SLUG_STRIP_RE to clean up afterward: a trailing
# space before the closing '#'s would otherwise survive stripping and
# become a spurious trailing '-' in the slug ("heading-" instead of
# "heading"). Applied only to fence-blanked text
# (see _heading_slugs) so a heading-shaped line inside a fenced code
# example is never read as a real heading.
HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", re.MULTILINE)
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
# Setext H2 whose "text" is the whole "## Heading" line, hashes included.
SETEXT_HEADING_RE = re.compile(r"^[ ]{0,3}(?!#{1,6}(?:[ \t]|$))(\S.*?)[ \t]*\n[ ]{0,3}(?:=+|-+)[ \t]*$", re.MULTILINE)
# GitHub's own heading-to-anchor slug punctuation strip set -- a denylist
# of specific ASCII punctuation plus two Unicode "General Punctuation"/
# "Supplemental Punctuation" blocks, matching the real github-slugger
# algorithm's own regex, NOT an ASCII allowlist. This denylist form
# preserves Unicode letters/digits (and underscore/hyphen/space) while
# stripping the same fixed punctuation set GitHub's own slugger strips --
# an ASCII-only allowlist would incorrectly also delete non-ASCII Unicode
# letters (e.g. turning "## Café Notes" into "caf-notes" instead of
# GitHub's real "café-notes").
ANCHOR_SLUG_STRIP_RE = re.compile(r"[\u2000-\u206F\u2E00-\u2E7F\\'!\"#$%&()*+,./:;<=>?@\[\]^`{|}~]")


# A cross-skill "file+heading" citation: this repository's own
# established convention for naming a specific sibling skill's reference
# file and heading in prose (e.g. "`evaluating-skill-quality`'s
# `references/adversarial-self-audit.md` Isolation verification section").
# Both the skill
# name and the file path sit in their OWN inline-code span (unlike the
# bare-prose citation checks below, this one is never inline-code-stripped
# first -- the regex depends on the backticks being present), while the
# heading text itself is bare prose ending at the literal word "section".
# Skill-name char class matches BACKTICK_SKILL_NAME_RE's own kebab-case
# shape (same convention _stale_related_skill_references already reads a
# sibling skill name against). A plain ASCII apostrophe before "s",
# matching this repository's own established prose (this repository's own
# skill content uses only plain ASCII apostrophes). The
# heading-text group is deliberately narrow (letters/digits/space/
# apostrophe/slash/hyphen, non-greedy) so it stops at the literal " section"
# boundary rather than running on into the next sentence.
#
# "s?" (not a bare "s") plus a following-character guard, not a plain
# "\s+": a sibling skill directory name that itself already ends in "s"
# (e.g. "scorer-gated-skill-edits") is correctly cited with the bare
# English possessive apostrophe and no trailing "s" -- the same "\b does
# not work here" pitfall PORTABLE_SKILL_FACT_CLAIM_RE's own comment
# documents. Without the same fix, a cross-skill citation naming such a
# sibling in the grammatically-correct bare-apostrophe form would never
# match at all, never flagged as dangling even if broken. The
# following-character guard is a negative lookahead for
# a word character, not a literal "\s+": a possessive immediately followed
# by punctuation before further prose (e.g. a comma) still needs to match.
CROSS_SKILL_CITATION_RE = re.compile(
    r"`([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)`'s?(?![A-Za-z0-9])\s*"
    r"`references/([A-Za-z0-9._-]+\.md)`\s+"
    r"([A-Za-z0-9][A-Za-z0-9 '/-]*?)\s+[Ss]ection\b"
)

# Mechanism-fit subsection completeness: every ATX heading in a
# document, this time captured WITH its own '#'-run (unlike HEADING_RE,
# which only needs a heading's text for anchor-slug purposes and is
# level-agnostic) -- the Mechanism-fit check below needs to tell a level-2
# "## Mechanism fit" heading apart from a level-3 "### " subsection nested
# under it, so it cannot reuse HEADING_RE's own single-capture-group shape.
MECHANISM_FIT_HEADING_RE = re.compile(r"^[ ]{0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", re.MULTILINE)
# A "[label]"-style citation bracket -- this repository's own established
# reference-style-link-label convention (e.g. "[sd]", "[ab]",
# "[modeleffort]"), the same shape a Mechanism-fit subsection already uses
# today wherever it cites a primary source. Presence-only: this check does
# not verify the label resolves to a real "[label]: url" definition
# elsewhere in the document (a distinct, narrower question this check
# does not attempt), only that a subsection carries SOME citation-shaped marker
# rather than none.
MECHANISM_FIT_CITATION_RE = re.compile(r"\[[a-z0-9][a-z0-9-]*\]")
# The literal disclosure phrase this repository's own rubric.md already
# uses (verbatim, twice) to mark a Mechanism-fit claim as its own reasoned
# extension rather than an Anthropic-sourced one.
MECHANISM_FIT_REASONED_EXTENSION_PHRASE = "this repository's own reasoned extension"


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
LINK_TITLE_RE = re.compile(r"""[ \t]+(?:"[^"]*"|'[^']*'|\([^()]*\))[ \t]*$""")


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


# (check-name, citation_re, hedge_phrases, human-readable citation-kind
# label) for each Portable-only inline-code citation check. Table-driven so
# a third citation kind is "add a row", not "copy the block a third time" --
# ``_portable_path_citation_checks`` below builds one ``CheckResult`` per
# row from a single loop instead of a hand-duplicated block per kind. The
# repo-path row uses ``GENERIC_ROLE_HEDGE_PHRASES`` (issue #1051), the
# narrow "the calling repository"/"the target repository" half of
# ``HEDGE_PHRASES`` only -- see that constant's own comment for why: those
# two phrases mark a citation as a generic illustrative path name for
# whatever repository the skill lands in, never a citation to THIS origin
# repository's own real file, so there is nothing to vendor-break in the
# first place. The other half of ``HEDGE_PHRASES`` ("this repository" /
# "gitapex") never rescued a match here even before issue #1051 -- it marks
# the opposite, a deliberate real-file reference, which is exactly the #220
# failure shape (a hedge discloses a real dependency without removing it).
# The issue-number row keeps its own, separate hedge-phrase list unchanged
# -- issue #1051 only revisits the repo-path row's escape, not the
# issue-number citation rule this table also drives.
_INLINE_CITATION_CHECK_SPECS = (
    ("portable-no-inline-path-citation", REPO_PATH_CITATION_RE, GENERIC_ROLE_HEDGE_PHRASES, "origin-repository path"),
    ("portable-no-unhedged-inline-issue-citation", ISSUE_CITATION_RE, ISSUE_CITATION_HEDGE_PHRASES, "issue/PR-number"),
)


# Conventional constant-naming heuristic (no-voodoo-constant, issue #1045
# ACM item A): a bare-uppercase-leading identifier of only letters, digits,
# and underscores. This is the scoping filter that keeps the check from
# flagging an ordinary lowercase/mixed-case variable, or a regex-compiled
# module "constant" like ``NAME_RE = re.compile(...)`` -- that RHS is a
# Call, not a literal, and so is excluded by ``_is_simple_literal_node``
# below regardless of the name matching this pattern.
_ALL_CAPS_CONST_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
