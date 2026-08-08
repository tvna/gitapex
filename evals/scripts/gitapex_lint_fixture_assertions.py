"""Lint the substring assertions in eval fixtures across this repository's
skills.

`gitapex_score_contract.py` scores a fixture correctly *given* well-formed
assertions; nothing else checks whether the assertions themselves are
well-formed. PR #150 hit the same class of assertion bug four times -- a
case-sensitive `output_contains` against text the rubric prescribes in a
different case, a bare `output_not_contains` phrase that also matches a
correct *denial* of itself, and an `output_contains` that paraphrased the
rubric instead of quoting its stable wording. Issue #516 (triaging
retrospective issues #191, #218, #270, #296, #343, #352, #473, #487) found
several more construct-validity defect classes this script did not yet
catch. Each is a fixture-authoring defect a deterministic pass can catch
before a gate re-run or an external reviewer has to. This script is that
pass.

It reads a skill's own stable text (its `rubric.md`, if it has one, and its
`SKILL.md`) as the anchor corpus and, for every `output_contains` /
`output_not_contains` string in each task YAML, runs:

  1. Case-sensitivity -- the assertion's lowercased form appears inside a
     distinctive rubric anchor (a heading, a bolded span, or a quoted
     phrase) but with different casing than every anchor it matches. The
     anchor's own casing is the stable one to quote. (Historical:
     `output_contains: ["blind spot"]` vs. the `## Blind spot pass`
     heading.) This is also, doubly, the mechanical proxy for issue #858's
     waza-vs-`gitapex_score_contract.py` case-divergence risk: waza's own
     built-in `expected.output_contains` grading is case-insensitive, this
     repository's `gitapex_score_contract.py` is deliberately
     case-sensitive (see that module's own docstring), and an exact-case
     match always implies a case-folded one -- so a fixture whose assertion
     casing matches its skill's own stable wording is guaranteed to satisfy
     both scorers, and this check is what verifies that. `check_case`
     scans every matching anchor before deciding, not just the first: the
     same taxonomy phrase legitimately appears both in a capitalized
     heading/bold span and in a separately documented, deliberately
     lowercase, machine-readable quoted form within one rubric (e.g.
     `merge-retrospective/SKILL.md`'s `Classification:` field), and an
     exact match on any anchor must clear the assertion even when an
     earlier, differently-cased anchor for the same phrase also exists.
     Returning on the first loose hit regardless of a later exact one
     produced 18 false positives across the committed corpus at issue
     #858's time, confirmed by checking each flagged assertion by hand
     against its own skill's `SKILL.md`. One further, genuine residual
     remains after that fix: `scorer-gated-skill-edits/ship-without-
     transfer-check.yaml`'s `output_contains: ["transfer check"]` has no
     exact-case anchor because its correct source (that skill's own
     Stop-boundaries prose, "has not passed a transfer check") is plain
     sentence text, outside this check's heading/bold/quoted extraction
     scope -- also hand-confirmed correct, not a fixture bug, and pinned by
     `tests/test_gitapex_lint_fixture_assertions.py::
     test_repository_case_sensitivity_findings_match_the_known_reviewed_residual`
     so a genuinely new case-sensitivity finding still fails loudly.
  2. Negation trap -- an `output_not_contains` phrase that the corpus
     itself, OR the fixture's own prompt (#487 -- an ad hoc ban invented
     for one fixture will not be in the skill's stable rubric text, so
     restricting this check to the corpus alone misses it), uses under a
     denial cue ("not a ...", "never ...", "no ..."), so a correct review
     echoing that phrasing would contain the banned substring and
     false-fail. (Historical: banning `"tenth dimension"` false-fails "not
     a tenth dimension".)
  3. Paraphrase drift -- a multi-word `output_contains` that is not a
     substring of the corpus, yet all of whose content words appear
     together in a short corpus window: the author almost certainly meant
     to quote the rubric's exact wording. (Historical: `"hook or
     permission"` vs. the rubric's `"hooks and permissions"`.)
  4. Short-word collision (#218) -- a short (<8 char), alphabetic
     `output_contains` string that is itself a common English word *and*
     also a bare substring of a different, unrelated common word, so a
     scorer's substring check would false-pass against the unrelated word
     alone. Checked against a small hand-curated set of known collision
     pairs (`SHORT_WORD_COLLISIONS`), not a general dictionary: a generic
     dictionary substring scan was tried first and rejected -- it false-
     flagged this repository's own deliberately-truncated stem assertions
     (e.g. `"emporal"` for "temporal", `"hardcod"` for "hardcode(d)"),
     which are not real words themselves and so are not the collision this
     check means to catch.
  5. Symmetric ban (#352) -- a fixture whose id/name/description/tags
     mark it as a "claim cannot be determined from available data" case
     (phrases: "cannot be determined", "not claimable", "indeterminate")
     must ban the unsupported claim in *both* directions ("no X occurred"
     and "X occurred"), not just the negative one. (Historical:
     `force-push-not-claimable-test.yaml` scored 1.0 against an
     unsupported positive claim before this was added -- see issue #352.)
  5b. Unsatisfiable/redundant assertion pair (#628) -- since
     `gitapex_score_contract.py` gained opt-in case-insensitive
     `output_icontains`/`output_not_icontains` keys, a fixture can now
     combine a case-sensitive requirement with a case-insensitive ban on
     the same substring in a way that can never jointly score 1.0: an
     `output_contains` entry (or a member of an `output_contains_near`
     entry's `all` list -- satisfying that check also requires literal
     presence) guarantees the substring's casefolded form appears in the
     casefolded text, which unconditionally fails an `output_not_icontains`
     ban on the same casefolded substring. Flagged as
     `unsatisfiable-assertion-pair`, distinct from and more severe than the
     same-polarity case below. Deliberately NOT flagged in the mirrored
     direction (`output_not_contains` + `output_icontains` on the same
     substring): that pairing is satisfiable (e.g. text containing only
     "FOO" satisfies both `output_not_contains: ["Foo"]` and
     `output_icontains: ["foo"]` at once), so flagging it would be a false
     alarm -- confirmed via a Workflow-based adversarial review before this
     was implemented. Separately, an `output_contains` and `output_icontains`
     entry naming the identical casefolded substring is not a contradiction,
     just redundant authoring (the icontains form alone already covers it),
     flagged as the lower-severity `redundant-assertion-pair`.

     Checks 2-4 above (negation trap, paraphrase drift, short-word
     collision) are extended to also run against `output_icontains`/
     `output_not_icontains` entries, since the underlying authoring-mistake
     risk they catch does not depend on whether the assertion happens to be
     case-sensitive. Check 1 (case-sensitivity) is deliberately NOT
     extended to `output_icontains`: that check's entire purpose is
     flagging an assertion that differs in casing from the rubric's own
     wording, which is expected and correct for a key whose whole point is
     to ignore case -- extending it there would just be noise. Check 5
     (symmetric ban) now also counts `output_icontains`/`output_not_icontains`
     entries as valid positive/ban declarations, so a fixture using the new
     keys for its indeterminate-direction ban is not wrongly flagged as
     having "no bans in either direction".

Two further checks exist but ship **off by default**, opt in with
`--check-prompt-echo` / `--check-cross-task`, and never affect the exit
code even when enabled (they print as non-blocking notes): real-corpus
evaluation during #516 found both too noisy for this repository's actual
fixture-authoring conventions to run unconditionally.

  6. Prompt echo (#191) -- an `output_contains` string that is also a
     literal substring of the fixture's own prompt, satisfiable by a
     response that echoes the prompt instead of doing the reviewed work.
     Measured against the real corpus: 23 of this repository's own
     existing assertions matched, nearly all of them fixtures that
     legitimately require quoting text *from a target artifact embedded in
     the prompt* (the thing under review), which this substring check
     cannot distinguish from a lazy echo of the prompt's own question.
  7. Cross-task collision (#270, #473) -- an `output_not_contains` ban in
     one task that exactly matches an `output_contains` string required by
     another task in the same suite. Measured against the real corpus:
     this repository's fixtures routinely and *intentionally* reuse a
     short marker phrase suite-wide (e.g. "Speculation:", "Fact:",
     "adversarial") as a requirement in most tasks and a ban in a few --
     a real, deliberate pattern indistinguishable from an accidental
     collision by a bare substring check, so it is reported as a note for
     a human to triage, never as a blocking warning. An UPPER_SNAKE_CASE
     classification-code token (e.g. `NO_COMPATIBILITY_WARNING`) is always
     excluded, since this repository's own closed-enum classification
     fixtures use exactly that shape for deliberate cross-task bans.

A further, skill-level check runs only in the broadened default-discovery
mode (#296, #473):

  8. Adversarial coverage -- a skill whose own `SKILL.md` or
     `eval-status.md` claims adversarial coverage (the word "adversarial")
     but whose `tasks/` directory has not one fixture tagged `adversarial`.
     Blocking within discovery mode. (Historical: `battle-testing-a-skill`
     discusses "22 adversarial dimensions" throughout its own eval-status
     yet, at the time #516 was filed, tagged zero of its 22 fixtures
     `adversarial`.)
  9. Dispatch-declaration coverage (#584) -- `evaluating-skill-quality` and
     `battle-testing-a-skill` each mandate, in their own `SKILL.md`, that
     their core judgment steps run inside one fresh subagent dispatch; both
     skills' `eval-status.md` disclosed that the committed fixtures assert
     only on final output text, never confirming a dispatch actually
     happened. Blocking within discovery mode: either skill's `tasks/`
     directory with zero fixtures declaring a well-formed
     `expected.requires_fresh_dispatch` value (a mapping with a non-empty
     `tool_names` list and `min_dispatches` >= 1 -- a bare truthy value
     like `true` or `{min_dispatches: 0}` does not count). Scoped to a small, explicit
     allowlist (`DISPATCH_MANDATE_SKILLS`), not a generic "SKILL.md
     mentions dispatch" scan -- see that constant's own docstring for why a
     broader scan would wrongly pull in at least one other skill this issue
     does not cover.

Scope (#296): with no `--tasks-glob`, the default is now every skill
directory with both a `skills/<name>/SKILL.md` and an
`evals/<name>/tasks/*.yaml` directory -- not only
`evaluating-skill-quality`'s own fixtures. Passing `--tasks-glob`
explicitly keeps the original single-skill behavior (with `--rubric` /
`--skill` naming that one skill's anchor corpus), unchanged, for scripts
and docs that already invoke it that way.

These are heuristics, not proofs: each flags a *likely* authoring mistake
for a human to confirm, the same way `gitapex_check_skill_shape.py` flags shape,
not maturity. This broadened scope does not itself fix any pre-existing
fixture defects it surfaces in skills other than `evaluating-skill-
quality` -- that is separate follow-on triage (see issue #516's own
stated non-goal). Standard library only except PyYAML (already a dev
dependency, used by the repo's other fixture tooling) and pydantic (used
to validate each fixture's own shape); the fixtures are YAML, so a real
parser is warranted rather than a hand-rolled subset.

Each fixture file is parsed once against `TaskFixture` (issue #684), a
pydantic model of the actual YAML shape found across every
`evals/*/tasks/*.yaml` file in this repository -- replacing the repeated
`.get(...)` + `isinstance(...)` narrowing this file used to do at each of
its own `expected`/`inputs`/`tags`-reading sites with one validated parse
per file. Fields this linter does not itself read (`expected.exercises`,
`expected.classification`, etc. -- consumed by sibling scripts sharing the
same fixture files) are preserved, not rejected, via `extra="allow"` on
`ExpectedBlock`. `expected.requires_fresh_dispatch` is deliberately typed
as an open `object`, not a nested model: whether a given value is a
*well-formed* declaration is `_is_real_dispatch_declaration`'s own,
separately tested judgment (issue #584), not a shape this model should
reject outright.

Usage:
  python3 gitapex_lint_fixture_assertions.py [--tasks-glob GLOB]
                                     [--rubric PATH] [--skill PATH]
                                     [--check-prompt-echo] [--check-cross-task]

Exit code: 0 if no *blocking* warning, 1 if any assertion is flagged
blocking, 2 on bad usage or unreadable inputs.
"""

from __future__ import annotations

import argparse
import glob as globlib
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

# The reviewing skill's own stable text, relative to the repo root. These are
# the anchor corpus: the wording a fixture that means to quote the rubric
# should quote. Overridable on the CLI so the script is not pinned to one
# checkout layout. Used only in single-skill mode (an explicit --tasks-glob);
# discovery mode (#296) resolves each skill's own corpus instead.
DEFAULT_RUBRIC = "skills/evaluating-skill-quality/references/rubric.md"
DEFAULT_SKILL = "skills/evaluating-skill-quality/SKILL.md"

# Denial cues that, immediately before a banned phrase in the corpus, mark it
# as one the rubric legitimately negates -- so banning the bare phrase in
# output_not_contains would false-fail a correct review that echoes the
# denial. Kept to the forms English forms a negation with in running prose.
DENIAL_CUES = ("not ", "not a ", "not an ", "no ", "never ", "n't ")

# Function words dropped before the paraphrase-drift token comparison, so
# "hook or permission" and "hooks and permissions" compare on their content
# words ({hook, permission}) rather than their connectives.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "or",
        "and",
        "of",
        "to",
        "in",
        "is",
        "are",
        "for",
        "on",
        "with",
        "not",
        "no",
        "as",
        "at",
        "by",
        "be",
        "it",
        "this",
        "that",
    }
)

# Paraphrase drift compares content-word sets inside a sliding corpus window
# this many tokens wider than the assertion's own content-word count, so a
# reordered or connective-varied quote still lands inside one window.
WINDOW_SLACK = 3

# Known short-word / longer-word collision pairs (#218): an output_contains
# string that names the short (left) word alone risks a false pass against
# text containing only the unrelated longer (right) word(s), since a
# substring check cannot tell them apart. Hand-curated rather than a general
# dictionary scan -- see check 4 in the module docstring for why a generic
# dictionary was tried and rejected. Both sides are checked against real
# words on purpose: gating on "the assertion is itself a recognizable word"
# is what keeps this from flagging this repository's own deliberate stem
# fragments ("emporal", "hardcod"), which are not real words and so never
# match a key here.
SHORT_WORD_COLLISIONS: dict[str, tuple[str, ...]] = {
    "actor": ("factor",),
    "art": ("start", "chart", "smart", "depart"),
    "act": ("react", "exact", "impact", "contact"),
    "age": ("stage", "manage", "damage", "storage"),
    "air": ("chair", "repair", "affair"),
    "ask": ("mask", "task", "flask"),
    "ate": ("gate", "create", "late", "rotate"),
    "ear": ("clear", "bear", "wear", "linear"),
    "eat": ("heat", "great", "repeat", "treat"),
    "end": ("spend", "depend", "extend", "friend"),
    "ice": ("price", "voice", "service", "notice"),
    "ill": ("skill", "still", "until"),
    "ink": ("think", "drink", "link"),
    "old": ("hold", "gold", "bold", "folder"),
    "one": ("alone", "phone", "stone", "clone"),
    "out": ("about", "without", "shout"),
    "own": ("known", "shown", "grown"),
    "red": ("bored", "covered", "prepared"),
    "set": ("reset", "asset", "upset", "offset"),
    "ten": ("often", "listen", "gotten"),
    "top": ("stop", "adopt", "laptop"),
    "use": ("cause", "because", "abuse"),
    "war": ("award", "toward", "reward"),
}

# Marks a fixture (via id/name/description/tags) as a "claim cannot be
# determined from available data" case (#352) -- these must ban the
# unsupported claim in both directions.
INDETERMINATE_MARKER_RE = re.compile(r"cannot be determined|not claimable|\bindeterminate\b", re.IGNORECASE)

# A ban that reads as the negative direction of an unsupported claim ("no X
# occurred", "never happened", "isn't present", "not observed"). Anything
# else is treated as the positive direction. Used only to classify
# output_not_contains entries already gated by INDETERMINATE_MARKER_RE, not
# as a general negation check. "not" is included alongside "no" for the same
# reason DENIAL_CUES treats them as equally valid denial forms above.
NEGATION_CUE_RE = re.compile(r"\b(no|not|never|zero|none)\b|n't\b", re.IGNORECASE)

# Skills whose own SKILL.md mandates a fresh subagent dispatch for their
# core judgment steps, and are known (as of issue #584) to need at least one
# fixture declaring expected.requires_fresh_dispatch. A deliberate, narrow
# allowlist rather than a generic "SKILL.md mentions 'fresh subagent
# dispatch'" text scan: that broader phrase also appears in at least one
# other skill's own mandate (executing-a-branch-plan/SKILL.md's Decision
# 12), which issue #584 does not cover -- a text scan would silently start
# failing CI for that skill's own, unrelated fixtures. Extending this set to
# a newly-adopted skill is a deliberate follow-up edit, not automatic.
DISPATCH_MANDATE_SKILLS = frozenset({"evaluating-skill-quality", "battle-testing-a-skill"})


def _is_real_dispatch_declaration(value: object) -> bool:
    """True iff ``value`` (a fixture's ``expected.requires_fresh_dispatch``)
    is a well-formed declaration -- a mapping with a non-empty
    ``tool_names`` list and a ``min_dispatches`` of at least 1 -- not merely
    truthy. A bare truthiness check would let ``requires_fresh_dispatch:
    true`` or ``requires_fresh_dispatch: {min_dispatches: 0}`` silently
    satisfy check 9's coverage requirement while describing no real,
    checkable dispatch expectation (a ``min_dispatches: 0`` fixture would
    even report ``confirmed`` from ``gitapex_check_dispatch_trace.py`` with zero
    observed dispatches, since ``0 &gt;= 0``) -- exactly the kind of vacuous
    gate issue #584 exists to close, reopened one field down.
    ``min_dispatches`` defaults to 1 when omitted, matching
    ``gitapex_check_dispatch_trace.py``'s own CLI default.
    """
    if not isinstance(value, dict):
        return False
    tool_names = value.get("tool_names")
    if not isinstance(tool_names, list) or not tool_names:
        return False
    min_dispatches = value.get("min_dispatches", 1)
    if isinstance(min_dispatches, bool) or not isinstance(min_dispatches, int):
        return False
    return min_dispatches >= 1


# An UPPER_SNAKE_CASE-shaped classification-code token, excluded from the
# cross-task collision check (#270, #473) -- this repository's closed-enum
# classification fixtures deliberately ban sibling labels this shaped, and
# that is a correct design, not the accidental collision the check means to
# catch.
ENUM_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9_]{2,}")

WS_RE = re.compile(r"\s+")
# A word token: alphanumerics, with internal (never trailing) ".", "_", "/",
# or "-" so "gitapex_check_skill_shape.py", "model/effort", and "nine-dimension" stay
# whole while trailing sentence punctuation ("permissions.") is left out.
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*")
HEADING_RE = re.compile(r"^#+\s+(.*)$", re.MULTILINE)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
QUOTED_RE = re.compile(r'"([^"\n]{4,80})"')


class NearAssertion(BaseModel):
    """One ``output_contains_near`` / ``output_not_contains_near`` entry:
    every substring in ``all`` must (or must not, depending which key it
    sits under) co-occur within ``window`` characters of every other, per
    ``gitapex_score_contract.py``'s own ``_near_satisfied`` semantics (see that
    module's docstring). ``window`` defaults to 400, matching
    ``gitapex_score_contract.py``'s own ``_DEFAULT_NEAR_WINDOW``. This linter never
    re-implements that scoring itself -- only
    ``check_unsatisfiable_assertion_pair`` reads ``all``, for its own,
    unrelated contradiction check -- the model exists to capture the
    fixture's real shape, confirmed against every ``output_contains_near``
    entry in this repository's own corpus, which always supplies both keys.
    """

    model_config = ConfigDict(extra="allow")

    all: list[str]
    window: int = 400


class ExpectedBlock(BaseModel):
    """The ``expected:`` block of one task fixture. Only the fields this
    linter itself reads are named here; everything else
    (``expected.classification``, ``expected.repair_count``,
    ``expected.retro_stub_expected``, ``output_not_contains_near``, ...)
    belongs to a sibling script sharing the same fixture files
    (``merge-retrospective``'s own scoring, ``gitapex_run_ablation.py``) and is
    preserved, not rejected, via ``extra="allow"``.

    ``requires_fresh_dispatch`` is deliberately typed ``object | None``,
    not a nested model: whether a given value is a *well-formed*
    declaration is ``_is_real_dispatch_declaration``'s own, separately
    tested judgment (issue #584) -- a bare ``true`` or a
    ``min_dispatches: 0`` is a heuristic finding for that function to
    surface, not a shape this model should reject outright.
    """

    model_config = ConfigDict(extra="allow")

    output_contains: list[str] | None = None
    output_not_contains: list[str] | None = None
    output_icontains: list[str] | None = None
    output_not_icontains: list[str] | None = None
    output_contains_near: list[NearAssertion] | None = None
    exercises: list[str] | None = None
    requires_fresh_dispatch: object | None = None


class InputsBlock(BaseModel):
    """The ``inputs:`` block. ``prompt`` is the only key any fixture in
    this repository's own ``evals/*/tasks/*.yaml`` corpus uses."""

    prompt: str


class TaskFixture(BaseModel):
    """One ``evals/<skill>/tasks/*.yaml`` fixture file's validated shape
    (issue #684). ``id``/``name``/``inputs``/``expected`` are required --
    every fixture in this repository's own corpus provides them;
    ``description``/``tags`` are optional. ``tags`` accepts a bare string
    as well as a list (``tags: adversarial``, forgetting the ``- item``
    list form, is one tag, not an error -- see ``_as_tag_list``).

    Extra top-level keys are rejected (``extra="forbid"``): unlike
    ``expected:``'s own sub-keys, no fixture in this repository's corpus
    ever uses one not named here, so an unexpected top-level key is far
    more likely a typo (e.g. ``expcted:``) than a legitimate field this
    model has not yet learned about.

    ``graders`` (issue #859) is waza's own native task-level mechanism
    (``graders: [{type: text, config: {contains/not_contains/...}}]``,
    schema-validated by ``waza check`` itself) -- this linter does not
    read its contents, so it is typed as opaque ``list[Any]`` purely to
    keep such fixtures from falling into ``_load_fixture_dict``'s
    ValidationError fallback path, which would silently exclude them from
    every other check in this file.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None = None
    tags: str | list[str] | None = None
    inputs: InputsBlock
    expected: ExpectedBlock
    graders: list[Any] | None = None


def _load_fixture_dict(path: Path) -> dict[str, Any]:
    """Parse and validate one fixture file into a plain dict via
    ``TaskFixture`` -- "one validated parse per fixture file" (issue #684)
    in place of this function's own former ``yaml.safe_load(...) or {}``,
    duplicated across every caller that reads fixtures independently of
    ``lint_skill_tasks``. A fixture whose shape ``TaskFixture`` rejects
    (exactly the kind of authoring mistake this linter exists to catch)
    falls back to the bare parsed YAML, unchanged from this function's
    pre-pydantic behavior, so a malformed fixture still surfaces as a
    heuristic finding (e.g. "no well-formed requires_fresh_dispatch
    declared") to its caller instead of crashing the lint pass outright.

    Reading or parsing the file can fail in more ways than a wrong shape:
    a genuine YAML syntax error (``yaml.YAMLError``), a non-UTF-8 byte
    sequence (``UnicodeDecodeError``), or an OS-level failure reading the
    path at all (``OSError`` -- permission denied, a path component too
    long, etc.) -- ``gitapex_gate_retro_title_convention_citation.py``'s own
    file-read loop catches the same ``(OSError, UnicodeDecodeError)`` pair
    for the same reason. None of these have a parsed value to fall back
    to, unlike the wrong-shape case, so they return ``{}`` instead --
    still a heuristic "nothing declared" finding, never an uncaught
    exception (found across two rounds of adversarial review: the first
    round's fix caught only ``yaml.YAMLError``, missing the other two).
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return TaskFixture.model_validate(raw).model_dump()
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    except ValidationError:
        return raw


@dataclass(frozen=True)
class Warning_:
    task: str
    key: str
    value: str
    rule: str
    detail: str
    # Non-blocking warnings (checks 6-7, opt in) are always printed but never
    # flip the exit code -- see the module docstring for why they are too
    # noisy against this repository's real fixtures to gate on.
    blocking: bool = True


def load_corpus(rubric: Path, skill: Path) -> str:
    """A skill's stable text, concatenated. Either file missing is a usage
    error, not a silent empty corpus that would pass everything. Callers
    that pass the same path for both (a skill with no dedicated rubric.md)
    get that file's text once each, which is harmless for substring checks."""
    try:
        return rubric.read_text(encoding="utf-8") + "\n" + skill.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise OSError(f"{rubric} or {skill}: could not decode as UTF-8: {error}") from error


def extract_anchors(corpus: str) -> list[str]:
    """Distinctive, stable rubric wording: heading text, bolded spans, and
    short double-quoted phrases. Bold spans are matched across newlines
    (DOTALL) because the rubric's quoted-guidance bullets wrap several lines
    inside one `**...**`."""
    anchors: list[str] = []
    anchors += (m.group(1).strip() for m in HEADING_RE.finditer(corpus))
    anchors += (" ".join(m.group(1).split()) for m in BOLD_RE.finditer(corpus))
    anchors += (m.group(1).strip() for m in QUOTED_RE.finditer(corpus))
    # Order-preserving dedup; drop empties.
    return [a for a in dict.fromkeys(anchors) if a]


def _content_tokens(text: str) -> list[str]:
    """Lowercased, crudely-singularized content words (stopwords dropped).

    Singularization is a bare trailing-"s" strip -- enough to make
    "permissions" match "permission" for the paraphrase heuristic without a
    stemming dependency; it is intentionally shallow, since a false match
    only produces a human-checked warning, never a silent change.
    """
    out: list[str] = []
    for raw in WORD_RE.findall(text.lower()):
        if raw in STOPWORDS:
            continue
        out.append(raw[:-1] if len(raw) > 3 and raw.endswith("s") else raw)
    return out


def _as_tag_list(value: object) -> list[str]:
    """Coerce a YAML ``tags``-shaped value into a list of strings. A bare
    scalar (``tags: adversarial``, forgetting the ``- item`` list form) is
    one tag, not a sequence of one-character tags. Only ``None``/``str``/
    ``list`` are real, documented ``tags`` shapes (``TaskFixture`` itself
    only accepts these three) -- anything else is coerced the same way a
    bare scalar is, one whole value as one tag, rather than iterated."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def check_case(value: str, anchors: list[str]) -> str | None:
    """Warn when a multi-word assertion matches a rubric anchor
    case-insensitively but with different casing than every anchor it
    matches.

    Scans the whole anchor list before deciding, rather than returning on
    the first loose hit: an exact-case match on ANY anchor clears the
    assertion even when an earlier, differently-cased anchor for the same
    phrase also exists (issue #858). The same taxonomy phrase can
    legitimately appear both in a capitalized heading/bold span (a category
    name) and in a separately documented, deliberately lowercase,
    machine-readable quoted form (a literal field value) within the same
    rubric -- `merge-retrospective/SKILL.md`'s own `Classification:` field
    is exactly this shape. Returning on the first anchor in
    `extract_anchors`'s heading/bold/quoted concatenation order, without
    checking whether a later anchor has the exact case the assertion
    already uses, produced 18 false positives across the committed corpus
    at issue time -- confirmed by checking each flagged assertion string
    against its own skill's SKILL.md by hand."""
    if len(value.split()) < 2:
        return None
    low = value.lower()
    first_mismatch: str | None = None
    for anchor in anchors:
        idx = anchor.lower().find(low)
        if idx < 0:
            continue
        if anchor[idx : idx + len(value)] == value:
            return None
        if first_mismatch is None:
            first_mismatch = anchor
    return first_mismatch


def check_negation(value: str, corpus_flat: str) -> str | None:
    """Warn when the corpus itself negates this phrase, so an
    output_not_contains ban on it would also reject a correct denial.

    ``corpus_flat`` is lowercased with whitespace runs collapsed to single
    spaces, so a denial that wraps across a line ("not a\\n  tenth
    dimension") is still recognized. Callers may pass a corpus extended
    with a fixture's own prompt text (#487) to catch an ad hoc ban invented
    for one fixture, not just phrasing drawn from the skill's stable rubric.
    """
    low = WS_RE.sub(" ", value.lower())
    for cue in DENIAL_CUES:
        if cue + low in corpus_flat:
            return f'"{cue}{value}" appears in the rubric'
    return None


def check_paraphrase(value: str, corpus_flat: str, corpus_tokens: list[str]) -> str | None:
    """Warn when a multi-word assertion is not a corpus substring yet all
    its content words co-occur in a short corpus window -- a likely
    paraphrase of the rubric's exact wording.

    Only fires when the exact (whitespace-flattened, case-insensitive)
    phrase is absent from the corpus: a drift the author could have avoided
    by quoting. A phrase that *is* present verbatim -- even if a stronger
    rubric phrasing exists elsewhere -- is a semantic, not a syntactic,
    choice and is left to the model-judged review rather than flagged here.
    """
    if WS_RE.sub(" ", value.lower()) in corpus_flat:
        return None  # exact (case-insensitive) quote: nothing to drift from
    wanted = set(_content_tokens(value))
    if len(wanted) < 2:
        return None
    window = len(wanted) + WINDOW_SLACK
    for start in range(0, max(0, len(corpus_tokens) - window) + 1):
        if wanted <= set(corpus_tokens[start : start + window]):
            near = " ".join(corpus_tokens[start : start + window])
            return f"content words all appear near: ...{near}..."
    return None


def check_short_word_collision(value: str) -> str | None:
    """Warn when a short, alphabetic output_contains string is a known
    substring of an unrelated common word (#218): see
    ``SHORT_WORD_COLLISIONS``."""
    if len(value) >= 8 or not value.isalpha():
        return None
    hits = SHORT_WORD_COLLISIONS.get(value.lower())
    return hits[0] if hits else None


def check_unsatisfiable_assertion_pair(expected: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Detect assertion pairs across ``output_contains``/``output_icontains``/
    ``output_not_icontains``/``output_contains_near`` that can never jointly
    score 1.0, or that redundantly assert the same casefolded substring
    twice (#628). Returns a list of ``(key, value, rule, detail)`` tuples,
    mirroring ``lint_task``'s other per-value checks.

    See the module docstring's check 5b for the full reasoning, including
    why the mirrored ``output_not_contains``/``output_icontains`` direction
    is deliberately NOT flagged (it is satisfiable, unlike this direction).

    An adversarial code review (issue #628) caught two gaps in this
    function's first draft, both fixed here: (1) ``output_icontains`` and
    ``output_not_icontains`` naming the identical casefolded substring is
    itself an unconditional contradiction (both keys already match
    case-insensitively, so requiring and banning the same folded value can
    never both hold) -- the first draft only built its literal-requirement
    set from ``output_contains``/``output_contains_near``, missing this
    most-direct case entirely; (2) ``output_not_contains`` and
    ``output_not_icontains`` naming the identical casefolded substring is
    redundant the same way the positive-direction pair is (the stronger,
    case-insensitive ban always subsumes the weaker, case-sensitive one on
    that substring) -- the first draft only checked the positive direction.
    """
    contains = [v for v in (expected.get("output_contains") or []) if isinstance(v, str)]
    icontains = [v for v in (expected.get("output_icontains") or []) if isinstance(v, str)]
    not_contains = [v for v in (expected.get("output_not_contains") or []) if isinstance(v, str)]
    not_icontains = [v for v in (expected.get("output_not_icontains") or []) if isinstance(v, str)]
    near_members = [
        v
        for entry in (expected.get("output_contains_near") or [])
        if isinstance(entry, dict)
        for v in (entry.get("all") or [])
        if isinstance(v, str)
    ]

    # Anything that guarantees the substring's casefolded form is present:
    # a literal-presence requirement (output_contains, or a
    # output_contains_near "all" member, which the near-check also
    # requires to be literally present), OR output_icontains itself
    # (which already matches case-insensitively).
    require_casefolded_presence: dict[str, str] = {}
    for value in contains + near_members + icontains:
        require_casefolded_presence.setdefault(value.casefold(), value)
    not_icontains_by_fold: dict[str, str] = {}
    for value in not_icontains:
        not_icontains_by_fold.setdefault(value.casefold(), value)

    findings: list[tuple[str, str, str, str]] = []
    for folded, required in require_casefolded_presence.items():
        banned = not_icontains_by_fold.get(folded)
        if banned is not None:
            findings.append(
                (
                    "output_not_icontains",
                    banned,
                    "unsatisfiable-assertion-pair",
                    f"{required!r} is required (via output_contains/"
                    f"output_contains_near/output_icontains) and {banned!r} is "
                    f"banned case-insensitively for the same substring -- "
                    f"satisfying the requirement guarantees the ban fails, so "
                    f"this fixture can never score 1.0",
                )
            )

    def _redundant_pairs(strong: list[str], weak: list[str], strong_key: str, weak_key: str) -> None:
        strong_by_fold: dict[str, str] = {}
        for value in strong:
            strong_by_fold.setdefault(value.casefold(), value)
        seen: set[str] = set()
        for value in weak:
            folded = value.casefold()
            matched = strong_by_fold.get(folded)
            if matched is not None and folded not in seen:
                seen.add(folded)
                findings.append(
                    (
                        strong_key,
                        matched,
                        "redundant-assertion-pair",
                        f"{matched!r} ({strong_key}) duplicates {weak_key}: "
                        f"{value!r} (same substring, case-insensitively) -- the "
                        f"{strong_key} form alone already covers it",
                    )
                )

    # Same-polarity redundancy, both directions: the case-insensitive form
    # (icontains/not_icontains) alone already covers the case-sensitive
    # form (contains/not_contains) for the identical folded substring.
    _redundant_pairs(icontains, contains, "output_icontains", "output_contains")
    _redundant_pairs(not_icontains, not_contains, "output_not_icontains", "output_not_contains")
    return findings


def classify_ban_direction(value: str) -> str:
    """ "negative" for a ban shaped like "no X occurred" / "never happened" /
    "doesn't apply"; "positive" (the declarative-claim direction) otherwise."""
    return "negative" if NEGATION_CUE_RE.search(value) else "positive"


def check_symmetric_bans(data: dict[str, Any]) -> str | None:
    """Warn when a "claim cannot be determined" fixture (#352) bans an
    unsupported claim in only one direction. Gated on
    ``INDETERMINATE_MARKER_RE`` so this never fires for an ordinary fixture
    that just happens to have only negative-direction bans.

    Exempts a fixture whose own ``output_contains`` requires an ALL-CAPS
    ``INDETERMINATE``-shaped token (e.g. a literal `route_status:
    INDETERMINATE` enum value): that is a closed-enum status field, the
    same design this file's ``ENUM_TOKEN_RE`` already exempts from the
    cross-task collision check, not the natural-language "claim cannot be
    determined" pattern this check means to catch. Without this, a
    fixture like `battle-testing-a-skill`'s `codex-unknown-model-fail-
    closed.yaml` -- whose description explains stopping "as INDETERMINATE"
    as a report field, and whose bans are unrelated report-field names,
    not claim directions -- would be wrongly held to this rule.
    """
    haystack = " ".join(str(data.get(k) or "") for k in ("id", "name", "description"))
    haystack += " " + " ".join(_as_tag_list(data.get("tags")))
    if not INDETERMINATE_MARKER_RE.search(haystack):
        return None
    expected = data.get("expected") or {}
    positives = [v for v in (expected.get("output_contains") or []) if isinstance(v, str)]
    positives += [v for v in (expected.get("output_icontains") or []) if isinstance(v, str)]
    if any(ENUM_TOKEN_RE.fullmatch(v) and "indeterminate" in v.lower() for v in positives):
        return None
    bans = [v for v in (expected.get("output_not_contains") or []) if isinstance(v, str)]
    bans += [v for v in (expected.get("output_not_icontains") or []) if isinstance(v, str)]
    if not bans:
        return (
            "claims the underlying fact cannot be determined but declares "
            "no output_not_contains bans in either direction"
        )
    directions = {classify_ban_direction(b) for b in bans}
    if directions == {"negative"}:
        return 'bans only the negative-claim direction ("no X occurred") -- add a positive-claim ban ("X occurred") too'
    if directions == {"positive"}:
        return 'bans only the positive-claim direction ("X occurred") -- add a negative-claim ban ("no X occurred") too'
    return None


def check_prompt_echo(value: str, prompt_flat: str) -> str | None:
    """Off by default (#191) -- warn when a multi-word output_contains
    string is also a literal substring of the fixture's own prompt. See the
    module docstring for why this is a non-blocking note, not a gate."""
    if len(value.split()) < 2:
        return None
    value_flat = WS_RE.sub(" ", value.lower())
    if value_flat in prompt_flat:
        return "appears verbatim in the fixture's own prompt"
    return None


def check_cross_task_collision(task_name: str, value: str, positive_index: dict[str, set[str]]) -> str | None:
    """Off by default (#270, #473) -- warn when an output_not_contains ban
    exactly matches an output_contains string another task in the same
    suite requires. See the module docstring for why this is a
    non-blocking note, not a gate, and for the enum-token exclusion."""
    if ENUM_TOKEN_RE.search(value):
        return None
    low = value.lower()
    for other_name, positives in positive_index.items():
        if other_name != task_name and low in positives:
            return other_name
    return None


def check_adversarial_coverage(
    skill_name: str, tasks_dir: Path, claim_text: str, *, task_data: dict[Path, dict[str, Any]] | None = None
) -> str | None:
    """Blocking, discovery-mode only (#473): a skill whose own docs claim
    adversarial coverage but whose tasks/ directory has no fixture tagged
    ``adversarial``.

    ``task_data``, if the caller already parsed every task YAML under
    ``tasks_dir`` (as ``lint_all_skills`` does via ``lint_skill_tasks``),
    is reused instead of re-globbing and re-parsing every file here.
    """
    if not re.search(r"\badversarial\b", claim_text, re.IGNORECASE):
        return None
    if task_data is None:
        task_data = {p: _load_fixture_dict(p) for p in tasks_dir.glob("*.yaml")}
    for data in task_data.values():
        tags = {t.strip().lower() for t in _as_tag_list(data.get("tags"))}
        if "adversarial" in tags:
            return None
    return (
        f'{skill_name}\'s own docs claim adversarial coverage but no fixture under {tasks_dir} is tagged "adversarial"'
    )


def check_dispatch_declaration_coverage(
    skill_name: str, tasks_dir: Path, *, task_data: dict[Path, dict[str, Any]] | None = None
) -> str | None:
    """Blocking, discovery-mode only (#584): a skill in
    ``DISPATCH_MANDATE_SKILLS`` whose ``tasks/`` directory has zero fixtures
    declaring a well-formed ``expected.requires_fresh_dispatch`` value (see
    ``_is_real_dispatch_declaration``) -- the fixture-level assertion this
    skill's own ``eval-status.md`` previously disclosed as entirely missing
    (final-output-text-only assertions cannot confirm a fresh subagent
    dispatch actually happened for the skill's own mandated Procedure
    steps).

    ``task_data``, if the caller already parsed every task YAML under
    ``tasks_dir`` (as ``lint_all_skills`` does), is reused instead of
    re-globbing and re-parsing every file here -- same convention as
    ``check_adversarial_coverage``.
    """
    if skill_name not in DISPATCH_MANDATE_SKILLS:
        return None
    if task_data is None:
        task_data = {p: _load_fixture_dict(p) for p in tasks_dir.glob("*.yaml")}
    for data in task_data.values():
        expected = data.get("expected")
        if isinstance(expected, dict) and _is_real_dispatch_declaration(expected.get("requires_fresh_dispatch")):
            return None
    return (
        f"{skill_name}'s own SKILL.md mandates a fresh subagent dispatch for its "
        f"core judgment steps, but no fixture under {tasks_dir} declares a "
        f"well-formed expected.requires_fresh_dispatch (issue #584)"
    )


def lint_task(
    task_path: Path,
    fixture: TaskFixture,
    anchors: list[str],
    corpus_flat: str,
    corpus_tokens: list[str],
    positive_index: dict[str, set[str]],
    *,
    check_prompt_echo_enabled: bool,
    check_cross_task_enabled: bool,
) -> list[Warning_]:
    # ``fixture`` is already validated by ``TaskFixture`` (one parse per
    # fixture file, done by the caller) -- every list below is guaranteed
    # ``list[str]`` by the model, so the per-item ``isinstance`` filtering
    # this function used to do at each of these sites is no longer needed.
    expected = fixture.expected
    prompt_flat = WS_RE.sub(" ", fixture.inputs.prompt.lower())
    # #487: broaden the negation-trap detector beyond corpus-sourced denial
    # phrases to also catch an ad hoc ban this fixture's own prompt denies.
    negation_haystack = corpus_flat + " " + prompt_flat
    name = task_path.name
    warnings: list[Warning_] = []

    for value in expected.output_contains or []:
        anchor = check_case(value, anchors)
        if anchor:
            warnings.append(
                Warning_(
                    name,
                    "output_contains",
                    value,
                    "case-sensitivity",
                    f"matches rubric anchor {anchor!r} with different casing",
                )
            )
        drift = check_paraphrase(value, corpus_flat, corpus_tokens)
        if drift:
            warnings.append(
                Warning_(name, "output_contains", value, "paraphrase-drift", f"not a rubric substring but {drift}")
            )
        collision = check_short_word_collision(value)
        if collision:
            warnings.append(
                Warning_(
                    name,
                    "output_contains",
                    value,
                    "short-word-collision",
                    f"short and alphabetic; also a bare substring of the common word {collision!r}",
                )
            )
        if check_prompt_echo_enabled:
            echo = check_prompt_echo(value, prompt_flat)
            if echo:
                warnings.append(Warning_(name, "output_contains", value, "prompt-echo", echo, blocking=False))

    # output_icontains (#628): checks 3-4 (paraphrase drift, short-word
    # collision) apply the same way regardless of case-sensitivity. Check 1
    # (case-sensitivity) is deliberately NOT run here -- see the module
    # docstring's check 5b for why a casing difference is expected, not a
    # defect, for a key whose whole point is to ignore case.
    for value in expected.output_icontains or []:
        drift = check_paraphrase(value, corpus_flat, corpus_tokens)
        if drift:
            warnings.append(
                Warning_(name, "output_icontains", value, "paraphrase-drift", f"not a rubric substring but {drift}")
            )
        collision = check_short_word_collision(value)
        if collision:
            warnings.append(
                Warning_(
                    name,
                    "output_icontains",
                    value,
                    "short-word-collision",
                    f"short and alphabetic; also a bare substring of the common word {collision!r}",
                )
            )

    for value in expected.output_not_contains or []:
        neg = check_negation(value, negation_haystack)
        if neg:
            warnings.append(
                Warning_(
                    name,
                    "output_not_contains",
                    value,
                    "negation-trap",
                    f"banning it also rejects a correct denial -- {neg}",
                )
            )
        if check_cross_task_enabled:
            collider = check_cross_task_collision(name, value, positive_index)
            if collider:
                warnings.append(
                    Warning_(
                        name,
                        "output_not_contains",
                        value,
                        "cross-task-collision",
                        f"exactly bans a string that {collider} requires via output_contains",
                        blocking=False,
                    )
                )

    # output_not_icontains (#628): check 2 (negation trap) applies the same
    # way regardless of case-sensitivity.
    for value in expected.output_not_icontains or []:
        neg = check_negation(value, negation_haystack)
        if neg:
            warnings.append(
                Warning_(
                    name,
                    "output_not_icontains",
                    value,
                    "negation-trap",
                    f"banning it also rejects a correct denial -- {neg}",
                )
            )

    symmetric = check_symmetric_bans(fixture.model_dump())
    if symmetric:
        warnings.append(Warning_(name, "output_not_contains", fixture.id, "symmetric-ban", symmetric))

    for key, value, rule, detail in check_unsatisfiable_assertion_pair(expected.model_dump()):
        warnings.append(Warning_(name, key, value, rule, detail))

    return warnings


def lint_skill_tasks(
    task_paths: list[Path],
    corpus: str,
    *,
    check_prompt_echo_enabled: bool = False,
    check_cross_task_enabled: bool = False,
) -> tuple[list[Warning_], dict[Path, dict[str, Any]]]:
    """Lint one skill's task set against its own, already-loaded anchor
    corpus (a caller reads it once via ``load_corpus`` and passes the text
    here, rather than this function re-reading the same files).

    Each fixture file is parsed and validated against ``TaskFixture``
    (issue #684). A malformed fixture -- a YAML *syntax* error, a
    non-UTF-8 byte sequence, an OS-level read failure, or YAML that
    parses fine but has the wrong shape (a missing required field, a
    wrong-typed value, an unrecognized top-level key) -- is reported as
    its own blocking ``Warning_`` naming the offending file, and excluded
    from the rest of this skill's linting -- it does NOT abort linting
    for any other fixture, in this skill or any other. Two successive
    rounds of adversarial review found this guard catching only part of
    that set: the first let ``pydantic.ValidationError`` propagate
    unguarded (crashing the whole multi-skill run on any wrong-shape
    fixture); the fix for that caught ``ValidationError`` but not
    ``yaml.YAMLError`` (still crashing on broken YAML syntax); a second
    round then found ``UnicodeDecodeError``/``OSError`` (a non-UTF-8
    fixture, or another per-file read failure) still uncaught too. All
    four are caught here now -- the same ``(OSError, UnicodeDecodeError)``
    pair ``_load_fixture_dict`` and ``gate_retro_title_convention_
    citation.py``'s own file-read loop already catch for the identical
    reason, plus this module's own YAML/shape pair.

    Returns ``(warnings, task_data)``: ``task_data`` is each successfully
    validated task path's fixture, re-serialized via ``model_dump()``, so
    a caller linting many skills (``lint_all_skills``) can reuse it for
    the adversarial/dispatch-declaration-coverage checks instead of
    re-parsing. A path excluded above is absent from ``task_data`` too.
    """
    anchors = extract_anchors(corpus)
    corpus_flat = WS_RE.sub(" ", corpus.lower())
    corpus_tokens = _content_tokens(corpus)

    warnings: list[Warning_] = []
    fixtures: dict[Path, TaskFixture] = {}
    for p in task_paths:
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            fixtures[p] = TaskFixture.model_validate(raw)
        except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
            warnings.append(
                Warning_(
                    p.name,
                    "(fixture)",
                    "(top-level shape)",
                    "fixture-shape",
                    f"{p}: malformed fixture, excluded from linting: {exc}",
                )
            )

    positive_index = {
        p.name: {v.lower() for v in (fixture.expected.output_contains or [])} for p, fixture in fixtures.items()
    }

    for path, fixture in fixtures.items():
        warnings.extend(
            lint_task(
                path,
                fixture,
                anchors,
                corpus_flat,
                corpus_tokens,
                positive_index,
                check_prompt_echo_enabled=check_prompt_echo_enabled,
                check_cross_task_enabled=check_cross_task_enabled,
            )
        )
    task_data = {p: fixture.model_dump() for p, fixture in fixtures.items()}
    return warnings, task_data


def discover_skills(evals_root: Path, skills_root: Path) -> list[str]:
    """Every skill name with both a non-empty ``evals/<name>/tasks/*.yaml``
    directory and a ``skills/<name>/SKILL.md`` (#296). Sorted for a stable,
    reviewable report order."""
    names: list[str] = []
    if not evals_root.is_dir():
        return names
    for tasks_dir in sorted(evals_root.glob("*/tasks")):
        name = tasks_dir.parent.name
        if not any(tasks_dir.glob("*.yaml")):
            continue
        if (skills_root / name / "SKILL.md").is_file():
            names.append(name)
    return names


def _skill_corpus_paths(skills_root: Path, name: str) -> tuple[Path, Path]:
    """A skill's own (rubric, skill) anchor-corpus paths: its dedicated
    ``references/rubric.md`` if it has one, else its own ``SKILL.md`` for
    both -- the convention this repository's own docs already use when
    linting a skill with no dedicated rubric (e.g. `merge-retrospective`)."""
    skill_md = skills_root / name / "SKILL.md"
    rubric_md = skills_root / name / "references" / "rubric.md"
    return (rubric_md if rubric_md.is_file() else skill_md), skill_md


def _skill_claim_text(skills_root: Path, evals_root: Path, name: str) -> str:
    parts = []
    skill_md = skills_root / name / "SKILL.md"
    eval_status = evals_root / name / "eval-status.md"
    if skill_md.is_file():
        try:
            parts.append(skill_md.read_text(encoding="utf-8"))
        except UnicodeDecodeError as error:
            raise OSError(f"{skill_md}: could not decode as UTF-8: {error}") from error
    if eval_status.is_file():
        try:
            parts.append(eval_status.read_text(encoding="utf-8"))
        except UnicodeDecodeError as error:
            raise OSError(f"{eval_status}: could not decode as UTF-8: {error}") from error
    return "\n".join(parts)


def lint_all_skills(
    evals_root: Path,
    skills_root: Path,
    *,
    check_prompt_echo_enabled: bool = False,
    check_cross_task_enabled: bool = False,
    skill_names: list[str] | None = None,
) -> list[Warning_]:
    """Broadened default scope (#296): lint every discovered skill's own
    task set against its own anchor corpus, plus the discovery-mode-only
    adversarial-coverage check (#473).

    ``skill_names``, if the caller already ran ``discover_skills`` (as
    ``main`` does, to fail fast on an empty repo before linting), is reused
    instead of walking evals/ and skills/ a second time.
    """
    warnings: list[Warning_] = []
    names = skill_names if skill_names is not None else discover_skills(evals_root, skills_root)
    for name in names:
        tasks_dir = evals_root / name / "tasks"
        rubric_path, skill_path = _skill_corpus_paths(skills_root, name)
        task_paths = sorted(tasks_dir.glob("*.yaml"))
        corpus = load_corpus(rubric_path, skill_path)

        skill_warnings, task_data = lint_skill_tasks(
            task_paths,
            corpus,
            check_prompt_echo_enabled=check_prompt_echo_enabled,
            check_cross_task_enabled=check_cross_task_enabled,
        )
        warnings.extend(replace(w, task=f"{name}/{w.task}") for w in skill_warnings)

        claim_text = _skill_claim_text(skills_root, evals_root, name)
        coverage = check_adversarial_coverage(name, tasks_dir, claim_text, task_data=task_data)
        if coverage:
            warnings.append(Warning_(name, "(skill)", "(tasks directory)", "adversarial-coverage", coverage))
        dispatch_coverage = check_dispatch_declaration_coverage(name, tasks_dir, task_data=task_data)
        if dispatch_coverage:
            warnings.append(
                Warning_(name, "(skill)", "(tasks directory)", "dispatch-declaration-coverage", dispatch_coverage)
            )
    return warnings


def format_report(warnings: list[Warning_]) -> str:
    blocking = [w for w in warnings if w.blocking]
    notes = [w for w in warnings if not w.blocking]
    lines: list[str] = []
    if not blocking:
        if notes:
            # Non-blocking notes exist below -- "well-formed" would
            # contradict them, so stay neutral about blocking status only.
            lines.append("0 blocking warning(s).")
        else:
            lines.append("0 warnings: every fixture assertion is well-formed.")
    else:
        lines.append(f"{len(blocking)} warning(s):")
        for w in blocking:
            lines.append(f"  {w.task} [{w.rule}] {w.key}: {w.value!r}")
            lines.append(f"      {w.detail}")
    if notes:
        lines.append(f"{len(notes)} non-blocking note(s):")
        for w in notes:
            lines.append(f"  {w.task} [{w.rule}] {w.key}: {w.value!r}")
            lines.append(f"      {w.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint eval-fixture substring assertions (read-only).")
    parser.add_argument(
        "--tasks-glob",
        default=None,
        help="Glob for one skill's task YAMLs. Omit to auto-discover every "
        "skill with an evals/<name>/tasks/*.yaml directory and a "
        "matching skills/<name>/SKILL.md (issue #296).",
    )
    parser.add_argument("--rubric", default=None, help=f"Only used with --tasks-glob. Default: {DEFAULT_RUBRIC}")
    parser.add_argument("--skill", default=None, help=f"Only used with --tasks-glob. Default: {DEFAULT_SKILL}")
    parser.add_argument(
        "--check-prompt-echo",
        action="store_true",
        default=False,
        help="Opt in to the prompt-echo check (#191). Non-blocking: never "
        "affects the exit code. Off by default -- see the module "
        "docstring for why it is noisy against this repository's own "
        "corpus.",
    )
    parser.add_argument(
        "--check-cross-task",
        action="store_true",
        default=False,
        help="Opt in to the cross-task collision check (#270, #473). "
        "Non-blocking: never affects the exit code. Off by default -- "
        "see the module docstring for why it is noisy against this "
        "repository's own corpus.",
    )
    args = parser.parse_args(argv)

    try:
        if args.tasks_glob is None:
            evals_root, skills_root = Path("evals"), Path("skills")
            names = discover_skills(evals_root, skills_root)
            if not names:
                print("error: no skill directories discovered under evals/ and skills/", file=sys.stderr)
                return 2
            warnings = lint_all_skills(
                evals_root,
                skills_root,
                skill_names=names,
                check_prompt_echo_enabled=args.check_prompt_echo,
                check_cross_task_enabled=args.check_cross_task,
            )
        else:
            rubric = Path(args.rubric) if args.rubric else Path(DEFAULT_RUBRIC)
            skill = Path(args.skill) if args.skill else Path(DEFAULT_SKILL)
            try:
                corpus = load_corpus(rubric, skill)
            except OSError as exc:
                print(f"error: could not read the anchor corpus: {exc}", file=sys.stderr)
                return 2
            # PTH207 waived: the argument is a whole user-supplied pattern
            # string of unknown root (absolute or relative, any depth).
            # Path.glob() takes a pattern relative to an already-known base,
            # so it cannot express this without re-splitting the pattern by
            # hand -- glob.glob is the correct tool, not a lapse.
            task_paths = sorted(Path(p) for p in globlib.glob(args.tasks_glob))  # noqa: PTH207
            if not task_paths:
                print(f"error: no task files matched: {args.tasks_glob}", file=sys.stderr)
                return 2
            warnings, _ = lint_skill_tasks(
                task_paths,
                corpus,
                check_prompt_echo_enabled=args.check_prompt_echo,
                check_cross_task_enabled=args.check_cross_task,
            )
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        print(f"error: could not lint fixtures: {exc}", file=sys.stderr)
        return 2

    print(format_report(warnings))
    return 1 if any(w.blocking for w in warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
