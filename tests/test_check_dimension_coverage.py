"""Tests for the dimension/axis coverage-report tool.

Unit tests run each discovery/citation function against a small synthetic
corpus so they are self-contained; one integration test runs the tool
against the real `evaluating-deterministic-gate-quality` skill and its real
committed corpus, pinning the exact covered/uncovered sets so a future
fixture change that silently drops a citation (or a future dimension added
to `dimensions.md` with no fixture written for it) is caught here, not only
by the separate disclosure-sync gate that consumes this module's output.
"""
from pathlib import Path

import check_dimension_coverage as C

REPO_ROOT = Path(__file__).resolve().parents[1]

# A synthetic dimensions.md exercising both heading conventions this
# repository's own skills use: a Markdown heading with a leading number,
# and a bold numbered-list item whose title wraps a line before its
# closing "**" (the historical bug this script's own regex once missed).
_DIMENSIONS_MD = (
    "# Dimensions\n\n"
    "1. **Deny path is non-bypassable, not silently downgraded to\n"
    "   advisory.** A gate meant to block an action can fail to block it.\n"
    "2. **Dual-signal deny.** Signaled through every channel.\n"
)

_SKILL_MD = (
    "# skill\n\n"
    "### Axis: Compatibility awareness\n\n"
    "A warning-only axis.\n\n"
    "### Axis: Reproducibility / Domain-coverage\n\n"
    "Asks in how many domains a policy is realized.\n"
)


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _write_task(tmp_path, filename, **fields):
    lines = []
    for key in ("id", "name"):
        if key in fields:
            lines.append(f"{key}: {fields[key]}")
    if "description" in fields:
        lines.append(f"description: {fields['description']}")
    if "tags" in fields:
        tags = fields["tags"]
        if isinstance(tags, str):
            lines.append(f"tags: {tags}")  # a bare scalar, not a list -- see below
        else:
            lines.append("tags:")
            lines += [f"  - {t}" for t in tags]
    lines.append("inputs:")
    lines.append("  prompt: |")
    lines.append(f"    {fields.get('prompt', 'p')}")
    (tmp_path / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---- discover_dimensions ----

def test_discover_dimensions_handles_multiline_bold_title(tmp_path):
    path = _write(tmp_path, "dimensions.md", _DIMENSIONS_MD)
    found = C.discover_dimensions(path)
    assert set(found) == {"1", "2"}
    assert "advisory" in found["1"]
    assert "\n" not in found["1"]  # wrapped title normalized to one line


def test_discover_dimensions_heading_style(tmp_path):
    path = _write(tmp_path, "rubric.md", "## 8. Behavioural evidence\n\nBody.\n")
    found = C.discover_dimensions(path)
    assert found == {"8": "Behavioural evidence"}


def test_discover_dimensions_missing_file_is_empty_not_error(tmp_path):
    assert C.discover_dimensions(tmp_path / "nope.md") == {}


# ---- discover_axes ----

def test_discover_axes_short_key_drops_qualifier(tmp_path):
    path = _write(tmp_path, "SKILL.md", _SKILL_MD)
    axes = C.discover_axes(path)
    assert axes == {
        "Compatibility awareness": "Compatibility awareness",
        "Reproducibility": "Reproducibility / Domain-coverage",
    }


def test_discover_axes_missing_file_is_empty_not_error(tmp_path):
    assert C.discover_axes(tmp_path / "nope.md") == {}


def test_discover_axes_short_key_collision_is_first_match_wins(tmp_path):
    text = (
        "### Axis: Reproducibility / Domain-coverage\n\nFirst.\n\n"
        "### Axis: Reproducibility / Something-else\n\nSecond.\n"
    )
    path = _write(tmp_path, "SKILL.md", text)
    axes = C.discover_axes(path)
    assert axes == {"Reproducibility": "Reproducibility / Domain-coverage"}


# ---- discover_citations ----

def test_discover_citations_finds_dimension_in_prompt_not_only_description(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="unrelated text",
                prompt="Give me the verdict for dimension 2 on this gate.")
    dims = {"1": "x", "2": "y"}
    dim_hits, _ = C.discover_citations(str(tasks / "*.yaml"), dims, {})
    assert dim_hits == {"2": ["a.yaml"]}


def test_discover_citations_dimension_number_is_word_bounded(tmp_path):
    # "dimension 1" must not match inside a fixture that only cites
    # "dimension 12" -- a substring match without a word boundary would
    # wrongly report dimension 1 as covered.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="see dimension 12 for detail")
    dims = {"1": "x", "12": "y"}
    dim_hits, _ = C.discover_citations(str(tasks / "*.yaml"), dims, {})
    assert dim_hits == {"12": ["a.yaml"]}
    assert "1" not in dim_hits


def test_discover_citations_axis_short_key_case_insensitive(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="exercises the COMPATIBILITY AWARENESS axis")
    _, axis_hits = C.discover_citations(str(tasks / "*.yaml"), {}, {"Compatibility awareness": "Compatibility awareness"})
    assert axis_hits == {"Compatibility awareness": ["a.yaml"]}


def test_discover_citations_axis_short_key_is_word_bounded(tmp_path):
    # "compatibility awareness" must not match as a bare substring of
    # "incompatibility awareness" -- an unrelated phrase that happens to
    # contain it.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="this hook has an incompatibility awareness gap")
    _, axis_hits = C.discover_citations(
        str(tasks / "*.yaml"), {}, {"Compatibility awareness": "Compatibility awareness"}
    )
    assert axis_hits == {}


def test_discover_citations_dimension_plural_and_list_form(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="this exercises dimensions 9, 11, and 12 together")
    dims = {"9": "x", "11": "y", "12": "z", "13": "w"}
    dim_hits, _ = C.discover_citations(str(tasks / "*.yaml"), dims, {})
    assert set(dim_hits) == {"9", "11", "12"}
    assert "13" not in dim_hits


def test_discover_citations_dimension_hyphenated_form(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="see dimension-9 for detail")
    dims = {"9": "x"}
    dim_hits, _ = C.discover_citations(str(tasks / "*.yaml"), dims, {})
    assert dim_hits == {"9": ["a.yaml"]}


def test_discover_citations_dimension_number_stops_at_sentence_end(tmp_path):
    # A number belonging to a later, unrelated sentence must not be
    # attributed to an earlier "dimension" mention just because it falls
    # within the raw character window.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(
        tasks, "a.yaml",
        description="this exercises dimension 9. Unrelated -- see issue 12 for context.",
    )
    dims = {"9": "x", "12": "y"}
    dim_hits, _ = C.discover_citations(str(tasks / "*.yaml"), dims, {})
    assert dim_hits == {"9": ["a.yaml"]}


def test_discover_citations_scalar_tags_not_char_iterated(tmp_path):
    # "tags: reproducibility" (a bare scalar, not a "- item" list) must be
    # treated as one tag, not iterated character-by-character.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="unrelated", tags="reproducibility")
    _, axis_hits = C.discover_citations(
        str(tasks / "*.yaml"), {}, {"Reproducibility": "Reproducibility / Domain-coverage"}
    )
    assert axis_hits == {"Reproducibility": ["a.yaml"]}


# ---- compute_coverage / CoverageReport ----

def test_compute_coverage_uncovered_lists_are_sorted_numerically(tmp_path):
    skill_dir = tmp_path / "skill"
    (skill_dir / "references").mkdir(parents=True)
    _write(skill_dir, "SKILL.md", "# skill\n")
    _write(skill_dir / "references", "dimensions.md",
           "1. **A.**\n2. **B.**\n10. **C.**\n")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="dimension 2")

    report = C.compute_coverage(skill_dir, str(tasks / "*.yaml"))
    assert report.uncovered_dimensions == ["1", "10"]  # numeric, not lexical, order


# ---- integration: the real corpus ----

# ---- format_report / main (CLI surface) ----

def _skill_dir(tmp_path, dimensions_md, skill_md):
    skill_dir = tmp_path / "skill"
    (skill_dir / "references").mkdir(parents=True)
    _write(skill_dir / "references", "dimensions.md", dimensions_md)
    _write(skill_dir, "SKILL.md", skill_md)
    return skill_dir


def test_format_report_lists_covered_and_uncovered(tmp_path):
    skill_dir = _skill_dir(
        tmp_path, "1. **A.**\n2. **B.**\n",
        "# skill\n\n### Axis: Reproducibility / Domain-coverage\n\n### Axis: Blast-radius\n",
    )
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="dimension 1, exercises the Reproducibility axis")

    report = C.compute_coverage(skill_dir, str(tasks / "*.yaml"))
    text = C.format_report(report)
    assert "Dimensions: 1/2 cited" in text
    assert "covered by a.yaml" in text
    assert "UNCOVERED" in text
    assert "Uncovered dimensions: 2" in text
    assert "Axes: 1/2 cited" in text
    assert "Uncovered axes: Blast-radius" in text


def test_main_prints_report_and_exits_zero(tmp_path, capsys):
    skill_dir = _skill_dir(tmp_path, "1. **A.**\n", "# skill\n")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="dimension 1")

    rc = C.main(["--skill-dir", str(skill_dir), "--tasks-glob", str(tasks / "*.yaml")])
    assert rc == 0
    assert "Dimensions: 1/1 cited" in capsys.readouterr().out


def test_main_reports_error_and_exits_two_on_malformed_fixture_shape(tmp_path):
    # A task file that parses to a non-mapping top level (a bare scalar
    # string here) must not crash main() with an uncaught AttributeError.
    skill_dir = _skill_dir(tmp_path, "1. **A.**\n", "# skill\n")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "bad.yaml").write_text("just a scalar string\n", encoding="utf-8")

    rc = C.main(["--skill-dir", str(skill_dir), "--tasks-glob", str(tasks / "*.yaml")])
    assert rc == 2


# ---- new pydantic-model CLI-arg validation (added by issue #684's T8) ----
# argparse's own required=True only guarantees presence, not a non-blank
# value -- these three cases were not rejected before this task's pydantic
# wrap existed (a blank --skill-dir/--tasks-glob/--dimensions-file would
# have silently reached compute_coverage as an unusable path/glob instead).


def test_main_rejects_blank_skill_dir_returns_2(tmp_path, capsys):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="dimension 1")

    rc = C.main(["--skill-dir", "   ", "--tasks-glob", str(tasks / "*.yaml")])

    assert rc == 2
    assert "error: --skill-dir must not be blank" in capsys.readouterr().err


def test_main_rejects_blank_tasks_glob_returns_2(tmp_path, capsys):
    skill_dir = _skill_dir(tmp_path, "1. **A.**\n", "# skill\n")

    rc = C.main(["--skill-dir", str(skill_dir), "--tasks-glob", "  "])

    assert rc == 2
    assert "error: --tasks-glob must not be blank" in capsys.readouterr().err


def test_main_rejects_blank_dimensions_file_returns_2(tmp_path, capsys):
    skill_dir = _skill_dir(tmp_path, "1. **A.**\n", "# skill\n")
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, "a.yaml", description="dimension 1")

    rc = C.main(
        [
            "--skill-dir", str(skill_dir),
            "--tasks-glob", str(tasks / "*.yaml"),
            "--dimensions-file", "   ",
        ]
    )

    assert rc == 2
    assert "error: --dimensions-file must not be blank" in capsys.readouterr().err


def test_real_corpus_coverage_matches_expected_snapshot():
    skill_dir = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality"
    tasks_glob = str(
        REPO_ROOT / "evals" / "evaluating-deterministic-gate-quality" / "tasks" / "*.yaml"
    )
    report = C.compute_coverage(skill_dir, tasks_glob)
    assert len(report.dimensions) == 20
    assert report.uncovered_dimensions == ["9", "11", "12", "13", "14", "16", "17", "20"]
    assert report.uncovered_axes == []
