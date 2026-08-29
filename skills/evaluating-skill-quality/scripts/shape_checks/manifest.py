"""The metadata/gitapex.yaml sidecar manifest parser (state-aware,
indentation-driven, stdlib-only -- deliberately not a real YAML parser;
see _parse_manifest's own docstring)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from shape_checks.constants import (
    _INLINE_COMMENT_RE,
    EXEC_REQ_NETWORK_SUBKEYS,
    EXEC_REQ_PACKAGES_KEY_RE,
    EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE,
    EXEC_REQ_TOOLS_LIST_ITEM_RE,
    EXEC_REQ_TOOLS_SUBKEYS,
    EXTERNAL_CITATION_ITEM_INDENT,
    EXTERNAL_CITATION_ITEM_REQUIRED_SUBKEYS,
    EXTERNAL_CITATION_ITEM_SUBKEYS,
    INLINE_KEY_VALUE_RE,
    KEY_LINE_RE_4,
    KEY_LINE_RE_6,
    KEY_LINE_RE_8,
    LIFECYCLE_FIELDS,
    LIFECYCLE_SCALAR_KEYS,
    LIFECYCLE_SUBKEYS,
    REFERENCES_ITEM_INDENT,
    REFERENCES_ITEM_REQUIRED_SUBKEYS,
    REFERENCES_ITEM_SUBKEYS,
    REFERENCES_LIST_ITEM_RE,
    REFERENCES_MAPPING_LIKE_RE,
    SKILL_DEP_LIST_ITEM_RE,
    SKILL_DEPENDENCY_SUBKEYS,
    YAML_NON_STRING_SCALAR_RE,
)
from shape_checks.frontmatter import _match_key_line, _strip_bare_comment, _unquote


def _is_non_string_plain_scalar(raw_text: str) -> bool:
    """Whether an UNQUOTED list item's raw text is a YAML null/boolean/
    numeric scalar rather than a string, comment stripped first the same
    way a real YAML parser would before resolving the item's type.
    Shared by every gated list-of-scalar-strings site (spec.references;
    spec.skillDependencies.requires/relatedTo;
    spec.executionRequirements.tools.read/write/shell;
    spec.executionRequirements.packages.<ecosystem>)."""
    stripped = _INLINE_COMMENT_RE.sub("", raw_text).strip()
    return bool(YAML_NON_STRING_SCALAR_RE.match(stripped))


@dataclass(frozen=True)
class ManifestParse:
    """Result of ``_parse_manifest``: the parsed top-level mapping plus any
    malformed top-level lines found alongside it.

    ``malformed_lines`` holds each offending line (trimmed), in file order --
    empty when the sidecar's top-level structure is clean. See
    ``_parse_manifest`` for the exact malformed-line rule.

    ``malformed_reference_items`` holds each spec.references list item's
    own opening line (trimmed) that could not be read as a well-formed
    item mapping -- an indent inconsistent with the rest of its own list,
    an opening line not shaped like "<key>: <value>" at all (e.g. the
    plain-scalar or pipe-delimited-string shapes this field used before),
    an opening key outside REFERENCES_ITEM_SUBKEYS, or an otherwise
    well-opened item missing one of REFERENCES_ITEM_REQUIRED_SUBKEYS
    (``kind``/``anchor``/``summary``) by the time it closes. Empty when
    every item in every spec.references list parsed cleanly. Unlike
    ``malformed_lines``, these are indented lines; they would otherwise be
    silently skipped by this parser's own "indented lines are never
    malformed" rule, which is why they need this separate, explicit
    channel rather than reusing ``malformed_lines``.

    ``unknown_reference_item_keys`` holds each key found inside an
    otherwise-well-opened spec.references item that is not one of
    REFERENCES_ITEM_SUBKEYS (trimmed line, e.g. "notes: foo") -- the
    item's other recognized fields still parse normally; only the stray
    key itself is flagged, the same asymmetry
    ``unknown_lifecycle_fields``/``unknown_skill_dependency_keys`` already
    use for their own sibling fields.

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
    spec.executionRequirements' equivalents: the first holds each key found directly under
    spec.executionRequirements that is not ``tools``, ``packages``, or
    ``network`` (only three recognized keys exist so far -- further
    categories are deferred to sibling child issues, and any other key
    here is unknown, not reserved space); the second holds each key found
    directly under ``tools`` that is not ``read``, ``write``, or
    ``shell``; the third holds each
    read/write/shell list item that is mapping-shaped or inconsistently
    indented, the same rule ``malformed_reference_items``/
    ``malformed_skill_dependency_items`` use one nesting level shallower.
    All three empty when the field is absent or parsed cleanly.

    ``unknown_execution_requirement_network_keys`` and
    ``malformed_execution_requirement_network_items`` are ``network``'s own
    equivalents to ``unknown_execution_requirement_tools_keys``/
    ``malformed_execution_requirement_tools_items``: the first holds each
    key found directly under ``network`` that is not ``mode`` or
    ``domains``; the second holds each ``domains`` list item that is
    mapping-shaped or inconsistently indented. Both empty when the field
    is absent or parsed cleanly.

    ``unknown_execution_requirement_packages_keys`` and
    ``malformed_execution_requirement_packages_items`` are ``packages``'s
    own equivalents, differing from ``tools``'/``network``'s in HOW both
    are populated: since ``packages``' own subkeys are free-form
    ecosystem identifiers rather than a fixed tuple (see
    EXEC_REQ_PACKAGES_KEY_RE), the first holds each key found directly
    under ``packages`` that does NOT match EXEC_REQ_PACKAGES_KEY_RE's own
    pattern (a regex mismatch, not a tuple-membership miss); the second
    holds each per-ecosystem list item that is mapping-shaped or
    inconsistently indented, the same rule every other malformed-item
    channel above uses, PLUS one packages-only addition
    (EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE, see its own comment): a line
    that looks like an attempted "- <value>" item (a "-" as its first
    non-whitespace character) but whose leading whitespace fails the
    strict list-item regex's own "6 or more literal spaces" requirement
    -- a tab, or fewer than 6 spaces -- is ALSO recorded here rather than
    silently finalizing the list as empty, indistinguishable from the
    package never having been declared at all. tools'/network's own
    sibling list-item blocks do not have this addition; see
    EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE's own comment for why that gap
    is deliberately left as-is there. Both empty when the field is absent
    or parsed cleanly.

    ``malformed_external_citation_items`` and
    ``unknown_external_citation_item_keys`` are spec.externalCitations'
    equivalents to ``malformed_reference_items``/
    ``unknown_reference_item_keys`` (issue #1055): the former holds each
    externalCitations list item's own opening line (trimmed) that could
    not be read as a well-formed item mapping (bad indent, not "<key>:
    <value>" shaped, an opening key outside EXTERNAL_CITATION_ITEM_SUBKEYS,
    or missing ``path``/``role`` by the time it closes); the latter holds
    each key found inside an otherwise-well-opened item that is not
    ``path``/``role``. Both empty when the field is absent or parsed
    cleanly.
    """

    root: dict[str, object]
    malformed_lines: list[str]
    malformed_reference_items: list[str]
    unknown_reference_item_keys: list[str]
    malformed_skill_dependency_items: list[str]
    unknown_skill_dependency_keys: list[str]
    unknown_lifecycle_keys: list[str]
    unknown_lifecycle_fields: list[str]
    unknown_execution_requirement_keys: list[str]
    unknown_execution_requirement_tools_keys: list[str]
    malformed_execution_requirement_tools_items: list[str]
    unknown_execution_requirement_packages_keys: list[str]
    malformed_execution_requirement_packages_items: list[str]
    unknown_execution_requirement_network_keys: list[str]
    malformed_execution_requirement_network_items: list[str]
    malformed_external_citation_items: list[str]
    unknown_external_citation_item_keys: list[str]


@dataclass
class _ParseState:
    """Mutable working state threaded through ``_parse_manifest``'s own
    per-line dispatch helpers below -- issue #1330 ACM row 2's own
    decomposition of what used to be one large function's local/nonlocal
    variables. Pure rename: every field here is a straight carry-over of a
    former local, same name, same initial value, same mutation sites (now
    spelled ``state.x`` instead of a bare/``nonlocal`` ``x``) -- no
    detection-logic change. See each per-line handler function below for
    the actual parsing behavior; this class only carries the state between
    them, mirroring what ``_parse_manifest``'s own closures already shared
    via Python's normal enclosing-scope capture before this split.
    """

    root: dict[str, object] = field(default_factory=dict)
    current: dict[str, object] | None = None
    collecting_refs: list[dict[str, object]] | None = None
    # The spec.references item mapping currently being read (between its
    # own "- <key>: <value>" opening line and either the next item, a
    # dedent, or end of file); None between items. current_ref_item_valid
    # goes False the moment the item's own opening line or any of its
    # fields turns out malformed, so the item is excluded at finalization
    # even though its now-known-garbage lines are still consumed here
    # (not left to desync the references list's own end-of-block
    # detection). current_ref_open_line is the item's own opening line
    # (trimmed), kept only for evidence messages.
    current_ref_item: dict[str, object] | None = None
    current_ref_item_valid: bool = True
    current_ref_open_line: str = ""
    # Non-None while inside that item's own optional "outcome:" nested
    # mapping (one level deeper still -- see KEY_LINE_RE_8).
    current_ref_outcome: dict[str, object] | None = None
    malformed: list[str] = field(default_factory=list)
    malformed_refs: list[str] = field(default_factory=list)
    unknown_ref_item_keys: list[str] = field(default_factory=list)
    # spec.externalCitations' own state, structurally parallel to
    # spec.references' above but simpler -- each item is a flat two-field
    # mapping (path/role) with no nested "outcome" sub-block.
    collecting_ext_citations: list[dict[str, object]] | None = None
    current_ext_citation_item: dict[str, object] | None = None
    current_ext_citation_item_valid: bool = True
    current_ext_citation_open_line: str = ""
    malformed_ext_citations: list[str] = field(default_factory=list)
    unknown_ext_citation_item_keys: list[str] = field(default_factory=list)
    in_skill_deps: bool = False
    skill_deps: dict[str, object] = field(default_factory=dict)
    # Whether spec.skillDependencies has seen at least one real child line
    # (a recognized or unknown key) since it was opened -- distinguishes a
    # block header left with nothing under it (real YAML null) from one
    # that genuinely has content, however malformed.
    # Mirrored by lifecycle_has_content/lifecycle_subkey_has_content/
    # exec_req_has_content/exec_tools_has_content below, one per gated
    # mapping block.
    skill_deps_has_content: bool = False
    collecting_dep_list: list[str] | None = None
    collecting_dep_key: str | None = None
    dep_list_indent: int | None = None
    malformed_deps: list[str] = field(default_factory=list)
    unknown_dep_keys: list[str] = field(default_factory=list)
    in_lifecycle: bool = False
    lifecycle: dict[str, object] = field(default_factory=dict)
    lifecycle_has_content: bool = False
    lifecycle_subkey: str | None = None
    lifecycle_field_buffer: dict[str, object] = field(default_factory=dict)
    lifecycle_subkey_has_content: bool = False
    unknown_lifecycle_keys: list[str] = field(default_factory=list)
    unknown_lifecycle_fields: list[str] = field(default_factory=list)
    # Set when a scalar-only lifecycle key (currently only renamedFrom) is
    # seen with a blank/comment-only value -- deferred one line, since that
    # shape is ambiguous until the next line is known: it is either a
    # legitimately absent declaration (next line dedents or is a sibling),
    # or the start of a wrongly block-shaped value (next line is more
    # deeply indented than spec.lifecycle's own 4-space level). See
    # ``_handle_lifecycle_scalar_pending_line`` below.
    lifecycle_scalar_pending: str | None = None
    in_execution_requirements: bool = False
    execution_requirements: dict[str, object] = field(default_factory=dict)
    exec_req_has_content: bool = False
    in_exec_tools: bool = False
    exec_tools: dict[str, object] = field(default_factory=dict)
    exec_tools_has_content: bool = False
    collecting_exec_tools_list: list[str] | None = None
    collecting_exec_tools_key: str | None = None
    exec_tools_list_indent: int | None = None
    malformed_exec_tools_items: list[str] = field(default_factory=list)
    unknown_exec_req_keys: list[str] = field(default_factory=list)
    unknown_exec_tools_keys: list[str] = field(default_factory=list)
    # packages' own state, structurally parallel to exec_tools' above (see
    # EXEC_REQ_NETWORK_SUBKEYS' own comment for why this is a hand-
    # duplicated analog rather than a shared helper -- a third parallel
    # block here rather than an extraction, same precedent, same
    # regression-risk-vs-scope tradeoff). Unlike exec_tools/exec_network,
    # unknown_exec_packages_keys is populated by a REGEX mismatch
    # (EXEC_REQ_PACKAGES_KEY_RE), not a tuple-membership miss -- see
    # ``_handle_exec_packages_line`` below.
    in_exec_packages: bool = False
    exec_packages: dict[str, object] = field(default_factory=dict)
    exec_packages_has_content: bool = False
    collecting_exec_packages_list: list[str] | None = None
    collecting_exec_packages_key: str | None = None
    exec_packages_list_indent: int | None = None
    malformed_exec_packages_items: list[str] = field(default_factory=list)
    unknown_exec_packages_keys: list[str] = field(default_factory=list)
    # network's own state, structurally parallel to exec_tools' above (see
    # EXEC_REQ_NETWORK_SUBKEYS' own comment for why this is a hand-
    # duplicated analog rather than a shared helper).
    in_exec_network: bool = False
    exec_network: dict[str, object] = field(default_factory=dict)
    exec_network_has_content: bool = False
    collecting_exec_network_list: list[str] | None = None
    collecting_exec_network_key: str | None = None
    exec_network_list_indent: int | None = None
    malformed_exec_network_items: list[str] = field(default_factory=list)
    unknown_exec_network_keys: list[str] = field(default_factory=list)


def _finalize_ref_outcome(state: _ParseState) -> None:
    if state.current_ref_outcome is not None and state.current_ref_item is not None:
        state.current_ref_item["outcome"] = state.current_ref_outcome if state.current_ref_outcome else None
    state.current_ref_outcome = None


def _finalize_current_ref_item(state: _ParseState) -> None:
    _finalize_ref_outcome(state)
    if state.current_ref_item is not None:
        missing = [k for k in REFERENCES_ITEM_REQUIRED_SUBKEYS if k not in state.current_ref_item]
        if state.current_ref_item_valid and missing:
            joined = ", ".join(missing)
            state.malformed_refs.append(f"{state.current_ref_open_line} (missing required field(s): {joined})")
        elif state.current_ref_item_valid and state.collecting_refs is not None:
            state.collecting_refs.append(state.current_ref_item)
    state.current_ref_item = None
    state.current_ref_item_valid = True
    state.current_ref_open_line = ""


def _finalize_refs(state: _ParseState) -> None:
    _finalize_current_ref_item(state)
    if state.collecting_refs is not None and state.current is not None:
        state.current["references"] = state.collecting_refs
    state.collecting_refs = None


def _finalize_current_ext_citation_item(state: _ParseState) -> None:
    if state.current_ext_citation_item is not None:
        missing = [k for k in EXTERNAL_CITATION_ITEM_REQUIRED_SUBKEYS if k not in state.current_ext_citation_item]
        if state.current_ext_citation_item_valid and missing:
            joined = ", ".join(missing)
            state.malformed_ext_citations.append(
                f"{state.current_ext_citation_open_line} (missing required field(s): {joined})"
            )
        elif state.current_ext_citation_item_valid and state.collecting_ext_citations is not None:
            state.collecting_ext_citations.append(state.current_ext_citation_item)
    state.current_ext_citation_item = None
    state.current_ext_citation_item_valid = True
    state.current_ext_citation_open_line = ""


def _finalize_ext_citations(state: _ParseState) -> None:
    _finalize_current_ext_citation_item(state)
    if state.collecting_ext_citations is not None and state.current is not None:
        state.current["externalCitations"] = state.collecting_ext_citations
    state.collecting_ext_citations = None


def _finalize_dep_list(state: _ParseState) -> None:
    if state.collecting_dep_list is not None and state.collecting_dep_key is not None:
        state.skill_deps[state.collecting_dep_key] = state.collecting_dep_list
    state.collecting_dep_list = None
    state.collecting_dep_key = None
    state.dep_list_indent = None


def _finalize_skill_deps(state: _ParseState) -> None:
    _finalize_dep_list(state)
    if state.in_skill_deps and state.current is not None:
        # A block header with zero real children ever seen is real
        # YAML null, not an empty-but-present mapping.
        state.current["skillDependencies"] = state.skill_deps if state.skill_deps_has_content else None
    state.in_skill_deps = False
    state.skill_deps = {}
    state.skill_deps_has_content = False


def _finalize_lifecycle_subkey(state: _ParseState) -> None:
    if state.lifecycle_subkey is not None:
        state.lifecycle[state.lifecycle_subkey] = (
            state.lifecycle_field_buffer if state.lifecycle_subkey_has_content else None
        )
    state.lifecycle_subkey = None
    state.lifecycle_field_buffer = {}
    state.lifecycle_subkey_has_content = False


def _finalize_lifecycle(state: _ParseState) -> None:
    _finalize_lifecycle_subkey(state)
    if state.in_lifecycle and state.current is not None:
        state.current["lifecycle"] = state.lifecycle if state.lifecycle_has_content else None
    state.in_lifecycle = False
    state.lifecycle = {}
    state.lifecycle_has_content = False


def _finalize_exec_tools_list(state: _ParseState) -> None:
    if state.collecting_exec_tools_list is not None and state.collecting_exec_tools_key is not None:
        state.exec_tools[state.collecting_exec_tools_key] = state.collecting_exec_tools_list
    state.collecting_exec_tools_list = None
    state.collecting_exec_tools_key = None
    state.exec_tools_list_indent = None


def _finalize_exec_tools(state: _ParseState) -> None:
    _finalize_exec_tools_list(state)
    if state.in_exec_tools:
        state.execution_requirements["tools"] = state.exec_tools if state.exec_tools_has_content else None
    state.in_exec_tools = False
    state.exec_tools = {}
    state.exec_tools_has_content = False


def _finalize_exec_packages_list(state: _ParseState) -> None:
    if state.collecting_exec_packages_list is not None and state.collecting_exec_packages_key is not None:
        state.exec_packages[state.collecting_exec_packages_key] = state.collecting_exec_packages_list
    state.collecting_exec_packages_list = None
    state.collecting_exec_packages_key = None
    state.exec_packages_list_indent = None


def _finalize_exec_packages(state: _ParseState) -> None:
    _finalize_exec_packages_list(state)
    if state.in_exec_packages:
        state.execution_requirements["packages"] = state.exec_packages if state.exec_packages_has_content else None
    state.in_exec_packages = False
    state.exec_packages = {}
    state.exec_packages_has_content = False


def _finalize_exec_network_list(state: _ParseState) -> None:
    if state.collecting_exec_network_list is not None and state.collecting_exec_network_key is not None:
        state.exec_network[state.collecting_exec_network_key] = state.collecting_exec_network_list
    state.collecting_exec_network_list = None
    state.collecting_exec_network_key = None
    state.exec_network_list_indent = None


def _finalize_exec_network(state: _ParseState) -> None:
    _finalize_exec_network_list(state)
    if state.in_exec_network:
        state.execution_requirements["network"] = state.exec_network if state.exec_network_has_content else None
    state.in_exec_network = False
    state.exec_network = {}
    state.exec_network_has_content = False


def _finalize_execution_requirements(state: _ParseState) -> None:
    _finalize_exec_tools(state)
    _finalize_exec_packages(state)
    _finalize_exec_network(state)
    if state.in_execution_requirements and state.current is not None:
        state.current["executionRequirements"] = state.execution_requirements if state.exec_req_has_content else None
    state.in_execution_requirements = False
    state.execution_requirements = {}
    state.exec_req_has_content = False


def _handle_references_line(line: str, state: _ParseState) -> bool:
    """The ``collecting_refs is not None`` branch of ``_parse_manifest``'s
    per-line dispatch, verbatim. Returns True where the original loop hit
    ``continue`` for this line; False where it fell through (after calling
    ``_finalize_refs``) to the next gated block's own check on the same
    line."""
    item = REFERENCES_LIST_ITEM_RE.match(line)
    if item:
        # A new "- <key>: <value>" item marker always closes
        # whatever item (and its own outcome sub-block, if open)
        # came before it.
        _finalize_current_ref_item(state)
        item_indent = len(line) - len(line.lstrip(" "))
        raw_text = item.group(1).strip()
        opened = _match_key_line(INLINE_KEY_VALUE_RE, raw_text)
        state.current_ref_open_line = line.strip()
        if item_indent != REFERENCES_ITEM_INDENT or opened is None or opened[0] not in REFERENCES_ITEM_SUBKEYS:
            # Wrong indent (exactly 4 spaces required -- one level
            # under spec.references' own 2-space key, matching
            # every other gated block's own fixed-indent
            # convention, not the old bare-scalar-list design's
            # "2 or more spaces" tolerance), not a "key: value"
            # shape at all (the old pipe-string/bare-scalar shape
            # this field used before, or other garbage), or an
            # unrecognized first
            # key -- flag the whole item rather than silently
            # misreading it. Still track it as "an item is open"
            # so its own (now-known-garbage) continuation lines
            # are consumed here instead of desyncing this block's
            # own end-of-list detection.
            state.malformed_refs.append(line.strip())
            state.current_ref_item = {}
            state.current_ref_item_valid = False
        else:
            key, value = opened
            state.current_ref_item = {}
            state.current_ref_item_valid = True
            if value:
                state.current_ref_item[key] = _unquote(value)
        return True
    if state.current_ref_outcome is not None:
        matched = _match_key_line(KEY_LINE_RE_8, line)
        if matched:
            key, value = matched
            if value:
                state.current_ref_outcome[key] = _unquote(value)
            return True
        indent = len(line) - len(line.lstrip(" "))
        if line[:1] in (" ", "\t") and indent >= 8:
            # Same fail-closed reasoning as every other gated
            # block's own equivalent branch: an unmatched line at
            # outcome's own indent invalidates the item rather
            # than being silently tolerated or misread.
            state.current_ref_item_valid = False
            return True
        # Not more deeply indented: outcome's own block ends here.
        # Finalize it and fall through to re-check this same line
        # against the item's own 6-space fields below.
        _finalize_ref_outcome(state)
    if state.current_ref_item is not None:
        matched = _match_key_line(KEY_LINE_RE_6, line)
        if matched:
            key, value = matched
            value = _strip_bare_comment(value)
            if key not in REFERENCES_ITEM_SUBKEYS:
                state.unknown_ref_item_keys.append(line.strip())
            elif key == "outcome" and not value:
                state.current_ref_outcome = {}
            elif value:
                state.current_ref_item[key] = _unquote(value)
            return True
        indent = len(line) - len(line.lstrip(" "))
        if line[:1] in (" ", "\t") and indent >= 6:
            # Same fail-closed reasoning as every other gated
            # block's own equivalent branch.
            state.current_ref_item_valid = False
            state.unknown_ref_item_keys.append(line.strip())
            return True
    # Neither a new item marker nor a continuation of the current
    # one: the references list ends here (there is no legitimate
    # content under spec.references besides its own items).
    # Finalize it and fall through to process this line normally
    # below.
    _finalize_refs(state)
    return False


def _handle_external_citations_line(line: str, state: _ParseState) -> bool:
    """The ``collecting_ext_citations is not None`` branch, verbatim --
    same True/False contract as ``_handle_references_line`` above."""
    item = REFERENCES_LIST_ITEM_RE.match(line)
    if item:
        # A new "- <key>: <value>" item marker always closes
        # whatever item came before it -- same rule as
        # spec.references' own items above.
        _finalize_current_ext_citation_item(state)
        item_indent = len(line) - len(line.lstrip(" "))
        raw_text = item.group(1).strip()
        opened = _match_key_line(INLINE_KEY_VALUE_RE, raw_text)
        state.current_ext_citation_open_line = line.strip()
        if (
            item_indent != EXTERNAL_CITATION_ITEM_INDENT
            or opened is None
            or opened[0] not in EXTERNAL_CITATION_ITEM_SUBKEYS
        ):
            state.malformed_ext_citations.append(line.strip())
            state.current_ext_citation_item = {}
            state.current_ext_citation_item_valid = False
        else:
            key, value = opened
            state.current_ext_citation_item = {}
            state.current_ext_citation_item_valid = True
            if value:
                state.current_ext_citation_item[key] = _unquote(value)
        return True
    if state.current_ext_citation_item is not None:
        matched = _match_key_line(KEY_LINE_RE_6, line)
        if matched:
            key, value = matched
            value = _strip_bare_comment(value)
            if key not in EXTERNAL_CITATION_ITEM_SUBKEYS:
                state.unknown_ext_citation_item_keys.append(line.strip())
            elif value:
                state.current_ext_citation_item[key] = _unquote(value)
            return True
        indent = len(line) - len(line.lstrip(" "))
        if line[:1] in (" ", "\t") and indent >= 6:
            # Same fail-closed reasoning as spec.references' own
            # equivalent branch.
            state.current_ext_citation_item_valid = False
            state.unknown_ext_citation_item_keys.append(line.strip())
            return True
    # Neither a new item marker nor a continuation of the current
    # one: the externalCitations list ends here. Finalize it and
    # fall through to process this line normally below.
    _finalize_ext_citations(state)
    return False


def _handle_dep_list_line(line: str, state: _ParseState) -> bool:
    """The ``collecting_dep_list is not None`` branch, verbatim."""
    item = SKILL_DEP_LIST_ITEM_RE.match(line)
    if item:
        item_indent = len(line) - len(line.lstrip(" "))
        if state.dep_list_indent is None:
            state.dep_list_indent = item_indent
        if item_indent != state.dep_list_indent:
            state.malformed_deps.append(line.strip())
            return True
        raw_text = item.group(1).strip()
        is_quoted = len(raw_text) >= 2 and raw_text[0] == raw_text[-1] and raw_text[0] in "\"'"
        if (not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text)) or (
            not is_quoted and _is_non_string_plain_scalar(raw_text)
        ):
            state.malformed_deps.append(line.strip())
        else:
            if state.collecting_dep_list is None:
                # Unreachable: this function is only ever entered (see
                # _parse_manifest's own gate) while collecting_dep_list is
                # open. Narrows the type for mypy without a bare `assert`
                # (S101) -- same fail-loud contract, still a real branch.
                raise AssertionError("dep list handler entered without an open dep list")
            state.collecting_dep_list.append(_unquote(raw_text))
        return True
    # Not a list item: this requires/relatedTo list ends here.
    _finalize_dep_list(state)
    return False


def _handle_skill_deps_line(line: str, state: _ParseState) -> bool:
    """The ``in_skill_deps`` branch, verbatim."""
    matched = _match_key_line(KEY_LINE_RE_4, line)
    if matched:
        state.skill_deps_has_content = True
        key, value = matched
        # A value that is NOTHING BUT a comment (e.g. "requires:
        # # comment") must read as blank/absent, not as the
        # literal comment text -- otherwise it neither opens the
        # list nor equals "[]" and is instead stored as a raw,
        # wrong-type scalar.
        value = _strip_bare_comment(value)
        if key not in SKILL_DEPENDENCY_SUBKEYS:
            state.unknown_dep_keys.append(line.strip())
        elif value == "[]":
            state.skill_deps[key] = []
        elif not value:
            state.collecting_dep_list = []
            state.collecting_dep_key = key
            state.dep_list_indent = None
        else:
            # Not an empty list and not "[]" -- this narrow parser
            # has no flow-sequence support; store the raw scalar so
            # the shape gate can fail it as the wrong type rather
            # than silently dropping it.
            state.skill_deps[key] = value
        return True
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
        # is the actual fail-closed contract.
        state.skill_deps_has_content = True
        state.unknown_dep_keys.append(line.strip())
        return True
    # Dedented below the block's own indent: skillDependencies ends
    # here. Finalize it and fall through to process this line
    # normally below.
    _finalize_skill_deps(state)
    return False


def _handle_lifecycle_subkey_line(line: str, state: _ParseState) -> bool:
    """The ``lifecycle_subkey is not None`` branch, verbatim."""
    matched = _match_key_line(KEY_LINE_RE_6, line)
    if matched:
        state.lifecycle_subkey_has_content = True
        key, value = matched
        value = _strip_bare_comment(value)
        if state.lifecycle_subkey is None:
            # Unreachable: this function is only ever entered (see
            # _parse_manifest's own gate) while lifecycle_subkey is set.
            # Narrows the type for mypy without a bare `assert` (S101).
            raise AssertionError("lifecycle subkey handler entered without an open subkey")
        if key in LIFECYCLE_FIELDS.get(state.lifecycle_subkey, ()):
            if value:
                state.lifecycle_field_buffer[key] = _unquote(value)
        else:
            state.unknown_lifecycle_fields.append(line.strip())
        return True
    indent = len(line) - len(line.lstrip(" "))
    if line[:1] in (" ", "\t") and indent >= 6:
        # Same fail-closed reasoning as spec.skillDependencies'
        # equivalent branch above -- an unmatched line at this
        # indent (including one KEY_LINE_RE_6 cannot parse due to
        # quoting/escaping) is flagged, not silently tolerated.
        state.lifecycle_subkey_has_content = True
        state.unknown_lifecycle_fields.append(line.strip())
        return True
    # Dedented below the sub-block's own indent: this
    # experimental/deprecated block ends here. Finalize it and
    # fall through to process this line normally below (it may be
    # the other sub-block's header, or a dedent out of lifecycle
    # entirely).
    _finalize_lifecycle_subkey(state)
    return False


def _handle_lifecycle_scalar_pending_line(line: str, state: _ParseState) -> bool:
    """The ``lifecycle_scalar_pending is not None`` branch, verbatim."""
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
        if state.lifecycle_scalar_pending is None:
            # Unreachable: this function is only ever entered (see
            # _parse_manifest's own gate) while lifecycle_scalar_pending is
            # set. Narrows the type for mypy without a bare `assert` (S101).
            raise AssertionError("lifecycle scalar-pending handler entered with nothing pending")
        state.lifecycle[state.lifecycle_scalar_pending] = {}
        state.lifecycle_scalar_pending = None
        return True
    # Not more deeply indented: the key really was declared blank
    # (or comment-only) with nothing following -- matches this
    # parser's "blank scalar assignment means not declared"
    # convention. Fall through to process the current line
    # normally below.
    state.lifecycle_scalar_pending = None
    return False


def _handle_lifecycle_line(line: str, state: _ParseState) -> bool:
    """The ``in_lifecycle`` branch, verbatim."""
    matched = _match_key_line(KEY_LINE_RE_4, line)
    if matched:
        state.lifecycle_has_content = True
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
                state.lifecycle[key] = value
            else:
                state.lifecycle_subkey = key
                state.lifecycle_field_buffer = {}
        elif key in LIFECYCLE_SCALAR_KEYS:
            if value:
                state.lifecycle[key] = _unquote(value)
            else:
                # Blank (or comment-only) value: ambiguous until the
                # next line is seen -- see
                # ``_handle_lifecycle_scalar_pending_line`` above.
                state.lifecycle_scalar_pending = key
        else:
            state.unknown_lifecycle_keys.append(line.strip())
        return True
    indent = len(line) - len(line.lstrip(" "))
    if line[:1] in (" ", "\t") and indent >= 4:
        # Same fail-closed reasoning as spec.skillDependencies'
        # equivalent branch above.
        state.lifecycle_has_content = True
        state.unknown_lifecycle_keys.append(line.strip())
        return True
    # Dedented below spec.lifecycle's own indent: the block ends
    # here. Finalize it and fall through to process this line
    # normally below.
    _finalize_lifecycle(state)
    return False


def _handle_exec_tools_list_line(line: str, state: _ParseState) -> bool:
    """The ``collecting_exec_tools_list is not None`` branch, verbatim."""
    item = EXEC_REQ_TOOLS_LIST_ITEM_RE.match(line)
    if item:
        item_indent = len(line) - len(line.lstrip(" "))
        if state.exec_tools_list_indent is None:
            state.exec_tools_list_indent = item_indent
        if item_indent != state.exec_tools_list_indent:
            # Same list, different indent than its own first item --
            # real YAML would reject this outright.
            state.malformed_exec_tools_items.append(line.strip())
            return True
        raw_text = item.group(1).strip()
        is_quoted = len(raw_text) >= 2 and raw_text[0] == raw_text[-1] and raw_text[0] in "\"'"
        if (not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text)) or (
            not is_quoted and _is_non_string_plain_scalar(raw_text)
        ):
            state.malformed_exec_tools_items.append(line.strip())
        else:
            if state.collecting_exec_tools_list is None:
                # Unreachable: this function is only ever entered (see
                # _parse_manifest's own gate) while collecting_exec_tools_list
                # is open. Narrows the type for mypy without a bare `assert`
                # (S101) -- same fail-loud contract, still a real branch.
                raise AssertionError("exec tools list handler entered without an open list")
            state.collecting_exec_tools_list.append(_unquote(raw_text))
        return True
    # Not a list item: this read/write/shell list ends here.
    _finalize_exec_tools_list(state)
    return False


def _handle_exec_tools_line(line: str, state: _ParseState) -> bool:
    """The ``in_exec_tools`` branch, verbatim."""
    matched = _match_key_line(KEY_LINE_RE_6, line)
    if matched:
        state.exec_tools_has_content = True
        key, value = matched
        # Same comment-only-value fix as spec.skillDependencies'
        # equivalent branch above (e.g. "read:  # comment").
        value = _strip_bare_comment(value)
        if key not in EXEC_REQ_TOOLS_SUBKEYS:
            state.unknown_exec_tools_keys.append(line.strip())
        elif value == "[]":
            state.exec_tools[key] = []
        elif not value:
            state.collecting_exec_tools_list = []
            state.collecting_exec_tools_key = key
            state.exec_tools_list_indent = None
        else:
            # Not an empty list and not "[]" -- no flow-sequence
            # support; store the raw scalar so the shape gate can
            # fail it as the wrong type rather than silently
            # dropping it, exactly as spec.skillDependencies does.
            state.exec_tools[key] = value
        return True
    indent = len(line) - len(line.lstrip(" "))
    if line[:1] in (" ", "\t") and indent >= 6:
        # Same fail-closed reasoning as spec.skillDependencies'/
        # spec.lifecycle's equivalent branches -- an unmatched
        # line at this indent is flagged, not silently tolerated.
        state.exec_tools_has_content = True
        state.unknown_exec_tools_keys.append(line.strip())
        return True
    # Dedented below tools' own indent: the block ends here.
    # Finalize it and fall through to process this line normally
    # below.
    _finalize_exec_tools(state)
    return False


def _handle_exec_packages_list_line(line: str, state: _ParseState) -> bool:
    """The ``collecting_exec_packages_list is not None`` branch,
    verbatim."""
    item = EXEC_REQ_TOOLS_LIST_ITEM_RE.match(line)
    if item:
        item_indent = len(line) - len(line.lstrip(" "))
        if state.exec_packages_list_indent is None:
            state.exec_packages_list_indent = item_indent
        if item_indent != state.exec_packages_list_indent:
            # Same list, different indent than its own first item --
            # real YAML would reject this outright.
            state.malformed_exec_packages_items.append(line.strip())
            return True
        raw_text = item.group(1).strip()
        is_quoted = len(raw_text) >= 2 and raw_text[0] == raw_text[-1] and raw_text[0] in "\"'"
        if not is_quoted:
            # A trailing "# comment" on an otherwise-valid item
            # (e.g. "- requests  # transitively needed") must not
            # become part of the stored package name. Real YAML's
            # own comment rule -- an unquoted "#" preceded by
            # start-of-string or whitespace -- is exactly what
            # _INLINE_COMMENT_RE already encodes for
            # _is_non_string_plain_scalar's own type-classification
            # use below; that stripped copy was never fed back into
            # the STORED value before this fix, so a trailing
            # comment silently became part of the parsed package
            # name and then failed the allowlist check with
            # nothing pointing at the comment as the actual
            # problem. Gated on is_quoted the same way
            # REFERENCES_MAPPING_LIKE_RE/_is_non_string_plain_scalar
            # below already are -- a quoted item's own "#" is never
            # a real comment marker, so stripping must not touch
            # it. Scoped to packages only, per this fix's own
            # issue: tools'/network's own sibling item-storage
            # sites below share this same "stored value keeps a
            # trailing comment" gap and are deliberately left as-is
            # here.
            raw_text = _INLINE_COMMENT_RE.sub("", raw_text).strip()
        if (not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text)) or (
            not is_quoted and _is_non_string_plain_scalar(raw_text)
        ):
            state.malformed_exec_packages_items.append(line.strip())
        else:
            if state.collecting_exec_packages_list is None:
                # Unreachable: this function is only ever entered (see
                # _parse_manifest's own gate) while
                # collecting_exec_packages_list is open. Narrows the type
                # for mypy without a bare `assert` (S101).
                raise AssertionError("exec packages list handler entered without an open list")
            state.collecting_exec_packages_list.append(_unquote(raw_text))
        return True
    if (
        line[:1] in (" ", "\t")
        and line.strip() not in ("---", "...")
        and EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE.match(line)
    ):
        # Looks like an attempted list item that the strict regex
        # above rejected on indentation alone (a tab, or fewer
        # than 6 spaces) -- see
        # EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE's own comment. A
        # real YAML parser (and a human reading the file) would
        # still see a declared package here, so this must fail
        # loudly as a malformed item like any other malformed
        # packages entry, rather than silently finalizing the list
        # as empty -- indistinguishable from the package never
        # having been declared at all.
        #
        # The line[:1] guard (found live by an independent
        # adversarial review) is required because
        # EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE's own leading
        # "[ \t]*" is zero-or-more, deliberately looser than
        # EXEC_REQ_TOOLS_LIST_ITEM_RE's own "{6,}" -- exactly the
        # width this branch needs to catch an under-indented item
        # (the bug the comment above already describes), but that
        # same width also matches a column-0 "---"/"..." YAML
        # document marker (both start with "-") and a bare
        # column-0 "- stray" line, neither of which is an
        # attempted list item at all. Excluding both here lets
        # them fall through to their own correct handling instead
        # (the document-marker skip below, or the generic
        # top-level malformed-line catch-all) rather than being
        # misreported as a malformed *packages* item and spuriously
        # failing a sidecar whose packages list is actually
        # well-formed. A real, indented-but-under-6-spaces item
        # (the tab/two-space regression fixtures this branch
        # already has) always starts with a space or tab, so this
        # guard does not narrow the original fix's own coverage.
        state.malformed_exec_packages_items.append(line.strip())
        return True
    # Not a list item: this per-ecosystem package-name list ends here.
    _finalize_exec_packages_list(state)
    return False


def _handle_exec_packages_line(line: str, state: _ParseState) -> bool:
    """The ``in_exec_packages`` branch, verbatim."""
    matched = _match_key_line(KEY_LINE_RE_6, line)
    if matched:
        state.exec_packages_has_content = True
        key, value = matched
        # Same comment-only-value fix as tools'/network's own
        # equivalent branches above (e.g. "pip:  # comment").
        value = _strip_bare_comment(value)
        # REGEX match, not tuple membership -- packages' own
        # subkeys are free-form ecosystem identifiers
        # (EXEC_REQ_PACKAGES_KEY_RE), unlike tools'/network's own
        # fixed EXEC_REQ_TOOLS_SUBKEYS/EXEC_REQ_NETWORK_SUBKEYS
        # tuples (see EXEC_REQ_PACKAGES_KEY_RE's own comment).
        # fullmatch(), not match(): Python's trailing "$" (unlike
        # JSON Schema's own ECMA-262 "$", which EXEC_REQ_PACKAGES_KEY_RE
        # is hand-duplicated from -- see its own comment) also
        # matches immediately before a trailing "\n", which
        # match() would silently accept. key can never actually
        # carry a "\n" here (every line is rstrip()-ped before
        # this point in the parsing loop), so this is defense in
        # depth against unintended reuse of this pattern with
        # unstripped input, not a reachable bug today. Deliberately
        # NOT rewritten to "\Z" in the regex source itself: that
        # would desync EXEC_REQ_PACKAGES_KEY_RE.pattern from
        # skill-metadata.schema.json's own propertyNames.pattern,
        # which test_execution_requirement_packages_key_pattern_matches_schema
        # asserts stay byte-identical -- and "\Z" is not a valid
        # ECMA-262 escape, so mirroring it into the JSON Schema
        # file would break every real downstream JSON-Schema
        # validator that consumes it. fullmatch() gets the same
        # exact-end semantics without touching the shared pattern
        # text.
        if not EXEC_REQ_PACKAGES_KEY_RE.fullmatch(key):
            state.unknown_exec_packages_keys.append(line.strip())
        elif value == "[]":
            state.exec_packages[key] = []
        elif not value:
            state.collecting_exec_packages_list = []
            state.collecting_exec_packages_key = key
            state.exec_packages_list_indent = None
        else:
            # Not an empty list and not "[]" -- no flow-sequence
            # support; store the raw scalar so the shape gate can
            # fail it as the wrong type rather than silently
            # dropping it, exactly as tools'/network's own
            # equivalent branches do.
            state.exec_packages[key] = value
        return True
    indent = len(line) - len(line.lstrip(" "))
    if line[:1] in (" ", "\t") and indent >= 6:
        # Same fail-closed reasoning as tools'/network's own
        # equivalent branches -- an unmatched line at this indent
        # is flagged, not silently tolerated.
        state.exec_packages_has_content = True
        state.unknown_exec_packages_keys.append(line.strip())
        return True
    # Dedented below packages' own indent: the block ends here.
    # Finalize it and fall through to process this line normally
    # below.
    _finalize_exec_packages(state)
    return False


def _handle_exec_network_list_line(line: str, state: _ParseState) -> bool:
    """The ``collecting_exec_network_list is not None`` branch,
    verbatim."""
    item = EXEC_REQ_TOOLS_LIST_ITEM_RE.match(line)
    if item:
        item_indent = len(line) - len(line.lstrip(" "))
        if state.exec_network_list_indent is None:
            state.exec_network_list_indent = item_indent
        if item_indent != state.exec_network_list_indent:
            # Same list, different indent than its own first item --
            # real YAML would reject this outright.
            state.malformed_exec_network_items.append(line.strip())
            return True
        raw_text = item.group(1).strip()
        is_quoted = len(raw_text) >= 2 and raw_text[0] == raw_text[-1] and raw_text[0] in "\"'"
        if (not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text)) or (
            not is_quoted and _is_non_string_plain_scalar(raw_text)
        ):
            state.malformed_exec_network_items.append(line.strip())
        else:
            if state.collecting_exec_network_list is None:
                # Unreachable: this function is only ever entered (see
                # _parse_manifest's own gate) while
                # collecting_exec_network_list is open. Narrows the type
                # for mypy without a bare `assert` (S101).
                raise AssertionError("exec network list handler entered without an open list")
            state.collecting_exec_network_list.append(_unquote(raw_text))
        return True
    # Not a list item: this domains list ends here.
    _finalize_exec_network_list(state)
    return False


def _handle_exec_network_line(line: str, state: _ParseState) -> bool:
    """The ``in_exec_network`` branch, verbatim."""
    matched = _match_key_line(KEY_LINE_RE_6, line)
    if matched:
        state.exec_network_has_content = True
        key, value = matched
        # Same comment-only-value fix as tools' equivalent branch
        # above (e.g. "domains:  # comment").
        value = _strip_bare_comment(value)
        if key not in EXEC_REQ_NETWORK_SUBKEYS:
            state.unknown_exec_network_keys.append(line.strip())
        elif value == "[]":
            state.exec_network[key] = []
        elif not value:
            # Blank value: opens a list for "domains" (its normal,
            # valid case) or, for "mode", wrongly opens a list
            # where a scalar is expected -- the parser stores
            # either the same way and leaves that judgment to
            # _execution_requirements_checks, per this block's own
            # module-docstring note above.
            state.collecting_exec_network_list = []
            state.collecting_exec_network_key = key
            state.exec_network_list_indent = None
        else:
            # Not an empty list and not "[]" -- store the raw
            # scalar. This is "mode"'s own normal, valid case
            # (e.g. "mode: disabled"); for "domains", an inline
            # scalar here is the wrong type, caught downstream the
            # same way tools' own list-only subkeys already are.
            state.exec_network[key] = value
        return True
    indent = len(line) - len(line.lstrip(" "))
    if line[:1] in (" ", "\t") and indent >= 6:
        # Same fail-closed reasoning as tools'/spec.skillDependencies'/
        # spec.lifecycle's equivalent branches.
        state.exec_network_has_content = True
        state.unknown_exec_network_keys.append(line.strip())
        return True
    # Dedented below network's own indent: the block ends here.
    # Finalize it and fall through to process this line normally
    # below.
    _finalize_exec_network(state)
    return False


def _handle_execution_requirements_line(line: str, state: _ParseState) -> bool:
    """The ``in_execution_requirements`` branch, verbatim."""
    matched = _match_key_line(KEY_LINE_RE_4, line)
    if matched:
        state.exec_req_has_content = True
        key, value = matched
        # Same comment-only-value fix as spec.skillDependencies'
        # equivalent branch above (e.g. "tools:  # comment").
        value = _strip_bare_comment(value)
        if key not in ("tools", "packages", "network"):
            state.unknown_exec_req_keys.append(line.strip())
        elif value:
            # Not opening a block -- a bare scalar written where a
            # mapping is expected (e.g. "tools: true"). Store the
            # raw scalar so the checker layer reports it as the
            # wrong type rather than silently dropping it.
            state.execution_requirements[key] = value
        elif key == "tools":
            state.in_exec_tools = True
            state.exec_tools = {}
        elif key == "packages":
            state.in_exec_packages = True
            state.exec_packages = {}
        else:
            state.in_exec_network = True
            state.exec_network = {}
        return True
    indent = len(line) - len(line.lstrip(" "))
    if line[:1] in (" ", "\t") and indent >= 4:
        # Same fail-closed reasoning as spec.skillDependencies'/
        # spec.lifecycle's equivalent branches.
        state.exec_req_has_content = True
        state.unknown_exec_req_keys.append(line.strip())
        return True
    # Dedented below spec.executionRequirements' own indent: the
    # block ends here. Finalize it and fall through to process
    # this line normally below.
    _finalize_execution_requirements(state)
    return False


def _handle_indented_line(line: str, state: _ParseState) -> None:
    """The ``line[:1] in (" ", "\\t")`` branch of ``_parse_manifest``'s
    per-line dispatch, verbatim -- always consumes the line (the caller
    always ``continue``s after calling this), covering the five gated-
    block-opening keys plus the ``dependencyPolicy``/generic-scalar cases
    directly under ``spec:``."""
    # Indented: nested/list content this parser does not interpret,
    # except spec.references and spec.skillDependencies (handled
    # above once each starts). Exactly two spaces: a four-space
    # line (a child of a nested map) has a space where this
    # expects a key character, so it will not match and is
    # skipped -- never malformed either way.
    nested = re.match(r"[ ]{2}([A-Za-z0-9_-]+):\s*(.*)$", line)
    if nested and state.current is not None:
        key, value = nested.group(1), nested.group(2).strip()
        # A value that is NOTHING BUT a comment (e.g.
        # "executionRequirements:  # not yet fully specified")
        # must read as blank, the same way a real YAML parser
        # reads it -- otherwise `not value` is False, none of
        # these four gated blocks ever opens, and the entire
        # nested block underneath is discarded as a raw,
        # wrong-type scalar string instead.
        value = _strip_bare_comment(value)
        # state.current is state.root["spec"] by identity exactly
        # while inside the spec: block, so this is "are we directly
        # under spec" without tracking a separate current-top-key
        # variable.
        if key == "references" and state.current is state.root.get("spec") and not value:
            state.collecting_refs = []
        elif key == "externalCitations" and state.current is state.root.get("spec") and not value:
            state.collecting_ext_citations = []
        elif key == "skillDependencies" and state.current is state.root.get("spec") and not value:
            state.in_skill_deps = True
            state.skill_deps = {}
        elif key == "lifecycle" and state.current is state.root.get("spec") and not value:
            state.in_lifecycle = True
            state.lifecycle = {}
        elif key == "executionRequirements" and state.current is state.root.get("spec") and not value:
            state.in_execution_requirements = True
            state.execution_requirements = {}
        elif key == "dependencyPolicy" and state.current is state.root.get("spec") and not value:
            # dependencyPolicy is a closed-vocabulary scalar, not a
            # block key like the four above -- but it still needs its
            # own explicit branch: dependency-policy-declared is the
            # first check in this checker to treat "spec.get(key) is
            # None" as "absent, therefore fine" for an *optional*
            # field (contrast with the reserved, silently-ignored
            # spec.evalStatus, see
            # test_manifest_parser_still_ignores_eval_status).
            # Falling through here would leave a bare
            # "dependencyPolicy:" (or one followed by list/mapping
            # content this parser does not interpret at this key's
            # own indent) completely unregistered, indistinguishable
            # from the key never having been written at all --
            # dependency-policy-declared would then silently PASS a
            # present-and-malformed declaration as if it were
            # absent. Registering it as an empty string keeps it
            # distinct from real absence while still failing the
            # DEPENDENCY_POLICY_LEVELS membership check (empty
            # string is not StdlibOnly/Declared).
            state.current[key] = ""
        elif value:
            state.current[key] = _unquote(value)


def _handle_root_level_line(line: str, state: _ParseState) -> None:
    """The final ``_parse_manifest`` per-line stage, verbatim: reached
    only for a column-0, non-indented line that no gated block above
    consumed. Skips a YAML document marker, records a recognized
    ``key: value`` pair at the root, or -- if neither -- records the line
    as malformed."""
    if line.strip() in ("---", "..."):
        return
    top = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", line)
    if top:
        key, value = top.group(1), top.group(2).strip()
        if value:
            state.root[key] = _unquote(value)
            state.current = None
        else:
            child: dict[str, object] = {}
            state.root[key] = child
            state.current = child
        return
    state.malformed.append(line.strip())


def _parse_manifest(text: str) -> ManifestParse:
    """Parse the YAML subset the metadata sidecar is specified to use.

    Reads top-level 'key: value' scalars and exactly-two-space-indented
    scalars under a top-level map (metadata:, spec:). Two exceptions:

    - spec.references (and only that key, and only directly under spec) is
      read as a list whose items are themselves mappings -- one
      maintainer-facing provenance event each (see the design spec's
      Sub-project C and its issue #488 follow-up). Each item opens with a
      "- <key>: <value>" line (its first field given inline right after
      the dash) at exactly 4-space indent, with further recognized fields
      as "<key>: <value>" continuation lines at exactly 6-space indent --
      one level deeper, matching every other gated block's own indent-
      doubling convention. Recognized keys: ``kind`` (required, a closed
      vocabulary -- REFERENCES_KIND_VOCAB), ``anchor`` (required, the
      provenance source), ``summary`` (required, free prose), and
      ``outcome`` (optional, itself an empty-value key opening a further
      nested mapping of free-form key/value atoms at 8-space indent --
      KEY_LINE_RE_8 -- with no closed vocabulary of its own). A key inside
      an item other than these four is collected into
      ``ManifestParse.unknown_reference_item_keys`` instead of being
      silently skipped, the same reasoning
      ``unknown_skill_dependency_keys`` documents below; an item whose own
      opening line is not "<key>: <value>" shaped at all, opens with an
      unrecognized key, is indented inconsistently with the rest of its
      own list, or is missing one of the three required keys by the time
      it closes is collected (its opening line, trimmed) into
      ``ManifestParse.malformed_reference_items`` and excluded from the
      parsed list entirely, rather than kept as a partial or garbled item.
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
      ``_handle_lifecycle_scalar_pending_line`` above) and stored
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
    - spec.executionRequirements' second recognized block sub-key (issue
      #845): ``network``, structurally parallel to ``tools`` above -- also
      an empty value opening a nested block at 6-space indent, also
      finalizing to real YAML null when its own header sees zero child
      key lines. Its own two subkeys, ``mode``/``domains``, are each
      captured the identical way tools' own read/write/shell are: an
      inline non-blank value is stored as a raw scalar (``mode``'s normal,
      valid case: ``mode: disabled``); a blank value opens a list of
      "- <value>" items at 6-or-more-space indent, reusing
      ``EXEC_REQ_TOOLS_LIST_ITEM_RE`` verbatim (``domains``'s normal, valid
      case). The parser draws no distinction between the two subkeys --
      whether a stored value is the "right" shape for its own key (mode as
      a scalar, domains as a list) is left entirely to
      ``_execution_requirements_checks``, exactly as it already is for
      tools' own three list-only subkeys. A key inside ``network`` other
      than ``mode``/``domains`` is collected into
      ``ManifestParse.unknown_execution_requirement_network_keys``; a
      malformed ``domains`` list item is collected into
      ``ManifestParse.malformed_execution_requirement_network_items``.
    - spec.executionRequirements' third recognized block sub-key:
      ``packages``, also an empty value opening a nested block at 6-space
      indent, also finalizing to real YAML null when its own header sees
      zero child key lines -- but unlike ``tools``' fixed
      read/write/shell and ``network``'s fixed mode/domains, ``packages``'
      own subkeys are free-form ecosystem identifiers (``pip``, ``npm``,
      ...) matching ``EXEC_REQ_PACKAGES_KEY_RE``, not a closed tuple,
      mirroring skill-metadata.schema.json's own
      executionRequirementsPackages.propertyNames pattern (no closed enum
      of supported ecosystems, so a future ecosystem needs no parser
      change to become recognized). Each ecosystem key matching that
      pattern is captured the same way tools' own read/write/shell are:
      an inline non-blank value is stored as a raw scalar (the wrong
      shape for a package list, caught downstream by
      ``_execution_requirements_checks``); a blank value opens a list of
      "- <value>" items at 6-or-more-space indent, reusing
      ``EXEC_REQ_TOOLS_LIST_ITEM_RE`` verbatim (the same depth-reuse
      ``domains`` above already established -- an ecosystem key sits at
      the identical 6-space depth tools' own read/write/shell and
      network's mode/domains do). A key under ``packages`` NOT matching
      ``EXEC_REQ_PACKAGES_KEY_RE`` is collected into
      ``ManifestParse.unknown_execution_requirement_packages_keys``
      instead of being silently skipped; a malformed per-ecosystem list
      item is collected into
      ``ManifestParse.malformed_execution_requirement_packages_items``.

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
    malformed channels, though the two fields' own item shapes differ
    (references' own items are mappings; skillDependencies.requires/
    relatedTo's are still plain scalar strings): a spec.references item
    not shaped like "<key>: <value>" at all, indented inconsistently with
    the rest of its own list, opening with an unrecognized key, or missing
    a required field by the time it closes is collected (its opening
    line, trimmed) into ``ManifestParse.malformed_reference_items`` (see
    this field's own fuller description above); a
    spec.skillDependencies.requires/relatedTo item shaped like an
    unquoted YAML mapping key ("path: foo", real YAML would read that as
    a nested mapping, not the scalar string this list still expects), one
    indented inconsistently with the rest of its own list, or an unquoted
    null/boolean/numeric scalar (issue #356: real YAML resolves e.g.
    "true"/"123"/"null" to that type, not a string) is collected the same
    way into ``ManifestParse.malformed_skill_dependency_items`` -- both
    instead of being silently accepted as a garbled or wrongly-typed
    value.

    Every gated *mapping*-valued block (spec.skillDependencies,
    spec.lifecycle and its experimental/deprecated/stable sub-blocks,
    spec.executionRequirements, spec.executionRequirements.tools,
    spec.executionRequirements.network) stores
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
    (requires/relatedTo, tools.read/write/shell, network.domains) are NOT
    affected by this change -- a blank list header still parses to ``[]``, per each
    field's own pre-existing "explicit empty list" semantics.

    Issue #1330 ACM row 2: the per-line dispatch body itself is
    decomposed into the ``_handle_*``/``_finalize_*`` module-level
    functions above, one per gated block, threaded through the shared
    ``_ParseState`` -- pure structural extraction (this docstring, the
    resulting ``ManifestParse``, and every parsing decision are otherwise
    unchanged). Each gate below (``if state.X and _handle_X_line(line,
    state): continue``) mirrors the original inline block's own gate
    check plus its own trailing ``continue``.
    """
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    state = _ParseState()

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if state.collecting_refs is not None and _handle_references_line(line, state):
            continue
        if state.collecting_ext_citations is not None and _handle_external_citations_line(line, state):
            continue
        if state.collecting_dep_list is not None and _handle_dep_list_line(line, state):
            continue
        if state.in_skill_deps and _handle_skill_deps_line(line, state):
            continue
        if state.lifecycle_subkey is not None and _handle_lifecycle_subkey_line(line, state):
            continue
        if state.lifecycle_scalar_pending is not None and _handle_lifecycle_scalar_pending_line(line, state):
            continue
        if state.in_lifecycle and _handle_lifecycle_line(line, state):
            continue
        if state.collecting_exec_tools_list is not None and _handle_exec_tools_list_line(line, state):
            continue
        if state.in_exec_tools and _handle_exec_tools_line(line, state):
            continue
        if state.collecting_exec_packages_list is not None and _handle_exec_packages_list_line(line, state):
            continue
        if state.in_exec_packages and _handle_exec_packages_line(line, state):
            continue
        if state.collecting_exec_network_list is not None and _handle_exec_network_list_line(line, state):
            continue
        if state.in_exec_network and _handle_exec_network_line(line, state):
            continue
        if state.in_execution_requirements and _handle_execution_requirements_line(line, state):
            continue
        if line[:1] in (" ", "\t"):
            _handle_indented_line(line, state)
            continue
        _handle_root_level_line(line, state)

    _finalize_refs(state)
    _finalize_ext_citations(state)
    _finalize_skill_deps(state)
    _finalize_lifecycle(state)
    _finalize_execution_requirements(state)
    return ManifestParse(
        root=state.root,
        malformed_lines=state.malformed,
        malformed_reference_items=state.malformed_refs,
        unknown_reference_item_keys=state.unknown_ref_item_keys,
        malformed_skill_dependency_items=state.malformed_deps,
        unknown_skill_dependency_keys=state.unknown_dep_keys,
        unknown_lifecycle_keys=state.unknown_lifecycle_keys,
        unknown_lifecycle_fields=state.unknown_lifecycle_fields,
        unknown_execution_requirement_keys=state.unknown_exec_req_keys,
        unknown_execution_requirement_tools_keys=state.unknown_exec_tools_keys,
        malformed_execution_requirement_tools_items=state.malformed_exec_tools_items,
        unknown_execution_requirement_packages_keys=state.unknown_exec_packages_keys,
        malformed_execution_requirement_packages_items=state.malformed_exec_packages_items,
        unknown_execution_requirement_network_keys=state.unknown_exec_network_keys,
        malformed_execution_requirement_network_items=state.malformed_exec_network_items,
        malformed_external_citation_items=state.malformed_ext_citations,
        unknown_external_citation_item_keys=state.unknown_ext_citation_item_keys,
    )


def spec_of(parsed: ManifestParse) -> dict[str, object] | None:
    """Return ``parsed.root["spec"]`` if present and a mapping, else None.

    A malformed sidecar can write ``spec:`` as a scalar or list rather than
    a mapping; every consumer that only cares about "does this sidecar have
    a real spec mapping" needs the same isinstance guard around
    ``root.get("spec")``; sharing this guard avoids the pattern regressing
    independently at each call site. Callers outside this module (e.g.
    tests/test_gitapex_skill_metadata_sidecar.py) should use this instead of
    inlining ``parsed.root.get("spec")`` themselves.
    """
    spec = parsed.root.get("spec")
    return spec if isinstance(spec, dict) else None
