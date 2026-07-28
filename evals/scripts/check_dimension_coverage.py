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
references/dimensions.md`). Cross-cutting axes are discovered from a
skill's own `SKILL.md` via its `### Axis: <name>` heading convention.

Coverage is citation-based, not semantic: a task fixture "covers" a
dimension if its own text names it (`"dimension N"`, case-insensitive,
anywhere in `id`/`name`/`description`/`tags`/`inputs.prompt`), and an axis
if its short name (the text before a `" / "` separator, if any -- axis
headings compound a primary name with a qualifier, e.g. "Reproducibility /
Domain-coverage", but fixtures typically cite only the primary name)
appears the same way. This is a heuristic, not a proof, the same way
`lint_fixture_assertions.py`'s case/negation/paraphrase checks are: a
fixture can substantively exercise a dimension's concept without ever
writing its number (a false "uncovered"), and a passing contrastive
mention ("...unlike dimension 1, this fails dimension 2...") counts as
coverage for both numbers even though only one is really under test (a
false "covered"). Treat the report as a starting point for a human or
reviewing skill to confirm, not a final verdict.

Usage:
  python3 check_dimension_coverage.py --skill-dir DIR --tasks-glob GLOB
                                       [--dimensions-file PATH]

Exit code: always 0 -- this is a report tool, like `check_skill_shape.py`'s
per-line PASS/FAIL output. Enforcement (a fixed set of dimensions must stay
disclosed as gaps) lives in a separate pytest gate that imports this
module directly, not in this script's own exit code.
"""
from __future__ import annotations

import argparse
import glob as globlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_DIMENSIONS_FILENAME = "references/dimensions.md"

# Two dimension-heading conventions, tried in order; both are merged (first
# match per number wins) since a file could in principle mix them, even
# though no current skill does.
_DIMENSION_HEADING_RE = re.compile(r"^#{1,6}\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
# DOTALL: several dimensions' bold title wraps onto a second physical line
# before its closing "**" (e.g. dimension 1 in evaluating-deterministic-gate-
# quality's own dimensions.md) -- a MULTILINE-only "." would stop at the
# first newline and silently drop that dimension from discovery entirely.
_DIMENSION_LIST_RE = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*", re.MULTILINE | re.DOTALL)
_AXIS_RE = re.compile(r"^###\s+Axis:\s+(.+?)\s*$", re.MULTILINE)


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
    found: dict[str, str] = {}
    for m in _DIMENSION_HEADING_RE.finditer(text):
        found.setdefault(m.group(1), m.group(2).strip())
    for m in _DIMENSION_LIST_RE.finditer(text):
        found.setdefault(m.group(1), " ".join(m.group(2).split()))
    return found


def discover_axes(skill_md: Path) -> dict[str, str]:
    """Cross-cutting axes declared in ``skill_md`` via ``### Axis: <name>``,
    as {short_key: full_heading_text}. ``short_key`` is the text before a
    ``" / "`` separator, if the heading has one -- fixtures in this
    repository cite an axis's primary name, not its full compound heading.
    """
    if not skill_md.is_file():
        return {}
    text = skill_md.read_text(encoding="utf-8")
    axes: dict[str, str] = {}
    for m in _AXIS_RE.finditer(text):
        full = m.group(1).strip()
        short = full.split(" / ", 1)[0].strip()
        axes[short] = full
    return axes


def _fixture_text(data: dict) -> str:
    """Every field a citation could plausibly live in, concatenated."""
    inputs = data.get("inputs") or {}
    parts = [
        str(data.get("id", "")),
        str(data.get("name", "")),
        str(data.get("description", "")),
        " ".join(str(t) for t in (data.get("tags") or [])),
        str(inputs.get("prompt", "")),
    ]
    return " ".join(parts).lower()


def discover_citations(
    tasks_glob: str, dimensions: dict[str, str], axes: dict[str, str]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """For each task file matching ``tasks_glob``, which dimension numbers
    and axis short keys it cites. Returns (dimension_hits, axis_hits), each
    mapping the item key to the sorted list of citing fixture filenames.
    """
    dimension_hits: dict[str, list[str]] = {}
    axis_hits: dict[str, list[str]] = {}
    dim_res = {n: re.compile(rf"\bdimension\s+{re.escape(n)}\b") for n in dimensions}
    axis_res = {k: re.compile(re.escape(k.lower())) for k in axes}

    for path in sorted(Path(p) for p in globlib.glob(tasks_glob)):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        haystack = _fixture_text(data)
        for number, pattern in dim_res.items():
            if pattern.search(haystack):
                dimension_hits.setdefault(number, []).append(path.name)
        for key, pattern in axis_res.items():
            if pattern.search(haystack):
                axis_hits.setdefault(key, []).append(path.name)

    for hits in (dimension_hits, axis_hits):
        for key in hits:
            hits[key].sort()
    return dimension_hits, axis_hits


def compute_coverage(
    skill_dir: Path, tasks_glob: str, dimensions_file: Path | None = None
) -> CoverageReport:
    dim_path = dimensions_file or (skill_dir / DEFAULT_DIMENSIONS_FILENAME)
    dimensions = discover_dimensions(dim_path)
    axes = discover_axes(skill_dir / "SKILL.md")
    dimension_hits, axis_hits = discover_citations(tasks_glob, dimensions, axes)
    return CoverageReport(dimensions, axes, dimension_hits, axis_hits)


def format_report(report: CoverageReport) -> str:
    lines: list[str] = []
    lines.append(
        f"Dimensions: {len(report.dimension_hits)}/{len(report.dimensions)} cited"
    )
    for number in sorted(report.dimensions, key=int):
        title = report.dimensions[number]
        hits = report.dimension_hits.get(number)
        status = f"covered by {', '.join(hits)}" if hits else "UNCOVERED"
        lines.append(f"  {number}. {title} -- {status}")

    lines.append(f"Axes: {len(report.axis_hits)}/{len(report.axes)} cited")
    for key in sorted(report.axes):
        hits = report.axis_hits.get(key)
        status = f"covered by {', '.join(hits)}" if hits else "UNCOVERED"
        lines.append(f"  {key} ({report.axes[key]}) -- {status}")

    if report.uncovered_dimensions:
        lines.append(f"Uncovered dimensions: {', '.join(report.uncovered_dimensions)}")
    if report.uncovered_axes:
        lines.append(f"Uncovered axes: {', '.join(report.uncovered_axes)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report dimension/axis coverage of an eval corpus (read-only)."
    )
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--tasks-glob", required=True)
    parser.add_argument("--dimensions-file", default=None)
    args = parser.parse_args(argv)

    skill_dir = Path(args.skill_dir)
    dimensions_file = Path(args.dimensions_file) if args.dimensions_file else None
    try:
        report = compute_coverage(skill_dir, args.tasks_glob, dimensions_file)
    except (OSError, yaml.YAMLError) as exc:
        print(f"error: could not compute coverage: {exc}", file=sys.stderr)
        return 2

    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
