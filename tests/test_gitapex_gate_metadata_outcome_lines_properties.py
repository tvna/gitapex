"""Hypothesis property-based layer for
``.github/scripts/gitapex_gate_metadata_outcome_lines.py``'s ``_claims_in_value``
(issue #939). A pilot: this module is the whole rollout, and no other
parser-shaped script under ``.github/scripts/`` or ``evals/scripts/`` is in
scope until this layer has demonstrated it catches a real defect here.

Why property-based at all
-------------------------
The motivating defect is the target-binding false negative PR #882 shipped and
``9d3b426`` fixed: ``_bind_target`` tracked consumption by *resolved path*
rather than by *token occurrence*, so ``lines: "one.md 1->5, one.md 5->99"``
let the first delta consume the file and left the second -- the current-state
claim, the one that matters -- bound to nothing and skipped as unverified
behind exit 0. It was found by an independent review, not by this repository's
own gates.

Line coverage is the wrong instrument for that defect class: the defect lived
in a file at 100% line coverage with 47 collected tests passing, and no
example-based test happened to name one file twice. A coverage threshold
cannot close that gap; input-shape generation can.

Why the first property is model-based
-------------------------------------
Only :func:`test_each_delta_binds_the_filename_token_before_it` detects the
motivating defect, and it does so because it is **model-based**: the generator
knows the intended (filename, delta) pairing, so the parser's own output cannot
define correctness. A self-consistency property cannot distinguish the buggy
parser from the fixed one, because the buggy parser was internally consistent
-- it did emit a reasoned note for the delta it failed to bind.

Retrospective #887 (repair 2) proposed a property for this defect but stated
its invariant as accounting ("every delta either binds a distinct target or is
reported with a reason"). That invariant holds on the buggy code. It is
implemented below as :func:`test_every_delta_is_either_claimed_or_noted`, which
documents in its own docstring that it does not detect the motivating defect --
see https://github.com/tvna/gitapex/issues/887#issuecomment-5231672881.

The other three property groups (accounting, robustness, containment) cover
defect classes the example suite also does not reach, and each says in its own
docstring that it does not detect the motivating defect, so a later reader does
not mistake one of them for the layer that covers it.

None of the four exercises the ``outcome.commit`` sibling-key anchoring branch
(``_explicit_rev``'s first-tier resolution, ahead of the inline-SHA fallback):
every property here drives ``_claims_in_value`` through :func:`_run`, which
hardcodes ``outcome={}``, so every generated claim is either unanchored or
inline-SHA-anchored, never commit-key-anchored. That branch is exercised by
the existing example-based suite
(``test_outcome_commit_key_is_checked_at_that_commit`` in
``tests/test_gitapex_gate_metadata_outcome_lines.py``), so the gap is covered
today, not open -- but it is a real scope boundary of this pilot's own
fixture, disclosed here rather than left for a reader to discover by tracing
:func:`_run`.

Reproducibility
---------------
``derandomize=True`` with an explicit ``max_examples``: this repository runs
pytest under ``pytest-xdist`` (``-n auto``, wired into ``[tool.pytest.ini_options]
addopts``), where a randomly-seeded generator turns a latent failure into an
intermittently red suite that reruns green. (``pytest-split`` is a declared
dev dependency but not yet wired into any workflow's pytest invocation --
no ``--splits``/``--group`` flag exists in ``.github/workflows/`` today -- so
only the xdist half of this reasoning is live in CI as of this pilot; the
same derandomization argument would apply once splitting lands.) The trade
is disclosed rather than hidden -- a derandomized run explores a fixed
example set, so a defect outside that set is not explored on any run, and
that example set is a function of the resolved Hypothesis version: the
`>=6.100` dependency bound in ``pyproject.toml`` does not pin it, so a future
`uv lock` refresh can silently change which examples a derandomized run
explores. A version bump only fails loudly if the new example set happens to
expose a real defect; on a still-correct parser, coverage can drift with no
red test to say so.

``deadline=None`` for the same reason: Hypothesis' default per-example deadline
measures wall-clock time, which under ``-n auto`` on a loaded CI runner is a
scheduling measurement, not a property of the parser.

The fixture below is **module-scoped** rather than ``tmp_path``. That is what
resolves Hypothesis' ``function_scoped_fixture`` health check, instead of
suppressing the health check: a function-scoped fixture is set up once and then
reused across every generated example, which is exactly what that health check
exists to warn about. A module-scoped tree is honest about being built once,
and these properties only ever read it. No health check is suppressed at all:
an earlier revision of this module suppressed ``HealthCheck.too_slow`` on the
assumption that ``-n auto`` would trip it, and removing the suppression was
measured to leave all four properties passing -- so the suppression was
protecting against nothing and is gone.

Scope superseded by issue #1178, for the paths that gate actually covers
--------------------------------------------------------------------------
This module's opening paragraph states that no other parser-shaped script under
``.github/scripts/`` or ``evals/scripts/`` is in scope until this layer has
demonstrated it catches a real defect here. For ``.github/scripts/`` that
sentence is now formally superseded by issue #1178's own
``detection-logic-property-coverage`` gate
(``.github/scripts/gitapex_gate_detection_logic_property_coverage.py``), which
requires Hypothesis property coverage for new or materially changed detection
logic across ``skills/*/scripts/gitapex_check_*.py``,
``.github/scripts/gitapex_gate_*.py``, and ``hooks/gitapex_check_*.py`` --
regardless of whether this specific pilot has yet demonstrated its own catch.
``evals/scripts/`` is not one of those three patterns and stays outside issue
#1178's gate entirely; the opening paragraph's "no other script in scope yet"
sentence is still current for it, not superseded. A reader should not treat
the opening paragraph's sentence as still current for ``.github/scripts/``,
nor assume it is superseded for ``evals/scripts/`` -- the two halves now have
different answers, and the current, superseding scope boundary for the first
half lives in issue #1178's gate, not here.
"""

from __future__ import annotations

import pathlib

import gitapex_gate_metadata_outcome_lines as gate
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# The two real reference files every generated value draws from. Deliberately
# a pool of exactly two, paired with `min_size=3` below, so the pigeonhole
# principle makes a repeated filename token occur in *every* generated example
# rather than merely being likely across the example set -- repetition is what
# separates the fixed parser from the pre-`9d3b426` one.
#
# Neither name contains a digit (so no filename fragment can be read as a
# delta's `before`/`after`) nor a 7-or-more-character all-hex word (so
# `_SHA_TOKEN_RE` cannot read one as a commit citation and turn the claim
# unanchored-vs-anchored). Both constraints are properties of the parser this
# module tests, not incidental style.
_FILE_POOL = ("alpha-notes.md", "beta-notes.md")

_SKILL = "alpha"

# A file that exists *outside* the skill directory, plus the tokens that try to
# reach it. `escape.md` is a real symlink inside the skill tree pointing at it,
# which is the one escape vector `_resolve_in_skill`'s lexical `..`/absolute
# checks do not catch on their own -- its `resolve().is_relative_to` check is
# what has to.
_OUTSIDE_FILE = "outside-target.md"
_HOSTILE_TOKENS = (
    "../outside-target.md",
    "../../outside-target.md",
    "references/../../outside-target.md",
    "/etc/passwd",
    "/tmp/outside-target.md",  # a token to be refused, never opened
    "escape.md",
    "./../outside-target.md",
)

# Applied per test rather than registered as a global Hypothesis profile:
# `settings.register_profile` + `load_profile` mutate process-global state that
# would follow into every other test module in this suite, which is a wider
# blast radius than a pilot should take.
_PROPERTIES = settings(
    derandomize=True,
    max_examples=200,
    deadline=None,
)


@pytest.fixture(scope="module")
def skill_dir(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """A read-only ``skills/alpha/`` tree, built once for the whole module.

    Module-scoped on purpose -- see this module's docstring for why that, and
    not a ``suppress_health_check``, is the resolution for Hypothesis'
    ``function_scoped_fixture`` health check. Every property below only reads
    this tree; none writes to it, so sharing it across examples cannot leak
    state from one example into the next.
    """
    root = tmp_path_factory.mktemp("outcome_lines_properties")
    skills = root / "skills"
    directory = skills / _SKILL
    (directory / "references").mkdir(parents=True)
    (directory / gate._SKILL_MD).write_text("x\n" * 10, encoding="utf-8")
    for name in _FILE_POOL:
        (directory / "references" / name).write_text("y\n" * 5, encoding="utf-8")

    # The containment target and the symlink that tries to reach it from
    # inside the skill directory.
    (skills / _OUTSIDE_FILE).write_text("z\n" * 3, encoding="utf-8")
    (directory / "escape.md").symlink_to(skills / _OUTSIDE_FILE)
    return directory


def _expected(name: str) -> str:
    return f"skills/{_SKILL}/references/{name}"


def _pair_text(name: str, before: int, after: int) -> str:
    return f"{name} {before}->{after}"


def _run(
    value: str, skill_dir: pathlib.Path, key: str = "lines"
) -> tuple[list[gate.Claim], list[gate.Note], list[gate.Finding]]:
    return gate._claims_in_value(key, value, {}, skill_dir, "fixture spec.references[0]")


# --------------------------------------------------------------------------
# Model-based: the one property that detects the motivating defect
# --------------------------------------------------------------------------

_PAIRS = st.lists(
    st.tuples(st.sampled_from(_FILE_POOL), st.integers(min_value=0, max_value=999), st.integers(0, 999)),
    min_size=3,
    max_size=6,
)


@_PROPERTIES
@given(pairs=_PAIRS)
def test_each_delta_binds_the_filename_token_before_it(
    pairs: list[tuple[str, int, int]], skill_dir: pathlib.Path
) -> None:
    """N alternating (filename, delta) pairs yield exactly N claims, each bound
    to the filename token immediately preceding it.

    **This is the property that detects the #887-repair-2 defect class.** The
    generator holds the intended pairing, so a parser that drops a claim (the
    pre-`9d3b426` path-keyed consumption, on any value naming one file twice)
    fails against the model instead of defining its own output as correct.
    `_FILE_POOL` has two entries and `min_size` is 3, so every generated
    example repeats a filename -- by the pigeonhole principle, not by luck.

    Flip-tested against the real defect, not a proxy: with `_bind_target`
    locally reverted to its pre-`9d3b426` path-keyed consumption, this test
    FAILS on its first generated example (`alpha-notes.md` three times) --
    the empty-`notes` assertion below fires first, reporting two
    `binds to no file in this skill; not verified` notes, and the
    `len(claims) == len(pairs)` assertion fails on the same example. With
    `_bind_target` restored it passes. Both outcomes were observed, not
    predicted.
    """
    value = ", ".join(_pair_text(name, before, after) for name, before, after in pairs)
    claims, notes, findings = _run(value, skill_dir)

    assert findings == []
    assert [note.render() for note in notes] == []
    assert len(claims) == len(pairs)
    assert [claim.target for claim in claims] == [_expected(name) for name, _, _ in pairs]
    assert [claim.after for claim in claims] == [after for _, _, after in pairs]


# --------------------------------------------------------------------------
# Accounting -- #887 repair 2's own stated invariant. Does NOT detect the
# motivating defect.
# --------------------------------------------------------------------------


@_PROPERTIES
@given(
    pairs=_PAIRS,
    trailing=st.sampled_from(["", ", fixtures 29->33", ", 0.75 -> 0.9", ", origin/main 1->2"]),
)
def test_every_delta_is_either_claimed_or_noted(
    pairs: list[tuple[str, int, int]], trailing: str, skill_dir: pathlib.Path
) -> None:
    """No delta vanishes: every arrow match in the value is accounted for by
    exactly one claim or one note.

    **Does NOT detect the motivating defect.** This is retrospective #887
    repair 2's invariant as originally stated, and it holds on the
    pre-`9d3b426` code, which emitted a reasoned note for the delta it failed
    to bind -- so an implementer working from #887's line alone would ship a
    property that passes on the bug. Kept because it does cover a different
    class (a delta dropped *silently*, with neither a claim nor a note), and
    kept honest by this paragraph. The correction is recorded at
    https://github.com/tvna/gitapex/issues/887#issuecomment-5231672881.
    """
    value = ", ".join(_pair_text(name, before, after) for name, before, after in pairs) + trailing
    claims, notes, findings = _run(value, skill_dir)

    assert findings == []
    deltas = len(gate._ARROW_CLAIM_RE.findall(value))
    assert len(claims) + len(notes) == deltas


# --------------------------------------------------------------------------
# Robustness. Does NOT detect the motivating defect.
# --------------------------------------------------------------------------


@_PROPERTIES
@given(value=st.text(max_size=200), key=st.sampled_from(["lines", "worked_examples_lines"]))
def test_arbitrary_text_never_raises_and_is_deterministic(value: str, key: str, skill_dir: pathlib.Path) -> None:
    """Arbitrary text produces a result rather than an exception, and the same
    input produces the same output.

    **Does NOT detect the motivating defect.** ``outcome`` is a genuinely
    free-form field (``skill-metadata.schema.json``: "no closed vocabulary"),
    so any string can reach this parser. An exception escaping here is not a
    finding the gate reports -- it is a crashed gate, which fails the whole
    pytest step with a traceback instead of a claim report. Determinism is
    asserted alongside it because a parser whose output depends on set or dict
    iteration order would make the gate's own report unstable between runs.
    """
    first = _run(value, skill_dir, key=key)
    second = _run(value, skill_dir, key=key)
    assert first == second


# --------------------------------------------------------------------------
# Containment. Does NOT detect the motivating defect.
# --------------------------------------------------------------------------


_HOSTILE_PAIRS = st.lists(
    st.tuples(st.sampled_from(_HOSTILE_TOKENS), st.integers(min_value=0, max_value=999)),
    min_size=1,
    max_size=4,
)


@_PROPERTIES
@given(pairs=_HOSTILE_PAIRS)
def test_traversal_tokens_never_bind_outside_the_skill_directory(
    pairs: list[tuple[str, int]], skill_dir: pathlib.Path
) -> None:
    """A token carrying ``..``, an absolute path, or a symlink out of the tree
    never produces a claim about a file outside the skill directory.

    **Does NOT detect the motivating defect.** ``skills/`` content is
    repository-owned, so this is defense in depth rather than a live threat
    today; ``_resolve_in_skill``'s own docstring records that ``pathlib``'s
    ``/`` operator discards the left operand for an absolute right operand,
    which is the trap this asserts is closed. ``escape.md`` is a real symlink
    pointing outside the tree -- the one vector the lexical ``..``/absolute
    checks cannot catch, left to the ``resolve().is_relative_to`` check.

    Confirmed to have teeth rather than assumed to: deleting that
    ``resolve().is_relative_to`` check from ``_resolve_in_skill`` makes this
    property FAIL, and restoring it makes it pass. Not every token in
    ``_HOSTILE_TOKENS`` is load-bearing, though, and the honest reading is
    narrower than the list looks -- ``_PATH_TOKEN_RE`` must start at an
    alphanumeric, so a leading ``../`` or ``/`` is simply not part of the
    matched token, and ``/etc/passwd`` carries no dotted extension to match at
    all. The two tokens that actually exercise a refusal branch are
    ``references/../../outside-target.md`` (matched whole, refused by the
    lexical ``..`` check) and ``escape.md`` (matched, resolves, refused by the
    containment check). The rest are kept as regression cover for the day the
    token regex widens.

    ``pairs`` is one paired strategy (:data:`_HOSTILE_PAIRS`), the same shape
    :data:`_PAIRS` already uses -- not two independently-sized lists zipped
    together. An earlier revision drew a token list and an integer list
    separately and combined them with ``zip(..., strict=False)``, which
    silently truncates to the shorter list whenever Hypothesis draws the two
    at different lengths: measured at ~74% of examples under this file's own
    settings, so most generated examples exercised fewer hostile tokens than
    ``max_size=4`` implied. Pairing them up front removes the possibility by
    construction.
    """
    value = ", ".join(_pair_text(token, index, after) for index, (token, after) in enumerate(pairs))
    claims, _, findings = _run(value, skill_dir)

    assert findings == []
    prefix = f"skills/{_SKILL}/"
    for claim in claims:
        assert claim.target.startswith(prefix), claim.target
        assert _OUTSIDE_FILE not in claim.target
