"""Bundled-script-related checks: out-of-skill script references, the
no-voodoo-constant AST scan, and script-execution-intent citation
checks."""

from __future__ import annotations

import ast
import os.path
import re
import tokenize
from io import StringIO
from pathlib import Path

from shape_checks.citation_checks import _citation_sources
from shape_checks.citations import _blank_fenced_blocks, _dedup, _strip_illustrative_spans
from shape_checks.constants import _ALL_CAPS_CONST_NAME_RE, SCRIPTS_PATH_BARE_RE, CheckResult
from shape_checks.links_portability import _escapes_skill_dir, _is_ignorable


def _out_of_skill_scripts_offenders(skill_dir: Path, source_text: str) -> list[str]:
    """Issue #192 (Refs #26 repair 3, #36 repair 3, #20 item d): return
    each bare-prose "scripts/PATH" mention (SCRIPTS_PATH_BARE_RE) in
    ``source_text`` whose path does NOT resolve to a real file under
    ``skill_dir`` -- the same "must resolve inside the skill's own
    directory" rule links-inside-skill/_out_of_skill_link_targets already
    applies to a real Markdown link, applied here to the bare-prose form
    that rule does not see (a Markdown link's target is only path-checked
    when written as "[text](scripts/foo.py)" -- a bare "run
    `scripts/foo.py`"-shaped mention has no link syntax to check at all).

    A "scripts/PATH" mention that DOES resolve inside the skill's own
    directory is a common, legitimate self-reference (every skill's
    SKILL.md routinely names its own bundled script this way) and is not
    flagged -- unlike REPO_PATH_CITATION_RE's evals/docs prefixes, which
    never legitimately resolve inside a skill directory and so are
    unconditionally flagged, "scripts/..." needs this resolution check
    rather than an unconditional flag or a hedge-phrase-proximity check
    (confirmed by a corpus-wide simulation before adding this check: every
    real bare-prose "scripts/..." mention in this repository's own
    Portable skills today is a same-skill self-reference).

    Resolution reuses ``_escapes_skill_dir`` (a review finding: a plain
    ``(skill_dir / path).is_file()`` check, with no lexical boundary
    check first, would treat a "scripts/../../other-skill/scripts/x.py"-
    shaped citation that plainly escapes the citing skill's own directory
    as a legitimate self-reference whenever the traversed-to file happens
    to exist -- the same boundary test links-inside-skill's own
    ``_out_of_skill_link_targets`` already applies to a real Markdown
    link, applied here too). A trailing ".,;:)" is stripped from the raw
    regex match before resolution (another review finding: sentence-final
    punctuation immediately after a real extension, e.g. "run
    scripts/check_foo.py.", is captured by SCRIPTS_PATH_BARE_RE's own
    character class -- which must include "." for real extensions -- and
    would otherwise make a genuine self-reference fail the existence
    check purely because of how the sentence ends); no real path ends in
    one of these characters, so stripping them is never lossy.
    """
    bare = _strip_illustrative_spans(_blank_fenced_blocks(source_text))
    skill_norm = os.path.normpath(str(skill_dir))
    offenders: list[str] = []
    for match in SCRIPTS_PATH_BARE_RE.finditer(bare):
        path = match.group(0).rstrip(".,;:)")
        normalized = os.path.normpath(Path(skill_norm) / path)
        if _escapes_skill_dir(normalized, skill_norm) or not Path(normalized).is_file():
            offenders.append(path)
    return offenders


def _out_of_skill_scripts_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _out_of_skill_scripts_offenders,
    scanning SKILL.md and every references/*.md file the same way every
    other _citation_sources-based check does. Only called when
    ``_is_portable`` is true (see ``check_shape``), matching
    ``_portable_path_citation_checks``'s own Portable-only gate: a
    Mixed/Repository-scoped skill legitimately depends on a repo-specific
    scripts/ path.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        for offender in _out_of_skill_scripts_offenders(skill_dir, source_text):
            offenders.append(f"{label}:{offender}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "portable-no-out-of-skill-scripts-citation",
            not offenders,
            "Portable content has no bare-prose 'scripts/...' path citation outside the skill's own directory",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _is_simple_literal_node(node: ast.expr) -> bool:
    """Whether ``node`` (an assignment's RHS value) is a "simple literal"
    for the no-voodoo-constant check: a bare ``ast.Constant``, an
    ``ast.Tuple``/``ast.List``/``ast.Set`` whose every element is itself an
    ``ast.Constant`` (covers e.g. ``shape_checks/constants.py``'s own
    ``EXEC_REQ_NETWORK_MODES = ("disabled", "allowlist", "unrestricted")``-
    shaped constants), or an ``ast.Dict`` whose every key and value is
    itself an ``ast.Constant`` (a literal-keys-and-values config mapping is
    exactly the "voodoo constant" shape this check exists to catch; a
    ``None`` key -- the AST's own shape for a ``**spread`` entry -- fails
    the ``ast.Constant`` check and so is correctly excluded). Deliberately
    excludes any RHS containing a Call, a Name reference, or a nested
    container -- those are outside this check's narrow "bare data literal
    with no adjacent justification" scope.
    """
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(isinstance(elt, ast.Constant) for elt in node.elts)
    if isinstance(node, ast.Dict):
        return all(isinstance(k, ast.Constant) for k in node.keys) and all(
            isinstance(v, ast.Constant) for v in node.values
        )
    return False


def _bundled_python_scripts(skill_dir: Path) -> list[Path]:
    """Every non-test ``*.py`` file anywhere under the skill's own
    ``scripts/`` directory, sorted for deterministic offender ordering.
    Returns an empty list when ``scripts/`` does not exist -- the shared
    "not declared (optional)" precondition both new bundled-script checks
    use. ``test_*.py`` files are excluded, by basename regardless of
    depth: test fixture literals are not "configuration" and would be
    enormous false-positive noise (e.g. this very checker's own
    7000+-line ``test_gitapex_check_skill_shape.py``).

    RECURSIVE (``scripts_dir.rglob``), not ``scripts_dir.iterdir()``: a
    skill may ship its scripts as a package (a ``scripts/<name>/``
    subdirectory of modules), and that subpackage's own content is just
    as much the skill's real bundled code as a top-level script's -- a
    top-level-only scan silently exempts all of it. This checker's own
    ``skills/evaluating-skill-quality`` demonstrated the failure mode
    live: the shape-check families were moved into ``scripts/
    shape_checks/`` (a package of ~5000 lines, ``constants.py`` among
    them), and a top-level-only scan stopped seeing every one of those
    modules' module-level constants overnight, without a single check
    changing. Matches the established convention this skill's own sibling
    scanner already uses for the same "what are this skill's bundled
    Python scripts" question (see
    ``gitapex_scan_execution_requirements_drift.py``'s own
    ``_bundled_script_trees``, likewise recursive, likewise excluding
    ``test_*`` by basename at any depth). ``_is_ignorable`` drops
    dotfiles and ``__pycache__`` bytecode-cache content, the same junk
    filter the references/ checks already apply.
    """
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [
        p
        for p in sorted(scripts_dir.rglob("*.py"))
        if p.is_file() and not p.name.startswith("test_") and not _is_ignorable(p)
    ]


def _assignment_target_names(node: ast.stmt) -> tuple[list[str], ast.expr | None]:
    """Return (bare-Name target names, RHS value) for a module-level
    ``ast.Assign`` or ``ast.AnnAssign`` statement, uniformly -- an
    ``ast.AnnAssign`` (``TIMEOUT: int = 30``) carries a single ``target``,
    not a ``targets`` list, and its own ``value`` is ``None`` for a
    bare annotation with no assignment (``TIMEOUT: int``, nothing to
    scan). Any other statement type, or an ``ast.AnnAssign`` with no
    value, returns ``([], None)``.

    Each target is evaluated independently by the caller rather than
    requiring every target in a chained assignment (``FOO = bar = 1``) to
    match the ALL-CAPS heuristic together -- a tuple-unpacking, attribute,
    or subscript target is simply excluded from the returned name list
    (not a reason to discard the whole statement), since those are not
    simple named constants either.
    """
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)], node.value
    if isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
        return [node.target.id], node.value
    return [], None


def _comment_line_numbers(source: str) -> set[int]:
    """Physical (1-indexed) line numbers carrying a real ``COMMENT`` token,
    per Python's own tokenizer -- correctly distinguishes an actual
    comment from a ``#`` character living inside a string literal (the
    tokenizer never emits a ``COMMENT`` token for one), unlike a naive
    ``"#" in line`` text scan. Returns an empty set on any tokenizer error
    -- callers already treat a file that fails ``ast.parse`` as
    contributing zero offenders, so a source that also fails to tokenize
    (unlikely once it has already parsed, but not impossible for exotic
    encodings) degrades to "no comments found" rather than raising.
    """
    comment_lines: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comment_lines.add(tok.start[0])
    except (tokenize.TokenError, IndentationError, SyntaxError, UnicodeDecodeError):
        return set()
    return comment_lines


def _has_adjacent_comment(node: ast.stmt, lines: list[str], comment_lines: set[int]) -> bool:
    """Whether ``node`` (an ``ast.Assign``/``ast.AnnAssign`` statement) has
    an adjacent justifying comment: (a) a real ``COMMENT`` token (per
    ``comment_lines``, tokenizer-derived -- never a ``#`` living inside a
    string-literal RHS, e.g. ``PREFIX = "issue #"``) exists on ANY
    physical line the statement itself spans (``node.lineno`` through
    ``node.end_lineno`` inclusive) -- covers both a trailing comment on a
    single-line assignment and a trailing comment on a multi-line
    container literal's own opening line (e.g.
    ``NAME = (  # explanation`` ... ``)``), which a strict
    "only the very last line" check would miss; or (b) the nearest
    non-blank source line above the statement's first line is itself a
    comment-only line.
    """
    end_lineno = node.end_lineno or node.lineno
    if any(lineno in comment_lines for lineno in range(node.lineno, end_lineno + 1)):
        return True
    prev_idx = node.lineno - 2
    while prev_idx >= 0:
        prev_line = lines[prev_idx].strip()
        if not prev_line:
            prev_idx -= 1
            continue
        return prev_line.startswith("#")
    return False


def _voodoo_constant_offenders(scripts: list[Path], skill_dir: Path) -> list[str]:
    """Return ``scripts/FILE.py:LINE:NAME`` for each module-level,
    ALL-CAPS-named, simple-literal assignment or annotated assignment in
    ``scripts`` with no adjacent justifying comment -- see the module
    docstring's no-voodoo-constant entry for the full rule and its
    deliberate escape hatch (any adjacent comment, however short,
    satisfies this check).

    Only ``tree.body`` (module-level statements) is walked, never
    recursed into a function or class body -- a constant assigned inside a
    function is a local, not a "voodoo constant" in the configuration
    sense this check targets. A file that fails to parse (``SyntaxError``)
    contributes zero offenders -- a malformed script is a different
    problem, not this check's (this repository's other gates, e.g. a
    full pytest run, already catch it). A file that cannot even be read
    as UTF-8 text (``UnicodeDecodeError``/``OSError``) is different:
    unlike a syntax error, nothing else in this repository's own gates
    is guaranteed to notice a bundled script that is simply unreadable,
    so silently skipping it here would let the check pass vacuously for
    a script nobody actually scanned -- reported as an offender instead,
    matching this checker's own ``skill-md-readable`` check's fail-loud
    precedent (``shape_checks/orchestrator.py``'s ``_skill_md_read_result``)
    for the same failure mode on ``SKILL.md`` itself.

    Each offender is labelled by its path relative to ``skill_dir`` (e.g.
    ``scripts/helperpkg/config.py``), not a bare ``scripts/<basename>``:
    ``_bundled_python_scripts`` above scans recursively, so two different
    subdirectories can hold a same-named module and the evidence string
    must still point at the real file. Identical to the old bare-basename
    label for a script sitting directly under ``scripts/``. Same reasoning
    ``gitapex_scan_execution_requirements_drift.py``'s own
    ``_bundled_script_trees`` already records for its own relative-name
    reporting.
    """
    offenders: list[str] = []
    for script in scripts:
        relpath = script.relative_to(skill_dir).as_posix()
        try:
            source = script.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            offenders.append(f"{relpath}:0:unreadable ({type(exc).__name__})")
            continue
        try:
            tree = ast.parse(source, filename=str(script))
        except SyntaxError:
            continue
        lines = source.splitlines()
        comment_lines = _comment_line_numbers(source)
        for node in tree.body:
            names, value = _assignment_target_names(node)
            if not names or value is None or not _is_simple_literal_node(value):
                continue
            if _has_adjacent_comment(node, lines, comment_lines):
                continue
            for name in names:
                if _ALL_CAPS_CONST_NAME_RE.match(name):
                    offenders.append(f"{relpath}:{node.lineno}:{name}")
    return offenders


def _no_voodoo_constant_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _voodoo_constant_offenders,
    issue #1045's Acceptance Criteria Map item A. Runs unconditionally, at
    every portability level -- unlike the Portable-gated checks above, an
    uncommented configuration constant is a defect regardless of a skill's
    declared portability.
    """
    rule = "every bundled script's module-level ALL-CAPS constant assignment has an adjacent justifying comment (no voodoo constants)"
    scripts = _bundled_python_scripts(skill_dir)
    if not scripts:
        return [CheckResult("no-voodoo-constant", True, rule, "not declared (optional)")]
    offenders = sorted(_voodoo_constant_offenders(scripts, skill_dir))
    return [
        CheckResult(
            "no-voodoo-constant",
            not offenders,
            rule,
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _bundled_scripts(skill_dir: Path) -> list[Path]:
    """Every file (any extension) anywhere under the skill's own
    ``scripts/`` directory, sorted for deterministic offender ordering --
    the script-execution-intent-stated check's own scope, wider than
    ``_bundled_python_scripts`` above since a referenced ``.sh`` script
    counts too. Returns an empty list when ``scripts/`` does not exist.

    RECURSIVE for the same reason ``_bundled_python_scripts`` above is
    (see its own docstring): a script shipped inside a ``scripts/<name>/``
    subdirectory is still one of the skill's own bundled scripts, and a
    top-level-only scan exempts it from the execution-intent rule
    entirely. ``_is_ignorable`` drops dotfiles and ``__pycache__``
    content -- the latter matters more here than for the ``*.py``-only
    scan above, since this one accepts any extension and would otherwise
    pick up compiled ``.pyc`` bytecode as if it were a bundled script.
    """
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [p for p in sorted(scripts_dir.rglob("*")) if p.is_file() and not _is_ignorable(p)]


def _markdown_paragraphs(source_text: str) -> list[str]:
    """Blank-line-delimited paragraphs from ``source_text``, each with its
    own internal hard-wrapped newlines joined to a single space -- the
    same unit Markdown itself treats a hard-wrapped sentence as. A
    citation and its qualifying execution-intent phrase can legitimately
    fall on different physical source lines purely because of where a
    line-wrap happens to land (this repository's own Markdown is
    hard-wrapped around 80 columns); paragraph-level matching recognizes
    them as adjacent regardless, where a strict same-physical-line match
    would not.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    for line in source_text.split("\n"):
        if line.strip() == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _script_execution_intent_offenders(
    skill_md: Path, skill_dir: Path, body: list[str], scripts: list[Path]
) -> list[str]:
    """Return ``label:filename`` for each bundled script in ``scripts``
    that IS mentioned somewhere in ``_citation_sources`` as an inline-code
    span of its own exact filename (`` `filename` ``) but carries no such
    mention whose own enclosing paragraph (``_markdown_paragraphs`` --
    blank-line-delimited, hard-wrapped newlines joined) also states
    explicit execution intent (``Run `filename` `` or
    ``See `filename` ... for ...``) -- see the module docstring's
    script-execution-intent-stated entry for the full rule.

    A script never mentioned this way anywhere is skipped entirely, not an
    offender -- an unlinked/unreferenced script is a separate
    dimension-5 progressive-disclosure concern, out of scope for this
    check. The result is deduplicated by filename -- a script mentioned in
    multiple files with no qualifying phrase in any of them is reported
    once, labelled by the first source it was found unqualified in.
    """
    sources = _citation_sources(skill_md, skill_dir, body)
    offenders: list[str] = []
    seen: set[str] = set()
    for script in scripts:
        filename = script.name
        token = f"`{filename}`"
        # Case-insensitive: "run"/"see" mid-sentence ("...also run `x.py`
        # to...") is natural, grammatically-required lowercase prose, not
        # a defect -- only the capitalized, sentence-initial imperative
        # form the rubric's own illustrative example happens to use. Case
        # carries no semantic distinction for "does this state execution
        # intent," so gating on it would only pressure authors toward
        # awkward, sentence-initial-only phrasing to satisfy the check.
        run_re = re.compile(r"\bRun\s+`" + re.escape(filename) + r"`", re.IGNORECASE)
        see_re = re.compile(r"\bSee\s+`" + re.escape(filename) + r"`[^\n]*\bfor\b", re.IGNORECASE)
        mentioned = False
        satisfied = False
        first_offending_label: str | None = None
        for label, source_text in sources:
            if token not in source_text:
                continue
            for para in _markdown_paragraphs(source_text):
                if token not in para:
                    continue
                mentioned = True
                if run_re.search(para) or see_re.search(para):
                    satisfied = True
                    break
                if first_offending_label is None:
                    first_offending_label = label
            if satisfied:
                break
        if mentioned and not satisfied and filename not in seen:
            offenders.append(f"{first_offending_label}:{filename}")
            seen.add(filename)
    return offenders


def _script_execution_intent_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _script_execution_intent_offenders,
    issue #1045's Acceptance Criteria Map item A. Runs unconditionally, at
    every portability level -- like _no_voodoo_constant_checks above, this
    is about a skill's own bundled scripts, orthogonal to the portability
    axis.
    """
    rule = "a bundled script referenced from SKILL.md/references/ states explicit execution intent ('Run `X`' or 'See `X` for ...')"
    scripts = _bundled_scripts(skill_dir)
    if not scripts:
        return [CheckResult("script-execution-intent-stated", True, rule, "not declared (optional)")]
    offenders = _script_execution_intent_offenders(skill_md, skill_dir, body, scripts)
    return [
        CheckResult(
            "script-execution-intent-stated",
            not offenders,
            rule,
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]
