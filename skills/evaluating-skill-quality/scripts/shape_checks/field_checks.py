"""Single-field CheckResult builders (description/name/references-grammar/
invocation-mode) plus the read-scope/path-resolution helpers check_shape()
itself relies on."""

from __future__ import annotations

import os.path
from pathlib import Path

from shape_checks.constants import (
    INVOCATION_FALSE_LITERALS,
    INVOCATION_FIELD_DEFAULTS,
    INVOCATION_TRUE_LITERALS,
    REFERENCES_KIND_VOCAB,
    TAG_RE,
    UNSAFE_COLON_RE,
    UNSAFE_COMMENT_RE,
    CheckResult,
)


def _no_xml_check(field: str, value: str) -> CheckResult:
    has_tag = bool(TAG_RE.search(value))
    return CheckResult(
        f"{field}-no-xml", not has_tag, f"{field} has no XML tags", "tag found" if has_tag else "no tags"
    )


def _length_check(field: str, value: str, limit: int) -> CheckResult:
    return CheckResult(f"{field}-length", len(value) <= limit, f"{field} <= {limit} chars", f"{len(value)} chars")


def _yaml_plain_scalar_safety_check(field: str, value: str, is_plain_scalar: bool) -> CheckResult:
    rule = (
        f"{field} (an unquoted YAML plain scalar) has no ': ', trailing "
        "':', or ' #'/leading '#' that would break or silently "
        "truncate under a real YAML parser"
    )
    if not is_plain_scalar:
        # A quoted or block-scalar (>/|) value is already safe under a real
        # YAML parser regardless of what characters it contains -- the
        # hazard this check exists for is specific to the unquoted plain
        # scalar form (the one every SKILL.md in this repository currently
        # uses), so a quoted/block-scalar field is exempt rather than
        # scanned against already-unquoted/already-joined text that no
        # longer reflects how it was actually written.
        return CheckResult(f"{field}-yaml-safe", True, rule, "safe (quoted or block scalar in source)")
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


def _owning_skill_dir(target: Path) -> Path:
    """Normalize a CLI-supplied path to the skill directory ``check_shape()``
    accepts (issue #1387): a pre-commit hook hands this script whichever
    changed files matched its ``files:`` pattern, which includes a skill's
    ``metadata/gitapex.yaml`` sidecar and its ``references/*.md`` files, not
    only ``SKILL.md`` itself. A directory is already what
    ``_resolve_skill_md`` expects and is returned unchanged; a ``SKILL.md``
    path is normalized to its parent. Otherwise, walk up through every
    ancestor (nearest first) for one named ``metadata`` or ``references``
    and, on the first match, return ITS parent -- not simply the target's
    own immediate parent, which would silently walk to the wrong directory
    for a file more than one level under ``references/`` (adversarial
    review finding: ``.pre-commit-config.yaml``'s own ``files:`` pattern for
    this hook, ``references/.*\\.md``, matches a nested path like
    ``references/sub/deep.md`` too, since ``.*`` crosses ``/`` -- the very
    shape ``references-flat`` exists to flag as a violation). This still
    grades every skill directory once per commit: a commit touching both a
    skill's ``SKILL.md`` and a (possibly nested) ``references/*.md`` file
    dedupes to the same key.

    Known residual limitation, not reachable through the pre-commit hook's
    own ``files:`` pattern (which only ever emits ``SKILL.md``,
    ``metadata/gitapex.yaml``, or a path under ``references/``, never a
    loose file directly inside a directory literally named ``metadata`` or
    ``references``): a skill directory whose own name IS ``metadata`` or
    ``references`` would misresolve a loose file sitting directly in it.
    This repository's own naming convention (kebab-case skill slugs) and
    the ``name-pattern``/``name-not-reserved`` checks make that shape
    already unlikely to exist; guarding it would add complexity this
    unreachable-via-the-actual-caller path does not warrant."""
    if target.is_dir():
        return target
    if target.name == "SKILL.md":
        return target.parent
    for ancestor in target.parents:
        if ancestor.name in ("metadata", "references"):
            return ancestor.parent
    return target


def _validate_read_scope(target: Path, allowed_root: Path) -> None:
    """Reject an escaped or symlinked CLI target before reading any content."""
    # PTH100 waived on both abspath calls in this file: Path.resolve()
    # follows symlinks, os.path.abspath does not. This function depends on
    # that difference -- it absolutizes without resolving so the loop below
    # can still see each symlinked component and reject it. Rewriting to
    # resolve() would collapse the very links this check exists to catch.
    root = Path(os.path.abspath(allowed_root))  # noqa: PTH100
    if not root.is_dir():
        raise ValueError(f"allowed root is not a directory: {allowed_root}")

    candidate = _resolve_skill_md(Path(os.path.abspath(target)))  # noqa: PTH100
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"target is outside allowed root: {target}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink is not allowed in target path: {current}")

    root_real = root.resolve(strict=True)
    candidate_real = candidate.resolve(strict=True)
    try:
        candidate_real.relative_to(root_real)
    except ValueError as exc:
        raise ValueError(f"resolved target is outside allowed root: {target}") from exc

    skill_dir = candidate.parent
    for directory, dirnames, filenames in os.walk(skill_dir, followlinks=False):
        for name in dirnames:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"symlink is not allowed in target skill: {path}")
        for name in filenames:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"symlink is not allowed in target skill: {path}")
            if not path.is_file():
                raise ValueError(f"special file is not allowed in target skill: {path}")


def _references_grammar_check(references: object) -> CheckResult:
    """spec.references entries must each have a ``kind`` drawn from
    REFERENCES_KIND_VOCAB -- the one thing about an already-well-shaped
    item (see ``references-well-formed``, which already guarantees
    ``kind``/``anchor``/``summary`` are all non-empty strings and
    ``outcome``, if present, is itself a mapping) that is a semantic
    enum-membership question rather than a parse-time shape question, the
    same division of labor ``portability-declared``/
    ``capability-assumption-declared`` already use relative to
    ``manifest-envelope``. Runs independently of references-well-formed (a
    malformed-shape entry can also carry an unrecognized ``kind``, and a
    reader benefits from seeing both findings rather than only the first
    one that happens to fail); when the field isn't a usable list of item
    mappings at all, that precondition failure is already reported by
    references-well-formed, so this reports "nothing to check" instead of
    a redundant or misleading second failure.

    Deliberately does not validate the anchor field's own internal shape
    (a GitHub URL, an external URL, a `method:<skill>` token, or a
    repo-relative path are all legitimate depending on the entry's kind) --
    the existing no-bare-issue-citation scan already enforces the one rule
    that actually matters for an anchor (no bare `#N`/`owner/repo#N`
    citation anywhere in the entry), so a second, narrower anchor-shape
    regex here would just be unenforced ornamentation.
    """
    rule = f"spec.references, if present, has each entry's kind field one of {REFERENCES_KIND_VOCAB}"
    if references is None:
        return CheckResult("references-grammar", True, rule, "not declared (optional)")
    if not (
        isinstance(references, list)
        and references
        and all(isinstance(r, dict) and isinstance(r.get("kind"), str) for r in references)
    ):
        return CheckResult(
            "references-grammar", True, rule, "nothing to check (already reported by references-well-formed)"
        )
    offenders = [r["kind"] for r in references if r["kind"] not in REFERENCES_KIND_VOCAB]
    count = len(offenders)
    return CheckResult(
        "references-grammar",
        not offenders,
        rule,
        "all entries match"
        if not offenders
        else f"{count} entr{'y' if count == 1 else 'ies'} with an unrecognized kind: {offenders[0]!r}",
    )


def _invocation_mode_check(fields: dict[str, str]) -> CheckResult:
    """The two invocation-control frontmatter fields must each carry a
    documented boolean literal, and must not together leave the skill
    invocable by nobody.

    Deliberately narrow. Whether the declared mode *matches the trigger the
    skill's own description and procedure claim* -- a manual-only skill
    promising to fire automatically on some event -- is the semantic
    question, and it stays with the model-judged Invocation-mode fit check
    in references/rubric.md; a script cannot read a trigger sentence's
    intent. What a script CAN decide is exactly two things:

    - a value outside Claude Code's documented boolean literal set, where
      the runtime's own behavior (rejected, or silently read as one branch)
      is Unknown per the runtime-compatibility baseline, so the author's
      intent is unknowable from the file alone; and
    - ``disable-model-invocation`` truthy together with
      ``user-invocable`` false, which removes both invocation paths the
      product documents and leaves a skill nothing can start. That
      combination is never a deliberate state -- unlike either field alone,
      each of which is a documented, useful choice.

    Absent fields pass: the documented defaults (auto-loadable, and visible
    in the / menu) are the normal, overwhelmingly common state.

    Known false positive, disclosed rather than worked around: a value
    carrying a trailing inline YAML comment (``true  # manual only``)
    fails, because ``_parse_frontmatter`` deliberately does not strip
    inline comments and reads the whole remainder as the value. This is
    the same fail-closed-against-an-expected-literal tradeoff
    ``_parse_manifest``'s own docstring already states for the sidecar's
    enum fields, applied here to a frontmatter field for the first time --
    a loud failure naming the exact offending raw value, never a silent
    pass.
    """
    rule = (
        "disable-model-invocation/user-invocable, if present, each carry a "
        "documented boolean literal, and do not together disable both "
        "invocation paths"
    )
    declared = {k: v for k, v in fields.items() if k in INVOCATION_FIELD_DEFAULTS}
    if not declared:
        return CheckResult("invocation-mode-well-formed", True, rule, "not declared (optional)")
    resolved: dict[str, bool] = dict(INVOCATION_FIELD_DEFAULTS)
    malformed: list[str] = []
    for key, raw in declared.items():
        literal = raw.strip().lower()
        if literal in INVOCATION_TRUE_LITERALS:
            resolved[key] = True
        elif literal in INVOCATION_FALSE_LITERALS:
            resolved[key] = False
        else:
            malformed.append(f"{key}: {raw!r}")
    if malformed:
        return CheckResult(
            "invocation-mode-well-formed",
            False,
            rule,
            f"value outside {INVOCATION_TRUE_LITERALS + INVOCATION_FALSE_LITERALS} "
            f"(case-insensitive): {', '.join(malformed)}",
        )
    if resolved["disable-model-invocation"] and not resolved["user-invocable"]:
        return CheckResult(
            "invocation-mode-well-formed",
            False,
            rule,
            "invocable by nobody: disable-model-invocation blocks the model "
            "and user-invocable: false hides it from the / menu",
        )
    return CheckResult(
        "invocation-mode-well-formed",
        True,
        rule,
        "declared: " + ", ".join(f"{k}={str(resolved[k]).lower()}" for k in sorted(declared)),
    )
