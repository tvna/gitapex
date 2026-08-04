"""CI gate: every real skill in this repository passes the deterministic
shape checker (skills/evaluating-skill-quality/scripts/gitapex_check_skill_shape.py).

Today that checker's own unit tests run in CI, but the checker was never
actually applied to the repository's real skills as part of any automated
run -- a new skill with a missing or malformed metadata/gitapex.yaml sidecar
(or any other shape violation) could merge green. This test closes that gap
by discovering every skills/*/ directory that has a SKILL.md and running
check_shape() against it, parametrized per skill so a failure names the
offending skill directly rather than reporting one opaque aggregate result.
"""

from __future__ import annotations

import pathlib
import re

import gitapex_check_skill_shape as css
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"

# Guards against the discovery silently finding nothing (e.g. a bad REPO_ROOT
# or a moved skills/ directory) and the test suite then vacuously "passing".
# There are 17 skills in this repository today; a floor of 10 would tolerate
# losing 7 of them silently, so the floor is set close to the real count.
MIN_EXPECTED_SKILLS = 15


def _discover_skill_dirs() -> list[pathlib.Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p.parent for p in SKILLS_DIR.glob("*/SKILL.md") if p.is_file())


SKILL_DIRS = _discover_skill_dirs()


def test_discovery_found_a_plausible_number_of_skills():
    assert len(SKILL_DIRS) >= MIN_EXPECTED_SKILLS, (
        f"expected at least {MIN_EXPECTED_SKILLS} skills under {SKILLS_DIR}, "
        f"found {len(SKILL_DIRS)}: {[d.name for d in SKILL_DIRS]}. "
        "This usually means skill discovery is broken (wrong repo root, "
        "moved skills/ directory), not that skills were actually removed."
    )


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=[d.name for d in SKILL_DIRS])
def test_skill_passes_deterministic_shape_checker(skill_dir):
    results = css.check_shape(skill_dir)
    failures = [r for r in results if not r.passed]
    assert not failures, f"{skill_dir.name}: {len(failures)} shape check(s) failed:\n" + "\n".join(
        f"  - {r.name}: {r.rule} -- evidence: {r.evidence}" for r in failures
    )


# Drift gate for the single-source-of-truth invariant Sub-project C
# established: docs/skill-provenance.md was retired in favor of each
# skill's own metadata/gitapex.yaml spec.references, precisely so
# provenance has exactly one home. Per CLAUDE.md's rule that such an
# invariant ships its drift gate in the same change, not a follow-up.

# The four skills docs/skill-provenance.md named before it was retired
# (Sub-project C, issue #184) -- kept here, not re-derived from the
# (deleted) file, since this is a fixed historical fact of that migration.
SKILLS_WITH_MIGRATED_PROVENANCE = (
    "battle-testing-a-skill",
    "establishing-ubiquitous-language",
    "scorer-gated-skill-edits",
    "evaluating-skill-quality",
)


def test_skill_provenance_file_stays_retired():
    assert not (REPO_ROOT / "docs" / "skill-provenance.md").exists(), (
        "docs/skill-provenance.md was retired in favor of each skill's own "
        "metadata/gitapex.yaml spec.references (Sub-project C, issue #184) "
        "-- recreating it would reintroduce a second home for the same "
        "maintainer-facing provenance data."
    )


@pytest.mark.parametrize("skill_name", SKILLS_WITH_MIGRATED_PROVENANCE)
def test_migrated_provenance_stays_populated(skill_name):
    skill_dir = SKILLS_DIR / skill_name
    parsed = css._parse_manifest((skill_dir / css.SIDECAR_RELATIVE_PATH).read_text(encoding="utf-8"))
    spec = css.spec_of(parsed)
    references = spec.get("references") if spec is not None else None
    assert isinstance(references, list) and references, (
        f"{skill_name}'s metadata/gitapex.yaml lost its migrated "
        "spec.references content (Sub-project C, issue #184); this is the "
        "sole remaining home for that provenance now that "
        "docs/skill-provenance.md is retired."
    )


# ---- spec.skillDependencies.requires cycle gate (Sub-project D, issue #188) ----
#
# check_shape() operates on one skill directory at a time and cannot see the
# graph across skills, so this repo-wide invariant lives here, alongside the
# other repo-wide gates above, rather than in the single-skill checker.
#
# Decision (scope item 4 of #188): a `requires` cycle IS an error. `relatedTo`
# cycles are fine -- they are boundary/complement statements between two
# independently-usable skills (e.g. ranking-the-open-queue <->
# responding-to-a-fresh-arrival <-> screening-a-low-trust-contribution, and
# evaluating-skill-quality <-> scorer-gated-skill-edits, both real cycles in
# this repository today). A `requires` cycle would mean neither skill in the
# cycle could ever function standalone, contradicting the load-bearing
# definition in the design spec (section 4.1): "requires: the procedure
# cannot function without it." Two skills each unable to function without
# the other is not a coherent state.


def _find_requires_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return one cycle (as a path of skill names) if ``graph`` -- a
    skill-name -> its `requires` list mapping -- contains one, else None.

    Standard white/gray/black DFS. A name that appears as a dependency but
    is not itself a key in ``graph`` (a dangling reference) is treated as a
    dead end, not an error -- that is gate 2's (skill-dependencies-resolve)
    job, not this one's.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in graph}
    path: list[str] = []

    def visit(name: str) -> list[str] | None:
        color[name] = GRAY
        path.append(name)
        for dep in graph.get(name, []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                return [*path[path.index(dep) :], dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found:
                    return found
        path.pop()
        color[name] = BLACK
        return None

    for name in graph:
        if color[name] == WHITE:
            found = visit(name)
            if found:
                return found
    return None


def test_find_requires_cycle_returns_none_for_acyclic_graph():
    graph = {"a": ["b"], "b": ["c"], "c": []}
    assert _find_requires_cycle(graph) is None


def test_find_requires_cycle_detects_a_two_cycle():
    graph = {"a": ["b"], "b": ["a"]}
    cycle = _find_requires_cycle(graph)
    assert cycle is not None
    assert set(cycle) == {"a", "b"}


def test_find_requires_cycle_detects_a_longer_cycle():
    graph = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycle = _find_requires_cycle(graph)
    assert cycle is not None
    assert set(cycle) == {"a", "b", "c"}


def test_find_requires_cycle_ignores_dangling_dependencies():
    # A name in `requires` with no entry in the graph is a dead end for
    # this helper, not a crash and not a cycle -- dangling detection is
    # skill-dependencies-resolve's job.
    graph = {"a": ["ghost-skill"]}
    assert _find_requires_cycle(graph) is None


def test_find_requires_cycle_handles_relatedto_style_mutual_edges_if_misused():
    # Sanity: if this helper were ever pointed at a relatedTo graph instead
    # of requires, a legitimate mutual/cyclic relatedTo pair (fine per the
    # design spec) would still report as a "cycle" -- confirming callers
    # must build the graph from `requires` only, never `relatedTo`.
    graph = {
        "ranking-the-open-queue": ["responding-to-a-fresh-arrival"],
        "responding-to-a-fresh-arrival": ["ranking-the-open-queue"],
    }
    assert _find_requires_cycle(graph) is not None


def _real_requires_graph(
    skill_dirs: list[pathlib.Path] | None = None,
) -> dict[str, list[str]]:
    graph: dict[str, list[str]] = {}
    for skill_dir in SKILL_DIRS if skill_dirs is None else skill_dirs:
        sidecar = skill_dir / css.SIDECAR_RELATIVE_PATH
        if not sidecar.is_file():
            continue
        parsed = css._parse_manifest(sidecar.read_text(encoding="utf-8"))
        spec = css.spec_of(parsed)
        deps = spec.get("skillDependencies") if spec is not None else None
        requires = deps.get("requires") if isinstance(deps, dict) else None
        graph[skill_dir.name] = requires if isinstance(requires, list) else []
    return graph


def test_real_requires_graph_does_not_crash_on_malformed_spec_scalar(tmp_path):
    # Regression guard: a future sidecar with `spec:` written as a scalar
    # (not a mapping) must not crash this repo-wide cycle test with an
    # opaque AttributeError -- it should be treated as having no
    # skillDependencies, same as a missing spec.
    skill_dir = tmp_path / "malformed-skill"
    (skill_dir / pathlib.Path(css.SIDECAR_RELATIVE_PATH).parent).mkdir(parents=True)
    (skill_dir / css.SIDECAR_RELATIVE_PATH).write_text(
        "apiVersion: gitapex.io/v1alpha1\nkind: SkillMetadata\nspec: not-a-mapping-scalar\n", encoding="utf-8"
    )
    graph = _real_requires_graph(skill_dirs=[skill_dir])
    assert graph == {"malformed-skill": []}


def test_no_requires_cycle_among_real_skills():
    cycle = _find_requires_cycle(_real_requires_graph())
    assert cycle is None, (
        f"requires cycle found: {' -> '.join(cycle)} -- a requires cycle is "
        "an error per #188's scope item 4 (see the module docstring above): "
        "no skill in the cycle could ever function standalone."
    )


# ---- no-bare-spec-get lint (issue #228 repair 2, tracked via #396) ----
#
# `css.spec_of(parsed)` centralizes the isinstance(spec, dict) guard a
# malformed sidecar's `spec:` scalar/list needs. Inlining a bare get call
# for the spec key directly is exactly the pattern that regressed twice in
# one file within a single PR (#228 repairs 2 and 3) before that guard
# existed everywhere it was needed. This scans every test module for a
# reintroduced bare chain rather than relying on a reviewer to notice a new
# inline occurrence.
#
# Matched against each file's full text, not line-by-line: `\s` already
# spans newlines, so this also catches the call wrapped across lines (e.g.
# `parsed.root.get(\n    "spec"\n)`), which a splitlines()-then-search
# approach would silently miss (Codex review, PR #397).

_BARE_GET_SPEC_RE = re.compile(r"""\.get\(\s*["']spec["']""")


def _find_bare_get_spec_offenders(text: str) -> list[int]:
    """1-based line numbers of a bare get-on-spec chain in ``text``."""
    return [text.count("\n", 0, match.start()) + 1 for match in _BARE_GET_SPEC_RE.finditer(text)]


def test_find_bare_get_spec_offenders_catches_multiline_call():
    # Regression guard: reformatting the call across lines must not evade
    # this lint by defeating a line-by-line scan (Codex review, PR #397).
    text = 'x = parsed.root.get(\n    "spec"\n)\n'
    assert _find_bare_get_spec_offenders(text) == [1]


# tests/*.py is this repo's shared test suite; skills/*/scripts/test_*.py
# is where each skill keeps tests for its own bundled scripts (e.g.
# skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py, right
# next to spec_of()'s own implementation) -- both are "test-side consumers"
# of parsed.root["spec"] in the sense issue #228 meant, so both are scanned
# (issue #525 widened this from the original tests/*.py-only scan, which
# predated any skills/*/scripts/test_*.py file existing in this repo).
_SCANNED_GLOBS: tuple[str, ...] = ("tests/*.py", "skills/*/scripts/test_*.py")


def _scan_for_bare_get_spec(root: pathlib.Path) -> list[str]:
    """Offending 'path:lineno' strings for every bare get-on-spec chain
    found under any of ``_SCANNED_GLOBS``, resolved relative to ``root``."""
    offenders: list[str] = []
    for pattern in _SCANNED_GLOBS:
        for test_file in sorted(root.glob(pattern)):
            text = test_file.read_text(encoding="utf-8")
            offenders.extend(
                f"{test_file.relative_to(root)}:{lineno}" for lineno in _find_bare_get_spec_offenders(text)
            )
    return offenders


def test_no_bare_get_spec_chain_in_tests():
    offenders = _scan_for_bare_get_spec(REPO_ROOT)
    assert not offenders, (
        "bare get-on-spec chain found outside css.spec_of() -- use "
        "css.spec_of(parsed) instead, which guards against a malformed "
        "sidecar's spec: being a non-mapping scalar/list (issue #228 "
        f"repairs 2/3): {offenders}"
    )


# Built via concatenation, not one literal, so this module's own source
# text never contains the offending get-on-spec substring -- otherwise
# this file (itself scanned by test_no_bare_get_spec_chain_in_tests, since
# it lives under tests/*.py) would flag itself.
_OFFENDING_LINE = "x = parsed.root.get(" + '"spec"' + ")\n"


def test_scan_for_bare_get_spec_catches_offender_in_skill_scripts_glob(tmp_path):
    # Regression pin for the widened glob (issue #525): a bare get-on-spec
    # chain reintroduced right next to gitapex_check_skill_shape.py itself, in
    # skills/*/scripts/test_*.py, must be caught -- not just tests/*.py.
    skill_scripts = tmp_path / "skills" / "some-skill" / "scripts"
    skill_scripts.mkdir(parents=True)
    (skill_scripts / "test_something.py").write_text(_OFFENDING_LINE, encoding="utf-8")
    offenders = _scan_for_bare_get_spec(tmp_path)
    assert offenders == ["skills/some-skill/scripts/test_something.py:1"]


def test_scan_for_bare_get_spec_ignores_non_test_files_in_skill_scripts(tmp_path):
    # A skill's own non-test implementation file (e.g. gitapex_check_skill_shape.py
    # itself) legitimately contains the guarded pattern inside spec_of()'s
    # own body -- the glob is test_*.py-scoped specifically so it never
    # flags that internal implementation.
    skill_scripts = tmp_path / "skills" / "some-skill" / "scripts"
    skill_scripts.mkdir(parents=True)
    (skill_scripts / "check_something.py").write_text(_OFFENDING_LINE, encoding="utf-8")
    assert _scan_for_bare_get_spec(tmp_path) == []


# ---- SKILL_DEP_LIST_ITEM_RE docstring-consistency gate (#228 repair 3) ----
#
# gitapex_check_skill_shape.py has two independent prose descriptions of
# SKILL_DEP_LIST_ITEM_RE's minimum indent width: a comment block directly
# above its definition, and _parse_manifest's own docstring. Only one was
# updated when the regex's width last changed (#228 repair 3), so this
# extracts the regex's actual {N,} numeral and asserts both prose sites
# still state the same number, instead of relying on a second review pass
# to notice a stale one.

_MIN_INDENT_RE = re.compile(r"\{(\d+),\}")
_STATED_MIN_INDENT_RE = re.compile(r"(\d+) or more spaces")


def _preceding_prose_block(source_lines: list[str], target_line_index: int) -> str:
    """Every line immediately above ``source_lines[target_line_index]``
    (0-based) up to (not including) the nearest blank line -- the
    paragraph-style comment block documenting it, tolerating an
    intervening sibling constant assignment line (as sits between
    SKILL_DEP_LIST_ITEM_RE and its comment block's own SKILL_DEPENDENCY_SUBKEYS
    line)."""
    block: list[str] = []
    i = target_line_index - 1
    while i >= 0 and source_lines[i].strip() != "":
        block.insert(0, source_lines[i])
        i -= 1
    return "\n".join(block)


def test_skill_dep_list_item_re_indent_matches_its_docstrings():
    numeral_match = _MIN_INDENT_RE.search(css.SKILL_DEP_LIST_ITEM_RE.pattern)
    assert numeral_match is not None, (
        "SKILL_DEP_LIST_ITEM_RE.pattern no longer has a {N,} minimum-indent "
        "quantifier -- update this test's extraction logic to match its "
        "new shape."
    )
    numeral = numeral_match.group(1)

    source_lines = pathlib.Path(css.__file__).read_text(encoding="utf-8").splitlines()
    definition_index = next(
        i for i, line in enumerate(source_lines) if line.startswith("SKILL_DEP_LIST_ITEM_RE = re.compile(")
    )
    comment_block = _preceding_prose_block(source_lines, definition_index)
    comment_stated = _STATED_MIN_INDENT_RE.search(comment_block)
    assert comment_stated is not None, (
        "the comment block above SKILL_DEP_LIST_ITEM_RE's definition no "
        "longer states an 'N or more spaces' minimum indent -- update this "
        "test's extraction logic to match its new wording."
    )
    assert comment_stated.group(1) == numeral, (
        f"SKILL_DEP_LIST_ITEM_RE now requires {numeral}+ spaces, but the "
        f"comment above its definition still says {comment_stated.group(1)}+ "
        "-- issue #228 repair 3's exact drift, recurring."
    )

    docstring = css._parse_manifest.__doc__
    # The docstring also describes spec.references' "2 or more spaces" rule
    # before this bullet and spec.executionRequirements.tools' "6 or more
    # spaces" rule after it; bound the search to the spec.skillDependencies
    # bullet's own span (up to the next "- spec.*" bullet, or end of string
    # if it is the last one) so neither neighbor's unrelated numeral can be
    # matched instead if this bullet's own numeral goes missing (Codex
    # review, PR #402).
    skill_deps_index = docstring.index("spec.skillDependencies")
    next_bullet = re.search(r"\n {4}- spec\.\w+", docstring[skill_deps_index:])
    skill_deps_end = skill_deps_index + next_bullet.start() if next_bullet else len(docstring)
    docstring_stated = _STATED_MIN_INDENT_RE.search(docstring, skill_deps_index, skill_deps_end)
    assert docstring_stated is not None, (
        "_parse_manifest's docstring no longer states an 'N or more spaces' "
        "minimum indent for spec.skillDependencies list items -- update "
        "this test's extraction logic to match its new wording."
    )
    assert docstring_stated.group(1) == numeral, (
        f"SKILL_DEP_LIST_ITEM_RE now requires {numeral}+ spaces, but "
        f"_parse_manifest's docstring still says {docstring_stated.group(1)}+ "
        "-- issue #228 repair 3's exact drift, recurring."
    )
