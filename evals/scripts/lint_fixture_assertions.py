"""Lint the substring assertions in eval fixtures across this repository's
skills.

`score_contract.py` scores a fixture correctly *given* well-formed
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
     phrase) but with different casing than the anchor. The anchor's own
     casing is the stable one to quote. (Historical: `output_contains:
     ["blind spot"]` vs. the `## Blind spot pass` heading.)
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

Scope (#296): with no `--tasks-glob`, the default is now every skill
directory with both a `skills/<name>/SKILL.md` and an
`evals/<name>/tasks/*.yaml` directory -- not only
`evaluating-skill-quality`'s own fixtures. Passing `--tasks-glob`
explicitly keeps the original single-skill behavior (with `--rubric` /
`--skill` naming that one skill's anchor corpus), unchanged, for scripts
and docs that already invoke it that way.

These are heuristics, not proofs: each flags a *likely* authoring mistake
for a human to confirm, the same way `check_skill_shape.py` flags shape,
not maturity. This broadened scope does not itself fix any pre-existing
fixture defects it surfaces in skills other than `evaluating-skill-
quality` -- that is separate follow-on triage (see issue #516's own
stated non-goal). Standard library only except PyYAML (already a dev
dependency, used by the repo's other fixture tooling); the fixtures are
YAML, so a real parser is warranted rather than a hand-rolled subset.

Usage:
  python3 lint_fixture_assertions.py [--tasks-glob GLOB]
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

import yaml

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
STOPWORDS = frozenset({
    "a", "an", "the", "or", "and", "of", "to", "in", "is", "are", "for",
    "on", "with", "not", "no", "as", "at", "by", "be", "it", "this", "that",
})

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
INDETERMINATE_MARKER_RE = re.compile(
    r"cannot be determined|not claimable|\bindeterminate\b", re.IGNORECASE)

# A ban that reads as the negative direction of an unsupported claim ("no X
# occurred", "never happened", "isn't present"). Anything else is treated as
# the positive direction. Used only to classify output_not_contains entries
# already gated by INDETERMINATE_MARKER_RE, not as a general negation check.
NEGATION_CUE_RE = re.compile(r"\b(no|never|zero|none)\b|n't\b",
                              re.IGNORECASE)

# An UPPER_SNAKE_CASE-shaped classification-code token, excluded from the
# cross-task collision check (#270, #473) -- this repository's closed-enum
# classification fixtures deliberately ban sibling labels this shaped, and
# that is a correct design, not the accidental collision the check means to
# catch.
ENUM_TOKEN_RE = re.compile(r"[A-Z][A-Z0-9_]{2,}")

WS_RE = re.compile(r"\s+")
# A word token: alphanumerics, with internal (never trailing) ".", "_", "/",
# or "-" so "check_skill_shape.py", "model/effort", and "nine-dimension" stay
# whole while trailing sentence punctuation ("permissions.") is left out.
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*")
HEADING_RE = re.compile(r"^#+\s+(.*)$", re.MULTILINE)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
QUOTED_RE = re.compile(r'"([^"\n]{4,80})"')


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
    return rubric.read_text(encoding="utf-8") + "\n" + skill.read_text(encoding="utf-8")


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
    one tag, not a sequence of one-character tags."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def check_case(value: str, anchors: list[str]) -> str | None:
    """Warn when a multi-word assertion matches a rubric anchor
    case-insensitively but with different casing than the anchor."""
    if len(value.split()) < 2:
        return None
    low = value.lower()
    for anchor in anchors:
        idx = anchor.lower().find(low)
        if idx >= 0 and anchor[idx:idx + len(value)] != value:
            return anchor
    return None


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


def check_paraphrase(value: str, corpus_flat: str,
                     corpus_tokens: list[str]) -> str | None:
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
        if wanted <= set(corpus_tokens[start:start + window]):
            near = " ".join(corpus_tokens[start:start + window])
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


def classify_ban_direction(value: str) -> str:
    """"negative" for a ban shaped like "no X occurred" / "never happened" /
    "doesn't apply"; "positive" (the declarative-claim direction) otherwise."""
    return "negative" if NEGATION_CUE_RE.search(value) else "positive"


def check_symmetric_bans(data: dict) -> str | None:
    """Warn when a "claim cannot be determined" fixture (#352) bans an
    unsupported claim in only one direction. Gated on
    ``INDETERMINATE_MARKER_RE`` so this never fires for an ordinary fixture
    that just happens to have only negative-direction bans."""
    haystack = " ".join(str(data.get(k) or "") for k in ("id", "name", "description"))
    haystack += " " + " ".join(_as_tag_list(data.get("tags")))
    if not INDETERMINATE_MARKER_RE.search(haystack):
        return None
    expected = data.get("expected") or {}
    bans = [v for v in (expected.get("output_not_contains") or []) if isinstance(v, str)]
    if not bans:
        return ("claims the underlying fact cannot be determined but declares "
                "no output_not_contains bans in either direction")
    directions = {classify_ban_direction(b) for b in bans}
    if directions == {"negative"}:
        return ('bans only the negative-claim direction ("no X occurred") -- '
                'add a positive-claim ban ("X occurred") too')
    if directions == {"positive"}:
        return ('bans only the positive-claim direction ("X occurred") -- '
                'add a negative-claim ban ("no X occurred") too')
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


def check_cross_task_collision(task_name: str, value: str,
                                positive_index: dict[str, set[str]]) -> str | None:
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


def check_adversarial_coverage(skill_name: str, tasks_dir: Path,
                                claim_text: str) -> str | None:
    """Blocking, discovery-mode only (#473): a skill whose own docs claim
    adversarial coverage but whose tasks/ directory has no fixture tagged
    ``adversarial``."""
    if not re.search(r"\badversarial\b", claim_text, re.IGNORECASE):
        return None
    for path in tasks_dir.glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        tags = {t.strip().lower() for t in _as_tag_list(data.get("tags"))}
        if "adversarial" in tags:
            return None
    return (f"{skill_name}'s own docs claim adversarial coverage but no fixture "
            f"under {tasks_dir} is tagged \"adversarial\"")


def lint_task(task_path: Path, data: dict, anchors: list[str], corpus_flat: str,
              corpus_tokens: list[str], positive_index: dict[str, set[str]], *,
              check_prompt_echo_enabled: bool,
              check_cross_task_enabled: bool) -> list[Warning_]:
    expected = data.get("expected") or {}
    prompt = (data.get("inputs") or {}).get("prompt") or ""
    prompt_flat = WS_RE.sub(" ", prompt.lower())
    # #487: broaden the negation-trap detector beyond corpus-sourced denial
    # phrases to also catch an ad hoc ban this fixture's own prompt denies.
    negation_haystack = corpus_flat + " " + prompt_flat
    name = task_path.name
    warnings: list[Warning_] = []

    for value in expected.get("output_contains") or []:
        if not isinstance(value, str):
            continue
        anchor = check_case(value, anchors)
        if anchor:
            warnings.append(Warning_(
                name, "output_contains", value, "case-sensitivity",
                f"matches rubric anchor {anchor!r} with different casing"))
        drift = check_paraphrase(value, corpus_flat, corpus_tokens)
        if drift:
            warnings.append(Warning_(
                name, "output_contains", value, "paraphrase-drift",
                f"not a rubric substring but {drift}"))
        collision = check_short_word_collision(value)
        if collision:
            warnings.append(Warning_(
                name, "output_contains", value, "short-word-collision",
                f"short and alphabetic; also a bare substring of the common "
                f"word {collision!r}"))
        if check_prompt_echo_enabled:
            echo = check_prompt_echo(value, prompt_flat)
            if echo:
                warnings.append(Warning_(
                    name, "output_contains", value, "prompt-echo", echo,
                    blocking=False))

    for value in expected.get("output_not_contains") or []:
        if not isinstance(value, str):
            continue
        neg = check_negation(value, negation_haystack)
        if neg:
            warnings.append(Warning_(
                name, "output_not_contains", value, "negation-trap",
                f"banning it also rejects a correct denial -- {neg}"))
        if check_cross_task_enabled:
            collider = check_cross_task_collision(name, value, positive_index)
            if collider:
                warnings.append(Warning_(
                    name, "output_not_contains", value, "cross-task-collision",
                    f"exactly bans a string that {collider} requires via "
                    f"output_contains", blocking=False))

    symmetric = check_symmetric_bans(data)
    if symmetric:
        warnings.append(Warning_(
            name, "output_not_contains", str(data.get("id", name)),
            "symmetric-ban", symmetric))

    return warnings


def lint_skill_tasks(task_paths: list[Path], rubric_path: Path, skill_path: Path, *,
                     check_prompt_echo_enabled: bool = False,
                     check_cross_task_enabled: bool = False) -> list[Warning_]:
    """Lint one skill's task set against its own anchor corpus."""
    corpus = load_corpus(rubric_path, skill_path)
    anchors = extract_anchors(corpus)
    corpus_flat = WS_RE.sub(" ", corpus.lower())
    corpus_tokens = _content_tokens(corpus)

    task_data = {p: (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) for p in task_paths}
    positive_index = {
        p.name: {v.lower() for v in ((d.get("expected") or {}).get("output_contains") or [])
                 if isinstance(v, str)}
        for p, d in task_data.items()
    }

    warnings: list[Warning_] = []
    for path, data in task_data.items():
        warnings.extend(lint_task(
            path, data, anchors, corpus_flat, corpus_tokens, positive_index,
            check_prompt_echo_enabled=check_prompt_echo_enabled,
            check_cross_task_enabled=check_cross_task_enabled))
    return warnings


def discover_skills(evals_root: Path, skills_root: Path) -> list[str]:
    """Every skill name with both a non-empty ``evals/<name>/tasks/*.yaml``
    directory and a ``skills/<name>/SKILL.md`` (#296). Sorted for a stable,
    reviewable report order."""
    names = []
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
        parts.append(skill_md.read_text(encoding="utf-8"))
    if eval_status.is_file():
        parts.append(eval_status.read_text(encoding="utf-8"))
    return "\n".join(parts)


def lint_all_skills(evals_root: Path, skills_root: Path, *,
                    check_prompt_echo_enabled: bool = False,
                    check_cross_task_enabled: bool = False) -> list[Warning_]:
    """Broadened default scope (#296): lint every discovered skill's own
    task set against its own anchor corpus, plus the discovery-mode-only
    adversarial-coverage check (#473)."""
    warnings: list[Warning_] = []
    for name in discover_skills(evals_root, skills_root):
        tasks_dir = evals_root / name / "tasks"
        rubric_path, skill_path = _skill_corpus_paths(skills_root, name)
        task_paths = sorted(tasks_dir.glob("*.yaml"))

        skill_warnings = lint_skill_tasks(
            task_paths, rubric_path, skill_path,
            check_prompt_echo_enabled=check_prompt_echo_enabled,
            check_cross_task_enabled=check_cross_task_enabled)
        warnings.extend(replace(w, task=f"{name}/{w.task}") for w in skill_warnings)

        claim_text = _skill_claim_text(skills_root, evals_root, name)
        coverage = check_adversarial_coverage(name, tasks_dir, claim_text)
        if coverage:
            warnings.append(Warning_(
                name, "(skill)", "(tasks directory)", "adversarial-coverage",
                coverage))
    return warnings


def format_report(warnings: list[Warning_]) -> str:
    blocking = [w for w in warnings if w.blocking]
    notes = [w for w in warnings if not w.blocking]
    lines: list[str] = []
    if not blocking:
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
    parser = argparse.ArgumentParser(
        description="Lint eval-fixture substring assertions (read-only).")
    parser.add_argument(
        "--tasks-glob", default=None,
        help="Glob for one skill's task YAMLs. Omit to auto-discover every "
             "skill with an evals/<name>/tasks/*.yaml directory and a "
             "matching skills/<name>/SKILL.md (issue #296).")
    parser.add_argument("--rubric", default=None,
                        help=f"Only used with --tasks-glob. Default: {DEFAULT_RUBRIC}")
    parser.add_argument("--skill", default=None,
                        help=f"Only used with --tasks-glob. Default: {DEFAULT_SKILL}")
    parser.add_argument(
        "--check-prompt-echo", action="store_true", default=False,
        help="Opt in to the prompt-echo check (#191). Non-blocking: never "
             "affects the exit code. Off by default -- see the module "
             "docstring for why it is noisy against this repository's own "
             "corpus.")
    parser.add_argument(
        "--check-cross-task", action="store_true", default=False,
        help="Opt in to the cross-task collision check (#270, #473). "
             "Non-blocking: never affects the exit code. Off by default -- "
             "see the module docstring for why it is noisy against this "
             "repository's own corpus.")
    args = parser.parse_args(argv)

    try:
        if args.tasks_glob is None:
            evals_root, skills_root = Path("evals"), Path("skills")
            if not discover_skills(evals_root, skills_root):
                print("error: no skill directories discovered under evals/ "
                      "and skills/", file=sys.stderr)
                return 2
            warnings = lint_all_skills(
                evals_root, skills_root,
                check_prompt_echo_enabled=args.check_prompt_echo,
                check_cross_task_enabled=args.check_cross_task)
        else:
            rubric = Path(args.rubric) if args.rubric else Path(DEFAULT_RUBRIC)
            skill = Path(args.skill) if args.skill else Path(DEFAULT_SKILL)
            try:
                load_corpus(rubric, skill)  # fail fast on an unreadable corpus
            except OSError as exc:
                print(f"error: could not read the anchor corpus: {exc}", file=sys.stderr)
                return 2
            task_paths = sorted(Path(p) for p in globlib.glob(args.tasks_glob))
            if not task_paths:
                print(f"error: no task files matched: {args.tasks_glob}", file=sys.stderr)
                return 2
            warnings = lint_skill_tasks(
                task_paths, rubric, skill,
                check_prompt_echo_enabled=args.check_prompt_echo,
                check_cross_task_enabled=args.check_cross_task)
    except (OSError, yaml.YAMLError) as exc:
        print(f"error: could not lint fixtures: {exc}", file=sys.stderr)
        return 2

    print(format_report(warnings))
    return 1 if any(w.blocking for w in warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
