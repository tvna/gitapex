"""Report which of a skill's own numbered dimensions and named cross-cutting
axes its committed eval corpus actually cites, and which it does not.

Neither `evaluating-skill-quality` nor `battle-testing-a-skill` measures
this today: `evaluating-skill-quality`'s Dimension 8 checks named-trigger-
scenario-vs-fixture coverage (a narrower, different claim), and
`battle-testing-a-skill`'s Dimension 14 grades only whether an adversarial
regression corpus exists and grows. A `fable` subagent built this coverage
map by hand for `evaluating-deterministic-gate-quality`'s corpus in one
review round; this script makes that repeatable instead of a one-off.

Two dimension-heading conventions exist across this repository's own
skills and are both recognized: a Markdown heading with a leading number
("## 8. Behavioural evidence", `evaluating-skill-quality/references/
rubric.md` and `battle-testing-a-skill/references/adversarial-
dimensions.md`), and a bold numbered-list item inline in prose
("1. **Deny path is...**", `evaluating-deterministic-gate-quality/
references/dimensions.md`). No skill currently mixes both conventions in
one file, so the heading style is tried first and the list style only as a
fallback when it finds nothing. Cross-cutting axes are discovered from a
skill's own `SKILL.md` via its `### Axis: <name>` heading convention.

Coverage is citation-based, not semantic: a task fixture "covers" a
dimension if its own text names it near the word "dimension"/"dimensions"
(singular, hyphenated, or list/plural forms -- "dimension 9", "dimension-9",
and "dimensions 9, 11, and 12" are all recognized, since this repository's
own fixtures and eval-status.md prose use all three), and an axis if its
short name (the text before a `" / "` separator, if any -- axis headings
compound a primary name with a qualifier, e.g. "Reproducibility /
Domain-coverage", but fixtures typically cite only the primary name)
appears as a whole word/phrase, in `id`/`name`/`description`/`tags`/
`inputs.prompt`. This is a heuristic, not a proof, the same way
`lint_fixture_assertions.py`'s case/negation/paraphrase checks are: a
fixture can substantively exercise a dimension's concept without ever
writing its number (a false "uncovered"), and a passing contrastive
mention ("...unlike dimension 1, this fails dimension 2...") counts as
coverage for both numbers even though only one is really under test (a
false "covered"). Treat the report as a starting point for a human or
reviewing skill to confirm, not a final verdict.

This tool is general-purpose -- it has been run against both
`evaluating-deterministic-gate-quality`'s and `evaluating-skill-quality`'s
own real corpora -- but a CI-enforced disclosure-sync gate currently exists
for only the former
(`tests/test_evaluating_deterministic_gate_quality_dimension_coverage.py`).
Wiring an equivalent gate for `evaluating-skill-quality` or
`battle-testing-a-skill`'s own corpus is a disclosed, deliberate follow-up,
not done here: each skill's own `eval-status.md` is independently
maintained narrative content deserving its own dedicated pass rather than
a rushed addition riding on this change. Consuming this tool's *output* as
evidence (the rubric/reference-doc bullets added alongside this script) is
not the same claim as *enforcing* it in CI for those two skills' own
corpora -- do not conflate the two when reading this module's history.

Usage:
  python3 check_dimension_coverage.py --skill-dir DIR --tasks-glob GLOB
                                       [--dimensions-file PATH]

Exit code: always 0 -- this is a report tool, like `check_skill_shape.py`'s
per-line PASS/FAIL output. Enforcement (a fixed set of dimensions must stay
disclosed as gaps) lives in a separate pytest gate that imports this
module directly, not in this script's own exit code. 2 on a malformed or
unreadable input (a fixture, dimensions file, or SKILL.md this script
cannot parse into the shape it expects).
"""
from __future__ import annotations

import argparse
import glob as globlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError, field_validator

DEFAULT_DIMENSIONS_FILENAME = "references/dimensions.md"

_DIMENSION_HEADING_RE = re.compile(r"^#{1,6}\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
# DOTALL: several dimensions' bold title wraps onto a second physical line
# before its closing "**" (e.g. dimension 1 in evaluating-deterministic-gate-
# quality's own dimensions.md) -- a MULTILINE-only "." would stop at the
# first newline and silently drop that dimension from discovery entirely.
_DIMENSION_LIST_RE = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*", re.MULTILINE | re.DOTALL)
_AXIS_RE = re.compile(r"^###\s+Axis:\s+(.+?)\s*$", re.MULTILINE)

# Citation scan: every occurrence of "dimension"/"dimensions" (case-
# insensitive), then every digit run within DIM_CITATION_WINDOW characters
# or the current sentence, whichever ends first, is treated as a cited
# number. This single shared scan (rather than one compiled regex per
# dimension number) is what lets "dimensions 9, 11, and 12" attribute a
# citation to three different numbers from one mention, and lets
# "dimension-9" match without a literal space before the number.
_DIMENSION_WORD_RE = re.compile(r"\bdimensions?\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+")
_SENTENCE_END_RE = re.compile(r"[.!?\n]")
DIM_CITATION_WINDOW = 60


@dataclass(frozen=True)
class CoverageReport:
    dimensions: dict[str, str]  # number -> title
    axes: dict[str, str]  # short key -> full heading text
    dimension_hits: dict[str, list[str]] = field(default_factory=dict)  # number -> fixture files
    axis_hits: dict[str, list[str]] = field(default_factory=dict)  # short key -> fixture files

    @property
    def uncovered_dimensions(self) -> list[str]:
        return sorted(
            (n for n in self.dimensions if n not in self.dimension_hits),
            key=int,
        )

    @property
    def uncovered_axes(self) -> list[str]:
        return sorted(k for k in self.axes if k not in self.axis_hits)


def discover_dimensions(dimensions_file: Path) -> dict[str, str]:
    """Numbered dimensions declared in ``dimensions_file``, as {number: title}.

    An empty dict means the file is absent or declares none this way --
    not every skill enumerates dimensions this way, so that is not an error.
    """
    if not dimensions_file.is_file():
        return {}
    text = dimensions_file.read_text(encoding="utf-8")
    found = {m.group(1): m.group(2).strip() for m in _DIMENSION_HEADING_RE.finditer(text)}
    if found:
        return found
    return {
        m.group(1): " ".join(m.group(2).split())
        for m in _DIMENSION_LIST_RE.finditer(text)
    }


def discover_axes(skill_md: Path) -> dict[str, str]:
    """Cross-cutting axes declared in ``skill_md`` via ``### Axis: <name>``,
    as {short_key: full_heading_text}. ``short_key`` is the text before a
    ``" / "`` separator, if the heading has one -- fixtures in this
    repository cite an axis's primary name, not its full compound heading.

    First heading wins on a short-key collision (two axes sharing the same
    primary name before " / "), matching ``discover_dimensions``'s own
    first-match-wins rule for a duplicate number -- explicit rather than
    silently overwriting a prior axis with a later one of the same name.
    """
    if not skill_md.is_file():
        return {}
    text = skill_md.read_text(encoding="utf-8")
    axes: dict[str, str] = {}
    for m in _AXIS_RE.finditer(text):
        full = m.group(1).strip()
        short = full.split(" / ", 1)[0].strip()
        axes.setdefault(short, full)
    return axes


def _as_text_list(value: object) -> list[str]:
    """Coerce a YAML ``tags``-shaped value into a list of strings.

    A fixture author who writes ``tags: reproducibility`` (a bare scalar,
    forgetting the ``- item`` list form) hands this a plain ``str``, which
    is iterable character-by-character -- silently destroying the citation
    the tag was meant to carry. Treat a bare string as one tag, not a
    sequence of one-character tags.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def _fixture_text(data: object) -> str:
    """Every field a citation could plausibly live in, concatenated.

    ``data`` is whatever ``yaml.safe_load`` returned for a task file; a
    well-formed fixture is a mapping, but a malformed one (a bare scalar or
    list at the top level) is handed through as-is and raises here rather
    than being silently coerced -- callers see a clear ``AttributeError``/
    ``TypeError`` they can catch and report, not a fixture treated as
    citing nothing.
    """
    inputs = data.get("inputs") or {}
    parts = [
        str(data.get("id", "")),
        str(data.get("name", "")),
        str(data.get("description", "")),
        " ".join(_as_text_list(data.get("tags"))),
        str(inputs.get("prompt", "")),
    ]
    return " ".join(parts).lower()


def _cited_dimension_numbers(haystack: str) -> set[str]:
    """Every dimension number cited near the word "dimension"/"dimensions"
    in ``haystack``: singular ("dimension 9"), hyphenated ("dimension-9"),
    and list/plural forms ("dimensions 9, 11, and 12") are all recognized
    by collecting every digit run that follows the word, up to
    ``DIM_CITATION_WINDOW`` characters or the end of the sentence,
    whichever comes first.
    """
    found: set[str] = set()
    for word_match in _DIMENSION_WORD_RE.finditer(haystack):
        tail = haystack[word_match.end():word_match.end() + DIM_CITATION_WINDOW]
        end_match = _SENTENCE_END_RE.search(tail)
        if end_match:
            tail = tail[:end_match.start()]
        found.update(_NUMBER_RE.findall(tail))
    return found


def discover_citations(
    tasks_glob: str, dimensions: dict[str, str], axes: dict[str, str]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """For each task file matching ``tasks_glob``, which dimension numbers
    and axis short keys it cites. Returns (dimension_hits, axis_hits), each
    mapping the item key to the list of citing fixture filenames, in the
    same (sorted-by-path) order the files were visited in.
    """
    dimension_hits: dict[str, list[str]] = {}
    axis_hits: dict[str, list[str]] = {}
    # Word-boundary anchored so an axis short key never matches as a bare
    # substring of an unrelated word (e.g. "compatibility awareness" inside
    # "incompatibility awareness").
    axis_res = {k: re.compile(rf"\b{re.escape(k.lower())}\b") for k in axes}

    # PTH207 waived: the argument is a whole user-supplied pattern
    # string of unknown root (absolute or relative, any depth).
    # Path.glob() takes a pattern relative to an already-known base,
    # so it cannot express this without re-splitting the pattern by
    # hand -- glob.glob is the correct tool, not a lapse.
    for path in sorted(Path(p) for p in globlib.glob(tasks_glob)):  # noqa: PTH207
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        haystack = _fixture_text(data)
        cited_numbers = _cited_dimension_numbers(haystack)
        for number in dimensions:
            if number in cited_numbers:
                dimension_hits.setdefault(number, []).append(path.name)
        for key, pattern in axis_res.items():
            if pattern.search(haystack):
                axis_hits.setdefault(key, []).append(path.name)

    return dimension_hits, axis_hits


def compute_coverage(
    skill_dir: Path, tasks_glob: str, dimensions_file: Path | None = None
) -> CoverageReport:
    dim_path = dimensions_file or (skill_dir / DEFAULT_DIMENSIONS_FILENAME)
    dimensions = discover_dimensions(dim_path)
    axes = discover_axes(skill_dir / "SKILL.md")
    dimension_hits, axis_hits = discover_citations(tasks_glob, dimensions, axes)
    return CoverageReport(dimensions, axes, dimension_hits, axis_hits)


def _item_line(key: str, hits: list[str] | None, label: str) -> str:
    status = f"covered by {', '.join(hits)}" if hits else "UNCOVERED"
    return f"  {label} -- {status}"


def format_report(report: CoverageReport) -> str:
    lines: list[str] = []
    lines.append(
        f"Dimensions: {len(report.dimension_hits)}/{len(report.dimensions)} cited"
    )
    for number in sorted(report.dimensions, key=int):
        label = f"{number}. {report.dimensions[number]}"
        lines.append(_item_line(number, report.dimension_hits.get(number), label))

    lines.append(f"Axes: {len(report.axis_hits)}/{len(report.axes)} cited")
    for key in sorted(report.axes):
        label = f"{key} ({report.axes[key]})"
        lines.append(_item_line(key, report.axis_hits.get(key), label))

    if report.uncovered_dimensions:
        lines.append(f"Uncovered dimensions: {', '.join(report.uncovered_dimensions)}")
    if report.uncovered_axes:
        lines.append(f"Uncovered axes: {', '.join(report.uncovered_axes)}")
    return "\n".join(lines)


class _CheckDimensionCoverageArgs(BaseModel):
    """Validates the parsed CLI namespace's string values immediately after
    ``parser.parse_args()``. No hand-validation existed here before this
    model (argparse's own ``required=True`` only guarantees presence, not a
    non-blank value) -- rejecting a blank ``--skill-dir``/``--tasks-glob``
    is new, additive validation: previously an empty string would silently
    reach ``compute_coverage`` as an unusable path/glob rather than being
    reported as a malformed input. ``--dimensions-file`` keeps its existing
    "omitted means absent, not an error" semantics when ``None``."""

    skill_dir: str
    tasks_glob: str
    dimensions_file: str | None = None

    @field_validator("skill_dir")
    @classmethod
    def _skill_dir_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("--skill-dir must not be blank")
        return value

    @field_validator("tasks_glob")
    @classmethod
    def _tasks_glob_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("--tasks-glob must not be blank")
        return value

    @field_validator("dimensions_file")
    @classmethod
    def _dimensions_file_must_not_be_blank_if_given(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("--dimensions-file must not be blank")
        return value


def _validation_error_message(exc: ValidationError) -> str:
    """The first error's original message, unwrapped from pydantic's own
    "Value error, " prefix -- keeps this script's own plain-text error
    convention rather than pydantic's own formatted error text."""
    error = exc.errors()[0]
    ctx = error.get("ctx") or {}
    original = ctx.get("error")
    if isinstance(original, Exception):
        return str(original)
    return str(error["msg"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report dimension/axis coverage of an eval corpus (read-only)."
    )
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--tasks-glob", required=True)
    parser.add_argument("--dimensions-file", default=None)
    args = parser.parse_args(argv)

    try:
        validated_args = _CheckDimensionCoverageArgs(
            skill_dir=args.skill_dir,
            tasks_glob=args.tasks_glob,
            dimensions_file=args.dimensions_file,
        )
    except ValidationError as exc:
        print(f"error: {_validation_error_message(exc)}", file=sys.stderr)
        return 2

    skill_dir = Path(validated_args.skill_dir)
    dimensions_file = Path(validated_args.dimensions_file) if validated_args.dimensions_file else None
    try:
        report = compute_coverage(skill_dir, validated_args.tasks_glob, dimensions_file)
    except (OSError, yaml.YAMLError, AttributeError, TypeError) as exc:
        print(f"error: could not compute coverage: {exc}", file=sys.stderr)
        return 2

    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
