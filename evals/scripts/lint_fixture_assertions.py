"""Lint the substring assertions in evaluating-skill-quality eval fixtures.

`score_contract.py` scores a fixture correctly *given* well-formed
assertions; nothing else checks whether the assertions themselves are
well-formed. PR #150 hit the same class of assertion bug four times -- a
case-sensitive `output_contains` against text the rubric prescribes in a
different case, a bare `output_not_contains` phrase that also matches a
correct *denial* of itself, and an `output_contains` that paraphrased the
rubric instead of quoting its stable wording. Each is a fixture-authoring
defect a deterministic pass can catch before a gate re-run or an external
reviewer has to. This script is that pass.

It reads the reviewing skill's own stable text (its `rubric.md` and
`SKILL.md`) as the anchor corpus and, for every
`output_contains` / `output_not_contains` string in each task YAML, runs:

  1. Case-sensitivity -- the assertion's lowercased form appears inside a
     distinctive rubric anchor (a heading, a bolded span, or a quoted
     phrase) but with different casing than the anchor. The anchor's own
     casing is the stable one to quote. (Historical: `output_contains:
     ["blind spot"]` vs. the `## Blind spot pass` heading.)
  2. Negation trap -- an `output_not_contains` phrase that the corpus
     itself uses under a denial cue ("not a ...", "never ...", "no ..."),
     so a correct review echoing that phrasing would contain the banned
     substring and false-fail. (Historical: banning `"tenth dimension"`
     false-fails "not a tenth dimension".)
  3. Paraphrase drift -- a multi-word `output_contains` that is not a
     substring of the corpus, yet all of whose content words appear
     together in a short corpus window: the author almost certainly meant
     to quote the rubric's exact wording. (Historical: `"hook or
     permission"` vs. the rubric's `"hooks and permissions"`.)

These are heuristics, not proofs: each flags a *likely* authoring mistake
for a human to confirm, the same way `check_skill_shape.py` flags shape,
not maturity. Standard library only except PyYAML (already a dev
dependency, used by the repo's other fixture tooling); the fixtures are
YAML, so a real parser is warranted rather than a hand-rolled subset.

Usage:
  python3 lint_fixture_assertions.py [--tasks-glob GLOB]
                                     [--rubric PATH] [--skill PATH]

Exit code: 0 if no warning, 1 if any assertion is flagged, 2 on bad usage
or unreadable inputs.
"""
from __future__ import annotations

import argparse
import glob as globlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# The reviewing skill's own stable text, relative to the repo root. These are
# the anchor corpus: the wording a fixture that means to quote the rubric
# should quote. Overridable on the CLI so the script is not pinned to one
# checkout layout.
DEFAULT_RUBRIC = "skills/evaluating-skill-quality/references/rubric.md"
DEFAULT_SKILL = "skills/evaluating-skill-quality/SKILL.md"
DEFAULT_TASKS_GLOB = "evals/evaluating-skill-quality/tasks/*.yaml"

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


def load_corpus(rubric: Path, skill: Path) -> str:
    """The reviewing skill's stable text, concatenated. Either file missing
    is a usage error, not a silent empty corpus that would pass everything."""
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
    dimension") is still recognized.
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


def lint_task(task_path: Path, anchors: list[str], corpus_flat: str,
              corpus_tokens: list[str]) -> list[Warning_]:
    data = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
    expected = data.get("expected") or {}
    warnings: list[Warning_] = []
    name = task_path.name

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

    for value in expected.get("output_not_contains") or []:
        if not isinstance(value, str):
            continue
        neg = check_negation(value, corpus_flat)
        if neg:
            warnings.append(Warning_(
                name, "output_not_contains", value, "negation-trap",
                f"banning it also rejects a correct denial -- {neg}"))
    return warnings


def format_report(warnings: list[Warning_]) -> str:
    if not warnings:
        return "0 warnings: every fixture assertion is well-formed."
    lines = [f"{len(warnings)} warning(s):"]
    for w in warnings:
        lines.append(f"  {w.task} [{w.rule}] {w.key}: {w.value!r}")
        lines.append(f"      {w.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint eval-fixture substring assertions (read-only).")
    parser.add_argument("--tasks-glob", default=DEFAULT_TASKS_GLOB)
    parser.add_argument("--rubric", default=DEFAULT_RUBRIC)
    parser.add_argument("--skill", default=DEFAULT_SKILL)
    args = parser.parse_args(argv)

    try:
        corpus = load_corpus(Path(args.rubric), Path(args.skill))
    except OSError as exc:
        print(f"error: could not read the anchor corpus: {exc}", file=sys.stderr)
        return 2

    anchors = extract_anchors(corpus)
    corpus_flat = WS_RE.sub(" ", corpus.lower())
    corpus_tokens = _content_tokens(corpus)

    task_paths = sorted(Path(p) for p in globlib.glob(args.tasks_glob))
    if not task_paths:
        print(f"error: no task files matched: {args.tasks_glob}", file=sys.stderr)
        return 2

    warnings: list[Warning_] = []
    try:
        for path in task_paths:
            warnings.extend(
                lint_task(path, anchors, corpus_flat, corpus_tokens))
    except (OSError, yaml.YAMLError) as exc:
        print(f"error: could not lint fixtures: {exc}", file=sys.stderr)
        return 2

    print(format_report(warnings))
    return 1 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
