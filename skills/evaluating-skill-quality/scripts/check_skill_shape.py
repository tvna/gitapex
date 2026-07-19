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
  - metadata sidecar (gitapex_metadata.yaml, next to SKILL.md): present;
    has no malformed top-level lines (manifest-parsable -- a column-0 line
    that is not blank/comment/document-marker and does not match the
    top-level "key:" pattern, e.g. a stray "- invalid mapping entry");
    apiVersion is gitapex.dev/v1alpha1 and kind is SkillMetadata;
    metadata.name equals the skill directory name; spec.portability is one
    of Portable/Repository-scoped/Mixed; spec.capabilityAssumption is one
    of Broad/Frontier/Adaptive; spec.references, if present, is a non-empty
    list of non-empty strings (references-well-formed) -- the only gated
    list field. Other ungated sidecar fields (e.g. spec.skillDependencies,
    spec.evalStatus) ARE parsed into the spec map by _parse_manifest, just
    not gated/checked here; only nested maps and list items under them are
    skipped by the parser, and indented lines are never flagged as
    malformed regardless of shape.
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

Usage:
  python3 check_skill_shape.py <skill-dir-or-SKILL.md>

Exit code: 0 if every check passes, 1 if any check fails, 2 on bad usage or
when no readable SKILL.md is found.
"""
from __future__ import annotations

import argparse
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
# Anthropic Agent Skills standard -- hence the gitapex_ prefix. It is never
# auto-loaded by the skill runtime, so it can never change skill behavior.
SIDECAR_FILENAME = "gitapex_metadata.yaml"
# Kubernetes-manifest-shaped envelope, borrowed as a convention only; the
# version lets the schema grow without breaking older sidecars.
EXPECTED_API_VERSION = "gitapex.dev/v1alpha1"
EXPECTED_KIND = "SkillMetadata"
PORTABILITY_LEVELS = ("Portable", "Repository-scoped", "Mixed")
CAPABILITY_ASSUMPTIONS = ("Broad", "Frontier", "Adaptive")
# A plain "- <value>" list item, indented exactly 4 spaces (2 for the
# parent map's nesting, 2 more for the list marker) -- the only list shape
# this parser understands, and only under spec.references specifically.
REFERENCES_LIST_ITEM_RE = re.compile(r"^[ ]{4}-\s*(.*)$")

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
# this repository declare portability in gitapex_metadata.yaml instead.
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
        return value[1:-1]
    return value


@dataclass(frozen=True)
class ManifestParse:
    """Result of ``_parse_manifest``: the parsed top-level mapping plus any
    malformed top-level lines found alongside it.

    ``malformed_lines`` holds each offending line (trimmed), in file order --
    empty when the sidecar's top-level structure is clean. See
    ``_parse_manifest`` for the exact malformed-line rule.
    """
    root: dict[str, object]
    malformed_lines: list[str]


def _parse_manifest(text: str) -> ManifestParse:
    """Parse the YAML subset the metadata sidecar is specified to use.

    Reads top-level 'key: value' scalars and exactly-two-space-indented
    scalars under a top-level map (metadata:, spec:). One exception:
    spec.references (and only that key, and only directly under spec) is
    read as a flat list of scalar strings, each a "- <value>" line indented
    exactly 4 spaces -- the shape this repository's sidecars use for
    maintainer-facing provenance (see the design spec's Sub-project C).
    Every other nested map or list (e.g. spec.skillDependencies) is still
    deliberately skipped, exactly as before: no other gated field uses
    list/nested structure, and skipping keeps this stdlib-only with no
    YAML dependency. Inline '# comment' text after a value on the same
    line is not stripped -- it is read as part of the value, which is safe
    (fails closed against the expected enum/literal) but is not a
    supported way to annotate a sidecar field.

    A top-level (column-0) line that is not blank, not a '#' comment, not a
    YAML document marker ('---' or '...'), and does not match the top-level
    'key:' pattern is malformed -- e.g. a stray '- invalid mapping entry'
    that real PyYAML would reject with a ParserError. Every such line is
    collected (trimmed) into the returned ``ManifestParse.malformed_lines``,
    so a caller can fail the sidecar even though this permissive parser
    itself does not raise. Indented lines are NEVER considered malformed --
    lines under spec.references are read as list items (see above); every
    other indented line belongs to nested/list structures this parser
    deliberately does not interpret, and flagging them would defeat that
    reserved-field design.
    """
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    root: dict[str, object] = {}
    current: dict[str, object] | None = None
    current_key: str | None = None
    collecting_refs: list[str] | None = None
    malformed: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if collecting_refs is not None:
            item = REFERENCES_LIST_ITEM_RE.match(line)
            if item:
                collecting_refs.append(_unquote(item.group(1).strip()))
                continue
            # Not a list item: the references list ends here. Finalize it
            # and fall through to process this line normally below.
            current["references"] = collecting_refs
            collecting_refs = None
        if line[:1] in (" ", "\t"):
            # Indented: nested/list content this parser does not interpret,
            # except spec.references (handled above once its list starts).
            # Exactly two spaces: a four-space line (a child of a nested
            # map) has a space where this expects a key character, so it
            # will not match and is skipped -- never malformed either way.
            nested = re.match(r"[ ]{2}([A-Za-z0-9_-]+):\s*(.*)$", line)
            if nested and current is not None:
                key, value = nested.group(1), nested.group(2).strip()
                if key == "references" and current_key == "spec" and not value:
                    collecting_refs = []
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
                current_key = None
            else:
                child: dict[str, object] = {}
                root[key] = child
                current = child
                current_key = key
            continue
        malformed.append(line.strip())
    if collecting_refs is not None and current is not None:
        current["references"] = collecting_refs
    return ManifestParse(root=root, malformed_lines=malformed)


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

    - "absent": no ``gitapex_metadata.yaml`` next to SKILL.md. The
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


def _strip_illustrative_spans(body_text: str) -> str:
    """Return ``body_text`` with every span that quotes a token
    illustratively or externally removed, leaving only bare prose.

    Removes fenced code blocks wholesale, then per surviving line strips
    inline code spans, absolute URLs, Markdown inline/reference links, and
    reference definitions. These are exactly the forms in which this repo's
    Portable skills already write an issue number or repo path without it
    resolving live (an inline-code ``#149``, a full URL, a ``[PR #2][pr2]``
    worked-example link), so what remains is a citation sitting unguarded in
    running prose -- the shape the historical incidents took.
    """
    out: list[str] = []
    in_fence = False
    for line in body_text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        if MD_REF_DEF_RE.match(line):
            out.append("")
            continue
        stripped = INLINE_CODE_RE.sub(" ", line)
        stripped = BARE_URL_RE.sub(" ", stripped)
        stripped = MD_INLINE_LINK_RE.sub(" ", stripped)
        stripped = MD_REF_LINK_RE.sub(" ", stripped)
        out.append(stripped)
    return "\n".join(out)


def _portable_citation_offenders(body_text: str) -> tuple[list[str], list[str]]:
    """Return (issue-number, repo-path) bare-prose citations in ``body_text``.

    Applies the illustrative-span strip first, so only citations left
    unguarded in running prose are reported. Order-preserving and
    deduplicated so the evidence string is stable and terse.
    """
    prose = _strip_illustrative_spans(body_text)
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

    sidecar = skill_dir / SIDECAR_FILENAME
    if not sidecar.is_file():
        results.append(CheckResult(
            "metadata-file-present", False,
            f"{SIDECAR_FILENAME} exists next to SKILL.md", "missing"))
        sidecar_portability = SidecarPortability(state="absent")
    else:
        results.append(CheckResult(
            "metadata-file-present", True,
            f"{SIDECAR_FILENAME} exists next to SKILL.md", "present"))
        # Single read+parse site for the sidecar in this module (see the
        # SidecarPortability docstring): a corrupt (non-UTF-8) or otherwise
        # unreadable sidecar must not raise out of check_shape -- it is a
        # shape defect, reported as FAILed checks, not a usage error.
        try:
            parsed = _parse_manifest(sidecar.read_text(encoding="utf-8"))
            manifest: dict[str, object] | None = parsed.root
            malformed_lines = parsed.malformed_lines
            read_error: str | None = None
        except (OSError, UnicodeDecodeError) as exc:
            manifest = None
            malformed_lines = []
            read_error = type(exc).__name__

        if manifest is None:
            evidence = f"unreadable: {read_error}"
            results.append(CheckResult(
                "manifest-parsable", False,
                "gitapex_metadata.yaml has no malformed top-level lines",
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
                "gitapex_metadata.yaml has no malformed top-level lines",
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
            spec = manifest.get("spec")
            spec = spec if isinstance(spec, dict) else {}
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
            if references is None:
                results.append(CheckResult(
                    "references-well-formed", True,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    "not declared (optional)"))
            elif (isinstance(references, list) and references
                  and all(isinstance(r, str) and r.strip() for r in references)):
                results.append(CheckResult(
                    "references-well-formed", True,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    f"{len(references)} entries"))
            else:
                ref_evidence = ("empty list" if references == []
                                else f"not a list of non-empty strings: {references!r}")
                results.append(CheckResult(
                    "references-well-formed", False,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    ref_evidence))
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
    for label, source_text in sources:
        issues, paths = _portable_citation_offenders(source_text)
        issue_hits += [f"{label}:{c}" for c in issues]
        path_hits += [f"{label}:{c}" for c in paths]

    return [
        CheckResult(
            "portable-no-issue-citation", not issue_hits,
            "Portable content has no bare-prose GitHub issue/PR-number citation",
            "none" if not issue_hits else "found: " + ", ".join(issue_hits)),
        CheckResult(
            "portable-no-repo-path-citation", not path_hits,
            "Portable content has no bare-prose origin-repository path citation",
            "none" if not path_hits else "found: " + ", ".join(path_hits)),
    ]


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
