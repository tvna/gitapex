"""Out-of-skill link targets, heading-anchor resolution, and the
sidecar/body portability-fallback consistency check."""

from __future__ import annotations

import os.path
from dataclasses import dataclass
from pathlib import Path

from shape_checks.citations import _blank_fenced_blocks, _dedup
from shape_checks.constants import (
    ANCHOR_SLUG_STRIP_RE,
    BACKTICK_SKILL_NAME_RE,
    HEADING_RE,
    LINK_RE,
    LINK_TITLE_RE,
    NON_PORTABLE_LEVEL_RE,
    PORTABILITY_MAX_BODY_LINE,
    PORTABILITY_RE,
    PORTABLE_LEVEL_RE,
    REFDEF_RE,
    RELATED_SKILL_BULLET_RE,
    SCHEME_RE,
    SETEXT_HEADING_RE,
)


def _body_after_frontmatter(text: str) -> list[str]:
    """Lines after the closing frontmatter '---'. If there is no
    frontmatter, the whole text is the body."""
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    lines = text.splitlines()
    if not text.startswith("---"):
        return lines
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return lines
    return lines[end + 1 :]


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


def _out_of_skill_link_targets(body_text: str, skill_dir: Path, source_dir: Path | None = None) -> list[str]:
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

    ``source_dir`` (default: ``skill_dir`` itself) is the directory a
    relative target is resolved AGAINST -- real relative-link semantics,
    the file-relative rule ``_resolve_anchor_link_file`` already
    established for the anchor-fragment check. For SKILL.md,
    which sits at the skill root, "relative to the containing file" and
    "relative to the skill root" coincide, so the default keeps that call
    site unchanged. A references/*.md file does NOT sit at the skill
    root, though: a relative target written there (e.g. "other.md" meaning
    "references/other.md") must resolve against references/, not the
    skill root, or a same-directory link would be misclassified as
    escaping. The escape-BOUNDARY test itself stays ``skill_dir``
    regardless of ``source_dir`` -- escaping the skill directory is the
    failure this check exists to catch, not escaping references/ alone.
    """
    skill_norm = os.path.normpath(str(skill_dir))
    source_norm = os.path.normpath(str(source_dir if source_dir is not None else skill_dir))
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
        if Path(path_part).is_absolute():
            normalized = os.path.normpath(path_part)
        else:
            normalized = os.path.normpath(Path(source_norm) / path_part)
        if _escapes_skill_dir(normalized, skill_norm):
            offenders.append(target)
    return offenders


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
    "foo-1". This loop instead keeps incrementing the
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


def _resolve_anchor_link_file(raw_path: str, source_dir: Path, skill_norm: str) -> Path | None:
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
    if Path(raw_path).is_absolute():
        resolved = os.path.normpath(raw_path)
    else:
        resolved = os.path.normpath(Path(source_dir) / raw_path)
    if _escapes_skill_dir(resolved, skill_norm):
        return None
    return Path(resolved)


def _cached_target_heading_slugs(path: Path, cache: dict[Path, frozenset[str] | None]) -> frozenset[str] | None:
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
    body_text: str, source_path: Path, skill_dir: Path, cache: dict[Path, frozenset[str] | None]
) -> list[str]:
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
            target = target[: title_match.start()].rstrip()
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


def _is_bare_skill_name(entry: str) -> bool:
    """Whether ``entry`` is shaped like a real skill directory name -- a
    bare path component (no separator, not ".", not "..") -- rather than a
    path that could escape the skills root when joined with "/".
    ``(skill_dir.parent / entry).is_dir()`` does not itself guard against
    pathlib's absolute-operand-replaces-the-left-side behavior
    (``Path("/repo/skills") / "/etc" == Path("/etc")``) or a "../"
    traversal segment, so an entry that is not a bare name must never be
    treated as potentially resolving. Mirrors
    ``.github/scripts/gitapex_scan_skill_metadata_schema.py``'s own
    ``_is_bare_skill_name``; kept as an independent copy rather than a
    shared import because this file is stdlib-only by design (see the
    module docstring) and that module is not (issue #757)."""
    return entry not in ("", ".", "..") and "/" not in entry and "\\" not in entry


def _resolves_to_sibling_skill(name: str, siblings_dir: Path) -> bool:
    """Whether ``name`` names an existing sibling skill directory: a bare
    name (see ``_is_bare_skill_name``) whose ``siblings_dir / name`` also
    contains a real ``SKILL.md`` -- not merely ``.is_dir()``. Without the
    ``SKILL.md`` check, any non-skill directory under ``siblings_dir`` (a
    docs folder, a work-in-progress directory with no ``SKILL.md`` yet, a
    stray build artifact) would incorrectly read as a resolved reference.
    Shared by this checker's four dangling-reference resolve checks
    (related-skill-references-resolve, portable-no-unhedged-skill-fact-claim,
    skill-dependencies-resolve, lifecycle-deprecated-replacement-resolves)
    so the one safety-critical "does this reference resolve" predicate has
    exactly one implementation across the whole package, not four copies
    that could silently diverge. Backports the identical gap fixed in
    ``gitapex_scan_skill_metadata_schema.py``'s own
    ``_resolves_to_sibling_skill`` (issue #757)."""
    return _is_bare_skill_name(name) and (siblings_dir / name / "SKILL.md").is_file()


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
            if not _resolves_to_sibling_skill(name, skill_dir.parent):
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
    returns -- this function's return value never gates it.

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
            if not (PORTABLE_LEVEL_RE.search(line) or NON_PORTABLE_LEVEL_RE.search(line)):
                decl = " ".join(window[i : i + 2])  # level wrapped to next line
            return bool(PORTABLE_LEVEL_RE.search(decl)) and not NON_PORTABLE_LEVEL_RE.search(decl)
    return False
